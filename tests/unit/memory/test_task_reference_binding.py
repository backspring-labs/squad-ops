"""A task instruction's ``@current`` reference, bound with its cycle when it is written (SIP-0110
Appendix A §3.6, §3.7; #2178, T16's task part). Written through the records route (an intervention)
over the in-memory stores, and each dispatch composed by the live composer (``supply_lessons``
through ``SnapshotRecall``), with a resolver standing in for a family's.

What bugs would these catch? ``@current`` resolved at dispatch, so a target revised between a task's
attempts reaches the second; the bound revision or its digest not handed, or not in the exposure; a
revision before dispatch keeping the old binding instead of binding again; a resolver's failure
answered as the writer's mistake; the digest or what was written dropped when a revision is stored
as a document.
"""

from __future__ import annotations

import pytest

from adapters.memory.recall import SnapshotRecall
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.records import Reference, revision_document, revision_from_document
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT
from tests.unit.api.test_rebinding import DESIGN, NOW, RECORDS, _World
from tests.unit.cycles.test_failure_recall import _plan
from tests.unit.memory.test_reference_binding import _Crashing, _Resolver

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]

REF = "fake:doc:spec@current"


def _world() -> tuple[_World, _Resolver]:
    world, resolver = _World(), _Resolver()
    world.client.app.state.reference_resolvers = {"fake": resolver}
    return world, resolver


def _instruct(world: _World, cycle_id: str, *, required: bool = True):
    return world.client.post(
        RECORDS,
        json={"kind": "instruction", "scope": "task", "project_id": "group_run",
              "body": "Follow the spec.", "target": {"cycle_id": cycle_id, "task_types": [DESIGN]},
              "references": [{"ref": REF, "required": required}]},
    )  # fmt: skip


async def _dispatch(world: _World, cycle, run_id: str):
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(
            world.store, records=world.records,
            resolvers=world.client.app.state.reference_resolvers,
        ),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id=run_id, now=NOW,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    [exposure] = [
        e for e in await world.store.list_exposures(run_id) if e.query.task_type == DESIGN
    ]
    [handed] = design.inputs[TASK_INSTRUCTIONS_INPUT]["instructions"]
    return handed["references"], exposure.task_instructions


async def test_every_dispatch_of_the_cycle_reads_the_revision_bound_when_it_was_written():
    """T16, task part. Bugs caught: the reference resolved again at dispatch, so the target
    revised between attempts reaches the second; the bound revision handed without its digest, or
    missing from the exposure."""
    world, resolver = _world()
    cycle = await world.admit_cycle()
    written = _instruct(world, cycle.cycle_id)
    record_id = written.json()["record_id"]

    first = await _dispatch(world, cycle, "run_ref000001")
    resolver.revision = "r2"  # the target is revised between the task's attempts
    again = await _dispatch(world, cycle, "run_ref000002")

    assert written.status_code == 201, written.text
    bound = [{"ref": "fake:doc:spec@r1", "required": True, "digest": "sha256:r1", "content": "r1"}]
    assert first[0] == again[0] == bound
    assert again[1]["bound_references"] == [
        {"record_id": record_id, "ref": "fake:doc:spec@r1", "digest": "sha256:r1"}
    ]


async def test_a_revision_before_dispatch_binds_again():
    """§3.6's release of a task instruction: it is revised before its task dispatches, and the task
    dispatches with the new binding. Bug caught: the revision keeping the revision bound when the
    instruction was first written."""
    world, resolver = _world()
    cycle = await world.admit_cycle()
    record_id = _instruct(world, cycle.cycle_id).json()["record_id"]
    resolver.revision = "r2"

    revised = world.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": "Follow the revised spec.",
              "target": {"cycle_id": cycle.cycle_id, "task_types": [DESIGN]},
              "references": [{"ref": REF, "required": True}]},
    )  # fmt: skip
    handed, _ = await _dispatch(world, cycle, "run_ref000001")

    assert revised.status_code == 201, revised.text
    assert handed == [
        {"ref": "fake:doc:spec@r2", "required": True, "digest": "sha256:r2", "content": "r2"}
    ]


async def test_a_resolver_that_fails_is_a_fault_not_the_writers_mistake():
    """Bug caught: a timeout in the family's resolver answered 422, telling the writer to name a
    revision when nothing about the instruction was wrong; or the instruction stored unbound."""
    world, _ = _world()
    world.client.app.state.reference_resolvers = {"fake": _Crashing()}
    cycle = await world.admit_cycle()

    with pytest.raises(TimeoutError):
        _instruct(world, cycle.cycle_id)

    assert await world.records.list_project("group_run") == []


def test_a_bound_reference_survives_its_revision_stored_as_a_document():
    """Bug caught: the digest or what was written dropped by the document the Postgres store keeps,
    so a restarted runtime hands the revision without its digest, and a continuation can't bind it
    again."""
    from squadops.memory.records import Revision, Source, TaskTarget

    revision = Revision(
        number=1, body="Follow the spec.", author="ada", created_at=NOW, source=Source("api_call"),
        confirmed_by="ada", target=TaskTarget("cyc_x", (DESIGN,)),
        references=(Reference("fake:doc:spec@r1", True, digest="sha256:r1", written=REF),),
    )  # fmt: skip

    assert revision_from_document(revision_document(revision)).references == revision.references


async def test_a_revision_echoing_the_references_a_read_returned_binds_them_again():
    """The second read of the task part. Bug caught: a revision built from a GET's references
    (bound, with ``digest`` and ``written``) stored as a plain revision, so its dispatch is handed
    no digest, its exposure lists nothing bound, and a continuation never binds it again."""
    world, resolver = _world()
    cycle = await world.admit_cycle()
    record_id = _instruct(world, cycle.cycle_id).json()["record_id"]
    read = world.client.get(f"{RECORDS}/{record_id}").json()["revisions"][-1]["references"]
    resolver.revision = "r2"

    revised = world.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": "Follow the spec.", "references": read,
              "target": {"cycle_id": cycle.cycle_id, "task_types": [DESIGN]}},
    )  # fmt: skip
    mismatched = world.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": "Follow the spec.",
              "references": [{**read[0], "written": "fake:doc:other@current"}],
              "target": {"cycle_id": cycle.cycle_id, "task_types": [DESIGN]}},
    )  # fmt: skip
    handed, _ = await _dispatch(world, cycle, "run_ref000001")

    assert revised.status_code == 201, revised.text
    assert handed == [
        {"ref": "fake:doc:spec@r2", "required": True, "digest": "sha256:r2", "content": "r2"}
    ]
    assert mismatched.status_code == 422


async def test_an_instruction_for_a_dispatched_task_is_refused_as_such_before_any_binding():
    """The second read of the task part. Bug caught: the reference bound first, so a resolver
    that is down turns ``409 TASK_DISPATCHED`` into a server error, and one that refuses turns it
    into a 422 about the reference."""
    world, _ = _world()
    world.client.app.state.reference_resolvers = {"fake": _Crashing()}
    cycle = await world.admit_cycle()
    await _dispatch_plain(world, cycle)

    response = _instruct(world, cycle.cycle_id)

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "TASK_DISPATCHED"


async def _dispatch_plain(world: _World, cycle) -> None:
    await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(
            world.store, records=world.records,
            resolvers=world.client.app.state.reference_resolvers,
        ),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id="run_ref000000", now=NOW,
    )  # fmt: skip
