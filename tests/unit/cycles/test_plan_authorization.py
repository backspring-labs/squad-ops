"""SIP-0100 follow-up — plan-authoring target authorization (Phase B validation)."""

from __future__ import annotations

from types import SimpleNamespace

from squadops.cycles.plan_authorization import (
    PlanAuthorization,
    PlanTargetViolation,
    validate_plan_write_targets,
)
from squadops.cycles.verification_contract import (
    Behavioral,
    FillFile,
    FrozenFile,
    Skeleton,
    VerificationContract,
)

_AUTHZ = PlanAuthorization(
    read_only_paths=frozenset({"backend/main.py", "backend/models.py", "frontend/src/App.jsx"}),
    dev_writable=frozenset({"backend/routes.py", "frontend/src/views/RunCreationForm.jsx"}),
    qa_namespace=("backend/tests/", "frontend/src/tests/"),
    required_coverage=frozenset({"backend/routes.py", "frontend/src/views/RunCreationForm.jsx"}),
    source_prefixes=("backend/", "frontend/src/", "frontend/src/views/"),
    contract_hash="mh123",
)


def _task(task_type, targets, idx=0, role="dev"):
    return SimpleNamespace(
        task_type=task_type, expected_artifacts=list(targets), task_index=idx, role=role
    )


def _full_coverage_dev():
    """Two dev tasks that assign both required slots exactly once (a clean baseline)."""
    return [
        _task("development.develop", ["backend/routes.py"], idx=0),
        _task("development.develop", ["frontend/src/views/RunCreationForm.jsx"], idx=1),
    ]


def _codes(rejections):
    return {r.code for r in rejections}


def test_valid_plan_passes_clean():
    assert validate_plan_write_targets(_full_coverage_dev(), _AUTHZ) == []


def test_frozen_target_rejected():
    tasks = _full_coverage_dev() + [_task("development.develop", ["backend/main.py"], idx=2)]
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    hits = [r for r in rej if r.canonical_target == "backend/main.py"]
    assert hits and hits[0].code == PlanTargetViolation.UNAUTHORIZED
    assert "frozen" in hits[0].detail
    # frozen rejection offers the fill slots as alternatives
    assert "backend/routes.py" in hits[0].nearest_slots


def test_undeclared_workspace_source_rejected():
    tasks = _full_coverage_dev() + [
        _task("development.develop", ["backend/store.py", "frontend/src/components/X.tsx"], idx=2)
    ]
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    bad = {r.canonical_target for r in rej if r.code == PlanTargetViolation.UNAUTHORIZED}
    assert "backend/store.py" in bad  # under backend/, not a slot
    assert "frontend/src/components/X.tsx" in bad  # under frontend/src/, not a slot


def test_glob_and_directory_targets_are_ambiguous():
    tasks = [
        _task("development.develop", ["frontend/src/components/*.tsx"], idx=0),
        _task("development.develop", ["frontend/src/views/"], idx=1),
    ]
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    ambiguous = [r for r in rej if r.code == PlanTargetViolation.AMBIGUOUS_SCOPE]
    assert {r.raw_target for r in ambiguous} == {
        "frontend/src/components/*.tsx",
        "frontend/src/views/",
    }


def test_normalized_and_traversal_aliases_authorize_as_the_slot():
    """./ and ../ aliases of a fill slot resolve to the slot (D7) — authorized, and they satisfy
    coverage so no MISSING_REQUIRED_SLOT fires for that slot."""
    tasks = [
        _task("development.develop", ["./backend/routes.py"], idx=0),
        _task("development.develop", ["frontend/src/foo/../views/RunCreationForm.jsx"], idx=1),
    ]
    assert validate_plan_write_targets(tasks, _AUTHZ) == []


def test_root_deliverable_is_allowed():
    tasks = _full_coverage_dev() + [
        _task("development.develop", ["qa_handoff.md", "requirements.txt"], idx=2)
    ]
    # deliverables sit under no source prefix → allowed (v1-permissive); no rejection for them
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    assert not any(r.raw_target in ("qa_handoff.md", "requirements.txt") for r in rej)


def test_qa_namespace_ok_but_cross_role_rejected():
    qa_ok = _task("qa.test", ["backend/tests/test_runs.py"], idx=5, role="qa")
    qa_source = _task("qa.test", ["backend/routes.py"], idx=6, role="qa")
    dev_test = _task("development.develop", ["backend/tests/test_x.py"], idx=7)
    rej = validate_plan_write_targets([qa_ok, qa_source, dev_test], _AUTHZ)
    by_target = {r.canonical_target: r for r in rej if r.code == PlanTargetViolation.UNAUTHORIZED}
    assert "backend/tests/test_runs.py" not in by_target  # QA in its namespace is fine
    assert "backend/routes.py" in by_target  # QA writing dev's slot
    assert "backend/tests/test_x.py" in by_target  # dev writing a test


def test_missing_required_slot():
    tasks = [_task("development.develop", ["backend/routes.py"], idx=0)]  # view slot unassigned
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    missing = [r for r in rej if r.code == PlanTargetViolation.MISSING_REQUIRED_SLOT]
    assert [r.canonical_target for r in missing] == ["frontend/src/views/RunCreationForm.jsx"]


def test_duplicate_slot_ownership():
    tasks = [
        _task("development.develop", ["backend/routes.py"], idx=0),
        _task("development.develop", ["backend/routes.py"], idx=1),
        _task("development.develop", ["frontend/src/views/RunCreationForm.jsx"], idx=2),
    ]
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    assert PlanTargetViolation.DUPLICATE_OWNERSHIP in _codes(rej)


def test_all_defects_returned_atomically():
    """A plan with several defects returns them all — the caller rejects the whole plan, never
    silently strips a target."""
    tasks = [_task("development.develop", ["backend/main.py", "backend/store.py"], idx=0)]
    rej = validate_plan_write_targets(tasks, _AUTHZ)
    # 2 unauthorized targets + 2 missing required slots
    assert len([r for r in rej if r.code == PlanTargetViolation.UNAUTHORIZED]) == 2
    assert len([r for r in rej if r.code == PlanTargetViolation.MISSING_REQUIRED_SLOT]) == 2


def test_from_contract_derives_the_surfaces():
    contract = VerificationContract(
        contract_version=1,
        skeleton=Skeleton(expander="fullstack_fastapi_react", interface_manifest_hash="mh9"),
        capabilities=(),
        frozen_files=(FrozenFile("backend/main.py", "h"), FrozenFile("frontend/src/App.jsx", "h")),
        fill_files=(FillFile("backend/routes.py"), FillFile("frontend/src/views/X.jsx")),
        behavioral=Behavioral(),
    )
    authz = PlanAuthorization.from_contract(contract)
    assert authz.read_only_paths == {"backend/main.py", "frontend/src/App.jsx"}
    assert authz.dev_writable == {"backend/routes.py", "frontend/src/views/X.jsx"}
    assert authz.qa_namespace == ("backend/tests/", "frontend/src/tests/")
    assert authz.required_coverage == authz.dev_writable
    assert authz.contract_hash == "mh9"
    # source prefixes cover both stacks so undeclared source is caught
    assert "backend/" in authz.source_prefixes
    assert "frontend/src/" in authz.source_prefixes
