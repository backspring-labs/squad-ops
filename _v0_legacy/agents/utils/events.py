"""
Structured Event Models - ACI observability event emission.

All events originate from lifecycle hooks and include full lineage fields.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StructuredEvent(BaseModel):
    """
    ACI Structured Event - Emitted at lifecycle hooks.
    
    All lineage fields must be present (never omitted).
    Suitable for SOC Ledger ingestion, trace/log correlation, and causal graph reconstruction.
    """
    event_type: str  # e.g., "task_started", "pulse_failed", "cycle_started"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Full lineage identity set (all fields from ACI Section 5.4)
    project_id: str
    cycle_id: str
    pulse_id: str
    task_id: str | None  # Nullable until task creation
    agent_id: str
    correlation_id: str
    causation_id: str
    trace_id: str
    span_id: str
    
    # Optional metadata payload
    metadata: dict[str, Any] = Field(default_factory=dict)

