"""The campaign registry's control-log contract, on the memory adapter (SIP-0109 §12a, §12b, §13).

Part B runs the same scenarios against Postgres, where atomicity and restart are real.
"""

from __future__ import annotations

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.lifecycle import launch_id_for
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignExistsError,
    CampaignNotFoundError,
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    CycleKind,
    LaunchIntentNotFoundError,
    LaunchIntentState,
    LaunchRequest,
    RefusalReason,
)
from tests.unit.campaigns.builders import campaign, move

S = CampaignState
CID = "cmp_aaaaaaaaaaaa"


def _launching(to: S, key: str, **overrides):
    return move(
        to,
        key,
        launch=LaunchRequest(CycleKind.INCREMENT, {"request_profile": "group-run-react"}),
        **overrides,
    )


@pytest.fixture
async def registry() -> MemoryCampaignRegistry:
    reg = MemoryCampaignRegistry()
    await reg.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    return reg


async def _walk_to_at_proposal(reg) -> None:
    await reg.transition(CID, move(S.CALIBRATING, "k-cal"))
    await reg.transition(CID, move(S.AT_PROPOSAL, "k-prop"))


async def test_a_launching_decision_commits_state_row_and_intent_together(registry):
    """Bug caught: an intent written without its row, a row without its state, or a launch id
    not derived from the deciding row — each breaks restart from the log (§12a, §12b)."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    result = await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-decide"))

    stored = await registry.get_campaign(CID)
    log = await registry.control_log(CID)
    intent = await registry.get_launch_intent(result.intent.launch_id)
    assert stored.state is S.AT_PROPOSAL
    assert log[-1] == result.entry
    assert (log[-1].prior_state, log[-1].next_state) == (S.CALIBRATING, S.AT_PROPOSAL)
    assert intent.launch_id == launch_id_for(result.entry.entry_id) == result.entry.launch_id
    assert intent.decision_entry_id == result.entry.entry_id
    assert (intent.state, intent.cycle_kind) == (LaunchIntentState.PENDING, CycleKind.INCREMENT)
    assert [e.seq for e in log] == [1, 2, 3]


async def test_a_repeated_operation_replays_and_launches_nothing_new(registry):
    """Bug caught: a ruling or decision delivered twice launching twice (§12a: a repeated ruling
    changes nothing)."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    first = await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-decide"))
    again = await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-decide"))

    assert again.replayed and not first.replayed
    assert again.entry == first.entry
    assert again.intent == first.intent
    assert len(await registry.control_log(CID)) == 3
    assert [i.launch_id for i in await registry.pending_launch_intents()] == [
        first.intent.launch_id
    ]


async def test_a_repeat_after_the_campaign_moved_on_replays_instead_of_refusing_as_stale(registry):
    await _walk_to_at_proposal(registry)
    ruling = move(S.AWAITING_RULING, "k-gate", expected_state=S.AT_PROPOSAL)
    first = await registry.transition(CID, ruling)
    await registry.transition(CID, move(S.BUILDING, "k-approve", operation=ControlOperation.RULE))

    again = await registry.transition(CID, ruling)
    assert again.replayed and again.entry == first.entry
    assert (await registry.get_campaign(CID)).state is S.BUILDING


def _promote(to: S, key: str, identity: str, cycle_id: str = "cyc_cal000000001"):
    return move(
        to, key, operation=ControlOperation.PROMOTE, accepted=AcceptedTree(identity, cycle_id)
    )


async def test_only_a_promotion_moves_the_accepted_tree(registry):
    """§12a. Bug caught: the tree dropped by a later transition (every rebuild of the campaign
    from a transition must carry it), or set by a decision rather than a promotion."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    promoted = await registry.transition(CID, _promote(S.CALIBRATING, "k-promote", "sha-cal"))
    await registry.transition(CID, move(S.AT_PROPOSAL, "k-prop"))
    await registry.transition(CID, move(S.PAUSED, "k-pause", operation=ControlOperation.PAUSE))

    stored = await registry.get_campaign(CID)
    assert promoted.entry.operation is ControlOperation.PROMOTE
    assert stored.accepted == AcceptedTree("sha-cal", "cyc_cal000000001")
    assert stored.state is S.PAUSED


async def test_a_second_promotion_under_the_same_key_with_another_tree_is_refused(registry):
    """§12a: a promotion is keyed by (campaign, increment, candidate identity). Bug caught: the
    tree left out of the request hash, so a different tree under a used key replays as the first
    and the caller believes the second was accepted."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    await registry.transition(CID, _promote(S.CALIBRATING, "k-promote", "sha-cal"))

    replay = await registry.transition(CID, _promote(S.CALIBRATING, "k-promote", "sha-cal"))
    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(CID, _promote(S.CALIBRATING, "k-promote", "sha-other"))

    assert replay.replayed
    assert refused.value.entry.refusal is RefusalReason.CONFLICTING_IDEMPOTENCY_KEY
    assert (await registry.get_campaign(CID)).accepted.identity == "sha-cal"


async def test_a_conflicting_idempotency_key_is_refused_and_recorded(registry):
    """Bug caught: a second, different ruling under a used key silently overwriting the first."""
    await _walk_to_at_proposal(registry)
    await registry.transition(CID, move(S.AWAITING_RULING, "k-gate"))

    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(CID, move(S.AWAITING_RULING, "k-gate", reason="different"))

    log = await registry.control_log(CID)
    assert refused.value.entry == log[-1]
    assert (log[-1].outcome, log[-1].refusal) == (
        ControlOutcome.REFUSED,
        RefusalReason.CONFLICTING_IDEMPOTENCY_KEY,
    )
    assert (await registry.get_campaign(CID)).state is S.AWAITING_RULING


@pytest.mark.parametrize(
    ("transition", "refusal"),
    [
        (move(S.BUILDING, "k-x"), RefusalReason.ILLEGAL_TRANSITION),
        (move(S.AWAITING_RULING, "k-x", expected_state=S.EVALUATING), RefusalReason.STALE_STATE),
    ],
)
async def test_a_refused_operation_writes_its_row_and_nothing_else(registry, transition, refusal):
    """Bug caught: a refused launching operation leaving its intent or its state behind."""
    await _walk_to_at_proposal(registry)
    launching = move(
        transition.next_state,
        transition.idempotency_key,
        expected_state=transition.expected_state,
        launch=LaunchRequest(CycleKind.INCREMENT),
    )

    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(CID, launching)

    assert refused.value.entry.refusal is refusal
    assert refused.value.entry.launch_id is None
    assert (await registry.get_campaign(CID)).state is S.AT_PROPOSAL
    assert await registry.pending_launch_intents() == []
    # The refusal holds no key: the same key, now legal, still applies.
    applied = await registry.transition(CID, move(S.AWAITING_RULING, transition.idempotency_key))
    assert not applied.replayed


async def test_no_launch_follows_an_abort(registry):
    """§12a: an abort is terminal and no continuation follows, whatever was pending when it
    committed or arrives after."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    pending = await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-decide"))
    await registry.transition(
        CID,
        move(
            S.COMPLETED,
            "k-abort",
            operation=ControlOperation.ABORT,
            outcome=CampaignOutcome.ABORTED,
            actor_role="owner",
        ),
    )

    assert await registry.pending_launch_intents() == []
    with pytest.raises(ControlOperationRefused) as refused:
        await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-late"))
    assert refused.value.entry.refusal is RefusalReason.CAMPAIGN_COMPLETED
    # The intent is still not launched: it is withheld, and its record says so truthfully.
    assert (await registry.get_launch_intent(pending.intent.launch_id)).state is (
        LaunchIntentState.PENDING
    )


async def test_marking_an_intent_launched_is_keyed_by_its_launch(registry):
    """Bug caught: two launchers marking one intent with different cycles — two cycles for one
    launch — accepted silently instead of refused and recorded (§12b)."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    decided = await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-decide"))
    launch_id = decided.intent.launch_id

    marked = await registry.mark_launch_intent_launched(launch_id, "cyc_111111111111", actor="l1")
    again = await registry.mark_launch_intent_launched(launch_id, "cyc_111111111111", actor="l1")
    with pytest.raises(ControlOperationRefused) as refused:
        await registry.mark_launch_intent_launched(launch_id, "cyc_222222222222", actor="l1")

    intent = await registry.get_launch_intent(launch_id)
    assert (intent.state, intent.cycle_id) == (LaunchIntentState.LAUNCHED, "cyc_111111111111")
    assert marked.entry.launch_id == launch_id and again.replayed
    assert refused.value.entry.refusal is RefusalReason.CONFLICTING_IDEMPOTENCY_KEY
    assert (marked.entry.prior_state, marked.entry.next_state) == (S.AT_PROPOSAL, S.AT_PROPOSAL)
    assert await registry.pending_launch_intents() == []


async def test_a_launch_made_before_an_abort_is_still_recorded(registry):
    await registry.transition(CID, move(S.CALIBRATING, "k-cal"))
    decided = await registry.transition(CID, _launching(S.AT_PROPOSAL, "k-decide"))
    await registry.transition(
        CID,
        move(
            S.COMPLETED,
            "k-abort",
            operation=ControlOperation.ABORT,
            outcome=CampaignOutcome.ABORTED,
        ),
    )

    marked = await registry.mark_launch_intent_launched(
        decided.intent.launch_id, "cyc_111111111111", actor="l1"
    )
    assert marked.campaign.state is S.COMPLETED
    assert marked.intent.cycle_id == "cyc_111111111111"


async def test_the_campaign_state_is_its_last_applied_row(registry):
    """§12a: on restart the campaign's state is the log's last committed transition. A refused
    row in between must not be read as the state."""
    await _walk_to_at_proposal(registry)
    with pytest.raises(ControlOperationRefused):
        await registry.transition(CID, move(S.PROMOTING, "k-bad"))

    log = await registry.control_log(CID)
    last_applied = [e for e in log if e.outcome is ControlOutcome.APPLIED][-1]
    assert (await registry.get_campaign(CID)).state is last_applied.next_state is S.AT_PROPOSAL


async def test_creation_replays_and_refuses_a_different_creation_under_the_same_id(registry):
    again = await registry.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    assert again.replayed and again.entry.seq == 1

    with pytest.raises(CampaignExistsError):
        await registry.create_campaign(
            campaign(CID, project_id="other"),
            actor="owner",
            actor_role="owner",
            reason="r",
            idempotency_key="create-1",
        )
    with pytest.raises(ValueError, match="created in draft"):
        await registry.create_campaign(
            campaign("cmp_bbbbbbbbbbbb", state=S.CALIBRATING),
            actor="owner",
            actor_role="owner",
            reason="r",
            idempotency_key="create-2",
        )


async def test_the_stored_log_is_not_reachable_through_a_returned_row(registry):
    """Bug caught: the memory adapter handing out its own dicts, so a caller editing a returned
    row's binding rewrites the append-only log."""
    await registry.transition(CID, move(S.CALIBRATING, "k-cal", binding={"proposal_id": "p1"}))
    (await registry.control_log(CID))[-1].binding["proposal_id"] = "tampered"
    assert (await registry.control_log(CID))[-1].binding == {"proposal_id": "p1"}


async def test_unknown_ids_raise_their_not_found_errors(registry):
    with pytest.raises(CampaignNotFoundError):
        await registry.transition("cmp_missing00000", move(S.CALIBRATING, "k"))
    with pytest.raises(CampaignNotFoundError):
        await registry.control_log("cmp_missing00000")
    with pytest.raises(LaunchIntentNotFoundError):
        await registry.mark_launch_intent_launched("lnc_missing00000", "cyc_1", actor="l1")
