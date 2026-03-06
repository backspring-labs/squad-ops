"""Tests for MetricsBridge subscriber."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from squadops.events.bridges.metrics import MetricsBridge
from squadops.events.models import CycleEvent
from squadops.events.types import EventType


def _make_event(**overrides) -> CycleEvent:
    defaults = {
        "event_id": "evt_test1",
        "occurred_at": datetime(2026, 3, 1, tzinfo=UTC),
        "source_service": "test",
        "source_version": "0.0.1",
        "event_type": EventType.RUN_COMPLETED,
        "entity_type": "run",
        "entity_id": "run_1",
        "context": {"cycle_id": "cyc_1"},
        "payload": {},
        "sequence": 1,
        "semantic_key": "cyc_1:run:run_1:completed:1",
    }
    defaults.update(overrides)
    return CycleEvent(**defaults)


@pytest.fixture
def mock_metrics():
    return MagicMock()


@pytest.fixture
def bridge(mock_metrics):
    return MetricsBridge(mock_metrics)


@pytest.mark.domain_events
class TestMetricsBridge:
    def test_run_completed_increments_counter(self, bridge, mock_metrics):
        bridge.on_event(_make_event(event_type=EventType.RUN_COMPLETED))
        mock_metrics.counter.assert_called_once_with(
            "runs_completed_total", labels={"entity_type": "run"}
        )

    def test_run_failed_increments_counter(self, bridge, mock_metrics):
        bridge.on_event(_make_event(event_type=EventType.RUN_FAILED))
        mock_metrics.counter.assert_called_once_with(
            "runs_failed_total", labels={"entity_type": "run"}
        )

    def test_cycle_created_increments_counter(self, bridge, mock_metrics):
        bridge.on_event(
            _make_event(
                event_type=EventType.CYCLE_CREATED,
                entity_type="cycle",
                entity_id="cyc_1",
            )
        )
        mock_metrics.counter.assert_called_once_with(
            "cycles_created_total", labels={"entity_type": "cycle"}
        )

    def test_task_succeeded_increments_counter(self, bridge, mock_metrics):
        bridge.on_event(
            _make_event(
                event_type=EventType.TASK_SUCCEEDED,
                entity_type="task",
                entity_id="t_1",
            )
        )
        mock_metrics.counter.assert_called_once_with(
            "tasks_succeeded_total", labels={"entity_type": "task"}
        )

    def test_task_failed_increments_counter(self, bridge, mock_metrics):
        bridge.on_event(
            _make_event(
                event_type=EventType.TASK_FAILED,
                entity_type="task",
                entity_id="t_1",
            )
        )
        mock_metrics.counter.assert_called_once_with(
            "tasks_failed_total", labels={"entity_type": "task"}
        )

    def test_task_succeeded_with_duration_records_histogram(self, bridge, mock_metrics):
        bridge.on_event(
            _make_event(
                event_type=EventType.TASK_SUCCEEDED,
                entity_type="task",
                entity_id="t_1",
                payload={"duration_ms": 3500},
            )
        )
        mock_metrics.histogram.assert_called_once_with(
            "task_duration_ms", value=3500.0, labels={"entity_type": "task"}
        )

    def test_task_succeeded_without_duration_no_histogram(self, bridge, mock_metrics):
        bridge.on_event(
            _make_event(
                event_type=EventType.TASK_SUCCEEDED,
                entity_type="task",
                entity_id="t_1",
            )
        )
        mock_metrics.histogram.assert_not_called()

    def test_unrelated_event_no_calls(self, bridge, mock_metrics):
        bridge.on_event(_make_event(event_type=EventType.GATE_DECIDED))
        mock_metrics.counter.assert_not_called()
        mock_metrics.histogram.assert_not_called()

    def test_all_five_counter_events_covered(self, bridge, mock_metrics):
        """All 5 mapped events produce counter increments."""
        events = [
            (EventType.CYCLE_CREATED, "cycle"),
            (EventType.RUN_COMPLETED, "run"),
            (EventType.RUN_FAILED, "run"),
            (EventType.TASK_SUCCEEDED, "task"),
            (EventType.TASK_FAILED, "task"),
        ]
        for event_type, entity_type in events:
            mock_metrics.reset_mock()
            bridge.on_event(_make_event(event_type=event_type, entity_type=entity_type))
            assert mock_metrics.counter.call_count == 1, f"Expected counter call for {event_type}"
