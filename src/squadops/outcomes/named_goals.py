"""What became of the goals an increment's change request named (SIP-0113 §4.5; §10t step 5).

A proposal may name, in ``moves_goals``, the goals its change is meant to make pass (SIP-0109
§24by). After the build, each is read against the increment's own evaluation and the evaluation of
the tree it was built on, the tree whose results the proposal was shown:
- ``moved``: not passing before, passing after;
- ``still failing``: not passing before, failing after;
- ``already passing``: passing before and after. Naming one is not refused (§10t ruling 5);
- ``regressed``: passing before, failing after;
- ``not verified``: the evaluator couldn't check it after;
- ``not evaluated``: either tree has no reading of it.

Reporting only, by id: the package and the digest never carry a goal's statement.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from squadops.scenarios.evaluation import EvaluationRecord, ScenarioResult


class GoalMove(StrEnum):
    MOVED = "moved"
    STILL_FAILING = "still failing"
    ALREADY_PASSING = "already passing"
    REGRESSED = "regressed"
    NOT_VERIFIED = "not verified"
    NOT_EVALUATED = "not evaluated"


def _results(record: EvaluationRecord | None) -> dict[str, ScenarioResult | None]:
    return {o.scenario_id: o.result for o in record.outcomes} if record else {}


def named_goal_moves(
    named: Sequence[str], record: EvaluationRecord | None, previous: EvaluationRecord | None
) -> dict[str, GoalMove]:
    """Each named goal's move, in the order the request named them."""
    after, before = _results(record), _results(previous)
    moves: dict[str, GoalMove] = {}
    for goal in dict.fromkeys(named):
        if goal not in after or goal not in before:
            moves[goal] = GoalMove.NOT_EVALUATED
        elif after[goal] not in (ScenarioResult.PASSED, ScenarioResult.FAILED):
            moves[goal] = GoalMove.NOT_VERIFIED
        elif before[goal] is ScenarioResult.PASSED:
            passed = after[goal] is ScenarioResult.PASSED
            moves[goal] = GoalMove.ALREADY_PASSING if passed else GoalMove.REGRESSED
        elif after[goal] is ScenarioResult.PASSED:
            moves[goal] = GoalMove.MOVED
        else:
            moves[goal] = GoalMove.STILL_FAILING
    return moves
