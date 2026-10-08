"""Cross-Cycle Memory's store (SIP-0110 §0.2, §0.8; the 2.2 plan's D13).

Phase 1's records live in Postgres beside the cycle registry, behind this port, with an
in-memory adapter for tests. It is not SIP-042's ``MemoryPort``, which is each agent's own
semantic store: the runtime API, where recall and the projections run, has none of those, and
Phase 1's recall is exact filtering that needs no embedding. Slice 3a stores observations; the
pattern revisions and approvals join in 3d.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from squadops.memory.observations import Observation, ObservationSource


class CrossCycleMemoryStorePort(ABC):
    @abstractmethod
    async def record_observations(self, observations: Sequence[Observation]) -> int:
        """Store each observation not already stored (by ``source_id``), and return how many were
        new. Projecting a source record again adds nothing (§0.3)."""

    @abstractmethod
    async def list_observations(
        self, project_id: str, *, source: ObservationSource | None = None
    ) -> list[Observation]:
        """A project's observations, oldest first by ``observed_at``, then ``source_id``."""
