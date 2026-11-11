"""``/api/v1/workers`` over HTTP, as a worker calls it (SIP-0117 R3.3, R5.5).

Every answer is read strictly. A status this adapter doesn't expect, a body with a key missing
or of the wrong kind, and a 404 that isn't the route's own "no such session" each raise with
what was received. None is read as "nothing to do": a worker pointed at the wrong address
would otherwise poll it forever and look idle.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import httpx

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
    RuntimeUnreachable,
    UnknownSession,
    WorkerRefused,
    WorkerRegistration,
)
from squadops.runtime.models import RuntimeStatus

_SESSIONS = "/api/v1/workers/sessions"
#: A call that takes longer than this got no answer. Well inside a lease, so a renewal that
#: hangs is tried again before the lease runs out.
_TIMEOUT_SECONDS = 10.0


class HttpWorkerApi(WorkerApiPort):
    def __init__(
        self,
        base_url: str,
        token: Callable[[], Awaitable[str]],
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=_TIMEOUT_SECONDS, transport=transport
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
            session_id=_text(body, "session_id"),
            heartbeat=timedelta(seconds=_number(body, "heartbeat_seconds")),
            lease=timedelta(seconds=_number(body, "lease_seconds")),
        )

    async def heartbeat(self, session_id: str, runtime_status: RuntimeStatus) -> None:
        path = f"{_SESSIONS}/{session_id}/heartbeats"
        status, body = await self._post(path, {"runtime_status": runtime_status})
        self._expect_ok(status, body, path, session_id)
        if _field(body, "lease") is not None:
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
        lease = _object(_field(body, "lease"), "lease")
        refusal = _field(lease, "refusal")
        held = _field(lease, "held")
        if not isinstance(held, bool) or held != (refusal is None):
            raise RuntimeAnswerUnreadable(f"a lease that is held={held!r} with refusal={refusal!r}")
        expires_at = _field(lease, "expires_at")
        cancel_requested = _field(lease, "cancel_requested")
        if not isinstance(cancel_requested, bool):
            raise RuntimeAnswerUnreadable(f"cancel_requested is {cancel_requested!r}")
        return LeaseReading(
            refusal=None if refusal is None else _refusal(refusal),
            expires_at=None if expires_at is None else _instant(expires_at, "lease.expires_at"),
            cancel_requested=cancel_requested,
        )

    async def claim(self, session_id: str) -> Claim | None:
        path = f"{_SESSIONS}/{session_id}/claims"
        status, body = await self._post(path, None)
        self._expect_ok(status, body, path, session_id)
        claimed = _field(body, "claim")
        if claimed is None:
            return None
        claimed = _object(claimed, "claim")
        attempt = _field(claimed, "attempt")
        reconcile_first = _field(claimed, "reconcile_first")
        if not isinstance(attempt, int) or isinstance(attempt, bool):
            raise RuntimeAnswerUnreadable(f"claim.attempt is {attempt!r}")
        if not isinstance(reconcile_first, bool):
            raise RuntimeAnswerUnreadable(f"claim.reconcile_first is {reconcile_first!r}")
        try:
            request = request_from_wire(_field(claimed, "request"))
        except ValueError as e:
            raise RuntimeAnswerUnreadable(f"the claim's request can't be read: {e}") from e
        return Claim(
            fence=Fence(
                _text(claimed, "operation_id"), attempt, session_id, _text(claimed, "lease_id")
            ),
            request=request,
            lease_expires_at=_instant(
                _field(claimed, "lease_expires_at"), "claim.lease_expires_at"
            ),
            reconcile_first=reconcile_first,
        )

    async def submit_result(self, fence: Fence, result: RemoteOperationResult) -> ResultReading:
        path = f"{_SESSIONS}/{fence.session_id}/results"
        status, body = await self._post(
            path, {"fence": _fence(fence), "result": result_to_wire(result)}
        )
        if status == 409 and _error_code(body) == ERROR_RESULT_REFUSED:
            details = _object(_field(_error(body), "details"), "error.details")
            return ResultReading(_refusal(_field(details, "refusal")))
        if status != 200:
            raise _refused(status, body, path)
        accepted, replayed = _field(body, "accepted"), _field(body, "replayed")
        if accepted is not True or not isinstance(replayed, bool):
            raise RuntimeAnswerUnreadable(f"a result answered 200 with {body!r}")
        return ResultReading(None, replayed=replayed)

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ one call

    async def _post(self, path: str, body: Mapping[str, Any] | None) -> tuple[int, Any]:
        """The status and the JSON body. No answer, or a server failure, is ``RuntimeUnreachable``."""
        bearer = await self._bearer()
        try:
            reply = await self._client.post(
                path, json=body, headers={"Authorization": f"Bearer {bearer}"}
            )
        except httpx.TransportError as e:
            raise RuntimeUnreachable(f"no answer from {path}: {type(e).__name__}: {e}") from e
        if reply.status_code >= 500:
            raise RuntimeUnreachable(f"HTTP {reply.status_code} from {path}: {reply.text[:300]}")
        try:
            return reply.status_code, reply.json()
        except ValueError as e:
            raise RuntimeAnswerUnreadable(
                f"HTTP {reply.status_code} from {path} with a body that isn't JSON: "
                f"{reply.text[:300]!r}"
            ) from e

    async def _bearer(self) -> str:
        try:
            return await self._token()
        except httpx.TransportError as e:
            raise RuntimeUnreachable(
                f"no answer from the identity provider: {type(e).__name__}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status >= 500:
                raise RuntimeUnreachable(f"HTTP {status} from the identity provider") from e
            raise WorkerRefused(
                f"the identity provider refused the worker's client credentials (HTTP {status}): "
                f"{e.response.text[:300]}"
            ) from e

    def _expect_ok(self, status: int, body: Any, path: str, session_id: str) -> None:
        if status == 404 and _error_code(body) == ERROR_SESSION_NOT_FOUND:
            raise UnknownSession(session_id)
        if status != 200:
            raise _refused(status, body, path)


def _refused(status: int, body: Any, path: str) -> WorkerRefused:
    return WorkerRefused(f"HTTP {status} from {path}: {body!r}")


def _error(body: Any) -> Mapping[str, Any]:
    """The standard error envelope's ``error`` object (``squadops.api.errors``)."""
    return _object(_field(_object(_field(body, "detail"), "detail"), "error"), "detail.error")


def _error_code(body: Any) -> str | None:
    """The envelope's code, or ``None`` when the body isn't the envelope: a 404 from an address
    that isn't the runtime API has none, and is then no route's "not found"."""
    try:
        return _text(_error(body), "code")
    except RuntimeAnswerUnreadable:
        return None


def _fence(fence: Fence) -> dict[str, Any]:
    return {
        "operation_id": fence.operation_id,
        "attempt": fence.attempt,
        "lease_id": fence.lease_id,
    }


def _object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeAnswerUnreadable(f"{where} is {value!r}, and an object was expected")
    return value


def _field(body: Any, key: str) -> Any:
    body = _object(body, "the answer")
    if key not in body:
        raise RuntimeAnswerUnreadable(f"the answer has no {key!r}: {dict(body)!r}")
    return body[key]


def _text(body: Any, key: str) -> str:
    value = _field(body, key)
    if not isinstance(value, str) or not value:
        raise RuntimeAnswerUnreadable(f"{key} is {value!r}, and text was expected")
    return value


def _number(body: Any, key: str) -> float:
    value = _field(body, key)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise RuntimeAnswerUnreadable(f"{key} is {value!r}, and a number of seconds was expected")
    return float(value)


def _instant(value: Any, where: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value)
    except (TypeError, ValueError) as e:
        raise RuntimeAnswerUnreadable(f"{where} is {value!r}, and a time was expected") from e
    if instant.tzinfo is None:
        raise RuntimeAnswerUnreadable(f"{where} is {value!r}, which names no time zone")
    return instant


def _refusal(value: Any) -> FenceRefusal:
    try:
        return FenceRefusal(value)
    except ValueError as e:
        raise RuntimeAnswerUnreadable(
            f"the refusal {value!r} is none of {', '.join(r.value for r in FenceRefusal)}"
        ) from e
