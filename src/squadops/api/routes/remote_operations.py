"""``/api/v1/remote-operations``: a requester's calls (SIP-0117 R3.3, R5.6).

The handler of ``qa.run_remote_operation`` runs in an agent, and a worker on another machine
runs the operation. These routes are how the one's request reaches the other's queue:

- **create** queues an operation for a worker that serves it. With no such worker being heard
  from, nothing is queued, and the answer says which it is;
- **read** returns the operation as it stands, with its result once it has one;
- **cancel** asks for it to stop. A queued operation settles as ``not_executed`` at once. A
  claimed one is marked: its worker sees that at its next heartbeat and submits
  ``interrupted``.

Every route needs ``operations:request``, which the agent role alone holds. A worker's role
doesn't, so a worker can't queue work for itself, and no person's role does.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_worker_registry
from squadops.api.worker_schemas import RemoteOperationCreate, RemoteOperationResponse
from squadops.auth.models import Scope
from squadops.remote_execution.registry import WorkerRegistry, cadence
from squadops.remote_execution.wire import (
    ERROR_NO_WORKER,
    ERROR_OPERATION_NOT_FOUND,
    request_from_wire,
    result_to_wire,
)
from squadops.remote_execution.workers import QueuedOperation, UnknownOperation

router = APIRouter(
    prefix="/api/v1/remote-operations",
    tags=["remote-operations"],
    dependencies=[Depends(require_scopes(Scope.OPERATIONS_REQUEST))],
)

#: The origin key the route writes itself: the identity the request was made under.
ORIGIN_REQUESTED_BY = "requested_by"


def _registry(request: Request) -> WorkerRegistry:
    registry = get_worker_registry(request)
    if registry is None:
        raise http_error(
            503, "WORKER_REGISTRY_UNAVAILABLE", "the worker registry is not configured"
        )
    return registry


def _unknown(operation_id: str):
    return http_error(
        404,
        ERROR_OPERATION_NOT_FOUND,
        "no remote operation has this id",
        {"operation_id": operation_id},
    )


def _response(operation: QueuedOperation) -> RemoteOperationResponse:
    _, lease = cadence()
    return RemoteOperationResponse(
        operation_id=operation.operation_id,
        state=operation.state.value,
        attempt=operation.attempt,
        max_attempts=operation.max_attempts,
        cancel_requested=operation.cancel_requested,
        created_at=operation.created_at,
        settled_at=operation.settled_at,
        result=result_to_wire(operation.result) if operation.result is not None else None,
        lease_seconds=lease.total_seconds(),
    )


@router.post("", status_code=201)
async def create(request: Request, body: RemoteOperationCreate) -> RemoteOperationResponse:
    """Queue an operation for a worker that serves it."""
    try:
        operation_request = request_from_wire(body.request)
    except ValueError as e:
        raise http_error(
            422, "OPERATION_REQUEST_INVALID", "the request can't be read", {"defect": str(e)}
        ) from None
    blank = sorted(k for k, v in body.origin.items() if not k.strip() or not v.strip())
    if not body.origin or blank:
        raise http_error(
            422,
            "OPERATION_ORIGIN_INVALID",
            "origin says who asked, for the audit: it is required, and every key and value "
            "of it is text",
            {"blank": blank},
        )
    registry = _registry(request)
    no_worker = await registry.no_worker_for(
        operation_request.provider, operation_request.operation
    )
    if no_worker is not None:
        raise http_error(
            409,
            ERROR_NO_WORKER,
            "no worker can run the operation now; nothing was queued",
            {"reason": no_worker.reason, "unreachable": list(no_worker.unreachable)},
        )
    origin = dict(body.origin)
    identity = getattr(request.state, "identity", None)
    if identity is not None:
        # The route's own word on who asked, over whatever the body said under that key.
        origin[ORIGIN_REQUESTED_BY] = identity.user_id
    operation = await registry.enqueue(operation_request, origin, max_attempts=body.max_attempts)
    return _response(operation)


@router.get("/{operation_id}")
async def read(request: Request, operation_id: str) -> RemoteOperationResponse:
    """The operation as it stands. A lease that ran out is ended first, so the answer never
    shows an operation held by a worker that stopped renewing it."""
    try:
        return _response(await _registry(request).operation(operation_id))
    except UnknownOperation:
        raise _unknown(operation_id) from None


@router.post("/{operation_id}/cancel")
async def cancel(request: Request, operation_id: str) -> RemoteOperationResponse:
    """Ask for the operation to stop, and return it as that left it. Asking again, or asking
    of one that already has its result, changes nothing."""
    try:
        return _response(await _registry(request).cancel(operation_id))
    except UnknownOperation:
        raise _unknown(operation_id) from None
