"""Unit tests for SIP-0089 §4.5/D25 — coordinator RuntimeTransaction (UoW) wiring.

Proves the coordinator opens ONE unit of work and threads its connection from
`RuntimeTransactionPort.begin()` through the lease + activity + mode writes, in
§4.5 order (activity abort *before* the mode write); and that the default NoOp
transaction threads `conn=None` (the backward-compatible path). The genuine
rollback-on-failure guarantee is proved against live Postgres in the integration
test (slice 3) — an in-memory fake can't model a real abort.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from squadops.ports.runtime.transaction import RuntimeTransactionPort
from squadops.runtime import reasons
from squadops.runtime.coordinator import RuntimeCoordinator
from squadops.runtime.models import AgentRuntimeState, LeaseGranted, RuntimeActivity

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 28, 1, 0, tzinfo=UTC)
_SENTINEL = "uow-conn"


def _state(mode="ambient") -> AgentRuntimeState:
    return AgentRuntimeState("max", mode, "online", "", None, "high", NOW, None)


def _activity(mode="duty") -> RuntimeActivity:
    return RuntimeActivity(
        runtime_activity_id="act-1",
        agent_id="max",
        mode=mode,
        activity_type="x",
        goal="g",
        priority=0,
        state="running",
        source_kind="cycle_task",
        source_ref="r",
        cycle_id=None,
        workload_id=None,
        task_id=None,
        can_pause=False,
        can_resume=False,
        can_abort=True,
    )


class _RecordingUoW(RuntimeTransactionPort):
    """Yields a sentinel connection and counts how many units of work were opened."""

    def __init__(self) -> None:
        self.begins = 0

    @asynccontextmanager
    async def begin(self):
        self.begins += 1
        yield _SENTINEL


class _StateFake:
    def __init__(self, rec: list, initial: AgentRuntimeState) -> None:
        self._rec = rec
        self._state = initial

    async def get_state(self, agent_id):
        return self._state

    async def ensure_state(self, agent_id):
        return self._state

    async def upsert_state(self, state, *, conn=None):
        self._rec.append(("upsert_state", conn))
        self._state = state
        return state


class _LeaseFake:
    def __init__(self, rec: list) -> None:
        self._rec = rec
        self._n = 0

    async def get_current_lease(self, agent_id, *, conn=None):
        self._rec.append(("get_current_lease", conn))
        return None

    async def request_lease(self, agent_id, owner_type, owner_ref, idem, *, conn=None, **kw):
        self._rec.append(("request_lease", conn))
        self._n += 1
        return LeaseGranted(f"L{self._n}", None, reasons.FOCUS_LEASE_GRANTED)

    async def release_lease(self, lease_id, reason_code, *, conn=None):
        self._rec.append(("release_lease", conn))

    async def revoke_lease(self, lease_id, reason_code, *, conn=None):
        self._rec.append(("revoke_lease", conn))


class _ActivityFake:
    def __init__(self, rec: list, current: RuntimeActivity) -> None:
        self._rec = rec
        self._current = current

    async def get_current_activity(self, agent_id, *, conn=None):
        self._rec.append(("get_current_activity", conn))
        return self._current

    async def abort_activity(self, activity_id, reason_code, *, conn=None):
        self._rec.append(("abort_activity", conn))
        return replace(self._current, state="aborted")


async def test_uow_conn_threaded_through_all_writes_in_4_5_order():
    rec: list = []
    uow = _RecordingUoW()
    state = _StateFake(rec, _state("ambient"))
    lease = _LeaseFake(rec)
    activity = _ActivityFake(rec, _activity(mode="duty"))  # orphaned by ambient→cycle
    coord = RuntimeCoordinator(state, focus_lease=lease, activity=activity, transaction=uow)

    outcome = await coord.request_transition(
        "max", "cycle", reasons.CYCLE_RECRUITED, requester_kind="external", owner_ref="run-1"
    )

    assert outcome.applied is True
    assert uow.begins == 1  # exactly one unit of work
    assert {conn for _, conn in rec} == {_SENTINEL}  # every write ran on the UoW conn
    ops = [op for op, _ in rec]
    assert ops.index("abort_activity") < ops.index("upsert_state")  # §4.5: activity before mode
    assert ops.index("request_lease") < ops.index("abort_activity")  # lease first


async def test_default_null_transaction_threads_conn_none():
    rec: list = []
    state = _StateFake(rec, _state("ambient"))
    lease = _LeaseFake(rec)
    coord = RuntimeCoordinator(state, focus_lease=lease)  # no transaction port → NoOp UoW

    await coord.request_transition(
        "max", "cycle", reasons.CYCLE_RECRUITED, requester_kind="external", owner_ref="run-1"
    )

    assert {conn for _, conn in rec} == {None}  # NoOp yields None → adapters acquire their own
