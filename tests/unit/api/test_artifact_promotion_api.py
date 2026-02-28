"""Tests for SIP-0076 artifact promotion API routes (Phase 3).

Covers ACs 11, 16, 19 at route level.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.artifacts import router
from squadops.cycles.models import (
    ArtifactNotFoundError,
    ArtifactRef,
    Cycle,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_WORKING_ARTIFACT = ArtifactRef(
    artifact_id="art_001",
    project_id="proj_001",
    artifact_type="code",
    filename="main.py",
    content_hash="sha256:abc",
    size_bytes=100,
    media_type="text/plain",
    created_at=NOW,
    cycle_id="cyc_001",
    run_id="run_001",
    promotion_status="working",
)

_PROMOTED_ARTIFACT = ArtifactRef(
    artifact_id="art_001",
    project_id="proj_001",
    artifact_type="code",
    filename="main.py",
    content_hash="sha256:abc",
    size_bytes=100,
    media_type="text/plain",
    created_at=NOW,
    cycle_id="cyc_001",
    run_id="run_001",
    promotion_status="promoted",
)

_CYCLE = Cycle(
    cycle_id="cyc_001",
    project_id="proj_001",
    created_at=NOW,
    created_by="system",
    prd_ref=None,
    squad_profile_id="full-squad",
    squad_profile_snapshot_ref="sha256:abc",
    task_flow_policy=TaskFlowPolicy(mode="sequential"),
    build_strategy="incremental",
)


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.promote_artifact.return_value = _PROMOTED_ARTIFACT
    mock.get_metadata.return_value = _WORKING_ARTIFACT
    mock.list_artifacts.return_value = [_WORKING_ARTIFACT]
    return mock


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_cycle.return_value = _CYCLE
    return mock


@pytest.fixture
def client(mock_vault, mock_registry, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_artifact_vault", mock_vault)
    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_registry)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Promotion endpoint (AC 11)
# ---------------------------------------------------------------------------


class TestPromoteArtifactRoute:
    def test_promote_returns_200(self, client):
        resp = client.post("/api/v1/artifacts/art_001/promote")
        assert resp.status_code == 200
        body = resp.json()
        assert body["promotion_status"] == "promoted"

    def test_promote_already_promoted_returns_200(self, client, mock_vault):
        mock_vault.promote_artifact.return_value = _PROMOTED_ARTIFACT
        resp = client.post("/api/v1/artifacts/art_001/promote")
        assert resp.status_code == 200

    def test_promote_not_found_returns_404(self, client, mock_vault):
        mock_vault.promote_artifact.side_effect = ArtifactNotFoundError("not found")
        resp = client.post("/api/v1/artifacts/nonexistent/promote")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Artifact list filter (AC 16)
# ---------------------------------------------------------------------------


class TestArtifactListFilterRoute:
    def test_list_with_promotion_status_filter(self, client, mock_vault):
        resp = client.get("/api/v1/projects/proj_001/artifacts?promotion_status=working")
        assert resp.status_code == 200
        mock_vault.list_artifacts.assert_called_once_with(
            project_id="proj_001",
            artifact_type=None,
            promotion_status="working",
        )

    def test_list_without_filter(self, client, mock_vault):
        resp = client.get("/api/v1/projects/proj_001/artifacts")
        assert resp.status_code == 200
        mock_vault.list_artifacts.assert_called_once_with(
            project_id="proj_001",
            artifact_type=None,
            promotion_status=None,
        )

    def test_invalid_promotion_status_returns_422(self, client):
        resp = client.get("/api/v1/projects/proj_001/artifacts?promotion_status=invalid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Baseline rejects working artifacts (AC 19)
# ---------------------------------------------------------------------------


class TestBaselineRejectsWorking:
    def test_baseline_rejects_working_artifact(self, client, mock_vault):
        """D6: set_baseline rejects working artifacts."""
        mock_vault.get_metadata.return_value = _WORKING_ARTIFACT
        resp = client.post(
            "/api/v1/projects/proj_001/baseline/code",
            json={"artifact_id": "art_001"},
        )
        assert resp.status_code == 422

    def test_baseline_accepts_promoted_artifact(self, client, mock_vault):
        """D6: set_baseline succeeds for promoted artifacts."""
        mock_vault.get_metadata.return_value = _PROMOTED_ARTIFACT
        resp = client.post(
            "/api/v1/projects/proj_001/baseline/code",
            json={"artifact_id": "art_001"},
        )
        assert resp.status_code == 200
