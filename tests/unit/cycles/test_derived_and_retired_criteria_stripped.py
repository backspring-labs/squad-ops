"""What the planner may not author, replayed on the plans it actually authored (#1254/#1312).

Two strips, one seam. **Derived** (#1254): the framework binds `harness_boundary` on every
bound qa suite from the scaffold's own entry modules, and the planner authored it anyway on
25 of the last 40 stored plans' qa tasks — both 1.7.1 React shakeouts carried the row twice
on `backend/tests/test_runs.py`. **Retired** (#1312): `qa_handoff.md` is no longer required,
prompted for, or produced, and a criterion over it now evaluates `file_not_found` and
rejects a correct roll.

Replayed against the two shakeouts' stored plans rather than fixtures written here, so the
guard is measured against what a real planner emitted (the 5 and 6 handoff regexes are the
rows #1252 was filed from).
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan, TypedCheck
from squadops.cycles.task_plan import _applicable_acceptance

pytestmark = [pytest.mark.domain_cycles]

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
_PLANS = (
    "1-7-1-react-shakeout-1-implementation_plan.yaml",
    "1-7-1-react-shakeout-2-implementation_plan.yaml",
)


def _plan(name: str) -> ImplementationPlan:
    return ImplementationPlan.from_yaml((_REPLAYS / name).read_text(encoding="utf-8"))


def _typed(task) -> list[TypedCheck]:
    return [c for c in task.acceptance_criteria if isinstance(c, TypedCheck)]


@pytest.mark.parametrize("plan_name", _PLANS)
def test_the_authored_harness_boundary_is_dropped_and_the_rest_survives(plan_name, caplog):
    """The doubling #1254 measured: the planner's row plus the framework's injection, both
    evaluated, on the same file. Dropping the wrong one would remove the check entirely —
    so this also asserts what SURVIVES."""
    plan = _plan(plan_name)
    authored = [t for t in plan.tasks if any(c.check == "harness_boundary" for c in _typed(t))]
    assert authored, "the fixture is not a plan that authored the boundary"

    for task in authored:
        with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
            caplog.clear()
            kept = _applicable_acceptance(task)
        assert [
            c for c in kept if isinstance(c, TypedCheck) and c.check == "harness_boundary"
        ] == []
        assert any("derived_check_stripped" in r.message for r in caplog.records)
        # Everything the author IS entitled to write stays: its coverage floors and prose.
        authored_own = [
            c
            for c in _typed(task)
            if c.check not in {"harness_boundary"} and c.params.get("file") != "qa_handoff.md"
        ]
        assert [c for c in kept if isinstance(c, TypedCheck)] == authored_own
        assert [c for c in task.acceptance_criteria if isinstance(c, str)] == [
            c for c in kept if isinstance(c, str)
        ]


@pytest.mark.parametrize("plan_name", _PLANS)
def test_a_declared_handoff_keeps_its_criteria(plan_name, caplog):
    """#1312 retired the framework's REQUIREMENT, not the word.

    Both stored plans declare `qa_handoff.md` in the builder task's expected_artifacts,
    so the builder produces it and those 5 and 6 criteria are satisfiable. Stripping them
    here would delete real checks on a real deliverable — and the corpus every
    verification set runs on (`examples/03_group_run/prd.md`) still asks for a document
    by that name.
    """
    plan = _plan(plan_name)
    task = next(t for t in plan.tasks if t.task_type == "builder.assemble")
    assert "qa_handoff.md" in {str(a).split("/")[-1] for a in task.expected_artifacts}

    with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
        kept = _applicable_acceptance(task)

    handoff = [c for c in _typed(task) if c.params.get("file") == "qa_handoff.md"]
    assert len(handoff) >= 5
    assert [
        c for c in kept if isinstance(c, TypedCheck) and c.params.get("file") == "qa_handoff.md"
    ] == handoff
    assert not [r for r in caplog.records if "retired_artifact_criterion_stripped" in r.message]


def test_a_criterion_over_an_undeclared_handoff_is_dropped(caplog):
    """The transition case: nothing produces the file, so the check evaluates
    `file_not_found` and rejects a correct roll. The planner has a strong prior about this
    filename — 213 of 213 builder criteria in the last 40 stored plans named it — so a
    quieter prompt alone would not have been an answer."""
    task = SimpleNamespace(
        task_index=3,
        expected_artifacts=["Dockerfile", "README.md"],
        acceptance_criteria=[
            TypedCheck(
                check="regex_match",
                params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                severity="error",
            ),
            TypedCheck(
                check="regex_match",
                params={"file": "README.md", "pattern": "## Configuration"},
                severity="error",
            ),
        ],
    )
    with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
        kept = _applicable_acceptance(task)

    assert [c.params["file"] for c in kept if isinstance(c, TypedCheck)] == ["README.md"]
    assert any("retired_artifact_criterion_stripped" in r.message for r in caplog.records)


def test_a_criterion_over_another_document_is_kept():
    """Over-stripping guard, and the reason the retired strip is keyed on the FILENAME
    rather than on `regex_match`: a README or runbook check is still the author's."""
    task = SimpleNamespace(
        task_index=4,
        expected_artifacts=["README.md"],
        acceptance_criteria=[
            TypedCheck(
                check="regex_match",
                params={"file": "README.md", "pattern": "## Configuration"},
                severity="error",
            ),
            "the package documents its configuration",
        ],
    )
    kept = _applicable_acceptance(task)
    assert len(kept) == 2


def test_a_derived_check_over_a_file_the_framework_would_not_inject_it_on_is_still_dropped():
    """The rule is about WHO owns the check, not about where it would land. A
    `harness_boundary` authored on a file outside the qa namespace is not extra coverage
    the framework missed — its `entry_modules` are a guess at the scaffold's declaration,
    and a guess that happens to sit somewhere the framework does not look is worse, not
    better."""
    task = SimpleNamespace(
        task_index=7,
        expected_artifacts=["backend/helpers.py"],
        acceptance_criteria=[
            TypedCheck(
                check="harness_boundary",
                params={"file": "backend/helpers.py", "entry_modules": ["app.main"]},
                severity="error",
            )
        ],
    )
    assert _applicable_acceptance(task) == []
