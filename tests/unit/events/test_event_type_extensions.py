"""Tests for SIP-0079 EventType extensions (checkpoint + correction events)."""

import pytest

from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_events]


class TestSIP0079EventTypes:
    def test_all_returns_25_items(self):
        assert len(EventType.all()) == 25

    def test_checkpoint_created_value(self):
        assert EventType.CHECKPOINT_CREATED == "checkpoint.created"

    def test_checkpoint_restored_value(self):
        assert EventType.CHECKPOINT_RESTORED == "checkpoint.restored"

    def test_correction_initiated_value(self):
        assert EventType.CORRECTION_INITIATED == "correction.initiated"

    def test_correction_decided_value(self):
        assert EventType.CORRECTION_DECIDED == "correction.decided"

    def test_correction_completed_value(self):
        assert EventType.CORRECTION_COMPLETED == "correction.completed"

    def test_no_duplicate_values(self):
        all_values = EventType.all()
        assert len(all_values) == len(set(all_values))

    def test_new_entity_types_present(self):
        entities = {et.split(".")[0] for et in EventType.all()}
        assert "checkpoint" in entities
        assert "correction" in entities
