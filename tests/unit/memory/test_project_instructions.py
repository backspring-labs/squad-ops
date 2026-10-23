"""Project instructions, pinned in a unit's snapshot at admission and binding on its tasks (SIP-0110
Appendix A §3.6–§3.7; #2179 stage 1). Entered where the live cycle pins (``pin_unit``) and supplies
(``supply_lessons``), with the snapshot recall over both stores."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.lessons import Snapshot, UnitKind
from squadops.memory.pinning import pin_unit
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.records import (
    InstructionApplicability,
    Revision,
    Source,
    new_record,
    withdrawn,
)
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT, TaskInstructionsUnavailable
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 19, tzinfo=UTC)
DESIGN = "development.design_plan"


def _instruction(record_id: str, *types: str, text: str = "Name each run by its route.", **change):
    return new_record(
        record_id=record_id, kind="instruction", scope="project", project_id="group_run",
        owner_id="ada",
        revision=Revision(
            number=1, body=text, author="ada", created_at=T0, source=Source("api_call"),
            confirmed_by="ada", applicability=InstructionApplicability(types, ("*",), ("*",)),
            **change,
        ),
    )  # fmt: skip


async def _admit(store, records, unit_id="cyc_recall", *, at=T0, disabled=False) -> Snapshot:
    return await pin_unit(
        store, unit_kind=UnitKind.CYCLE, unit_id=unit_id, project_id="group_run", pinned_at=at,
        disabled=disabled, records=records,
    )  # fmt: skip


async def _supplied(store, records, cycle=None):
    cycle = cycle or _framing_cycle()
    return await supply_lessons(
        _plan(cycle),
        recall=SnapshotRecall(store, records=records),
        unit=unit_of(cycle),
        stack="fullstack_fastapi_react",
        run_id="run_recall0001",
        now=T0,
    )


def _texts(envelope, key=PROJECT_INSTRUCTIONS_INPUT) -> list[str]:
    handed = envelope.inputs.get(key)
    return [i["text"] for i in handed["instructions"]] if handed else []


async def test_a_pinned_instruction_reaches_the_tasks_its_applicability_names():
    """T1. Bug caught: a project instruction for the design plan reaching the cycle's other
    authoring tasks, or reaching none; or an exposure that doesn't name the revision handed."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    record = _instruction("mrec_design", DESIGN)
    await records.create(record)
    await _admit(store, records)

    supplied = await _supplied(store, records)

    assert {str(e.task_type) for e in supplied if _texts(e)} == {DESIGN}
    [design] = [e for e in supplied if str(e.task_type) == DESIGN]
    exposures = {x.task_id: x for x in await store.list_exposures("run_recall0001")}
    assert exposures[design.task_id].project_instructions["supplied"] == [
        {"record_id": "mrec_design", "revision": "1"}
    ]


async def test_a_running_unit_keeps_its_pin_and_a_later_unit_gets_the_new_instruction():
    """T6. Bug caught: an instruction confirmed while a unit runs changing that unit's later
    prompts, or never reaching the units admitted after it."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _admit(store, records)
    await records.create(_instruction("mrec_late", DESIGN))
    later = _framing_cycle(cycle_id="cyc_later")
    await _admit(store, records, "cyc_later", at=T0 + timedelta(hours=1))

    running = await _supplied(store, records)
    admitted_after = await _supplied(store, records, later)

    assert all(not _texts(e) for e in running)
    assert [_texts(e) for e in admitted_after if str(e.task_type) == DESIGN] == [
        ["Name each run by its route."]
    ]


async def test_memory_disabled_pins_no_lesson_and_still_pins_the_instructions():
    """§3.7: today's memory-disabled is the lessons-disabled arm. Bug caught: a counted roll's
    requirements changing with its memory declaration, so its arms differ in more than lessons."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await records.create(_instruction("mrec_req", DESIGN))

    snapshot = await _admit(store, records, disabled=True)

    assert (snapshot.disabled, snapshot.entries) == (True, ())
    assert [i.record_id for i in snapshot.instructions] == ["mrec_req"]


async def test_a_withdrawn_or_unconfirmed_instruction_is_not_pinned():
    """Bug caught: a withdrawn instruction pinned into units admitted after its withdrawal, or a
    draft that no one confirmed binding the work."""
    records = InMemoryMemoryRecords()
    kept = _instruction("mrec_kept", DESIGN)
    gone = _instruction("mrec_gone", DESIGN)
    await records.create(kept)
    await records.create(gone)
    change = withdrawn(gone, by="ada", at=T0, why="replaced").status_changes[-1]
    await records.append_status("mrec_gone", change)

    snapshot = await _admit(InMemoryCrossCycleMemoryStore(), records)

    assert [i.record_id for i in snapshot.instructions] == ["mrec_kept"]


class _Down(InMemoryCrossCycleMemoryStore):
    async def get_snapshot(self, unit_kind, unit_id):
        raise ConnectionError("store down")


class _RecordsDown(InMemoryMemoryRecords):
    async def list_project(self, project_id):
        raise ConnectionError("records down")


async def test_an_unreadable_snapshot_or_an_oversized_binding_holds_the_task():
    """§3.6, T8's project part. Bug caught: a store failure dispatching a task without the
    instruction its unit pinned, or the two binding sections cut to fit the prompt."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await records.create(_instruction("mrec_big", DESIGN, text="x" * 2_000_000))
    await _admit(store, records)
    with pytest.raises(TaskInstructionsUnavailable, match="project instructions take"):
        await _supplied(store, records)

    with pytest.raises(TaskInstructionsUnavailable, match="snapshot could not be read"):
        await _supplied(_Down(), records)


async def test_a_pin_that_could_not_read_the_records_keeps_its_lessons_and_holds_the_task():
    """The second read of PR #2515. Bug caught: records that fail at admission costing the unit
    its lesson pin, or leaving a snapshot whose tasks read "no instruction" and dispatch without
    the one in force, with nothing on the exposure."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await records.create(_instruction("mrec_any", "*"))

    snapshot = await _admit(store, _RecordsDown())

    assert (snapshot.instructions, snapshot.disabled) == ((), False)
    assert "could not be read at admission" in snapshot.instructions_unread
    assert Snapshot.from_dict(snapshot.to_dict()) == snapshot
    with pytest.raises(TaskInstructionsUnavailable, match="can't be known"):
        await _supplied(store, records)


@pytest.mark.parametrize("admitted", ["unreadable", "never pinned", "pin missed the records"])
async def test_an_unknown_pin_in_a_project_with_no_instruction_runs_as_before(admitted):
    """Records are append-only, so a project holding no project instruction pinned none. Bug
    caught: every task of a project that never wrote an instruction failing its run because its
    snapshot store blinked, where 2.3 failed only the lessons and ran the task."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    if admitted == "unreadable":
        store = _Down()
    elif admitted == "pin missed the records":
        await _admit(store, _RecordsDown())

    supplied = await _supplied(store, records)

    assert all(PROJECT_INSTRUCTIONS_INPUT not in e.inputs for e in supplied)


async def test_the_records_unreadable_at_supply_hold_a_task_whose_pin_is_unknown():
    """Bug caught: an unknown pin read as empty because the records that would say otherwise
    couldn't be read either."""
    with pytest.raises(TaskInstructionsUnavailable, match="checked against the project's records"):
        await _supplied(_Down(), _RecordsDown())


async def test_a_snapshot_with_no_instruction_is_stored_as_it_was_and_one_with_reads_back():
    """Bug caught: every stored snapshot gaining a key, so a pin from before #2179 no longer
    reads as it was; or a pinned instruction losing its applicability through the store."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    plain = await _admit(store, records)
    assert "instructions" not in plain.to_dict()

    await records.create(_instruction("mrec_rt", DESIGN, "qa.test"))
    pinned = await _admit(InMemoryCrossCycleMemoryStore(), records, "cyc_rt")
    assert Snapshot.from_dict(pinned.to_dict()) == pinned


async def test_the_author_shows_the_task_then_the_project_instructions_then_the_lessons():
    """The slot's precedence, at the technical design's real ``handle()`` with the shipped
    assets. Bug caught: the project's standing instruction shown before the task's own, or the
    section absent from the prompt."""
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler
    from squadops.memory.recall import LESSONS_INPUT
    from tests.unit.campaigns.test_prior_cycle import _rendered
    from tests.unit.memory.test_lesson_slots import _HEADING, _LESSONS

    def given(text):
        return {"instructions": [{"record_id": "m", "revision": 1, "text": text, "references": []}]}

    shown = await _rendered(
        DevelopmentDesignPlanHandler(),
        {
            "prd": "the PRD",
            "resolved_config": {},
            TASK_INSTRUCTIONS_INPUT: given("This cycle: keep the join idempotent."),
            PROJECT_INSTRUCTIONS_INPUT: given("This project: name each run by its route."),
            LESSONS_INPUT: _LESSONS,
        },
    )

    order = [
        shown.index("## INSTRUCTIONS FOR THIS TASK"),
        shown.index("## THIS PROJECT'S STANDING INSTRUCTIONS"),
        shown.index(_HEADING),
    ]
    assert order == sorted(order)
    assert "1. This project: name each run by its route." in shown


async def test_an_at_current_reference_is_never_pinned_verbatim():
    """The second read of PR #2515, as T16 builds it (#2179). Bug caught: ``@current`` pinned
    verbatim into a snapshot, where nothing can bind it after the fact (§3.7: resolved once, when
    bound). A family no resolver binds is refused at write (``unbindable``); one the pin can't bind
    is kept on the pin as unbound, which holds a task it applies to (§3.6)."""
    from squadops.memory.records import Reference, unbindable

    record = _instruction(
        "mrec_cur", DESIGN, references=(Reference("manifest:decision:join@current", True),)
    )
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await records.create(record)

    pinned = await _admit(store, records)

    assert unbindable(record.current, families=()) == ["manifest:decision:join@current"]
    assert unbindable(record.current, families=("manifest",)) == []
    [p] = pinned.instructions
    assert p.held_by == [
        ("manifest:decision:join@current", "no resolver binds the manifest family")
    ]


@pytest.mark.parametrize(
    "budget, reason",
    [
        (-1, "the model's prompt budget is unknown"),
        (0, "the project instructions take 2 tokens and the prompt has 0"),
    ],
)
def test_a_hold_says_whether_the_budget_was_unknown_or_spent(budget, reason):
    """Bug caught: task instructions that spend a known budget reported as a model whose window
    is unknown, sending whoever reads the hold to the model registry."""
    from squadops.memory.context import RecordRef, SectionKind
    from squadops.memory.task_instructions import binding_section

    section = binding_section(
        SectionKind.PROJECT_INSTRUCTIONS, [(RecordRef("m", "1"), "x" * 8)], budget=budget
    )

    assert [why for _, why in section.unresolved] == [reason]


def test_a_redispatch_is_not_charged_for_what_its_attempt_was_handed():
    """The second read of PR #2515. Bug caught: the attempt before's instructions counted as the
    task's own input and again as its section, so a binding that fit attempt 1 holds attempt 2;
    and an unknown model reading as a spent window."""
    from squadops.capabilities.prompt_budget import prompt_budget
    from squadops.memory.recall import LESSONS_INPUT

    first = _plan(_framing_cycle())[0]
    budget = prompt_budget(first)
    for key in (TASK_INSTRUCTIONS_INPUT, PROJECT_INSTRUCTIONS_INPUT, LESSONS_INPUT):
        first.inputs[key] = {"instructions": [{"text": "x" * 40_000}]}

    assert budget > 0
    assert prompt_budget(first) == budget
    first.inputs["agent_model"] = "no-such-model"
    assert prompt_budget(first) == -1
