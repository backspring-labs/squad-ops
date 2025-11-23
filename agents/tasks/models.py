"""
Tasks Adapter Models - Backend-agnostic DTOs for task management
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
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
    path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content: Optional[Any] = None  # Can store actual content if needed


class TaskFilters(BaseModel):
    """Filters for querying tasks"""
    ecid: Optional[str] = None
    agent: Optional[str] = None
    status: Optional[str] = None
    pid: Optional[str] = None
    limit: Optional[int] = 50


class TaskCreate(BaseModel):
    """DTO for creating a new task"""
    task_id: str
    ecid: str
    agent: str
    status: str = "started"
    priority: Optional[str] = "MEDIUM"
    description: Optional[str] = None
    dependencies: Optional[List[str]] = Field(default_factory=list)
    delegated_by: Optional[str] = None
    delegated_to: Optional[str] = None
    phase: Optional[str] = None
    pid: Optional[str] = None


class Task(BaseModel):
    """Complete task model matching agent_task_log table"""
    task_id: str
    pid: Optional[str] = None
    ecid: Optional[str] = None
    agent: str
    phase: Optional[str] = None
    status: str
    priority: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[str] = None  # INTERVAL type as string
    artifacts: Optional[List[Artifact]] = Field(default_factory=list)
    dependencies: Optional[List[str]] = Field(default_factory=list)
    error_log: Optional[str] = None
    delegated_by: Optional[str] = None
    delegated_to: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FlowRun(BaseModel):
    """Execution cycle (flow) model matching execution_cycle table"""
    ecid: str
    pid: str
    run_type: str  # 'warmboot', 'project', 'experiment', 'tuning'
    title: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    initiated_by: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class FlowCreate(BaseModel):
    """DTO for creating a new execution cycle"""
    ecid: str
    pid: str
    run_type: str
    title: str
    description: Optional[str] = None
    initiated_by: str


class FlowUpdate(BaseModel):
    """DTO for updating an execution cycle"""
    status: Optional[str] = None
    notes: Optional[str] = None


class TaskStatus(BaseModel):
    """Task status model matching task_status table"""
    task_id: str
    agent_name: str
    status: str
    progress: float = 0.0
    eta: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    """Task summary statistics for an execution cycle"""
    total_tasks: int
    completed: int
    in_progress: int
    delegated: int
    failed: int
    avg_duration: Optional[str] = None  # INTERVAL type as string

    class Config:
        from_attributes = True

