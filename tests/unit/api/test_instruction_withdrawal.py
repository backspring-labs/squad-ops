"""A project instruction's emergency withdrawal (SIP-0110 Appendix A §3.8, §0.7; #2179 stage 2), entered
at the HTTP surface over the in-memory stores, with each unit pinned where admission pins it
(``pin_unit``) and each exposure recorded where the composer records it (``supply_lessons``).

What bugs would these catch? A withdrawal that says nothing of the units running with the
instruction pinned, so their work and measurements go on as if it never happened; a unit admitted
before the instruction named as holding it; a store failure answered as "no unit holds it"; an
exposure that used a withdrawn instruction read as if it were still in force, or rewritten.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.routes.memory import memory_records_router, memory_router
from squadops.auth.models import Role
from squadops.campaigns.models import CampaignState
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
from tests.unit.api.test_lesson_routes import _identity, _Units
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]

RECORDS = "/api/v1/memory-records"
DESIGN = "development.design_plan"


class _World:
    def __init__(self) -> None:
        self.store = InMemoryCrossCycleMemoryStore()
        self.records = InMemoryMemoryRecords()
        self.units = _Units()
        app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = _identity(Role.ADMIN)
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(memory_router)
        app.include_router(memory_records_router)
        app.state.memory_store = self.store
        app.state.memory_records = self.records
        app.state.campaign_registry = self.units
        app.state.cycle_registry = self.units
        app.state.authz_port = KeycloakAuthzAdapter()
        self.app = app
        self.client = TestClient(app)

    def instruct(self, task_type: str = DESIGN) -> str:
        body = {
            "kind": "instruction", "scope": "project", "project_id": "group_run",
            "body": "Name each run by its route.",
            "applicability": {"task_types": [task_type], "roles": ["*"], "stacks": ["*"]},
        }  # fmt: skip
        response = self.client.post(RECORDS, json=body)
        assert response.status_code == 201, response.text
        return response.json()["record_id"]

    async def admit(self, kind: UnitKind, unit_id: str):
        return await pin_unit(
            self.store, unit_kind=kind, unit_id=unit_id, project_id="group_run",
            pinned_at=datetime.now(UTC), disabled=False, records=self.records,
        )  # fmt: skip

    def withdraw(self, record_id: str):
        return self.client.post(f"{RECORDS}/{record_id}/withdrawal", json={"why": "harmful"})


async def test_a_withdrawal_names_the_units_that_pinned_it_and_later_units_pin_without_it():
    """§3.8 through the route. Bugs caught: a withdrawal silent about the running unit that holds
    the instruction; a unit admitted before it was confirmed named as holding it; a finished unit
    asked to halt; a unit admitted afterwards still pinning it."""
    world = _World()
    await world.admit(UnitKind.CYCLE, "cyc_before")
    record_id = world.instruct()
    world.units.campaigns.update({"cmp_live": CampaignState.BUILDING})
    world.units.runs.update({"cyc_before": ["running"], "cyc_done": ["completed", "completed"]})
    await world.admit(UnitKind.CAMPAIGN, "cmp_live")
    await world.admit(UnitKind.CYCLE, "cyc_done")

    response = world.withdraw(record_id)
    after = await world.admit(UnitKind.CYCLE, "cyc_after")

    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "withdrawn"
    assert [u["unit_id"] for u in body["units_holding_it"]] == ["cmp_live"]
    assert [u["unit_id"] for u in body["finished_units_holding_it"]] == ["cyc_done"]
    assert "halt or restart" in body["next"] and "Appendix A §3.8" in body["next"]
    assert "a new cycle of a campaign, reads the same snapshot" in body["next"]
    assert after.instructions == ()


class _Unreadable(InMemoryCrossCycleMemoryStore):
    async def list_snapshots_pinning(self, record_id: str):
        raise ConnectionError("the pool is gone")


@pytest.mark.parametrize("store", [None, _Unreadable()], ids=["store-absent", "store-fails"])
async def test_a_withdrawal_whose_snapshots_cant_be_read_says_the_holders_are_unknown(store):
    """Bug caught: a snapshot store that can't answer reported as "no unit holds it", so the
    running unit that pinned the instruction is never halted. The withdrawal itself stands, and
    the store's error text stays in the log."""
    world = _World()
    record_id = world.instruct()
    await world.admit(UnitKind.CAMPAIGN, "cmp_live")
    world.app.state.memory_store = store

    body = world.withdraw(record_id).json()

    assert body["status"] == "withdrawn"
    assert (body["units_holding_it"], body["finished_units_holding_it"]) == (None, None)
    assert "unknown" in body["next"] and "pool is gone" not in body["next"]
    assert (await world.records.get(record_id)).status == "withdrawn"


async def test_a_notes_withdrawal_reads_no_snapshot_and_names_no_unit():
    """Bug caught: a note's withdrawal answering "no unit holds it", or "holders unknown" when
    the snapshot store is down, though no kind but a project instruction is ever pinned."""
    world = _World()
    world.app.state.memory_store = _Unreadable()
    note = world.client.post(
        RECORDS, json={"kind": "note", "scope": "project", "project_id": "group_run", "body": "x"}
    ).json()["record_id"]

    body = world.withdraw(note).json()

    assert body["status"] == "withdrawn"
    assert (body["units_holding_it"], body["finished_units_holding_it"], body["next"]) == (
        [], [], None,
    )  # fmt: skip


async def test_an_exposure_that_used_a_withdrawn_instruction_is_marked_and_kept_as_recorded():
    """§3.8's "what a person sees", wired from the composer's exposure. Bugs caught: a dispatch
    that was handed a now-withdrawn instruction read as if it were still in force; a mark written
    into the exposure, so the record of what the task received changes; a task never handed it
    marked."""
    world = _World()
    record_id = world.instruct()
    cycle = _framing_cycle()
    await world.admit(UnitKind.CYCLE, cycle.cycle_id)
    await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(world.store, records=world.records),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id="run_recall0001",
        now=datetime.now(UTC),
    )  # fmt: skip
    url = "/api/v1/projects/group_run/exposures"
    before = world.client.get(url, params={"run_id": "run_recall0001"}).json()

    world.withdraw(record_id)
    after = world.client.get(url, params={"run_id": "run_recall0001"}).json()

    marks = {e["task_id"]: e["withdrawn_instructions"] for e in after}
    handed = [e["task_id"] for e in before if e.get("project_instructions", {}).get("supplied")]
    assert len(handed) == 1 and all(e["withdrawn_instructions"] == [] for e in before)
    [mark] = marks[handed[0]]
    assert (mark["record_id"], mark["revision"], mark["section"], mark["why"]) == (
        record_id, "1", "project_instructions", "harmful",
    )  # fmt: skip
    assert all(marks[t] == [] for t in marks if t != handed[0])
    assert [{k: v for k, v in e.items() if k != "withdrawn_instructions"} for e in after] == [
        {k: v for k, v in e.items() if k != "withdrawn_instructions"} for e in before
    ]


async def test_an_exposure_whose_records_cant_be_read_is_not_read_as_unwithdrawn():
    """Bug caught: the records store being down answering "nothing it used was withdrawn" for a
    task that was handed an instruction."""
    world = _World()
    world.instruct()
    cycle = _framing_cycle()
    await world.admit(UnitKind.CYCLE, cycle.cycle_id)
    await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(world.store, records=world.records),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id="run_recall0001",
        now=datetime.now(UTC),
    )  # fmt: skip
    world.app.state.memory_records = None

    exposures = world.client.get(
        "/api/v1/projects/group_run/exposures", params={"run_id": "run_recall0001"}
    ).json()

    marks = {
        bool(e.get("project_instructions", {}).get("supplied")): e["withdrawn_instructions"]
        for e in exposures
    }
    assert marks == {True: None, False: []}
