"""
Canonical runtime-state reason codes (SIP-0089, D14, D18).

Reasons describe **why** a decision happened. Events (in `events.py`)
describe **what happened**. The two vocabularies are deliberately separate —
see D18. Both are locked v1.1 constants after the §1.0 spike normalization pass.

Phases 2/3 extend this set for assignment scheduling and focus-lease decisions.
"""

from __future__ import annotations

from typing import Final

# Mode-transition reasons (Phase 1)
DUTY_WINDOW_OPENED: Final[str] = "duty_window_opened"
DUTY_WINDOW_CLOSED: Final[str] = "duty_window_closed"
CYCLE_RECRUITED: Final[str] = "cycle_recruited"
CYCLE_COMPLETED: Final[str] = "cycle_completed"

# Heartbeat-recovery reasons (Phase 1)
RUNTIME_STATUS_CHANGED_TO_ONLINE: Final[str] = "runtime_status_changed_to_online"

# Transition-rejection reasons (Phase 2 §2.6 — coordinator)
MISSING_REASON_CODE: Final[str] = "missing_reason_code"
INVALID_MODE_TRANSITION: Final[str] = "invalid_mode_transition"
OFFLINE_CANNOT_ENTER_DUTY: Final[str] = "offline_cannot_enter_duty"

# Duty-window scheduling reasons (Phase 2 §2.4 — scheduler)
DUTY_WINDOW_STARTED_LATE: Final[str] = "duty_window_started_late"
DUTY_WINDOW_MISSED: Final[str] = "duty_window_missed"
DUTY_WINDOW_MISSED_OPERATOR_REVIEW: Final[str] = "duty_window_missed_operator_review"

# Cycle recruitment-guard reasons (Phase 2 §2.5 — reserve buffer)
UPCOMING_HARD_DUTY_WINDOW: Final[str] = "upcoming_hard_duty_window"

# Focus-lease decision reasons (Phase 3 §3.1/§3.5 — FocusLease arbitration)
FOCUS_LEASE_GRANTED: Final[str] = "focus_lease_granted"
FOCUS_LEASE_RELEASED: Final[str] = "focus_lease_released"
FOCUS_LEASE_PREEMPTED: Final[str] = "focus_lease_preempted"
# Rejection reasons that a recruitment attempt may surface (§3.5). Per the §2.5
# precedent these ride a RUN_PAUSED payload rather than a new cycle EventType.
FOCUS_LEASE_CONFLICT: Final[str] = "focus_lease_conflict"
CURRENT_ACTIVITY_CANNOT_PAUSE: Final[str] = "current_activity_cannot_pause"
AGENT_RUNTIME_STATUS_UNAVAILABLE: Final[str] = "agent_runtime_status_unavailable"
# Deferred-queue rejection (§3.0/D20): a request that would have queued in v1.2.
FOCUS_LEASE_QUEUEING_NOT_SUPPORTED: Final[str] = "focus_lease_queueing_not_supported_in_v1.1"

# Runtime-activity reasons (Phase 4 §4.4/§4.5)
ACTIVITY_STARTED: Final[str] = "activity_started"
ACTIVITY_COMPLETED: Final[str] = "activity_completed"
ACTIVITY_FAILED: Final[str] = "activity_failed"
# The coordinator aborts an activity orphaned by a mode change (§4.5 thin seam).
ACTIVITY_PREEMPTED_BY_MODE_CHANGE: Final[str] = "activity_preempted_by_mode_change"
