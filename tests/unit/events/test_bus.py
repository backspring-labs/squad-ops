"""Tests for InProcessCycleEventBus, NoOpCycleEventBus, and factory."""

import pytest

from adapters.events.factory import create_cycle_event_bus
from adapters.events.in_process_cycle_event_bus import InProcessCycleEventBus
from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus
from squadops.events.models import CycleEvent
from squadops.events.types import EventType
from squadops.ports.events.cycle_event_bus import CycleEventBusPort
from tests.unit.events.conftest import CollectingSubscriber


@pytest.mark.domain_events
class TestInProcessCycleEventBus:
    def test_emit_returns_cycle_event(self, event_bus):
        result = event_bus.emit(
            EventType.RUN_STARTED,
            entity_type="run",
            entity_id="run_1",
            context={"cycle_id": "cyc_1"},
        )
        assert isinstance(result, CycleEvent)
        assert result.event_type == "run.started"
        assert result.entity_type == "run"
        assert result.entity_id == "run_1"

    def test_emit_enriches_envelope_fields(self, event_bus):
        result = event_bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
        )
        assert result.event_id.startswith("evt_")
        assert result.occurred_at is not None
        assert result.source_service == "test-service"
        assert result.source_version == "0.0.1"

    def test_subscriber_receives_event(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.RUN_STARTED,
            entity_type="run",
            entity_id="run_1",
        )
        assert len(collector.events) == 1
        assert collector.events[0].event_type == "run.started"

    def test_multiple_subscribers_called_in_order(self, event_bus):
        order = []

        class Sub:
            def __init__(self, name):
                self.name = name

            def on_event(self, event):
                order.append(self.name)

        event_bus.subscribe(Sub("first"))
        event_bus.subscribe(Sub("second"))
        event_bus.subscribe(Sub("third"))
        event_bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
        )
        assert order == ["first", "second", "third"]

    def test_subscriber_failure_does_not_propagate(self, event_bus, collector):
        class FailingSub:
            def on_event(self, event):
                raise RuntimeError("boom")

        event_bus.subscribe(FailingSub())
        event_bus.subscribe(collector)

        # Should not raise
        result = event_bus.emit(
            EventType.RUN_FAILED,
            entity_type="run",
            entity_id="run_1",
        )
        assert result is not None
        # Second subscriber still called
        assert len(collector.events) == 1

    def test_sequence_monotonicity(self, event_bus, collector):
        event_bus.subscribe(collector)
        ctx = {"cycle_id": "cyc_1", "run_id": "run_1"}
        for _ in range(5):
            event_bus.emit(
                EventType.TASK_DISPATCHED,
                entity_type="task",
                entity_id="task_x",
                context=ctx,
            )
        sequences = [e.sequence for e in collector.events]
        assert sequences == [1, 2, 3, 4, 5]

    def test_independent_sequences_per_run(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="t1",
            context={"cycle_id": "cyc_1", "run_id": "run_a"},
        )
        event_bus.emit(
            EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="t2",
            context={"cycle_id": "cyc_1", "run_id": "run_b"},
        )
        event_bus.emit(
            EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id="t3",
            context={"cycle_id": "cyc_1", "run_id": "run_a"},
        )
        # run_a: seq 1, 2; run_b: seq 1
        assert collector.events[0].sequence == 1  # run_a
        assert collector.events[1].sequence == 1  # run_b
        assert collector.events[2].sequence == 2  # run_a

    def test_cycle_level_events_use_empty_run_id(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
            context={"cycle_id": "cyc_1"},
        )
        assert collector.events[0].sequence == 1
        assert "cyc_1" in collector.events[0].semantic_key

    def test_semantic_key_format(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.RUN_STARTED,
            entity_type="run",
            entity_id="run_1",
            context={"cycle_id": "cyc_1", "run_id": "run_1"},
        )
        key = collector.events[0].semantic_key
        assert key == "cyc_1:run:run_1:started:1"

    def test_event_id_uniqueness(self, event_bus, collector):
        event_bus.subscribe(collector)
        for _ in range(1000):
            event_bus.emit(
                EventType.TASK_DISPATCHED,
                entity_type="task",
                entity_id="t",
                context={"cycle_id": "c", "run_id": "r"},
            )
        ids = [e.event_id for e in collector.events]
        assert len(set(ids)) == 1000

    def test_context_defaults_to_empty(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
        )
        assert collector.events[0].context == {}

    def test_payload_defaults_to_empty(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
        )
        assert collector.events[0].payload == {}

    def test_payload_passed_through(self, event_bus, collector):
        event_bus.subscribe(collector)
        event_bus.emit(
            EventType.RUN_COMPLETED,
            entity_type="run",
            entity_id="run_1",
            payload={"duration_ms": 5000},
        )
        assert collector.events[0].payload == {"duration_ms": 5000}


@pytest.mark.domain_events
class TestNoOpCycleEventBus:
    def test_emit_returns_none(self):
        bus = NoOpCycleEventBus()
        result = bus.emit(
            EventType.RUN_STARTED,
            entity_type="run",
            entity_id="run_1",
        )
        assert result is None

    def test_subscribe_does_not_raise(self):
        bus = NoOpCycleEventBus()
        bus.subscribe(CollectingSubscriber())  # no error

    def test_emit_does_not_raise(self):
        bus = NoOpCycleEventBus()
        bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
            context={"cycle_id": "cyc_1"},
            payload={"key": "val"},
        )


@pytest.mark.domain_events
class TestFactory:
    def test_in_process_provider(self):
        bus = create_cycle_event_bus(
            "in_process",
            source_service="test",
            source_version="1.0.0",
        )
        assert isinstance(bus, InProcessCycleEventBus)
        assert isinstance(bus, CycleEventBusPort)

    def test_noop_provider(self):
        bus = create_cycle_event_bus("noop")
        assert isinstance(bus, NoOpCycleEventBus)
        assert isinstance(bus, CycleEventBusPort)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown cycle event bus provider"):
            create_cycle_event_bus("rabbitmq")

    def test_default_provider_is_in_process(self):
        bus = create_cycle_event_bus()
        assert isinstance(bus, InProcessCycleEventBus)
