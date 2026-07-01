"""
Runtime state coordinator — the sole authority for RuntimeMode transitions
(SIP-0089 §2.6, D16).

Every mode change flows through `request_transition`. The coordinator is the
only writer of `AgentRuntimeState.mode` (D16); schedulers, CLI, and external
callers *request* transitions and the coordinator validates and applies them.

Phase 2 gates:
- a reason code is required (§11.2);
- target == current is an idempotent no-op;
- the (from, to) pair must be an allowed transition (§11.1 lists all six ordered
  pairs among the three modes, so this mainly rejects malformed `target_mode`
  strings that bypass the type hint);
- an `offline` runtime may not enter `duty` directly (§11.3);
- D12 idempotency: a transition tagged `(assignment_id, scheduled_at)` applies at
  most once, so repeated scheduler ticks within a window never duplicate it.

Phase 3 (§3.4) wires FocusLease arbitration: entering a focus-bearing mode
(`cycle`/`duty`) must secure the owner's lease *before* the mode write (§4.5
step 4 precedes step 6), and **lease ≠ mode** — a granted lease never changes
`RuntimeMode`; the upsert is authoritative. Phase 3 uses best-effort compensation
(a lease acquired for a transition is rolled back if the mode write fails — no
stranded leases). With `focus_lease=None` the coordinator behaves as in Phase 2.

Phase 4 (§4.5, thin v1.1 seam) wires a RuntimeActivity action: a mode change
orphans any activity bound to the previous mode, so it is aborted best-effort
*after* the mode write. The full §4.5 transition order (activity before mode) and
D25's single-Postgres-transaction wrapping of lease+activity+mode remain a
follow-up in #244 (now unblocked — recruitment #233 has landed); the
activity-orphan path stays unexercised in v1.1. With `activity=None` there is no
activity bookkeeping.

On apply, a canonical mode-transition event plus the relevant `focus_lease.*`
events are emitted, each with a *separate* reason code (D14/D18) through the
injected `RuntimeEventPublisher`.
"""

from __future__ import annotations

import dataclasses
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from squadops.ports.runtime.activity import RuntimeActivityPort
from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.focus_lease import FocusLeasePort
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.ports.runtime.transaction import RuntimeTransactionPort
from squadops.runtime import events, reasons
from squadops.runtime.models import (
    AgentRuntimeState,
    LeaseGranted,
    LeasePreempting,
    OwnerType,
    RuntimeActivity,
    RuntimeMode,
)

logger = logging.getLogger(__name__)

RequesterKind = Literal["scheduler", "coordinator", "cli", "external"]

# §11.1 allowed mode transitions. All six ordered pairs among the three modes are
# permitted (some policy-gated — cycle→duty preemption, duty→cycle window-ended —
# whose deeper checks land with FocusLease in Phase 3 / RuntimeActivity in
# Phase 4). Kept explicit so a malformed `target_mode` is rejected, not applied.
_ALLOWED_TRANSITIONS: frozenset[tuple[RuntimeMode, RuntimeMode]] = frozenset(
    {
        ("ambient", "cycle"),
        ("ambient", "duty"),
        ("cycle", "ambient"),
        ("cycle", "duty"),
        ("duty", "ambient"),
        ("duty", "cycle"),
    }
)


@dataclass(frozen=True)
class TransitionOutcome:
    """Result of a `request_transition` call.

    Exactly one of three shapes: applied (`applied=True`, `event_name` set),
    idempotent no-op (`idempotent_skip=True`), or rejected (`rejected_reason`
    set). `reason_code` echoes the requested reason in all cases.
    """

    applied: bool
    agent_id: str
    from_mode: RuntimeMode | None
    to_mode: str
    reason_code: str
    event_name: str | None = None
    rejected_reason: str | None = None
    idempotent_skip: bool = False


@dataclass(frozen=True)
class _LeaseArbitration:
    """Outcome of the §3.4 lease step for one transition (internal).

    `acquired_lease_id` is a lease secured for the *target* mode — held so the
    mode write can roll it back on failure. `release_after_lease_id` is the
    leaving-mode lease to release only *after* a successful mode write (entering
    ambient), so a write failure can't strand it. The flags drive event emission.
    """

    ok: bool
    rejected_reason: str | None = None
    acquired_lease_id: str | None = None
    release_after_lease_id: str | None = None
    granted: bool = False
    preempted: bool = False
    released: bool = False


def _owner_type_for_mode(mode: str) -> OwnerType | None:
    """The FocusLease `owner_type` a mode claims, or `None` for ambient.

    Ambient holds no primary lease in v1.1 — §10.4 permits an ambient lease only
    under explicit policy, which the coordinator does not grant by default.
    """
    return mode if mode in ("cycle", "duty") else None  # type: ignore[return-value]


class _TransitionRejected(Exception):
    """Internal: a lease conflict aborts the transition's unit of work (§4.5/D25).

    Raised inside the `RuntimeTransactionPort.begin()` block so any partial
    arbitration writes (e.g. a preempt-revoke that then failed to re-grant) roll
    back with the transaction. The coordinator catches it and returns a *reject*
    outcome — a rejection, not an error.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _NullTransaction(RuntimeTransactionPort):
    """Default no-op unit of work: yields no connection (§4.5/D25).

    With `conn=None`, each runtime port write acquires its own auto-committing
    connection — the exact Phase-3/4 behavior — and the coordinator's compensation
    (release a just-acquired lease on a failed mode write) stands in for a real
    transaction rollback. Used when the coordinator is built without a
    `RuntimeTransactionPort`.
    """

    @asynccontextmanager
    async def begin(self) -> Any:
        yield None


class RuntimeCoordinator:
    """Validates and applies RuntimeMode transitions; emits reason-coded events."""

    def __init__(
        self,
        state: RuntimeStatePort,
        *,
        events_publisher: RuntimeEventPublisher | None = None,
        focus_lease: FocusLeasePort | None = None,
        activity: RuntimeActivityPort | None = None,
        transaction: RuntimeTransactionPort | None = None,
    ) -> None:
        self._state = state
        self._events = events_publisher
        # FocusLease arbitration (§3.4). None → Phase-2 behavior (no lease gate).
        self._focus_lease = focus_lease
        # RuntimeActivity seam (§4.5, thin v1.1). None → no activity bookkeeping.
        self._activity = activity
        # RuntimeTransaction UoW (§4.5/D25). None → _NullTransaction: each write
        # uses its own connection and compensation stands in for a rollback (the
        # Phase-3/4 behavior). A real UoW makes lease+activity+mode atomic.
        self._transaction: RuntimeTransactionPort = transaction or _NullTransaction()
        # D12 idempotency ledger. In-process for v1.1 (single in-process scheduler);
        # durable persistence is a refinement for the SIP-0091 Temporal adapter.
        self._applied_keys: set[str] = set()

    async def request_transition(
        self,
        agent_id: str,
        target_mode: str,
        reason_code: str,
        *,
        requester_kind: RequesterKind,
        owner_ref: str,
        assignment_id: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> TransitionOutcome:
        # (1 §11.2) a reason code is mandatory.
        if not reason_code:
            return TransitionOutcome(
                applied=False,
                agent_id=agent_id,
                from_mode=None,
                to_mode=target_mode,
                reason_code=reason_code,
                rejected_reason=reasons.MISSING_REASON_CODE,
            )

        # (D12) repeated request for the same scheduled window is a no-op.
        idem_key = _idem_key(agent_id, assignment_id, scheduled_at, target_mode)
        if idem_key is not None and idem_key in self._applied_keys:
            return TransitionOutcome(
                applied=False,
                agent_id=agent_id,
                from_mode=target_mode if target_mode in ("duty", "cycle", "ambient") else None,
                to_mode=target_mode,
                reason_code=reason_code,
                idempotent_skip=True,
            )

        state = await self._state.get_state(agent_id)
        if state is None:
            state = await self._state.ensure_state(agent_id)
        current = state.mode

        # target == current: nothing to do.
        if current == target_mode:
            if idem_key is not None:
                self._applied_keys.add(idem_key)
            return TransitionOutcome(
                applied=False,
                agent_id=agent_id,
                from_mode=current,
                to_mode=target_mode,
                reason_code=reason_code,
                idempotent_skip=True,
            )

        # (4 §11.1) structural allow-list — also rejects malformed target modes.
        if (current, target_mode) not in _ALLOWED_TRANSITIONS:
            return self._reject(
                agent_id, current, target_mode, reason_code, reasons.INVALID_MODE_TRANSITION
            )

        # (4 §11.3) an offline runtime must reach online/recovering before duty.
        if target_mode == "duty" and state.runtime_status == "offline":
            return self._reject(
                agent_id, current, target_mode, reason_code, reasons.OFFLINE_CANNOT_ENTER_DUTY
            )

        # All gates passed — arbitrate the lease, write the mode, emit (§4.5 4-7).
        return await self._apply_transition(
            agent_id,
            state,
            target_mode,
            reason_code,
            requester_kind=requester_kind,
            owner_ref=owner_ref,
            assignment_id=assignment_id,
            idem_key=idem_key,
        )

    async def _apply_transition(
        self,
        agent_id: str,
        state: AgentRuntimeState,
        target_mode: str,
        reason_code: str,
        *,
        requester_kind: RequesterKind,
        owner_ref: str,
        assignment_id: str | None,
        idem_key: str | None,
    ) -> TransitionOutcome:
        """Apply lease → activity → mode as one unit of work, then emit (§4.5/D25).

        Reached only after every validation gate passes. The three writes run in
        `RuntimeTransactionPort.begin()` in §4.5 order (lease step 4 → activity
        step 5 → mode step 6): with a real UoW a failure at any step aborts the
        transaction, rolling back the lease acquisition and the activity abort;
        with the default null UoW the writes use their own connections and the
        compensation below stands in for a rollback. lease ≠ mode throughout.

        Events are emitted only *after* the unit of work commits, so an aborted
        transition (lease conflict or write failure) emits nothing.
        """
        current = state.mode
        arb: _LeaseArbitration | None = None
        aborted_activity: RuntimeActivity | None = None
        # (6 D16) the sole `mode` write. Entering duty binds the active assignment;
        # leaving duty clears it. Built up front; written last, inside the UoW.
        new_state = dataclasses.replace(
            state,
            mode=target_mode,
            current_assignment_ref=(assignment_id if target_mode == "duty" else None),
        )
        try:
            async with self._transaction.begin() as conn:
                # (4 §4.5) FocusLease arbitration. A rejected lease aborts the unit
                # of work (undoing any partial preempt-revoke) via _TransitionRejected.
                if self._focus_lease is not None:
                    arb = await self._arbitrate_lease(
                        agent_id, current, target_mode, owner_ref, conn=conn
                    )
                    if not arb.ok:
                        raise _TransitionRejected(
                            arb.rejected_reason or reasons.FOCUS_LEASE_CONFLICT
                        )
                # (5 §4.5) RuntimeActivity action BEFORE the mode write, inside the
                # transaction: abort an activity orphaned by this transition.
                if self._activity is not None:
                    aborted_activity = await self._abort_orphaned_activity(
                        agent_id, target_mode, conn=conn
                    )
                # (6 §4.5/D16) the mode write.
                await self._state.upsert_state(new_state, conn=conn)
                # Release the leaving-mode lease (entering ambient) within the same
                # unit of work, so it commits atomically with the mode write.
                if arb is not None and arb.release_after_lease_id is not None:
                    await self._focus_lease.release_lease(
                        arb.release_after_lease_id, reasons.FOCUS_LEASE_RELEASED, conn=conn
                    )
        except _TransitionRejected as rej:
            # A lease conflict — the unit of work rolled back; prior mode is authoritative.
            self._emit_lease_event(
                events.FOCUS_LEASE_REJECTED,
                agent_id,
                rej.reason,
                from_mode=current,
                to_mode=target_mode,
                owner_ref=owner_ref,
            )
            return self._reject(agent_id, current, target_mode, reason_code, rej.reason)
        except Exception:
            # Unexpected failure. A real UoW already rolled back the lease acquisition;
            # for the null-UoW path this compensation (§3.4) ensures a lease acquired
            # for this transition never outlives the failed write. Harmless no-op when
            # already rolled back (the row matches no active lease).
            if arb is not None and arb.acquired_lease_id is not None:
                await self._focus_lease.release_lease(
                    arb.acquired_lease_id, reasons.FOCUS_LEASE_RELEASED
                )
            raise

        # Committed. Emit events post-commit (D14/D18): arbitration → activity → mode.
        if arb is not None:
            self._emit_arbitration_events(
                arb, agent_id, from_mode=current, to_mode=target_mode, owner_ref=owner_ref
            )
        if aborted_activity is not None and self._events is not None:
            self._events.emit(
                events.RUNTIME_ACTIVITY_ABORTED,
                agent_id=agent_id,
                reason_code=reasons.ACTIVITY_PREEMPTED_BY_MODE_CHANGE,
                payload={
                    "runtime_activity_id": aborted_activity.runtime_activity_id,
                    "from_mode": aborted_activity.mode,
                    "to_mode": target_mode,
                },
            )
        if self._events is not None:
            self._events.emit(
                events.MODE_TRANSITION,
                agent_id=agent_id,
                reason_code=reason_code,
                payload={
                    "from_mode": current,
                    "to_mode": target_mode,
                    "assignment_id": assignment_id,
                    "requester_kind": requester_kind,
                    "owner_ref": owner_ref,
                },
            )

        # record idempotency key only after a successful apply.
        if idem_key is not None:
            self._applied_keys.add(idem_key)

        return TransitionOutcome(
            applied=True,
            agent_id=agent_id,
            from_mode=current,
            to_mode=target_mode,
            reason_code=reason_code,
            event_name=events.MODE_TRANSITION,
        )

    @staticmethod
    def _reject(
        agent_id: str,
        from_mode: RuntimeMode,
        to_mode: str,
        reason_code: str,
        rejected_reason: str,
    ) -> TransitionOutcome:
        return TransitionOutcome(
            applied=False,
            agent_id=agent_id,
            from_mode=from_mode,
            to_mode=to_mode,
            reason_code=reason_code,
            rejected_reason=rejected_reason,
        )

    async def _arbitrate_lease(
        self,
        agent_id: str,
        current: RuntimeMode,
        target_mode: str,
        owner_ref: str,
        *,
        conn: Any = None,
    ) -> _LeaseArbitration:
        """Secure (or clear) the FocusLease for a `current → target_mode` move.

        Never writes `mode` (lease ≠ mode). All reads/writes run on the caller's
        unit-of-work `conn` (§4.5/D25) so they roll back with the transition on a
        later failure. Resolution by case:
        - entering ambient → no acquire; defer releasing the leaving-mode lease
          to after the mode write;
        - entering cycle/duty with no conflict → acquire (`granted`);
        - entering a mode that outranks the holder (cycle→duty) → revoke the
          holder, re-request (`granted` + `preempted`);
        - entering a mode that does NOT outrank the holder but we are voluntarily
          leaving that holder's mode (duty→cycle, window ended) → release it,
          re-request (`granted` + `released`);
        - otherwise the holder wins → not ok (`rejected_reason`).
        """
        fl = self._focus_lease
        assert fl is not None  # guarded by the caller
        new_owner = _owner_type_for_mode(target_mode)
        leaving_owner = _owner_type_for_mode(current)
        old_lease = await fl.get_current_lease(agent_id, conn=conn)
        holds_leaving_lease = old_lease is not None and old_lease.owner_type == leaving_owner

        if new_owner is None:
            return _LeaseArbitration(
                ok=True,
                release_after_lease_id=(old_lease.lease_id if holds_leaving_lease else None),
            )

        # Stable idem key: repeated requests for the same (owner, agent) replay the
        # same lease (D12) rather than minting duplicates across scheduler ticks.
        idem = f"{new_owner}:{owner_ref}:{agent_id}"
        decision = await fl.request_lease(agent_id, new_owner, owner_ref, idem, conn=conn)

        if isinstance(decision, LeaseGranted):
            return _LeaseArbitration(ok=True, acquired_lease_id=decision.lease_id, granted=True)

        if isinstance(decision, LeasePreempting):
            if old_lease is not None:
                await fl.revoke_lease(old_lease.lease_id, reasons.FOCUS_LEASE_PREEMPTED, conn=conn)
            regrant = await fl.request_lease(agent_id, new_owner, owner_ref, idem, conn=conn)
            if isinstance(regrant, LeaseGranted):
                return _LeaseArbitration(
                    ok=True, acquired_lease_id=regrant.lease_id, granted=True, preempted=True
                )
            return _LeaseArbitration(ok=False, rejected_reason=regrant.reason_code)

        # LeaseRejected. If our own leaving-mode lease is what blocks us, release
        # it (the agent is done with that focus) and retry once.
        if holds_leaving_lease and old_lease is not None:
            await fl.release_lease(old_lease.lease_id, reasons.FOCUS_LEASE_RELEASED, conn=conn)
            regrant = await fl.request_lease(agent_id, new_owner, owner_ref, idem, conn=conn)
            if isinstance(regrant, LeaseGranted):
                return _LeaseArbitration(
                    ok=True, acquired_lease_id=regrant.lease_id, granted=True, released=True
                )
            return _LeaseArbitration(ok=False, rejected_reason=regrant.reason_code)

        return _LeaseArbitration(ok=False, rejected_reason=decision.reason_code)

    def _emit_lease_event(
        self,
        event_name: str,
        agent_id: str,
        reason_code: str,
        *,
        from_mode: str,
        to_mode: str,
        owner_ref: str,
    ) -> None:
        if self._events is None:
            return
        self._events.emit(
            event_name,
            agent_id=agent_id,
            reason_code=reason_code,
            payload={"from_mode": from_mode, "to_mode": to_mode, "owner_ref": owner_ref},
        )

    def _emit_arbitration_events(
        self,
        arb: _LeaseArbitration,
        agent_id: str,
        *,
        from_mode: str,
        to_mode: str,
        owner_ref: str,
    ) -> None:
        """Emit the focus_lease.* events for a successful arbitration (D18)."""
        if arb.preempted:
            self._emit_lease_event(
                events.FOCUS_LEASE_PREEMPTED,
                agent_id,
                reasons.FOCUS_LEASE_PREEMPTED,
                from_mode=from_mode,
                to_mode=to_mode,
                owner_ref=owner_ref,
            )
        if arb.released or arb.release_after_lease_id is not None:
            self._emit_lease_event(
                events.FOCUS_LEASE_RELEASED,
                agent_id,
                reasons.FOCUS_LEASE_RELEASED,
                from_mode=from_mode,
                to_mode=to_mode,
                owner_ref=owner_ref,
            )
        if arb.granted:
            self._emit_lease_event(
                events.FOCUS_LEASE_GRANTED,
                agent_id,
                reasons.FOCUS_LEASE_GRANTED,
                from_mode=from_mode,
                to_mode=to_mode,
                owner_ref=owner_ref,
            )

    async def _abort_orphaned_activity(
        self, agent_id: str, target_mode: str, *, conn: Any = None
    ) -> RuntimeActivity | None:
        """Abort the agent's current activity if a mode change orphaned it (§4.5/D25).

        An activity belongs to a mode; once the agent leaves that mode the activity
        can't continue, so it's aborted. An activity already in the target mode
        (e.g. a handler started it for the mode we're entering) is left alone.
        Runs on the caller's unit-of-work `conn`, so the abort commits atomically
        with the mode write and rolls back if a later step fails. `update_state`'s
        active-only guard keeps it race-safe against the owning handler
        terminalizing first (matches no row → returns None).

        Returns the aborted activity (so the caller can emit `runtime_activity.*`
        post-commit), or `None` when nothing was orphaned / the guard matched
        nothing. Unlike the Phase-4 thin seam this no longer swallows errors: the
        abort is now part of the atomic unit (D25), so a failure aborts the
        transition. In v1.1 this path is effectively unexercised — scheduler
        `ambient↔duty` has no live activity, cycle activities are owned by their
        handler (§4.4), and recruitment (#233) moves only the lease — so the
        best-effort→transactional change is observable only under a future
        live-activity preemption (cycle→duty mid-task).
        """
        assert self._activity is not None  # guarded by the caller
        current = await self._activity.get_current_activity(agent_id, conn=conn)
        if current is None or current.mode == target_mode:
            return None
        return await self._activity.abort_activity(
            current.runtime_activity_id, reasons.ACTIVITY_PREEMPTED_BY_MODE_CHANGE, conn=conn
        )


def _idem_key(
    agent_id: str,
    assignment_id: str | None,
    scheduled_at: datetime | None,
    target_mode: str,
) -> str | None:
    """Idempotency key for a scheduled transition, or None when untagged.

    Requires both `assignment_id` and `scheduled_at` — ad-hoc (CLI/external)
    transitions are not deduplicated.
    """
    if assignment_id is None or scheduled_at is None:
        return None
    return f"{agent_id}|{assignment_id}|{scheduled_at.isoformat()}|{target_mode}"
