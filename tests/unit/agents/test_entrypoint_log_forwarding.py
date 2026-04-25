"""Tests for AgentRunner log-forwarder wiring (SIP-0087, hex-arch refactor).

Behavior of the factory + adapter is covered in
``tests/unit/observability/test_log_forwarder_factory.py``. These tests focus
on the AgentRunner-side wiring: the runner builds a port through the factory,
stores the resulting :class:`LogForwarderPort`, releases it on ``stop()``, and
tears it down on a partial-start failure.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.observability.log_forwarder import (
    NoOpLogForwarder,
    PrefectLogForwarderAdapter,
)
from squadops.config.schema import PrefectConfig

pytestmark = [pytest.mark.domain_agents]

_PREFECT_FWD_PATCH = "adapters.observability.log_forwarder.prefect.PrefectLogForwarder"


def _make_runner():
    """Build a bare AgentRunner without invoking __init__ (loads instances.yaml)."""
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner._log_forwarder = None
    return runner


def _config_with_prefect(*, api_url: str, log_forwarding: bool, log_level: str = "INFO"):
    cfg = MagicMock()
    cfg.prefect = PrefectConfig(api_url=api_url, log_forwarding=log_forwarding, log_level=log_level)
    return cfg


@pytest.fixture(autouse=True)
def _strip_added_root_handlers():
    before = list(logging.getLogger().handlers)
    yield
    for h in list(logging.getLogger().handlers):
        if h not in before:
            logging.getLogger().removeHandler(h)


# ---------------------------------------------------------------------------
# Wiring goes through the factory and yields a port
# ---------------------------------------------------------------------------


async def test_factory_returns_noop_when_disabled_and_runner_stores_it():
    """Always-inject contract: even with forwarding off, the runner gets a port."""
    runner = _make_runner()
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=False)
    runner._log_forwarder = await runner._create_log_forwarder(cfg)
    assert isinstance(runner._log_forwarder, NoOpLogForwarder)


async def test_runner_stores_prefect_adapter_when_install_succeeds():
    runner = _make_runner()
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=True)

    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        runner._log_forwarder = await runner._create_log_forwarder(cfg)

    assert isinstance(runner._log_forwarder, PrefectLogForwarderAdapter)
    assert runner._log_forwarder._handler in logging.getLogger().handlers


# ---------------------------------------------------------------------------
# Lifecycle: stop() and partial-start failure both close the port
# ---------------------------------------------------------------------------


async def test_stop_closes_port():
    runner = _make_runner()
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=True)

    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        runner._log_forwarder = await runner._create_log_forwarder(cfg)

    port = runner._log_forwarder
    handler = port._handler
    runner._shutdown_event = asyncio.Event()
    runner._heartbeat_task = None
    runner.system = None

    from squadops.agents.entrypoint import AgentRunner

    await AgentRunner.stop(runner)

    assert handler not in logging.getLogger().handlers
    fake_forwarder.close.assert_awaited_once()
    assert runner._log_forwarder is None


async def test_start_failure_after_install_tears_down_port():
    """If start() raises after the port is installed, the forwarder is closed."""
    cfg = _config_with_prefect(api_url="http://prefect:4200/api", log_forwarding=True)
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())

    runner = _make_runner()
    runner.role = "dev"

    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder),
        patch(
            "adapters.observability.healthcheck_http.HealthCheckHttpReporter",
            side_effect=RuntimeError("bootstrap exploded"),
        ),
    ):
        from squadops.agents.entrypoint import AgentRunner

        with pytest.raises(RuntimeError, match="bootstrap exploded"):
            await AgentRunner.start(runner)

    fake_forwarder.close.assert_awaited_once()
    assert runner._log_forwarder is None
