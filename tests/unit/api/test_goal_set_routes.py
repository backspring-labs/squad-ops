"""``/api/v1/projects/{id}/goal-set`` (SIP-0115 §8.1; #2884, #2886), at the routes the CLI calls,
behind the runtime's own auth middleware and error handlers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.api.routes.cycles.goal_sets import router
from squadops.auth.models import ROLE_SCOPES, Identity, Role, TokenClaims
from squadops.cycles.models import (
    GateDecisionValue,
    GoalSetNotFoundError,
    Project,
    ProjectNotFoundError,
    StaleGoalSetRevisionError,
)
from squadops.projects.goal_set import Change, ChangeKind, GoalSetRevision, parse_goal_set
from tests.fixtures.goal_set import GoalSetStore, goal_set_document, proposed, started

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
PATH = "/api/v1/projects/prj-lantern/goal-set"


def _client(role: str, projects: AsyncMock, goal_sets, campaigns=None) -> TestClient:
    """The app as the runtime builds it for these routes: a token resolving to ``role``'s
    principal, its scopes the ones the realm's role grants. ``campaigns``: the registry slice 3's
    actions read the Campaign the crew acts within from."""
    identity = Identity(
        user_id=f"{role}-principal",
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(ROLE_SCOPES[role])),
    )
    now = datetime.now(tz=UTC)
    auth_port = AsyncMock()
    auth_port.validate_token = AsyncMock(
        return_value=TokenClaims(
            subject=identity.user_id,
            issuer="http://kc/realms/squadops",
            audience="squadops-runtime",
            expires_at=now + timedelta(hours=1),
            issued_at=now,
            roles=identity.roles,
            scopes=identity.scopes,
        )
    )
    auth_port.resolve_identity = AsyncMock(return_value=identity)
    app = FastAPI()
    app.add_middleware(AuthMiddleware, auth_port=auth_port, provider="keycloak", expose_docs=False)
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    register_domain_error_handlers(app)
    app.state.project_registry = projects
    app.state.goal_set_registry = goal_sets
    app.state.campaign_registry = campaigns if campaigns is not None else MemoryCampaignRegistry()
    return TestClient(app, headers={"Authorization": "Bearer t"})


@pytest.fixture
def projects():
    registry = AsyncMock()
    registry.get_project.return_value = Project(
        project_id="prj-lantern", name="Lantern", description="", created_at=NOW
    )
    return registry


@pytest.fixture
def goal_sets():
    store = AsyncMock()

    async def record(revision, **kwargs):
        return revision, False

    store.record_revision.side_effect = record
    return store


@pytest.fixture
def authz():
    with patch("squadops.api.middleware.auth.get_authz_port", return_value=KeycloakAuthzAdapter()):
        yield


def _body(**overrides) -> dict:
    return {
        "idempotency_key": "k-1",
        "expected_revision": 1,
        "reason": "the owner added the weekly total",
        "source_ref": "https://chat.example.invalid/thread/42",
        "goal_set": goal_set_document(),
    } | overrides


def _stored(revision: int) -> GoalSetRevision:
    return GoalSetRevision(
        project_id="prj-lantern",
        revision=revision,
        goal_set=parse_goal_set(goal_set_document()),
        author="owner",
        reason=f"revision {revision}",
        created_at=NOW,
    )


@pytest.mark.usefixtures("authz")
class TestWriting:
    def test_the_owners_write_reaches_the_store_as_the_next_revision_by_its_principal(
        self, projects, goal_sets
    ):
        """The wiring test (anti-pattern 6a): entered at the route the CLI posts to. Bugs
        caught: the author taken from the body or left anonymous rather than the authenticated
        principal; the revision not the expected one's successor; the reason or source_ref
        dropped between the body and the store; the create answered 200."""
        resp = _client(Role.ADMIN, projects, goal_sets).post(f"{PATH}/revisions", json=_body())

        assert resp.status_code == 201, resp.text
        written = goal_sets.record_revision.await_args.args[0]
        assert (
            written.project_id,
            written.revision,
            written.author,
            written.reason,
            written.source_ref,
        ) == (
            "prj-lantern",
            2,
            "admin-principal",
            "the owner added the weekly total",
            "https://chat.example.invalid/thread/42",
        )
        assert written.goal_set == parse_goal_set(goal_set_document())
        assert goal_sets.record_revision.await_args.kwargs["idempotency_key"] == "k-1"
        body = resp.json()
        assert (body["revision"]["revision"], body["replayed"]) == (2, False)
        assert body["revision"]["goal_set"]["backlog"][0]["id"] == "B-1"

    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (Role.ADMIN, 201),
            (Role.OPERATOR, 403),
            (Role.VIEWER, 403),
            # §6: the crew never writes the goal or expected results; a delegated reorder is
            # slice 3's, under Q41
            (Role.CAMPAIGN_SUPERVISOR, 403),
            (Role.CAMPAIGN_TRIAGE, 403),
        ],
    )
    def test_only_the_owners_scope_writes(self, role, expected, projects, goal_sets):
        """Bug caught: the write left on a read, cycle-write or campaign scope, so an operator
        or the crew's principal rewrites the owner's goal. The crew's 403 here is Q41's "reorder,
        no": slice 3 delegates a promotion, a drop and a split through their own routes, never
        the whole-document write, which is the only way to reorder."""
        resp = _client(role, projects, goal_sets).post(f"{PATH}/revisions", json=_body())

        assert resp.status_code == expected
        assert goal_sets.record_revision.await_count == (1 if expected == 201 else 0)

    def test_an_invalid_goal_set_is_refused_naming_its_field_and_nothing_is_written(
        self, projects, goal_sets
    ):
        """Bug caught: a malformed goal set answered 500, or written."""
        doc = goal_set_document()
        doc["backlog"][1]["serves"] = ["ER-gone"]

        resp = _client(Role.ADMIN, projects, goal_sets).post(
            f"{PATH}/revisions", json=_body(goal_set=doc)
        )

        error = resp.json()["detail"]["error"]
        assert (resp.status_code, error["code"], error["details"]) == (
            422,
            "GOAL_SET_INVALID",
            {"field": "backlog[1].serves"},
        )
        goal_sets.record_revision.assert_not_awaited()

    def test_a_stale_expected_revision_is_a_conflict(self, projects, goal_sets):
        """Bug caught: a concurrent edit answered as a server error, or overwriting silently."""
        goal_sets.record_revision.side_effect = StaleGoalSetRevisionError(
            "Project prj-lantern's goal set is at revision 3"
        )

        resp = _client(Role.ADMIN, projects, goal_sets).post(f"{PATH}/revisions", json=_body())

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            409,
            "STALE_GOAL_SET_REVISION",
        )

    def test_an_unknown_project_is_not_found_and_nothing_is_written(self, projects, goal_sets):
        projects.get_project.side_effect = ProjectNotFoundError("Project not found: prj-lantern")

        resp = _client(Role.ADMIN, projects, goal_sets).post(f"{PATH}/revisions", json=_body())

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            404,
            "PROJECT_NOT_FOUND",
        )
        goal_sets.record_revision.assert_not_awaited()


@pytest.mark.usefixtures("authz")
class TestReading:
    def test_the_active_goal_set_and_one_revision_read_through_the_store(self, projects, goal_sets):
        """Bug caught: the active read asking the store for a pinned revision, or ``/revisions/1``
        reading the latest."""
        goal_sets.get_revision.side_effect = lambda project_id, revision=None: _stored(
            revision or 3
        )
        client = _client(Role.VIEWER, projects, goal_sets)

        active = client.get(PATH)
        first = client.get(f"{PATH}/revisions/1")

        assert (active.status_code, active.json()["revision"]) == (200, 3)
        assert (first.status_code, first.json()["revision"]) == (200, 1)
        assert first.json()["goal_set"] == parse_goal_set(goal_set_document()).to_document()

    def test_the_crews_principals_read_the_goal_set(self, projects, goal_sets):
        """Bug caught: the read put behind a scope the crew lacks, which slice 5 depends on."""
        goal_sets.list_revisions.return_value = [_stored(2), _stored(1)]

        resp = _client(Role.CAMPAIGN_TRIAGE, projects, goal_sets).get(f"{PATH}/revisions")

        assert [r["revision"] for r in resp.json()] == [2, 1]

    def test_no_goal_set_yet_is_not_found(self, projects, goal_sets):
        goal_sets.get_revision.side_effect = GoalSetNotFoundError("prj-lantern has no goal set")

        resp = _client(Role.VIEWER, projects, goal_sets).get(PATH)

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            404,
            "GOAL_SET_NOT_FOUND",
        )

    @pytest.mark.parametrize("suffix", ["", "/revisions", "/revisions/1"])
    def test_an_unknown_projects_goal_set_is_the_project_not_found(
        self, suffix, projects, goal_sets
    ):
        """Bug caught: an unknown Project read as one with no goal set (an empty history, or
        GOAL_SET_NOT_FOUND), so a typo'd id looks like a Project waiting for its goals."""
        projects.get_project.side_effect = ProjectNotFoundError("Project not found: prj-lantrn")

        resp = _client(Role.VIEWER, projects, goal_sets).get(
            f"/api/v1/projects/prj-lantrn/goal-set{suffix}"
        )

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            404,
            "PROJECT_NOT_FOUND",
        )


# --- slice 3 (#2886): candidates and splits, behind the runtime's auth (§6, Q41) ---

DELEGATED = ("promote", "drop", "split")


def _action(action: str, **overrides) -> tuple[str, dict]:
    """Each action's path and body, as the CLI posts it, against revision 1."""
    body: dict = {
        "idempotency_key": "k-3",
        "expected_revision": 1,
        "reason": "the crew found it blocks the weekly total",
        "source_ref": "https://chat.example.invalid/thread/7",
    }
    if action == "add":
        path = f"{PATH}/candidates"
        body["candidate"] = {"id": "C-2", "title": "Delete a session", "found_by": "crew"}
    elif action == "promote":
        path = f"{PATH}/candidates/C-1/promote"
        body["serves"] = ["ER-week"]
    elif action == "drop":
        path = f"{PATH}/candidates/C-1/drop"
    else:
        path = f"{PATH}/backlog/B-1/split"
        body["into"] = [{"id": "B-1a", "title": "the book"}, {"id": "B-1b", "title": "the minutes"}]
    return path, body | overrides


@pytest.fixture
def store() -> GoalSetStore:
    """The goal set at revision 1, in a store that keeps the port's rules."""
    held = GoalSetStore()
    held.write("prj-lantern", goal_set_document())
    return held


@pytest.fixture
def campaigns() -> MemoryCampaignRegistry:
    """Two Campaigns on Lantern's goal set: one the owner started, one the crew's own."""
    registry = MemoryCampaignRegistry()
    asyncio.run(started(registry, "cmp_owner", created_by="owner"))
    asyncio.run(started(registry, "cmp_crew", created_by="campaign-supervisor-principal"))
    return registry


def _error(resp) -> tuple[int, str | None]:
    detail = resp.json().get("detail") if resp.status_code >= 400 else None
    return resp.status_code, detail["error"]["code"] if detail else None


@pytest.mark.usefixtures("authz")
class TestWhoMayAct:
    @pytest.mark.parametrize("action", DELEGATED)
    @pytest.mark.parametrize(
        ("role", "campaign", "expected"),
        [
            (Role.ADMIN, None, (201, None)),
            (Role.ADMIN, "cmp_owner", (201, None)),
            (Role.CAMPAIGN_SUPERVISOR, "cmp_owner", (201, None)),
            (Role.CAMPAIGN_SUPERVISOR, None, (403, "NOT_DELEGATED")),
            (Role.CAMPAIGN_SUPERVISOR, "cmp_crew", (403, "NOT_DELEGATED")),
            (Role.CAMPAIGN_SUPERVISOR, "cmp_none", (404, "CAMPAIGN_NOT_FOUND")),
            (Role.CAMPAIGN_TRIAGE, "cmp_owner", (403, "FORBIDDEN")),
            (Role.VIEWER, "cmp_owner", (403, "FORBIDDEN")),
            (Role.OPERATOR, None, (403, "FORBIDDEN")),
        ],
        ids=[
            "the owner",
            "the owner naming a Campaign",
            "the crew within the owner's Campaign",
            "the crew outside any Campaign",
            "the crew within its own Campaign",
            "the crew naming no Campaign that exists",
            "triage",
            "a viewer",
            "an operator",
        ],
    )
    def test_who_may_promote_drop_or_split(
        self, action, role, campaign, expected, projects, store, campaigns
    ):
        """§6 and Q41 at each delegated route. Bugs caught: the crew acting with no Campaign, or
        within one it started itself; triage (reads only, #1719), a viewer or an operator acting;
        the owner asked for a Campaign; a refusal after the revision was written."""
        path, body = _action(action, **({"campaign_id": campaign} if campaign else {}))

        resp = _client(role, projects, store, campaigns).post(path, json=body)

        assert _error(resp) == expected, resp.text
        assert len(store.revisions["prj-lantern"]) == (2 if expected[0] == 201 else 1)

    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (Role.ADMIN, 201),
            (Role.CAMPAIGN_SUPERVISOR, 201),
            (Role.CAMPAIGN_TRIAGE, 403),
            (Role.VIEWER, 403),
            (Role.OPERATOR, 403),
            (Role.AGENT, 403),
        ],
    )
    def test_who_may_add_a_candidate(self, role, expected, projects, store):
        """§6: the owner and the crew add what they find, with no Campaign named. Bugs caught: the
        crew asked for a delegation to add; a reader adding; the squad's agent principal (which
        holds no read scope here, §10c) adding."""
        path, body = _action("add")

        resp = _client(role, projects, store).post(path, json=body)

        assert resp.status_code == expected, resp.text
        if expected == 201:
            written = store.revisions["prj-lantern"][-1]
            assert (written.author, written.change) == (
                f"{role}-principal",
                Change(ChangeKind.CANDIDATE_ADDED, "C-2"),
            )
            assert [c.id for c in written.goal_set.candidates] == ["C-1", "C-2"]
            assert written.goal_set.candidates[-1].found_at is not None


@pytest.mark.usefixtures("authz")
class TestPromotionAndSplit:
    def test_the_crews_promotion_within_the_owners_campaign_reaches_the_store_as_the_next_revision(
        self, projects, store, campaigns
    ):
        """The wiring test (anti-pattern 6a): entered at the route the CLI posts to, as the
        crew's principal. Bugs caught: the author taken as the owner; the Campaign the crew acted
        within not recorded; the candidate's id re-minted or its item put anywhere but the end;
        the reason or source_ref dropped; the action unnamed on the revision; a retry under the
        key written again."""
        path, body = _action("promote", campaign_id="cmp_owner")
        client = _client(Role.CAMPAIGN_SUPERVISOR, projects, store, campaigns)

        resp = client.post(path, json=body)
        again = client.post(path, json=body)

        assert resp.status_code == 201, resp.text
        written = store.revisions["prj-lantern"][-1]
        assert (written.revision, written.author, written.reason, written.source_ref) == (
            2,
            "campaign-supervisor-principal",
            "the crew found it blocks the weekly total",
            "https://chat.example.invalid/thread/7",
        )
        assert written.change == Change(
            ChangeKind.CANDIDATE_PROMOTED, "C-1", position=3, campaign_id="cmp_owner"
        )
        assert [i.id for i in written.goal_set.backlog] == ["B-1", "B-2", "C-1"]
        assert written.goal_set.backlog[-1].serves == ("ER-week",)
        assert written.goal_set.candidates == ()
        answered = resp.json()
        assert (answered["revision"]["revision"], answered["replayed"]) == (2, False)
        assert answered["revision"]["change"] == {
            "kind": "candidate_promoted",
            "subject": "C-1",
            "position": 3,
            "campaign_id": "cmp_owner",
        }
        assert (again.status_code, again.json()["replayed"]) == (201, True)
        assert len(store.revisions["prj-lantern"]) == 2

    def test_the_crew_appends_and_the_owner_places(self, projects, store, campaigns):
        """Q41: "a promoted candidate is appended at the end of the backlog; putting it anywhere
        else is a reorder." Bug caught: the crew's position honoured, so the crew steers the
        order through promotions."""
        path, body = _action("promote", campaign_id="cmp_owner", position=1)

        crew = _client(Role.CAMPAIGN_SUPERVISOR, projects, store, campaigns).post(path, json=body)
        owner = _client(Role.ADMIN, projects, store, campaigns).post(path, json=body)

        assert _error(crew) == (403, "NOT_DELEGATED")
        assert "reorder" in crew.json()["detail"]["error"]["message"]
        assert owner.status_code == 201, owner.text
        assert [i["id"] for i in owner.json()["revision"]["goal_set"]["backlog"]] == [
            "C-1",
            "B-1",
            "B-2",
        ]

    def test_the_owners_split_reaches_the_store_naming_the_parts_in_the_parents_place(
        self, projects, store, campaigns
    ):
        """The wiring test for a split. Bugs caught: the parts appended rather than in the
        parent's place; a part's ``serves`` left empty rather than inherited; the split
        recorded as a plain removal (no ``split_into``), so the view can't name the parts."""
        path, body = _action("split")

        resp = _client(Role.ADMIN, projects, store, campaigns).post(path, json=body)

        assert resp.status_code == 201, resp.text
        written = store.revisions["prj-lantern"][-1]
        assert written.change == Change(ChangeKind.ITEM_SPLIT, "B-1", split_into=("B-1a", "B-1b"))
        assert [(i.id, i.serves) for i in written.goal_set.backlog] == [
            ("B-1a", ("ER-log",)),
            ("B-1b", ("ER-log",)),
            ("B-2", ("ER-week",)),
        ]
        assert resp.json()["revision"]["change"]["split_into"] == ["B-1a", "B-1b"]

    @pytest.mark.parametrize(
        ("ruled", "status"),
        [(None, "proposed"), (GateDecisionValue.APPROVED, "in_increment")],
        ids=["proposed", "in_increment"],
    )
    def test_a_split_waits_while_a_live_campaign_reads_the_item_proposed_or_building(
        self, ruled, status, projects, store, campaigns
    ):
        """§5.5a at the route. Bug caught: the split written while the item's increment builds,
        so the acceptance lands on an item that is gone; or answered 500."""
        asyncio.run(proposed(campaigns, "cmp_owner", "B-1", ruled=ruled))
        path, body = _action("split")

        resp = _client(Role.ADMIN, projects, store, campaigns).post(path, json=body)

        assert _error(resp) == (409, "BACKLOG_ITEM_IN_PROGRESS")
        assert f"B-1 is {status} in campaign cmp_owner" in resp.json()["detail"]["error"]["message"]
        assert len(store.revisions["prj-lantern"]) == 1

    @pytest.mark.parametrize(
        ("action", "overrides", "expected", "field"),
        [
            ("split", {"into": [{"id": "B-1a", "title": "t"}]}, (422, "GOAL_SET_INVALID"), "into"),
            (
                "split",
                {"into": [{"id": "B-1a", "title": "t"}, {"id": "B-2", "title": "t"}]},
                (422, "GOAL_SET_INVALID"),
                "into",
            ),
            (
                "split",
                {"into": [{"id": "B-1a", "title": "t"}, {"id": "B-1b", "title": "t", "serves": ["ER-x"]}]},
                (422, "GOAL_SET_INVALID"),
                "into[1].serves",
            ),
            ("promote", {"serves": ["ER-x"]}, (422, "GOAL_SET_INVALID"), "serves"),
            ("add", {"candidate": {"id": "C-2", "title": "t", "found_by": "c", "x": 1}}, (422, "GOAL_SET_INVALID"), "candidate"),
            ("drop", {"expected_revision": 0}, (404, "GOAL_SET_NOT_FOUND"), None),
            ("drop", {"expected_revision": 2}, (404, "GOAL_SET_NOT_FOUND"), None),
            ("drop", {"campaign_id": None, "stale": True}, (409, "STALE_GOAL_SET_REVISION"), None),
        ],
        ids=[
            "one part",
            "a part with another item's id",
            "a part serving an unknown result",
            "serving an unknown result",
            "an unknown candidate field",
            "no goal set yet",
            "a revision not written",
            "a revision another writer passed",
        ],
    )  # fmt: skip
    def test_an_action_is_refused_in_the_envelope_naming_its_field(
        self, action, overrides, expected, field, projects, store, campaigns
    ):
        """Bugs caught: a refusal answered 500 or written; the field unnamed, so a client can't
        say which part was wrong; an action against a stale or missing revision written over
        another writer's."""
        if overrides.pop("stale", False):
            store.write("prj-lantern", goal_set_document())
        before = len(store.revisions["prj-lantern"])
        path, body = _action(action, **overrides)

        resp = _client(Role.ADMIN, projects, store, campaigns).post(path, json=body)

        assert _error(resp) == expected, resp.text
        if field is not None:
            assert resp.json()["detail"]["error"]["details"] == {"field": field}
        assert len(store.revisions["prj-lantern"]) == before

    @pytest.mark.parametrize(
        ("path", "code"),
        [
            (f"{PATH}/candidates/C-9/promote", "CANDIDATE_NOT_FOUND"),
            (f"{PATH}/candidates/C-9/drop", "CANDIDATE_NOT_FOUND"),
            (f"{PATH}/backlog/B-9/split", "BACKLOG_ITEM_NOT_FOUND"),
        ],
    )
    def test_an_unknown_candidate_or_item_is_not_found(self, path, code, projects, store, campaigns):
        action = "split" if path.endswith("split") else "promote" if "promote" in path else "drop"
        _, body = _action(action)

        resp = _client(Role.ADMIN, projects, store, campaigns).post(path, json=body)

        assert _error(resp) == (404, code), resp.text
        assert len(store.revisions["prj-lantern"]) == 1
