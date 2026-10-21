"""A unit's dispatch turn (#2545; SIP-0110 §5v, §5w), entered where the live run does: each change at
its route, over HTTP on the test's own event loop, and each dispatch through the live composer
(``supply_lessons`` through ``SnapshotRecall``), over one store.

What bugs would these catch? A re-binding or a task instruction going forward while a dispatch it
changes is between reading what it's handed and disclosing it, so the dispatch is handed what the
change's check said no dispatch had; a dispatch reading its binding while a change it would see is
being written, so it's handed the binding the change replaced; a turn that is never given back.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import httpx
import pytest

from squadops.api.routes.memory import interventions
from squadops.cycles.models import RunStatus
from squadops.memory.dispatch_turns import DispatchTurns
from squadops.memory.task_instructions import TaskInstructionsUnavailable
from tests.unit.api.test_rebinding import DESIGN, RECORDS, SNAPSHOTS, _World
from tests.unit.api.test_task_instruction_interventions import (
    _admit_with_instruction,
    _dispatch,
)
from tests.unit.cycles.test_failure_recall import _framing_cycle

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]

OLD, NEW = "Name each run by its route.", "Name each run by its route and its date."


class _Hold:
    """Stops the first call it's set on until released, and says when that call arrived."""

    def __init__(self) -> None:
        self.reached = asyncio.Event()
        self.released = asyncio.Event()

    def on(self, target: Any, name: str, when=lambda *a, **k: True) -> None:
        original = getattr(target, name)

        async def held(*args, **kwargs):
            if when(*args, **kwargs) and not self.reached.is_set():
                self.reached.set()
                await self.released.wait()
            return await original(*args, **kwargs)

        setattr(target, name, held)


async def _still_waiting(task: asyncio.Task) -> bool:
    """Whether ``task`` is still waiting once everything else that's ready has run."""
    done, _ = await asyncio.wait({task}, timeout=0.2)
    return not done


def _client(world: _World) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=world.app), base_url="http://t")


@dataclasses.dataclass
class _Change:
    """One change to what a unit's dispatches are handed: how it's set up, sent and written, what
    its refusal is, and what the design dispatch is handed before and after it."""

    name: str
    refusal: str
    #: The store and method where the change writes, as the route calls it.
    writes: tuple[str, str]

    async def setup(self, world: _World):
        cycle = _framing_cycle()
        if self.name == "rebind":
            record_id = world.instruct(OLD)
            cycle = await world.admit_cycle()
            await world.run(cycle, "run_recall0001", RunStatus.RUNNING)
            world.revise(record_id, NEW)
        elif self.name == "add":
            await world.cycles.create_cycle(cycle)
            record_id = None
        else:
            record_id = await _admit_with_instruction(world, cycle)
        return cycle, record_id

    def send(self, client: httpx.AsyncClient, cycle, record_id):
        target = {"cycle_id": cycle.cycle_id, "task_types": [DESIGN]}
        if self.name == "rebind":
            return client.post(
                f"{SNAPSHOTS}/cycle/{cycle.cycle_id}/rebindings",
                json={"record_id": record_id, "why": "the old text was ambiguous"},
            )
        if self.name == "add":
            return client.post(
                RECORDS,
                json={"kind": "instruction", "scope": "task", "project_id": "group_run",
                      "body": NEW, "target": target},
            )  # fmt: skip
        return client.post(f"{RECORDS}/{record_id}/revisions", json={"body": NEW, "target": target})

    async def handed(self, world: _World, cycle) -> list[str]:
        """What the cycle's design task is handed by this change's kind of instruction."""
        if self.name == "rebind":
            return await world.dispatch(cycle)
        handed, _ = await _dispatch(world, cycle)
        return [i["text"] for i in handed]

    def before(self) -> list[str]:
        return [] if self.name == "add" else [OLD if self.name == "rebind" else "Name the routes."]


CHANGES = [
    _Change("rebind", "RESTART_REQUIRED", ("store", "rebind_snapshot")),
    _Change("add", "TASK_DISPATCHED", ("records", "create")),
    _Change("revise", "TASK_DISPATCHED", ("records", "append_revision")),
]


@pytest.mark.parametrize("change", CHANGES, ids=lambda c: c.name)
async def test_a_change_waits_for_a_dispatch_being_composed_then_sees_it(change):
    """The dispatch has read what it's handed and is disclosing it. Bugs caught: the change's check
    running in that gap, finding no dispatch and going forward, so the dispatch is handed what the
    change replaced; the composer giving up its turn between its read and its disclosure."""
    world = _World()
    cycle, record_id = await change.setup(world)
    hold = _Hold()
    hold.on(world.store, "record_exposure", lambda e: e.query.task_type == DESIGN)

    composing = asyncio.create_task(change.handed(world, cycle))
    await hold.reached.wait()
    async with _client(world) as client:
        changing = asyncio.create_task(change.send(client, cycle, record_id))
        waited = await _still_waiting(changing)
        hold.released.set()
        handed, response = await composing, await changing

    assert waited
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == change.refusal
    assert handed == change.before()


@pytest.mark.parametrize("change", CHANGES, ids=lambda c: c.name)
async def test_a_dispatch_waits_for_a_change_being_written_then_is_handed_it(change):
    """The change has passed its check and is writing. Bugs caught: the dispatch reading its binding
    in that gap, so it's handed what the change replaces while the change goes forward; the change
    giving up its turn between its check and its write."""
    world = _World()
    cycle, record_id = await change.setup(world)
    hold = _Hold()
    where, method = change.writes
    hold.on(getattr(world, where), method)

    async with _client(world) as client:
        changing = asyncio.create_task(change.send(client, cycle, record_id))
        await hold.reached.wait()
        composing = asyncio.create_task(change.handed(world, cycle))
        waited = await _still_waiting(composing)
        hold.released.set()
        response, handed = await changing, await composing

    assert waited
    assert response.status_code == 201, response.text
    assert handed == [NEW]


async def test_a_turn_not_given_refuses_a_change_within_its_bound_and_holds_a_dispatch(monkeypatch):
    """Bugs caught: a change written without its turn; one waiting on it for the dispatch's bound,
    past the CLI's own request timeout, so the operator reads a timeout rather than its 503 (#2605);
    a dispatch sent without its turn, or one that hangs the run."""
    world = _World()
    cycle, _ = await CHANGES[1].setup(world)
    monkeypatch.setattr(interventions, "CHANGE_WAIT_SECONDS", 0.05)

    async with world.store.dispatch_turn("cycle", cycle.cycle_id), _client(world) as client:
        response = await asyncio.wait_for(CHANGES[1].send(client, cycle, None), timeout=5)
    world.store._turns = DispatchTurns(wait_seconds=0.05)
    async with world.store.dispatch_turn("cycle", cycle.cycle_id):
        with pytest.raises(TaskInstructionsUnavailable, match="dispatch turn"):
            await _dispatch(world, cycle)

    assert response.status_code == 503, response.text
    assert response.json()["detail"]["error"]["code"] == "DISPATCH_TURN_UNAVAILABLE"
    assert await world.records.list_project("group_run") == []
    assert await world.store.list_exposures("run_recall0001") == []


async def _dispatching(store, unit, exposure, entered: asyncio.Event, release: asyncio.Event):
    """A dispatch in its unit's turn, as the composer takes it: it has read what it's handed, and
    discloses once released."""
    async with store.dispatch_turn(*unit):
        entered.set()
        await release.wait()
        await store.record_exposure(exposure)
