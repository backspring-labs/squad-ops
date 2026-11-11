"""``/api/v1/workers`` over HTTP, as a worker calls it (SIP-0117 R3.3, R5.5).

Every answer is read strictly. A status this adapter doesn't expect, a body with a key missing
or of the wrong kind, and a 404 that isn't the route's own "no such session" each raise with
what was received. None is read as "nothing to do": a worker pointed at the wrong address
would otherwise poll it forever and look idle.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import Any

import httpx

from adapters.remote_execution.runtime_api_calls import (
    RuntimeApiCalls,
    as_object,
    error,
    error_code,
    field,
    instant,
    seconds,
    text,
)
from squadops.ports.remote_execution import WorkerApiPort
from squadops.remote_execution.models import RemoteOperationResult
from squadops.remote_execution.wire import (
    ERROR_RESULT_REFUSED,
    ERROR_SESSION_NOT_FOUND,
    request_from_wire,
    result_to_wire,
)
from squadops.remote_execution.workers import (
    Claim,
    Enrolment,
    Fence,
    FenceRefusal,
    LeaseReading,
    ResultReading,
    RuntimeAnswerUnreadable,
    UnknownSession,
    WorkerRefused,
    WorkerRegistration,
)
from squadops.runtime.models import RuntimeStatus

_SESSIONS = "/api/v1/workers/sessions"


class HttpWorkerApi(WorkerApiPort):
    def __init__(
        self,
        base_url: str,
        token: Callable[[], Awaitable[str]],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._calls = RuntimeApiCalls(
            base_url, token, caller="the worker's", refused=WorkerRefused, transport=transport
        )

    async def register(self, registration: WorkerRegistration) -> Enrolment:
        status, body = await self._post(
            _SESSIONS,
            {
                "worker_id": registration.worker_id,
                "platform": registration.platform,
                "tool_versions": dict(registration.tool_versions),
                "operations": [
                    {"provider": o.provider, "operation": o.operation}
                    for o in registration.operations
                ],
            },
        )
        if status != 201:
            raise _refused(status, body, _SESSIONS)
        return Enrolment(
            session_id=text(body, "session_id"),
            heartbeat=timedelta(seconds=seconds(body, "heartbeat_seconds")),
            lease=timedelta(seconds=seconds(body, "lease_seconds")),
        )

    async def heartbeat(self, session_id: str, runtime_status: RuntimeStatus) -> None:
        path = f"{_SESSIONS}/{session_id}/heartbeats"
        status, body = await self._post(path, {"runtime_status": runtime_status})
        self._expect_ok(status, body, path, session_id)
        if field(body, "lease") is not None:
            raise RuntimeAnswerUnreadable(
                f"a heartbeat that presented no claim was answered with a lease: {body!r}"
            )

    async def renew(
        self, session_id: str, runtime_status: RuntimeStatus, fence: Fence
    ) -> LeaseReading:
        path = f"{_SESSIONS}/{session_id}/heartbeats"
        status, body = await self._post(
            path, {"runtime_status": runtime_status, "fence": _fence(fence)}
        )
        self._expect_ok(status, body, path, session_id)
        lease = as_object(field(body, "lease"), "lease")
        refusal = field(lease, "refusal")
        held = field(lease, "held")
        if not isinstance(held, bool) or held != (refusal is None):
            raise RuntimeAnswerUnreadable(f"a lease that is held={held!r} with refusal={refusal!r}")
        expires_at = field(lease, "expires_at")
        cancel_requested = field(lease, "cancel_requested")
        if not isinstance(cancel_requested, bool):
            raise RuntimeAnswerUnreadable(f"cancel_requested is {cancel_requested!r}")
        return LeaseReading(
            refusal=None if refusal is None else _refusal(refusal),
            expires_at=None if expires_at is None else instant(expires_at, "lease.expires_at"),
            cancel_requested=cancel_requested,
        )

    async def claim(self, session_id: str) -> Claim | None:
        path = f"{_SESSIONS}/{session_id}/claims"
        status, body = await self._post(path, None)
        self._expect_ok(status, body, path, session_id)
        claimed = field(body, "claim")
        if claimed is None:
            return None
        claimed = as_object(claimed, "claim")
        attempt = field(claimed, "attempt")
        reconcile_first = field(claimed, "reconcile_first")
        if not isinstance(attempt, int) or isinstance(attempt, bool):
            raise RuntimeAnswerUnreadable(f"claim.attempt is {attempt!r}")
        if not isinstance(reconcile_first, bool):
            raise RuntimeAnswerUnreadable(f"claim.reconcile_first is {reconcile_first!r}")
        try:
            request = request_from_wire(field(claimed, "request"))
        except ValueError as e:
            raise RuntimeAnswerUnreadable(f"the claim's request can't be read: {e}") from e
        return Claim(
            fence=Fence(
                text(claimed, "operation_id"), attempt, session_id, text(claimed, "lease_id")
            ),
            request=request,
            lease_expires_at=instant(field(claimed, "lease_expires_at"), "claim.lease_expires_at"),
            reconcile_first=reconcile_first,
        )

    async def submit_result(self, fence: Fence, result: RemoteOperationResult) -> ResultReading:
        path = f"{_SESSIONS}/{fence.session_id}/results"
        status, body = await self._post(
            path, {"fence": _fence(fence), "result": result_to_wire(result)}
        )
        if status == 409 and error_code(body) == ERROR_RESULT_REFUSED:
            details = as_object(field(error(body), "details"), "error.details")
            return ResultReading(_refusal(field(details, "refusal")))
        if status != 200:
            raise _refused(status, body, path)
        accepted, replayed = field(body, "accepted"), field(body, "replayed")
        if accepted is not True or not isinstance(replayed, bool):
            raise RuntimeAnswerUnreadable(f"a result answered 200 with {body!r}")
        return ResultReading(None, replayed=replayed)

    async def close(self) -> None:
        await self._calls.close()

    async def _post(self, path: str, body: Mapping[str, Any] | None) -> tuple[int, Any]:
        return await self._calls.post(path, body)

    def _expect_ok(self, status: int, body: Any, path: str, session_id: str) -> None:
        if status == 404 and error_code(body) == ERROR_SESSION_NOT_FOUND:
            raise UnknownSession(session_id)
        if status != 200:
            raise _refused(status, body, path)


def _refused(status: int, body: Any, path: str) -> WorkerRefused:
    return WorkerRefused(f"HTTP {status} from {path}: {body!r}")


def _fence(fence: Fence) -> dict[str, Any]:
    return {
        "operation_id": fence.operation_id,
        "attempt": fence.attempt,
        "lease_id": fence.lease_id,
    }


def _refusal(value: Any) -> FenceRefusal:
    try:
        return FenceRefusal(value)
    except ValueError as e:
        raise RuntimeAnswerUnreadable(
            f"the refusal {value!r} is none of {', '.join(r.value for r in FenceRefusal)}"
        ) from e
