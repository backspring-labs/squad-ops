"""Tests for TaskDispatcher (adapters/cycles/task_dispatcher.py).

The request/reply transport moved out of DispatchedFlowExecutor in SIP-0097
slice 5; these classes moved with it (from test_dispatched_flow_executor.py,
assertions unchanged) and now construct the collaborator directly — no
executor anywhere (SIP-0097 §9). Covers publish/await mechanics, timeout,
the SIP-0087 Prefect task-run lifecycle + contextvar scope + heartbeat, and
the SIP-0094 no-pending-future-leak invariants.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from adapters.cycles.execution_errors import _CancellationError
from adapters.cycles.task_dispatcher import TaskDispatcher
from squadops.tasks.models import TaskEnvelope, TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Fixtures — FakeReplyRouter + the `reply_router` fixture live in conftest.py
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_queue(reply_router):
    """Mock QueuePort bound to the reply router: publishing a ``comms.task``
    auto-delivers the agent's reply (SIP-0094 cutover)."""
    mock = AsyncMock()
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    mock.consume.return_value = []
    return reply_router.bind(mock)


@pytest.fixture
def dispatcher(mock_queue, reply_router):
    return TaskDispatcher(
        queue=mock_queue,
        reply_router=reply_router,
        task_timeout=5.0,  # Short timeout for tests
    )


# ---------------------------------------------------------------------------
# Dispatch mechanics
# ---------------------------------------------------------------------------


class TestDispatchTask:
    """Verify publish/consume mechanics of dispatch_task."""

    async def test_publishes_to_agent_comms_queue(self, dispatcher, mock_queue) -> None:
        """Task is published to {agent_id}_comms with comms.task action."""
        # Default reply_router responder auto-succeeds the dispatched task.
        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(envelope, "run_001")

        # Verify publish to correct queue
        mock_queue.publish.assert_awaited_once()
        pub_args = mock_queue.publish.call_args
        assert pub_args.args[0] == "neo_comms"

        published = json.loads(pub_args.args[1])
        assert published["action"] == "comms.task"
        # SIP-0094: reply address is now the per-agent reply queue.
        assert published["metadata"]["reply_queue"] == "neo_replies"
        assert published["payload"]["task_id"] == "task_abc"

    async def test_returns_agent_result_from_router(self, dispatcher, reply_router) -> None:
        """The agent's TaskResult (delivered via the reply router) is returned
        by _dispatch_task with its outputs intact (SIP-0094)."""
        reply_router.results["task_abc"] = TaskResult(
            task_id="task_abc", status="SUCCEEDED", outputs={"summary": "implemented"}
        )

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        result = await dispatcher.dispatch_task(envelope, "run_001")

        assert result.task_id == "task_abc"
        assert result.status == "SUCCEEDED"
        assert result.outputs["summary"] == "implemented"
        # The reply router/subscribe primitive owns ack now — not the executor
        # (ack behavior is covered in test_reply_router.py).

    async def test_timeout_returns_failed(self, dispatcher, reply_router) -> None:
        """If the agent never replies within the timeout, returns FAILED."""
        reply_router.suppress.add("task_abc")  # agent never replies
        dispatcher._task_timeout = 0.1  # Very short

        envelope = TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

        # NOTE: do NOT patch asyncio.sleep here. The concurrent heartbeat loop
        # (`while True: await asyncio.sleep(30)`) would then spin instantly and
        # starve the event loop, so wait_for's 0.1s timer never fires. With real
        # sleep the heartbeat parks for 30s and the timeout fires cleanly.
        result = await dispatcher.dispatch_task(envelope, "run_001")

        assert result.status == "FAILED"
        assert "Timed out" in result.error

    # SIP-0094 removed the executor-side reply polling loop (consume_blocking +
    # invalidate_queue recovery). Two tests that asserted that mechanism —
    # transient-consume-error recovery and "uses long-block consume not short
    # poll" — are deleted here; their coverage moved to the reply substrate:
    # channel-close resubscribe is tested in tests/unit/comms/
    # test_rabbitmq_adapter.py (94.2b) and the router resolve path in
    # tests/unit/cycles/test_reply_router.py.


# ---------------------------------------------------------------------------
# SIP-0087: Prefect task-run lifecycle + contextvar scope + heartbeat
# ---------------------------------------------------------------------------


class TestDispatchTaskPrefectLifecycle:
    """Verify dispatch_task drives the Prefect task-run lifecycle, enters the
    correlation contextvar scope, and spawns the heartbeat."""

    @pytest.fixture
    def envelope(self):
        return TaskEnvelope(
            task_id="task_abc",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev", "capability_id": "dev.design"},
        )

    @pytest.fixture
    def mock_reporter(self):
        reporter = MagicMock()
        reporter.create_task_run = AsyncMock(return_value="tr_new")
        reporter.set_task_run_state = AsyncMock()
        return reporter

    def _build_dispatcher(self, mock_queue, mock_reporter=None):
        return TaskDispatcher(
            queue=mock_queue,
            reply_router=mock_queue.reply_router,
            task_timeout=5.0,
            workflow_tracker=mock_reporter,
        )

    def _wire_success_reply(self, mock_queue, task_id: str):
        """Seed the reply router so the dispatched task gets a SUCCEEDED reply."""
        mock_queue.reply_router.results[task_id] = TaskResult(
            task_id=task_id, status="SUCCEEDED", outputs={"summary": "ok", "artifacts": []}
        )

    async def test_creates_task_run_and_sets_running_when_prefect_enabled(
        self, mock_queue, mock_reporter, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(envelope, "run_001", flow_run_id="fr_abc")

        # #185: label prefixes with the agent (envelope.agent_id="neo"), not
        # the role ("dev") — proves the executor wires build_task_name through.
        mock_reporter.create_task_run.assert_awaited_once_with(
            "fr_abc", "task_abc", "neo: development.design"
        )
        # #506: transport-owned lifecycle — RUNNING at creation, terminal from
        # the result (the bridge no longer writes task-run state).
        assert mock_reporter.set_task_run_state.await_args_list == [
            call("tr_new", "RUNNING", "Running"),
            call("tr_new", "COMPLETED", "Completed"),
        ]

    async def test_no_prefect_calls_when_reporter_missing(self, mock_queue, envelope):
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter=None)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await dispatcher.dispatch_task(envelope, "run_001", flow_run_id="fr_abc")

        assert result.status == "SUCCEEDED"

    async def test_no_prefect_calls_when_flow_run_id_missing(
        self, mock_queue, mock_reporter, envelope
    ):
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(envelope, "run_001", flow_run_id=None)

        mock_reporter.create_task_run.assert_not_awaited()
        mock_reporter.set_task_run_state.assert_not_awaited()

    async def test_skips_creation_when_task_run_id_preallocated(
        self, mock_queue, mock_reporter, envelope
    ):
        # Sequential path pre-creates the task_run (so TASK_DISPATCHED can
        # emit it) and passes task_run_id in. _dispatch_task must not create
        # a second one — but it DOES re-enter RUNNING (#506): the supplied id
        # may be a prior attempt's already-terminal task run, and the retry
        # re-attempt was invisible in flight for exactly that reason (the
        # July-19 develop task heartbeating with no live row).
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_preallocated"
            )

        mock_reporter.create_task_run.assert_not_awaited()
        assert mock_reporter.set_task_run_state.await_args_list == [
            call("tr_preallocated", "RUNNING", "Running"),
            call("tr_preallocated", "COMPLETED", "Completed"),
        ]

    async def test_failed_result_sets_terminal_failed(self, mock_queue, mock_reporter, envelope):
        # a FAILED reply must leave the row FAILED — before #506 nothing
        # transitioned an internally-created task run, so it hung RUNNING
        mock_queue.reply_router.results[envelope.task_id] = TaskResult(
            task_id=envelope.task_id, status="FAILED", outputs={}, error="boom"
        )
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(envelope, "run_001", flow_run_id="fr_abc")

        assert mock_reporter.set_task_run_state.await_args_list == [
            call("tr_new", "RUNNING", "Running"),
            call("tr_new", "FAILED", "Failed"),
        ]

    async def test_tracker_failure_never_breaks_dispatch(self, mock_queue, mock_reporter, envelope):
        # best-effort contract: a tracker transport error is logged, never raised
        mock_reporter.set_task_run_state = AsyncMock(side_effect=RuntimeError("prefect down"))
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await dispatcher.dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_x"
            )

        assert result.status == "SUCCEEDED"

    async def test_published_envelope_carries_run_ids(self, mock_queue, mock_reporter, envelope):
        """SIP-0087 B1: dispatched envelope on the wire carries flow_run_id /
        task_run_id so the agent can scope its handler logs to the right
        Prefect task pane."""
        published_payload: dict[str, object] = {}

        async def capture_publish(_queue_name, body):
            published_payload.update(json.loads(body)["payload"])

        mock_queue.publish.side_effect = capture_publish
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        assert published_payload["flow_run_id"] == "fr_abc"
        assert published_payload["task_run_id"] == "tr_123"

    async def test_published_envelope_run_ids_empty_when_prefect_disabled(
        self, mock_queue, envelope
    ):
        """No Prefect → run IDs serialize as empty strings (not nulls)."""
        published_payload: dict[str, object] = {}

        async def capture_publish(_queue_name, body):
            published_payload.update(json.loads(body)["payload"])

        mock_queue.publish.side_effect = capture_publish
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter=None)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(envelope, "run_001")

        assert published_payload["flow_run_id"] == ""
        assert published_payload["task_run_id"] == ""

    async def test_scopes_correlation_context_during_publish(
        self, mock_queue, mock_reporter, envelope
    ):
        """The publish coroutine must see the active CorrelationContext so
        any logs emitted during dispatch land in the right Prefect pane."""
        from squadops.telemetry.context import get_correlation_context

        seen: dict[str, object] = {}

        async def capture_ctx(*args, **kwargs):
            ctx = get_correlation_context()
            seen["cycle_id"] = ctx.cycle_id if ctx else None
            seen["flow_run_id"] = ctx.flow_run_id if ctx else None
            seen["task_run_id"] = ctx.task_run_id if ctx else None

        mock_queue.publish.side_effect = capture_ctx
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        assert seen == {
            "cycle_id": "cyc_001",
            "flow_run_id": "fr_abc",
            "task_run_id": "tr_123",
        }
        # Context must be cleared after dispatch returns.
        assert get_correlation_context() is None

    async def test_task_heartbeat_logs_periodically_under_contextvar_scope(
        self, mock_queue, envelope, caplog
    ):
        """``_task_heartbeat`` emits an INFO line per interval and carries
        the live correlation context so records are tagged for Prefect."""
        import logging as stdlog

        import adapters.cycles.task_dispatcher as dfe
        from squadops.telemetry.context import (
            get_correlation_context,
            use_correlation_context,
            use_run_ids,
        )
        from squadops.telemetry.models import CorrelationContext

        dispatcher = self._build_dispatcher(mock_queue)

        seen_ids: list[tuple[str | None, str | None]] = []
        real_sleep = asyncio.sleep

        async def capturing_sleep(_interval: float) -> None:
            ctx = get_correlation_context()
            seen_ids.append((ctx.flow_run_id if ctx else None, ctx.task_run_id if ctx else None))
            # Let the event loop advance; real sleep avoids tight-looping.
            await real_sleep(0)

        with (
            patch.object(dfe.asyncio, "sleep", capturing_sleep),
            caplog.at_level(stdlog.INFO, logger=dfe.__name__),
        ):
            base = CorrelationContext(cycle_id="cyc_001")
            with (
                use_correlation_context(base),
                use_run_ids(flow_run_id="fr_abc", task_run_id="tr_123"),
            ):
                hb = asyncio.create_task(dispatcher._task_heartbeat(envelope, interval=0.01))
                # Yield a few times so the heartbeat can iterate.
                for _ in range(5):
                    await real_sleep(0)
                hb.cancel()
                try:
                    await hb
                except asyncio.CancelledError:
                    pass

        messages = [r.getMessage() for r in caplog.records if "task_heartbeat" in r.getMessage()]
        assert messages, "expected at least one task_heartbeat log line"
        first = messages[0]
        assert "capability_id=dev.design" in first
        assert "task_id=task_abc" in first
        # Heartbeat coroutine saw the active flow/task run IDs via contextvar
        # inheritance at create_task time.
        assert ("fr_abc", "tr_123") in seen_ids

    async def test_dispatch_task_cancels_heartbeat_on_return(
        self, mock_queue, mock_reporter, envelope
    ):
        """After ``_dispatch_task`` returns, no orphan heartbeat task should
        remain on the event loop."""
        self._wire_success_reply(mock_queue, envelope.task_id)
        dispatcher = self._build_dispatcher(mock_queue, mock_reporter)

        with patch(
            "adapters.cycles.task_dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await dispatcher.dispatch_task(
                envelope, "run_001", flow_run_id="fr_abc", task_run_id="tr_123"
            )

        leftover = [
            t
            for t in asyncio.all_tasks()
            if t.get_name().startswith("prefect-heartbeat-") and not t.done()
        ]
        assert leftover == []


class TestPublishAndAwaitInvariants:
    """SIP-0094 cutover invariants of _publish_and_await: ordering (D14/#2),
    pending-future-leak safety on every exit path (#9/#10), concurrent
    first-dispatch (#13), and global task_id uniqueness across runs (D14)."""

    @staticmethod
    def _env(task_id="t1", agent_id="neo"):
        return TaskEnvelope(
            task_id=task_id,
            agent_id=agent_id,
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.design",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

    async def test_subscribes_and_registers_before_publish(
        self, dispatcher, mock_queue, reply_router
    ):
        """D14/#2: ensure_subscribed + register happen BEFORE publish, so a fast
        reply can't arrive before the consumer is live."""
        seen = {}

        async def _publish(queue_name, payload, delay_seconds=None):
            data = json.loads(payload)
            seen["registered"] = data["payload"]["task_id"] in reply_router.registered
            seen["subscribed"] = "neo" in reply_router.subscribed
            reply_router._autorespond(data["payload"])

        mock_queue.publish.side_effect = _publish

        await dispatcher._publish_and_await(self._env(), "run_001")

        assert seen == {"registered": True, "subscribed": True}

    async def test_publish_failure_removes_pending_future(
        self, dispatcher, mock_queue, reply_router
    ):
        """#10: if publish raises after register(), the pending future is dropped
        (no leak) and the error propagates."""
        mock_queue.publish.side_effect = RuntimeError("broker down")

        with pytest.raises(RuntimeError, match="broker down"):
            await dispatcher._publish_and_await(self._env("t_fail"), "run_001")

        assert "t_fail" in reply_router.cancelled
        assert "t_fail" not in reply_router._futures

    async def test_timeout_leaves_no_pending_future(self, dispatcher, reply_router):
        """#9: a timed-out dispatch cancels its future (no leak) and returns FAILED."""
        reply_router.suppress.add("t_to")
        dispatcher._task_timeout = 0.1

        result = await dispatcher._publish_and_await(self._env("t_to"), "run_001")

        assert result.status == "FAILED"
        assert "t_to" in reply_router.cancelled
        assert "t_to" not in reply_router._futures

    async def test_concurrent_dispatch_same_agent_both_resolve(
        self, dispatcher, mock_queue, reply_router
    ):
        """#13: two concurrent dispatches to one agent both resolve to their own
        results and both publish to that agent's comms queue."""
        reply_router.results["ta"] = TaskResult(
            task_id="ta", status="SUCCEEDED", outputs={"n": "a"}
        )
        reply_router.results["tb"] = TaskResult(
            task_id="tb", status="SUCCEEDED", outputs={"n": "b"}
        )

        ra, rb = await asyncio.gather(
            dispatcher._publish_and_await(self._env("ta"), "run_001"),
            dispatcher._publish_and_await(self._env("tb"), "run_001"),
        )

        assert ra.outputs["n"] == "a"
        assert rb.outputs["n"] == "b"
        pub_queues = [c.args[0] for c in mock_queue.publish.call_args_list]
        assert pub_queues.count("neo_comms") == 2

    async def test_cross_run_task_ids_dont_collide(self, dispatcher, reply_router):
        """D14: globally-unique task_ids from different runs resolve to their own
        results on the shared per-agent reply queue (no cross-run mixup)."""
        reply_router.results["task-run_aaaa-1"] = TaskResult(
            task_id="task-run_aaaa-1", status="SUCCEEDED", outputs={"r": "a"}
        )
        reply_router.results["task-run_bbbb-1"] = TaskResult(
            task_id="task-run_bbbb-1", status="SUCCEEDED", outputs={"r": "b"}
        )

        r1 = await dispatcher._publish_and_await(self._env("task-run_aaaa-1"), "run_aaaa")
        r2 = await dispatcher._publish_and_await(self._env("task-run_bbbb-1"), "run_bbbb")

        assert r1.outputs["r"] == "a"
        assert r2.outputs["r"] == "b"


class TestAcceptPatchToken:
    """#389: the "accept_patch" routing token returns success WITHOUT
    re-dispatching the task."""

    def _envelope(self):
        return TaskEnvelope(
            task_id="task_patch",
            agent_id="bob",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="builder.assemble",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "builder"},
        )

    def _cycle(self):
        from squadops.cycles.models import Cycle, TaskFlowPolicy

        return Cycle(
            cycle_id="cyc_001",
            project_id="proj_001",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )

    async def test_accept_patch_returns_success_without_redispatch(
        self, mock_queue, reply_router
    ) -> None:
        """Bug caught: an unhandled token falls through the retry loop and
        re-dispatches — the generative re-roll that clobbers the repair."""
        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            task_timeout=5.0,
            event_bus=MagicMock(),
        )
        envelope = self._envelope()
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"], status="FAILED", error="acceptance failed"
        )

        async def handle_outcome(result):
            return "accept_patch"

        with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            task_succeeded, result = await dispatcher.dispatch_with_retry(
                envelope,
                envelope,
                self._cycle(),
                "run_001",
                handle_task_outcome=handle_outcome,
            )

        assert task_succeeded is True
        # The dispatcher hands back the raw failed result; the executor
        # substitutes the corrected one from its holder (#389).
        assert result.status == "FAILED"
        assert mock_queue.publish.await_count == 1


# ---------------------------------------------------------------------------
# Cancellation probe (#586)
# ---------------------------------------------------------------------------


class TestCancellationProbe:
    """§6.1 dispatch-boundary cancellation check.

    Before #586 this class documented the probe as "deliberately not wired"
    while ``CorrectionRunner`` documented itself as relying on it — so the only
    real check was the executor's between-task one, and a run cancelled inside
    a correction loop kept dispatching repairs for 2h20m.
    """

    def _envelope(self):
        return TaskEnvelope(
            task_id="task_repair",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj_001",
            task_type="development.develop",
            correlation_id="corr",
            causation_id="cause",
            trace_id="trace",
            span_id="span",
            metadata={"role": "dev"},
        )

    async def test_cancelled_run_raises_before_publishing(self, mock_queue, reply_router) -> None:
        """Bug caught: a repair dispatched onto a cancelled run — the #586 shape.

        The assertion that matters is ``publish`` never happening: raising after
        publish would still hand the agent an LLM task to burn.
        """
        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            task_timeout=5.0,
            is_cancelled=AsyncMock(return_value=True),
        )

        with pytest.raises(_CancellationError) as exc_info:
            await dispatcher.dispatch_task(self._envelope(), "run_001")

        assert "run_001" in str(exc_info.value)
        mock_queue.publish.assert_not_awaited()

    async def test_cancelled_run_creates_no_prefect_task_run(
        self, mock_queue, reply_router
    ) -> None:
        """Bug caught: probing after task-run creation orphans a RUNNING
        task_run in the Prefect UI for every cancelled dispatch."""
        tracker = AsyncMock()
        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            workflow_tracker=tracker,
            task_timeout=5.0,
            is_cancelled=AsyncMock(return_value=True),
        )

        with pytest.raises(_CancellationError):
            await dispatcher.dispatch_task(self._envelope(), "run_001", flow_run_id="flow_001")

        tracker.create_task_run.assert_not_awaited()
        tracker.set_task_run_state.assert_not_awaited()

    async def test_live_run_dispatches_normally(self, mock_queue, reply_router) -> None:
        """Bug caught: a probe wired fail-closed (always raising) would kill
        every healthy run — the inverse regression of the fix."""
        probe = AsyncMock(return_value=False)
        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            task_timeout=5.0,
            is_cancelled=probe,
        )

        with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await dispatcher.dispatch_task(self._envelope(), "run_001")

        assert result.status == "SUCCEEDED"
        mock_queue.publish.assert_awaited_once()
        probe.assert_awaited_once_with("run_001")

    async def test_probe_failure_propagates_rather_than_dispatching(
        self, mock_queue, reply_router
    ) -> None:
        """Bug caught: swallowing probe errors silently restores the #586
        behaviour — a registry blip would resume dispatching on a cancelled
        run. The between-task check this complements is fail-closed too."""
        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            task_timeout=5.0,
            is_cancelled=AsyncMock(side_effect=RuntimeError("registry down")),
        )

        with pytest.raises(RuntimeError, match="registry down"):
            await dispatcher.dispatch_task(self._envelope(), "run_001")

        mock_queue.publish.assert_not_awaited()

    async def test_unwired_probe_dispatches(self, mock_queue, reply_router) -> None:
        """Bug caught: making the probe mandatory breaks the standalone and
        in-memory compositions that construct a dispatcher without one."""
        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            task_timeout=5.0,
        )

        with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await dispatcher.dispatch_task(self._envelope(), "run_001")

        assert result.status == "SUCCEEDED"
        mock_queue.publish.assert_awaited_once()

    async def test_retry_loop_stops_when_cancelled_mid_flight(
        self, mock_queue, reply_router
    ) -> None:
        """Bug caught: cancel landing during a retry/correction sequence lets the
        loop re-dispatch anyway. Probing inside ``dispatch_task`` (not only at
        the loop top) is what bounds post-cancel work to the in-flight task."""
        from squadops.cycles.models import Cycle, TaskFlowPolicy

        cancelled = {"now": False}

        async def probe(run_id: str) -> bool:
            return cancelled["now"]

        dispatcher = TaskDispatcher(
            queue=mock_queue,
            reply_router=reply_router,
            task_timeout=5.0,
            event_bus=MagicMock(),
            is_cancelled=probe,
        )
        envelope = self._envelope()
        reply_router.responder = lambda env: TaskResult(
            task_id=env["task_id"], status="FAILED", error="needs repair"
        )

        async def handle_outcome(result):
            # Stands in for the correction protocol: the run is cancelled while
            # the outcome is being routed, then the loop asks for a re-dispatch.
            cancelled["now"] = True
            return "continue"

        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="proj_001",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )

        with (
            patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(_CancellationError),
        ):
            await dispatcher.dispatch_with_retry(
                envelope,
                envelope,
                cycle,
                "run_001",
                handle_task_outcome=handle_outcome,
            )

        # One dispatch happened (the in-flight task); the retry never published.
        assert mock_queue.publish.await_count == 1
