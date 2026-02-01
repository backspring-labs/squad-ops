"""Tasks domain models.

New frozen dataclasses for task identity subset.
Full TaskEnvelope migration deferred to 0.8.8.

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskIdentity:
    """Immutable identity subset of TaskEnvelope for internal use.

    This is the new domain model for task identification.
    Full TaskEnvelope migration to frozen dataclasses in 0.8.8.
    """

    task_id: str
    task_type: str
    source_agent: str
    target_agent: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
