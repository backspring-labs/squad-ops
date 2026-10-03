"""A launch the box refuses (SIP-0109 §9.3; #1802), entering at the launcher: ``drain`` is the
path every decision's intent takes, and ``retry_blocked`` is what the campaign sweep calls.
Each test asserts what reached the cycle registry and the control log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.box import LaunchRefusal, LaunchVerdict
from squadops.campaigns.launch_blocking import escalated_by_a_blocked_launch
from squadops.campaigns.launcher import CampaignLauncher
from squadops.campaigns.models import (
    CampaignState,
    ControlOperation,
    CycleKind,
    LaunchIntentState,
    LaunchRequest,
)
from tests.unit.campaigns.builders import campaign, cycle_for, move, policy

S = CampaignState
CID = "cmp_bbbbbbbbbbbb"
LOUD = LaunchVerdict(
    LaunchRefusal.BOX_NOT_QUIET,
    ("engine ollama has qwen2.5:3b-instruct loaded, which the deploy record does not declare",),
)


class _Box:
    """The box the launcher reads, switched by the test."""

    def __init__(self, verdict: LaunchVerdict) -> None:
        self.now = verdict

    async def verdict(self) -> LaunchVerdict:
        return self.now


async def _world(attempts: int = 6):
    campaigns = MemoryCampaignRegistry()
    await campaigns.create_campaign(
        campaign(CID, policy=policy(launch_blocked_attempts=attempts)),
        actor="owner",
        actor_role="owner",
        reason="r",
        idempotency_key="create-1",
    )
    await campaigns.transition(CID, move(S.CALIBRATING, "k-cal"))
    intent = (
        await campaigns.transition(
            CID, move(S.AT_PROPOSAL, "k-decide", launch=LaunchRequest(CycleKind.INCREMENT))
        )
    ).intent
    cycles = MemoryCycleRegistry()
    box = _Box(LOUD)

    async def build(i):
        return cycle_for(i)

    launcher = CampaignLauncher(campaigns, cycles, build, actor="launcher", box_verdict=box.verdict)
    return campaigns, cycles, box, launcher, intent


def _later(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)


async def test_a_launch_the_box_refuses_blocks_the_campaign_and_creates_no_cycle():
    """Bug caught: a campaign launching beside a crew model; and a blocked campaign whose
    refusal leaves no row naming the attempt, the refusal and its reasons."""
    campaigns, cycles, _box, launcher, intent = await _world()

    assert await launcher.drain() == []
    assert await launcher.drain() == []  # a holding campaign is not blocked again

    assert await cycles.list_cycles("group_run") == []
    assert (await campaigns.get_campaign(CID)).state is S.LAUNCH_BLOCKED
    blocked = [
        e
        for e in await campaigns.control_log(CID)
        if e.operation is ControlOperation.LAUNCH_BLOCKED
    ]
    assert [e.binding for e in blocked] == [
        {
            "launch_id": intent.launch_id,
            "attempt": 1,
            "blocked_from": "at_proposal",
            "refusal": "box_not_quiet",
            "reasons": list(LOUD.reasons),
        }
    ]


async def test_a_blocked_launch_is_retried_when_due_and_launched_once_when_the_box_allows():
    """Bug caught: a retry before the policy's interval; a box that frees never resuming the
    campaign; or the unblock launching the held intent twice."""
    campaigns, cycles, box, launcher, intent = await _world()
    await launcher.drain()

    assert await launcher.retry_blocked(_later(60)) == []  # the interval is 300 s
    [second] = await launcher.retry_blocked(_later(301))
    assert (second.binding["attempt"], second.next_state) == (2, S.LAUNCH_BLOCKED)

    box.now = LaunchVerdict(None)
    [unblock] = await launcher.retry_blocked(_later(700))
    assert (unblock.operation, unblock.next_state) == (
        ControlOperation.LAUNCH_UNBLOCKED,
        S.AT_PROPOSAL,
    )
    [launched] = await launcher.drain()
    assert await launcher.drain() == []
    assert [c.cycle_id for c in await cycles.list_cycles("group_run")] == [launched.cycle_id]
    stored = await campaigns.get_launch_intent(intent.launch_id)
    assert (stored.state, stored.cycle_id) == (LaunchIntentState.LAUNCHED, launched.cycle_id)


async def test_a_launch_still_refused_at_the_policys_count_escalates_and_launches_nothing():
    """Bug caught: a blocked launch retried forever, or launched past its count without the
    owner's word."""
    campaigns, cycles, _box, launcher, _intent = await _world(attempts=2)
    await launcher.drain()
    [last] = await launcher.retry_blocked(_later(301))

    assert (last.binding["attempt"], last.next_state) == (2, S.ESCALATED)
    escalated = await campaigns.get_campaign(CID)
    assert escalated_by_a_blocked_launch(escalated, await campaigns.control_log(CID))
    assert await launcher.retry_blocked(_later(900)) == []
    assert await launcher.drain() == []
    assert await cycles.list_cycles("group_run") == []
