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
        mock_row = {
            "agent_id": "max",
            "lifecycle_state": "READY",
            "network_status": "online",
            "version": "0.9.7",
            "tps": 5,
            "memory_count": 10,
            "last_heartbeat": datetime(2026, 2, 16, 12, 0, 0),
            "current_task_id": None,
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

    def test_get_agent_status_not_found(self, client, mock_health_checker):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn

        resp = client.get("/health/agents/status/unknown")
        assert resp.status_code == 404


class TestCreateOrUpdateAgentStatus:
    def test_valid_heartbeat(self, client, mock_health_checker):
        resp = client.post(
            "/health/agents/status",
            json={
                "agent_id": "max",
                "lifecycle_state": "READY",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        mock_health_checker.update_agent_status_in_db.assert_awaited_once()

    def test_invalid_lifecycle_state_returns_400(self, client, mock_health_checker):
        resp = client.post(
            "/health/agents/status",
            json={
                "agent_id": "max",
                "lifecycle_state": "INVALID",
            },
        )
        assert resp.status_code == 400
        assert "Invalid lifecycle_state" in resp.json()["detail"]


class TestUpdateAgentStatus:
    def test_update_with_no_fields_returns_400(self, client, mock_health_checker):
        resp = client.put("/health/agents/status/max", json={})
        assert resp.status_code == 400
        assert "No fields" in resp.json()["detail"]

    def test_update_valid_fields(self, client, mock_health_checker):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn

        resp = client.put(
            "/health/agents/status/max",
            json={
                "lifecycle_state": "WORKING",
                "tps": 10,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"

    def test_update_not_found(self, client, mock_health_checker):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_health_checker.pg_pool.acquire.return_value = mock_conn

        resp = client.put(
            "/health/agents/status/ghost",
            json={
                "lifecycle_state": "READY",
            },
        )
        assert resp.status_code == 404
