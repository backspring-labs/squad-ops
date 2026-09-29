"""
FastAPI dependencies for Runtime API (SIP-0048, SIP-0062, SIP-0064).

#1448: every port the routes read lives on the app that owns it — ``app.state``, beside the
connections #286 moved there — and each getter here is a FastAPI dependency provider over the
request's app. There is no process-wide registry: two runtime apps in one process each resolve
their own ports (``docs/architecture/composition-roots.md`` R4). The composition root assigns the
slots (``squadops/api/runtime/main.py``); ``create_app`` starts every slot at ``None``, so an
unwired port reads as unconfigured exactly as it did before.

Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/deps.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import Request

from squadops import __version__ as SQUADOPS_VERSION
from squadops._version import resolve_git_sha
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleAssessment
from squadops.ports.auth.authentication import AuthPort
from squadops.ports.auth.authorization import AuthorizationPort
from squadops.ports.comms.queue import QueuePort
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.ports.cycles.squad_profile import SquadProfilePort
from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
from squadops.ports.events.cycle_event_bus import CycleEventBusPort
from squadops.ports.llm.provider import LLMPort
from squadops.ports.runtime.assignments import AssignmentPort

if TYPE_CHECKING:
    from squadops.api.runtime.health_checker import HealthChecker
    from squadops.ports.runtime.activity import RuntimeActivityPort
    from squadops.ports.runtime.focus_lease import FocusLeasePort
    from squadops.runtime.coordinator import RuntimeCoordinator

logger = logging.getLogger(__name__)

#: The ports the routes read, one ``app.state`` slot each. ``create_app`` starts them at ``None``
#: and the composition root assigns them; the getters below are the only readers.
PORT_SLOTS = (
    "auth_port",  # SIP-0062
    "authz_port",
    "audit_port",  # SIP-0062 Phase 3b
    "project_registry",  # SIP-0064
    "cycle_registry",
    "squad_profile",
    "artifact_vault",
    "flow_executor",
    "cycle_event_bus",  # SIP-0077 — best-effort: read as a no-op when unwired
    "llm_port",  # SIP-0075
    "assignment_port",  # SIP-0089 §2.7
    # #373/#529/#561: what a cancel tears down (it bypasses the executor's finalize path);
    # all None without a Postgres pool. The coordinator is the root's single instance (D16).
    "focus_lease_port",
    "activity_port",
    "cancel_queue_port",  # #1648
    # SIP-0085 chat
    "chat_repo",
    "chat_cache",
    "a2a_client",
    "all_agents",
    "messaging_agents",
)
#: Slots #286 already declared for connections and processes, read here too: the health checker,
#: the workflow tracker and the runtime coordinator (``main._STATE_SLOTS``).


def _slot(request: Request, name: str) -> Any:
    return getattr(request.app.state, name, None)


def get_auth_port(request: Request) -> AuthPort | None:
    """Return the app's AuthPort, or None if not configured."""
    return _slot(request, "auth_port")


def get_authz_port(request: Request) -> AuthorizationPort | None:
    """Return the app's AuthorizationPort, or None if not configured."""
    return _slot(request, "authz_port")


def get_audit_port(request: Request):
    """Return the app's AuditPort, or None if not configured."""
    return _slot(request, "audit_port")


# =============================================================================
# SIP-0064 cycle ports
# =============================================================================


def _required(request: Request, name: str, port: str) -> Any:
    value = _slot(request, name)
    if value is None:
        raise RuntimeError(f"{port} not configured")
    return value


def get_project_registry(request: Request) -> ProjectRegistryPort:
    """Return the ProjectRegistryPort (T14: never None at call sites)."""
    return _required(request, "project_registry", "ProjectRegistryPort")


def get_cycle_registry(request: Request) -> CycleRegistryPort:
    """Return the CycleRegistryPort (T14: never None at call sites)."""
    return _required(request, "cycle_registry", "CycleRegistryPort")


def get_squad_profile_port(request: Request) -> SquadProfilePort:
    """Return the SquadProfilePort (T14: never None at call sites)."""
    return _required(request, "squad_profile", "SquadProfilePort")


def get_artifact_vault(request: Request) -> ArtifactVaultPort:
    """Return the ArtifactVaultPort (T14: never None at call sites)."""
    return _required(request, "artifact_vault", "ArtifactVaultPort")


async def assess_cycle_from_stores(request: Request, cycle_id: str) -> CycleAssessment:
    """Compute a cycle's assessment from the app's registry and vault (SIP-0108 §4.1 (a)).

    Composed here because assembling the evidence is an adapter concern and only a
    composition root may import one (#154). The projection itself is pure and lives in
    ``squadops.cycles.cycle_assessment``; nothing is stored, and the assessor identity is
    this deploy's, the same pair a cycle records at creation (#80).
    """
    from adapters.cycles.cycle_evidence import assess_cycle

    return await assess_cycle(
        get_cycle_registry(request),
        get_artifact_vault(request),
        cycle_id,
        assessor=AssessorIdentity(framework_version=SQUADOPS_VERSION, git_sha=resolve_git_sha()),
    )


def get_flow_executor(request: Request) -> FlowExecutionPort:
    """Return the FlowExecutionPort (T14: never None at call sites)."""
    return _required(request, "flow_executor", "FlowExecutionPort")


# =============================================================================
# Health checker
# =============================================================================


def get_health_checker(request: Request) -> HealthChecker:
    """Return the app's HealthChecker."""
    return _required(request, "health_checker", "HealthChecker")


# =============================================================================
# SIP-0077: Cycle event bus; #77: workflow tracker — both best-effort
# =============================================================================


def _warn_once(request: Request, flag: str, message: str) -> None:
    state = request.app.state
    if not getattr(state, flag, False):
        logger.warning(message)
        setattr(state, flag, True)


def get_cycle_event_bus(request: Request) -> CycleEventBusPort:
    """Return the app's CycleEventBusPort.

    Unlike other port getters, this returns NoOpCycleEventBus instead of
    raising RuntimeError — event emission is best-effort, routes should
    never fail because the bus is unconfigured. Logs a warning once per
    app when falling back to NoOp.
    """
    bus = _slot(request, "cycle_event_bus")
    if bus is not None:
        return bus
    _warn_once(
        request,
        "cycle_event_bus_warned",
        "CycleEventBusPort not configured — using NoOpCycleEventBus. "
        "Canonical event publication is disabled/degraded.",
    )
    from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus

    return NoOpCycleEventBus()


def get_workflow_tracker(request: Request) -> WorkflowTrackerPort:
    """Return the app's WorkflowTrackerPort (#77: used by cancel routes to stop orphaned runs).

    Best-effort like the event bus: returns NoOpWorkflowTracker instead of
    raising when unconfigured, so cancel routes never fail because workflow
    tracking is off. Warns once per app on fallback.
    """
    tracker = _slot(request, "workflow_tracker")
    if tracker is not None:
        return tracker
    _warn_once(
        request,
        "workflow_tracker_warned",
        "WorkflowTrackerPort not configured — using NoOpWorkflowTracker. "
        "Cancellations will not propagate to Prefect.",
    )
    from adapters.cycles.noop_workflow_tracker import NoOpWorkflowTracker

    return NoOpWorkflowTracker()


# =============================================================================
# SIP-0075: LLM port for model management
# =============================================================================


def get_llm_port(request: Request) -> LLMPort:
    """Return the app's LLMPort."""
    return _required(request, "llm_port", "LLMPort")


# =============================================================================
# SIP-0089 §2.7: Assignment port
# =============================================================================


def get_assignment_port(request: Request) -> AssignmentPort:
    """Return the app's AssignmentPort.

    Raises RuntimeError if unconfigured — assignments require a Postgres pool,
    so a missing port at a route call site is a wiring error, not a no-op.
    """
    return _required(request, "assignment_port", "AssignmentPort")


# =============================================================================
# #373/#529/#561: runtime ports the cancel path tears down
# =============================================================================


def get_runtime_coordinator(request: Request) -> RuntimeCoordinator | None:
    """Return the shared coordinator, or None when no Postgres pool is wired."""
    return _slot(request, "runtime_coordinator")


def get_focus_lease_port(request: Request) -> FocusLeasePort | None:
    """Return the focus-lease port, or None when no Postgres pool is wired.

    Unlike :func:`get_assignment_port` this never raises: cancellation must
    succeed on a pool-less deployment, where there are no leases to release.
    """
    return _slot(request, "focus_lease_port")


def get_cancel_queue_port(request: Request) -> QueuePort | None:
    """Return the queue a cancel's notice goes out on, or None when none is wired (#1648)."""
    return _slot(request, "cancel_queue_port")


def get_activity_port(request: Request) -> RuntimeActivityPort | None:
    """Return the activity port, or None when no Postgres pool is wired.

    Never raises, for the same reason as :func:`get_focus_lease_port`.
    """
    return _slot(request, "activity_port")
