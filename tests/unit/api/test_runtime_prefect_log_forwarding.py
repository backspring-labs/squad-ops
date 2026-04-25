"""Tests for Prefect log forwarder install/teardown helpers (SIP-0087 phase-3)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.api.runtime.prefect_log_forwarding import (
    install_prefect_log_handler,
    teardown_prefect_log_handler,
)


def _make_config(*, api_url: str, log_forwarding: bool, log_level: str = "INFO"):
    return SimpleNamespace(
        prefect=SimpleNamespace(
            api_url=api_url,
            log_forwarding=log_forwarding,
            log_level=log_level,
        )
    )


@pytest.fixture(autouse=True)
def _strip_added_root_handlers():
    before = list(logging.getLogger().handlers)
    yield
    for h in list(logging.getLogger().handlers):
        if h not in before:
            logging.getLogger().removeHandler(h)


def test_skipped_when_api_url_unset():
    cfg = _make_config(api_url="", log_forwarding=True)
    with patch("adapters.cycles.prefect_log_forwarder.PrefectLogForwarder") as fwd_cls:
        forwarder, handler = install_prefect_log_handler(cfg)
    fwd_cls.assert_not_called()
    assert (forwarder, handler) == (None, None)


def test_skipped_when_flag_disabled():
    cfg = _make_config(api_url="http://prefect:4200/api", log_forwarding=False)
    with patch("adapters.cycles.prefect_log_forwarder.PrefectLogForwarder") as fwd_cls:
        forwarder, handler = install_prefect_log_handler(cfg)
    fwd_cls.assert_not_called()
    assert (forwarder, handler) == (None, None)


def test_installs_handler_with_configured_level():
    cfg = _make_config(
        api_url="http://prefect:4200/api", log_forwarding=True, log_level="DEBUG"
    )
    fake_forwarder = MagicMock(start=MagicMock())
    with patch(
        "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
        return_value=fake_forwarder,
    ) as fwd_cls:
        forwarder, handler = install_prefect_log_handler(cfg)

    fwd_cls.assert_called_once_with(api_url="http://prefect:4200/api")
    fake_forwarder.start.assert_called_once()
    assert handler is not None
    assert handler in logging.getLogger().handlers
    assert handler._filters.min_level == logging.DEBUG
    assert forwarder is fake_forwarder


def test_unknown_log_level_falls_back_to_info():
    cfg = _make_config(
        api_url="http://prefect:4200/api", log_forwarding=True, log_level="VERBOSE"
    )
    fake_forwarder = MagicMock(start=MagicMock())
    with patch(
        "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        _, handler = install_prefect_log_handler(cfg)
    assert handler is not None
    assert handler._filters.min_level == logging.INFO


def test_init_failure_does_not_propagate():
    cfg = _make_config(api_url="http://prefect:4200/api", log_forwarding=True)
    with patch(
        "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
        side_effect=RuntimeError("boom"),
    ):
        forwarder, handler = install_prefect_log_handler(cfg)
    assert (forwarder, handler) == (None, None)


async def test_teardown_removes_handler_and_closes_forwarder():
    cfg = _make_config(api_url="http://prefect:4200/api", log_forwarding=True)
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock())
    with patch(
        "adapters.cycles.prefect_log_forwarder.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        forwarder, handler = install_prefect_log_handler(cfg)
    assert handler in logging.getLogger().handlers

    await teardown_prefect_log_handler(forwarder, handler)

    assert handler not in logging.getLogger().handlers
    fake_forwarder.close.assert_awaited_once()


async def test_teardown_noop_when_not_installed():
    # Should not raise when forwarder/handler are both None.
    await teardown_prefect_log_handler(None, None)
