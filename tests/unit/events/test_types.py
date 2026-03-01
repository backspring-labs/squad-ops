"""Tests for EventType constants."""

import pytest

from squadops.events.types import EventType


@pytest.mark.domain_events
class TestEventType:
    def test_all_returns_20_events(self):
        all_types = EventType.all()
        assert len(all_types) == 20

    def test_entity_transition_format(self):
        for event_type in EventType.all():
            parts = event_type.split(".")
            assert len(parts) == 2, f"Expected 'entity.transition' format, got: {event_type}"
            entity, transition = parts
            assert entity, f"Empty entity in: {event_type}"
            assert transition, f"Empty transition in: {event_type}"

    def test_all_six_entity_types_present(self):
        entities = {et.split(".")[0] for et in EventType.all()}
        assert entities == {"cycle", "run", "gate", "task", "pulse", "artifact"}

    def test_entity_counts(self):
        by_entity: dict[str, int] = {}
        for et in EventType.all():
            entity = et.split(".")[0]
            by_entity[entity] = by_entity.get(entity, 0) + 1
        assert by_entity == {
            "cycle": 2,
            "run": 7,
            "gate": 1,
            "task": 3,
            "pulse": 5,
            "artifact": 2,
        }

    def test_constants_match_all(self):
        """Every class-level constant appears in all() and vice versa."""
        constants = {
            v
            for k, v in vars(EventType).items()
            if not k.startswith("_") and k == k.upper() and isinstance(v, str)
        }
        assert constants == set(EventType.all())
