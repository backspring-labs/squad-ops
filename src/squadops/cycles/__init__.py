"""
Cycle execution domain (SIP-0064).

Domain models, enums, exceptions, and lifecycle logic for Projects, Cycles,
Runs, Squad Profiles, Task Flow Policy, and Artifact Vault integration.
"""

from squadops.cycles.lifecycle import (
    GATE_REJECTED_STATES,
    compute_config_hash,
    compute_profile_snapshot_hash,
    derive_cycle_status,
    resolve_cycle_status,
    validate_run_transition,
)
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactNotFoundError,
    ArtifactRef,
    ArtifactType,
    BaselineNotAllowedError,
    BuildStrategy,
    Cycle,
    CycleError,
    CycleNotFoundError,
    CycleStatus,
    FlowMode,
    Gate,
    GateAlreadyDecidedError,
    GateDecision,
    GateDecisionValue,
    IllegalStateTransitionError,
    Project,
    ProjectNotFoundError,
    Run,
    RunInitiator,
    RunNotFoundError,
    RunStatus,
    RunTerminalError,
    SquadProfile,
    TaskFlowPolicy,
    ValidationError,
)

__all__ = [
    # Enums
    "CycleStatus",
    "RunStatus",
    "FlowMode",
    "BuildStrategy",
    "GateDecisionValue",
    # Constants
    "ArtifactType",
    "RunInitiator",
    # Exceptions
    "CycleError",
    "CycleNotFoundError",
    "RunNotFoundError",
    "IllegalStateTransitionError",
    "GateAlreadyDecidedError",
    "RunTerminalError",
    "ProjectNotFoundError",
    "ArtifactNotFoundError",
    "BaselineNotAllowedError",
    "ValidationError",
    # Domain models
    "Project",
    "Gate",
    "TaskFlowPolicy",
    "GateDecision",
    "Cycle",
    "Run",
    "ArtifactRef",
    "AgentProfileEntry",
    "SquadProfile",
    # Lifecycle
    "validate_run_transition",
    "derive_cycle_status",
    "resolve_cycle_status",
    "compute_config_hash",
    "compute_profile_snapshot_hash",
    # Lifecycle constants
    "GATE_REJECTED_STATES",
]
