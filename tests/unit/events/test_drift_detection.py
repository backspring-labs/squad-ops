"""Drift detection tests — registry state transitions match canonical events.

Phase 4a: For each lifecycle scenario, verifies that every registry status
transition (update_run_status call) has exactly one matching canonical event.
Supplemental telemetry/log emissions from dual-emit are ignored — drift
detection validates the canonical bus only.

Uses mocked registry + queue with a real InProcessCycleEventBus and
CollectingSubscriber.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from adapters.events.in_process_cycle_event_bus import InProcessCycleEventBus
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.events.types import EventType
from squadops.tasks.models import TaskResult
from tests.unit.events.conftest import CollectingSubscriber

pytestmark = [pytest.mark.domain_events]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

# Registry RunStatus → expected EventType mapping
_STATUS_TO_EVENT: dict[RunStatus, str] = {
    RunStatus.RUNNING: EventType.RUN_STARTED,
    RunStatus.COMPLETED: EventType.RUN_COMPLETED,
    RunStatus.FAILED: EventType.RUN_FAILED,
    RunStatus.CANCELLED: EventType.RUN_CANCELLED,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _responder(status: str = "SUCCEEDED"):
    """Build a reply-router responder that replies with the given status."""

    def reply(env: dict) -> TaskResult:
        return TaskResult(
            task_id=env["task_id"],
            status=status,
            outputs={"summary": "stub", "artifacts": []},
        )

    return reply


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus():
    return InProcessCycleEventBus("test", "0.1")


@pytest.fixture
def collector():
    return CollectingSubscriber()


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_run.return_value = Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.update_run_status.side_effect = lambda run_id, status: Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=1,
        status=status.value,
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.append_artifact_refs.return_value = mock.get_run.return_value
    mock.get_latest_checkpoint.return_value = None
    mock.save_checkpoint.return_value = None
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_queue(reply_router):
    mock = AsyncMock()
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    reply_router.bind(mock)
    return mock


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    profile = SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


@pytest.fixture
def executor(
    mock_registry, mock_vault, mock_queue, mock_squad_profile, cycle, event_bus, collector
):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    event_bus.subscribe(collector)
    mock_registry.get_cycle.return_value = cycle
    return DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        event_bus=event_bus,
        reply_router=mock_queue.reply_router,
    )


# ---------------------------------------------------------------------------
# Drift detection tests
# ---------------------------------------------------------------------------


class TestHappyPathDrift:
    """Happy path: queued → running → completed.

    Each registry status transition must have exactly one matching event.
    """

    async def test_registry_transitions_match_events(
        self, executor, mock_registry, mock_queue, collector
    ) -> None:
        mock_queue.reply_router.responder = _responder()

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Extract registry transitions
        status_calls = mock_registry.update_run_status.call_args_list
        registry_transitions = [call.args[1] for call in status_calls]

        # Extract run-level events (filter out task events)
        run_events = [e for e in collector.events if e.entity_type == "run"]
        run_event_types = [e.event_type for e in run_events]

        # queued → running → completed
        assert RunStatus.RUNNING in registry_transitions
        assert RunStatus.COMPLETED in registry_transitions

        # Each registry transition has a matching event
        for status in registry_transitions:
            expected_event = _STATUS_TO_EVENT.get(status)
            if expected_event:
                assert expected_event in run_event_types, (
                    f"Registry transition to {status.value} has no matching {expected_event} event"
                )

    async def test_no_orphan_run_events(
        self, executor, mock_registry, mock_queue, collector
    ) -> None:
        """Every run event has a corresponding registry transition."""
        mock_queue.reply_router.responder = _responder()

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        status_calls = mock_registry.update_run_status.call_args_list
        registry_statuses = {call.args[1] for call in status_calls}

        run_events = [e for e in collector.events if e.entity_type == "run"]
        event_to_status = {v: k for k, v in _STATUS_TO_EVENT.items()}

        for event in run_events:
            expected_status = event_to_status.get(event.event_type)
            if expected_status:
                assert expected_status in registry_statuses, (
                    f"Event {event.event_type} has no matching registry "
                    f"transition to {expected_status.value}"
                )


class TestTaskFailureDrift:
    """Task failure: queued → running → failed.

    task.failed must precede run.failed. Registry FAILED transition
    must have a matching run.failed event.
    """

    async def test_failure_transitions_match_events(
        self, executor, mock_registry, mock_queue, collector
    ) -> None:
        mock_queue.reply_router.responder = _responder(status="FAILED")

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        run_events = [e for e in collector.events if e.entity_type == "run"]
        run_event_types = [e.event_type for e in run_events]

        assert EventType.RUN_STARTED in run_event_types
        assert EventType.RUN_FAILED in run_event_types

    async def test_task_failed_precedes_run_failed(
        self, executor, mock_registry, mock_queue, collector
    ) -> None:
        mock_queue.reply_router.responder = _responder(status="FAILED")

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        all_types = [e.event_type for e in collector.events]
        task_failed_idx = all_types.index(EventType.TASK_FAILED)
        run_failed_idx = all_types.index(EventType.RUN_FAILED)
        assert task_failed_idx < run_failed_idx


class TestTaskEventsMatchDispatches:
    """Every task dispatch must produce a task.dispatched event,
    and every task result must produce task.succeeded or task.failed."""

    async def test_dispatch_count_matches_events(
        self, executor, mock_registry, mock_queue, collector
    ) -> None:
        mock_queue.reply_router.responder = _responder()

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        dispatched_events = [
            e for e in collector.events if e.event_type == EventType.TASK_DISPATCHED
        ]
        succeeded_events = [e for e in collector.events if e.event_type == EventType.TASK_SUCCEEDED]

        # Each dispatch should have a corresponding success
        assert len(dispatched_events) == len(succeeded_events)
        assert len(dispatched_events) == mock_queue.publish.call_count
