"""Tests for SIP-0076 API changes (Phase 2).

Covers ACs 5, 8, 9, 10, 14, 21.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.dtos import (
    GateDecisionRequest,
)
from squadops.api.routes.cycles.mapping import artifact_to_response, run_to_response
from squadops.api.routes.cycles.runs import router as runs_router
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    Run,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_CYCLE = Cycle(
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


# ---------------------------------------------------------------------------
# DTO serialization (ACs 5, 8, 9)
# ---------------------------------------------------------------------------


class TestGateDecisionRequestExpanded:
    """AC 5: GateDecisionRequest accepts all four decision values."""

    @pytest.mark.parametrize(
        "value",
        ["approved", "approved_with_refinements", "returned_for_revision", "rejected"],
    )
    def test_valid_decisions(self, value):
        req = GateDecisionRequest(decision=value)
        assert req.decision == value

    def test_unknown_decision_rejected(self):
        with pytest.raises(Exception):
            GateDecisionRequest(decision="maybe")


# ---------------------------------------------------------------------------
# Mapping functions (AC 14)
# ---------------------------------------------------------------------------


class TestRunToResponseMapping:
    """AC 14: run_to_response maps workload_type."""

    def test_maps_workload_type(self):
        run = Run(
            run_id="r1",
            cycle_id="c1",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="h",
            workload_type="implementation",
        )
        resp = run_to_response(run)
        assert resp.workload_type == "implementation"

    def test_maps_none_workload_type(self):
        run = Run(
            run_id="r1",
            cycle_id="c1",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="h",
        )
        resp = run_to_response(run)
        assert resp.workload_type is None


class TestArtifactToResponseMapping:
    """AC 14: artifact_to_response maps promotion_status."""

    def test_maps_promotion_status(self):
        artifact = ArtifactRef(
            artifact_id="a1",
            project_id="p1",
            artifact_type="code",
            filename="f.py",
            content_hash="h",
            size_bytes=10,
            media_type="text/plain",
            created_at=NOW,
            promotion_status="promoted",
        )
        resp = artifact_to_response(artifact)
        assert resp.promotion_status == "promoted"

    def test_maps_default_working(self):
        artifact = ArtifactRef(
            artifact_id="a1",
            project_id="p1",
            artifact_type="code",
            filename="f.py",
            content_hash="h",
            size_bytes=10,
            media_type="text/plain",
            created_at=NOW,
        )
        resp = artifact_to_response(artifact)
        assert resp.promotion_status == "working"


# ---------------------------------------------------------------------------
# Route-level tests (ACs 10, 21)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cycle_registry():
    mock = AsyncMock()
    mock.get_cycle.return_value = _CYCLE
    mock.list_runs.return_value = []
    mock.create_run.side_effect = lambda r: r
    return mock


@pytest.fixture
def client(mock_cycle_registry, monkeypatch):
    app = FastAPI()
    app.include_router(runs_router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_cycle_registry)
    return TestClient(app)


class TestListRunsWorkloadFilter:
    """AC 10: list_runs supports ?workload_type= filter."""

    def test_no_filter(self, client, mock_cycle_registry):
        run = Run(
            run_id="r1",
            cycle_id="cyc_001",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="h",
        )
        mock_cycle_registry.list_runs.return_value = [run]
        resp = client.get("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        mock_cycle_registry.list_runs.assert_called_once_with("cyc_001", workload_type=None)

    def test_with_workload_type_filter(self, client, mock_cycle_registry):
        resp = client.get("/api/v1/projects/hello_squad/cycles/cyc_001/runs?workload_type=framing")
        assert resp.status_code == 200
        mock_cycle_registry.list_runs.assert_called_once_with("cyc_001", workload_type="framing")


class TestCreateRunWorkloadType:
    """AC 21: workload_type input validation on create_run."""

    def test_create_run_without_workload_type(self, client):
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["workload_type"] is None

    def test_create_run_with_workload_type(self, client):
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs?workload_type=framing"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["workload_type"] == "framing"
