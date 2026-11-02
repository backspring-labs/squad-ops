"""
Pydantic DTOs for SIP-0064 cycle API request/response serialization.

Beside ``api/schemas.py`` rather than under ``api/routes/cycles/`` (#582): the contracts
layer reads ``CycleCreateRequest`` to validate request-profile defaults, and importing any
module of a routes package runs that package's ``__init__``, which imports every router and
therefore FastAPI (and python-multipart, at route registration). That chain made the
``squadops`` console script depend on the API framework it only ever talks to over HTTP.
A DTO is pydantic alone; it lives where nothing framework-shaped is executed to reach it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

# =============================================================================
# Nested DTOs
# =============================================================================


class GateDTO(BaseModel):
    # Nested in CycleCreateRequest, which forbids extras: a misspelt key here is refused too,
    # never dropped (SIP-0112 contract 2).
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    after_task_types: list[str] = Field(default_factory=list)


class TaskFlowPolicyDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["sequential", "fan_out_fan_in", "fan_out_soft_gates"] = "sequential"
    gates: list[GateDTO] = Field(default_factory=list)


# =============================================================================
# Request DTOs
# =============================================================================


class TaskInstructionDTO(BaseModel):
    """A task instruction given when a cycle is created (SIP-0110 Appendix A §3.5; #2178): binding,
    for the named task types of this cycle only."""

    text: str
    task_types: list[str]
    references: list[dict] = Field(default_factory=list)
    #: ``"continuations"``: it also reaches a campaign's repair or retry of this cycle (§3.7).
    carries_into: str | None = None

    model_config = ConfigDict(extra="forbid")


class SourcePreconditionDTO(BaseModel):
    """What a caller expects an external Project's source to be (SIP-0112 FR-09, §D.3). A
    Project that has moved past it is refused, never silently re-pinned."""

    model_config = ConfigDict(extra="forbid")

    development_baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    development_configuration_revision: int | None = Field(default=None, ge=1)


class CycleCreateRequest(BaseModel):
    """Create a new cycle + first run (T17: atomic)."""

    prd_ref: str | None = None
    squad_profile_id: str
    task_flow_policy: TaskFlowPolicyDTO = Field(default_factory=lambda: TaskFlowPolicyDTO())
    build_strategy: Literal["fresh", "incremental"] = "fresh"  # T13
    applied_defaults: dict = Field(default_factory=dict)  # SIP-0065 D2: CRP defaults from CLI
    execution_overrides: dict = Field(default_factory=dict)
    expected_artifact_types: list[str] = Field(default_factory=list)
    experiment_context: dict = Field(default_factory=dict)
    request_profile: str | None = None  # SIP-0096: cycle-level config provenance (CRP name)
    notes: str | None = None
    #: #2178: directives for this cycle's selected tasks, stored as task instructions with it.
    task_instructions: list[TaskInstructionDTO] = Field(default_factory=list)
    # SIP-0112 §D.3 (E.4.3): an external Project's expected source; absent, the current one.
    source_precondition: SourcePreconditionDTO | None = None

    model_config = ConfigDict(extra="forbid")


class ProposalBindingDTO(BaseModel):
    """What an increment ruling binds to (SIP-0109 §9.2)."""

    proposal_id: str
    version: int
    content_hash: str
    baseline_tree: str

    model_config = ConfigDict(extra="forbid")


class ProposalRatingRequest(BaseModel):
    """The supervisor's rating of a proposal nothing builds (SIP-0109 §11a; §24af): bound to the
    change request's ``content_hash``, the verdict the ruling would have been, its reason, and
    ``ratings`` keyed by dimension, each ``{"score": 1-3, "note": ...}``."""

    content_hash: str
    verdict: str
    reason: str
    ratings: dict[str, dict] = Field(default_factory=dict)


class ProposalRatingResponse(BaseModel):
    artifact_id: str
    proposal_id: str
    version: int
    verdict: str


class GateDecisionRequest(BaseModel):
    """Gate decision (T4+T13: normalized vocab, typed).

    ``waived_checks``/``waiver_reason`` (SIP-0096 §6.5, #682): explicit
    accept-with-waiver — validated against the run's unverified disclosure.
    """

    decision: Literal[
        "approved",
        "approved_with_refinements",
        "returned_for_revision",
        "rejected",
    ]
    notes: str | None = None
    #: #812: who is deciding, when the token cannot say. An agent authenticating as a
    #: person is invisible to the token, so declaring is the only way the record can be
    #: true. Omitted → the identity's own type is used; never inferred from behavior.
    decided_by_kind: Literal["human", "agent"] | None = None
    waived_checks: list[str] = Field(default_factory=list)
    waiver_reason: str | None = None
    #: SIP-0109 §9.2, the increment gate only: the proposal and accepted tree the ruling is made
    #: on, and the caller's retry key. Required there, refused elsewhere.
    binding: ProposalBindingDTO | None = None
    idempotency_key: str | None = None
    #: SIP-0109 §24bi, the increment gate only: a return's classification (§9.4's class, or
    #: ``unclassified``) and, with ``unclassified``, the rationale. Refused elsewhere.
    classification: str | None = None
    classification_rationale: str | None = None
    #: SIP-0110 Appendix A §3.5 (#2178), the increment gate's approval only: task instructions for
    #: the ruled cycle's framing and build, beside the free notes, which reach no prompt. Refused
    #: elsewhere, and for a task that has dispatched.
    task_instructions: list[TaskInstructionDTO] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SetActiveProfileRequest(BaseModel):
    profile_id: str

    model_config = ConfigDict(extra="forbid")


class AgentProfileEntryRequest(BaseModel):
    """Agent entry in a profile create/update request (SIP-0075)."""

    agent_id: str
    role: str
    model: str
    enabled: bool = True
    config_overrides: dict = Field(default_factory=dict)
    #: The step roles this agent serves (SIP-0108 §10i item 1) — declared, never inferred.
    #: ``role`` is what the agent IS; this is what it DOES in this profile. An enabled agent
    #: that serves only its own role declares ``[<role>]``; a disabled one may declare none.
    serves_roles: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ProfileCreateRequest(BaseModel):
    """Create a new squad profile (SIP-0075)."""

    name: str
    description: str = ""
    agents: list[AgentProfileEntryRequest]

    model_config = ConfigDict(extra="forbid")


class ProfileUpdateRequest(BaseModel):
    """Update an existing squad profile (SIP-0075)."""

    name: str | None = None
    description: str | None = None
    agents: list[AgentProfileEntryRequest] | None = None

    model_config = ConfigDict(extra="forbid")


class ProfileCloneRequest(BaseModel):
    """Clone a squad profile with a new name (SIP-0075)."""

    name: str

    model_config = ConfigDict(extra="forbid")


class BaselinePromoteRequest(BaseModel):
    artifact_id: str

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Response DTOs
# =============================================================================


class ProjectOriginRequest(BaseModel):
    """How the Project's source comes to exist (SIP-0112 D.2). E.4.1 registers an existing
    repository; ``new`` (greenfield, E.4.6) and ``attach`` (in place, E.4.7) come later."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["import"]


class ProjectSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_uri: str = Field(min_length=1, max_length=2000)
    base_ref: str = Field(min_length=1, max_length=255)
    contribution_mode: Literal["review_request", "patch_export", "direct_push"]
    repository_root: str = "."


class ProjectOwnershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1, max_length=200)
    delegated_actions: list[
        Literal["engineering_decisions", "candidate_acceptance", "contribution", "integration"]
    ] = Field(default_factory=list)
    acceptance_policy_ref: str | None = None


class ProjectRegistrationRequest(BaseModel):
    """Register an existing product (SIP-0112 FR-02, E.4.1): ``POST /api/v1/projects``."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    origin: ProjectOriginRequest
    source: ProjectSourceRequest
    ownership: ProjectOwnershipRequest


class ProjectSourceResponse(BaseModel):
    """The external source binding (SIP-0112 §B.5): the authoritative locator and its refs."""

    repo_uri: str
    base_ref: str
    contribution_mode: str
    repository_root: str


class ProjectOwnershipResponse(BaseModel):
    """The external product's authority (SIP-0112 §B.5.1)."""

    owner: str
    delegated_actions: list[str]
    acceptance_policy_ref: str | None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: str
    created_at: datetime
    tags: list[str]
    has_prd: bool = False
    # SIP-0112's Project Record (E.4.1): added fields only, so a client reading the six above is
    # unchanged (D.6). A sample application reads READY at version 1 with no source or owner.
    lifecycle_status: str
    record_version: int
    source: ProjectSourceResponse | None
    ownership: ProjectOwnershipResponse | None
    development_configuration_revision: int | None
    development_baseline_commit: str | None
    integrated_upstream_commit: str | None
    validation_diagnostic: str | None


class ProjectValidationRequest(BaseModel):
    """Validate a registered Project (SIP-0112 E.4.2): reach its source, record what was found."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    #: The owner's own forge token, for a private repository's fetch in this one act: never
    #: stored, logged or returned. Absent, the deploy's token for the Project is used, if any.
    token: SecretStr | None = Field(default=None, min_length=1, max_length=512)


class DevelopmentConfigurationRequest(BaseModel):
    """Record a Project's next Development Configuration revision (SIP-0112 §B.5, E.4.2).
    ``expected_revision`` is the current one (0 for the first), so a concurrent recording is
    refused rather than silently superseded (§D.2's version precondition)."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)
    technical: dict[str, Any]
    quality: dict[str, Any] | None = None


class DevelopmentConfigurationResponse(BaseModel):
    """One revision, as it is stored and read: the document is contract 7's carrier."""

    project_id: str
    revision: int
    document: dict[str, Any]


class DevelopmentConfigurationRecordedResponse(BaseModel):
    configuration: DevelopmentConfigurationResponse
    idempotency_key: str
    replayed: bool


class InheritedBaselineRequest(BaseModel):
    """Capture a Project's inherited baseline (SIP-0112 FR-20, E.4.2)."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)


class SourceFileResponse(BaseModel):
    """A file of a registered product, read from the managed clone at the Project's integrated
    commit: the commit a Campaign's ``repo:file:<path>@current`` requirements resolve to (#2855)."""

    project_id: str
    path: str
    commit: str
    content: str


class InheritedBaselineResponse(BaseModel):
    """The baseline, as the shared fixture records it, and whether this replayed a capture."""

    project_id: str
    document: dict[str, Any]
    replayed: bool = False
    #: The profile derived at the Project's latest capture (SIP-0112 H.4, contract 8), or ``None``
    #: when that capture predates profiles.
    derived_profile: dict[str, Any] | None = None


class DerivedProfileResponse(BaseModel):
    """The derived development profile, as contract 8 records it (SIP-0112 H.6)."""

    project_id: str
    document: dict[str, Any]


class ContributionRequest(BaseModel):
    """Contribute a run's verified change through the Project's own process (SIP-0112 FR-06)."""

    model_config = ConfigDict(extra="forbid")

    cycle_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)
    #: The contributor's own forge token, for this one act: used in memory for the push and the
    #: review request, never stored, logged or returned. Absent, the deploy's token for the
    #: Project is used (`projects.review_request_tokens`).
    token: SecretStr | None = Field(default=None, min_length=1, max_length=512)


class ContributionResponse(BaseModel):
    """A contribution, pending until the product takes it, and whether this replayed one."""

    contribution: dict[str, Any]
    replayed: bool = False


class InitializationRequest(BaseModel):
    """Make a greenfield Project's first commit from an approved interface manifest (SIP-0112
    FR-01, E.4.6)."""

    model_config = ConfigDict(extra="forbid")

    #: The approved interface manifest, as YAML: the structure the blueprint's layout is
    #: rendered from, kept as submitted.
    manifest: str = Field(min_length=1, max_length=200_000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    #: The owner's own forge token, for this one act: used in memory for the push, never stored,
    #: logged or returned. Absent, the deploy's token for the Project is used.
    token: SecretStr | None = Field(default=None, min_length=1, max_length=512)


class InitializationResponse(BaseModel):
    """A greenfield Project's initialization, and whether this replayed one."""

    initialization: dict[str, Any]
    replayed: bool = False


class SourceSyncRequest(BaseModel):
    """Read a Project's upstream against its approved baseline (SIP-0112 FR-21, E.4.4)."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    #: The caller's own forge token, to read its review requests' state for this sync only.
    token: SecretStr | None = Field(default=None, min_length=1, max_length=512)


class SourceSyncResponse(BaseModel):
    """A sync's record: the drift by category and each contribution's standing."""

    document: dict[str, Any]
    replayed: bool = False


class ProjectRegistrationResponse(BaseModel):
    """A registration, applied or replayed: the Project, and the key a retry resends (D.6)."""

    project: ProjectResponse
    idempotency_key: str
    replayed: bool


class GateDecisionResponse(BaseModel):
    gate_name: str
    decision: str
    decided_by: str
    decided_at: datetime
    notes: str | None = None
    waived_checks: list[str] = Field(default_factory=list)  # SIP-0096 §6.5 (#682)
    waiver_reason: str | None = None


class UnresolvedRecordResponse(BaseModel):
    """One record a binding hold couldn't bind (SIP-0110 §A.3.6, #2178)."""

    ref: str
    reason: str
    #: ``store``: the store didn't answer. ``input``: an operator's input can't be bound.
    kind: str


class BindingHoldResponse(BaseModel):
    """A run held on a task's binding sections, and its release (SIP-0110 §5ag, #2178)."""

    hold_id: str
    task_id: str
    task_type: str
    unresolved: list[UnresolvedRecordResponse]
    sections: list[str]
    held_at: datetime
    released_at: datetime | None = None
    cause: str | None = None


class RunHaltResponse(BaseModel):
    """A run halted by a task instruction's emergency withdrawal (SIP-0110 §A.3.8, T13; #2178)."""

    record_id: str
    requested_by: str
    why: str
    requested_at: datetime
    #: The task its restart runs again from; ``None``: nothing in it restarts.
    restart_from_task_id: str | None = None
    #: The run its cycle restarted it as, once it has.
    restart_run_id: str | None = None


class RunResponse(BaseModel):
    run_id: str
    cycle_id: str
    run_number: int
    status: str
    initiated_by: str
    resolved_config_hash: str
    resolved_config_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_decisions: list[GateDecisionResponse] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    workload_type: str | None = None
    failure_reason: str | None = None
    #: #2178: each time the run was held on a task's bindings, oldest first.
    binding_holds: list[BindingHoldResponse] = Field(default_factory=list)
    #: #2178 (T13): the emergency withdrawal that halted it, if one did.
    halt: RunHaltResponse | None = None


class WorkloadProgressEntry(BaseModel):
    """Per-workload status in a multi-workload cycle (SIP-0083 §5.8)."""

    index: int
    workload_type: str
    run_id: str | None = None
    status: str  # "pending" | "running" | "completed" | "failed" | "gate_awaiting" | "rejected"


class UnverifiedCheckDTO(BaseModel):
    """A not-executed check disclosed in the cycle roll-up (SIP-0096 §6.6.3)."""

    check_id: str
    reason: str
    required: bool


class WaivedCheckDTO(BaseModel):
    """SIP-0096 §6.5: an operator waiver recorded above the evidence (#682)."""

    check_id: str
    reason: str
    waived_by: str | None = None


class ReplayProvenanceDTO(BaseModel):
    """SIP-0101 §4.1: the prefix of this outcome was restored from another run's
    checkpoint — inherited evidence, never presentable as earned."""

    source_run_id: str
    boundary_index: int
    compatibility_set: list[str] = Field(default_factory=list)


class CycleOutcomeDTO(BaseModel):
    """SIP-0096 §10 per-cycle verification roll-up, derived on read.

    `verdict` is the worst-of-runs verification verdict — **not** a cycle status
    (§6.5). `blocked_unverified` is a harness/evidence problem, not a product
    failure. Not-executed checks are always disclosed in `unverified`.
    """

    verdict: str  # accepted | rejected | blocked_unverified
    verified: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    unverified: list[UnverifiedCheckDTO] = Field(default_factory=list)
    required_unmet: list[str] = Field(default_factory=list)
    run_count: int = 0
    inert: list[str] = Field(default_factory=list)  # §9 chronic not-executed (#684)
    waived: list[WaivedCheckDTO] = Field(default_factory=list)  # §6.5 (#682)
    replay: ReplayProvenanceDTO | None = None  # SIP-0101 — present iff replayed


class CycleResponse(BaseModel):
    cycle_id: str
    project_id: str
    created_at: datetime
    created_by: str
    prd_ref: str | None = None
    squad_profile_id: str
    squad_profile_snapshot_ref: str
    task_flow_policy: TaskFlowPolicyDTO
    build_strategy: str
    applied_defaults: dict = Field(default_factory=dict)
    execution_overrides: dict = Field(default_factory=dict)
    expected_artifact_types: list[str] = Field(default_factory=list)
    experiment_context: dict = Field(default_factory=dict)
    # Lineage (#80): which configuration and which code created the cycle. None on a cycle
    # created before the field existed.
    request_profile: str | None = None
    framework_version: str | None = None
    framework_git_sha: str | None = None
    #: #1720: the deploy record the cycle was created on; None when no deploy had been recorded.
    deploy_id: str | None = None
    # SIP-0109 §19: a cycle's campaign and why it was launched; null on a cycle no campaign
    # launched, which is otherwise unchanged.
    campaign_id: str | None = None
    kind: str | None = None
    #: #2578 part 2: the increment the cycle belongs to (its proposal's id); null otherwise.
    increment_id: str | None = None
    # SIP-0112 contract 1 (E.4.3): the external source this Cycle pinned; None for a sample app.
    source_context: dict[str, Any] | None = None
    notes: str | None = None
    status: str  # Derived CycleStatus
    runs: list[RunResponse] = Field(default_factory=list)
    workload_progress: list[WorkloadProgressEntry] = Field(default_factory=list)
    cycle_outcome: CycleOutcomeDTO | None = None  # SIP-0096 §10, derived on the detail GET


class PreflightWarningDTO(BaseModel):
    """A non-blocking create-time preflight warning (SIP-0095 §7).

    `code` is a stable machine label (e.g. `model_unverifiable`); `message` is the
    actionable operator text. The cycle was created despite the warning (warn-and-allow).
    """

    code: str
    message: str


class CycleCreateResponse(BaseModel):
    """Response for cycle creation — includes first run_id."""

    cycle_id: str
    project_id: str
    run_id: str
    run_number: int
    status: str
    prd_ref: str | None = None
    squad_profile_id: str
    squad_profile_snapshot_ref: str
    task_flow_policy: TaskFlowPolicyDTO
    resolved_config_hash: str
    # SIP-0095 Phase 4: non-blocking preflight warnings surfaced to the operator.
    warnings: list[PreflightWarningDTO] = Field(default_factory=list)
    # SIP-0112 §D.3: the external source the server pinned, stated or implicit.
    source_context: dict[str, Any] | None = None


class EvidenceRefDTO(BaseModel):
    """One evidence reference an indicator read (SIP-0108 §3.3)."""

    kind: str
    id: str


class IndicatorDTO(BaseModel):
    """One indicator in the three-state vocabulary (#1445)."""

    name: str
    state: str
    value: Any = None
    reason: str | None = None
    refs: list[EvidenceRefDTO] = Field(default_factory=list)


class ContributionDTO(BaseModel):
    """One contributing disposition, citing the fact it came from (SIP-0108 §4.2)."""

    attribution: str
    source: str
    run_id: str
    task_id: str
    round_index: int | None = None
    check_id: str | None = None
    value: str


class AttributionReadingDTO(BaseModel):
    """The attribution, its state, and what the stores did not hold for it."""

    state: str
    primary: str | None = None
    contributing: list[ContributionDTO] = Field(default_factory=list)
    terminal_kind: str | None = None
    registry_version: int | None = None
    reason: str | None = None
    unrecorded: list[str] = Field(default_factory=list)
    refs: list[EvidenceRefDTO] = Field(default_factory=list)


class CycleAssessmentResponse(BaseModel):
    """A cycle's assessment, computed on read (SIP-0108 §4.1 (a)).

    Four dimensions of three-state indicators, the attribution, and the identity of what
    produced them. Nothing here is stored: the assessment is a projection over the durable
    record, recomputed each time it is asked for.
    """

    cycle_id: str
    outcome: list[IndicatorDTO]
    quality: list[IndicatorDTO]
    coordination: list[IndicatorDTO]
    efficiency: list[IndicatorDTO]
    attribution: AttributionReadingDTO
    assessment_version: int
    attribution_registry_version: int
    evidence_identity: str
    assessor_framework_version: str
    assessor_git_sha: str | None = None


class AgentProfileEntryResponse(BaseModel):
    agent_id: str
    role: str
    role_label: str | None = None
    display_name: str | None = None
    model: str
    enabled: bool
    config_overrides: dict = Field(default_factory=dict)
    #: The declared role → agent map (SIP-0108 §10i item 1). On the wire because it is
    #: execution-determining and part of the profile's snapshot identity: the verification
    #: driver rebuilds a profile from this response and recomputes that identity before it
    #: will launch a counting roll, so a reader that omits the field computes a different
    #: hash from the runtime and every roll refuses to start.
    serves_roles: list[str] = Field(default_factory=list)


class SquadProfileResponse(BaseModel):
    profile_id: str
    name: str
    description: str
    version: int
    agents: list[AgentProfileEntryResponse]
    created_at: datetime
    is_active: bool = False
    updated_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class ArtifactRefResponse(BaseModel):
    artifact_id: str
    project_id: str
    cycle_id: str | None = None
    run_id: str | None = None
    artifact_type: str
    filename: str
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime
    metadata: dict = Field(default_factory=dict)
    vault_uri: str | None = None
    promotion_status: str = "working"

    # Prompt provenance (SIP-0084 §10)
    system_prompt_bundle_hash: str | None = None
    system_fragment_ids: tuple[str, ...] | None = None
    system_fragment_versions: tuple[str, ...] | None = None
    request_template_id: str | None = None
    request_template_version: str | None = None
    request_render_hash: str | None = None
    capability_supplement_ids: tuple[str, ...] | None = None
    full_invocation_bundle_hash: str | None = None
    prompt_environment: str | None = None


class PromptMetaResponse(BaseModel):
    """Prompt field metadata for cycle request profile (SIP-0074 §5.8)."""

    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)
    type: str | None = None
    required: bool = False


class CycleRequestResolveRequest(BaseModel):
    """A request profile's name resolved into a cycle-create body, server-side (#2520): the squad,
    the caller's values over the profile's, and the notes and PRD the body carries."""

    squad_profile_id: str
    values: dict = Field(default_factory=dict)
    notes: str | None = None
    prd_ref: str | None = None

    model_config = ConfigDict(extra="forbid")


class CycleRequestProfileResponse(BaseModel):
    """Cycle request profile with defaults and prompt metadata (SIP-0074)."""

    name: str
    description: str = ""
    defaults: dict = Field(default_factory=dict)
    prompts: dict[str, PromptMetaResponse] = Field(default_factory=dict)
    #: The stacks an operator profile runs on, each adding its request defaults beneath the
    #: profile's (#316, R2.3), so a client offers the choice the CLI's ``--set build_profile``
    #: makes (#2520). Empty for every other profile: it pins its stack or takes none.
    stacks: list[str] = Field(default_factory=list)


class ModelSpecResponse(BaseModel):
    """Model registry entry (SIP-0074, SIP-0073)."""

    name: str
    context_window: int
    default_max_completion: int


class PulledModelResponse(BaseModel):
    """A locally pulled model with active profile cross-reference (SIP-0075)."""

    name: str
    size_bytes: int | None = None
    modified_at: str | None = None
    in_active_profile: bool = False
    used_by_active_profile: list[str] = Field(default_factory=list)
    registry_spec: ModelSpecResponse | None = None


class PullModelRequest(BaseModel):
    """Request to pull a model from Ollama registry (SIP-0075)."""

    name: str

    model_config = ConfigDict(extra="forbid")


class PullStatusResponse(BaseModel):
    """Status of an in-progress model pull (SIP-0075)."""

    pull_id: str
    model_name: str
    status: str
    error: str | None = None


class RunResumeRequest(BaseModel):
    """Resume a paused or failed run (SIP-0079)."""

    resume_reason: str | None = None

    model_config = ConfigDict(extra="forbid")


class CheckpointSummaryResponse(BaseModel):
    """Checkpoint summary for list endpoint (SIP-0079)."""

    checkpoint_index: int
    completed_task_count: int
    artifact_ref_count: int
    created_at: datetime


class CancellationResponse(BaseModel):
    """What a cancel tore down, since it bypasses the executor's finalize path: the Prefect flow
    runs (#77), the focus leases (#529) and the open activities (#561), with the agents told
    first (#1648)."""

    status: Literal["cancelled"]
    prefect_flow_runs_cancelled: int
    focus_leases_released: int
    activities_ended: int
    agents_notified: int


class RunCancelResponse(CancellationResponse):
    run_id: str


class CycleCancelResponse(CancellationResponse):
    cycle_id: str


class BaselinePromotedResponse(BaseModel):
    status: Literal["ok"]
    project_id: str
    artifact_type: str


class ActiveProfileSetResponse(BaseModel):
    status: Literal["ok"]
    active_profile_id: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
