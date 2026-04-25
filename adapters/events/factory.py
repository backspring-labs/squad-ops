"""Factory for CycleEventBusPort adapter selection.

Follows the create_cycle_registry() / create_llm_observability_provider()
pattern with lazy imports inside each branch.

The factory also handles bridge wiring: when ``llm_observability`` and/or
``workflow_tracker`` ports are passed, the corresponding subscriber bridges
are subscribed automatically. Composition roots (runtime-api, agent
entrypoints) hand the factory their ports and never import bridge classes
by name — that keeps vendor-themed bridge symbols out of core wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.ports.events.cycle_event_bus import CycleEventBusPort

if TYPE_CHECKING:
    from squadops.ports.cycles import WorkflowTrackerPort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort


def create_cycle_event_bus(
    provider: str = "in_process",
    *,
    llm_observability: LLMObservabilityPort | None = None,
    workflow_tracker: WorkflowTrackerPort | None = None,
    **kwargs,
) -> CycleEventBusPort:
    """Select a :class:`CycleEventBusPort` and subscribe standard bridges.

    Args:
        provider: ``"in_process"`` (default) or ``"noop"``.
        llm_observability: When provided, an ``LLMObservabilityBridge`` is
            subscribed so cycle events flow into the LLM-observability port
            (LangFuse / NoOp / etc.).
        workflow_tracker: When provided, a ``WorkflowTrackerBridge`` is
            subscribed so run/task lifecycle events drive the workflow
            tracker port (Prefect / NoOp / etc.).
        **kwargs: Passed to the adapter constructor. ``in_process`` requires
            ``source_service`` and ``source_version``.
    """
    if provider == "in_process":
        from adapters.events.in_process_cycle_event_bus import InProcessCycleEventBus

        bus: CycleEventBusPort = InProcessCycleEventBus(
            source_service=kwargs.get("source_service", "unknown"),
            source_version=kwargs.get("source_version", "0.0.0"),
        )
    elif provider == "noop":
        from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus

        bus = NoOpCycleEventBus()
    else:
        raise ValueError(f"Unknown cycle event bus provider: {provider}")

    if llm_observability is not None:
        from squadops.events.bridges import LLMObservabilityBridge

        bus.subscribe(LLMObservabilityBridge(llm_observability))
    if workflow_tracker is not None:
        from squadops.events.bridges import WorkflowTrackerBridge

        bus.subscribe(WorkflowTrackerBridge(workflow_tracker))

    return bus
