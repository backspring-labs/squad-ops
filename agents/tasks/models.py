"""
Tasks Adapter Models - Backend-agnostic DTOs for task management
"""

from datetime import datetime
from enum import Enum
from typing import Any  # SIP-0048: Dict used for metrics and inputs

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Task state enumeration"""
    PENDING = "pending"
    STARTED = "started"
    ACTIVE_NON_BLOCKING = "Active-Non-Blocking"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"
    IN_PROGRESS = "in_progress"


class FlowState(str, Enum):
    """Execution cycle (flow) state enumeration"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Artifact(BaseModel):
    """Artifact model for task outputs"""
    type: str  # e.g., "code", "test_report", "build_plan", "pr", "log"
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: Any | None = None  # Can store actual content if needed


class TaskFilters(BaseModel):
    """Filters for querying tasks"""
    cycle_id: str | None = None  # SIP-0048: renamed from ecid
    agent: str | None = None
    status: str | None = None
    pid: str | None = None
    limit: int | None = 50


class TaskCreate(BaseModel):
    """DTO for creating a new task (SIP-0048: enhanced with agent_id, task_name)"""
    task_id: str
    cycle_id: str  # SIP-0048: renamed from ecid
    agent: str  # Kept for backward compatibility
    agent_id: str | None = None  # SIP-0048: Agent identifier (use agent_id, not role normalization)
    task_name: str | None = None  # SIP-0048: Task name/type identifier
    status: str = "started"
    priority: str | None = "MEDIUM"
    description: str | None = None
    dependencies: list[str] | None = Field(default_factory=list)
    delegated_by: str | None = None
    delegated_to: str | None = None
    phase: str | None = None
    pid: str | None = None


class Task(BaseModel):
    """Complete task model matching agent_task_log table (SIP-0048: enhanced with agent_id, task_name, metrics)"""
    task_id: str
    pid: str | None = None
    cycle_id: str | None = None  # SIP-0048: renamed from ecid
    agent: str  # Kept for backward compatibility
    agent_id: str | None = None  # SIP-0048: Agent identifier (use agent_id, not role normalization)
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
        from_attributes = True


class FlowRun(BaseModel):
    """Execution cycle (flow) model matching cycle table (SIP-0048: renamed from execution_cycle, enhanced with new fields)"""
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
    inputs: dict[str, Any] | None = Field(default_factory=dict)  # SIP-0048: Cycle inputs as JSON (PIDs, repo, branch)
    created_at: datetime | None = None
    initiated_by: str | None = None
    status: str = "active"
    notes: str | None = None

    class Config:
        from_attributes = True


class FlowCreate(BaseModel):
    """DTO for creating a new execution cycle"""
    cycle_id: str  # SIP-0048: renamed from ecid
    pid: str
    project_id: str | None = None  # SIP-0047
    run_type: str
    title: str
    description: str | None = None
    initiated_by: str


class FlowUpdate(BaseModel):
    """DTO for updating an execution cycle"""
    status: str | None = None
    notes: str | None = None


class TaskStatus(BaseModel):
    """Task status model matching task_status table"""
    task_id: str
    agent_name: str
    status: str
    progress: float = 0.0
    eta: str | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    """Task summary statistics for an execution cycle"""
    total_tasks: int
    completed: int
    in_progress: int
    delegated: int
    failed: int
    avg_duration: str | None = None  # INTERVAL type as string

    class Config:
        from_attributes = True

