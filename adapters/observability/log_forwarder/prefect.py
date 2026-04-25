"""Prefect implementation of :class:`LogForwarderPort`.

Wraps the lower-level ``PrefectLogForwarder`` (HTTP batcher) and
``PrefectLogHandler`` (``logging.Handler``) defined in
``adapters/cycles/prefect_log_forwarder.py``. The adapter is responsible for:

1. Constructing the forwarder and starting its background flush task.
2. Constructing the handler and attaching it to the root logger.
3. Lifting source-logger levels for the prefixes the handler watches, so
   uvicorn-rooted INFO records aren't dropped before they reach us.
4. Releasing both lifecycles atomically on ``aclose()``.

Core code never imports this module — only the factory does.
"""

from __future__ import annotations

import logging

from adapters.cycles.prefect_log_forwarder import (
    LogHandlerFilters,
    PrefectLogForwarder,
    PrefectLogHandler,
)
from squadops.ports.observability.log_forwarder import LogForwarderPort

logger = logging.getLogger(__name__)


class PrefectLogForwarderAdapter(LogForwarderPort):
    """Forwards Python ``logging`` records to a Prefect server's ``/api/logs``.

    The factory installs the handler and starts the flush loop before
    returning the adapter, so callers need only hold the reference and call
    ``aclose()`` on shutdown.
    """

    def __init__(
        self,
        forwarder: PrefectLogForwarder,
        handler: PrefectLogHandler,
    ) -> None:
        self._forwarder = forwarder
        self._handler = handler
        self._closed = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        logging.getLogger().removeHandler(self._handler)
        await self._forwarder.close()


async def install_prefect_adapter(
    api_url: str,
    log_level: int,
) -> PrefectLogForwarderAdapter:
    """Build, install, and start a Prefect log forwarder.

    Internal to the factory — kept separate so the factory stays declarative.
    """
    forwarder = PrefectLogForwarder(api_url=api_url)
    forwarder.start()
    filters = LogHandlerFilters(min_level=log_level)
    handler = PrefectLogHandler(forwarder, filters=filters)
    logging.getLogger().addHandler(handler)

    # Lift source-logger levels for the prefixes we forward. uvicorn's root is
    # WARNING, so without this INFO records from squadops/adapters never reach
    # the handler. Idempotent and bounded to the watched prefixes.
    for prefix in filters.allowed_prefixes:
        logging.getLogger(prefix).setLevel(log_level)

    return PrefectLogForwarderAdapter(forwarder=forwarder, handler=handler)


__all__ = ["PrefectLogForwarderAdapter", "install_prefect_adapter"]
