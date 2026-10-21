"""The increment gate's approval carries task instructions for the ruled cycle (SIP-0110 Appendix A
§3.5; #2178), entered at ``POST …/gates/progress_increment_ruling`` with the world the gate's own
tests use, and the records store beside it.

What bugs would these catch? An approval's instructions left in its free notes, which reach no
prompt; a repeated ruling storing them twice, or refused as a conflicting retry; instructions with a
return, which launches nothing; one for a task already dispatched; another gate taking them; an
instruction admitted at the gate marked as an intervention.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.cycle_schemas import TaskInstructionDTO
from squadops.api.routes.cycles.runs import _ruling_record_id
from squadops.api.routes.memory.interventions import turn_of
from squadops.campaigns.gate import INCREMENT_RULING_GATE
from squadops.campaigns.models import ControlOperation
from squadops.memory.exposures import Exposure
from squadops.memory.recall import RecallQuery
from squadops.memory.task_instructions import is_intervention
from tests.unit.api.test_dispatch_turns import _dispatching, _still_waiting
from tests.unit.api.test_increment_gate_route import BINDING, CID, world  # noqa: F401

pytestmark = pytest.mark.auth

INSTRUCTION = {"text": "Keep capacity optional on create.", "task_types": ["development.develop"]}


async def _rule_rows(w):
    return [e for e in await w.campaigns.control_log(CID) if e.operation is ControlOperation.RULE]


async def _dispatch(w, task_type: str = "development.develop"):
    await w.client.app.state.memory_store.record_exposure(
        Exposure(
            run_id="run_impl", task_id="t_dev", cycle_id="cyc_inc", agent_id="neo",
            seam="build_authoring", query=RecallQuery(project_id="group_run", task_type=task_type),
            recalled={}, recorded_at=datetime.now(UTC),
        )
    )  # fmt: skip


def _with_records(w):
    records = InMemoryMemoryRecords()
    w.client.app.state.memory_records = records
    w.client.app.state.memory_store = InMemoryCrossCycleMemoryStore()
    return records


async def test_an_approvals_instructions_are_the_ruled_cycles_admitted_inputs(world):  # noqa: F811
    records = _with_records(world)

    first = world.rule(task_instructions=[INSTRUCTION])
    again = world.rule(task_instructions=[INSTRUCTION])

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    [record] = await records.list_project("group_run")
    assert (record.current.target.cycle_id, record.current.body) == ("cyc_inc", INSTRUCTION["text"])
    assert (record.current.source.kind, record.current.source.ids["gate"]) == (
        "gate_decision", "progress_increment_ruling",
    )  # fmt: skip
    assert not is_intervention(record)
    [row] = [
        e for e in await world.campaigns.control_log(CID) if e.operation is ControlOperation.RULE
    ]
    assert row.binding["task_instructions"] == [record.record_id]
    # Its id is the ruled cycle's, so another campaign's ruling under the same key gets its own.
    assert record.record_id == _ruling_record_id(
        "cyc_inc", "rule-1", 0, TaskInstructionDTO(**INSTRUCTION)
    )


async def test_a_ruling_repeated_with_other_instructions_conflicts_and_keeps_the_first(world):  # noqa: F811
    """§12a. Bug caught: the record ids drawn from the retry key alone, so a repeat with other
    instructions replays the first ruling and its caller is told they were taken."""
    records = _with_records(world)
    world.rule(task_instructions=[INSTRUCTION])

    changed = world.rule(task_instructions=[{**INSTRUCTION, "text": "Make capacity required."}])

    assert changed.status_code == 409, changed.text
    assert [r.current.body for r in await records.list_project("group_run")] == [
        INSTRUCTION["text"]
    ]


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"decision": "returned_for_revision", "classification": "scope_too_large"}, "an approval"),
        ({"task_instructions": [{"text": "x", "task_types": ["no.such_task"]}]}, "authors nothing"),
    ],
    ids=["with-a-return", "for-a-task-that-authors-nothing"],
)
async def test_a_ruling_the_rules_refuse_stores_no_instruction(world, change, says):  # noqa: F811
    records = _with_records(world)

    response = world.rule(**{"task_instructions": [INSTRUCTION], **change})

    assert response.status_code == 422, response.text
    assert says in response.json()["detail"]["error"]["message"]
    assert await records.list_project("group_run") == []
    assert await _rule_rows(world) == []  # refused before the row, not after it


async def test_another_gate_takes_no_instructions(world):  # noqa: F811
    from squadops.auth.models import Role
    from tests.unit.api.test_increment_gate_route import _identity

    _with_records(world)
    world.identity = _identity(Role.ADMIN)  # one who may decide the plan review

    response = world.rule(
        gate="progress_plan_review", binding=None, idempotency_key=None,
        task_instructions=[INSTRUCTION],
    )  # fmt: skip

    assert response.status_code == 422
    assert "task_instructions belong to the" in response.json()["detail"]["error"]["message"]


@pytest.mark.parametrize(
    ("world_has", "status", "code"),
    [("a-dispatched-task", 409, "TASK_DISPATCHED"), ("no-records-store", 422, "VALIDATION_ERROR")],
)
async def test_an_approval_whose_instructions_cant_be_taken_rules_nothing(
    world,  # noqa: F811
    world_has,
    status,
    code,
):
    """§3.5, the second read of PR #2556. Bugs caught: an instruction for a task already dispatched
    admitted as if the task hadn't run; an approval taken with nowhere to keep its instructions;
    either refused only after the ``rule`` row was written, so the ruling stands without them."""
    records = _with_records(world)
    if world_has == "a-dispatched-task":
        await _dispatch(world)
    else:
        world.client.app.state.memory_records = None

    response = world.rule(task_instructions=[INSTRUCTION])

    assert response.status_code == status, response.text
    assert response.json()["detail"]["error"]["code"] == code
    assert await records.list_project("group_run") == []
    assert await _rule_rows(world) == []


async def test_a_ruling_repeated_after_its_framing_dispatched_replays(world):  # noqa: F811
    """§12a, the second read of PR #2556. Bug caught: the repeat of an applied ruling refused as
    dispatched, though the ruling's own instructions are what reached that task."""
    records = _with_records(world)
    world.rule(task_instructions=[INSTRUCTION])
    await _dispatch(world)

    again = world.rule(task_instructions=[INSTRUCTION])

    assert again.status_code == 200, again.text
    assert len(await records.list_project("group_run")) == 1
    assert len(await _rule_rows(world)) == 1


def test_two_cycles_ruled_with_one_key_and_instruction_get_their_own_records():
    """The second read of PR #2556. Bug caught: the record id drawn from the retry key and the
    text alone, which is unique within a campaign only; the second campaign's ruling then finds
    the first's record, keeps it, and its own cycle's instruction is never stored."""
    given = TaskInstructionDTO(**INSTRUCTION)

    assert _ruling_record_id("cyc_a", "approve-1", 0, given) != _ruling_record_id(
        "cyc_b", "approve-1", 0, given
    )


async def test_an_approvals_current_reference_is_bound_with_the_ruled_cycle(world):  # noqa: F811
    """T16's task part. Bug caught: the gate's instruction stored ``@current`` as written, or bound
    for some unit other than the cycle whose framing and build it directs."""
    from tests.unit.memory.test_reference_binding import _Resolver

    records = _with_records(world)
    resolver = _Resolver()
    world.client.app.state.reference_resolvers = {"fake": resolver}
    given = {**INSTRUCTION, "references": [{"ref": "fake:doc:spec@current", "required": True}]}

    response = world.rule(task_instructions=[given])

    assert response.status_code == 200, response.text
    [record] = await records.list_project("group_run")
    assert [(r.ref, r.digest) for r in record.current.references] == [
        ("fake:doc:spec@r1", "sha256:r1")
    ]
    assert [(c.unit_kind, c.unit_id) for c in resolver.seen] == [("cycle", "cyc_inc")]


@pytest.mark.parametrize("resolver_now", ["refusing", "down"])
async def test_a_repeated_ruling_replays_whatever_its_resolver_says_now(world, resolver_now):  # noqa: F811
    """§12a, T16, the second read of the task part. Bug caught: a repeat of an applied ruling
    binding its instructions again before seeing they are stored, so a resolver that now refuses,
    or is down, answers the repeat 422 or 500: a ruling whose first attempt stopped after its row
    could then never record its gate decision."""
    from tests.unit.memory.test_reference_binding import _Crashing, _Resolver

    records = _with_records(world)
    resolver = _Resolver()
    world.client.app.state.reference_resolvers = {"fake": resolver}
    given = {**INSTRUCTION, "references": [{"ref": "fake:doc:spec@current", "required": True}]}
    world.rule(task_instructions=[given])
    if resolver_now == "refusing":
        resolver.refuse = "the document was deleted"
    else:
        world.client.app.state.reference_resolvers = {"fake": _Crashing()}

    again = world.rule(task_instructions=[given])

    assert again.status_code == 200, again.text
    [record] = await records.list_project("group_run")
    assert record.current.references[0].ref == "fake:doc:spec@r1"


async def test_an_approvals_instructions_wait_for_a_dispatch_being_composed(world):  # noqa: F811
    """#2545. Bug caught: the ruling's dispatched check run while the cycle's dispatch is between
    reading its instructions and disclosing them, so the approval stores an instruction for a task
    that dispatched without it, as an admitted input."""
    records = _with_records(world)
    store = world.client.app.state.memory_store
    entered, release = asyncio.Event(), asyncio.Event()
    exposure = Exposure(
        run_id="run_impl", task_id="t_dev", cycle_id="cyc_inc", agent_id="neo",
        seam="build_authoring",
        query=RecallQuery(project_id="group_run", task_type="development.develop"),
        recalled={}, recorded_at=datetime.now(UTC),
    )  # fmt: skip
    unit = turn_of(await world.cycles.get_cycle("cyc_inc"))
    dispatching = asyncio.create_task(_dispatching(store, unit, exposure, entered, release))
    await entered.wait()
    body = {"decision": "approved", "notes": "the footprint stays inside the create view",
            "binding": BINDING, "idempotency_key": "rule-1", "task_instructions": [INSTRUCTION]}  # fmt: skip
    transport = httpx.ASGITransport(app=world.client.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        ruling = asyncio.create_task(
            client.post(
                f"/api/v1/projects/group_run/cycles/cyc_inc/runs/run_prop/gates/{INCREMENT_RULING_GATE}",
                json=body,
            )
        )
        waited = await _still_waiting(ruling)
        release.set()
        await dispatching
        response = await ruling

    assert waited
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "TASK_DISPATCHED"
    assert await records.list_project("group_run") == []
    assert await _rule_rows(world) == []
