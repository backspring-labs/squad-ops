"""WorkflowTrackerPort — per-task workflow tracking abstraction.

Used by the distributed flow executor and the cycle event bridges to record
flow runs, task runs, and their state transitions on an external workflow UI
(today: Prefect; tomorrow: anything else with a comparable concept).

Vendor-specific concerns (REST endpoints, auth, retry policy) live entirely
in adapters. Core composition roots receive a :class:`WorkflowTrackerPort`
through a factory and never import a concrete reporter by name.

Design follows the always-inject pattern used by SIP-0061
(``LLMObservabilityPort``) and SIP-0087 (``LogForwarderPort``): a NoOp
adapter is returned when no backend is configured, so callers never branch
on ``None``. Public methods MUST be best-effort — implementations swallow
transport errors and log warnings rather than raising.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WorkflowTrackerPort(ABC):
    """Records cycle execution structure (flow runs / task runs) on an external UI.

    All methods are async and best-effort. ``ensure_flow``, ``create_flow_run``,
    and ``create_task_run`` MUST always return a non-empty string identifier;
    on failure, implementations SHOULD return a synthetic placeholder so the
    caller can proceed.
    """

    @abstractmethod
    async def ensure_flow(self, flow_name: str = "cycle-execution") -> str:
        """Get-or-create a flow by name. Returns ``flow_id``."""

    @abstractmethod
    async def create_flow_run(
        self,
        flow_id: str,
        run_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """Create a flow run inside the given flow. Returns ``flow_run_id``."""

    @abstractmethod
    async def create_task_run(
        self,
        flow_run_id: str,
        task_key: str,
        task_name: str,
    ) -> str:
        """Create a task run inside the given flow run. Returns ``task_run_id``."""

    @abstractmethod
    async def set_flow_run_state(
        self,
        flow_run_id: str,
        state_type: str,
        state_name: str,
    ) -> None:
        """Update the flow run's state (RUNNING, COMPLETED, FAILED, ...)."""

    @abstractmethod
    async def set_task_run_state(
        self,
        task_run_id: str,
        state_type: str,
        state_name: str,
    ) -> None:
        """Update the task run's state (RUNNING, COMPLETED, FAILED, ...)."""

    @abstractmethod
    async def close(self) -> None:
        """Release any held transport resources. Idempotent."""
