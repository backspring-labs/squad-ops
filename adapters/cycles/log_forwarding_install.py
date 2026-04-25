"""Composition-root install/teardown for the Prefect log forwarder (SIP-0087).

Lives next to ``prefect_log_forwarder`` in ``adapters/cycles/`` because it is
adapter-installation glue, not domain logic. Both the runtime-api startup and
the agent entrypoint import from here, so the dependency direction stays
``runtime/agent → adapters/`` (never the reverse).

Use ``install_prefect_log_handler(prefect_cfg)`` to obtain a
``PrefectLogForwarderHandle`` and ``await handle.aclose()`` on shutdown. The
handle owns both the forwarder and the root-logger handler so both lifecycles
are released atomically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from adapters.cycles.prefect_log_forwarder import (
    LogHandlerFilters,
    PrefectLogForwarder,
    PrefectLogHandler,
)
from squadops.config.schema import PrefectConfig

logger = logging.getLogger(__name__)


@dataclass
class PrefectLogForwarderHandle:
    """Owns the forwarder + root-logger handler installed by ``install_prefect_log_handler``."""

    forwarder: PrefectLogForwarder
    handler: PrefectLogHandler

    async def aclose(self) -> None:
        """Remove the handler from the root logger and close the forwarder."""
        logging.getLogger().removeHandler(self.handler)
        await self.forwarder.close()


async def install_prefect_log_handler(
    prefect_cfg: PrefectConfig,
) -> PrefectLogForwarderHandle | None:
    """Install ``PrefectLogHandler`` on the root logger.

    Returns ``None`` when Prefect is not configured or ``log_forwarding`` is
    disabled. Init failures are logged and swallowed (telemetry is best-effort
    by SIP-0087 design); a degraded forwarder must never block boot.

    Async because ``PrefectLogForwarder.start()`` schedules an ``asyncio`` task
    on the calling loop — making the precondition explicit in the signature.
    """
    if not prefect_cfg.api_url or not prefect_cfg.log_forwarding:
        return None
    try:
        # PrefectConfig.log_level is a Literal at the schema layer, so the
        # mapping lookup cannot KeyError here.
        level = logging.getLevelNamesMapping()[prefect_cfg.log_level]
        forwarder = PrefectLogForwarder(api_url=prefect_cfg.api_url)
        forwarder.start()
        handler = PrefectLogHandler(forwarder, filters=LogHandlerFilters(min_level=level))
        logging.getLogger().addHandler(handler)
        logger.info(
            "Prefect log forwarding enabled (level=%s, api_url=%s)",
            prefect_cfg.log_level,
            prefect_cfg.api_url,
        )
        return PrefectLogForwarderHandle(forwarder=forwarder, handler=handler)
    except Exception as e:
        logger.error("Failed to initialize Prefect log forwarder: %s", e)
        return None


__all__ = ["PrefectLogForwarderHandle", "install_prefect_log_handler"]
