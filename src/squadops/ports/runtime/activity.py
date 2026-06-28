"""
RuntimeActivityPort — abstract interface for RuntimeActivity persistence
(SIP-0089 §10.6, Phase 4 §4.3).

A RuntimeActivity is the observable unit of work an agent performs within a mode.
At most one *active* (`pending`/`running`/`paused`) activity per agent (D9),
enforced by the §4.2 partial unique index — `start_activity` raises if one
already exists. Handlers/workloads emit these at task granularity (D19); the
coordinator (§4.5) pauses/aborts the current activity during a mode transition.

The terminal helpers (`complete`/`fail`/`abort`) and their `evidence_ref` /
`reason_code` are surfaced on the canonical `runtime_activity.*` event (D18); the
reason is not persisted as a column in v1.1 — `state` + `ended_at` are.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.runtime.models import (
        ActivitySourceKind,
        ActivityState,
        RuntimeActivity,
        RuntimeMode,
    )


class RuntimeActivityPort(ABC):
    """Port for `RuntimeActivity` persistence and lifecycle transitions."""

    @abstractmethod
    async def start_activity(
        self,
        agent_id: str,
        *,
        mode: RuntimeMode,
        activity_type: str,
        goal: str,
        source_kind: ActivitySourceKind,
        source_ref: str,
        priority: int = 0,
        cycle_id: str | None = None,
        workload_id: str | None = None,
        task_id: str | None = None,
        can_pause: bool = False,
        can_resume: bool = False,
        can_abort: bool = True,
        completion_conditions: tuple[dict, ...] = (),
        evidence_requirements: tuple[dict, ...] = (),
    ) -> RuntimeActivity:
        """Create a new `running` activity for `agent_id` and return it.

        Mints the id and sets `started_at`. Raises if the agent already holds an
        active activity (D9 — the partial unique index rejects a second). Source
        identity is explicit (`cycle_id`/`workload_id`/`task_id`); `source_ref` is
        opaque and never parsed by core.
        """

    @abstractmethod
    async def update_state(self, activity_id: str, state: ActivityState) -> RuntimeActivity | None:
        """Transition an activity to `state`, managing timestamps automatically.

        `paused` stamps `paused_at`; a terminal state stamps `ended_at`; `running`
        ensures `started_at` is set (resume keeps the original). Returns the updated
        activity, or `None` if no such activity exists.
        """

    @abstractmethod
    async def complete_activity(
        self, activity_id: str, *, evidence_ref: str | None = None
    ) -> RuntimeActivity | None:
        """Terminal helper: mark the activity `completed`. `evidence_ref` is
        event-surfaced (proof of completion), not persisted in v1.1."""

    @abstractmethod
    async def fail_activity(self, activity_id: str, reason_code: str) -> RuntimeActivity | None:
        """Terminal helper: mark the activity `failed`. `reason_code` is
        event-surfaced (D18), not persisted in v1.1."""

    @abstractmethod
    async def abort_activity(self, activity_id: str, reason_code: str) -> RuntimeActivity | None:
        """Terminal helper: mark the activity `aborted` (non-cooperative stop).
        `reason_code` is event-surfaced (D18), not persisted in v1.1."""

    @abstractmethod
    async def get_current_activity(self, agent_id: str) -> RuntimeActivity | None:
        """Return the agent's current (active) activity, or `None`."""
