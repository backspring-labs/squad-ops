"""Startup migration runner for runtime-api.

Applies pending SQL migrations from a configured directory.
Idempotent: tracks applied files in ``_schema_migrations`` table.
Each migration runs in its own transaction: execute SQL + record
applied row atomically.  On failure the transaction rolls back and
the migration is not marked as applied.

One applier at a time (#300): the connection takes a session-level advisory lock
before it touches the tracking table and releases it after the last file, so two
runtime-api instances starting together cannot race the per-file transactions —
the second waits, then finds every file already recorded.
"""

from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

#: The advisory-lock key every applier takes (#300). Any fixed bigint works as long as
#: every runtime-api instance uses the same one; this is ``b"sqop-mig"`` as a number,
#: so a row in ``pg_locks`` reads back as its purpose.
MIGRATIONS_ADVISORY_LOCK_KEY = int.from_bytes(b"sqop-mig", "big") & 0x7FFFFFFFFFFFFFFF


async def apply_migrations(pool: asyncpg.Pool, migrations_dir: Path) -> int:
    """Apply pending migrations.  Returns count of newly applied files."""
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", MIGRATIONS_ADVISORY_LOCK_KEY)
        try:
            return await _apply_under_lock(conn, migrations_dir)
        finally:
            # Released whatever happened above, so a failed migration never hands a
            # locked connection back to the pool.
            await conn.execute("SELECT pg_advisory_unlock($1)", MIGRATIONS_ADVISORY_LOCK_KEY)


async def _apply_under_lock(conn: asyncpg.Connection, migrations_dir: Path) -> int:
    """The apply loop, on a connection that holds the migrations lock."""
    applied = 0
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
