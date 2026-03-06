"""Tests for AuditEvent model (SIP-0062 Phase 3b)."""

from datetime import UTC, datetime

import pytest

from squadops.auth.models import AuditEvent


@pytest.mark.auth
class TestAuditEvent:
    def test_frozen_immutability(self):
        event = AuditEvent(
            action="auth.token_validated",
            actor_id="user-1",
            actor_type="human",
            resource_type="api",
        )
        with pytest.raises(AttributeError):
            event.action = "changed"  # type: ignore

    def test_defaults_for_optionals(self):
        event = AuditEvent(
            action="test",
            actor_id="u1",
            actor_type="human",
            resource_type="api",
        )
        assert event.result == "success"
        assert event.denial_reason is None
        assert event.resource_id is None
        assert event.metadata == ()
        assert event.request_id is None
        assert event.ip_address is None
        # event_id is auto-generated UUID
        assert len(event.event_id) > 0

    def test_timestamp_must_be_timezone_aware(self):
        """All AuditEvent timestamps MUST be timezone-aware UTC."""
        event = AuditEvent(
            action="test",
            actor_id="u1",
            actor_type="human",
            resource_type="api",
        )
        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo == UTC

    def test_timestamp_default_is_utc(self):
        """Default timestamp uses datetime.now(timezone.utc)."""
        before = datetime.now(UTC)
        event = AuditEvent(
            action="test",
            actor_id="u1",
            actor_type="human",
            resource_type="api",
        )
        after = datetime.now(UTC)
        assert before <= event.timestamp <= after

    def test_metadata_as_tuples(self):
        event = AuditEvent(
            action="test",
            actor_id="u1",
            actor_type="human",
            resource_type="api",
            metadata=(("key1", "val1"), ("key2", "val2")),
        )
        assert event.metadata == (("key1", "val1"), ("key2", "val2"))

    def test_event_id_unique(self):
        e1 = AuditEvent(action="test", actor_id="u1", actor_type="human", resource_type="api")
        e2 = AuditEvent(action="test", actor_id="u1", actor_type="human", resource_type="api")
        assert e1.event_id != e2.event_id
