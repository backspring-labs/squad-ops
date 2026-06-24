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
