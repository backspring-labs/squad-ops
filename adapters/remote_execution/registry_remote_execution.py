"""The remote-execution port, straight into the worker registry (SIP-0117 R5.4; #3053).

The runtime runs Campaign acceptance, and the runtime holds the registry. So when acceptance asks
for a scenario on an increment's overlay, it queues straight into ``WorkerRegistry`` with no HTTP
leg back into itself. An agent's handler asks through the runtime API instead
(``runtime_api_remote_execution``). The wait is the same for both: ``remote_execution.waiting``.

**Who asks, and which ask supersedes another.** The registry keys an operation on (task id,
dispatch id), and a newer send of a task stops every unsettled operation of that task. Acceptance
names each ask ``campaign:<campaign>:<increment>:<criterion>:<side>`` with a dispatch id per
evaluation (``models.acceptance_task_id``), so two criteria or two sides never stop each other, and a
re-evaluation stops the older one's operation.

| what happens | the result |
|---|---|
| no worker serves the operation, or none is being heard from | ``not_executed``, with the registry's reason. Nothing is queued |
| the operation settles | its result, as the worker or the registry wrote it |
| no result within the wait | the operation is asked to stop, then read for one lease's length: its result, or ``interrupted`` naming its state |
| the registry no longer knows the operation | ``interrupted``: whether it ran is unknown |
| the requester itself is stopped | the operation is asked to stop, and the stop goes on |
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta

from squadops.ports.remote_execution import RemoteExecutionPort
from squadops.remote_execution.models import (
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.registry import WorkerRegistry, cadence
from squadops.remote_execution.waiting import OperationReading, await_result, ended
from squadops.remote_execution.workers import NoWorker, QueuedOperation, UnknownOperation

logger = logging.getLogger(__name__)


class RegistryRemoteExecution(RemoteExecutionPort):
    def __init__(
        self,
        registry: WorkerRegistry,
        *,
        origin: Mapping[str, str],
        wait: timedelta,
        max_attempts: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """``origin`` says who asks, for the audit. ``wait`` is how long a result is waited for
        before the operation is asked to stop, and ``max_attempts`` how many times a worker may
        claim it."""
        if wait <= timedelta(0):
            raise ValueError(f"wait is {wait}; a result needs some time to arrive")
        if max_attempts < 1:
            raise ValueError(f"max_attempts is {max_attempts}; an operation needs at least one")
        self._registry = registry
        self._origin = dict(origin)
        self._wait = wait
        self._max_attempts = max_attempts
        self._clock = clock
        self._sleep = sleep
        self._lease_seconds = cadence()[1].total_seconds()

    async def run_operation(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        deadline = self._clock() + self._wait.total_seconds()
        queued = await self._registry.enqueue(
            request, self._origin, max_attempts=self._max_attempts, only_with_worker=True
        )
        if isinstance(queued, NoWorker):
            return ended(request, OperationStatus.NOT_EXECUTED, queued.reason)
        operation_id = queued.operation.operation_id
        try:
            return await await_result(
                request,
                operation_id,
                self._reading(queued.operation),
                deadline=deadline,
                waited_for=self._wait.total_seconds(),
                read=lambda _last: self._read(operation_id),
                cancel=lambda: self._cancel(operation_id),
                clock=self._clock,
                sleep=self._sleep,
            )
        except UnknownOperation:
            return ended(
                request,
                OperationStatus.INTERRUPTED,
                f"the registry no longer knows operation {operation_id}, which it had queued: "
                "whether it ran is unknown",
            )
        except asyncio.CancelledError:
            # Nobody will read the result now. Ask the operation to stop too, without holding
            # this stop up on it.
            await self._ask_to_stop_in_parting(operation_id)
            raise

    def _reading(self, operation: QueuedOperation) -> OperationReading:
        return OperationReading(operation.state, operation.result, self._lease_seconds)

    async def _read(self, operation_id: str) -> OperationReading:
        return self._reading(await self._registry.operation(operation_id))

    async def _cancel(self, operation_id: str) -> OperationReading:
        return self._reading(await self._registry.cancel(operation_id))

    async def _ask_to_stop_in_parting(self, operation_id: str) -> None:
        try:
            await self._registry.cancel(operation_id)
        except Exception as e:  # noqa: BLE001 - the stop this serves must not be replaced by it
            logger.warning(
                "remote_operation_left_running",
                extra={"operation_id": operation_id, "reason": f"{type(e).__name__}: {e}"},
            )
