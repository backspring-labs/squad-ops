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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.handlers.fault_injection import PRIOR_ATTEMPTS_KEY
from squadops.capabilities.lesson_supply import supply_lessons, supply_the_dispatch, unit_of
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import generate_task_plan
from squadops.memory.exposures import exposure_id_for
from squadops.memory.lessons import (
    ANY_STACK,
    Applicability,
    Approval,
    PatternRevision,
    RecallDisposition,
    Recalled,
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


async def test_every_consuming_task_asks_the_context_port_with_its_cycle_and_its_snapshot_owner():
    """#2176: the seams go through the context-assembly port. Bugs caught: a seam that still calls
    recall directly, so 2.4's binding sections would never reach it; a request whose snapshot owner is
    the cycle, so a campaign's cycle asks a snapshot it never pinned; a target cycle taken from the
    campaign, so a task instruction for one cycle would match another (§3.7)."""
    from squadops.capabilities.lesson_supply import LessonContextAssembly
    from squadops.memory.context import UnitRef

    seen = []
    original = LessonContextAssembly.assemble

    async def spy(self, request):
        seen.append(request)
        return await original(self, request)

    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CAMPAIGN, "cmp_x")
    cycle = _framing_cycle(campaign_id="cmp_x")
    with patch.object(LessonContextAssembly, "assemble", spy):
        supplied = await _supplied(SnapshotRecall(store), cycle)

    consuming = [e.task_id for e in supplied if authoring_seam_of(str(e.task_type))]
    assert [r.consumer.task_id for r in seen] == consuming
    assert {(r.consumer.target_cycle_id, r.consumer.snapshot_owner) for r in seen} == {
        (cycle.cycle_id, UnitRef(UnitKind.CAMPAIGN, "cmp_x"))
    }
    assert {r.binding.project_id for r in seen} == {cycle.project_id}


async def test_a_unit_with_no_pin_hands_nothing_and_records_the_recall_as_failed():
    """§0.8. Bug caught: a unit whose pin failed read as memory off, so its tasks count as a
    memory-off trial rather than an invalid measurement."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))

    supplied = await _supplied(SnapshotRecall(store))

    assert not any(LESSONS_INPUT in e.inputs for e in supplied)
    assert {x.disposition for x in await store.list_exposures("run_recall0001")} == {
        "recall_failed"
    }


def _redispatched(envelope):
    """``envelope`` as the loop holds it for its second dispatch: stamped with the one attempt
    made (#1304), beside the enriched copy the loop actually dispatches."""
    envelope.inputs[PRIOR_ATTEMPTS_KEY] = 1
    return envelope, dataclasses.replace(envelope, inputs=dict(envelope.inputs))


async def test_a_redispatched_task_records_its_own_exposure_and_its_first_keeps_its_id():
    """§0.2: an exposure is one authoring invocation's (#2162). Bugs caught: a re-take or an
    emission retry, which authors again with its own envelope, recording nothing, so its output
    has no exposure to be assessed under; or the first attempt's id moving, so the exposures
    already stored no longer join to their envelopes; or a task at no consuming seam asking."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    supplied = await _supplied(SnapshotRecall(store))
    [design] = [e for e in supplied if str(e.task_type) == "development.design_plan"]
    other = next(e for e in supplied if authoring_seam_of(str(e.task_type)) is None)

    for task in (design, other):
        await supply_the_dispatch(
            _redispatched(task),
            recall=SnapshotRecall(store),
            cycle=_framing_cycle(),
            run_id="run_recall0001",
            now=_NOW,
        )

    exposures = await store.list_exposures("run_recall0001")
    mine = sorted((x for x in exposures if x.task_id == design.task_id), key=lambda x: x.attempt)
    assert [(x.attempt, x.disposition) for x in mine] == [(1, "supplied"), (2, "supplied")]
    assert mine[0].exposure_id == exposure_id_for("run_recall0001", design.task_id)
    assert mine[1].exposure_id != mine[0].exposure_id
    assert not [x for x in exposures if x.task_id == other.task_id]


async def test_a_redispatch_answered_with_nothing_carries_no_earlier_lesson():
    """Bug caught: the re-dispatch keeping the lesson its first attempt was handed while its own
    exposure records that recall failed, so the record says memory was off for an authoring that
    rendered a lesson. Both envelopes the loop holds are kept equal to the answer."""
    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    supplied = await _supplied(SnapshotRecall(store))
    [design] = [e for e in supplied if str(e.task_type) == "development.design_plan"]
    assert LESSONS_INPUT in design.inputs
    held = _redispatched(design)

    class _LessonsUnread(SnapshotRecall):
        """The lessons' read fails; the snapshot's pinned instructions, which bind, still read
        (#2179: an unreadable snapshot holds the task instead)."""

        async def recall(self, query):
            return Recalled(None, RecallDisposition.FAILED)

    await supply_the_dispatch(
        held,
        recall=_LessonsUnread(store),
        cycle=_framing_cycle(),
        run_id="run_recall0001",
        now=_NOW,
    )

    assert [LESSONS_INPUT in e.inputs for e in held] == [False, False]
    [second] = [x for x in await store.list_exposures("run_recall0001") if x.attempt == 2]
    assert (second.task_id, second.disposition) == (design.task_id, "recall_failed")


async def test_a_task_the_run_dispatches_again_records_an_exposure_per_dispatch(reply_router):
    """Wiring, entered at ``execute_run`` with the snapshot recall over a store: a framing run whose
    design-plan writer fails once on transport and is dispatched again. Bug caught (#2162, the
    rebuild 5 and 6 Next.js regression cycles): the re-dispatch rode the first attempt's envelope
    and recorded nothing, so 11 authorings had 10 exposures. Each dispatch's exposure is joined by
    the attempt its envelope carries."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.tasks.models import TaskResult

    store = await _store_with()
    await _pinned(store, UnitKind.CYCLE, "cyc_recall", disabled=True)
    cycle, run = _framing_cycle(), _framing_run()
    registry = AsyncMock()
    registry.get_cycle.return_value = cycle
    registry.get_run.return_value = run
    registry.get_latest_checkpoint.return_value = None
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (_PROFILE, "sha")
    queue = reply_router.bind(AsyncMock())
    executor = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=AsyncMock(),
        queue=queue,
        squad_profile=profiles,
        task_timeout=5.0,
        reply_router=reply_router,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=SnapshotRecall(store),
        proposal_evidence=NoOpProposalEvidence(),
    )
    dispatched: list[tuple[str, int]] = []

    def responder(env):
        inputs = env.get("inputs") or {}
        dispatched.append((env["task_id"], int(inputs.get(PRIOR_ATTEMPTS_KEY) or 0) + 1))
        first_design = env["task_type"] == "development.design_plan" and not inputs.get(
            PRIOR_ATTEMPTS_KEY
        )
        if first_design:
            return TaskResult(task_id=env["task_id"], status="FAILED", error="transient")
        return TaskResult(task_id=env["task_id"], status="SUCCEEDED", outputs={"summary": "ok"})

    reply_router.responder = responder
    with patch("squadops.execution.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock):
        await executor.execute_run(cycle_id=cycle.cycle_id, run_id=run.run_id)

    consuming = {t for t, _ in dispatched if authoring_seam_of(t.rsplit("-", 1)[-1])}
    recorded = {(x.task_id, x.attempt) for x in await store.list_exposures(run.run_id)}
    assert [a for t, a in dispatched if t.endswith("-development.design_plan")] == [1, 2]
    assert recorded == {(t, a) for t, a in dispatched if t in consuming}


_DESIGN_TASK = "development.design_plan"


async def test_provisioning_checks_the_plan_and_hands_nothing():
    """Wiring, entered at ``RunProvisioning.prepare``, the step ``execute_run`` takes before
    dispatch, with the real plan generation and the snapshot recall over a store. Bug caught
    (#2684): every authoring task's exposure recorded before any dispatched, so each read as
    dispatched and an instruction added for a task that never ran was refused. The plan is only
    checked here; each task is composed at its own dispatch."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.execution.run_provisioning import RunInProgress

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
        proposal_evidence=NoOpProposalEvidence(),
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

    [design] = [e for e in state.plan if str(e.task_type) == _DESIGN_TASK]
    assert LESSONS_INPUT not in design.inputs
    assert await store.list_exposures(run.run_id) == []


async def test_a_dispatch_carries_the_lessons_its_own_exposure_names(reply_router):
    """Wiring, entered at ``execute_run`` with the snapshot recall over a store holding a lesson for
    the design writer. Bug caught (#2681): the lessons composed when the plan was, not at the
    dispatch, so they never reached the envelope the agent received, or reached it without the
    exposure that discloses them."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.tasks.models import TaskResult

    store = await _store_with(("Name the manifest element each criterion checks.", _DESIGN))
    await _pinned(store, UnitKind.CYCLE, "cyc_recall")
    cycle, run = _framing_cycle(), _framing_run()
    registry = AsyncMock()
    registry.get_cycle.return_value = cycle
    registry.get_run.return_value = run
    registry.get_latest_checkpoint.return_value = None
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (_PROFILE, "sha")
    executor = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=AsyncMock(),
        queue=reply_router.bind(AsyncMock()),
        squad_profile=profiles,
        task_timeout=5.0,
        reply_router=reply_router,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=SnapshotRecall(store),
        proposal_evidence=NoOpProposalEvidence(),
    )
    received: dict[str, dict] = {}

    def responder(env):
        received[env["task_type"]] = env.get("inputs") or {}
        return TaskResult(task_id=env["task_id"], status="SUCCEEDED", outputs={"summary": "ok"})

    reply_router.responder = responder
    await executor.execute_run(cycle_id=cycle.cycle_id, run_id=run.run_id)

    [exposure] = [
        x for x in await store.list_exposures(run.run_id) if x.query.task_type == _DESIGN_TASK
    ]
    handed = received[_DESIGN_TASK][LESSONS_INPUT]["lessons"]
    assert [lesson["revision_id"] for lesson in handed] == [
        e["revision_id"] for e in exposure.recalled["intervention"]
    ]


async def test_a_binding_that_fits_the_plan_but_not_the_dispatch_holds_at_the_dispatch():
    """#2681, entered at the two seams the executor calls: ``check_the_plan`` on the plan envelope
    and ``supply_the_dispatch`` on it and the copy the executor enriched. Bug caught: the budget
    measured on the plan envelope alone, so a project instruction that fit before the executor
    added the task's upstream outputs was handed to a prompt the guard then refused."""
    from adapters.memory.records import InMemoryMemoryRecords
    from squadops.capabilities.lesson_supply import check_the_plan
    from squadops.capabilities.prompt_budget import prompt_budget
    from squadops.memory.task_instructions import TaskInstructionsUnavailable
    from tests.unit.memory.test_project_instructions import _instruction

    records = InMemoryMemoryRecords()
    store = await _store_with()
    cycle = _framing_cycle()
    [design] = [e for e in _plan(cycle) if str(e.task_type) == _DESIGN_TASK]
    room = prompt_budget(design)
    await records.create(_instruction("mrec_fits", _DESIGN_TASK, text="x" * (room * 4 // 2)))
    await pin_unit(store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
                   pinned_at=_NOW, disabled=False, records=records)  # fmt: skip
    recall = SnapshotRecall(store, records=records)
    enriched = dataclasses.replace(
        design, inputs={**design.inputs, "prior_outputs": {"strat": "y" * (room * 4)}}
    )

    await check_the_plan([design], recall=recall, cycle=cycle, run_id="run_fit", now=_NOW)
    with pytest.raises(TaskInstructionsUnavailable):
        await supply_the_dispatch(
            (design, enriched), recall=recall, cycle=cycle, run_id="run_fit", now=_NOW
        )

    [held] = await store.list_exposures("run_fit")
    assert held.held and held.task_id == design.task_id


async def test_a_correction_repair_is_supplied_its_lessons_when_it_is_composed():
    """Repair (§0.9), entered at ``CorrectionRunner.run_correction_protocol`` with the snapshot
    recall, composing a real dev repair of a failed ``development.develop``. Bugs caught: the
    repair composed without asking, so a correction-round lesson reaches only the next cycle's
    first authoring; or the analyzer and the decision, which author no output, handed lessons."""
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
