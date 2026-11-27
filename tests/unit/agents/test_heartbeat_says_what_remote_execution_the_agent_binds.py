"""An agent's heartbeat says which remote-execution provider its own port binds (#3235).

Bug class guarded: on 2026-11-19 the runtime was switched to ``runtime_api`` and rebuilt while
the QA agent still bound no port. Nothing on record said so, a cycle was created, and its in-run
evaluation read "no remote execution port" as an unverified check on the candidate. The agent's
own word has to travel the whole way, from the configuration that binds its port to the row a
cycle's creation reads, and an agent that hasn't said must arrive as not having said.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry
from adapters.observability.healthcheck_http import HealthCheckHttpReporter
from squadops.api.routes import agent_status
from squadops.api.runtime.health_checker import HealthChecker
from squadops.capabilities.tool_checks import AgentRemoteExecution

pytestmark = pytest.mark.domain_agents


def _pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = conn
    return pool, conn


def _checker(pool) -> HealthChecker:
    config = MagicMock()
    config.agent.heartbeat_timeout_window = 90
    return HealthChecker(pg_pool=pool, config=config, deploy_registry=MemoryDeployRegistry())


def _runner(reporter: HealthCheckHttpReporter, provider: str | None):
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "eve"
    runner._lifecycle_state = "READY"
    runner._heartbeat_reporter = reporter
    runner._shutdown_event = asyncio.Event()
    runner._config = (
        SimpleNamespace(remote_execution=SimpleNamespace(provider=provider))
        if provider is not None
        else None
    )
    return runner


@pytest.mark.parametrize(
    "bound", ["runtime_api", "none", None], ids=["a-provider", "none", "not-yet-configured"]
)
async def test_what_the_agent_binds_reaches_its_status_row(bound):
    """Wiring, entered at the agent's ``_send_heartbeat``: the real reporter posts into the real
    route, and the real health checker writes the row."""
    pool, conn = _pool()
    checker = _checker(pool)
    checker._update_runtime_state_heartbeat = AsyncMock()
    app = FastAPI()
    app.include_router(agent_status.router)
    into_the_app = httpx.ASGITransport(app=app)
    real_client = httpx.AsyncClient

    with (
        patch.object(agent_status, "_get_health_checker", return_value=checker),
        patch(
            "adapters.observability.healthcheck_http.httpx.AsyncClient",
            side_effect=lambda **kw: real_client(transport=into_the_app, **kw),
        ),
    ):
        reporter = HealthCheckHttpReporter(base_url="http://runtime-api:8001", fail_silently=False)
        await _runner(reporter, bound)._send_heartbeat()

    sql, *params = conn.execute.await_args.args
    assert "remote_execution = $10" in sql
    assert (params[0], params[9]) == ("eve", bound)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {"remote_execution": "none", "revision": "3f2a91c", "age": 5},
            ("none", "3f2a91c", True),
        ),
        (
            {"remote_execution": "runtime_api", "revision": None, "age": 5},
            ("runtime_api", None, True),
        ),
        ({"remote_execution": None, "revision": "3f2a91c", "age": 5}, (None, "3f2a91c", True)),
        (
            {"remote_execution": "runtime_api", "revision": "3f2a91c", "age": 3600},
            ("runtime_api", "3f2a91c", False),
        ),
    ],
    ids=["binds-none", "build-unrecorded", "hasnt-said", "not-heard-from-for-an-hour"],
)
async def test_the_runtime_reads_back_what_the_agent_last_said(row, expected):
    """What a cycle's creation asks the health checker for. Bug caught: an agent that hasn't
    said read as bound, or one not heard from for an hour read as fresh."""
    pool, conn = _pool()
    heard = datetime.utcnow() - timedelta(seconds=row["age"])
    conn.fetchrow = AsyncMock(
        return_value={
            "remote_execution": row["remote_execution"],
            "revision": row["revision"],
            "last_heartbeat": heard,
        }
    )

    report = await _checker(pool).agent_remote_execution("eve")

    assert report == AgentRemoteExecution(expected[0], expected[1], heard, expected[2])
    assert conn.fetchrow.await_args.args[1] == "eve"


async def test_an_agent_that_never_sent_a_heartbeat_has_no_report():
    pool, conn = _pool()
    conn.fetchrow = AsyncMock(return_value=None)

    assert await _checker(pool).agent_remote_execution("eve") is None
