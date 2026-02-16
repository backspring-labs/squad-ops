"""
FastAPI dependencies for Runtime API (SIP-0048, SIP-0062, SIP-0064).

Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/deps.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort
from squadops.ports.tasks.registry import TaskRegistryPort

if TYPE_CHECKING:
    from squadops.api.runtime.health_checker import HealthChecker

# Global adapter instances (initialized at startup)
_adapter: TaskRegistryPort | None = None
_auth_port: AuthPort | None = None
_authz_port: AuthorizationPort | None = None
_audit_port = None  # AuditPort | None
_health_checker: HealthChecker | None = None

# SIP-0064 cycle port singletons
_project_registry: ProjectRegistryPort | None = None
_cycle_registry: CycleRegistryPort | None = None
_squad_profile: SquadProfilePort | None = None
_artifact_vault: ArtifactVaultPort | None = None
_flow_executor: FlowExecutionPort | None = None


def set_tasks_adapter(adapter: TaskRegistryPort) -> None:
    """Set the tasks adapter instance for dependency injection."""
    global _adapter
    _adapter = adapter


def set_auth_ports(
    auth: AuthPort | None = None,
    authz: AuthorizationPort | None = None,
) -> None:
    """Set auth adapter instances for dependency injection (SIP-0062)."""
    global _auth_port, _authz_port
    _auth_port = auth
    _authz_port = authz


def set_audit_port(audit) -> None:
    """Set audit port instance (SIP-0062 Phase 3b)."""
    global _audit_port
    _audit_port = audit


def get_auth_port() -> AuthPort | None:
    """Return the current AuthPort instance, or None if not configured."""
    return _auth_port


def get_authz_port() -> AuthorizationPort | None:
    """Return the current AuthorizationPort instance, or None if not configured."""
    return _authz_port


def get_audit_port():
    """Return the current AuditPort instance, or None if not configured."""
    return _audit_port


async def get_tasks_adapter_dep() -> TaskRegistryPort:
    """
    FastAPI dependency function that returns the configured tasks adapter.

    Used via FastAPI Depends() in route handlers.

    Returns:
        TaskRegistryPort instance

    Raises:
        RuntimeError: If adapter not initialized
    """
    if _adapter is None:
        raise RuntimeError("Tasks adapter not initialized. Call set_tasks_adapter() at startup.")
    return _adapter


# =============================================================================
# SIP-0064 cycle port setters/getters
# =============================================================================


def set_cycle_ports(
    project_registry: ProjectRegistryPort | None = None,
    cycle_registry: CycleRegistryPort | None = None,
    squad_profile: SquadProfilePort | None = None,
    artifact_vault: ArtifactVaultPort | None = None,
    flow_executor: FlowExecutionPort | None = None,
) -> None:
    """Set SIP-0064 cycle port instances for dependency injection."""
    global _project_registry, _cycle_registry, _squad_profile, _artifact_vault, _flow_executor
    if project_registry is not None:
        _project_registry = project_registry
    if cycle_registry is not None:
        _cycle_registry = cycle_registry
    if squad_profile is not None:
        _squad_profile = squad_profile
    if artifact_vault is not None:
        _artifact_vault = artifact_vault
    if flow_executor is not None:
        _flow_executor = flow_executor


def get_project_registry() -> ProjectRegistryPort:
    """Return the ProjectRegistryPort (T14: never None at call sites)."""
    if _project_registry is None:
        raise RuntimeError("ProjectRegistryPort not configured")
    return _project_registry


def get_cycle_registry() -> CycleRegistryPort:
    """Return the CycleRegistryPort (T14: never None at call sites)."""
    if _cycle_registry is None:
        raise RuntimeError("CycleRegistryPort not configured")
    return _cycle_registry


def get_squad_profile_port() -> SquadProfilePort:
    """Return the SquadProfilePort (T14: never None at call sites)."""
    if _squad_profile is None:
        raise RuntimeError("SquadProfilePort not configured")
    return _squad_profile


def get_artifact_vault() -> ArtifactVaultPort:
    """Return the ArtifactVaultPort (T14: never None at call sites)."""
    if _artifact_vault is None:
        raise RuntimeError("ArtifactVaultPort not configured")
    return _artifact_vault


def get_flow_executor() -> FlowExecutionPort:
    """Return the FlowExecutionPort (T14: never None at call sites)."""
    if _flow_executor is None:
        raise RuntimeError("FlowExecutionPort not configured")
    return _flow_executor


# =============================================================================
# Health checker singleton
# =============================================================================


def set_health_checker(checker: HealthChecker) -> None:
    """Set the HealthChecker instance for dependency injection."""
    global _health_checker
    _health_checker = checker


def get_health_checker() -> HealthChecker:
    """Return the HealthChecker instance."""
    if _health_checker is None:
        raise RuntimeError("HealthChecker not configured")
    return _health_checker
