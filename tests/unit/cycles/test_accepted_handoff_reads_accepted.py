"""#3000 (the 2.9 plan's item 5; SIP-0077 §24a): an accepted qa hand-off reads accepted
everywhere, and a rejected one reads failed everywhere.

Entered at ``TaskDispatcher.dispatch_with_retry``, the call the executor makes for every task,
with a real dispatcher over a reply router and mocks for the three places a task's ending is
read: the Prefect task run (the workflow tracker), the agent's activity, and the cycle events
the metrics bridge counts.

What bugs would these catch?
- The hand-off's reply settling the task before the product's runner was asked: a task run set
  ``Failed`` that nothing sets again, an activity failed with "left to the product's runner", and
  a ``task.failed`` counted in ``tasks_failed_total``, all for a suite that was then accepted.
  That was the behaviour before #3000 (the 2.8.0 package's screenshot shows the red bar).
- The verdict read after the routing, so a rejected hand-off's task run stays open across the
  whole correction that follows it.
- A verdict that can't be read leaving the task run and the activity open.
- The hold leaking to a reply that is no hand-off, or to a task dispatched with no ``HandOff``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import Cycle, TaskFlowPolicy
from squadops.events.bridges.metrics import MetricsBridge
from squadops.events.types import EventType
from squadops.execution.product_suite import left_to_the_product_runner
from squadops.execution.task_dispatcher import HandOff, TaskDispatcher
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 26, tzinfo=UTC)
LEFT = "left to the product's runner"
#: The reply of a qa image that left the suite to the product's own runner (#2949).
_HANDED_OFF = {
    "validation_result": {
        "checks": [
            {"check": "tests_pass", "executed": False, "passed": False, "runner": "product_runner"}
        ]
    }
}
#: A suite the image ran and failed: a failed attempt, and no hand-off.
_RAN_AND_FAILED = {
    "validation_result": {
        "checks": [
            {"check": "tests_pass", "executed": True, "passed": False, "runner": "product_runner"}
        ]
    }
}
_CYCLE = Cycle(
    cycle_id="cyc_1",
    project_id="prj",
    created_at=NOW,
    created_by="s",
    prd_ref="prd",
    squad_profile_id="full",
    squad_profile_snapshot_ref="x",
    task_flow_policy=TaskFlowPolicy(mode="sequential"),
    build_strategy="fresh",
)
_ENVELOPE = TaskEnvelope(
    task_id="task_qa",
    agent_id="eve",
    cycle_id="cyc_1",
    pulse_id="p",
    project_id="prj",
    task_type="qa.test",
    correlation_id="c",
    causation_id="c",
    trace_id="t",
    span_id="s",
    metadata={"role": "qa"},
)


class _World:
    """A dispatcher, the reply its agent sends, and everything that reads the task's ending."""

    def __init__(self, reply_router, outputs: dict) -> None:
        self.tracker, self.activity, self.bus = AsyncMock(), AsyncMock(), MagicMock()
        self.tracker.create_task_run.return_value = "tr_1"
        self.activity.start_activity.return_value = MagicMock(runtime_activity_id="act_1")
        self.dispatcher = TaskDispatcher(
            queue=reply_router.bind(AsyncMock()),
            reply_router=reply_router,
            workflow_tracker=self.tracker,
            activity_port=self.activity,
            event_bus=self.bus,
            task_timeout=5.0,
        )
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"], status="FAILED", error=LEFT, outputs=outputs
        )
        #: What happened, in order: the verdict's read, the routing, and each signal as set.
        self.order: list[str] = []
        self.tracker.set_task_run_state.side_effect = lambda _id, kind, name: self.order.append(
            f"task_run:{name}"
        )
        self.bus.emit.side_effect = lambda event, **_kw: self.order.append(f"event:{event}")

    async def run(self, hand_off: HandOff | None, action: str):
        async def route(_result):
            self.order.append("routed")
            return action

        async def unscreened(result):
            return result

        return await self.dispatcher.dispatch_with_retry(
            _ENVELOPE,
            _ENVELOPE,
            _CYCLE,
            "run_1",
            flow_run_id="fr_1",
            handle_task_outcome=route,
            screen_success=unscreened,
            hand_off=hand_off,
        )

    def verdict(self, accepted) -> HandOff:
        async def read(_result):
            self.order.append("verdict")
            if isinstance(accepted, BaseException):
                raise accepted
            return accepted

        return HandOff(left=left_to_the_product_runner, accepted=read)

    @property
    def task_events(self) -> list[str]:
        return [e.removeprefix("event:") for e in self.order if e.startswith("event:task.")]

    @property
    def task_run_states(self) -> list[str]:
        return [e.removeprefix("task_run:") for e in self.order if e.startswith("task_run:")]


def _counted(world: _World) -> dict[str, int]:
    """The metrics bridge's counters over the events the dispatcher emitted."""
    counts: dict[str, int] = {}
    metrics = MagicMock()
    metrics.counter.side_effect = lambda name, **_kw: counts.__setitem__(
        name, counts.get(name, 0) + 1
    )
    bridge = MetricsBridge(metrics)
    for call in world.bus.emit.call_args_list:
        bridge.on_event(
            MagicMock(event_type=call.args[0], entity_type="task", payload=call.kwargs["payload"])
        )
    return counts


async def test_an_accepted_hand_off_ends_succeeded_in_all_four(reply_router):
    world = _World(reply_router, _HANDED_OFF)

    succeeded, _result = await world.run(world.verdict(True), "accept_patch")

    assert succeeded is True
    assert world.task_run_states == ["Running", "HandedOff", "Completed"]
    assert world.activity.complete_activity.await_args_list[0].args == ("act_1",)
    assert world.activity.fail_activity.await_count == 0
    assert world.task_events == [EventType.TASK_HANDED_OFF, EventType.TASK_SUCCEEDED]
    assert _counted(world) == {"tasks_succeeded_total": 1}
    # The task ended on the verdict, before its attempt was routed.
    assert world.order.index("verdict") < world.order.index("task_run:Completed")
    assert world.order.index(f"event:{EventType.TASK_SUCCEEDED}") < world.order.index("routed")


async def test_a_rejected_hand_off_ends_failed_in_all_four_before_its_correction(reply_router):
    world = _World(reply_router, _HANDED_OFF)

    succeeded, _result = await world.run(world.verdict(False), "break_correction")

    assert succeeded is False
    assert world.task_run_states == ["Running", "HandedOff", "Failed"]
    assert world.activity.fail_activity.await_args_list[0].args == ("act_1", LEFT)
    assert world.activity.complete_activity.await_count == 0
    assert world.task_events == [EventType.TASK_HANDED_OFF, EventType.TASK_FAILED]
    assert _counted(world) == {"tasks_failed_total": 1}
    # Failed before the routing, which is where the correction that follows it runs.
    assert world.order.index("task_run:Failed") < world.order.index("routed")
    assert world.order.count("verdict") == 1


async def test_a_verdict_that_cant_be_read_ends_the_task_failed_and_raises(reply_router):
    world = _World(reply_router, _HANDED_OFF)

    with pytest.raises(RuntimeError, match="the sandbox didn't answer"):
        await world.run(world.verdict(RuntimeError("the sandbox didn't answer")), "accept_patch")

    assert world.task_run_states == ["Running", "HandedOff", "Failed"]
    assert world.activity.fail_activity.await_args_list[0].args == (
        "act_1",
        "RuntimeError: the sandbox didn't answer",
    )
    assert world.task_events == [EventType.TASK_HANDED_OFF, EventType.TASK_FAILED]
    assert "routed" not in world.order


@pytest.mark.parametrize(
    ("outputs", "with_hand_off"),
    [(_RAN_AND_FAILED, True), (_HANDED_OFF, False)],
    ids=["a suite the image ran and failed", "a task dispatched with no hand-off"],
)
async def test_a_reply_that_is_held_by_nothing_settles_as_it_always_did(
    reply_router, outputs, with_hand_off
):
    """The edges: a failed attempt the product's runner may still overrule (#2818) is a failed
    attempt, and a task whose caller declares no hand-off is never held, whatever its reply."""
    world = _World(reply_router, outputs)
    hand_off = world.verdict(True) if with_hand_off else None

    succeeded, _result = await world.run(hand_off, "accept_patch")

    assert succeeded is True  # the routing's own answer, as before
    assert world.task_run_states == ["Running", "Failed"]
    assert world.activity.fail_activity.await_args_list[0].args == ("act_1", LEFT)
    assert world.task_events == [EventType.TASK_FAILED]
    assert "verdict" not in world.order


async def test_the_hold_ends_with_the_attempt_so_a_correction_dispatch_settles_itself(
    reply_router,
):
    """Bug caught: the hold left set while the attempt is routed, so a repair task the
    correction dispatches through ``dispatch_task``, replying in a hand-off's shape, is left
    open with nothing to end it."""
    world = _World(reply_router, _HANDED_OFF)
    repair = TaskEnvelope(
        task_id="task_repair",
        agent_id="eve",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="prj",
        task_type="qa.repair",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        metadata={"role": "qa"},
    )

    async def route(_result):
        await world.dispatcher.dispatch_task(repair, "run_1", flow_run_id="fr_1")
        return "break_correction"

    async def unscreened(result):
        return result

    await world.dispatcher.dispatch_with_retry(
        _ENVELOPE,
        _ENVELOPE,
        _CYCLE,
        "run_1",
        flow_run_id="fr_1",
        handle_task_outcome=route,
        screen_success=unscreened,
        hand_off=world.verdict(False),
    )

    # Two tasks, each ended once: the hand-off on its verdict, the repair on its own reply.
    assert world.task_run_states == ["Running", "HandedOff", "Failed", "Running", "Failed"]
    assert world.activity.fail_activity.await_count == 2
