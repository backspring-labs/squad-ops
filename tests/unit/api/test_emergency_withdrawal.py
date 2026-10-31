"""A task instruction's emergency withdrawal (SIP-0110 Appendix A §3.8, T13; #2178), entered at the
HTTP surface over the in-memory stores and the memory cycle registry, with each exposure recorded
where the live composer records it (``supply_lessons``).

The restart itself is the cycle's (``tests/unit/cycles/test_emergency_restart.py``); these hold
what the route decides and writes: which runs it halts, where each restarts from, the replacement
the restart is handed, and what it refuses with nothing written.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.campaigns.models import ControlOperation
from squadops.cycles.models import RunStatus
from squadops.memory.records import RecordStatus
from squadops.memory.task_instructions import is_intervention
from squadops.outcomes.ledger import is_intervention as is_ledger_intervention
from tests.unit.api.test_rebinding import RECORDS, _World
from tests.unit.api.test_task_instruction_interventions import _admit_with_instruction, _dispatch
from tests.unit.campaigns.builders import campaign
from tests.unit.cycles.test_failure_recall import _framing_cycle

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]

WHY = "it names the wrong table"


def _emergency(world: _World, record_id: str, **extra):
    return world.client.post(
        f"{RECORDS}/{record_id}/withdrawal", json={"why": WHY, "emergency": True, **extra}
    )


async def test_an_emergency_halts_the_run_that_received_it_and_its_restart_gets_the_correction():
    """§3.8 through the route. Bugs caught: an emergency that halts nothing, so the run goes on
    building on the instruction; a halt that doesn't say where the restart runs from; the restart
    handed the withdrawn instruction, or never handed the correction, which §5w's own check would
    refuse to add once the task has dispatched."""
    world = _World()
    cycle = _framing_cycle()
    record_id = await _admit_with_instruction(world, cycle)
    await world.run(cycle, "run_recall0001", RunStatus.RUNNING)
    _, exposure = await _dispatch(world, cycle)
    halted_when_cancelled = []
    cancel = world.cycles.cancel_run

    async def cancel_run(run_id):
        # The cycle restarts what it reads halted when it sees the cancel: the halt comes first.
        halted_when_cancelled.append((await world.cycles.get_run(run_id)).halt is not None)
        await cancel(run_id)

    world.cycles.cancel_run = cancel_run

    response = _emergency(world, record_id, replacement="Name the routes by their resource.")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["halted"] == [
        {"run_id": "run_recall0001", "restart_from_task_id": exposure.task_id}
    ]
    run = await world.cycles.get_run("run_recall0001")
    assert (run.status, run.halt.record_id, run.halt.requested_by, run.halt.why) == (
        "cancelled", record_id, "ada", WHY,
    )  # fmt: skip
    assert run.halt.restart_from_task_id == exposure.task_id and halted_when_cancelled == [True]
    original = await world.records.get(record_id)
    correction = await world.records.get(body["replacement_record_id"])
    assert original.status == RecordStatus.WITHDRAWN
    assert (correction.status, correction.current.target) == (
        RecordStatus.ACTIVE, original.current.target,
    )  # fmt: skip
    assert is_intervention(correction) and correction.current.source.ids["corrects"] == record_id

    handed, _ = await _dispatch(world, cycle, run_id="run_restart0001")
    assert [(i["text"], i.get("intervention")) for i in handed] == [
        ("Name the routes by their resource.", True)
    ]


async def _received_then(world: _World, cycle, setup: str) -> None:
    """The cycle's runs, after its first run received the instruction (unless ``not dispatched``)."""
    from squadops.cycles.models import Run

    first = RunStatus.RUNNING if setup == "not dispatched" else RunStatus.COMPLETED
    await world.run(cycle, "run_recall0001", first)
    if setup != "not dispatched":
        await _dispatch(world, cycle)
    if setup == "a later run built on it":
        await world.cycles.create_run(
            Run(run_id="run_impl0001", cycle_id=cycle.cycle_id, run_number=2, status="running",
                initiated_by="system", resolved_config_hash="h", workload_type="implementation")
        )  # fmt: skip


@pytest.mark.parametrize(
    ("setup", "halted"),
    [
        ("a later run built on it", [{"run_id": "run_impl0001", "restart_from_task_id": None}]),
        ("nothing in flight", []),
        ("not dispatched", []),
    ],
)
async def test_what_an_emergency_halts(setup, halted):
    """Bugs caught: a run that only built on the instruction's work (its framing run finished)
    left running; a run that built on it restarted from a task it never ran; a finished run
    cancelled, rewriting what happened; a run that never received the instruction halted."""
    world = _World()
    cycle = _framing_cycle()
    record_id = await _admit_with_instruction(world, cycle)
    await _received_then(world, cycle, setup)
    statuses = {r.run_id: r.status for r in await world.cycles.list_runs(cycle.cycle_id)}

    response = _emergency(world, record_id)

    assert response.status_code == 201, response.text
    assert response.json()["halted"] == halted
    after = {r.run_id: r.status for r in await world.cycles.list_runs(cycle.cycle_id)}
    assert after == {**statuses, **{h["run_id"]: "cancelled" for h in halted}}


@pytest.mark.parametrize(
    ("case", "status"),
    [
        ("dispatches unreadable", 503),
        ("a project instruction", 422),
        ("a replacement without an emergency", 422),
        ("a blank replacement", 422),
    ],
)
async def test_an_emergency_refused_writes_nothing(case, status):
    """Bugs caught: an emergency that can't read what received the instruction answered as
    "nothing did", withdrawing it and leaving the work running; a project instruction's emergency
    halting runs its re-binding owns (§5v); a correction stored with no emergency behind it, which
    would bypass §5w's dispatched check; an empty correction handed to the restart."""
    world = _World()
    cycle = _framing_cycle()
    record_id = await _admit_with_instruction(world, cycle)
    await world.run(cycle, "run_recall0001", RunStatus.RUNNING)
    await _dispatch(world, cycle)
    body: dict = {"why": WHY, "emergency": True}
    if case == "dispatches unreadable":
        world.client.app.state.memory_store = None
    elif case == "a project instruction":
        record_id = world.instruct()
    elif case == "a replacement without an emergency":
        body = {"why": WHY, "replacement": "Name the routes."}
    else:
        body["replacement"] = "  "
    before = await world.records.list_project("group_run")

    response = world.client.post(f"{RECORDS}/{record_id}/withdrawal", json=body)

    assert response.status_code == status, response.text
    assert await world.records.list_project("group_run") == before
    assert (await world.cycles.get_run("run_recall0001")).status == "running"


async def test_a_campaign_cycles_emergency_is_its_intervention_row_naming_what_it_halted():
    """A campaign's measurement is set apart where its ledger counts it. Bugs caught: the
    emergency missing from the campaign's control log, or written as a plain withdrawal that
    doesn't say what it halted."""
    world = _World()
    await world.campaigns.create_campaign(
        campaign("cmp_emergency"), actor="ada", actor_role="admin", reason="t", idempotency_key="c"
    )
    cycle = dataclasses.replace(_framing_cycle(), cycle_id="cyc_camp", campaign_id="cmp_emergency")
    record_id = await _admit_with_instruction(world, cycle)
    await world.run(cycle, "run_recall0001", RunStatus.RUNNING)
    _, exposure = await _dispatch(world, cycle)

    response = _emergency(world, record_id)

    [row] = [
        e for e in await world.campaigns.control_log("cmp_emergency")
        if e.operation is ControlOperation.INSTRUCT
    ]  # fmt: skip
    assert row.entry_id == response.json()["control_log_entry_id"]
    assert (row.binding["action"], row.binding["emergency"], row.reason) == (
        "emergency_withdraw", True, WHY,
    )  # fmt: skip
    assert row.binding["halted"] == [
        {"run_id": "run_recall0001", "restart_from_task_id": exposure.task_id}
    ]
    assert is_ledger_intervention(row)
