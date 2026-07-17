"""Tests for SIP-0076 API changes (Phase 2).

Covers ACs 5, 8, 9, 10, 14, 21.
"""

from __future__ import annotations

from dataclasses import replace
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
    squad_profile_id="full",
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
    # create_run now enqueues execution (#133), so a flow executor must be wired.
    monkeypatch.setattr(deps_mod, "_flow_executor", AsyncMock())
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
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs?workload_type=framing")
        assert resp.status_code == 200
        body = resp.json()
        assert body["workload_type"] == "framing"


_MULTI_WORKLOAD_CYCLE = replace(
    _CYCLE,
    applied_defaults={
        "workload_sequence": [
            {"type": "framing", "workload_ref": "planning_workload"},
            {"type": "implementation", "workload_ref": "implementation_workload"},
        ]
    },
)


def _existing_run(run_number: int, status: str, workload_type: str | None = None) -> Run:
    return Run(
        run_id=f"run_{run_number:03d}",
        cycle_id="cyc_001",
        run_number=run_number,
        status=status,
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=workload_type,
    )


class TestCreateRunPositionalResolution:
    """#433: an unspecified workload_type resolves positionally (D14), never
    silently to None on a multi-workload cycle."""

    def test_retry_resolves_next_workload_positionally(self, client, mock_cycle_registry):
        # The incident shape: framing completed, retry meant for implementation.
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        mock_cycle_registry.list_runs.return_value = [
            _existing_run(1, "completed", "framing"),
        ]
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        assert resp.json()["workload_type"] == "implementation"

    def test_cancelled_runs_do_not_advance_position(self, client, mock_cycle_registry):
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        mock_cycle_registry.list_runs.return_value = [
            _existing_run(1, "completed", "framing"),
            _existing_run(2, "cancelled", "implementation"),
        ]
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        assert resp.json()["workload_type"] == "implementation"

    def test_all_prior_runs_cancelled_resolves_position_zero(self, client, mock_cycle_registry):
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        mock_cycle_registry.list_runs.return_value = [
            _existing_run(1, "cancelled", "framing"),
            _existing_run(2, "cancelled", None),
        ]
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        assert resp.json()["workload_type"] == "framing"

    def test_out_of_bounds_position_rejected(self, client, mock_cycle_registry):
        # Sequence exhausted: rejecting beats a silent None-typed run (the
        # legacy plan shape + no artifact seeding).
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        mock_cycle_registry.list_runs.return_value = [
            _existing_run(1, "completed", "framing"),
            _existing_run(2, "failed", "implementation"),
        ]
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 422
        error = resp.json()["detail"]["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "Cancel the run being retried" in error["message"]

    def test_explicit_workload_type_bypasses_resolution(self, client, mock_cycle_registry):
        # Same exhausted-sequence state as above: an explicit param must win.
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        mock_cycle_registry.list_runs.return_value = [
            _existing_run(1, "completed", "framing"),
            _existing_run(2, "failed", "implementation"),
        ]
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs?workload_type=implementation"
        )
        assert resp.status_code == 200
        assert resp.json()["workload_type"] == "implementation"

    def test_legacy_cycle_with_runs_stays_none(self, client, mock_cycle_registry):
        # No workload_sequence: legacy cycles must keep the None type that
        # selects their legacy plan path, regardless of run count.
        mock_cycle_registry.list_runs.return_value = [
            _existing_run(1, "completed"),
            _existing_run(2, "failed"),
            _existing_run(3, "completed"),
        ]
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        assert resp.json()["workload_type"] is None
