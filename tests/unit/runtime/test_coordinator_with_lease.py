"""Unit tests for SIP-0089 §3.4 — RuntimeCoordinator wired to FocusLease.

Bug classes guarded:
- the coordinator writing `mode` without first securing the target owner's lease
  (lease ≠ mode), or letting a lease rejection silently apply the mode anyway;
- a granted lease outliving a FAILED mode write — a *stranded lease* that blocks
  the agent forever (the load-bearing regression, §3.6);
- preemption not revoking the displaced holder, or not emitting the distinct
  focus_lease.* events (D18) for granted / rejected / preempted / released.

Uses an in-memory `FocusLeasePort` fake that behaves like the real store
(grant-when-free, precedence-based preempt/reject, release/revoke clear the slot)
so assertions are on the coordinator's orchestration, not on mock call shapes.
The adapter's own decision logic is covered separately in `test_focus_lease.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.focus_lease import FocusLeasePort
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.coordinator import RuntimeCoordinator
from squadops.runtime.models import (
    AgentRuntimeState,
    FocusLease,
    LeaseGranted,
    LeasePreempting,
    LeaseRejected,
    owner_type_outranks,
)

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 28, 1, 0, tzinfo=UTC)


def _state(mode="ambient", runtime_status="online", assignment_ref=None) -> AgentRuntimeState:
    return AgentRuntimeState(
        agent_id="max",
        mode=mode,
        runtime_status=runtime_status,
        focus="",
        current_runtime_activity_id=None,
        interruptibility="high",
        last_heartbeat_at=NOW,
        current_assignment_ref=assignment_ref,
    )


class _FakeStatePort(RuntimeStatePort):
    def __init__(self, initial: AgentRuntimeState, *, fail_upsert: bool = False) -> None:
        self._rows: dict[str, AgentRuntimeState] = {initial.agent_id: initial}
        self.upserts: list[AgentRuntimeState] = []
        self.fail_upsert = fail_upsert

    async def get_state(self, agent_id):
        return self._rows.get(agent_id)

    async def upsert_state(self, state, *, conn=None):
        if self.fail_upsert:
            raise RuntimeError("simulated mode-write failure")
        self._rows[state.agent_id] = state
        self.upserts.append(state)
        return state

    async def ensure_state(self, agent_id):
        return self._rows[agent_id]

    async def update_heartbeat(self, agent_id, *, runtime_status=None):
        return self._rows[agent_id]

    async def mark_offline(self, agent_id):
        return self._rows.get(agent_id)


class _FakeFocusLease(FocusLeasePort):
    """In-memory FocusLeasePort mirroring the real store's resolution rules."""

    def __init__(self) -> None:
        self._active: dict[str, FocusLease] = {}
        self._counter = 0
        self.released: list[str] = []
        self.revoked: list[str] = []

    def seed(self, agent_id: str, owner_type: str, owner_ref: str) -> FocusLease:
        self._counter += 1
        lease = FocusLease(
            lease_id=f"seed-{self._counter}",
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
        self._active[agent_id] = lease
        return lease

    async def request_lease(
        self,
        agent_id,
        owner_type,
        owner_ref,
        idempotency_key,
        *,
        expires_at=None,
        renewal_policy="ttl",
        interruptibility="high",
        recall_policy="graceful",
        preemption_grace=timedelta(),
        wait=False,
        conn=None,
    ):
        cur = self._active.get(agent_id)
        if cur is not None:
            if cur.idempotency_key == idempotency_key:
                return LeaseGranted(cur.lease_id, cur.expires_at, reasons.FOCUS_LEASE_GRANTED)
            if owner_type_outranks(owner_type, cur.owner_type):
                return LeasePreempting(
                    cur.owner_ref, preemption_grace, reasons.FOCUS_LEASE_PREEMPTED
                )
            if wait:
                return LeaseRejected(cur.owner_ref, reasons.FOCUS_LEASE_QUEUEING_NOT_SUPPORTED)
            return LeaseRejected(cur.owner_ref, reasons.FOCUS_LEASE_CONFLICT)
        self._counter += 1
        lease_id = f"lease-{self._counter}"
        self._active[agent_id] = FocusLease(
            lease_id=lease_id,
            agent_id=agent_id,
            owner_type=owner_type,
            owner_ref=owner_ref,
            acquired_at=NOW,
            expires_at=expires_at,
            renewal_policy=renewal_policy,
            interruptibility=interruptibility,
            recall_policy=recall_policy,
            released_at=None,
            idempotency_key=idempotency_key,
        )
        return LeaseGranted(lease_id, expires_at, reasons.FOCUS_LEASE_GRANTED)

    async def renew_lease(self, lease_id, *, expires_at=None):
        return True

    async def release_lease(self, lease_id, reason_code, *, conn=None):
        self.released.append(lease_id)
        self._drop(lease_id)

    async def revoke_lease(self, lease_id, reason_code, *, conn=None):
        self.revoked.append(lease_id)
        self._drop(lease_id)

    async def get_current_lease(self, agent_id, *, conn=None):
        return self._active.get(agent_id)

    def _drop(self, lease_id):
        for aid, lease in list(self._active.items()):
            if lease.lease_id == lease_id:
                del self._active[aid]


class _RecordingPublisher(RuntimeEventPublisher):
    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, event_name, *, agent_id, reason_code, payload=None):
        self.emitted.append((event_name, agent_id, reason_code, payload))

    def names(self) -> list[str]:
        return [e[0] for e in self.emitted]

    def reason_for(self, event_name: str) -> str:
        return next(e[2] for e in self.emitted if e[0] == event_name)


# ---------------------------------------------------------------------------
# granted / rejected / preempted / released
# ---------------------------------------------------------------------------


async def test_ambient_to_cycle_acquires_lease_and_emits_granted():
    """Bug class: entering cycle must secure a cycle lease AND write mode. The
    lease is held for the cycle owner and focus_lease.granted is emitted with the
    granted reason (event name ≠ reason, D18)."""
    state = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    fl = _FakeFocusLease()
    coord = RuntimeCoordinator(state, events_publisher=pub, focus_lease=fl)

    outcome = await coord.request_transition(
        "max", "cycle", reasons.CYCLE_RECRUITED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert outcome.applied is True
    assert state.upserts[-1].mode == "cycle"
    lease = await fl.get_current_lease("max")
    assert lease is not None and lease.owner_type == "cycle" and lease.owner_ref == "cyc-1"
    assert events.FOCUS_LEASE_GRANTED in pub.names()
    assert pub.reason_for(events.FOCUS_LEASE_GRANTED) == reasons.FOCUS_LEASE_GRANTED
    assert events.FOCUS_LEASE_GRANTED != reasons.FOCUS_LEASE_GRANTED  # D18


async def test_lease_rejection_blocks_transition_without_writing_mode():
    """Bug class (lease = hard gate): an agent still bound by a non-preemptable
    lease (a stale duty lease) must NOT be recruited into cycle. The transition is
    rejected, mode stays ambient, no upsert happens, focus_lease.rejected emits."""
    state = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    fl = _FakeFocusLease()
    fl.seed("max", "duty", "duty-held")  # duty outranks the requested cycle
    coord = RuntimeCoordinator(state, events_publisher=pub, focus_lease=fl)

    outcome = await coord.request_transition(
        "max", "cycle", reasons.CYCLE_RECRUITED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.FOCUS_LEASE_CONFLICT
    assert state.upserts == []  # mode never written
    assert (await state.get_state("max")).mode == "ambient"
    assert events.MODE_TRANSITION not in pub.names()
    assert pub.reason_for(events.FOCUS_LEASE_REJECTED) == reasons.FOCUS_LEASE_CONFLICT


async def test_cycle_to_duty_preempts_holder_and_emits_preempted_and_granted():
    """Bug class: a duty window opening while the agent is mid-cycle must PREEMPT
    the cycle lease (revoke it), acquire the duty lease, and switch mode to duty.
    Both focus_lease.preempted and focus_lease.granted are emitted."""
    state = _FakeStatePort(_state(mode="cycle", assignment_ref=None))
    pub = _RecordingPublisher()
    fl = _FakeFocusLease()
    cycle_lease = fl.seed("max", "cycle", "cyc-1")
    coord = RuntimeCoordinator(state, events_publisher=pub, focus_lease=fl)

    outcome = await coord.request_transition(
        "max",
        "duty",
        reasons.DUTY_WINDOW_OPENED,
        requester_kind="scheduler",
        owner_ref="duty-1",
        assignment_id="assign-1",
    )

    assert outcome.applied is True
    assert state.upserts[-1].mode == "duty"
    assert cycle_lease.lease_id in fl.revoked  # displaced holder revoked
    held = await fl.get_current_lease("max")
    assert held is not None and held.owner_type == "duty"
    assert events.FOCUS_LEASE_PREEMPTED in pub.names()
    assert events.FOCUS_LEASE_GRANTED in pub.names()
    assert pub.reason_for(events.FOCUS_LEASE_PREEMPTED) == reasons.FOCUS_LEASE_PREEMPTED


async def test_duty_to_ambient_releases_lease_after_mode_write():
    """Bug class: leaving duty for ambient must release the duty lease (free the
    slot) and emit focus_lease.released. Release happens cooperatively, not as a
    preemption (it must NOT appear in revoked)."""
    state = _FakeStatePort(_state(mode="duty", assignment_ref="assign-1"))
    pub = _RecordingPublisher()
    fl = _FakeFocusLease()
    duty_lease = fl.seed("max", "duty", "duty-1")
    coord = RuntimeCoordinator(state, events_publisher=pub, focus_lease=fl)

    outcome = await coord.request_transition(
        "max", "ambient", reasons.DUTY_WINDOW_CLOSED, requester_kind="scheduler", owner_ref="duty-1"
    )

    assert outcome.applied is True
    assert state.upserts[-1].mode == "ambient"
    assert duty_lease.lease_id in fl.released
    assert duty_lease.lease_id not in fl.revoked  # cooperative, not preemption
    assert await fl.get_current_lease("max") is None
    assert events.FOCUS_LEASE_RELEASED in pub.names()


# ---------------------------------------------------------------------------
# lease ≠ mode + rollback (the load-bearing regression)
# ---------------------------------------------------------------------------


async def test_failed_mode_write_rolls_back_acquired_lease():
    """Bug class (load-bearing, §3.6): a lease acquired for the transition must be
    rolled back when the mode write fails — otherwise it strands and blocks the
    agent forever. Asserts lease ≠ mode too: the grant alone does NOT advance
    mode; after the failed write the agent is still ambient and holds no lease."""
    state = _FakeStatePort(_state(mode="ambient"), fail_upsert=True)
    pub = _RecordingPublisher()
    fl = _FakeFocusLease()
    coord = RuntimeCoordinator(state, events_publisher=pub, focus_lease=fl)

    with pytest.raises(RuntimeError, match="simulated mode-write failure"):
        await coord.request_transition(
            "max", "cycle", reasons.CYCLE_RECRUITED, requester_kind="coordinator", owner_ref="cyc-1"
        )

    # No stranded lease, and mode never advanced (lease ≠ mode).
    assert await fl.get_current_lease("max") is None
    assert len(fl.released) == 1  # the just-acquired lease was released
    assert (await state.get_state("max")).mode == "ambient"
    # We rolled back, so we must not have announced a grant or a transition.
    assert events.FOCUS_LEASE_GRANTED not in pub.names()
    assert events.MODE_TRANSITION not in pub.names()


async def test_no_lease_port_preserves_phase2_behavior():
    """Bug class: focus_lease=None must keep the Phase-2 coordinator behavior
    exactly — a plain mode write with no lease events."""
    state = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(state, events_publisher=pub)  # no focus_lease

    outcome = await coord.request_transition(
        "max", "cycle", reasons.CYCLE_RECRUITED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert outcome.applied is True and state.upserts[-1].mode == "cycle"
    assert pub.names() == [events.MODE_TRANSITION]  # no focus_lease.* events
