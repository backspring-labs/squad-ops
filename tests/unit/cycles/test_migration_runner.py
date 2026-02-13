"""Tests for the startup migration runner (SIP-Postgres-Cycle-Registry §1.4)."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from squadops.api.runtime.migrations import apply_migrations

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeAcquireCtx:
    """Async context manager that yields *conn*."""

    def __init__(self, conn: AsyncMock) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


def _make_pool(conn: AsyncMock) -> MagicMock:
    """Build a fake asyncpg.Pool whose acquire() yields *conn*."""
    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquireCtx(conn)
    return pool


class _FakeTxnCtx:
    """Async context manager mimicking ``conn.transaction()``."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False  # Don't suppress exceptions


def _make_conn(*, already_applied: set[str] | None = None) -> AsyncMock:
    """Build a fake asyncpg.Connection with transaction support."""
    conn = AsyncMock()

    applied = already_applied or set()

    async def _fetchval(sql, filename):
        return 1 if filename in applied else None

    conn.fetchval = AsyncMock(side_effect=_fetchval)

    # Transaction context manager
    conn.transaction = MagicMock(return_value=_FakeTxnCtx())

    return conn


def _write_sql(tmp_path: Path, name: str, content: str = "SELECT 1;") -> Path:
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(exist_ok=True)
    f = migrations_dir / name
    f.write_text(content)
    return migrations_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestApplyMigrations:
    async def test_creates_tracking_table(self, tmp_path):
        """Tracking table DDL is always executed."""
        conn = _make_conn()
        pool = _make_pool(conn)
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        await apply_migrations(pool, migrations_dir)

        # First execute call creates the tracking table
        first_call_sql = conn.execute.call_args_list[0][0][0]
        assert "_schema_migrations" in first_call_sql
        assert "CREATE TABLE IF NOT EXISTS" in first_call_sql

    async def test_skips_already_applied(self, tmp_path):
        """Files recorded in _schema_migrations are skipped."""
        migrations_dir = _write_sql(tmp_path, "001_first.sql", "CREATE TABLE foo();")

        conn = _make_conn(already_applied={"001_first.sql"})
        pool = _make_pool(conn)

        count = await apply_migrations(pool, migrations_dir)

        assert count == 0
        # Only the tracking table DDL should have been executed
        # (no migration SQL, no INSERT into tracking)
        conn.transaction.assert_not_called()

    async def test_applies_new_file(self, tmp_path):
        """New migration: SQL executed + tracking row inserted within a transaction."""
        migrations_dir = _write_sql(tmp_path, "001_init.sql", "CREATE TABLE t1();")

        conn = _make_conn()
        pool = _make_pool(conn)

        count = await apply_migrations(pool, migrations_dir)

        assert count == 1
        # Should have opened a transaction
        conn.transaction.assert_called_once()
        # Inside the transaction: execute SQL + insert tracking row
        execute_calls = conn.execute.call_args_list
        # Call 0: tracking table creation
        # Call 1: migration SQL
        # Call 2: INSERT into _schema_migrations
        assert len(execute_calls) == 3
        assert "CREATE TABLE t1();" in execute_calls[1][0][0]
        assert "_schema_migrations" in execute_calls[2][0][0]
        assert execute_calls[2][0][1] == "001_init.sql"

    async def test_returns_count(self, tmp_path):
        """Return value equals number of newly applied migrations."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "001_a.sql").write_text("SELECT 1;")
        (migrations_dir / "002_b.sql").write_text("SELECT 2;")

        conn = _make_conn()
        pool = _make_pool(conn)

        count = await apply_migrations(pool, migrations_dir)
        assert count == 2

    async def test_no_dir_returns_zero(self, tmp_path):
        """Non-existent dir returns 0, no error."""
        conn = _make_conn()
        pool = _make_pool(conn)

        count = await apply_migrations(pool, tmp_path / "nonexistent")
        assert count == 0

    async def test_idempotent(self, tmp_path):
        """Running twice: second run applies nothing."""
        migrations_dir = _write_sql(tmp_path, "001_init.sql")

        # First run: nothing applied yet
        conn1 = _make_conn()
        pool1 = _make_pool(conn1)
        first = await apply_migrations(pool1, migrations_dir)
        assert first == 1

        # Second run: file now "already applied"
        conn2 = _make_conn(already_applied={"001_init.sql"})
        pool2 = _make_pool(conn2)
        second = await apply_migrations(pool2, migrations_dir)
        assert second == 0

    async def test_rollback_on_failure(self, tmp_path):
        """SQL error → transaction rolls back, migration NOT recorded."""
        migrations_dir = _write_sql(tmp_path, "001_bad.sql", "INVALID SQL;")

        conn = _make_conn()
        pool = _make_pool(conn)

        # Make execute raise on the migration SQL (second call)
        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # The migration SQL execution
                raise Exception("syntax error")

        conn.execute = AsyncMock(side_effect=_execute_side_effect)

        with pytest.raises(Exception, match="syntax error"):
            await apply_migrations(pool, migrations_dir)

        # The INSERT into tracking should never have been called
        # (exception happened before it)
        assert call_count == 2  # tracking DDL + failed SQL

    async def test_applies_in_sorted_order(self, tmp_path):
        """Migrations are applied in filename-sorted order."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "003_c.sql").write_text("SELECT 3;")
        (migrations_dir / "001_a.sql").write_text("SELECT 1;")
        (migrations_dir / "002_b.sql").write_text("SELECT 2;")

        conn = _make_conn()
        pool = _make_pool(conn)

        await apply_migrations(pool, migrations_dir)

        # Extract the filenames from INSERT calls
        insert_calls = [
            c for c in conn.execute.call_args_list
            if len(c[0]) > 1 and isinstance(c[0][1], str) and c[0][1].endswith(".sql")
        ]
        filenames = [c[0][1] for c in insert_calls]
        assert filenames == ["001_a.sql", "002_b.sql", "003_c.sql"]


class TestMigrationSQLStyle:
    """Validate 001_cycle_registry.sql conforms to D12 (migration SQL style rules)."""

    @pytest.fixture
    def migration_sql(self) -> str:
        sql_path = Path(__file__).parents[3] / "infra" / "migrations" / "001_cycle_registry.sql"
        assert sql_path.exists(), f"Migration file not found: {sql_path}"
        return sql_path.read_text()

    def test_no_psql_metacommands(self, migration_sql):
        """No psql backslash commands (\\d, \\copy, \\set, etc.)."""
        # Match backslash followed by a word char at line start or after whitespace
        psql_pattern = re.compile(r"(?:^|\s)\\[a-zA-Z]", re.MULTILINE)
        matches = psql_pattern.findall(migration_sql)
        assert not matches, f"Found psql meta-commands: {matches}"

    def test_idempotent_ddl(self, migration_sql):
        """All CREATE statements use IF NOT EXISTS."""
        create_stmts = re.findall(r"CREATE\s+(?:TABLE|INDEX)\b[^;]+", migration_sql, re.IGNORECASE)
        for stmt in create_stmts:
            assert "IF NOT EXISTS" in stmt.upper(), (
                f"Non-idempotent DDL: {stmt[:80]}..."
            )
