"""Unit tests for telemetry domain models."""

from datetime import UTC, datetime

import pytest

from squadops.tasks.models import TaskEnvelope
from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    MetricType,
    PromptLayer,
    PromptLayerMetadata,
    Span,
    StructuredEvent,
)


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
        now = datetime.now(UTC)
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
        now = datetime.now(UTC)
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


# ---------------------------------------------------------------------------
# SIP-0061: LLM Observability domain model tests
# ---------------------------------------------------------------------------


class TestCorrelationContext:
    """Tests for CorrelationContext frozen dataclass."""

    def test_minimal_context(self):
        ctx = CorrelationContext(cycle_id="cycle-1")
        assert ctx.cycle_id == "cycle-1"
        assert ctx.pulse_id is None
        assert ctx.task_id is None
        assert ctx.correlation_id is None
        assert ctx.agent_id is None

    def test_full_context(self):
        ctx = CorrelationContext(
            cycle_id="c1",
            pulse_id="p1",
            task_id="t1",
            correlation_id="corr-1",
            causation_id="cause-1",
            trace_id="trace-1",
            span_id="span-1",
            agent_id="agent-1",
            agent_role="dev",
            message_id="msg-1",
        )
        assert ctx.pulse_id == "p1"
        assert ctx.task_id == "t1"
        assert ctx.agent_role == "dev"
        assert ctx.message_id == "msg-1"

    def test_context_is_frozen(self):
        ctx = CorrelationContext(cycle_id="c1")
        with pytest.raises(AttributeError):
            ctx.cycle_id = "changed"  # type: ignore

    def test_for_cycle_factory(self):
        ctx = CorrelationContext.for_cycle(cycle_id="cycle-1", agent_id="a1")
        assert ctx.cycle_id == "cycle-1"
        assert ctx.agent_id == "a1"
        assert ctx.pulse_id is None
        assert ctx.task_id is None

    def test_for_pulse_factory(self):
        ctx = CorrelationContext.for_pulse(cycle_id="cycle-1", pulse_id="pulse-1", agent_id="a1")
        assert ctx.cycle_id == "cycle-1"
        assert ctx.pulse_id == "pulse-1"
        assert ctx.agent_id == "a1"
        assert ctx.task_id is None

    def test_from_envelope_factory(self):
        envelope = TaskEnvelope(
            task_id="task-1",
            agent_id="agent-1",
            cycle_id="cycle-1",
            pulse_id="pulse-1",
            project_id="proj-1",
            task_type="dev.code",
            inputs={},
            correlation_id="corr-1",
            causation_id="cause-1",
            trace_id="trace-1",
            span_id="span-1",
        )
        ctx = CorrelationContext.from_envelope(
            envelope=envelope, agent_id="dev-001", agent_role="dev"
        )
        assert ctx.cycle_id == "cycle-1"
        assert ctx.pulse_id == "pulse-1"
        assert ctx.task_id == "task-1"
        assert ctx.correlation_id == "corr-1"
        assert ctx.causation_id == "cause-1"
        assert ctx.trace_id == "trace-1"
        assert ctx.span_id == "span-1"
        assert ctx.agent_id == "dev-001"
        assert ctx.agent_role == "dev"

    def test_nullable_fields(self):
        ctx = CorrelationContext(cycle_id="c1")
        nullable = [
            ctx.pulse_id,
            ctx.task_id,
            ctx.correlation_id,
            ctx.causation_id,
            ctx.trace_id,
            ctx.span_id,
            ctx.agent_id,
            ctx.agent_role,
            ctx.message_id,
        ]
        assert all(v is None for v in nullable)


class TestPromptLayer:
    """Tests for PromptLayer frozen dataclass."""

    def test_minimal_layer(self):
        layer = PromptLayer(layer_type="system", layer_id="sys-1")
        assert layer.layer_type == "system"
        assert layer.layer_id == "sys-1"
        assert layer.layer_version is None
        assert layer.layer_hash is None

    def test_full_layer(self):
        layer = PromptLayer(
            layer_type="task",
            layer_id="task-1",
            layer_version="1.0",
            layer_hash="abc123",
        )
        assert layer.layer_version == "1.0"
        assert layer.layer_hash == "abc123"

    def test_layer_is_frozen(self):
        layer = PromptLayer(layer_type="system", layer_id="sys-1")
        with pytest.raises(AttributeError):
            layer.layer_type = "changed"  # type: ignore


class TestPromptLayerMetadata:
    """Tests for PromptLayerMetadata frozen dataclass."""

    def test_metadata_with_layers(self):
        layers = (
            PromptLayer(layer_type="system", layer_id="sys-1"),
            PromptLayer(layer_type="task", layer_id="task-1"),
        )
        meta = PromptLayerMetadata(prompt_layer_set_id="PLS-1", layers=layers)
        assert meta.prompt_layer_set_id == "PLS-1"
        assert len(meta.layers) == 2
        assert meta.layers[0].layer_type == "system"

    def test_metadata_is_frozen(self):
        meta = PromptLayerMetadata(
            prompt_layer_set_id="PLS-1",
            layers=(PromptLayer(layer_type="system", layer_id="sys-1"),),
        )
        with pytest.raises(AttributeError):
            meta.prompt_layer_set_id = "changed"  # type: ignore

    def test_layers_is_tuple(self):
        meta = PromptLayerMetadata(
            prompt_layer_set_id="PLS-1",
            layers=(PromptLayer(layer_type="system", layer_id="sys-1"),),
        )
        assert isinstance(meta.layers, tuple)


class TestGenerationRecord:
    """Tests for GenerationRecord frozen dataclass."""

    def test_minimal_record(self):
        record = GenerationRecord(
            generation_id="gen-1",
            model="llama3",
            prompt_text="hello",
            response_text="world",
        )
        assert record.generation_id == "gen-1"
        assert record.model == "llama3"
        assert record.prompt_tokens is None
        assert record.latency_ms is None

    def test_full_record(self):
        record = GenerationRecord(
            generation_id="gen-1",
            model="llama3",
            prompt_text="hello",
            response_text="world",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=42.5,
        )
        assert record.prompt_tokens == 10
        assert record.latency_ms == 42.5

    def test_generation_id_is_required(self):
        with pytest.raises(TypeError):
            GenerationRecord(model="m", prompt_text="p", response_text="r")  # type: ignore

    def test_record_is_frozen(self):
        record = GenerationRecord(
            generation_id="gen-1", model="m", prompt_text="p", response_text="r"
        )
        with pytest.raises(AttributeError):
            record.model = "changed"  # type: ignore
