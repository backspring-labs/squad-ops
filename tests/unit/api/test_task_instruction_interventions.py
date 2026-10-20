"""A task instruction added or revised after its cycle's admission (SIP-0110 Appendix A §3.5;
#2178 stage 2), entered at the records route over the in-memory stores, with each dispatch composed
by the live composer (``supply_lessons`` through ``SnapshotRecall``).

What bugs would these catch? An instruction added after a task dispatched, so the task's re-takes,
repairs and the work built on its output mix a binding its first dispatch never had; an unreadable
exposure store read as "nothing dispatched"; an intervention that reaches the task unmarked, so its
measurement isn't set apart; an instruction admitted with the cycle marked as one; a campaign
cycle's intervention the intervention ledger never sees.
"""

from __future__ import annotations

import dataclasses

import pytest

from adapters.memory.recall import SnapshotRecall
from squadops.campaigns.models import ControlOperation
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
from squadops.memory.records import Source, SourceKind
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT, admitted
from squadops.outcomes.ledger import is_intervention
from tests.unit.api.test_rebinding import DESIGN, NOW, RECORDS, _World
from tests.unit.campaigns.builders import campaign
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]


def _add(world: _World, cycle_id: str = "cyc_recall", text: str = "Cover the empty list."):
    return world.client.post(
        RECORDS,
        json={"kind": "instruction", "scope": "task", "project_id": "group_run", "body": text,
              "target": {"cycle_id": cycle_id, "task_types": [DESIGN]}},
    )  # fmt: skip


async def _admit_with_instruction(world: _World, cycle, types=(DESIGN,)) -> str:
    """The cycle and the instruction its create request carried, as the cycle route stores them."""
    await world.cycles.create_cycle(cycle)
    [record] = admitted(
        [{"text": "Name the routes.", "task_types": list(types)}],
        project_id="group_run", cycle_id=cycle.cycle_id, actor="ada", now=NOW,
        instructable=lambda t: True,
        source=Source(SourceKind.CYCLE_REQUEST, {"cycle_id": cycle.cycle_id}),
    )  # fmt: skip
    await world.records.create(record)
    return record.record_id


async def _dispatch(world: _World, cycle, run_id: str = "run_recall0001"):
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(world.store, records=world.records),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id=run_id, now=NOW,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    [exposure] = [
        e for e in await world.store.list_exposures(run_id) if e.query.task_type == DESIGN
    ]
    return (design.inputs.get(TASK_INSTRUCTIONS_INPUT) or {}).get("instructions", []), exposure


async def test_an_instruction_added_before_its_task_dispatches_reaches_it_marked_as_an_intervention():
    """§3.5, wired. Bugs caught: the added instruction never reaching the task; reaching it
    unmarked, so the measurement isn't set apart; the admitted one marked too."""
    world = _World()
    cycle = _framing_cycle()
    admitted_id = await _admit_with_instruction(world, cycle)

    response = _add(world)
    handed, exposure = await _dispatch(world, cycle)

    assert response.status_code == 201, response.text
    added_id = response.json()["record_id"]
    assert [(i["record_id"], i.get("intervention")) for i in handed] == [
        (admitted_id, None), (added_id, True),
    ]  # fmt: skip
    assert exposure.task_instructions["interventions"] == [added_id]
    assert response.json()["control_log_entry_id"] is None


@pytest.mark.parametrize("change", ["add", "revise"])
async def test_an_instruction_for_a_task_that_already_dispatched_is_refused(change):
    """Bugs caught: an instruction added or corrected after its task dispatched, in any run, so
    its re-take, its repairs or the work built on its output get a binding it never had."""
    world = _World()
    cycle = _framing_cycle()
    admitted_id = await _admit_with_instruction(world, cycle)
    await _dispatch(world, cycle)
    before = await world.records.list_project("group_run")

    if change == "add":
        response = _add(world)
    else:
        response = world.client.post(
            f"{RECORDS}/{admitted_id}/revisions",
            json={"body": "Name the routes and the methods.",
                  "target": {"cycle_id": cycle.cycle_id, "task_types": [DESIGN]}},
        )  # fmt: skip

    assert response.status_code == 409, response.text
    error = response.json()["detail"]["error"]
    assert error["code"] == "TASK_DISPATCHED" and "run_recall0001" in error["message"]
    assert await world.records.list_project("group_run") == before


async def test_an_exposure_store_that_cant_be_read_refuses_the_instruction():
    """Bug caught: no store to read the dispatches from answered as "nothing dispatched"."""
    world = _World()
    await world.cycles.create_cycle(_framing_cycle())
    world.client.app.state.memory_store = None

    response = _add(world)

    assert response.status_code == 503
    assert await world.records.list_project("group_run") == []


async def test_a_campaign_cycles_instruction_and_its_withdrawal_are_control_log_interventions():
    world = _World()
    cmp = campaign("cmp_instructed")
    await world.campaigns.create_campaign(
        cmp, actor="ada", actor_role="admin", reason="test", idempotency_key="create"
    )
    await world.cycles.create_cycle(
        dataclasses.replace(_framing_cycle(), cycle_id="cyc_camp", campaign_id="cmp_instructed")
    )

    added = _add(world, cycle_id="cyc_camp")
    record_id = added.json()["record_id"]
    gone = world.client.post(f"{RECORDS}/{record_id}/withdrawal", json={"why": "superseded"})

    rows = [
        e for e in await world.campaigns.control_log("cmp_instructed")
        if e.operation is ControlOperation.INSTRUCT
    ]  # fmt: skip
    assert [(r.binding["action"], r.binding["record_id"]) for r in rows] == [
        ("add", record_id), ("withdraw", record_id),
    ]  # fmt: skip
    assert [r.entry_id for r in rows] == [
        added.json()["control_log_entry_id"], gone.json()["control_log_entry_id"],
    ]  # fmt: skip
    assert all(is_intervention(r) for r in rows)


async def test_another_cycles_dispatch_leaves_this_cycles_instruction_open():
    """Bug caught: the project's dispatches read as this cycle's, so a cycle that hasn't started
    refuses an instruction because another cycle of the project ran the same task type."""
    world = _World()
    other = dataclasses.replace(_framing_cycle(), cycle_id="cyc_other")
    await world.cycles.create_cycle(other)
    await world.cycles.create_cycle(_framing_cycle())
    await _dispatch(world, other, run_id="run_other")

    response = _add(world)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("kind", ["cycle_request", "gate_decision"])
async def test_a_source_only_its_own_route_writes_is_refused_here(kind):
    """The second reader's finding. Bug caught: a client claiming ``cycle_request`` so its
    instruction reads as admitted and reaches the task unmarked, its roll still counted."""
    world = _World()
    await world.cycles.create_cycle(_framing_cycle())

    response = world.client.post(
        RECORDS,
        json={"kind": "instruction", "scope": "task", "project_id": "group_run", "body": "Spoof.",
              "target": {"cycle_id": "cyc_recall", "task_types": [DESIGN]},
              "source": {"kind": kind, "ids": {"cycle_id": "cyc_recall"}}},
    )  # fmt: skip

    assert response.status_code == 422
    assert "written by its own route" in response.json()["detail"]["error"]["message"]
    assert await world.records.list_project("group_run") == []


async def test_a_revision_never_moves_an_instruction_to_another_cycle():
    """The second reader's finding. Bug caught: an instruction whose task dispatched, moved to a
    standalone cycle: in effect a withdrawal after dispatch, recorded on neither cycle, and past
    the campaign's permission for someone who lacks it."""
    world = _World()
    record_id = await _admit_with_instruction(world, _framing_cycle())
    await world.cycles.create_cycle(dataclasses.replace(_framing_cycle(), cycle_id="cyc_b"))

    response = world.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": "Moved.", "target": {"cycle_id": "cyc_b", "task_types": [DESIGN]}},
    )

    assert response.status_code == 422
    assert "cycle is fixed" in response.json()["detail"]["error"]["message"]
    assert len((await world.records.get(record_id)).revisions) == 1


async def test_a_revision_dropping_a_task_type_that_dispatched_is_refused():
    """Bug caught: narrowing an instruction to leave out a type that already dispatched, which
    withdraws it from that task's re-takes and repairs after its first dispatch had it."""
    world = _World()
    cycle = _framing_cycle()
    record_id = await _admit_with_instruction(world, cycle, types=(DESIGN, "qa.test"))
    await _dispatch(world, cycle)

    response = world.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": "Narrowed.", "target": {"cycle_id": "cyc_recall", "task_types": ["qa.test"]}},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "TASK_DISPATCHED"
    assert len((await world.records.get(record_id)).revisions) == 1


def _citing(cycle_id: str, scope: str = "task", **extra) -> dict:
    """A records-API body whose provenance cites a lesson revision."""
    body = {
        "kind": "instruction",
        "scope": scope,
        "project_id": "group_run",
        "body": "Apply it.",
        "source": {"kind": "api_call", "ids": {"lesson_revision": "pat_0123456789abcdef@2"}},
    }
    if scope == "task":
        body["target"] = {"cycle_id": cycle_id, "task_types": [DESIGN]}
    else:
        body["applicability"] = {"task_types": [DESIGN], "roles": ["*"], "stacks": ["*"]}
    return {**body, **extra}  # fmt: skip


class _SnapshotUnreadable:
    """A memory store whose snapshot read fails, everything else as the in-memory one."""

    def __init__(self, inner):
        self._inner = inner

    async def get_snapshot(self, *_):
        raise ConnectionError("the pool is gone")

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.mark.parametrize(
    ("unit", "disabled", "status", "says"),
    [
        ("cycle", True, 422, "declares lessons disabled"),
        ("cycle", False, 201, None),
        ("campaign", True, 422, "declares lessons disabled"),
        ("campaign", False, 201, None),
        ("unreadable", False, 422, "can't be read"),
    ],
    ids=["own-unit-disabled", "own-unit-on", "campaigns-unit-disabled", "campaigns-unit-on",
         "snapshot-unreadable"],
)  # fmt: skip
async def test_the_records_api_never_lets_a_lesson_reach_the_lessons_disabled_control(
    unit, disabled, status, says
):
    """§3.7, through the records API, the second reader's finding on #2180 (its three mutants
    survived). Bugs caught: the rule enforced in chat only; a campaign's cycle judged by a snapshot
    of its own, which it never has, rather than its campaign's; an unreadable snapshot read as
    "not the control"."""
    world = _World()
    if unit == "campaign":
        cmp = campaign("cmp_lessons")
        await world.campaigns.create_campaign(
            cmp, actor="ada", actor_role="admin", reason="t", idempotency_key="c"
        )
        cycle = dataclasses.replace(_framing_cycle(), cycle_id="cyc_c", campaign_id="cmp_lessons")
        await world.cycles.create_cycle(cycle)
        await pin_unit(
            world.store, unit_kind=UnitKind.CAMPAIGN, unit_id="cmp_lessons",
            project_id="group_run", pinned_at=NOW, disabled=disabled, records=world.records,
        )  # fmt: skip
    else:
        cycle = _framing_cycle()
        await world.cycles.create_cycle(cycle)
        await pin_unit(
            world.store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
            pinned_at=NOW, disabled=disabled, records=world.records,
        )  # fmt: skip
        if unit == "unreadable":
            world.client.app.state.memory_store = _SnapshotUnreadable(world.store)

    response = world.client.post(RECORDS, json=_citing(cycle.cycle_id))

    assert response.status_code == status, response.text
    if says:
        assert says in response.json()["detail"]["error"]["message"]


async def test_a_project_instruction_never_carries_a_lesson():
    """Bug caught: a lesson cited by a project instruction, which every unit pins, the
    lessons-disabled control included, so the guarantee leaks through the project."""
    world = _World()

    response = world.client.post(RECORDS, json=_citing("", scope="project"))

    assert response.status_code == 422
    assert "through its approval" in response.json()["detail"]["error"]["message"]
