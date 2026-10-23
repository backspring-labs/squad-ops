"""Task instructions reach the tasks they name, and only those (SIP-0110 Appendix A §3.5–§3.7; #2178).

Entered where the live cycle supplies them: ``supply_lessons`` at plan composition and
``supply_the_dispatch`` at each dispatch after the first, with the snapshot recall over the typed
records' store.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from adapters.noop.ports import NoOpProposalEvidence
from squadops.capabilities.lesson_supply import (
    reaches,
    supply_lessons,
    supply_the_dispatch,
    unit_of,
)
from squadops.memory.records import (
    RecordRefused,
    Reference,
    Revision,
    Source,
    TaskTarget,
    new_record,
    withdrawn,
)
from squadops.memory.task_instructions import (
    TASK_INSTRUCTIONS_INPUT,
    TaskInstructionsUnavailable,
    admitted,
)
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan, _redispatched

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 19, tzinfo=UTC)
DESIGN = "development.design_plan"


def _instruction(cycle_id: str, *types: str, text: str = "Keep the join idempotent."):
    [record] = admitted(
        [{"text": text, "task_types": list(types)}],
        project_id="group_run",
        cycle_id=cycle_id,
        actor="ada",
        now=T0,
        instructable=lambda t: True,
        source=Source("cycle_request", {"cycle_id": cycle_id}),
    )
    return record


async def _supplied(records, cycle):
    recall = SnapshotRecall(InMemoryCrossCycleMemoryStore(), records=records)
    supplied = await supply_lessons(
        _plan(cycle),
        recall=recall,
        unit=unit_of(cycle),
        stack="fullstack_fastapi_react",
        run_id="run_recall0001",
        now=T0,
    )
    return supplied, recall


def _texts(envelope) -> list[str]:
    handed = envelope.inputs.get(TASK_INSTRUCTIONS_INPUT)
    return [i["text"] for i in handed["instructions"]] if handed else []


async def test_an_instruction_reaches_its_cycles_named_task_and_no_other():
    """T3. Bug caught: an instruction for cycle A's design plan reaching A's other authoring
    tasks, or cycle B's design plan, which shares the project and the task type."""
    records = InMemoryMemoryRecords()
    await records.create(_instruction("cyc_recall", DESIGN))
    cycle_b = _framing_cycle(cycle_id="cyc_other")

    a, _ = await _supplied(records, _framing_cycle())
    b, _ = await _supplied(records, cycle_b)

    reached = {str(e.task_type) for e in a if _texts(e)}
    assert reached == {DESIGN}
    assert [_texts(e) for e in a if str(e.task_type) == DESIGN] == [["Keep the join idempotent."]]
    assert all(TASK_INSTRUCTIONS_INPUT not in e.inputs for e in b)


async def test_the_exposure_names_the_revision_each_dispatch_was_handed():
    """Bug caught: a task handed an instruction whose exposure doesn't say so, so what reached
    the model can't be told from the record."""
    records = InMemoryMemoryRecords()
    record = _instruction("cyc_recall", DESIGN)
    await records.create(record)
    store = InMemoryCrossCycleMemoryStore()
    supplied = await supply_lessons(
        _plan(_framing_cycle()),
        recall=SnapshotRecall(store, records=records),
        unit=unit_of(_framing_cycle()),
        stack="fullstack_fastapi_react",
        run_id="run_recall0001",
        now=T0,
    )

    [design] = [e for e in supplied if str(e.task_type) == DESIGN]
    exposures = {x.task_id: x for x in await store.list_exposures("run_recall0001")}
    assert exposures[design.task_id].task_instructions == {
        "disposition": "supplied",
        "supplied": [{"record_id": record.record_id, "revision": "1"}],
        "unresolved": [],
    }
    others = [x for t, x in exposures.items() if t != design.task_id]
    assert others and all(x.task_instructions is None for x in others)


@pytest.mark.parametrize(
    ("selector", "dispatch", "reached"),
    [
        (("qa.test",), "qa.test_repair", True),
        (("qa.test",), "development.correction_repair", False),
        (("development.develop",), "development.correction_repair", True),
        (("development.design_plan",), "development.correction_repair", False),
        (("builder.assemble",), "builder.assemble_repair", True),
    ],
    ids=["qa-reauthoring", "qa-behavioural-repair", "develop-repair", "plan-no-repair",
         "builder-repair"],
)  # fmt: skip
def test_an_instruction_reaches_the_repair_that_revises_its_tasks_output(
    selector, dispatch, reached
):
    """T12's repair part. Bug caught: an instruction for qa.test reaching the app's repair, which
    revises the code, not the tests; or never reaching qa.test's own re-authoring."""
    assert reaches(selector, dispatch) is reached


async def test_a_withdrawn_instruction_is_gone_from_the_next_dispatch():
    """Each dispatch reads its bindings again (§3.7). Bug caught: a re-dispatch keeping the
    instruction its first attempt was handed after it was withdrawn."""
    records = InMemoryMemoryRecords()
    record = _instruction("cyc_recall", DESIGN)
    await records.create(record)
    supplied, recall = await _supplied(records, _framing_cycle())
    [design] = [e for e in supplied if str(e.task_type) == DESIGN]
    assert _texts(design)

    gone = withdrawn(record, by="ada", at=T0, why="the plan doesn't need it")
    await records.append_status(record.record_id, gone.status_changes[-1])
    held = _redispatched(design)
    await supply_the_dispatch(
        held, recall=recall, cycle=_framing_cycle(), run_id="run_recall0001", now=T0
    )

    assert [TASK_INSTRUCTIONS_INPUT in e.inputs for e in held] == [False, False]


async def test_a_binding_that_cant_fit_or_cant_be_read_holds_the_task_with_why():
    """§3.6: a binding section is never cut and never read as none. Bugs caught: an oversized
    instruction truncated into the prompt, or a store failure dispatching the task without the
    instruction it was given; and (#2178) a store failure held as the operator's input, so a
    Campaign's expiry escalates an outage to the owner instead of retrying it, or the reverse."""
    records = InMemoryMemoryRecords()
    await records.create(_instruction("cyc_recall", DESIGN, text="x" * 2_000_000))
    with pytest.raises(TaskInstructionsUnavailable, match="tokens and the prompt has") as over:
        await _supplied(records, _framing_cycle())

    class Down(InMemoryMemoryRecords):
        async def list_project(self, project_id):
            raise ConnectionError("store down")

    with pytest.raises(TaskInstructionsUnavailable, match="could not be read") as down:
        await _supplied(Down(), _framing_cycle())

    assert [(e.value.task_type, [k for *_, k in e.value.unresolved], e.value.sections)
            for e in (over, down)] == [
        (DESIGN, ["input"], ("task_instructions",)),
        # The project section's pin check reads the same records, so it holds for the store too.
        (DESIGN, ["store", "store"], ("task_instructions", "project_instructions")),
    ]  # fmt: skip


def test_an_instruction_for_a_task_that_authors_nothing_is_refused_at_admission():
    """Bug caught: an instruction stored for a task type no authoring seam supplies, which then
    reaches nothing while its creator believes it binds."""
    with pytest.raises(RecordRefused, match="data.report authors nothing"):
        admitted(
            [{"text": "say so", "task_types": ["data.report"]}],
            project_id="group_run", cycle_id="c", actor="ada", now=T0,
            instructable=lambda t: t != "data.report", source=Source("cycle_request"),
        )  # fmt: skip


@pytest.mark.parametrize("path", ["admitted-unbound", "the-record-model"])
def test_a_task_instructions_current_reference_is_never_stored_unbound(path):
    """T16's task part: a task instruction is bound with its cycle when written. Bugs caught:
    ``@current`` stored, then read at each dispatch, so two attempts of one task see two revisions
    of the decision it names; a write path that forgot to bind storing it anyway, past the record
    model's own check."""
    current = {"ref": "manifest:decision:join@current", "required": True}
    with pytest.raises(RecordRefused, match="@current"):
        if path == "admitted-unbound":
            admitted(
                [{"text": "x", "task_types": [DESIGN], "references": [current]}],
                project_id="group_run", cycle_id="c", actor="ada", now=T0,
                instructable=lambda t: True, source=Source("cycle_request"),
            )  # fmt: skip
        else:
            new_record(
                record_id="mrec_x", kind="instruction", scope="task", project_id="group_run",
                owner_id="ada",
                revision=Revision(
                    number=1, body="x", author="ada", created_at=T0, source=Source("api_call"),
                    confirmed_by="ada", target=TaskTarget("c", (DESIGN,)),
                    references=(Reference(current["ref"], True),),
                ),
            )  # fmt: skip


async def test_no_instruction_leaves_every_task_as_it_was():
    """The byte-identical half. Bug caught: an empty instructions input or section added to
    every task, so prompts change for cycles nobody instructed."""
    plain = _plan(_framing_cycle())
    supplied, _ = await _supplied(InMemoryMemoryRecords(), _framing_cycle())

    assert [dataclasses.asdict(e)["inputs"] for e in supplied] == [
        dataclasses.asdict(e)["inputs"] for e in plain
    ]


async def test_the_run_dispatches_the_instruction_with_its_task_and_its_redispatch(reply_router):
    """Wiring, entered at ``execute_run`` with the snapshot recall over the records' store: a
    framing run whose design-plan writer fails once and is dispatched again. Bug caught: the
    instruction composed into the plan but off the dispatched envelope, or lost on the re-dispatch,
    or reaching the run's other authoring tasks."""
    from unittest.mock import AsyncMock, patch

    from squadops.capabilities.handlers.fault_injection import PRIOR_ATTEMPTS_KEY
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.memory.recall import UnitKind
    from squadops.tasks.models import TaskResult
    from tests.unit.cycles.test_failure_recall import _PROFILE, _framing_run, _pinned

    store = InMemoryCrossCycleMemoryStore()
    await _pinned(store, UnitKind.CYCLE, "cyc_recall", disabled=True)
    records = InMemoryMemoryRecords()
    record = _instruction("cyc_recall", DESIGN)
    await records.create(record)
    cycle, run = _framing_cycle(), _framing_run()
    registry = AsyncMock()
    registry.get_cycle.return_value = cycle
    registry.get_run.return_value = run
    registry.get_latest_checkpoint.return_value = None
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (_PROFILE, "sha")
    executor = DispatchedFlowExecutor(
        cycle_registry=registry, artifact_vault=AsyncMock(), queue=reply_router.bind(AsyncMock()),
        squad_profile=profiles, task_timeout=5.0, reply_router=reply_router, project_registry=None,
        campaign_registry=None, campaign_progress=None, box_verdict=None,
        failure_recall=SnapshotRecall(store, records=records),
        proposal_evidence=NoOpProposalEvidence(),
    )  # fmt: skip
    handed: list[tuple[str, int, list[str]]] = []

    def responder(env):
        inputs = env.get("inputs") or {}
        attempt = int(inputs.get(PRIOR_ATTEMPTS_KEY) or 0) + 1
        given = inputs.get(TASK_INSTRUCTIONS_INPUT) or {}
        handed.append(
            (env["task_type"], attempt, [i["text"] for i in given.get("instructions", [])])
        )
        if env["task_type"] == DESIGN and attempt == 1:
            return TaskResult(task_id=env["task_id"], status="FAILED", error="transient")
        return TaskResult(task_id=env["task_id"], status="SUCCEEDED", outputs={"summary": "ok"})

    reply_router.responder = responder
    with patch("squadops.execution.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock):
        await executor.execute_run(cycle_id=cycle.cycle_id, run_id=run.run_id)

    text = ["Keep the join idempotent."]
    assert [(a, t) for task, a, t in handed if task == DESIGN] == [(1, text), (2, text)]
    assert all(not t for task, _, t in handed if task != DESIGN)
    design = [x for x in await store.list_exposures(run.run_id) if x.task_id.endswith(DESIGN)]
    assert sorted(x.attempt for x in design) == [1, 2]
    assert all(x.task_instructions["supplied"][0]["record_id"] == record.record_id for x in design)


async def test_every_slotted_template_renders_unchanged_with_no_instructions():
    """The byte-identical half at the prompt. Bug caught: the instructions' slot adding a line or
    a heading to a prompt no instruction applies to."""
    import re
    from pathlib import Path

    from tests.unit.memory.test_lesson_slots import _render

    templates = Path(__file__).resolve().parents[3] / "src/squadops/prompts/request_templates"
    slotted = [
        t for t in templates.glob("*.md") if "{{task_instructions_section}}" in t.read_text()
    ]
    assert len(slotted) >= 10
    for path in slotted:
        text = path.read_text().split("---", 2)[2]
        names = set(re.findall(r"{{(\w+)}}", text))
        fill = {n: f"<{n}>" for n in names if n != "task_instructions_section"}
        before = text.replace("{{task_instructions_section}}", "")
        assert await _render(text, fill) == await _render(before, fill), path.name


async def test_an_author_shows_the_instructions_it_is_handed_before_the_lessons():
    """Wiring, entered at the technical design's real ``handle()`` with the shipped assets. Bug
    caught: the instruction on the envelope and absent from the prompt, or shown after the
    lessons, which the slot's precedence puts after it."""
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler
    from squadops.memory.recall import LESSONS_INPUT
    from tests.unit.campaigns.test_prior_cycle import _rendered
    from tests.unit.memory.test_lesson_slots import _HEADING, _LESSONS

    handed = {"instructions": [{"record_id": "mrec_1", "revision": 1, "text": "Keep the join idempotent.", "references": []}]}  # fmt: skip
    base = {"prd": "the PRD", "resolved_config": {}}

    shown = await _rendered(
        DevelopmentDesignPlanHandler(),
        {**base, TASK_INSTRUCTIONS_INPUT: handed, LESSONS_INPUT: _LESSONS},
    )
    plain = await _rendered(DevelopmentDesignPlanHandler(), base)

    assert "## INSTRUCTIONS FOR THIS TASK" in shown and "1. Keep the join idempotent." in shown
    assert shown.index("## INSTRUCTIONS FOR THIS TASK") < shown.index(_HEADING)
    assert "INSTRUCTIONS FOR THIS TASK" not in plain
