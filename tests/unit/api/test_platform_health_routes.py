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
    hc._compute_network_status = MagicMock(return_value="online")
    hc._get_display_name = MagicMock(return_value="Max")

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

        resp = client.get("/health/agents/status/max")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "max"
        assert data["lifecycle_state"] == "READY"
        # #231: the single-agent route now carries the canonical health + posture
        # at parity with the list route, with network_status demoted to back-compat.
        assert data["runtime_status"] == "online"
        assert data["mode"] == "cycle"
        assert data["network_status"] == "online"  # legacy field still present

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
