"""
HTTP adapter for reporting agent heartbeats to the runtime-api service.

Env:
- SQUADOPS_RUNTIME_API_URL: base URL for the runtime API
  (default: http://runtime-api:8001)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from squadops.ports.observability.heartbeat import AgentHeartbeatReporter

logger = logging.getLogger(__name__)


class HealthCheckHttpReporter(AgentHeartbeatReporter):
    """Posts agent status updates to the runtime-api agent-status endpoint.

    Writes go to the authed /api/v1 lane (#326). When ``token_provider`` is
    set (agent service identity via client credentials), each request carries
    a Bearer token; without it the request is unauthenticated — valid only
    for auth-disabled deployments.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: int = 5,
        fail_silently: bool = True,
        token_provider: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        # The final default is the runtime-api's in-network compose address — a
        # service-discovery default, not the config-masking class #333 targets:
        # an explicit SQUADOPS_RUNTIME_API_URL still wins, and a wrong endpoint
        # fails visibly (connection error), it doesn't fabricate required data.
        self._base_url = (
            base_url or os.getenv("SQUADOPS_RUNTIME_API_URL") or "http://runtime-api:8001"
        ).rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._fail_silently = fail_silently
        self._token_provider = token_provider

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
        url = f"{self._base_url}/api/v1/agents/status"
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "lifecycle_state": lifecycle_state,
            "current_task_id": current_task_id,
            "version": version,
            "tps": int(tps) if tps is not None else 0,
            "memory_count": memory_count,
        }

        try:
            headers: dict[str, str] = {}
            if self._token_provider is not None:
                token = await self._token_provider()
                headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                resp = await client.post(url, json=payload, headers=headers)
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
