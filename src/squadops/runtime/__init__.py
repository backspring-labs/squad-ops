"""
Agent runtime state — SIP-0089.

Pure coordination layer for `RuntimeMode`, `RuntimeActivity`, `FocusLease`,
`Assignment`, and `DutyWindow`. Depends on `squadops.ports.*`; never on
`adapters.*` (D1, enforced by `tests/unit/architecture/test_forbidden_imports.py`
per D26).
"""

from squadops.runtime.coordinator import (
    RequesterKind,
    RuntimeCoordinator,
    TransitionOutcome,
)
from squadops.runtime.models import (
    ActivitySourceKind,
    ActivityState,
    AgentRuntimeState,
    Assignment,
    AssignmentType,
    DutyWindow,
    FocusLease,
    LeaseDecision,
    LeaseGranted,
    LeasePreempting,
    LeaseRejected,
    MissedWindowPolicy,
    OwnerType,
    RecallPolicy,
    RenewalPolicy,
    RuntimeActivity,
    Strictness,
    WindowState,
    is_active_activity_state,
    is_terminal_activity_state,
    owner_type_outranks,
    window_state,
)
from squadops.runtime.recruitment import RecruitmentDecision, reserve_buffer_decision
from squadops.runtime.scheduler import DutyScheduler

__all__ = [
    "ActivitySourceKind",
    "ActivityState",
    "AgentRuntimeState",
    "Assignment",
    "AssignmentType",
    "DutyScheduler",
    "DutyWindow",
    "FocusLease",
    "LeaseDecision",
    "LeaseGranted",
    "LeasePreempting",
    "LeaseRejected",
    "MissedWindowPolicy",
    "OwnerType",
    "RecallPolicy",
    "RecruitmentDecision",
    "RenewalPolicy",
    "RequesterKind",
    "RuntimeActivity",
    "RuntimeCoordinator",
    "Strictness",
    "TransitionOutcome",
    "WindowState",
    "is_active_activity_state",
    "is_terminal_activity_state",
    "owner_type_outranks",
    "reserve_buffer_decision",
    "window_state",
]
