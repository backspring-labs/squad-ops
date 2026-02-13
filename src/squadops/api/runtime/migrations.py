"""Startup migration runner for runtime-api.

Applies pending SQL migrations from a configured directory.
Idempotent: tracks applied files in ``_schema_migrations`` table.
Each migration runs in its own transaction: execute SQL + record
applied row atomically.  On failure the transaction rolls back and
the migration is not marked as applied.
"""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


async def apply_migrations(pool: asyncpg.Pool, migrations_dir: Path) -> int:
    """Apply pending migrations.  Returns count of newly applied files."""
    applied = 0
    async with pool.acquire() as conn:
        # Create tracking table (idempotent, outside per-file txn)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                filename    TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        if not migrations_dir.is_dir():
            logger.info("No migrations directory at %s — skipping", migrations_dir)
            return 0

        for sql_file in sorted(migrations_dir.glob("*.sql")):
            already = await conn.fetchval(
                "SELECT 1 FROM _schema_migrations WHERE filename = $1",
                sql_file.name,
            )
            if already:
                continue

            sql = sql_file.read_text()
            # Per-file transaction: SQL + tracking row atomically
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _schema_migrations (filename) VALUES ($1)",
                    sql_file.name,
                )
            logger.info("Applied migration: %s", sql_file.name)
            applied += 1

    return applied
