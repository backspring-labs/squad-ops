"""Unit tests for SIP-0089 §4.5 (thin v1.1 seam) — coordinator RuntimeActivity action.

A mode change orphans any activity bound to the *previous* mode; the coordinator
aborts it best-effort, post-write. Bug classes guarded:
- an activity left running after its mode ended (stale "current work");
- aborting an activity that belongs to the mode being ENTERED (false abort);
- the activity action breaking an otherwise-applied transition (it must be
  best-effort — observability never fails a mode change);
- emitting/aborting when there is no current activity.

The full §4.5 transition order + D25 single transaction are deferred to #244; these
tests pin the v1.1 seam behavior.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from squadops.ports.runtime.activity import RuntimeActivityPort
from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.coordinator import RuntimeCoordinator
from squadops.runtime.models import AgentRuntimeState, RuntimeActivity

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 28, 1, 0, tzinfo=UTC)


def _state(mode="cycle") -> AgentRuntimeState:
    return AgentRuntimeState("max", mode, "online", "", None, "high", NOW, None)


def _activity(mode="cycle", activity_id="act-1") -> RuntimeActivity:
    return RuntimeActivity(
        runtime_activity_id=activity_id,
        agent_id="max",
        mode=mode,
        activity_type="design",
        goal="g",
        priority=5,
        state="running",
        source_kind="cycle_task",
        source_ref="task-1",
        cycle_id="cyc-1",
        workload_id=None,
        task_id="task-1",
        can_pause=False,
        can_resume=False,
        can_abort=True,
    )


class _FakeStatePort(RuntimeStatePort):
    def __init__(self, initial: AgentRuntimeState) -> None:
        self._rows = {initial.agent_id: initial}
        self.upserts: list[AgentRuntimeState] = []

    async def get_state(self, agent_id):
        return self._rows.get(agent_id)

    async def upsert_state(self, state):
        self._rows[state.agent_id] = state
        self.upserts.append(state)
        return state

    async def ensure_state(self, agent_id):
        return self._rows[agent_id]

    async def update_heartbeat(self, agent_id, *, runtime_status=None):
        return self._rows[agent_id]

    async def mark_offline(self, agent_id):
        return self._rows.get(agent_id)


class _FakeActivityPort(RuntimeActivityPort):
    def __init__(
        self, current: RuntimeActivity | None = None, *, abort_raises: bool = False
    ) -> None:
        self._current = current
        self.abort_raises = abort_raises
        self.aborted: list[tuple[str, str]] = []

    async def start_activity(self, agent_id, **kwargs):  # unused here
        raise NotImplementedError

    async def update_state(self, activity_id, state):  # unused here
        raise NotImplementedError

    async def complete_activity(self, activity_id, *, evidence_ref=None):  # unused here
        raise NotImplementedError

    async def fail_activity(self, activity_id, reason_code):  # unused here
        raise NotImplementedError

    async def abort_activity(self, activity_id, reason_code):
        if self.abort_raises:
            raise RuntimeError("boom")
        self.aborted.append((activity_id, reason_code))
        cur = self._current
        self._current = None
        return replace(cur, state="aborted") if cur is not None else None

    async def get_current_activity(self, agent_id):
        return self._current


class _RecordingPublisher(RuntimeEventPublisher):
    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, event_name, *, agent_id, reason_code, payload=None):
        self.emitted.append((event_name, agent_id, reason_code, payload))

    def names(self) -> list[str]:
        return [e[0] for e in self.emitted]


async def test_orphaned_activity_is_aborted_and_event_emitted():
    """Bug class: leaving a mode must abort the activity bound to it, else it
    lingers as stale current work. cycle→ambient aborts the cycle activity and
    emits runtime_activity.aborted with the preemption reason."""
    state = _FakeStatePort(_state(mode="cycle"))
    pub = _RecordingPublisher()
    act = _FakeActivityPort(_activity(mode="cycle", activity_id="act-9"))
    coord = RuntimeCoordinator(state, events_publisher=pub, activity=act)

    outcome = await coord.request_transition(
        "max", "ambient", reasons.CYCLE_COMPLETED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert outcome.applied is True and state.upserts[-1].mode == "ambient"
    assert act.aborted == [("act-9", reasons.ACTIVITY_PREEMPTED_BY_MODE_CHANGE)]
    assert events.RUNTIME_ACTIVITY_ABORTED in pub.names()


async def test_activity_in_target_mode_is_not_aborted():
    """Bug class: an activity belonging to the mode being ENTERED must NOT be
    aborted (a duty handler may have already opened its activity). ambient→duty
    with a duty activity present leaves it running."""
    state = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    act = _FakeActivityPort(_activity(mode="duty"))
    coord = RuntimeCoordinator(state, events_publisher=pub, activity=act)

    await coord.request_transition(
        "max", "duty", reasons.DUTY_WINDOW_OPENED, requester_kind="scheduler", owner_ref="assign-1"
    )

    assert act.aborted == []
    assert events.RUNTIME_ACTIVITY_ABORTED not in pub.names()


async def test_no_current_activity_is_a_noop():
    """Bug class: with no current activity the seam must do nothing — no abort, no
    runtime_activity event."""
    state = _FakeStatePort(_state(mode="cycle"))
    pub = _RecordingPublisher()
    act = _FakeActivityPort(None)
    coord = RuntimeCoordinator(state, events_publisher=pub, activity=act)

    await coord.request_transition(
        "max", "ambient", reasons.CYCLE_COMPLETED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert act.aborted == []
    assert events.RUNTIME_ACTIVITY_ABORTED not in pub.names()


async def test_activity_abort_failure_does_not_break_transition():
    """Bug class (best-effort): the activity action is observability — a failure
    aborting the activity must NOT fail an already-applied mode transition. The
    mode is written, the transition reports applied, no abort event is emitted."""
    state = _FakeStatePort(_state(mode="cycle"))
    pub = _RecordingPublisher()
    act = _FakeActivityPort(_activity(mode="cycle"), abort_raises=True)
    coord = RuntimeCoordinator(state, events_publisher=pub, activity=act)

    outcome = await coord.request_transition(
        "max", "ambient", reasons.CYCLE_COMPLETED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert outcome.applied is True and state.upserts[-1].mode == "ambient"
    assert events.RUNTIME_ACTIVITY_ABORTED not in pub.names()  # abort failed → no event


async def test_no_activity_port_keeps_prior_behavior():
    """Bug class: activity=None must keep the pre-Phase-4 path — a plain mode write
    with no activity interaction and no runtime_activity events."""
    state = _FakeStatePort(_state(mode="cycle"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(state, events_publisher=pub)  # no activity

    outcome = await coord.request_transition(
        "max", "ambient", reasons.CYCLE_COMPLETED, requester_kind="coordinator", owner_ref="cyc-1"
    )

    assert outcome.applied is True
    assert pub.names() == [events.MODE_TRANSITION]
