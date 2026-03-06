"""Tests for LangFuseBridge subscriber."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from squadops.events.bridges.langfuse import LangFuseBridge
from squadops.events.models import CycleEvent
from squadops.events.types import EventType
from squadops.telemetry.models import CorrelationContext, StructuredEvent


def _make_event(**overrides) -> CycleEvent:
    defaults = {
        "event_id": "evt_test1",
        "occurred_at": datetime(2026, 3, 1, tzinfo=UTC),
        "source_service": "test",
        "source_version": "0.0.1",
        "event_type": EventType.RUN_STARTED,
        "entity_type": "run",
        "entity_id": "run_1",
        "context": {"cycle_id": "cyc_1", "trace_id": "trace_abc"},
        "payload": {},
        "sequence": 1,
        "semantic_key": "cyc_1:run:run_1:started:1",
    }
    defaults.update(overrides)
    return CycleEvent(**defaults)


@pytest.fixture
def mock_obs():
    return MagicMock()


@pytest.fixture
def bridge(mock_obs):
    return LangFuseBridge(mock_obs)


@pytest.mark.domain_events
class TestLangFuseBridge:
    def test_record_event_called(self, bridge, mock_obs):
        bridge.on_event(_make_event())
        mock_obs.record_event.assert_called_once()

    def test_correlation_context_uses_cycle_id(self, bridge, mock_obs):
        bridge.on_event(_make_event(context={"cycle_id": "cyc_99"}))
        ctx = mock_obs.record_event.call_args[0][0]
        assert isinstance(ctx, CorrelationContext)
        assert ctx.cycle_id == "cyc_99"

    def test_correlation_context_uses_trace_id(self, bridge, mock_obs):
        bridge.on_event(_make_event(context={"cycle_id": "cyc_1", "trace_id": "t_123"}))
        ctx = mock_obs.record_event.call_args[0][0]
        assert ctx.trace_id == "t_123"

    def test_correlation_context_missing_trace_id(self, bridge, mock_obs):
        bridge.on_event(_make_event(context={"cycle_id": "cyc_1"}))
        ctx = mock_obs.record_event.call_args[0][0]
        assert ctx.trace_id is None

    def test_structured_event_name_is_event_type(self, bridge, mock_obs):
        bridge.on_event(_make_event(event_type=EventType.TASK_DISPATCHED))
        se = mock_obs.record_event.call_args[0][1]
        assert isinstance(se, StructuredEvent)
        assert se.name == "task.dispatched"

    def test_structured_event_message_format(self, bridge, mock_obs):
        bridge.on_event(_make_event(entity_type="run", entity_id="run_42"))
        se = mock_obs.record_event.call_args[0][1]
        assert "run" in se.message
        assert "run_42" in se.message

    def test_payload_attributes_included(self, bridge, mock_obs):
        bridge.on_event(_make_event(payload={"duration_ms": 5000, "status": "ok"}))
        se = mock_obs.record_event.call_args[0][1]
        attr_dict = dict(se.attributes)
        assert attr_dict["duration_ms"] == 5000
        assert attr_dict["status"] == "ok"

    def test_entity_fields_in_attributes(self, bridge, mock_obs):
        bridge.on_event(_make_event(entity_type="task", entity_id="t_1"))
        se = mock_obs.record_event.call_args[0][1]
        attr_dict = dict(se.attributes)
        assert attr_dict["entity_type"] == "task"
        assert attr_dict["entity_id"] == "t_1"

    def test_event_id_in_attributes(self, bridge, mock_obs):
        bridge.on_event(_make_event(event_id="evt_xyz"))
        se = mock_obs.record_event.call_args[0][1]
        attr_dict = dict(se.attributes)
        assert attr_dict["event_id"] == "evt_xyz"

    def test_empty_context_defaults(self, bridge, mock_obs):
        bridge.on_event(_make_event(context={}))
        ctx = mock_obs.record_event.call_args[0][0]
        assert ctx.cycle_id == ""
        assert ctx.trace_id is None
