"""
Adapter factory for SIP-0064 cycle execution ports.
"""

from __future__ import annotations

from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort


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

        return MemoryCycleRegistry(**kwargs)
    raise ValueError(f"Unknown cycle registry provider: {provider}")


def create_squad_profile_port(provider: str = "config", **kwargs) -> SquadProfilePort:
    """Create a SquadProfilePort adapter (T7: consistent naming)."""
    if provider == "config":
        from adapters.cycles.config_squad_profile import ConfigSquadProfile

        return ConfigSquadProfile(**kwargs)
    raise ValueError(f"Unknown squad profile provider: {provider}")


def create_artifact_vault(provider: str = "filesystem", **kwargs) -> ArtifactVaultPort:
    """Create an ArtifactVaultPort adapter."""
    if provider == "filesystem":
        from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

        return FilesystemArtifactVault(**kwargs)
    raise ValueError(f"Unknown artifact vault provider: {provider}")


def create_flow_executor(provider: str = "in_process", **kwargs) -> FlowExecutionPort:
    """Create a FlowExecutionPort adapter."""
    if provider == "in_process":
        from adapters.cycles.in_process_flow_executor import InProcessFlowExecutor

        return InProcessFlowExecutor(**kwargs)
    raise ValueError(f"Unknown flow executor provider: {provider}")
