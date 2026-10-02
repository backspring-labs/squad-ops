"""Campaign API DTOs (SIP-0109 §13, #1799).

The wire shapes of ``/api/v1/campaigns``. Every policy field is required: a limit is set from
its basis and recorded, never defaulted (the 2.0 plan's limits ruling). The actor and role of a
control operation are never fields here — they come from the caller's verified token.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CampaignObjectiveDTO(BaseModel):
    statement: str
    allowed_scope: list[str] = Field(default_factory=list)
    measurement: str


class CampaignPolicyDTO(BaseModel):
    max_cycles: int
    max_elapsed_s: int
    budget_tokens: int
    max_repair_cycles_per_increment: int
    max_retry_cycles_per_increment: int
    max_proposal_run_retries: int
    max_proposal_revisions: int
    max_rejected_proposals_in_row: int
    max_unaccepted_increments: int
    crew_ruling_bound_s: int
    owner_ruling_bound_s: int
    lease_expiry_s: int
    launch_blocked_interval_s: int
    launch_blocked_attempts: int
    calibration_profile: str
    proposal_profile: str
    squad_profile: str


class CampaignCreateRequest(BaseModel):
    """A new campaign, in ``draft``. Starting it (its calibration cycle) is a later operation."""

    project_id: str
    objective: CampaignObjectiveDTO
    policy: CampaignPolicyDTO
    reason: str
    #: The caller's retry key: the same key and content replays the creation.
    idempotency_key: str
    #: Optional: a caller that retries passes the id it minted, so a retry names the same campaign.
    campaign_id: str | None = None


class ControlRequest(BaseModel):
    """A control operation's caller-supplied part: why, under which key, and on which state."""

    reason: str
    idempotency_key: str
    #: The state the caller acted on; a campaign that has moved since refuses the operation.
    expected_state: str | None = None


class ResumeRequest(ControlRequest):
    """The owner's word (§10). A paused campaign resumes into its held action, or where it was;
    an escalated one resumes on the action named here: ``propose``, ``abandon_and_propose``,
    ``repair`` or ``retry`` (stopping it is ``abort``)."""

    action: str | None = None


class ClassificationRequest(ControlRequest):
    """The supervisor's classification of what went wrong with one proposal version (§9.4)."""

    proposal_id: str
    version: int
    classification: str


class AcceptedTreeDTO(BaseModel):
    identity: str
    cycle_id: str


class CampaignResponse(BaseModel):
    campaign_id: str
    project_id: str
    objective: CampaignObjectiveDTO
    policy: CampaignPolicyDTO
    state: str
    outcome: str | None
    created_at: datetime
    created_by: str
    updated_at: datetime
    #: The accepted tree every increment is proposed against; ``None`` until the calibration
    #: cycle's tree is promoted.
    accepted: AcceptedTreeDTO | None = None


class ControlLogEntryResponse(BaseModel):
    entry_id: str
    campaign_id: str
    seq: int
    operation: str
    actor: str
    actor_role: str
    reason: str
    target: str | None
    idempotency_key: str
    binding: dict[str, Any]
    outcome: str
    refusal: str | None
    prior_state: str | None
    next_state: str
    committed_at: datetime
    launch_id: str | None


class ControlResultResponse(BaseModel):
    """What an applied (or replayed) control operation left."""

    campaign: CampaignResponse
    entry: ControlLogEntryResponse
    replayed: bool
    #: Cycles the operation cancelled through the existing cancel path (an abort's).
    cancelled_cycles: list[str] = Field(default_factory=list)
    #: Cycles the operation's launch intent started (a start's calibration cycle, §12b).
    launched_cycles: list[str] = Field(default_factory=list)
