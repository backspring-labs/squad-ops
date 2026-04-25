"""Tests for AgentRunner Prefect log forwarder wiring (SIP-0087 phase-3).

Behavior of the install/teardown helper itself is covered in
``tests/unit/cycles/test_log_forwarding_install.py``. These tests focus on
the AgentRunner-side wiring: the runner stores the handle returned by the
helper, releases it on ``stop()``, and tears it down on a partial-start
failure.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.cycles.log_forwarding_install import PrefectLogForwarderHandle
from squadops.config.schema import PrefectConfig

pytestmark = [pytest.mark.domain_agents]


def _make_runner():
    """Build a bare AgentRunner without invoking __init__ (loads instances.yaml)."""
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner._prefect_log_handle = None
    return runner


def _config_with_prefect(*, api_url: str, log_forwarding: bool, log_level: str = "INFO"):
    cfg = MagicMock()
    cfg.prefect = PrefectConfig(
        api_url=api_url, log_forwarding=log_forwarding, log_level=log_level
    )
    return cfg


@pytest.fixture(autouse=True)
def _strip_added_root_handlers():
    before = list(logging.getLogger().handlers)
    yield
    for h in list(logging.getLogger().handlers):
        if h not in before:
            logging.getLogger().removeHandler(h)


# ---------------------------------------------------------------------------
# Wiring delegates to the helper
# ---------------------------------------------------------------------------


async def test_no_handle_when_disabled():
    runner = _make_runner()
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=False)
    await runner._install_prefect_log_forwarding(cfg)
    assert runner._prefect_log_handle is None


async def test_handle_is_stored_when_install_succeeds():
    runner = _make_runner()
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=True)

    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        await runner._install_prefect_log_forwarding(cfg)

    assert isinstance(runner._prefect_log_handle, PrefectLogForwarderHandle)
    assert runner._prefect_log_handle.handler in logging.getLogger().handlers


# ---------------------------------------------------------------------------
# Lifecycle: stop() and partial-start failure both close the handle
# ---------------------------------------------------------------------------


async def test_stop_closes_handle():
    runner = _make_runner()
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=True)

    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        await runner._install_prefect_log_forwarding(cfg)

    handle = runner._prefect_log_handle
    runner._shutdown_event = asyncio.Event()
    runner._heartbeat_task = None
    runner.system = None

    from squadops.agents.entrypoint import AgentRunner

    await AgentRunner.stop(runner)

    assert handle.handler not in logging.getLogger().handlers
    fake_forwarder.close.assert_awaited_once()
    assert runner._prefect_log_handle is None


async def test_start_failure_after_install_tears_down_handle():
    """If start() raises after the handle is installed, the forwarder is closed."""
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=True)
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())

    runner = _make_runner()
    runner.role = "dev"

    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch(
            "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
            return_value=fake_forwarder,
        ),
        patch(
            "adapters.observability.healthcheck_http.HealthCheckHttpReporter",
            side_effect=RuntimeError("bootstrap exploded"),
        ),
    ):
        from squadops.agents.entrypoint import AgentRunner

        with pytest.raises(RuntimeError, match="bootstrap exploded"):
            await AgentRunner.start(runner)

    fake_forwarder.close.assert_awaited_once()
    assert runner._prefect_log_handle is None
