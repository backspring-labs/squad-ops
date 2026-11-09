"""The owner's grant of a Campaign's goal-set curation to the operator, as a control-log row (SIP-0115
Q41, §10c; SIP-0109 §24dd), through the registry that commits it. The route's scope is
``tests/unit/api/test_goal_delegation_routes.py``'s."""

from __future__ import annotations

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.goal_delegation import goal_delegation, goal_delegation_transition
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    RefusalReason,
)
from tests.fixtures.goal_set import campaign_on, started
from tests.unit.campaigns.builders import move

CID = "cmp_1"


def _grant(campaign, key: str = "g-1", **overrides):
    values = dict(actor="owner", actor_role="admin", reason="the owner approved it")
    return goal_delegation_transition(campaign, idempotency_key=key, **(values | overrides))


async def _abort(registry) -> None:
    await registry.transition(
        CID,
        move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
             outcome=CampaignOutcome.ABORTED),
    )  # fmt: skip


@pytest.fixture
async def registry():
    held = MemoryCampaignRegistry()
    await started(held, CID)
    return held


async def test_a_grant_moves_no_state_and_reads_back_with_who_why_and_where_from(registry):
    """Bugs caught: the grant moving the Campaign, so a grant at a gate loses the gate; who
    granted, why or the conversation's link missing from the row the operator's authority rests on."""
    campaign = await registry.get_campaign(CID)

    result = await registry.transition(
        CID, _grant(campaign, source_ref="https://chat.example.invalid/thread/7")
    )

    found = goal_delegation(await registry.control_log(CID))
    assert found is not None and found.entry_id == result.entry.entry_id
    assert (found.actor, found.actor_role, found.reason) == (
        "owner",
        "admin",
        "the owner approved it",
    )
    assert found.binding == {
        "goal_set": "prj-lantern",
        "source_ref": "https://chat.example.invalid/thread/7",
    }
    assert (found.prior_state, found.next_state) == (
        CampaignState.AT_PROPOSAL,
        CampaignState.AT_PROPOSAL,
    )
    assert (await registry.get_campaign(CID)).state is CampaignState.AT_PROPOSAL


async def test_a_completed_campaign_refuses_a_grant_and_records_the_refusal(registry):
    """Bug caught: the grant treated as every other record-only row, which a completed Campaign
    accepts, so the log reads a delegation for a Campaign with no life left."""
    campaign = await registry.get_campaign(CID)
    await _abort(registry)

    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(CID, _grant(campaign))

    assert refused.value.entry.refusal is RefusalReason.CAMPAIGN_COMPLETED
    log = await registry.control_log(CID)
    assert log[-1].outcome is ControlOutcome.REFUSED
    assert goal_delegation(log) is None


async def test_a_committed_grant_replays_even_after_the_campaign_completed(registry):
    """§12a. Bug caught: a retry whose first answer was lost refused as ``campaign_completed``,
    so the owner reads a grant that is on the log as one that failed."""
    campaign = await registry.get_campaign(CID)
    first = await registry.transition(CID, _grant(campaign))
    await _abort(registry)

    again = await registry.transition(CID, _grant(campaign))

    assert (again.replayed, again.entry.entry_id) == (True, first.entry.entry_id)
    log = await registry.control_log(CID)
    assert [e.operation for e in log].count(ControlOperation.GOAL_DELEGATION_GRANTED) == 1


async def test_a_refused_grant_grants_nothing(registry):
    """Bug caught: the reader matching the operation alone, so a refused attempt's row reads as
    the owner's grant."""
    campaign = await registry.get_campaign(CID)

    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(CID, _grant(campaign, expected_state=CampaignState.PAUSED))

    assert refused.value.entry.refusal is RefusalReason.STALE_STATE
    log = await registry.control_log(CID)
    assert log[-1].operation is ControlOperation.GOAL_DELEGATION_GRANTED
    assert goal_delegation(log) is None


async def test_no_binding_on_another_row_stands_in_for_a_grant(registry):
    """Q41: the operator writes rows too. Bug caught: the reader taking a binding's word for it, so a
    row the operator may write (a classification) authorizes the operator."""
    await registry.transition(
        CID,
        CampaignTransition(
            operation=ControlOperation.CLASSIFY, actor="operator", actor_role="campaign-supervisor",
            reason="r", idempotency_key="c-1", next_state=None, target="prop_1",
            binding={"goal_set": "prj-lantern", "operation": "goal_delegation_granted"},
        ),
    )  # fmt: skip

    assert goal_delegation(await registry.control_log(CID)) is None


def test_a_campaign_with_no_goal_set_has_nothing_to_delegate():
    with pytest.raises(ValueError, match="names no goal set"):
        _grant(campaign_on("prj-lantern", CID, goals=False))
