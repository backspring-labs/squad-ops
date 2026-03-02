"""Bridge parity tests — verify bridge output matches existing direct-wired semantics.

For each lifecycle transition, bridge output produces the same transition meaning
and entity correlation as the existing direct calls in the executor:
  - LangFuse: event name + correlation identity (cycle_id, trace_id)
  - Prefect: resulting state transition on flow/task run
  - Metrics: counter/histogram effect (metric name + value)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from squadops.events.bridges.langfuse import LangFuseBridge
from squadops.events.bridges.metrics import MetricsBridge
from squadops.events.bridges.prefect import PrefectBridge
from squadops.events.models import CycleEvent
from squadops.events.types import EventType
from squadops.telemetry.models import CorrelationContext


def _event(event_type: str, entity_type: str, entity_id: str, **kw) -> CycleEvent:
    return CycleEvent(
        event_id="evt_parity",
        occurred_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        source_service="test",
        source_version="0.0.1",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        context=kw.get("context", {"cycle_id": "cyc_1", "trace_id": "trace_1"}),
        payload=kw.get("payload", {}),
        sequence=kw.get("sequence", 1),
        semantic_key=kw.get("semantic_key", ""),
    )


# ---------------------------------------------------------------------------
# LangFuse parity
# ---------------------------------------------------------------------------


@pytest.mark.domain_events
class TestLangFuseParity:
    """Bridge record_event() semantics match executor's direct record_event() calls."""

    def test_cycle_started_event_name_matches(self):
        """Executor calls record_event with name='cycle.started'.
        Bridge uses event_type directly as the StructuredEvent name.
        The executor's 'cycle.started' maps to EventType.RUN_STARTED in the
        current taxonomy (run.started), but the bridge faithfully forwards
        whatever event_type it receives."""
        obs = MagicMock()
        bridge = LangFuseBridge(obs)
        bridge.on_event(_event(EventType.RUN_STARTED, "run", "run_1"))

        se = obs.record_event.call_args[0][1]
        assert se.name == "run.started"

    def test_correlation_identity_matches_executor_pattern(self):
        """Executor constructs CorrelationContext(cycle_id=..., trace_id=...).
        Bridge constructs the same from event.context."""
        obs = MagicMock()
        bridge = LangFuseBridge(obs)
        bridge.on_event(
            _event(
                EventType.RUN_STARTED,
                "run",
                "run_1",
                context={"cycle_id": "cyc_99", "trace_id": "tr_abc"},
            )
        )

        ctx = obs.record_event.call_args[0][0]
        assert isinstance(ctx, CorrelationContext)
        assert ctx.cycle_id == "cyc_99"
        assert ctx.trace_id == "tr_abc"

    def test_cycle_completed_event_name(self):
        """Executor record_event name='cycle.completed' maps to run.completed."""
        obs = MagicMock()
        bridge = LangFuseBridge(obs)
        bridge.on_event(_event(EventType.RUN_COMPLETED, "run", "run_1"))

        se = obs.record_event.call_args[0][1]
        assert se.name == "run.completed"

    def test_payload_attributes_forwarded(self):
        """Executor passes attributes as tuple of tuples.
        Bridge converts payload dict items to StructuredEvent attributes."""
        obs = MagicMock()
        bridge = LangFuseBridge(obs)
        bridge.on_event(
            _event(
                EventType.TASK_SUCCEEDED,
                "task",
                "t_1",
                payload={"duration_ms": 5000, "status": "SUCCEEDED"},
            )
        )

        se = obs.record_event.call_args[0][1]
        attr_dict = dict(se.attributes)
        assert attr_dict["duration_ms"] == 5000
        assert attr_dict["status"] == "SUCCEEDED"

    def test_all_events_produce_record_event_call(self):
        """Every event type in the taxonomy produces exactly one record_event call."""
        obs = MagicMock()
        bridge = LangFuseBridge(obs)
        for et in EventType.all():
            obs.reset_mock()
            entity = et.split(".")[0]
            bridge.on_event(_event(et, entity, f"{entity}_1"))
            assert obs.record_event.call_count == 1, f"No record_event for {et}"


# ---------------------------------------------------------------------------
# Prefect parity
# ---------------------------------------------------------------------------


@pytest.mark.domain_events
class TestPrefectParity:
    """Bridge state transitions match executor's direct PrefectReporter calls."""

    def test_run_started_state_matches(self):
        """Executor: set_flow_run_state(frid, 'RUNNING', 'Running')"""
        reporter = MagicMock()
        reporter.set_flow_run_state = AsyncMock()
        bridge = PrefectBridge(reporter)

        bridge.on_event(
            _event(
                EventType.RUN_STARTED,
                "run",
                "run_1",
                context={"cycle_id": "cyc_1", "run_id": "run_1", "flow_run_id": "fr_1"},
            )
        )
        reporter.set_flow_run_state.assert_called_with("fr_1", "RUNNING", "Running")

    def test_run_terminal_states_match(self):
        """Executor: set_flow_run_state(frid, terminal_status, terminal_status.title())"""
        for event_type, expected_state in [
            (EventType.RUN_COMPLETED, "COMPLETED"),
            (EventType.RUN_FAILED, "FAILED"),
            (EventType.RUN_CANCELLED, "CANCELLED"),
        ]:
            reporter = MagicMock()
            reporter.set_flow_run_state = AsyncMock()
            bridge = PrefectBridge(reporter)

            bridge.on_event(
                _event(
                    event_type,
                    "run",
                    "run_1",
                    context={"cycle_id": "cyc_1", "run_id": "run_1", "flow_run_id": "fr_1"},
                )
            )
            reporter.set_flow_run_state.assert_called_with(
                "fr_1", expected_state, expected_state.title()
            )

    def test_task_dispatch_creates_then_runs(self):
        """Executor: create_task_run() then set_task_run_state(trid, 'RUNNING', 'Running')"""
        reporter = MagicMock()
        reporter.create_task_run = AsyncMock(return_value="tr_99")
        reporter.set_task_run_state = AsyncMock()
        bridge = PrefectBridge(reporter)

        bridge.on_event(
            _event(
                EventType.TASK_DISPATCHED,
                "task",
                "task_key_a",
                context={"cycle_id": "cyc_1", "run_id": "run_1", "flow_run_id": "fr_1"},
                payload={"task_name": "dev: implementation"},
            )
        )
        reporter.create_task_run.assert_called_once()
        reporter.set_task_run_state.assert_called_with("tr_99", "RUNNING", "Running")

    def test_task_success_sets_completed(self):
        """Executor: set_task_run_state(trid, 'COMPLETED', 'Completed')"""
        reporter = MagicMock()
        reporter.create_task_run = AsyncMock(return_value="tr_99")
        reporter.set_task_run_state = AsyncMock()
        bridge = PrefectBridge(reporter)

        ctx = {"cycle_id": "cyc_1", "run_id": "run_1", "flow_run_id": "fr_1"}
        bridge.on_event(
            _event(EventType.TASK_DISPATCHED, "task", "t_1", context=ctx)
        )
        reporter.reset_mock()

        bridge.on_event(
            _event(EventType.TASK_SUCCEEDED, "task", "t_1", context=ctx)
        )
        reporter.set_task_run_state.assert_called_with("tr_99", "COMPLETED", "Completed")

    def test_task_failure_sets_failed(self):
        """Executor: set_task_run_state(trid, 'FAILED', 'Failed')"""
        reporter = MagicMock()
        reporter.create_task_run = AsyncMock(return_value="tr_99")
        reporter.set_task_run_state = AsyncMock()
        bridge = PrefectBridge(reporter)

        ctx = {"cycle_id": "cyc_1", "run_id": "run_1", "flow_run_id": "fr_1"}
        bridge.on_event(
            _event(EventType.TASK_DISPATCHED, "task", "t_1", context=ctx)
        )
        reporter.reset_mock()

        bridge.on_event(
            _event(EventType.TASK_FAILED, "task", "t_1", context=ctx)
        )
        reporter.set_task_run_state.assert_called_with("tr_99", "FAILED", "Failed")


# ---------------------------------------------------------------------------
# Metrics parity
# ---------------------------------------------------------------------------


@pytest.mark.domain_events
class TestMetricsParity:
    """Bridge counter/histogram effects match expected metric semantics."""

    def test_run_completed_counter(self):
        metrics = MagicMock()
        bridge = MetricsBridge(metrics)
        bridge.on_event(_event(EventType.RUN_COMPLETED, "run", "run_1"))
        metrics.counter.assert_called_once_with(
            "runs_completed_total", labels={"entity_type": "run"}
        )

    def test_run_failed_counter(self):
        metrics = MagicMock()
        bridge = MetricsBridge(metrics)
        bridge.on_event(_event(EventType.RUN_FAILED, "run", "run_1"))
        metrics.counter.assert_called_once_with(
            "runs_failed_total", labels={"entity_type": "run"}
        )

    def test_task_succeeded_counter_and_histogram(self):
        metrics = MagicMock()
        bridge = MetricsBridge(metrics)
        bridge.on_event(
            _event(
                EventType.TASK_SUCCEEDED,
                "task",
                "t_1",
                payload={"duration_ms": 4200},
            )
        )
        metrics.counter.assert_called_once_with(
            "tasks_succeeded_total", labels={"entity_type": "task"}
        )
        metrics.histogram.assert_called_once_with(
            "task_duration_ms", value=4200.0, labels={"entity_type": "task"}
        )

    def test_non_mapped_event_produces_no_metrics(self):
        """Events outside the 5-event counter map produce no metric calls."""
        metrics = MagicMock()
        bridge = MetricsBridge(metrics)
        bridge.on_event(_event(EventType.RUN_STARTED, "run", "run_1"))
        metrics.counter.assert_not_called()
        metrics.histogram.assert_not_called()
