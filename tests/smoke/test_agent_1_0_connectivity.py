"""
Smoke test: 1.0 DI agent shims can be instantiated and can use injected ports.

This test is intentionally hermetic:
- Secrets are resolved via an in-test SecretProvider.
- DB runtime uses an in-memory SQLite SQLAlchemy engine.
- Heartbeats use a fake reporter (no network).

Constraint:
- Instantiating/importing 1.0 agents must not import `_v0_legacy`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import sessionmaker

from squadops.core.secrets import SecretManager
from squadops.ports.db import DbRuntime, HealthResult
from squadops.ports.observability.heartbeat import AgentHeartbeatReporter
from squadops.ports.secrets import SecretProvider


class InTestSecretProvider(SecretProvider):
    def __init__(self, secrets: dict[str, str]):
        self._secrets = secrets

    @property
    def provider_name(self) -> str:
        return "in_test"

    def resolve(self, provider_key: str) -> str:
        if provider_key not in self._secrets:
            raise KeyError(provider_key)
        return self._secrets[provider_key]

    def exists(self, provider_key: str) -> bool:
        return provider_key in self._secrets


class SqliteDbRuntime(DbRuntime):
    def __init__(self):
        self._engine = create_engine("sqlite+pysqlite:///:memory:")
        self._session_factory = sessionmaker(bind=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        return self._session_factory

    def db_health_check(self) -> HealthResult:
        try:
            with self._engine.connect() as conn:
                row = conn.execute(text("SELECT 1")).fetchone()
            if not row or row[0] != 1:
                return HealthResult(status="unhealthy", message="Unexpected SELECT 1 result")
            return HealthResult(status="healthy")
        except Exception as e:
            return HealthResult(status="unhealthy", message=str(e))

    def dispose(self) -> None:
        self._engine.dispose()


@dataclass
class FakeHeartbeatReporter(AgentHeartbeatReporter):
    calls: list[dict] = None

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    async def send_status(
        self,
        *,
        agent_id: str,
        lifecycle_state: str,
        current_task_id: str | None = None,
        version: str | None = None,
        tps: float | None = None,
        memory_count: int | None = None,
    ) -> None:
        self.calls.append(
            {
                "agent_id": agent_id,
                "lifecycle_state": lifecycle_state,
                "current_task_id": current_task_id,
                "version": version,
                "tps": tps,
                "memory_count": memory_count,
            }
        )


@pytest.mark.asyncio
async def test_full_squad_1_0_di_connectivity():
    modules_before = set(sys.modules.keys())

    # Import shims inside the test so we can compute newly imported modules.
    from squadops.execution.squad import DataAgent, DevAgent, LeadAgent, QaAgent, StrategyAgent

    modules_after = set(sys.modules.keys())
    newly_imported = modules_after - modules_before

    leaked_legacy = sorted([m for m in newly_imported if m.startswith("_v0_legacy")])
    assert leaked_legacy == [], f"1.0 execution layer imported legacy modules: {leaked_legacy}"

    provider = InTestSecretProvider({"DB_PASS": "p@ss"})
    secret_manager = SecretManager(provider=provider, name_map={})
    db_runtime = SqliteDbRuntime()
    heartbeat = FakeHeartbeatReporter()

    agents = [
        (LeadAgent, "Max"),
        (StrategyAgent, "Nat"),
        (DevAgent, "Neo"),
        (QaAgent, "EVE"),
        (DataAgent, "Data"),
    ]

    for agent_cls, expected_id in agents:
        agent = agent_cls(
            secret_manager=secret_manager,
            db_runtime=db_runtime,
            heartbeat_reporter=heartbeat,
            agent_id=expected_id,
        )

        # Identity verification
        assert agent.agent_id == expected_id

        # Secrets verification
        assert agent.resolve("secret://DB_PASS") == "p@ss"

        # DB verification
        health = agent.health_check()
        assert isinstance(health, HealthResult)
        assert health.status == "healthy"

        # Heartbeat wiring verification (no network)
        await agent.send_heartbeat(lifecycle_state="READY", tps=0)

    assert len(heartbeat.calls) == 5
    assert {c["agent_id"] for c in heartbeat.calls} == {"Max", "Nat", "Neo", "EVE", "Data"}

