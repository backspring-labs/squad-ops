"""
Tests for SIP-0064 artifact API routes.
"""

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

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_ARTIFACT = ArtifactRef(
    artifact_id="art_001",
    project_id="hello_squad",
    artifact_type="prd",
    filename="prd-v1.md",
    content_hash="sha256:abc",
    size_bytes=100,
    media_type="text/markdown",
    created_at=NOW,
    vault_uri="/data/artifacts/art_001/prd-v1.md",
)


@pytest.fixture
def mock_artifact_vault():
    mock = AsyncMock()
    mock.store.return_value = _ARTIFACT
    mock.get_metadata.return_value = _ARTIFACT
    mock.retrieve.return_value = (_ARTIFACT, b"# PRD v1")
    mock.list_artifacts.return_value = [_ARTIFACT]
    mock.set_baseline.return_value = None
    mock.get_baseline.return_value = _ARTIFACT
    mock.list_baselines.return_value = {"prd": _ARTIFACT}
    return mock


@pytest.fixture
def mock_cycle_registry():
    mock = AsyncMock()
    cycle = Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="incremental",
    )
    mock.get_cycle.return_value = cycle
    return mock


@pytest.fixture
def client(mock_artifact_vault, mock_cycle_registry, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_artifact_vault", mock_artifact_vault)
    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_cycle_registry)
    return TestClient(app)


class TestIngestArtifact:
    def test_ingest_multipart(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/artifacts/ingest",
            files={"file": ("prd.md", b"# PRD content", "text/markdown")},
            data={
                "artifact_type": "prd",
                "filename": "prd.md",
                "media_type": "text/markdown",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["artifact_type"] == "prd"
        assert body["artifact_id"] == "art_001"

    def test_ingest_oversized_file(self, client, mock_artifact_vault):
        # 51 MB content
        big_content = b"x" * (51 * 1024 * 1024)
        resp = client.post(
            "/api/v1/projects/hello_squad/artifacts/ingest",
            files={"file": ("big.bin", big_content, "application/octet-stream")},
            data={
                "artifact_type": "code",
                "filename": "big.bin",
                "media_type": "application/octet-stream",
            },
        )
        assert resp.status_code == 413


class TestGetArtifactMetadata:
    def test_returns_metadata(self, client):
        resp = client.get("/api/v1/artifacts/art_001")
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == "art_001"

    def test_not_found(self, client, mock_artifact_vault):
        mock_artifact_vault.get_metadata.side_effect = ArtifactNotFoundError("Not found")
        resp = client.get("/api/v1/artifacts/nonexistent")
        assert resp.status_code == 404


class TestListProjectArtifacts:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/projects/hello_squad/artifacts")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_type(self, client):
        resp = client.get("/api/v1/projects/hello_squad/artifacts?artifact_type=prd")
        assert resp.status_code == 200


class TestBaselinePromotion:
    def test_promote_incremental(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/baseline/prd",
            json={"artifact_id": "art_001"},
        )
        assert resp.status_code == 200

    def test_promote_fresh_rejected(self, client, mock_cycle_registry):
        # Change cycle to fresh build strategy
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
        # Set artifact with cycle_id so enforcement triggers

        from squadops.cycles.models import ArtifactRef

        art_with_cycle = ArtifactRef(
            artifact_id="art_001",
            project_id="hello_squad",
            artifact_type="prd",
            filename="prd.md",
            content_hash="h",
            size_bytes=10,
            media_type="text/markdown",
            created_at=NOW,
            cycle_id="cyc_001",
        )

        import squadops.api.runtime.deps as deps_mod

        deps_mod._artifact_vault.get_metadata.return_value = art_with_cycle

        resp = client.post(
            "/api/v1/projects/hello_squad/baseline/prd",
            json={"artifact_id": "art_001"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "BASELINE_NOT_ALLOWED"


class TestGetBaseline:
    def test_returns_baseline(self, client):
        resp = client.get("/api/v1/projects/hello_squad/baseline/prd")
        assert resp.status_code == 200
        assert resp.json()["artifact_id"] == "art_001"


class TestListBaselines:
    def test_returns_baselines(self, client):
        resp = client.get("/api/v1/projects/hello_squad/baseline")
        assert resp.status_code == 200
        data = resp.json()
        assert "prd" in data
