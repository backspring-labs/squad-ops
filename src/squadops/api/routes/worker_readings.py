"""``GET /api/v1/workers``: the worker registry, as an operator reads it (#3047).

During an overnight Campaign the first question about a remote operation is the worker's: is it
being heard from, what does it serve, what is it holding, and why was its last result refused.
These two routes answer it without a database shell. As every reader of the registry does, a
lease that ran out is ended first, so an operation is never shown held by a silent worker.

Both need ``workers:read``, a person's scope (admin, operator, viewer and the Campaign roles). A
worker's role doesn't hold it: the calls a worker makes are ``routes/workers.py``'s, under
``workers:serve``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_worker_registry
from squadops.api.worker_schemas import (
    HeldOperationDTO,
    RefusedResultDTO,
    ServedOperationDTO,
    WorkerReadingResponse,
)
from squadops.auth.models import Scope
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.workers import WorkerReading

router = APIRouter(
    prefix="/api/v1/workers",
    tags=["workers"],
    dependencies=[Depends(require_scopes(Scope.WORKERS_READ))],
)

ERROR_WORKER_NOT_FOUND = "WORKER_NOT_FOUND"


def _registry(request: Request) -> WorkerRegistry:
    registry = get_worker_registry(request)
    if registry is None:
        raise http_error(
            503, "WORKER_REGISTRY_UNAVAILABLE", "the worker registry is not configured"
        )
    return registry


def _response(reading: WorkerReading) -> WorkerReadingResponse:
    session = reading.session
    return WorkerReadingResponse(
        worker_id=session.worker_id,
        session_id=session.session_id,
        platform=session.platform,
        health=reading.health,
        reported_status=session.runtime_status,
        registered_at=session.registered_at,
        last_heartbeat_at=session.last_heartbeat_at,
        tool_versions=dict(session.tool_versions),
        operations=[
            ServedOperationDTO(provider=o.provider, operation=o.operation)
            for o in session.operations
        ],
        held=[
            HeldOperationDTO(
                operation_id=h.operation_id,
                provider=h.request.provider,
                operation=h.request.operation,
                attempt=h.attempt,
                max_attempts=h.max_attempts,
                lease_expires_at=h.lease_expires_at,
                cancel_requested=h.cancel_requested,
                origin=dict(h.origin),
                scenario_id=h.request.scenario.scenario_id,
            )
            for h in reading.held
        ],
        recent_refusals=[
            RefusedResultDTO(
                operation_id=r.fence.operation_id,
                attempt=r.fence.attempt,
                session_id=r.fence.session_id,
                refusal=r.refusal.value,
                received_at=r.received_at,
            )
            for r in reading.refusals
        ],
    )


@router.get("")
async def list_workers(request: Request) -> list[WorkerReadingResponse]:
    """Every live session, oldest registration first. A worker that registers again ends its
    earlier session, so each worker appears once."""
    return [_response(r) for r in await _registry(request).readings()]


@router.get("/{worker_id}")
async def show_worker(worker_id: str, request: Request) -> WorkerReadingResponse:
    """The worker's live session. A worker with none is not found: it never registered, or its
    session ended."""
    for reading in await _registry(request).readings():
        if reading.session.worker_id == worker_id:
            return _response(reading)
    raise http_error(
        404,
        ERROR_WORKER_NOT_FOUND,
        "no live session for this worker: it never registered, or its session ended",
        {"worker_id": worker_id},
    )
