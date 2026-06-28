"""
Canonical runtime-state event names (SIP-0089, D14, D18).

Events describe **what happened**. Reasons (in `reasons.py`) describe **why**.
The two vocabularies are deliberately separate — see D18. Both are locked
v1.1 constants after the §1.0 spike normalization pass.

Initial v1.1 vocabulary. Phases 2/3 extend this set for assignments and
focus leases; new names go through the same normalization step.
"""

from __future__ import annotations

from typing import Final

# Mode transitions (Phase 1)
MODE_TRANSITION: Final[str] = "runtime_state.mode_transition"

# Heartbeat lifecycle (Phase 1)
HEARTBEAT_INITIALIZED: Final[str] = "runtime_state.heartbeat_initialized"
HEARTBEAT_RECOVERED: Final[str] = "runtime_state.heartbeat_recovered"

# Assignment window lifecycle (Phase 2 §2.4 — scheduler-emitted, non-transition)
ASSIGNMENT_WINDOW_SKIPPED: Final[str] = "assignment.window.skipped"
ASSIGNMENT_WINDOW_REVIEW_REQUIRED: Final[str] = "assignment.window.review_required"

# Focus-lease lifecycle (Phase 3 §3.4 — coordinator-emitted). All lease outcomes
# emit a `focus_lease.*` event from this canonical set (§11.5). Distinct from the
# reason codes in `reasons.py` (D18).
FOCUS_LEASE_GRANTED: Final[str] = "focus_lease.granted"
FOCUS_LEASE_REJECTED: Final[str] = "focus_lease.rejected"
FOCUS_LEASE_PREEMPTED: Final[str] = "focus_lease.preempted"
FOCUS_LEASE_RELEASED: Final[str] = "focus_lease.released"

# Runtime-activity lifecycle (Phase 4 §4.4 handler-emitted, §4.5 coordinator-emitted).
# Every activity transition emits a `runtime_activity.*` event (D14/D22).
RUNTIME_ACTIVITY_STARTED: Final[str] = "runtime_activity.started"
RUNTIME_ACTIVITY_COMPLETED: Final[str] = "runtime_activity.completed"
RUNTIME_ACTIVITY_FAILED: Final[str] = "runtime_activity.failed"
RUNTIME_ACTIVITY_ABORTED: Final[str] = "runtime_activity.aborted"
