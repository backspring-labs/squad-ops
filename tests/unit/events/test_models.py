"""Tests for CycleEvent domain model."""

import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from squadops.events.models import CycleEvent
from squadops.events.types import EventType


def _make_event(**overrides) -> CycleEvent:
    defaults = {
        "event_id": "evt_test123",
        "occurred_at": datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
        "source_service": "runtime-api",
        "source_version": "0.9.15",
        "event_type": EventType.RUN_STARTED,
        "entity_type": "run",
        "entity_id": "run_abc123",
        "context": {"cycle_id": "cyc_001", "project_id": "proj_001"},
        "payload": {"workload_type": "implementation"},
        "sequence": 1,
        "semantic_key": "cyc_001:run:run_abc123:started:1",
    }
    defaults.update(overrides)
    return CycleEvent(**defaults)


@pytest.mark.domain_events
class TestCycleEvent:
    def test_construction(self):
        event = _make_event()
        assert event.event_id == "evt_test123"
        assert event.event_type == "run.started"
        assert event.entity_type == "run"
        assert event.entity_id == "run_abc123"

    def test_frozen_immutability(self):
        event = _make_event()
        with pytest.raises(FrozenInstanceError):
            event.event_id = "different"  # type: ignore[misc]

    def test_required_fields(self):
        with pytest.raises(TypeError):
            CycleEvent()  # type: ignore[call-arg]

    def test_context_defaults_to_empty_dict(self):
        event = CycleEvent(
            event_id="evt_1",
            occurred_at=datetime.now(tz=timezone.utc),
            source_service="test",
            source_version="0.0.0",
            event_type=EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
        )
        assert event.context == {}
        assert event.payload == {}

    def test_sequence_defaults_to_zero(self):
        event = CycleEvent(
            event_id="evt_1",
            occurred_at=datetime.now(tz=timezone.utc),
            source_service="test",
            source_version="0.0.0",
            event_type=EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id="cyc_1",
        )
        assert event.sequence == 0
        assert event.semantic_key == ""

    def test_all_fields_accessible(self):
        event = _make_event()
        assert event.source_service == "runtime-api"
        assert event.source_version == "0.9.15"
        assert event.occurred_at.year == 2026
        assert event.context["cycle_id"] == "cyc_001"
        assert event.payload["workload_type"] == "implementation"
        assert event.sequence == 1
        assert "cyc_001" in event.semantic_key

    def test_equality(self):
        e1 = _make_event()
        e2 = _make_event()
        assert e1 == e2

    def test_inequality_on_different_id(self):
        e1 = _make_event(event_id="evt_a")
        e2 = _make_event(event_id="evt_b")
        assert e1 != e2

    def test_context_isolation(self):
        """Context dicts from different events are independent."""
        e1 = _make_event(context={"a": 1})
        e2 = _make_event(context={"b": 2})
        assert e1.context != e2.context

    def test_payload_isolation(self):
        """Payload dicts from different events are independent."""
        e1 = _make_event(payload={"x": 1})
        e2 = _make_event(payload={"y": 2})
        assert e1.payload != e2.payload

    def test_each_event_type_constructable(self):
        """Every EventType constant can construct a valid CycleEvent."""
        for et in EventType.all():
            entity = et.split(".")[0]
            event = CycleEvent(
                event_id=f"evt_{et}",
                occurred_at=datetime.now(tz=timezone.utc),
                source_service="test",
                source_version="0.0.0",
                event_type=et,
                entity_type=entity,
                entity_id=f"{entity}_test",
            )
            assert event.event_type == et
            assert event.entity_type == entity
