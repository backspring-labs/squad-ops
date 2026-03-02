"""CycleEvent domain model — the canonical lifecycle event envelope.

Frozen dataclass following the Cycle/Run/Gate pattern in cycles/models.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CycleEvent:
    """A single canonical lifecycle event.

    Identity and timing fields are enriched by the adapter (not the caller).
    Callers provide semantic inputs: event_type, entity fields, context, payload.
    """

    # --- Identity (adapter-enriched) ---
    event_id: str
    occurred_at: datetime

    # --- Source (adapter-enriched) ---
    source_service: str
    source_version: str

    # --- Event classification ---
    event_type: str  # EventType constant value

    # --- Entity ---
    entity_type: str  # e.g. "cycle", "run", "gate", "task", "pulse", "artifact"
    entity_id: str

    # --- Context (caller-provided) ---
    context: dict = field(default_factory=dict)

    # --- Payload (caller-provided, event-type-specific) ---
    payload: dict = field(default_factory=dict)

    # --- Sequence (adapter-enriched) ---
    sequence: int = 0
    semantic_key: str = ""
