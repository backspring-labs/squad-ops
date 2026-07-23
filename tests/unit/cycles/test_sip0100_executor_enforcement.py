"""SIP-0100 Task 2.4 — executor artifact-storage frozen-ownership enforcement."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.bound_scaffold_record import build_bound_record

_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST.read_text())


def _record():
    return build_bound_record(_manifest(), run_id="r", attempt_id="a", created_at="t")


def _env(task_type="development.develop"):
    return SimpleNamespace(task_id="task-1", task_type=task_type)


def test_frozen_emission_is_restored_others_pass_through():
    """pf-26: a producer emitting the frozen main.py (tampered) has its content restored to the
    scaffold bytes; a fill-slot emission (routes.py) passes through unchanged."""
    artifacts = [
        {"name": "backend/main.py", "content": "TAMPERED = 1\n"},
        {"name": "backend/routes.py", "content": "def real_route(): return 1\n"},
    ]
    enforced = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), artifacts, _record(), _env()
    )
    by_name = {a["name"]: a["content"] for a in enforced}
    # main.py restored to the scaffold's frozen bytes (relative import), not the tamper.
    assert "from .routes import router" in by_name["backend/main.py"]
    assert by_name["backend/main.py"] != "TAMPERED = 1\n"
    # routes.py (a fill slot) is untouched.
    assert by_name["backend/routes.py"] == "def real_route(): return 1\n"


def test_conftest_is_frozen_and_restored_too():
    """The SIP-0100 harness (conftest.py) is frozen — a producer can't overwrite it either."""
    enforced = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), [{"path": "conftest.py", "content": "import os  # tampered"}], _record(), _env()
    )
    assert "client" in enforced[0]["content"]  # restored to the scaffold conftest (has the fixture)


def test_build_bound_record_none_for_unbound_and_unscaffoldable():
    assert DispatchedFlowExecutor._build_bound_record_for_run(object(), None, "r") is None
    bad = InterfaceManifest.from_dict(
        {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "cobol_cics"}
    )
    assert DispatchedFlowExecutor._build_bound_record_for_run(object(), bad, "r") is None


def test_build_bound_record_for_scaffoldable_manifest():
    rec = DispatchedFlowExecutor._build_bound_record_for_run(object(), _manifest(), "r")
    assert rec is not None
    assert "backend/main.py" in rec.frozen_paths()
