"""Tests for the composition root's startup hygiene sweeps (#373, #710, #672).

`startup_reaps` owns the three things `main.py` used to inline: the wiring gate
and the "is the owner finished?" predicate. Both are where the silent-no-op bugs
live, so both are tested here rather than through the domain reapers.

Bug classes guarded:
- a pool-less deployment raising (or the reap running against None ports) at
  startup — runtime-api that will not boot is worse than one that boots with
  residue;
- the run-terminal predicate answering "terminal" for a *live* run, which would
  release the focus leases of an executing cycle;
- a missing owner row read as live, so the rows most certainly stranded (their
  run/cycle is gone) are the only ones never reaped;
- a registry failure propagating out and aborting startup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from squadops.api.runtime.startup_reaps import (
    reap_stranded_activities,
    reap_stranded_leases,
    reap_stranded_modes,
)
from squadops.cycles.models import CycleNotFoundError, Run, RunNotFoundError, RunStatus
from squadops.runtime.models import FocusLease, RuntimeActivity

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 8, 4, tzinfo=UTC)


def _lease(agent_id="max", owner_ref="run_1") -> FocusLease:
    return FocusLease(
        lease_id="lease-1",
        agent_id=agent_id,
        owner_type="cycle",
        owner_ref=owner_ref,
        acquired_at=NOW,
        expires_at=None,
        renewal_policy="ttl",
        interruptibility="high",
        recall_policy="graceful",
        released_at=None,
        idempotency_key=f"cycle:{owner_ref}:{agent_id}",
    )


def _activity(cycle_id="cyc_1") -> RuntimeActivity:
    return RuntimeActivity(
        runtime_activity_id="act-1",
        agent_id="max",
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


def _run(status: str) -> Run:
    return Run(
        run_id="run_1",
        cycle_id="cyc_1",
        run_number=1,
        status=status,
        initiated_by="api",
        resolved_config_hash="x",
    )


def _lease_ports(*, cleared: bool):
    """A lease port holding one lease; `cleared` decides what the re-read sees."""
    port = AsyncMock()
    port.list_active_leases.return_value = (_lease(),)
    port.get_current_lease.return_value = None if cleared else _lease()
    return port, AsyncMock()


# ---------------------------------------------------------------------------
# reap_stranded_leases (#373)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coordinator", "focus_lease"),
    [(None, AsyncMock()), (AsyncMock(), None), (None, None)],
    ids=["no-coordinator", "no-lease-port", "neither"],
)
async def test_lease_reap_is_a_noop_without_wiring(coordinator, focus_lease):
    registry = AsyncMock()

    assert await reap_stranded_leases(registry, coordinator, focus_lease) == 0
    registry.get_run.assert_not_awaited()


@pytest.mark.parametrize(
    "status",
    [
        RunStatus.RUNNING.value,
        RunStatus.QUEUED.value,
        RunStatus.PAUSED.value,
        RunStatus.COMPLETED.value,
        RunStatus.FAILED.value,
        RunStatus.CANCELLED.value,
    ],
)
async def test_every_held_lease_is_released_whatever_the_run_status(status):
    """#373's own evidence is a lease under a run still marked `running`: a
    SIGKILL leaves that status forever. Sparing non-terminal owners would leave
    exactly the reported case needing manual SQL — and nothing can be executing
    in a process that has not started serving yet."""
    port, coordinator = _lease_ports(cleared=True)
    registry = AsyncMock()
    registry.get_run.return_value = _run(status)

    assert await reap_stranded_leases(registry, coordinator, port) == 1
    assert coordinator.request_transition.await_count == 1


async def test_a_non_terminal_owner_is_logged_as_a_dead_executor(caplog):
    """The silent-hang complaint in #373: releasing a lease under a `running` run
    means the previous process died mid-run, and an operator has to be able to
    see that rather than infer it."""
    port, coordinator = _lease_ports(cleared=True)
    registry = AsyncMock()
    registry.get_run.return_value = _run(RunStatus.RUNNING.value)

    with caplog.at_level("WARNING"):
        await reap_stranded_leases(registry, coordinator, port)

    assert "run_1" in caplog.text
    assert "died mid-run" in caplog.text


async def test_missing_run_row_still_releases_the_lease():
    """A lease whose owning run is gone is the most certainly stranded row there
    is — a lookup failure must not exempt it."""
    port, coordinator = _lease_ports(cleared=True)
    registry = AsyncMock()
    registry.get_run.side_effect = RunNotFoundError("gone")

    assert await reap_stranded_leases(registry, coordinator, port) == 1


async def test_lease_reap_failure_never_blocks_startup():
    port, coordinator = _lease_ports(cleared=True)
    port.list_active_leases.side_effect = RuntimeError("db down")
    registry = AsyncMock()

    assert await reap_stranded_leases(registry, coordinator, port) == 0


# ---------------------------------------------------------------------------
# reap_stranded_modes (#710)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coordinator", "state_port"),
    [(None, AsyncMock()), (AsyncMock(), None), (None, None)],
    ids=["no-coordinator", "no-state-port", "neither"],
)
async def test_mode_reap_is_a_noop_without_wiring(coordinator, state_port):
    assert await reap_stranded_modes(coordinator, state_port) == 0


async def test_mode_reap_asks_only_for_cycle_agents():
    """Narrowed in SQL, not in Python: `duty` must never be enumerated by a sweep
    that unconditionally sends everything it finds to ambient."""
    coordinator = AsyncMock()
    state_port = AsyncMock()
    state_port.list_states.return_value = ()

    await reap_stranded_modes(coordinator, state_port)

    state_port.list_states.assert_awaited_once_with(mode="cycle")


async def test_mode_reap_failure_never_blocks_startup():
    coordinator = AsyncMock()
    state_port = AsyncMock()
    state_port.list_states.side_effect = RuntimeError("db down")

    assert await reap_stranded_modes(coordinator, state_port) == 0


# ---------------------------------------------------------------------------
# reap_stranded_activities (#672 — relocated from main.py, behavior unchanged)
# ---------------------------------------------------------------------------


async def test_activity_reap_is_a_noop_without_a_port():
    registry = AsyncMock()

    assert await reap_stranded_activities(registry, None) == 0
    registry.get_cycle.assert_not_awaited()


async def test_missing_cycle_row_is_treated_as_terminal():
    activity_port = AsyncMock()
    activity_port.list_active_activities.return_value = (_activity(),)
    activity_port.abort_activity.return_value = _activity()
    registry = AsyncMock()
    registry.get_cycle.side_effect = CycleNotFoundError("gone")

    assert await reap_stranded_activities(registry, activity_port) == 1


async def test_an_activity_of_a_still_active_cycle_is_ended_and_logged(caplog):
    """#561's live evidence: a cycle whose runs were killed derives as ACTIVE
    forever, so gating on a terminal cycle spared exactly the rows a crash
    strands — two agents sat dead for three days. Nothing dispatches at startup,
    so the row is residue whatever the derived status says."""
    activity_port = AsyncMock()
    activity_port.list_active_activities.return_value = (_activity(),)
    activity_port.abort_activity.return_value = _activity()
    registry = AsyncMock()
    # The predicate reads only `cancelled` off the cycle; the run list carries
    # the rest of the derivation.
    registry.get_cycle.return_value = SimpleNamespace(cancelled=False)
    registry.list_runs.return_value = [_run(RunStatus.RUNNING.value)]

    with caplog.at_level("WARNING"):
        assert await reap_stranded_activities(registry, activity_port) == 1

    assert "cyc_1" in caplog.text
    assert "died mid-task" in caplog.text


async def test_an_activity_with_no_owning_cycle_is_ended():
    """The residue #672 left unreachable: no cycle to consult meant no sweep
    could ever clear the row."""
    activity_port = AsyncMock()
    activity_port.list_active_activities.return_value = (_activity(cycle_id=None),)
    activity_port.abort_activity.return_value = _activity(cycle_id=None)
    registry = AsyncMock()

    assert await reap_stranded_activities(registry, activity_port) == 1
    registry.get_cycle.assert_not_awaited()  # nothing to ask


async def test_activity_reap_failure_never_blocks_startup():
    activity_port = AsyncMock()
    activity_port.list_active_activities.side_effect = RuntimeError("db down")

    assert await reap_stranded_activities(AsyncMock(), activity_port) == 0
