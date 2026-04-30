"""
Tests for SIP-0064 run API routes.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.runs import router
from squadops.cycles.models import (
    Cycle,
    GateAlreadyDecidedError,
    GateDecision,
    Run,
    RunNotFoundError,
    RunTerminalError,
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

_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="queued",
    initiated_by="api",
    resolved_config_hash="hash123",
)


@pytest.fixture
def mock_cycle_registry():
    mock = AsyncMock()
    mock.get_cycle.return_value = _CYCLE
    mock.list_runs.return_value = [_RUN]
    mock.create_run.side_effect = lambda r: r
    mock.get_run.return_value = _RUN
    mock.cancel_run.return_value = None
    return mock


@pytest.fixture
def mock_artifact_vault():
    mock = AsyncMock()
    mock.list_artifacts.return_value = []
    return mock


@pytest.fixture
def client(mock_cycle_registry, mock_artifact_vault, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_cycle_registry)
    monkeypatch.setattr(deps_mod, "_artifact_vault", mock_artifact_vault)
    return TestClient(app)


class TestCreateRun:
    def test_creates_retry_run(self, client):
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_number"] == 2
        assert body["initiated_by"] == "retry"
        assert body["status"] == "queued"


class TestListRuns:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["run_id"] == "run_001"


class TestGetRun:
    def test_returns_run(self, client):
        resp = client.get("/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run_001"

    def test_not_found(self, client, mock_cycle_registry):
        mock_cycle_registry.get_run.side_effect = RunNotFoundError("Not found")
        resp = client.get("/api/v1/projects/hello_squad/cycles/cyc_001/runs/nonexistent")
        assert resp.status_code == 404


class TestCancelRun:
    def test_cancel_success(self, client):
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


class TestGateDecision:
    def test_approve_gate(self, client, mock_cycle_registry):
        updated_run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="hash123",
            gate_decisions=(
                GateDecision(
                    gate_name="qa_review",
                    decision="approved",
                    decided_by="system",
                    decided_at=NOW,
                ),
            ),
        )
        mock_cycle_registry.record_gate_decision.return_value = updated_run

        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/gates/qa_review",
            json={"decision": "approved"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["gate_decisions"]) == 1
        assert body["gate_decisions"][0]["decision"] == "approved"

    def test_double_approve_idempotent(self, client, mock_cycle_registry):
        updated_run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="hash123",
            gate_decisions=(
                GateDecision(
                    gate_name="qa_review",
                    decision="approved",
                    decided_by="system",
                    decided_at=NOW,
                ),
            ),
        )
        mock_cycle_registry.record_gate_decision.return_value = updated_run

        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/gates/qa_review",
            json={"decision": "approved"},
        )
        assert resp.status_code == 200

    def test_conflicting_decision(self, client, mock_cycle_registry):
        mock_cycle_registry.record_gate_decision.side_effect = GateAlreadyDecidedError(
            "Already decided"
        )
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/gates/qa_review",
            json={"decision": "rejected"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "GATE_ALREADY_DECIDED"

    def test_terminal_run(self, client, mock_cycle_registry):
        mock_cycle_registry.record_gate_decision.side_effect = RunTerminalError("Terminal")
        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/gates/qa_review",
            json={"decision": "approved"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"]["code"] == "RUN_TERMINAL"

    def test_approve_promotes_working_artifacts(
        self, client, mock_cycle_registry, mock_artifact_vault
    ):
        """SIP-0086: approved gate promotes all working artifacts for the run."""
        from squadops.cycles.models import ArtifactRef

        working_doc = ArtifactRef(
            artifact_id="art_doc",
            project_id="hello_squad",
            artifact_type="document",
            filename="plan.md",
            content_hash="h1",
            size_bytes=10,
            media_type="text/markdown",
            created_at=NOW,
            cycle_id="cyc_001",
            run_id="run_001",
            promotion_status="working",
        )
        working_manifest = ArtifactRef(
            artifact_id="art_manifest",
            project_id="hello_squad",
            artifact_type="control_implementation_plan",
            filename="implementation_plan.yaml",
            content_hash="h2",
            size_bytes=20,
            media_type="text/yaml",
            created_at=NOW,
            cycle_id="cyc_001",
            run_id="run_001",
            promotion_status="working",
        )
        already = ArtifactRef(
            artifact_id="art_already",
            project_id="hello_squad",
            artifact_type="document",
            filename="x.md",
            content_hash="h3",
            size_bytes=5,
            media_type="text/markdown",
            created_at=NOW,
            cycle_id="cyc_001",
            run_id="run_001",
            promotion_status="promoted",
        )
        mock_artifact_vault.list_artifacts.return_value = [
            working_doc,
            working_manifest,
            already,
        ]
        updated_run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="hash123",
            gate_decisions=(
                GateDecision(
                    gate_name="progress_plan_review",
                    decision="approved",
                    decided_by="system",
                    decided_at=NOW,
                ),
            ),
        )
        mock_cycle_registry.record_gate_decision.return_value = updated_run

        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/gates/progress_plan_review",
            json={"decision": "approved"},
        )

        assert resp.status_code == 200
        promoted_ids = [
            call.args[0] for call in mock_artifact_vault.promote_artifact.await_args_list
        ]
        assert promoted_ids == ["art_doc", "art_manifest"]

    def test_reject_does_not_promote(self, client, mock_cycle_registry, mock_artifact_vault):
        """Only approved decisions trigger promotion."""
        updated_run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="hash123",
            gate_decisions=(
                GateDecision(
                    gate_name="progress_plan_review",
                    decision="rejected",
                    decided_by="system",
                    decided_at=NOW,
                ),
            ),
        )
        mock_cycle_registry.record_gate_decision.return_value = updated_run

        resp = client.post(
            "/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/gates/progress_plan_review",
            json={"decision": "rejected"},
        )

        assert resp.status_code == 200
        mock_artifact_vault.promote_artifact.assert_not_awaited()
