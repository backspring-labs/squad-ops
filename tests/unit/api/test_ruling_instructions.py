"""The increment gate's approval carries task instructions for the ruled cycle (SIP-0110 Appendix A
§3.5; #2178), entered at ``POST …/gates/progress_increment_ruling`` with the world the gate's own
tests use, and the records store beside it.

What bugs would these catch? An approval's instructions left in its free notes, which reach no
prompt; a repeated ruling storing them twice, or refused as a conflicting retry; instructions with a
return, which launches nothing; one for a task already dispatched; another gate taking them; an
instruction admitted at the gate marked as an intervention.
"""

from __future__ import annotations

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.campaigns.models import ControlOperation
from squadops.memory.task_instructions import is_intervention
from tests.unit.api.test_increment_gate_route import CID, world  # noqa: F401

pytestmark = pytest.mark.auth

INSTRUCTION = {"text": "Keep capacity optional on create.", "task_types": ["development.develop"]}


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
