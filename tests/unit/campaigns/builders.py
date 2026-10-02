"""Builders shared by the campaign tests (SIP-0109), and by part B's Postgres tests."""

from __future__ import annotations

from datetime import UTC, datetime

from squadops.campaigns.models import (
    Campaign,
    CampaignObjective,
    CampaignPolicy,
    CampaignState,
    CampaignTransition,
    ControlOperation,
)

T0 = datetime(2026, 10, 2, 3, 0, tzinfo=UTC)


def policy(**overrides) -> CampaignPolicy:
    values = dict(
        max_cycles=6,
        max_elapsed_s=12 * 3600,
        budget_tokens=2_000_000,
        max_repair_cycles_per_increment=1,
        max_retry_cycles_per_increment=1,
        max_proposal_run_retries=1,
        max_proposal_revisions=2,
        max_rejected_proposals_in_row=2,
        max_unaccepted_increments=2,
        crew_ruling_bound_s=1800,
        owner_ruling_bound_s=12 * 3600,
        lease_expiry_s=3600,
        launch_blocked_interval_s=300,
        launch_blocked_attempts=6,
        calibration_profile="group-run-react",
        proposal_profile="group-run-proposal",
    )
    values.update(overrides)
    return CampaignPolicy(**values)


def campaign(campaign_id: str = "cmp_aaaaaaaaaaaa", **overrides) -> Campaign:
    values = dict(
        campaign_id=campaign_id,
        project_id="group_run",
        objective=CampaignObjective(
            statement="evolve group_run toward its PRD's expansion scope",
            allowed_scope=("backend", "frontend"),
            measurement="two accepted increments",
        ),
        policy=policy(),
        state=CampaignState.DRAFT,
        created_at=T0,
        created_by="owner",
        updated_at=T0,
    )
    values.update(overrides)
    return Campaign(**values)


def move(
    to: CampaignState,
    key: str,
    *,
    operation: ControlOperation = ControlOperation.DECIDE,
    **overrides,
) -> CampaignTransition:
    values = dict(
        operation=operation,
        actor="squadops",
        actor_role="system",
        reason=f"to {to}",
        idempotency_key=key,
        next_state=to,
    )
    values.update(overrides)
    return CampaignTransition(**values)
