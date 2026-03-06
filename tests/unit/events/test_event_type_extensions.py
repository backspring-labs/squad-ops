"""Tests for SIP-0079 EventType extensions (checkpoint + correction events)."""

import pytest

from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_events]


class TestSIP0079EventTypes:
    def test_all_returns_25_items(self):
        assert len(EventType.all()) == 25

    def test_no_duplicate_values(self):
        all_values = EventType.all()
        assert len(all_values) == len(set(all_values))

    def test_new_entity_types_present(self):
        entities = {et.split(".")[0] for et in EventType.all()}
        assert "checkpoint" in entities
        assert "correction" in entities
