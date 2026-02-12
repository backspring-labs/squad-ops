"""
Cycle execution domain models (SIP-0064 Section 8).

Frozen dataclasses for Projects, Cycles, Runs, Squad Profiles, Task Flow Policy,
Gate Decisions, and Artifact Refs. Enums, constants, and exceptions are co-located.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums (str, Enum) — following config/schema.py SSLMode pattern
# =============================================================================


class CycleStatus(str, Enum):
    """Cycle lifecycle status (derived from latest Run). SIP-0064 §6.1."""

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(str, Enum):
    """Run lifecycle status. SIP-0064 §6.2."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FlowMode(str, Enum):
    """Task flow orchestration mode. SIP-0064 §5.6."""

    SEQUENTIAL = "sequential"
    FAN_OUT_FAN_IN = "fan_out_fan_in"
    FAN_OUT_SOFT_GATES = "fan_out_soft_gates"


class BuildStrategy(str, Enum):
    """Build strategy for cycle execution."""

    FRESH = "fresh"
    INCREMENTAL = "incremental"


class GateDecisionValue(str, Enum):
    """Gate decision values (T4: normalized to approved/rejected everywhere)."""

    APPROVED = "approved"
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


class RunInitiator:
    """Run initiation source constants."""

    API = "api"
    CLI = "cli"
    RETRY = "retry"
    SYSTEM = "system"


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
