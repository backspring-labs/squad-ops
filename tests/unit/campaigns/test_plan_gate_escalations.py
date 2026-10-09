"""The plan-review tier's escalation queue (SIP-0109 §24bj, §24bk; #1708).

Entered at ``CampaignProgress.sweep_ruling_bounds``, the call ``main._sweep_campaigns`` makes every
interval, over a real memory campaign registry and a real memory cycle registry holding a tier
campaign's cycle, its framing run waiting at the plan gate, and the escalation the gate opened.

Bug classes guarded: a gate nobody answers waiting for ever (#1708's "no gate waits without bound");
an expiry that moves nothing, or a cycle parked that a person had already decided; an escalation
that ends twice, or one read as pending after its campaign ended; the §24aj overdue row contradicting
the expiry it shares a bound with.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.escalation import (
    EscalationIdentity,
    EscalationState,
    escalations,
    opening_transition,
    parked_run,
    plan_identity,
)
from squadops.campaigns.models import (
    CampaignState,
    ControlOperation,
    ControlOperationRefused,
    CycleKind,
    LaunchRequest,
)
from squadops.campaigns.plan_review_tier import TierCondition, plan_review_tier
from squadops.campaigns.progress import CampaignProgress
from squadops.cycles.models import Gate, GateDecision, Run, RunStatus, TaskFlowPolicy
from tests.unit.campaigns.builders import campaign, cycle_for, move, policy

S = CampaignState
CID = "cmp_escalate0001"
BOUND = 1800  # the builders' policy: the supervisor's ruling bound (§24al)
OPENED = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
GATE = "progress_plan_review"
SEQUENCE = [
    {"type": "proposal", "gate": "progress_increment_ruling"},
    {"type": "framing", "gate": GATE},
    {"type": "implementation", "gate": None},
]
QUESTION = "which order does the runs list use?"


def _run(run_id: str, n: int, workload: str, decided: str | None = None) -> Run:
    gate = "progress_increment_ruling" if workload == "proposal" else GATE
    return Run(
        run_id=run_id,
        cycle_id="",
        run_number=n,
        status="completed",
        initiated_by="system",
        resolved_config_hash="h",
        finished_at=OPENED,
        gate_decisions=(
            (GateDecision(gate, "approved", decided, OPENED, "an answer"),) if decided else ()
        ),
        workload_type=workload,
    )


def _flow_policy(profile: str) -> TaskFlowPolicy:
    """The task-flow policy a cycle launched on ``profile`` carries, its plan gate included."""
    from squadops.contracts.cycle_request_profiles import load_profile

    raw = load_profile(profile).defaults["task_flow_policy"]
    return TaskFlowPolicy(
        mode=raw["mode"],
        gates=tuple(
            Gate(g["name"], g["description"], tuple(g["after_task_types"]))
            for g in raw.get("gates") or ()
        ),
    )


def _identity(cycle_id: str, plan: str = "plan-a") -> EscalationIdentity:
    return EscalationIdentity(
        campaign_id=CID,
        cycle_id=cycle_id,
        run_id="run_f",
        gate_name=GATE,
        proposal_id="prop_cap",
        proposal_version=1,
        baseline="sha-accepted",
        plan_identity=plan_identity("manifest", plan),
    )


async def _world():
    campaigns = MemoryCampaignRegistry()
    cycles = MemoryCycleRegistry()
    await campaigns.create_campaign(
        campaign(CID, policy=policy(plan_gate="tier")),
        actor="o",
        actor_role="o",
        reason="r",
        idempotency_key="c",
    )
    await campaigns.transition(CID, move(S.CALIBRATING, "k0"))
    intent = (
        await campaigns.transition(
            CID, move(S.AT_PROPOSAL, "k1", launch=LaunchRequest(CycleKind.INCREMENT))
        )
    ).intent
    cycle = dataclasses.replace(
        cycle_for(intent),
        applied_defaults={"workload_sequence": SEQUENCE},
        task_flow_policy=_flow_policy("campaign-increment"),
    )
    await cycles.create_cycle(cycle)
    await campaigns.mark_launch_intent_launched(intent.launch_id, cycle.cycle_id, actor="l")
    await campaigns.transition(CID, move(S.AWAITING_RULING, "k2"))
    await campaigns.transition(CID, move(S.BUILDING, "k3"))
    for run in (
        _run("run_p", 1, "proposal", decided="human:owner"),
        _run("run_f", 2, "framing"),
    ):
        await cycles.create_run(dataclasses.replace(run, cycle_id=cycle.cycle_id))
    verdict = plan_review_tier(
        kind=CycleKind.INCREMENT,
        open_questions=(QUESTION,),
        footprint=("backend/routes.py",),
        allowed_scope=("backend/**",),
        refused_framing_runs=(),
        answered_on_record={},
    )
    await campaigns.transition(
        CID,
        opening_transition(
            _identity(cycle.cycle_id), verdict, (("list-ordering", QUESTION),), OPENED
        ),
    )
    now = [OPENED + timedelta(seconds=BOUND)]
    progress = CampaignProgress(
        campaigns=campaigns,
        cycles=cycles,
        vault=AsyncMock(),
        assess=AsyncMock(),
        launch=AsyncMock(),
        clock=lambda: now[0],
    )
    return campaigns, cycles, progress, now, cycle.cycle_id


def _closings(rows) -> list[tuple[str, str]]:
    return [
        (e.binding["state"], e.actor)
        for e in rows
        if e.operation is ControlOperation.ESCALATION_CLOSED
    ]


async def test_an_escalation_past_its_bound_expires_once_and_parks_its_run():
    """§24bj's expiry. Bugs caught: the gate waiting for ever; an expiry written every sweep; the
    run left waiting, so the cycle never ends parked; the §24aj overdue row, which shares the
    bound and says the gate still waits, written beside it."""
    campaigns, cycles, progress, now, _ = await _world()

    first = await progress.sweep_ruling_bounds()
    again = await progress.sweep_ruling_bounds()

    assert _closings(first) == [("expired", "squadops")]
    assert [e.operation for e in first] == [ControlOperation.ESCALATION_CLOSED]
    assert again == []
    assert (await cycles.get_run("run_f")).status == RunStatus.CANCELLED.value
    log = await campaigns.control_log(CID)
    assert parked_run(log, "run_f")
    assert [e.state for e in escalations(log, S.BUILDING)] == [EscalationState.EXPIRED]
    assert (await campaigns.get_campaign(CID)).state is S.BUILDING


async def test_before_its_bound_an_escalation_waits_and_nothing_moves():
    campaigns, cycles, progress, now, _ = await _world()
    now[0] = OPENED + timedelta(seconds=BOUND - 1)

    assert await progress.sweep_ruling_bounds() == []
    assert (await cycles.get_run("run_f")).status == RunStatus.COMPLETED.value
    log = await campaigns.control_log(CID)
    assert [e.state for e in escalations(log, S.BUILDING)] == [EscalationState.PENDING]


async def test_a_person_deciding_the_gate_resolves_it_and_the_run_goes_on():
    """Bug caught: a gate a person answered parked anyway because the bound passed meanwhile, or
    the escalation left pending once its gate was decided. A blank-noted answer resolves it too:
    the gate is decided, and its question is asked again at the next gate (§24ad, §24bk)."""
    campaigns, cycles, progress, now, cycle_id = await _world()
    answered = _run("run_f", 2, "framing", decided="human:owner")
    await cycles.record_gate_decision("run_f", answered.gate_decisions[0])

    rows = await progress.sweep_ruling_bounds()

    assert _closings(rows) == [("resolved", "human:owner")]
    assert (await cycles.get_run("run_f")).status == RunStatus.COMPLETED.value
    assert not parked_run(await campaigns.control_log(CID), "run_f")


async def test_a_run_that_stopped_waiting_with_no_decision_supersedes_it():
    """A supervisor's return re-framed the cycle, or an operator cancelled the run: the gate the
    escalation was opened for is no longer waiting, and nobody answered it."""
    campaigns, cycles, progress, now, _ = await _world()
    await cycles.cancel_run("run_f")

    rows = await progress.sweep_ruling_bounds()

    assert _closings(rows) == [("superseded", "squadops")]
    assert not parked_run(await campaigns.control_log(CID), "run_f")


async def test_an_escalation_ends_exactly_once():
    """Every ending shares one key, so a second ending of one escalation is a conflicting key:
    refused, recorded, and never applied. Bug caught: a late resolution un-parking a parked cycle
    in the record, or two endings read for one escalation."""
    from squadops.campaigns.escalation import RunAtGate, closing_transitions

    campaigns, cycles, progress, now, _ = await _world()
    await progress.sweep_ruling_bounds()
    log = await campaigns.control_log(CID)
    campaign_now = await campaigns.get_campaign(CID)
    # The same escalation, read as if it were still pending and a person had decided its gate.
    reopened = [e for e in log if e.operation is not ControlOperation.ESCALATION_CLOSED]
    [late] = closing_transitions(
        campaign_now, reopened, {"run_f": RunAtGate(waiting=True, decided_by="human:late")}, now[0]
    )

    with pytest.raises(ControlOperationRefused):
        await campaigns.transition(CID, late)
    log = await campaigns.control_log(CID)
    assert [e.state for e in escalations(log, S.BUILDING)] == [EscalationState.EXPIRED]


def test_an_escalation_pending_when_its_campaign_ended_reads_cancelled():
    from squadops.campaigns.models import ControlLogEntry, ControlOutcome

    verdict = plan_review_tier(
        kind=CycleKind.INCREMENT,
        open_questions=(QUESTION,),
        footprint=("backend/routes.py",),
        allowed_scope=("backend/**",),
        refused_framing_runs=(),
        answered_on_record={},
    )
    opening = opening_transition(
        _identity("cyc_x"), verdict, (("list-ordering", QUESTION),), OPENED
    )
    entry = ControlLogEntry(
        entry_id="ctl_1",
        campaign_id=CID,
        seq=7,
        operation=opening.operation,
        actor=opening.actor,
        actor_role=opening.actor_role,
        reason=opening.reason,
        target=opening.target,
        idempotency_key=opening.idempotency_key,
        request_hash="h",
        binding=opening.binding,
        outcome=ControlOutcome.APPLIED,
        refusal=None,
        prior_state=S.BUILDING,
        next_state=None,
        committed_at=OPENED,
    )

    [esc] = escalations([entry], S.COMPLETED)

    assert esc.state is EscalationState.CANCELLED
    assert esc.failed == ((str(TierCondition.NO_OPEN_QUESTION), f"1 open: {QUESTION}"),)
    assert esc.questions == (QUESTION,)


def test_an_escalations_identity_is_what_it_is_about():
    """The same gate, run and plan is one escalation (a re-entered gate replays it); a changed
    plan is another."""
    assert _identity("cyc_x").escalation_id == _identity("cyc_x").escalation_id
    assert _identity("cyc_x").escalation_id != _identity("cyc_x", plan="plan-b").escalation_id
    assert _identity("cyc_x").escalation_id.startswith("esc_")


async def test_the_digest_asks_while_pending_then_for_a_late_answer_then_shows_it():
    """The queue's reader is the owner's digest (§24bj). Bugs caught: an escalation the owner is
    never asked about; an expired one shown as settled with nothing to answer; a late answer that
    leaves the ask standing; unresolved work mixed into what was accepted."""
    from squadops.campaigns.escalation import answer_transition
    from squadops.campaigns.evidence import digest, package

    campaigns, cycles, progress, now, _ = await _world()

    async def read():
        return digest(
            package(await campaigns.get_campaign(CID), await campaigns.control_log(CID), [], [])
        )

    now[0] = OPENED + timedelta(seconds=BOUND - 1)
    await progress.sweep_ruling_bounds()
    pending = await read()
    now[0] = OPENED + timedelta(seconds=BOUND)
    await progress.sweep_ruling_bounds()
    expired = await read()
    [esc] = escalations(await campaigns.control_log(CID), S.BUILDING)
    await campaigns.transition(
        CID,
        answer_transition(
            esc,
            {esc.decision_ids[0]: "insertion order"},
            actor="human:owner",
            actor_role="owner",
            reason="late",
        ),
    )
    answered = await read()

    assert "The plan gate on `run_f` escalated: answer it at the gate" in pending
    assert f"Escalation `{esc.escalation_id}` expired with nobody answering" in expired
    assert f"squadops campaigns answer {CID} {esc.escalation_id}" in expired
    assert "expired with nobody answering" not in answered
    assert "Answered late by human:owner: list-ordering: insertion order" in answered
    # Kept apart from the accepted work: its own section.
    assert answered.index("## Escalations") > answered.index("## Accepted")
