"""
Tests for SIP-0064 project API routes.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.projects import router
from squadops.cycles.models import Project, ProjectNotFoundError

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_project_registry():
    mock = AsyncMock()
    mock.list_projects.return_value = [
        Project(
            project_id="hello_squad",
            name="Hello Squad",
            description="Test",
            created_at=NOW,
            tags=("example",),
        ),
    ]
    mock.get_project.return_value = Project(
        project_id="hello_squad",
        name="Hello Squad",
        description="Test",
        created_at=NOW,
        tags=("example",),
    )
    return mock


@pytest.fixture
def client(mock_project_registry, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    register_domain_error_handlers(app)  # as the runtime does (#576)

    app.state.project_registry = mock_project_registry
    return TestClient(app)


class TestListProjects:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "hello_squad"
        assert data[0]["tags"] == ["example"]

    def test_has_prd_false_when_no_prd_path(self, client):
        resp = client.get("/api/v1/projects")
        data = resp.json()
        assert data[0]["has_prd"] is False

    def test_has_prd_true_when_prd_path_set(self, client, mock_project_registry):
        mock_project_registry.list_projects.return_value = [
            Project(
                project_id="with_prd",
                name="With PRD",
                description="Test",
                created_at=NOW,
                prd_path="/some/prd.md",
            ),
        ]
        resp = client.get("/api/v1/projects")
        data = resp.json()
        assert data[0]["has_prd"] is True


class TestGetProject:
    def test_returns_project(self, client):
        resp = client.get("/api/v1/projects/hello_squad")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "hello_squad"

    def test_not_found(self, client, mock_project_registry):
        mock_project_registry.get_project.side_effect = ProjectNotFoundError("Not found")
        resp = client.get("/api/v1/projects/unknown")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"
        assert body["detail"]["error"]["details"] is None


class TestTheProjectRecordAddsFieldsOnly:
    """SIP-0112 D.6, IR-1 (#2408): ``projects list/show`` change only by added fields. Bugs
    caught: a sample application's existing fields changed by the record's arrival; a registered
    Project's source or owner dropped between the registry and the response."""

    def test_a_sample_applications_six_fields_are_unchanged_and_the_record_reads_ready(
        self, client
    ):
        body = client.get("/api/v1/projects/hello_squad").json()

        assert {k: body[k] for k in ("project_id", "name", "description", "tags", "has_prd")} == {
            "project_id": "hello_squad",
            "name": "Hello Squad",
            "description": "Test",
            "tags": ["example"],
            "has_prd": False,
        }
        assert body["created_at"].startswith("2026-01-15T12:00:00")
        assert {k: body[k] for k in body if k not in _LEGACY_FIELDS} == {
            "lifecycle_status": "READY",
            "record_version": 1,
            "source": None,
            "ownership": None,
            "development_configuration_revision": None,
        }

    def test_a_registered_projects_source_and_owner_reach_the_response(
        self, client, mock_project_registry
    ):
        from squadops.projects.models import (
            ProjectLifecycleStatus,
            ProjectOwnership,
            ProjectSource,
        )

        mock_project_registry.get_project.return_value = Project(
            project_id="prj-tally",
            name="Tally",
            description="an external product",
            created_at=NOW,
            lifecycle_status=ProjectLifecycleStatus.REGISTERING,
            record_version=2,
            source=ProjectSource(
                repo_uri="https://code.example.invalid/tally/tally.git",
                base_ref="refs/heads/main",
                contribution_mode="review_request",
            ),
            ownership=ProjectOwnership(
                owner="Tally Maintainer", delegated_actions=("contribution",)
            ),
        )

        body = client.get("/api/v1/projects/prj-tally").json()

        assert (body["lifecycle_status"], body["record_version"]) == ("REGISTERING", 2)
        assert body["source"] == {
            "repo_uri": "https://code.example.invalid/tally/tally.git",
            "base_ref": "refs/heads/main",
            "contribution_mode": "review_request",
            "repository_root": ".",
        }
        assert body["ownership"] == {
            "owner": "Tally Maintainer",
            "delegated_actions": ["contribution"],
            "acceptance_policy_ref": None,
        }


_LEGACY_FIELDS = {"project_id", "name", "description", "created_at", "tags", "has_prd"}


_REGISTRATION = {
    "idempotency_key": "import-1",
    "name": "Tally",
    "origin": {"mode": "import"},
    "source": {
        "repo_uri": "https://code.example.invalid/tally/tally.git",
        "base_ref": "refs/heads/main",
        "contribution_mode": "review_request",
    },
    "ownership": {"owner": "Tally Maintainer", "delegated_actions": ["contribution"]},
}


class TestRegisterProject:
    """``POST /api/v1/projects`` (SIP-0112 E.4.1), entered at the route the CLI calls. Bugs
    caught: a refused locator reaching the registry; the registration's fields lost between the
    body and the record; a read-only registry's refusal surfacing as a 500; the key a safe retry
    needs missing from the answer."""

    @pytest.fixture
    def registering(self, client, mock_project_registry):
        from squadops.projects.models import ProjectLifecycleStatus
        from squadops.projects.registration import LocatorPolicy

        client.app.state.project_locator_policy = LocatorPolicy()

        async def register(registration, *, actor):
            return (
                Project(
                    project_id=registration.project_id,
                    name=registration.name,
                    description=registration.description,
                    created_at=NOW,
                    lifecycle_status=ProjectLifecycleStatus.REGISTERING,
                    source=registration.source,
                    ownership=registration.ownership,
                ),
                False,
            )

        mock_project_registry.register_project.side_effect = register
        return mock_project_registry

    def test_a_registration_is_answered_registering_with_its_key(self, client, registering):
        resp = client.post("/api/v1/projects", json=_REGISTRATION)

        body = resp.json()
        assert resp.status_code == 201
        assert (body["idempotency_key"], body["replayed"]) == ("import-1", False)
        assert body["project"]["project_id"] == "prj-tally"
        assert body["project"]["lifecycle_status"] == "REGISTERING"
        assert body["project"]["source"]["repo_uri"] == _REGISTRATION["source"]["repo_uri"]
        [call] = registering.register_project.await_args_list
        assert call.kwargs == {"actor": "anonymous"}
        assert call.args[0].ownership.delegated_actions == ("contribution",)

    def test_a_refused_locator_never_reaches_the_registry(self, client, registering):
        body = {
            **_REGISTRATION,
            "source": {**_REGISTRATION["source"], "repo_uri": "/home/me/tally"},
        }

        resp = client.post("/api/v1/projects", json=body)

        error = resp.json()["detail"]["error"]
        assert (resp.status_code, error["code"]) == (422, "LOCATOR_REFUSED")
        assert error["details"] == {"reason": "local_path"}
        registering.register_project.assert_not_awaited()

    def test_only_an_existing_repository_is_registered_in_this_slice(self, client, registering):
        """``new`` is greenfield (E.4.6), ``attach`` writing in place (E.4.7)."""
        resp = client.post("/api/v1/projects", json={**_REGISTRATION, "origin": {"mode": "new"}})

        assert resp.status_code == 422
        registering.register_project.assert_not_awaited()

    def test_the_config_registry_refuses_the_write_as_read_only(self, client):
        from adapters.cycles.config_project_registry import ConfigProjectRegistry
        from squadops.projects.registration import LocatorPolicy

        client.app.state.project_registry = ConfigProjectRegistry()
        client.app.state.project_locator_policy = LocatorPolicy()

        resp = client.post("/api/v1/projects", json=_REGISTRATION)

        error = resp.json()["detail"]["error"]
        assert (resp.status_code, error["code"]) == (409, "PROJECT_REGISTRY_READ_ONLY")

    @pytest.mark.parametrize(
        ("role", "scopes", "expected"),
        [
            ("OPERATOR", ("CYCLES_READ", "CYCLES_WRITE"), 403),
            ("ADMIN", ("CYCLES_READ", "CYCLES_WRITE", "ADMIN_WRITE"), 201),
        ],
    )
    def test_registering_needs_admin_write(self, role, scopes, expected):
        """R6. Bug caught: the route left on a read or cycle-write scope, so any operator or
        viewer registers a product on the owner's behalf."""
        from datetime import timedelta
        from unittest.mock import patch

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
        from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
        from squadops.auth.models import Identity, Role, Scope, TokenClaims
        from squadops.projects.registration import LocatorPolicy

        identity = Identity(
            user_id="someone",
            display_name="Someone",
            roles=(getattr(Role, role),),
            scopes=tuple(getattr(Scope, s) for s in scopes),
        )
        now = datetime.now(tz=UTC)
        auth_port = AsyncMock()
        auth_port.validate_token = AsyncMock(
            return_value=TokenClaims(
                subject="someone",
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
        app.add_middleware(
            AuthMiddleware, auth_port=auth_port, provider="keycloak", expose_docs=False
        )
        app.add_middleware(RequestIDMiddleware)
        app.include_router(router)
        registry = AsyncMock()
        registry.register_project.return_value = (
            Project(project_id="prj-tally", name="Tally", description="", created_at=NOW),
            False,
        )
        app.state.project_registry = registry
        app.state.project_locator_policy = LocatorPolicy()

        with patch(
            "squadops.api.middleware.auth.get_authz_port", return_value=KeycloakAuthzAdapter()
        ):
            resp = TestClient(app).post(
                "/api/v1/projects", json=_REGISTRATION, headers={"Authorization": "Bearer t"}
            )

        assert resp.status_code == expected
        assert registry.register_project.await_count == (1 if expected == 201 else 0)
        if expected == 201:
            assert registry.register_project.await_args.kwargs == {"actor": "someone"}
