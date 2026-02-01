"""Unit tests for telemetry domain models."""
import pytest
from datetime import datetime, timezone

from squadops.telemetry.models import MetricType, Span, StructuredEvent


class TestMetricType:
    """Tests for MetricType enum."""

    def test_counter_value(self):
        assert MetricType.COUNTER.value == "counter"

    def test_gauge_value(self):
        assert MetricType.GAUGE.value == "gauge"

    def test_histogram_value(self):
        assert MetricType.HISTOGRAM.value == "histogram"

    def test_all_types_defined(self):
        assert len(MetricType) == 3


class TestSpan:
    """Tests for Span dataclass."""

    def test_minimal_span(self):
        span = Span(name="test", trace_id="trace-1", span_id="span-1")
        assert span.name == "test"
        assert span.trace_id == "trace-1"
        assert span.span_id == "span-1"
        assert span.parent_span_id is None
        assert span.start_time is None
        assert span.end_time is None
        assert span.attributes == ()

    def test_full_span(self):
        now = datetime.now(timezone.utc)
        span = Span(
            name="test",
            trace_id="trace-1",
            span_id="span-1",
            parent_span_id="parent-1",
            start_time=now,
            end_time=now,
            attributes=(("key", "value"),),
        )
        assert span.parent_span_id == "parent-1"
        assert span.start_time == now
        assert span.end_time == now
        assert span.attributes == (("key", "value"),)

    def test_span_is_frozen(self):
        span = Span(name="test", trace_id="trace-1", span_id="span-1")
        with pytest.raises(AttributeError):
            span.name = "modified"  # type: ignore


class TestStructuredEvent:
    """Tests for StructuredEvent dataclass."""

    def test_minimal_event(self):
        event = StructuredEvent(name="test", message="test message")
        assert event.name == "test"
        assert event.message == "test message"
        assert event.level == "info"
        assert event.attributes == ()
        assert event.timestamp is None
        assert event.span_id is None

    def test_full_event(self):
        now = datetime.now(timezone.utc)
        event = StructuredEvent(
            name="test",
            message="test message",
            level="error",
            attributes=(("key", "value"),),
            timestamp=now,
            span_id="span-1",
        )
        assert event.level == "error"
        assert event.attributes == (("key", "value"),)
        assert event.timestamp == now
        assert event.span_id == "span-1"

    def test_event_is_frozen(self):
        event = StructuredEvent(name="test", message="test message")
        with pytest.raises(AttributeError):
            event.name = "modified"  # type: ignore

    def test_event_level_options(self):
        for level in ["debug", "info", "warning", "error"]:
            event = StructuredEvent(name="test", message="msg", level=level)
            assert event.level == level
