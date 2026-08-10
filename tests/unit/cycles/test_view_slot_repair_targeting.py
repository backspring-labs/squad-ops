"""Which files are views is the contract's answer, not a directory prefix (#822).

`_widen_target_for_frontend_build` exists because of fay-8 (cyc_7f5f1b8b1790): five correction
rounds, four identical `frontend_build` failures, every repair emitting backend and test files
only — RC2's package scoping never reaches `frontend/*`, so the loop polished a passing backend
while the build-breaking view sat outside every target. #650 closed it by unioning frontend
source into the repair target.

It identified that source as `path.startswith("frontend/")`. That is stack #1's layout stated as
a property of views. A stack that builds at the project root unions nothing, and the trap
reopens intact — in the correction path, where it costs a full round each time rather than one
check.

The fix is the relation `_probe_owned_slots` already uses (#688), one criterion over: only the
contract joins "the manifest declared these views" to "the blueprint put them here."

Bug classes guarded:

- **a root-built stack's views never reaching the repair target**, which is fay-8 again for
  stack #2 and costs correction budget per round;
- **stack #1's target changing**, which would alter repair behavior on the configuration the
  release's banked evidence was measured on;
- the accessor reading a prefix by another name — a view outside `frontend/` must be found
  *because the contract says it is a view*, not because of where it sits;
- the value being computed and not carried. #796 was exactly this: an artifact stored,
  validated, promoted, and silently not forwarded, so the capability was dead while looking
  built;
- the widening firing when no frontend build failed, or crashing when the contract carries no
  views at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.cycles.correction_runner import _widen_target_for_frontend_build
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_contracts]

_REFERENCE = InterfaceManifest.from_yaml(
    (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "03_group_run"
        / "interface_manifest.yaml"
    ).read_text(encoding="utf-8")
)


def _failed_build_evidence() -> dict:
    return {"validation_result": {"checks": [{"check": "frontend_build", "passed": False}]}}


def _contract(fill_files: dict) -> VerificationContract:
    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {"expander": "s", "interface_manifest_hash": "h"},
            "capabilities": [],
            "frozen": [],
            "fill_files": fill_files,
            "behavioral": {
                "build": [],
                "suite": {"checks": [], "coverage_expectations": []},
                "probes": [],
            },
        }
    )


# --------------------------------------------------------------------------- #
# The relation
# --------------------------------------------------------------------------- #


def test_the_reference_contract_names_its_three_views():
    """Exact values: this is the set the prefix used to produce, so a difference here is a
    behavior change on the configuration 1.4's evidence was measured against."""
    contract = VerificationContract.from_dict(emit_contract_dict(_REFERENCE))

    assert contract.view_slots() == (
        "frontend/src/views/RunsListView.jsx",
        "frontend/src/views/CreateRunView.jsx",
        "frontend/src/views/RunDetailView.jsx",
    )


def test_a_view_outside_the_first_stacks_directory_is_still_a_view():
    """The whole point. `app/runs/page.tsx` is a view because the contract bundler-checks it,
    not because of where it sits — a prefix rule answers "no views" for this contract."""
    contract = _contract(
        {
            "app/runs/page.tsx": {
                "interface": [],
                "implementation": [
                    {"check": "frontend_compiles", "id": "vc-v", "file": "app/runs/page.tsx"}
                ],
            },
            "app/api/runs/route.ts": {
                "interface": [
                    {"check": "endpoint_defined", "id": "vc-r", "methods_paths": ["GET /runs"]}
                ],
                "implementation": [],
            },
        }
    )

    assert contract.view_slots() == ("app/runs/page.tsx",)
    assert not [p for p in contract.view_slots() if p.startswith("frontend/")]


def test_a_contract_that_bundler_checks_nothing_has_no_views():
    """A backend-only stack must yield an empty tuple rather than raising — and it is the same
    condition under which no `frontend_build` row can fail, so the caller is unaffected."""
    contract = _contract(
        {
            "src/routes.go": {
                "interface": [],
                "implementation": [
                    {"check": "command_exit_zero", "id": "x", "argv": ["go", "build"]}
                ],
            }
        }
    )

    assert contract.view_slots() == ()


# --------------------------------------------------------------------------- #
# The widening
# --------------------------------------------------------------------------- #


def test_a_root_built_stacks_views_reach_the_repair_target():
    """fay-8 for stack #2. Under the prefix rule this returned the target unchanged, and the
    correction loop would repair everything except the file that broke the build."""
    target = _widen_target_for_frontend_build(
        ["app/api/runs/route.ts"],
        _failed_build_evidence(),
        {
            "contract_view_slots": ["app/runs/page.tsx"],
            "implementation_artifacts": ["app/runs/page.tsx"],
        },
    )

    assert target == ["app/api/runs/route.ts", "app/runs/page.tsx"]


def test_the_first_stacks_widening_is_unchanged():
    """Same three views the prefix produced, in the same union order."""
    views = list(VerificationContract.from_dict(emit_contract_dict(_REFERENCE)).view_slots())

    target = _widen_target_for_frontend_build(
        ["backend/routes.py"], _failed_build_evidence(), {"contract_view_slots": views}
    )

    assert target == ["backend/routes.py", *views]


def test_no_widening_when_the_build_did_not_fail():
    """The widening is conditional on the evidence, not on the inputs being present."""
    target = _widen_target_for_frontend_build(
        ["backend/routes.py"],
        {"validation_result": {"checks": [{"check": "frontend_build", "passed": True}]}},
        {"contract_view_slots": ["frontend/src/views/V.jsx"]},
    )

    assert target == ["backend/routes.py"]


@pytest.mark.parametrize("inputs", [{}, {"contract_view_slots": []}, {"contract_view_slots": None}])
def test_absent_view_slots_leave_the_target_alone(inputs):
    """Pre-#822 envelopes and contract-less cycles must be byte-identical, never crash."""
    assert _widen_target_for_frontend_build(["a.py"], _failed_build_evidence(), inputs) == ["a.py"]


def test_the_target_does_not_duplicate_a_view_already_in_it():
    """The union is order-preserving and deduplicated — a duplicated path would be handed to
    the repair prompt twice."""
    target = _widen_target_for_frontend_build(
        ["frontend/src/views/V.jsx"],
        _failed_build_evidence(),
        {"contract_view_slots": ["frontend/src/views/V.jsx"]},
    )

    assert target == ["frontend/src/views/V.jsx"]


# --------------------------------------------------------------------------- #
# The wiring — computed is not carried
# --------------------------------------------------------------------------- #


def test_the_composer_threads_the_view_slots_onto_the_task():
    """#796's lesson: an artifact was stored, validated, promoted and silently not forwarded,
    so authored mode was dead while looking built. An accessor nothing carries is the same
    defect — this asserts the value reaches task inputs, not merely that it can be computed."""
    from squadops.capabilities.context_assembly import get_context_contract
    from squadops.cycles.task_plan import inject_contract_inputs

    contract = VerificationContract.from_dict(emit_contract_dict(_REFERENCE))
    task_type = next(
        t
        for t in ("qa.test", "development.implement_task")
        if get_context_contract(t).bind_behavioral_surface
    )

    inputs: dict = {}
    inject_contract_inputs(inputs, contract, task_type, _REFERENCE)

    assert inputs["contract_view_slots"] == list(contract.view_slots())
