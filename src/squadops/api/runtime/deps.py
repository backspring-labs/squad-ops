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
from squadops.ports.events.cycle_event_bus import CycleEventBusPort
from squadops.ports.llm.provider import LLMPort

if TYPE_CHECKING:
    from squadops.api.runtime.health_checker import HealthChecker

# Global adapter instances (initialized at startup)
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

# SIP-0077: Cycle event bus
_cycle_event_bus: CycleEventBusPort | None = None
_cycle_event_bus_warned: bool = False

# SIP-0075: LLM port for model management endpoints
_llm_port: LLMPort | None = None


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


# =============================================================================
# SIP-0077: Cycle event bus
# =============================================================================


def set_cycle_event_bus(bus: CycleEventBusPort) -> None:
    """Set the cycle event bus instance (SIP-0077)."""
    global _cycle_event_bus
    _cycle_event_bus = bus


def get_cycle_event_bus() -> CycleEventBusPort:
    """Return the CycleEventBusPort instance.

    Unlike other port getters, this returns NoOpCycleEventBus instead of
    raising RuntimeError — event emission is best-effort, routes should
    never fail because the bus is unconfigured. Logs a warning once per
    process when falling back to NoOp.
    """
    global _cycle_event_bus_warned
    if _cycle_event_bus is not None:
        return _cycle_event_bus

    if not _cycle_event_bus_warned:
        import logging

        logging.getLogger(__name__).warning(
            "CycleEventBusPort not configured — using NoOpCycleEventBus. "
            "Canonical event publication is disabled/degraded."
        )
        _cycle_event_bus_warned = True

    from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus

    return NoOpCycleEventBus()


# =============================================================================
# SIP-0075: LLM port for model management
# =============================================================================


def set_llm_port(llm: LLMPort) -> None:
    """Set the LLM port instance (SIP-0075: model management endpoints)."""
    global _llm_port
    _llm_port = llm


def get_llm_port() -> LLMPort:
    """Return the LLMPort instance."""
    if _llm_port is None:
        raise RuntimeError("LLMPort not configured")
    return _llm_port


# =============================================================================
# SIP-0085: Chat ports
# =============================================================================


def set_chat_ports(
    *,
    chat_repo: object | None = None,
    chat_cache: object | None = None,
    a2a_client: object | None = None,
    all_agents: dict | None = None,
    messaging_agents: dict | None = None,
) -> None:
    """Set SIP-0085 chat port instances for dependency injection."""
    from squadops.api.routes.chat import routes as chat_routes

    if chat_repo is not None:
        chat_routes._chat_repo = chat_repo
    if chat_cache is not None:
        chat_routes._chat_cache = chat_cache
    if a2a_client is not None:
        chat_routes._a2a_client = a2a_client
    if all_agents is not None:
        chat_routes._all_agents = all_agents
    if messaging_agents is not None:
        chat_routes._messaging_agents = messaging_agents
