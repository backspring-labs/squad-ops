"""``/api/v1/projects/{id}/goal-set`` (SIP-0115 §8.1, #2884), at the routes the CLI calls, behind
the runtime's own auth middleware and error handlers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.api.routes.cycles.goal_sets import router
from squadops.auth.models import ROLE_SCOPES, Identity, Role, TokenClaims
from squadops.cycles.models import (
    GoalSetNotFoundError,
    Project,
    ProjectNotFoundError,
    StaleGoalSetRevisionError,
)
from squadops.projects.goal_set import GoalSetRevision, parse_goal_set
from tests.fixtures.goal_set import goal_set_document

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
PATH = "/api/v1/projects/prj-lantern/goal-set"


def _client(role: str, projects: AsyncMock, goal_sets: AsyncMock) -> TestClient:
    """The app as the runtime builds it for these routes: a token resolving to ``role``'s
    principal, its scopes the ones the realm's role grants."""
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
        or the crew's principal rewrites the owner's goal."""
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
