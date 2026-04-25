"""Tests for ``adapters.observability.log_forwarder`` factory + adapters
(SIP-0087 hex-arch refactor).

Behavior-focused: drive the installed handler with real ``LogRecord`` objects
and assert what reaches the underlying forwarder. Also pins the always-inject
contract — the factory MUST return a usable port even when no backend is
configured, so core never branches on ``is None``.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.observability.log_forwarder import (
    NoOpLogForwarder,
    PrefectLogForwarderAdapter,
    create_log_forwarder,
)
from squadops.config.schema import PrefectConfig
from squadops.ports.observability import LogForwarderPort
from squadops.telemetry.context import use_correlation_context
from squadops.telemetry.models import CorrelationContext

_PREFECT_FWD_PATCH = "adapters.observability.log_forwarder.prefect.PrefectLogForwarder"


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
# Always-inject contract: factory always returns a port
# ---------------------------------------------------------------------------


async def test_factory_returns_noop_when_config_is_none():
    forwarder = await create_log_forwarder(None)
    assert isinstance(forwarder, NoOpLogForwarder)
    assert isinstance(forwarder, LogForwarderPort)
    # aclose is safe to call (and idempotent).
    await forwarder.aclose()
    await forwarder.aclose()


async def test_factory_returns_noop_when_api_url_unset():
    cfg = _prefect_cfg(api_url="")
    with patch(_PREFECT_FWD_PATCH) as fwd_cls:
        forwarder = await create_log_forwarder(cfg)
    fwd_cls.assert_not_called()
    assert isinstance(forwarder, NoOpLogForwarder)


async def test_factory_returns_noop_when_log_forwarding_disabled():
    cfg = _prefect_cfg(log_forwarding=False)
    with patch(_PREFECT_FWD_PATCH) as fwd_cls:
        forwarder = await create_log_forwarder(cfg)
    fwd_cls.assert_not_called()
    assert isinstance(forwarder, NoOpLogForwarder)


async def test_factory_falls_back_to_noop_on_init_failure():
    cfg = _prefect_cfg()
    with patch(_PREFECT_FWD_PATCH, side_effect=RuntimeError("boom")):
        forwarder = await create_log_forwarder(cfg)
    assert isinstance(forwarder, NoOpLogForwarder)


# ---------------------------------------------------------------------------
# Behavior: configured level governs which records are forwarded
# ---------------------------------------------------------------------------


async def test_records_below_configured_level_are_dropped():
    cfg = _prefect_cfg(log_level="WARNING")
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    assert isinstance(forwarder, PrefectLogForwarderAdapter)
    with use_correlation_context(_ctx_with_run_ids()):
        logging.getLogger("squadops.test").info("ignored")
    fake_forwarder.enqueue.assert_not_called()


async def test_records_at_or_above_level_are_forwarded():
    cfg = _prefect_cfg(log_level="WARNING")
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    with use_correlation_context(_ctx_with_run_ids()):
        logging.getLogger("squadops.test").warning("hit")
        logging.getLogger("adapters.test").error("hit")
    assert fake_forwarder.enqueue.call_count == 2
    await forwarder.aclose()


async def test_default_info_level_drops_debug():
    cfg = _prefect_cfg()  # log_level="INFO"
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    debug_logger = logging.getLogger("squadops.test_debug")
    debug_logger.setLevel(logging.DEBUG)
    with use_correlation_context(_ctx_with_run_ids()):
        debug_logger.debug("ignored")
        debug_logger.info("hit")
    assert fake_forwarder.enqueue.call_count == 1
    await forwarder.aclose()


async def test_records_outside_allowed_prefixes_are_dropped():
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    with use_correlation_context(_ctx_with_run_ids()):
        logging.getLogger("httpx").info("noise")
        logging.getLogger("aio_pika.heartbeat").info("noise")
    fake_forwarder.enqueue.assert_not_called()
    await forwarder.aclose()


async def test_records_without_correlation_context_are_dropped():
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock(), close=AsyncMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    # No use_correlation_context → record is system-level and must be dropped.
    logging.getLogger("squadops.test").info("ignored")
    fake_forwarder.enqueue.assert_not_called()
    await forwarder.aclose()


# ---------------------------------------------------------------------------
# Side-effects of installation
# ---------------------------------------------------------------------------


async def test_install_lifts_source_logger_levels():
    """Records emitted by squadops/adapters loggers must clear their own
    filter so they reach the root handler. Without this, runtime-api
    (uvicorn-managed root at WARNING) silently drops every INFO record."""
    cfg = _prefect_cfg(log_level="INFO")
    fake_forwarder = MagicMock(start=MagicMock(), enqueue=MagicMock(), close=AsyncMock())

    logging.getLogger("squadops").setLevel(logging.WARNING)
    logging.getLogger("adapters").setLevel(logging.WARNING)

    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    assert logging.getLogger("squadops").level == logging.INFO
    assert logging.getLogger("adapters").level == logging.INFO
    await forwarder.aclose()


# ---------------------------------------------------------------------------
# Adapter lifecycle
# ---------------------------------------------------------------------------


async def test_aclose_removes_handler_and_closes_forwarder():
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock(), enqueue=MagicMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    assert isinstance(forwarder, PrefectLogForwarderAdapter)
    handler = forwarder._handler  # lifecycle assertion only — not asserting on internals' values
    assert handler in logging.getLogger().handlers

    await forwarder.aclose()

    assert handler not in logging.getLogger().handlers
    fake_forwarder.close.assert_awaited_once()


async def test_aclose_is_idempotent():
    """Double-aclose must not double-close the underlying forwarder."""
    cfg = _prefect_cfg()
    fake_forwarder = MagicMock(start=MagicMock(), close=AsyncMock(), enqueue=MagicMock())
    with patch(_PREFECT_FWD_PATCH, return_value=fake_forwarder):
        forwarder = await create_log_forwarder(cfg)

    await forwarder.aclose()
    await forwarder.aclose()

    fake_forwarder.close.assert_awaited_once()
