"""Unit tests for telemetry factory."""
import pytest

from adapters.telemetry.console import ConsoleAdapter
from adapters.telemetry.factory import (
    create_event_provider,
    create_metrics_provider,
    create_telemetry_provider,
)
from adapters.telemetry.null import NullAdapter
from adapters.telemetry.otel import OTelAdapter


class TestCreateMetricsProvider:
    """Tests for create_metrics_provider factory."""

    def test_creates_otel_adapter_by_default(self):
        adapter = create_metrics_provider()
        assert isinstance(adapter, OTelAdapter)

    def test_creates_otel_adapter_explicitly(self):
        adapter = create_metrics_provider(provider="otel")
        assert isinstance(adapter, OTelAdapter)

    def test_creates_console_adapter(self):
        adapter = create_metrics_provider(provider="console")
        assert isinstance(adapter, ConsoleAdapter)

    def test_creates_null_adapter(self):
        adapter = create_metrics_provider(provider="null")
        assert isinstance(adapter, NullAdapter)

    def test_raises_on_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown telemetry provider"):
            create_metrics_provider(provider="unknown")

    def test_production_mode_rejects_console_adapter(self):
        """Production mode MUST reject dev-only adapters."""
        with pytest.raises(ValueError, match="DEV-ONLY"):
            create_metrics_provider(provider="console", production_mode=True)

    def test_production_mode_allows_otel_adapter(self):
        """Production mode allows production-ready adapters."""
        adapter = create_metrics_provider(provider="otel", production_mode=True)
        assert isinstance(adapter, OTelAdapter)

    def test_production_mode_allows_null_adapter(self):
        """Production mode allows null adapter (for testing)."""
        adapter = create_metrics_provider(provider="null", production_mode=True)
        assert isinstance(adapter, NullAdapter)

    def test_dev_mode_allows_console_adapter(self):
        """Dev mode (default) allows all adapters."""
        adapter = create_metrics_provider(provider="console", production_mode=False)
        assert isinstance(adapter, ConsoleAdapter)


class TestCreateEventProvider:
    """Tests for create_event_provider factory."""

    def test_creates_otel_adapter_by_default(self):
        adapter = create_event_provider()
        assert isinstance(adapter, OTelAdapter)

    def test_creates_console_adapter(self):
        adapter = create_event_provider(provider="console")
        assert isinstance(adapter, ConsoleAdapter)

    def test_creates_null_adapter(self):
        adapter = create_event_provider(provider="null")
        assert isinstance(adapter, NullAdapter)

    def test_production_mode_rejects_console_adapter(self):
        with pytest.raises(ValueError, match="DEV-ONLY"):
            create_event_provider(provider="console", production_mode=True)

    def test_production_mode_allows_otel_adapter(self):
        adapter = create_event_provider(provider="otel", production_mode=True)
        assert isinstance(adapter, OTelAdapter)


class TestCreateTelemetryProvider:
    """Tests for create_telemetry_provider factory."""

    def test_returns_tuple_of_same_adapter(self):
        metrics, events = create_telemetry_provider(provider="null")
        assert metrics is events  # Same instance
        assert isinstance(metrics, NullAdapter)

    def test_production_mode_rejects_console(self):
        with pytest.raises(ValueError, match="DEV-ONLY"):
            create_telemetry_provider(provider="console", production_mode=True)

    def test_production_mode_allows_otel(self):
        metrics, events = create_telemetry_provider(provider="otel", production_mode=True)
        assert isinstance(metrics, OTelAdapter)
        assert isinstance(events, OTelAdapter)
