"""Tests for the stranded-activity sweeps (#672 — `runtime.activity_reaper`).

Bug classes guarded:
- the startup reaper aborting an activity whose owning cycle is still live —
  would kill real in-flight task tracking;
- cycle-less (duty/ambient) activities swept by the cycle-scoped rules;
- one bad row (predicate or abort failure) aborting the whole sweep — the
  remaining stranded rows would then never clear, and one stranded row blocks
  all of that agent's future activity tracking;
- the finalize sweep reaching beyond its own cycle's activities (aborting a
  concurrent cycle's live rows);
- counting attempted rather than actually-flipped rows — a concurrent
  terminalization returns None from `abort_activity` and must not be counted;
- the wrong reason code on either sweep (the codes are event/log-surfaced
  triage evidence).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from squadops.ports.runtime.activity import RuntimeActivityPort
from squadops.runtime import reasons
from squadops.runtime.activity_reaper import abort_cycle_activities, reap_stale_activities
from squadops.runtime.models import RuntimeActivity, is_active_activity_state

pytestmark = [pytest.mark.domain_runtime]


def _activity(activity_id="act-1", agent_id="max", cycle_id="cyc-1") -> RuntimeActivity:
    return RuntimeActivity(
        runtime_activity_id=activity_id,
        agent_id=agent_id,
        mode="cycle",
        activity_type="development.develop",
        goal="Fill the slot",
        priority=0,
        state="running",
        source_kind="cycle_task",
        source_ref="t1",
        cycle_id=cycle_id,
        workload_id=None,
        task_id="t1",
        can_pause=False,
        can_resume=False,
        can_abort=True,
    )


class _FakeActivityPort(RuntimeActivityPort):
    def __init__(
        self,
        activities: tuple[RuntimeActivity, ...] = (),
        *,
        abort_raises_for: frozenset[str] = frozenset(),
        abort_gone_for: frozenset[str] = frozenset(),
    ) -> None:
        self._activities = list(activities)
        self._abort_raises_for = abort_raises_for
        # Rows a concurrent writer already terminalized: abort returns None.
        self._abort_gone_for = abort_gone_for
        self.aborted: list[tuple[str, str]] = []
        self.list_calls: list[str | None] = []

    async def start_activity(self, agent_id, **kwargs):  # unused here
        raise NotImplementedError

    async def update_state(self, activity_id, state, *, conn=None):  # unused here
        raise NotImplementedError

    async def complete_activity(self, activity_id, *, evidence_ref=None):  # unused here
        raise NotImplementedError

    async def fail_activity(self, activity_id, reason_code):  # unused here
        raise NotImplementedError

    async def abort_activity(self, activity_id, reason_code, *, conn=None):
        if activity_id in self._abort_raises_for:
            raise RuntimeError("db down")
        self.aborted.append((activity_id, reason_code))
        if activity_id in self._abort_gone_for:
            return None
        for i, act in enumerate(self._activities):
            if act.runtime_activity_id == activity_id:
                self._activities[i] = replace(act, state="aborted")
                return self._activities[i]
        return None

    async def get_current_activity(self, agent_id, *, conn=None):  # unused here
        raise NotImplementedError

    async def list_active_activities(self, *, cycle_id=None, conn=None):
        self.list_calls.append(cycle_id)
        active = [a for a in self._activities if is_active_activity_state(a.state)]
        if cycle_id is not None:
            active = [a for a in active if a.cycle_id == cycle_id]
        return tuple(active)


def _terminal_only(terminal_cycles: set[str], *, raises_for: set[str] | None = None):
    calls: list[str | None] = []

    async def owner_is_finished(cycle_id: str | None) -> bool:
        calls.append(cycle_id)
        if raises_for and cycle_id in raises_for:
            raise RuntimeError("registry down")
        return cycle_id in terminal_cycles

    owner_is_finished.calls = calls  # type: ignore[attr-defined]
    return owner_is_finished


# ---------------------------------------------------------------------------
# reap_stale_activities (startup)
# ---------------------------------------------------------------------------


async def test_reap_aborts_terminal_cycle_rows_and_spares_live_ones():
    """Bug class: reaping a live cycle's activity kills real in-flight tracking;
    sparing a terminal cycle's row leaves the collision class in place."""
    port = _FakeActivityPort(
        (
            _activity("act-dead", agent_id="eve", cycle_id="cyc-dead"),
            _activity("act-live", agent_id="neo", cycle_id="cyc-live"),
        )
    )

    reaped = await reap_stale_activities(port, owner_is_finished=_terminal_only({"cyc-dead"}))

    assert reaped == 1
    assert port.aborted == [("act-dead", reasons.ACTIVITY_STRANDED_AT_STARTUP)]


async def test_reap_asks_the_predicate_about_cycle_less_activities_too():
    """Bug class (#561): a row skipped *before* the predicate is a row no sweep
    can ever reach — permanently stranded, and one stranded row blocks all of
    that agent's future activity tracking. The caller decides whether a
    cycle-less row is finished; this module must not silently spare it."""
    port = _FakeActivityPort((_activity("act-duty", cycle_id=None),))
    predicate = _terminal_only(set())

    reaped = await reap_stale_activities(port, owner_is_finished=predicate)

    assert reaped == 0  # this predicate answers "not finished"
    assert predicate.calls == [None]  # but it was ASKED — that is the fix


async def test_reap_ends_a_cycle_less_activity_when_the_predicate_says_finished():
    port = _FakeActivityPort((_activity("act-duty", cycle_id=None),))

    async def _finished(cycle_id: str | None) -> bool:
        return True

    assert await reap_stale_activities(port, owner_is_finished=_finished) == 1
    assert port.aborted == [("act-duty", reasons.ACTIVITY_STRANDED_AT_STARTUP)]


async def test_reap_survives_predicate_failure_and_clears_the_rest():
    """Bug class: one unreadable cycle aborting the whole sweep — the other
    stranded rows would never clear. The failing row itself must NOT be aborted
    (its cycle's liveness is unknown)."""
    port = _FakeActivityPort(
        (
            _activity("act-unknown", agent_id="max", cycle_id="cyc-unknown"),
            _activity("act-dead", agent_id="eve", cycle_id="cyc-dead"),
        )
    )

    reaped = await reap_stale_activities(
        port,
        owner_is_finished=_terminal_only({"cyc-dead"}, raises_for={"cyc-unknown"}),
    )

    assert reaped == 1
    assert port.aborted == [("act-dead", reasons.ACTIVITY_STRANDED_AT_STARTUP)]


async def test_reap_survives_abort_failure_and_clears_the_rest():
    port = _FakeActivityPort(
        (
            _activity("act-a", agent_id="max", cycle_id="cyc-dead"),
            _activity("act-b", agent_id="eve", cycle_id="cyc-dead"),
        ),
        abort_raises_for=frozenset({"act-a"}),
    )

    reaped = await reap_stale_activities(port, owner_is_finished=_terminal_only({"cyc-dead"}))

    assert reaped == 1
    assert ("act-b", reasons.ACTIVITY_STRANDED_AT_STARTUP) in port.aborted


async def test_reap_does_not_count_concurrently_terminalized_rows():
    """Bug class: `abort_activity` returns None when the row already left the
    active states (the adapter's race guard) — counting it would report reaps
    that never happened."""
    port = _FakeActivityPort(
        (_activity("act-gone", cycle_id="cyc-dead"),),
        abort_gone_for=frozenset({"act-gone"}),
    )

    reaped = await reap_stale_activities(port, owner_is_finished=_terminal_only({"cyc-dead"}))

    assert reaped == 0


# ---------------------------------------------------------------------------
# abort_cycle_activities (run finalize)
# ---------------------------------------------------------------------------


async def test_finalize_sweep_is_scoped_to_its_own_cycle():
    """Bug class: an unscoped sweep aborts a concurrent cycle's live activity.
    The port must be queried WITH the cycle filter, and only the finishing
    cycle's rows flipped."""
    port = _FakeActivityPort(
        (
            _activity("act-mine", agent_id="eve", cycle_id="cyc-finishing"),
            _activity("act-other", agent_id="neo", cycle_id="cyc-other"),
        )
    )

    aborted = await abort_cycle_activities(port, "cyc-finishing")

    assert port.list_calls == ["cyc-finishing"]
    assert aborted == 1
    assert port.aborted == [("act-mine", reasons.ACTIVITY_STRANDED_AT_RUN_FINALIZE)]


async def test_finalize_sweep_survives_abort_failure_and_clears_the_rest():
    port = _FakeActivityPort(
        (
            _activity("act-a", agent_id="max", cycle_id="cyc-1"),
            _activity("act-b", agent_id="eve", cycle_id="cyc-1"),
        ),
        abort_raises_for=frozenset({"act-a"}),
    )

    aborted = await abort_cycle_activities(port, "cyc-1")

    assert aborted == 1
    assert ("act-b", reasons.ACTIVITY_STRANDED_AT_RUN_FINALIZE) in port.aborted


async def test_finalize_sweep_with_no_active_rows_is_a_quiet_no_op():
    """The common case: every task terminalized its own activity. The sweep
    must flip nothing and report zero."""
    port = _FakeActivityPort(())

    aborted = await abort_cycle_activities(port, "cyc-1")

    assert aborted == 0
    assert port.aborted == []
