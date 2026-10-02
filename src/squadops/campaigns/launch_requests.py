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


def increment_launch(campaign: Campaign, baseline_manifest: str) -> LaunchRequest:
    """An increment cycle (§7.3): the policy's proposal profile, run by its squad, proposing
    against the accepted tree. The ``campaign_proposal`` block carries what the proposal run
    reads — the accepted tree's identity and its manifest's text (the agent has no vault, #1821),
    the objective — and the campaign's revision budget, which the increment gate spends (§9.5)."""
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
                        "prior_criteria": [],
                        "max_revisions": policy.max_proposal_revisions,
                    }
                },
                notes=f"campaign {campaign.campaign_id}: increment (SIP-0109 §7.3)",
            )
        },
    )
