"""Request and response bodies for Cross-Cycle Memory's lesson routes (SIP-0110 §0.6, slice 3d;
responses #1976)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApplicabilityDTO(BaseModel):
    """Where a lesson applies; the project is the route's. Every field names what it covers."""

    task_types: list[str] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    stacks: list[str] = Field(min_length=1)
    model_families: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class LessonDraftRequest(BaseModel):
    """The auditor's draft (D15): a revision of the target behavior's pattern."""

    target_behavior: str
    text: str
    applicability: ApplicabilityDTO
    template_id: str
    template_version: str
    drafter_model: str
    drafter_version: str
    cited_observations: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class ReplayCheckDTO(BaseModel):
    reference: str
    result: str

    model_config = ConfigDict(extra="forbid")


class CombinedCheckDTO(BaseModel):
    """The auditor's check of the draft with every approved lesson supplied beside it (§0.6)."""

    revision_ids: list[str]
    verdict: Literal["no_conflict", "conflict"]
    reference: str

    model_config = ConfigDict(extra="forbid")


class LessonApprovalRequest(BaseModel):
    """The owner's approval. ``applicability`` defaults to the revision's own, and may narrow it."""

    ruling: str
    replay_check: ReplayCheckDTO
    combined_check: CombinedCheckDTO
    applicability: ApplicabilityDTO | None = None

    model_config = ConfigDict(extra="forbid")


class RevocationRequest(BaseModel):
    reason: str

    model_config = ConfigDict(extra="forbid")


class AssessmentRequest(BaseModel):
    """One target's state in an exposure's authored output (SIP-0110 §0.10)."""

    pattern_id: str
    state: Literal["present", "absent", "not_applicable", "unassessed"]
    #: Whether the output did its required work; an absence requires it.
    required_work_done: bool | None = None
    rubric: str
    evidence: str

    model_config = ConfigDict(extra="forbid")


class AnnotationRequest(BaseModel):
    """A proposed classification of an observation classified only in prose (SIP-0110 §0.4, #2160).
    It classifies nothing until the owner reviews it."""

    values: list[str] = Field(min_length=1)
    target_behavior: str | None = None
    rationale: str | None = None
    #: The ruling's own words and the elements that settle the classification.
    evidence: dict[str, Any] = Field(min_length=1)
    #: The case's original context: at least ``deploy`` and ``prompt``.
    context: dict[str, Any]
    #: Who drafted it: a model and its version, or a person.
    annotator: str

    model_config = ConfigDict(extra="forbid")


class AnnotationReviewRequest(BaseModel):
    note: str = ""

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Responses (#1976). Each mirrors its record's ``to_dict()``, so OpenAPI shows what the route
# promises. ``extra="allow"`` passes on a field a record gains before its model does, so a client
# never loses one silently; ``test_memory_response_models.py`` holds each model to its record.
# Timestamps are the records' ISO strings.
# =============================================================================


class _Record(BaseModel):
    model_config = ConfigDict(extra="allow")


class ApplicabilityResponse(_Record):
    project_id: str
    task_types: list[str]
    roles: list[str]
    stacks: list[str]
    model_families: list[str]


class ApprovalResponse(_Record):
    approval_id: str
    revision_id: str
    applicability: ApplicabilityResponse
    approved_by: str
    approved_at: str
    replay_check: dict[str, Any]
    revoked_at: str | None
    ruling: str
    combined_check: dict[str, Any]
    revoked_by: str | None
    revocation_reason: str | None


class LessonResponse(_Record):
    """One revision of a lesson, with its approvals (revoked ones included)."""

    revision_id: str
    pattern_id: str
    revision: int
    target_behavior: str
    text: str
    applicability: ApplicabilityResponse
    template_id: str
    template_version: str
    drafter_model: str
    drafter_version: str
    cited_observations: list[str]
    created_at: str
    approvals: list[ApprovalResponse]


class SuppliedTogetherResponse(BaseModel):
    revision_id: str
    revision_ids: list[str]


class HoldingUnitResponse(BaseModel):
    unit_kind: str
    unit_id: str
    snapshot_id: str
    pinned_at: str


class RevocationResponse(BaseModel):
    """The revoked approval, the units holding it (running, then finished) and what to do next."""

    approval: ApprovalResponse
    units_holding_it: list[HoldingUnitResponse]
    finished_units_holding_it: list[HoldingUnitResponse]
    next: str


class ClassificationResponse(_Record):
    vocabulary: str
    values: list[str]
    rationale: str | None


class AnnotationResponse(_Record):
    annotation_id: str
    project_id: str
    source_id: str
    classification: ClassificationResponse
    target_behavior: str | None
    evidence: dict[str, Any]
    context: dict[str, Any]
    annotator: str
    annotated_at: str
    reviewed_by: str | None
    reviewed_at: str | None
    review_note: str | None


class ObservationResponse(_Record):
    """An observation, its annotations, and the classification they leave in effect."""

    source: str
    source_id: str
    project_id: str
    campaign_id: str | None
    cycle_id: str | None
    run_id: str | None
    task_id: str | None
    observed_at: str
    classification: ClassificationResponse
    evidence: dict[str, Any]
    annotations: list[AnnotationResponse]
    effective_classification: ClassificationResponse


class AssessmentResponse(_Record):
    assessment_id: str
    project_id: str
    exposure_id: str
    pattern_id: str
    state: str
    required_work_done: bool | None
    supplied: bool
    rubric: str
    evidence: str
    assessed_by: str
    assessed_at: str


class WithdrawnUseResponse(BaseModel):
    """An instruction the exposure was handed whose record is withdrawn now (Appendix A §3.8)."""

    record_id: str
    revision: str
    section: str
    withdrawn_by: str
    withdrawn_at: str
    why: str


class ExposureResponse(_Record):
    """One exposure (what a task was supplied) and its latest assessments."""

    exposure_id: str
    run_id: str
    task_id: str
    attempt: int
    cycle_id: str
    agent_id: str
    seam: str
    query: dict[str, Any]
    recalled: dict[str, Any]
    recorded_at: str
    assessments: list[AssessmentResponse]
    #: The instructions it was handed that are withdrawn now, marked; the exposure is unchanged.
    #: ``None`` when it was handed instructions and the records couldn't be read.
    withdrawn_instructions: list[WithdrawnUseResponse] | None = []


class AbsenceRateResponse(BaseModel):
    pattern_id: str
    supplied: bool
    absent: int
    assessed: int
    not_applicable: int
    unassessed: int
    rate: float | None


# --- the typed memory records (SIP-0110 Appendix A; #2177) ---


class InstructionApplicabilityDTO(BaseModel):
    """Where a project instruction applies: each field explicit, ``*`` for any."""

    model_config = ConfigDict(extra="forbid")
    task_types: list[str]
    roles: list[str]
    stacks: list[str]


class TaskTargetDTO(BaseModel):
    """A task instruction's target: one cycle, and its tasks by type (§A.3.7)."""

    model_config = ConfigDict(extra="forbid")
    cycle_id: str
    task_types: list[str]
    #: ``"continuations"``: it also reaches a campaign's repair or retry of the cycle (§3.7).
    carries_into: str | None = None


class RecordSourceDTO(BaseModel):
    """Where the record came from (§A.3.4). An API call, unless the caller says otherwise."""

    model_config = ConfigDict(extra="forbid")
    kind: str = "api_call"
    ids: dict[str, str] = Field(default_factory=dict)


class MemoryRecordContent(BaseModel):
    """A revision's content. References are ``{"ref": "<family>:<kind>:<id>@<revision>",
    "required": bool}``; one that carries the target's content is refused, naming where that
    fact is changed (§A.3.2)."""

    model_config = ConfigDict(extra="forbid")
    body: str
    suggestion: bool = False
    applicability: InstructionApplicabilityDTO | None = None
    target: TaskTargetDTO | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    source: RecordSourceDTO = Field(default_factory=RecordSourceDTO)


class MemoryRecordCreateRequest(MemoryRecordContent):
    kind: str
    scope: str
    project_id: str | None = None


class MemoryRecordWithdrawalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    why: str
    #: A task instruction's emergency withdrawal (Appendix A §3.8, T13): the work already built on
    #: it is halted, and a run that received it restarts without it.
    emergency: bool = False
    #: With ``emergency``: the corrected instruction, given to the same tasks as a new task
    #: instruction, which the restart is handed instead.
    replacement: str | None = None


class MemoryRecordRevisionResponse(BaseModel):
    number: int
    body: str
    author: str
    created_at: str
    source: dict[str, Any]
    confirmed_by: str | None
    supersedes: int | None
    suggestion: bool
    applicability: dict[str, Any] | None
    target: dict[str, Any] | None
    references: list[dict[str, Any]]


class MemoryRecordTaskUse(BaseModel):
    """A dispatch whose binding section handed the record, or that it held (#2182)."""

    exposure_id: str
    cycle_id: str
    run_id: str
    task_id: str
    attempt: int
    seam: str
    section: str
    revision: str
    disposition: str
    held: str | None = None


class MemoryRecordChatUse(BaseModel):
    """One of the reader's own chat turns whose context held the record."""

    session_id: str
    message_id: str
    revision: str
    disposition: str
    assembled_at: str


class MemoryRecordBuild(BaseModel):
    """A build the record's dispatches fed, once, with its indicators observed (SIP-0110 §0.10)."""

    run_id: str
    exposures: list[str]
    verdict: str | None = None
    failed_rounds: int | None = None
    refunded_rounds: int | None = None
    rounds_to_green: int | None = None
    accepted: bool | None = None


class MemoryRecordUsesResponse(BaseModel):
    """What used the record, apart from what it did (Appendix A §3.11)."""

    record_id: str
    tasks: list[MemoryRecordTaskUse]
    chats: list[MemoryRecordChatUse]
    #: Other people's chat turns that held it: counted, never opened (§3.4).
    others_chat_turns: int
    builds: list[MemoryRecordBuild]
    #: Dispatches with no build to report, by state: none of them a build failure (§0.10).
    unbuilt: dict[str, list[str]]
    effect: str


class MemoryRecordSourceTurnResponse(BaseModel):
    """The one chat turn a record came from, opened by its session's owner only (§A.3.4, T15)."""

    session_id: str
    message_id: str
    role: str
    content: str
    created_at: str


class MemoryRecordResponse(BaseModel):
    record_id: str
    kind: str
    scope: str
    project_id: str | None
    owner_id: str
    status: str
    current: MemoryRecordRevisionResponse
    revisions: list[MemoryRecordRevisionResponse]
    status_changes: list[dict[str, Any]]
    #: A campaign cycle's task instruction changed after admission: its row in the campaign's
    #: control log (§3.5), or ``None`` when the row couldn't be written. ``None`` for any other.
    control_log_entry_id: str | None = None


class HaltedRunResponse(BaseModel):
    run_id: str
    restart_from_task_id: str | None = None


class MemoryRecordWithdrawalResponse(MemoryRecordResponse):
    """A withdrawn record. For a project instruction, the units whose snapshot pinned it (running,
    then finished) and what to do next: its emergency withdrawal (Appendix A §3.8). No other kind
    is pinned, so for them the lists are empty and ``next`` is ``None``. A list is ``None`` when the
    snapshots couldn't be read, and ``next`` says so: unknown is never read as "none holds it"."""

    units_holding_it: list[HoldingUnitResponse] | None = []
    finished_units_holding_it: list[HoldingUnitResponse] | None = []
    next: str | None = None
    #: An emergency withdrawal's: each run halted, and the task its restart runs again from
    #: (``None``: the run only built on the instruction's work, and nothing in it restarts).
    halted: list[HaltedRunResponse] = []
    #: An emergency withdrawal's corrected instruction, as the new record the restart is handed.
    replacement_record_id: str | None = None


# --- a unit's snapshot as it binds now, and its re-binding (Appendix A §3.7; #2179) ---


class PinnedInstructionResponse(BaseModel):
    record_id: str
    revision: int
    text: str
    applicability: dict[str, list[str]]
    references: list[dict[str, Any]]


class RebindingResponse(BaseModel):
    """One re-binding: the revision replaced, its replacement (``None``: withdrawn), who, when and
    why."""

    record_id: str
    replaced: PinnedInstructionResponse
    replacement: PinnedInstructionResponse | None
    by: str
    at: str
    why: str


class SnapshotBindingResponse(BaseModel):
    """A unit's snapshot: the project instructions it binds now, and every re-binding since it was
    admitted, so what it bound then is still read."""

    unit_kind: str
    unit_id: str
    snapshot_id: str
    pinned_at: str
    instructions: list[PinnedInstructionResponse]
    instructions_unread: str | None
    memory_context_withheld: bool
    rebindings: list[RebindingResponse]


class RebindRequest(BaseModel):
    """Re-bind a running unit to a project instruction's current revision, or off it when the
    record is withdrawn. ``why`` is the intervention's reason."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    why: str


class RebindResponse(SnapshotBindingResponse):
    """The unit after its re-binding, the re-binding itself, its control-log row for a campaign
    (``None`` for a cycle, or when the row couldn't be written, which ``next`` says), and what
    follows."""

    rebinding: RebindingResponse
    control_log_entry_id: str | None
    next: str
