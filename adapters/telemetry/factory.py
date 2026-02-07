"""Telemetry adapter factory.

Factory functions for creating telemetry adapters with production mode guards.
Part of SIP-0.8.7 Infrastructure Ports Migration.
Extended with LLM observability factory (SIP-0061).
"""
import logging
from typing import TextIO

from adapters.telemetry.console import ConsoleAdapter
from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter
from adapters.telemetry.null import NullAdapter
from adapters.telemetry.otel import OTelAdapter
from squadops.config.schema import LangFuseConfig
from squadops.core.secrets import SecretManager
from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
from squadops.ports.telemetry.metrics import MetricsPort

logger = logging.getLogger(__name__)

# Dev-only adapters that cannot be used in production mode
DEV_ONLY_ADAPTERS = {"console"}


def create_metrics_provider(
    provider: str = "otel",
    production_mode: bool = False,
    output: TextIO | None = None,
) -> MetricsPort:
    """Create a metrics provider.

    Args:
        provider: Provider name ("otel", "console", "null")
        production_mode: If True, rejects dev-only adapters
        output: Output stream for console adapter (testing)

    Returns:
        MetricsPort implementation

    Raises:
        ValueError: If provider is unknown or dev-only in production mode
    """
    if production_mode and provider in DEV_ONLY_ADAPTERS:
        raise ValueError(
            f"Adapter '{provider}' is DEV-ONLY and cannot be used in production mode. "
            f"Use 'otel' or 'null' instead."
        )

    if provider == "otel":
        return OTelAdapter()
    if provider == "console":
        return ConsoleAdapter(output=output)
    if provider == "null":
        return NullAdapter()

    raise ValueError(f"Unknown telemetry provider: {provider}")


def create_event_provider(
    provider: str = "otel",
    production_mode: bool = False,
    output: TextIO | None = None,
) -> EventPort:
    """Create an event provider.

    Args:
        provider: Provider name ("otel", "console", "null")
        production_mode: If True, rejects dev-only adapters
        output: Output stream for console adapter (testing)

    Returns:
        EventPort implementation

    Raises:
        ValueError: If provider is unknown or dev-only in production mode
    """
    if production_mode and provider in DEV_ONLY_ADAPTERS:
        raise ValueError(
            f"Adapter '{provider}' is DEV-ONLY and cannot be used in production mode. "
            f"Use 'otel' or 'null' instead."
        )

    if provider == "otel":
        return OTelAdapter()
    if provider == "console":
        return ConsoleAdapter(output=output)
    if provider == "null":
        return NullAdapter()

    raise ValueError(f"Unknown telemetry provider: {provider}")


def create_telemetry_provider(
    provider: str = "otel",
    production_mode: bool = False,
    output: TextIO | None = None,
) -> tuple[MetricsPort, EventPort]:
    """Create both metrics and event providers.

    Convenience function that returns a single adapter implementing both ports.

    Args:
        provider: Provider name ("otel", "console", "null")
        production_mode: If True, rejects dev-only adapters
        output: Output stream for console adapter (testing)

    Returns:
        Tuple of (MetricsPort, EventPort) - typically the same adapter instance

    Raises:
        ValueError: If provider is unknown or dev-only in production mode
    """
    if production_mode and provider in DEV_ONLY_ADAPTERS:
        raise ValueError(
            f"Adapter '{provider}' is DEV-ONLY and cannot be used in production mode. "
            f"Use 'otel' or 'null' instead."
        )

    if provider == "otel":
        adapter = OTelAdapter()
        return adapter, adapter
    if provider == "console":
        adapter = ConsoleAdapter(output=output)
        return adapter, adapter
    if provider == "null":
        adapter = NullAdapter()
        return adapter, adapter

    raise ValueError(f"Unknown telemetry provider: {provider}")


def create_llm_observability_provider(
    provider: str = "langfuse",
    config: LangFuseConfig | None = None,
    secret_manager: SecretManager | None = None,
) -> LLMObservabilityPort:
    """Create LLM observability provider (SIP-0061).

    Returns NoOpLLMObservabilityAdapter when config is None or config.enabled is False.
    When config.enabled is True but the langfuse SDK is missing, returns a degraded
    NoOp adapter and logs a warning rather than crashing.

    Args:
        provider: Provider name (currently only "langfuse")
        config: LangFuseConfig from AppConfig
        secret_manager: For resolving secret:// references in config

    Returns:
        LLMObservabilityPort implementation
    """
    if config is None or not config.enabled:
        return NoOpLLMObservabilityAdapter()

    if provider == "langfuse":
        try:
            from adapters.telemetry.langfuse.adapter import LangFuseAdapter

            resolved_config = _resolve_secrets(config, secret_manager)
            return LangFuseAdapter(resolved_config)
        except ImportError:
            logger.warning(
                "langfuse SDK not installed; falling back to NoOp adapter. "
                "Install with: pip install 'squadops[langfuse]'"
            )
            return NoOpLLMObservabilityAdapter(
                health_status="degraded",
                health_reason="langfuse SDK not installed",
            )

    raise ValueError(f"Unknown LLM observability provider: {provider}")


def _resolve_secrets(config: LangFuseConfig, secret_manager: SecretManager | None) -> LangFuseConfig:
    """Resolve secret:// references in LangFuseConfig fields.

    Returns a new LangFuseConfig with resolved values. If no secret_manager
    is provided, returns the config unchanged (secret:// references remain).
    """
    if secret_manager is None:
        return config

    return config.model_copy(
        update={
            "public_key": secret_manager.resolve(config.public_key),
            "secret_key": secret_manager.resolve(config.secret_key),
        }
    )
