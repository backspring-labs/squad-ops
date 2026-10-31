"""Chat on the memory substrate, entered where the console enters it (SIP-0110 Appendix A §3.3–§3.6, §A.8
Q29; #2180 stage A): ``POST /api/v1/chat/{agent_id}`` and the session routes, with the records' routes
beside them. The A2A client records what each turn's agent receives, so the assertions are on the context
the agent was handed, not on the assembler's inputs."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.chat.routes import router as chat_router
from squadops.api.routes.memory import memory_records_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.comms.chat_history import MEMORY_CONTEXT_KEY
from squadops.comms.models import SessionNotFoundError
from squadops.config.schema import ChatConfig
from squadops.cycles.models import ProjectNotFoundError
from squadops.memory.context import Disposition, SectionKind

pytestmark = [pytest.mark.domain_memory, pytest.mark.auth]

_AGENT = {"a2a_messaging_enabled": True, "a2a_port": 8080, "a2a_host": "localhost"}
AGENTS = {
    "comms-agent": {"id": "comms-agent", "display_name": "Joi", "description": "", **_AGENT},
    "lead-agent": {"id": "lead-agent", "display_name": "Max", "description": "", **_AGENT},
}


class _Chats:
    """The chat repository's contract, in memory: a deleted session keeps its row, marked."""

    def __init__(self) -> None:
        self.sessions: dict = {}
        self.messages: list = []

    async def create_session(self, session):
        self.sessions[session.session_id] = session
        return session

    async def get_session(self, session_id):
        if session_id not in self.sessions:
            raise SessionNotFoundError(session_id)
        return self.sessions[session_id]

    async def list_sessions(self, agent_id, user_id, limit=50):
        return [
            s
            for s in self.sessions.values()
            if (s.agent_id, s.user_id) == (agent_id, user_id) and s.deleted_at is None
        ]

    async def delete_session(self, session_id, deleted_at):
        session = self.sessions.get(session_id)
        if session is None or session.deleted_at is not None:
            raise SessionNotFoundError(session_id)
        self.sessions[session_id] = replace(session, deleted_at=deleted_at)
        self.messages = [m for m in self.messages if m.session_id != session_id]

    async def store_message(self, message):
        session = self.sessions.get(message.session_id)
        if session is None or session.deleted_at is not None:
            raise SessionNotFoundError(message.session_id)
        self.messages.append(message)
        return message

    async def get_session_messages(self, session_id, limit=100):
        return [m for m in self.messages if m.session_id == session_id]

    async def get_message(self, message_id):
        return next((m for m in self.messages if m.message_id == message_id), None)


class _Agent:
    """An A2A client that keeps each turn's metadata and answers with ``reply``."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        self.reply = "Noted."

    async def send_message_stream(self, base_url, message, **kwargs):
        self.received.append(kwargs.get("metadata") or {})
        yield self.reply


class _Projects:
    async def get_project(self, project_id):
        if project_id not in ("group_run", "play_game"):
            raise ProjectNotFoundError(project_id)
        return SimpleNamespace(project_id=project_id)


def _identity(user: str, role: str) -> Identity:
    return Identity(
        user_id=user, display_name=user, roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))), identity_type=IdentityType.HUMAN,
    )  # fmt: skip


@pytest.fixture
def world():
    class World:
        def __init__(self) -> None:
            self.identity = _identity("ada", Role.ADMIN)
            app = FastAPI()
            outer = self

            class InjectIdentity(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):
                    request.state.identity = outer.identity
                    return await call_next(request)

            app.add_middleware(InjectIdentity)
            app.include_router(chat_router)
            app.include_router(memory_records_router)
            register_domain_error_handlers(app)
            app.state.config = SimpleNamespace(comms=SimpleNamespace(chat=ChatConfig()))
            self.chats, self.agent = _Chats(), _Agent()
            self.records, self.store = InMemoryMemoryRecords(), InMemoryCrossCycleMemoryStore()
            app.state.chat_repo, app.state.a2a_client, app.state.chat_cache = (
                self.chats, self.agent, None,
            )  # fmt: skip
            app.state.all_agents = app.state.messaging_agents = AGENTS
            app.state.memory_records, app.state.memory_store = self.records, self.store
            app.state.project_registry = _Projects()
            app.state.authz_port = KeycloakAuthzAdapter()
            self.client = TestClient(app)

        def as_(self, user: str, role: str):
            self.identity = _identity(user, role)
            return self

        def say(self, message, *, agent="comms-agent", **body):
            response = self.client.post(f"/api/v1/chat/{agent}", json={"message": message, **body})
            events = [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            return response, events

        def handed(self, n=-1) -> dict:
            return self.agent.received[n].get(MEMORY_CONTEXT_KEY) or {}

        def note(self, body, **fields):
            response = self.client.post(
                "/api/v1/memory-records", json={"kind": "note", "body": body, **fields}
            )
            assert response.status_code == 201, response.text
            return response.json()

    return World()


def _texts(handed: dict, kind: str = "notes") -> list[str]:
    return [
        e["text"] for s in handed.get("sections", ()) if s["kind"] == kind for e in s["entries"]
    ]


def test_each_turn_carries_the_context_its_sessions_stored_binding_admits(world):
    """The wiring test (T4, T14): entered at ``POST /api/v1/chat/{agent_id}``, asserted on what the
    agent received. Bug caught: another project's or person's notes reaching a turn, a client's
    claimed project replacing the stored binding, or an unbound session seeing a project's notes."""
    world.note("ada's own note", scope="user")
    world.note("group_run's note", scope="project", project_id="group_run")
    world.note("play_game's note", scope="project", project_id="play_game")
    world.as_("bo", Role.VIEWER).note("bo's own note", scope="user")
    world.as_("ada", Role.ADMIN)

    opened, _ = world.say("what about the note?", project_id="group_run")
    bound = world.handed()
    session_id = opened.headers["X-Session-Id"]
    world.say("and now?", session_id=session_id, project_id="play_game")
    claimed = world.handed()
    world.say("unbound, what do I have?")
    unbound = world.handed()

    assert sorted(_texts(bound)) == ["ada's own note", "group_run's note"]
    assert (claimed["project_id"], sorted(_texts(claimed))) == (
        "group_run", ["ada's own note", "group_run's note"],
    )  # fmt: skip
    assert (unbound["project_id"], _texts(unbound)) == (None, ["ada's own note"])


def test_one_project_note_reaches_two_agents_chats_as_one_revision_and_no_task(world):
    """T2's chat half. Bug caught: a note copied per session or per agent (two rows, two ids), or a
    project note reaching a task's prompt."""
    note = world.note("join returns 409 when full", scope="project", project_id="group_run")

    world.say("the join?", project_id="group_run")
    world.say("the join?", agent="lead-agent", project_id="group_run")

    supplied = [
        [(e["record_id"], e["revision"]) for s in world.handed(n)["sections"] for e in s["entries"]]
        for n in (0, 1)
    ]
    assert supplied == [[(note["record_id"], 1)]] * 2
    assert len(world.chats.sessions) == 2
    assert [r.record_id for r in world.records._records.values()] == [note["record_id"]]
    exposures = [e for s in world.chats.sessions for e in _run(world.store.list_chat_exposures(s))]
    assert {next(x for x in e.sections if x.kind is SectionKind.NOTES).supplied[0].record_id
            for e in exposures} == {note["record_id"]}  # fmt: skip
    assert not _task_receives(world.records, "join returns 409 when full")
    # §A.3.11: each reply names the records its context supplied
    replies = [m.content for m in world.chats.messages if m.role == "assistant"]
    assert replies == [f"Noted.\n\n_Memory used: {note['record_id']}@1._"] * 2


@pytest.mark.parametrize(
    ("role", "project_id", "status"),
    [(Role.ADMIN, "no_such_project", 422), (Role.AGENT, "group_run", 403)],
    ids=["a-project-that-doesnt-exist", "a-person-who-cant-read-it"],
)
def test_opening_a_session_bound_to_a_project_is_checked_server_side(
    world, role, project_id, status
):
    """T14's binding part. Bug caught: a session bound to a project that doesn't exist, or by
    someone who can't read it, then seeing its records on every turn."""
    response, _ = world.as_("ada", role).say("hello", project_id=project_id)

    assert response.status_code == status
    assert world.chats.sessions == {}


def test_nothing_is_stored_until_confirmed_and_only_an_offered_choice_is(world):
    """§3.5, §3.3. Bug caught: a proposal stored as a record before anyone confirms it, the capture
    block left in the stored reply, a crafted request for a scope the card didn't offer accepted,
    or the reply not saying what was saved and when it takes effect."""
    world.agent.reply = 'Will do.\n<memory-capture>{"text": "QA mocks the clock", "kind": "note", "scope": "project"}</memory-capture>'  # fmt: skip
    world.as_("bo", Role.VIEWER)
    opened, events = world.say("remember: QA mocks the clock", project_id="group_run")
    session_id = opened.headers["X-Session-Id"]
    [capture] = [e["capture"] for e in events if "capture" in e]
    stored_reply = world.chats.messages[-1]

    crafted = world.client.post(
        f"/api/v1/chat/sessions/{session_id}/captures",
        json={"message_id": capture["source_message_id"], "text": capture["text"], "kind": "note", "scope": "project"},
    )  # fmt: skip
    nothing_yet = world.client.get("/api/v1/memory-records").json()
    confirmed = world.client.post(
        f"/api/v1/chat/sessions/{session_id}/captures",
        json={"message_id": capture["source_message_id"], "text": capture["text"], "kind": "note", "scope": "user"},
    )  # fmt: skip

    assert {(c["kind"], c["scope"]) for c in capture["choices"]} == {
        ("note", "user"), ("preference", "user"),
    }  # fmt: skip
    assert (stored_reply.content, nothing_yet) == ("Will do.", [])
    assert crafted.status_code == 403
    assert confirmed.status_code == 201, confirmed.text
    body = confirmed.json()
    record = world.client.get(f"/api/v1/memory-records/{body['record_id']}").json()
    assert (record["scope"], record["current"]["source"]["ids"]) == (
        "user", {"session_id": session_id, "message_id": capture["source_message_id"]},
    )  # fmt: skip
    assert body["reply"]["content"] == (
        f"Saved note {body['record_id']} (yours only). It takes effect in your chats from your "
        "next turn; no task receives it."
    )


def test_a_save_that_fails_is_said_in_the_reply_answered_as_an_error_and_logged(world, caplog):
    """T8's chat part, the save. Bug caught: a failed save swallowed, so the person believes it
    was kept."""
    world.as_("ada", Role.ADMIN)
    opened, _ = world.say("keep this")
    session_id = opened.headers["X-Session-Id"]
    turn = world.chats.messages[0]

    async def down(record):
        raise ConnectionError("password authentication failed for svc (hunter2)")

    world.records.create = down
    with caplog.at_level(logging.WARNING):
        failed = world.client.post(
            f"/api/v1/chat/sessions/{session_id}/captures",
            json={"message_id": turn.message_id, "text": "keep this", "kind": "note", "scope": "user"},
        )  # fmt: skip

    assert failed.status_code == 503
    assert failed.json()["detail"]["error"]["code"] == "MEMORY_SAVE_FAILED"
    assert world.chats.messages[-1].content.startswith("Not saved: the note could not be stored")
    assert "chat_capture_failed" in caplog.text
    # #1976 (the second read of PR #2517): the answer and the transcript never carry the error's text
    assert "hunter2" not in failed.text and "hunter2" not in world.chats.messages[-1].content


def test_a_retrieval_that_fails_is_failed_in_the_exposure_and_said_in_the_reply(world, caplog):
    """T8's chat part, the read. Bug caught: a store failure answered as "no notes", with nothing
    in the reply or the exposure to say it wasn't so."""

    async def down(**kwargs):
        raise ConnectionError("search down")

    world.records.search_notes = down
    with caplog.at_level(logging.WARNING):
        opened, events = world.say("what do I know?")
    session_id = opened.headers["X-Session-Id"]
    [exposure] = _run(world.store.list_chat_exposures(session_id))

    assert events[0]["text"].startswith("_Memory: your notes could not be read for this reply")
    assert world.chats.messages[-1].content.startswith("_Memory: your notes could not be read")
    assert next(s for s in exposure.sections if s.kind is SectionKind.NOTES).disposition is (
        Disposition.FAILED
    )
    assert "chat_context_unavailable" in caplog.text


def test_a_chat_records_link_opens_its_one_turn_for_its_owner_only(world):
    """T15. Bug caught: another reader shown the private session's ids or allowed to follow the
    link, or the owner's link opening more than the one turn."""
    world.as_("ada", Role.ADMIN)
    opened, _ = world.say("first turn, private", project_id="group_run")
    session_id = opened.headers["X-Session-Id"]
    world.say("the turn to keep", session_id=session_id)
    turn = world.chats.messages[2]
    saved = world.client.post(
        f"/api/v1/chat/sessions/{session_id}/captures",
        json={"message_id": turn.message_id, "text": "kept", "kind": "note", "scope": "project"},
    ).json()  # fmt: skip
    link = f"/api/v1/memory-records/{saved['record_id']}/revisions/1/source"

    owner = world.client.get(link)
    world.as_("bo", Role.VIEWER)
    seen_by_another = world.client.get(f"/api/v1/memory-records/{saved['record_id']}").json()
    followed_by_another = world.client.get(link)

    assert (owner.status_code, owner.json()["content"]) == (200, "the turn to keep")
    assert set(owner.json()) == {"session_id", "message_id", "role", "content", "created_at"}
    assert "ids" not in seen_by_another["current"]["source"]
    assert seen_by_another["current"]["source"]["summary"].startswith(
        "converted from a private chat turn by ada"
    )
    assert followed_by_another.status_code == 403


def test_a_deleted_session_is_gone_for_good_and_its_record_says_where_it_came_from(world):
    """Q29. Bug caught: a deleted session still resumable or readable, another person able to
    delete it, or a record confirmed from it losing its mark or its link pointing at nothing."""
    world.as_("ada", Role.ADMIN)
    opened, _ = world.say("keep this")
    session_id = opened.headers["X-Session-Id"]
    turn = world.chats.messages[0]
    saved = world.client.post(
        f"/api/v1/chat/sessions/{session_id}/captures",
        json={"message_id": turn.message_id, "text": "kept", "kind": "note", "scope": "user"},
    ).json()  # fmt: skip

    by_another = world.as_("bo", Role.VIEWER).client.delete(f"/api/v1/chat/sessions/{session_id}")
    deleted = world.as_("ada", Role.ADMIN).client.delete(f"/api/v1/chat/sessions/{session_id}")
    resumed, _ = world.say("again", session_id=session_id)
    record = world.client.get(f"/api/v1/memory-records/{saved['record_id']}").json()
    link = world.client.get(f"/api/v1/memory-records/{saved['record_id']}/revisions/1/source")

    assert (by_another.status_code, deleted.status_code, deleted.content) == (404, 204, b"")
    assert world.client.get(f"/api/v1/chat/sessions/{session_id}/messages").status_code == 404
    assert resumed.status_code == 404
    assert _run(world.chats.get_session_messages(session_id)) == []
    assert record["current"]["source"]["session_deleted"] is True
    assert link.status_code == 404


def test_a_chat_source_claimed_through_the_records_api_is_refused(world):
    """§3.4. Bug caught: anyone writing a record whose source claims a chat turn, which the link
    would then vouch for."""
    response = world.client.post(
        "/api/v1/memory-records",
        json={"kind": "note", "scope": "user", "body": "x",
              "source": {"kind": "chat_message", "ids": {"session_id": "s", "message_id": "m"}}},
    )  # fmt: skip

    assert response.status_code == 422
    assert "captured in chat" in response.json()["detail"]["error"]["message"]


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _task_receives(records, text: str) -> bool:
    """Whether any authoring task of a ``group_run`` cycle is handed ``text``: the composer reads
    task instructions and lessons, and a note is neither (§3.6: a note never reaches a task)."""
    from adapters.memory.recall import SnapshotRecall
    from squadops.capabilities.lesson_supply import supply_lessons, unit_of
    from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

    cycle = _framing_cycle()
    envelopes = _run(
        supply_lessons(
            _plan(cycle),
            recall=SnapshotRecall(InMemoryCrossCycleMemoryStore(), records=records),
            unit=unit_of(cycle),
            stack="fullstack_fastapi_react",
            run_id="run_note0001",
            now=datetime(2026, 10, 19, tzinfo=UTC),
        )
    )
    return any(text in json.dumps(e.inputs, default=str) for e in envelopes)


@pytest.mark.parametrize(
    ("role", "bound", "kind", "scope"),
    [
        (Role.VIEWER, True, "note", "project"),
        (Role.ADMIN, False, "note", "project"),
        (Role.VIEWER, True, "instruction", "task"),
        (Role.VIEWER, True, "instruction", "project"),
        (Role.ADMIN, True, "preference", "project"),
    ],
    ids=[
        "no-memory-note",
        "no-binding",
        "no-cycle-authority",
        "no-memory-instruct",
        "no-such-scope-for-the-kind",
    ],
)
def test_a_capture_the_card_didnt_offer_is_refused_whoever_asks(world, role, bound, kind, scope):
    """§3.3: the card's choices are the rule, not a hint. Bug caught: an admin's crafted request
    storing a project note from an unbound session, or a project instruction captured from chat
    before stage B makes it reach its tasks."""
    opened, _ = world.as_("ada", role).say(
        "keep it", **({"project_id": "group_run"} if bound else {})
    )
    turn = world.chats.messages[0]

    response = world.client.post(
        f"/api/v1/chat/sessions/{opened.headers['X-Session-Id']}/captures",
        json={"message_id": turn.message_id, "text": "kept", "kind": kind, "scope": scope},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["message"].startswith(
        f"this session offers you no {scope} {kind}"
    )
    assert world.records._records == {}


def test_a_record_the_rules_cant_read_fails_the_context_and_the_turn_still_answers(world, caplog):
    """The second read of PR #2517. Bug caught: one malformed stored record turning every turn of
    its owner into a 500 after their message was already stored."""
    from squadops.memory.records import MemoryRecord

    world.records._records["mrec_bad"] = MemoryRecord(
        "mrec_bad", "preference", "user", None, "ada", ()
    )

    with caplog.at_level(logging.WARNING):
        opened, events = world.say("hello")

    assert opened.status_code == 200
    assert events[0]["text"].startswith("_Memory: your project instructions, task instructions,")
    assert "chat_context_unassembled" in caplog.text


def test_a_bound_turn_asking_about_lessons_is_shown_the_approved_ones_with_their_evidence(world):
    """#2181 through the route. Bug caught: the lessons API's records not reaching a turn that asks,
    or reaching one that's unbound, or the count of dispatches supplied a lesson wrong."""
    from tests.unit.memory.test_lessons import _approve, _revision

    revision = _revision("criterion_already_satisfied")
    _run(world.store.record_revision(revision))
    _run(world.store.record_approval(_approve(revision, ruling="approved 10-19")))

    world.say("what lessons does this project have?", project_id="group_run")
    bound = world.handed()
    world.say("what lessons do I have?")
    unbound = world.handed()

    [inspected] = [s for s in bound["sections"] if s["kind"] == "inspected_lessons"]
    assert [(e["revision_id"], e["supplied_in"]) for e in inspected["entries"]] == [
        (revision.revision_id, 0)
    ]
    assert all(s["kind"] != "inspected_lessons" for s in unbound["sections"])
    bound_reply = next(m for m in world.chats.messages if m.role == "assistant")
    assert bound_reply.content.endswith(f"_Memory used: {revision.revision_id}._")


def test_a_conversational_claim_is_a_suggestion_note_that_can_never_become_a_lesson(world):
    """T5. Bug caught: a claim said in chat stored as anything but a suggestion note, cited by a
    lesson's draft, carried in a unit's snapshot, or reaching an approval through a chat route."""
    from squadops.memory.approval import LessonRefused, draft_revision
    from squadops.memory.lessons import UnitKind
    from squadops.memory.pinning import pin_unit
    from tests.unit.memory.test_lessons import WHERE

    world.agent.reply = 'Noted.\n<memory-capture>{"text": "QA should always mock the clock.", "kind": "note", "suggestion": true}</memory-capture>'  # fmt: skip
    opened, events = world.say("QA should always mock the clock", project_id="group_run")
    [capture] = [e["capture"] for e in events if "capture" in e]
    saved = world.client.post(
        f"/api/v1/chat/sessions/{opened.headers['X-Session-Id']}/captures",
        json={"message_id": capture["source_message_id"], "text": capture["text"], "kind": "note",
              "scope": "project", "suggestion": capture["suggestion"]},
    ).json()  # fmt: skip
    record = world.client.get(f"/api/v1/memory-records/{saved['record_id']}").json()

    assert (capture["suggestion"], record["kind"], record["current"]["suggestion"]) == (
        True, "note", True,
    )  # fmt: skip
    with pytest.raises(LessonRefused, match=saved["record_id"]):
        draft_revision(
            target_behavior="clock", text="Mock the clock.", applicability=WHERE,
            template_id="lesson.x", template_version="1", drafter_model="m", drafter_version="1",
            cited_observations=[saved["record_id"]], citable_observations=[], revisions=[],
            now=datetime(2026, 10, 19, tzinfo=UTC),
        )  # fmt: skip
    snapshot = _run(
        pin_unit(world.store, unit_kind=UnitKind.CYCLE, unit_id="cyc_t5", project_id="group_run",
                 pinned_at=datetime(2026, 10, 19, tzinfo=UTC), disabled=False, records=world.records)
    )  # fmt: skip
    assert saved["record_id"] not in json.dumps(snapshot.to_dict())


def test_no_chat_route_drafts_approves_or_revokes_a_lesson():
    """§3.5: chat inspects lessons and never changes them. Bug caught: a chat route added that
    reaches the lessons' draft, approval, revocation or annotation review."""
    from squadops.api.routes.chat.routes import agents_router

    paths = {
        (method, route.path)
        for r in (chat_router, agents_router)
        for route in r.routes
        for method in route.methods
    }

    assert not [
        p for p in paths
        if any(word in p[1] for word in ("lesson", "approval", "revocation", "annotation", "draft"))
    ]  # fmt: skip
    assert {p for p in paths if p[0] != "GET"} == {
        ("POST", "/api/v1/chat/{agent_id}"),
        ("POST", "/api/v1/chat/sessions/{session_id}/captures"),
        ("DELETE", "/api/v1/chat/sessions/{session_id}"),
    }


async def test_a_project_instruction_captured_in_chat_reaches_the_next_cycles_task_it_names(world):
    """T1 through chat (#2180 stage B). Bug caught: an instruction confirmed on a card stored without
    its applicability, unconfirmed, or never reaching the task it names in a unit admitted after it;
    or reaching every task."""
    from adapters.memory.recall import SnapshotRecall
    from squadops.capabilities.lesson_supply import supply_lessons, unit_of
    from squadops.memory.lessons import UnitKind
    from squadops.memory.pinning import pin_unit
    from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
    from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan

    world.agent.reply = 'Will do.\n<memory-capture>{"text": "Name each run by its route.", "kind": "instruction", "applicability": {"task_types": ["development.design_plan"]}}</memory-capture>'  # fmt: skip
    opened, events = world.say("from now on, name each run by its route", project_id="group_run")
    [capture] = [e["capture"] for e in events if "capture" in e]
    applicability = {**capture["applicability"], "roles": ["*"], "stacks": ["*"]}
    saved = world.client.post(
        f"/api/v1/chat/sessions/{opened.headers['X-Session-Id']}/captures",
        json={"message_id": capture["source_message_id"], "text": capture["text"],
              "kind": "instruction", "scope": "project", "applicability": applicability},
    )  # fmt: skip
    cycle = _framing_cycle()
    await pin_unit(
        world.store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
        pinned_at=datetime(2026, 10, 20, tzinfo=UTC), disabled=False, records=world.records,
    )  # fmt: skip
    supplied = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(world.store, records=world.records),
        unit=unit_of(cycle), stack="fullstack_fastapi_react", run_id="run_t1chat",
        now=datetime(2026, 10, 20, tzinfo=UTC),
    )  # fmt: skip

    assert saved.status_code == 201, saved.text
    assert saved.json()["takes_effect"].startswith("for group_run's cycles and campaigns admitted")
    record = world.client.get(f"/api/v1/memory-records/{saved.json()['record_id']}").json()
    assert (record["kind"], record["current"]["confirmed_by"]) == ("instruction", "ada")
    reached = {
        str(e.task_type)
        for e in supplied
        if PROJECT_INSTRUCTIONS_INPUT in e.inputs
        and "Name each run by its route." in str(e.inputs[PROJECT_INSTRUCTIONS_INPUT])
    }
    assert reached == {"development.design_plan"}


@pytest.mark.parametrize(
    ("kind", "scope", "applicability", "message"),
    [
        ("instruction", "project", None, "names its task_types, roles and stacks"),
        ("instruction", "project", {"task_types": ["*"], "roles": ["development"], "stacks": ["*"]}, "role 'development'"),
        ("note", "user", {"task_types": ["*"], "roles": ["*"], "stacks": ["*"]}, "a note has no applicability"),
        ("instruction", "project", {"task_types": ["*"], "roles": ["*"], "stacks": ["*"], "stack": ["python_cli"]}, None),
        ("instruction", "project", {"task_types": ["*"], "roles": ["*"], "stacks": []}, "names its stacks"),
    ],
    ids=["an-instruction-without-one", "a-role-no-dispatch-carries", "a-note-with-one",
         "a-key-the-records-api-refuses", "a-field-left-blank"],
)  # fmt: skip
def test_a_captured_instructions_applicability_is_required_and_checked(
    world, kind, scope, applicability, message
):
    """Bug caught: an instruction captured with no applicability (binding nothing, or everything), or
    one naming a role no squad has (the records API's check, skipped in chat)."""
    opened, _ = world.say("keep it", project_id="group_run")
    turn = world.chats.messages[0]

    response = world.client.post(
        f"/api/v1/chat/sessions/{opened.headers['X-Session-Id']}/captures",
        json={"message_id": turn.message_id, "text": "kept", "kind": kind, "scope": scope, "applicability": applicability},
    )  # fmt: skip

    assert response.status_code == 422
    if message is not None:  # a body the model refuses answers with its validation detail instead
        assert message in response.json()["detail"]["error"]["message"]
    assert world.records._records == {}
