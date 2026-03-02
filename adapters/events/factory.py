"""Factory for CycleEventBusPort adapter selection.

Follows the create_cycle_registry() / create_llm_observability_provider()
pattern with lazy imports inside each branch.
"""

from __future__ import annotations

from squadops.ports.events.cycle_event_bus import CycleEventBusPort


def create_cycle_event_bus(provider: str = "in_process", **kwargs) -> CycleEventBusPort:
    """Select the configured CycleEventBusPort adapter implementation.

    Args:
        provider: ``"in_process"`` (default) or ``"noop"``.
        **kwargs: Passed to the adapter constructor. ``in_process`` requires
            ``source_service`` and ``source_version``.
    """
    if provider == "in_process":
        from adapters.events.in_process_cycle_event_bus import InProcessCycleEventBus

        return InProcessCycleEventBus(
            source_service=kwargs.get("source_service", "unknown"),
            source_version=kwargs.get("source_version", "0.0.0"),
        )
    elif provider == "noop":
        from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus

        return NoOpCycleEventBus()

    raise ValueError(f"Unknown cycle event bus provider: {provider}")
