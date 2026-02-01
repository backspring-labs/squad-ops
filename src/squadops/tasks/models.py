"""Tasks domain models.

Frozen dataclasses for task envelope and result models.
Migrated from Pydantic BaseModel in SIP-0.8.8.

Part of SIP-0.8.7/0.8.8 Infrastructure Ports Migration.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TaskIdentity:
    """Immutable identity subset of TaskEnvelope for internal use.

    This is the new domain model for task identification.
    """

    task_id: str
    task_type: str
    source_agent: str
    target_agent: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class TaskEnvelope:
    """ACI Task Envelope - Contract between SquadOps runtime and agent container.

    All fields are always present (never omitted). Lineage fields may be placeholders
    when tracing is not enabled, but must be present.

    Identity and lineage fields (task_id, correlation_id, causation_id, trace_id, span_id)
    are immutable once created.

    Migrated from Pydantic BaseModel to frozen dataclass in SIP-0.8.8.
    """

    # Required identity fields
    task_id: str
    agent_id: str
    cycle_id: str
    pulse_id: str
    project_id: str
    task_type: str

    # Lineage fields (always present; may be placeholders)
    correlation_id: str
    causation_id: str
    trace_id: str
    span_id: str

    # Fields with defaults
    inputs: dict[str, Any] = field(default_factory=dict)
    priority: str | None = None
    timeout: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    task_name: str | None = None


@dataclass(frozen=True)
class TaskResult:
    """ACI Task Result - Terminal result from agent container execution.

    Matches ACI Section 7.2: task_id, status, outputs or error.
    Extended with execution_evidence for SIP-0.8.8 "No Silent Mocks".

    Migrated from Pydantic BaseModel to frozen dataclass in SIP-0.8.8.
    """

    task_id: str
    status: str  # SUCCEEDED, FAILED, or CANCELED
    outputs: dict[str, Any] | None = None
    error: str | None = None
    execution_evidence: dict[str, Any] | None = None  # SIP-0.8.8
