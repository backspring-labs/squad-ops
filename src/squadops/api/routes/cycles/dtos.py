"""
Pydantic DTOs for SIP-0064 cycle API request/response serialization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# =============================================================================
# Nested DTOs
# =============================================================================


class GateDTO(BaseModel):
    name: str
    description: str
    after_task_types: list[str] = Field(default_factory=list)


class TaskFlowPolicyDTO(BaseModel):
    mode: Literal["sequential", "fan_out_fan_in", "fan_out_soft_gates"] = "sequential"
    gates: list[GateDTO] = Field(default_factory=list)


# =============================================================================
# Request DTOs
# =============================================================================


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
    notes: str | None = None

    class Config:
        extra = "forbid"


class GateDecisionRequest(BaseModel):
    """Gate decision (T4+T13: normalized vocab, typed)."""

    decision: Literal[
        "approved",
        "approved_with_refinements",
        "returned_for_revision",
        "rejected",
    ]
    notes: str | None = None

    class Config:
        extra = "forbid"


class SetActiveProfileRequest(BaseModel):
    profile_id: str

    class Config:
        extra = "forbid"


class AgentProfileEntryRequest(BaseModel):
    """Agent entry in a profile create/update request (SIP-0075)."""

    agent_id: str
    role: str
    model: str
    enabled: bool = True
    config_overrides: dict = Field(default_factory=dict)

    class Config:
        extra = "forbid"


class ProfileCreateRequest(BaseModel):
    """Create a new squad profile (SIP-0075)."""

    name: str
    description: str = ""
    agents: list[AgentProfileEntryRequest]

    class Config:
        extra = "forbid"


class ProfileUpdateRequest(BaseModel):
    """Update an existing squad profile (SIP-0075)."""

    name: str | None = None
    description: str | None = None
    agents: list[AgentProfileEntryRequest] | None = None

    class Config:
        extra = "forbid"


class ProfileCloneRequest(BaseModel):
    """Clone a squad profile with a new name (SIP-0075)."""

    name: str

    class Config:
        extra = "forbid"


class BaselinePromoteRequest(BaseModel):
    artifact_id: str

    class Config:
        extra = "forbid"


# =============================================================================
# Response DTOs
# =============================================================================


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: str
    created_at: datetime
    tags: list[str]
    has_prd: bool = False


class GateDecisionResponse(BaseModel):
    gate_name: str
    decision: str
    decided_by: str
    decided_at: datetime
    notes: str | None = None


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
    notes: str | None = None
    status: str  # Derived CycleStatus
    runs: list[RunResponse] = Field(default_factory=list)


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


class AgentProfileEntryResponse(BaseModel):
    agent_id: str
    role: str
    role_label: str | None = None
    display_name: str | None = None
    model: str
    enabled: bool
    config_overrides: dict = Field(default_factory=dict)


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


class PromptMetaResponse(BaseModel):
    """Prompt field metadata for cycle request profile (SIP-0074 §5.8)."""

    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)
    type: str | None = None
    required: bool = False


class CycleRequestProfileResponse(BaseModel):
    """Cycle request profile with defaults and prompt metadata (SIP-0074)."""

    name: str
    description: str = ""
    defaults: dict = Field(default_factory=dict)
    prompts: dict[str, PromptMetaResponse] = Field(default_factory=dict)


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

    class Config:
        extra = "forbid"


class PullStatusResponse(BaseModel):
    """Status of an in-progress model pull (SIP-0075)."""

    pull_id: str
    model_name: str
    status: str
    error: str | None = None


class RunResumeRequest(BaseModel):
    """Resume a paused or failed run (SIP-0079)."""

    resume_reason: str | None = None

    class Config:
        extra = "forbid"


class CheckpointSummaryResponse(BaseModel):
    """Checkpoint summary for list endpoint (SIP-0079)."""

    checkpoint_index: int
    completed_task_count: int
    artifact_ref_count: int
    created_at: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
