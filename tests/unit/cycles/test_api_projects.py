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
            "development_baseline_commit": None,
            "integrated_upstream_commit": None,
            "validation_diagnostic": None,
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


class TestValidateProject:
    """``POST /api/v1/projects/{id}/validate`` (SIP-0112 E.4.2), at the route the CLI calls.
    Bugs caught: the route reading a different registry or clone than the runtime wires; a
    failed validation answered as an error rather than recorded and returned."""

    @pytest.fixture
    def wired(self, client, mock_project_registry):
        from squadops.projects.models import (
            CheckoutTree,
            ProjectLifecycleStatus,
            ProjectSource,
        )

        source = ProjectSource(
            repo_uri="https://code.example.invalid/tally.git",
            base_ref="refs/heads/main",
            contribution_mode="review_request",
        )
        project = Project(
            project_id="prj-tally", name="Tally", description="", created_at=NOW, source=source,
            lifecycle_status=ProjectLifecycleStatus.REGISTERING,
        )  # fmt: skip
        mock_project_registry.get_project.return_value = project

        async def record(project_id, *, commit, diagnostic, actor, idempotency_key):
            status = (
                ProjectLifecycleStatus.READY
                if commit
                else ProjectLifecycleStatus.FAILED_REGISTRATION
            )
            return (
                Project(
                    project_id=project_id,
                    name="Tally",
                    description="",
                    created_at=NOW,
                    source=source,
                    lifecycle_status=status,
                    development_baseline_commit=commit,
                    integrated_upstream_commit=commit,
                    validation_diagnostic=diagnostic,
                ),
                False,
            )

        mock_project_registry.record_validation.side_effect = record
        clone = AsyncMock()
        clone.sync.return_value = "c" * 40
        clone.tree_at.return_value = CheckoutTree(
            "c" * 40, {}, frozenset(), frozenset(), frozenset()
        )
        client.app.state.source_repository = clone
        return clone

    def test_a_reached_source_answers_ready_at_its_commit(self, client, wired):
        resp = client.post("/api/v1/projects/prj-tally/validate", json={"idempotency_key": "v-1"})

        project = resp.json()["project"]
        assert resp.status_code == 200
        assert (project["lifecycle_status"], project["development_baseline_commit"]) == (
            "READY",
            "c" * 40,
        )
        wired.sync.assert_awaited_once_with(
            "prj-tally", "https://code.example.invalid/tally.git", "refs/heads/main", token=None
        )

    def test_a_private_repository_is_reached_with_the_owners_token_for_this_act(
        self, client, wired
    ):
        """E.4.6's private destination, and any private product. Bugs caught: the owner's token
        not reaching the fetch, so a private repository can't be validated; the token returned."""
        resp = client.post(
            "/api/v1/projects/prj-tally/validate",
            json={"idempotency_key": "v-3", "token": "owner-secret"},
        )

        assert resp.status_code == 200
        assert wired.sync.await_args.kwargs["token"] == "owner-secret"
        assert "owner-secret" not in resp.text

    def test_an_unreachable_source_is_recorded_and_answered_not_raised(self, client, wired):
        from squadops.projects.models import SourceUnavailable

        wired.sync.side_effect = SourceUnavailable("git clone failed: denied", reason="clone")

        resp = client.post("/api/v1/projects/prj-tally/validate", json={"idempotency_key": "v-2"})

        project = resp.json()["project"]
        assert resp.status_code == 200
        assert project["lifecycle_status"] == "FAILED_REGISTRATION"
        assert project["validation_diagnostic"] == "clone: git clone failed: denied"

    def test_a_ready_projects_unreachable_re_validation_is_a_502_and_records_nothing(
        self, client, wired, mock_project_registry
    ):
        """E.4.4. Bug caught: a READY Project's failed re-validation answered as recorded, or
        recorded as a failed registration, refusing every Cycle over a product that was fine."""
        import dataclasses

        from squadops.projects.models import ProjectLifecycleStatus, SourceUnavailable

        mock_project_registry.get_project.return_value = dataclasses.replace(
            mock_project_registry.get_project.return_value,
            lifecycle_status=ProjectLifecycleStatus.READY,
            development_baseline_commit="b" * 40,
        )
        wired.sync.side_effect = SourceUnavailable("git fetch failed: denied", reason="fetch")

        resp = client.post("/api/v1/projects/prj-tally/validate", json={"idempotency_key": "v-3"})

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            502, "SOURCE_UNAVAILABLE",
        )  # fmt: skip
        mock_project_registry.record_validation.assert_not_awaited()


class TestDevelopmentConfigurationRoutes:
    """``/api/v1/projects/{id}/development-configuration(s)`` (SIP-0112 E.4.2), at the routes
    the CLI calls. Bugs caught: a malformed declaration answered 500 instead of naming its
    field; the stored document altered between the registry and the response."""

    @pytest.fixture
    def configured(self, client, mock_project_registry, tmp_path):
        import copy

        from squadops.projects.models import CheckoutTree, ProjectSource
        from tests.fixtures.shared_contract.repository import (
            build_repository,
            recorded,
            tracked_files,
        )

        repo = build_repository(tmp_path / "tally")
        mock_project_registry.get_project.return_value = Project(
            project_id="prj-tally",
            name="Tally",
            description="",
            created_at=NOW,
            source=ProjectSource(
                repo_uri="https://code.example.invalid/tally.git",
                base_ref="refs/heads/main",
                contribution_mode="review_request",
            ),
            development_baseline_commit=repo.second_commit,
        )

        async def record(configuration, **kwargs):
            return configuration, False

        mock_project_registry.record_development_configuration.side_effect = record
        mock_project_registry.get_initialization.return_value = None  # an existing product
        clone = AsyncMock()
        clone.tree_at.return_value = CheckoutTree(
            repo.second_commit,
            tracked_files(repo.path, repo.second_commit),
            frozenset(),
            frozenset(),
            frozenset(),
        )
        client.app.state.source_repository = clone
        valid = recorded("development_configuration", "valid")
        return copy.deepcopy(valid["configuration"]["technical"]), valid

    def test_a_recording_answers_the_stored_document(self, client, configured):
        technical, valid = configured

        resp = client.post(
            "/api/v1/projects/prj-tally/development-configurations",
            json={"idempotency_key": "c-1", "expected_revision": 0, "technical": technical},
        )

        assert resp.status_code == 201
        assert resp.json()["configuration"]["document"] == valid
        assert resp.json()["replayed"] is False

    def test_a_malformed_declaration_is_refused_naming_its_field(
        self, client, configured, mock_project_registry
    ):
        technical, _ = configured
        technical["commands"]["start"]["start"] = "python3 -m tally serve"

        resp = client.post(
            "/api/v1/projects/prj-tally/development-configurations",
            json={"idempotency_key": "c-1", "expected_revision": 0, "technical": technical},
        )

        error = resp.json()["detail"]["error"]
        assert (resp.status_code, error["code"]) == (422, "CONFIGURATION_INVALID")
        assert error["details"] == {"field": "technical.commands.start.start"}
        mock_project_registry.record_development_configuration.assert_not_awaited()

    def test_the_current_revision_reads_back(self, client, configured, mock_project_registry):
        from squadops.projects.development_configuration import parse_configuration

        _, valid = configured
        mock_project_registry.get_development_configuration.return_value = parse_configuration(
            valid
        )

        resp = client.get("/api/v1/projects/prj-tally/development-configuration")

        assert resp.json() == {"project_id": "prj-tally", "revision": 1, "document": valid}


class TestBaselineRoutes:
    """``/api/v1/projects/{id}/baseline(s)`` (SIP-0112 FR-20). Bugs caught: a capture with no
    sandbox recording an empty baseline as if the checks had run; no baseline answered 500."""

    def test_a_capture_without_a_sandbox_client_is_refused_and_records_nothing(
        self, client, mock_project_registry
    ):
        from squadops.projects.development_configuration import parse_configuration
        from squadops.projects.models import ProjectSource
        from tests.fixtures.shared_contract.repository import recorded

        configuration = parse_configuration(recorded("development_configuration", "valid"))
        mock_project_registry.get_project.return_value = Project(
            project_id="prj-tally",
            name="Tally",
            description="",
            created_at=NOW,
            source=ProjectSource(
                "https://code.example.invalid/t.git", "refs/heads/main", "review_request"
            ),
            development_baseline_commit=configuration.validated_at_commit,
        )
        mock_project_registry.get_development_configuration.return_value = configuration
        client.app.state.source_repository = AsyncMock()
        client.app.state.sandbox_client = None

        resp = client.post("/api/v1/projects/prj-tally/baselines", json={"idempotency_key": "b-1"})

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            503,
            "SANDBOX_UNAVAILABLE",
        )
        mock_project_registry.record_inherited_baseline.assert_not_awaited()

    def test_no_baseline_yet_is_not_found(self, client, mock_project_registry):
        from squadops.cycles.models import InheritedBaselineNotFoundError

        mock_project_registry.get_inherited_baseline.side_effect = InheritedBaselineNotFoundError(
            "none"
        )

        resp = client.get("/api/v1/projects/prj-tally/baseline")

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            404,
            "INHERITED_BASELINE_NOT_FOUND",
        )

    @pytest.mark.parametrize("stored", [True, False], ids=["recorded", "captured before profiles"])
    def test_the_derived_profile_reads_as_recorded_and_its_absence_is_not_found(
        self, client, mock_project_registry, stored
    ):
        """H.4, contract 8. Bugs caught: a capture from before profiles answered 500, or read as
        an empty profile rather than absent; the baseline's read failing for want of one."""
        from squadops.cycles.models import DerivedProfileNotFoundError
        from squadops.projects.baseline import parse_baseline
        from squadops.projects.derived_profile import parse_profile
        from tests.fixtures.shared_contract.repository import recorded

        valid = recorded("derived_profile", "valid")
        baseline_doc = recorded("inherited_baseline", "valid")
        mock_project_registry.get_inherited_baseline.return_value = parse_baseline(baseline_doc)
        if stored:
            mock_project_registry.get_derived_profile.return_value = parse_profile(valid)
        else:
            mock_project_registry.get_derived_profile.side_effect = DerivedProfileNotFoundError(
                "none"
            )

        profile = client.get("/api/v1/projects/prj-tally/profile")
        baseline = client.get("/api/v1/projects/prj-tally/baseline")

        assert baseline.status_code == 200
        if stored:
            assert (profile.status_code, profile.json()["document"]) == (200, valid)
            assert baseline.json()["derived_profile"] == valid
        else:
            assert (profile.status_code, profile.json()["detail"]["error"]["code"]) == (
                404,
                "DERIVED_PROFILE_NOT_FOUND",
            )
            assert baseline.json()["derived_profile"] is None


class TestContributionRoutes:
    """``/api/v1/projects/{id}/contributions`` (SIP-0112 FR-06, E.4.3). Bugs caught: a refused
    contribution answered as a server failure; a forge's failure answered as the caller's; the
    recorded contribution not what the response says."""

    def _sample(self, client, mock_project_registry):
        mock_project_registry.contributions.return_value = []
        client.app.state.source_repository = AsyncMock()

    def test_a_run_with_no_accepted_change_is_refused_and_records_nothing(
        self, client, mock_project_registry
    ):
        self._sample(client, mock_project_registry)

        resp = client.post(
            "/api/v1/projects/hello_squad/contributions",
            json={"cycle_id": "cyc_1", "run_id": "run_1", "idempotency_key": "c-1"},
        )

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            409,
            "CONTRIBUTION_REFUSED",
        )
        assert "sample application" in resp.json()["detail"]["error"]["message"]
        mock_project_registry.record_contribution.assert_not_awaited()

    def test_a_pending_contribution_lists_as_recorded(self, client, mock_project_registry):
        from squadops.projects.contribution import Contribution

        contribution = Contribution(
            project_id="prj-tally",
            cycle_id="cyc_1",
            run_id="run_1",
            commit="a" * 40,
            parent_commit="b" * 40,
            mode="review_request",
            state="pending",
            branch="squadops/cyc_1",
            review_url="https://github.com/owner/tally/pull/7",
            contributed_by="owner",
            contributed_at=NOW,
        )
        mock_project_registry.contributions.return_value = [contribution]

        resp = client.get("/api/v1/projects/prj-tally/contributions")

        assert resp.status_code == 200
        assert resp.json() == [{"contribution": contribution.to_document(), "replayed": False}]

    def test_a_contribution_without_its_key_is_refused(self, client, mock_project_registry):
        """The key is required, so a retried contribution replays rather than contributes
        twice."""
        self._sample(client, mock_project_registry)

        resp = client.post(
            "/api/v1/projects/hello_squad/contributions",
            json={"cycle_id": "cyc_1", "run_id": "run_1"},
        )

        assert resp.status_code == 422
        mock_project_registry.record_contribution.assert_not_awaited()

    @pytest.mark.parametrize(
        ("token", "deploy_tokens", "expected"),
        [("own-t0ken", {"prj-tally": "deploy"}, {"prj-tally": "own-t0ken"}),
         (None, {"prj-tally": "deploy"}, {"prj-tally": "deploy"})],
        ids=["the-contributors-own", "the-deploys"],
    )  # fmt: skip
    def test_the_contributors_own_token_is_used_for_this_act_and_never_answered(
        self, client, mock_project_registry, monkeypatch, token, deploy_tokens, expected
    ):
        """Bugs caught: the contributor's token ignored for the deploy's, or the deploy's
        ignored without one; the token echoed back in the response."""
        from squadops.api.routes.cycles import projects as route
        from squadops.projects.contribution import Contribution

        recorded = Contribution(
            project_id="prj-tally", cycle_id="cyc_1", run_id="run_1", commit="a" * 40,
            parent_commit="b" * 40, mode="review_request", state="pending",
            branch="squadops/cyc_1", review_url="https://github.com/o/t/pull/7",
            contributed_by="anonymous", contributed_at=NOW,
        )  # fmt: skip
        seen = AsyncMock(return_value=(recorded, False))
        monkeypatch.setattr(route, "contribute", seen)
        client.app.state.source_repository = AsyncMock()
        client.app.state.review_request_tokens = deploy_tokens
        body = {"cycle_id": "cyc_1", "run_id": "run_1", "idempotency_key": "c-1"}

        resp = client.post(
            "/api/v1/projects/prj-tally/contributions",
            json={**body, **({"token": token} if token else {})},
        )

        assert resp.status_code == 201
        assert seen.await_args.kwargs["tokens"] == expected
        assert "t0ken" not in resp.text


class TestSyncRoutes:
    """``/api/v1/projects/{id}/syncs`` (SIP-0112 FR-21, E.4.4). Bugs caught: a sample
    application's sync answered as a server failure; the recorded findings not what's listed."""

    def test_a_sample_application_has_no_upstream_to_sync(self, client, mock_project_registry):
        client.app.state.source_repository = AsyncMock()

        resp = client.post("/api/v1/projects/hello_squad/syncs", json={"idempotency_key": "s-1"})

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (409, "SYNC_REFUSED")
        mock_project_registry.record_sync.assert_not_awaited()

    def test_the_findings_list_as_recorded(self, client, mock_project_registry):
        document = {"schema": "source-sync/v1", "project_id": "prj-tally", "drift": None}
        mock_project_registry.source_syncs.return_value = [document]

        resp = client.get("/api/v1/projects/prj-tally/syncs")

        assert resp.json() == [{"document": document, "replayed": False}]


class TestInitializationRoutes:
    """``/api/v1/projects/{id}/initializations`` (SIP-0112 FR-01, E.4.6). Bugs caught: an owner's
    repository that already has a commit answered as a server failure, inviting retries; a
    forge's refusal answered as the caller's; the owner's token not reaching the push, or
    returned in the answer."""

    def _greenfield(self, client, mock_project_registry, repository):
        from pathlib import Path

        import yaml

        from squadops.projects.models import ProjectLifecycleStatus, ProjectSource

        mock_project_registry.get_project.return_value = Project(
            project_id="shelfnote",
            name="Shelfnote",
            description="",
            created_at=NOW,
            lifecycle_status=ProjectLifecycleStatus.REGISTERING,
            source=ProjectSource(
                "https://github.com/owner/shelfnote.git", "refs/heads/main", "review_request"
            ),
        )
        mock_project_registry.get_initialization.return_value = None
        client.app.state.source_repository = repository
        root = Path(__file__).resolve().parents[3]
        manifest = yaml.safe_load(
            (root / "examples/03_group_run/interface_manifest.yaml").read_text()
        )
        manifest["project_id"] = "shelfnote"
        return yaml.safe_dump(manifest)

    @pytest.mark.parametrize(
        ("reason", "status", "code"),
        [("not_empty", 409, "INITIALIZATION_REFUSED"), ("push", 502, "INITIALIZATION_FAILED")],
        ids=["the-branch-has-a-commit", "the-forge-refused-the-push"],
    )
    def test_the_clones_refusal_is_answered_by_whose_it_is(
        self, client, mock_project_registry, reason, status, code
    ):
        from squadops.projects.models import SourceUnavailable

        repository = AsyncMock()
        repository.initialize.side_effect = SourceUnavailable("refused", reason=reason)
        manifest = self._greenfield(client, mock_project_registry, repository)

        resp = client.post(
            "/api/v1/projects/shelfnote/initializations",
            json={"manifest": manifest, "idempotency_key": "i-1", "token": "owner-secret"},
        )

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (status, code)
        assert repository.initialize.await_args.kwargs["token"] == "owner-secret"
        assert "owner-secret" not in resp.text
        mock_project_registry.record_initialization.assert_not_awaited()

    def test_a_sample_application_is_refused_and_nothing_is_pushed(
        self, client, mock_project_registry
    ):
        repository = AsyncMock()
        client.app.state.source_repository = repository
        mock_project_registry.get_initialization.return_value = None

        resp = client.post(
            "/api/v1/projects/hello_squad/initializations",
            json={"manifest": "kind: interface_manifest\n", "idempotency_key": "i-1"},
        )

        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            409,
            "INITIALIZATION_REFUSED",
        )
        repository.initialize.assert_not_awaited()
