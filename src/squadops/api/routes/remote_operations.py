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

**Only the task's current send** (R5.6). A request names its task and the send of it (the
dispatch id the runtime minted, #2932). Every route answers only while that send is the one the
runtime's reply router is waiting on for the task. One client identity serves all of the squad's
agents, so the send is what tells one requester from another. An earlier send's reply would be
dropped as stale, so its operation is read by nobody: its calls are refused, and a newer send's
create stops its operation. A create the send already made returns the operation it made (200),
so a requester that lost the answer, or restarted, reads the one it has.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_reply_router, get_worker_registry
from squadops.api.worker_schemas import RemoteOperationCreate, RemoteOperationResponse
from squadops.auth.models import Scope
from squadops.execution.reply_router import ReplyRouter
from squadops.remote_execution.models import RemoteOperationRequest
from squadops.remote_execution.registry import WorkerRegistry, cadence
from squadops.remote_execution.wire import (
    ERROR_NO_WORKER,
    ERROR_OPERATION_NOT_FOUND,
    request_from_wire,
    result_to_wire,
)
from squadops.remote_execution.workers import (
    NoWorker,
    QueuedOperation,
    SendConflict,
    UnknownOperation,
)

router = APIRouter(
    prefix="/api/v1/remote-operations",
    tags=["remote-operations"],
    dependencies=[Depends(require_scopes(Scope.OPERATIONS_REQUEST))],
)

#: The origin key the route writes itself: the identity the request was made under.
ORIGIN_REQUESTED_BY = "requested_by"
#: The send named isn't the task's current one, so nothing is done under it.
ERROR_SEND_NOT_CURRENT = "REMOTE_OPERATION_SEND_NOT_CURRENT"
#: The send already asked, with a different request.
ERROR_SEND_CONFLICT = "REMOTE_OPERATION_SEND_CONFLICT"


def _registry(request: Request) -> WorkerRegistry:
    registry = get_worker_registry(request)
    if registry is None:
        raise http_error(
            503, "WORKER_REGISTRY_UNAVAILABLE", "the worker registry is not configured"
        )
    return registry


def _reply_router(request: Request) -> ReplyRouter:
    router = get_reply_router(request)
    if router is None:
        raise http_error(
            503, "REPLY_ROUTER_UNAVAILABLE", "the runtime holds no task's current send"
        )
    return router


def _require_current(request: Request, operation_request: RemoteOperationRequest) -> None:
    """Refuse a call made under a send that isn't its task's current one."""
    task_id, dispatch_id = operation_request.task_id, operation_request.dispatch_id
    current = _reply_router(request).current_dispatch(task_id)
    if current != dispatch_id:
        raise http_error(
            403,
            ERROR_SEND_NOT_CURRENT,
            "the runtime is not waiting on this send of the task, so nothing is done under it",
            {"task_id": task_id, "dispatch_id": dispatch_id, "waiting": current is not None},
        )


async def _current_operation(request: Request, operation_id: str) -> QueuedOperation:
    """The operation, when it was asked for by its task's current send."""
    try:
        operation = await _registry(request).operation(operation_id)
    except UnknownOperation:
        raise _unknown(operation_id) from None
    _require_current(request, operation.request)
    return operation


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
async def create(
    request: Request, response: Response, body: RemoteOperationCreate
) -> RemoteOperationResponse:
    """Queue an operation for a worker that serves it: once per send of its task."""
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
    _require_current(request, operation_request)
    origin = dict(body.origin)
    identity = getattr(request.state, "identity", None)
    if identity is not None:
        # The route's own word on who asked, over whatever the body said under that key.
        origin[ORIGIN_REQUESTED_BY] = identity.user_id
    try:
        queued = await _registry(request).enqueue(
            operation_request, origin, max_attempts=body.max_attempts, only_with_worker=True
        )
    except SendConflict as e:
        raise http_error(
            409,
            ERROR_SEND_CONFLICT,
            "this send already asked for an operation, with a different request",
            {"defect": str(e)},
        ) from None
    if isinstance(queued, NoWorker):
        raise http_error(
            409,
            ERROR_NO_WORKER,
            "no worker can run the operation now; nothing was queued",
            {"reason": queued.reason, "unreachable": list(queued.unreachable)},
        )
    if queued.repeated:
        response.status_code = 200
    return _response(queued.operation)


@router.get("/{operation_id}")
async def read(request: Request, operation_id: str) -> RemoteOperationResponse:
    """The operation as it stands. A lease that ran out is ended first, so the answer never
    shows an operation held by a worker that stopped renewing it."""
    return _response(await _current_operation(request, operation_id))


@router.post("/{operation_id}/cancel")
async def cancel(request: Request, operation_id: str) -> RemoteOperationResponse:
    """Ask for the operation to stop, and return it as that left it. Asking again, or asking
    of one that already has its result, changes nothing."""
    await _current_operation(request, operation_id)
    try:
        return _response(await _registry(request).cancel(operation_id))
    except UnknownOperation:
        raise _unknown(operation_id) from None
