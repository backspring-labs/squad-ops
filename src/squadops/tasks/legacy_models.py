"""
Legacy Tasks Adapter Models - Backend-agnostic DTOs for task management.

Pydantic models maintained for DB operations and backward compatibility.
Part of SIP-0.8.9 migration from _v0_legacy.

Note: New code should prefer the frozen dataclass models in models.py.
These legacy Pydantic models are retained for DB ORM compatibility.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskState(StrEnum):
    """Task state enumeration."""

    PENDING = "pending"
    STARTED = "started"
    ACTIVE_NON_BLOCKING = "Active-Non-Blocking"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"
    IN_PROGRESS = "in_progress"


class FlowState(StrEnum):
    """Execution cycle (flow) state enumeration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Artifact(BaseModel):
    """Artifact model for task outputs."""

    type: str  # e.g., "code", "test_report", "build_plan", "pr", "log"
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: Any | None = None  # Can store actual content if needed


class TaskFilters(BaseModel):
    """Filters for querying tasks."""

    cycle_id: str | None = None  # SIP-0048: renamed from ecid
    agent: str | None = None
    status: str | None = None
    pid: str | None = None
    limit: int | None = 50


class TaskCreate(BaseModel):
    """
    DTO for creating a new task (ACI v0.8: enhanced with lineage fields).

    All lineage fields are required. If not provided, LineageGenerator will fill them.
    task_type and inputs are required for ACI compliance.
    """

    task_id: str
    cycle_id: str  # SIP-0048: renamed from ecid
    agent: str  # Kept for backward compatibility
    agent_id: str | None = None  # SIP-0048: Agent identifier
    task_name: str | None = None  # Optional human-readable label
    task_type: str  # Required standardized taxonomy/behavior category (ACI)
    inputs: dict[str, Any] = Field(default_factory=dict)  # Required structured task inputs (ACI)
    status: str = "started"
    priority: str | None = "MEDIUM"
    description: str | None = None
    dependencies: list[str] | None = Field(default_factory=list)
    delegated_by: str | None = None
    delegated_to: str | None = None
    phase: str | None = None
    pid: str | None = None

    # ACI Lineage fields (required, will be generated if not provided)
    project_id: str | None = None
    pulse_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


class Task(BaseModel):
    """Complete task model matching agent_task_log table."""

    task_id: str
    pid: str | None = None
    cycle_id: str | None = None  # SIP-0048: renamed from ecid
    agent: str  # Kept for backward compatibility
    agent_id: str | None = None  # SIP-0048: Agent identifier
    task_name: str | None = None  # SIP-0048: Task name/type identifier
    phase: str | None = None
    status: str
    priority: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: str | None = None  # INTERVAL type as string
    artifacts: list[Artifact] | None = Field(default_factory=list)
    metrics: dict[str, Any] | None = Field(default_factory=dict)  # SIP-0048: Task metrics as JSON
    dependencies: list[str] | None = Field(default_factory=list)
    error_log: str | None = None
    delegated_by: str | None = None
    delegated_to: str | None = None
    created_at: datetime | None = None

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class FlowRun(BaseModel):
    """Execution cycle (flow) model matching cycle table."""

    cycle_id: str  # SIP-0048: renamed from ecid
    pid: str
    project_id: str | None = None  # SIP-0047
    run_type: str  # 'warmboot', 'project', 'experiment', 'tuning'
    title: str
    description: str | None = None
    name: str | None = None  # SIP-0048: Human-readable cycle name
    goal: str | None = None  # SIP-0048: Cycle objective or goal statement
    start_time: datetime | None = None  # SIP-0048: Cycle start timestamp
    end_time: datetime | None = None  # SIP-0048: Cycle end timestamp
    inputs: dict[str, Any] | None = Field(default_factory=dict)  # SIP-0048: Cycle inputs as JSON
    created_at: datetime | None = None
    initiated_by: str | None = None
    status: str = "active"
    notes: str | None = None

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class FlowCreate(BaseModel):
    """DTO for creating a new execution cycle."""

    cycle_id: str  # SIP-0048: renamed from ecid
    pid: str
    project_id: str | None = None  # SIP-0047
    run_type: str
    title: str
    description: str | None = None
    initiated_by: str


class FlowUpdate(BaseModel):
    """DTO for updating an execution cycle."""

    status: str | None = None
    notes: str | None = None


class TaskStatus(BaseModel):
    """Task status model matching task_status table."""

    task_id: str
    agent_name: str
    status: str
    progress: float = 0.0
    eta: str | None = None
    updated_at: datetime | None = None

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class TaskSummary(BaseModel):
    """Task summary statistics for an execution cycle."""

    total_tasks: int
    completed: int
    in_progress: int
    delegated: int
    failed: int
    avg_duration: str | None = None  # INTERVAL type as string

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class LegacyTaskEnvelope(BaseModel):
    """
    ACI Task Envelope - Contract between SquadOps runtime and agent container.

    Legacy Pydantic version maintained for DB operations.
    New code should use the frozen dataclass TaskEnvelope from models.py.
    """

    # Required identity fields
    task_id: str
    agent_id: str
    cycle_id: str
    pulse_id: str
    project_id: str
    task_type: str  # Standardized taxonomy/behavior category
    inputs: dict[str, Any] = Field(default_factory=dict)  # Execution-relevant data

    # Lineage fields (always present; may be placeholders)
    correlation_id: str  # Cycle-scoped, stable within cycle
    causation_id: str  # Immediate parent event/message/decision
    trace_id: str  # Distributed tracing identifier (may be placeholder)
    span_id: str  # Current span identifier (may be placeholder)

    # Optional fields
    priority: str | None = None
    timeout: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)  # Orchestration/transport info
    task_name: str | None = None  # Optional human-readable label


class LegacyTaskResult(BaseModel):
    """
    ACI Task Result - Terminal result from agent container execution.

    Legacy Pydantic version maintained for DB operations.
    New code should use the frozen dataclass TaskResult from models.py.
    """

    task_id: str  # Must match original envelope task_id
    status: str  # SUCCEEDED, FAILED, or CANCELED
    outputs: dict[str, Any] | None = None  # Present when status=SUCCEEDED
    error: str | None = None  # Present when status=FAILED or CANCELED
