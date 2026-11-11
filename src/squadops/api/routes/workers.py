"""``/api/v1/workers``: a remote-execution worker's calls (SIP-0117 R3.3, R5.3, R5.4).

A worker connects outward to these and nothing connects to it:

- **register** a session: its identity, platform, tool versions and the operations it serves;
- **heartbeat**: its health in the canonical vocabulary, and the lease of the claim it holds;
- **claim** at most one operation, under a lease;
- **result**: accepted only under the current operation, attempt, session and lease ids. A
  result whose ids aren't current is refused with the reason, and the refusal is recorded.

Every route needs ``workers:serve``, which the worker role alone holds. No person's role and
no squad agent's does.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_worker_registry
from squadops.api.worker_schemas import (
    ClaimDTO,
    ClaimResponse,
    FenceDTO,
    HeartbeatRequest,
    HeartbeatResponse,
    LeaseDTO,
    ResultRequest,
    ResultResponse,
    WorkerRegistrationRequest,
    WorkerSessionResponse,
)
from squadops.auth.models import Scope
from squadops.remote_execution import leasing
from squadops.remote_execution.registry import WorkerRegistry, cadence
from squadops.remote_execution.wire import request_to_wire, result_from_wire
from squadops.remote_execution.workers import (
    Fence,
    ServedOperation,
    UnknownSession,
    WorkerRegistration,
)

router = APIRouter(
    prefix="/api/v1/workers",
    tags=["workers"],
    dependencies=[Depends(require_scopes(Scope.WORKERS_SERVE))],
)


def _registry(request: Request) -> WorkerRegistry:
    registry = get_worker_registry(request)
    if registry is None:
        raise http_error(
            503, "WORKER_REGISTRY_UNAVAILABLE", "the worker registry is not configured"
        )
    return registry


def _unknown_session(session_id: str):
    return http_error(
        404,
        "WORKER_SESSION_NOT_FOUND",
        "no live session has this id: register again",
        {"session_id": session_id},
    )


def _fence(session_id: str, body: FenceDTO) -> Fence:
    return Fence(body.operation_id, body.attempt, session_id, body.lease_id)


@router.post("/sessions", status_code=201)
async def register(request: Request, body: WorkerRegistrationRequest) -> WorkerSessionResponse:
    """Register a session for the worker. A worker that registers again has restarted: its
    earlier session ends, with the claim it held."""
    registration = WorkerRegistration(
        worker_id=body.worker_id,
        platform=body.platform,
        tool_versions=body.tool_versions,
        operations=tuple(ServedOperation(o.provider, o.operation) for o in body.operations),
    )
    errors = leasing.registration_errors(registration)
    if errors:
        raise http_error(
            422,
            "WORKER_REGISTRATION_INVALID",
            "the registration can't be matched to work",
            {"errors": errors},
        )
    session = await _registry(request).register(registration)
    heartbeat, lease = cadence()
    return WorkerSessionResponse(
        session_id=session.session_id,
        worker_id=session.worker_id,
        registered_at=session.registered_at,
        heartbeat_seconds=heartbeat.total_seconds(),
        lease_seconds=lease.total_seconds(),
    )


@router.post("/sessions/{session_id}/heartbeats")
async def heartbeat(request: Request, session_id: str, body: HeartbeatRequest) -> HeartbeatResponse:
    """Report the worker's health, and renew the lease of the claim it holds."""
    try:
        reported = leasing.runtime_status(body.runtime_status)
    except ValueError:
        raise http_error(
            422,
            "RUNTIME_STATUS_INVALID",
            "runtime_status is outside the health vocabulary; busy is the lease, never a status",
            {"runtime_status": body.runtime_status, "known": list(leasing.RUNTIME_STATUSES)},
        ) from None
    fence = _fence(session_id, body.fence) if body.fence is not None else None
    try:
        reading = await _registry(request).heartbeat(session_id, reported, fence)
    except UnknownSession:
        raise _unknown_session(session_id) from None
    if reading is None:
        return HeartbeatResponse(lease=None)
    return HeartbeatResponse(
        lease=LeaseDTO(
            held=reading.refusal is None,
            refusal=reading.refusal.value if reading.refusal is not None else None,
            expires_at=reading.expires_at,
            cancel_requested=reading.cancel_requested,
        )
    )


@router.post("/sessions/{session_id}/claims")
async def claim(request: Request, session_id: str) -> ClaimResponse:
    """Claim the oldest queued operation the session serves, if there is one."""
    try:
        claimed = await _registry(request).claim(session_id)
    except UnknownSession:
        raise _unknown_session(session_id) from None
    if claimed is None:
        return ClaimResponse(claim=None)
    return ClaimResponse(
        claim=ClaimDTO(
            operation_id=claimed.fence.operation_id,
            attempt=claimed.fence.attempt,
            lease_id=claimed.fence.lease_id,
            lease_expires_at=claimed.lease_expires_at,
            reconcile_first=claimed.reconcile_first,
            request=request_to_wire(claimed.request),
        )
    )


@router.post("/sessions/{session_id}/results")
async def submit_result(request: Request, session_id: str, body: ResultRequest) -> ResultResponse:
    """Submit the result of the claim the session holds."""
    try:
        result = result_from_wire(body.result)
    except ValueError as e:
        raise http_error(
            422, "RESULT_INVALID", "the result can't be read", {"defect": str(e)}
        ) from None
    fence = _fence(session_id, body.fence)
    reading = await _registry(request).submit_result(fence, result)
    if reading.refusal is not None:
        raise http_error(
            409,
            "RESULT_REFUSED",
            "the result's ids are not the current ones for this operation; it was recorded "
            "and not accepted",
            {
                "refusal": reading.refusal.value,
                "operation_id": fence.operation_id,
                "attempt": fence.attempt,
            },
        )
    return ResultResponse(accepted=True, replayed=reading.replayed)
