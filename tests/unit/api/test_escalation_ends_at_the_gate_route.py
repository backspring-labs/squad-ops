"""A person's decision on an escalated plan gate ends its escalation (SIP-0109 §24eh; #3174).

Entered at ``POST /api/v1/projects/{p}/cycles/{c}/runs/{r}/gates/progress_plan_review``, the route
``squadops runs gate`` posts to, with the real authorization adapter over the memory registries.
The campaign is building, the tier has escalated the framing run's plan gate, and a person decides
it. What the campaign's control log and its escalation queue then hold is read back. The sweep is
``CampaignProgress.sweep_ruling_bounds``, the call ``main._sweep_campaigns`` makes every interval,
on a service built fresh over the same registries, as a restarted runtime builds it.

Found on 2026-11-17 (``cmp_c22ad50e1de0``): a person approved an escalated plan gate, the run
failed 27 seconds later, and ten minutes on the escalation still read ``pending``. Only the sweep
wrote the ending, and only for a campaign in a building state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from squadops.api.routes.cycles import runs as runs_route
from squadops.auth.models import Role
from squadops.campaigns.escalation import EscalationState, escalations
from squadops.campaigns.models import CampaignState, ControlOperation
from squadops.campaigns.progress import CampaignProgress
from tests.unit.api.test_increment_gate_route import CID, _escalated_gate, _identity, _World
from tests.unit.campaigns.builders import move

pytestmark = pytest.mark.auth

S = CampaignState
GATE = "progress_plan_review"
URL = f"/api/v1/projects/group_run/cycles/cyc_inc/runs/run_prop/gates/{GATE}"
APPROVAL = {"decision": "approved", "notes": "the scenario files are provisioned outside the build"}
BOUND = 1800  # the builders' policy: the supervisor's ruling bound
PERSON = "human:user-admin"


async def _world(opened_ago: float = 60.0) -> _World:
    """A building campaign whose plan gate the tier escalated ``opened_ago`` seconds ago, and an
    admin at the gate: the person who approved it on 2026-11-17."""
    w = await _escalated_gate((), opened_at=datetime.now(UTC) - timedelta(seconds=opened_ago))
    await w.campaigns.transition(CID, move(S.BUILDING, "to-building"))
    w.identity = _identity(Role.ADMIN)
    return w


async def _the_run_fails_and_the_campaign_escalates(w: _World) -> None:
    """The control log's rows 10 to 12 of ``cmp_c22ad50e1de0``: the cycle ended, the continuation
    chose a retry, and its launch was refused, all within a second."""
    await w.campaigns.transition(CID, move(S.EVALUATING, "cycle-ended"))
    await w.campaigns.transition(CID, move(S.RETRYING, "row-10"))
    await w.campaigns.transition(
        CID, move(S.ESCALATED, "launch-refused", operation=ControlOperation.LAUNCH_REFUSED)
    )


def _restarted(w: _World, now: datetime) -> CampaignProgress:
    """The progress service a runtime builds at its start, over what the last one stored."""
    return CampaignProgress(
        campaigns=w.campaigns,
        cycles=w.cycles,
        vault=AsyncMock(),
        assess=AsyncMock(),
        launch=AsyncMock(),
        evaluate_outcome=None,
        evaluate_baseline=None,
        outcome_section=None,
        intervention_section=None,
        campaign_branch=None,
        goal_sets=None,
        clock=lambda: now,
    )


async def _closes(w: _World) -> list:
    """Every ``escalation_closed`` row of the log, applied or refused."""
    return [
        e
        for e in await w.campaigns.control_log(CID)
        if e.operation is ControlOperation.ESCALATION_CLOSED
    ]


async def _queue(w: _World):
    """The escalation as ``squadops campaigns escalations`` reads it: the projection the
    escalations route serialises."""
    campaign = await w.campaigns.get_campaign(CID)
    [escalation] = escalations(await w.campaigns.control_log(CID), campaign.state)
    return escalation


async def _stored_decision(w: _World):
    [decision] = (await w.cycles.get_run("run_prop")).gate_decisions
    return decision


@pytest.mark.parametrize(
    "the_run_then_fails", [False, True], ids=["approved", "the-run-then-fails"]
)
async def test_an_approval_ends_the_escalation_resolved_once_where_it_is_decided(
    the_run_then_fails,
):
    """#3174's done-when. Bugs caught:
    - the approval leaving its escalation ``pending``, so a supervisor takes an answered question
      for open work (2026-11-17);
    - the ending written only when a sweep next finds the campaign building, so a run that fails
      soon after the approval leaves it pending for good;
    - an ending that doesn't say who decided or when, or dates itself by the row's write."""
    w = await _world()

    resp = w.client.post(URL, json=APPROVAL)
    if the_run_then_fails:
        await _the_run_fails_and_the_campaign_escalates(w)
    swept = await _restarted(w, datetime.now(UTC) + timedelta(minutes=10)).sweep_ruling_bounds()

    assert resp.status_code == 200, resp.json()
    decision = await _stored_decision(w)
    [close] = await _closes(w)
    assert (close.outcome, close.actor, close.binding["state"]) == ("applied", PERSON, "resolved")
    assert close.binding == {
        "escalation_id": "esc_plangate001",
        "state": "resolved",
        "decided_by": PERSON,
        "decided_at": decision.decided_at.isoformat(),
    }
    queue = await _queue(w)
    assert (queue.state, queue.closed_by, queue.closed_at) == (
        EscalationState.RESOLVED, PERSON, decision.decided_at,
    )  # fmt: skip
    assert swept == []  # the sweep finds it ended, and writes nothing
    if the_run_then_fails:
        # Written at the decision: before the cycle's end moved the campaign.
        operations = [e.operation for e in await w.campaigns.control_log(CID)]
        assert operations.index(ControlOperation.ESCALATION_CLOSED) < operations.index(
            ControlOperation.LAUNCH_REFUSED
        )
        assert (await w.campaigns.get_campaign(CID)).state is S.ESCALATED


async def test_a_decision_whose_ending_wasnt_written_is_ended_after_a_restart(monkeypatch):
    """The runtime stopped between recording the decision and writing the ending, and the run
    failed meanwhile, so the campaign is escalated when the next runtime starts. Bugs caught:
    - the request failing for an ending it couldn't write, when the gate is already decided;
    - a sweep that reads only building campaigns, so the stored decision is never read again;
    - the ending dated by the sweep that found it, ten minutes after the person decided;
    - a second sweep writing it again."""
    w = await _world()

    async def stopped(*_args, **_kwargs):
        raise RuntimeError("the runtime stopped here")

    monkeypatch.setattr(runs_route, "end_decided", stopped)
    resp = w.client.post(URL, json=APPROVAL)
    monkeypatch.undo()
    unwritten = await _closes(w)
    await _the_run_fails_and_the_campaign_escalates(w)
    later = datetime.now(UTC) + timedelta(minutes=10)

    first = await _restarted(w, later).sweep_ruling_bounds()
    again = await _restarted(w, later + timedelta(minutes=1)).sweep_ruling_bounds()

    assert resp.status_code == 200, resp.json()
    decision = await _stored_decision(w)
    assert (decision.decision, unwritten) == ("approved", [])
    assert [(e.operation, e.actor, e.binding["state"]) for e in first] == [
        (ControlOperation.ESCALATION_CLOSED, PERSON, "resolved")
    ]
    assert again == [] and len(await _closes(w)) == 1
    queue = await _queue(w)
    assert (queue.state, queue.closed_by, queue.closed_at) == (
        EscalationState.RESOLVED, PERSON, decision.decided_at,
    )  # fmt: skip
    assert queue.closed_at < later


async def test_the_same_decision_posted_twice_writes_one_ending():
    """A retried request: the registry takes the same decision again as a no-op. Bug caught: a
    second ``escalation_closed`` row, applied or refused, for one decision."""
    w = await _world()

    first, second = w.client.post(URL, json=APPROVAL), w.client.post(URL, json=APPROVAL)

    assert (first.status_code, second.status_code) == (200, 200), second.json()
    [close] = await _closes(w)
    assert (close.outcome, close.binding["state"]) == ("applied", "resolved")
    assert len((await w.cycles.get_run("run_prop")).gate_decisions) == 1


@pytest.mark.parametrize(
    ("opened_ago", "state", "closed_by"),
    [
        (BOUND - 60, "resolved", PERSON),
        (BOUND + 10, "expired", "squadops"),
    ],
    ids=["a-minute-inside-the-bound", "ten-seconds-past-the-bound"],
)
async def test_a_decision_is_read_against_the_bound_by_its_own_time(opened_ago, state, closed_by):
    """The plan's rule: resolved is a person deciding before the bound. Bugs caught:
    - a decision made after the bound reading ``resolved`` because the sweep hadn't yet written
      the expiry, so the same late answer reads either way by the sweep's phase;
    - the late decision dropped from the record, or the gate left undecided: it stands on the
      run, and the expiry names it;
    - a later sweep rewriting the expiry as resolved."""
    w = await _world(opened_ago)

    resp = w.client.post(URL, json=APPROVAL)
    swept = await _restarted(w, datetime.now(UTC) + timedelta(minutes=10)).sweep_ruling_bounds()

    assert resp.status_code == 200, resp.json()
    decision = await _stored_decision(w)
    [close] = await _closes(w)
    assert (close.binding["state"], close.actor, swept) == (state, closed_by, [])
    assert (close.binding["decided_by"], close.binding["decided_at"]) == (
        PERSON, decision.decided_at.isoformat(),
    )  # fmt: skip
    assert (await _queue(w)).state is EscalationState(state)
    if state == "expired":
        assert f"before {PERSON} decided the {GATE} gate on run_prop" in close.reason
        assert (await w.cycles.get_run("run_prop")).status == "completed"  # never parked


async def test_a_gate_no_escalation_holds_ends_nothing():
    """Bug caught: an ending written for a campaign cycle's plan gate the tier never escalated,
    or the route failing for want of one."""
    from tests.unit.api.test_increment_gate_route import at_the_gate
    from tests.unit.campaigns.builders import campaign

    w = _World()
    await w.campaigns.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await at_the_gate(w)
    w.identity = _identity(Role.ADMIN)
    rows = len(await w.campaigns.control_log(CID))

    resp = w.client.post(URL, json=APPROVAL)

    assert resp.status_code == 200, resp.json()
    assert len(await w.campaigns.control_log(CID)) == rows
