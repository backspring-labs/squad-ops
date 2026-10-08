"""The increment gate's ruling bound (SIP-0109 §9.2, §9.5, §19 criterion 10; §24ae; #1801).

§9.5's row: the ruling bound pauses the campaign (``awaiting_ruling``), and a ruling, or the
owner, resumes it. The sweep records each seat's bound as it passes, once per proposal version,
and rules on nothing. Through the memory registry, whose transaction adjudicates each row
against the committed campaign.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.gate import (
    gate_opened_at,
    ruling_overdue_transitions,
    ruling_transition,
    submission,
)
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.models import GateDecisionValue
from tests.unit.campaigns.builders import campaign, move

S = CampaignState
CID = "cmp_bound0000001"
BASE = "sha-accepted"
V1 = ProposalBinding("prop_1", 1, "hash-v1", BASE)
V2 = ProposalBinding("prop_1", 2, "hash-v2", BASE)
BOUND = 1800  # the builders' policy: the supervisor's ruling bound (§24al)


async def _submit(reg, binding, run_id):
    state = (await reg.get_campaign(CID)).state
    await reg.transition(CID, submission(state, SubmittedProposal(binding, "cyc_1", run_id)))


@pytest.fixture
async def at_the_gate() -> MemoryCampaignRegistry:
    reg = MemoryCampaignRegistry()
    await reg.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await reg.transition(CID, move(S.CALIBRATING, "k-cal"))
    await reg.transition(
        CID,
        move(
            S.CALIBRATING,
            "k-promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree(BASE, "cyc_cal"),
            binding={"cycle_id": "cyc_cal", "identity": BASE, "files": 2},
        ),
    )
    await reg.transition(CID, move(S.AT_PROPOSAL, "k-propose"))
    await _submit(reg, V1, "run_p1")
    return reg


async def _owed(reg, waited: float) -> list[str]:
    log = await reg.control_log(CID)
    now = gate_opened_at(log) + timedelta(seconds=waited)
    return [
        t.idempotency_key for t in ruling_overdue_transitions(await reg.get_campaign(CID), log, now)
    ]


@pytest.mark.parametrize(
    ("waited", "keys"),
    [
        (BOUND - 1, []),
        (BOUND, ["ruling_overdue:run_p1:v1"]),
        (24 * BOUND, ["ruling_overdue:run_p1:v1"]),
    ],
    ids=["inside-the-bound", "the-bound", "long-past-it"],
)
async def test_the_gate_is_owed_one_row_once_its_bound_passes(at_the_gate, waited, keys):
    """One bound, the supervisor's, whoever holds the seat (§24al). Bug caught: a bound read off
    by one, or a second row owed for the same version as the wait grows."""
    assert await _owed(at_the_gate, waited) == keys


async def test_the_sweep_records_each_bound_once_and_a_ruling_still_resolves_the_gate(
    at_the_gate,
):
    """Entered at ``CampaignProgress.sweep_ruling_bounds``, the call ``main._sweep_campaigns``
    makes every interval. Bugs caught: a bound left unrecorded (a gate unruled forever, §19
    criterion 10); a row written every sweep; the campaign moved off the gate, or a ruling
    after a bound refused, when §9.5 says a ruling resolves it; a bound that rules."""
    opened = gate_opened_at(await at_the_gate.control_log(CID))
    now = [opened + timedelta(seconds=BOUND)]
    progress = CampaignProgress(
        campaigns=at_the_gate,
        cycles=AsyncMock(),
        vault=AsyncMock(),
        assess=AsyncMock(),
        launch=AsyncMock(),
        clock=lambda: now[0],
    )

    first = await progress.sweep_ruling_bounds()
    again = await progress.sweep_ruling_bounds()
    # The reading itself owes only what is unwritten: no transaction per sweep for a row on record.
    assert await _owed(at_the_gate, 24 * BOUND) == []
    now[0] = opened + timedelta(seconds=24 * BOUND)
    later = await progress.sweep_ruling_bounds()

    assert [(e.operation, e.binding["version"], e.binding["bound_s"]) for e in first] == [
        (ControlOperation.RULING_OVERDUE, 1, BOUND),
    ]
    assert again == [] and later == []
    assert (await at_the_gate.get_campaign(CID)).state is S.AWAITING_RULING
    ruled = await at_the_gate.transition(
        CID,
        ruling_transition(
            GateDecisionValue.APPROVED,
            V1,
            run_id="run_p1",
            actor="crew-supervisor",
            actor_role="campaign-supervisor",
            reason="read late, after the bound",
            idempotency_key="k-rule",
        ),
    )
    assert ruled.campaign.state is S.BUILDING
    assert await progress.sweep_ruling_bounds() == []


async def test_a_gate_that_reopens_is_timed_from_its_reopening(at_the_gate):
    """The edges: a held proposal returned to the gate by a resume, and a revision's new
    version. Bug caught: a bound timed from the first submission, so a gate reopened after a
    long pause, or a fresh version, is overdue the moment it opens; or a version's row read as
    the next version's."""
    await at_the_gate.transition(CID, move(S.PAUSED, "k-pause", operation=ControlOperation.PAUSE))
    await at_the_gate.transition(
        CID, move(S.AWAITING_RULING, "k-resume", operation=ControlOperation.RESUME)
    )
    resumed = await at_the_gate.control_log(CID)
    assert gate_opened_at(resumed) == resumed[-1].committed_at
    assert await _owed(at_the_gate, BOUND - 1) == []

    await at_the_gate.transition(
        CID,
        ruling_transition(
            GateDecisionValue.RETURNED_FOR_REVISION,
            V1,
            run_id="run_p1",
            actor="crew-supervisor",
            actor_role="campaign-supervisor",
            reason="narrow the footprint",
            idempotency_key="k-revise",
            classification="criteria_not_checkable",
        ),
    )
    await _submit(at_the_gate, V2, "run_p2")
    log = await at_the_gate.control_log(CID)
    [row] = ruling_overdue_transitions(
        await at_the_gate.get_campaign(CID), log, gate_opened_at(log) + timedelta(seconds=BOUND)
    )
    assert (gate_opened_at(log), row.idempotency_key) == (
        log[-1].committed_at,
        "ruling_overdue:run_p2:v2",
    )


async def test_a_campaign_off_the_gate_is_owed_nothing(at_the_gate):
    """Bug caught: a building campaign recorded overdue for a gate already ruled."""
    await at_the_gate.transition(
        CID,
        ruling_transition(
            GateDecisionValue.APPROVED,
            V1,
            run_id="run_p1",
            actor="owner",
            actor_role="admin",
            reason="approved",
            idempotency_key="k-rule",
        ),
    )
    log = await at_the_gate.control_log(CID)

    owed = ruling_overdue_transitions(
        await at_the_gate.get_campaign(CID), log, gate_opened_at(log) + timedelta(days=2)
    )

    assert owed == []


async def test_the_runtime_sweeps_every_interval_and_survives_a_failed_sweep():
    """``main._sweep_campaigns``, the loop the runtime starts. Bug caught: one failed sweep (a
    database blip) ending the loop, so no bound is ever recorded again until a restart."""
    from types import SimpleNamespace

    from squadops.api.runtime import main

    progress = SimpleNamespace(
        sweep_ruling_bounds=AsyncMock(side_effect=[RuntimeError("db blip"), []])
    )
    with (
        patch.object(
            main.asyncio, "sleep", AsyncMock(side_effect=[None, None, asyncio.CancelledError()])
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await main._sweep_campaigns(SimpleNamespace(campaign_progress=progress))

    assert progress.sweep_ruling_bounds.await_count == 2


async def test_the_digest_asks_for_the_ruling_and_says_which_bounds_it_has_passed(at_the_gate):
    """The overdue row's reader: the owner's morning digest. Bug caught: a bound recorded where
    nobody reads it, so the owner is not told a gate has waited past its bound."""
    from squadops.campaigns.evidence import digest, package

    log = await at_the_gate.control_log(CID)
    [row] = ruling_overdue_transitions(
        await at_the_gate.get_campaign(CID), log, gate_opened_at(log) + timedelta(seconds=BOUND)
    )
    before = digest(package(await at_the_gate.get_campaign(CID), log, [], []))
    await at_the_gate.transition(CID, row)

    after = digest(
        package(await at_the_gate.get_campaign(CID), await at_the_gate.control_log(CID), [], [])
    )

    assert "- The increment gate waits on a ruling for `prop_1` v1. Rule it" in before
    assert (
        "- The increment gate waits on a ruling for `prop_1` v1, past its ruling bound. "
        "Rule it, or abort the campaign." in after
    )
