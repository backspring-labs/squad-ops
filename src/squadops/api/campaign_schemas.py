"""Campaign API DTOs (SIP-0109 §13, #1799).

The wire shapes of ``/api/v1/campaigns``. Every policy field is required: a limit is set from
its basis and recorded, never defaulted (the 2.0 plan's limits ruling). The actor and role of a
control operation are never fields here — they come from the caller's verified token.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from squadops.campaigns.models import PlanGate


class WorkClassDTO(BaseModel):
    """SIP-0113 §4.6 (the owner's ruling of 2026-10-18): the class the campaign's work belongs
    to, declared, never inferred. With the target (the increment count), what AOR groups by."""

    model_config = ConfigDict(extra="forbid")

    prd_tier: Literal["core", "tier-1", "tier-2", "tier-3"]
    attendance: Literal["attended", "unattended"]


class CampaignObjectiveDTO(BaseModel):
    statement: str
    allowed_scope: list[str] = Field(default_factory=list)
    measurement: str
    #: §24ah: the accepted increments that meet the objective, read by §10 row 3. Required of a
    #: new campaign; ``None`` reads back only for one stored before the field existed.
    target_accepted_increments: int | None
    #: SIP-0113 §4.6: required of a new campaign, as the target is; ``None`` reads back only for
    #: one stored before the field existed.
    work_class: WorkClassDTO | None = None
    #: SIP-0109 §24bv point 5 (D10 point 3): a repository-backed Project's requirements source,
    #: ``repo:file:<path>@current`` or a stored artifact's id. Required at creation for one, and
    #: refused for a sample application.
    requirements: str | None = None


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
    ruling_bound_s: int
    lease_expiry_s: int
    launch_blocked_interval_s: int
    launch_blocked_attempts: int
    calibration_profile: str
    proposal_profile: str
    squad_profile: str
    #: §24bj: required, so a definition that does not declare it is refused at creation.
    plan_gate: PlanGate
    #: §24bs (#2443): the stack every cycle the campaign launches builds on. Omitted, it is the
    #: campaign profiles' own.
    stack: str | None = None


class CampaignDefinitionDTO(BaseModel):
    """The file a campaign is created from (#1954): its path as given, and its bytes' sha256."""

    path: str
    sha256: str


class CampaignCreateRequest(BaseModel):
    """A new campaign, in ``draft``. Starting it (its calibration cycle) is a later operation."""

    #: Contract 2: an unknown field is refused, so a misspelled ``scenario_suit`` is not a
    #: campaign created with no suite pinned (#2448's review).
    model_config = ConfigDict(extra="forbid")

    project_id: str
    objective: CampaignObjectiveDTO
    policy: CampaignPolicyDTO
    reason: str
    #: The caller's retry key: the same key and content replays the creation.
    idempotency_key: str
    #: Optional: a caller that retries passes the id it minted, so a retry names the same campaign.
    campaign_id: str | None = None
    #: Optional (#1954): the definition file, recorded on the creation row. ``campaigns create
    #: --file`` always sends it; a caller with no file sends none.
    definition: CampaignDefinitionDTO | None = None
    #: SIP-0113 §4.7, phase 1 (#2413; SIP-0109 §24bt): the digest of an approved held-out scenario
    #: suite, pinned on the campaign in Outcome Evaluation's own record. No SIP-0109 decision reads
    #: it. Optional: a campaign created without one is evaluated by no suite.
    scenario_suite: str | None = None


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


class LeaseRequest(ControlRequest):
    """The supervisor takes the box at the increment gate (§9.3; #1802). ``expires_in_s`` is
    how long it holds it, at most the campaign policy's ``lease_expiry_s``: a supervisor that
    crashes cannot hold the box forever. Asking again before it expires renews it."""

    expires_in_s: int = Field(gt=0)


class LeaseResponse(BaseModel):
    """The box's lease: who holds it, for which campaign, until when."""

    holder: str
    held_by: str
    campaign_id: str | None
    acquired_at: datetime
    expires_at: datetime | None
    #: Whether the supervisor holds the box now (a supervisor's lease past its expiry does not).
    supervisor_holds: bool


class LeaseResultResponse(BaseModel):
    """An applied (or replayed) lease change: its control-log row and the lease it left."""

    entry: ControlLogEntryResponse
    replayed: bool
    lease: LeaseResponse


class ClassificationRequest(ControlRequest):
    """The supervisor's classification of what went wrong with one proposal version (§9.4)."""

    proposal_id: str
    version: int
    classification: str


class EscalationAnswerRequest(BaseModel):
    """A late answer to an expired or cancelled escalation (SIP-0109 §24bj, §24bm): one answer per
    decision it answers, by the decision's id, never one text for several. One record per
    escalation: its key is the escalation's own, so a retry of the same answers replays it and
    different ones are refused."""

    answers: dict[str, str] = Field(min_length=1)
    reason: str
    #: Who answered, as a gate decision records it (#812, #2305): an agent answering with a
    #: person's credentials is invisible to the token, so it says so. Omitted, the token's own
    #: identity type is recorded.
    answered_by_kind: Literal["human", "agent"] | None = None


class EscalationResponse(BaseModel):
    """One escalation, as the control log holds it (§24bj, §24bk): a plan gate the tier couldn't
    approve, or a cycle held on its instruction bindings (§24bw), whose unresolved records stand
    in ``failed`` (the reference as ``condition``, its reason as ``reading``)."""

    escalation_id: str
    cycle_id: str
    run_id: str
    gate_name: str
    state: str
    opened_at: datetime
    failed: list[dict[str, str]]
    questions: list[str]
    decision_ids: list[str]
    closed_by: str | None
    closed_at: datetime | None
    answers: dict[str, str]
    answered_by: str | None
    answered_at: datetime | None
    #: §24bw: ``plan_review`` or ``binding_hold``, and a hold's cause class (``store``, ``input``).
    kind: str = "plan_review"
    hold_class: str | None = None


class AcceptedTreeDTO(BaseModel):
    """The accepted tree's identity and the one thing it names (§24cc): the cycle whose candidate
    it is, or, on a repository-backed Project, the calibration record whose commit it is. On such
    a Project, ``commit`` is the head of the campaign's branch (§24bv point 2)."""

    identity: str
    cycle_id: str | None = None
    calibration_record_id: str | None = None
    commit: str | None = None


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


class LedgerEntryResponse(BaseModel):
    """One proposal version in the ledger (§9.4): its submission, then its ruling, its cycle's
    outcome and its classification as each is recorded."""

    proposal_id: str
    version: int
    content_hash: str
    baseline_tree: str
    cycle_id: str
    run_id: str
    submitted_at: str
    ruling: dict[str, Any] | None = None
    outcome: dict[str, Any] | None = None
    classification: dict[str, Any] | None = None
    #: #2578 part 4: each cycle that carried the version, in launch order, with its deciding row.
    cycles: list[dict[str, Any]] = Field(default_factory=list)


class PackageMaterializedResponse(BaseModel):
    """The evidence package and digest a materialization stored (§14, #1710)."""

    identity: str
    package_artifact_id: str
    digest_artifact_id: str


class PackageDigestResponse(BaseModel):
    """The latest stored evidence package's identity and its digest's text."""

    identity: str | None
    digest_artifact_id: str
    digest: str


class ReviewPushRequest(BaseModel):
    """Push the Campaign's review request (SIP-0109 §24ci (b)): the supervisor's act, with the
    supervisor's own forge token for it."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    #: The supervisor's own forge token, for this one push: used in memory, never stored, logged or
    #: returned. Required: nothing in the deploy is stored for a Campaign's push.
    token: SecretStr = Field(min_length=1, max_length=512)


class ReviewPushResponse(BaseModel):
    """One push of the Campaign's review request, as its row records it."""

    campaign_id: str
    branch: str
    commit: str
    #: The commit the push was leased on: the last one pushed, or ``None`` for the first.
    lease: str | None
    #: Whether the push rewrote the branch: a rebase's head, after the commit last pushed.
    forced: bool
    review_url: str
    entry_id: str
    replayed: bool


class ControlResultResponse(BaseModel):
    """What an applied (or replayed) control operation left."""

    campaign: CampaignResponse
    entry: ControlLogEntryResponse
    replayed: bool
    #: Cycles the operation cancelled through the existing cancel path (an abort's).
    cancelled_cycles: list[str] = Field(default_factory=list)
    #: Cycles the operation's launch intent started (a start's calibration cycle, §12b).
    launched_cycles: list[str] = Field(default_factory=list)
    #: #2621: the row of the launch this operation's own drain refused, which escalated the
    #: campaign. ``campaign`` is read after that drain, so it reads escalated with it. ``None``
    #: when nothing was refused.
    refused_launch: ControlLogEntryResponse | None = None
