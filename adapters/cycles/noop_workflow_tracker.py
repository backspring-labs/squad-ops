"""NoOp :class:`WorkflowTrackerPort` — always-inject default.

Used by :func:`create_workflow_tracker` when no workflow-tracking backend is
configured. Returns synthetic placeholder IDs from ``ensure_flow``,
``create_flow_run``, and ``create_task_run`` so callers can proceed without
branching on enablement; state setters and ``close`` are pure no-ops.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from squadops.ports.cycles import WorkflowTrackerPort


class NoOpWorkflowTracker(WorkflowTrackerPort):
    """Does nothing. Returns ``noop-<hex>`` placeholders for create_* methods."""

    @staticmethod
    def _placeholder() -> str:
        return f"noop-{uuid4().hex[:8]}"

    async def ensure_flow(self, flow_name: str = "cycle-execution") -> str:
        return self._placeholder()

    async def create_flow_run(
        self,
        flow_id: str,
        run_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        return self._placeholder()

    async def create_task_run(
        self,
        flow_run_id: str,
        task_key: str,
        task_name: str,
    ) -> str:
        return self._placeholder()

    async def set_flow_run_state(
        self,
        flow_run_id: str,
        state_type: str,
        state_name: str,
    ) -> None:
        return None

    async def set_task_run_state(
        self,
        task_run_id: str,
        state_type: str,
        state_name: str,
    ) -> None:
        return None

    async def close(self) -> None:
        return None
