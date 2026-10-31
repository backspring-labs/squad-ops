"""The proposal task's outcome evidence, on its own inputs and nowhere else (SIP-0113 §4.5; §10t
ruling 1).

What bugs would these catch? The evidence on a framing or build task, so every role is shown the
goals; the evidence in the cycle's resolved config, which is stored, served, copied into retries
and released; a correction round carrying it on from a task that held it; a proposal outside any
campaign asking a port that has nothing for it; nothing to show still changing the task's inputs;
and a failed read dispatching the proposal without its evidence.

Entered at ``RunProvisioning.prepare``, the step ``execute_run`` takes before dispatch, with the
real plan generation, and at ``CorrectionRunner.run_correction_protocol``. The goals are invented.
"""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.models import Run, WorkloadType
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.execution.execution_errors import _ExecutionError
from squadops.execution.run_provisioning import RunInProgress
from squadops.outcomes.proposal_evidence import (
    PROPOSAL_EVIDENCE_INPUT,
    AcceptedSection,
    GoalEvidence,
    GoalResult,
    ProposalEvidence,
    QualityMove,
)
from squadops.ports.outcomes import ProposalEvidencePort
from tests.unit.cycles.test_increment_evaluation_wiring import (
    _PLAN,
    CANDIDATE,
    PROFILE,
    STORED,
    _cycle,
)

pytestmark = [pytest.mark.domain_orchestration]

_STATEMENT = "A reader exports the ledger as a spreadsheet"
_EVIDENCE = ProposalEvidence(
    goals=(
        GoalEvidence("goal_export", _STATEMENT, GoalResult.FAILED),
        GoalEvidence("goal_search", "A reader finds an entry by its payee", GoalResult.PASSED),
    ),
    quality=(QualityMove("lint:total", 14, 9),),
    accepted_prd=(AcceptedSection("ledger", "Entries carry a payee and an amount."),),
)


class _Port(ProposalEvidencePort):
    def __init__(self, answer: ProposalEvidence | Exception = _EVIDENCE) -> None:
        self.answer = answer
        self.asked: list[tuple[str, str]] = []

    async def for_proposal(self, *, campaign_id: str, accepted_cycle_id: str) -> ProposalEvidence:
        self.asked.append((campaign_id, accepted_cycle_id))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _increment():
    """An increment as a campaign launches one: the ``campaign-increment`` profile's own
    defaults, and the accepted cycle on its launch block."""
    cycle = _cycle(True)
    return dataclasses.replace(
        cycle,
        applied_defaults={
            **dict(load_profile("campaign-increment").defaults),
            "build_profile": "fullstack_fastapi_react",
            "implementation_plan": True,
        },
    )


def _run(workload: str, number: int) -> Run:
    return Run(
        f"run_{workload}", "cyc_inc", number, "queued", "system", "cfg", workload_type=workload
    )


def _contract():
    """The candidate manifest's contract, as the approval forwards it to the framing (#1840)."""
    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- C1"]
    contract.behavioral.probes = ()
    contract.frozen_files = ()
    return contract


async def _prepare(
    port: ProposalEvidencePort, cycle, run: Run, plan=None, contract=None, change_request=STORED
) -> list:
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
        proposal_evidence=port,
        task_timeout=5.0,
    )
    executor._prepare_cycle_for_run = AsyncMock(return_value=(cycle, None))
    executor._cycle_registry.get_run.return_value = run
    executor._cycle_registry.get_latest_checkpoint.return_value = None
    executor._squad_profile.resolve_snapshot.return_value = (PROFILE, "sha")
    executor._load_plan_for_run = AsyncMock(return_value=plan)
    executor._load_contract_for_run = AsyncMock(return_value=contract)
    executor._seeded_manifest_for_authoring = AsyncMock(return_value=CANDIDATE)
    executor._cycle_event_bus = MagicMock()
    state = RunInProgress()
    with patch(
        "squadops.execution.run_provisioning.approved_change_request",
        AsyncMock(return_value=change_request),
    ):
        await executor._run_provisioning.prepare(
            state, cycle.cycle_id, run.run_id, "full", forwarding_overrides=None
        )
    return state.plan


async def test_an_increments_proposal_task_alone_carries_its_evidence():
    """Every run of one increment, as its campaign runs them: the proposal, the framing and the
    implementation. Bugs caught: the evidence on any other task, asked for any other run, or
    written into the resolved config every envelope carries."""
    port, cycle = _Port(), _increment()
    # The proposal's approval forwards the candidate manifest's contract to what follows (#1840).
    approved = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "contract_ref": "art_contract"}
    )
    plans = {
        WorkloadType.PROPOSAL: await _prepare(port, cycle, _run("proposal", 1)),
        WorkloadType.FRAMING: await _prepare(
            port, approved, _run("framing", 2), contract=_contract()
        ),
        WorkloadType.IMPLEMENTATION: await _prepare(
            port, approved, _run("implementation", 3), plan=_PLAN, contract=_contract()
        ),
    }

    carrying = [
        (workload, str(e.task_type))
        for workload, plan in plans.items()
        for e in plan
        if PROPOSAL_EVIDENCE_INPUT in e.inputs
    ]
    assert carrying == [(WorkloadType.PROPOSAL, "strategy.propose_increment")]
    assert port.asked == [("cmp_1", "cyc_accepted")]
    [proposal] = plans[WorkloadType.PROPOSAL]
    assert proposal.inputs[PROPOSAL_EVIDENCE_INPUT] == {
        "goals": [
            {"goal_id": "goal_export", "statement": _STATEMENT, "result": "failed"},
            {
                "goal_id": "goal_search",
                "statement": "A reader finds an entry by its payee",
                "result": "passed",
            },
        ],
        "quality": [{"measure": "lint:total", "before": 14, "after": 9}],
        "accepted_prd": [{"id": "ledger", "text": "Entries carry a payee and an amount."}],
        "held_back": 0,
    }
    # Nowhere else: not in the cycle's config, and on no envelope bar the proposal's own key.
    assert PROPOSAL_EVIDENCE_INPUT not in cycle.resolved_config()
    assert PROPOSAL_EVIDENCE_INPUT not in approved.resolved_config()
    elsewhere = [
        json.dumps({k: v for k, v in e.inputs.items() if k != PROPOSAL_EVIDENCE_INPUT}, default=str)
        for plan in plans.values()
        for e in plan
    ]
    assert len(elsewhere) > 3 and not [x for x in elsewhere if _STATEMENT in x]


async def test_a_correction_round_carries_no_evidence_on_from_the_task_it_repairs():
    """The widest premise: a failed build task that held the evidence. Bug caught: a repair, its
    analysis, its decision or its retest forwarding a failed task's inputs wholesale, so a goal
    reaches the developer who repairs the build."""
    from squadops.capabilities.context_assembly import retest_forwarded_inputs
    from squadops.execution.correction_runner import CorrectionRunner
    from squadops.tasks.models import TaskResult
    from tests.unit.cycles.test_correction_context_golden import (
        _CYCLE,
        _DEV_FAILED_INPUTS,
        _DEV_FAILED_RESULT,
        _HARNESS_PROFILE,
        _RUN_ID,
        _STEP_OUTPUTS,
        _failed_envelope,
    )

    failed_inputs = {**_DEV_FAILED_INPUTS, PROPOSAL_EVIDENCE_INPUT: _EVIDENCE.to_inputs()}
    runner = CorrectionRunner(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        event_bus=MagicMock(),
        task_dispatcher=AsyncMock(),
        store_artifact=AsyncMock(),
        failure_recall=NoOpFailurePatternRecall(),
    )
    dispatched = []

    async def _dispatch(step_envelope, *args, **kwargs):
        dispatched.append(step_envelope)
        outputs = _STEP_OUTPUTS.get(step_envelope.task_type, {"artifacts": []})
        return TaskResult(task_id=step_envelope.task_id, status="SUCCEEDED", outputs=dict(outputs))

    runner._dispatch_protocol_step = _dispatch  # type: ignore[method-assign]

    await runner.run_correction_protocol(
        run_id=_RUN_ID,
        cycle=_CYCLE,
        envelope=_failed_envelope("development.develop", failed_inputs, "dev"),
        result=_DEV_FAILED_RESULT,
        correction_attempts=0,
        prior_outputs={"dev": {"summary": "[dev] built"}},
        all_artifact_refs=["art_routes"],
        stored_artifacts=[],
        completed_task_ids=["task-development.develop"],
        plan_delta_refs=[],
        profile=_HARNESS_PROFILE,
        flow_run_id=None,
        interface_manifest=None,
        artifact_contents=None,
        scaffold_enforcement_carry=None,
        budget_guard=None,
        signature_state=None,
        correction_budget=3,
    )

    composed = [str(e.task_type) for e in dispatched]
    assert "development.correction_repair" in composed and "data.analyze_failure" in composed
    reached = [
        str(e.task_type) for e in dispatched if _STATEMENT in json.dumps(e.inputs, default=str)
    ]
    assert reached == []
    assert PROPOSAL_EVIDENCE_INPUT not in retest_forwarded_inputs(failed_inputs)


async def test_a_proposal_outside_any_campaign_asks_nothing_and_carries_nothing():
    """The reference's proposal half (§11a): an increment's block, and no campaign. Bug caught:
    the port asked for a campaign the cycle doesn't belong to, and the run failing on it."""
    port = _Port()
    cycle = dataclasses.replace(_increment(), campaign_id=None, kind=None)

    [proposal] = await _prepare(port, cycle, _run("proposal", 1))

    assert port.asked == []
    assert PROPOSAL_EVIDENCE_INPUT not in proposal.inputs


async def test_nothing_to_show_leaves_the_proposals_inputs_as_they_were():
    """Bug caught: an empty evidence written as a key, so every proposal's stored inputs change
    before §10t step 3 has anything to show."""
    cycle = _increment()
    [before] = await _prepare(_Port(ProposalEvidence()), cycle, _run("proposal", 1))
    port = _Port(ProposalEvidence())

    [after] = await _prepare(port, cycle, _run("proposal", 1))

    assert port.asked == [("cmp_1", "cyc_accepted")]
    assert after.inputs == before.inputs and PROPOSAL_EVIDENCE_INPUT not in after.inputs


@pytest.mark.parametrize(
    ("block_change", "answer", "raised", "match"),
    [
        ({}, RuntimeError("the evaluation store is down"), RuntimeError, "store is down"),
        ({"accepted_cycle_id": None}, _EVIDENCE, _ExecutionError, "names no accepted cycle"),
    ],
)
async def test_a_proposal_whose_evidence_cannot_be_read_is_never_dispatched(
    block_change, answer, raised, match
):
    """§10t ruling 6, require, don't default. Bugs caught: a failed read swallowed into a proposal
    shown nothing, and a campaign proposal with no accepted tree read as one with nothing to show.
    Either way the run's plan is never recorded, so nothing is dispatched."""
    cycle = _increment()
    block = {**cycle.execution_overrides["campaign_proposal"], **block_change}
    cycle = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "campaign_proposal": block}
    )

    with pytest.raises(raised, match=match):
        await _prepare(_Port(answer), cycle, _run("proposal", 1))


async def test_an_increments_framing_is_shown_its_request_without_the_goals_it_moves():
    """§10t ruling 4, entered at ``RunProvisioning.prepare`` for the framing run with the approved
    request as the vault returns it. Bug caught: the framing handed the stored document whole, so
    every design and test author learns which held-out goal the increment is aimed at."""
    from squadops.campaigns.change_request import (
        content_hash,
        load_stored_change_request,
        stored_change_request,
    )

    request = dataclasses.replace(load_stored_change_request(STORED), moves_goals=("goal_export",))
    named = stored_change_request(dataclasses.replace(request, content_hash=content_hash(request)))
    cycle = _increment()
    approved = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "contract_ref": "art_contract"}
    )

    plan = await _prepare(
        _Port(), approved, _run("framing", 2), contract=_contract(), change_request=named
    )

    shown = [
        e.inputs["increment_change_request"] for e in plan if "increment_change_request" in e.inputs
    ]
    assert len(shown) == len(plan) > 1
    assert not [d for d in shown if "goal_export" in d or "moves_goals" in d]
    assert yaml.safe_load(shown[0])["criteria"] == yaml.safe_load(named)["criteria"]


async def test_a_proposal_is_shown_its_accepted_trees_goals_through_the_reader():
    """§10t step 3, entered at ``RunProvisioning.prepare`` for the proposal run with the reader the
    runtime root builds, over a store holding the campaign's pinned suite and its accepted tree's
    evaluation. Bugs caught: the reader asked for another campaign or tree than the proposal's
    launch names, and a step's value or a blocked reason on any envelope."""
    from squadops.campaigns.models import CycleKind
    from squadops.outcomes.proposal_reader import StoredProposalEvidence
    from squadops.scenarios.models import CampaignSuitePin
    from tests.unit.outcomes.test_proposal_reader import (
        REASON,
        STEP_VALUE,
        SUITE,
        T0,
        _Campaigns,
        _record,
        _store,
    )

    store = await _store(pin=False)
    await store.save_pin(CampaignSuitePin("cmp_1", SUITE.digest, pinned_by="owner", pinned_at=T0))
    await store.save_evaluation(_record("cyc_accepted", "a" * 64, None, campaign_id="cmp_1"))
    campaigns = _Campaigns()
    campaigns.promote("cyc_accepted", CycleKind.CALIBRATION)
    reader = StoredProposalEvidence(
        scenarios=store, campaigns=campaigns, cycles=AsyncMock(), vault=AsyncMock()
    )

    [proposal] = await _prepare(reader, _increment(), _run("proposal", 1))

    shown = proposal.inputs[PROPOSAL_EVIDENCE_INPUT]
    assert [(g["goal_id"], g["result"]) for g in shown["goals"]] == [
        ("export", "failed"),
        ("search", "passed"),
        ("totals", "not verified"),
    ]
    assert shown["held_back"] == 1
    envelope = json.dumps(proposal.inputs, default=str)
    assert STEP_VALUE not in envelope and REASON not in envelope
