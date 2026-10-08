"""The plan-review tier's verdict (SIP-0109 §24bj, #1708).

Bug classes guarded: the tier approving a plan one condition should have escalated (it approves
only when all hold, and it may only approve); a calibration escalated for the builder's notes at
the root, which would park every calibration; a footprint read wrongly, so scope reads true of
nothing; and a verdict whose notes do not say what each condition read.
"""

from __future__ import annotations

import pytest

from squadops.campaigns.models import CycleKind
from squadops.campaigns.plan_review_tier import (
    TierCondition,
    plan_footprint,
    plan_review_tier,
)

SCOPE = ("backend/**", "frontend/**")
#: The calibration footprint this line's plans named (`cyc_17cd76a351a0`): the builder's notes sit
#: at the root, outside the objective's scope.
CALIBRATION_FOOTPRINT = ("backend/routes.py", "frontend/src/App.jsx", "assembly_notes.md")


def _verdict(**overrides):
    values = dict(
        kind=CycleKind.INCREMENT,
        open_questions=(),
        footprint=("backend/routes.py", "backend/tests/test_runs.py"),
        allowed_scope=SCOPE,
        refused_framing_runs=(),
        answered_on_record={},
    )
    values.update(overrides)
    return plan_review_tier(**values)


def test_a_plan_every_condition_holds_for_is_approved_with_each_reading_in_its_notes():
    verdict = _verdict()

    assert verdict.approves
    assert verdict.failed == ()
    notes = verdict.notes()
    assert "Plan validation passed" in notes
    assert "no_open_question: held: the design asks nothing" in notes
    assert "inside_scope: held: all 2 files inside (backend/**, frontend/**)" in notes
    assert "framed_once: held: the framing ran once" in notes


@pytest.mark.parametrize(
    ("overrides", "failed", "reading"),
    [
        (
            {"open_questions": ("which order does the runs list use?",)},
            TierCondition.NO_OPEN_QUESTION,
            "1 open: which order does the runs list use?",
        ),
        (
            {"open_questions": None},
            TierCondition.NO_OPEN_QUESTION,
            "the cycle has no interface manifest",
        ),
        (
            {"footprint": ("backend/routes.py", "docker-compose.yml")},
            TierCondition.INSIDE_SCOPE,
            "outside (backend/**, frontend/**): docker-compose.yml",
        ),
        ({"footprint": ()}, TierCondition.INSIDE_SCOPE, "the plan names no file"),
        (
            {"refused_framing_runs": ("run_first",)},
            TierCondition.FRAMED_ONCE,
            "plan validation refused and re-rolled run_first",
        ),
    ],
    ids=["an open question", "no manifest", "outside scope", "no footprint", "a re-roll"],
)
def test_any_one_condition_missing_escalates_and_names_what_it_read(overrides, failed, reading):
    verdict = _verdict(**overrides)

    assert not verdict.approves
    assert [c.condition for c in verdict.failed] == [failed]
    assert reading in verdict.failed[0].reading
    assert f"{failed}: FAILED: " in verdict.notes()


@pytest.mark.parametrize(
    ("kind", "approves"),
    [
        (CycleKind.CALIBRATION, True),
        (CycleKind.INCREMENT, False),
        (CycleKind.REPAIR, False),
        (CycleKind.RETRY, False),
    ],
)
def test_only_a_calibration_is_exempt_from_the_scope(kind, approves):
    """The owner's ruling of 2026-10-08: a calibration builds the baseline the scope is read
    against. Bug caught either way: every calibration parked for its builder notes, or an
    increment, repair or retry let out of the scope it evolves inside."""
    verdict = _verdict(kind=kind, footprint=CALIBRATION_FOOTPRINT)

    assert verdict.approves is approves


def test_the_footprint_is_every_tasks_expected_artifacts_once_in_first_seen_order():
    plan = """\
version: 1
project_id: group_run
cycle_id: cyc_x
prd_hash: h
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: routes
    description: d
    expected_artifacts: [backend/routes.py, backend/errors.py]
    acceptance_criteria: [a]
  - task_index: 1
    task_type: qa.test
    role: qa
    focus: tests
    description: d
    expected_artifacts: [backend/tests/test_t5.py, backend/routes.py]
    acceptance_criteria: [a]
    depends_on: [0]
summary:
  total_dev_tasks: 1
  total_qa_tasks: 1
  total_tasks: 2
  estimated_layers: [backend]
"""
    assert plan_footprint(plan) == (
        "backend/routes.py",
        "backend/errors.py",
        "backend/tests/test_t5.py",
    )


@pytest.mark.parametrize("plan", [None, "", "::: not yaml :::", "version: 1\ntasks: []\n"])
def test_an_absent_or_unreadable_plan_has_no_footprint_so_it_escalates(plan):
    assert plan_footprint(plan) == ()
    assert not _verdict(footprint=plan_footprint(plan)).approves
