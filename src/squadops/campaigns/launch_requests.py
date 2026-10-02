"""The cycles a campaign launches, as launch requests (SIP-0109 §12b).

A launch intent carries the whole cycle-create request, built here from the campaign's policy
when the deciding row is written, so a launch re-drained after a restart creates the cycle the
decision named, not one rebuilt from whatever the profiles say by then.
"""

from __future__ import annotations

import uuid

from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    CycleKind,
    LaunchRequest,
)
from squadops.contracts.cycle_request_profiles import cycle_request_body


def calibration_launch(campaign: Campaign) -> LaunchRequest:
    """The calibration cycle (§11): the policy's calibration profile, run by its squad, on the
    campaign's project. Its accepted tree becomes the first baseline."""
    policy = campaign.policy
    return LaunchRequest(
        CycleKind.CALIBRATION,
        {
            "body": cycle_request_body(
                policy.calibration_profile,
                squad_profile_id=policy.squad_profile,
                notes=f"campaign {campaign.campaign_id}: calibration (SIP-0109 §11)",
            )
        },
    )


def start_transition(
    campaign: Campaign, *, actor: str, actor_role: str, reason: str, idempotency_key: str
) -> CampaignTransition:
    """The owner's start: a draft campaign moves to calibrating, and its calibration cycle's
    launch intent is written in the same transaction (§12b). Acted on the draft only."""
    return CampaignTransition(
        operation=ControlOperation.START,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=CampaignState.CALIBRATING,
        expected_state=CampaignState.DRAFT,
        launch=calibration_launch(campaign),
    )


def increment_launch(
    campaign: Campaign, baseline_manifest: str, frozen: tuple[dict, ...] = ()
) -> LaunchRequest:
    """An increment cycle (§7.3): the policy's proposal profile, run by its squad, proposing
    against the accepted tree. The ``campaign_proposal`` block carries what the proposal run
    reads — the accepted tree's identity and its manifest's text (the agent has no vault, #1821),
    the objective — and the campaign's revision budget, which the increment gate spends (§9.5).

    ``frozen`` is every criterion earlier increments froze (§8.1), each with its own test file and
    its verifier bundle's artifact: pinned at launch, so the proposal knows the ids it may not
    reuse and the evaluation runs exactly these bundles, whatever is promoted meanwhile."""
    policy = campaign.policy
    assert campaign.accepted is not None
    return LaunchRequest(
        CycleKind.INCREMENT,
        {
            "body": cycle_request_body(
                policy.proposal_profile,
                squad_profile_id=policy.squad_profile,
                user_values={
                    "campaign_proposal": {
                        "proposal_id": f"prop_{uuid.uuid4().hex[:12]}",
                        "version": 1,
                        "baseline_tree": campaign.accepted.identity,
                        # The cycle whose delivered files the increment builds on (§7.1).
                        "accepted_cycle_id": campaign.accepted.cycle_id,
                        "baseline_manifest": baseline_manifest,
                        "objective": {
                            "statement": campaign.objective.statement,
                            "allowed_scope": list(campaign.objective.allowed_scope),
                            "measurement": campaign.objective.measurement,
                        },
                        "prior_criteria": [f["criterion_id"] for f in frozen],
                        "frozen_criteria": [dict(f) for f in frozen],
                        "max_revisions": policy.max_proposal_revisions,
                    }
                },
                notes=f"campaign {campaign.campaign_id}: increment (SIP-0109 §7.3)",
            )
        },
    )


def bound_launch(
    campaign: Campaign,
    kind: CycleKind,
    block: dict,
    plan_artifact_refs: list[str],
    contract_ref: str | None,
) -> LaunchRequest:
    """A cycle that reuses an increment's bound change request, ruling, baseline and footprint
    (§10a): the policy's proposal profile — so the stack is the campaign's — with its proposal
    step removed, since no proposal is run and no ruling is asked. It carries the increment's
    ``campaign_proposal`` block and the approved seeds, so every increment seam reads it as the
    increment it continues."""
    from squadops.contracts.cycle_request_profiles import load_profile
    from squadops.cycles.models import WorkloadType

    policy = campaign.policy
    sequence = [
        dict(w)
        for w in load_profile(policy.proposal_profile).defaults["workload_sequence"]
        if w.get("type") != WorkloadType.PROPOSAL
    ]
    assert kind in (CycleKind.RETRY, CycleKind.REPAIR), kind
    user_values: dict = {
        "campaign_proposal": dict(block),
        "plan_artifact_refs": list(plan_artifact_refs),
        "workload_sequence": sequence,
    }
    if contract_ref:
        user_values["contract_ref"] = contract_ref
    return LaunchRequest(
        kind,
        {
            "body": cycle_request_body(
                policy.proposal_profile,
                squad_profile_id=policy.squad_profile,
                user_values=user_values,
                notes=f"campaign {campaign.campaign_id}: {kind} of {block.get('proposal_id')} "
                "(SIP-0109 §10a)",
            )
        },
    )
