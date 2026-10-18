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
