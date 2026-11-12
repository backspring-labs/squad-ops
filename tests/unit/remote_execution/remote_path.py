"""The remote-execution path end to end, with its faults (#3050, slice 1; SIP-0117 R3.3, R5.6).

One composition, from the squad's side to the worker's, every hop the real one:

- the agent's ``RuntimeApiRemoteExecution`` (what ``qa.run_remote_operation``'s handler is
  given), over HTTP into
- the runtime's real ``/api/v1/remote-operations`` and ``/api/v1/workers`` routes
  (``tests.unit.api.worker_world``), over
- the real ``WorkerRegistry`` on the store the subclass names, and
- ``Worker.serve()`` (what ``worker_main`` runs) over ``HttpWorkerApi``, back into the same
  routes, with #3044's ``fixture/declared_scenario`` as its tool.

Every seam is proved on its own elsewhere. This is the path a live cycle takes through all of
them, which is where #1250, #1256 and #1261 were found. Each fault is read by its name.

The clock is the test's: every sleep on the path passes its time and yields, so leases run out
when the path's own waiting says so.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta

import httpx
import pytest

from adapters.remote_execution.fixture_operation_runner import (
    OPERATION,
    PROVIDER,
    FixtureOperationRunner,
)
from adapters.remote_execution.http_worker_api import HttpWorkerApi
from adapters.remote_execution.runtime_api_remote_execution import RuntimeApiRemoteExecution
from squadops.auth.models import Role
from squadops.remote_execution import leasing
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.scenario import staged_revision
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.workers import (
    FenceRefusal,
    OperationState,
    ServedOperation,
    WorkerRegistration,
)
from tests.unit.api.worker_world import World, identity
from tests.unit.remote_execution.registry_contract import T0
from tests.unit.remote_execution.scenario_fixture import OPEN, door_opens, tree
from tests.unit.remote_execution.worker_harness import ScriptedRunner, Serving, sleeping_on

BASE_URL = "http://runtime-api"
DECLARED = ServedOperation(PROVIDER, OPERATION)
TASK = "task_play_1"
#: Longer than a lease, as a deploy's (900 s against 60 s): a lease that runs out is read before the
#: requester gives up.
WAIT = 300


class _Line(httpx.AsyncBaseTransport):
    """One caller's line to the runtime: the app, unless the test cuts it (``down``), or drops
    the answer to one request after the runtime handled it (``drop_answer_to``)."""

    def __init__(self, app) -> None:
        self._inner = httpx.ASGITransport(app=app)
        self.down = False
        self.drop_answer_to: tuple[str, str] | None = None
        self.dropped = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("the test cut this line", request=request)
        response = await self._inner.handle_async_request(request)
        if self.drop_answer_to == (request.method, request.url.path):
            self.drop_answer_to = None
            self.dropped += 1
            await response.aread()
            raise httpx.ReadError("the answer was lost on the way back", request=request)
        return response


def _token(name: str):
    async def token() -> str:
        return name

    return token


class Path:
    """The composition. ``store`` is the registry's store; ``None`` keeps the world's memory."""

    def __init__(self, store=None) -> None:
        self.world = World()
        if store is not None:
            self.world.registry = WorkerRegistry(store, clock=self.world.clock)
            self.world.app.state.worker_registry = self.world.registry
        self.world.tokens["agent"] = identity(Role.AGENT)
        self.world.tokens["worker"] = identity(Role.WORKER)
        self.clock = self.world.clock
        self.sleep = sleeping_on(self.clock)

    @property
    def registry(self) -> WorkerRegistry:
        return self.world.registry

    def line(self) -> _Line:
        return _Line(self.world.app)

    def requester(
        self, line: _Line | None = None, *, wait: int = WAIT
    ) -> RuntimeApiRemoteExecution:
        """The agent's port, as the handler of ``qa.run_remote_operation`` is given it."""
        return RuntimeApiRemoteExecution(
            BASE_URL,
            _token("agent"),
            origin={"cycle_id": "cyc_path", "run_id": "run_path"},
            wait=timedelta(seconds=wait),
            max_attempts=2,
            transport=line or self.line(),
            clock=lambda: (self.clock.now - T0).total_seconds(),
            sleep=self.sleep,
        )

    def worker(self, runner=None, *, worker_id: str = "spark-worker", line: _Line | None = None):
        """``Worker.serve()`` over HTTP, as ``worker_main`` builds it, running the fixture
        operation unless ``runner`` says otherwise."""
        return Worker(
            HttpWorkerApi(BASE_URL, _token("worker"), transport=line or self.line()),
            runner or FixtureOperationRunner(sleep=self.sleep),
            worker_id=worker_id,
            platform="linux-arm64",
            clock=self.clock,
            sleep=self.sleep,
        )

    @contextlib.asynccontextmanager
    async def serving(self, worker: Worker, worker_id: str = "spark-worker"):
        """``worker`` serving, once its session is live: a requester that asks before then is
        told no worker serves the operation, which is the offline case, not this one."""
        async with Serving(worker) as serving:

            async def registered() -> bool:
                return any(s.worker_id == worker_id for s, _ in await self.registry.sessions())

            await serving.until(registered)
            yield serving

    def hanging(self) -> ScriptedRunner:
        """A tool that serves the fixture operation and never finishes it."""
        runner = ScriptedRunner(self.clock, DECLARED)
        runner.run_seconds = None
        return runner

    def ask(self, dispatch_id: str = "send-1") -> RemoteOperationRequest:
        """The scenario's operation for this send of the task, made the runtime's current one."""
        files = tree(OPEN)
        asked = RemoteOperationRequest(
            contract="fixture.scenario",
            mode="play",
            provider=PROVIDER,
            operation=OPERATION,
            location="worker",
            source_revision=staged_revision(files),
            source_files=files,
            scenario=door_opens(),
            task_id=TASK,
            dispatch_id=dispatch_id,
        )
        return self.world.current(asked)

    async def operation_of(self, asked: RemoteOperationRequest):
        async with self.registry._store.exclusive() as tx:
            return await tx.operation_for_send(asked.task_id, asked.dispatch_id)

    async def unsettled(self) -> list:
        async with self.registry._store.exclusive() as tx:
            return await tx.unsettled_operations_of(TASK)


async def _until(predicate, turns: int = 5000) -> None:
    for _ in range(turns):
        if await predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"not reached in {turns} turns")


class RemotePathContract:
    """The path's cases. A subclass gives ``store``: the registry's store, or ``None``."""

    @pytest.fixture
    def path(self, store) -> Path:
        return Path(store)

    async def test_an_agents_operation_is_claimed_played_and_its_result_read(self, path):
        """The path, no fault. Bug caught: any hop losing what the next needs: the scenario's
        text on the wire, the fence on the result, the result on the requester's read."""
        asked = path.ask()
        async with path.serving(path.worker()):
            result = await path.requester().run_operation(asked)

        assert result.status is OperationStatus.COMPLETED
        assert result.dispatch_id == asked.dispatch_id
        assert {r.assertion_id: r.outcome for r in result.records} == {
            "spawned": AssertionOutcome.PASSED,
            "door-open": AssertionOutcome.PASSED,
        }
        settled = await path.operation_of(asked)
        assert (settled.state, settled.attempt) == (OperationState.SETTLED, 1)

    async def test_with_no_worker_at_dispatch_nothing_is_queued_and_it_is_not_executed(self, path):
        """Bug caught: an operation queued for nobody, so the task waits out its whole wait."""
        result = await path.requester().run_operation(path.ask())

        assert result.status is OperationStatus.NOT_EXECUTED
        assert result.reason == f"no registered worker serves {PROVIDER}/{OPERATION}"
        assert await path.unsettled() == []

    async def test_a_result_that_never_comes_is_asked_to_stop_and_reads_interrupted(self, path):
        """The cancel. Bug caught: a requester that waits for ever, or an operation left running
        for nobody after its requester gave up."""
        asked = path.ask()
        runner = path.hanging()
        async with path.serving(path.worker(runner)):
            result = await path.requester(wait=10).run_operation(asked)

        assert result.status is OperationStatus.INTERRUPTED
        assert result.reason == (
            "cancelled while the operation was running (its requester asked it to stop: no "
            "result within 10 s of asking)"
        )
        assert len(runner.stopped_at) == 1
        assert (await path.operation_of(asked)).state is OperationState.SETTLED

    async def test_a_worker_cut_off_mid_lease_loses_it_and_another_worker_runs_the_operation(
        self, path
    ):
        """The worker stopped mid-lease. Bug caught: the lease never running out, so the
        operation stays with a worker that is gone; or the second attempt's result not the one
        read."""
        asked = path.ask()
        first_line = path.line()
        stuck = path.hanging()
        waiting = None
        async with path.serving(path.worker(stuck, worker_id="first", line=first_line), "first"):
            waiting = asyncio.ensure_future(path.requester().run_operation(asked))
            await _until(lambda: _running(stuck))
            first_line.down = True  # gone mid-run: nothing it does reaches the runtime again
        async with path.serving(path.worker(worker_id="second"), "second"):
            result = await waiting

        assert result.status is OperationStatus.COMPLETED
        assert (await path.operation_of(asked)).attempt == 2
        assert len(stuck.runs) == 1

    async def test_a_late_result_after_another_worker_reclaimed_is_refused(self, path):
        """Bug caught: the first worker's completion, after its lease ran out and the operation
        was claimed again, read as the operation's result."""
        asked = path.ask()
        early_session = await path.registry.register(_registration("first"))
        waiting = asyncio.ensure_future(path.requester().run_operation(asked))
        await _until(lambda: _queued(path, asked))
        early = await path.registry.claim(early_session.session_id)
        path.clock.advance(leasing.LEASE_SECONDS + 1)
        async with path.serving(path.worker(worker_id="second"), "second"):
            result = await waiting
        late_line = path.line()
        late = await HttpWorkerApi(BASE_URL, _token("worker"), transport=late_line).submit_result(
            early.fence, _failing(asked)
        )

        assert result.status is OperationStatus.COMPLETED
        # The second attempt settled it, so the first's result finds nothing to settle.
        assert late.refusal is FenceRefusal.ALREADY_SETTLED
        settled = await path.operation_of(asked)
        assert settled.result.records == result.records

    async def test_a_lost_answer_and_a_restarted_requester_leave_one_operation_run_once(self, path):
        """The requester's side. The runtime stores the operation and its answer is lost; the
        requester restarts before it can read anything. Bug caught: a second operation queued
        for the same send, so the tool runs twice; or the result credited to neither."""
        await path.registry.register(_registration("idle"))  # a worker is there, not claiming
        asked = path.ask()
        first_line = path.line()
        first_line.drop_answer_to = ("POST", "/api/v1/remote-operations")
        stored = asyncio.ensure_future(path.requester(first_line).run_operation(asked))
        await _until(lambda: _answer_lost(first_line))
        first_line.down = True  # the process is gone: nothing it says reaches the runtime
        stored.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stored
        runner = FixtureOperationRunner(sleep=path.sleep)
        runs = []
        original = runner.run

        async def counted(request):
            runs.append(request.dispatch_id)
            return await original(request)

        runner.run = counted
        async with path.serving(path.worker(runner)):
            result = await path.requester().run_operation(asked)

        assert first_line.dropped == 1
        assert result.status is OperationStatus.COMPLETED
        assert runs == [asked.dispatch_id]
        settled = await path.operation_of(asked)
        assert (settled.state, settled.attempt, settled.result) == (
            OperationState.SETTLED,
            1,
            result,
        )

    async def test_a_superseded_send_is_stopped_and_never_runs_beside_the_current_one(self, path):
        """Bug caught: the task's older send still queued after a newer one asked, so a worker
        runs both and the older result lands for nobody, or is read as the newer's."""
        await path.registry.register(_registration("idle"))  # a worker is there, not claiming
        older = path.ask("send-1")
        waiting = asyncio.ensure_future(path.requester().run_operation(older))
        await _until(lambda: _queued(path, older))
        newer = path.ask("send-2")  # the runtime now waits on send-2
        runner = FixtureOperationRunner(sleep=path.sleep)
        ran = []
        original = runner.run

        async def counted(request):
            ran.append(request.dispatch_id)
            return await original(request)

        runner.run = counted
        async with path.serving(path.worker(runner)):
            current = await path.requester().run_operation(newer)
            stale = await waiting

        assert current.status is OperationStatus.COMPLETED
        assert stale.status is OperationStatus.INTERRUPTED
        assert "no longer task" in stale.reason
        assert ran == ["send-2"]
        stopped = await path.operation_of(older)
        assert stopped.state is OperationState.SETTLED
        assert stopped.result.status is not OperationStatus.COMPLETED


async def _running(runner: ScriptedRunner) -> bool:
    return len(runner.runs) == 1


async def _answer_lost(line: _Line) -> bool:
    return line.dropped == 1


async def _queued(path: Path, asked) -> bool:
    return await path.operation_of(asked) is not None


def _registration(worker_id: str) -> WorkerRegistration:
    return WorkerRegistration(
        worker_id=worker_id,
        platform="linux-arm64",
        tool_versions={PROVIDER: "2"},
        operations=(DECLARED,),
    )


def _failing(asked) -> RemoteOperationResult:
    return RemoteOperationResult(
        status=OperationStatus.COMPLETED,
        records=(AssertionRecord("door-open", AssertionOutcome.FAILED, "true", "false", "server"),),
        provider_version=f"{PROVIDER}@late",
        ran_with={},
        dispatch_id=asked.dispatch_id,
    )
