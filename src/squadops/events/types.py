"""Canonical event type constants for the cycle lifecycle event taxonomy.

20 event types across 6 entity types (cycle, run, gate, task, pulse, artifact).
Follows the WorkloadType / ArtifactType constants-class pattern (not enum).
"""

from __future__ import annotations


class EventType:
    """Canonical lifecycle event type constants.

    Format: ``{entity}.{transition}``
    """

    # --- Cycle (2) ---
    CYCLE_CREATED = "cycle.created"
    CYCLE_CANCELLED = "cycle.cancelled"

    # --- Run (7) ---
    RUN_CREATED = "run.created"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    RUN_PAUSED = "run.paused"
    RUN_RESUMED = "run.resumed"

    # --- Gate (1) ---
    GATE_DECIDED = "gate.decided"

    # --- Task (3) ---
    TASK_DISPATCHED = "task.dispatched"
    TASK_SUCCEEDED = "task.succeeded"
    TASK_FAILED = "task.failed"

    # --- Pulse (5) ---
    PULSE_BOUNDARY_REACHED = "pulse.boundary_reached"
    PULSE_SUITE_EVALUATED = "pulse.suite_evaluated"
    PULSE_BOUNDARY_DECIDED = "pulse.boundary_decided"
    PULSE_REPAIR_STARTED = "pulse.repair_started"
    PULSE_REPAIR_EXHAUSTED = "pulse.repair_exhausted"

    # --- Artifact (2) ---
    ARTIFACT_STORED = "artifact.stored"
    ARTIFACT_PROMOTED = "artifact.promoted"

    @classmethod
    def all(cls) -> tuple[str, ...]:
        """Return all 20 event type constants."""
        return tuple(
            v
            for k, v in vars(cls).items()
            if not k.startswith("_") and k == k.upper() and isinstance(v, str)
        )
