"""
Run API routes (SIP-0064 §9.4).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from squadops.api.routes.cycles.dtos import GateDecisionRequest
from squadops.api.routes.cycles.errors import handle_cycle_error
from squadops.api.routes.cycles.mapping import run_to_response
from squadops.cycles.lifecycle import compute_config_hash
from squadops.cycles.models import CycleError, GateDecision, Run

router = APIRouter(prefix="/api/v1/projects/{project_id}/cycles/{cycle_id}/runs", tags=["runs"])


@router.post("")
async def create_run(project_id: str, cycle_id: str):
    """Create a new Run (retry) for an existing Cycle."""
    from squadops.api.runtime.deps import get_cycle_registry

    try:
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
        )
        created = await registry.create_run(run)
        return run_to_response(created)
    except CycleError as e:
        raise handle_cycle_error(e) from e


@router.get("")
async def list_runs(project_id: str, cycle_id: str):
    from squadops.api.runtime.deps import get_cycle_registry

    try:
        registry = get_cycle_registry()
        runs = await registry.list_runs(cycle_id)
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
        return run_to_response(updated)
    except CycleError as e:
        raise handle_cycle_error(e) from e
