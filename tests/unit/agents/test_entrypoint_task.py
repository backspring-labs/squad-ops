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
from squadops.config.schema import CommsDeliveryConfig
from squadops.ports.comms.queue import AckPolicy
from squadops.ports.comms.task_attempts import TaskAttemptsPort
from squadops.tasks.models import TaskEnvelope, TaskResult


class _Attempts(TaskAttemptsPort):
    """A task delivery record in this process (#1977), or one that can't be read (``down``)."""

    def __init__(self, *, down: bool = False) -> None:
        self.attempts: dict[str, int] = {}
        self.done: set[str] = set()
        self.down = down

    async def completed(self, task_id: str) -> bool:
        if self.down:
            raise ConnectionError("redis unreachable")
        return task_id in self.done

    async def begin_attempt(self, task_id: str) -> int:
        if self.down:
            raise ConnectionError("redis unreachable")
        self.attempts[task_id] = self.attempts.get(task_id, 0) + 1
        return self.attempts[task_id]

    async def mark_completed(self, task_id: str) -> None:
        self.done.add(task_id)


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

    @pytest.mark.parametrize("published", [True, False], ids=["reply-out", "publish-failed"])
    async def test_a_task_is_marked_completed_only_once_its_reply_is_out(
        self, runner, published
    ) -> None:
        """#1977, §5.3, through the handler the comms path calls. Bugs caught: a task marked
        completed before its reply, so a redelivery after a lost publish is acked as a duplicate
        and the cycle hears nothing; or one never marked, so a lost ack re-runs it."""
        runner._task_attempts = _Attempts()
        if not published:
            runner._queue.publish.side_effect = ConnectionError("broker gone")
        payload = _make_envelope_payload(_sample_envelope(), reply_queue="neo_replies")

        if published:
            await runner._handle_task_envelope(payload, payload["metadata"])
        else:
            with pytest.raises(ConnectionError):
                await runner._handle_task_envelope(payload, payload["metadata"])

        assert runner._task_attempts.done == ({"task_123"} if published else set())

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
        # #1977: a comms delivery whose callback raises is handed back for redelivery (its task's
        # attempts bound it); a control notice is acked whatever its callback does.
        subscribed = {
            c.args[0]: (c.kwargs["on_message"], c.kwargs["ack_policy"])
            for c in r._queue.subscribe.await_args_list
        }
        assert subscribed == {
            "neo_comms": (r._process_comms_message, AckPolicy.REDELIVER_ON_FAILURE),
            "neo_control": (r._process_control_message, AckPolicy.ACK_ALWAYS),
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
    """`_process_comms_message` — the subscribe() callback — routes actions and never acks (the
    subscription layer owns the ack). It raises only a task's own failure, which the
    subscription hands back for redelivery (#1977)."""

    def _runner(self):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._handle_chat_message = AsyncMock()
            r._handle_task_envelope = AsyncMock()
            r._task_attempts = _Attempts()
            r._delivery = CommsDeliveryConfig()
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
        payload = {
            "action": "comms.task",
            "metadata": {"reply_queue": "q"},
            "payload": {"task_id": "t1"},
        }

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

    async def test_a_tasks_failure_is_handed_back_and_a_chats_is_swallowed(self) -> None:
        """#1977. A task whose handler raised propagates, so the subscription hands the delivery
        back for redelivery and its attempts bound it. Bug caught: a task's failure acked and
        lost, as D12's ack-always did. A chat has no task budget to bound it, so its failure is
        swallowed and acked as before. Neither callback acks here: the subscription owns it."""
        r = self._runner()
        r._handle_task_envelope.side_effect = RuntimeError("handler blew up")
        r._handle_chat_message.side_effect = RuntimeError("chat blew up")
        task = {"action": "comms.task", "metadata": {}, "payload": {"task_id": "t1"}}
        chat = {"action": "comms.chat", "metadata": {}, "payload": {}}

        with pytest.raises(RuntimeError, match="handler blew up"):
            await r._process_comms_message(self._message(task))
        await r._process_comms_message(self._message(chat))

        r._queue.ack.assert_not_awaited()


class TestADispatchedTaskIsBoundedByItsAttempts:
    """#1977, SIP-Agent-Comms-Delivery-Guarantees §5.1, §5.3 and §5.3a as amended 2026-10-14.

    #1626: the qa agent segfaulted inside a repair handler and was restarted 37 times on the
    same redelivered message. The broker keeps no count of a classic queue's redeliveries,
    neither a raising handler's requeue nor a dying agent's (measured, #1977), so the agent
    counts each task's attempts in Redis before the handler runs, marks it completed only after
    its reply is out, and quarantines and fails it past its attempts. With no readable record,
    #1627's rule stands in: a redelivered task is failed unrun."""

    def _runner(self, attempts: _Attempts | None = None):
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "eve"
            r.role = "qa"
            r._queue = AsyncMock()
            r._handle_chat_message = AsyncMock()
            r._handle_task_envelope = AsyncMock()
            r._task_attempts = attempts if attempts is not None else _Attempts()
            r._delivery = CommsDeliveryConfig(max_attempts=3)
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

    TASK = "repair-run_4c30fc23-00-qa.test_repair"
    PAYLOAD = {
        "action": "comms.task",
        "metadata": {"reply_queue": "q", "correlation_id": "c1"},
        "payload": {"task_id": TASK, "task_type": "qa.test_repair", "correlation_id": "c1"},
    }

    def _published(self, r) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for call in r._queue.publish.await_args_list:
            out.setdefault(call.args[0], []).append(json.loads(call.args[1]))
        return out

    async def test_a_task_that_kills_its_agent_runs_within_its_attempts_then_is_failed(self):
        """The bug: #1626's handler ran 37 times on one delivery. Here each delivery of the task
        dies (the handler is never seen to finish), so the next one is a redelivery; the
        attempts are counted in the record that outlives the process. Three run, the fourth is
        quarantined with why and failed for the cycle to decide."""
        attempts = _Attempts()
        for n in range(1, 5):
            r = self._runner(attempts)  # a fresh process each time: the record is what persists
            await r._process_comms_message(self._message(self.PAYLOAD, redelivered=n > 1))
            ran = r._handle_task_envelope.await_count

            if n <= 3:
                assert (ran, self._published(r)) == (1, {}), f"delivery {n}"
        assert ran == 0
        published = self._published(r)
        [quarantined] = published["comms.dlq"]
        [failed] = published["q"]
        assert (quarantined["task_id"], quarantined["reason"]) == (
            self.TASK,
            "3 deliveries ran and none completed",
        )
        assert quarantined["delivery"] == self.PAYLOAD
        assert (failed["action"], failed["payload"]["task_id"], failed["payload"]["status"]) == (
            "comms.task.result",
            self.TASK,
            "FAILED",
        )
        assert "3 deliveries of this task ran and none completed" in failed["payload"]["error"]

    async def test_a_completed_task_redelivered_is_acked_as_a_duplicate_never_run(self):
        """§5.3: the work finished and its reply went out, but the ack was lost. Bug caught: the
        task run a second time, or (as #1627's rule did) answered with a FAILED that races the
        success it follows."""
        attempts = _Attempts()
        attempts.done.add(self.TASK)
        r = self._runner(attempts)

        await r._process_comms_message(self._message(self.PAYLOAD, redelivered=True))

        r._handle_task_envelope.assert_not_awaited()
        r._queue.publish.assert_not_awaited()
        assert attempts.attempts == {}

    @pytest.mark.parametrize("redelivered", [True, False], ids=["redelivered", "first-delivery"])
    async def test_with_no_readable_record_a_redelivery_is_failed_unrun(self, redelivered):
        """Redis unreachable. Bug caught: losing the record reopening #1626's crash loop. The
        rule it replaces stands in: a redelivery proves only that a prior delivery was not
        acknowledged, so the task is failed, claiming no more than that; a first delivery runs."""
        r = self._runner(_Attempts(down=True))

        await r._process_comms_message(self._message(self.PAYLOAD, redelivered=redelivered))

        if redelivered:
            r._handle_task_envelope.assert_not_awaited()
            [failed] = self._published(r)["q"]
            err = failed["payload"]["error"]
            assert failed["payload"]["status"] == "FAILED"
            assert "not acknowledged" in err and "completion is unknown" in err
        else:
            r._handle_task_envelope.assert_awaited_once()
            r._queue.publish.assert_not_awaited()

    async def test_a_task_with_no_id_is_quarantined_and_failed_not_run(self):
        """Nothing to count its attempts under, so it can't be bounded. The failure must not
        depend on the envelope being well-formed: a failure that throws leaves silence."""
        r = self._runner()
        payload = {"action": "comms.task", "metadata": {"reply_queue": "q"}, "payload": {}}

        await r._process_comms_message(self._message(payload, redelivered=False))

        r._handle_task_envelope.assert_not_awaited()
        published = self._published(r)
        assert published["comms.dlq"][0]["reason"] == "the envelope carries no task id"
        assert published["q"][0]["payload"]["task_id"] == "unknown"
        assert published["q"][0]["payload"]["status"] == "FAILED"

    async def test_a_redelivered_CHAT_delivery_is_not_counted_or_refused(self):
        """Scope is task dispatch only (§5.3a): chat has no cycle budget to hand a failed round
        to, and claiming this bounds consumer poison loops in general would overstate it."""
        attempts = _Attempts()
        r = self._runner(attempts)
        chat = {"action": "comms.chat", "metadata": {"correlation_id": "c1"}, "payload": {}}

        await r._process_comms_message(self._message(chat, redelivered=True))

        r._handle_chat_message.assert_awaited_once()
        r._queue.publish.assert_not_awaited()
        assert attempts.attempts == {}


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
