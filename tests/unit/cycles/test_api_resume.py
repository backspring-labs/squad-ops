"""
Tests for SIP-0079 resume and checkpoints API routes.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.runs import router
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import (
    Cycle,
    Run,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

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

_MULTI_WORKLOAD_CYCLE = Cycle(
    cycle_id="cyc_001",
    project_id="hello_squad",
    created_at=NOW,
    created_by="system",
    prd_ref=None,
    squad_profile_id="full-squad",
    squad_profile_snapshot_ref="sha256:abc",
    task_flow_policy=TaskFlowPolicy(mode="sequential"),
    build_strategy="fresh",
    applied_defaults={
        "workload_sequence": [
            {"type": "planning", "gate": "progress_plan_review"},
            {"type": "implementation"},
            {"type": "wrapup"},
        ],
    },
)

_PAUSED_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="paused",
    initiated_by="api",
    resolved_config_hash="hash123",
)

_FAILED_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="failed",
    initiated_by="api",
    resolved_config_hash="hash123",
)

_COMPLETED_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="completed",
    initiated_by="api",
    resolved_config_hash="hash123",
)

_CANCELLED_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="cancelled",
    initiated_by="api",
    resolved_config_hash="hash123",
)

_RUNNING_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="running",
    initiated_by="api",
    resolved_config_hash="hash123",
)

_CHECKPOINT = RunCheckpoint(
    run_id="run_001",
    checkpoint_index=2,
    completed_task_ids=("task_1", "task_2"),
    prior_outputs={"task_1": "result_1"},
    artifact_refs=("art_1",),
    plan_delta_refs=(),
    created_at=NOW,
)

_URL_PREFIX = "/api/v1/projects/hello_squad/cycles/cyc_001/runs"


@pytest.fixture
def mock_cycle_registry():
    mock = AsyncMock()
    mock.get_cycle.return_value = _CYCLE
    mock.get_run.return_value = _PAUSED_RUN
    mock.list_runs.return_value = [_PAUSED_RUN]
    mock.get_latest_checkpoint.return_value = _CHECKPOINT
    mock.list_checkpoints.return_value = [_CHECKPOINT]
    mock.update_run_status.return_value = _RUNNING_RUN
    return mock


@pytest.fixture
def client(mock_cycle_registry, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_cycle_registry)
    return TestClient(app)


class TestResumeRun:
    def test_resume_from_paused(self, client, mock_cycle_registry):
        """Paused run with checkpoint resumes to running."""
        resp = client.post(f"{_URL_PREFIX}/run_001/resume")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["run_id"] == "run_001"

    def test_resume_from_failed(self, client, mock_cycle_registry):
        """Failed run with checkpoint can also be resumed."""
        mock_cycle_registry.get_run.return_value = _FAILED_RUN
        mock_cycle_registry.list_runs.return_value = [_FAILED_RUN]
        resp = client.post(f"{_URL_PREFIX}/run_001/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_resume_without_checkpoint(self, client, mock_cycle_registry):
        """Resume without any checkpoint returns 422."""
        mock_cycle_registry.get_latest_checkpoint.return_value = None
        resp = client.post(f"{_URL_PREFIX}/run_001/resume")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_resume_completed_run(self, client, mock_cycle_registry):
        """Completed run cannot be resumed — 409."""
        mock_cycle_registry.get_run.return_value = _COMPLETED_RUN
        resp = client.post(f"{_URL_PREFIX}/run_001/resume")
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "RUN_TERMINAL"

    def test_resume_cancelled_run(self, client, mock_cycle_registry):
        """Cancelled run cannot be resumed — 409."""
        mock_cycle_registry.get_run.return_value = _CANCELLED_RUN
        resp = client.post(f"{_URL_PREFIX}/run_001/resume")
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "RUN_TERMINAL"

    def test_resume_terminal_cycle(self, client, mock_cycle_registry):
        """Run in a completed cycle cannot be resumed — 409."""
        completed_run = Run(
            run_id="run_002",
            cycle_id="cyc_001",
            run_number=2,
            status="completed",
            initiated_by="api",
            resolved_config_hash="hash123",
        )
        # The run being resumed is paused, but the cycle has a completed run
        mock_cycle_registry.list_runs.return_value = [completed_run]
        resp = client.post(f"{_URL_PREFIX}/run_001/resume")
        assert resp.status_code == 409

    def test_resume_allowed_when_cycle_paused_at_gate(self, client, mock_cycle_registry):
        """SIP-0083 D16: PAUSED cycle (gate_awaiting) allows resume."""
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        # Run 1 completed (planning), run 2 paused (impl) — gate_awaiting on index 0
        paused_impl_run = Run(
            run_id="run_002",
            cycle_id="cyc_001",
            run_number=2,
            status="paused",
            initiated_by="api",
            resolved_config_hash="hash123",
            workload_type="implementation",
        )
        mock_cycle_registry.get_run.return_value = paused_impl_run
        mock_cycle_registry.list_runs.return_value = [
            _COMPLETED_RUN,  # run_001: completed planning
            paused_impl_run,  # run_002: paused impl
        ]
        resp = client.post(f"{_URL_PREFIX}/run_002/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_resume_allowed_when_pending_workloads_remain(self, client, mock_cycle_registry):
        """SIP-0083 D5 rule 3: completed run + pending workloads → ACTIVE, not
        COMPLETED — resume is allowed."""
        mock_cycle_registry.get_cycle.return_value = _MULTI_WORKLOAD_CYCLE
        # Only run 1 completed, workloads 2+3 still pending — cycle is ACTIVE
        failed_run = Run(
            run_id="run_002",
            cycle_id="cyc_001",
            run_number=2,
            status="failed",
            initiated_by="api",
            resolved_config_hash="hash123",
            workload_type="implementation",
        )
        mock_cycle_registry.get_run.return_value = failed_run
        mock_cycle_registry.list_runs.return_value = [
            _COMPLETED_RUN,  # run_001: completed planning
            failed_run,       # run_002: failed impl (wants resume)
        ]
        resp = client.post(f"{_URL_PREFIX}/run_002/resume")
        assert resp.status_code == 200


class TestListCheckpoints:
    def test_list_checkpoints(self, client, mock_cycle_registry):
        """Returns checkpoint summaries."""
        resp = client.get(f"{_URL_PREFIX}/run_001/checkpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["checkpoint_index"] == 2
        assert data[0]["completed_task_count"] == 2
        assert data[0]["artifact_ref_count"] == 1

    def test_list_checkpoints_empty(self, client, mock_cycle_registry):
        """Returns empty list when no checkpoints exist."""
        mock_cycle_registry.list_checkpoints.return_value = []
        resp = client.get(f"{_URL_PREFIX}/run_001/checkpoints")
        assert resp.status_code == 200
        assert resp.json() == []
