"""The ``memory_context: none`` arm (SIP-0110 Appendix A §3.7, T9's rest; #2179 stage 2): a unit that
declares it pins no lesson and no project instruction, keeps its own task instructions, and records its
exposures apart, so it never reads a lesson's effect."""

from __future__ import annotations

import pytest

from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.capabilities.lesson_supply import supply_for_cycle
from squadops.cycles.preflight import memory_declaration_decision
from squadops.memory.declarations import memory_context_none
from squadops.memory.lessons import RecallDisposition, Snapshot, recall
from squadops.memory.pinning import pin_standalone_cycle
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.recall import LESSONS_INPUT, RecallQuery, UnitKind
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT
from tests.unit.cycles.test_failure_recall import _DESIGN, _NOW, _framing_cycle, _plan, _store_with
from tests.unit.memory.test_project_instructions import _instruction as _project_instruction
from tests.unit.memory.test_task_instructions import _instruction as _task_instruction

pytestmark = [pytest.mark.domain_memory]

_DESIGN_PLAN = "development.design_plan"


@pytest.mark.parametrize(
    ("config", "withheld"),
    [
        ({}, False),
        ({"memory": "disabled"}, False),
        ({"memory_context": "none"}, True),
        ({"memory_context": " None "}, True),
        ({"memory_context": "none", "memory": "disabled"}, True),
    ],
)
def test_the_declaration_is_read_from_the_cycles_config_and_passes_create(config, withheld):
    """Bug caught: a declared ``memory_context: none`` read as absent because of its case or
    spacing, so the cycle runs with its project's instructions and lessons; or a consistent pair
    refused at create."""
    assert memory_context_none(config) is withheld
    assert memory_declaration_decision(config, campaign_cycle=False).blocking == ()


@pytest.mark.parametrize(
    "config",
    [
        {"memory_context": "off"},
        {"memory_context": "lessons"},
        {"memory_context": "none", "memory": "enabled"},
    ],
)
def test_a_declaration_that_could_be_read_either_way_is_refused_at_create(config):
    """Bug caught: a typo, or ``memory: enabled`` beside ``none``, created and run as one experiment
    while its record says the other."""
    decision = memory_declaration_decision(config, campaign_cycle=False)

    assert [f.code for f in decision.blocking] == ["memory_declaration_unknown"]
    with pytest.raises(ValueError):
        memory_context_none(config)


async def test_t9_each_arm_hands_the_design_plan_what_it_declares_and_records_which_it_ran():
    """T9's pair and its third arm, entering where a cycle is admitted (``pin_standalone_cycle``) and
    where a run's plan is supplied (``supply_for_cycle``, run provisioning's call). With a lesson approved, a project instruction in
    force and a task instruction for each cycle: lessons on hands all three; ``memory: disabled``
    the two instructions; ``memory_context: none`` the task instruction alone. Bug caught: a none
    unit handed its project's instructions or lessons, a lessons-disabled unit losing its project
    instruction, or a none unit's exposure recorded as ``memory_disabled``, joining the lesson
    comparison's control."""
    store = await _store_with(("Name each route's handler.", _DESIGN))
    records = InMemoryMemoryRecords()
    await records.create(_project_instruction("mrec_project", _DESIGN_PLAN))
    handed, recorded = {}, {}
    for arm, overrides in (
        ("on", {}),
        ("lessons_disabled", {"memory": "disabled"}),
        ("none", {"memory_context": "none"}),
    ):
        cycle = _framing_cycle(cycle_id=f"cyc_{arm}", execution_overrides=overrides)
        await records.create(_task_instruction(cycle.cycle_id, _DESIGN_PLAN))
        await pin_standalone_cycle(store, cycle, now=_NOW.replace(hour=1), records=records)
        plan = await supply_for_cycle(
            _plan(cycle),
            recall=SnapshotRecall(store, records=records),
            cycle=cycle,
            run_id=f"run_{arm}",
            now=_NOW.replace(hour=2),
        )
        design = next(e for e in plan if str(e.task_type) == _DESIGN_PLAN)
        handed[arm] = tuple(
            key in design.inputs
            for key in (TASK_INSTRUCTIONS_INPUT, PROJECT_INSTRUCTIONS_INPUT, LESSONS_INPUT)
        )
        [exposure] = [
            x for x in await store.list_exposures(f"run_{arm}") if x.task_id == design.task_id
        ]
        recorded[arm] = (exposure.disposition, exposure.project_instructions["disposition"])

    assert handed == {
        "on": (True, True, True),
        "lessons_disabled": (True, True, False),
        "none": (True, False, False),
    }
    assert recorded == {
        "on": ("supplied", "supplied"),
        "lessons_disabled": ("memory_disabled", "supplied"),
        "none": ("memory_context_none", "memory_context_none"),
    }


async def test_a_withheld_pin_is_stored_as_declared_and_every_other_pin_as_it_was():
    """Bug caught: the declaration lost when the snapshot is stored (Postgres keeps ``to_dict``),
    so after a restart a none unit's tasks read as memory disabled and join the lesson series; or
    every other snapshot's stored form changing."""
    store = await _store_with(("Name each route's handler.", _DESIGN))
    records = InMemoryMemoryRecords()
    await records.create(_project_instruction("mrec_project", _DESIGN_PLAN))
    pinned = {}
    for overrides in ({"memory_context": "none"}, {"memory": "disabled"}):
        cycle = _framing_cycle(cycle_id=f"cyc_{len(pinned)}", execution_overrides=overrides)
        pinned[cycle.cycle_id] = await pin_standalone_cycle(
            store, cycle, now=_NOW.replace(hour=1), records=records
        )
    withheld, disabled = pinned["cyc_0"], pinned["cyc_1"]
    stored = Snapshot.from_dict(withheld.to_dict())
    query = RecallQuery("group_run", _DESIGN_PLAN, unit_kind=UnitKind.CYCLE, unit_id="cyc_0")

    assert (stored, stored.entries, stored.instructions) == (withheld, (), ())
    assert recall(stored, query).disposition is RecallDisposition.CONTEXT_NONE
    assert "memory_context" not in disabled.to_dict() and len(disabled.instructions) == 1


@pytest.mark.parametrize("overrides", [{"memory_context": "none"}, {"memory": "disabled"}])
async def test_a_pin_that_withholds_the_lessons_never_reads_them(overrides):
    """The second read of PR #2528. Bug caught: a lesson store that can't be read costing a unit
    that never receives a lesson its whole snapshot, so its tasks hold, or recall as failed, for a
    read it didn't need."""
    store = await _store_with(("Name each route's handler.", _DESIGN))

    async def unreadable(project_id):
        raise ConnectionError("the lesson store is down")

    store.list_revisions = store.list_approvals = unreadable
    cycle = _framing_cycle(cycle_id="cyc_withholds", execution_overrides=overrides)

    snapshot = await pin_standalone_cycle(store, cycle, now=_NOW.replace(hour=1))

    assert (snapshot.disabled, snapshot.entries) == (True, ())
    assert await store.get_snapshot(UnitKind.CYCLE, "cyc_withholds") == snapshot


@pytest.mark.parametrize(
    ("overrides", "refused"),
    [
        ({"memory_context": "none"}, True),
        ({"memory": "disabled"}, True),
        ({"memory": "enabled"}, False),
        ({}, False),
    ],
)
async def test_a_campaigns_cycle_that_withholds_memory_is_refused_at_its_launch(
    monkeypatch, overrides, refused
):
    """Entered at ``prepare_cycle`` with the campaign named, as a campaign's launch calls it. Bug
    caught: a campaign's cycle admitted with a declaration it never runs under: it selects from
    its campaign's snapshot, so its tasks get the full context and its record says otherwise."""
    from adapters.cycles.factory import create_project_registry, create_squad_profile_port
    from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
    from squadops.api.cycle_schemas import CycleCreateRequest
    from squadops.api.routes.cycles.cycles import CreationPorts, prepare_cycle
    from squadops.cycles.models import PreflightRejectedError

    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")

    class Deploys:
        async def latest(self):
            return None

    ports = CreationPorts(
        project_registry=create_project_registry("config"),
        squad_profile=create_squad_profile_port("config"),
        cycle_registry=MemoryCycleRegistry(),
        deploy_registry=Deploys(),
    )
    body = CycleCreateRequest(squad_profile_id="full", execution_overrides=overrides)

    standalone = await prepare_cycle(ports, "group_run", body.model_copy(deep=True))
    if refused:
        with pytest.raises(PreflightRejectedError, match="recorded and never applied"):
            await prepare_cycle(ports, "group_run", body, campaign_id="cmp_x", kind="calibration")
    else:
        await prepare_cycle(ports, "group_run", body, campaign_id="cmp_x", kind="calibration")
    assert standalone.cycle.campaign_id is None
