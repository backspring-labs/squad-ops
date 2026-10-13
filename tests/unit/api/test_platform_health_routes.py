"""
Unit tests for platform health routes (health endpoint migration).
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.platform_health import router


@pytest.fixture()
def mock_health_checker():
    """Create a mock HealthChecker."""
    hc = MagicMock()
    hc.pg_pool = MagicMock()
    hc._heartbeat_is_fresh = MagicMock(return_value=True)
    hc._get_display_name = MagicMock(return_value="Max")
    hc.deployed_revisions = AsyncMock(return_value=None)  # #1720: no deploy recorded

    hc.check_rabbitmq = AsyncMock(return_value={"component": "RabbitMQ", "status": "online"})
    hc.check_postgres = AsyncMock(return_value={"component": "PostgreSQL", "status": "online"})
    hc.check_redis = AsyncMock(return_value={"component": "Redis", "status": "online"})
    hc.check_prefect = AsyncMock(return_value={"component": "Prefect Server", "status": "online"})
    hc.check_prometheus = AsyncMock(return_value={"component": "Prometheus", "status": "offline"})
    hc.check_grafana = AsyncMock(return_value={"component": "Grafana", "status": "online"})
    hc.check_otel_collector = AsyncMock(
        return_value={"component": "OTel Collector", "status": "online"}
    )
    hc.check_langfuse = AsyncMock(return_value={"component": "LangFuse", "status": "online"})
    hc.check_keycloak = AsyncMock(return_value={"component": "Keycloak", "status": "online"})

    hc.get_agent_status = AsyncMock(
        return_value=[
            {
                "agent_id": "max",
                "agent_name": "Max",
                "network_status": "online",
                "lifecycle_state": "READY",
            },
            {
                "agent_id": "neo",
                "agent_name": "Neo",
                "network_status": "online",
                "lifecycle_state": "WORKING",
            },
        ]
    )

    hc.update_agent_status_in_db = AsyncMock(return_value={"status": "updated", "agent_id": "max"})

    return hc


@pytest.fixture()
def client(mock_health_checker):
    """FastAPI test client with platform_health routes."""
    app = FastAPI()
    app.include_router(router)

    with patch(
        "squadops.api.routes.platform_health._get_health_checker", return_value=mock_health_checker
    ):
        yield TestClient(app)


class TestHealthInfra:
    def test_get_infra_returns_list(self, client, mock_health_checker):
        resp = client.get("/health/infra")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 9
        assert data[0]["component"] == "RabbitMQ"

    def test_get_infra_calls_all_probes(self, client, mock_health_checker):
        client.get("/health/infra")
        mock_health_checker.check_rabbitmq.assert_awaited_once()
        mock_health_checker.check_postgres.assert_awaited_once()
        mock_health_checker.check_redis.assert_awaited_once()
        mock_health_checker.check_keycloak.assert_awaited_once()


class TestHealthAgents:
    def test_get_agents_returns_list(self, client, mock_health_checker):
        resp = client.get("/health/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["agent_id"] == "max"

    def test_get_agents_calls_get_agent_status(self, client, mock_health_checker):
        client.get("/health/agents")
        mock_health_checker.get_agent_status.assert_awaited_once()


class TestAgentStatusById:
    def test_get_agent_status_found(self, client, mock_health_checker):
        # The route LEFT JOINs agent_runtime_state, so the row carries mode +
        # runtime_status (the canonical health signal, #231).
        mock_row = {
            "agent_id": "max",
            "lifecycle_state": "READY",
            "version": "0.9.7",
            "revision": "7acc2bc1",
            "tps": 5,
            "memory_count": 10,
            "last_heartbeat": datetime(2026, 2, 16, 12, 0, 0),
            "current_task_id": None,
            "mode": "cycle",
            "runtime_status": "online",
        }
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn
        # #1720: the latest deploy recorded max at another commit — max changed since.
        mock_health_checker.deployed_revisions = AsyncMock(return_value={"max": "ccc9475d"})

        resp = client.get("/health/agents/status/max")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "max"
        assert (data["revision"], data["deployed_revision"], data["revision_matches_deploy"]) == (
            "7acc2bc1",
            "ccc9475d",
            False,
        )
        assert data["lifecycle_state"] == "READY"
        # #231: the single-agent route now carries the canonical health + posture
        # at parity with the list route, with network_status demoted to back-compat.
        assert data["runtime_status"] == "online"
        assert data["mode"] == "cycle"
        assert "network_status" not in data  # retired (#305 Part B)

    def test_get_agent_status_not_found(self, client, mock_health_checker):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn

        resp = client.get("/health/agents/status/unknown")
        assert resp.status_code == 404


class TestHealthLaneIsReadOnly:
    """#326: agent-status writes moved to /api/v1/agents/status. The /health
    lane is unauthenticated, so a write route reappearing here is a security
    regression — these paths must not resolve at all."""

    def test_post_agent_status_gone_from_health_lane(self, client):
        resp = client.post(
            "/health/agents/status",
            json={"agent_id": "max", "lifecycle_state": "READY"},
        )
        assert resp.status_code == 404

    def test_put_agent_status_gone_from_health_lane(self, client):
        resp = client.put(
            "/health/agents/status/max",
            json={"lifecycle_state": "WORKING"},
        )
        # 405, not 404: the path still exists for GET (single-agent status
        # probe); only the write method must be gone.
        assert resp.status_code == 405

    def test_health_router_exposes_only_safe_methods(self):
        """Structural ratchet for the lane rule (#218): every route on the
        /health router must be GET-only. Catches any future write route added
        to this router before the middleware allowlist would expose it."""
        from squadops.api.routes.platform_health import router as health_router

        for route in health_router.routes:
            methods = getattr(route, "methods", set()) or set()
            unsafe = methods - {"GET", "HEAD"}
            assert not unsafe, (
                f"Route {route.path} exposes unsafe methods {unsafe} on the "
                "unauthenticated /health lane — writable resources belong on "
                "/api/v1 (see routes/agent_status.py, #326)"
            )


class TestAgentCurrentActivity:
    """SIP-0089 §4.7: GET /health/agents/{id}/activity."""

    def test_activity_found_returns_200(self, client, mock_health_checker):
        """Bug class: a working agent's current activity must be served as 200 with
        the activity body (the read the CLI/console render)."""
        mock_health_checker.get_current_activity = AsyncMock(
            return_value={"runtime_activity_id": "act-1", "state": "running", "mode": "cycle"}
        )

        resp = client.get("/health/agents/max/activity")

        assert resp.status_code == 200
        assert resp.json()["runtime_activity_id"] == "act-1"
        # agent_id is lower-cased to match how rows are stored.
        mock_health_checker.get_current_activity.assert_awaited_once_with("max")

    def test_activity_absent_returns_404(self, client, mock_health_checker):
        """Bug class: an idle agent (no active activity) must be a clean 404, which
        the CLI maps to 'idle' — not a 200 with a null body or a 500."""
        mock_health_checker.get_current_activity = AsyncMock(return_value=None)

        resp = client.get("/health/agents/idle/activity")

        assert resp.status_code == 404

    def test_activity_id_is_lowercased(self, client, mock_health_checker):
        """Bug class: rows are stored lower-cased; an upper-case path arg must be
        normalized or it would 404 against a row that exists."""
        mock_health_checker.get_current_activity = AsyncMock(return_value=None)

        client.get("/health/agents/MAX/activity")

        mock_health_checker.get_current_activity.assert_awaited_once_with("max")


class TestHealthHost:
    """GET /health/host (#2204): the host's numbers, the engines' loaded models and the box, on
    the unauthenticated lane."""

    def _client(self, mock_health_checker, box_reader):
        app = FastAPI()
        app.include_router(router)
        app.state.box_reader = box_reader
        mock_health_checker.read_host_resources = AsyncMock(
            return_value={"memory_available_bytes": 1.0e11, "swap_used_bytes": None}
        )
        patcher = patch(
            "squadops.api.routes.platform_health._get_health_checker",
            return_value=mock_health_checker,
        )
        patcher.start()
        self._patcher = patcher
        return TestClient(app)

    def teardown_method(self):
        if getattr(self, "_patcher", None):
            self._patcher.stop()

    def test_the_payload_carries_states_and_numbers_and_no_identity(self, mock_health_checker):
        """Entered at the route the console calls. Bugs caught: the lease holder's name, a
        campaign id or a model digest leaking onto the unauthenticated lane; an unreadable
        engine reported as holding nothing."""
        from datetime import UTC, datetime

        from squadops.campaigns.box import (
            BoxLease,
            EngineReading,
            LeaseHolder,
            Model,
            Quietness,
        )
        from squadops.campaigns.box_reading import BoxSnapshot

        expires = datetime(2026, 10, 11, 22, 0, tzinfo=UTC)
        reader = MagicMock()
        reader.snapshot = AsyncMock(
            return_value=BoxSnapshot(
                BoxLease(
                    LeaseHolder.SUPERVISOR,
                    "ripley-the-supervisor",
                    expires,
                    expires_at=expires,
                    campaign_id="cmp_secret0000001",
                ),
                (
                    EngineReading("ollama", (Model("qwen3.8:27b", "sha256deadbeefcafe"),)),
                    EngineReading("tensorfold", None, "ConnectError: refused"),
                ),
                Quietness(False, ("engine tensorfold could not be read",)),
            )
        )

        resp = self._client(mock_health_checker, reader).get("/health/host")

        body = resp.json()
        assert resp.status_code == 200
        assert body["host"] == {"memory_available_bytes": 1.0e11, "swap_used_bytes": None}
        assert body["floors"]["memory_available_after_load_bytes"] == 16 * 2**30
        assert body["engines"] == [
            {"engine": "ollama", "loaded": ["qwen3.8:27b"]},
            {"engine": "tensorfold", "loaded": None},
        ]
        assert body["box"] == {
            "quiet": False,
            "lease": {"holder": "supervisor", "expires_at": expires.isoformat()},
        }
        for leaked in ("ripley", "cmp_secret", "deadbeef", "ConnectError"):
            assert leaked not in resp.text

    def test_an_unreadable_box_is_unknown_never_quiet(self, mock_health_checker):
        """Bug caught: a box reader that raised, reported as a quiet box with no engines."""
        reader = MagicMock()
        reader.snapshot = AsyncMock(side_effect=RuntimeError("registry down"))

        body = self._client(mock_health_checker, reader).get("/health/host").json()

        assert (body["box"], body["engines"]) == (None, None)


def test_a_server_failure_on_an_unauthenticated_route_names_the_request_never_the_exception(
    mock_health_checker, caplog
):
    """#1976. Bug caught: ``/health/*`` answered a failed read with ``detail=f"...: {e}"``, so an
    unauthenticated caller read whatever the exception carried (here a connection string). Now
    the body says what failed and gives the request id, and the log keeps the traceback."""
    from squadops.api.middleware.auth import RequestIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(router)
    mock_health_checker.get_runtime_state = AsyncMock(
        side_effect=ConnectionError("postgresql://app:hunter2@db.internal:5432/records")
    )

    with patch(
        "squadops.api.routes.platform_health._get_health_checker", return_value=mock_health_checker
    ):
        resp = TestClient(app).get(
            "/health/agents/max/runtime-state", headers={"X-Request-ID": "req-1976"}
        )

    assert resp.status_code == 500
    assert resp.json() == {
        "detail": {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to read runtime state",
                "details": {"request_id": "req-1976"},
            }
        }
    }
    assert "hunter2" not in resp.text
    assert "req-1976" in caplog.text and "hunter2" in caplog.text
