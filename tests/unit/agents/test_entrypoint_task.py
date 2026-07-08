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

        r._queue.subscribe.assert_awaited_once()
        args, kwargs = r._queue.subscribe.await_args
        assert args[0] == "neo_comms"
        assert kwargs["on_message"] == r._process_comms_message
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

        handle.cancel.assert_awaited_once()
        assert teardown_order == ["cancel", "close"]


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
