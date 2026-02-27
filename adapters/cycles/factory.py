"""
Adapter factory for SIP-0064 cycle execution ports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort

if TYPE_CHECKING:
    from squadops.orchestration.orchestrator import AgentOrchestrator


def create_project_registry(provider: str = "config", **kwargs) -> ProjectRegistryPort:
    """Create a ProjectRegistryPort adapter."""
    if provider == "config":
        from adapters.cycles.config_project_registry import ConfigProjectRegistry

        return ConfigProjectRegistry(**kwargs)
    raise ValueError(f"Unknown project registry provider: {provider}")


def create_cycle_registry(provider: str = "memory", **kwargs) -> CycleRegistryPort:
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


def create_squad_profile_port(provider: str = "config", **kwargs) -> SquadProfilePort:
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


def create_artifact_vault(provider: str = "filesystem", **kwargs) -> ArtifactVaultPort:
    """Create an ArtifactVaultPort adapter."""
    if provider == "filesystem":
        from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

        return FilesystemArtifactVault(**kwargs)
    raise ValueError(f"Unknown artifact vault provider: {provider}")


def create_flow_executor(
    provider: str = "in_process",
    *,
    cycle_registry: CycleRegistryPort | None = None,
    artifact_vault: ArtifactVaultPort | None = None,
    orchestrator: AgentOrchestrator | None = None,
    squad_profile: SquadProfilePort | None = None,
    project_registry: ProjectRegistryPort | None = None,
    **kwargs,
) -> FlowExecutionPort:
    """Create a FlowExecutionPort adapter.

    SIP-0066: Accepts injected dependencies for executor wiring.
    """
    if provider == "in_process":
        from adapters.cycles.in_process_flow_executor import InProcessFlowExecutor

        return InProcessFlowExecutor(
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            orchestrator=orchestrator,
            squad_profile=squad_profile,
            project_registry=project_registry,
        )
    elif provider == "distributed":
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        prefect_reporter = kwargs.get("prefect_reporter")
        if not prefect_reporter and kwargs.get("prefect_api_url"):
            from adapters.cycles.prefect_reporter import PrefectReporter

            prefect_reporter = PrefectReporter(api_url=kwargs["prefect_api_url"])

        return DistributedFlowExecutor(
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            queue=kwargs.get("queue"),
            squad_profile=squad_profile,
            project_registry=project_registry,
            task_timeout=kwargs.get("task_timeout", 300.0),
            llm_observability=kwargs.get("llm_observability"),
            prefect_reporter=prefect_reporter,
        )
    raise ValueError(f"Unknown flow executor provider: {provider}")
