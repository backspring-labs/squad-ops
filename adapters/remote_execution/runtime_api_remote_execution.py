"""The remote-execution port, through the runtime API (SIP-0117 R3.3, R5.6).

An agent's handler asks for one operation. This adapter queues it at
``/api/v1/remote-operations`` under the agent's service identity, reads it until it has its
result, and returns that result. The worker that runs it is on another machine and is never
called from here: it claims the operation from the same registry.

The request names its task and the send of it (#2932). The runtime queues one operation per
send, so asking again is safe: a create that got no answer is sent again, and the runtime
returns the operation the first one queued, if it did. Every call is refused once the send is
no longer the task's current one.

**What it returns, and what it raises.** The port's rule is that an operation that can't run
is ``not_executed`` with the reason, and one that may have started and has no result is
``interrupted``. Neither is a pass or a failure. So:

| what happens | the result |
|---|---|
| no worker serves the operation, or none is being heard from | ``not_executed``, with the registry's reason. Nothing is queued |
| the runtime gives no answer to the request to queue | it is asked again, until the wait ends |
| the runtime gives no answer to any request to queue within the wait | ``interrupted``: it may have been queued, and whether it ran is unknown. The task's next send stops it |
| the operation settles | its result, as the worker or the registry wrote it |
| no result within the wait | the operation is asked to stop. Queued, it settles ``not_executed``. Claimed, its worker answers ``interrupted`` or its lease runs out, within one lease's length |
| it is still unsettled one lease after being asked to stop | ``interrupted``, naming its state |
| the runtime can't be reached when the wait ends | ``interrupted``: it was queued, and whether it ran is unknown |
| the runtime no longer knows the operation | ``interrupted``, likewise |

A runtime that **refuses** the agent (its credentials, its scope, a request it can't read, a
send that is no longer the task's current one), or answers with a document this version can't
read, raises (``RequestRefused``, ``RuntimeAnswerUnreadable``): the task fails with the reason,
and nothing is read as an operation that merely didn't run.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

import httpx

from adapters.remote_execution.runtime_api_calls import (
    RuntimeApiCalls,
    as_object,
    error,
    error_code,
    field,
    seconds,
    text,
)
from squadops.ports.remote_execution import RemoteExecutionPort
from squadops.remote_execution.models import (
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.wire import (
    ERROR_NO_WORKER,
    ERROR_OPERATION_NOT_FOUND,
    request_to_wire,
    result_from_wire,
)
from squadops.remote_execution.workers import (
    OperationState,
    RequestRefused,
    RuntimeAnswerUnreadable,
    RuntimeUnreachable,
)

logger = logging.getLogger(__name__)

_OPERATIONS = "/api/v1/remote-operations"
#: How often a waiting requester reads its operation. The requester's own number: the lease's
#: length is the runtime's, told in every answer.
POLL_SECONDS = 2.0
#: How long a requester that is itself being stopped waits for its cancel to be answered.
_PARTING_CANCEL_SECONDS = 5.0


@dataclass(frozen=True)
class _Reading:
    """One answer about the operation."""

    state: OperationState
    result: RemoteOperationResult | None
    lease_seconds: float


class _OperationLost(Exception):
    """The runtime has no operation with the id it gave."""


class RuntimeApiRemoteExecution(RemoteExecutionPort):
    def __init__(
        self,
        base_url: str,
        token: Callable[[], Awaitable[str]] | None,
        *,
        origin: Mapping[str, str],
        wait: timedelta,
        max_attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """``origin`` says who asks, for the audit; the request names its task and send. ``wait`` is how
        long a result is waited for before the operation is asked to stop, and
        ``max_attempts`` how many times a worker may claim it."""
        if wait <= timedelta(0):
            raise ValueError(f"wait is {wait}; a result needs some time to arrive")
        if max_attempts < 1:
            raise ValueError(f"max_attempts is {max_attempts}; an operation needs at least one")
        self._calls = RuntimeApiCalls(
            base_url, token, caller="the agent's", refused=RequestRefused, transport=transport
        )
        self._origin = dict(origin)
        self._wait = wait
        self._max_attempts = max_attempts
        self._clock = clock
        self._sleep = sleep

    async def run_operation(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        deadline = self._clock() + self._wait.total_seconds()
        queued = await self._queue_within(request, deadline)
        if isinstance(queued, RemoteOperationResult):
            return queued
        operation_id, first = queued
        try:
            return await self._result_of(request, operation_id, first, deadline)
        except _OperationLost:
            return _ended(
                request,
                OperationStatus.INTERRUPTED,
                f"the runtime API no longer knows operation {operation_id}, which it had "
                "queued: whether it ran is unknown",
            )
        except asyncio.CancelledError:
            # This requester is being stopped, so nobody will read the result. Ask once for
            # the operation to stop too, and don't let that hold the stop up.
            await self._ask_to_stop_in_parting(operation_id)
            raise

    async def close(self) -> None:
        await self._calls.close()

    # ------------------------------------------------------------------ the wait

    async def _queue_within(
        self, request: RemoteOperationRequest, deadline: float
    ) -> tuple[str, _Reading] | RemoteOperationResult:
        """Ask for the operation until the runtime answers or the wait ends. Asking again is
        safe: the runtime keeps one operation per send."""
        while True:
            try:
                return await self._queue(request)
            except RuntimeUnreachable as e:
                if self._clock() >= deadline:
                    return _ended(
                        request,
                        OperationStatus.INTERRUPTED,
                        f"the runtime API gave no answer to any request to queue within "
                        f"{self._wait.total_seconds():g} s, so the operation may be queued and "
                        f"whether it ran is unknown: {e}",
                    )
                logger.warning(
                    "remote_operation_queue_unanswered",
                    extra={
                        "task_id": request.task_id,
                        "dispatch_id": request.dispatch_id,
                        "reason": str(e),
                    },
                )
            await self._sleep(POLL_SECONDS)

    async def _result_of(
        self,
        request: RemoteOperationRequest,
        operation_id: str,
        reading: _Reading,
        deadline: float,
    ) -> RemoteOperationResult:
        while reading.result is None and self._clock() < deadline:
            await self._sleep(POLL_SECONDS)
            reading = await self._read_again(operation_id, reading)
        if reading.result is not None:
            return reading.result
        return await self._stopped(request, operation_id, reading)

    async def _stopped(
        self, request: RemoteOperationRequest, operation_id: str, reading: _Reading
    ) -> RemoteOperationResult:
        """Ask for the operation to stop and return how that ended it."""
        waited = f"no result within {self._wait.total_seconds():g} s of asking"
        try:
            reading = await self._cancel(operation_id)
        except RuntimeUnreachable as e:
            return _ended(
                request,
                OperationStatus.INTERRUPTED,
                f"{waited}, and the runtime API can't be reached to stop operation "
                f"{operation_id}: whether it ran is unknown ({e})",
            )
        # A claimed operation's worker sees the cancel at its next heartbeat, and a worker
        # that has gone silent loses its lease: either settles it within one lease's length.
        grace = reading.lease_seconds
        grace_ends = self._clock() + grace
        while reading.result is None and self._clock() < grace_ends:
            await self._sleep(POLL_SECONDS)
            reading = await self._read_again(operation_id, reading)
        if reading.result is None:
            return _ended(
                request,
                OperationStatus.INTERRUPTED,
                f"{waited}; operation {operation_id} was asked to stop and is still "
                f"{reading.state.value} {grace:g} s later",
            )
        if reading.result.status is OperationStatus.COMPLETED:
            # It finished as the cancel was sent. Its result stands.
            return reading.result
        return replace(
            reading.result,
            reason=f"{reading.result.reason} (its requester asked it to stop: {waited})",
        )

    async def _read_again(self, operation_id: str, last: _Reading) -> _Reading:
        """The operation now, or ``last`` while the runtime gives no answer: a runtime that
        restarts keeps the operation and its lease, so the wait goes on. Each failed read is
        named, never passed over."""
        try:
            return await self._read(operation_id)
        except RuntimeUnreachable as e:
            logger.warning(
                "remote_operation_read_unanswered",
                extra={"operation_id": operation_id, "reason": str(e)},
            )
            return last

    async def _ask_to_stop_in_parting(self, operation_id: str) -> None:
        try:
            await asyncio.wait_for(
                self._calls.post(f"{_OPERATIONS}/{operation_id}/cancel", None),
                _PARTING_CANCEL_SECONDS,
            )
        except Exception as e:  # noqa: BLE001 - the stop this serves must not be replaced by it
            # Named, since the operation is then left for a worker to run with nobody waiting.
            logger.warning(
                "remote_operation_left_running",
                extra={
                    "operation_id": operation_id,
                    "reason": f"{type(e).__name__}: {e}",
                },
            )

    # ------------------------------------------------------------------ one call each

    async def _queue(
        self, request: RemoteOperationRequest
    ) -> tuple[str, _Reading] | RemoteOperationResult:
        """The queued operation's id and first reading, or the result when no worker can run
        it. A send that already asked is answered 200 with the operation it asked for."""
        status, body = await self._calls.post(
            _OPERATIONS,
            {
                "request": request_to_wire(request),
                "origin": dict(self._origin),
                "max_attempts": self._max_attempts,
            },
        )
        if status == 409 and error_code(body) == ERROR_NO_WORKER:
            details = as_object(field(error(body), "details"), "error.details")
            return _ended(request, OperationStatus.NOT_EXECUTED, text(details, "reason"))
        if status not in (200, 201):
            raise self._calls.refusal(status, body, _OPERATIONS)
        return text(body, "operation_id"), _reading(body)

    async def _read(self, operation_id: str) -> _Reading:
        path = f"{_OPERATIONS}/{operation_id}"
        status, body = await self._calls.get(path)
        return self._answer(status, body, path, operation_id)

    async def _cancel(self, operation_id: str) -> _Reading:
        path = f"{_OPERATIONS}/{operation_id}/cancel"
        status, body = await self._calls.post(path, None)
        return self._answer(status, body, path, operation_id)

    def _answer(self, status: int, body: Any, path: str, operation_id: str) -> _Reading:
        if status == 404 and error_code(body) == ERROR_OPERATION_NOT_FOUND:
            raise _OperationLost(operation_id)
        if status != 200:
            raise self._calls.refusal(status, body, path)
        answered = text(body, "operation_id")
        if answered != operation_id:
            raise RuntimeAnswerUnreadable(
                f"asked about operation {operation_id} and answered about {answered}"
            )
        return _reading(body)


def _reading(body: Any) -> _Reading:
    raw_state = text(body, "state")
    try:
        state = OperationState(raw_state)
    except ValueError as e:
        raise RuntimeAnswerUnreadable(
            f"state is {raw_state!r}, and it is one of "
            f"{', '.join(member.value for member in OperationState)}"
        ) from e
    raw_result = field(body, "result")
    if (state is OperationState.SETTLED) != (raw_result is not None):
        raise RuntimeAnswerUnreadable(
            f"an operation that is {state.value} with result {raw_result!r}: only a settled "
            "one has a result"
        )
    result = None
    if raw_result is not None:
        try:
            result = result_from_wire(raw_result)
        except ValueError as e:
            raise RuntimeAnswerUnreadable(f"the operation's result can't be read: {e}") from e
    return _Reading(state, result, seconds(body, "lease_seconds"))


def _ended(
    request: RemoteOperationRequest, status: OperationStatus, reason: str
) -> RemoteOperationResult:
    return RemoteOperationResult(status=status, reason=reason, dispatch_id=request.dispatch_id)
