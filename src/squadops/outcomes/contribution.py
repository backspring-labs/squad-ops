"""Contribution, per increment (SIP-0113 §4.4; #2418).

A reading derived from two evaluation records of the same suite, never written by a model: the
increment's tree against the accepted tree it was built on. Scenarios recorded *not applicable*
take no part, and neither does one that is ``surface_absent`` on both trees, since the product never
had that surface and the scenario makes no claim about it.

| reading | when |
|---|---|
| ``regressed`` | a scenario that passed on the previous accepted tree fails |
| ``unverified`` | otherwise, a scenario that takes part is ``blocked_unverified`` |
| ``contributed`` | otherwise, at least one scenario newly passes |
| ``neutral`` | none of those: "output accepted; contribution negligible" |

The order is the reading's precedence, a choice §4.4 leaves open (SIP-0113 §10e): a blocked scenario
means the reading can't claim a contribution it couldn't check. A scenario that passed and is now
blocked is ``unverified``, not ``regressed``: §4.4 says a regression *fails*.
"""

from __future__ import annotations

from dataclasses import dataclass

from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
)


class Reading:
    """§4.4's four readings. Constants, not an enum, as the ledger's: ``neutral`` and the others
    are words other vocabularies use too (#380's guard)."""

    CONTRIBUTED = "contributed"
    NEUTRAL = "neutral"
    REGRESSED = "regressed"
    UNVERIFIED = "unverified"
    ALL = frozenset({CONTRIBUTED, NEUTRAL, REGRESSED, UNVERIFIED})


class NotComparable(ValueError):
    """Two records that don't read as an increment and its previous accepted tree."""


@dataclass(frozen=True)
class Contribution:
    """An increment's reading, with the scenarios behind it, by id."""

    reading: str
    newly_passing: tuple[str, ...] = ()
    regressed: tuple[str, ...] = ()
    unverified: tuple[str, ...] = ()
    #: Not applicable, or ``surface_absent`` on both trees: no part in the reading.
    taking_no_part: tuple[str, ...] = ()


def _absent(outcome: ScenarioOutcome | None) -> bool:
    return outcome is None or (
        outcome.applicability is Applicability.NOT_APPLICABLE
        or outcome.blocked_reason is BlockedReason.SURFACE_ABSENT
    )


def _comparable(current: EvaluationRecord, previous: EvaluationRecord) -> None:
    if previous.suite_digest != current.suite_digest:
        raise NotComparable(
            f"suite {previous.suite_digest} and suite {current.suite_digest} read different "
            "scenarios: a reading compares one suite's two evaluations"
        )
    if previous.evaluated_tree_identity != current.previous_accepted_tree_identity:
        raise NotComparable(
            f"the increment was built on {current.previous_accepted_tree_identity}, and the "
            f"previous record evaluated {previous.evaluated_tree_identity}"
        )


def _move(now: ScenarioOutcome, was: ScenarioOutcome | None) -> str | None:
    """One scenario's part in the reading: ``newly``, ``regressed``, ``unverified``, ``no_part``,
    or ``None`` when it stays as it was (passing, or still failing)."""
    if now.applicability is Applicability.NOT_APPLICABLE or (
        now.blocked_reason is BlockedReason.SURFACE_ABSENT and _absent(was)
    ):
        return "no_part"
    if now.result is ScenarioResult.BLOCKED_UNVERIFIED:
        return "unverified"
    passed_before = was is not None and was.result is ScenarioResult.PASSED
    if now.result is ScenarioResult.PASSED:
        return None if passed_before else "newly"
    return "regressed" if passed_before else None


def contribution(current: EvaluationRecord, previous: EvaluationRecord | None) -> Contribution:
    """The increment's reading. ``previous`` is the evaluation of the accepted tree it was built
    on, by the same suite, or ``None`` for a calibration, whose tree is compared with nothing."""
    if previous is not None:
        _comparable(current, previous)
    before = {o.scenario_id: o for o in previous.outcomes} if previous else {}
    moves: dict[str, list[str]] = {"newly": [], "regressed": [], "unverified": [], "no_part": []}
    for now in current.outcomes:
        move = _move(now, before.get(now.scenario_id))
        if move is not None:
            moves[move].append(now.scenario_id)
    if moves["regressed"]:
        reading = Reading.REGRESSED
    elif moves["unverified"]:
        reading = Reading.UNVERIFIED
    elif moves["newly"]:
        reading = Reading.CONTRIBUTED
    else:
        reading = Reading.NEUTRAL
    return Contribution(
        reading=reading,
        newly_passing=tuple(moves["newly"]),
        regressed=tuple(moves["regressed"]),
        unverified=tuple(moves["unverified"]),
        taking_no_part=tuple(moves["no_part"]),
    )
