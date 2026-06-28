"""Unit tests for SIP-0089 §2.6 — RuntimeCoordinator (the D16 transition authority).

Bug classes guarded:
- the coordinator silently applying a transition it should reject (offline→duty,
  malformed mode, missing reason) — each would corrupt runtime state or hide a
  scheduling bug;
- a non-idempotent coordinator letting a repeated scheduler tick (D12/D21) open
  the same window twice — duplicate transitions/events;
- mode/assignment writes drifting (entering duty must bind the assignment;
  leaving duty must clear it);
- event/reason collapse (D18) — the emitted event name and the reason code must
  be distinct values.

Uses an in-memory RuntimeStatePort + a recording publisher rather than mocks, so
assertions are on resulting state, not call shapes.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.ports.runtime.state import RuntimeStatePort
from squadops.runtime import events, reasons
from squadops.runtime.coordinator import RuntimeCoordinator
from squadops.runtime.models import AgentRuntimeState

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 24, 1, 0, tzinfo=UTC)


def _state(mode="ambient", runtime_status="online") -> AgentRuntimeState:
    return AgentRuntimeState(
        agent_id="max",
        mode=mode,
        runtime_status=runtime_status,
        focus="",
        current_runtime_activity_id=None,
        interruptibility="high",
        last_heartbeat_at=NOW,
        current_assignment_ref=None,
    )


class _FakeStatePort(RuntimeStatePort):
    def __init__(self, initial: AgentRuntimeState | None = None) -> None:
        self._rows: dict[str, AgentRuntimeState] = {}
        if initial is not None:
            self._rows[initial.agent_id] = initial
        self.upserts: list[AgentRuntimeState] = []

    async def get_state(self, agent_id):
        return self._rows.get(agent_id)

    async def upsert_state(self, state):
        self._rows[state.agent_id] = state
        self.upserts.append(state)
        return state

    async def ensure_state(self, agent_id):
        if agent_id not in self._rows:
            self._rows[agent_id] = _state()
        return self._rows[agent_id]

    async def update_heartbeat(self, agent_id, *, runtime_status=None):  # unused here
        return await self.ensure_state(agent_id)

    async def mark_offline(self, agent_id):  # unused here
        return self._rows.get(agent_id)


class _RecordingPublisher(RuntimeEventPublisher):
    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, event_name, *, agent_id, reason_code, payload=None):
        self.emitted.append((event_name, agent_id, reason_code, payload))


async def test_ambient_to_duty_applies_and_binds_assignment():
    """Bug class: entering duty must persist mode=duty AND bind the active
    assignment, else recall/scheduling can't tell which duty the agent serves."""
    port = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(port, events_publisher=pub)

    outcome = await coord.request_transition(
        "max",
        "duty",
        reasons.DUTY_WINDOW_OPENED,
        requester_kind="scheduler",
        owner_ref="assign-1",
        assignment_id="assign-1",
    )

    assert outcome.applied is True
    assert (outcome.from_mode, outcome.to_mode) == ("ambient", "duty")
    assert port.upserts[-1].mode == "duty"
    assert port.upserts[-1].current_assignment_ref == "assign-1"


async def test_duty_to_ambient_clears_assignment_ref():
    """Bug class: leaving duty must clear current_assignment_ref — a stale ref
    would make an ambient agent look like it's still on duty."""
    port = _FakeStatePort(
        AgentRuntimeState("max", "duty", "online", "", None, "high", NOW, "assign-1")
    )
    coord = RuntimeCoordinator(port, events_publisher=_RecordingPublisher())

    await coord.request_transition(
        "max",
        "ambient",
        reasons.DUTY_WINDOW_CLOSED,
        requester_kind="scheduler",
        owner_ref="assign-1",
    )

    assert port.upserts[-1].mode == "ambient"
    assert port.upserts[-1].current_assignment_ref is None


async def test_same_mode_is_idempotent_noop_without_write_or_event():
    """Bug class: a no-op transition must not write or emit — spurious events
    would pollute the audit trail and a needless upsert could race."""
    port = _FakeStatePort(_state(mode="duty"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(port, events_publisher=pub)

    outcome = await coord.request_transition(
        "max",
        "duty",
        reasons.DUTY_WINDOW_OPENED,
        requester_kind="scheduler",
        owner_ref="assign-1",
    )

    assert outcome.idempotent_skip is True and outcome.applied is False
    assert port.upserts == []
    assert pub.emitted == []


async def test_offline_runtime_cannot_enter_duty():
    """Bug class (§11.3): an offline agent transitioning straight to duty would
    schedule work onto an unreachable runtime."""
    port = _FakeStatePort(_state(mode="ambient", runtime_status="offline"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(port, events_publisher=pub)

    outcome = await coord.request_transition(
        "max",
        "duty",
        reasons.DUTY_WINDOW_OPENED,
        requester_kind="scheduler",
        owner_ref="assign-1",
    )

    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.OFFLINE_CANNOT_ENTER_DUTY
    assert port.upserts == [] and pub.emitted == []


async def test_missing_reason_code_rejected_before_state_load():
    """Bug class (§11.2): an unreasoned transition is unexplainable in the audit
    trail and must be refused outright."""
    port = _FakeStatePort(_state())
    coord = RuntimeCoordinator(port, events_publisher=_RecordingPublisher())

    outcome = await coord.request_transition(
        "max",
        "duty",
        "",
        requester_kind="cli",
        owner_ref="op",
    )

    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.MISSING_REASON_CODE
    assert port.upserts == []


async def test_malformed_target_mode_rejected():
    """Bug class: the allow-list catches a target_mode string that slipped past
    the type hint (e.g. a typo), rather than persisting an invalid mode."""
    port = _FakeStatePort(_state(mode="ambient"))
    coord = RuntimeCoordinator(port, events_publisher=_RecordingPublisher())

    outcome = await coord.request_transition(
        "max",
        "paused",
        reasons.DUTY_WINDOW_OPENED,
        requester_kind="external",
        owner_ref="x",
    )

    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.INVALID_MODE_TRANSITION
    assert port.upserts == []


async def test_repeated_scheduled_transition_is_deduped_d12():
    """Bug class (D12/D21): a repeated scheduler tick for the same
    (assignment, scheduled_at) must not open the window twice."""
    port = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(port, events_publisher=pub)
    kwargs = {
        "requester_kind": "scheduler",
        "owner_ref": "assign-1",
        "assignment_id": "assign-1",
        "scheduled_at": NOW,
    }

    first = await coord.request_transition("max", "duty", reasons.DUTY_WINDOW_OPENED, **kwargs)
    second = await coord.request_transition("max", "duty", reasons.DUTY_WINDOW_OPENED, **kwargs)

    assert first.applied is True
    assert second.applied is False and second.idempotent_skip is True
    assert len(port.upserts) == 1  # applied exactly once
    assert len(pub.emitted) == 1


async def test_applied_event_keeps_event_and_reason_distinct_d18():
    """Bug class (D18): the emitted event name and the reason code must be
    different values — collapsing them loses the what/why distinction."""
    port = _FakeStatePort(_state(mode="ambient"))
    pub = _RecordingPublisher()
    coord = RuntimeCoordinator(port, events_publisher=pub)

    await coord.request_transition(
        "max",
        "cycle",
        reasons.CYCLE_RECRUITED,
        requester_kind="coordinator",
        owner_ref="cyc-1",
    )

    event_name, agent_id, reason_code, payload = pub.emitted[0]
    assert event_name == events.MODE_TRANSITION
    assert reason_code == reasons.CYCLE_RECRUITED
    assert event_name != reason_code
    assert payload["from_mode"] == "ambient" and payload["to_mode"] == "cycle"
