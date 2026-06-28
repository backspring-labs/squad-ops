"""Unit tests for SIP-0089 Phase 3 — FocusLease arbitration.

Two layers are covered:

- `owner_type_outranks` (pure precedence rule) — the bug class is an inverted or
  mis-ranked comparison silently letting a cycle preempt a duty (or refusing a
  legitimate duty preemption);
- `PostgresFocusLease.request_lease` decision logic — granted / rejected /
  preempting / idempotent-replay / queue-deferral / lost-race, asserted on the
  returned `LeaseDecision` and on whether a lease row was actually written.

The asyncpg pool/connection fakes mirror `test_agent_runtime_state.py`: a single
`async with pool.acquire()` yields one connection whose `fetchrow`/`execute` are
scripted per the query sequence each method issues. Asserting "no INSERT on a
reject/preempt" is the load-bearing check — a buggy adapter that writes a second
active lease would violate the single-active-lease invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from adapters.persistence.runtime.focus_lease_postgres import PostgresFocusLease
from squadops.runtime import reasons
from squadops.runtime.models import (
    FocusLease,
    LeaseGranted,
    LeasePreempting,
    LeaseRejected,
    owner_type_outranks,
)

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 6, 28, 14, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# owner_type_outranks — precedence rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requester", "holder", "expected"),
    [
        ("duty", "cycle", True),
        ("duty", "ambient", True),
        ("cycle", "ambient", True),
        ("cycle", "duty", False),
        ("ambient", "duty", False),
        ("ambient", "cycle", False),
        ("duty", "duty", False),
        ("cycle", "cycle", False),
        ("ambient", "ambient", False),
    ],
)
def test_owner_type_outranks(requester, holder, expected):
    """Bug class: an inverted/mis-ranked comparison would let a cycle preempt a
    duty (or block a duty from preempting a cycle). Strictly-greater precedence:
    duty > cycle > ambient; equal never outranks."""
    assert owner_type_outranks(requester, holder) is expected


# ---------------------------------------------------------------------------
# asyncpg fakes
# ---------------------------------------------------------------------------


class _AcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        return False


def _make_pool(conn):
    pool = MagicMock()
    pool.acquire.return_value = _AcquireCtx(conn)
    return pool


def _lease_row(**overrides) -> dict:
    base = {
        "lease_id": "lease-1",
        "agent_id": "max",
        "owner_type": "cycle",
        "owner_ref": "cycle-7",
        "acquired_at": NOW,
        "expires_at": LATER,
        "renewal_policy": "ttl",
        "interruptibility": "high",
        "recall_policy": "graceful",
        "released_at": None,
        "idempotency_key": "key-1",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# request_lease — decision logic
# ---------------------------------------------------------------------------


async def test_request_lease_granted_when_no_current_lease():
    """Bug class: a clear agent must acquire focus. A new lease row is written and
    the decision echoes the requested expiry + the granted reason."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [None, None]  # no idempotent replay, no current lease
    conn.execute.return_value = "INSERT 0 1"
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease("max", "cycle", "cycle-7", "key-1", expires_at=LATER)

    assert isinstance(decision, LeaseGranted)
    assert decision.expires_at == LATER
    assert decision.reason_code == reasons.FOCUS_LEASE_GRANTED
    assert decision.lease_id  # a non-empty minted id
    conn.execute.assert_awaited_once()
    assert conn.execute.await_args.args[0].startswith("INSERT INTO focus_leases")


async def test_request_lease_rejected_when_equal_owner_holds():
    """Bug class: an equal/higher owner already holds focus — the request must be
    rejected with the holder's owner_ref, and (critically) NO second lease row may
    be written (single-active-lease invariant)."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [None, _lease_row(owner_type="cycle", owner_ref="cycle-held")]
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease("max", "cycle", "cycle-new", "key-new")

    assert isinstance(decision, LeaseRejected)
    assert decision.current_owner_ref == "cycle-held"
    assert decision.reason_code == reasons.FOCUS_LEASE_CONFLICT
    conn.execute.assert_not_awaited()  # no lease written on reject


async def test_request_lease_preempting_when_higher_owner_requests():
    """Bug class: a duty request against a cycle holder must PREEMPT (not reject,
    not auto-grant). It returns the grace + holder ref and writes nothing — the
    grace/revoke are the coordinator's explicit next steps."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [None, _lease_row(owner_type="cycle", owner_ref="cycle-held")]
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease(
        "max", "duty", "duty-3", "key-duty", preemption_grace=timedelta(minutes=2)
    )

    assert isinstance(decision, LeasePreempting)
    assert decision.current_owner_ref == "cycle-held"
    assert decision.preemption_grace == timedelta(minutes=2)
    assert decision.reason_code == reasons.FOCUS_LEASE_PREEMPTED
    conn.execute.assert_not_awaited()  # preemption does not write a lease


async def test_request_lease_idempotent_replay_returns_existing_without_insert():
    """Bug class (D12): a retried acquire with the same idempotency_key must
    return the ALREADY-granted lease, never mint a duplicate. The existing
    lease_id is returned and no INSERT is issued."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [_lease_row(lease_id="lease-existing", idempotency_key="key-1")]
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease("max", "cycle", "cycle-7", "key-1")

    assert isinstance(decision, LeaseGranted)
    assert decision.lease_id == "lease-existing"  # existing, not a new uuid
    conn.execute.assert_not_awaited()


async def test_request_lease_wait_policy_rejected_with_queueing_deferral():
    """Bug class (§3.0/D20): queueing is deferred to v1.2. A `wait=True` request
    that conflicts must be rejected with the explicit deferral reason, NOT silently
    queued or treated as a generic conflict."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [None, _lease_row(owner_type="cycle", owner_ref="cycle-held")]
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease("max", "cycle", "cycle-new", "key-new", wait=True)

    assert isinstance(decision, LeaseRejected)
    assert decision.reason_code == reasons.FOCUS_LEASE_QUEUEING_NOT_SUPPORTED
    assert decision.current_owner_ref == "cycle-held"


async def test_request_lease_lost_race_reresolves_to_conflict():
    """Bug class: the partial unique index rejects a second active lease. When the
    INSERT loses a race (UniqueViolation), the adapter must not crash — it
    re-resolves to a reject against the now-visible holder, upholding the
    single-active-lease invariant."""
    conn = AsyncMock()
    # key(None), current(None), [INSERT raises], replay-key(None), current(holder)
    conn.fetchrow.side_effect = [None, None, None, _lease_row(owner_ref="cycle-winner")]
    conn.execute.side_effect = asyncpg.UniqueViolationError("dup")
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease("max", "cycle", "cycle-loser", "key-loser")

    assert isinstance(decision, LeaseRejected)
    assert decision.current_owner_ref == "cycle-winner"
    assert decision.reason_code == reasons.FOCUS_LEASE_CONFLICT


async def test_request_lease_lost_race_reresolves_to_idempotent_grant():
    """Bug class: if the race was lost to OUR OWN concurrent replay (same key),
    re-resolution must return granted for that lease, not a spurious conflict."""
    conn = AsyncMock()
    # key(None), current(None), [INSERT raises], replay-key(matching active lease)
    conn.fetchrow.side_effect = [
        None,
        None,
        _lease_row(lease_id="lease-won", idempotency_key="key-x"),
    ]
    conn.execute.side_effect = asyncpg.UniqueViolationError("dup")
    adapter = PostgresFocusLease(_make_pool(conn))

    decision = await adapter.request_lease("max", "cycle", "cycle-7", "key-x")

    assert isinstance(decision, LeaseGranted)
    assert decision.lease_id == "lease-won"


# ---------------------------------------------------------------------------
# renew / release / revoke / get_current_lease
# ---------------------------------------------------------------------------


async def test_renew_lease_extends_expiry_for_active_lease():
    """Bug class: renew must advance expires_at and only ever touch an ACTIVE
    lease (the WHERE guards released_at IS NULL), returning True when one matched."""
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 1"
    adapter = PostgresFocusLease(_make_pool(conn))

    ok = await adapter.renew_lease("lease-1", expires_at=LATER)

    assert ok is True
    query = conn.execute.await_args.args[0]
    assert "expires_at = $2" in query
    assert "released_at IS NULL" in query
    assert conn.execute.await_args.args[2] == LATER


async def test_renew_lease_returns_false_when_no_active_lease_matched():
    """Bug class: renewing a released/unknown lease must report failure (False),
    not silently succeed — the caller needs to know the lease is gone."""
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 0"
    adapter = PostgresFocusLease(_make_pool(conn))

    assert await adapter.renew_lease("ghost", expires_at=LATER) is False


async def test_release_lease_marks_released_at_and_guards_active():
    """Bug class: release must free the slot by setting released_at, and only on
    a still-active lease (idempotent guard), never bumping acquired_at/owner."""
    conn = AsyncMock()
    adapter = PostgresFocusLease(_make_pool(conn))

    await adapter.release_lease("lease-1", reasons.FOCUS_LEASE_RELEASED)

    query = conn.execute.await_args.args[0]
    assert "released_at = now()" in query
    assert "released_at IS NULL" in query


async def test_revoke_lease_marks_released_at_non_cooperative():
    """Bug class: revoke (preemption path) must also free the active-lease slot.
    Its storage effect matches release; the audit distinction is the caller's
    reason/event, so the SQL must still set released_at on the active lease."""
    conn = AsyncMock()
    adapter = PostgresFocusLease(_make_pool(conn))

    await adapter.revoke_lease("lease-1", reasons.FOCUS_LEASE_PREEMPTED)

    query = conn.execute.await_args.args[0]
    assert "released_at = now()" in query
    assert "released_at IS NULL" in query


async def test_get_current_lease_returns_none_when_no_active_row():
    """Bug class: callers must distinguish 'no active lease' from a default lease.
    A missing row yields None, not a synthesized lease."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    adapter = PostgresFocusLease(_make_pool(conn))

    assert await adapter.get_current_lease("idle-agent") is None


async def test_get_current_lease_maps_row_to_dataclass():
    """Bug class: a row→dataclass mapper that drops/renames a field would degrade
    lease observability without failing. Assert the full mapping incl. released_at
    null and idempotency_key."""
    conn = AsyncMock()
    conn.fetchrow.return_value = _lease_row(
        lease_id="lease-9", owner_type="duty", owner_ref="duty-1"
    )
    adapter = PostgresFocusLease(_make_pool(conn))

    lease = await adapter.get_current_lease("max")

    assert lease == FocusLease(
        lease_id="lease-9",
        agent_id="max",
        owner_type="duty",
        owner_ref="duty-1",
        acquired_at=NOW,
        expires_at=LATER,
        renewal_policy="ttl",
        interruptibility="high",
        recall_policy="graceful",
        released_at=None,
        idempotency_key="key-1",
    )
    # current-lease lookup must filter to the active row.
    assert "released_at IS NULL" in conn.fetchrow.await_args.args[0]
