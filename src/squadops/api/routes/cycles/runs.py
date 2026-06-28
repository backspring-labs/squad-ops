"""
Run API routes (SIP-0064 §9.4).
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends

from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.dtos import (
    CheckpointSummaryResponse,
    GateDecisionRequest,
    RunResumeRequest,
)
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import compute_workload_progress, run_to_response
from squadops.auth.models import Scope
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles/{cycle_id}/runs", tags=["runs"])


@router.post("", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
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


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_runs(project_id: str, cycle_id: str, workload_type: str | None = None):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        runs = await registry.list_runs(cycle_id, workload_type=workload_type)
        return [run_to_response(r) for r in runs]
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{run_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_run(project_id: str, cycle_id: str, run_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        run = await registry.get_run(run_id)
        return run_to_response(run)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{run_id}/cancel", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def cancel_run(project_id: str, cycle_id: str, run_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        await registry.cancel_run(run_id)

        # #77: stop the orphaned Prefect flow run for this run.
        from squadops.api.routes.cycles.cancellation import cancel_orphaned_flow_runs

        cancelled = await cancel_orphaned_flow_runs(project_id, cycle_id, [run_id])

        return {
            "status": "cancelled",
            "run_id": run_id,
            "prefect_flow_runs_cancelled": cancelled,
        }
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post(
    "/{run_id}/gates/{gate_name}", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))]
)
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

        # SIP-0086: auto-promote the run's artifacts on approval so they
        # flow to the next workload via plan_artifact_refs /
        # prior_workload_artifact_refs. Without this the manifest stays
        # at "working" status and the impl workload gets no inputs.
        if body.decision == "approved":
            await _promote_run_artifacts(run_id)

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


@router.post("/{run_id}/resume", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def resume_run(
    project_id: str,
    cycle_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    body: RunResumeRequest | None = None,
):
    """Resume a paused or failed run (SIP-0079).

    Resumes from the latest checkpoint when one exists; a run PAUSED before any
    task ran (e.g. a SIP-0089 §2.5 duty deferral, #222) is re-attempted from the
    start. Re-execution is enqueued so the run actually proceeds — flipping status
    alone does not re-run the executor.
    """
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

        # 3. Resume source: a checkpoint (resume mid-plan), or — for a run PAUSED
        #    before any task ran (e.g. a §2.5 duty deferral, #222) — a re-attempt
        #    from the start. A checkpoint-less FAILED run still can't be resumed
        #    (no progress and no deliberate pause → create a fresh run).
        latest_cp = await registry.get_latest_checkpoint(run_id)
        if latest_cp is None and run.status != RunStatus.PAUSED.value:
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
                "checkpoint_index": latest_cp.checkpoint_index if latest_cp else None,
            },
        )

        # Re-attempt execution. Flipping status to RUNNING alone does not re-run
        # the executor — only cycle-create enqueues it. execute_run self-detects
        # the resume source: it resumes from the latest checkpoint if one exists,
        # else restarts the plan from the beginning, and re-runs the §2.5 duty
        # guard (a still-active hard-duty window simply re-defers).
        from squadops.api.runtime.deps import get_flow_executor

        background_tasks.add_task(
            get_flow_executor().execute_cycle,
            cycle_id,
            run_id,
            cycle.squad_profile_id,
        )

        return run_to_response(updated)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{run_id}/checkpoints", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
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


async def _promote_run_artifacts(run_id: str) -> None:
    """Promote all `working` artifacts produced by a run.

    Called from gate_decision() on approval. Idempotent: already-promoted
    artifacts are skipped by the vault. Errors are logged but do not fail
    the gate decision — the decision is the source of truth; promotion is
    a downstream effect that can be retried.
    """
    from squadops.api.runtime.deps import get_artifact_vault

    try:
        vault = get_artifact_vault()
    except Exception:
        logger.warning("artifact_vault unavailable; skipping promotion for run %s", run_id)
        return

    try:
        artifacts = await vault.list_artifacts(run_id=run_id)
    except Exception:
        logger.exception("failed to list artifacts for run %s during promotion", run_id)
        return

    for art in artifacts:
        if art.promotion_status == "promoted":
            continue
        try:
            await vault.promote_artifact(art.artifact_id)
        except Exception:
            logger.exception("failed to promote artifact %s for run %s", art.artifact_id, run_id)
