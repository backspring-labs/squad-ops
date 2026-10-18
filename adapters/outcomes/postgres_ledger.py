"""The intervention ledger's store in Postgres (SIP-0113 §4.3; #2417), over the runtime's pool.
Migration 1920 creates its tables."""

from __future__ import annotations

import asyncpg

from squadops.outcomes.ledger import Classification, DeclaredIntervention
from squadops.ports.outcomes import InterventionLedgerPort

_CLASSIFIED = (
    "entry_id, campaign_id, reason, severity, squad_could_resolve, note, classified_by, "
    "classified_at"
)
_DECLARED = (
    "declared_id, campaign_id, reason, severity, description, occurred_at, declared_by, "
    "declared_at, squad_could_resolve"
)


class PostgresInterventionLedger(InterventionLedgerPort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_classification(self, c: Classification) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO intervention_classifications ({_CLASSIFIED}) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (entry_id) DO UPDATE SET "
                "reason = EXCLUDED.reason, severity = EXCLUDED.severity, "
                "squad_could_resolve = EXCLUDED.squad_could_resolve, note = EXCLUDED.note, "
                "classified_by = EXCLUDED.classified_by, classified_at = EXCLUDED.classified_at",
                c.entry_id,
                c.campaign_id,
                c.reason,
                c.severity,
                c.squad_could_resolve,
                c.note,
                c.classified_by,
                c.classified_at,
            )

    async def classifications(self, campaign_id: str) -> list[Classification]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_CLASSIFIED} FROM intervention_classifications WHERE campaign_id = $1",
                campaign_id,
            )
        return [Classification(**dict(r)) for r in rows]

    async def save_declared(self, d: DeclaredIntervention) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO declared_interventions ({_DECLARED}) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                d.declared_id,
                d.campaign_id,
                d.reason,
                d.severity,
                d.description,
                d.occurred_at,
                d.declared_by,
                d.declared_at,
                d.squad_could_resolve,
            )

    async def declared(self, campaign_id: str) -> list[DeclaredIntervention]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_DECLARED} FROM declared_interventions WHERE campaign_id = $1 "
                "ORDER BY occurred_at",
                campaign_id,
            )
        return [DeclaredIntervention(**dict(r)) for r in rows]
