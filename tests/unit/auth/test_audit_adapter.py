"""Tests for LoggingAuditAdapter (SIP-0062 Phase 3b)."""

import json
import logging

import pytest

from adapters.audit.logging_adapter import LoggingAuditAdapter
from squadops.auth.models import AuditEvent


@pytest.fixture
def adapter():
    return LoggingAuditAdapter()


@pytest.fixture
def sample_event():
    return AuditEvent(
        action="auth.token_validated",
        actor_id="user-42",
        actor_type="human",
        resource_type="api",
        resource_id="/api/v1/tasks",
        request_id="req-123",
        ip_address="192.168.1.1",
    )


@pytest.mark.auth
class TestLoggingAuditAdapter:
    def test_record_emits_json_to_logger(self, adapter, sample_event, caplog):
        with caplog.at_level(logging.INFO, logger="squadops.audit"):
            adapter.record(sample_event)

        assert len(caplog.records) == 1
        data = json.loads(caplog.records[0].message)
        assert data["action"] == "auth.token_validated"

    def test_json_contains_all_fields(self, adapter, sample_event, caplog):
        with caplog.at_level(logging.INFO, logger="squadops.audit"):
            adapter.record(sample_event)

        data = json.loads(caplog.records[0].message)
        assert data["event_id"] == sample_event.event_id
        assert data["action"] == "auth.token_validated"
        assert data["actor_id"] == "user-42"
        assert data["actor_type"] == "human"
        assert data["resource_type"] == "api"
        assert data["resource_id"] == "/api/v1/tasks"
        assert data["result"] == "success"
        assert data["denial_reason"] is None
        assert data["request_id"] == "req-123"
        assert data["ip_address"] == "192.168.1.1"
        assert data["metadata"] == {}

    def test_timestamp_serialized_with_timezone(self, adapter, sample_event, caplog):
        with caplog.at_level(logging.INFO, logger="squadops.audit"):
            adapter.record(sample_event)

        data = json.loads(caplog.records[0].message)
        # isoformat() on TZ-aware datetime includes +00:00
        assert "+00:00" in data["timestamp"]

    def test_swallows_internal_errors(self, adapter):
        """record() MUST NOT raise even if something goes wrong internally."""
        # Create an event with a broken timestamp that can't be serialized
        # Using a valid event but monkeypatching json.dumps to fail
        event = AuditEvent(
            action="test",
            actor_id="u1",
            actor_type="human",
            resource_type="api",
        )
        # This should not raise
        import unittest.mock as mock

        with mock.patch("adapters.audit.logging_adapter.json.dumps", side_effect=Exception("boom")):
            adapter.record(event)  # Should not raise

    def test_close_is_noop(self, adapter):
        """close() should not raise."""
        adapter.close()
