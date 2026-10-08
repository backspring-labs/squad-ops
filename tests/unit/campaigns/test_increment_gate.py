"""The increment gate's submission and ruling (SIP-0109 §9.2, §19 criteria 3 and 5; #1801).

Through the memory registry, whose transaction adjudicates a ruling against the committed
campaign: the proposal submitted to the gate and the accepted tree.
"""

from __future__ import annotations

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.gate import (
    RETURNING_DECISIONS,
    binding_from_change_request,
    ruling_transition,
    submission,
)
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ControlOperationRefused,
    ProposalBinding,
    RefusalReason,
    SubmittedProposal,
)
from squadops.cycles.models import GateDecisionValue
from tests.unit.campaigns.builders import campaign, move

S = CampaignState
D = GateDecisionValue
CID = "cmp_gate00000001"
BASE = "sha-accepted"
V1 = ProposalBinding("prop_1", 1, "hash-v1", BASE)
V2 = ProposalBinding("prop_1", 2, "hash-v2", BASE)


def _rule(decision: GateDecisionValue, binding: ProposalBinding, key: str, run_id: str = "run_p1"):
    return ruling_transition(
        decision,
        binding,
        run_id=run_id,
        actor="crew-supervisor",
        actor_role="campaign-supervisor",
        reason="read the change request and its footprint",
        idempotency_key=key,
        # SIP-0109 §24bi: a return names what went wrong.
        classification="scope_too_large" if decision in RETURNING_DECISIONS else None,
    )


async def _submit(reg, binding: ProposalBinding, run_id: str):
    state = (await reg.get_campaign(CID)).state
    return await reg.transition(CID, submission(state, SubmittedProposal(binding, "cyc_1", run_id)))


@pytest.fixture
async def at_the_gate() -> MemoryCampaignRegistry:
    """Calibrated (its tree promoted), then v1 of a proposal submitted from run_p1."""
    reg = MemoryCampaignRegistry()
    await reg.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await reg.transition(CID, move(S.CALIBRATING, "k-cal"))
    await reg.transition(
        CID,
        move(
            S.CALIBRATING,
            "k-promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree(BASE, "cyc_cal"),
        ),
    )
    await reg.transition(CID, move(S.AT_PROPOSAL, "k-propose"))
    await _submit(reg, V1, "run_p1")
    return reg


async def test_a_submission_pins_the_proposal_and_opens_the_gate(at_the_gate):
    stored = await at_the_gate.get_campaign(CID)
    log = await at_the_gate.control_log(CID)
    assert stored.state is S.AWAITING_RULING
    assert stored.proposal == SubmittedProposal(V1, "cyc_1", "run_p1")
    assert (log[-1].operation, log[-1].target, log[-1].binding["content_hash"]) == (
        ControlOperation.SUBMIT,
        "run_p1",
        "hash-v1",
    )


@pytest.mark.parametrize(
    ("decision", "binding", "run_id", "refusal"),
    [
        # §9.2: refining would make the supervisor an author.
        (D.APPROVED_WITH_REFINEMENTS, V1, "run_p1", RefusalReason.ILLEGAL_RULING),
        (D.APPROVED, ProposalBinding("prop_1", 1, "hash-edited", BASE), "run_p1", "stale"),
        (D.APPROVED, ProposalBinding("prop_1", 0, "hash-v1", BASE), "run_p1", "stale"),
        (D.APPROVED, ProposalBinding("prop_1", 1, "hash-v1", "sha-older"), "run_p1", "stale"),
        (D.APPROVED, V1, "run_p0", "stale"),  # the gate of a run whose proposal is not current
    ],
    ids=["refinements", "content", "version", "baseline", "run"],
)
async def test_a_ruling_not_bound_to_the_current_proposal_is_refused_and_moves_nothing(
    at_the_gate, decision, binding, run_id, refusal
):
    """§19 criterion 5. Bug caught: a ruling on an edited, older or differently-based proposal
    building anyway — an approval authorizing scope nobody reviewed."""
    refusal = RefusalReason.STALE_BINDING if refusal == "stale" else refusal

    with pytest.raises(ControlOperationRefused) as refused:
        await at_the_gate.transition(CID, _rule(decision, binding, "k-rule", run_id))

    assert refused.value.entry.refusal is refusal
    assert (await at_the_gate.get_campaign(CID)).state is S.AWAITING_RULING


async def test_a_revision_makes_the_old_approval_stale_and_binds_the_new_version(at_the_gate):
    """§9.2: a revision request sends the proposal back; the new version is ruled on afresh.
    Bug caught: v1's binding still accepted once v2 is at the gate."""
    await at_the_gate.transition(CID, _rule(D.RETURNED_FOR_REVISION, V1, "k-revise"))
    await _submit(at_the_gate, V2, "run_p2")

    with pytest.raises(ControlOperationRefused) as stale:
        await at_the_gate.transition(CID, _rule(D.APPROVED, V1, "k-approve-v1", "run_p1"))
    approved = await at_the_gate.transition(CID, _rule(D.APPROVED, V2, "k-approve", "run_p2"))

    assert stale.value.entry.refusal is RefusalReason.STALE_BINDING
    assert approved.campaign.state is S.BUILDING
    assert approved.entry.binding == {
        "decision": "approved",
        "proposal_id": "prop_1",
        "version": 2,
        "content_hash": "hash-v2",
        "baseline_tree": BASE,
    }


async def test_a_repeated_ruling_changes_nothing_and_a_different_one_under_its_key_conflicts(
    at_the_gate,
):
    first = await at_the_gate.transition(CID, _rule(D.APPROVED, V1, "k-rule"))
    again = await at_the_gate.transition(CID, _rule(D.APPROVED, V1, "k-rule"))
    with pytest.raises(ControlOperationRefused) as conflict:
        await at_the_gate.transition(CID, _rule(D.REJECTED, V1, "k-rule"))

    assert again.replayed and again.entry == first.entry
    assert conflict.value.entry.refusal is RefusalReason.CONFLICTING_IDEMPOTENCY_KEY
    assert (await at_the_gate.get_campaign(CID)).state is S.BUILDING


async def test_a_proposal_submitted_while_paused_is_recorded_in_place(at_the_gate):
    """A pause during the proposal run must not be lifted by the gate opening."""
    await at_the_gate.transition(CID, _rule(D.RETURNED_FOR_REVISION, V1, "k-revise"))
    await at_the_gate.transition(CID, move(S.PAUSED, "k-pause", operation=ControlOperation.PAUSE))

    await _submit(at_the_gate, V2, "run_p2")

    stored = await at_the_gate.get_campaign(CID)
    assert (stored.state, stored.proposal.run_id) == (S.PAUSED, "run_p2")


@pytest.mark.parametrize(
    "document",
    ["- a list\n", "proposal_id: p\nversion: 1\ncontent_hash: ''\nbaseline_tree: b\n"],
    ids=["not-a-mapping", "no-hash"],
)
def test_a_change_request_without_its_identity_cannot_be_submitted(document):
    """Bug caught: a proposal pinned with a blank hash, which every ruling then matches."""
    with pytest.raises(ValueError):
        binding_from_change_request(document)
