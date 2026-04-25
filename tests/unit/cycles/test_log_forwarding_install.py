"""Tests for ``adapters.cycles.log_forwarding_install`` (SIP-0087 phase-3).

Behavior-focused: drive the installed handler with real ``LogRecord`` objects
and assert what reaches the forwarder, instead of reading private filter
attributes.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.cycles.log_forwarding_install import (
    PrefectLogForwarderHandle,
    install_prefect_log_handler,
)
from squadops.config.schema import PrefectConfig
from squadops.telemetry.context import use_correlation_context
from squadops.telemetry.models import CorrelationContext


def _prefect_cfg(**overrides) -> PrefectConfig:
    base = {"api_url": "http://prefect:4200/api", "log_forwarding": True, "log_level": "INFO"}
    base.update(overrides)
    return PrefectConfig(**base)


def _ctx_with_run_ids() -> CorrelationContext:
    return CorrelationContext(
        cycle_id="cyc-1",
        flow_run_id="fr-1",
        task_run_id="tr-1",
    )


@pytest.fixture(autouse=True)
def _strip_added_root_handlers():
    before = list(logging.getLogger().handlers)
    yield
    for h in list(logging.getLogger().handlers):
        if h not in before:
            logging.getLogger().removeHandler(h)


# ---------------------------------------------------------------------------
# Skip / install gating
# ---------------------------------------------------------------------------


async def test_returns_none_when_api_url_unset():
    cfg = _prefect_cfg(api_url="")
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder"
    ) as fwd_cls:
        handle = await install_prefect_log_handler(cfg)
    fwd_cls.assert_not_called()
    assert handle is None


async def test_returns_none_when_flag_disabled():
    cfg = _prefect_cfg(log_forwarding=False)
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder"
    ) as fwd_cls:
        handle = await install_prefect_log_handler(cfg)
    fwd_cls.assert_not_called()
    assert handle is None


async def test_init_failure_returns_none_and_does_not_propagate():
    cfg = _prefect_cfg()
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        side_effect=RuntimeError("boom"),
    ):
        handle = await install_prefect_log_handler(cfg)
    assert handle is None


# ---------------------------------------------------------------------------
# Behavior: configured level governs which records are forwarded
# ---------------------------------------------------------------------------


async def test_records_below_configured_level_are_dropped():
    """log_level=WARNING → INFO records do not reach the forwarder."""
    cfg = _prefect_cfg(log_level="WARNING")
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert handle is not None
    with use_correlation_context(_ctx_with_run_ids()):
        logging.getLogger("squadops.test").info("ignored")
    fake_forwarder.enqueue.assert_not_called()


async def test_records_at_or_above_level_are_forwarded():
    """log_level=WARNING → WARNING/ERROR records reach the forwarder."""
    cfg = _prefect_cfg(log_level="WARNING")
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert handle is not None
    with use_correlation_context(_ctx_with_run_ids()):
        logging.getLogger("squadops.test").warning("hit")
        logging.getLogger("adapters.test").error("hit")
    assert fake_forwarder.enqueue.call_count == 2


async def test_default_info_level_drops_debug():
    """Default install (log_level=INFO) drops DEBUG records."""
    cfg = _prefect_cfg()  # log_level="INFO"
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert handle is not None
    debug_logger = logging.getLogger("squadops.test_debug")
    debug_logger.setLevel(logging.DEBUG)
    with use_correlation_context(_ctx_with_run_ids()):
        debug_logger.debug("ignored")
        debug_logger.info("hit")
    assert fake_forwarder.enqueue.call_count == 1


async def test_records_outside_allowed_prefixes_are_dropped():
    """Third-party loggers (httpx, aio_pika, ...) never reach the forwarder."""
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert handle is not None
    with use_correlation_context(_ctx_with_run_ids()):
        logging.getLogger("httpx").info("noise")
        logging.getLogger("aio_pika.heartbeat").info("noise")
    fake_forwarder.enqueue.assert_not_called()


async def test_records_without_correlation_context_are_dropped():
    """No flow_run_id / task_run_id → handler drops the record."""
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert handle is not None
    # Intentionally no use_correlation_context — system-level log.
    logging.getLogger("squadops.test").info("ignored")
    fake_forwarder.enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Handle lifecycle
# ---------------------------------------------------------------------------


async def test_install_lifts_source_logger_levels():
    """Records emitted by squadops/adapters loggers must clear their own
    filter so they reach the root handler. Without this, runtime-api
    (uvicorn-managed root at WARNING) silently drops every INFO record."""
    cfg = _prefect_cfg(log_level="INFO")
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock())

    # Start with both loggers at WARNING (the runtime-api default).
    logging.getLogger("squadops").setLevel(logging.WARNING)
    logging.getLogger("adapters").setLevel(logging.WARNING)

    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert handle is not None
    assert logging.getLogger("squadops").level == logging.INFO
    assert logging.getLogger("adapters").level == logging.INFO


async def test_handle_aclose_removes_handler_and_closes_forwarder():
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock(), enqueue=MagicMock())
    with patch(
        "adapters.cycles.log_forwarding_install.PrefectLogForwarder",
        return_value=fake_forwarder,
    ):
        handle = await install_prefect_log_handler(cfg)

    assert isinstance(handle, PrefectLogForwarderHandle)
    assert handle.handler in logging.getLogger().handlers

    await handle.aclose()

    assert handle.handler not in logging.getLogger().handlers
    fake_forwarder.close.assert_awaited_once()
