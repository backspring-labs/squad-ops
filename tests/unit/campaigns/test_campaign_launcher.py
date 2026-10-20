"""Exactly-once launch (SIP-0109 §12b, criterion 12c), entering at the launcher.

The launcher is the caller of ``create_cycle_for_launch`` and of the intent's mark, so these
tests are its wiring tests too: each asserts what reached the cycle registry.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.launcher import CampaignLauncher
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
    LaunchIntentState,
    LaunchRequest,
)
from squadops.cycles.models import Cycle, ValidationError
from tests.unit.campaigns.builders import campaign, cycle_for, move, quiet_box

S = CampaignState
CID = "cmp_aaaaaaaaaaaa"


class _Crash(RuntimeError):
    """A process dying at an injected point."""


def _builder(*, yield_first: bool = False, fail_times: int = 0, before_return=None):
    """A cycle builder that mints a fresh id per call, as the cycle-create path does."""
    calls = {"n": 0}

    async def build(intent: LaunchIntent) -> Cycle:
        calls["n"] += 1
        if yield_first:
            await asyncio.sleep(0)  # let a second launcher read the same pending intent
        if calls["n"] <= fail_times:
            raise _Crash("after the intent committed, before the cycle was created")
        if before_return is not None:
            await before_return()
        return cycle_for(intent)

    return build


class _CrashAfterCreate(MemoryCycleRegistry):
    """Creates the cycle, then dies before the launcher can mark the intent."""

    def __init__(self) -> None:
        super().__init__()
        self.crash = True

    async def create_cycle_for_launch(self, cycle, launch_id):
        stored = await super().create_cycle_for_launch(cycle, launch_id)
        if self.crash:
            self.crash = False
            raise _Crash("after the cycle was created, before the intent was marked")
        return stored


@pytest.fixture
async def campaigns() -> MemoryCampaignRegistry:
    reg = MemoryCampaignRegistry()
    await reg.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    await reg.transition(CID, move(S.CALIBRATING, "k-cal"))
    return reg


async def _decide_launch(campaigns) -> str:
    result = await campaigns.transition(
        CID,
        move(S.AT_PROPOSAL, "k-decide", launch=LaunchRequest(CycleKind.INCREMENT)),
    )
    return result.intent.launch_id


async def _cycles_of(cycles: MemoryCycleRegistry) -> list[Cycle]:
    return await cycles.list_cycles("group_run")


async def test_a_drained_intent_becomes_one_cycle_that_carries_its_campaign(campaigns):
    cycles = MemoryCycleRegistry()
    launch_id = await _decide_launch(campaigns)

    [launched] = await CampaignLauncher(
        campaigns, cycles, _builder(), actor="l1", box_verdict=quiet_box
    ).drain()

    [cycle] = await _cycles_of(cycles)
    intent = await campaigns.get_launch_intent(launch_id)
    assert (cycle.campaign_id, cycle.kind) == (CID, "increment")
    assert (intent.state, intent.cycle_id) == (LaunchIntentState.LAUNCHED, cycle.cycle_id)
    assert launched.created and launched.cycle_id == cycle.cycle_id
    assert (
        await CampaignLauncher(
            campaigns, cycles, _builder(), actor="l1", box_verdict=quiet_box
        ).drain()
        == []
    )


async def test_a_crash_before_the_cycle_is_created_is_relaunched_once(campaigns):
    cycles = MemoryCycleRegistry()
    launch_id = await _decide_launch(campaigns)
    build = _builder(fail_times=1)

    with pytest.raises(_Crash):
        await CampaignLauncher(campaigns, cycles, build, actor="l1", box_verdict=quiet_box).drain()
    assert await _cycles_of(cycles) == []
    assert (await campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING

    await CampaignLauncher(campaigns, cycles, build, actor="l1", box_verdict=quiet_box).drain()
    assert len(await _cycles_of(cycles)) == 1


async def test_a_crash_after_the_cycle_is_created_finds_it_instead_of_creating_another(
    campaigns,
):
    """Bug caught: a re-drain that creates a second cycle because the intent was never marked."""
    cycles = _CrashAfterCreate()
    launch_id = await _decide_launch(campaigns)

    with pytest.raises(_Crash):
        await CampaignLauncher(
            campaigns, cycles, _builder(), actor="l1", box_verdict=quiet_box
        ).drain()
    [first] = await _cycles_of(cycles)
    assert (await campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING

    [launched] = await CampaignLauncher(
        campaigns, cycles, _builder(), actor="l1", box_verdict=quiet_box
    ).drain()

    assert [c.cycle_id for c in await _cycles_of(cycles)] == [first.cycle_id]
    assert launched.cycle_id == first.cycle_id and not launched.created
    assert (await campaigns.get_launch_intent(launch_id)).cycle_id == first.cycle_id


async def test_two_launchers_on_one_intent_create_one_cycle(campaigns):
    cycles = MemoryCycleRegistry()
    await _decide_launch(campaigns)
    build = _builder(yield_first=True)

    first, second = await asyncio.gather(
        CampaignLauncher(campaigns, cycles, build, actor="l1", box_verdict=quiet_box).drain(),
        CampaignLauncher(campaigns, cycles, build, actor="l2", box_verdict=quiet_box).drain(),
    )

    [cycle] = await _cycles_of(cycles)
    assert [r.cycle_id for r in first + second] == [cycle.cycle_id, cycle.cycle_id]
    marks = [
        e
        for e in await campaigns.control_log(CID)
        if e.operation is ControlOperation.MARK_LAUNCHED and e.outcome is ControlOutcome.APPLIED
    ]
    assert len(marks) == 1


async def test_a_launch_an_abort_overtook_is_cancelled_as_soon_as_it_exists(campaigns):
    """§12a: no continuation follows an abort. The intent was read before the abort committed,
    so the cycle is created and recorded — and cancelled before anything runs in it."""
    cycles = MemoryCycleRegistry()
    await _decide_launch(campaigns)

    async def abort():
        await campaigns.transition(
            CID,
            move(
                S.COMPLETED,
                "k-abort",
                operation=ControlOperation.ABORT,
                outcome=CampaignOutcome.ABORTED,
            ),
        )

    [launched] = await CampaignLauncher(
        campaigns, cycles, _builder(before_return=abort), actor="l1", box_verdict=quiet_box
    ).drain()

    [cycle] = await _cycles_of(cycles)
    assert launched.cancelled_after_abort and cycle.cancelled


async def test_a_built_cycle_that_does_not_name_the_intents_campaign_is_refused(campaigns):
    """Bug caught: a builder that forgets to stamp the campaign, leaving a launched cycle no
    reader can attribute to its campaign."""
    cycles = MemoryCycleRegistry()
    await _decide_launch(campaigns)

    async def unstamped(intent):
        cycle = await _builder()(intent)
        return Cycle(**{**cycle.__dict__, "campaign_id": None})

    with pytest.raises(ValueError, match="the built cycle names campaign None"):
        await CampaignLauncher(
            campaigns, cycles, unstamped, actor="l1", box_verdict=quiet_box
        ).drain()
    assert await _cycles_of(cycles) == []


async def test_a_launch_without_a_campaign_or_launch_id_is_refused_by_the_cycle_registry():
    cycles = MemoryCycleRegistry()
    intent_like = LaunchIntent(
        launch_id="lnc_000000000001",
        campaign_id=CID,
        decision_entry_id="ctl_000000000001",
        cycle_kind=CycleKind.INCREMENT,
        cycle_request={},
        state=LaunchIntentState.PENDING,
        created_at=datetime.now(UTC),
    )
    cycle = await _builder()(intent_like)
    with pytest.raises(ValidationError, match="launch needs"):
        await cycles.create_cycle_for_launch(
            Cycle(**{**cycle.__dict__, "campaign_id": None}), "lnc_1"
        )
    with pytest.raises(ValidationError, match="launch needs"):
        await cycles.create_cycle_for_launch(cycle, "")


async def test_one_campaigns_fault_holds_only_its_own_launch(campaigns):
    """The fifth read of #2570. Bug caught: a fault in one campaign's launch, such as its
    project's repository unreachable when its cycle binds, raising out of the drain before any
    later intent is read, so every other campaign's launch waits behind it, drain after drain,
    because the faulting intent is always the oldest."""
    other = "cmp_bbbbbbbbbbbb"
    await campaigns.create_campaign(
        campaign(other), actor="owner", actor_role="owner", reason="r", idempotency_key="create-2"
    )
    await campaigns.transition(other, move(S.CALIBRATING, "k-cal-2"))
    held = await _decide_launch(campaigns)
    result = await campaigns.transition(
        other, move(S.AT_PROPOSAL, "k-decide-2", launch=LaunchRequest(CycleKind.INCREMENT))
    )
    cycles = MemoryCycleRegistry()

    async def build(intent: LaunchIntent) -> Cycle:
        if intent.campaign_id == CID:
            raise TimeoutError("the project's repository did not answer")
        return cycle_for(intent)

    with pytest.raises(TimeoutError):
        await CampaignLauncher(campaigns, cycles, build, actor="l1", box_verdict=quiet_box).drain()

    assert [c.campaign_id for c in await _cycles_of(cycles)] == [other]
    assert (await campaigns.get_launch_intent(held)).state is LaunchIntentState.PENDING
    launched = await campaigns.get_launch_intent(result.intent.launch_id)
    assert launched.state is LaunchIntentState.LAUNCHED


async def test_a_campaign_faulted_before_its_launch_holds_only_itself_and_keeps_its_order(
    campaigns,
):
    """The sixth read of #2570. Bugs caught: a fault before the launch itself (the campaign
    unreadable) still raising out of the drain and holding every campaign behind it; and the
    faulted campaign's next pending intent launched ahead of the one that faulted."""
    other = "cmp_bbbbbbbbbbbb"
    await campaigns.create_campaign(
        campaign(other), actor="owner", actor_role="owner", reason="r", idempotency_key="create-2"
    )
    await campaigns.transition(other, move(S.CALIBRATING, "k-cal-2"))
    first = await _decide_launch(campaigns)
    later = (
        await campaigns.transition(
            CID, move(S.AT_PROPOSAL, "k-decide-3", launch=LaunchRequest(CycleKind.INCREMENT))
        )
    ).intent.launch_id
    await campaigns.transition(
        other, move(S.AT_PROPOSAL, "k-decide-2", launch=LaunchRequest(CycleKind.INCREMENT))
    )
    read = campaigns.get_campaign
    reads = []

    async def get_campaign(campaign_id):
        reads.append(campaign_id)
        if campaign_id == CID:
            raise TimeoutError("the campaign registry did not answer")
        return await read(campaign_id)

    campaigns.get_campaign = get_campaign
    cycles = MemoryCycleRegistry()

    with pytest.raises(TimeoutError):
        await CampaignLauncher(
            campaigns, cycles, _builder(), actor="l1", box_verdict=quiet_box
        ).drain()

    assert [c.campaign_id for c in await _cycles_of(cycles)] == [other]
    assert reads.count(CID) == 1
    for launch_id in (first, later):
        assert (await campaigns.get_launch_intent(launch_id)).state is LaunchIntentState.PENDING
