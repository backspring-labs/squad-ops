"""Helpers for installing the Prefect log forwarder (SIP-0087 phase-3).

Lives outside ``main.py`` so it can be unit-tested without triggering the
runtime-api's module-level config load.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def install_prefect_log_handler(config: Any) -> tuple[Any, logging.Handler] | tuple[None, None]:
    """Install ``PrefectLogHandler`` on the root logger.

    Returns ``(forwarder, handler)`` if installed, or ``(None, None)`` when
    skipped (Prefect not configured, flag disabled, or init failure).
    """
    if not config.prefect.api_url or not config.prefect.log_forwarding:
        return None, None
    try:
        from adapters.cycles.prefect_log_forwarder import (
            LogHandlerFilters,
            PrefectLogForwarder,
            PrefectLogHandler,
        )

        level = logging.getLevelNamesMapping().get(
            config.prefect.log_level.upper(), logging.INFO
        )
        forwarder = PrefectLogForwarder(api_url=config.prefect.api_url)
        forwarder.start()
        handler = PrefectLogHandler(forwarder, filters=LogHandlerFilters(min_level=level))
        logging.getLogger().addHandler(handler)
        logger.info(
            "Prefect log forwarding enabled (level=%s, api_url=%s)",
            config.prefect.log_level.upper(),
            config.prefect.api_url,
        )
        return forwarder, handler
    except Exception as e:
        logger.error("Failed to initialize Prefect log forwarder: %s", e)
        return None, None


async def teardown_prefect_log_handler(
    forwarder: Any | None, handler: logging.Handler | None
) -> None:
    """Remove the handler from root logger and close the forwarder."""
    if handler is not None:
        logging.getLogger().removeHandler(handler)
    if forwarder is not None:
        await forwarder.close()
