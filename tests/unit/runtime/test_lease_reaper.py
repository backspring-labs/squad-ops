"""Tests for the stranded-lease sweeps (#373/#529 — `runtime.lease_reaper`).

Bug classes guarded:
- the startup reaper releasing a lease whose owning run is still live — would
  yank focus out from under an executing cycle;
- `duty` leases swept by a run-shaped predicate: their ``owner_ref`` is an
  assignment id, so "no such run" would read as terminal and kill a live duty
  window;
- releasing the lease without returning the agent to `ambient` — the agent stays
  pinned in `cycle`, where the next recruitment takes the #288 same-mode path,
  finds no conflicting lease, and *idempotently skips*: admitted without
  acquiring, then lost mid-run when the real owner finalizes;
- the residue case the coordinator cannot express (agent already `ambient`, lease
  still held) leaving the lease held forever — the exact shape #373 observed;
- one bad row (predicate, transition, or release failure) aborting the sweep, so
  the remaining stranded leases never clear;
- the cancel sweep reaching beyond its own owner and releasing a concurrent
  run's leases;
- counting attempted rather than actually-cleared rows, and stealing a slot a
  new owner re-acquired mid-sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.ports.runtime.focus_lease import FocusLeasePort
from squadops.runtime import reasons
from squadops.runtime.lease_reaper import reap_stale_leases, release_owner_leases
from squadops.runtime.models import FocusLease

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 8, 4, tzinfo=UTC)


def _lease(lease_id="lease-1", agent_id="max", owner_ref="run_1", owner_type="cycle") -> FocusLease:
    return FocusLease(
        lease_id=lease_id,
        agent_id=agent_id,
        owner_type=owner_type,  # type: ignore[arg-type]
        owner_ref=owner_ref,
        acquired_at=NOW,
        expires_at=None,
        renewal_policy="ttl",
        interruptibility="high",
        recall_policy="graceful",
        released_at=None,
        idempotency_key=f"{owner_type}:{owner_ref}:{agent_id}",
    )


class _FakeLeaseStore(FocusLeasePort):
    """In-memory lease store keyed by agent (the §3.2 one-active-per-agent rule)."""

    def __init__(
        self,
        leases: tuple[FocusLease, ...] = (),
        *,
        release_raises_for: frozenset[str] = frozenset(),
    ) -> None:
        self._active: dict[str, FocusLease] = {lease.agent_id: lease for lease in leases}
        self._release_raises_for = release_raises_for
        self.released: list[tuple[str, str]] = []
        self.list_calls: list[str | None] = []

    async def request_lease(self, agent_id, owner_type, owner_ref, idempotency_key, **kwargs):
        raise NotImplementedError  # unused here

    async def renew_lease(self, lease_id, *, expires_at=None):
        raise NotImplementedError  # unused here

    async def release_lease(self, lease_id, reason_code, *, conn=None):
        if lease_id in self._release_raises_for:
            raise RuntimeError("db down")
        self.released.append((lease_id, reason_code))
        for agent_id, lease in list(self._active.items()):
            if lease.lease_id == lease_id:
                del self._active[agent_id]

    async def revoke_lease(self, lease_id, reason_code, *, conn=None):
        await self.release_lease(lease_id, reason_code)

    async def get_current_lease(self, agent_id, *, conn=None):
        return self._active.get(agent_id)

    async def list_active_leases(self, *, owner_ref=None, conn=None):
        self.list_calls.append(owner_ref)
        leases = sorted(self._active.values(), key=lambda lease: lease.lease_id)
        if owner_ref is not None:
            leases = [lease for lease in leases if lease.owner_ref == owner_ref]
        return tuple(leases)

    def replace_slot(self, agent_id: str, lease: FocusLease) -> None:
        """Simulate a concurrent owner re-acquiring the agent's slot."""
        self._active[agent_id] = lease


class _FakeCoordinator:
    """Coordinator stand-in with the real ambient-transition semantics.

    Leaving `cycle` writes ambient and releases the leaving-mode lease (§3.4);
    an agent already `ambient` is a same-mode idempotent skip that never reaches
    lease arbitration — the case that leaves the residue.
    """

    def __init__(
        self,
        store: _FakeLeaseStore,
        modes: dict[str, str] | None = None,
        *,
        raises_for: frozenset[str] = frozenset(),
    ) -> None:
        self._store = store
        self._modes = modes if modes is not None else {}
        self._raises_for = raises_for
        self.transitions: list[tuple[str, str, str]] = []

    async def request_transition(
        self, agent_id, target_mode, reason_code, *, requester_kind, owner_ref, **kwargs
    ):
        if agent_id in self._raises_for:
            raise RuntimeError("coordinator down")
        self.transitions.append((agent_id, target_mode, reason_code))
        if self._modes.get(agent_id, "cycle") == target_mode:
            return None  # same-mode idempotent skip: the lease is left held
        self._modes[agent_id] = target_mode
        held = await self._store.get_current_lease(agent_id)
        if held is not None:
            await self._store.release_lease(held.lease_id, reasons.FOCUS_LEASE_RELEASED)
        return None

    def mode_of(self, agent_id: str) -> str:
        return self._modes.get(agent_id, "cycle")


def _terminal_only(terminal_runs: set[str], *, raises_for: set[str] | None = None):
    async def owner_is_finished(run_id: str) -> bool:
        if raises_for and run_id in raises_for:
            raise RuntimeError("registry down")
        return run_id in terminal_runs

    return owner_is_finished


# ---------------------------------------------------------------------------
# reap_stale_leases (startup)
# ---------------------------------------------------------------------------


async def test_reap_clears_terminal_run_leases_and_spares_live_ones():
    store = _FakeLeaseStore(
        (
            _lease("lease-dead", agent_id="max", owner_ref="run_dead"),
            _lease("lease-live", agent_id="neo", owner_ref="run_live"),
        )
    )
    coordinator = _FakeCoordinator(store)

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=_terminal_only({"run_dead"}),
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 1
    assert await store.get_current_lease("max") is None
    live = await store.get_current_lease("neo")
    assert live is not None and live.lease_id == "lease-live"
    assert coordinator.transitions == [("max", "ambient", reasons.LEASE_STRANDED_AT_STARTUP)]


async def test_reap_never_touches_duty_leases():
    """A duty lease's owner_ref is an assignment id, not a run id — a run-shaped
    predicate would answer "no such run → terminal" and revoke a live window."""
    store = _FakeLeaseStore(
        (_lease("lease-duty", agent_id="eve", owner_ref="asn_7", owner_type="duty"),)
    )
    coordinator = _FakeCoordinator(store)
    predicate_calls: list[str] = []

    async def owner_is_finished(owner_ref: str) -> bool:
        predicate_calls.append(owner_ref)
        return True

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=owner_is_finished,
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 0
    assert predicate_calls == []  # skipped before the predicate is even asked
    assert (await store.get_current_lease("eve")).lease_id == "lease-duty"
    assert coordinator.transitions == []


async def test_reap_returns_the_agent_to_ambient():
    """Releasing the lease alone leaves mode=cycle, where the next recruitment
    #288-idempotently skips and free-rides instead of acquiring."""
    store = _FakeLeaseStore((_lease("lease-1", agent_id="max", owner_ref="run_dead"),))
    coordinator = _FakeCoordinator(store, {"max": "cycle"})

    await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=_terminal_only({"run_dead"}),
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert coordinator.mode_of("max") == "ambient"


async def test_lease_left_held_by_the_transition_is_released_directly():
    """#373's observed residue: the mode write committed and the release did not,
    so the agent is already `ambient` — a same-mode skip that never reaches lease
    arbitration. Nothing but a direct release can clear it."""
    store = _FakeLeaseStore((_lease("lease-orphan", agent_id="max", owner_ref="run_dead"),))
    coordinator = _FakeCoordinator(store, {"max": "ambient"})

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=_terminal_only({"run_dead"}),
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 1
    assert store.released == [("lease-orphan", reasons.LEASE_STRANDED_AT_STARTUP)]
    assert await store.get_current_lease("max") is None


async def test_predicate_failure_skips_only_that_row():
    store = _FakeLeaseStore(
        (
            _lease("lease-a", agent_id="max", owner_ref="run_boom"),
            _lease("lease-b", agent_id="neo", owner_ref="run_dead"),
        )
    )
    coordinator = _FakeCoordinator(store)

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=_terminal_only({"run_dead"}, raises_for={"run_boom"}),
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 1
    assert (await store.get_current_lease("max")).lease_id == "lease-a"  # untouched
    assert await store.get_current_lease("neo") is None


async def test_transition_failure_still_releases_the_lease():
    """A coordinator error must not leave the lease held — the whole point of the
    sweep is that a blocked slot is worse than a stale mode."""
    store = _FakeLeaseStore((_lease("lease-1", agent_id="max", owner_ref="run_dead"),))
    coordinator = _FakeCoordinator(store, raises_for=frozenset({"max"}))

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=_terminal_only({"run_dead"}),
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 1
    assert store.released == [("lease-1", reasons.LEASE_STRANDED_AT_STARTUP)]


async def test_release_failure_is_not_counted_and_does_not_stop_the_sweep():
    store = _FakeLeaseStore(
        (
            _lease("lease-stuck", agent_id="max", owner_ref="run_dead"),
            _lease("lease-ok", agent_id="neo", owner_ref="run_dead"),
        ),
        release_raises_for=frozenset({"lease-stuck"}),
    )
    coordinator = _FakeCoordinator(store, {"max": "ambient", "neo": "ambient"})

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=_terminal_only({"run_dead"}),
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 1  # only the row that actually cleared
    assert (await store.get_current_lease("max")).lease_id == "lease-stuck"
    assert await store.get_current_lease("neo") is None


async def test_a_reacquired_slot_counts_as_cleared_and_is_left_alone():
    """Our lease was released and a new owner took the slot mid-sweep. Releasing
    *that* lease would strand the run that just recruited."""
    store = _FakeLeaseStore((_lease("lease-old", agent_id="max", owner_ref="run_dead"),))
    coordinator = _FakeCoordinator(store, {"max": "ambient"})
    successor = _lease("lease-new", agent_id="max", owner_ref="run_new")

    async def owner_is_finished(run_id: str) -> bool:
        store.replace_slot("max", successor)  # a concurrent recruit wins the slot
        return True

    reaped = await reap_stale_leases(
        coordinator,
        store,
        owner_is_finished=owner_is_finished,
        reason_code=reasons.LEASE_STRANDED_AT_STARTUP,
    )

    assert reaped == 1
    assert store.released == []  # nothing released — the old lease was already gone
    assert (await store.get_current_lease("max")).lease_id == "lease-new"


# ---------------------------------------------------------------------------
# release_owner_leases (cancel / run finalize)
# ---------------------------------------------------------------------------


async def test_release_owner_leases_clears_only_the_named_owner():
    """Cancelling one run must not take down a concurrent run's leases."""
    store = _FakeLeaseStore(
        (
            _lease("lease-mine", agent_id="max", owner_ref="run_cancelled"),
            _lease("lease-theirs", agent_id="neo", owner_ref="run_other"),
        )
    )
    coordinator = _FakeCoordinator(store)

    released = await release_owner_leases(
        coordinator, store, "run_cancelled", reason_code=reasons.LEASE_STRANDED_AT_CANCEL
    )

    assert released == 1
    assert store.list_calls == ["run_cancelled"]  # narrowed at the query, not in Python
    assert await store.get_current_lease("max") is None
    assert (await store.get_current_lease("neo")).lease_id == "lease-theirs"
    assert coordinator.transitions == [("max", "ambient", reasons.LEASE_STRANDED_AT_CANCEL)]


async def test_release_owner_leases_clears_every_agent_the_run_holds():
    """#529's shape: a cancelled run holds one lease per recruited agent, and a
    single leftover blocks the next cycle just as hard as five."""
    store = _FakeLeaseStore(
        tuple(
            _lease(f"lease-{agent}", agent_id=agent, owner_ref="run_cancelled")
            for agent in ("data", "eve", "max", "nat", "neo")
        )
    )
    coordinator = _FakeCoordinator(store)

    released = await release_owner_leases(
        coordinator, store, "run_cancelled", reason_code=reasons.LEASE_STRANDED_AT_CANCEL
    )

    assert released == 5
    assert await store.list_active_leases() == ()


async def test_release_owner_leases_ignores_a_duty_lease_sharing_the_owner_ref():
    store = _FakeLeaseStore(
        (
            _lease("lease-cycle", agent_id="max", owner_ref="run_1"),
            _lease("lease-duty", agent_id="neo", owner_ref="run_1", owner_type="duty"),
        )
    )
    coordinator = _FakeCoordinator(store)

    released = await release_owner_leases(
        coordinator, store, "run_1", reason_code=reasons.LEASE_STRANDED_AT_CANCEL
    )

    assert released == 1
    assert (await store.get_current_lease("neo")).lease_id == "lease-duty"


async def test_release_owner_leases_on_an_owner_holding_nothing_is_a_noop():
    store = _FakeLeaseStore((_lease("lease-1", agent_id="max", owner_ref="run_other"),))
    coordinator = _FakeCoordinator(store)

    released = await release_owner_leases(
        coordinator, store, "run_gone", reason_code=reasons.LEASE_STRANDED_AT_RUN_FINALIZE
    )

    assert released == 0
    assert coordinator.transitions == []
    assert store.released == []
