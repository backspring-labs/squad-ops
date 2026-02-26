"""
Tests for project PRD content endpoint (SIP-0074 §3.5).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.projects import router
from squadops.cycles.models import Project, ProjectNotFoundError

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_project_registry():
    return AsyncMock()


@pytest.fixture
def client(mock_project_registry, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_project_registry", mock_project_registry)
    return TestClient(app)


class TestGetProjectPrdContent:
    """Tests for GET /api/v1/projects/{project_id}/prd-content."""

    def test_returns_prd_content(self, client, mock_project_registry, tmp_path):
        prd_file = tmp_path / "prd.md"
        prd_file.write_text("# My PRD\n\nBuild a widget.")

        mock_project_registry.get_project.return_value = Project(
            project_id="test_proj",
            name="Test",
            description="Test project",
            created_at=NOW,
            prd_path=str(prd_file),
        )

        resp = client.get("/api/v1/projects/test_proj/prd-content")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert resp.text == "# My PRD\n\nBuild a widget."

    def test_404_when_no_prd_path(self, client, mock_project_registry):
        mock_project_registry.get_project.return_value = Project(
            project_id="test_proj",
            name="Test",
            description="Test project",
            created_at=NOW,
            prd_path=None,
        )

        resp = client.get("/api/v1/projects/test_proj/prd-content")
        assert resp.status_code == 404
        assert "No PRD file configured" in resp.json()["detail"]

    def test_404_when_file_not_found(self, client, mock_project_registry, tmp_path):
        mock_project_registry.get_project.return_value = Project(
            project_id="test_proj",
            name="Test",
            description="Test project",
            created_at=NOW,
            prd_path=str(tmp_path / "nonexistent.md"),
        )

        resp = client.get("/api/v1/projects/test_proj/prd-content")
        assert resp.status_code == 404
        assert "PRD file not found" in resp.json()["detail"]

    def test_404_when_project_not_found(self, client, mock_project_registry):
        mock_project_registry.get_project.side_effect = ProjectNotFoundError("Not found")

        resp = client.get("/api/v1/projects/unknown/prd-content")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "PROJECT_NOT_FOUND"

    def test_returns_large_prd(self, client, mock_project_registry, tmp_path):
        """Endpoint should return content regardless of size — UI handles constraints."""
        prd_file = tmp_path / "big_prd.md"
        content = "# Big PRD\n" + "Lorem ipsum. " * 5000
        prd_file.write_text(content)

        mock_project_registry.get_project.return_value = Project(
            project_id="test_proj",
            name="Test",
            description="Test project",
            created_at=NOW,
            prd_path=str(prd_file),
        )

        resp = client.get("/api/v1/projects/test_proj/prd-content")
        assert resp.status_code == 200
        assert resp.text == content
