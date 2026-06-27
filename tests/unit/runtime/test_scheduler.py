"""Unit tests for SIP-0089 §2.4 — DutyScheduler.

Bug classes guarded:
- the scheduler writing AgentRuntimeState directly instead of requesting via the
  coordinator (violates D21 claimant-not-authority);
- window-open / window-close firing at the wrong window_state boundary;
- MissedWindowPolicy mis-enacted (a missed hard duty silently opening, or a
  within-grace late start being skipped);
- the scheduler polling on construction (must be started explicitly — D-note in
  §2.4 forbids implicit background activation in tests);
- repeated ticks within one window duplicating the open transition (D12/D21).

Fakes (recording coordinator + controllable state) keep assertions on what the
scheduler *requests*, not on a live coordinator's side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.coordinator import RuntimeCoordinator, TransitionOutcome
from squadops.runtime.models import AgentRuntimeState, Assignment, DutyWindow
from squadops.runtime.scheduler import DutyScheduler

pytestmark = [pytest.mark.domain_runtime]

WIN_START = datetime(2026, 6, 24, 1, 0, tzinfo=UTC)
WIN_END = datetime(2026, 6, 24, 6, 0, tzinfo=UTC)


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 24, hour, minute, tzinfo=UTC)


def _duty(
    *,
    policy: str = "skip",
    graceful: timedelta = timedelta(minutes=5),
    assignment_type: str = "duty",
) -> Assignment:
    return Assignment(
        assignment_id="assign-1",
        agent_id="max",
        assignment_type=assignment_type,  # type: ignore[arg-type]
        assigned_role="support",
        priority=10,
        strictness="hard",
        active_window=DutyWindow(start=WIN_START, end=WIN_END, timezone="UTC"),
        reserve_before_window=timedelta(minutes=15),
        reserve_after_window=timedelta(minutes=10),
        recall_policy="graceful",
        graceful_window=graceful,
        missed_window_policy=policy,  # type: ignore[arg-type]
        allowed_off_window_modes=("ambient", "cycle"),
    )


def _agent_state(mode="ambient", assignment_ref=None) -> AgentRuntimeState:
    return AgentRuntimeState("max", mode, "online", "", None, "high", WIN_START, assignment_ref)


class _FakeAssignments:
    def __init__(self, items: list[Assignment], to_close: list[Assignment] | None = None) -> None:
        self._items = items
        self._to_close = to_close or []
        self.calls = 0

    async def list_active_assignments(self, now):
        self.calls += 1
        return list(self._items)

    async def list_assignments_to_close(self, now):
        return list(self._to_close)


class _RecordingCoordinator:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def request_transition(self, agent_id, target_mode, reason_code, **kwargs):
        self.requests.append(
            {"agent_id": agent_id, "target_mode": target_mode, "reason_code": reason_code, **kwargs}
        )
        return TransitionOutcome(
            applied=True,
            agent_id=agent_id,
            from_mode=None,
            to_mode=target_mode,
            reason_code=reason_code,
            event_name=events.MODE_TRANSITION,
        )


class _FakeStatePort(RuntimeStatePort):
    def __init__(self, initial: AgentRuntimeState | None = None) -> None:
        self._row = initial
        self.upserts: list[AgentRuntimeState] = []

    async def get_state(self, agent_id):
        return self._row

    async def upsert_state(self, state):
        self._row = state
        self.upserts.append(state)
        return state

    async def ensure_state(self, agent_id):
        if self._row is None:
            self._row = _agent_state()
        return self._row

    async def update_heartbeat(self, agent_id, *, runtime_status=None):
        return await self.ensure_state(agent_id)

    async def mark_offline(self, agent_id):  # unused here
        return self._row


class _RecordingPublisher(RuntimeEventPublisher):
    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, event_name, *, agent_id, reason_code, payload=None):
        self.emitted.append((event_name, agent_id, reason_code, payload))


async def test_window_open_fires_on_time():
    coord = _RecordingCoordinator()
    sched = DutyScheduler(_FakeAssignments([_duty()]), coord, _FakeStatePort(None))

    await sched.tick(now=WIN_START)

    assert len(coord.requests) == 1
    r = coord.requests[0]
    assert (r["target_mode"], r["reason_code"]) == ("duty", reasons.DUTY_WINDOW_OPENED)
    assert r["scheduled_at"] == WIN_START
    assert r["assignment_id"] == "assign-1"
    assert r["requester_kind"] == "scheduler"


async def test_window_close_fires_for_serving_agent_after_window():
    coord = _RecordingCoordinator()
    state = _FakeStatePort(_agent_state(mode="duty", assignment_ref="assign-1"))
    sched = DutyScheduler(_FakeAssignments([_duty()]), coord, state)

    await sched.tick(now=_at(6, 5))  # in_reserve_after, agent serving

    assert len(coord.requests) == 1
    r = coord.requests[0]
    assert (r["target_mode"], r["reason_code"]) == ("ambient", reasons.DUTY_WINDOW_CLOSED)
    assert r["scheduled_at"] == WIN_END


async def test_close_sweep_fires_after_assignment_leaves_active_set():
    """Bug class (#226): with reserve_after=0 a served window leaves the active
    set at window_end, so pass 1 never observes in_reserve_after and the agent
    would stay stuck in duty. The close-sweep (pass 2) must still request the
    duty->ambient close, scheduled at window_end, for an agent still in duty —
    even when the active set is empty."""
    coord = _RecordingCoordinator()
    state = _FakeStatePort(_agent_state(mode="duty", assignment_ref="assign-1"))
    # Active set empty (assignment dropped out at window_end); close-sweep returns it.
    sched = DutyScheduler(_FakeAssignments([], to_close=[_duty()]), coord, state)

    await sched.tick(now=_at(7, 0))  # well past window_end

    assert len(coord.requests) == 1
    r = coord.requests[0]
    assert (r["target_mode"], r["reason_code"]) == ("ambient", reasons.DUTY_WINDOW_CLOSED)
    assert r["scheduled_at"] == WIN_END
    assert r["assignment_id"] == "assign-1"
    assert state.upserts == []  # D21: requested via coordinator, never written directly


async def test_close_sweep_empty_requests_no_transition():
    """Bug class: the close-sweep must not invent closes. With nothing to close
    (and no active assignments) the tick requests nothing, even though an agent
    row exists in duty — closing is driven by the sweep query, not by state."""
    coord = _RecordingCoordinator()
    state = _FakeStatePort(_agent_state(mode="duty", assignment_ref="assign-1"))
    sched = DutyScheduler(_FakeAssignments([], to_close=[]), coord, state)

    outcomes = await sched.tick(now=_at(7, 0))

    assert outcomes == [] and coord.requests == []


async def test_scheduler_never_writes_state_directly():
    """D21: the scheduler may read state but only the coordinator writes it."""
    coord = _RecordingCoordinator()
    state = _FakeStatePort(None)
    sched = DutyScheduler(_FakeAssignments([_duty()]), coord, state)

    await sched.tick(now=WIN_START)

    assert state.upserts == []  # scheduler requested, never wrote
    assert len(coord.requests) == 1


async def test_non_duty_assignment_is_ignored():
    coord = _RecordingCoordinator()
    sched = DutyScheduler(
        _FakeAssignments([_duty(assignment_type="cycle_eligibility")]),
        coord,
        _FakeStatePort(None),
    )

    outcomes = await sched.tick(now=WIN_START)

    assert outcomes == [] and coord.requests == []


async def test_construction_does_not_poll():
    """No implicit background activation — only start() polls."""
    provider = _FakeAssignments([_duty()])
    DutyScheduler(provider, _RecordingCoordinator(), _FakeStatePort(None))

    assert provider.calls == 0


async def test_late_start_within_grace_opens_late():
    coord = _RecordingCoordinator()
    sched = DutyScheduler(
        _FakeAssignments([_duty(policy="start_late_within_grace", graceful=timedelta(minutes=5))]),
        coord,
        _FakeStatePort(None),
    )

    await sched.tick(now=_at(1, 3))  # 3 min late, within 5-min grace

    assert len(coord.requests) == 1
    assert coord.requests[0]["reason_code"] == reasons.DUTY_WINDOW_STARTED_LATE
    assert coord.requests[0]["target_mode"] == "duty"


async def test_late_start_past_grace_skips_even_under_start_late_policy():
    coord = _RecordingCoordinator()
    pub = _RecordingPublisher()
    sched = DutyScheduler(
        _FakeAssignments([_duty(policy="start_late_within_grace", graceful=timedelta(minutes=5))]),
        coord,
        _FakeStatePort(None),
        events_publisher=pub,
    )

    await sched.tick(now=_at(1, 10))  # 10 min late, past grace

    assert coord.requests == []  # no transition
    assert pub.emitted[0][0] == events.ASSIGNMENT_WINDOW_SKIPPED
    assert pub.emitted[0][2] == reasons.DUTY_WINDOW_MISSED


async def test_skip_policy_does_not_open_late_window():
    coord = _RecordingCoordinator()
    pub = _RecordingPublisher()
    sched = DutyScheduler(
        _FakeAssignments([_duty(policy="skip")]),
        coord,
        _FakeStatePort(None),
        events_publisher=pub,
    )

    await sched.tick(now=_at(1, 1))  # 1 min late

    assert coord.requests == []
    assert pub.emitted[0][0] == events.ASSIGNMENT_WINDOW_SKIPPED


async def test_require_operator_review_flags_instead_of_transitioning():
    coord = _RecordingCoordinator()
    pub = _RecordingPublisher()
    sched = DutyScheduler(
        _FakeAssignments([_duty(policy="require_operator_review")]),
        coord,
        _FakeStatePort(None),
        events_publisher=pub,
    )

    await sched.tick(now=_at(1, 10))

    assert coord.requests == []
    assert pub.emitted[0][0] == events.ASSIGNMENT_WINDOW_REVIEW_REQUIRED
    assert pub.emitted[0][2] == reasons.DUTY_WINDOW_MISSED_OPERATOR_REVIEW


async def test_missed_window_after_end_enacts_skip():
    coord = _RecordingCoordinator()
    pub = _RecordingPublisher()
    sched = DutyScheduler(
        _FakeAssignments([_duty(policy="skip")]),
        coord,
        _FakeStatePort(None),
        events_publisher=pub,
    )

    await sched.tick(now=_at(6, 5))  # past window end, never entered → missed

    assert coord.requests == []
    assert pub.emitted[0][0] == events.ASSIGNMENT_WINDOW_SKIPPED
    assert pub.emitted[0][2] == reasons.DUTY_WINDOW_MISSED


async def test_repeated_ticks_open_window_exactly_once_with_real_coordinator():
    """D12/D21 end-to-end: two ticks within the same window → one open. The first
    applies; the second sees the agent already on duty (and the coordinator's
    idempotency key would also dedupe), so no second transition is written."""
    state = _FakeStatePort(_agent_state(mode="ambient"))
    coord = RuntimeCoordinator(state, events_publisher=_RecordingPublisher())
    sched = DutyScheduler(_FakeAssignments([_duty()]), coord, state)

    await sched.tick(now=WIN_START)
    await sched.tick(now=_at(1, 1))

    duty_upserts = [s for s in state.upserts if s.mode == "duty"]
    assert len(duty_upserts) == 1
    assert state.upserts[-1].current_assignment_ref == "assign-1"
