"""#3045: an increment blocked only because no worker took its scenarios is retried, never
repaired, within the increment's retries, then escalated.

The decisions, entered at the two functions the live path calls: ``increment_acceptance``
(delivery's verdict and its one structured fact, ``blocked_only_by_availability``) and
``campaign_continuation_decision`` (the hearing's row), with the hearing's read of a stored
evaluation between them. The path from a worker to these is ``test_machinery_increment`` and
``test_machinery_campaign``.

What bugs would these catch?
- A repair spent on an outage: a candidate nothing faulted rebuilt, and the increment's repairs
  gone before a worker comes back (the live shape #3084 found).
- The shortcut taken with any other gap beside the outage, so a real gap is retried unread
  instead of repaired.
- A failure beside an outage read as the outage, so a rejected candidate is retried.
- An evaluation stored before the flag read as flagged, or the retries never running out.
"""

from __future__ import annotations

import pytest

from squadops.campaigns.acceptance import (
    Discrimination,
    DiscriminationReason,
    FrozenResult,
    Held,
    IncrementVerdict,
    RouteResult,
    increment_acceptance,
)
from squadops.campaigns.continuation import (
    CycleEnding,
    EndedCycle,
    PendingAction,
    campaign_continuation_decision,
)
from squadops.campaigns.models import CycleKind
from squadops.campaigns.progress import blocked_only_by_availability
from squadops.cycles.verification_integrity import RunVerdict
from tests.unit.campaigns.test_continuation import CAMPAIGN, CYCLE, assessment, counters

pytestmark = [pytest.mark.domain_orchestration]

_MET = Discrimination("C-3", True, DiscriminationReason.DISCRIMINATES, ("lamp-lit",))
#: A new scenario whose candidate reading no worker took.
_UNTAKEN = Discrimination(
    "C-3", False, DiscriminationReason.NOT_RUN, detail="no worker", unavailable=True
)


def _frozen(held: Held, *, unavailable: bool = False, detail: str = "") -> FrozenResult:
    return FrozenResult("inc_2", "C-2", "tree", "addr", held, detail, unavailable)


@pytest.mark.parametrize(
    ("discriminations", "frozen", "routes", "verdict", "only_availability"),
    [
        # Every gap a scenario no worker took: a new one's reading, a frozen one's.
        ((_UNTAKEN,), (), (), IncrementVerdict.BLOCKED_UNVERIFIED, True),
        (
            (_MET,),
            (_frozen(Held.BLOCKED_UNVERIFIED, unavailable=True),),
            (),
            IncrementVerdict.BLOCKED_UNVERIFIED,
            True,
        ),
        # An outage beside a gap of another kind: a missing bundle, a route not rendered.
        (
            (_UNTAKEN,),
            (_frozen(Held.BLOCKED_UNVERIFIED, detail="the verifier bundle is missing"),),
            (),
            IncrementVerdict.BLOCKED_UNVERIFIED,
            False,
        ),
        (
            (_UNTAKEN,),
            (),
            (RouteResult("/", Held.BLOCKED_UNVERIFIED),),
            IncrementVerdict.BLOCKED_UNVERIFIED,
            False,
        ),
        # A failure beside an outage rejects: the outage changes nothing.
        (
            (_UNTAKEN,),
            (_frozen(Held.BROKEN, detail="door-open"),),
            (),
            IncrementVerdict.REJECTED,
            False,
        ),
        # Nothing blocked.
        ((_MET,), (_frozen(Held.HELD),), (), IncrementVerdict.ACCEPTED, False),
    ],
)
def test_delivery_names_an_outage_alone_only_when_every_blocking_gap_is_one(
    discriminations, frozen, routes, verdict, only_availability
):
    judged = increment_acceptance(discriminations, frozen, routes)

    assert judged.verdict is verdict
    assert judged.blocked_only_by_availability is only_availability


def _decide(*, flagged: bool, retry_cycles: int = 0):
    return campaign_continuation_decision(
        CAMPAIGN,
        counters(retry_cycles=retry_cycles),
        EndedCycle(
            CYCLE,
            CycleKind.INCREMENT,
            CycleEnding.ASSESSED,
            RunVerdict.BLOCKED_UNVERIFIED,
            blocked_only_by_availability=flagged,
        ),
        assessment(RunVerdict.BLOCKED_UNVERIFIED),
    )


@pytest.mark.parametrize(
    ("flagged", "retry_cycles", "row", "action"),
    [
        (True, 0, 10, PendingAction.RETRY),
        # The increment's retries spent across its launches: the owner hears of it.
        (True, 1, 11, PendingAction.ESCALATE),
        # Blocked for anything else is repaired, as before.
        (False, 0, 8, PendingAction.REPAIR),
    ],
)
def test_an_increment_blocked_only_for_want_of_a_worker_is_retried_then_escalated(
    flagged, retry_cycles, row, action
):
    decision = _decide(flagged=flagged, retry_cycles=retry_cycles)

    assert (decision.row, decision.action) == (row, action)


def test_a_rejected_increment_with_an_outage_beside_its_failure_is_repaired():
    """The mixed hearing: delivery rejects (a failure beside the outage), so the flag is never
    set, and the decision is the rejection's repair (row 12), not a retry."""
    judged = increment_acceptance((_UNTAKEN,), (_frozen(Held.BROKEN, detail="door-open"),), ())
    decision = campaign_continuation_decision(
        CAMPAIGN,
        counters(),
        EndedCycle(
            CYCLE,
            CycleKind.INCREMENT,
            CycleEnding.ASSESSED,
            RunVerdict(str(judged.verdict)),
            blocked_only_by_availability=judged.blocked_only_by_availability,
        ),
        assessment(RunVerdict.REJECTED),
    )

    assert (decision.row, decision.action) == (12, PendingAction.REPAIR)


@pytest.mark.parametrize(
    ("evaluation", "read"),
    [
        ({"verdict": "blocked_unverified", "blocked_only_by_availability": True}, True),
        # Stored before the flag: no key, so today's routing (a repair).
        ({"verdict": "blocked_unverified", "blocked": ["frozen C-2: not executed"]}, False),
        # The flag counts only on a blocked verdict.
        ({"verdict": "rejected", "blocked_only_by_availability": True}, False),
        (None, False),
    ],
)
def test_the_hearing_reads_the_flag_from_the_stored_evaluation(evaluation, read):
    assert blocked_only_by_availability(evaluation) is read
