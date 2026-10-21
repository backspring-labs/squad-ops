"""A Campaign cycle held on its instruction bindings escalates as its own kind (SIP-0109 §24bw;
SIP-0110 §A.3.6, #2178).

Entered where the runtime enters: the executor's ``open_binding_hold`` after it records the hold,
the sweep (``CampaignProgress.sweep_ruling_bounds``), and the hearing the cycle's end calls
(``cycle_ended``). The run's hold record (``Run.binding_holds``) and the registry's release are the
executor's (#2178), stood in for here by a cycle registry that holds them.

What bugs would these catch?
- a held Campaign cycle the owner never hears of, or one the sweep never ends;
- a hold's expiry read as a park, so row 15 abandons the increment and counts it as unaccepted,
  when the squad's work said nothing;
- the store's hold escalated to the owner, or an operator's input retried as if the box were down;
- a hold released by re-supply closed as anything but resolved, or the sweep cancelling a run the
  executor had just released;
- an answer accepted on a hold, which nothing reads;
- a restart that re-enters the hold writing a second escalation, or a standalone cycle given one.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns import binding_hold
from squadops.campaigns.continuation import PendingAction
from squadops.campaigns.escalation import (
    EscalationKind,
    EscalationState,
    answer_refusal,
    escalations,
    parked_run,
)
from squadops.campaigns.models import CampaignState, ControlOperation, CycleKind, LaunchRequest
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import Run, RunStatus
from tests.unit.campaigns.builders import campaign, cycle_for, move, policy

S = CampaignState
CID = "cmp_heldbind0001"
BOUND = 1800  # the builders' ruling bound
HELD = datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
STORE = (("snapshot:campaign:cmp_heldbind0001", "the memory store did not answer", "store"),)
INPUT = (("mrec_contrib:1", "repo:file:CLAUDE.md@current could not be read", "input"),)


@dataclasses.dataclass(frozen=True)
class _Hold:
    """The executor's ``BindingHold``, as #2178 records it on the run."""

    hold_id: str
    task_id: str
    task_type: str
    unresolved: tuple[tuple[str, str, str], ...]
    held_at: datetime
    released_at: datetime | None = None
    cause: str | None = None


class _HeldRun:
    """A ``Run`` with the hold records #2178 adds to it."""

    def __init__(self, run: Run, holds: tuple[_Hold, ...]) -> None:
        self._run, self.binding_holds = run, holds

    def __getattr__(self, name):
        return getattr(self._run, name)


class _HoldingCycles(MemoryCycleRegistry):
    """The cycle registry with #2178's hold records and its compare-and-set release."""

    def __init__(self) -> None:
        super().__init__()
        self.holds: dict[str, list[_Hold]] = {}
        self.releases: list[tuple[str, str, str]] = []

    async def get_run(self, run_id):
        return _HeldRun(await super().get_run(run_id), tuple(self.holds.get(run_id, ())))

    async def release_binding_hold(self, run_id, hold_id, *, released_at, cause) -> bool:
        holds = self.holds[run_id]
        for i, hold in enumerate(holds):
            if hold.hold_id == hold_id and hold.released_at is None:
                holds[i] = dataclasses.replace(hold, released_at=released_at, cause=cause)
                self.releases.append((run_id, hold_id, cause))
                return True
        return False


async def _world(unresolved=STORE):
    campaigns = MemoryCampaignRegistry()
    cycles = _HoldingCycles()
    await campaigns.create_campaign(
        campaign(CID, policy=policy()), actor="o", actor_role="o", reason="r", idempotency_key="c"
    )
    await campaigns.transition(CID, move(S.CALIBRATING, "k0"))
    intent = (
        await campaigns.transition(
            CID, move(S.AT_PROPOSAL, "k1", launch=LaunchRequest(CycleKind.INCREMENT))
        )
    ).intent
    cycle = cycle_for(intent)
    await cycles.create_cycle(cycle)
    await campaigns.mark_launch_intent_launched(intent.launch_id, cycle.cycle_id, actor="l")
    await campaigns.transition(CID, move(S.AWAITING_RULING, "k2"))
    await campaigns.transition(CID, move(S.BUILDING, "k3"))
    await cycles.create_run(
        Run(
            run_id="run_h",
            cycle_id=cycle.cycle_id,
            run_number=1,
            status=RunStatus.PAUSED.value,
            initiated_by="system",
            resolved_config_hash="h",
            workload_type="implementation",
        )
    )
    hold = _Hold("hold_0123456789ab", "task-run_h-003-development.develop", "development.develop",
                 unresolved, HELD)  # fmt: skip
    cycles.holds["run_h"] = [hold]
    now = [HELD]
    progress = CampaignProgress(
        campaigns=campaigns,
        cycles=cycles,
        vault=AsyncMock(),
        assess=AsyncMock(return_value=None),
        launch=AsyncMock(),
        evaluate_outcome=None,
        outcome_section=None,
        intervention_section=None,
        clock=lambda: now[0],
    )
    return campaigns, cycles, progress, now, cycle, hold


def _vacuous_accept(cycle_id: str):
    """The assessment a cancelled cycle can read (#2303's shape): ``accepted`` with nothing
    executed. A held cycle that ended must never be promoted on it."""
    from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
    from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict

    run = RunRecord(
        run_id="run_h",
        run_number=1,
        workload_type="implementation",
        status="cancelled",
        started_at=HELD,
        finished_at=HELD,
    )
    outcome = CycleOutcome(
        verdict=RunVerdict.ACCEPTED,
        verified=(),
        failed=(),
        unverified=(),
        run_count=1,
        criteria_verified=(),
        criteria_total=(),
    )
    evidence = CycleEvidence(cycle_id=cycle_id, runs=(run,), verification_summary_runs=("run_h",))
    return assess(outcome, evidence, assessor=AssessorIdentity("2.4.0", None))


def _closed(rows):
    return [
        {k: e.binding.get(k) for k in ("state", "cause", "hold_class")}
        for e in rows
        if e.operation is ControlOperation.ESCALATION_CLOSED
    ]


@pytest.mark.parametrize(
    ("unresolved", "row", "action"),
    [(STORE, 10, PendingAction.RETRY), (INPUT, 17, PendingAction.ESCALATE)],
    ids=["the-store-retries", "an-operators-input-escalates"],
)
async def test_a_hold_past_its_bound_ends_its_cycle_by_cause_never_parked(unresolved, row, action):
    """The whole path: the executor opens the escalation, the sweep leaves it inside the bound
    and expires it past, the run is released then cancelled, and the hearing reads the cycle's
    end by the hold's cause. Neither ending counts toward ``max_unaccepted_increments``, and a
    vacuous ``accepted`` on the cancelled run promotes nothing (#2303's shape)."""
    campaigns, cycles, progress, now, cycle, hold = await _world(unresolved)
    progress._assess = AsyncMock(return_value=_vacuous_accept(cycle.cycle_id))

    opened = await binding_hold.open_binding_hold(campaigns, cycle, "run_h", hold, HELD)
    inside = await progress.sweep_ruling_bounds()
    now[0] = HELD + timedelta(seconds=BOUND)
    past = await progress.sweep_ruling_bounds()
    ended = await cycles.get_run("run_h")
    decision = await progress.cycle_ended(
        await cycles.get_cycle(cycle.cycle_id), ended, CycleStopReason.RUN_CANCELLED
    )

    log = await campaigns.control_log(CID)
    [esc] = escalations(log, S.BUILDING)
    cls = unresolved[0][2]
    assert opened and esc.kind is EscalationKind.BINDING_HOLD and esc.hold_class == cls
    assert inside == []
    assert _closed(past) == [{"state": "expired", "cause": "expired", "hold_class": cls}]
    assert cycles.releases == [("run_h", hold.hold_id, "expired")]
    assert (ended.status, ended.failure_reason) == ("cancelled", "binding_hold_expired")
    assert not parked_run(log, "run_h")
    assert (decision.row, decision.action) == (row, action)
    assert [e for e in log if e.operation is ControlOperation.PROMOTE] == []
    assert (await campaigns.get_campaign(CID)).outcome is None


@pytest.mark.parametrize(
    ("cause", "status", "state"),
    [
        ("store_answered", RunStatus.RUNNING, EscalationState.RESOLVED),
        ("rebound", RunStatus.RUNNING, EscalationState.RESOLVED),
        ("cancelled", RunStatus.CANCELLED, EscalationState.SUPERSEDED),
    ],
    ids=["re-supplied", "re-bound", "cancelled-while-held"],
)
async def test_a_released_hold_closes_by_its_release_and_the_sweep_leaves_the_run(
    cause, status, state
):
    """Bug caught: a hold re-supplied before its bound closed as anything but resolved, a cancel
    read as a re-supply, or the sweep still cancelling or releasing a run it no longer holds."""
    campaigns, cycles, progress, now, cycle, hold = await _world()
    await binding_hold.open_binding_hold(campaigns, cycle, "run_h", hold, HELD)
    await cycles.release_binding_hold("run_h", hold.hold_id, released_at=HELD, cause=cause)
    await cycles.update_run_status("run_h", status)
    cycles.releases.clear()
    now[0] = HELD + timedelta(seconds=BOUND)

    closed = await progress.sweep_ruling_bounds()

    assert [c["state"] for c in _closed(closed)] == [state]
    assert _closed(closed)[0]["cause"] == cause
    assert cycles.releases == []
    assert (await cycles.get_run("run_h")).status == status.value


async def test_a_re_supply_that_lands_before_the_sweeps_release_wins_and_the_run_goes_on():
    """The race #2178's compare-and-set settles. Bug caught: the sweep cancelling a run the
    executor released after the sweep read it."""
    campaigns, cycles, progress, now, cycle, hold = await _world()
    await binding_hold.open_binding_hold(campaigns, cycle, "run_h", hold, HELD)
    now[0] = HELD + timedelta(seconds=BOUND)
    real = cycles.release_binding_hold

    async def executor_first(run_id, hold_id, *, released_at, cause):
        await real(run_id, hold_id, released_at=HELD, cause="store_answered")
        return await real(run_id, hold_id, released_at=released_at, cause=cause)

    cycles.release_binding_hold = executor_first

    await progress.sweep_ruling_bounds()

    run = await cycles.get_run("run_h")
    assert run.status == RunStatus.PAUSED.value, "the sweep cancelled a re-supplied run"
    assert [h.cause for h in run.binding_holds] == ["store_answered"]


async def test_a_restart_re_entering_the_hold_writes_one_escalation_and_a_standalone_cycle_none():
    """Bug caught: a second escalation per restart, its bound reset each time; or a standalone
    cycle, which has no campaign to escalate to, given a row."""
    campaigns, cycles, progress, now, cycle, hold = await _world()

    first = await binding_hold.open_binding_hold(campaigns, cycle, "run_h", hold, HELD)
    again = await binding_hold.open_binding_hold(
        campaigns, cycle, "run_h", hold, HELD + timedelta(seconds=60)
    )
    standalone = await binding_hold.open_binding_hold(
        campaigns, dataclasses.replace(cycle, campaign_id=None), "run_h", hold, HELD
    )

    [esc] = escalations(await campaigns.control_log(CID), S.BUILDING)
    assert (first, again, standalone) == (True, True, False)
    assert esc.opened_at == HELD


async def test_a_hold_is_released_by_re_supply_and_never_answered():
    """Bug caught: a late answer recorded against a hold, which no launch or gate reads, so the
    owner believes they've unblocked a cycle they haven't."""
    campaigns, cycles, progress, now, cycle, hold = await _world(INPUT)
    await binding_hold.open_binding_hold(campaigns, cycle, "run_h", hold, HELD)
    [esc] = escalations(await campaigns.control_log(CID), S.BUILDING)

    refusal = answer_refusal(esc, {"d1": "use the old file"})

    assert refusal is not None and "released by re-supply, not by an answer" in refusal


@pytest.mark.parametrize(
    ("unresolved", "cls"),
    [
        (STORE + INPUT, binding_hold.HoldClass.STORE),
        (INPUT, binding_hold.HoldClass.INPUT),
        ((("mrec_x:1", "no kind given"),), binding_hold.HoldClass.INPUT),
    ],
    ids=["the-store-dominates", "input-alone", "a-kind-not-given-reads-as-input"],
)
def test_a_holds_cause_class_is_the_stores_when_any_record_is(unresolved, cls):
    """Bug caught: a hold with the store down read as an operator's input, so the owner is sent to
    fix an instruction that's fine; or an entry with no kind read as the store's, retried
    unheard."""
    assert binding_hold.hold_class(unresolved) is cls
