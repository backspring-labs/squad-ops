"""The worker's loop, over the real registry (SIP-0117 R3.3, R5.5).

Each test enters at ``Worker.serve()``, the call the worker's process makes, with the runtime
in-process and the test's clock. What it asserts is what the runtime then holds: the
operation's state, its result, and each attempt.
"""

from __future__ import annotations

import pytest

from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution import leasing
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.serving import IDLE_POLL, REASON_CANCELLED, Worker
from squadops.remote_execution.workers import (
    OperationState,
    RuntimeAnswerUnreadable,
    WorkerRefused,
)
from tests.unit.remote_execution.registry_contract import (
    ORIGIN,
    PLAY,
    Clock,
    passing,
    registration,
    request,
)
from tests.unit.remote_execution.worker_harness import (
    RegistryWorkerApi,
    ScriptedRunner,
    Serving,
    sleeping_on,
)


class _World:
    def __init__(self) -> None:
        self.clock = Clock()
        self.store = MemoryWorkerRegistryStore()
        self.registry = WorkerRegistry(self.store, clock=self.clock)
        self.api = RegistryWorkerApi(self.registry)
        self.runner = ScriptedRunner(self.clock)
        self.worker = Worker(
            self.api,
            self.runner,
            worker_id="macbook",
            platform="darwin-arm64",
            clock=self.clock,
            sleep=sleeping_on(self.clock),
        )

    async def enqueue(self, *, max_attempts: int = 2, dispatch_id: str = "dispatch-1"):
        return await self.registry.enqueue(
            request(dispatch_id=dispatch_id), ORIGIN, max_attempts=max_attempts
        )

    async def stored(self, operation_id: str):
        """The operation's row as it is stored. Reading it decides nothing about its lease."""
        async with self.store.exclusive() as tx:
            return await tx.operation(operation_id)

    def settled(self, operation_id: str):
        async def holds() -> bool:
            return (await self.stored(operation_id)).state is OperationState.SETTLED

        return holds

    def claimed(self, operation_id: str, attempt: int = 1):
        async def holds() -> bool:
            operation = await self.stored(operation_id)
            return operation.state is OperationState.CLAIMED and operation.attempt == attempt

        return holds

    async def attempts(self):
        async with self.store.exclusive() as tx:
            return [
                (a.attempt, a.outcome.value if a.outcome else None)
                for a in reversed(await tx.attempts_of("macbook"))
            ]


@pytest.fixture
def w() -> _World:
    return _World()


async def test_a_queued_operation_is_run_and_settled_with_the_tools_result(w):
    """The whole of R3.3 from the worker's side. Bug caught: a worker that registers without
    what it serves (so nothing is ever handed to it), or one that stops renewing while the tool
    runs, so an operation longer than a lease is taken from it. This one runs for 150 seconds
    against a 60-second lease and is accepted on its first attempt."""
    queued = await w.enqueue()
    w.runner.run_seconds = 150

    async with Serving(w.worker) as serving:
        await serving.until(w.settled(queued.operation_id))

    operation = await w.stored(queued.operation_id)
    assert operation.result == passing("dispatch-1")
    assert await w.attempts() == [(1, "accepted")]
    assert w.api.renewals >= 150 // leasing.HEARTBEAT_SECONDS - 1
    assert await w.registry.refusals(queued.operation_id) == []
    ((session, health),) = await w.registry.sessions()
    assert (session.worker_id, session.platform, health) == ("macbook", "darwin-arm64", "online")
    assert session.operations == (PLAY,)
    assert session.tool_versions == {"scripted-editor": "7.2"}
    assert w.runner.runs == [queued.request]
    assert w.runner.resets == 0


async def test_a_cancel_stops_the_tool_resets_it_and_settles_the_operation_interrupted(w):
    """R3.3's cancel row. Bug caught: a cancelled operation left running on the tool, or
    settled as anything but ``interrupted`` (it had started), or the tool handed its next
    operation without a reset."""
    queued = await w.enqueue()
    w.runner.run_seconds = None

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(queued.operation_id))
        await w.registry.cancel(queued.operation_id)
        await serving.until(w.settled(queued.operation_id))

    operation = await w.stored(queued.operation_id)
    assert (operation.result.status, operation.result.reason) == (
        OperationStatus.INTERRUPTED,
        REASON_CANCELLED,
    )
    assert operation.result.dispatch_id == "dispatch-1"
    assert len(w.runner.stopped_at) == 1
    assert w.runner.resets == 1
    assert await w.attempts() == [(1, "accepted")]


async def test_a_lease_that_runs_out_unrenewed_stops_the_tool_and_the_next_attempt_runs(w):
    """R3.3's expiry row, from the worker's side. Bug caught: a worker that keeps its tool
    running on an operation the runtime has given up on (two attempts then run at once on one
    tool), one that stops at the first missed renewal instead of at the lease's end, one that
    submits the late result, or one that resets twice for one ending."""
    queued = await w.enqueue(max_attempts=2)
    w.runner.run_seconds = None

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(queued.operation_id))
        lease_ends = (await w.stored(queued.operation_id)).lease_expires_at
        w.api.down = {"renew", "claim", "heartbeat", "submit_result"}

        async def stopped_and_reset() -> bool:
            return w.runner.resets == 1

        await serving.until(stopped_and_reset)
        assert len(w.runner.stopped_at) == 1
        assert w.runner.stopped_at[0] >= lease_ends

        w.api.down = set()
        w.runner.run_seconds = 20
        await serving.until(w.settled(queued.operation_id))

    operation = await w.stored(queued.operation_id)
    assert operation.result == passing("dispatch-1")
    assert await w.attempts() == [(1, "expired"), (2, "accepted")]
    assert await w.registry.refusals(queued.operation_id) == []
    assert len(w.runner.runs) == 2
    assert w.runner.resets == 1


async def test_what_the_tool_raises_settles_the_operation_interrupted_with_it(w):
    """Bug caught: a tool's crash killing the worker with the claim held (the operation then
    waits out its lease for nothing), or reported as ``not_executed`` when it had started."""
    queued = await w.enqueue()
    w.runner.raises = RuntimeError("the place file is locked")

    async with Serving(w.worker) as serving:
        await serving.until(w.settled(queued.operation_id))

    result = (await w.stored(queued.operation_id)).result
    assert result.status is OperationStatus.INTERRUPTED
    assert result.reason == (
        "the tool raised while the operation ran: RuntimeError: the place file is locked"
    )
    assert result.records == ()
    assert w.runner.resets == 1


async def test_a_tool_that_cant_be_reset_runs_nothing_until_it_can(w):
    """Bug caught: an operation run on a tool whose state is unknown. After a cancel whose
    reset failed, the next operation is answered ``not_executed`` with why and never reaches
    the tool; once the tool resets, the one after runs."""
    first = await w.enqueue(dispatch_id="dispatch-1")
    w.runner.run_seconds = None
    w.runner.reset_raises = ConnectionError("the editor is not answering")

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(first.operation_id))
        await w.registry.cancel(first.operation_id)
        await serving.until(w.settled(first.operation_id))

        second = await w.enqueue(dispatch_id="dispatch-2")
        await serving.until(w.settled(second.operation_id))
        assert len(w.runner.runs) == 1

        w.runner.reset_raises = None
        w.runner.run_seconds = 0
        third = await w.enqueue(dispatch_id="dispatch-3")
        await serving.until(w.settled(third.operation_id))

    assert (await w.stored(first.operation_id)).result.reason == (
        f"{REASON_CANCELLED}; the worker's tool was not reset: "
        "ConnectionError: the editor is not answering"
    )
    refused = (await w.stored(second.operation_id)).result
    assert refused.status is OperationStatus.NOT_EXECUTED
    assert refused.reason == (
        f"the worker's tool could not be reset (operation {first.operation_id} was "
        "cancelled): ConnectionError: the editor is not answering"
    )
    assert refused.dispatch_id == "dispatch-2"
    assert (await w.stored(third.operation_id)).result == passing("dispatch-3")
    assert [r.dispatch_id for r in w.runner.runs] == ["dispatch-1", "dispatch-3"]
    assert w.runner.resets == 1


async def test_a_worker_whose_session_was_ended_stops_its_tool_and_registers_again(w):
    """Bug caught: a worker that keeps polling a session the runtime ended and looks idle
    forever, or keeps its tool running on the attempt that ended with the session."""
    queued = await w.enqueue(max_attempts=2)
    w.runner.run_seconds = None

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(queued.operation_id))
        ((first, _),) = await w.registry.sessions()
        intruder = await w.registry.register(registration("macbook", PLAY))

        async def stopped() -> bool:
            return bool(w.runner.stopped_at)

        await serving.until(stopped)
        w.runner.run_seconds = 0
        await serving.until(w.settled(queued.operation_id))

    ((session, _),) = await w.registry.sessions()
    assert session.session_id not in (first.session_id, intruder.session_id)
    assert (await w.stored(queued.operation_id)).result == passing("dispatch-1")
    assert await w.attempts() == [(1, "expired"), (2, "accepted")]
    assert w.runner.resets == 1


async def test_a_worker_told_to_stop_while_it_is_stopping_its_tool_stops(w):
    """Found by this suite: the worker read its own cancellation as the tool's and served on,
    so the process could not be stopped. Bug caught: a stop request that arrives while the
    tool is being stopped is swallowed. ``Serving`` fails when the worker serves on."""
    queued = await w.enqueue()
    w.runner.run_seconds = None

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(queued.operation_id))
        w.api.down = {"renew", "claim", "heartbeat", "submit_result"}

        async def being_stopped() -> bool:
            return bool(w.runner.stopped_at)

        await serving.until(being_stopped)

    assert w.runner.resets == 0
    assert (await w.stored(queued.operation_id)).state is OperationState.CLAIMED


async def test_a_worker_started_before_the_runtime_registers_once_it_answers(w):
    """Bug caught: a worker that exits, or never tries again, when the runtime isn't up yet."""
    w.api.down = {"register"}

    async with Serving(w.worker) as serving:
        started = w.clock()

        async def waited() -> bool:
            return w.clock() >= started + 5 * IDLE_POLL

        await serving.until(waited)
        assert await w.registry.sessions() == []

        w.api.down = set()

        async def registered() -> bool:
            return len(await w.registry.sessions()) == 1

        await serving.until(registered)


async def test_a_result_the_runtime_cant_take_yet_is_submitted_again_and_accepted(w):
    """Bug caught: a result dropped at the first failed submission, so a finished operation
    waits out its lease and runs a second time."""
    queued = await w.enqueue()
    w.api.down = {"submit_result"}

    async with Serving(w.worker) as serving:
        renewed_from = w.api.renewals

        async def retried() -> bool:
            return w.api.renewals >= renewed_from + 3

        await serving.until(retried)
        assert (await w.stored(queued.operation_id)).state is OperationState.CLAIMED

        w.api.down = set()
        await serving.until(w.settled(queued.operation_id))

    assert (await w.stored(queued.operation_id)).result == passing("dispatch-1")
    assert await w.attempts() == [(1, "accepted")]
    assert len(w.runner.runs) == 1


async def test_a_result_the_runtime_never_takes_is_given_up_after_one_lease(w):
    """Bug caught: a worker that holds a claim for ever, renewing it, because the submission
    alone keeps failing. It stops after one lease's length, the lease runs out, and the
    operation's last attempt settles as ``interrupted``."""
    queued = await w.enqueue(max_attempts=1)
    w.api.down = {"submit_result"}

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(queued.operation_id))
        claimed_at = w.clock()

        async def settled() -> bool:
            return (await w.registry.operation(queued.operation_id)).state is (
                OperationState.SETTLED
            )

        await serving.until(settled)

    operation = await w.stored(queued.operation_id)
    assert operation.result.status is OperationStatus.INTERRUPTED
    assert await w.attempts() == [(1, "expired")]
    assert (w.clock() - claimed_at).total_seconds() < 3 * leasing.LEASE_SECONDS


@pytest.mark.parametrize(
    "refusal",
    [WorkerRefused("HTTP 403: Missing required scopes"), RuntimeAnswerUnreadable("no lease_id")],
    ids=["refused", "unreadable"],
)
async def test_a_worker_the_runtime_refuses_stops_and_leaves_nothing_running(w, refusal):
    """Bug caught: a refusal retried for ever as if the runtime were only unreachable (a wrong
    secret then looks like an idle worker), or the tool left running when the worker stops."""
    queued = await w.enqueue()
    w.runner.run_seconds = None

    async with Serving(w.worker) as serving:
        await serving.until(w.claimed(queued.operation_id))

        async def renew(*_):
            raise refusal

        w.api.renew = renew
        ended = await serving.ended_with()

    assert ended is refusal
    assert len(w.runner.stopped_at) == 1
