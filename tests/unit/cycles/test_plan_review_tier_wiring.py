"""The plan-review tier as a campaign cycle reaches it (SIP-0109 §24bj, #1708).

Entered at ``WorkloadGate.decide``, the seam ``execute_cycle`` calls between framing and
implementation, on the real executor with a memory campaign registry, and the framing run's
implementation plan and interface manifest in the vault: V4 roll 2's authored manifest, which asks one
question, or the same design with it answered. Plan validation is upstream of the tier and tested on
its own. What is asserted is who decided the gate, whether it waited for a person, and what the
escalation it opened records.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.workload_gate import GateOutcome
from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.campaigns.escalation import (
    EscalationIdentity,
    EscalationState,
    answer_transition,
    escalations,
    opening_transition,
)
from squadops.campaigns.models import (
    CampaignObjective,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    CycleKind,
    PlanGate,
)
from squadops.campaigns.plan_review_tier import GATE_DECIDED_BY_PLAN_REVIEW_TIER, plan_review_tier
from squadops.cycles.manifest_authoring import GATE_DECIDED_BY_NO_QUESTIONS, open_decisions
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    GateDecision,
    GateDecisionValue,
    Run,
    TaskFlowPolicy,
)
from squadops.events.types import EventType
from tests.unit.campaigns.builders import campaign, move, policy

NOW = datetime(2026, 10, 8, 14, 0, tzinfo=UTC)
CID = "cmp_tier00000001"
PRIOR = "cmp_prior0000001"
GATE = "progress_plan_review"
#: V4 roll 2's authored manifest: it asks one question, decision `expansion-gating`.
_ASKING = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "authored_v4"
    / "interface_manifest_roll2.yaml"
).read_text(encoding="utf-8")
[(DECISION, QUESTION)] = open_decisions(_ASKING)


def _answered(manifest_yaml: str) -> str:
    """The same design with every question answered."""
    data = yaml.safe_load(manifest_yaml)
    for d in data.get("decisions", []):
        if d.pop("unresolved", False):
            d["choice"] = "resolved for the test"
            d["warrant"] = "PRD §x"
            d.pop("question", None)
    return yaml.dump(data, sort_keys=False)


def _plan(*paths: str) -> str:
    return f"""\
version: 1
project_id: group_run
cycle_id: cyc_tier
prd_hash: h
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: capacity validation
    description: d
    expected_artifacts: [{", ".join(paths)}]
    acceptance_criteria: [a]
summary:
  total_dev_tasks: 1
  total_qa_tasks: 0
  total_tasks: 1
  estimated_layers: [backend]
"""


def _artifact(artifact_id: str, artifact_type: str, filename: str, content: str):
    ref = ArtifactRef(
        artifact_id=artifact_id,
        project_id="group_run",
        artifact_type=artifact_type,
        filename=filename,
        content_hash="h",
        size_bytes=len(content),
        media_type="text/yaml",
        created_at=NOW,
        cycle_id="cyc_tier",
        run_id="run_frame",
    )
    return artifact_id, (ref, content.encode())


class _Vault:
    def __init__(self, plan: str, manifest: str) -> None:
        self.stored = dict(
            [
                _artifact(
                    "art_plan", "control_implementation_plan", "implementation_plan.yaml", plan
                ),
                _artifact(
                    "art_manifest", "interface_manifest", "interface_manifest.yaml", manifest
                ),
            ]
        )

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, *, run_id=None, promotion_status=None, **_):
        return [
            r for r, _ in self.stored.values() if promotion_status in (None, r.promotion_status)
        ]

    async def promote_artifact(self, artifact_id):
        ref, content = self.stored[artifact_id]
        self.stored[artifact_id] = (dataclasses.replace(ref, promotion_status="promoted"), content)


def _run(run_id: str, *decisions: GateDecision) -> Run:
    return Run(
        run_id=run_id,
        cycle_id="cyc_tier",
        run_number=1,
        status="completed",
        initiated_by="system",
        resolved_config_hash="cfg",
        workload_type="framing",
        artifact_refs=("art_plan", "art_manifest"),
        gate_decisions=decisions,
    )


_REFUSED = GateDecision(
    gate_name=GATE,
    decision=GateDecisionValue.REJECTED.value,
    decided_by="system:plan_validation",
    decided_at=NOW,
    notes="the plan names a role the squad lacks",
)


async def _a_late_answer_on_record(campaigns: MemoryCampaignRegistry) -> None:
    """An earlier campaign of the project whose escalation on `expansion-gating` expired, and
    which the owner answered late (§24bj's ruling 4)."""
    await campaigns.create_campaign(
        campaign(PRIOR, policy=policy(plan_gate=PlanGate.TIER)),
        actor="owner",
        actor_role="owner",
        reason="r",
        idempotency_key="create-prior",
    )
    identity = EscalationIdentity(PRIOR, "cyc_prior", "run_prior", GATE, None, None, None, "p")
    verdict = plan_review_tier(
        kind=CycleKind.CALIBRATION,
        open_questions=(QUESTION,),
        footprint=("backend/main.py",),
        allowed_scope=("backend/**",),
        refused_framing_runs=(),
        answered_on_record={},
    )
    await campaigns.transition(
        PRIOR, opening_transition(identity, verdict, ((DECISION, QUESTION),), NOW)
    )
    await campaigns.transition(
        PRIOR,
        CampaignTransition(
            operation=ControlOperation.ESCALATION_CLOSED,
            actor="squadops",
            actor_role="sweep",
            reason="the bound passed",
            idempotency_key=f"escalation_closed:{identity.escalation_id}",
            next_state=None,
            target="run_prior",
            binding={"escalation_id": identity.escalation_id, "state": "expired"},
        ),
    )
    [expired] = escalations(await campaigns.control_log(PRIOR), CampaignState.DRAFT)
    await campaigns.transition(
        PRIOR,
        answer_transition(
            expired, "after two weeks", actor="human:owner", actor_role="owner", reason="late"
        ),
    )


async def _tier_cycle(kind: str = "increment") -> Cycle:
    return Cycle(
        cycle_id="cyc_tier",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref=None,
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        campaign_id=CID,
        kind=kind,
    )


async def _reach_the_gate(
    plan_gate: PlanGate,
    *,
    kind: str = "increment",
    plan: str = _plan("backend/routes.py", "backend/tests/test_t5.py"),
    earlier_framings: tuple[Run, ...] = (),
    asks: bool = False,
    answered_late: bool = False,
):
    campaigns = MemoryCampaignRegistry()
    if answered_late:
        await _a_late_answer_on_record(campaigns)
    objective = CampaignObjective(
        statement="evolve group_run",
        allowed_scope=("backend/**", "frontend/**"),
        measurement="two accepted increments",
        target_accepted_increments=2,
    )
    await campaigns.create_campaign(
        campaign(CID, objective=objective, policy=policy(plan_gate=plan_gate)),
        actor="owner",
        actor_role="owner",
        reason="r",
        idempotency_key="create",
    )
    await campaigns.transition(CID, move(CampaignState.CALIBRATING, "cal"))

    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    framing = _run("run_frame")
    registry = AsyncMock()
    registry.list_runs.return_value = [*earlier_framings, framing]
    registry.record_gate_decision.side_effect = lambda run_id, decision: framing
    executor = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=_Vault(plan, _ASKING if asks else _answered(_ASKING)),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        campaign_registry=campaigns,
        project_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
    )
    executor._cycle_event_bus = MagicMock()
    executor._reject_invalid_plan_before_workload_gate = AsyncMock(return_value=[])
    executor._approve_gate_without_questions = AsyncMock(
        return_value=GateDecision(
            gate_name=GATE,
            decision=GateDecisionValue.APPROVED.value,
            decided_by=GATE_DECIDED_BY_NO_QUESTIONS,
            decided_at=NOW,
        )
    )
    executor._poll_inter_workload_gate = AsyncMock(
        return_value=GateDecision(
            gate_name=GATE,
            decision=GateDecisionValue.APPROVED.value,
            decided_by="human:crew-supervisor",
            decided_at=NOW,
            notes="answered",
        )
    )
    cycle = await _tier_cycle(kind)
    step = await executor._workload_gate.decide(
        cycle=cycle,
        cycle_id=cycle.cycle_id,
        run=framing,
        workload_entry={"type": "framing", "gate": GATE},
        gate_name=GATE,
        current_run_id=framing.run_id,
        forwarding_overrides=None,
        framing_rerolls=0,
        framing_revisions=0,
        max_framing_rerolls=2,
        max_framing_revisions=0,
    )
    return executor, registry, step


def _recorded_deciders(registry) -> list[str]:
    return [c.args[1].decided_by for c in registry.record_gate_decision.await_args_list]


async def test_a_tier_campaigns_plan_every_condition_holds_for_is_approved_by_the_tier():
    """Bug caught: a tier campaign's gate decided by #807's pass-through (no record of the
    tier's reading) or left waiting on a person it does not need."""
    executor, registry, step = await _reach_the_gate(PlanGate.TIER)
    log = await executor._campaign_registry.control_log(CID)
    assert escalations(log, CampaignState.CALIBRATING) == []

    assert step.outcome is GateOutcome.PROCEED
    assert _recorded_deciders(registry) == [GATE_DECIDED_BY_PLAN_REVIEW_TIER]
    notes = registry.record_gate_decision.await_args.args[1].notes
    assert "inside_scope: held: all 2 files inside" in notes
    executor._approve_gate_without_questions.assert_not_awaited()
    executor._poll_inter_workload_gate.assert_not_awaited()


@pytest.mark.parametrize(
    ("reach", "failed"),
    [
        ({"plan": _plan("backend/routes.py", "docker-compose.yml")}, ["inside_scope"]),
        ({"earlier_framings": (_run("run_refused", _REFUSED),)}, ["framed_once"]),
        ({"asks": True}, ["no_open_question"]),
    ],
    ids=["outside scope", "a re-rolled framing", "an open question"],
)
async def test_a_plan_the_tier_cannot_approve_waits_for_a_person(reach, failed):
    """§24bj: the tier may only approve, and anything else escalates. Bug caught: a plan outside
    the objective's scope, or after a refused framing, approved because #807's pass-through would
    have approved it — the two conditions the pass-through never checked."""
    executor, registry, step = await _reach_the_gate(PlanGate.TIER, **reach)

    assert _recorded_deciders(registry) == []
    executor._approve_gate_without_questions.assert_not_awaited()
    executor._poll_inter_workload_gate.assert_awaited_once()
    (awaiting,) = [
        c
        for c in executor._cycle_event_bus.emit.call_args_list
        if c.args[0] == EventType.WORKLOAD_GATE_AWAITING
    ]
    assert awaiting.kwargs["payload"]["tier_failed"] == failed
    assert step.outcome is GateOutcome.PROCEED  # the person's answer moved it
    # §24bj: the gate opened one escalation, about this run and gate, naming what failed.
    campaigns = executor._campaign_registry
    [esc] = escalations(await campaigns.control_log(CID), CampaignState.CALIBRATING)
    assert (esc.run_id, esc.gate_name, esc.state) == ("run_frame", GATE, EscalationState.PENDING)
    assert [condition for condition, _ in esc.failed] == failed
    assert esc.questions == ((QUESTION,) if reach.get("asks") else ())
    assert esc.decision_ids == ((DECISION,) if reach.get("asks") else ())


async def test_re_entering_an_escalated_gate_after_a_restart_opens_no_second_escalation():
    """Keyed by what it is about (§24bj). Bug caught: a restart re-entering the gate opening a
    second escalation for the same plan, so one question expires twice."""
    executor, _, _ = await _reach_the_gate(PlanGate.TIER, asks=True)
    campaigns = executor._campaign_registry
    await executor._workload_gate.decide(
        cycle=await _tier_cycle(),
        cycle_id="cyc_tier",
        run=_run("run_frame"),
        workload_entry={"type": "framing", "gate": GATE},
        gate_name=GATE,
        current_run_id="run_frame",
        forwarding_overrides=None,
        framing_rerolls=0,
        framing_revisions=0,
        max_framing_rerolls=2,
        max_framing_revisions=0,
    )

    opened = [
        e
        for e in await campaigns.control_log(CID)
        if e.operation is ControlOperation.ESCALATION_OPENED
    ]
    assert len(opened) == 1


async def test_a_tier_calibrations_builder_notes_at_the_root_do_not_escalate_it():
    """The owner's ruling of 2026-10-08, live: both of this line's calibration plans name
    `assembly_notes.md` at the root."""
    executor, registry, _ = await _reach_the_gate(
        PlanGate.TIER, kind="calibration", plan=_plan("backend/main.py", "assembly_notes.md")
    )

    assert _recorded_deciders(registry) == [GATE_DECIDED_BY_PLAN_REVIEW_TIER]
    executor._poll_inter_workload_gate.assert_not_awaited()


async def test_a_supervised_campaign_keeps_the_pass_through_unchanged():
    """`supervised` is today's behaviour (§24bj). Bug caught: the tier's conditions applied to a
    campaign that never declared it, so a supervised plan outside scope would stop."""
    executor, registry, step = await _reach_the_gate(
        PlanGate.SUPERVISED, plan=_plan("backend/routes.py", "docker-compose.yml")
    )

    executor._approve_gate_without_questions.assert_awaited_once()
    executor._poll_inter_workload_gate.assert_not_awaited()
    assert _recorded_deciders(registry) == []
    assert step.outcome is GateOutcome.PROCEED


async def test_a_late_answer_on_record_answers_the_same_question_at_a_later_gate():
    """§24bj's ruling 4, read at the next campaign (§24bl): the owner's late answer to an earlier
    campaign's expired escalation answers the same decision, by id, so its question is not asked
    again. Bug caught: the late answer recorded where no gate reads it, so every campaign asks
    the question again and parks on it."""
    executor, registry, step = await _reach_the_gate(PlanGate.TIER, asks=True, answered_late=True)

    assert _recorded_deciders(registry) == [GATE_DECIDED_BY_PLAN_REVIEW_TIER]
    notes = registry.record_gate_decision.await_args.args[1].notes
    assert f"every question the design asks is answered on record: {DECISION} (esc_" in notes
    executor._poll_inter_workload_gate.assert_not_awaited()
    assert (
        escalations(await executor._campaign_registry.control_log(CID), CampaignState.CALIBRATING)
        == []
    )
