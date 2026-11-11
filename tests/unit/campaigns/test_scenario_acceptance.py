"""A scenario criterion's discrimination and holding, read from its assertion records (#3053).

What bugs would these catch?
- Crediting a reading of another revision, another scenario digest, or the other side: stale or
  edited evidence counting as this tree's.
- An assertion that never executed (missing, setup failed) read as a pass, or as a failure.
- A precondition failing on the baseline read as discrimination: the scenario's world isn't the
  baseline's, so its named failure says nothing about the change.
- A scenario that already passes on the baseline read as met.
- A precondition broken on a later candidate read as holding because the named assertion passed.
- The reason a reading wasn't credited lost before it reaches the increment's verdict.
"""

from __future__ import annotations

import pytest

from squadops.campaigns.acceptance import (
    BaselineVerdict,
    DiscriminationReason,
    FrozenScenario,
    Held,
    IncrementVerdict,
    Side,
    _baseline_verdict,
    credited_outcomes,
    discrimination_on_scenario,
    held_on_scenario,
    increment_acceptance,
)
from squadops.remote_execution.models import AssertionOutcome

DIGEST = "sha256:" + "ab" * 32
FROZEN = FrozenScenario(DIGEST, "lamp-lit")
BASE = "rev-base-0001"
CAND = "rev-cand-0002"
DECLARED = ("spawned", "lamp-lit")


def reading(side, revision, outcomes, *, digest=DIGEST, status="completed", reason=""):
    """The handler's ``operation_assertions.json``, with #3044's ``side``."""
    return {
        "side": side,
        "source_revision": revision,
        "scenario": {"scenario_id": "S-1", "digest": digest, "assertions": list(DECLARED)},
        "status": status,
        "reason": reason,
        "assertions": [
            {"assertion_id": a, "outcome": o, "observed": "", "expected": "", "context": "server"}
            for a, o in outcomes.items()
        ],
    }


def baseline(outcomes):
    return reading("baseline", BASE, outcomes)


def candidate(outcomes):
    return reading("candidate", CAND, outcomes)


GOOD_BASE = baseline({"spawned": "passed", "lamp-lit": "failed"})
GOOD_CAND = candidate({"spawned": "passed", "lamp-lit": "passed"})


@pytest.mark.parametrize(
    ("base", "cand", "met", "reason", "detail"),
    [
        (GOOD_BASE, GOOD_CAND, True, DiscriminationReason.DISCRIMINATES, ""),
        (
            baseline({"spawned": "passed", "lamp-lit": "passed"}),
            GOOD_CAND,
            False,
            DiscriminationReason.NO_BASELINE_FAILURE,
            "lamp-lit already passes on the baseline",
        ),
        (
            baseline({"spawned": "failed", "lamp-lit": "failed"}),
            GOOD_CAND,
            False,
            DiscriminationReason.ONLY_SETUP_FAILURES,
            "preconditions fail on the baseline: spawned",
        ),
        (
            # The named assertion recorded, the precondition not: nothing shows the world.
            baseline({"lamp-lit": "failed"}),
            GOOD_CAND,
            False,
            DiscriminationReason.NOT_RUN,
            "didn't execute on the baseline: spawned (missing)",
        ),
        (
            GOOD_BASE,
            candidate({"spawned": "failed", "lamp-lit": "passed"}),
            False,
            DiscriminationReason.FAILS_ON_CANDIDATE,
            "fail on the candidate: spawned",
        ),
        (
            GOOD_BASE,
            candidate({"spawned": "setup_failed", "lamp-lit": "passed"}),
            False,
            DiscriminationReason.NOT_RUN,
            "didn't execute on the candidate: spawned (setup_failed)",
        ),
    ],
)
def test_discrimination_reads_both_sides_records(base, cand, met, reason, detail):
    d = discrimination_on_scenario("C-1", FROZEN, BASE, CAND, base, cand)

    assert (d.met, d.reason, d.detail) == (met, reason, detail)
    assert d.discriminating == (("lamp-lit",) if met else ())


def test_an_already_passing_scenario_says_whether_the_candidate_keeps_it():
    already = baseline({"spawned": "passed", "lamp-lit": "passed"})
    kept = discrimination_on_scenario("C-1", FROZEN, BASE, CAND, already, GOOD_CAND)
    lost = discrimination_on_scenario(
        "C-1", FROZEN, BASE, CAND, already, candidate({"spawned": "passed"})
    )
    stale = discrimination_on_scenario(
        "C-1", FROZEN, BASE, CAND, already, reading("candidate", BASE, {"lamp-lit": "passed"})
    )

    assert (kept.candidate_passed, lost.candidate_passed, stale.candidate_passed) == (
        True,
        False,
        False,
    )


@pytest.mark.parametrize(
    ("the_reading", "why"),
    [
        (None, "no candidate reading"),
        (reading("baseline", CAND, {}), "the reading is the baseline side's, not the candidate"),
        (
            reading("candidate", BASE, {"spawned": "passed", "lamp-lit": "passed"}),
            f"the reading is of revision {BASE}, and the candidate judged is {CAND}",
        ),
        (
            reading("candidate", CAND, {}, digest="sha256:" + "cd" * 32),
            f"the reading ran scenario sha256:{'cd' * 32}, and the frozen one is {DIGEST}",
        ),
        (
            reading("candidate", CAND, {}, status="not_executed", reason="no worker for it"),
            "the operation is not_executed: no worker for it",
        ),
        (
            reading("candidate", CAND, {"spawned": "passed", "lamp-lit": "skipped"}),
            "a record's outcome 'skipped' is no assertion outcome",
        ),
    ],
)
def test_a_reading_is_credited_only_for_its_digest_revision_and_side(the_reading, why):
    outcomes, reason = credited_outcomes(the_reading, FROZEN, CAND, Side.CANDIDATE)
    held = held_on_scenario(FROZEN, CAND, the_reading)

    assert (outcomes, reason) == (None, why)
    assert held == (Held.BLOCKED_UNVERIFIED, why)


def test_a_frozen_scenario_naming_an_undeclared_assertion_credits_nothing():
    renamed = FrozenScenario(DIGEST, "door-open")

    assert credited_outcomes(GOOD_CAND, renamed, CAND, Side.CANDIDATE) == (
        None,
        "the scenario declares no assertion 'door-open'",
    )


@pytest.mark.parametrize(
    ("outcomes", "held"),
    [
        ({"spawned": "passed", "lamp-lit": "passed"}, (Held.HELD, "")),
        # The precondition's world is gone: the named assertion passing doesn't hold it.
        ({"spawned": "failed", "lamp-lit": "passed"}, (Held.BROKEN, "spawned")),
        # A failure is read even beside an assertion that never ran.
        ({"lamp-lit": "failed"}, (Held.BROKEN, "lamp-lit")),
        (
            {"spawned": "wrong_context", "lamp-lit": "passed"},
            (Held.BLOCKED_UNVERIFIED, "didn't execute: spawned (wrong_context)"),
        ),
    ],
)
def test_an_earlier_scenario_holds_only_when_every_assertion_ran_and_passed(outcomes, held):
    assert held_on_scenario(FROZEN, CAND, reading("candidate", CAND, outcomes)) == held


@pytest.mark.parametrize(
    ("outcomes", "verdict"),
    [
        ({"spawned": "passed", "lamp-lit": "failed"}, BaselineVerdict.MAY_START),
        ({"spawned": "passed", "lamp-lit": "passed"}, BaselineVerdict.SCENARIO_PASSES_ON_BASELINE),
        ({"spawned": "failed", "lamp-lit": "failed"}, BaselineVerdict.PRECONDITION_FAILS),
        # A gap blocks before an author error is read: nothing shows the world is the baseline's.
        ({"spawned": "missing", "lamp-lit": "passed"}, BaselineVerdict.BLOCKED),
    ],
)
def test_the_baseline_verdict(outcomes, verdict):
    typed = {a: AssertionOutcome(o) for a, o in outcomes.items()}

    assert _baseline_verdict(typed, "lamp-lit")[0] is verdict


def test_the_increment_says_why_a_scenario_was_unread_or_unmet():
    unread = discrimination_on_scenario(
        "C-1", FROZEN, BASE, CAND, GOOD_BASE, reading("candidate", BASE, {})
    )
    unmet = discrimination_on_scenario(
        "C-2", FROZEN, BASE, CAND, GOOD_BASE, candidate({"spawned": "failed"})
    )

    blocked = increment_acceptance((unread,), (), ())
    rejected = increment_acceptance((unmet,), (), ())

    assert (blocked.verdict, blocked.blocked) == (
        IncrementVerdict.BLOCKED_UNVERIFIED,
        (
            f"criterion C-1: not run: the reading is of revision {BASE}, and the candidate "
            f"judged is {CAND}",
        ),
    )
    assert (rejected.verdict, rejected.unmet) == (
        IncrementVerdict.REJECTED,
        ("criterion C-2: fails_on_candidate (fail on the candidate: spawned)",),
    )
