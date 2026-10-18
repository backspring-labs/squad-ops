"""The scenario store in Postgres (SIP-0113 §4.1; #2413), over the runtime's one pool (#577).

Migration 1900 creates its tables. A suite's content is stored as its document, and its digest
is recomputed on every read: JSONB orders keys its own way, so the digest is the content's
canonical hash, never the stored text's. A row whose content no longer hashes to its key is
refused rather than served.
"""

from __future__ import annotations

import asyncpg

from squadops.ports.scenarios import ScenarioStorePort
from squadops.scenarios.models import (
    CampaignSuitePin,
    SuiteRecord,
    SuiteState,
    parse_suite,
)

_SUITE_COLUMNS = "digest, content, state, drafted_by, drafted_at, approved_by, approved_at"


class PostgresScenarioStore(ScenarioStorePort):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_suite(self, record: SuiteRecord) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO scenario_suites ({_SUITE_COLUMNS}) VALUES ($1,$2,$3,$4,$5,$6,$7) "
                "ON CONFLICT (digest) DO UPDATE SET state = EXCLUDED.state, "
                "approved_by = EXCLUDED.approved_by, approved_at = EXCLUDED.approved_at",
                record.digest,
                record.suite.content(),
                record.state.value,
                record.drafted_by,
                record.drafted_at,
                record.approved_by,
                record.approved_at,
            )

    async def get_suite(self, digest: str) -> SuiteRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SUITE_COLUMNS} FROM scenario_suites WHERE digest = $1", digest
            )
        return _row_to_record(row) if row else None

    async def list_suites(self) -> list[SuiteRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_SUITE_COLUMNS} FROM scenario_suites ORDER BY drafted_at DESC"
            )
        return [_row_to_record(r) for r in rows]

    async def save_pin(self, pin: CampaignSuitePin) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO campaign_scenario_suites (campaign_id, suite_digest, pinned_by, "
                "pinned_at) VALUES ($1,$2,$3,$4)",
                pin.campaign_id,
                pin.suite_digest,
                pin.pinned_by,
                pin.pinned_at,
            )

    async def get_pin(self, campaign_id: str) -> CampaignSuitePin | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT campaign_id, suite_digest, pinned_by, pinned_at "
                "FROM campaign_scenario_suites WHERE campaign_id = $1",
                campaign_id,
            )
        return CampaignSuitePin(**dict(row)) if row else None


def _row_to_record(row: asyncpg.Record) -> SuiteRecord:
    suite = parse_suite(row["content"])
    if suite.digest != row["digest"]:
        raise ValueError(
            f"scenario suite {row['digest']} no longer hashes to its key ({suite.digest}): "
            "its stored content changed"
        )
    return SuiteRecord(
        suite=suite,
        state=SuiteState(row["state"]),
        drafted_by=row["drafted_by"],
        drafted_at=row["drafted_at"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )
