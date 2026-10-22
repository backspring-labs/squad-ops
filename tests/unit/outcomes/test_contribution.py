"""Contribution, per increment (SIP-0113 §4.4; #2418): the increment's evaluation read against the
accepted tree's, by the same suite, never written by a model."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.outcomes.contribution import NotComparable, Reading, contribution
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
)

T0 = datetime(2026, 10, 19, tzinfo=UTC)
BASE, INCREMENT = "a" * 64, "b" * 64
P, F = ScenarioResult.PASSED, ScenarioResult.FAILED


def _outcome(scenario_id: str, state) -> ScenarioOutcome:
    common = {"scenario_id": scenario_id, "version": "v" * 64, "goal": f"{scenario_id}'s goal"}
    if state == "n/a":
        return ScenarioOutcome(**common, applicability=Applicability.NOT_APPLICABLE)
    if isinstance(state, BlockedReason):
        return ScenarioOutcome(
            **common,
            applicability=Applicability.APPLICABLE,
            result=ScenarioResult.BLOCKED_UNVERIFIED,
            blocked_reason=state,
        )
    return ScenarioOutcome(
        **common,
        applicability=Applicability.APPLICABLE,
        result=state,
        first_failing_step=1 if state is F else None,
    )


def _record(tree: str, built_on: str | None, suite: str = "s" * 64, **states) -> EvaluationRecord:
    return EvaluationRecord(
        evaluation_id=f"evl_{tree[:4]}",
        project_id="group_run",
        campaign_id="cmp_window00001",
        cycle_id=f"cyc_{tree[:12]}",
        evaluated_tree_identity=tree,
        previous_accepted_tree_identity=built_on,
        suite_digest=suite,
        outcomes=tuple(_outcome(sid, state) for sid, state in states.items()),
        evaluated_at=T0,
    )


ABSENT, START = BlockedReason.SURFACE_ABSENT, BlockedReason.START_FAILED
CONTROL = BlockedReason.CONTROL_ABSENT


@pytest.mark.parametrize(
    ("before", "after", "reading", "moved"),
    [
        ({"join": P, "cap": F}, {"join": P, "cap": F}, Reading.NEUTRAL, {}),
        (
            {"join": P, "cap": F},
            {"join": P, "cap": P},
            Reading.CONTRIBUTED,
            {"newly_passing": ("cap",)},
        ),
        (
            {"join": P, "cap": F},
            {"join": F, "cap": P},
            Reading.REGRESSED,
            {"regressed": ("join",), "newly_passing": ("cap",)},
        ),
        ({"join": P}, {"join": START}, Reading.UNVERIFIED, {"unverified": ("join",)}),
        (
            {"join": P, "cap": ABSENT},
            {"join": P, "cap": ABSENT},
            Reading.NEUTRAL,
            {"taking_no_part": ("cap",)},
        ),
        (
            {"join": P, "cap": P},
            {"join": P, "cap": ABSENT},
            Reading.UNVERIFIED,
            {"unverified": ("cap",)},
        ),
        (
            {"join": P, "page": "n/a"},
            {"join": P, "page": "n/a"},
            Reading.NEUTRAL,
            {"taking_no_part": ("page",)},
        ),
        (
            {"join": F, "cap": F},
            {"join": P, "cap": START},
            Reading.UNVERIFIED,
            {"newly_passing": ("join",), "unverified": ("cap",)},
        ),
        (
            {"join": P, "page": CONTROL},
            {"join": P, "page": CONTROL},
            Reading.UNVERIFIED,
            {"unverified": ("page",)},
        ),
    ],
    ids=[
        "accepted-and-nothing-moved",
        "a-scenario-newly-passes",
        "a-passing-scenario-now-fails",
        "a-scenario-that-takes-part-is-blocked",
        "absent-on-both-trees-takes-no-part",
        "a-surface-that-disappears-is-unverified",
        "not-applicable-takes-no-part",
        "a-contribution-it-couldnt-check-isnt-claimed",
        "a-control-not-found-on-both-trees-is-unverified-never-no-part",
    ],
)
def test_an_increment_reads_as_its_scenarios_moved(before, after, reading, moved):
    """§4.4. Bug caught: an accepted increment that moved no scenario read as contributing (the
    window's prediction 3 needs some to read neutral); a regression hidden by a new pass; a feature
    the product never had counted against it; or a contribution claimed while a scenario was
    blocked; or a page scenario whose names match no delivery vanishing from every reading, as an
    absent surface does (§10p ruling 4)."""
    result = contribution(_record(INCREMENT, BASE, **after), _record(BASE, None, **before))

    assert result.reading == reading
    for field in ("newly_passing", "regressed", "unverified", "taking_no_part"):
        assert getattr(result, field) == moved.get(field, ())


def test_a_calibration_reads_its_passing_scenarios_as_new():
    """A calibration builds on nothing. Bug caught: the first tree read as neutral because there
    was nothing to compare, hiding what it established."""
    result = contribution(_record(BASE, None, join=P, cap=F), None)

    assert (result.reading, result.newly_passing) == (Reading.CONTRIBUTED, ("join",))


@pytest.mark.parametrize(
    ("previous", "message"),
    [
        (_record(BASE, None, suite="t" * 64, join=P), "read different scenarios"),
        (_record("c" * 64, None, join=P), "was built on"),
    ],
    ids=["another-suite", "another-tree"],
)
def test_two_records_that_arent_an_increment_and_its_base_are_refused(previous, message):
    """Bug caught: an increment compared with another suite's evaluation, or with a tree it wasn't
    built on, so its reading describes a change that never happened."""
    with pytest.raises(NotComparable, match=message):
        contribution(_record(INCREMENT, BASE, join=P), previous)
