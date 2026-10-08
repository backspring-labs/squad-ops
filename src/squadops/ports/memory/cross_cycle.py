"""Cross-Cycle Memory's store (SIP-0110 §0.2, §0.8; the 2.2 plan's D13).

Phase 1's records live in Postgres beside the cycle registry, behind this port, with an
in-memory adapter for tests. It is not SIP-042's ``MemoryPort``, which is each agent's own
semantic store: the runtime API, where recall and the projections run, has none of those, and
Phase 1's recall is exact filtering that needs no embedding. It holds the observations (3a), and
the lessons, their approvals, each unit's pinned snapshot, each consuming task's exposure (3c), and
each exposure's assessments (3d).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from squadops.memory.assessment import Assessment
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Approval, PatternRevision, Snapshot, UnitKind
from squadops.memory.observations import Observation, ObservationSource


class RecordIncompatible(ValueError):
    """A stored record this code cannot read: written by a newer version, or damaged. Recall
    reports it as its own outcome (§0.8), never as nothing eligible."""


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

    @abstractmethod
    async def record_revision(self, revision: PatternRevision) -> bool:
        """Store a lesson's revision. Revisions are immutable: a second write of the same
        ``revision_id`` is refused when its content differs, and a no-op when it is the same.
        Returns whether it was new."""

    @abstractmethod
    async def list_revisions(self, project_id: str) -> list[PatternRevision]:
        """A project's revisions, by pattern and revision number."""

    @abstractmethod
    async def record_approval(self, approval: Approval) -> bool:
        """Store an approval; a second write of the same ``approval_id`` is a no-op."""

    @abstractmethod
    async def record_revocation(self, revoked: Approval) -> None:
        """Store an approval's revocation (``squadops.memory.approval.revoke``: when, by whom and
        why). Units admitted later pin without it (§0.7). An approval revoked once stays so."""

    @abstractmethod
    async def list_approvals(self, project_id: str) -> list[Approval]:
        """The approvals of a project's revisions, revoked ones included, oldest first."""

    @abstractmethod
    async def record_snapshot(self, snapshot: Snapshot) -> Snapshot:
        """Store a unit's pin, once: if the unit already pinned, that snapshot is returned and
        this one is dropped, so a restart reproduces the original (§0.7)."""

    @abstractmethod
    async def get_snapshot(self, unit_kind: UnitKind, unit_id: str) -> Snapshot | None:
        """The snapshot a unit pinned, or ``None`` for a unit that has not. Raises
        :class:`RecordIncompatible` for a stored pin this code cannot read."""

    @abstractmethod
    async def list_snapshots_holding(self, approval_id: str) -> list[Snapshot]:
        """The pinned snapshots that carry ``approval_id``: the units a revocation names."""

    @abstractmethod
    async def record_exposure(self, exposure: Exposure) -> bool:
        """Store a task's exposure, once per task of a run (``exposure_id``); composing the task
        again adds nothing. Returns whether it was new."""

    @abstractmethod
    async def list_exposures(self, run_id: str) -> list[Exposure]:
        """A run's exposures, by task."""

    @abstractmethod
    async def get_exposure(self, exposure_id: str) -> Exposure | None:
        """One exposure, or ``None``."""

    @abstractmethod
    async def list_project_exposures(self, project_id: str) -> list[Exposure]:
        """A project's exposures, oldest first."""

    @abstractmethod
    async def record_assessment(self, assessment: Assessment) -> bool:
        """Store an assessment; append-only, so a reassessment is a new record (§0.10). Returns
        whether it was new."""

    @abstractmethod
    async def list_assessments(self, project_id: str) -> list[Assessment]:
        """A project's assessments, oldest first."""
