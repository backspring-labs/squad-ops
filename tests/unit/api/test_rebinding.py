"""Re-binding a running unit (SIP-0110 Appendix A §3.7; #2179 stage 2), entered at the HTTP surface
over the in-memory stores and registries. Each unit is pinned by the caller admission uses
(``pin_standalone_cycle``, ``pin_campaign``), and each dispatch is composed by the live composer
(``supply_lessons`` through ``SnapshotRecall``).

What bugs would these catch? A re-binding stored but never read, so the next dispatch is handed the
revision it replaced; one reaching a unit it wasn't made on; a re-binding by someone holding only
one of its two permissions; a unit re-bound in place though its later work would build on work done
under the replaced revision; a campaign's re-binding the intervention ledger never sees.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.routes.memory import memory_records_router, memory_snapshots_router
from squadops.auth.models import Identity, IdentityType, Role, Scope
from squadops.campaigns.models import ControlOperation
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.cycles.models import Run, RunStatus
from squadops.memory.pinning import pin_campaign, pin_standalone_cycle
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.outcomes.ledger import is_intervention
from tests.unit.api.test_memory_record_routes import _identity
from tests.unit.campaigns.builders import campaign
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

pytestmark = [pytest.mark.auth, pytest.mark.domain_memory]

RECORDS = "/api/v1/memory-records"
SNAPSHOTS = "/api/v1/projects/group_run/snapshots"
DESIGN = "development.design_plan"
WHERE = {"task_types": [DESIGN], "roles": ["*"], "stacks": ["*"]}
NOW = datetime(2026, 10, 20, tzinfo=UTC)


class _Launches:
    """The campaign launcher's lock, which a campaign's re-binding holds (``launches_held``)."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()

    def launches_held(self) -> asyncio.Lock:
        return self.lock


class _World:
    def __init__(self) -> None:
        self.store = InMemoryCrossCycleMemoryStore()
        self.records = InMemoryMemoryRecords()
        self.cycles = MemoryCycleRegistry()
        self.campaigns = MemoryCampaignRegistry()
        self.identity: Identity = _identity("ada", Role.ADMIN)
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(memory_records_router)
        app.include_router(memory_snapshots_router)
        app.state.memory_store = self.store
        app.state.memory_records = self.records
        app.state.cycle_registry = self.cycles
        app.state.campaign_registry = self.campaigns
        app.state.campaign_launch = self.launches = _Launches()
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def instruct(self, text: str = "Name each run by its route.") -> str:
        body = {"kind": "instruction", "scope": "project", "project_id": "group_run",
                "body": text, "applicability": WHERE}  # fmt: skip
        return self.client.post(RECORDS, json=body).json()["record_id"]

    def revise(self, record_id: str, text: str) -> None:
        response = self.client.post(
            f"{RECORDS}/{record_id}/revisions", json={"body": text, "applicability": WHERE}
        )
        assert response.status_code == 201, response.text

    async def admit_cycle(self, cycle_id: str = "cyc_recall"):
        cycle = dataclasses.replace(_framing_cycle(), cycle_id=cycle_id)
        await self.cycles.create_cycle(cycle)
        await pin_standalone_cycle(self.store, cycle, now=NOW, records=self.records)
        return cycle

    async def run(self, cycle, run_id: str, status: RunStatus) -> None:
        await self.cycles.create_run(
            Run(run_id=run_id, cycle_id=cycle.cycle_id, run_number=1, status=status.value,
                initiated_by="api", resolved_config_hash="h", workload_type="framing")
        )  # fmt: skip

    async def dispatch(self, cycle, run_id: str = "run_recall0001") -> list[str]:
        """The project instructions the cycle's design task is handed, as the live composer
        hands them, recording each exposure."""
        envelopes = await supply_lessons(
            _plan(cycle), recall=SnapshotRecall(self.store, records=self.records),
            unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id=run_id, now=NOW,
        )  # fmt: skip
        return [
            i["text"]
            for e in envelopes
            if str(e.task_type) == DESIGN
            for i in (e.inputs.get(PROJECT_INSTRUCTIONS_INPUT) or {}).get("instructions", [])
        ]

    def rebind(self, record_id: str, kind: str = "cycle", unit_id: str = "cyc_recall", why="x"):
        return self.client.post(
            f"{SNAPSHOTS}/{kind}/{unit_id}/rebindings", json={"record_id": record_id, "why": why}
        )


async def test_a_rebinding_reaches_the_units_next_dispatch_and_no_other_unit():
    """§3.7's forward path, wired. Bugs caught: the re-binding stored and recall still serving the
    admission pin; another unit that pinned the same revision moved with it; the history lost."""
    world = _World()
    record_id = world.instruct()
    cycle, other = await world.admit_cycle(), await world.admit_cycle("cyc_other")
    world.revise(record_id, "Name each run by its route and its date.")

    response = world.rebind(record_id, why="the old text was ambiguous")
    shown = world.client.get(f"{SNAPSHOTS}/cycle/cyc_recall").json()

    assert response.status_code == 201, response.text
    assert await world.dispatch(cycle) == ["Name each run by its route and its date."]
    assert await world.dispatch(other, "run_other") == ["Name each run by its route."]
    [r] = shown["rebindings"]
    assert (r["replaced"]["revision"], r["replacement"]["revision"], r["why"]) == (
        1, 2, "the old text was ambiguous",
    )  # fmt: skip
    assert "Set its measurements apart from the first task this affects" in response.json()["next"]


def _scoped(*scopes: str) -> Identity:
    return Identity(
        user_id="sam", display_name="sam", roles=(), scopes=scopes,
        identity_type=IdentityType.HUMAN,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("scopes", "status"),
    [
        ((Scope.MEMORY_INSTRUCT,), 403),
        ((Scope.CYCLES_WRITE,), 403),
        ((Scope.MEMORY_INSTRUCT, Scope.CAMPAIGNS_SUPERVISE), 403),
        ((Scope.MEMORY_INSTRUCT, Scope.CYCLES_WRITE), 201),
    ],
    ids=["record-only", "unit-only", "the-wrong-units-authority", "both"],
)
async def test_a_rebinding_needs_the_records_permission_and_the_units_authority(scopes, status):
    world = _World()
    record_id = world.instruct()
    await world.admit_cycle()
    world.revise(record_id, "revised")
    world.identity = _scoped(*scopes)

    response = world.rebind(record_id)

    assert response.status_code == status, response.text
    stored = await world.store.get_snapshot(*unit_of(_framing_cycle()))
    assert len(stored.rebindings) == (1 if status == 201 else 0)


@pytest.mark.parametrize("status", [RunStatus.RUNNING, RunStatus.FAILED])
async def test_a_unit_whose_dispatch_was_handed_the_revision_is_never_rebound_in_place(status):
    """§3.7's forward path is for a unit none of whose dispatches had the replaced revision. Bugs
    caught: a running run re-bound mid-way, its later tasks building on work done under the old
    revision; an ended run's output (a framing plan, an accepted tree) carried into work under the
    new one, the second reader's finding on the first draft."""
    world = _World()
    record_id = world.instruct()
    cycle = await world.admit_cycle()
    await world.run(cycle, "run_recall0001", RunStatus.RUNNING)
    await world.dispatch(cycle)
    if status is RunStatus.FAILED:
        await world.cycles.update_run_status("run_recall0001", RunStatus.FAILED)
    world.revise(record_id, "revised")

    refused = world.rebind(record_id)

    assert refused.status_code == 409
    error = refused.json()["detail"]["error"]
    assert error["code"] == "RESTART_REQUIRED"
    assert "run_recall0001" in error["message"] and "new standalone cycle" in error["message"]
    stored = await world.store.get_snapshot(*unit_of(cycle))
    assert stored.rebindings == () and [p.revision for p in stored.instructions] == [1]


async def test_a_withdrawn_instruction_is_rebound_off_and_no_longer_handed():
    world = _World()
    record_id = world.instruct()
    cycle = await world.admit_cycle()
    world.client.post(f"{RECORDS}/{record_id}/withdrawal", json={"why": "harmful"})

    response = world.rebind(record_id, why="withdrawn: stop handing it")

    assert response.status_code == 201, response.text
    assert response.json()["instructions"] == []
    assert response.json()["rebinding"]["replacement"] is None
    assert await world.dispatch(cycle) == []


async def test_a_campaigns_rebinding_is_a_control_log_row_the_ledger_reads_as_an_intervention():
    world = _World()
    record_id = world.instruct()
    cmp = campaign("cmp_rebound")
    await world.campaigns.create_campaign(
        cmp, actor="ada", actor_role="admin", reason="test", idempotency_key="create"
    )
    await pin_campaign(world.store, cmp, now=NOW, records=world.records)
    world.revise(record_id, "revised")

    response = world.rebind(record_id, kind="campaign", unit_id="cmp_rebound", why="clarified")

    assert response.status_code == 201, response.text
    [row] = [
        e for e in await world.campaigns.control_log("cmp_rebound")
        if e.operation is ControlOperation.REBIND
    ]  # fmt: skip
    assert response.json()["control_log_entry_id"] == row.entry_id
    assert (row.binding["replaced_revision"], row.binding["replacement_revision"]) == (1, 2)
    assert is_intervention(row)


async def _cycle_whose_run_completed(world: _World) -> None:
    cycle = await world.admit_cycle()
    await world.run(cycle, "run_done", RunStatus.COMPLETED)


@pytest.mark.parametrize(
    ("arrange", "path", "status", "says"),
    [
        ("confirmed-after-admission", "cycle/cyc_recall", 422, "binds no revision"),
        ("unrevised", "cycle/cyc_recall", 422, "already binds revision 1"),
        ("ended", "cycle/cyc_recall", 409, "has ended"),
        ("campaigns-cycle", "cycle/cyc_camp", 422, "binds the campaign's snapshot"),
        ("unit-kind", "run/cyc_recall", 422, "a cycle or a campaign"),
    ],
)
async def test_a_rebinding_the_rules_refuse_stores_nothing(arrange, path, status, says):
    world = _World()
    if arrange == "confirmed-after-admission":
        await world.admit_cycle()
        record_id = world.instruct()
    else:
        record_id = world.instruct()
        if arrange == "ended":
            await _cycle_whose_run_completed(world)
        elif arrange == "campaigns-cycle":
            await world.cycles.create_cycle(
                dataclasses.replace(_framing_cycle(), cycle_id="cyc_camp", campaign_id="cmp_x")
            )
        else:
            await world.admit_cycle()
    if arrange != "unrevised":
        world.revise(record_id, "revised")

    response = world.client.post(
        f"{SNAPSHOTS}/{path}/rebindings", json={"record_id": record_id, "why": "x"}
    )

    assert response.status_code == status, response.text
    assert says in response.json()["detail"]["error"]["message"]
    held = await world.store.get_snapshot(*unit_of(_framing_cycle()))
    assert held is None or held.rebindings == ()


async def test_a_rebinding_to_a_revision_naming_current_binds_it_for_the_unit():
    """#2179 T16, the second read's first finding. Bugs caught: the new revision's ``@current``
    stored verbatim, which reads as bound to nothing and releases a hold it should keep; a bound
    reference's revision and digest swapped for the verbatim form."""
    from squadops.memory.rebinding import RebindRefused, rebound
    from tests.unit.memory.test_reference_binding import _Resolver

    world = _World()
    resolver = _Resolver()
    world.client.app.state.reference_resolvers = {"fake": resolver}
    response = world.client.post(
        RECORDS,
        json={"kind": "instruction", "scope": "project", "project_id": "group_run",
              "body": "Read the spec.", "applicability": WHERE,
              "references": [{"ref": "fake:doc:spec@current", "required": True}]},
    )  # fmt: skip
    record_id = response.json()["record_id"]
    cycle = await world.admit_cycle()
    resolver.revision = "r2"
    world.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": "Read the spec, then the notes.", "applicability": WHERE,
              "references": [{"ref": "fake:doc:spec@current", "required": True}]},
    )  # fmt: skip

    applied = world.rebind(record_id, why="the spec moved")

    assert applied.status_code == 201, applied.text
    stored = await world.store.get_snapshot(*unit_of(cycle))
    [bound] = stored.instructions[0].references
    assert (bound.ref, bound.digest) == ("fake:doc:spec@r2", "sha256:r2")
    record = await world.records.get(record_id)
    with pytest.raises(RebindRefused, match="names @current"):
        rebound(stored, record, by="ada", at=NOW, why="no binding given")
