"""SIP-0111 §5.6 (#2199): the engine switch fails closed, and verifies what it started against the recipe."""

from __future__ import annotations

import importlib.util
import json
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
