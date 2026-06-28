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
    Strictness,
    WindowState,
    owner_type_outranks,
    window_state,
)
from squadops.runtime.recruitment import RecruitmentDecision, reserve_buffer_decision
from squadops.runtime.scheduler import DutyScheduler

__all__ = [
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
    "RuntimeCoordinator",
    "Strictness",
    "TransitionOutcome",
    "WindowState",
    "owner_type_outranks",
    "reserve_buffer_decision",
    "window_state",
]
