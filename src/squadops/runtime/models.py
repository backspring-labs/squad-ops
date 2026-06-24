"""
Runtime state dataclasses for SIP-0089.

Phase 1: `AgentRuntimeState` mirrors SIP-0089 §10.1.
Phase 2 (§2.1): `Assignment` + `DutyWindow` mirror §10.2/§10.3, plus the
`window_state()` time classifier used by the scheduler (§2.4) and the cycle
reserve-buffer guard (§2.5).

All models are frozen dataclasses; mutate via `dataclasses.replace()`. `Literal`
types in code mirror the DB `CHECK` constraints (D3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

RuntimeMode = Literal["duty", "cycle", "ambient"]
RuntimeStatus = Literal["online", "degraded", "recovering", "offline"]
Interruptibility = Literal["none", "low", "medium", "high"]


@dataclass(frozen=True)
class AgentRuntimeState:
    """Observable runtime state for a single agent.

    `mode`, `focus`, `current_runtime_activity_id`, and `current_assignment_ref`
    are coordinator-owned (D16). Heartbeat may initialize a missing row and
    update `last_heartbeat_at` + `runtime_status`, but must not overwrite
    coordinator-owned fields (D17).
    """

    agent_id: str
    mode: RuntimeMode
    runtime_status: RuntimeStatus
    focus: str
    current_runtime_activity_id: str | None
    interruptibility: Interruptibility
    last_heartbeat_at: datetime
    current_assignment_ref: str | None


# ---------------------------------------------------------------------------
# Phase 2 (§2.1) — Assignments and Duty Windows
# ---------------------------------------------------------------------------

AssignmentType = Literal["duty", "reserve", "cycle_eligibility"]
Strictness = Literal["hard", "soft"]
RecallPolicy = Literal["immediate", "graceful", "none"]
MissedWindowPolicy = Literal["skip", "start_late_within_grace", "require_operator_review"]
WindowState = Literal[
    "before_window",
    "in_reserve_before",
    "active",
    "in_reserve_after",
    "closed",
    "missed",
]


@dataclass(frozen=True)
class DutyWindow:
    """The time range an Assignment is active, plus its civil timezone.

    Per SIP-0089 §10.3, window fields live inside the Assignment rather than in a
    separate table for v1.1. `start`/`end` are absolute, timezone-aware instants;
    `timezone` is the civil tz (e.g. ``America/New_York``) the window was authored
    in, retained for display and recurrence reasoning. Half-open ``[start, end)``:
    `start` is inside the window, `end` is the first instant after it.
    """

    start: datetime
    end: datetime
    timezone: str


@dataclass(frozen=True)
class Assignment:
    """A durable commitment that may claim an agent during its DutyWindow.

    Mirrors SIP-0089 §10.2. Frozen; mutate via ``dataclasses.replace()``. An agent
    may hold multiple Assignments but exactly one current RuntimeMode (§10.2);
    conflicts are resolved by scheduling policy before a focus claim is attempted.

    `reserve_before_window`/`reserve_after_window` are first-class v1.1 policy
    (§11.4): the pre-duty buffer during which cycle recruitment is rejected.
    Strictness-dependent defaults (15m hard / 0m soft) are applied at creation
    time, not here — every Assignment carries explicit values (D7).
    """

    assignment_id: str
    assignment_type: AssignmentType
    assigned_role: str
    priority: int
    strictness: Strictness
    active_window: DutyWindow
    reserve_before_window: timedelta
    reserve_after_window: timedelta
    recall_policy: RecallPolicy
    graceful_window: timedelta
    missed_window_policy: MissedWindowPolicy
    allowed_off_window_modes: tuple[RuntimeMode, ...]
    active: bool = True


def window_state(
    assignment: Assignment,
    now: datetime,
    *,
    entered_active: bool = True,
) -> WindowState:
    """Classify where ``now`` falls relative to ``assignment``'s duty window.

    The five time-geometry states derive purely from the window and its reserve
    buffers (all bounds half-open, inclusive-start / exclusive-end):

        before_window      before the pre-duty reserve buffer opens
        in_reserve_before  inside the pre-duty reserve buffer, before the window (§11.4)
        active             inside the window itself
        in_reserve_after   after the window, inside the trailing reserve buffer
        closed             past the trailing reserve buffer

    The sixth state, ``missed``, is NOT derivable from time alone — it requires
    knowing the agent never entered duty. The scheduler (§2.4) tracks that and
    passes ``entered_active=False``; only once the window has *ended* without entry
    does the result become ``missed`` (it never pre-empts ``active``, since the
    agent could still enter while the window is open). The default ``True`` makes
    the documented ``window_state(assignment, now)`` a pure time classifier — all
    the §2.5 reserve guard needs, since it acts only on ``in_reserve_before`` and
    ``active``.

    All datetimes must be timezone-aware; mixing aware/naive raises ``TypeError``
    from the comparison, which is the desired fail-fast.
    """
    window = assignment.active_window
    reserve_before_start = window.start - assignment.reserve_before_window
    reserve_after_end = window.end + assignment.reserve_after_window

    if now < reserve_before_start:
        return "before_window"
    if now < window.start:
        return "in_reserve_before"
    if now < window.end:
        return "active"
    # The window has ended.
    if not entered_active:
        return "missed"
    if now < reserve_after_end:
        return "in_reserve_after"
    return "closed"
