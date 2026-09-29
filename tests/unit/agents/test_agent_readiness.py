"""An agent's readiness mark, as its container's health check reads it (#1691).

What bug would these catch? The one #1691 found: a health check that passes whether or not the
agent started — ``compose up --wait`` returned on it while every agent restart-looped on the #352
startup guard, and the deploy reported healthy. So: a refused start must never read as ready,
not even from the mark its predecessor left; a running agent must read as ready; one that
stopped looping must stop reading as ready.
"""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.agents import readiness

pytestmark = [pytest.mark.domain_agents]


@pytest.fixture
def mark_file(tmp_path, monkeypatch):
    path = tmp_path / "ready"
    monkeypatch.setattr(readiness, "READY_FILE", path)
    return path


@pytest.mark.parametrize(
    ("age_seconds", "interval", "ready"),
    [
        (None, "30", False),
        (10, "30", True),
        (100, "30", False),
        (100, "60", True),
    ],
    ids=["never marked", "fresh", "stale: three heartbeats missed", "a longer interval ages later"],
)
def test_ready_is_a_mark_fresher_than_three_heartbeats(
    mark_file, monkeypatch, age_seconds, interval, ready
):
    monkeypatch.setenv(readiness.HEARTBEAT_INTERVAL_ENV, interval)
    if age_seconds is not None:
        readiness.mark()
        then = time.time() - age_seconds
        os.utime(mark_file, (then, then))

    assert readiness.is_ready() is ready
    assert readiness.main() == (0 if ready else 1)


def _runner():
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner._log_forwarder = None
    runner._service_token_client = None
    runner._shutdown_event = asyncio.Event()
    return runner


async def test_a_start_the_startup_guard_refuses_never_reads_as_ready(mark_file):
    """Wiring, entered at ``AgentRunner.start`` with a mark a previous process in the same
    container left. Bug this catches: the #1691 loop — the #352 guard refuses the start and the
    container still reads healthy, from its predecessor's mark or from nothing at all."""
    readiness.mark()
    runner = _runner()
    runner._create_log_forwarder = AsyncMock(return_value=MagicMock(aclose=AsyncMock()))
    runner._create_heartbeat_reporter = MagicMock()
    runner._create_system = AsyncMock(
        side_effect=RuntimeError(
            "Prompt registry unavailable: langfuse — 19 shipped prompt asset(s)"
        )
    )

    with (
        patch("squadops.config.load_config", return_value=MagicMock()),
        pytest.raises(RuntimeError, match="Prompt registry unavailable"),
    ):
        await runner.start()

    assert readiness.is_ready() is False
    assert not mark_file.exists()


async def test_a_looping_agent_marks_itself_ready(mark_file):
    """Wiring, entered at the heartbeat loop ``start`` runs once the system bootstrapped. Bug
    this catches: the mark written somewhere a started agent never reaches, so every agent
    reads unhealthy and the deploy refuses a stack that works."""
    runner = _runner()

    async def _one_heartbeat():
        runner._shutdown_event.set()

    runner._send_heartbeat = _one_heartbeat

    await runner._heartbeat_loop()

    assert readiness.is_ready() is True
