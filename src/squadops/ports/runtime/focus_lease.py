"""
FocusLeasePort — abstract interface for FocusLease persistence + arbitration
(SIP-0089 §10.4, Phase 3 §3.3).

A FocusLease is the hard gate for an agent's primary attention. `request_lease`
resolves to exactly one v1.1 `LeaseDecision` (§11.5): `LeaseGranted`,
`LeaseRejected`, or `LeasePreempting`. Queueing (`queued`) is deferred to v1.2+
(§3.0/D20); a would-be-queued request is rejected with reason
`focus_lease_queueing_not_supported_in_v1.1`.

The single active-lease invariant (at most one un-released lease per agent) is
enforced by the §3.2 partial unique index, not in code. Acquire/preempt are
replay-safe via `idempotency_key` (D12): a repeated request with the same key
returns the already-granted lease rather than creating a duplicate.

`request_lease` does NOT change `AgentRuntimeState.mode` — lease ≠ mode (§3.4).
The coordinator wires lease arbitration to mode transitions and is responsible
for rolling a freshly-granted lease back if the mode write fails.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.runtime.models import (
        FocusLease,
        Interruptibility,
        LeaseDecision,
        OwnerType,
        RecallPolicy,
        RenewalPolicy,
    )


class FocusLeasePort(ABC):
    """Port for `FocusLease` persistence and focus arbitration."""

    @abstractmethod
    async def request_lease(
        self,
        agent_id: str,
        owner_type: OwnerType,
        owner_ref: str,
        idempotency_key: str,
        *,
        expires_at: datetime | None = None,
        renewal_policy: RenewalPolicy = "ttl",
        interruptibility: Interruptibility = "high",
        recall_policy: RecallPolicy = "graceful",
        preemption_grace: timedelta = timedelta(),
        wait: bool = False,
        conn: Any = None,
    ) -> LeaseDecision:
        """Attempt to acquire the agent's primary focus; resolve to one outcome.

        Resolution (§11.5):
        - no current lease (or an idempotent replay of `idempotency_key`) →
          `LeaseGranted`;
        - a current lease held by a strictly lower-precedence owner type →
          `LeasePreempting` (no new lease is written; the caller honors
          `preemption_grace`, revokes the holder, then re-requests);
        - a current lease held by an equal/higher owner type → `LeaseRejected`
          (reason `focus_lease_conflict`), or — when `wait=True` — rejected with
          `focus_lease_queueing_not_supported_in_v1.1` (queueing deferred, D20).
        """

    @abstractmethod
    async def renew_lease(self, lease_id: str, *, expires_at: datetime | None = None) -> bool:
        """Extend an active lease. Returns True iff an active lease matched.

        With `expires_at` set, advances the expiry (the `ttl`/`fixed_window`
        path); without it, just refreshes `updated_at` (the `heartbeat` path).
        A released or unknown `lease_id` returns False (nothing to renew).
        """

    @abstractmethod
    async def release_lease(self, lease_id: str, reason_code: str, *, conn: Any = None) -> None:
        """Cooperatively complete a lease (the owner finished its focus work).

        Marks `released_at`, freeing the single-active-lease slot. `reason_code`
        is surfaced by the coordinator's `focus_lease.released` event (D18); it is
        not persisted as a column in v1.1. A no-op for an already-released lease.

        `conn` (§4.5/D25): run on the caller's unit-of-work connection when given.
        """

    @abstractmethod
    async def revoke_lease(self, lease_id: str, reason_code: str, *, conn: Any = None) -> None:
        """Non-cooperatively remove a lease (preemption / forced reclaim).

        Same storage effect as `release_lease` (marks `released_at`); the
        distinction is audit-only — revoke is initiated by a displacing owner, not
        the holder, and is surfaced via the `focus_lease.preempted` reason/event.

        `conn` (§4.5/D25): run on the caller's unit-of-work connection when given.
        """

    @abstractmethod
    async def get_current_lease(self, agent_id: str, *, conn: Any = None) -> FocusLease | None:
        """Return the agent's current (un-released) lease, or `None`.

        `conn` (§4.5/D25): read on the caller's unit-of-work connection when given,
        so the coordinator sees a consistent snapshot within its transaction.
        """

    @abstractmethod
    async def list_active_leases(
        self, *, owner_ref: str | None = None, conn: Any = None
    ) -> tuple[FocusLease, ...]:
        """Return every un-released lease, oldest first.

        `owner_ref` narrows the result to the leases one owner holds — a run id
        for `cycle` leases, an assignment id for `duty` leases. At most one
        active lease exists per agent (§3.2), so the result is bounded by the
        roster size and callers iterate it without pagination. Backs the
        #373/#529 stranded-lease sweeps (`runtime.focus_reaper`), which need to
        find held leases *by owner* — `get_current_lease` answers only the
        inverse question, and an owner whose agents are unknown (a dead process,
        a cancelled run) cannot ask it.

        `conn` (§4.5/D25): read on the caller's unit-of-work connection when given.
        """
