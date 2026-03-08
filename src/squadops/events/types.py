"""Canonical event type constants for the cycle lifecycle event taxonomy.

28 event types across 9 entity types (cycle, run, gate, task, pulse, artifact, checkpoint, correction, workload).
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

    # --- Checkpoint (2) — SIP-0079 ---
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"

    # --- Correction (3) — SIP-0079 ---
    CORRECTION_INITIATED = "correction.initiated"
    CORRECTION_DECIDED = "correction.decided"
    CORRECTION_COMPLETED = "correction.completed"

    # --- Workload (3) — SIP-0083 ---
    WORKLOAD_COMPLETED = "workload.completed"
    WORKLOAD_GATE_AWAITING = "workload.gate_awaiting"
    WORKLOAD_ADVANCED = "workload.advanced"

    @classmethod
    def all(cls) -> tuple[str, ...]:
        """Return all 28 event type constants."""
        return tuple(
            v
            for k, v in vars(cls).items()
            if not k.startswith("_") and k == k.upper() and isinstance(v, str)
        )
