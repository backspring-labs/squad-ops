#!/usr/bin/env python3
"""Switch the Spark's inference engine between Ollama and TensorFold, failing closed (SIP-0111 §5.6, #2199).

Both engines are containers (#2249): Ollama is the deploy's ``ollama`` service, TensorFold is started here
from a pinned recipe (``infra/tensorfold/recipes/*.yaml``). Only one is ever resident.

    engine_switch.py to-tensorfold RECIPE   the switch, steps 1-7; any failure restores Ollama
    engine_switch.py to-ollama              restoration: TensorFold stopped and released, then Ollama
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
7. One healthy generation.

Every step is a JSON line in the record (``var/engine_switch/<utc>.jsonl`` under the main checkout).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
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
TF_CONTAINER = "squadops-tensorfold"
TF_PORT = 8090
TF_URL = f"http://127.0.0.1:{TF_PORT}"
OLLAMA_URL = "http://127.0.0.1:11434"
#: The checkpoints' cache and the API key's file, outside every checkout.
TF_HOME = Path.home() / "tensorfold"
KEY_FILE = TF_HOME / "secrets" / "api_key"

#: SIP-0111 §5.6 (Q7): the floors, as squadops.campaigns.box defines them.
GIB = 2**30
FLOOR_BEFORE_LOAD = 90 * GIB
FLOOR_AFTER_LOAD = 16 * GIB


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


def compose(*args: str, timeout: float = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args], cwd=MAIN, capture_output=True, text=True, timeout=timeout
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


def serve_command(recipe: dict[str, Any]) -> list[str]:
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
    line = path.read_text().strip()
    return line.split(":", 1)[1].strip() if ":" in line else line


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


def start_tensorfold(rec: Record, recipe: dict[str, Any], ready_timeout: float) -> None:
    cmd = serve_command(recipe)
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


# --- the switch -----------------------------------------------------------------------------------


def to_ollama(rec: Record) -> None:
    """Restoration: TensorFold stopped and its release confirmed BEFORE Ollama starts; never both."""
    stop_tensorfold(rec)
    wait_released(rec, "released_for_ollama")
    start_ollama(rec)


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
    sub.add_parser("status")
    args = parser.parse_args()

    RECORDS.mkdir(parents=True, exist_ok=True)
    rec = Record(RECORDS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{args.command}.jsonl")
    if args.command == "status":
        rec.write(
            "status",
            tensorfold=container_running(TF_CONTAINER),
            ollama=container_running("squadops-ollama"),
            gpu_processes=gpu_compute_processes(),
        )
        return 0
    try:
        if args.command == "to-ollama":
            to_ollama(rec)
        else:
            to_tensorfold(rec, args.recipe, args.ready_timeout)
        rec.write("done", command=args.command)
        return 0
    except (SwitchFailed, httpx.HTTPError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        rec.write("failed", error=str(exc)[:500])
        if args.command == "to-tensorfold":
            try:
                to_ollama(rec)
                rec.write("restored", engine="ollama")
            except Exception as restore_exc:  # noqa: BLE001 — say so loudly; nothing is left running
                rec.write("RESTORATION_FAILED", error=str(restore_exc)[:500])
                return 3
        return 2


if __name__ == "__main__":
    sys.exit(main())
