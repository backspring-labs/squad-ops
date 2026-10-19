"""A memory record's uses, entered at the route the console's record view calls (SIP-0110 Appendix A §3.11,
T11; #2182): ``GET /api/v1/memory-records/{id}/uses``, over the stores a deploy reads, with a real build
behind an exposure."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.routes.memory import memory_records_router
from squadops.auth.models import Role
from squadops.cycles.models import Cycle, TaskFlowPolicy
from squadops.cycles.verification_integrity import RunVerdict
from squadops.memory.chat import ChatExposure
from squadops.memory.context import Disposition, Need, RecordRef, Section, SectionKind
from squadops.memory.record_uses import NO_EFFECT_MEASURED
from tests.unit.api.test_a_failed_cycle_does_not_read_accepted import _summary as _verification
from tests.unit.api.test_memory_record_routes import ANYWHERE, _identity
from tests.unit.memory.test_indicators import _exposure, _run
from tests.unit.memory.test_indicators import _summary as _loop

pytestmark = [pytest.mark.domain_memory, pytest.mark.auth]

T0 = datetime(2026, 10, 19, tzinfo=UTC)
URL = "/api/v1/memory-records"


@pytest.fixture
def world():
    class World:
        def __init__(self) -> None:
            self.identity = _identity("ada", Role.ADMIN)
            outer = self
            app = FastAPI()

            class InjectIdentity(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):
                    request.state.identity = outer.identity
                    return await call_next(request)

            app.add_middleware(InjectIdentity)
            app.include_router(memory_records_router)
            self.records, self.store = InMemoryMemoryRecords(), InMemoryCrossCycleMemoryStore()
            self.cycles, self.campaigns = MemoryCycleRegistry(), MemoryCampaignRegistry()
            app.state.memory_records, app.state.memory_store = self.records, self.store
            app.state.cycle_registry, app.state.campaign_registry = self.cycles, self.campaigns
            app.state.authz_port = KeycloakAuthzAdapter()
            self.client = TestClient(app)

        def as_(self, user: str, role: str):
            self.identity = _identity(user, role)
            return self

    return World()


async def _built_cycle(cycles: MemoryCycleRegistry) -> None:
    """``cyc_1``: a framing run, then an implementation run that went green after two failed rounds."""
    await cycles.create_cycle(
        Cycle(
            cycle_id="cyc_1", project_id="group_run", created_at=T0, created_by="ada",
            prd_ref=None, squad_profile_id="full", squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"), build_strategy="fresh",
        )
    )  # fmt: skip
    await cycles.create_run(_run("run_f", "framing"))
    await cycles.create_run(_run("run_i", "implementation", number=2))
    await cycles.record_run_loop_summary("run_i", _loop(2))
    await cycles.record_run_verification_summary("run_i", _verification(RunVerdict.ACCEPTED))


def _chat(user: str, message_id: str, record_id: str) -> ChatExposure:
    section = Section(
        SectionKind.PROJECT_INSTRUCTIONS, Need.OPTIONAL, Disposition.SUPPLIED,
        supplied=(RecordRef(record_id, "1"),),
    )  # fmt: skip
    return ChatExposure(f"s_{user}", message_id, user, "comms-agent", "group_run", T0, (section,))


async def test_an_instructions_uses_are_its_dispatches_its_turns_and_one_build_and_no_effect(world):
    """T11. Bug caught: a dispatch that was handed the instruction missing from its view, one build
    counted once per dispatch it fed, another person's chat turn opened to a reader, or an effect
    read off a green build."""
    record_id = world.client.post(
        URL,
        json={"kind": "instruction", "scope": "project", "project_id": "group_run",
              "body": "name each run by its route", "applicability": ANYWHERE},
    ).json()["record_id"]  # fmt: skip
    await _built_cycle(world.cycles)
    handed = {"disposition": "supplied", "supplied": [{"record_id": record_id, "revision": "1"}]}
    plan = replace(_exposure("run_f", "t_plan"), project_instructions=handed)
    build = replace(_exposure("run_i", "t_dev"), project_instructions=handed)
    unrelated = _exposure("run_i", "t_qa")
    for exposure in (plan, build, unrelated):
        await world.store.record_exposure(exposure)
    await world.store.record_chat_exposure(_chat("ada", "m_ada", record_id))
    await world.store.record_chat_exposure(_chat("bo", "m_bo", record_id))

    uses = world.client.get(f"{URL}/{record_id}/uses").json()

    assert sorted((t["task_id"], t["section"], t["revision"]) for t in uses["tasks"]) == [
        ("t_dev", "project_instructions", "1"),
        ("t_plan", "project_instructions", "1"),
    ]
    assert [(b["run_id"], sorted(b["exposures"]), b["verdict"], b["rounds_to_green"]) for b in uses["builds"]] == [
        ("run_i", sorted([plan.exposure_id, build.exposure_id]), RunVerdict.ACCEPTED, 2),
    ]  # fmt: skip
    assert [c["message_id"] for c in uses["chats"]] == ["m_ada"]
    assert uses["others_chat_turns"] == 1
    assert uses["effect"] == NO_EFFECT_MEASURED


async def test_a_task_the_record_held_is_a_use_and_feeds_no_build(world):
    """§3.6's hold, in the view. Bug caught: a task held undispatched for the record read as if it
    were supplied, and credited with the build its run never reached."""
    record_id = world.client.post(
        URL,
        json={"kind": "instruction", "scope": "project", "project_id": "group_run",
              "body": "x", "applicability": ANYWHERE},
    ).json()["record_id"]  # fmt: skip
    await _built_cycle(world.cycles)
    held = {
        "disposition": "incomplete", "supplied": [],
        "unresolved": [{"record_id": record_id, "revision": "1", "why": "too long for the prompt"}],
    }  # fmt: skip
    await world.store.record_exposure(
        replace(_exposure("run_i", "t_dev"), project_instructions=held)
    )

    uses = world.client.get(f"{URL}/{record_id}/uses").json()

    assert [(t["disposition"], t["held"]) for t in uses["tasks"]] == [
        ("incomplete", "too long for the prompt")
    ]
    assert uses["builds"] == []


def test_a_record_the_reader_cant_read_has_no_uses_to_show(world):
    """Bug caught: the uses route answering for another person's private note, revealing that
    it exists and where it was used."""
    private = world.client.post(URL, json={"kind": "note", "scope": "user", "body": "mine"}).json()

    response = world.as_("bo", Role.ADMIN).client.get(f"{URL}/{private['record_id']}/uses")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("status", "listed"),
    [("active", ["kept"]), ("withdrawn", ["gone"]), ("all", ["kept", "gone"])],
)
def test_the_list_answers_by_status_and_a_retrieval_stays_active(world, status, listed):
    """The view's filter. Bug caught: a withdrawn record vanishing from the memory view (its
    history is kept, §3.8), or the default list, a retrieval, answering with one."""
    for body in ("kept", "gone"):
        world.client.post(URL, json={"kind": "note", "scope": "user", "body": body})
    gone = next(
        r["record_id"] for r in world.client.get(URL).json() if r["current"]["body"] == "gone"
    )
    world.client.post(f"{URL}/{gone}/withdrawal", json={"why": "wrong"})

    found = world.client.get(URL, params={"status": status}).json()

    assert [r["current"]["body"] for r in found] == listed
    assert [r["current"]["body"] for r in world.client.get(URL).json()] == ["kept"]
    assert world.client.get(URL, params={"status": "lost"}).status_code == 422


async def test_a_record_supplied_beside_an_incomplete_section_is_a_held_use_and_feeds_no_build(
    world,
):
    """The second read of PR #2524. Bug caught: a project instruction supplied in an exposure whose
    task instructions couldn't be fitted, read as a use that fed a build, though the bundle was
    incomplete and the task was held (§3.6)."""
    record_id = world.client.post(
        URL,
        json={"kind": "instruction", "scope": "project", "project_id": "group_run",
              "body": "x", "applicability": ANYWHERE},
    ).json()["record_id"]  # fmt: skip
    await _built_cycle(world.cycles)
    exposure = replace(
        _exposure("run_i", "t_dev"),
        project_instructions={"disposition": "supplied", "supplied": [{"record_id": record_id, "revision": "1"}]},
        task_instructions={"disposition": "incomplete", "supplied": [], "unresolved": [{"record_id": "mrec_other", "revision": "1", "why": "too long"}]},
    )  # fmt: skip
    await world.store.record_exposure(exposure)

    uses = world.client.get(f"{URL}/{record_id}/uses").json()

    assert [(t["disposition"], t["held"]) for t in uses["tasks"]] == [
        ("supplied", "the task was held: its task instructions were incomplete")
    ]
    assert uses["builds"] == []


def test_a_private_record_naming_a_project_is_listed_once(world):
    """The second read of PR #2524 (it predates the view). Bug caught: a user-scope record created
    with a project id listed twice in a project-bound list, once as its owner's and once as the
    project's, out of oldest-first order."""
    world.client.post(
        URL, json={"kind": "note", "scope": "user", "body": "first", "project_id": "group_run"}
    )
    world.client.post(
        URL, json={"kind": "note", "scope": "project", "body": "second", "project_id": "group_run"}
    )

    listed = world.client.get(URL, params={"project_id": "group_run"}).json()

    assert [r["current"]["body"] for r in listed] == ["first", "second"]
