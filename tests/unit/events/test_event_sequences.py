"""Event sequence tests — lifecycle paths produce expected event subsets
with monotonic sequences and unique semantic keys.

Phase 3e: Scenario-specific tests that verify event ordering and
sequence integrity for common lifecycle paths.
"""

from __future__ import annotations

import pytest

from adapters.events.in_process_cycle_event_bus import InProcessCycleEventBus
from squadops.events.types import EventType
from tests.unit.events.conftest import CollectingSubscriber

pytestmark = [pytest.mark.domain_events]


def _emit_scenario(
    bus: InProcessCycleEventBus,
    events: list[tuple[str, str, str]],
    cycle_id: str = "cyc_001",
    run_id: str = "run_001",
    project_id: str = "proj_001",
) -> None:
    """Emit a sequence of events for a scenario.

    Each tuple is (event_type, entity_type, entity_id).
    """
    for event_type, entity_type, entity_id in events:
        bus.emit(
            event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            context={
                "cycle_id": cycle_id,
                "run_id": run_id,
                "project_id": project_id,
            },
            payload={},
        )


class TestHappyPathSequence:
    """A successful run produces events in expected order."""

    def test_happy_path_event_types(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_SUCCEEDED, "task", "task_001"),
                (EventType.TASK_DISPATCHED, "task", "task_002"),
                (EventType.TASK_SUCCEEDED, "task", "task_002"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        types = [e.event_type for e in collector.events]
        assert types == [
            EventType.RUN_STARTED,
            EventType.TASK_DISPATCHED,
            EventType.TASK_SUCCEEDED,
            EventType.TASK_DISPATCHED,
            EventType.TASK_SUCCEEDED,
            EventType.RUN_COMPLETED,
        ]

    def test_sequences_are_monotonic(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_SUCCEEDED, "task", "task_001"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        sequences = [e.sequence for e in collector.events]
        assert sequences == [1, 2, 3, 4]

    def test_semantic_keys_are_unique(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_SUCCEEDED, "task", "task_001"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        keys = [e.semantic_key for e in collector.events]
        assert len(keys) == len(set(keys))


class TestFailureSequence:
    """A failed task produces run.failed after task.failed."""

    def test_failure_event_order(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_FAILED, "task", "task_001"),
                (EventType.RUN_FAILED, "run", "run_001"),
            ],
        )

        types = [e.event_type for e in collector.events]
        assert types == [
            EventType.RUN_STARTED,
            EventType.TASK_DISPATCHED,
            EventType.TASK_FAILED,
            EventType.RUN_FAILED,
        ]

    def test_failure_sequences_monotonic(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_FAILED, "task", "task_001"),
                (EventType.RUN_FAILED, "run", "run_001"),
            ],
        )

        sequences = [e.sequence for e in collector.events]
        assert sequences == [1, 2, 3, 4]


class TestGatePauseSequence:
    """A gate pause produces run.paused then run.resumed."""

    def test_gate_pause_resume_order(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_SUCCEEDED, "task", "task_001"),
                (EventType.RUN_PAUSED, "run", "run_001"),
                (EventType.GATE_DECIDED, "gate", "progress_gate"),
                (EventType.RUN_RESUMED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_002"),
                (EventType.TASK_SUCCEEDED, "task", "task_002"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        types = [e.event_type for e in collector.events]
        assert EventType.RUN_PAUSED in types
        pause_idx = types.index(EventType.RUN_PAUSED)
        resume_idx = types.index(EventType.RUN_RESUMED)
        assert resume_idx > pause_idx

    def test_gate_pause_sequence_continuity(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.RUN_PAUSED, "run", "run_001"),
                (EventType.GATE_DECIDED, "gate", "progress_gate"),
                (EventType.RUN_RESUMED, "run", "run_001"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        sequences = [e.sequence for e in collector.events]
        assert sequences == [1, 2, 3, 4, 5]


class TestPulseRepairSequence:
    """Pulse verification with repair produces expected event subset."""

    def test_pulse_repair_event_order(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.PULSE_BOUNDARY_REACHED, "pulse", "boundary_1"),
                (EventType.PULSE_SUITE_EVALUATED, "pulse", "suite_001"),
                (EventType.PULSE_BOUNDARY_DECIDED, "pulse", "boundary_1"),
                (EventType.PULSE_REPAIR_STARTED, "pulse", "boundary_1"),
                # After repair, re-evaluate
                (EventType.PULSE_BOUNDARY_REACHED, "pulse", "boundary_1"),
                (EventType.PULSE_SUITE_EVALUATED, "pulse", "suite_001"),
                (EventType.PULSE_BOUNDARY_DECIDED, "pulse", "boundary_1"),
            ],
        )

        types = [e.event_type for e in collector.events]
        assert types[0] == EventType.PULSE_BOUNDARY_REACHED
        assert EventType.PULSE_REPAIR_STARTED in types

    def test_pulse_exhaustion_sequence(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.PULSE_BOUNDARY_REACHED, "pulse", "boundary_1"),
                (EventType.PULSE_SUITE_EVALUATED, "pulse", "suite_001"),
                (EventType.PULSE_BOUNDARY_DECIDED, "pulse", "boundary_1"),
                (EventType.PULSE_REPAIR_STARTED, "pulse", "boundary_1"),
                (EventType.PULSE_BOUNDARY_REACHED, "pulse", "boundary_1"),
                (EventType.PULSE_SUITE_EVALUATED, "pulse", "suite_001"),
                (EventType.PULSE_BOUNDARY_DECIDED, "pulse", "boundary_1"),
                (EventType.PULSE_REPAIR_EXHAUSTED, "pulse", "boundary_1"),
                (EventType.RUN_FAILED, "run", "run_001"),
            ],
        )

        types = [e.event_type for e in collector.events]
        exhausted_idx = types.index(EventType.PULSE_REPAIR_EXHAUSTED)
        failed_idx = types.index(EventType.RUN_FAILED)
        assert failed_idx > exhausted_idx


class TestIndependentRunSequences:
    """Different runs have independent sequence counters."""

    def test_independent_sequences(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        # Run 1
        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
            run_id="run_001",
        )

        # Run 2
        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_002"),
                (EventType.RUN_COMPLETED, "run", "run_002"),
            ],
            run_id="run_002",
        )

        run1_events = [e for e in collector.events if e.context.get("run_id") == "run_001"]
        run2_events = [e for e in collector.events if e.context.get("run_id") == "run_002"]

        assert [e.sequence for e in run1_events] == [1, 2]
        assert [e.sequence for e in run2_events] == [1, 2]


class TestEventIdentity:
    """All events in a scenario have unique event_id and semantic_key."""

    def test_unique_event_ids_across_scenario(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_SUCCEEDED, "task", "task_001"),
                (EventType.TASK_DISPATCHED, "task", "task_002"),
                (EventType.TASK_SUCCEEDED, "task", "task_002"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        event_ids = [e.event_id for e in collector.events]
        assert len(event_ids) == len(set(event_ids))

    def test_unique_semantic_keys_across_scenario(self) -> None:
        bus = InProcessCycleEventBus("test", "0.1")
        collector = CollectingSubscriber()
        bus.subscribe(collector)

        _emit_scenario(
            bus,
            [
                (EventType.RUN_STARTED, "run", "run_001"),
                (EventType.TASK_DISPATCHED, "task", "task_001"),
                (EventType.TASK_SUCCEEDED, "task", "task_001"),
                (EventType.TASK_DISPATCHED, "task", "task_002"),
                (EventType.TASK_SUCCEEDED, "task", "task_002"),
                (EventType.RUN_COMPLETED, "run", "run_001"),
            ],
        )

        keys = [e.semantic_key for e in collector.events]
        assert len(keys) == len(set(keys))
