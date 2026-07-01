"""
Tests for SIP-0064 cycle API routes.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.cycles import router
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    CycleNotFoundError,
    ProjectNotFoundError,
    SquadProfile,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_project_registry():
    from squadops.cycles.models import Project

    mock = AsyncMock()
    mock.get_project.return_value = Project(
        project_id="hello_squad",
        name="Hello Squad",
        description="Test",
        created_at=NOW,
    )
    return mock


@pytest.fixture
def mock_cycle_registry():
    mock = AsyncMock()
    mock.create_cycle.side_effect = lambda c: c
    mock.create_run.side_effect = lambda r: r
    mock.list_cycles.return_value = []
    mock.list_runs.return_value = []
    return mock


def _full_plan_profile():
    """A squad carrying every role the default (plan) workload requires (SIP-0095),
    so the create-time preflight passes. Models are unverifiable in these tests (no
    LLM port wired → warn-and-allow), so only roles gate here."""
    roles = [("max", "lead"), ("nat", "strat"), ("neo", "dev"), ("eve", "qa"), ("data", "data")]
    return SquadProfile(
        profile_id="full",
        name="Full Squad",
        description="All agents",
        version=1,
        agents=tuple(
            AgentProfileEntry(agent_id=aid, role=role, model="gpt-4", enabled=True)
            for aid, role in roles
        ),
        created_at=NOW,
    )


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    mock.resolve_snapshot.return_value = (_full_plan_profile(), "sha256:abc123")
    return mock


@pytest.fixture
def mock_flow_executor():
    mock = AsyncMock()
    return mock


@pytest.fixture
def client(
    mock_project_registry,
    mock_cycle_registry,
    mock_squad_profile,
    mock_flow_executor,
    monkeypatch,
):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_project_registry", mock_project_registry)
    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_cycle_registry)
    monkeypatch.setattr(deps_mod, "_squad_profile", mock_squad_profile)
    monkeypatch.setattr(deps_mod, "_flow_executor", mock_flow_executor)
    return TestClient(app)


class TestCreateCycle:
    def test_creates_cycle_and_run(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={
                "squad_profile_id": "full",
                "task_flow_policy": {"mode": "sequential"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "hello_squad"
        assert body["run_number"] == 1
        assert body["status"] == "queued"
        assert body["squad_profile_id"] == "full"
        assert "cycle_id" in body
        assert "run_id" in body

    def test_create_cycle_prd_ref_none(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={
                "prd_ref": None,
                "squad_profile_id": "full",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["prd_ref"] is None

    def test_create_cycle_unknown_project(self, client, mock_project_registry):
        mock_project_registry.get_project.side_effect = ProjectNotFoundError("Not found")
        resp = client.post(
            "/api/v1/projects/unknown/cycles",
            json={"squad_profile_id": "full"},
        )
        assert resp.status_code == 404

    def test_workload_type_from_workload_sequence(self, client, mock_cycle_registry):
        """When applied_defaults has workload_sequence, run gets workload_type from first entry."""
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={
                "squad_profile_id": "full",
                "applied_defaults": {
                    "workload_sequence": [
                        {"type": "framing", "gate": "progress_plan_review"},
                        {"type": "implementation", "gate": None},
                    ],
                },
            },
        )
        assert resp.status_code == 200
        run = mock_cycle_registry.create_run.call_args[0][0]
        assert run.workload_type == "framing"

    def test_workload_type_none_without_workload_sequence(self, client, mock_cycle_registry):
        """Without workload_sequence, run.workload_type stays None (legacy path)."""
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={"squad_profile_id": "full"},
        )
        assert resp.status_code == 200
        run = mock_cycle_registry.create_run.call_args[0][0]
        assert run.workload_type is None

    def test_create_cycle_extra_fields_rejected(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={
                "squad_profile_id": "full",
                "bogus_field": "bad",
            },
        )
        assert resp.status_code == 422


class TestListCycles:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/projects/hello_squad/cycles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_status(self, client):
        resp = client.get("/api/v1/projects/hello_squad/cycles?status=completed")
        assert resp.status_code == 200


class TestGetCycle:
    def test_returns_cycle(self, client, mock_cycle_registry):
        cycle = Cycle(
            cycle_id="cyc_001",
            project_id="hello_squad",
            created_at=NOW,
            created_by="system",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
        mock_cycle_registry.get_cycle.return_value = cycle
        mock_cycle_registry.list_runs.return_value = []

        resp = client.get("/api/v1/projects/hello_squad/cycles/cyc_001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cycle_id"] == "cyc_001"
        assert body["status"] == "created"

    def test_not_found(self, client, mock_cycle_registry):
        mock_cycle_registry.get_cycle.side_effect = CycleNotFoundError("Not found")
        resp = client.get("/api/v1/projects/hello_squad/cycles/nonexistent")
        assert resp.status_code == 404


class TestCancelCycle:
    def test_cancel_success(self, client, mock_cycle_registry):
        mock_cycle_registry.cancel_cycle.return_value = None
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_propagates_to_prefect(self, client, mock_cycle_registry, monkeypatch):
        """#77: cancelling a cycle transitions its still-running Prefect flow
        run(s) to CANCELLED so workers stop executing the orphaned cycle."""
        import squadops.api.runtime.deps as deps_mod
        from squadops.cycles.models import Run

        mock_cycle_registry.cancel_cycle.return_value = None
        mock_cycle_registry.list_runs.return_value = [
            Run(
                run_id="run_001",
                cycle_id="cyc_001",
                run_number=1,
                status="running",
                initiated_by="api",
                resolved_config_hash="x",
            ),
        ]
        fake_tracker = AsyncMock()
        fake_tracker.find_active_flow_run_ids.return_value = ["flowrun-xyz"]
        monkeypatch.setattr(deps_mod, "_workflow_tracker", fake_tracker)

        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/cancel")

        assert resp.status_code == 200
        assert resp.json()["prefect_flow_runs_cancelled"] == 1
        # Found by the reconstructed flow-run name (single-sourced with the executor)
        # and transitioned to CANCELLED.
        fake_tracker.find_active_flow_run_ids.assert_awaited_once_with(
            ["hello_squad/cyc_001/run_001"]
        )
        fake_tracker.set_flow_run_state.assert_awaited_once_with(
            "flowrun-xyz", "CANCELLED", "Cancelled"
        )

    def test_cancel_survives_prefect_failure(self, client, mock_cycle_registry, monkeypatch):
        """Registry cancellation is the source of truth: if Prefect propagation
        fails, the cycle is still reported cancelled (best-effort, #77)."""
        import squadops.api.runtime.deps as deps_mod
        from squadops.cycles.models import Run

        mock_cycle_registry.cancel_cycle.return_value = None
        mock_cycle_registry.list_runs.return_value = [
            Run(
                run_id="run_001",
                cycle_id="cyc_001",
                run_number=1,
                status="running",
                initiated_by="api",
                resolved_config_hash="x",
            ),
        ]
        fake_tracker = AsyncMock()
        fake_tracker.find_active_flow_run_ids.side_effect = RuntimeError("prefect down")
        monkeypatch.setattr(deps_mod, "_workflow_tracker", fake_tracker)

        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/cancel")

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["prefect_flow_runs_cancelled"] == 0


class TestCycleRouteScopeEnforcement:
    """#150: with auth enabled, cycle routes enforce cycles:read/write.

    Proves the require_scopes guards are actually wired onto the real routes
    (not merely that require_scopes works in isolation) — a request with an
    insufficient scope is rejected before the handler runs."""

    def _auth_app(self, identity):
        from datetime import timedelta

        from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
        from squadops.auth.models import TokenClaims

        now = datetime.now(tz=UTC)
        claims = TokenClaims(
            subject=identity.user_id,
            issuer="http://kc/realms/squadops",
            audience="squadops-runtime",
            expires_at=now + timedelta(hours=1),
            issued_at=now,
            roles=identity.roles,
            scopes=identity.scopes,
        )
        auth_port = AsyncMock()
        auth_port.validate_token = AsyncMock(return_value=claims)
        auth_port.resolve_identity = AsyncMock(return_value=identity)

        app = FastAPI()
        app.add_middleware(
            AuthMiddleware, auth_port=auth_port, provider="keycloak", expose_docs=False
        )
        app.add_middleware(RequestIDMiddleware)
        app.include_router(router)
        return app

    def test_write_route_forbidden_without_write_scope(self):
        """A read-only identity hitting a write route (cancel) gets 403."""
        from unittest.mock import patch

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
        from squadops.auth.models import Identity, Role, Scope

        identity = Identity(
            user_id="reader",
            display_name="Reader",
            roles=(Role.VIEWER,),
            scopes=(Scope.CYCLES_READ,),
        )
        app = self._auth_app(identity)
        with patch("squadops.api.runtime.deps.get_authz_port", return_value=KeycloakAuthzAdapter()):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/projects/hello_squad/cycles/cyc_001/cancel",
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == 403

    def test_read_route_requires_authentication_when_auth_on(self):
        """Auth enabled but no token → 401 even on a read route."""
        from unittest.mock import patch

        from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
        from squadops.auth.models import Identity, Role, Scope

        identity = Identity(
            user_id="x", display_name="x", roles=(Role.VIEWER,), scopes=(Scope.CYCLES_READ,)
        )
        app = self._auth_app(identity)
        with patch("squadops.api.runtime.deps.get_authz_port", return_value=KeycloakAuthzAdapter()):
            client = TestClient(app)
            resp = client.get("/api/v1/projects/hello_squad/cycles", headers={})
        assert resp.status_code == 401


class TestCreateCyclePreflight:
    """SIP-0095 Phase 3: the create-time preflight fails fast (422) before persist."""

    _REQUEST = {"squad_profile_id": "full", "task_flow_policy": {"mode": "sequential"}}

    def test_full_squad_with_unverifiable_models_is_allowed(self, client):
        """Roles satisfied + LLM backend unreachable (None) → warn-and-allow → 200."""
        resp = client.post("/api/v1/projects/hello_squad/cycles", json=self._REQUEST)
        assert resp.status_code == 200

    def test_blocks_when_squad_cannot_satisfy_required_roles(
        self, client, mock_squad_profile, mock_cycle_registry
    ):
        lean = SquadProfile(
            profile_id="lite",
            name="Lean",
            description="",
            version=1,
            agents=(AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),),
            created_at=NOW,
        )
        mock_squad_profile.resolve_snapshot.return_value = (lean, "sha256:x")

        resp = client.post("/api/v1/projects/hello_squad/cycles", json=self._REQUEST)

        assert resp.status_code == 422
        err = resp.json()["detail"]["error"]
        assert err["code"] == "PREFLIGHT_REJECTED"
        assert "role" in err["message"]  # names the missing role
        mock_cycle_registry.create_cycle.assert_not_called()  # fail-fast: nothing persisted
        mock_cycle_registry.create_run.assert_not_called()

    def test_blocks_when_a_required_model_is_not_pulled(self, client, mock_cycle_registry):
        # backend reachable but empty → the profile's `gpt-4` is definitively absent
        with patch(
            "squadops.api.routes.cycles.cycles._pulled_model_names",
            new=AsyncMock(return_value=[]),
        ):
            resp = client.post("/api/v1/projects/hello_squad/cycles", json=self._REQUEST)

        assert resp.status_code == 422
        err = resp.json()["detail"]["error"]
        assert err["code"] == "PREFLIGHT_REJECTED"
        assert "gpt-4" in err["message"]
        mock_cycle_registry.create_cycle.assert_not_called()

    def test_allows_when_required_model_is_pulled(self, client):
        # tagless `gpt-4` matches the canonical `gpt-4:latest` (no family inference)
        with patch(
            "squadops.api.routes.cycles.cycles._pulled_model_names",
            new=AsyncMock(return_value=["gpt-4:latest"]),
        ):
            resp = client.post("/api/v1/projects/hello_squad/cycles", json=self._REQUEST)
        assert resp.status_code == 200
