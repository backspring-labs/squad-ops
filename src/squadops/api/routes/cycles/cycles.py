"""
Cycle API routes (SIP-0064 §9.3).
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends

from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.dtos import CycleCreateRequest, CycleCreateResponse
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import cycle_to_response
from squadops.auth.models import Scope
from squadops.cycles.lifecycle import compute_config_hash
from squadops.cycles.models import (
    Cycle,
    CycleError,
    CycleStatus,
    Gate,
    PreflightRejectedError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.preflight import (
    combine,
    model_availability_decision,
    required_roles_decision,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles", tags=["cycles"])


async def _pulled_model_names() -> list[str] | None:
    """Best-effort list of the LLM backend's pulled-model names, or ``None``.

    ``None`` (backend not configured / not an Ollama adapter / unreachable) makes the
    model-availability preflight *warn and allow* rather than block — never block on
    missing evidence (SIP-0095 §6.2). Only a reachable backend yields a verifiable list.
    """
    from squadops.api.runtime.deps import get_llm_port

    try:
        from adapters.llm.ollama import OllamaAdapter

        port = get_llm_port()
        if not isinstance(port, OllamaAdapter):
            return None
        raw = await port.list_pulled_models()
    except Exception as exc:  # not configured, wrong adapter, or backend unreachable
        logger.info("preflight_model_list_unverifiable", extra={"error": str(exc)})
        return None
    return [name for m in raw if (name := m.get("name"))]


async def _run_create_preflight(profile: SquadProfile, applied_defaults: dict) -> None:
    """SIP-0095 create-time preflight: fail fast BEFORE persist/dispatch.

    Blocks (HTTP 422) when the squad can't satisfy the requested workloads' required
    roles or names a model definitively not pulled; an unreachable backend warns and
    allows. Warnings are logged here — the response/CLI surface is Phase 4.
    """
    decision = combine(
        required_roles_decision(profile, applied_defaults),
        model_availability_decision(profile, await _pulled_model_names()),
    )
    for w in decision.warnings:
        logger.warning(
            "cycle_create_preflight_warning", extra={"code": w.code, "detail": w.message}
        )
    if decision.rejected:
        raise PreflightRejectedError(decision.summary())


@router.post("", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def create_cycle(
    project_id: str, body: CycleCreateRequest, background_tasks: BackgroundTasks
):
    """Create a Cycle + first Run (T17: atomic).

    SIP-0066: After persisting, enqueues execute_run as a background task.
    """
    from squadops.api.runtime.deps import (
        get_cycle_registry,
        get_flow_executor,
        get_project_registry,
        get_squad_profile_port,
    )

    try:
        # Verify project exists
        project_registry = get_project_registry()
        await project_registry.get_project(project_id)

        # Resolve squad profile snapshot
        profile_port = get_squad_profile_port()
        profile, snapshot_hash = await profile_port.resolve_snapshot(body.squad_profile_id)

        # Build domain objects
        cycle_id = f"cyc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # Convert DTO policy to domain
        gates = tuple(
            Gate(
                name=g.name,
                description=g.description,
                after_task_types=tuple(g.after_task_types),
            )
            for g in body.task_flow_policy.gates
        )
        policy = TaskFlowPolicy(mode=body.task_flow_policy.mode, gates=gates)

        # SIP-0065 D2: use client-supplied applied_defaults (CRP defaults from CLI)
        applied_defaults = body.applied_defaults

        # SIP-0095: create-time preflight — fail fast (422) before persist/dispatch.
        await _run_create_preflight(profile, applied_defaults)

        config_hash = compute_config_hash(applied_defaults, body.execution_overrides)

        cycle = Cycle(
            cycle_id=cycle_id,
            project_id=project_id,
            created_at=now,
            created_by="system",
            prd_ref=body.prd_ref,
            squad_profile_id=body.squad_profile_id,
            squad_profile_snapshot_ref=snapshot_hash,
            task_flow_policy=policy,
            build_strategy=body.build_strategy,
            applied_defaults=applied_defaults,
            execution_overrides=body.execution_overrides,
            expected_artifact_types=tuple(body.expected_artifact_types),
            experiment_context=body.experiment_context,
            notes=body.notes,
        )

        # Resolve workload_type from workload_sequence (fixes #26)
        ws = applied_defaults.get("workload_sequence", [])
        workload_type = ws[0]["type"] if ws else None

        run = Run(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            cycle_id=cycle_id,
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash=config_hash,
            workload_type=workload_type,
        )

        # Persist atomically (T17)
        cycle_registry = get_cycle_registry()
        await cycle_registry.create_cycle(cycle)
        await cycle_registry.create_run(run)

        # SIP-0077: cycle.created
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        get_cycle_event_bus().emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id=cycle.cycle_id,
            context={"cycle_id": cycle.cycle_id, "project_id": project_id},
            payload={
                "project_id": project_id,
                "created_by": cycle.created_by,
                "squad_profile_id": cycle.squad_profile_id,
                "prd_ref": cycle.prd_ref,
            },
        )

        # SIP-0083: Enqueue cycle execution (wraps execute_run for multi-workload)
        flow_executor = get_flow_executor()
        background_tasks.add_task(
            flow_executor.execute_cycle,
            cycle.cycle_id,
            run.run_id,
            body.squad_profile_id,
        )

        return CycleCreateResponse(
            cycle_id=cycle.cycle_id,
            project_id=project_id,
            run_id=run.run_id,
            run_number=run.run_number,
            status=run.status,
            prd_ref=cycle.prd_ref,
            squad_profile_id=cycle.squad_profile_id,
            squad_profile_snapshot_ref=snapshot_hash,
            task_flow_policy=body.task_flow_policy,
            resolved_config_hash=config_hash,
        )
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_cycles(project_id: str, status: CycleStatus | None = None):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        cycles = await registry.list_cycles(project_id, status=status)
        results = []
        for c in cycles:
            runs = await registry.list_runs(c.cycle_id)
            results.append(cycle_to_response(c, runs))
        return results
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("/{cycle_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_cycle(project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        cycle = await registry.get_cycle(cycle_id)
        runs = await registry.list_runs(cycle_id)
        return cycle_to_response(cycle, runs)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.post("/{cycle_id}/cancel", dependencies=[Depends(require_scopes(Scope.CYCLES_WRITE))])
async def cancel_cycle(project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        await registry.cancel_cycle(cycle_id)

        # SIP-0077: cycle.cancelled
        from squadops.api.runtime.deps import get_cycle_event_bus
        from squadops.events.types import EventType

        get_cycle_event_bus().emit(
            EventType.CYCLE_CANCELLED,
            entity_type="cycle",
            entity_id=cycle_id,
            context={"cycle_id": cycle_id, "project_id": project_id},
            payload={"project_id": project_id},
        )

        # #77: stop the orphaned Prefect flow run(s) for this cycle's runs so
        # workers don't keep executing a logically-cancelled cycle.
        from squadops.api.routes.cycles.cancellation import cancel_orphaned_flow_runs

        run_ids = [run.run_id for run in await registry.list_runs(cycle_id)]
        cancelled = await cancel_orphaned_flow_runs(project_id, cycle_id, run_ids)

        return {
            "status": "cancelled",
            "cycle_id": cycle_id,
            "prefect_flow_runs_cancelled": cancelled,
        }
    except CycleError as e:
        raise handle_cycle_error(e) from e
