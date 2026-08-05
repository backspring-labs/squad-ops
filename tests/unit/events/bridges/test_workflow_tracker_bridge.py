"""Tests for WorkflowTrackerBridge subscriber.

As of #506 the bridge handles flow-level state transitions ONLY — the full
task-run lifecycle (creation, per-attempt RUNNING, terminal state) is
transport-owned in ``TaskDispatcher.dispatch_task``, so any task event is
a no-op here.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.events.bridges.workflow_tracker import WorkflowTrackerBridge
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
    return WorkflowTrackerBridge(mock_reporter)


@pytest.mark.domain_events
class TestWorkflowTrackerBridgeRunStates:
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

    def test_no_flow_run_id_skips_run_state(self, bridge, mock_reporter):
        event = _make_event(
            event_type=EventType.RUN_STARTED,
            context={"cycle_id": "cyc_1", "run_id": "run_1"},  # no flow_run_id
        )
        bridge.on_event(event)
        mock_reporter.set_flow_run_state.assert_not_called()


@pytest.mark.domain_events
class TestWorkflowTrackerBridgeTaskStates:
    @pytest.mark.parametrize("event_type", [EventType.TASK_SUCCEEDED, EventType.TASK_FAILED])
    def test_terminal_task_events_are_noop(self, bridge, mock_reporter, event_type):
        # #506: the FULL task-run lifecycle is transport-owned in
        # TaskDispatcher.dispatch_task. A bridge transition here would be a
        # second writer of the same state — and its context task_run_id was
        # blank on exactly the paths that needed it (retry re-attempts).
        event = _make_event(
            event_type=event_type,
            entity_type="task",
            entity_id="task_a",
            context={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "task_run_id": "tr_from_executor",
            },
        )
        bridge.on_event(event)
        mock_reporter.set_task_run_state.assert_not_called()

    def test_task_dispatched_is_noop(self, bridge, mock_reporter):
        # Task-run creation moved to the executor; bridge must not react to
        # TASK_DISPATCHED anymore.
        event = _make_event(
            event_type=EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="task_a",
            context={
                "cycle_id": "cyc_1",
                "run_id": "run_1",
                "flow_run_id": "fr_abc",
                "task_run_id": "tr_from_executor",
            },
            payload={"task_name": "My Task"},
        )
        bridge.on_event(event)
        mock_reporter.create_task_run.assert_not_called()
        mock_reporter.set_task_run_state.assert_not_called()

    def test_unrelated_event_no_calls(self, bridge, mock_reporter):
        event = _make_event(event_type=EventType.CYCLE_CREATED)
        bridge.on_event(event)
        mock_reporter.set_flow_run_state.assert_not_called()
        mock_reporter.create_task_run.assert_not_called()
        mock_reporter.set_task_run_state.assert_not_called()
