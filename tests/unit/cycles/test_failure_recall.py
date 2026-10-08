"""Supplying approved lessons when a run's plan is composed (SIP-0110 §0.8–§0.9; #2096, on #1964's
call site).

What bugs would these catch? A memory-disabled or empty unit handing a task anything, so the
counted rolls' inputs change when nothing is approved; a consuming task with no exposure, so a
measurement cannot tell "disabled" from "never asked"; lessons handed to a task their approval
does not cover; a scope read from anywhere but the plan the framework wrote; a campaign's cycle
reading a snapshot of its own; and a call site off the path a run takes.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import generate_task_plan
from squadops.memory.lessons import (
    ANY_STACK,
    Applicability,
    Approval,
    PatternRevision,
    UnitKind,
    pattern_id_for,
)
from squadops.memory.pinning import pin_unit
from squadops.memory.recall import LESSONS_INPUT

pytestmark = [pytest.mark.domain_memory]

_NOW = datetime(2026, 10, 8, tzinfo=UTC)
_MODEL = "qwen3.8:27b"


def _framing_cycle(**changes) -> Cycle:
    cycle = Cycle(
        cycle_id="cyc_recall",
        project_id="group_run",
        created_at=_NOW,
        created_by="s",
        prd_ref="PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={
            "plan_authoring_contributors": ["development", "qa", "strategy"],
            "build_profile": "fullstack_fastapi_react",
        },
        execution_overrides={},
        expected_artifact_types=["source"],
    )
    return dataclasses.replace(cycle, **changes)


def _framing_run() -> Run:
    return Run(
        run_id="run_recall0001",
        cycle_id="cyc_recall",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=WorkloadType.FRAMING,
    )


_PROFILE = SquadProfile(
    profile_id="full",
    name="F",
    description="d",
    version=1,
    agents=[
        AgentProfileEntry(agent_id=a, role=r, model=_MODEL, enabled=True, serves_roles=(r,))
        for a, r in (("max", "lead"), ("neo", "dev"), ("nat", "strat"), ("eve", "qa"))
    ]
    + [
        AgentProfileEntry(
            agent_id="data", role="data", model=_MODEL, enabled=True, serves_roles=("data",)
        )
    ],
    created_at=_NOW,
)

_DESIGN = Applicability(
    project_id="group_run",
    task_types=("development.design_plan",),
    roles=("dev",),
    stacks=("fullstack_fastapi_react",),
    model_families=("qwen3.8",),
)


async def _store_with(*approved: tuple[str, Applicability]) -> InMemoryCrossCycleMemoryStore:
    store = InMemoryCrossCycleMemoryStore()
    for text, where in approved:
        revision = PatternRevision(
            pattern_id=pattern_id_for("group_run", text, where.task_types[0]),
            revision=1,
            target_behavior=text,
            text=text,
            applicability=where,
            template_id="lesson.t",
            template_version="1",
            drafter_model="auditor",
            drafter_version="1",
            cited_observations=("correction_round:x",),
            created_at=_NOW,
        )
        await store.record_revision(revision)
        await store.record_approval(
            Approval(f"apr_{text}", revision.revision_id, where, "owner", _NOW)
        )
    return store


async def _pinned(store, unit_kind, unit_id, *, disabled=False):
    await pin_unit(
        store,
        unit_kind=unit_kind,
        unit_id=unit_id,
        project_id="group_run",
        pinned_at=_NOW.replace(hour=1),
        disabled=disabled,
    )


def _plan(cycle=None):
    return generate_task_plan(cycle or _framing_cycle(), _framing_run(), _PROFILE)


async def _supplied(recall, cycle=None):
    cycle = cycle or _framing_cycle()
    return await supply_lessons(
        _plan(cycle),
        recall=recall,
        unit=unit_of(cycle),
        stack="fullstack_fastapi_react",
        run_id="run_recall0001",
        now=_NOW,
    )


@pytest.mark.parametrize("unit", ["disabled", "empty", "no recall"])
async def test_a_unit_with_nothing_to_supply_hands_every_task_its_inputs_unchanged(unit):
    """§0.9's inertness, at the inputs. Bug caught: a key written on every envelope whatever the
    answer, so every prompt that renders its inputs changes when nothing is approved."""
    store = await _store_with()
    await _pinned(store, UnitKind.CYCLE, "cyc_recall", disabled=unit == "disabled")
    recall = NoOpFailurePatternRecall() if unit == "no recall" else SnapshotRecall(store)

    supplied = await _supplied(recall)

    assert [e.inputs for e in supplied] == [e.inputs for e in _plan()]


async def test_every_consuming_task_discloses_its_answer_and_no_other_task_does():
    """§0.7: a memory-disabled unit's every consuming task records a ``memory_disabled`` exposure.
    Bug caught: an exposure missing for a disabled task, so the counted rolls' series without
    memory cannot be told from tasks that were never asked."""
    store = await _store_with()
    await _pinned(store, UnitKind.CYCLE, "cyc_recall", disabled=True)

    supplied = await _supplied(SnapshotRecall(store))

    exposures = await store.list_exposures("run_recall0001")
    consuming = {e.task_id for e in supplied if authoring_seam_of(str(e.task_type))}
    assert consuming  # a framing plan has plan writers
    assert {x.task_id for x in exposures} == consuming
    assert {x.disposition for x in exposures} == {"memory_disabled"}
    # §0.15 identity: the agent that ran the task, kept apart from its role.
    by_task = {e.task_id: e for e in supplied}
    assert all(x.agent_id == by_task[x.task_id].agent_id for x in exposures)
    assert {x.agent_id for x in exposures} != {x.query.role for x in exposures}


async def test_a_lesson_reaches_exactly_the_tasks_its_approval_covers_with_the_plans_own_scope():
    """§0.8 steps 1 and 3. Bugs caught: a lesson handed to another plan writer; or the scope
    read from somewhere but the plan the framework wrote (the role from the agent's name, the
    family unknown for a registered model), so the approved lesson reaches nobody."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")

    supplied = await _supplied(SnapshotRecall(store))

    handed = {
        str(e.task_type): e.inputs[LESSONS_INPUT] for e in supplied if LESSONS_INPUT in e.inputs
    }
    assert list(handed) == ["development.design_plan"]
    assert [lesson["text"] for lesson in handed["development.design_plan"]["lessons"]] == [
        "Name the manifest element each criterion checks."
    ]
    [design] = [
        x
        for x in await store.list_exposures("run_recall0001")
        if x.query.task_type == "development.design_plan"
    ]
    assert (design.query.role, design.query.stack, design.query.model_family) == (
        "dev",
        "fullstack_fastapi_react",
        "qwen3.8",
    )
    assert design.disposition == "supplied"


async def test_a_lesson_for_any_stack_and_one_for_another_family_are_told_apart():
    """Bug caught: a lesson tuned on another family's mistakes handed to this squad's model."""
    any_stack = dataclasses.replace(_DESIGN, stacks=(ANY_STACK,))
    other_family = dataclasses.replace(_DESIGN, model_families=("qwen3.6",))
    store = await _store_with(("any stack", any_stack), ("other family", other_family))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")

    supplied = await _supplied(SnapshotRecall(store))

    [design] = [e for e in supplied if str(e.task_type) == "development.design_plan"]
    assert [lesson["text"] for lesson in design.inputs[LESSONS_INPUT]["lessons"]] == ["any stack"]


async def test_a_campaigns_cycle_selects_from_its_campaigns_snapshot():
    """§0.7. Bug caught: a campaign's cycle reading a snapshot of its own, which it never pinned,
    so every task of every campaign records recall as failed."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CAMPAIGN, "cmp_x")
    cycle = _framing_cycle(campaign_id="cmp_x")

    supplied = await _supplied(SnapshotRecall(store), cycle)

    assert unit_of(cycle) == (UnitKind.CAMPAIGN, "cmp_x")
    assert any(LESSONS_INPUT in e.inputs for e in supplied)
    assert {x.query.unit_id for x in await store.list_exposures("run_recall0001")} == {"cmp_x"}


async def test_a_unit_with_no_pin_hands_nothing_and_records_the_recall_as_failed():
    """§0.8. Bug caught: a unit whose pin failed read as memory off, so its tasks count as a
    memory-off trial rather than an invalid measurement."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))

    supplied = await _supplied(SnapshotRecall(store))

    assert not any(LESSONS_INPUT in e.inputs for e in supplied)
    assert {x.disposition for x in await store.list_exposures("run_recall0001")} == {
        "recall_failed"
    }


async def test_provisioning_supplies_the_plan_it_builds():
    """Wiring, entered at ``RunProvisioning.prepare``, the step ``execute_run`` takes before
    dispatch, with the real plan generation and the snapshot recall over a store. Bug caught: the
    call site off the run's path, so an approved lesson would reach no envelope."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
    from adapters.cycles.run_provisioning import RunInProgress

    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=SnapshotRecall(store),
        task_timeout=5.0,
    )
    cycle, run = _framing_cycle(), _framing_run()
    executor._prepare_cycle_for_run = AsyncMock(return_value=(cycle, None))
    executor._cycle_registry.get_run.return_value = run
    executor._cycle_registry.get_latest_checkpoint.return_value = None
    executor._squad_profile.resolve_snapshot.return_value = (_PROFILE, "sha")
    executor._load_plan_for_run = AsyncMock(return_value=None)
    executor._load_contract_for_run = AsyncMock(return_value=None)
    executor._cycle_event_bus = MagicMock()
    state = RunInProgress()

    await executor._run_provisioning.prepare(
        state, cycle.cycle_id, run.run_id, "full", forwarding_overrides=None
    )

    [design] = [e for e in state.plan if str(e.task_type) == "development.design_plan"]
    assert design.inputs[LESSONS_INPUT]["lessons"][0]["revision_id"].endswith("@1")
    assert await store.list_exposures(run.run_id)


async def test_a_correction_repair_is_supplied_its_lessons_when_it_is_composed():
    """Repair (§0.9), entered at ``CorrectionRunner.run_correction_protocol`` with the snapshot
    recall, composing a real dev repair of a failed ``development.develop``. Bugs caught: the
    repair composed without asking, so a correction-round lesson reaches only the next cycle's
    first authoring; or the analyzer and the decision, which author no output, handed lessons."""
    from adapters.cycles.correction_runner import CorrectionRunner
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

    repair_where = Applicability(
        project_id="proj",
        task_types=("development.correction_repair",),
        roles=("dev",),
        stacks=(ANY_STACK,),
        model_families=("qwen3.8",),
    )
    store = InMemoryCrossCycleMemoryStore()
    for text, where in (("Declare the field the client reads.", repair_where),):
        revision = PatternRevision(
            pattern_id=pattern_id_for("proj", text, "development.correction_repair"),
            revision=1,
            target_behavior=text,
            text=text,
            applicability=where,
            template_id="lesson.t",
            template_version="1",
            drafter_model="auditor",
            drafter_version="1",
            cited_observations=("correction_round:x",),
            created_at=_NOW,
        )
        await store.record_revision(revision)
        await store.record_approval(Approval("apr_r", revision.revision_id, where, "owner", _NOW))
    await pin_unit(
        store,
        unit_kind=UnitKind.CYCLE,
        unit_id=_CYCLE.cycle_id,
        project_id="proj",
        pinned_at=_NOW.replace(hour=1),
        disabled=False,
    )
    profile = dataclasses.replace(
        _HARNESS_PROFILE,
        agents=tuple(dataclasses.replace(a, model=_MODEL) for a in _HARNESS_PROFILE.agents),
    )
    runner = CorrectionRunner(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        event_bus=MagicMock(),
        task_dispatcher=AsyncMock(),
        store_artifact=AsyncMock(),
        failure_recall=SnapshotRecall(store),
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
        envelope=_failed_envelope("development.develop", _DEV_FAILED_INPUTS, "dev"),
        result=_DEV_FAILED_RESULT,
        correction_attempts=0,
        prior_outputs={"dev": {"summary": "[dev] built"}},
        all_artifact_refs=["art_routes"],
        stored_artifacts=[],
        completed_task_ids=["task-development.develop"],
        plan_delta_refs=[],
        profile=profile,
        flow_run_id=None,
        interface_manifest=None,
        artifact_contents=None,
        scaffold_enforcement_carry=None,
        budget_guard=None,
        signature_state=None,
        correction_budget=3,
    )

    handed = {str(e.task_type): e.inputs.get(LESSONS_INPUT) for e in dispatched}
    assert [x["text"] for x in handed["development.correction_repair"]["lessons"]] == [
        "Declare the field the client reads."
    ]
    assert handed["data.analyze_failure"] is None
    assert handed["governance.correction_decision"] is None
    [exposure] = await store.list_exposures(_RUN_ID)
    assert (exposure.seam, exposure.disposition) == ("repair", "supplied")
