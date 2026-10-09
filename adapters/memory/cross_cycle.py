"""Cross-Cycle Memory's store, in Postgres beside the cycle registry, and in memory for tests
(SIP-0110 §0.8, D13). Selected as the cycle registry is, by the registry's required provider."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from squadops.memory.approval import units_holding
from squadops.memory.assessment import Assessment
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Approval, PatternRevision, Snapshot, UnitKind
from squadops.memory.observations import Observation, ObservationSource
from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort, RecordIncompatible


def _ordered(observations: list[Observation]) -> list[Observation]:
    return sorted(observations, key=lambda o: (o.observed_at, o.source_id))


class RevisionConflict(ValueError):
    """A revision id written again with different content: a revision is immutable (§0.2)."""


class InMemoryCrossCycleMemoryStore(CrossCycleMemoryStorePort):
    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}
        self._revisions: dict[str, PatternRevision] = {}
        self._approvals: dict[str, Approval] = {}
        self._snapshots: dict[tuple[str, str], Snapshot] = {}
        self._exposures: dict[str, Exposure] = {}
        self._assessments: dict[str, Assessment] = {}

    async def record_observations(self, observations: Sequence[Observation]) -> int:
        new = 0
        for observation in observations:
            if observation.source_id not in self._observations:
                self._observations[observation.source_id] = observation
                new += 1
        return new

    async def list_observations(
        self, project_id: str, *, source: ObservationSource | None = None
    ) -> list[Observation]:
        return _ordered(
            [
                o
                for o in self._observations.values()
                if o.project_id == project_id and (source is None or o.source is source)
            ]
        )

    async def record_revision(self, revision: PatternRevision) -> bool:
        held = self._revisions.get(revision.revision_id)
        if held is not None:
            if held != revision:
                raise RevisionConflict(f"{revision.revision_id} already holds other content")
            return False
        self._revisions[revision.revision_id] = revision
        return True

    async def list_revisions(self, project_id: str) -> list[PatternRevision]:
        return sorted(
            (r for r in self._revisions.values() if r.applicability.project_id == project_id),
            key=lambda r: (r.pattern_id, r.revision),
        )

    async def record_approval(self, approval: Approval) -> bool:
        if approval.approval_id in self._approvals:
            return False
        self._approvals[approval.approval_id] = approval
        return True

    async def record_revocation(self, revoked: Approval) -> None:
        held = self._approvals[revoked.approval_id]
        if held.revoked_at is None:
            self._approvals[revoked.approval_id] = revoked

    async def list_approvals(self, project_id: str) -> list[Approval]:
        return sorted(
            (a for a in self._approvals.values() if a.applicability.project_id == project_id),
            key=lambda a: (a.approved_at, a.approval_id),
        )

    async def record_snapshot(self, snapshot: Snapshot) -> Snapshot:
        key = (snapshot.unit_kind.value, snapshot.unit_id)
        return self._snapshots.setdefault(key, snapshot)

    async def get_snapshot(self, unit_kind: UnitKind, unit_id: str) -> Snapshot | None:
        return self._snapshots.get((unit_kind.value, unit_id))

    async def list_snapshots_holding(self, approval_id: str) -> list[Snapshot]:
        return units_holding(approval_id, self._snapshots.values())

    async def record_exposure(self, exposure: Exposure) -> bool:
        if exposure.exposure_id in self._exposures:
            return False
        self._exposures[exposure.exposure_id] = exposure
        return True

    async def list_exposures(self, run_id: str) -> list[Exposure]:
        return sorted(
            (e for e in self._exposures.values() if e.run_id == run_id),
            key=lambda e: (e.task_id, e.attempt),
        )

    async def get_exposure(self, exposure_id: str) -> Exposure | None:
        return self._exposures.get(exposure_id)

    async def list_project_exposures(self, project_id: str) -> list[Exposure]:
        return sorted(
            (e for e in self._exposures.values() if e.query.project_id == project_id),
            key=lambda e: (e.recorded_at, e.exposure_id),
        )

    async def record_assessment(self, assessment: Assessment) -> bool:
        if assessment.assessment_id in self._assessments:
            return False
        self._assessments[assessment.assessment_id] = assessment
        return True

    async def list_assessments(self, project_id: str) -> list[Assessment]:
        return sorted(
            (a for a in self._assessments.values() if a.project_id == project_id),
            key=lambda a: (a.assessed_at, a.assessment_id),
        )


class PostgresCrossCycleMemoryStore(CrossCycleMemoryStorePort):
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def record_observations(self, observations: Sequence[Observation]) -> int:
        new = 0
        async with self._pool.acquire() as conn, conn.transaction():
            for o in observations:
                status = await conn.execute(
                    "INSERT INTO memory_observations (source_id, source, project_id, campaign_id, "
                    "cycle_id, run_id, task_id, observed_at, classification, evidence) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
                    "ON CONFLICT (source_id) DO NOTHING",
                    o.source_id,
                    o.source.value,
                    o.project_id,
                    o.campaign_id,
                    o.cycle_id,
                    o.run_id,
                    o.task_id,
                    o.observed_at,
                    o.classification.to_dict(),
                    dict(o.evidence),
                )
                new += status.endswith(" 1")
        return new

    async def list_observations(
        self, project_id: str, *, source: ObservationSource | None = None
    ) -> list[Observation]:
        query = (
            "SELECT source_id, source, project_id, campaign_id, cycle_id, run_id, task_id, "
            "observed_at, classification, evidence FROM memory_observations WHERE project_id = $1"
        )
        args: list[Any] = [project_id]
        if source is not None:
            query += " AND source = $2"
            args.append(source.value)
        query += " ORDER BY observed_at, source_id"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [
            Observation.from_dict({**dict(row), "observed_at": row["observed_at"].isoformat()})
            for row in rows
        ]

    async def record_revision(self, revision: PatternRevision) -> bool:
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                "INSERT INTO memory_revisions (revision_id, pattern_id, revision, project_id, "
                "revision_body) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (revision_id) DO NOTHING",
                revision.revision_id,
                revision.pattern_id,
                revision.revision,
                revision.applicability.project_id,
                revision.to_dict(),
            )
            if status.endswith(" 1"):
                return True
            held = await conn.fetchval(
                "SELECT revision_body FROM memory_revisions WHERE revision_id = $1",
                revision.revision_id,
            )
        if PatternRevision.from_dict(held) != revision:
            raise RevisionConflict(f"{revision.revision_id} already holds other content")
        return False

    async def list_revisions(self, project_id: str) -> list[PatternRevision]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT revision_body FROM memory_revisions WHERE project_id = $1 "
                "ORDER BY pattern_id, revision",
                project_id,
            )
        return [PatternRevision.from_dict(r["revision_body"]) for r in rows]

    async def record_approval(self, approval: Approval) -> bool:
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                "INSERT INTO memory_approvals (approval_id, revision_id, project_id, approved_at, "
                "approval_body) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (approval_id) DO NOTHING",
                approval.approval_id,
                approval.revision_id,
                approval.applicability.project_id,
                approval.approved_at,
                approval.to_dict(),
            )
        return status.endswith(" 1")

    async def record_revocation(self, revoked: Approval) -> None:
        async with self._pool.acquire() as conn:
            # The first revocation stands: a second never rewrites when, by whom or why.
            status = await conn.execute(
                "UPDATE memory_approvals SET approval_body = $2, revoked_at = $3 "
                "WHERE approval_id = $1 AND revoked_at IS NULL",
                revoked.approval_id,
                revoked.to_dict(),
                revoked.revoked_at,
            )
            if status.endswith(" 0") and not await conn.fetchval(
                "SELECT 1 FROM memory_approvals WHERE approval_id = $1", revoked.approval_id
            ):
                raise KeyError(revoked.approval_id)

    async def list_approvals(self, project_id: str) -> list[Approval]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT approval_body FROM memory_approvals WHERE project_id = $1 "
                "ORDER BY approved_at, approval_id",
                project_id,
            )
        return [Approval.from_dict(r["approval_body"]) for r in rows]

    async def record_snapshot(self, snapshot: Snapshot) -> Snapshot:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO memory_snapshots (unit_kind, unit_id, snapshot_id, pinned_at, "
                "snapshot_body) VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (unit_kind, unit_id) DO NOTHING",
                snapshot.unit_kind.value,
                snapshot.unit_id,
                snapshot.snapshot_id,
                snapshot.pinned_at,
                snapshot.to_dict(),
            )
        held = await self.get_snapshot(snapshot.unit_kind, snapshot.unit_id)
        assert held is not None  # just written, or written first by another
        return held

    async def get_snapshot(self, unit_kind: UnitKind, unit_id: str) -> Snapshot | None:
        async with self._pool.acquire() as conn:
            body = await conn.fetchval(
                "SELECT snapshot_body FROM memory_snapshots WHERE unit_kind = $1 AND unit_id = $2",
                unit_kind.value,
                unit_id,
            )
        if body is None:
            return None
        try:
            return Snapshot.from_dict(body)
        except (KeyError, TypeError, ValueError) as e:
            raise RecordIncompatible(f"{unit_kind.value} {unit_id}'s snapshot: {e!r}") from e

    async def list_snapshots_holding(self, approval_id: str) -> list[Snapshot]:
        # A text match narrows the rows; the domain's read of each entry decides.
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT snapshot_body FROM memory_snapshots "
                "WHERE strpos(snapshot_body::text, $1) > 0 ORDER BY pinned_at, unit_id",
                approval_id,
            )
        return units_holding(approval_id, [Snapshot.from_dict(r["snapshot_body"]) for r in rows])

    async def record_exposure(self, exposure: Exposure) -> bool:
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                "INSERT INTO memory_exposures (exposure_id, project_id, cycle_id, run_id, task_id, "
                "task_type, seam, disposition, snapshot_id, exposure_body, recorded_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) "
                "ON CONFLICT (exposure_id) DO NOTHING",
                exposure.exposure_id,
                exposure.query.project_id,
                exposure.cycle_id,
                exposure.run_id,
                exposure.task_id,
                exposure.query.task_type,
                exposure.seam,
                exposure.disposition,
                exposure.recalled.get("snapshot"),
                exposure.to_dict(),
                exposure.recorded_at,
            )
        return status.endswith(" 1")

    async def list_exposures(self, run_id: str) -> list[Exposure]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT exposure_body FROM memory_exposures WHERE run_id = $1 "
                "ORDER BY task_id, COALESCE((exposure_body->>'attempt')::int, 1)",
                run_id,
            )
        return [Exposure.from_dict(r["exposure_body"]) for r in rows]

    async def get_exposure(self, exposure_id: str) -> Exposure | None:
        async with self._pool.acquire() as conn:
            body = await conn.fetchval(
                "SELECT exposure_body FROM memory_exposures WHERE exposure_id = $1", exposure_id
            )
        return Exposure.from_dict(body) if body is not None else None

    async def list_project_exposures(self, project_id: str) -> list[Exposure]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT exposure_body FROM memory_exposures WHERE project_id = $1 "
                "ORDER BY recorded_at, exposure_id",
                project_id,
            )
        return [Exposure.from_dict(r["exposure_body"]) for r in rows]

    async def record_assessment(self, assessment: Assessment) -> bool:
        async with self._pool.acquire() as conn:
            status = await conn.execute(
                "INSERT INTO memory_assessments (assessment_id, project_id, exposure_id, "
                "pattern_id, state, assessed_at, assessment_body) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (assessment_id) DO NOTHING",
                assessment.assessment_id,
                assessment.project_id,
                assessment.exposure_id,
                assessment.pattern_id,
                assessment.state.value,
                assessment.assessed_at,
                assessment.to_dict(),
            )
        return status.endswith(" 1")

    async def list_assessments(self, project_id: str) -> list[Assessment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT assessment_body FROM memory_assessments WHERE project_id = $1 "
                "ORDER BY assessed_at, assessment_id",
                project_id,
            )
        return [Assessment.from_dict(r["assessment_body"]) for r in rows]


def create_cross_cycle_store(provider: str, **kwargs: Any) -> CrossCycleMemoryStorePort:
    """The store for ``provider``, the cycle registry's (``memory`` or ``postgres``). Required:
    an unknown or missing name is refused, never defaulted (#1568)."""
    if provider == "memory":
        return InMemoryCrossCycleMemoryStore()
    if provider == "postgres":
        return PostgresCrossCycleMemoryStore(pool=kwargs["pool"])
    raise ValueError(f"unknown cross-cycle memory store provider {provider!r}")
