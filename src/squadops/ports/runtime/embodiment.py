"""
EmbodimentStatePort — abstract interface for Embodiment record + lifecycle-state
persistence (SIP-0090 §5).

Phase 1 surface (plan §4.3). A **record/lifecycle store, not an action surface**:
it has no method that decides intent/mode/priority or executes an embodied action.
Attaching, detaching, sending, and listening are the Phase-2 ``EmbodimentSurfacePort``'s
job — and even there only for *already-authorized* requests (§6 authority boundary).
Keeping the two ports separate is deliberate; they never merge.

Named to mirror SIP-0089's ``RuntimeStatePort``. Mutating methods accept an optional
``conn`` for the §-D25 unit-of-work seam (as ``RuntimeStatePort.upsert_state`` does),
so a Phase-3 coordinator can commit a transition atomically with its other writes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.runtime.embodiment import AttachmentState, Embodiment, Health


class EmbodimentStatePort(ABC):
    """Port for `Embodiment` record CRUD and lifecycle-state writes (SIP-0090 §5)."""

    @abstractmethod
    async def create_embodiment(self, embodiment: Embodiment, *, conn: Any = None) -> Embodiment:
        """Persist a new `Embodiment` record and return it."""

    @abstractmethod
    async def get_embodiment(self, embodiment_id: str) -> Embodiment | None:
        """Return the `Embodiment` for `embodiment_id`, or `None` if no row exists."""

    @abstractmethod
    async def get_active_embodiment(self, agent_id: str) -> Embodiment | None:
        """Return the agent's single active embodiment (§5.5), or `None`.

        "Active" = attachment_state in {attached, desynced, reconnecting}. At most
        one such row exists per agent — the single-active invariant (the DB partial
        unique index in 1b is the hard backstop).
        """

    @abstractmethod
    async def list_for_agent(self, agent_id: str) -> tuple[Embodiment, ...]:
        """Return all `Embodiment` records for `agent_id` (any attachment state)."""

    @abstractmethod
    async def transition_state(
        self, embodiment_id: str, target_state: AttachmentState, *, conn: Any = None
    ) -> Embodiment:
        """Persist an attachment-state transition and return the updated record.

        The transition is validated **upstream** by the `EmbodimentCoordinator`
        (allow-list + single-active rule); this method only writes the result.
        """

    @abstractmethod
    async def update_health(
        self, embodiment_id: str, health: Health, *, conn: Any = None
    ) -> Embodiment:
        """Persist a health change for the embodiment and return the updated record."""

    @abstractmethod
    async def update_location(
        self, embodiment_id: str, location_ref: str | None, *, conn: Any = None
    ) -> Embodiment:
        """Persist an opaque `location_ref` (§5.4) and return the updated record.

        `location_ref` is stored and compared verbatim; this port never parses it.
        """
