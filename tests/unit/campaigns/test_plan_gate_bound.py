"""A plan gate waiting on a design question is bounded as the increment gate is (#1708; §24ae).

A framing whose plan asks a question stops its cycle at ``progress_plan_review`` until someone
answers. Before this, that wait had no bound and left no record. Entered at the sweep the runtime
runs every interval, over a real memory cycle registry holding the campaign's cycle and its runs.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.gate import plan_gate_overdue_transitions, waiting_gate
from squadops.campaigns.models import CampaignState, ControlOperation, CycleKind, LaunchRequest
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.models import GateDecision, Run
from tests.unit.campaigns.builders import campaign, cycle_for, move

S = CampaignState
CID = "cmp_plangate0001"
BOUND = 1800  # the builders' policy: the supervisor's ruling bound (§24al)
OPENED = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
SEQUENCE = [
    {"type": "proposal", "gate": "progress_increment_ruling"},
    {"type": "framing", "gate": "progress_plan_review"},
    {"type": "implementation", "gate": None},
]


def _run(run_id: str, n: int, workload: str, status: str = "completed", decided: str | None = None):
    return Run(
        run_id=run_id,
        cycle_id="",
        run_number=n,
        status=status,
        initiated_by="system",
        resolved_config_hash="h",
        finished_at=OPENED if status == "completed" else None,
        gate_decisions=((GateDecision(decided, "approved", "crew", OPENED),) if decided else ()),
        workload_type=workload,
    )


@pytest.mark.parametrize(
    ("runs", "waits_at"),
    [
        (
            [
                _run("p", 1, "proposal", decided="progress_increment_ruling"),
                _run("f", 2, "framing"),
            ],
            "f",
        ),
        (
            [
                _run("p", 1, "proposal", decided="progress_increment_ruling"),
                _run("f", 2, "framing", decided="progress_plan_review"),
            ],
            None,
        ),
        (
            [
                _run("p", 1, "proposal", decided="progress_increment_ruling"),
                _run("f", 2, "framing", "running"),
            ],
            None,
        ),
        # A re-rolled framing: the newest run is read, not the run at the workload's position.
        (
            [
                _run("p", 1, "proposal", decided="progress_increment_ruling"),
                _run("f1", 2, "framing", decided="progress_plan_review"),
                _run("f2", 3, "framing"),
            ],
            "f2",
        ),
        ([_run("i", 3, "implementation")], None),  # no gate after the last workload
    ],
    ids=["waiting", "answered", "still-framing", "re-rolled", "no-gate"],
)
def test_the_gate_a_cycle_waits_at_is_read_from_its_newest_run(runs, waits_at):
    """Bug caught: an answered gate, a running framing or a gateless workload read as waiting
    (a row written for nothing), or a re-rolled framing's answered first run hiding the second."""
    found = waiting_gate("cyc_1", SEQUENCE, runs)
    assert (found.run_id if found else None) == waits_at


async def _world():
    campaigns = MemoryCampaignRegistry()
    cycles = MemoryCycleRegistry()
    await campaigns.create_campaign(
        campaign(CID), actor="o", actor_role="o", reason="r", idempotency_key="c"
    )
    await campaigns.transition(CID, move(S.CALIBRATING, "k0"))
    intent = (
        await campaigns.transition(
            CID, move(S.AT_PROPOSAL, "k1", launch=LaunchRequest(CycleKind.INCREMENT))
        )
    ).intent
    cycle = dataclasses.replace(cycle_for(intent), applied_defaults={"workload_sequence": SEQUENCE})
    await cycles.create_cycle(cycle)
    await campaigns.mark_launch_intent_launched(intent.launch_id, cycle.cycle_id, actor="l")
    await campaigns.transition(CID, move(S.AWAITING_RULING, "k2"))
    await campaigns.transition(CID, move(S.BUILDING, "k3"))
    for run in (
        _run("run_p", 1, "proposal", decided="progress_increment_ruling"),
        _run("run_f", 2, "framing"),
    ):
        await cycles.create_run(dataclasses.replace(run, cycle_id=cycle.cycle_id))
    now = [OPENED + timedelta(seconds=BOUND)]
    progress = CampaignProgress(
        campaigns=campaigns,
        cycles=cycles,
        vault=AsyncMock(),
        assess=AsyncMock(),
        launch=AsyncMock(),
        clock=lambda: now[0],
    )
    return campaigns, cycles, progress, now


async def test_the_sweep_bounds_a_plan_gate_once_and_answers_nothing():
    """Entered at ``CampaignProgress.sweep_ruling_bounds``, the call ``main._sweep_campaigns`` makes
    every interval. Bugs caught: a plan gate left waiting with no record (#1708); a row written
    every sweep; the campaign moved by the bound; the gate decided by it."""
    campaigns, cycles, progress, now = await _world()

    first = await progress.sweep_ruling_bounds()
    again = await progress.sweep_ruling_bounds()
    # The reading itself owes only what is unwritten: no transaction per sweep for a row on record.
    gate = waiting_gate(
        "cyc",
        SEQUENCE,
        [
            _run("run_p", 1, "proposal", decided="progress_increment_ruling"),
            _run("run_f", 2, "framing"),
        ],
    )
    owed = plan_gate_overdue_transitions(
        await campaigns.get_campaign(CID), await campaigns.control_log(CID), gate, now[0]
    )
    assert owed == []
    now[0] = OPENED + timedelta(seconds=24 * BOUND)
    later = await progress.sweep_ruling_bounds()

    assert [(e.operation, e.binding["gate"], e.target) for e in first] == [
        (ControlOperation.RULING_OVERDUE, "progress_plan_review", "run_f"),
    ]
    assert again == [] and later == []
    assert (await campaigns.get_campaign(CID)).state is S.BUILDING
    assert (await cycles.get_run("run_f")).gate_decisions == ()


async def test_the_digest_asks_for_the_answer_until_the_campaign_moves_on():
    """The row's reader is the owner's morning digest. Bugs caught: a bound recorded where nobody
    reads it; or an ask that outlives the answer."""
    from squadops.campaigns.evidence import digest, package

    campaigns, _cycles, progress, _now = await _world()
    await progress.sweep_ruling_bounds()

    async def read():
        return digest(
            package(await campaigns.get_campaign(CID), await campaigns.control_log(CID), [], [])
        )

    waiting = await read()
    await campaigns.transition(CID, move(S.EVALUATING, "k-moved"))
    moved = await read()

    ask = (
        "- The `progress_plan_review` gate on run `run_f` waits on an answer to its design "
        "question, past its ruling bound."
    )
    assert ask in waiting
    assert "progress_plan_review" not in moved


@pytest.mark.parametrize("state", [S.AWAITING_RULING, S.PAUSED, S.ESCALATED])
def test_a_campaign_not_working_on_a_cycle_is_owed_nothing(state):
    """Bug caught: a plan-gate row on a campaign the increment gate's bound already covers, or one
    that holds."""
    from squadops.campaigns.gate import WaitingGate

    held = dataclasses.replace(campaign(CID), state=state)
    gate = WaitingGate("cyc_1", "run_f", "progress_plan_review", OPENED)
    assert plan_gate_overdue_transitions(held, [], gate, OPENED + timedelta(days=1)) == []
