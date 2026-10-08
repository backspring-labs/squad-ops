"""Cross-Cycle Memory's store, in Postgres beside the cycle registry, and in memory for tests
(SIP-0110 §0.8, D13). Selected as the cycle registry is, by the registry's required provider."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from squadops.memory.observations import Observation, ObservationSource
from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort


def _ordered(observations: list[Observation]) -> list[Observation]:
    return sorted(observations, key=lambda o: (o.observed_at, o.source_id))


class InMemoryCrossCycleMemoryStore(CrossCycleMemoryStorePort):
    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}

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


def create_cross_cycle_store(provider: str, **kwargs: Any) -> CrossCycleMemoryStorePort:
    """The store for ``provider``, the cycle registry's (``memory`` or ``postgres``). Required:
    an unknown or missing name is refused, never defaulted (#1568)."""
    if provider == "memory":
        return InMemoryCrossCycleMemoryStore()
    if provider == "postgres":
        return PostgresCrossCycleMemoryStore(pool=kwargs["pool"])
    raise ValueError(f"unknown cross-cycle memory store provider {provider!r}")
