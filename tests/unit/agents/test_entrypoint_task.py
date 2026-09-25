"""Tests for the AgentRunner comms path.

Verifies that the agent consumes its comms queue push-style (#323), routes
deliveries to the right action handler, correctly deserializes incoming
TaskEnvelopes, submits them to the local orchestrator, and publishes results
to the reply queue.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.comms.queue_message import QueueMessage
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_agents]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope_payload(envelope: TaskEnvelope, reply_queue: str = "cycle_results_run_001"):
    """Build the full message payload as the agent consumer would receive."""
    return {
        "action": "comms.task",
        "metadata": {
            "reply_queue": reply_queue,
            "correlation_id": envelope.correlation_id,
        },
        "payload": envelope.to_dict(),
    }


def _sample_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        timeout=600.0,  # the dispatcher stamps the declared wait (1.8.2 item 15)
        task_id="task_123",
        agent_id="neo",
        cycle_id="cyc_001",
        pulse_id="pulse_001",
        project_id="proj_001",
        task_type="development.design",
        correlation_id="corr_001",
        causation_id="cause_001",
        trace_id="trace_001",
        span_id="span_001",
        inputs={"prd": "Build something", "resolved_config": {}},
        metadata={"step_index": 1, "role": "dev"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandleTaskEnvelope:
    """AgentRunner._handle_task_envelope dispatches to orchestrator."""

    @pytest.fixture
    def runner(self):
        """Create a minimal AgentRunner with mocked internals."""
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._config = MagicMock()
            r._config.llm.timeout = 180.0

            # Mock orchestrator inside system
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_task.return_value = TaskResult(
                task_id="task_123",
                status="SUCCEEDED",
                outputs={"summary": "implemented"},
            )
            r.system = MagicMock()
            r.system.orchestrator = mock_orchestrator

            return r

    async def test_dispatches_to_orchestrator(self, runner) -> None:
        """submit_task() is called with the deserialized TaskEnvelope."""
        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope)

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner.system.orchestrator.submit_task.assert_awaited_once()
        submitted = runner.system.orchestrator.submit_task.call_args.args[0]
        assert submitted.task_id == "task_123"
        assert submitted.task_type == "development.design"
        assert submitted.agent_id == "neo"

    async def test_publishes_result_to_reply_queue(self, runner) -> None:
        """TaskResult is published to the reply_queue from metadata."""
        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope, reply_queue="cycle_results_run_001")

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_awaited_once()
        call_args = runner._queue.publish.call_args
        assert call_args.args[0] == "cycle_results_run_001"

        published = json.loads(call_args.args[1])
        assert published["action"] == "comms.task.result"
        assert published["payload"]["task_id"] == "task_123"
        assert published["payload"]["status"] == "SUCCEEDED"

    async def test_error_returns_failed_result(self, runner) -> None:
        """If orchestrator raises, a FAILED TaskResult is published."""
        runner.system.orchestrator.submit_task.side_effect = RuntimeError("LLM timeout")

        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope)

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_awaited_once()
        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["payload"]["status"] == "FAILED"
        assert "LLM timeout" in published["payload"]["error"]

    async def test_no_reply_queue_logs_warning(self, runner) -> None:
        """If no reply_queue in metadata, result is not published."""
        envelope = _sample_envelope()
        payload = {
            "action": "comms.task",
            "metadata": {},  # no reply_queue
            "payload": envelope.to_dict(),
        }

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_not_awaited()

    async def test_result_includes_correlation_id(self, runner) -> None:
        """Published result metadata includes the envelope's correlation_id."""
        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope)

        await runner._handle_task_envelope(payload, payload["metadata"])

        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["metadata"]["correlation_id"] == "corr_001"


class TestConsumeTasksPushConsumer:
    """`_consume_tasks` registers ONE persistent subscribe() consumer (#323),
    declares the reply queue first (SIP-0094 D9), and tears the consumer down
    on shutdown."""

    def _runner(self):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._shutdown_event = asyncio.Event()
            return r

    async def test_declares_replies_queue_before_subscribing(self) -> None:
        """ensure_queue("{agent_id}_replies") must be awaited before the comms
        subscription registers (SIP-0094 D9) — a consumer that comes up first
        can receive a task whose reply queue doesn't exist yet."""
        r = self._runner()
        r._shutdown_event.set()  # tear down right after the subscription is up

        await r._consume_tasks()

        r._queue.ensure_queue.assert_awaited_once_with("neo_replies")
        names = [call[0] for call in r._queue.mock_calls]
        assert names.index("ensure_queue") < names.index("subscribe")

    async def test_subscribes_push_style_not_poll(self) -> None:
        """One subscribe() on the comms queue, routed to the runner's message
        processor; the poll-based consume() path must be gone — its per-poll
        open/close churn is the bug #323 removes."""
        r = self._runner()
        r._shutdown_event.set()

        await r._consume_tasks()

        # The comms queue, and (#1648) the control queue a cancel notice arrives on — consumed
        # beside it so a notice reaches the agent while the comms consumer is busy.
        subscribed = {c.args[0]: c.kwargs["on_message"] for c in r._queue.subscribe.await_args_list}
        assert subscribed == {
            "neo_comms": r._process_comms_message,
            "neo_control": r._process_control_message,
        }
        r._queue.consume.assert_not_awaited()

    async def test_consumer_survives_until_shutdown_then_cancels_before_close(self) -> None:
        """The subscription must stay up until the shutdown event fires, then
        be cancelled BEFORE the connection closes — close-then-cancel would
        strand the resubscribe loop against a dead connection."""
        r = self._runner()
        teardown_order: list[str] = []
        handle = AsyncMock()
        handle.cancel.side_effect = lambda: teardown_order.append("cancel")
        r._queue.subscribe.return_value = handle
        r._queue.close.side_effect = lambda: teardown_order.append("close")

        task = asyncio.create_task(r._consume_tasks())
        for _ in range(5):
            await asyncio.sleep(0)  # let the task reach the shutdown wait

        assert not task.done()
        handle.cancel.assert_not_awaited()

        r._shutdown_event.set()
        await asyncio.wait_for(task, timeout=1)

        # Both subscriptions cancelled, and both before the connection closes.
        assert handle.cancel.await_count == 2
        assert teardown_order == ["cancel", "cancel", "close"]


class TestProcessCommsMessage:
    """`_process_comms_message` — the subscribe() callback — routes actions,
    never raises, and never acks (the subscription layer owns the ack)."""

    def _runner(self):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._handle_chat_message = AsyncMock()
            r._handle_task_envelope = AsyncMock()
            return r

    @staticmethod
    def _message(body: dict | str) -> QueueMessage:
        return QueueMessage(
            message_id="42",
            queue_name="neo_comms",
            payload=body if isinstance(body, str) else json.dumps(body),
            receipt_handle="42",
            attributes={},
        )

    async def test_routes_task_action_with_parsed_payload(self) -> None:
        r = self._runner()
        payload = {"action": "comms.task", "metadata": {"reply_queue": "q"}, "payload": {}}

        await r._process_comms_message(self._message(payload))

        r._handle_task_envelope.assert_awaited_once_with(payload, {"reply_queue": "q"})
        r._handle_chat_message.assert_not_awaited()
        # The subscription acks every delivery itself; a second ack here would
        # raise on the same delivery tag.
        r._queue.ack.assert_not_awaited()

    async def test_routes_chat_action(self) -> None:
        r = self._runner()
        payload = {"action": "comms.chat", "metadata": {"correlation_id": "c1"}, "payload": {}}

        await r._process_comms_message(self._message(payload))

        r._handle_chat_message.assert_awaited_once_with(payload, {"correlation_id": "c1"})
        r._handle_task_envelope.assert_not_awaited()

    async def test_unknown_action_is_dropped_without_dispatch(self) -> None:
        r = self._runner()

        await r._process_comms_message(self._message({"action": "comms.bogus"}))

        r._handle_chat_message.assert_not_awaited()
        r._handle_task_envelope.assert_not_awaited()

    async def test_malformed_json_never_raises(self) -> None:
        """An unparseable delivery must be swallowed: if the callback raised,
        the message would still be acked upstream, but the agent-context error
        log (agent_id + message_id) would be lost to a generic transport log."""
        r = self._runner()

        await r._process_comms_message(self._message("{not json"))

        r._handle_task_envelope.assert_not_awaited()
        r._handle_chat_message.assert_not_awaited()

    async def test_handler_failure_is_swallowed_and_never_acked_here(self) -> None:
        """A raising handler must not propagate (the consumer keeps running)
        and must not trigger an ack from the callback — matching the old poll
        loop's log-and-ack-anyway policy, with the ack owned upstream."""
        r = self._runner()
        r._handle_task_envelope.side_effect = RuntimeError("handler blew up")
        payload = {"action": "comms.task", "metadata": {}}

        await r._process_comms_message(self._message(payload))

        r._queue.ack.assert_not_awaited()


class TestARedeliveredTaskIsRefusedNotRerun:
    """#1626: the qa agent segfaulted inside a repair handler and was restarted 37 times
    on the same redelivered message — no record, no handler RESULT reaching the correction /
    deadlock / repeated-signature machinery, and a `running` row that would have made every
    later preflight refuse. (`TaskDispatcher`'s task timeout does not need a handler to
    return; the claim is scoped to the rules that consume a result.)

    SIP-0094 D12 already forbids poison-looping by acking a failing callback, but that is
    enforceable only when the callback RETURNS. A process that DIES never acks, so the
    broker requeues.

    `redelivered` proves only that a prior delivery was NOT ACKNOWLEDGED — not that the work
    did not happen. The ack follows the callback, so the connection can close after the work
    and its reply succeeded, and the broker may mark a message redelivered that never
    reached the prior consumer. Completion is UNKNOWN, and the rule follows from the
    uncertainty rather than from a cause (SIP §5.3a)."""

    def _runner(self):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "eve"
            r.role = "qa"
            r._queue = AsyncMock()
            r._handle_chat_message = AsyncMock()
            r._handle_task_envelope = AsyncMock()
            return r

    @staticmethod
    def _message(body: dict, *, redelivered: bool) -> QueueMessage:
        return QueueMessage(
            message_id="42",
            queue_name="eve_comms",
            payload=json.dumps(body),
            receipt_handle="42",
            attributes={"redelivered": redelivered},
        )

    PAYLOAD = {
        "action": "comms.task",
        "metadata": {"reply_queue": "q", "correlation_id": "c1"},
        "payload": {
            "task_id": "repair-run_4c30fc23-00-qa.test_repair",
            "task_type": "qa.test_repair",
            "correlation_id": "c1",
        },
    }

    async def test_a_redelivered_task_is_not_executed_again(self) -> None:
        """The bug: #1626's handler ran 37 times on the same delivery."""
        r = self._runner()

        await r._process_comms_message(self._message(self.PAYLOAD, redelivered=True))

        r._handle_task_envelope.assert_not_awaited()

    async def test_the_refusal_publishes_a_FAILED_result_naming_the_reason(self) -> None:
        """The cycle must hear a failed round with a reason, not silence — every
        rule that consumes a handler RESULT (the correction budget, the #1221 deadlock
        rule) is starved by a death that produces none."""
        r = self._runner()

        await r._process_comms_message(self._message(self.PAYLOAD, redelivered=True))

        r._queue.publish.assert_awaited_once()
        queue, body = r._queue.publish.await_args.args
        assert queue == "q"
        sent = json.loads(body)
        assert sent["action"] == "comms.task.result"
        assert sent["payload"]["task_id"] == "repair-run_4c30fc23-00-qa.test_repair"
        assert sent["payload"]["status"] == "FAILED"
        # the error must claim only what the transport can prove
        err = sent["payload"]["error"]
        assert "not acknowledged" in err and "completion is unknown" in err
        assert "did not return" not in err, "the transport cannot prove the work did not run"

    async def test_a_malformed_envelope_is_still_refused_with_a_result(self) -> None:
        """The refusal must not depend on the envelope being well-formed: the whole
        premise of this path is that the previous attempt died. A refusal that throws
        leaves the cycle with silence, which is the failure it exists to prevent."""
        r = self._runner()
        payload = {"action": "comms.task", "metadata": {"reply_queue": "q"}, "payload": {}}

        await r._process_comms_message(self._message(payload, redelivered=True))

        r._handle_task_envelope.assert_not_awaited()
        r._queue.publish.assert_awaited_once()
        sent = json.loads(r._queue.publish.await_args.args[1])
        assert sent["payload"]["task_id"] == "unknown"
        assert sent["payload"]["status"] == "FAILED"

    async def test_a_redelivered_CHAT_delivery_is_not_refused(self) -> None:
        """Scope is task dispatch only (SIP §5.3a). Chat has no cycle budget to hand a
        failed round to, and claiming this rule bounds consumer poison loops in general
        would overstate it."""
        r = self._runner()
        chat = {"action": "comms.chat", "metadata": {"correlation_id": "c1"}, "payload": {}}

        await r._process_comms_message(self._message(chat, redelivered=True))

        r._handle_chat_message.assert_awaited_once()
        r._queue.publish.assert_not_awaited()

    async def test_a_first_delivery_still_runs_normally(self) -> None:
        """The control: the bound must not cost an ordinary task its first attempt."""
        r = self._runner()

        await r._process_comms_message(self._message(self.PAYLOAD, redelivered=False))

        r._handle_task_envelope.assert_awaited_once()
        r._queue.publish.assert_not_awaited()

    async def test_a_message_with_no_redelivered_attribute_runs_normally(self) -> None:
        """Adapters that do not surface the flag must not have every task refused."""
        r = self._runner()
        msg = QueueMessage(
            message_id="42",
            queue_name="eve_comms",
            payload=json.dumps(self.PAYLOAD),
            receipt_handle="42",
            attributes={},
        )

        await r._process_comms_message(msg)

        r._handle_task_envelope.assert_awaited_once()


class TestTheHandlerIsBoundedByTheDeclaredWait:
    """1.8.2 item 15: the agent bounds a dispatched task's handler by the wait the orchestrator
    declared and stamped on the task, never by its own model-call timeout."""

    @pytest.fixture
    def runner(self):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._config = MagicMock()
            r._config.llm.timeout = 180.0
            r.system = MagicMock()
            r.system.orchestrator = AsyncMock()
            r.system.orchestrator.submit_task.return_value = TaskResult(
                task_id="task_123", status="SUCCEEDED", outputs={}
            )
            return r

    async def test_the_declared_wait_bounds_the_handler_not_the_model_timeout(self, runner):
        """Wiring, entered at ``_handle_task_envelope`` — the comms path. Bug this catches:
        the handler killed at llm.timeout (180 s here) while the orchestrator waits the
        declared 600 s, or the reverse."""
        payload = _make_envelope_payload(_sample_envelope())

        await runner._handle_task_envelope(payload, payload["metadata"])

        assert runner.system.orchestrator.submit_task.call_args.kwargs["timeout_seconds"] == 600.0

    async def test_a_task_without_a_declared_wait_is_refused_not_defaulted(self, runner):
        """Require, don't default (2026-09-14): a runtime API older than item 15 sends no
        wait, and the agent says so instead of bounding the handler by a number nobody chose."""
        import dataclasses

        payload = _make_envelope_payload(dataclasses.replace(_sample_envelope(), timeout=None))

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner.system.orchestrator.submit_task.assert_not_awaited()
        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["payload"]["status"] == "FAILED"
        assert "carries no declared timeout" in published["payload"]["error"]


class TestACancelledRunsTaskIsDropped:
    """#1648 (1.8.2 item 10): the agent drops a task whose run was cancelled — before it runs if
    the notice came first, mid-task if the notice arrives while it runs — acks it and replies
    nothing, since nothing awaits a cancelled run's task."""

    @pytest.fixture
    def runner(self):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._config = MagicMock()
            r.system = MagicMock()
            r.system.ports.llm_observability = None
            r.system.orchestrator = AsyncMock()
            r.system.orchestrator.submit_task.return_value = TaskResult(
                task_id="task_123", status="SUCCEEDED", outputs={}
            )
            return r

    @staticmethod
    def _payload(run_id: str = "run_ab12cd34ef56"):
        import dataclasses

        envelope = _sample_envelope()
        envelope = dataclasses.replace(envelope, metadata={**envelope.metadata, "run_id": run_id})
        return _make_envelope_payload(envelope)

    @staticmethod
    def _notice(*run_ids: str) -> QueueMessage:
        return QueueMessage(
            message_id="m",
            queue_name="neo_control",
            payload=json.dumps(
                {
                    "action": "comms.run_cancelled",
                    "payload": {"cycle_id": "cyc", "run_ids": list(run_ids)},
                }
            ),
            receipt_handle="r",
            attributes={},
        )

    async def test_a_task_of_a_run_already_cancelled_never_runs(self, runner, caplog):
        """Wiring, entered at the control callback and then the comms path. Bug this catches:
        the #1648 ghost — a task consumed after its run was cancelled, run to completion."""
        await runner._process_control_message(self._notice("run_ab12cd34ef56"))
        payload = self._payload()

        with caplog.at_level("INFO"):
            await runner._handle_task_envelope(payload, payload["metadata"])

        runner.system.orchestrator.submit_task.assert_not_awaited()
        runner._queue.publish.assert_not_awaited()
        assert "dropped before it ran (#1648)" in caplog.text

    async def test_a_notice_mid_task_stops_it_and_nothing_is_replied(self, runner, caplog):
        """Bug this catches: the notice recorded but the running task left to finish, which is
        every ghost generation #1648 measured (5,709 tokens after the cancel)."""
        started = asyncio.Event()
        finished = asyncio.Event()

        async def long_generation(envelope, timeout_seconds=None):
            started.set()
            await asyncio.sleep(3600)
            finished.set()

        runner.system.orchestrator.submit_task.side_effect = long_generation
        payload = self._payload()
        handling = asyncio.create_task(runner._handle_task_envelope(payload, payload["metadata"]))
        await started.wait()

        with caplog.at_level("INFO"):
            await runner._process_control_message(self._notice("run_ab12cd34ef56"))
            await asyncio.wait_for(handling, timeout=5)

        assert not finished.is_set()
        runner._queue.publish.assert_not_awaited()
        assert "stopped mid-task (#1648)" in caplog.text

    async def test_a_notice_for_another_run_leaves_the_task_alone(self, runner):
        release = asyncio.Event()

        async def generation(envelope, timeout_seconds=None):
            await release.wait()
            return TaskResult(task_id="task_123", status="SUCCEEDED", outputs={})

        runner.system.orchestrator.submit_task.side_effect = generation
        payload = self._payload()
        handling = asyncio.create_task(runner._handle_task_envelope(payload, payload["metadata"]))
        await asyncio.sleep(0)
        await runner._process_control_message(self._notice("run_other0000"))
        release.set()
        await asyncio.wait_for(handling, timeout=5)

        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["payload"]["status"] == "SUCCEEDED"

    async def test_a_malformed_control_message_is_dropped_not_raised(self, runner):
        bad = QueueMessage(
            message_id="m",
            queue_name="neo_control",
            payload="{not json",
            receipt_handle="r",
            attributes={},
        )
        await runner._process_control_message(bad)
        assert not runner._cancelled_runs.is_cancelled("run_ab12cd34ef56")

    def test_a_told_run_expires_so_the_set_never_grows_for_the_containers_life(self):
        from squadops.agents.entrypoint import CancelledRuns

        runs = CancelledRuns()
        runs.add(["run_old"], now=0.0)
        runs.add(["run_new"], now=CancelledRuns.TTL_SECONDS + 1)
        assert not runs.is_cancelled("run_old") and runs.is_cancelled("run_new")
