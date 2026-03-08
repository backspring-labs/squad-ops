"""
Run API routes (SIP-0064 §9.4).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from squadops.api.routes.cycles.dtos import (
    CheckpointSummaryResponse,
    GateDecisionRequest,
    RunResumeRequest,
)
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import compute_workload_progress, run_to_response
from squadops.cycles.lifecycle import compute_config_hash, resolve_cycle_status
from squadops.cycles.models import (
    CycleError,
    CycleStatus,
    GateDecision,
    Run,
    RunStatus,
    RunTerminalError,
    ValidationError,
    validate_workload_type,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles/{cycle_id}/runs", tags=["runs"])


@router.post("")
async def create_run(project_id: str, cycle_id: str, workload_type: str | None = None):
    """Create a new Run (retry) for an existing Cycle."""
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        validated_wt = validate_workload_type(workload_type)
        registry = get_cycle_registry()
        cycle = await registry.get_cycle(cycle_id)
        existing_runs = await registry.list_runs(cycle_id)
        run_number = len(existing_runs) + 1

        config_hash = compute_config_hash(cycle.applied_defaults, cycle.execution_overrides)

        run = Run(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            cycle_id=cycle_id,
            run_number=run_number,
            status="queued",
            initiated_by="retry",
            resolved_config_hash=config_hash,
            workload_type=validated_wt,
        )
        created = await registry.create_run(run)

        # SIP-0077: run.created
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        get_cycle_event_bus().emit(
            EventType.RUN_CREATED,
            entity_type="run",
            entity_id=created.run_id,
            context={
                "cycle_id": cycle_id,
                "run_id": created.run_id,
                "project_id": project_id,
            },
            payload={
                "run_number": created.run_number,
                "initiated_by": created.initiated_by,
                "workload_type": created.workload_type,
            },
        )

        return run_to_response(created)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("")
async def list_runs(project_id: str, cycle_id: str, workload_type: str | None = None):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        runs = await registry.list_runs(cycle_id, workload_type=workload_type)
        return [run_to_response(r) for r in runs]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{run_id}")
async def get_run(project_id: str, cycle_id: str, run_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        run = await registry.get_run(run_id)
        return run_to_response(run)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{run_id}/cancel")
async def cancel_run(project_id: str, cycle_id: str, run_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        await registry.cancel_run(run_id)
        return {"status": "cancelled", "run_id": run_id}
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{run_id}/gates/{gate_name}")
async def gate_decision(
    project_id: str,
    cycle_id: str,
    run_id: str,
    gate_name: str,
    body: GateDecisionRequest,
):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        decision = GateDecision(
            gate_name=gate_name,
            decision=body.decision,
            decided_by="system",  # TODO: extract from auth context
            decided_at=datetime.now(UTC),
            notes=body.notes,
        )
        updated = await registry.record_gate_decision(run_id, decision)

        # SIP-0077: gate.decided
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        get_cycle_event_bus().emit(
            EventType.GATE_DECIDED,
            entity_type="gate",
            entity_id=gate_name,
            context={
                "cycle_id": cycle_id,
                "run_id": run_id,
                "project_id": project_id,
            },
            payload={
                "gate_name": gate_name,
                "decision": body.decision,
                "decided_by": decision.decided_by,
                "notes": body.notes,
            },
        )

        return run_to_response(updated)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{run_id}/resume")
async def resume_run(
    project_id: str,
    cycle_id: str,
    run_id: str,
    body: RunResumeRequest | None = None,
):
    """Resume a paused or failed run from its latest checkpoint (SIP-0079)."""
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()

        # 1. Fetch run — validates existence
        run = await registry.get_run(run_id)

        # 2. Status must be paused or failed
        if run.status not in (RunStatus.PAUSED.value, RunStatus.FAILED.value):
            raise RunTerminalError(
                f"Cannot resume run in status {run.status!r} — must be paused or failed"
            )

        # 3. Must have at least one checkpoint
        latest_cp = await registry.get_latest_checkpoint(run_id)
        if latest_cp is None:
            raise ValidationError("Cannot resume run without a checkpoint")

        # 4. Parent cycle must not be terminal
        cycle = await registry.get_cycle(cycle_id)  # validates cycle exists
        runs = await registry.list_runs(cycle_id)
        ws = cycle.applied_defaults.get("workload_sequence", [])
        progress = compute_workload_progress(ws, runs)
        workload_statuses = [e.status for e in progress] if progress else None
        cycle_status = resolve_cycle_status(runs, False, workload_statuses=workload_statuses)
        if cycle_status in (CycleStatus.COMPLETED, CycleStatus.CANCELLED):
            raise RunTerminalError(f"Cannot resume run — parent cycle is {cycle_status.value}")

        # 5. Transition to running
        updated = await registry.update_run_status(run_id, RunStatus.RUNNING)

        # SIP-0077: run.resumed
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        resume_reason = body.resume_reason if body else None
        get_cycle_event_bus().emit(
            EventType.RUN_RESUMED,
            entity_type="run",
            entity_id=run_id,
            context={
                "cycle_id": cycle_id,
                "run_id": run_id,
                "project_id": project_id,
            },
            payload={
                "resume_reason": resume_reason,
                "checkpoint_index": latest_cp.checkpoint_index,
            },
        )

        return run_to_response(updated)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{run_id}/checkpoints")
async def list_checkpoints(project_id: str, cycle_id: str, run_id: str):
    """List checkpoints for a run (SIP-0079)."""
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        checkpoints = await registry.list_checkpoints(run_id)
        return [
            CheckpointSummaryResponse(
                checkpoint_index=cp.checkpoint_index,
                completed_task_count=len(cp.completed_task_ids),
                artifact_ref_count=len(cp.artifact_refs),
                created_at=cp.created_at,
            )
            for cp in checkpoints
        ]
    except CycleError as e:
        raise handle_cycle_error(e) from e
