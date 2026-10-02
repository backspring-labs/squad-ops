"""The increment gate (SIP-0109 §9.2; #1801): the proposal submitted to it, and the ruling on it.

The gate follows a campaign increment cycle's ``proposal`` workload. When it opens, the proposal
the run produced is **submitted**: a control-log row that pins it as the campaign's proposal and
moves the campaign to ``awaiting_ruling``. The supervisor's ruling is recorded through the
existing gate decision path (``squadops runs gate``) as a ``rule`` row first, checked in that
row's transaction against the submitted proposal and the accepted tree, so an old approval
cannot authorize changed scope; the gate decision on the run follows the row.

The gate is never passed through by the absence of design questions (#807): an increment cycle
carries its baseline's manifest, which asks nothing, and only the ruling moves this gate.
"""

from __future__ import annotations

import yaml

from squadops.campaigns.models import (
    RULING_MOVES,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    IncrementRuling,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.cycles.models import GateDecisionValue

#: The gate's name, as a campaign increment profile declares it after the proposal workload.
INCREMENT_RULING_GATE = "increment_ruling"

#: The provenance of the candidate manifest an approved increment seeds for its framing (§7.3).
INCREMENT_SEED_PRODUCER = "campaign.increment_seed"

#: The role on the rows the executor writes for the campaign.
EXECUTOR_ROLE = "executor"


def binding_from_change_request(document: str) -> ProposalBinding:
    """The binding of a stored change request (``change_request.yaml``, the proposal run's
    artifact). Its identity fields are the framework's, written by the proposal's rails."""
    data = yaml.safe_load(document)
    if not isinstance(data, dict):
        raise ValueError("the change request is not a mapping")
    return ProposalBinding(
        proposal_id=str(data.get("proposal_id") or ""),
        version=int(data.get("version") or 0),
        content_hash=str(data.get("content_hash") or ""),
        baseline_tree=str(data.get("baseline_tree") or ""),
    )


def submission(state: CampaignState, proposal: SubmittedProposal) -> CampaignTransition:
    """The row that pins ``proposal`` at the gate. It moves an ``at_proposal`` campaign to
    ``awaiting_ruling``; a campaign holding (paused, escalated, launch-blocked) records the
    proposal in place, and its resume returns it to the gate. Keyed by the run, so the executor
    re-entering the gate after a restart replays the row."""
    return CampaignTransition(
        operation=ControlOperation.SUBMIT,
        actor="squadops",
        actor_role=EXECUTOR_ROLE,
        reason=(
            f"proposal {proposal.binding.proposal_id} v{proposal.binding.version} "
            f"at the increment gate"
        ),
        idempotency_key=f"submit:{proposal.run_id}",
        next_state=(CampaignState.AWAITING_RULING if state is CampaignState.AT_PROPOSAL else state),
        target=proposal.run_id,
        binding={
            "proposal_id": proposal.binding.proposal_id,
            "version": proposal.binding.version,
            "content_hash": proposal.binding.content_hash,
            "baseline_tree": proposal.binding.baseline_tree,
            "cycle_id": proposal.cycle_id,
        },
        submitted=proposal,
    )


def ruling_transition(
    decision: GateDecisionValue,
    binding: ProposalBinding,
    *,
    run_id: str,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
) -> CampaignTransition:
    """The ``rule`` row. A decision the gate does not take still becomes a row, refused as
    ``illegal_ruling`` and recorded; it moves nothing."""
    return CampaignTransition(
        operation=ControlOperation.RULE,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=RULING_MOVES.get(decision, CampaignState.AWAITING_RULING),
        target=run_id,
        binding={
            "decision": decision.value,
            "proposal_id": binding.proposal_id,
            "version": binding.version,
            "content_hash": binding.content_hash,
            "baseline_tree": binding.baseline_tree,
        },
        ruling=IncrementRuling(decision, binding, run_id),
    )
