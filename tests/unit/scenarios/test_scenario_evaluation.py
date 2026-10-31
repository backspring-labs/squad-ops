"""An evaluation run's record (SIP-0113 §4.1, §4.8; #2415)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    ScenarioOutcome,
    ScenarioResult,
    evaluation_record,
)
from squadops.scenarios.models import parse_suite
from squadops.scenarios.quality import LintReading, NotMeasured, QualityReading, QualityStatus
from squadops.scenarios.reference import EvaluationInvalid
from squadops.scenarios.suites import draft_suite
from tests.unit.scenarios.suite_fixtures import SUITE

T0 = datetime(2026, 10, 18, 21, 0, tzinfo=UTC)
TREE, PREVIOUS = "a" * 64, "b" * 64


def _outcomes(suite, **overrides) -> tuple[ScenarioOutcome, ...]:
    first, second = suite.scenarios
    return (
        ScenarioOutcome(
            first.scenario_id,
            first.version,
            first.goal,
            Applicability.APPLICABLE,
            ScenarioResult.PASSED,
            steps_taken=3,
        ),
        ScenarioOutcome(
            second.scenario_id,
            second.version,
            second.goal,
            Applicability.APPLICABLE,
            overrides.get("result", ScenarioResult.BLOCKED_UNVERIFIED),
            blocked_reason=overrides.get("reason", BlockedReason.NO_START_DECLARATION),
        ),
    )


def _record(suite, outcomes, **kwargs):
    return evaluation_record(
        suite,
        outcomes,
        project_id="group_run",
        campaign_id=kwargs.get("campaign_id", "cmp_eval00000001"),
        cycle_id="cyc_eval00000001",
        evaluated_tree_identity=TREE,
        previous_accepted_tree_identity=PREVIOUS,
        evaluated_at=kwargs.get("at", T0),
        quality=QualityReading(QualityStatus.NOT_APPLICABLE),
        lint=LintReading.not_measured(NotMeasured.NO_RUNNER),
    )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (dict(applicability="not_applicable", result="passed"), "not applicable, so it has no"),
        (dict(applicability="applicable", result=None), "applicable, so it has a result"),
        (dict(result="blocked_unverified", blocked_reason=None), "names why"),
        (dict(result="passed", blocked_reason="start_failed"), "names why"),
        (dict(result="failed", first_failing_step=None), "first failing step"),
    ],
    ids=[
        "not-applicable-with-a-result",
        "applicable-without-one",
        "blocked-without-a-reason",
        "passed-with-a-reason",
        "failed-without-its-step",
    ],
)
def test_an_outcome_that_says_two_things_at_once_is_refused(fields, message):
    """§4.1 and SIP-0112 §8.3.1. Bug caught: a not-applicable scenario counted in a rate, a
    blocked one with no reason (read later as a failure), or a failure that can't say where."""
    values = dict(
        scenario_id="s",
        version="v",
        goal="g",
        applicability="applicable",
        result="passed",
        blocked_reason=None,
        first_failing_step=None,
    )
    values.update(fields)
    with pytest.raises(EvaluationInvalid, match=message):
        ScenarioOutcome(
            scenario_id=values["scenario_id"],
            version=values["version"],
            goal=values["goal"],
            applicability=Applicability(values["applicability"]),
            result=ScenarioResult(values["result"]) if values["result"] else None,
            blocked_reason=BlockedReason(values["blocked_reason"])
            if values["blocked_reason"]
            else None,
            first_failing_step=values["first_failing_step"],
        )


@pytest.mark.parametrize("cut", ["missing", "repeated", "other-version"])
def test_a_record_names_its_suites_scenarios_exactly(cut):
    """Bug caught: a record that omits a scenario (its absence reads as nothing tested), repeats
    one, or reports a version the suite doesn't hold."""
    suite = parse_suite(SUITE)
    outcomes = _outcomes(suite)
    if cut == "missing":
        outcomes = outcomes[:1]
    elif cut == "repeated":
        outcomes = (outcomes[0], outcomes[0], outcomes[1])
    else:
        first = outcomes[0]
        outcomes = (
            ScenarioOutcome(
                first.scenario_id, "0" * 64, first.goal, first.applicability, first.result
            ),
            outcomes[1],
        )

    with pytest.raises(EvaluationInvalid, match="each of its suite's scenarios once"):
        _record(suite, outcomes)


async def test_a_cycle_evaluated_twice_keeps_both_records_in_order():
    """§4.1: a cycle can be evaluated more than once. Bug caught: a re-run after a
    blocked_unverified result overwriting the first, or a record for a suite nothing holds."""
    store = MemoryScenarioStore()
    suite = parse_suite(SUITE)
    await draft_suite(store, suite, actor="supervisor", at=T0)
    first = _record(suite, _outcomes(suite), at=T0)
    rerun = _record(
        suite,
        _outcomes(suite, result=ScenarioResult.PASSED, reason=None),
        at=T0.replace(hour=22),
    )

    await store.save_evaluation(rerun)
    await store.save_evaluation(first)

    assert await store.evaluations_for_cycle("cyc_eval00000001") == [first, rerun]
    assert await store.get_evaluation(first.evaluation_id) == first
    with pytest.raises(ValueError, match="already written"):
        await store.save_evaluation(first)
    orphan = _record(
        parse_suite({**SUITE, "scenarios": SUITE["scenarios"][:1]}), _outcomes(suite)[:1]
    )
    with pytest.raises(ValueError, match="no suite"):
        await store.save_evaluation(orphan)
