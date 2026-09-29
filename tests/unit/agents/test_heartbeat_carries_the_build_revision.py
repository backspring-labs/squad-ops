"""The heartbeat carries the commit the agent's image was built from, into agent_status (#1720).

Bug class guarded: a cycle's lineage named only the runtime API's commit. The agents ran
another commit's images on deploy A′ and nothing on record could show it; a deploy that fails
to replace an agent (#370's class) reads the same as one that did. The revision has to travel
the whole way, agent to row, and an unknown build must arrive as unknown, never as a commit.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

import squadops
from adapters.observability.healthcheck_http import HealthCheckHttpReporter
from adapters.telemetry.otel import resource_attributes
from squadops._version import GIT_SHA_ENV
from squadops.api.routes import agent_status
from squadops.api.runtime.health_checker import HealthChecker

pytestmark = pytest.mark.domain_agents

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _recording_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = conn
    return pool, conn


def _runner(reporter: HealthCheckHttpReporter):
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner._lifecycle_state = "READY"
    runner._heartbeat_reporter = reporter
    runner._shutdown_event = asyncio.Event()
    return runner


@pytest.mark.parametrize(
    "built_from, stored",
    [
        ("ccc9475d", "ccc9475d"),
        ("8e2c2e87-dirty", "8e2c2e87-dirty"),
        ("unknown", None),
        (None, None),
    ],
    ids=["clean-build", "dirty-build", "built-without-the-script", "variable-unset"],
)
async def test_the_agents_build_revision_reaches_its_status_row(monkeypatch, built_from, stored):
    """Wiring, entered at the agent's ``_send_heartbeat``: the real reporter posts into the
    real route, and the real health checker writes the row. What reaches the pool is what a
    reader of ``agent_status`` sees."""
    if built_from is None:
        monkeypatch.delenv(GIT_SHA_ENV, raising=False)
    else:
        monkeypatch.setenv(GIT_SHA_ENV, built_from)
    pool, conn = _recording_pool()
    checker = HealthChecker(pg_pool=pool, config=MagicMock())
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
        await _runner(reporter)._send_heartbeat()

    sql, *params = conn.execute.await_args.args
    assert "revision = $9" in sql
    assert params[0] == "neo"
    assert params[8] == stored


@pytest.mark.parametrize(
    "built_from, expected",
    [("ccc9475d-dirty", "ccc9475d-dirty"), ("unknown", None), (None, None)],
    ids=["known", "built-without-the-script", "variable-unset"],
)
def test_every_signal_names_the_release_and_the_revision_it_knows(
    monkeypatch, built_from, expected
):
    if built_from is None:
        monkeypatch.delenv(GIT_SHA_ENV, raising=False)
    else:
        monkeypatch.setenv(GIT_SHA_ENV, built_from)

    attributes = resource_attributes("squadops-neo")

    assert attributes["service.name"] == "squadops-neo"
    assert attributes["service.version"] == squadops.__version__
    assert attributes.get("vcs.ref.head.revision") == expected


@pytest.mark.parametrize("dockerfile", ["agents/Dockerfile", "src/squadops/api/runtime/Dockerfile"])
def test_each_image_labels_the_revision_the_deploy_passed(dockerfile):
    """A ``LABEL`` or ``ENV`` that reads ``${SOURCE_HASH}`` before the final stage declares the
    argument expands to an empty string, silently, and the image claims no commit at all."""
    lines = (_REPO_ROOT / dockerfile).read_text().splitlines()
    final_stage = max(i for i, line in enumerate(lines) if line.startswith("FROM "))
    declared = [
        i for i, line in enumerate(lines) if i > final_stage and line.startswith("ARG SOURCE_HASH")
    ]
    uses = {
        line.split()[0] + " " + line.split()[1].split("=")[0]: i
        for i, line in enumerate(lines)
        if i > final_stage and "${SOURCE_HASH}" in line
    }

    assert declared, f"{dockerfile}'s final stage never declares SOURCE_HASH"
    assert "LABEL org.opencontainers.image.revision" in uses
    assert "ENV SQUADOPS_GIT_SHA" in uses
    assert all(at > declared[0] for at in uses.values())
