"""Factory for :class:`LogForwarderPort` implementations.

Selects a concrete adapter based on configuration. Returns an instance that is
already attached to the logging tree and has its background flush task
running, so callers only manage teardown via ``await port.aclose()``.

Selection rules (mirrors ``create_llm_observability_provider`` in SIP-0061):
- Prefect-shaped config with ``api_url`` set and ``log_forwarding=True`` →
  :class:`PrefectLogForwarderAdapter`.
- Anything else (or init failure) → :class:`NoOpLogForwarder`. Telemetry is
  best-effort by SIP-0087 design; a degraded forwarder must never block boot.
"""

from __future__ import annotations

import logging

from adapters.observability.log_forwarder.noop import NoOpLogForwarder
from adapters.observability.log_forwarder.prefect import install_prefect_adapter
from squadops.config.schema import PrefectConfig
from squadops.ports.observability.log_forwarder import LogForwarderPort

logger = logging.getLogger(__name__)


async def create_log_forwarder(prefect_cfg: PrefectConfig | None) -> LogForwarderPort:
    """Build the right log forwarder for the given config.

    Always returns a non-None port — callers never need to null-check.
    """
    if prefect_cfg is None or not prefect_cfg.api_url or not prefect_cfg.log_forwarding:
        return NoOpLogForwarder()
    try:
        # PrefectConfig.log_level is a Literal at the schema layer, so the
        # mapping lookup cannot KeyError here.
        level = logging.getLevelNamesMapping()[prefect_cfg.log_level]
        adapter = await install_prefect_adapter(
            api_url=prefect_cfg.api_url,
            log_level=level,
        )
        logger.info(
            "Log forwarder initialized (backend=prefect, level=%s, api_url=%s)",
            prefect_cfg.log_level,
            prefect_cfg.api_url,
        )
        return adapter
    except Exception as e:
        logger.error("Failed to initialize log forwarder; falling back to NoOp: %s", e)
        return NoOpLogForwarder()


__all__ = ["create_log_forwarder"]
