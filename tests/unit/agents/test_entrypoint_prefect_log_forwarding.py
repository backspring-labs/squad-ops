"""Tests for AgentRunner Prefect log forwarder wiring (SIP-0087 phase-3)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.domain_agents]


def _make_runner():
    """Build a bare AgentRunner without invoking __init__ (which loads instances.yaml)."""
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner._prefect_log_forwarder = None
    runner._prefect_log_handler = None
    return runner


def _make_config(*, api_url: str, log_forwarding: bool, log_level: str = "INFO"):
    return SimpleNamespace(
        prefect=SimpleNamespace(
            api_url=api_url,
            log_forwarding=log_forwarding,
            log_level=log_level,
        )
    )


@pytest.fixture(autouse=True)
def _strip_added_handlers():
    before = list(logging.getLogger().handlers)
    yield
    for h in list(logging.getLogger().handlers):
        if h not in before:
            logging.getLogger().removeHandler(h)


def test_skipped_when_api_url_unset():
    runner = _make_runner()
    cfg = _make_config(api_url="", log_forwarding=True)
    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch("adapters.cycles.prefect_log_forwarder.PrefectLogForwarder") as fwd_cls,
    ):
        runner._install_prefect_log_forwarding()
    fwd_cls.assert_not_called()
    assert runner._prefect_log_handler is None


def test_skipped_when_flag_disabled():
    runner = _make_runner()
    cfg = _make_config(api_url="http://prefect:4200/api", log_forwarding=False)
    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch("adapters.cycles.prefect_log_forwarder.PrefectLogForwarder") as fwd_cls,
    ):
        runner._install_prefect_log_forwarding()
    fwd_cls.assert_not_called()
    assert runner._prefect_log_handler is None


def test_installs_handler_with_configured_level():
    runner = _make_runner()
    cfg = _make_config(
        api_url="http://prefect:4200/api", log_forwarding=True, log_level="WARNING"
    )
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch(
            "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
            return_value=fake_forwarder,
        ) as fwd_cls,
    ):
        runner._install_prefect_log_forwarding()

    fwd_cls.assert_called_once_with(api_url="http://prefect:4200/api")
    fake_forwarder.start.assert_called_once()
    assert runner._prefect_log_handler is not None
    assert runner._prefect_log_handler in logging.getLogger().handlers
    assert runner._prefect_log_handler._filters.min_level == logging.WARNING


def test_unknown_log_level_falls_back_to_info():
    runner = _make_runner()
    cfg = _make_config(
        api_url="http://prefect:4200/api", log_forwarding=True, log_level="LOUD"
    )
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch(
            "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
            return_value=fake_forwarder,
        ),
    ):
        runner._install_prefect_log_forwarding()
    assert runner._prefect_log_handler._filters.min_level == logging.INFO


async def test_stop_removes_handler_and_closes_forwarder():
    runner = _make_runner()
    cfg = _make_config(api_url="http://prefect:4200/api", log_forwarding=True)

    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with (
        patch("squadops.config.load_config", return_value=cfg),
        patch(
            "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
            return_value=fake_forwarder,
        ),
    ):
        runner._install_prefect_log_forwarding()

    handler = runner._prefect_log_handler
    assert handler in logging.getLogger().handlers

    # Stub out the rest of stop()'s dependencies so we exercise just the
    # log-forwarder teardown branch.
    import asyncio

    runner._shutdown_event = asyncio.Event()
    runner._heartbeat_task = None
    runner.system = None

    from squadops.agents.entrypoint import AgentRunner

    await AgentRunner.stop(runner)

    assert handler not in logging.getLogger().handlers
    fake_forwarder.close.assert_awaited_once()
    assert runner._prefect_log_forwarder is None
    assert runner._prefect_log_handler is None
