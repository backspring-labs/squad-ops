"""
Cycle execution domain models (SIP-0064 Section 8).

Frozen dataclasses for Projects, Cycles, Runs, Squad Profiles, Task Flow Policy,
Gate Decisions, and Artifact Refs. Enums, constants, and exceptions are co-located.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

# =============================================================================
# Enums (str, Enum) — following config/schema.py SSLMode pattern
# =============================================================================


class CycleStatus(StrEnum):
    """Cycle lifecycle status (derived from latest Run). SIP-0064 §6.1."""

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    """Run lifecycle status. SIP-0064 §6.2."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FlowMode(StrEnum):
    """Task flow orchestration mode. SIP-0064 §5.6."""

    SEQUENTIAL = "sequential"
    FAN_OUT_FAN_IN = "fan_out_fan_in"
    FAN_OUT_SOFT_GATES = "fan_out_soft_gates"


class BuildStrategy(StrEnum):
    """Build strategy for cycle execution."""

    FRESH = "fresh"
    INCREMENTAL = "incremental"


class GateDecisionValue(StrEnum):
    """Gate decision values (SIP-0076 §10.2)."""

    APPROVED = "approved"
    APPROVED_WITH_REFINEMENTS = "approved_with_refinements"
    RETURNED_FOR_REVISION = "returned_for_revision"
    REJECTED = "rejected"


# =============================================================================
# Constants classes — following auth/models.py Role pattern
# =============================================================================


class ArtifactType:
    """Well-known artifact type constants."""

    PRD = "prd"
    CODE = "code"
    TEST_REPORT = "test_report"
    BUILD_PLAN = "build_plan"
    CONFIG_SNAPSHOT = "config_snapshot"
    QA_HANDOFF = "qa_handoff"


class RunInitiator:
    """Run initiation source constants."""

    API = "api"
    CLI = "cli"
    RETRY = "retry"
    SYSTEM = "system"


class WorkloadType:
    """Well-known workload type constants.

    workload_type on Run is free-form str | None. These constants
    document the standard vocabulary. Custom values are permitted.
    """

    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    EVALUATION = "evaluation"
    REFINEMENT = "refinement"
    WRAPUP = "wrapup"


class PromotionStatus:
    """Well-known artifact promotion status constants."""

    WORKING = "working"
    PROMOTED = "promoted"


# =============================================================================
# Exceptions — following auth/models.py pattern
# =============================================================================


class CycleError(Exception):
    """Base exception for cycle domain errors."""


class CycleNotFoundError(CycleError):
    """Raised when a cycle_id cannot be found."""


class RunNotFoundError(CycleError):
    """Raised when a run_id cannot be found."""


class IllegalStateTransitionError(CycleError):
    """Raised when a Run status transition is not legal."""


class GateAlreadyDecidedError(CycleError):
    """Raised when a conflicting gate decision is attempted."""


class RunTerminalError(CycleError):
    """Raised when an action is attempted on a Run in terminal state."""


class ProjectNotFoundError(CycleError):
    """Raised when a project_id cannot be found."""


class ArtifactNotFoundError(CycleError):
    """Raised when an artifact_id cannot be found."""


class BaselineNotAllowedError(CycleError):
    """Raised when baseline promotion is attempted on a fresh build strategy."""


class ValidationError(CycleError):
    """Raised for domain validation failures (e.g., unknown gate name)."""


class ProfileNotFoundError(CycleError):
    """Raised when a squad profile_id cannot be found."""


class ActiveProfileDeletionError(CycleError):
    """Raised when attempting to delete the active profile."""


class ProfileValidationError(CycleError):
    """Raised for squad profile validation failures (bad ID, unknown override keys)."""


# Allowed keys in AgentProfileEntry.config_overrides (SIP-0075 §5.5.1).
# Unknown keys are rejected with 422, not silently ignored.
ALLOWED_CONFIG_OVERRIDE_KEYS = frozenset({
    "temperature",
    "max_completion_tokens",
    "timeout_seconds",
})

# Required roles that must be present in a squad profile for plan generation.
# Missing required roles are a hard error, not a silent fallback. (SIP-0075)
REQUIRED_PLAN_ROLES = frozenset({"strat", "dev", "qa", "data", "lead"})

# Required roles for refinement workloads. Refinement is lead + QA only. (SIP-0078 §5.10)
REQUIRED_REFINEMENT_ROLES = frozenset({"lead", "qa"})

# Required roles for wrap-up workloads. Wrap-up is data + QA + lead. (SIP-0080 §7.1)
REQUIRED_WRAPUP_ROLES = frozenset({"data", "qa", "lead"})


# =============================================================================
# Validation helpers
# =============================================================================


def validate_workload_type(value: str | None) -> str | None:
    """Validate and normalize a workload_type value.

    Rules (SIP-0076 §9.8):
    - None is valid (legacy/unclassified run).
    - Leading/trailing whitespace is trimmed.
    - Empty string after trim is rejected (ValidationError).
    - Supplied value is preserved exactly after trim (no case normalization).
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        raise ValidationError("workload_type must be a non-empty string or null")
    return trimmed


# =============================================================================
# Frozen dataclasses — SIP-0064 §8
# =============================================================================


@dataclass(frozen=True)
class Project:
    """Pre-registered project entity. SIP-0064 §8.1."""

    project_id: str
    name: str
    description: str
    created_at: datetime
    tags: tuple[str, ...] = ()
    prd_path: str | None = None


@dataclass(frozen=True)
class Gate:
    """Named decision point in a task flow. SIP-0064 §8.3."""

    name: str
    description: str
    after_task_types: tuple[str, ...]


@dataclass(frozen=True)
class TaskFlowPolicy:
    """Declared orchestration intent. SIP-0064 §8.3."""

    mode: str  # FlowMode value
    gates: tuple[Gate, ...] = ()


@dataclass(frozen=True)
class GateDecision:
    """Recorded gate decision on a Run. SIP-0064 §8.4."""

    gate_name: str
    decision: str  # GateDecisionValue value
    decided_by: str
    decided_at: datetime
    notes: str | None = None


@dataclass(frozen=True)
class Cycle:
    """Experiment record — captures intent and configuration snapshot. SIP-0064 §8.2.

    A Cycle is created once and may have multiple Runs. All experiment parameters
    are immutable per Cycle (T5: applied_defaults and execution_overrides set once).
    """

    cycle_id: str
    project_id: str
    created_at: datetime
    created_by: str

    # Core experiment dimensions
    prd_ref: str | None
    squad_profile_id: str
    squad_profile_snapshot_ref: str
    task_flow_policy: TaskFlowPolicy

    # Execution mechanics
    build_strategy: str  # BuildStrategy value
    applied_defaults: dict = field(default_factory=dict)
    execution_overrides: dict = field(default_factory=dict)
    expected_artifact_types: tuple[str, ...] = ()

    # Extensible experiment context
    experiment_context: dict = field(default_factory=dict)

    notes: str | None = None


@dataclass(frozen=True)
class Run:
    """Single execution attempt of a Cycle. SIP-0064 §8.4."""

    run_id: str
    cycle_id: str
    run_number: int
    status: str  # RunStatus value
    initiated_by: str  # RunInitiator value
    resolved_config_hash: str
    resolved_config_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_decisions: tuple[GateDecision, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    workload_type: str | None = None


@dataclass(frozen=True)
class ArtifactRef:
    """Immutable artifact metadata. SIP-0064 §8.5."""

    artifact_id: str
    project_id: str
    artifact_type: str
    filename: str
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime
    cycle_id: str | None = None
    run_id: str | None = None
    metadata: dict = field(default_factory=dict)
    vault_uri: str | None = None
    promotion_status: str = "working"


@dataclass(frozen=True)
class AgentProfileEntry:
    """Agent configuration within a squad profile. SIP-0064 §8.6."""

    agent_id: str
    role: str
    model: str
    enabled: bool
    config_overrides: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SquadProfile:
    """Saved, versioned squad configuration. SIP-0064 §8.6."""

    profile_id: str
    name: str
    description: str
    version: int
    agents: tuple[AgentProfileEntry, ...]
    created_at: datetime
