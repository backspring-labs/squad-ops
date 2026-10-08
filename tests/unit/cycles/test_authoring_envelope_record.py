"""Recording each authoring envelope as its reply arrives (SIP-0110 §0.11; #2105): taken where
every dispatch returns, stored through the cycle registry, and never in the task's way."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.models import Run, RunNotFoundError
from squadops.memory.authoring_envelope import AuthoringSeam, capture_envelope
from squadops.tasks.models import TaskResult
from tests.unit.cycles.test_benchmark_registry import _cycle
from tests.unit.cycles.test_llm_usage import _envelope

pytestmark = [pytest.mark.domain_orchestration]


def _captured(task_id: str = "t-1", captured_at: str = "2026-10-08T02:00:00+00:00") -> dict:
    return capture_envelope(
        seam=AuthoringSeam.BUILD_AUTHORING,
        task_type="development.develop",
        task_id=task_id,
        cycle_id="cyc_1",
        project_id="group_run",
        agent_id="neo",
        role="dev",
        handler_name="development_develop_handler",
        captured_at=captured_at,
        messages=[("system", "s"), ("user", f"build it ({task_id})")],
        chat_kwargs={"model": "qwen"},
        inputs={"prd": "p"},
    ).to_dict()


def _dispatcher(reply_router, recorder):
    from adapters.cycles.task_dispatcher import TaskDispatcher

    return TaskDispatcher(
        queue=reply_router.bind(AsyncMock()),
        reply_router=reply_router,
        task_timeout=5.0,
        record_authoring_envelope=recorder,
    )


async def test_a_reply_carrying_an_envelope_is_recorded_for_its_run(reply_router):
    """Entry point: ``TaskDispatcher.dispatch_task``, the path every dispatch takes (tasks,
    retries, correction repairs, retests). Bugs caught: an envelope dropped in transit, credited
    to another run, or recorded for a task that carried none."""
    recorder = AsyncMock()
    captured = _captured()
    reply_router.results["t-1"] = TaskResult(
        task_id="t-1", status="SUCCEEDED", outputs={}, authoring_envelope=captured
    )
    reply_router.results["t-2"] = TaskResult(task_id="t-2", status="SUCCEEDED", outputs={})

    with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
        dispatcher = _dispatcher(reply_router, recorder)
        for task in ("t-1", "t-2"):
            await dispatcher.dispatch_task(_envelope(task), "run_a")

    recorder.assert_awaited_once_with("run_a", captured)


async def test_a_store_that_fails_leaves_the_task_and_its_result_alone(reply_router):
    """Bug caught: the instrument failing a task it only observes."""
    recorder = AsyncMock(side_effect=ConnectionError("db down"))
    reply_router.results["t-1"] = TaskResult(
        task_id="t-1", status="SUCCEEDED", outputs={"ok": 1}, authoring_envelope=_captured()
    )

    with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
        result = await _dispatcher(reply_router, recorder).dispatch_task(_envelope("t-1"), "run_a")

    assert result.status == "SUCCEEDED" and result.outputs == {"ok": 1}
    recorder.assert_awaited_once()


async def _registry_with_run() -> MemoryCycleRegistry:
    registry = MemoryCycleRegistry()
    await registry.create_cycle(_cycle("cyc_1"))
    t0 = datetime(2026, 10, 8, tzinfo=UTC)
    await registry.create_run(
        Run(
            run_id="run_a",
            cycle_id="cyc_1",
            run_number=1,
            status="running",
            initiated_by="api",
            resolved_config_hash="h",
            started_at=t0,
            workload_type="implementation",
        )
    )
    return registry


async def test_the_registry_keeps_one_row_per_capture_in_capture_order():
    """Bugs caught: a redelivered reply stored twice (a case counted twice), or envelopes read
    back out of order, so a replay cannot tell which authoring came first."""
    registry = await _registry_with_run()
    later = _captured("t-2", "2026-10-08T02:10:00+00:00")
    earlier = _captured("t-1", "2026-10-08T02:00:00+00:00")

    assert await registry.record_authoring_envelope("run_a", later) is True
    assert await registry.record_authoring_envelope("run_a", earlier) is True
    assert await registry.record_authoring_envelope("run_a", dict(earlier)) is False

    assert [e["task_id"] for e in await registry.list_authoring_envelopes("run_a")] == [
        "t-1",
        "t-2",
    ]


async def test_an_envelope_for_an_unknown_run_is_refused():
    """Bug caught: an envelope stored against no run, which no replay can find."""
    registry = await _registry_with_run()

    with pytest.raises(RunNotFoundError):
        await registry.record_authoring_envelope("run_missing", _captured())


async def test_the_executors_dispatcher_records_into_its_cycle_registry(reply_router):
    """Wiring, entered where the live run dispatches: the executor's own dispatcher, with the
    recorder the executor composes. Bug caught: the dispatcher built without the recorder (every
    envelope logged as not recorded), or the recorder pointed somewhere other than the registry
    the run lives in."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
    from adapters.noop.ports import NoOpFailurePatternRecall

    registry = await _registry_with_run()
    executor = DispatchedFlowExecutor(
        task_timeout=300.0,
        cycle_registry=registry,
        artifact_vault=AsyncMock(),
        queue=reply_router.bind(AsyncMock()),
        squad_profile=AsyncMock(),
        project_registry=AsyncMock(),
        reply_router=reply_router,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
    )
    captured = _captured()
    reply_router.results["t-1"] = TaskResult(
        task_id="t-1", status="SUCCEEDED", outputs={}, authoring_envelope=captured
    )

    with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
        await executor._task_dispatcher.dispatch_task(_envelope("t-1"), "run_a")

    assert await registry.list_authoring_envelopes("run_a") == [captured]
