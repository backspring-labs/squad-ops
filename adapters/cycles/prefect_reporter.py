"""Prefect REST API reporter for cycle execution visibility.

Concrete :class:`WorkflowTrackerPort` implementation. Reports cycle execution
progress to Prefect 2.x server via REST API. Uses httpx.AsyncClient — no
``prefect`` SDK dependency.

Best-effort: all public methods catch exceptions and log warnings.
Execution never blocks on Prefect failures.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from squadops.ports.cycles import WorkflowTrackerPort

logger = logging.getLogger(__name__)


class PrefectReporter(WorkflowTrackerPort):
    """Prefect-backed :class:`WorkflowTrackerPort`.

    Best-effort: all methods catch exceptions and log warnings. Execution
    never blocks on Prefect failures.
    """

    def __init__(self, api_url: str, timeout: int = 10) -> None:
        self._api_url = api_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._flow_id: str | None = None  # Cached after first ensure_flow()

    async def ensure_flow(self, flow_name: str = "cycle-execution") -> str:
        """Create or get the flow by name. Returns flow_id."""
        try:
            if self._flow_id:
                return self._flow_id

            # Try to find existing flow by name
            resp = await self._client.post(
                f"{self._api_url}/flows/filter",
                json={"flows": {"name": {"any_": [flow_name]}}},
            )
            resp.raise_for_status()
            flows = resp.json()
            if flows:
                self._flow_id = flows[0]["id"]
                return self._flow_id

            # Create new flow
            resp = await self._client.post(
                f"{self._api_url}/flows/",
                json={"name": flow_name},
            )
            resp.raise_for_status()
            self._flow_id = resp.json()["id"]
            return self._flow_id

        except Exception:
            logger.warning("Prefect ensure_flow failed", exc_info=True)
            # Return a placeholder so callers can proceed
            return self._flow_id or f"unknown-{uuid4().hex[:8]}"

    async def create_flow_run(
        self,
        flow_id: str,
        run_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """Create a flow run. Returns flow_run_id."""
        try:
            resp = await self._client.post(
                f"{self._api_url}/flow_runs/",
                json={
                    "flow_id": flow_id,
                    "name": run_name,
                    "parameters": parameters or {},
                    "state": {
                        "type": "SCHEDULED",
                        "name": "Scheduled",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()["id"]
        except Exception:
            logger.warning("Prefect create_flow_run failed", exc_info=True)
            return f"unknown-{uuid4().hex[:8]}"

    async def create_task_run(
        self,
        flow_run_id: str,
        task_key: str,
        task_name: str,
    ) -> str:
        """Create a task run within a flow run. Returns task_run_id."""
        try:
            resp = await self._client.post(
                f"{self._api_url}/task_runs/",
                json={
                    "flow_run_id": flow_run_id,
                    "task_key": task_key,
                    "name": task_name,
                    "dynamic_key": uuid4().hex[:8],
                },
            )
            resp.raise_for_status()
            return resp.json()["id"]
        except Exception:
            logger.warning("Prefect create_task_run failed", exc_info=True)
            return f"unknown-{uuid4().hex[:8]}"

    async def set_flow_run_state(self, flow_run_id: str, state_type: str, state_name: str) -> None:
        """Update flow run state (RUNNING, COMPLETED, FAILED, CANCELLED)."""
        try:
            resp = await self._client.post(
                f"{self._api_url}/flow_runs/{flow_run_id}/set_state",
                json={
                    "state": {
                        "type": state_type,
                        "name": state_name,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    "force": True,
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.warning(
                "Prefect set_flow_run_state(%s, %s) failed",
                flow_run_id,
                state_type,
                exc_info=True,
            )

    async def set_task_run_state(self, task_run_id: str, state_type: str, state_name: str) -> None:
        """Update task run state."""
        try:
            resp = await self._client.post(
                f"{self._api_url}/task_runs/{task_run_id}/set_state",
                json={
                    "state": {
                        "type": state_type,
                        "name": state_name,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    "force": True,
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.warning(
                "Prefect set_task_run_state(%s, %s) failed",
                task_run_id,
                state_type,
                exc_info=True,
            )

    async def close(self) -> None:
        """Close the httpx client."""
        await self._client.aclose()
