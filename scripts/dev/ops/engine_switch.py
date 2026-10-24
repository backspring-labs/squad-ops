#!/usr/bin/env python3
"""Switch the Spark's inference engine between Ollama and TensorFold, failing closed (SIP-0111 §5.6, #2199).

Both engines are containers (#2249): Ollama is the deploy's ``ollama`` service, TensorFold is started here
from a pinned recipe (``infra/tensorfold/recipes/*.yaml``). Only one is ever resident.

    engine_switch.py to-tensorfold RECIPE   the switch, steps 1-7; any failure restores Ollama
    engine_switch.py to-ollama              restoration: TensorFold stopped and released, then Ollama
    engine_switch.py restore                the same, for the memory watchdog after it killed TensorFold:
                                            no refusal for work on the box, nothing done if Ollama serves
    engine_switch.py status                 what is resident, and the memory

The steps (§5.6):
1. Hold the box: no run running, queued or paused, and no campaign open. With Ollama stopped the runtime
   cannot read the box, so every launch is refused until Ollama is back (§24an).
2. Nothing to drain: step 1 refuses a box with work on it.
3. Stop the old engine.
4. Confirm the release: no GPU compute process resident, MemAvailable >= 90 GiB.
5. Start TensorFold from the recipe.
6. Authenticate and verify: the served id, the window (``/tokenize``'s ``max_model_len``) and the recipe's
   own command line; MemAvailable >= 16 GiB after the load.
7. One healthy generation; then the clients move, together (provider, URL, key, model): every running
   model client is recreated with ``docker-compose.tensorfold.yml`` appended to the deploy's
   ``COMPOSE_FILE``, and one generation runs through the deployed adapter from inside an agent. The
   switch back recreates them without it. A restoration moves them back too, whatever step failed.

Every step is a JSON line in the record (``var/engine_switch/<utc>.jsonl`` under the main checkout).

One switch runs at a time on the host: each command that moves an engine takes ``LOCK`` first, and
waits for one in progress (#2288). The watchdog's restoration therefore never runs beside a switch's
own, and a switch that fails restores Ollama itself.

A switch that completes, and a restoration, then write a deploy record of what runs
(``record_deploy.sh``, #2284): the engine and every model client changed, so the rebuild's record no
longer describes the deploy. A switch that completed but could not record exits 4, so the stale
record is never silent.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkouts import main_checkout  # noqa: E402

#: The records go under the main checkout, whichever checkout runs the switch (scripts/dev/checkouts.py).
MAIN = main_checkout(Path(__file__).resolve().parents[3])
RECORDS = MAIN / "var" / "engine_switch"
#: Taken by every command that moves an engine (#2288). The kernel releases it when its holder dies.
LOCK = RECORDS / ".switch.lock"
#: A switch to TensorFold takes about 30 s with its kernels cached, and a first start compiles them.
LOCK_WAIT_SECONDS = 2700
TF_CONTAINER = "squadops-tensorfold"
TF_PORT = 8090
TF_URL = f"http://127.0.0.1:{TF_PORT}"
OLLAMA_URL = "http://127.0.0.1:11434"
#: The checkpoints' cache, outside every checkout.
TF_HOME = Path.home() / "tensorfold"
#: The server's key file (``label: key``), written from the deploy's SQUADOPS_TENSORFOLD_API_KEY by
#: ``deploy_credentials.py`` (#2006): one home, so a rotation reaches the server and every client.
KEY_FILE = MAIN / "secrets" / "tensorfold_api_key.txt"
#: The clients' side of the switch (§5.6 step 7), appended to the deploy's COMPOSE_FILE while
#: TensorFold serves; and the name the squad reaches it by on its network.
TF_OVERLAY = "docker-compose.tensorfold.yml"
TF_ALIAS = "tensorfold"
SQUADNET = "squadnet"
#: The agent the clients' generation runs from: one container, through the deployed adapter.
PROBE_AGENT = "squadops-max"
#: Its image carries the revision the deploy was built from (``rebuild_and_deploy.sh``).
RUNTIME_CONTAINER = "squadops-runtime-api"
REVISION_LABEL = "org.opencontainers.image.revision"

#: SIP-0111 §5.6 (Q7): the floors, as squadops.campaigns.box defines them.
GIB = 2**30
FLOOR_BEFORE_LOAD = 90 * GIB
FLOOR_AFTER_LOAD = 16 * GIB


class SwitchBusy(RuntimeError):
    """Another switch held the engine past the wait. Nothing was touched, so nothing is restored."""


@contextmanager
def switch_lock() -> Iterator[None]:
    """The host's one switch at a time (#2288), waited for rather than refused: the watchdog's
    restoration must still run once a switch in progress has finished."""
    wait = LOCK_WAIT_SECONDS
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a") as handle:
        give_up = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= give_up:
                    raise SwitchBusy(f"another switch held the engine for {wait:.0f}s") from None
                time.sleep(1)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class SwitchFailed(RuntimeError):
    """A step of the switch failed; the caller restores Ollama."""


@dataclass
class Record:
    path: Path
    started: float = field(default_factory=time.monotonic)

    def write(self, step: str, **fields: Any) -> None:
        line = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "t": round(time.monotonic() - self.started, 1),
            "step": step,
            **memory(),
            **fields,
        }
        with self.path.open("a") as f:
            f.write(json.dumps(line) + "\n")
        print(json.dumps(line), flush=True)


def memory() -> dict[str, float]:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        info[key] = int(value.split()[0]) * 1024
    return {
        "mem_available_gib": round(info["MemAvailable"] / GIB, 1),
        "swap_used_gib": round((info["SwapTotal"] - info["SwapFree"]) / GIB, 2),
    }


def mem_available() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise SwitchFailed("MemAvailable unreadable: residency unknown")


def run(*cmd: str, check: bool = True, timeout: float = 120) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise SwitchFailed(
            f"{' '.join(cmd[:4])} exited {proc.returncode}: {proc.stderr.strip()[-300:]}"
        )
    return proc


def gpu_compute_processes() -> list[str]:
    """Every GPU compute process, as nvidia-smi lists it. Unreadable residency fails closed."""
    proc = run(
        "nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader", check=False
    )
    if proc.returncode != 0:
        raise SwitchFailed(f"GPU residency unknown: nvidia-smi exited {proc.returncode}")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def psql(sql: str) -> str:
    return run(
        "docker",
        "exec",
        "squadops-postgres",
        "psql",
        "-U",
        "squadops",
        "-d",
        "squadops",
        "-At",
        "-c",
        sql,
    ).stdout.strip()


def box_work() -> list[str]:
    """What holds the box: runs in flight and open campaigns. Empty means the switch may hold it."""
    held = []
    runs = psql("select count(*) from cycle_runs where status in ('running','queued','paused')")
    if runs != "0":
        held.append(f"{runs} run(s) running, queued or paused")
    campaigns = psql("select count(*) from campaigns where state <> 'completed'")
    if campaigns != "0":
        held.append(f"{campaigns} campaign(s) open")
    return held


def compose(
    *args: str, timeout: float = 600, files: str | None = None
) -> subprocess.CompletedProcess:
    """``docker compose`` in the main checkout; ``files`` replaces the deploy's COMPOSE_FILE."""
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=MAIN,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "COMPOSE_FILE": files} if files else None,
    )


def container_running(name: str) -> bool:
    proc = run("docker", "inspect", "-f", "{{.State.Running}}", name, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def wait_released(rec: Record, step: str, timeout: float = 180) -> None:
    """Step 4: nothing on the GPU and the before-load floor met, or the switch fails."""
    deadline = time.monotonic() + timeout
    while True:
        procs = gpu_compute_processes()
        available = mem_available()
        if not procs and available >= FLOOR_BEFORE_LOAD:
            rec.write(step, released=True)
            return
        if time.monotonic() > deadline:
            raise SwitchFailed(
                f"memory not released: {len(procs)} GPU process(es) {procs[:3]}, "
                f"MemAvailable {available / GIB:.1f} GiB < {FLOOR_BEFORE_LOAD / GIB:.0f}"
            )
        time.sleep(3)


# --- Ollama ---------------------------------------------------------------------------------------


def stop_ollama(rec: Record) -> None:
    proc = compose("stop", "ollama", timeout=180)
    if proc.returncode != 0:
        raise SwitchFailed(f"ollama stop: {proc.stderr.strip()[-300:]}")
    if container_running("squadops-ollama"):
        raise SwitchFailed("ollama still running after stop")
    rec.write("ollama_stopped")


def start_ollama(rec: Record) -> None:
    proc = compose("up", "-d", "--wait", "ollama", timeout=600)
    if proc.returncode != 0:
        raise SwitchFailed(f"ollama start: {proc.stderr.strip()[-300:]}")
    model = ollama_model()
    t0 = time.monotonic()
    body = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        timeout=600,
        json={
            "model": model,
            "prompt": "Reply with the word ready.",
            "stream": False,
            "think": False,
            "options": {"num_predict": 8, "seed": 1},
        },
    ).json()
    if not body.get("response", "").strip():
        raise SwitchFailed(f"ollama generation empty: {str(body)[:200]}")
    httpx.post(f"{OLLAMA_URL}/api/generate", json={"model": model, "keep_alive": 0}, timeout=120)
    rec.write("ollama_healthy", model=model, generation_s=round(time.monotonic() - t0, 1))


def ollama_model() -> str:
    """The production model the deploy's squad profile runs (the 27B)."""
    return "qwen3.8:27b"


# --- TensorFold -----------------------------------------------------------------------------------


def load_recipe(path: Path) -> dict[str, Any]:
    recipe = yaml.safe_load(path.read_text())
    for key in (
        "name",
        "served_id",
        "image",
        "checkpoint",
        "context",
        "memory_reserve_gib",
        "serve_flags",
    ):
        if key not in recipe:
            raise SwitchFailed(f"recipe {path.name} lacks {key}")
    return recipe


def serve_command(recipe: dict[str, Any], network: str | None = None) -> list[str]:
    """The ``docker run`` that starts the recipe: everything it pins is on this line, so the line is the
    record of what was served."""
    cache = "/cache"
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        TF_CONTAINER,
        "--device",
        "nvidia.com/gpu=all",
        "--ipc=host",
        "--user",
        "1000:1000",
        "-e",
        f"HOME={cache}/home",
        "-e",
        f"HF_HOME={cache}/hf",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        f"TORCH_EXTENSIONS_DIR={cache}/torch_extensions",
        "-e",
        f"TRITON_CACHE_DIR={cache}/triton",
        "-e",
        f"TENSORFOLD_MEMORY_RESERVE_GIB={recipe['memory_reserve_gib']}",
        "-e",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "-v",
        f"{TF_HOME}:{cache}",
        "-v",
        f"{KEY_FILE}:/run/tensorfold_api_key:ro",
        "-p",
        f"127.0.0.1:{TF_PORT}:8080",
        # The squad's network, where every model client reaches it as `tensorfold` (§5.6 step 7).
        *(["--network", network, "--network-alias", TF_ALIAS] if network else []),
        recipe["image"],
        "serve",
        recipe["checkpoint"]["container_path"],
        "--name",
        recipe["served_id"],
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
        "--context",
        str(recipe["context"]),
        "--api-key-file",
        "/run/tensorfold_api_key",
        *[str(f) for f in recipe["serve_flags"]],
    ]
    return cmd


def api_key(path: Path = KEY_FILE) -> str:
    lines = [line.strip() for line in path.read_text().splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    owned = [line.split(":", 1)[1].strip() for line in lines
             if ":" in line and line.split(":", 1)[0].strip() == "squadops"]
    if len(owned) == 1 and owned[0] and not any(c.isspace() for c in owned[0]):
        return owned[0]
    if len(lines) == 1 and ":" not in lines[0] and not any(c.isspace() for c in lines[0]):
        return lines[0]  # legacy single unlabelled key
    raise SwitchFailed("TensorFold key file needs exactly one squadops entry; values withheld")


def tf_get(path: str, **kw: Any) -> httpx.Response:
    return httpx.get(
        f"{TF_URL}{path}", headers={"Authorization": f"Bearer {api_key()}"}, timeout=30, **kw
    )


def tf_post(path: str, body: dict, timeout: float = 600) -> httpx.Response:
    return httpx.post(
        f"{TF_URL}{path}",
        headers={"Authorization": f"Bearer {api_key()}"},
        json=body,
        timeout=timeout,
    )


def stop_tensorfold(rec: Record) -> None:
    if run("docker", "inspect", TF_CONTAINER, check=False).returncode == 0:
        logs = run("docker", "logs", "--tail", "200", TF_CONTAINER, check=False)
        (rec.path.parent / f"{rec.path.stem}.tensorfold.log").write_text(logs.stdout + logs.stderr)
        run("docker", "rm", "-f", TF_CONTAINER, check=False, timeout=180)
    rec.write("tensorfold_stopped")


def squad_network() -> str:
    """The deploy's squadnet as compose named it (the project's name prefixes it), read from the
    runtime API's container. Unknown fails the switch: a TensorFold no client can reach serves
    nothing."""
    proc = run(
        "docker",
        "inspect",
        "-f",
        "{{json .NetworkSettings.Networks}}",
        "squadops-runtime-api",
        check=False,
    )
    names = [
        n
        for n in (json.loads(proc.stdout or "{}") if proc.returncode == 0 else {})
        if n == SQUADNET or n.endswith(f"_{SQUADNET}")
    ]
    if len(names) != 1:
        raise SwitchFailed(f"the squad's network is unknown (the runtime API's networks: {names})")
    return names[0]


def start_tensorfold(rec: Record, recipe: dict[str, Any], ready_timeout: float) -> None:
    network = squad_network()
    rec.write("tensorfold_network", network=network, alias=TF_ALIAS)
    cmd = serve_command(recipe, network)
    rec.write("tensorfold_starting", recipe=recipe["name"], command=cmd)
    run(*cmd)
    deadline = time.monotonic() + ready_timeout
    unauthorized = 0
    while time.monotonic() < deadline:
        if not container_running(TF_CONTAINER):
            raise SwitchFailed("tensorfold exited during startup (see the record's log)")
        try:
            resp = tf_get("/v1/models")
            if resp.status_code == 200:
                rec.write("tensorfold_answering")
                return
            if resp.status_code == 401:
                unauthorized += 1
                if unauthorized >= 3:
                    raise SwitchFailed("tensorfold refused the key (401)")
        except httpx.HTTPError:
            pass
        if mem_available() < FLOOR_AFTER_LOAD:
            raise SwitchFailed(
                f"MemAvailable fell below {FLOOR_AFTER_LOAD / GIB:.0f} GiB during load"
            )
        time.sleep(5)
    raise SwitchFailed(f"tensorfold did not answer within {ready_timeout:.0f}s")


def verify_tensorfold(rec: Record, recipe: dict[str, Any]) -> None:
    models = tf_get("/v1/models").json()
    ids = {m.get("id") for m in models.get("data", [])}
    if recipe["served_id"] not in ids:
        raise SwitchFailed(f"served ids {sorted(ids)} lack the recipe's {recipe['served_id']}")
    window = tf_post("/tokenize", {"prompt": "x"}, timeout=60).json().get("max_model_len")
    if window != recipe["context"]:
        raise SwitchFailed(f"served window {window} != the recipe's {recipe['context']}")
    args = json.loads(run("docker", "inspect", "-f", "{{json .Args}}", TF_CONTAINER).stdout)
    if args[1] != recipe["checkpoint"]["container_path"] or not all(
        str(f) in args for f in recipe["serve_flags"]
    ):
        raise SwitchFailed("the running command line is not the recipe's")
    available = mem_available()
    if available < FLOOR_AFTER_LOAD:
        raise SwitchFailed(
            f"MemAvailable {available / GIB:.1f} GiB after load < {FLOOR_AFTER_LOAD / GIB:.0f}"
        )
    rec.write("tensorfold_verified", served_ids=sorted(ids), window=window)
    t0 = time.monotonic()
    body = tf_post(
        "/v1/chat/completions",
        {
            "model": recipe["served_id"],
            "messages": [{"role": "user", "content": "Reply with the word ready."}],
            "max_tokens": 16,
            "seed": 1,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    ).json()
    text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    if not text.strip():
        raise SwitchFailed(f"tensorfold generation empty: {str(body)[:200]}")
    rec.write("tensorfold_healthy", generation_s=round(time.monotonic() - t0, 1))


# --- the clients (§5.6 step 7) --------------------------------------------------------------------

#: One generation through the deployed adapter, inside an agent: the URL, the key, the network and the
#: adapter, together, as the squad will call them. It prints the engine and the reply's length only.
CLIENT_PROBE = """
import asyncio, sys
from adapters.llm.factory import create_llm_provider
from squadops.bootstrap.secrets import secret_provider_for
from squadops.config.loader import load_config
from squadops.llm.models import ChatMessage

async def main():
    llm = load_config(secret_provider_factory=secret_provider_for).llm
    port = create_llm_provider(provider=llm.provider, base_url=llm.url, default_model=sys.argv[1],
                               timeout_seconds=600.0, api_key=llm.api_key)
    reply = await port.chat(
        [ChatMessage(role="user", content="Reply with the word ready.")],
        max_tokens=16, reasoning="none")
    print(port.engine, len(reply.content.strip()))

asyncio.run(main())
"""


def deploy_compose_files() -> str:
    """The deploy's own COMPOSE_FILE, as its .env sets it for every ``docker compose`` there."""
    env = MAIN / ".env"
    for line in env.read_text().splitlines() if env.is_file() else []:
        if line.startswith("COMPOSE_FILE="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return "docker-compose.yml"


def base_compose_files() -> str:
    """The deploy's files without the TensorFold overlay: what its clients run with on Ollama."""
    return ":".join(f for f in deploy_compose_files().split(":") if f and f != TF_OVERLAY)


def client_files(engine: str) -> str:
    base = base_compose_files()
    return f"{base}:{TF_OVERLAY}" if engine == "tensorfold" else base


def deploy_engine() -> str:
    """The engine the deploy runs, as its .env records it: the switch writes it, every
    ``docker compose`` there reads it, and a rebuild keeps it (``rebuild_and_deploy.sh``)."""
    return "tensorfold" if TF_OVERLAY in deploy_compose_files().split(":") else "ollama"


def persist_engine(rec: Record, engine: str) -> None:
    """Record ``engine`` as the deploy's in its .env (``COMPOSE_FILE``), so the next rebuild, or any
    ``docker compose`` run there, recreates the clients on the engine that is serving rather than
    the one the deploy started with. The file keeps its owner-only mode (it holds credentials)."""
    env = MAIN / ".env"
    files = client_files(engine)
    lines = env.read_text().splitlines() if env.is_file() else []
    at = [i for i, line in enumerate(lines) if line.startswith("COMPOSE_FILE=")]
    if at:
        lines[at[0]] = f"COMPOSE_FILE={files}"
    else:
        lines.append(f"COMPOSE_FILE={files}")
    mode = env.stat().st_mode & 0o777 if env.is_file() else 0o600
    env.write_text("\n".join(lines) + "\n")
    env.chmod(mode)
    rec.write("deploy_engine", engine=engine, compose_file=files)


def llm_clients(files: str) -> list[str]:
    """The running services that call a model: each sets SQUADOPS__LLM__PROVIDER. The rendered
    composition holds the deploy's credentials, so it is parsed here and never written anywhere."""
    config = compose("config", "--format", "json", files=files)
    if config.returncode != 0:
        raise SwitchFailed(f"compose config: {config.stderr.strip()[-300:]}")
    running = set(compose("ps", "--services", "--status", "running").stdout.split())
    return sorted(
        name
        for name, service in json.loads(config.stdout)["services"].items()
        if "SQUADOPS__LLM__PROVIDER" in (service.get("environment") or {}) and name in running
    )


def client_engine(service: str) -> str | None:
    """The provider a running client was started with."""
    ids = compose("ps", "-q", service).stdout.split()
    if not ids:
        return None
    env = json.loads(run("docker", "inspect", "-f", "{{json .Config.Env}}", ids[0]).stdout)
    for item in env:
        key, _, value = item.partition("=")
        if key == "SQUADOPS__LLM__PROVIDER":
            return value
    return None


def switch_clients(rec: Record, engine: str, model: str) -> None:
    """Every running model client recreated on ``engine``, checked, then one generation through
    the deployed adapter from inside an agent."""
    files = client_files(engine)
    services = llm_clients(files)
    proc = compose(
        "up", "-d", "--no-deps", "--force-recreate", "--wait", *services, files=files, timeout=900
    )
    if proc.returncode != 0:
        raise SwitchFailed(f"clients to {engine}: {proc.stderr.strip()[-300:]}")
    wrong = {s: client_engine(s) for s in services if client_engine(s) != engine}
    if wrong:
        raise SwitchFailed(f"clients not on {engine} after recreation: {wrong}")
    rec.write("clients_switched", engine=engine, services=services)
    persist_engine(rec, engine)
    t0 = time.monotonic()
    probe = subprocess.run(
        ["docker", "exec", "-i", PROBE_AGENT, "python", "-", model],
        input=CLIENT_PROBE,
        capture_output=True,
        text=True,
        timeout=900,
    )
    said = probe.stdout.split()
    if probe.returncode != 0 or len(said) != 2 or said[0] != engine or said[1] == "0":
        raise SwitchFailed(
            f"the clients' generation on {engine} failed: {(probe.stderr or probe.stdout)[-300:]}"
        )
    rec.write("clients_healthy", engine=engine, generation_s=round(time.monotonic() - t0, 1))


def record_deploy(rec: Record, command: str) -> bool:
    """A deploy record of what runs now (#2284), through the rebuild's own recorder. Its source
    revision is the deploy's, read from the runtime image's label: a switch builds nothing, and the
    checkout may have moved since the images were built. Never raises: an engine that switched
    stays switched, and the caller reports the stale record."""
    revision = ""
    try:
        label = run(
            "docker",
            "inspect",
            "-f",
            f'{{{{index .Config.Labels "{REVISION_LABEL}"}}}}',
            RUNTIME_CONTAINER,
            check=False,
        ).stdout.strip()
        revision = "" if label in ("", "<no value>") else label
        proc = subprocess.run(
            [
                str(MAIN / "scripts" / "dev" / "ops" / "record_deploy.sh"),
                f"engine_switch.py {command}",
            ],
            cwd=MAIN,
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, "SOURCE_HASH": revision},
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        rec.write("deploy_record_failed", error=str(exc)[:300])
        return False
    if proc.returncode != 0:
        rec.write("deploy_record_failed", error=(proc.stderr or proc.stdout).strip()[-300:])
        return False
    rec.write("deploy_recorded", source_revision=revision or None, said=proc.stdout.strip()[-300:])
    return True


# --- the switch -----------------------------------------------------------------------------------


def to_ollama(rec: Record) -> None:
    """Restoration: TensorFold stopped and its release confirmed BEFORE Ollama starts; never both.
    Then the clients, if any had moved: a switch that failed before step 7 never moved them.

    Ollama is stopped too, as ``to_tensorfold`` stops both. Asked for while Ollama was already
    serving, the release check counted Ollama's own ``llama-server`` and failed after 180 s: G3's
    rolls stage, 2026-10-13, whose shakeouts stage had ended on Ollama. Now every switch back
    leaves a freshly started Ollama, whichever engine was resident."""
    stop_ollama(rec)
    stop_tensorfold(rec)
    wait_released(rec, "released_for_ollama")
    start_ollama(rec)
    files = base_compose_files()
    if deploy_engine() == "tensorfold" or any(
        client_engine(s) == "tensorfold" for s in llm_clients(files)
    ):
        switch_clients(rec, "ollama", ollama_model())


def restore(rec: Record) -> bool:
    """The restoration the memory watchdog runs after it killed TensorFold (#2288): Ollama
    started and the clients moved back, as a failed switch restores. It does not refuse work on
    the box: the engine that work ran on is gone, and its cycles fail until Ollama serves. False,
    with nothing touched, when Ollama already serves a deploy that records it."""
    if (
        not container_running(TF_CONTAINER)
        and container_running("squadops-ollama")
        and deploy_engine() == "ollama"
    ):
        rec.write("nothing_to_restore")
        return False
    to_ollama(rec)
    rec.write("restored", engine="ollama")
    return True


def to_tensorfold(rec: Record, recipe_path: Path, ready_timeout: float) -> None:
    recipe = load_recipe(recipe_path)
    held = box_work()
    if held:
        raise SwitchFailed(f"the box is not free: {'; '.join(held)}")
    rec.write("box_held", recipe=recipe["name"])
    stop_ollama(rec)
    stop_tensorfold(rec)  # another recipe may be resident: one engine, one recipe, at a time
    wait_released(rec, "released_for_tensorfold")
    start_tensorfold(rec, recipe, ready_timeout)
    verify_tensorfold(rec, recipe)
    switch_clients(rec, "tensorfold", recipe["served_id"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    tf = sub.add_parser("to-tensorfold")
    tf.add_argument("recipe", type=Path)
    tf.add_argument(
        "--ready-timeout",
        type=float,
        default=2400,
        help="seconds for the first answer (a first start compiles TensorFold's kernels)",
    )
    sub.add_parser("to-ollama")
    sub.add_parser("restore")
    sub.add_parser("status")
    # For rebuild_and_deploy.sh: one word, the engine the deploy's .env records. No record.
    sub.add_parser("deploy-engine")
    args = parser.parse_args()
    if args.command == "deploy-engine":
        print(deploy_engine())
        return 0

    RECORDS.mkdir(parents=True, exist_ok=True)
    rec = Record(RECORDS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{args.command}.jsonl")
    if args.command == "status":
        rec.write(
            "status",
            tensorfold=container_running(TF_CONTAINER),
            ollama=container_running("squadops-ollama"),
            deploy_engine=deploy_engine(),
            gpu_processes=gpu_compute_processes(),
        )
        return 0
    try:
        with switch_lock():
            return switch(args, rec)
    except SwitchBusy as exc:
        rec.write("busy", error=str(exc))
        return 5


def switch(args: argparse.Namespace, rec: Record) -> int:
    """One command that moves an engine, under the host's lock. Exits 0 when it completed and
    recorded the deploy, 2 when it failed (a failed switch to TensorFold restores Ollama), 3 when
    a restoration failed, and 4 when it completed but could not record."""
    try:
        if args.command == "to-ollama":
            # Asked for, not a restoration: the clients are recreated, so nothing may be running.
            held = box_work()
            if held:
                raise SwitchFailed(f"the box is not free: {'; '.join(held)}")
            to_ollama(rec)
        elif args.command == "restore":
            if not restore(rec):
                rec.write("done", command=args.command)
                return 0
        else:
            to_tensorfold(rec, args.recipe, args.ready_timeout)
        recorded = record_deploy(rec, args.command)
        rec.write("done", command=args.command)
        return 0 if recorded else 4
    except (SwitchFailed, httpx.HTTPError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        rec.write("failed", error=str(exc)[:500])
        if args.command == "restore":
            rec.write("RESTORATION_FAILED", error=str(exc)[:500])
            return 3
        if args.command == "to-tensorfold":
            try:
                to_ollama(rec)
                rec.write("restored", engine="ollama")
            except Exception as restore_exc:  # noqa: BLE001 — say so loudly; nothing is left running
                rec.write("RESTORATION_FAILED", error=str(restore_exc)[:500])
                return 3
            record_deploy(rec, "to-ollama (restoration)")
        return 2


if __name__ == "__main__":
    sys.exit(main())
