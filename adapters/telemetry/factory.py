"""Telemetry adapter factory.

Factory functions for creating telemetry adapters with production mode guards.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from typing import TextIO

from adapters.telemetry.console import ConsoleAdapter
from adapters.telemetry.null import NullAdapter
from adapters.telemetry.otel import OTelAdapter
from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort

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
