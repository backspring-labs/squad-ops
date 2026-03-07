"""Tests for PrefectBridge subscriber."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.events.bridges.prefect import PrefectBridge
from squadops.events.models import CycleEvent
from squadops.events.types import EventType


def _make_event(**overrides) -> CycleEvent:
    defaults = {
        "event_id": "evt_test1",
        "occurred_at": datetime(2026, 3, 1, tzinfo=UTC),
        "source_service": "test",
        "source_version": "0.0.1",
        "event_type": EventType.RUN_STARTED,
        "entity_type": "run",
        "entity_id": "run_1",
        "context": {
            "cycle_id": "cyc_1",
            "run_id": "run_1",
            "flow_run_id": "fr_abc",
        },
        "payload": {},
        "sequence": 1,
        "semantic_key": "cyc_1:run:run_1:started:1",
    }
    defaults.update(overrides)
    return CycleEvent(**defaults)


@pytest.fixture
def mock_reporter():
    reporter = MagicMock()
    reporter.set_flow_run_state = AsyncMock()
    reporter.set_task_run_state = AsyncMock()
    reporter.create_task_run = AsyncMock(return_value="tr_123")
    return reporter


@pytest.fixture
def bridge(mock_reporter):
    return PrefectBridge(mock_reporter)


@pytest.mark.domain_events
class TestPrefectBridge:
    def test_run_started_sets_flow_running(self, bridge, mock_reporter):
        bridge.on_event(_make_event(event_type=EventType.RUN_STARTED))
        mock_reporter.set_flow_run_state.assert_called_once_with("fr_abc", "RUNNING", "Running")

    def test_run_completed_sets_flow_completed(self, bridge, mock_reporter):
        bridge.on_event(_make_event(event_type=EventType.RUN_COMPLETED))
        mock_reporter.set_flow_run_state.assert_called_once_with("fr_abc", "COMPLETED", "Completed")

    def test_run_failed_sets_flow_failed(self, bridge, mock_reporter):
        bridge.on_event(_make_event(event_type=EventType.RUN_FAILED))
        mock_reporter.set_flow_run_state.assert_called_once_with("fr_abc", "FAILED", "Failed")

    def test_run_cancelled_sets_flow_cancelled(self, bridge, mock_reporter):
        bridge.on_event(_make_event(event_type=EventType.RUN_CANCELLED))
        mock_reporter.set_flow_run_state.assert_called_once_with("fr_abc", "CANCELLED", "Cancelled")

    def test_run_paused_sets_flow_paused(self, bridge, mock_reporter):
        bridge.on_event(_make_event(event_type=EventType.RUN_PAUSED))
        mock_reporter.set_flow_run_state.assert_called_once_with("fr_abc", "PAUSED", "Paused")

    def test_task_dispatched_creates_and_runs(self, bridge, mock_reporter):
        event = _make_event(
            event_type=EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="task_a",
            payload={"task_name": "My Task"},
        )
        bridge.on_event(event)
        mock_reporter.create_task_run.assert_called_once_with("fr_abc", "task_a", "My Task")
        mock_reporter.set_task_run_state.assert_called_once_with("tr_123", "RUNNING", "Running")

    def test_task_succeeded_sets_completed(self, bridge, mock_reporter):
        # First dispatch to register the task_run_id
        dispatch = _make_event(
            event_type=EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="task_a",
        )
        bridge.on_event(dispatch)
        mock_reporter.reset_mock()

        succeed = _make_event(
            event_type=EventType.TASK_SUCCEEDED,
            entity_type="task",
            entity_id="task_a",
        )
        bridge.on_event(succeed)
        mock_reporter.set_task_run_state.assert_called_once_with("tr_123", "COMPLETED", "Completed")

    def test_task_failed_sets_failed(self, bridge, mock_reporter):
        dispatch = _make_event(
            event_type=EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="task_a",
        )
        bridge.on_event(dispatch)
        mock_reporter.reset_mock()

        fail = _make_event(
            event_type=EventType.TASK_FAILED,
            entity_type="task",
            entity_id="task_a",
        )
        bridge.on_event(fail)
        mock_reporter.set_task_run_state.assert_called_once_with("tr_123", "FAILED", "Failed")

    def test_unrelated_event_no_calls(self, bridge, mock_reporter):
        event = _make_event(event_type=EventType.CYCLE_CREATED)
        bridge.on_event(event)
        mock_reporter.set_flow_run_state.assert_not_called()
        mock_reporter.create_task_run.assert_not_called()
        mock_reporter.set_task_run_state.assert_not_called()

    def test_duplicate_task_dispatched_ignored(self, bridge, mock_reporter):
        event = _make_event(
            event_type=EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="task_a",
        )
        bridge.on_event(event)
        bridge.on_event(event)
        assert mock_reporter.create_task_run.call_count == 1

    async def test_task_dispatched_no_deadlock_in_async_context(self, bridge, mock_reporter):
        """on_event from async context must not block the event loop."""
        event = _make_event(
            event_type=EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="task_a",
            payload={"task_name": "My Task"},
        )
        bridge.on_event(event)
        await asyncio.sleep(0)  # yield to let scheduled task complete
        mock_reporter.create_task_run.assert_called_once()
        mock_reporter.set_task_run_state.assert_called_once_with("tr_123", "RUNNING", "Running")

    def test_no_flow_run_id_skips_run_state(self, bridge, mock_reporter):
        event = _make_event(
            event_type=EventType.RUN_STARTED,
            context={"cycle_id": "cyc_1", "run_id": "run_1"},  # no flow_run_id
        )
        bridge.on_event(event)
        mock_reporter.set_flow_run_state.assert_not_called()
