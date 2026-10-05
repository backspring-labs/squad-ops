"""
Adapter factory for SIP-0064 cycle execution ports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.cycles.deploy_registry import DeployRegistryPort
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort

if TYPE_CHECKING:
    from adapters.cycles.reply_router import ReplyRouter
    from squadops.campaigns.launcher import BoxVerdict
    from squadops.campaigns.progress import CampaignProgress
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.ports.runtime.activity import RuntimeActivityPort
    from squadops.ports.runtime.assignments import AssignmentPort
    from squadops.ports.runtime.focus_lease import FocusLeasePort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
    from squadops.runtime.coordinator import RuntimeCoordinator


def create_project_registry(provider: str, **kwargs) -> ProjectRegistryPort:
    """Create a ProjectRegistryPort adapter."""
    if provider == "config":
        from adapters.cycles.config_project_registry import ConfigProjectRegistry

        return ConfigProjectRegistry(**kwargs)
    raise ValueError(f"Unknown project registry provider: {provider}")


def create_cycle_registry(provider: str, **kwargs) -> CycleRegistryPort:
    """Create a CycleRegistryPort adapter."""
    if provider == "memory":
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

        return MemoryCycleRegistry()
    elif provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for postgres cycle registry provider")
        from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry

        return PostgresCycleRegistry(pool=pool)
    raise ValueError(f"Unknown cycle registry provider: {provider}")


def create_deploy_registry(provider: str, **kwargs) -> DeployRegistryPort:
    """Create a DeployRegistryPort adapter (#1720). The same store as the cycle registry, so the
    same selector (``cycles.registry_provider``) chooses it."""
    if provider == "memory":
        from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry

        return MemoryDeployRegistry()
    elif provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for postgres deploy registry provider")
        from adapters.cycles.postgres_deploy_registry import PostgresDeployRegistry

        return PostgresDeployRegistry(pool=pool)
    raise ValueError(f"Unknown deploy registry provider: {provider}")


def create_campaign_registry(provider: str, **kwargs) -> CampaignRegistryPort:
    """Create a CampaignRegistryPort adapter (SIP-0109 §16). The campaigns live beside the
    cycles they launch, so the cycle registry's selector (``cycles.registry_provider``) chooses
    it."""
    if provider == "memory":
        from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry

        return MemoryCampaignRegistry()
    elif provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for postgres campaign registry provider")
        from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry

        return PostgresCampaignRegistry(pool=pool)
    raise ValueError(f"Unknown campaign registry provider: {provider}")


def create_squad_profile_port(provider: str, **kwargs) -> SquadProfilePort:
    """Create a SquadProfilePort adapter (T7: consistent naming)."""
    if provider == "config":
        from adapters.cycles.config_squad_profile import ConfigSquadProfile

        return ConfigSquadProfile(**kwargs)
    elif provider == "postgres":
        pool = kwargs.get("pool")
        if pool is None:
            raise ValueError("pool is required for postgres squad profile provider")
        from adapters.cycles.postgres_squad_profile import PostgresSquadProfile

        return PostgresSquadProfile(pool=pool)
    raise ValueError(f"Unknown squad profile provider: {provider}")


def create_artifact_vault(provider: str, **kwargs) -> ArtifactVaultPort:
    """Create an ArtifactVaultPort adapter."""
    if provider == "filesystem":
        from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

        return FilesystemArtifactVault(**kwargs)
    raise ValueError(f"Unknown artifact vault provider: {provider}")


def create_flow_executor(
    provider: str,
    *,
    cycle_registry: CycleRegistryPort | None,
    artifact_vault: ArtifactVaultPort | None,
    queue: QueuePort | None,
    squad_profile: SquadProfilePort | None,
    project_registry: ProjectRegistryPort | None,
    campaign_registry: CampaignRegistryPort | None,
    campaign_progress: CampaignProgress | None,
    box_verdict: BoxVerdict | None,
    task_timeout: float,
    llm_observability: LLMObservabilityPort | None = None,
    workflow_tracker: WorkflowTrackerPort | None = None,
    prefect_api_url: str | None = None,
    event_bus: CycleEventBusPort | None = None,
    reply_router: ReplyRouter | None = None,
    assignment_port: AssignmentPort | None = None,
    activity_port: RuntimeActivityPort | None = None,
    coordinator: RuntimeCoordinator | None = None,
    focus_lease_port: FocusLeasePort | None = None,
) -> FlowExecutionPort:
    """Create a FlowExecutionPort adapter.

    SIP-0066: Accepts injected dependencies for executor wiring. ``"dispatched"`` is the one
    provider: the in-process executor no root ever selected was deleted (#1984).

    #1987: every keyword is named and typed. The executor's dependencies passed through
    ``**kwargs`` as ``kwargs.get(...)``, so a misspelled keyword at the composition root was
    dropped unread and the dependency became ``None``: for ``box_verdict``, a run that starts
    with no box read. An unknown keyword is now a ``TypeError`` at boot, and the dependencies
    the executor cannot be built without have no default (the 2026-09-14 ruling: require,
    don't default, at the seams). The collaborators the executor builds for itself
    (``run_completion``, ``correction_runner`` …) are test injection points on its
    constructor, never wired here.
    """
    if provider != "dispatched":
        raise ValueError(f"Unknown flow executor provider: {provider}")

    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    if not workflow_tracker and prefect_api_url:
        # Route through the shared factory so the NoOp-fallback and init
        # logging apply here too (instead of inline-building the adapter and
        # raising on construction failure). Only build when a Prefect URL is
        # configured — when it isn't, workflow_tracker stays None, unchanged.
        from adapters.cycles.workflow_tracker_factory import create_workflow_tracker
        from squadops.config.schema import PrefectConfig

        workflow_tracker = create_workflow_tracker(PrefectConfig(api_url=prefect_api_url))

    return DispatchedFlowExecutor(
        cycle_registry=cycle_registry,
        artifact_vault=artifact_vault,
        queue=queue,
        squad_profile=squad_profile,
        project_registry=project_registry,
        campaign_registry=campaign_registry,
        campaign_progress=campaign_progress,
        box_verdict=box_verdict,
        task_timeout=task_timeout,
        llm_observability=llm_observability,
        workflow_tracker=workflow_tracker,
        event_bus=event_bus,
        reply_router=reply_router,
        assignment_port=assignment_port,
        activity_port=activity_port,
        coordinator=coordinator,
        focus_lease_port=focus_lease_port,
    )
