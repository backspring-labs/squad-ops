"""A scenario criterion's discrimination and holding, read from its assertion records (#3053).

Every reading here is built by ``records_document``, the one builder every lane writes a reading
with (#3044 §4). The end-to-end case runs the frozen ``DOOR_OPENS`` through the fixture's
``fixture/declared_scenario`` operation on the ``SHUT`` and ``OPEN`` worlds, so the decisions are
read off what an operation actually returned.

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

import asyncio
import dataclasses

import pytest

from adapters.remote_execution.fixture_operation_runner import (
    OPERATION,
    PROVIDER,
    FixtureOperationRunner,
)
from squadops.campaigns.acceptance import (
    DiscriminationReason,
    Held,
    IncrementVerdict,
    credited_outcomes,
    discrimination_on_scenario,
    held_on_scenario,
    increment_acceptance,
)
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    ReadingSide,
    RemoteOperationRequest,
    RemoteOperationResult,
    records_document,
)
from squadops.remote_execution.scenario import staged_revision
from tests.unit.remote_execution.scenario_fixture import OPEN, SHUT, door_opens, tree

FROZEN = door_opens()
BASE = "rev-base-0001"
CAND = "rev-cand-0002"
BASELINE, CANDIDATE = ReadingSide.BASELINE, ReadingSide.CANDIDATE


def _request(files: dict[str, str], revision: str, scenario=FROZEN) -> RemoteOperationRequest:
    return RemoteOperationRequest(
        contract="game.playtest",
        mode="simulation",
        provider=PROVIDER,
        operation=OPERATION,
        location="worker",
        source_revision=revision,
        source_files=files,
        scenario=scenario,
        task_id="campaign:cmp_1:inc_2:C-2:candidate",
        dispatch_id="d-1",
    )


def reading(side, revision, outcomes, *, scenario=FROZEN, status=OperationStatus.COMPLETED):
    """A reading with the outcomes given, as ``records_document`` writes it."""
    result = RemoteOperationResult(
        status=status,
        reason="" if status is OperationStatus.COMPLETED else "no worker serves it",
        records=tuple(AssertionRecord(a, AssertionOutcome(o)) for a, o in outcomes.items()),
        dispatch_id="d-1",
    )
    return records_document(_request({}, revision, scenario), result, side, not_staged=())


def played(world: dict, side: ReadingSide) -> tuple[dict, str]:
    """``DOOR_OPENS`` run by the fixture operation on ``world``: the reading, and the revision
    of the tree it was staged as."""
    files = tree(world)
    revision = staged_revision(files)
    request = _request(files, revision)
    result = asyncio.run(FixtureOperationRunner().run(request))
    return records_document(request, result, side, not_staged=()), revision


def test_the_door_that_opens_discriminates_and_then_holds_on_the_next_candidate():
    """End to end through the fixture operation: shut on the baseline, open on the candidate."""
    on_baseline, base = played(SHUT, BASELINE)
    on_candidate, cand = played(OPEN, CANDIDATE)
    closed_again, broken_rev = played(SHUT, CANDIDATE)

    d = discrimination_on_scenario("C-2", FROZEN, base, cand, on_baseline, on_candidate)

    assert (d.met, d.reason, d.discriminating, d.detail) == (
        True,
        DiscriminationReason.DISCRIMINATES,
        ("door-open",),
        "",
    )
    assert held_on_scenario(FROZEN, cand, on_candidate) == (Held.HELD, "")
    assert held_on_scenario(FROZEN, broken_rev, closed_again) == (Held.BROKEN, "door-open")
    # The open door's reading, offered for a later candidate's revision, counts for nothing.
    assert held_on_scenario(FROZEN, broken_rev, on_candidate)[0] is Held.BLOCKED_UNVERIFIED


GOOD_BASE = reading(BASELINE, BASE, {"spawned": "passed", "door-open": "failed"})
GOOD_CAND = reading(CANDIDATE, CAND, {"spawned": "passed", "door-open": "passed"})


@pytest.mark.parametrize(
    ("base", "cand", "met", "reason", "detail"),
    [
        (GOOD_BASE, GOOD_CAND, True, DiscriminationReason.DISCRIMINATES, ""),
        (
            reading(BASELINE, BASE, {"spawned": "passed", "door-open": "passed"}),
            GOOD_CAND,
            False,
            DiscriminationReason.NO_BASELINE_FAILURE,
            "door-open already passes on the baseline",
        ),
        (
            reading(BASELINE, BASE, {"spawned": "failed", "door-open": "failed"}),
            GOOD_CAND,
            False,
            DiscriminationReason.ONLY_SETUP_FAILURES,
            "preconditions failed on the baseline: spawned",
        ),
        (
            # The named assertion recorded, the precondition not: nothing shows the world.
            reading(BASELINE, BASE, {"door-open": "failed"}),
            GOOD_CAND,
            False,
            DiscriminationReason.NOT_RUN,
            "not executed on the baseline: spawned (missing)",
        ),
        (
            GOOD_BASE,
            reading(CANDIDATE, CAND, {"spawned": "failed", "door-open": "passed"}),
            False,
            DiscriminationReason.FAILS_ON_CANDIDATE,
            "fail on the candidate: spawned",
        ),
        (
            GOOD_BASE,
            reading(CANDIDATE, CAND, {"spawned": "setup_failed", "door-open": "passed"}),
            False,
            DiscriminationReason.NOT_RUN,
            "didn't execute on the candidate: spawned (setup_failed)",
        ),
    ],
)
def test_discrimination_reads_both_sides_records(base, cand, met, reason, detail):
    d = discrimination_on_scenario("C-2", FROZEN, BASE, CAND, base, cand)

    assert (d.met, d.reason, d.detail) == (met, reason, detail)
    assert d.discriminating == (("door-open",) if met else ())


def test_an_already_passing_scenario_says_whether_the_candidate_keeps_it():
    already = reading(BASELINE, BASE, {"spawned": "passed", "door-open": "passed"})
    kept = discrimination_on_scenario("C-2", FROZEN, BASE, CAND, already, GOOD_CAND)
    lost = discrimination_on_scenario(
        "C-2", FROZEN, BASE, CAND, already, reading(CANDIDATE, CAND, {"spawned": "passed"})
    )
    stale = discrimination_on_scenario(
        "C-2", FROZEN, BASE, CAND, already, reading(CANDIDATE, BASE, {"door-open": "passed"})
    )

    assert (kept.candidate_passed, lost.candidate_passed, stale.candidate_passed) == (
        True,
        False,
        False,
    )


EDITED = dataclasses.replace(FROZEN, digest="sha256:" + "cd" * 32)


@pytest.mark.parametrize(
    ("the_reading", "why"),
    [
        (None, "no candidate reading"),
        (reading(BASELINE, CAND, {}), "the reading is the baseline side's, not the candidate"),
        (
            reading(CANDIDATE, BASE, {"spawned": "passed", "door-open": "passed"}),
            f"the reading is of revision {BASE}, and the candidate judged is {CAND}",
        ),
        (
            reading(CANDIDATE, CAND, {}, scenario=EDITED),
            f"the reading ran scenario {EDITED.digest}, and the frozen one is {FROZEN.digest}",
        ),
        (
            reading(CANDIDATE, CAND, {}, status=OperationStatus.NOT_EXECUTED),
            "the operation is not_executed: no worker serves it",
        ),
        (
            {**GOOD_CAND, "assertions": [{"assertion_id": "spawned", "outcome": "skipped"}]},
            "a record's outcome 'skipped' is no assertion outcome",
        ),
    ],
)
def test_a_reading_is_credited_only_for_its_digest_revision_and_side(the_reading, why):
    outcomes, reason = credited_outcomes(the_reading, FROZEN, CAND, CANDIDATE)
    held = held_on_scenario(FROZEN, CAND, the_reading)

    assert (outcomes, reason) == (None, why)
    assert held == (Held.BLOCKED_UNVERIFIED, why)


def test_a_frozen_scenario_naming_an_undeclared_assertion_credits_nothing():
    renamed = dataclasses.replace(FROZEN, named_assertion="lamp-lit")

    assert credited_outcomes(GOOD_CAND, renamed, CAND, CANDIDATE) == (
        None,
        "the frozen scenario declares no assertion 'lamp-lit'",
    )


@pytest.mark.parametrize(
    ("outcomes", "held"),
    [
        ({"spawned": "passed", "door-open": "passed"}, (Held.HELD, "")),
        # The precondition's world is gone: the named assertion passing doesn't hold it.
        ({"spawned": "failed", "door-open": "passed"}, (Held.BROKEN, "spawned")),
        # A failure is read even beside an assertion that never ran.
        ({"door-open": "failed"}, (Held.BROKEN, "door-open")),
        (
            {"spawned": "wrong_context", "door-open": "passed"},
            (Held.BLOCKED_UNVERIFIED, "didn't execute: spawned (wrong_context)"),
        ),
    ],
)
def test_an_earlier_scenario_holds_only_when_every_assertion_ran_and_passed(outcomes, held):
    assert held_on_scenario(FROZEN, CAND, reading(CANDIDATE, CAND, outcomes)) == held


def test_the_increment_says_why_a_scenario_was_unread_or_unmet():
    unread = discrimination_on_scenario(
        "C-1", FROZEN, BASE, CAND, GOOD_BASE, reading(CANDIDATE, BASE, {})
    )
    unmet = discrimination_on_scenario(
        "C-2", FROZEN, BASE, CAND, GOOD_BASE, reading(CANDIDATE, CAND, {"spawned": "failed"})
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
