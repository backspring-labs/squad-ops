"""
Heartbeat reporting port.

The health-check dashboard depends on agents periodically posting status updates.
This port allows the execution layer to emit those updates without importing
any legacy infrastructure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AgentHeartbeatReporter(ABC):
    """Port for reporting agent heartbeat/status updates."""

    @abstractmethod
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
        """
        Send an agent status update.

        Args:
            agent_id: Logical agent name/id (e.g., \"Neo\") — health-check stores lowercase.
            lifecycle_state: Canonical lifecycle state (STARTING/READY/WORKING/BLOCKED/CRASHED/STOPPING).
            current_task_id: Optional current task id.
            version: Optional agent/framework version string.
            tps: Optional throughput estimate.
            memory_count: Optional memory count metric.
        """
        raise NotImplementedError

