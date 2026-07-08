"""Unit tests for SIP-0089 §4.4 — dispatch-side RuntimeActivity instrumentation.

The TaskDispatcher (SIP-0097 §6.1 — this instrumentation moved with the
transport out of DispatchedFlowExecutor in slice 5; renamed from
test_executor_activity_instrumentation.py) opens a RuntimeActivity per
dispatched task (start on dispatch, complete/fail on reply) so an agent's
current task is observable. Bug classes guarded:
- a dispatched task not opening an activity (no observability) or opening one with
  the wrong identity (mode/source_kind/refs);
- a SUCCEEDED task not completing its activity, or a FAILED/raised task not
  failing it (stale "running" activity);
- the instrumentation breaking dispatch when the activity port errors (must be
  best-effort);
- activity calls firing when the port is unwired (opt-in).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from adapters.cycles.task_dispatcher import TaskDispatcher
from squadops.ports.runtime.activity import RuntimeActivityPort
from squadops.runtime.models import RuntimeActivity
from squadops.tasks.models import TaskEnvelope, TaskResult


def _envelope(task_id="t1", agent_id="max", cycle_id="cyc-1", task_type="strategy.analyze_prd"):
    return TaskEnvelope(
        task_id=task_id,
        agent_id=agent_id,
        cycle_id=cycle_id,
        pulse_id="p1",
        project_id="proj",
        task_type=task_type,
        correlation_id="c",
        causation_id="ca",
        trace_id="tr",
        span_id="sp",
        task_name="Analyze the PRD",
    )


def _activity(activity_id="act-1") -> RuntimeActivity:
    return RuntimeActivity(
        runtime_activity_id=activity_id,
        agent_id="max",
        mode="cycle",
        activity_type="strategy.analyze_prd",
        goal="Analyze the PRD",
        priority=0,
        state="running",
        source_kind="cycle_task",
        source_ref="t1",
        cycle_id="cyc-1",
        workload_id=None,
        task_id="t1",
        can_pause=False,
        can_resume=False,
        can_abort=True,
    )


class _FakeActivityPort(RuntimeActivityPort):
    def __init__(self, *, start_raises: bool = False) -> None:
        self.start_raises = start_raises
        self.started: list[dict] = []
        self.completed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    async def start_activity(self, agent_id, **kwargs):
        if self.start_raises:
            raise RuntimeError("db down")
        self.started.append({"agent_id": agent_id, **kwargs})
        return _activity()

    async def update_state(self, activity_id, state, *, conn=None):
        raise NotImplementedError

    async def complete_activity(self, activity_id, *, evidence_ref=None):
        self.completed.append(activity_id)
        return None

    async def fail_activity(self, activity_id, reason_code):
        self.failed.append((activity_id, reason_code))
        return None

    async def abort_activity(self, activity_id, reason_code, *, conn=None):
        raise NotImplementedError

    async def get_current_activity(self, agent_id, *, conn=None):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# _start_task_activity
# ---------------------------------------------------------------------------


async def test_start_task_activity_opens_cycle_activity_with_task_identity():
    """Bug class: a dispatched task must open a `cycle` / `cycle_task` activity
    carrying the task's identity (source_ref, cycle_id, task_id) so it's queryable
    and attributable. Returns the minted activity id."""
    act = _FakeActivityPort()
    ex = TaskDispatcher(activity_port=act)

    activity_id = await ex._start_task_activity(_envelope())

    assert activity_id == "act-1"
    started = act.started[0]
    assert started["agent_id"] == "max"
    assert started["mode"] == "cycle"
    assert started["source_kind"] == "cycle_task"
    assert started["source_ref"] == "t1"
    assert started["cycle_id"] == "cyc-1"
    assert started["task_id"] == "t1"
    assert started["activity_type"] == "strategy.analyze_prd"


async def test_start_task_activity_disabled_when_no_port():
    """Bug class: instrumentation is opt-in. With no activity port, dispatch must
    not attempt any activity work — returns None, no calls."""
    ex = TaskDispatcher()  # no activity_port

    assert await ex._start_task_activity(_envelope()) is None


async def test_start_task_activity_swallows_errors():
    """Bug class (best-effort): a failure opening the activity must NOT propagate
    (it would break dispatch). Returns None so finish becomes a no-op."""
    act = _FakeActivityPort(start_raises=True)
    ex = TaskDispatcher(activity_port=act)

    assert await ex._start_task_activity(_envelope()) is None


# ---------------------------------------------------------------------------
# _finish_task_activity
# ---------------------------------------------------------------------------


async def test_finish_completes_on_succeeded_result():
    """Bug class: a SUCCEEDED task must complete its activity (not fail it)."""
    act = _FakeActivityPort()
    ex = TaskDispatcher(activity_port=act)

    await ex._finish_task_activity("act-1", TaskResult(task_id="t1", status="SUCCEEDED"))

    assert act.completed == ["act-1"] and act.failed == []


@pytest.mark.parametrize(
    "result",
    [
        TaskResult(task_id="t1", status="FAILED", error="boom"),
        TaskResult(task_id="t1", status="CANCELED"),
        None,  # reply wait raised
    ],
)
async def test_finish_fails_on_non_success(result):
    """Bug class: a FAILED/CANCELED/raised task must fail its activity, never leave
    it running or mark it complete."""
    act = _FakeActivityPort()
    ex = TaskDispatcher(activity_port=act)

    await ex._finish_task_activity("act-1", result)

    assert act.completed == []
    assert len(act.failed) == 1 and act.failed[0][0] == "act-1"


async def test_finish_noop_without_activity_id():
    """Bug class: if start was disabled/failed (activity_id None) finish must be a
    no-op — never call complete/fail with a missing id."""
    act = _FakeActivityPort()
    ex = TaskDispatcher(activity_port=act)

    await ex._finish_task_activity(None, TaskResult(task_id="t1", status="SUCCEEDED"))

    assert act.completed == [] and act.failed == []


# ---------------------------------------------------------------------------
# _dispatch_task wrapping (integration)
# ---------------------------------------------------------------------------


async def test_dispatch_task_starts_then_completes_activity_on_success():
    """Bug class (the end-to-end wrap): dispatching a task must open an activity
    before the reply wait and complete it after a SUCCEEDED reply."""
    act = _FakeActivityPort()
    ex = TaskDispatcher(activity_port=act)
    ex.create_task_run_if_enabled = AsyncMock(return_value=None)
    ex._publish_and_await = AsyncMock(return_value=TaskResult(task_id="t1", status="SUCCEEDED"))

    result = await ex.dispatch_task(_envelope(), "run-1", heartbeat_interval=999)

    assert result.status == "SUCCEEDED"
    assert len(act.started) == 1
    assert act.completed == ["act-1"] and act.failed == []


async def test_dispatch_task_fails_activity_on_failed_reply():
    """Bug class: a FAILED reply must fail the task's activity (not complete it),
    so a failed task never shows as completed work."""
    act = _FakeActivityPort()
    ex = TaskDispatcher(activity_port=act)
    ex.create_task_run_if_enabled = AsyncMock(return_value=None)
    ex._publish_and_await = AsyncMock(
        return_value=TaskResult(task_id="t1", status="FAILED", error="timeout")
    )

    result = await ex.dispatch_task(_envelope(), "run-1", heartbeat_interval=999)

    assert result.status == "FAILED"
    assert act.completed == [] and len(act.failed) == 1
