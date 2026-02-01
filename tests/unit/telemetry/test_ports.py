"""Unit tests for telemetry port interfaces."""
import pytest
from unittest.mock import MagicMock

from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort
from squadops.telemetry.models import Span, StructuredEvent


class TestMetricsPort:
    """Tests for MetricsPort interface."""

    def test_cannot_instantiate_directly(self):
        """MetricsPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            MetricsPort()  # type: ignore

    def test_has_counter_method(self):
        assert hasattr(MetricsPort, "counter")

    def test_has_gauge_method(self):
        assert hasattr(MetricsPort, "gauge")

    def test_has_histogram_method(self):
        assert hasattr(MetricsPort, "histogram")


class TestEventPort:
    """Tests for EventPort interface."""

    def test_cannot_instantiate_directly(self):
        """EventPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            EventPort()  # type: ignore

    def test_has_emit_method(self):
        assert hasattr(EventPort, "emit")

    def test_has_start_span_method(self):
        assert hasattr(EventPort, "start_span")

    def test_has_end_span_method(self):
        assert hasattr(EventPort, "end_span")

    def test_has_span_context_manager(self):
        assert hasattr(EventPort, "span")


class TestEventPortSpanWrapper:
    """Tests for EventPort.span() context manager wrapper."""

    def test_span_wrapper_calls_start_and_end(self):
        """Verify span() calls start_span and end_span correctly."""

        class MockEventPort(EventPort):
            def emit(self, event: StructuredEvent) -> None:
                pass

            def start_span(
                self,
                name: str,
                parent: Span | None = None,
                attributes: dict[str, str] | None = None,
            ) -> Span:
                return Span(
                    name=name,
                    trace_id="test-trace",
                    span_id="test-span",
                    attributes=tuple(attributes.items()) if attributes else (),
                )

            def end_span(self, span: Span) -> None:
                pass

        adapter = MockEventPort()
        adapter.start_span = MagicMock(wraps=adapter.start_span)
        adapter.end_span = MagicMock(wraps=adapter.end_span)

        with adapter.span("test-span", attributes={"key": "value"}) as span:
            assert span.name == "test-span"
            assert span.attributes == (("key", "value"),)

        adapter.start_span.assert_called_once_with("test-span", attributes={"key": "value"})
        adapter.end_span.assert_called_once()

    def test_span_wrapper_ends_span_on_exception(self):
        """Verify span() calls end_span even when exception is raised."""

        class MockEventPort(EventPort):
            def emit(self, event: StructuredEvent) -> None:
                pass

            def start_span(
                self,
                name: str,
                parent: Span | None = None,
                attributes: dict[str, str] | None = None,
            ) -> Span:
                return Span(name=name, trace_id="test", span_id="test")

            def end_span(self, span: Span) -> None:
                pass

        adapter = MockEventPort()
        adapter.end_span = MagicMock(wraps=adapter.end_span)

        with pytest.raises(ValueError):
            with adapter.span("test"):
                raise ValueError("test error")

        # end_span should still be called
        adapter.end_span.assert_called_once()
