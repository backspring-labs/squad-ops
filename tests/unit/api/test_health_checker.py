"""
Unit tests for HealthChecker (extracted from legacy health_app.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.api.runtime.health_checker import HealthChecker


@pytest.fixture()
def mock_config():
    """Create a mock AppConfig with all fields HealthChecker needs."""
    cfg = MagicMock()
    cfg.agent.instances_file = "/nonexistent/instances.yaml"
    cfg.agent.heartbeat_timeout_window = 90
    cfg.agent.reconciliation_interval = 45
    cfg.comms.rabbitmq.url = "amqp://guest:guest@rabbitmq:5672/"
    cfg.comms.redis.url = "redis://redis:6379/0"
    cfg.prefect.api_url = "http://prefect:4200/api"
    cfg.observability.prometheus.url = "http://prometheus:9090"
    cfg.observability.grafana.url = "http://grafana:3000"
    cfg.observability.otel.url = "http://otel:4318"
    cfg.observability.otel.health_url = "http://otel:13133"
    cfg.observability.otel.zpages_url = "http://otel:55679"
    cfg.observability.otel.version = "0.90.0"
    cfg.langfuse.host = "http://langfuse:3000"
    cfg.auth.enabled = True
    cfg.auth.provider = "keycloak"
    cfg.auth.oidc.issuer_url = "http://keycloak:8080/realms/squadops"
    cfg.auth.keycloak = None
    return cfg


@pytest.fixture()
def mock_pg_pool():
    """Create a mock asyncpg pool."""
    pool = MagicMock()
    return pool


@pytest.fixture()
def checker(mock_pg_pool, mock_config):
    """Create a HealthChecker with mocked dependencies."""
    return HealthChecker(pg_pool=mock_pg_pool, redis_client=None, config=mock_config)


class TestComputeNetworkStatus:
    def test_none_heartbeat_is_offline(self, checker):
        assert checker._compute_network_status(None) == "offline"

    def test_recent_heartbeat_is_online(self, checker):
        recent = datetime.utcnow() - timedelta(seconds=30)
        assert checker._compute_network_status(recent) == "online"

    def test_stale_heartbeat_is_offline(self, checker):
        stale = datetime.utcnow() - timedelta(seconds=200)
        assert checker._compute_network_status(stale) == "offline"

    def test_just_within_timeout_is_online(self, checker):
        at_boundary = datetime.utcnow() - timedelta(seconds=89)
        assert checker._compute_network_status(at_boundary) == "online"


class TestGetDefaultInstances:
    def test_returns_five_agents(self, checker):
        defaults = checker._get_default_instances()
        assert len(defaults) == 5
        assert "max" in defaults
        assert "neo" in defaults
        assert "nat" in defaults
        assert "eve" in defaults
        assert "data" in defaults

    def test_default_instance_has_display_name(self, checker):
        defaults = checker._get_default_instances()
        assert defaults["max"]["display_name"] == "Max"

    def test_default_instance_has_role(self, checker):
        defaults = checker._get_default_instances()
        assert defaults["neo"]["role"] == "dev"


class TestGetDisplayName:
    def test_fallback_to_title_case(self, checker):
        assert checker._get_display_name("unknown_agent") == "Unknown_Agent"

    def test_uses_instances_cache(self, checker):
        checker._instances_cache = {"max": {"display_name": "Max", "role": "lead"}}
        checker._instances_cache_mtime = 12345.0
        assert checker._get_display_name("max") == "Max"


class TestGetAgentStatus:
    @pytest.mark.asyncio
    async def test_returns_agent_list(self, checker, mock_pg_pool):
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "agent_id": "max",
            "lifecycle_state": "READY",
            "version": "0.9.7",
            "tps": 5,
            "memory_count": 10,
            "last_heartbeat": datetime.utcnow(),
            "current_task_id": None,
        }[key]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pg_pool.acquire.return_value = mock_conn

        result = await checker.get_agent_status()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_returns_fallback_on_db_error(self, checker, mock_pg_pool):
        mock_pg_pool.acquire.side_effect = Exception("DB down")
        result = await checker.get_agent_status()
        assert isinstance(result, list)
        assert len(result) == 5  # from _get_default_instances
        assert all(a["network_status"] == "offline" for a in result)


class TestUpdateAgentStatusInDb:
    @pytest.mark.asyncio
    async def test_upsert_returns_updated(self, checker, mock_pg_pool):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pg_pool.acquire.return_value = mock_conn

        result = await checker.update_agent_status_in_db(
            {
                "agent_id": "max",
                "lifecycle_state": "READY",
                "version": "0.9.7",
                "tps": 5,
                "memory_count": 10,
            }
        )
        assert result["status"] == "updated"
        assert result["agent_id"] == "max"
        mock_conn.execute.assert_awaited_once()


class TestCheckRedis:
    @pytest.mark.asyncio
    async def test_redis_not_configured(self, checker):
        result = await checker.check_redis()
        assert result["status"] == "offline"
        assert "not configured" in result["notes"]

    @pytest.mark.asyncio
    async def test_redis_online(self, checker):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.info = AsyncMock(
            return_value={
                "redis_version": "7.2.0",
                "used_memory_human": "1.5M",
            }
        )
        checker.redis_client = mock_redis
        result = await checker.check_redis()
        assert result["status"] == "online"
        assert result["version"] == "7.2.0"


class TestCheckPostgres:
    @pytest.mark.asyncio
    async def test_postgres_online(self, checker, mock_pg_pool):
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(
            side_effect=[
                "PostgreSQL 15.3 on x86_64-pc-linux-gnu",
                5,
            ]
        )
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pg_pool.acquire.return_value = mock_conn

        result = await checker.check_postgres()
        assert result["status"] == "online"
        assert result["version"] == "15.3"
        assert "5 agents" in result["notes"]

    @pytest.mark.asyncio
    async def test_postgres_offline(self, checker, mock_pg_pool):
        mock_pg_pool.acquire.side_effect = Exception("Connection refused")
        result = await checker.check_postgres()
        assert result["status"] == "offline"
