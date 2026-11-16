"""The remote-execution port straight into the registry, as Campaign acceptance uses it (#3053).

Entered at ``run_operation`` over the real registry and memory store, with the fixture worker
claiming through the registry and running ``fixture/declared_scenario``: the path a scenario
criterion's reading takes at an increment's delivery. The clocks are the test's: each wait the
adapter sleeps moves both, and the worker acts when the test says.

What bugs would these catch?
- A scenario run at delivery whose result isn't the worker's (lost, or read off another ask).
- No worker read as anything but ``not_executed``, or something queued for nobody.
- A worker that claims and goes silent leaving acceptance waiting for ever, or its silence read
  as a pass or a failure instead of ``interrupted``.
- Two criteria's asks stopping each other because they shared a task.
- #3045: a reading flagged as taken by no worker when a worker did take it (claimed and went
  silent, or played it), so an outage's routing is given to the work's own failure; or one no
  worker took left unflagged, so the Campaign spends a repair on it.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from adapters.remote_execution.fixture_operation_runner import (
    OPERATION,
    PROVIDER,
    FixtureOperationRunner,
)
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from adapters.remote_execution.registry_remote_execution import RegistryRemoteExecution
from squadops.campaigns.acceptance import Held, held_on_scenario
from squadops.remote_execution import leasing
from squadops.remote_execution.models import (
    OperationStatus,
    ReadingSide,
    RemoteOperationRequest,
    acceptance_task_id,
    reading_unavailable,
    records_document,
)
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.scenario import staged_revision
from squadops.remote_execution.workers import OperationState, ServedOperation
from tests.unit.remote_execution.registry_contract import Clock, registration
from tests.unit.remote_execution.scenario_fixture import OPEN, SHUT, door_opens, tree

DECLARED = ServedOperation(PROVIDER, OPERATION)
WAIT = timedelta(seconds=30)


class Harness:
    """The registry, the adapter, and a worker the test drives from the adapter's sleeps."""

    def __init__(self, *, worker: bool = True, max_attempts: int = 1) -> None:
        self.clock = Clock()
        self.seconds = 0.0
        self.registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=self.clock)
        self.adapter = RegistryRemoteExecution(
            self.registry,
            origin={"campaign_id": "cmp_1", "increment_id": "inc_2"},
            wait=WAIT,
            max_attempts=max_attempts,
            clock=lambda: self.seconds,
            sleep=self._sleep,
        )
        self.session = (
            asyncio.run(self.registry.register(registration("macbook", DECLARED))).session_id
            if worker
            else None
        )
        #: What the worker does at the adapter's next sleep: ``play``, ``hold`` (claim and go
        #: silent) or nothing.
        self.worker_does: str | None = "play"

    async def _sleep(self, seconds: float) -> None:
        self.seconds += seconds
        self.clock.advance(seconds)
        await asyncio.sleep(0)  # a real wait lets the other asks run
        if self.worker_does == "play":
            claim = await self.registry.claim(self.session)
            if claim is not None:
                result = await FixtureOperationRunner().run(claim.request)
                await self.registry.submit_result(claim.fence, result)
        elif self.worker_does == "hold":
            await self.registry.claim(self.session)
            self.worker_does = None


def ask(world: dict, criterion: str = "C-2", dispatch: str = "eval-1") -> RemoteOperationRequest:
    files = tree(world)
    return RemoteOperationRequest(
        contract="game.playtest",
        mode="simulation",
        provider=PROVIDER,
        operation=OPERATION,
        location="worker",
        source_revision=staged_revision(files),
        source_files=files,
        scenario=door_opens(),
        task_id=acceptance_task_id("cmp_1", "inc_2", criterion, ReadingSide.CANDIDATE),
        dispatch_id=dispatch,
    )


def test_a_scenario_run_at_delivery_comes_back_as_the_workers_reading_and_is_credited():
    h = Harness()
    request = ask(OPEN)

    result = asyncio.run(h.adapter.run_operation(request))
    reading = records_document(request, result, ReadingSide.CANDIDATE, not_staged=())

    assert result.status is OperationStatus.COMPLETED
    assert result.dispatch_id == "eval-1"
    assert held_on_scenario(door_opens(), request.source_revision, reading) == (Held.HELD, "")


def test_with_no_worker_nothing_is_queued_and_the_reading_is_not_executed():
    h = Harness(worker=False)

    result = asyncio.run(h.adapter.run_operation(ask(OPEN)))

    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason == "no registered worker serves fixture/declared_scenario"
    assert result.records == ()
    assert asyncio.run(_operations(h)) == []


def test_a_worker_that_claims_and_goes_silent_reads_interrupted_within_a_lease_after_the_wait():
    h = Harness()
    h.worker_does = "hold"

    result = asyncio.run(h.adapter.run_operation(ask(OPEN)))

    assert result.status is OperationStatus.INTERRUPTED
    assert result.records == ()
    assert f"no result within {WAIT.total_seconds():g} s of asking" in result.reason
    assert h.seconds <= WAIT.total_seconds() + leasing.LEASE_SECONDS + 2


def test_two_criteria_asked_at_once_are_two_operations_and_neither_stops_the_other():
    h = Harness()
    h.worker_does = None
    first = ask(SHUT, criterion="C-1")
    second = ask(OPEN, criterion="C-2")

    async def both():
        return await asyncio.gather(
            h.adapter.run_operation(first), h.adapter.run_operation(second), _then_play(h)
        )

    one, two, _ = asyncio.run(both())

    assert (one.status, two.status) == (OperationStatus.COMPLETED, OperationStatus.COMPLETED)
    assert held_on_scenario(
        door_opens(),
        second.source_revision,
        records_document(second, two, ReadingSide.CANDIDATE, not_staged=()),
    ) == (Held.HELD, "")
    assert held_on_scenario(
        door_opens(),
        first.source_revision,
        records_document(first, one, ReadingSide.CANDIDATE, not_staged=()),
    ) == (Held.BROKEN, "door-open")


async def _then_play(h: Harness) -> None:
    """Let both asks queue before the worker starts playing them."""
    await asyncio.sleep(0)
    h.worker_does = "play"


@pytest.mark.parametrize(
    ("worker", "does", "status", "unavailable"),
    [
        (False, None, OperationStatus.NOT_EXECUTED, True),  # no worker serves it
        (True, None, OperationStatus.NOT_EXECUTED, True),  # served, never claimed in the wait
        (True, "hold", OperationStatus.INTERRUPTED, False),  # claimed, then silent
        (True, "play", OperationStatus.COMPLETED, False),
    ],
)
def test_a_reading_is_flagged_unavailable_only_when_no_worker_took_it(
    worker, does, status, unavailable
):
    h = Harness(worker=worker)
    h.worker_does = does
    request = ask(OPEN)

    result = asyncio.run(h.adapter.run_operation(request))
    document = records_document(request, result, ReadingSide.CANDIDATE, not_staged=())

    assert (result.status, result.unavailable) == (status, unavailable)
    assert document["unavailable"] is unavailable
    assert reading_unavailable(document) is unavailable


def test_a_reading_kept_before_the_flag_reads_as_taken_by_a_worker():
    """#3045: a stored reading with no ``unavailable`` key keeps the routing it had then."""
    request = ask(OPEN)
    result = asyncio.run(Harness(worker=False).adapter.run_operation(request))
    document = records_document(request, result, ReadingSide.CANDIDATE, not_staged=())
    del document["unavailable"]

    assert reading_unavailable(document) is False
    assert reading_unavailable(None) is False


@pytest.mark.parametrize(("wait", "attempts"), [(timedelta(0), 1), (WAIT, 0)])
def test_a_requester_that_could_never_be_answered_is_refused(wait, attempts):
    with pytest.raises(ValueError, match="wait is|max_attempts is"):
        RegistryRemoteExecution(
            WorkerRegistry(MemoryWorkerRegistryStore()),
            origin={},
            wait=wait,
            max_attempts=attempts,
        )


def test_a_silent_workers_operation_is_settled_not_left_held_when_the_wait_ends():
    h = Harness()
    h.worker_does = "hold"
    request = ask(OPEN)

    asyncio.run(h.adapter.run_operation(request))

    assert [o.state for o in asyncio.run(_operations(h))] == [OperationState.SETTLED]


async def _operations(h: Harness):
    async with h.registry._store.exclusive() as tx:  # the test reads every row it made
        return list(tx._rows.operations.values())


def test_a_request_past_the_limit_is_refused_by_name_and_nothing_is_queued():
    """#3049, at the port. Bugs caught: a multi-megabyte tree queued, stored and sent at every
    claim past what a run carries; the tree cut to fit, so the worker plays part of the
    candidate; or the refusal read as no worker being available, so a Campaign waits for one."""
    from dataclasses import replace

    from squadops.remote_execution.models import REQUEST_TREE_LIMIT_BYTES

    h = Harness()
    request = ask(OPEN)
    big = replace(
        request,
        source_files={**request.source_files, "src/Big.luau": "x" * REQUEST_TREE_LIMIT_BYTES},
    )

    result = asyncio.run(h.adapter.run_operation(big))

    assert (result.status, result.records, result.unavailable) == (
        OperationStatus.NOT_EXECUTED,
        (),
        False,
    )
    assert "past the 4,194,304-byte limit a remote operation carries" in result.reason
    assert "Its largest files: src/Big.luau (4,194,304)" in result.reason
    assert asyncio.run(_operations(h)) == []
