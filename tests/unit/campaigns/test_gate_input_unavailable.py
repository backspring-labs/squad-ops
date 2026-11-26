"""A Campaign cycle whose gate couldn't read a recorded artifact is the environment's (SIP-0109
§24ei, #3128; the 2.9 plan's item 4).

Entered where the runtime enters: the hearing the cycle's end calls (``CampaignProgress.cycle_ended``),
with the cycle's ending recorded as the completion boundary records it, before the campaign is
told. The executor's side, from the gate's raise to that record, is
``tests/unit/cycles/test_execute_cycle.py``.

What bugs would these catch?
- the ending decided by row 18 (the increment abandoned) or row 6 (proposed again), so a vault
  fault is charged to the squad's plan or its proposal;
- the retry launched with nothing on the record saying which artifact couldn't be read, so the
  escalation that follows a second failure can't name it;
- the detail read from somewhere other than the cycle's recorded ending, which is the one record
  a restart re-hears from.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.continuation import PendingAction
from squadops.campaigns.models import CampaignState, ControlOperation, CycleKind, LaunchRequest
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import Run, RunStatus
from tests.unit.campaigns.builders import campaign, cycle_for, move, policy

S = CampaignState
CID = "cmp_gateinput001"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
UNREAD = (
    "an artifact of the run its gate reads (artifact art_plan_9) couldn't be read from the vault "
    "(artifact_unretrieved): ConnectionError: the vault didn't answer. The run's record names "
    "it, so it is never treated as absent"
)


def _vacuous_accept(cycle_id: str, workload: str):
    """The assessment a cycle that never built can read: ``accepted`` with nothing executed. A
    cycle that ended at its gate must never be promoted on it."""
    from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
    from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict

    run = RunRecord(
        run_id="run_g",
        run_number=1,
        workload_type=workload,
        status="completed",
        started_at=NOW,
        finished_at=NOW,
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
    evidence = CycleEvidence(cycle_id=cycle_id, runs=(run,), verification_summary_runs=("run_g",))
    return assess(outcome, evidence, assessor=AssessorIdentity("2.9.0", None))


async def _world(workload: str):
    """A Campaign building an increment whose ``workload`` run completed, and whose gate then
    couldn't read one of the run's artifacts: the cycle's ending is recorded with its detail."""
    campaigns = MemoryCampaignRegistry()
    cycles = MemoryCycleRegistry()
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
    run = Run(
        run_id="run_g",
        cycle_id=cycle.cycle_id,
        run_number=1,
        status=RunStatus.COMPLETED.value,
        initiated_by="system",
        resolved_config_hash="h",
        workload_type=workload,
    )
    await cycles.create_run(run)
    await cycles.record_cycle_end(
        RecordedEnd(cycle.cycle_id, run.run_id, CycleStopReason.GATE_INPUT_UNAVAILABLE, UNREAD)
    )
    progress = CampaignProgress(
        campaigns=campaigns,
        cycles=cycles,
        vault=AsyncMock(),
        assess=AsyncMock(return_value=_vacuous_accept(cycle.cycle_id, workload)),
        launch=AsyncMock(),
        evaluate_outcome=None,
        evaluate_baseline=None,
        outcome_section=None,
        intervention_section=None,
        campaign_branch=None,
        goal_sets=None,
        clock=lambda: NOW,
    )
    return campaigns, cycles, progress, cycle, run


@pytest.mark.parametrize("workload", ["framing", "proposal"])
async def test_the_campaign_retries_it_and_its_decision_row_names_the_artifact(workload):
    campaigns, cycles, progress, cycle, run = await _world(workload)

    decision = await progress.cycle_ended(
        await cycles.get_cycle(cycle.cycle_id), run, CycleStopReason.GATE_INPUT_UNAVAILABLE
    )

    assert (decision.row, decision.action) == (10, PendingAction.RETRY)
    [decided] = [
        e
        for e in await campaigns.control_log(CID)
        if e.operation is ControlOperation.DECIDE and "row" in (e.binding or {})
    ]
    assert {k: decided.binding[k] for k in ("row", "ending", "verdict", "ending_detail")} == {
        "row": 10,
        "ending": "gate_input_unavailable",
        "verdict": None,
        "ending_detail": UNREAD,
    }
    assert "gate_input_unavailable" in decided.reason
    # Nothing was promoted, and the Campaign goes on: the squad's work said nothing.
    assert [
        e for e in await campaigns.control_log(CID) if e.operation is ControlOperation.PROMOTE
    ] == []
    assert (await campaigns.get_campaign(CID)).outcome is None


async def test_a_decision_row_carries_the_detail_only_when_its_ending_names_one():
    """The key rides only on a row that has one, so every other row hashes as it did. Bug caught:
    ``ending_detail: null`` written on every decision row."""
    from squadops.campaigns.continuation import ContinuationDecision, CycleEnding, Guard
    from squadops.campaigns.progress import decision_transition

    campaigns, _cycles, _progress, cycle, _run = await _world("framing")
    stored = await campaigns.get_campaign(CID)
    retry = ContinuationDecision(
        cycle.cycle_id, 10, action=PendingAction.RETRY, guard=Guard.PROCEED
    )

    without = decision_transition(
        stored, retry, ending=CycleEnding.HELD_STORE, verdict=None, launch=None
    )
    named = decision_transition(
        stored,
        retry,
        ending=CycleEnding.GATE_INPUT_UNAVAILABLE,
        verdict=None,
        launch=None,
        ending_detail=UNREAD,
    )

    assert "ending_detail" not in without.binding
    assert named.binding["ending_detail"] == UNREAD
