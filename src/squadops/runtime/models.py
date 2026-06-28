"""
Runtime state dataclasses for SIP-0089.

Phase 1: `AgentRuntimeState` mirrors SIP-0089 §10.1.
Phase 2 (§2.1): `Assignment` + `DutyWindow` mirror §10.2/§10.3, plus the
`window_state()` time classifier used by the scheduler (§2.4) and the cycle
reserve-buffer guard (§2.5).
Phase 3 (§3.1): `FocusLease` mirrors §10.4, plus the `LeaseDecision` union
(`LeaseGranted` / `LeaseRejected` / `LeasePreempting`) returned by the
`FocusLeasePort`. Queueing (`LeaseQueued`) is deferred to v1.2+ (§3.0/D20).
Phase 4 (§4.1): `RuntimeActivity` mirrors §10.6 — the observable unit of work an
agent performs within a mode, with at most one *active* activity per agent (D9).

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

    `agent_id` (the holder) is not in the §10.2 field sketch but is required by the
    §2.2 table and the §2.3 port: `list_active_assignments(now)` returns rows across
    agents, and the §2.5 reserve guard filters them to a run's participating agents,
    so each Assignment must carry its holder.

    `reserve_before_window`/`reserve_after_window` are first-class v1.1 policy
    (§11.4): the pre-duty buffer during which cycle recruitment is rejected.
    Strictness-dependent defaults (15m hard / 0m soft) are applied at creation
    time, not here — every Assignment carries explicit values (D7).
    """

    assignment_id: str
    agent_id: str
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


def default_reserve_before_window(strictness: Strictness) -> timedelta:
    """Return the strictness-dependent pre-duty reserve buffer (SIP-0089 §11.4 / D7).

    Hard duty reserves the 15 minutes before its window (cycle recruitment is
    rejected during that buffer so the agent is free when duty opens); soft duty
    reserves nothing (the scheduler handles soft recall when the window opens, so
    there is no pre-duty hold). The trailing `reserve_after_window` default is
    always zero, so it has no helper — callers pass ``timedelta()``.

    Applied at Assignment creation time (the API create route), never inside the
    dataclass: per D7 every Assignment carries explicit reserve values, so this
    only fills the gap when a caller omits them.
    """
    return timedelta(minutes=15) if strictness == "hard" else timedelta()


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


# ---------------------------------------------------------------------------
# Phase 3 (§3.1) — Focus leases
# ---------------------------------------------------------------------------

OwnerType = Literal["duty", "cycle", "ambient"]
RenewalPolicy = Literal["heartbeat", "ttl", "fixed_window"]

# Owner-type precedence for focus arbitration (§11.5 / §12). A higher rank may
# preempt a lower one; equal or lower is rejected. Duty outranks cycle outranks
# ambient — the same ordering that lets a duty window displace ambient/cycle work.
_OWNER_TYPE_PRECEDENCE: dict[OwnerType, int] = {"ambient": 0, "cycle": 1, "duty": 2}


def owner_type_outranks(requester: OwnerType, holder: OwnerType) -> bool:
    """True when a `requester` owner type may preempt a `holder` of focus.

    Strictly-greater precedence: a duty request preempts a cycle/ambient holder,
    a cycle request preempts an ambient holder, and nothing preempts an equal or
    higher owner type (those resolve to `rejected`, not `preempting`).
    """
    return _OWNER_TYPE_PRECEDENCE[requester] > _OWNER_TYPE_PRECEDENCE[holder]


@dataclass(frozen=True)
class FocusLease:
    """An explicit ownership claim over an agent's primary attention (§10.4).

    Mirrors the SIP §10.4 sketch plus the holder (`agent_id`) and the persistence
    bookkeeping the §3.2 table needs: `released_at` (null while the lease is the
    current/active one — the partial unique index enforces at most one such row
    per agent) and `idempotency_key` (replay-safe acquire/preempt per D12).

    A lease does NOT encode RuntimeMode: holding a lease is the *hard gate* for
    primary attention within a mode, but the coordinator still writes `mode`
    separately (§3.4, "lease ≠ mode").
    """

    lease_id: str
    agent_id: str
    owner_type: OwnerType
    owner_ref: str
    acquired_at: datetime
    expires_at: datetime | None
    renewal_policy: RenewalPolicy
    interruptibility: Interruptibility
    recall_policy: RecallPolicy
    released_at: datetime | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class LeaseGranted:
    """Focus acquired — the agent now holds the lease (§11.5 `granted`)."""

    lease_id: str
    expires_at: datetime | None
    reason_code: str


@dataclass(frozen=True)
class LeaseRejected:
    """Focus denied; the current owner keeps it (§11.5 `rejected`).

    `retry_after` is advisory (when the caller might usefully retry); `None` when
    no estimate is available. v1.1's deferred-queue rejections also use this shape
    with reason `focus_lease_queueing_not_supported_in_v1.1` (§3.0/D20).
    """

    current_owner_ref: str
    reason_code: str
    retry_after: timedelta | None = None


@dataclass(frozen=True)
class LeasePreempting:
    """A higher-precedence owner is displacing the current owner (§11.5 `preempting`).

    No new lease exists yet: the caller must honor `preemption_grace`, revoke the
    current owner's lease, then re-request to obtain a `LeaseGranted`. Kept as a
    distinct outcome (rather than auto-granting) so the grace period and the
    revoke are explicit, observable steps.
    """

    current_owner_ref: str
    preemption_grace: timedelta
    reason_code: str


# Discriminated union of v1.1 lease outcomes. `LeaseQueued` is a recognized
# v1.2+ outcome (§3.0/D20) and is deliberately absent here.
LeaseDecision = LeaseGranted | LeaseRejected | LeasePreempting


# ---------------------------------------------------------------------------
# Phase 4 (§4.1) — Runtime activities
# ---------------------------------------------------------------------------

ActivityState = Literal["pending", "running", "paused", "completed", "aborted", "failed"]
ActivitySourceKind = Literal[
    "cycle_task", "workload", "duty_handler", "ambient_observation", "embodied_action"
]

# An activity occupies the agent's single active slot (D9) while in one of these
# states; the complement are terminal. The §4.2 partial unique index enforces at
# most one active row per agent.
_ACTIVE_ACTIVITY_STATES: frozenset[ActivityState] = frozenset({"pending", "running", "paused"})
_TERMINAL_ACTIVITY_STATES: frozenset[ActivityState] = frozenset({"completed", "aborted", "failed"})


def is_active_activity_state(state: ActivityState) -> bool:
    """True while the activity holds the agent's single active slot (D9)."""
    return state in _ACTIVE_ACTIVITY_STATES


def is_terminal_activity_state(state: ActivityState) -> bool:
    """True once the activity has ended (`completed`/`aborted`/`failed`)."""
    return state in _TERMINAL_ACTIVITY_STATES


@dataclass(frozen=True)
class RuntimeActivity:
    """An observable unit of work an agent performs within a mode (§10.6).

    Makes current work visible without digging through prompt history. At most one
    *active* (`pending`/`running`/`paused`) activity per agent (D9), enforced by the
    §4.2 partial unique index. RuntimeActivities don't perform work — handlers and
    workloads do, emitting these at task granularity (D19); `pending` is short-lived.

    Source identity is explicit and queryable: `cycle_id` / `workload_id` /
    `task_id` are first-class columns. `source_ref` is opaque adapter detail that
    **core never parses** (§4.1) — history-by-X queries use the explicit columns.

    Frozen; mutate via `dataclasses.replace()`. `completion_conditions` /
    `evidence_requirements` carry decoded JSONB payloads (opaque in v1.1); they make
    the instance unhashable, which is fine — runtime activities are never hashed.
    """

    runtime_activity_id: str
    agent_id: str
    mode: RuntimeMode
    activity_type: str
    goal: str
    priority: int
    state: ActivityState
    source_kind: ActivitySourceKind
    source_ref: str
    cycle_id: str | None
    workload_id: str | None
    task_id: str | None
    can_pause: bool
    can_resume: bool
    can_abort: bool
    completion_conditions: tuple[dict, ...] = ()
    evidence_requirements: tuple[dict, ...] = ()
    started_at: datetime | None = None
    paused_at: datetime | None = None
    ended_at: datetime | None = None
