"""SIP-0111 §5.6 (#2199): the engine switch fails closed, and verifies what it started against the recipe."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "engine_switch", ROOT / "scripts/dev/ops/engine_switch.py"
)
es = importlib.util.module_from_spec(_spec)
sys.modules["engine_switch"] = es  # its dataclass resolves annotations through sys.modules
_spec.loader.exec_module(es)

GIB = 2**30
RECIPE = {
    "name": "qwen27b-mlx4",
    "served_id": "qwen3.8-27b-tf-mlx4",
    "image": "squadops-tensorfold:0.6.6-cb2ebf05",
    "checkpoint": {"container_path": "/cache/hf/hub/models--TensorFold--x/snapshots/abc"},
    "context": 65536,
    "memory_reserve_gib": 20,
    "serve_flags": ["--drafter", "/cache/hf/hub/models--z-lab--d/snapshots/def"],
}


@pytest.fixture
def rec(tmp_path):
    return es.Record(tmp_path / "switch.jsonl")


class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


def _steps(rec) -> list[str]:
    return [json.loads(line)["step"] for line in rec.path.read_text().splitlines()]


def test_the_serve_command_carries_every_pin_the_recipe_names():
    """Bug caught: a recipe field (the window, the reserve, a flag) silently left off the command line, so the
    engine serves its own default and the record claims the recipe."""
    cmd = es.serve_command(RECIPE)
    serve = cmd[cmd.index(RECIPE["image"]) + 1 :]
    assert serve[:2] == ["serve", RECIPE["checkpoint"]["container_path"]]
    assert ["--context", "65536"] == serve[serve.index("--context") : serve.index("--context") + 2]
    assert serve[-2:] == RECIPE["serve_flags"]
    assert "TENSORFOLD_MEMORY_RESERVE_GIB=20" in cmd
    assert "127.0.0.1:8090:8080" in cmd  # never published beyond the host's loopback


def test_a_recipe_missing_a_pin_is_refused(tmp_path):
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump({k: v for k, v in RECIPE.items() if k != "context"}))
    with pytest.raises(es.SwitchFailed, match="lacks context"):
        es.load_recipe(path)


@pytest.mark.parametrize(
    ("models", "window", "available", "match"),
    [
        ({"data": [{"id": "someone-else"}]}, 65536, 40 * GIB, "lack the recipe's"),
        ({"data": [{"id": "qwen3.8-27b-tf-mlx4"}]}, 32768, 40 * GIB, "served window 32768"),
        ({"data": [{"id": "qwen3.8-27b-tf-mlx4"}]}, 65536, 12 * GIB, "after load"),
    ],
    ids=["wrong-model", "wrong-window", "below-the-after-load-floor"],
)
def test_verification_refuses_what_the_recipe_did_not_ask_for(
    monkeypatch, rec, models, window, available, match
):
    """Bugs caught: an engine serving another model or a different window read as the recipe's; a load that
    left less than the 16 GiB floor accepted."""
    monkeypatch.setattr(es, "tf_get", lambda path, **kw: _Resp(models))
    monkeypatch.setattr(
        es, "tf_post", lambda path, body, timeout=600: _Resp({"max_model_len": window})
    )
    monkeypatch.setattr(
        es,
        "run",
        lambda *a, **k: type(
            "P",
            (),
            {
                "stdout": json.dumps(
                    ["serve", RECIPE["checkpoint"]["container_path"], *RECIPE["serve_flags"]]
                )
            },
        )(),
    )
    monkeypatch.setattr(es, "mem_available", lambda: available)
    with pytest.raises(es.SwitchFailed, match=match):
        es.verify_tensorfold(rec, RECIPE)


def test_the_release_is_not_confirmed_while_anything_holds_the_gpu(monkeypatch, rec):
    """Bug caught: TensorFold started while Ollama's runner still held the GPU: two engines in unified memory."""
    monkeypatch.setattr(
        es, "gpu_compute_processes", lambda: ["4022774, /usr/lib/ollama/llama-server"]
    )
    monkeypatch.setattr(es, "mem_available", lambda: 110 * GIB)
    monkeypatch.setattr(es.time, "sleep", lambda s: None)
    with pytest.raises(es.SwitchFailed, match="GPU process"):
        es.wait_released(rec, "released_for_tensorfold", timeout=0)


def test_a_failed_switch_restores_ollama_and_says_so(monkeypatch, tmp_path):
    """Entered at ``main``, as the overnight driver runs it. Bug caught: a switch that fails after Ollama was
    stopped and leaves the box with no engine, or restores without recording that it failed."""
    monkeypatch.setattr(es, "RECORDS", tmp_path)
    monkeypatch.setattr(
        es.sys, "argv", ["engine_switch.py", "to-tensorfold", str(tmp_path / "r.yaml")]
    )
    calls = []

    def fail(rec, recipe_path, ready_timeout):
        calls.append("to_tensorfold")
        raise es.SwitchFailed("tensorfold exited during startup")

    monkeypatch.setattr(es, "to_tensorfold", fail)
    monkeypatch.setattr(es, "to_ollama", lambda rec: calls.append("to_ollama"))

    assert es.main() == 2
    (record,) = tmp_path.glob("*.jsonl")
    steps = [json.loads(line)["step"] for line in record.read_text().splitlines()]
    assert calls == ["to_tensorfold", "to_ollama"]
    assert steps == ["failed", "restored"]


def test_a_restoration_that_fails_is_reported_loudly(monkeypatch, tmp_path):
    monkeypatch.setattr(es, "RECORDS", tmp_path)
    monkeypatch.setattr(
        es.sys, "argv", ["engine_switch.py", "to-tensorfold", str(tmp_path / "r.yaml")]
    )
    monkeypatch.setattr(
        es, "to_tensorfold", lambda *a: (_ for _ in ()).throw(es.SwitchFailed("no"))
    )
    monkeypatch.setattr(
        es, "to_ollama", lambda rec: (_ for _ in ()).throw(es.SwitchFailed("still held"))
    )

    assert es.main() == 3
    (record,) = tmp_path.glob("*.jsonl")
    assert [json.loads(line)["step"] for line in record.read_text().splitlines()] == [
        "failed",
        "RESTORATION_FAILED",
    ]


# --- the clients (§5.6 step 7, the owner's ruling of 2026-10-13) ----------------------------------

_CLIENTS = ["bob", "data", "eve", "max", "nat", "neo", "runtime-api"]
_DEPLOY_FILES = "docker-compose.yml:docker-compose.ollama.yml"


class _Deploy:
    """The deploy, as compose answers for it: each running model client on an engine, one service
    that calls no model, and every ``up`` the switch sends, with the files it named."""

    def __init__(self, engine: str):
        self.engines = dict.fromkeys(_CLIENTS, engine)
        self.ups: list[tuple[str | None, list[str]]] = []
        self.probes: list[list[str]] = []
        self.probe_says = None

    def compose(self, *args, timeout=600, files=None):
        done = lambda out="": subprocess.CompletedProcess(args, 0, out, "")  # noqa: E731
        if args[0] == "config":
            services = {
                s: {"environment": {"SQUADOPS__LLM__PROVIDER": e}} for s, e in self.engines.items()
            }
            return done(json.dumps({"services": services | {"postgres": {"environment": {}}}}))
        if args[0] == "ps":
            return done("\n".join([*self.engines, "postgres"]))
        if args[0] == "up":
            names = [a for a in args[1:] if not a.startswith("-")]
            self.ups.append((files, names))
            for name in names:
                self.engines[name] = "tensorfold" if files.endswith(es.TF_OVERLAY) else "ollama"
            return done()
        raise AssertionError(f"unexpected compose {args}")

    def exec_probe(self, cmd, **kw):
        assert cmd[:4] == ["docker", "exec", "-i", es.PROBE_AGENT], cmd
        assert kw["input"] == es.CLIENT_PROBE
        self.probes.append(cmd)
        said = f"{self.engines['max']} 5" if self.probe_says is None else self.probe_says
        return subprocess.CompletedProcess(cmd, 0, said, "")


@pytest.fixture
def deploy(monkeypatch, tmp_path):
    """A deploy whose clients are all on ``engine`` and whose ``.env`` says so. The main checkout is
    a scratch directory: the switch writes the deploy's ``.env``, and a test must never write the
    real one."""

    def at(engine: str) -> _Deploy:
        d = _Deploy(engine)
        files = _DEPLOY_FILES + (f":{es.TF_OVERLAY}" if engine == "tensorfold" else "")
        env = tmp_path / ".env"
        env.write_text(f"POSTGRES_PASSWORD=kept\nCOMPOSE_FILE={files}\nCOMPOSE_PROFILES=gpu\n")
        env.chmod(0o600)
        monkeypatch.setattr(es, "MAIN", tmp_path)
        monkeypatch.setattr(es, "compose", d.compose)
        monkeypatch.setattr(es, "client_engine", lambda service: d.engines.get(service))
        monkeypatch.setattr(es.subprocess, "run", d.exec_probe)
        return d

    return at


def test_the_clients_move_together_and_answer_through_the_deployed_adapter(deploy, rec):
    """Bugs caught: a client left on Ollama while the engine is TensorFold (calls to a stopped
    engine), the overlay named without the deploy's own files (the clients lose its other
    settings), a service that calls no model recreated, and a switch that reports the clients moved
    without one generation through the adapter they now run."""
    d = deploy("ollama")

    es.switch_clients(rec, "tensorfold", "qwen3.8-27b-tf-nvfp4")

    assert d.ups == [(f"{_DEPLOY_FILES}:{es.TF_OVERLAY}", _CLIENTS)]
    assert set(d.engines.values()) == {"tensorfold"}
    assert d.probes[0][-1] == "qwen3.8-27b-tf-nvfp4"
    assert _steps(rec) == ["clients_switched", "deploy_engine", "clients_healthy"]


@pytest.mark.parametrize(
    "said",
    ["ollama 5", "tensorfold 0", ""],
    ids=["answered by the other engine", "an empty reply", "no answer"],
)
def test_a_client_generation_that_did_not_come_from_the_engine_fails_the_switch(deploy, rec, said):
    d = deploy("ollama")
    d.probe_says = said
    with pytest.raises(es.SwitchFailed, match="clients' generation on tensorfold"):
        es.switch_clients(rec, "tensorfold", "qwen3.8-27b-tf-nvfp4")


@pytest.mark.parametrize(
    ("clients_on", "ups"),
    [("tensorfold", [(_DEPLOY_FILES, _CLIENTS)]), ("ollama", [])],
    ids=["after the clients moved", "a switch that failed before they moved"],
)
def test_restoration_moves_the_clients_back_only_when_they_moved(
    deploy, rec, monkeypatch, clients_on, ups
):
    """Bug caught: a restoration that leaves the squad calling a stopped TensorFold; or one that
    restarts every agent after a switch that never touched them."""
    d = deploy(clients_on)
    for step in ("stop_ollama", "stop_tensorfold", "start_ollama"):
        monkeypatch.setattr(es, step, lambda rec: None)
    monkeypatch.setattr(es, "wait_released", lambda rec, step: None)

    es.to_ollama(rec)

    assert d.ups == ups
    assert set(d.engines.values()) == {"ollama"}


def test_an_asked_for_switch_back_refuses_a_busy_box(monkeypatch, tmp_path):
    """Recreating the clients restarts the runtime API, which runs every cycle. Bug caught: a
    switch back that kills a running cycle. A restoration after a failed switch is not asked
    for and holds the box already, so it is not refused."""
    monkeypatch.setattr(es, "RECORDS", tmp_path)
    monkeypatch.setattr(es.sys, "argv", ["engine_switch.py", "to-ollama"])
    monkeypatch.setattr(es, "box_work", lambda: ["run run_1 is running"])
    monkeypatch.setattr(es, "to_ollama", lambda rec: pytest.fail("switched with work on the box"))

    assert es.main() == 2
    (record,) = tmp_path.glob("*.jsonl")
    assert "run run_1 is running" in json.loads(record.read_text().splitlines()[-1])["error"]


def test_tensorfold_joins_the_squads_network_under_the_name_the_clients_call(monkeypatch):
    """Bug caught: TensorFold published on the host's loopback only, which no container reaches."""
    cmd = es.serve_command(RECIPE, "squad-ops_squadnet")
    assert cmd[cmd.index("--network") : cmd.index("--network") + 4] == [
        "--network",
        "squad-ops_squadnet",
        "--network-alias",
        "tensorfold",
    ]
    assert cmd.index("--network") < cmd.index(RECIPE["image"])

    networks = {"squad-ops_squadnet": {}, "bridge": {}}
    monkeypatch.setattr(
        es, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, json.dumps(networks), "")
    )
    assert es.squad_network() == "squad-ops_squadnet"
    networks.pop("squad-ops_squadnet")
    with pytest.raises(es.SwitchFailed, match="network is unknown"):
        es.squad_network()


def test_the_clients_move_only_after_the_engine_is_verified(monkeypatch, rec, tmp_path):
    """§5.6's order. Bug caught: clients moved to a TensorFold that never answered, or not moved at
    all, so the squad keeps calling a stopped Ollama."""
    order = []
    recipe = tmp_path / "r.yaml"
    recipe.write_text(yaml.safe_dump(RECIPE))
    monkeypatch.setattr(es, "load_recipe", lambda path: RECIPE)
    monkeypatch.setattr(es, "box_work", lambda: [])
    for step in ("stop_ollama", "stop_tensorfold"):
        monkeypatch.setattr(es, step, lambda rec, step=step: order.append(step))
    monkeypatch.setattr(es, "wait_released", lambda rec, step: order.append("wait_released"))
    monkeypatch.setattr(es, "start_tensorfold", lambda rec, r, t: order.append("start_tensorfold"))
    monkeypatch.setattr(es, "verify_tensorfold", lambda rec, r: order.append("verify_tensorfold"))
    monkeypatch.setattr(
        es, "switch_clients", lambda rec, engine, model: order.append(("clients", engine, model))
    )

    es.to_tensorfold(rec, recipe, 60)

    assert order[-2:] == ["verify_tensorfold", ("clients", "tensorfold", RECIPE["served_id"])]


@pytest.mark.parametrize(
    ("start", "engine", "files"),
    [
        ("ollama", "tensorfold", f"{_DEPLOY_FILES}:{es.TF_OVERLAY}"),
        ("tensorfold", "ollama", _DEPLOY_FILES),
    ],
    ids=["to TensorFold", "back to Ollama"],
)
def test_a_switch_records_the_engine_in_the_deploys_env(
    deploy, rec, tmp_path, start, engine, files
):
    """Bugs caught: a rebuild after the cutover recreating every client on a stopped Ollama, because
    the deploy's .env still named Ollama's files; or a rollback that left the overlay there, so the
    next rebuild moved the clients to a stopped TensorFold. Also: the rewrite dropping the file's
    other lines (its credentials) or widening its owner-only mode."""
    deploy(start)

    es.switch_clients(rec, engine, "a-model")

    env = tmp_path / ".env"
    assert env.read_text().splitlines() == [
        "POSTGRES_PASSWORD=kept",
        f"COMPOSE_FILE={files}",
        "COMPOSE_PROFILES=gpu",
    ]
    assert env.stat().st_mode & 0o777 == 0o600
    assert es.deploy_engine() == engine
    assert _steps(rec)[-2:] == ["deploy_engine", "clients_healthy"]


def test_a_switch_back_moves_the_clients_when_the_deploy_records_tensorfold(
    deploy, rec, monkeypatch
):
    """Bug caught: a rollback that read only the containers, found them on Ollama (an interrupted
    switch had recreated them) and left the .env on TensorFold, so the next rebuild undid it."""
    d = deploy("tensorfold")
    d.engines = dict.fromkeys(d.engines, "ollama")
    for step in ("stop_ollama", "stop_tensorfold", "start_ollama"):
        monkeypatch.setattr(es, step, lambda rec: None)
    monkeypatch.setattr(es, "wait_released", lambda rec, step: None)

    es.to_ollama(rec)

    assert es.deploy_engine() == "ollama"
    assert d.ups == [(_DEPLOY_FILES, _CLIENTS)]


def test_a_switch_back_with_ollama_already_serving_releases_it_first(deploy, rec, monkeypatch):
    """Bug caught: ``to-ollama`` asked for while Ollama was serving. Only TensorFold was stopped,
    so the release check counted Ollama's own process and failed after 180 s (G3's rolls stage,
    2026-10-13). Both engines are stopped before the check, as ``to_tensorfold`` does."""
    deploy("ollama")
    calls: list[str] = []
    for step in ("stop_ollama", "stop_tensorfold", "start_ollama"):
        monkeypatch.setattr(es, step, lambda rec, step=step: calls.append(step))
    monkeypatch.setattr(es, "wait_released", lambda rec, step: calls.append("wait_released"))

    es.to_ollama(rec)

    assert calls == ["stop_ollama", "stop_tensorfold", "wait_released", "start_ollama"]
