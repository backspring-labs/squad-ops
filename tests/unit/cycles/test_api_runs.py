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
from squadops.runtime.models import FocusLease

pytestmark = [pytest.mark.domain_orchestration]

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

_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="queued",
    initiated_by="api",
    resolved_config_hash="hash123",
)


def _focus_lease(agent_id: str, owner_ref: str) -> FocusLease:
    return FocusLease(
        lease_id=f"lease-{agent_id}",
        agent_id=agent_id,
        owner_type="cycle",
        owner_ref=owner_ref,
        acquired_at=NOW,
        expires_at=None,
        renewal_policy="ttl",
        interruptibility="high",
        recall_policy="graceful",
        released_at=None,
        idempotency_key=f"cycle:{owner_ref}:{agent_id}",
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
def mock_flow_executor():
    return AsyncMock()


@pytest.fixture
def client(mock_cycle_registry, mock_artifact_vault, mock_flow_executor, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_cycle_registry", mock_cycle_registry)
    monkeypatch.setattr(deps_mod, "_artifact_vault", mock_artifact_vault)
    monkeypatch.setattr(deps_mod, "_flow_executor", mock_flow_executor)
    return TestClient(app)


class TestCreateRun:
    def test_creates_retry_run(self, client):
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_number"] == 2
        assert body["initiated_by"] == "retry"
        assert body["status"] == "queued"

    def test_retry_run_is_dispatched_for_execution(self, client, mock_flow_executor):
        """#133: a retry must actually run — the route enqueues execute_cycle for
        the new run (not just create a queued record that never executes).
        TestClient runs background tasks after the response."""
        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs")
        assert resp.status_code == 200
        new_run_id = resp.json()["run_id"]

        mock_flow_executor.execute_cycle.assert_awaited_once_with("cyc_001", new_run_id, "full")


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

    def test_cancel_propagates_to_prefect(self, client, monkeypatch):
        """#77: cancelling a single run transitions its still-running Prefect
        flow run to CANCELLED."""
        import squadops.api.runtime.deps as deps_mod

        fake_tracker = AsyncMock()
        fake_tracker.find_active_flow_run_ids.return_value = ["flowrun-abc"]
        monkeypatch.setattr(deps_mod, "_workflow_tracker", fake_tracker)

        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/cancel")

        assert resp.status_code == 200
        assert resp.json()["prefect_flow_runs_cancelled"] == 1
        fake_tracker.find_active_flow_run_ids.assert_awaited_once_with(
            ["hello_squad/cyc_001/run_001"]
        )
        fake_tracker.set_flow_run_state.assert_awaited_once_with(
            "flowrun-abc", "CANCELLED", "Cancelled"
        )

    def test_cancel_releases_the_runs_focus_leases(self, client, monkeypatch):
        """#529: cancellation bypasses the executor's finalize path, so without
        this sweep the run's cycle leases stay held and the next cycle recruiting
        any of those agents deadlocks on focus_lease_conflict."""
        import squadops.api.runtime.deps as deps_mod

        held = _focus_lease("data", "run_001")
        lease_port = AsyncMock()
        lease_port.list_active_leases.return_value = (held,)
        lease_port.get_current_lease.return_value = None  # the transition cleared it
        coordinator = AsyncMock()
        monkeypatch.setattr(deps_mod, "_focus_lease_port", lease_port)
        monkeypatch.setattr(deps_mod, "_runtime_coordinator", coordinator)

        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/cancel")

        assert resp.status_code == 200
        assert resp.json()["focus_leases_released"] == 1
        # Scoped to the cancelled run's own leases, and the agent goes back to
        # ambient — releasing the lease alone would leave it pinned in `cycle`.
        lease_port.list_active_leases.assert_awaited_once_with(owner_ref="run_001")
        agent_id, target_mode = coordinator.request_transition.await_args.args[:2]
        assert (agent_id, target_mode) == ("data", "ambient")

    def test_cancel_survives_a_lease_sweep_failure(self, client, monkeypatch):
        """Registry cancellation is the source of truth (the #77 contract): a
        lease-release failure must not turn a cancel into a 500."""
        import squadops.api.runtime.deps as deps_mod

        lease_port = AsyncMock()
        lease_port.list_active_leases.side_effect = RuntimeError("db down")
        monkeypatch.setattr(deps_mod, "_focus_lease_port", lease_port)
        monkeypatch.setattr(deps_mod, "_runtime_coordinator", AsyncMock())

        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/cancel")

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["focus_leases_released"] == 0

    def test_cancel_without_lease_wiring_still_succeeds(self, client, monkeypatch):
        """A pool-less deployment has no leases to release; cancel must not 500."""
        import squadops.api.runtime.deps as deps_mod

        monkeypatch.setattr(deps_mod, "_focus_lease_port", None)
        monkeypatch.setattr(deps_mod, "_runtime_coordinator", None)

        resp = client.post("/api/v1/projects/hello_squad/cycles/cyc_001/runs/run_001/cancel")

        assert resp.status_code == 200
        assert resp.json()["focus_leases_released"] == 0


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
