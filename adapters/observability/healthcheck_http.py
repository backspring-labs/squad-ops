"""
HTTP adapter for reporting agent heartbeats to the runtime-api service.

Env:
- SQUADOPS_RUNTIME_API_URL: base URL for the runtime API
  (default: http://runtime-api:8001)
- SQUADOPS_HEALTH_CHECK_URL: legacy env var (fallback)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from squadops.ports.observability.heartbeat import AgentHeartbeatReporter

logger = logging.getLogger(__name__)


class HealthCheckHttpReporter(AgentHeartbeatReporter):
    """Posts agent status updates to the runtime-api health endpoints."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: int = 5,
        fail_silently: bool = True,
    ) -> None:
        self._base_url = (
            base_url
            or os.getenv("SQUADOPS_RUNTIME_API_URL")
            or os.getenv("SQUADOPS_HEALTH_CHECK_URL")
            or "http://runtime-api:8001"
        ).rstrip("/")
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
            "tps": int(tps) if tps is not None else 0,
            "memory_count": memory_count,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code >= 400:
                    raise RuntimeError(f"runtime-api responded {resp.status_code}: {resp.text}")
        except Exception as e:
            if self._fail_silently:
                logger.warning(
                    "heartbeat_send_failed",
                    extra={
                        "agent_id": agent_id,
                        "lifecycle_state": lifecycle_state,
                        "error": str(e),
                    },
                )
                return
            raise
