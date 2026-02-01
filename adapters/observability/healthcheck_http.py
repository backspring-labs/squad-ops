"""
HTTP adapter for reporting agent heartbeats to the health-check service.

Env:
- SQUADOPS_HEALTH_CHECK_URL: base URL for the health-check service
  (default: http://health-check:8000)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

from squadops.ports.observability.heartbeat import AgentHeartbeatReporter

logger = logging.getLogger(__name__)


class HealthCheckHttpReporter(AgentHeartbeatReporter):
    """Posts agent status updates to the health-check service."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: int = 5,
        fail_silently: bool = True,
    ) -> None:
        self._base_url = (base_url or os.getenv("SQUADOPS_HEALTH_CHECK_URL") or "http://health-check:8000").rstrip(
            "/"
        )
        self._timeout_seconds = timeout_seconds
        self._fail_silently = fail_silently

    async def send_status(
        self,
        *,
        agent_id: str,
        lifecycle_state: str,
        current_task_id: str | None = None,
        version: str | None = None,
        tps: float | None = None,
        memory_count: int | None = None,
    ) -> None:
        url = f"{self._base_url}/health/agents/status"
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "lifecycle_state": lifecycle_state,
            "current_task_id": current_task_id,
            "version": version,
            # Health-check expects an int; be forgiving and coerce.
            "tps": int(tps) if tps is not None else 0,
            "memory_count": memory_count,
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        raise RuntimeError(f"health-check responded {resp.status}: {body}")
        except Exception as e:
            if self._fail_silently:
                logger.warning(
                    "heartbeat_send_failed",
                    extra={"agent_id": agent_id, "lifecycle_state": lifecycle_state, "error": str(e)},
                )
                return
            raise

