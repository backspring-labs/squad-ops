"""Unit tests for telemetry factory."""

from unittest.mock import MagicMock

import pytest

from adapters.telemetry.console import ConsoleAdapter
from adapters.telemetry.factory import (
    create_event_provider,
    create_llm_observability_provider,
    create_metrics_provider,
    create_telemetry_provider,
)
from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter
from adapters.telemetry.null import NullAdapter
from adapters.telemetry.otel import OTelAdapter
from squadops.config.schema import LangFuseConfig
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort


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


class TestCreateLlmObservabilityProvider:
    """Tests for create_llm_observability_provider factory (SIP-0061)."""

    def test_returns_noop_when_config_none(self):
        adapter = create_llm_observability_provider(config=None)
        assert isinstance(adapter, NoOpLLMObservabilityAdapter)

    def test_returns_noop_when_disabled(self):
        config = LangFuseConfig(enabled=False)
        adapter = create_llm_observability_provider(config=config)
        assert isinstance(adapter, NoOpLLMObservabilityAdapter)

    def test_noop_health_ok_when_disabled(self):
        import asyncio

        adapter = create_llm_observability_provider(config=None)
        result = asyncio.get_event_loop().run_until_complete(adapter.health())
        assert result["status"] == "ok"

    def test_returns_langfuse_adapter_when_enabled(self):
        """When SDK is available, factory returns LangFuseAdapter."""
        import sys
        import types

        config = LangFuseConfig(
            enabled=True,
            host="http://localhost:3000",
            public_key="pk-test",
            secret_key="sk-test",
        )
        # Inject a fake langfuse module so the lazy import succeeds
        fake_langfuse = types.ModuleType("langfuse")
        fake_langfuse.Langfuse = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
        old = sys.modules.get("langfuse")
        sys.modules["langfuse"] = fake_langfuse
        # Clear any cached import of the adapter module so it re-imports
        sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
        try:
            adapter = create_llm_observability_provider(config=config)
            assert isinstance(adapter, LLMObservabilityPort)
            assert not isinstance(adapter, NoOpLLMObservabilityAdapter)
            # Cleanup
            adapter._shutdown.set()
            adapter._flush_requested.set()
            adapter._flush_thread.join(timeout=2)
        finally:
            if old is None:
                sys.modules.pop("langfuse", None)
            else:
                sys.modules["langfuse"] = old
            sys.modules.pop("adapters.telemetry.langfuse.adapter", None)

    def test_returns_degraded_noop_when_sdk_missing(self):
        """When SDK is missing, factory returns degraded NoOp adapter."""
        import asyncio
        import sys

        config = LangFuseConfig(
            enabled=True,
            host="http://localhost:3000",
            public_key="pk-test",
            secret_key="sk-test",
        )
        # Ensure langfuse module is NOT available
        old_langfuse = sys.modules.pop("langfuse", None)
        old_adapter = sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
        try:
            # Block the import by inserting None (forces ImportError)
            sys.modules["langfuse"] = None  # type: ignore[assignment]
            sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
            adapter = create_llm_observability_provider(config=config)
            assert isinstance(adapter, NoOpLLMObservabilityAdapter)
            result = asyncio.get_event_loop().run_until_complete(adapter.health())
            assert result["status"] == "degraded"
            assert "SDK not installed" in result["details"]["reason"]
        finally:
            sys.modules.pop("langfuse", None)
            sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
            if old_langfuse is not None:
                sys.modules["langfuse"] = old_langfuse
            if old_adapter is not None:
                sys.modules["adapters.telemetry.langfuse.adapter"] = old_adapter

    def test_raises_on_unknown_provider(self):
        config = LangFuseConfig(enabled=True, public_key="pk", secret_key="sk")
        with pytest.raises(ValueError, match="Unknown LLM observability provider"):
            create_llm_observability_provider(provider="unknown", config=config)

    def test_resolves_secrets(self):
        """Factory resolves secret:// references via secret_manager."""
        import sys
        import types

        config = LangFuseConfig(
            enabled=True,
            public_key="secret://LANGFUSE_PK",
            secret_key="secret://LANGFUSE_SK",
        )
        mock_sm = MagicMock()
        mock_sm.resolve.side_effect = lambda v: v.replace(
            "secret://LANGFUSE_PK", "resolved-pk"
        ).replace("secret://LANGFUSE_SK", "resolved-sk")

        # Inject fake langfuse module
        fake_langfuse = types.ModuleType("langfuse")
        fake_langfuse.Langfuse = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
        old = sys.modules.get("langfuse")
        sys.modules["langfuse"] = fake_langfuse
        sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
        try:
            adapter = create_llm_observability_provider(config=config, secret_manager=mock_sm)
            assert mock_sm.resolve.call_count == 2
            # Cleanup
            adapter._shutdown.set()
            adapter._flush_requested.set()
            adapter._flush_thread.join(timeout=2)
        finally:
            if old is None:
                sys.modules.pop("langfuse", None)
            else:
                sys.modules["langfuse"] = old
            sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
