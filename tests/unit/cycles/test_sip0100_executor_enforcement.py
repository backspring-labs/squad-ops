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


def test_frozen_emission_is_dropped_others_pass_through():
    """pf-26: a producer emitting the frozen main.py (tampered) has that artifact dropped; a
    fill-slot emission (routes.py) passes through unchanged.

    #691: the drop replaced a restore-to-scaffold-bytes. Either way the producer cannot
    clobber the scaffold, but the restore also STORED the scaffold's bytes under the
    producer's task type, and that duplicate was read back as producer drift."""
    artifacts = [
        {"name": "backend/main.py", "content": "TAMPERED = 1\n"},
        {"name": "backend/routes.py", "content": "def real_route(): return 1\n"},
    ]
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), artifacts, _record(), _env()
    )
    by_name = {a["name"]: a["content"] for a in enforced}
    # The tamper never lands, and no copy of the frozen file is emitted under this producer.
    assert "backend/main.py" not in by_name
    # routes.py (a fill slot) is untouched.
    assert by_name["backend/routes.py"] == "def real_route(): return 1\n"
    # 3.3: exactly one evidence record (the frozen violation), the sibling routes.py is retained.
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.normalized_path == "backend/main.py"
    assert ev.violation_code == "frozen_path_emission"
    assert ev.kind == "attempted_emission"
    assert ev.disposition == "dropped"
    assert ev.siblings_retained == 1  # routes.py kept
    assert ev.producer_task_id == "task-1"
    # attempted hash reflects the tamper; expected hash reflects the scaffold bytes — they differ.
    assert ev.attempted_sha256 is not None
    assert ev.expected_sha256 is not None
    assert ev.attempted_sha256 != ev.expected_sha256


def test_conftest_is_frozen_and_dropped_too():
    """The SIP-0100 harness (conftest.py) is frozen — a producer can't overwrite it either.

    A frozen-only response therefore accepts nothing, which is the honest outcome: the
    producer emitted no file it was authorized to write."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), [{"path": "conftest.py", "content": "import os  # tampered"}], _record(), _env()
    )
    assert enforced == []
    assert evidence[0].normalized_path == "conftest.py"
    assert evidence[0].siblings_retained == 0  # the only artifact in the response


def test_clean_response_yields_no_evidence():
    """A producer that writes only its fill slot emits no violation and no evidence."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), [{"name": "backend/routes.py", "content": "x = 1\n"}], _record(), _env()
    )
    assert evidence == []
    assert enforced[0]["content"] == "x = 1\n"


# ---- 3.1: QA producers are scoped to the QA test namespace ----


def test_qa_write_to_dev_fill_slot_is_dropped():
    """3.1: a qa.test task rewriting dev's routes.py (the source under test) is DROPPED — the
    owning producer's version stays. This is the pf-26 class one step past the frozen main.py."""
    artifacts = [
        {"name": "backend/tests/test_api.py", "content": "def test_x(): assert True\n"},
        {"name": "backend/routes.py", "content": "def sneaky(): return 1\n"},
    ]
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), artifacts, _record(), _env("qa.test")
    )
    names = {a["name"] for a in enforced}
    assert "backend/routes.py" not in names  # dropped
    assert "backend/tests/test_api.py" in names  # QA's own test kept
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.normalized_path == "backend/routes.py"
    assert ev.violation_code == "unauthorized_slot_emission"
    assert ev.disposition == "dropped"
    assert ev.expected_sha256 is None  # a fill slot has no canonical scaffold bytes
    assert ev.attempted_sha256 is not None
    assert ev.siblings_retained == 1  # the test file passed through


def test_qa_write_in_its_namespace_passes():
    """A QA task writing its own tests is authorized — no evidence, content untouched."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "backend/tests/test_api.py", "content": "T = 1\n"}],
        _record(),
        _env("qa.test"),
    )
    assert evidence == []
    assert enforced[0]["content"] == "T = 1\n"


def test_qa_undeclared_deliverable_is_allowed():
    """An undeclared path (a QA deliverable like test_report.md) is NOT dropped — we can't tell it
    from a rogue file here, so leaving it be keeps QA's reports safe (undeclared-reject is 3.4)."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "test_report.md", "content": "# report\n"}],
        _record(),
        _env("qa.test"),
    )
    assert evidence == []
    assert enforced[0]["content"] == "# report\n"


def test_qa_write_to_frozen_reports_the_frozen_violation_not_the_slot_one():
    """3.1 does not weaken 2.4: a QA emission of frozen main.py is enforced as a FROZEN
    violation, not reclassified as an unauthorized-slot one — the reason code is what a
    correction reads to know the path is scaffold-owned and permanently unwritable."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "backend/main.py", "content": "TAMPER\n"}],
        _record(),
        _env("qa.test"),
    )
    assert enforced == []
    assert evidence[0].violation_code == "frozen_path_emission"
    assert evidence[0].disposition == "dropped"


def test_dev_write_to_its_own_fill_slot_is_not_dropped():
    """3.1 scopes QA only: a dev task writing dev's routes.py is legitimate and untouched."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "backend/routes.py", "content": "def real(): return 1\n"}],
        _record(),
        _env("development.develop"),
    )
    assert evidence == []
    assert enforced[0]["content"] == "def real(): return 1\n"


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


# ---------------------------------------------------------------------------
# #649: builder write authorization — assembly re-packages, it does not author
# ---------------------------------------------------------------------------


def test_builder_net_new_source_is_dropped():
    """fay-7: bob authored an uninstructed root start.py (StaticFiles mount on
    frontend/dist) — import-time RuntimeError in every test workspace, and
    dev-scoped repairs structurally never touch a builder artifact. Net-new
    source at assembly is refused at emission, with evidence."""
    artifacts = [
        {"name": "start.py", "content": "from backend.main import app\n"},
        {"name": "qa_handoff.md", "content": "## How to Run\n"},
    ]
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(), artifacts, _record(), _env("builder.assemble")
    )
    names = {a["name"] for a in enforced}
    assert "start.py" not in names  # dropped
    assert "qa_handoff.md" in names  # the deliverable passes
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.normalized_path == "start.py"
    assert ev.disposition == "dropped"
    assert ev.siblings_retained == 1


def test_builder_fill_surface_reemission_passes():
    """Assembly's whole job: re-packaging the accepted fill files stays authorized."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "backend/routes.py", "content": "def assembled(): return 1\n"}],
        _record(),
        _env("builder.assemble"),
    )
    assert evidence == []
    assert enforced[0]["content"] == "def assembled(): return 1\n"


def test_builder_write_into_qa_namespace_is_dropped():
    """The QA namespace is another producer's lane — a builder emission there is
    refused the same way QA's writes to dev slots are."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "backend/tests/test_sneaky.py", "content": "def test_x(): pass\n"}],
        _record(),
        _env("builder.assemble"),
    )
    assert enforced == []
    assert len(evidence) == 1
    assert evidence[0].violation_code == "unauthorized_slot_emission"


def test_builder_undeclared_non_source_passes_and_frozen_still_drops():
    """Docs/reports remain deliverables; frozen enforcement applies to builders too."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [
            {"name": "deploy_notes.md", "content": "# notes\n"},
            {"name": "backend/main.py", "content": "TAMPERED = 1\n"},
        ],
        _record(),
        _env("builder.assemble"),
    )
    by_name = {a["name"]: a["content"] for a in enforced}
    assert by_name["deploy_notes.md"] == "# notes\n"
    assert "backend/main.py" not in by_name  # dropped
    assert len(evidence) == 1 and evidence[0].violation_code == "frozen_path_emission"


def test_dev_producer_unaffected_by_builder_rule():
    """A dev task emitting an undeclared .py helper keeps today's behavior (passes) —
    the #649 rule scopes builders only; dev undeclared-reject stays gated on 3.4."""
    enforced, evidence = DispatchedFlowExecutor._enforce_frozen_ownership(
        object(),
        [{"name": "backend/helpers.py", "content": "X = 1\n"}],
        _record(),
        _env("development.develop"),
    )
    assert evidence == []
    assert enforced[0]["content"] == "X = 1\n"
