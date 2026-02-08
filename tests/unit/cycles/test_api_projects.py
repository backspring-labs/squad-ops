"""
Tests for SIP-0064 project API routes.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.projects import router
from squadops.cycles.models import Project, ProjectNotFoundError

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


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
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_project_registry", mock_project_registry)
    return TestClient(app)


class TestListProjects:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "hello_squad"
        assert data[0]["tags"] == ["example"]


class TestGetProject:
    def test_returns_project(self, client):
        resp = client.get("/api/v1/projects/hello_squad")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == "hello_squad"

    def test_not_found(self, client, mock_project_registry):
        mock_project_registry.get_project.side_effect = ProjectNotFoundError(
            "Not found"
        )
        resp = client.get("/api/v1/projects/unknown")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"
        assert body["detail"]["error"]["details"] is None
