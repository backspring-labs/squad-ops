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
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), artifacts, _record(), _env()
    )
    by_name = {a["name"]: a["content"] for a in enforced}
    # main.py restored to the scaffold's frozen bytes (relative import), not the tamper.
    assert "from .routes import router" in by_name["backend/main.py"]
    assert by_name["backend/main.py"] != "TAMPERED = 1\n"
    # routes.py (a fill slot) is untouched.
    assert by_name["backend/routes.py"] == "def real_route(): return 1\n"
    # 3.3: exactly one evidence record (the frozen violation), the sibling routes.py is retained.
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.normalized_path == "backend/main.py"
    assert ev.violation_code == "frozen_path_emission"
    assert ev.kind == "attempted_emission"
    assert ev.disposition == "restored"
    assert ev.siblings_retained == 1  # routes.py kept
    assert ev.producer_task_id == "task-1"
    # attempted hash reflects the tamper; expected hash reflects the scaffold bytes — they differ.
    assert ev.attempted_sha256 is not None
    assert ev.expected_sha256 is not None
    assert ev.attempted_sha256 != ev.expected_sha256


def test_conftest_is_frozen_and_restored_too():
    """The SIP-0100 harness (conftest.py) is frozen — a producer can't overwrite it either."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), [{"path": "conftest.py", "content": "import os  # tampered"}], _record(), _env()
    )
    assert "client" in enforced[0]["content"]  # restored to the scaffold conftest (has the fixture)
    assert evidence[0].normalized_path == "conftest.py"
    assert evidence[0].siblings_retained == 0  # the only artifact in the response


def test_clean_response_yields_no_evidence():
    """A producer that writes only its fill slot emits no violation and no evidence."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), [{"name": "backend/routes.py", "content": "x = 1\n"}], _record(), _env()
    )
    assert evidence == []
    assert enforced[0]["content"] == "x = 1\n"


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
