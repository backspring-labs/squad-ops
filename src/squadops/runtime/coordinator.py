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

FocusLease (Phase 3, §10.4) and RuntimeActivity (Phase 4) resolution are
deliberately stubbed seams here — see the precondition comments in
`request_transition`. On apply, a canonical event is emitted with a *separate*
reason code (D14/D18) through the injected `RuntimeEventPublisher`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.models import RuntimeMode

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


class RuntimeCoordinator:
    """Validates and applies RuntimeMode transitions; emits reason-coded events."""

    def __init__(
        self,
        state: RuntimeStatePort,
        *,
        events_publisher: RuntimeEventPublisher | None = None,
    ) -> None:
        self._state = state
        self._events = events_publisher
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
            return self._reject(agent_id, current, target_mode, reason_code, reasons.INVALID_MODE_TRANSITION)

        # (4 §11.3) an offline runtime must reach online/recovering before duty.
        if target_mode == "duty" and state.runtime_status == "offline":
            return self._reject(
                agent_id, current, target_mode, reason_code, reasons.OFFLINE_CANNOT_ENTER_DUTY
            )

        # (2) FocusLease decision — Phase 3 (§10.4) wires arbitration here.
        # (3) RuntimeActivity decision — Phase 4 wires pause/resume/abort here.
        # Both are intentional no-ops in Phase 2.

        # (5 D16) apply — the coordinator is the sole writer of `mode`. Entering
        # duty binds the active assignment; leaving duty clears it.
        new_state = dataclasses.replace(
            state,
            mode=target_mode,
            current_assignment_ref=(assignment_id if target_mode == "duty" else None),
        )
        await self._state.upsert_state(new_state)

        # (5 D14/D18) emit the canonical event with a separate reason code.
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

        # (6) record idempotency key only after a successful apply.
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
