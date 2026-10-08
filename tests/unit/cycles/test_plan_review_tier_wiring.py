"""The plan-review tier as a campaign cycle reaches it (SIP-0109 §24bj, #1708).

Entered at ``WorkloadGate.decide``, the seam ``execute_cycle`` calls between framing and
implementation, on the real executor with a memory campaign registry and the framing run's real
implementation plan in the vault. Plan validation and the design's questions are upstream of the
tier and tested on their own; here they are what the gate read. What is asserted is who decided the
gate, and whether it waited for a person.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.workload_gate import GateOutcome
from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.campaigns.models import CampaignObjective, CampaignState, PlanGate
from squadops.campaigns.plan_review_tier import GATE_DECIDED_BY_PLAN_REVIEW_TIER
from squadops.cycles.manifest_authoring import GATE_DECIDED_BY_NO_QUESTIONS
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
GATE = "progress_plan_review"


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


class _Vault:
    def __init__(self, plan: str) -> None:
        ref = ArtifactRef(
            artifact_id="art_plan",
            project_id="group_run",
            artifact_type="control_implementation_plan",
            filename="implementation_plan.yaml",
            content_hash="h",
            size_bytes=len(plan),
            media_type="text/yaml",
            created_at=NOW,
            cycle_id="cyc_tier",
            run_id="run_frame",
        )
        self.stored = {"art_plan": (ref, plan.encode())}

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
        artifact_refs=("art_plan",),
        gate_decisions=decisions,
    )


_REFUSED = GateDecision(
    gate_name=GATE,
    decision=GateDecisionValue.REJECTED.value,
    decided_by="system:plan_validation",
    decided_at=NOW,
    notes="the plan names a role the squad lacks",
)


async def _reach_the_gate(
    plan_gate: PlanGate,
    *,
    kind: str = "increment",
    plan: str = _plan("backend/routes.py", "backend/tests/test_t5.py"),
    earlier_framings: tuple[Run, ...] = (),
    questions: tuple[str, ...] = (),
):
    campaigns = MemoryCampaignRegistry()
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
        artifact_vault=_Vault(plan),
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
    executor._design_questions_for_gate = AsyncMock(return_value=questions)
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
    cycle = Cycle(
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
        ({"questions": ("which order does the runs list use?",)}, ["no_open_question"]),
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
