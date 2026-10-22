"""A run halted by a task instruction's emergency withdrawal restarts in its own place (SIP-0110
Appendix A §3.8, T13; #2178).

Entered where the live cycle restarts it: ``execute_cycle``, over the memory registry, with the
snapshot recall over the typed records' store. The halt is made as the route makes it, from the
same rules (``tasks_received``, ``halts_for``): the halt recorded, then the run cancelled.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.cycles.models import Run, RunHalt, RunStatus
from squadops.memory.emergency import EMERGENCY_RESTART_OVERRIDE, halts_for, tasks_received
from squadops.memory.records import withdrawn
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT
from tests.unit.cycles.test_failure_recall import _PROFILE, _framing_cycle, _framing_run
from tests.unit.memory.test_task_instructions import DESIGN, _instruction

pytestmark = [pytest.mark.domain_cycles]

T0 = datetime(2026, 10, 22, tzinfo=UTC)


async def _halt_as_the_route_does(store, records, registry, record, cycle_id: str) -> None:
    """The route's halt, from its rules: the record withdrawn, each run in flight halted where the
    exposures say it received the instruction, the halt recorded before the cancel."""
    gone = withdrawn(record, by="ada", at=T0, why="it names the wrong table")
    await records.append_status(record.record_id, gone.status_changes[-1])
    exposures = await store.list_exposures(_framing_run().run_id)
    for halt in halts_for(
        tasks_received(record.record_id, exposures, cycle_id=cycle_id),
        await registry.list_runs(cycle_id),
    ):
        await registry.record_run_halt(
            halt.run_id,
            RunHalt(record.record_id, "ada", "it names the wrong table", T0,
                    restart_from_task_id=halt.restart_from_task_id),
        )  # fmt: skip
        await registry.cancel_run(halt.run_id)


async def test_a_halted_run_restarts_from_the_task_that_received_the_instruction(reply_router):
    """Wiring, entered at ``execute_cycle`` (a single-workload framing cycle): the design-plan
    instruction is withdrawn in an emergency while its task is out. Bugs caught: the cycle ending
    on the halt, so the work never restarts; the restart running the whole workload again, or
    taking the halted run's later work (built on the instruction) as accepted; the restart handed
    the withdrawn instruction; a halted run restarted twice."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.tasks.models import TaskResult

    store = InMemoryCrossCycleMemoryStore()
    records = InMemoryMemoryRecords()
    record = _instruction("cyc_recall", DESIGN)
    await records.create(record)
    cycle, run = _framing_cycle(), _framing_run()
    registry = MemoryCycleRegistry()
    await registry.create_cycle(cycle)
    await registry.create_run(run)
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (_PROFILE, "sha")
    queue = reply_router.bind(AsyncMock())
    executor = DispatchedFlowExecutor(
        cycle_registry=registry, artifact_vault=AsyncMock(), queue=queue,
        squad_profile=profiles, task_timeout=5.0, reply_router=reply_router, project_registry=None,
        campaign_registry=None, campaign_progress=None, box_verdict=None,
        failure_recall=SnapshotRecall(store, records=records),
    )  # fmt: skip
    dispatched: list[tuple[str, str, bool]] = []
    halted = asyncio.Event()
    answer = queue.publish.side_effect

    async def publish(queue_name, payload, delay_seconds=None):
        """The design task goes out, and the emergency lands while it's out."""
        task = (json.loads(payload).get("payload") or {}) if "comms.task" in payload else {}
        if task.get("task_type") == DESIGN and not halted.is_set():
            halted.set()
            await _halt_as_the_route_does(store, records, registry, record, cycle.cycle_id)
        return await answer(queue_name, payload, delay_seconds)

    def responder(env):
        given = TASK_INSTRUCTIONS_INPUT in (env.get("inputs") or {})
        dispatched.append((env["task_id"][5:17], env["task_type"], given))
        return TaskResult(task_id=env["task_id"], status="SUCCEEDED", outputs={"summary": "ok"})

    queue.publish.side_effect = publish
    reply_router.responder = responder
    with patch("squadops.execution.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock):
        await asyncio.wait_for(executor.execute_cycle(cycle.cycle_id, run.run_id), timeout=10)

    [first, restart] = sorted(await registry.list_runs(cycle.cycle_id), key=lambda r: r.run_number)
    assert (first.status, first.halt.restart_run_id) == ("cancelled", restart.run_id)
    assert (restart.status, restart.workload_type) == ("completed", first.workload_type)
    halted_prefix, restart_prefix = first.run_id[:12], restart.run_id[:12]
    by_run: dict[str, list[tuple[str, bool]]] = {}
    for prefix, task_type, given in dispatched:
        by_run.setdefault(prefix, []).append((task_type, given))
    assert by_run[halted_prefix][-1] == (DESIGN, True)
    before = [t for t, _ in by_run[halted_prefix][:-1]]
    assert before == ["data.research_context", "strategy.frame_objective"]
    assert by_run[restart_prefix][0] == (DESIGN, False)
    assert not set(before) & {t for t, _ in by_run[restart_prefix]}
    assert all(not given for _, given in by_run[restart_prefix])


@pytest.fixture
def stubbed():
    """An executor whose runs are stubbed, over the memory registry: what each run does is the
    test's."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor

    registry = MemoryCycleRegistry()
    vault = AsyncMock()
    vault.list_artifacts.return_value = []
    executor = DispatchedFlowExecutor(
        cycle_registry=registry, artifact_vault=vault, queue=AsyncMock(),
        squad_profile=AsyncMock(), task_timeout=5.0, project_registry=None,
        campaign_registry=None, campaign_progress=None, box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
    )  # fmt: skip
    executor._cycle_event_bus = MagicMock()
    return executor, registry


@pytest.mark.parametrize("restart_from", ["task-run_001-002-development.design_plan", None])
async def test_a_halted_workload_restarts_in_its_own_place_in_the_sequence(stubbed, restart_from):
    """The multi-workload loop. Bugs caught: the sequence stopping on the halt; the restart put
    after the next workload, or the next workload created twice; the restart run not told what it
    restarts from; a run halted only for building on the instruction restarted anyway."""
    import dataclasses

    executor, registry = stubbed
    cycle = dataclasses.replace(
        _framing_cycle(cycle_id="cyc_001"),
        applied_defaults={
            "workload_sequence": [{"type": "framing", "gate": None}, {"type": "implementation"}]
        },
    )
    await registry.create_cycle(cycle)
    await registry.create_run(
        Run(run_id="run_001", cycle_id="cyc_001", run_number=1, status="queued",
            initiated_by="api", resolved_config_hash="h", workload_type="framing")
    )  # fmt: skip
    calls: list[tuple[str, dict | None]] = []

    async def run_it(cycle_id, run_id, profile_id=None, *, forwarding_overrides=None):
        calls.append((run_id, forwarding_overrides))
        await registry.update_run_status(run_id, RunStatus.RUNNING)
        if run_id == "run_001":
            await registry.record_run_halt(
                run_id,
                RunHalt("mrec_1", "ada", "wrong table", T0, restart_from_task_id=restart_from),
            )
            await registry.cancel_run(run_id)
        else:
            await registry.update_run_status(run_id, RunStatus.COMPLETED)

    executor.execute_run = run_it
    executor._starting_workload_index = AsyncMock(return_value=0)

    await executor.execute_cycle("cyc_001", "run_001")

    runs = sorted(await registry.list_runs("cyc_001"), key=lambda r: r.run_number)
    if restart_from is None:
        assert [(r.workload_type, r.status) for r in runs] == [("framing", "cancelled")]
        assert [run_id for run_id, _ in calls] == ["run_001"]
        return
    halted, restart, implementation = runs
    assert [(r.workload_type, r.status) for r in runs] == [
        ("framing", "cancelled"), ("framing", "completed"), ("implementation", "completed"),
    ]  # fmt: skip
    assert halted.halt.restart_run_id == restart.run_id
    assert [run_id for run_id, _ in calls] == ["run_001", restart.run_id, implementation.run_id]
    assert calls[1][1][EMERGENCY_RESTART_OVERRIDE] == {
        "source_run_id": "run_001", "before_task_id": restart_from,
    }  # fmt: skip
    assert EMERGENCY_RESTART_OVERRIDE not in (calls[2][1] or {})


async def test_a_halted_run_restarts_once(stubbed):
    """Bug caught: a halted run restarted twice, two runs then holding its place, when the cycle
    reads its halt again (a re-entry after a restart of the process)."""
    executor, registry = stubbed
    cycle = _framing_cycle(cycle_id="cyc_001")
    await registry.create_cycle(cycle)
    await registry.create_run(
        Run(run_id="run_001", cycle_id="cyc_001", run_number=1, status="running",
            initiated_by="api", resolved_config_hash="h", workload_type="framing")
    )  # fmt: skip
    await registry.record_run_halt(
        "run_001", RunHalt("mrec_1", "ada", "wrong", T0, restart_from_task_id="task-run_001-002-x")
    )
    await registry.cancel_run("run_001")
    halted = await registry.get_run("run_001")

    first = await executor._emergency_restart(cycle, halted, {"type": "framing"}, None)
    again = await executor._emergency_restart(cycle, halted, {"type": "framing"}, None)

    assert first is not None and again is None
    live = [r for r in await registry.list_runs("cyc_001") if r.status != "cancelled"]
    assert [r.run_id for r in live] == [first[0]]


@pytest.mark.parametrize("cancelled", ["after the halt", "after the restart is recorded"])
async def test_a_cycle_cancelled_around_the_restart_starts_nothing(stubbed, cancelled):
    """SIP-0109 §12a: nothing runs after an abort. A campaign's abort or a cycle cancel sets the
    cycle's flag, then cancels the runs it lists. Bugs caught: the restart created on a cycle
    already cancelled; or created just after the cancel listed its runs, so nothing cancels it and
    it executes after the campaign is aborted."""
    executor, registry = stubbed
    cycle = _framing_cycle(cycle_id="cyc_001")
    await registry.create_cycle(cycle)
    await registry.create_run(
        Run(run_id="run_001", cycle_id="cyc_001", run_number=1, status="queued",
            initiated_by="api", resolved_config_hash="h", workload_type="framing")
    )  # fmt: skip
    started: list[str] = []

    async def run_it(cycle_id, run_id, profile_id=None, *, forwarding_overrides=None):
        started.append(run_id)
        await registry.update_run_status(run_id, RunStatus.RUNNING)
        await registry.record_run_halt(
            run_id, RunHalt("mrec_1", "ada", "wrong", T0, restart_from_task_id="task-x-002-d")
        )
        await registry.cancel_run(run_id)
        if cancelled == "after the halt":
            await registry.cancel_cycle(cycle_id)

    recorded = registry.record_restart

    async def record_then_cancel(run_id, restart_run_id):
        landed = await recorded(run_id, restart_run_id)
        await registry.cancel_cycle("cyc_001")  # the cancel listed the runs before this one existed
        return landed

    if cancelled == "after the restart is recorded":
        registry.record_restart = record_then_cancel
    executor.execute_run = run_it
    executor._cycle_completion = AsyncMock()

    await executor.execute_cycle("cyc_001", "run_001")

    assert started == ["run_001"]
    runs = sorted(await registry.list_runs("cyc_001"), key=lambda r: r.run_number)
    if cancelled == "after the halt":
        assert [(r.run_id, r.status) for r in runs] == [("run_001", "cancelled")]
    else:
        assert [r.status for r in runs] == ["cancelled", "cancelled"]
        assert runs[0].halt.restart_run_id == runs[1].run_id
