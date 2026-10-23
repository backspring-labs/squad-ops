"""What became of the goals an increment's request named (SIP-0113 §4.5; §10t step 5).

What bugs would these catch? A goal that passed before read as moved, so a proposal aimed at a goal
already met scores as a prediction kept; a blocked result read as failing or as moved; a goal with
no reading on either tree read as anything but not evaluated; and a goal named twice counted twice.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.outcomes.named_goals import GoalMove, named_goal_moves
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
)
from squadops.scenarios.quality import LintReading, QualityReading, QualityStatus

pytestmark = [pytest.mark.domain_contracts]

P, F, B = ScenarioResult.PASSED, ScenarioResult.FAILED, ScenarioResult.BLOCKED_UNVERIFIED


def _record(**results) -> EvaluationRecord:
    outcomes = tuple(
        ScenarioOutcome(
            goal_id,
            1,
            "an invented goal",
            Applicability.APPLICABLE,
            result,
            blocked_reason=BlockedReason.SURFACE_ABSENT if result is B else None,
            first_failing_step=1 if result is F else None,
        )
        for goal_id, result in results.items()
    )
    return EvaluationRecord(
        evaluation_id="evl_x",
        project_id="p",
        campaign_id="cmp_x",
        cycle_id="cyc_x",
        evaluated_tree_identity="t",
        previous_accepted_tree_identity=None,
        suite_digest="d",
        outcomes=outcomes,
        evaluated_at=datetime(2026, 10, 22, tzinfo=UTC),
        quality=QualityReading(QualityStatus.MEASURED, pages=(), evaluator="e"),
        lint=LintReading(QualityStatus.MEASURED, reading={}, evaluator="e"),
    )


@pytest.mark.parametrize(
    ("before", "after", "move"),
    [
        (F, P, GoalMove.MOVED),
        (B, P, GoalMove.MOVED),
        (F, F, GoalMove.STILL_FAILING),
        (B, F, GoalMove.STILL_FAILING),
        (P, P, GoalMove.ALREADY_PASSING),
        (P, F, GoalMove.REGRESSED),
        (F, B, GoalMove.NOT_VERIFIED),
        (P, B, GoalMove.NOT_VERIFIED),
    ],
)
def test_a_named_goal_moves_by_its_results_before_and_after(before, after, move):
    assert named_goal_moves(["g"], _record(g=after), _record(g=before)) == {"g": move}


@pytest.mark.parametrize(
    ("record", "previous"),
    [
        (None, _record(g=F)),
        (_record(g=P), None),
        (_record(other=P), _record(g=F)),
        (_record(g=P), _record(other=F)),
    ],
)
def test_a_goal_either_tree_has_no_reading_of_is_not_evaluated(record, previous):
    assert named_goal_moves(["g"], record, previous) == {"g": GoalMove.NOT_EVALUATED}


def test_each_goal_is_read_once_in_the_order_it_was_named():
    moves = named_goal_moves(["b", "a", "b"], _record(a=P, b=F), _record(a=F, b=F))

    assert list(moves.items()) == [("b", GoalMove.STILL_FAILING), ("a", GoalMove.MOVED)]
