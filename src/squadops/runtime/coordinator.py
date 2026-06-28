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
stranded leases); D25's single-Postgres-transaction wrapping of the lease + mode
writes lands in Phase 4 (§4.5) alongside RuntimeActivity. With `focus_lease=None`
the coordinator behaves exactly as in Phase 2.

On apply, a canonical mode-transition event plus the relevant `focus_lease.*`
events are emitted, each with a *separate* reason code (D14/D18) through the
injected `RuntimeEventPublisher`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.focus_lease import FocusLeasePort
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.models import (
    AgentRuntimeState,
    LeaseGranted,
    LeasePreempting,
    OwnerType,
    RuntimeMode,
)

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


class RuntimeCoordinator:
    """Validates and applies RuntimeMode transitions; emits reason-coded events."""

    def __init__(
        self,
        state: RuntimeStatePort,
        *,
        events_publisher: RuntimeEventPublisher | None = None,
        focus_lease: FocusLeasePort | None = None,
    ) -> None:
        self._state = state
        self._events = events_publisher
        # FocusLease arbitration (§3.4). None → Phase-2 behavior (no lease gate).
        self._focus_lease = focus_lease
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
        """Arbitrate the lease, write the mode, and emit events (§4.5 steps 4–7).

        Reached only after every validation gate passes. lease ≠ mode: a lease
        secured here is rolled back if the mode write fails (§3.4 compensation),
        and the leaving-mode lease is released only after the write succeeds so a
        failure can never strand state.
        """
        current = state.mode

        # (2/4 §4.5) FocusLease arbitration before the mode write. A rejected
        # lease blocks the transition (prior mode stays authoritative).
        # (3) RuntimeActivity decision — Phase 4 wires pause/resume/abort here.
        arb: _LeaseArbitration | None = None
        if self._focus_lease is not None:
            arb = await self._arbitrate_lease(agent_id, current, target_mode, owner_ref)
            if not arb.ok:
                rejected = arb.rejected_reason or reasons.FOCUS_LEASE_CONFLICT
                self._emit_lease_event(
                    events.FOCUS_LEASE_REJECTED,
                    agent_id,
                    rejected,
                    from_mode=current,
                    to_mode=target_mode,
                    owner_ref=owner_ref,
                )
                return self._reject(agent_id, current, target_mode, reason_code, rejected)

        # (6 D16) apply — the coordinator is the sole writer of `mode`. Entering
        # duty binds the active assignment; leaving duty clears it.
        new_state = dataclasses.replace(
            state,
            mode=target_mode,
            current_assignment_ref=(assignment_id if target_mode == "duty" else None),
        )
        try:
            await self._state.upsert_state(new_state)
        except Exception:
            # Compensation (§3.4): a lease acquired for this transition must not
            # outlive a failed mode write. Prior mode remains authoritative.
            if arb is not None and arb.acquired_lease_id is not None:
                await self._focus_lease.release_lease(
                    arb.acquired_lease_id, reasons.FOCUS_LEASE_RELEASED
                )
            raise

        # Post-write lease bookkeeping: release the leaving-mode lease (entering
        # ambient) only now that the mode write succeeded, then emit focus_lease.*
        # events for what the arbitration did (D18 — distinct from the reason).
        if arb is not None:
            if arb.release_after_lease_id is not None:
                await self._focus_lease.release_lease(
                    arb.release_after_lease_id, reasons.FOCUS_LEASE_RELEASED
                )
            self._emit_arbitration_events(
                arb, agent_id, from_mode=current, to_mode=target_mode, owner_ref=owner_ref
            )

        # (7 D14/D18) emit the canonical mode-transition event with its own reason.
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
    ) -> _LeaseArbitration:
        """Secure (or clear) the FocusLease for a `current → target_mode` move.

        Never writes `mode` (lease ≠ mode). Resolution by case:
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
        old_lease = await fl.get_current_lease(agent_id)
        holds_leaving_lease = old_lease is not None and old_lease.owner_type == leaving_owner

        if new_owner is None:
            return _LeaseArbitration(
                ok=True,
                release_after_lease_id=(old_lease.lease_id if holds_leaving_lease else None),
            )

        # Stable idem key: repeated requests for the same (owner, agent) replay the
        # same lease (D12) rather than minting duplicates across scheduler ticks.
        idem = f"{new_owner}:{owner_ref}:{agent_id}"
        decision = await fl.request_lease(agent_id, new_owner, owner_ref, idem)

        if isinstance(decision, LeaseGranted):
            return _LeaseArbitration(ok=True, acquired_lease_id=decision.lease_id, granted=True)

        if isinstance(decision, LeasePreempting):
            if old_lease is not None:
                await fl.revoke_lease(old_lease.lease_id, reasons.FOCUS_LEASE_PREEMPTED)
            regrant = await fl.request_lease(agent_id, new_owner, owner_ref, idem)
            if isinstance(regrant, LeaseGranted):
                return _LeaseArbitration(
                    ok=True, acquired_lease_id=regrant.lease_id, granted=True, preempted=True
                )
            return _LeaseArbitration(ok=False, rejected_reason=regrant.reason_code)

        # LeaseRejected. If our own leaving-mode lease is what blocks us, release
        # it (the agent is done with that focus) and retry once.
        if holds_leaving_lease and old_lease is not None:
            await fl.release_lease(old_lease.lease_id, reasons.FOCUS_LEASE_RELEASED)
            regrant = await fl.request_lease(agent_id, new_owner, owner_ref, idem)
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
