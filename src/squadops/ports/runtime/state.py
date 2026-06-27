"""
RuntimeStatePort — abstract interface for agent runtime-state persistence (SIP-0089 §10.1).

Phase 1 surface. Phases 2–4 add `AssignmentPort`, `FocusLeasePort`, and
`RuntimeActivityPort` alongside this one.

Operations preserve D17's non-authoritative-heartbeat semantics:
`ensure_state` initializes a missing row with safe defaults; `update_heartbeat`
must not overwrite coordinator-owned fields (`mode`, `focus`,
`current_assignment_ref`, `current_runtime_activity_id`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.runtime.models import AgentRuntimeState


class RuntimeStatePort(ABC):
    """Port for `AgentRuntimeState` CRUD and heartbeat updates."""

    @abstractmethod
    async def get_state(self, agent_id: str) -> AgentRuntimeState | None:
        """Return the current state for `agent_id`, or `None` if no row exists."""

    @abstractmethod
    async def upsert_state(self, state: AgentRuntimeState) -> AgentRuntimeState:
        """Persist `state` (insert or update by `agent_id`) and return it.

        Coordinator-owned writes go through this method. Heartbeat must not.
        """

    @abstractmethod
    async def ensure_state(self, agent_id: str) -> AgentRuntimeState:
        """Initialize default state for `agent_id` if no row exists; idempotent.

        Default values: `mode=ambient`, `runtime_status=online`,
        `interruptibility=high`, `focus=""`, all activity/assignment refs null.
        Calling on an existing row returns the existing row unchanged.
        """

    @abstractmethod
    async def update_heartbeat(
        self,
        agent_id: str,
        *,
        runtime_status: str | None = None,
    ) -> AgentRuntimeState:
        """Apply a heartbeat update (non-authoritative per D17).

        Always updates `last_heartbeat_at`. Optionally updates `runtime_status`
        (health only). Never writes `mode`, `focus`, `current_assignment_ref`,
        or `current_runtime_activity_id` — those are coordinator-owned (D16).

        Calls `ensure_state` first if no row exists.
        """

    @abstractmethod
    async def mark_offline(self, agent_id: str) -> AgentRuntimeState | None:
        """Mark a timed-out agent `offline` (health-only, non-authoritative per D17).

        Sets `runtime_status = 'offline'` and nothing else: it must NOT touch
        `last_heartbeat_at` (a dead agent's last heartbeat is meaningful) nor any
        coordinator-owned field (`mode`, `focus`, `current_assignment_ref`,
        `current_runtime_activity_id`). Unlike `update_heartbeat` it never creates
        a row — an agent that never heartbeated has no runtime state to mark.

        Returns the updated row, or `None` when no row exists or it was already
        `offline` (idempotent no-op). Used by the reconciliation loop so the
        coordinator's offline→duty rejection (§11.3) sees a crashed agent.
        """
