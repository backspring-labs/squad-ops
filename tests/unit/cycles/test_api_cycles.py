"""
Tests for SIP-0064 cycle API routes.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

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

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


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


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    profile = SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All agents",
        version=1,
        agents=(
            AgentProfileEntry(
                agent_id="max", role="lead", model="gpt-4", enabled=True
            ),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc123")
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
                "squad_profile_id": "full-squad",
                "task_flow_policy": {"mode": "sequential"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "hello_squad"
        assert body["run_number"] == 1
        assert body["status"] == "queued"
        assert body["squad_profile_id"] == "full-squad"
        assert "cycle_id" in body
        assert "run_id" in body

    def test_create_cycle_prd_ref_none(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={
                "prd_ref": None,
                "squad_profile_id": "full-squad",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["prd_ref"] is None

    def test_create_cycle_unknown_project(self, client, mock_project_registry):
        mock_project_registry.get_project.side_effect = ProjectNotFoundError(
            "Not found"
        )
        resp = client.post(
            "/api/v1/projects/unknown/cycles",
            json={"squad_profile_id": "full-squad"},
        )
        assert resp.status_code == 404

    def test_create_cycle_extra_fields_rejected(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles",
            json={
                "squad_profile_id": "full-squad",
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
            squad_profile_id="full-squad",
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
