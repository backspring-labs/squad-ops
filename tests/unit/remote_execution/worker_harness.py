"""A worker under test: the runtime in-process, a tool that does what the test says, and the
test's own clock (SIP-0117 R5.5).

``RegistryWorkerApi`` is the runtime as a worker calls it, over the real ``WorkerRegistry``, so
every rule a worker meets is the real one. ``ScriptedRunner`` is a tool. ``Serving`` runs
``Worker.serve()``, the call the worker's process makes, until the test has seen what it
waits for.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timedelta

from squadops.ports.remote_execution import OperationRunnerPort, WorkerApiPort
from squadops.remote_execution.models import RemoteOperationRequest, RemoteOperationResult
from squadops.remote_execution.registry import WorkerRegistry, cadence
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.workers import (
    Enrolment,
    RuntimeUnreachable,
    ServedOperation,
)
from tests.unit.remote_execution.registry_contract import PLAY, Clock, passing


def sleeping_on(clock: Clock) -> Callable[[float], Awaitable[None]]:
    """A sleep that passes the test's time, and lets everything else take a turn."""

    async def sleep(seconds: float) -> None:
        clock.advance(seconds)
        await asyncio.sleep(0)

    return sleep


class RegistryWorkerApi(WorkerApiPort):
    """The worker's calls, straight onto the registry. ``down`` names the calls that get no
    answer, as a cut network would leave them."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self._registry = registry
        self.down: set[str] = set()
        self.renewals = 0

    def _reach(self, call: str) -> None:
        if call in self.down:
            raise RuntimeUnreachable(f"the test cut {call}")

    async def register(self, registration):
        self._reach("register")
        session = await self._registry.register(registration)
        heartbeat, lease = cadence()
        return Enrolment(session.session_id, heartbeat, lease)

    async def heartbeat(self, session_id, runtime_status):
        self._reach("heartbeat")
        await self._registry.heartbeat(session_id, runtime_status, None)

    async def renew(self, session_id, runtime_status, fence):
        self._reach("renew")
        self.renewals += 1
        return await self._registry.heartbeat(session_id, runtime_status, fence)

    async def claim(self, session_id):
        self._reach("claim")
        return await self._registry.claim(session_id)

    async def submit_result(self, fence, result):
        self._reach("submit_result")
        return await self._registry.submit_result(fence, result)

    async def close(self):
        return None


class ScriptedRunner(OperationRunnerPort):
    """A tool. Each run lasts ``run_seconds`` of the test's time (forever when ``None``) and
    then returns ``result``, or raises ``raises`` at once."""

    def __init__(self, clock: Clock, *served: ServedOperation) -> None:
        self._clock = clock
        self._served = served or (PLAY,)
        self.run_seconds: float | None = 0
        self.result: RemoteOperationResult | None = None
        self.raises: Exception | None = None
        self.reset_raises: Exception | None = None
        self.runs: list[RemoteOperationRequest] = []
        self.resets = 0
        #: When each run was stopped before it ended.
        self.stopped_at: list[datetime] = []

    def serves(self):
        return self._served

    async def tool_versions(self):
        return {"scripted-editor": "7.2"}

    async def health(self):
        return "online"

    async def reset(self):
        if self.reset_raises is not None:
            raise self.reset_raises
        self.resets += 1

    async def run(self, request):
        self.runs.append(request)
        if self.raises is not None:
            raise self.raises
        started = self._clock()
        try:
            while self.run_seconds is None or self._clock() < started + timedelta(
                seconds=self.run_seconds
            ):
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            self.stopped_at.append(self._clock())
            raise
        return self.result or passing(request.dispatch_id)


class Serving:
    """``Worker.serve()`` running beside the test. ``until`` gives it turns until the test's
    condition holds, and fails when it never does or the worker stops with an error."""

    def __init__(self, worker: Worker) -> None:
        self._worker = worker
        self._task: asyncio.Future | None = None

    async def __aenter__(self) -> Serving:
        self._task = asyncio.ensure_future(self._worker.serve())
        return self

    async def __aexit__(self, *exc) -> None:
        assert self._task is not None
        if self._task.done():
            return  # what it raised was the test's to read, through until() or ended_with()
        self._task.cancel()
        for _ in range(200):
            if self._task.done():
                break
            await asyncio.sleep(0)
        else:
            raise AssertionError("the worker kept serving after it was told to stop")
        with suppress(asyncio.CancelledError):
            await self._task

    async def until(self, holds: Callable[[], Awaitable[bool]], *, turns: int = 5000) -> None:
        assert self._task is not None
        for _ in range(turns):
            if self._task.done():
                self._task.result()
                raise AssertionError("the worker stopped serving")
            if await holds():
                return
            await asyncio.sleep(0)
        raise AssertionError(f"not reached in {turns} turns")

    async def ended_with(self, *, turns: int = 5000) -> BaseException | None:
        """What ``serve()`` raised, once it has stopped."""
        assert self._task is not None
        for _ in range(turns):
            if self._task.done():
                return self._task.exception()
            await asyncio.sleep(0)
        raise AssertionError(f"the worker was still serving after {turns} turns")
