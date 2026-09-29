"""Deploy records in Postgres (#1720), over the runtime's one pool (#577)."""

from __future__ import annotations

import asyncpg

from squadops.cycles.deploy_record import DeployRecord, ModelWeights, ServiceImage
from squadops.ports.cycles.deploy_registry import DeployRegistryPort

_COLUMNS = "deploy_id, recorded_at, recorded_by, source_revision, services, models"


class PostgresDeployRegistry(DeployRegistryPort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def record(self, record: DeployRecord) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO deploy_records ({_COLUMNS}) VALUES ($1,$2,$3,$4,$5,$6)",
                record.deploy_id,
                record.recorded_at,
                record.recorded_by,
                record.source_revision,
                [
                    {"service": s.service, "image_id": s.image_id, "revision": s.revision}
                    for s in record.services
                ],
                [{"model": m.model, "digest": m.digest} for m in record.models],
            )

    async def latest(self) -> DeployRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM deploy_records ORDER BY recorded_at DESC LIMIT 1"
            )
        return _row_to_record(row) if row else None

    async def get(self, deploy_id: str) -> DeployRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM deploy_records WHERE deploy_id = $1", deploy_id
            )
        return _row_to_record(row) if row else None


def _row_to_record(row: asyncpg.Record) -> DeployRecord:
    return DeployRecord(
        deploy_id=row["deploy_id"],
        recorded_at=row["recorded_at"],
        recorded_by=row["recorded_by"],
        source_revision=row["source_revision"],
        services=tuple(ServiceImage(**s) for s in row["services"]),
        models=tuple(ModelWeights(**m) for m in row["models"]),
    )
