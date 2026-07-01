"""DDL↔model drift guard (#158): migration columns stay in sync with the models.

Bug this catches: a model field added without a migration (can't be persisted),
or a DDL column added/removed without the model knowing (silent schema drift).

The check is a curated registry of (table, model) pairs with per-table allowlists
for *intentional* divergences — DB-managed columns (e.g. is_active, updated_at)
and relation fields stored in a child table (e.g. Run.gate_decisions). A table's
column set is the union of its CREATE TABLE columns and any later
ALTER TABLE ... ADD COLUMN (e.g. cycle_runs.workload_type in 004).
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from squadops.cycles.models import Cycle, GateDecision, Run, SquadProfile

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "infra" / "migrations"

# First tokens that are table-level constraints, not column names.
_CONSTRAINT_KEYWORDS = {"PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE", "CHECK", "EXCLUDE"}

_CREATE_RE = re.compile(
    r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\)",
    re.DOTALL | re.IGNORECASE,
)
_ALTER_RE = re.compile(
    r"ALTER TABLE(?:\s+IF EXISTS)?\s+(\w+)\s+ADD COLUMN(?:\s+IF NOT EXISTS)?\s+(\w+)",
    re.IGNORECASE,
)


def _parse_table_columns(migrations_dir: Path) -> dict[str, set[str]]:
    """Return {table: {column, ...}} across all migrations (CREATE + ALTER ADD COLUMN)."""
    columns: dict[str, set[str]] = {}
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        text = sql_file.read_text()
        for table, body in _CREATE_RE.findall(text):
            table_cols = columns.setdefault(table, set())
            for raw in body.split("\n"):
                line = raw.strip().rstrip(",").strip()
                if not line:
                    continue
                first = line.split()[0].strip('"')
                if first.upper() in _CONSTRAINT_KEYWORDS:
                    continue
                table_cols.add(first)
        for table, col in _ALTER_RE.findall(text):
            columns.setdefault(table, set()).add(col)
    return columns


# (table, model, db_only_columns, model_only_fields)
_REGISTRY = [
    ("cycle_registry", Cycle, set(), set()),
    ("cycle_runs", Run, set(), {"gate_decisions"}),  # gate_decisions -> child table
    # run_id = parent FK; id = SERIAL surrogate PK (both DB-only, not model fields)
    ("cycle_gate_decisions", GateDecision, {"run_id", "id"}, set()),
    ("squad_profiles", SquadProfile, {"is_active", "updated_at"}, set()),  # DB-managed
]


@pytest.fixture(scope="module")
def table_columns() -> dict[str, set[str]]:
    return _parse_table_columns(MIGRATIONS_DIR)


def test_parser_finds_registered_tables(table_columns):
    """Sanity: the DDL parser actually extracted the tables (else drift checks are vacuous)."""
    for table, *_ in _REGISTRY:
        assert table_columns.get(table), f"parser found no columns for {table}"
    # spot-check a known column set to catch parser breakage
    assert {"cycle_id", "project_id", "squad_profile_id"} <= table_columns["cycle_registry"]
    assert "workload_type" in table_columns["cycle_runs"]  # added via ALTER in 004


@pytest.mark.parametrize("table,model,db_only,model_only", _REGISTRY, ids=[r[0] for r in _REGISTRY])
def test_no_ddl_model_drift(table_columns, table, model, db_only, model_only):
    columns = table_columns[table]
    fields = {f.name for f in dataclasses.fields(model)}

    # Every model field must have a backing column (except allowlisted relations).
    fields_without_column = fields - model_only - columns
    assert not fields_without_column, (
        f"{model.__name__} has field(s) with no {table} column "
        f"(add a migration, or allowlist as a relation): {sorted(fields_without_column)}"
    )

    # Every column must map to a model field (except allowlisted DB-only columns).
    columns_without_field = columns - db_only - fields
    assert not columns_without_field, (
        f"{table} has column(s) not on {model.__name__} "
        f"(update the model, or allowlist as DB-only): {sorted(columns_without_field)}"
    )


def test_allowlists_are_not_stale(table_columns):
    """Allowlisted db-only columns must actually exist (else the allowlist is dead)."""
    for table, model, db_only, model_only in _REGISTRY:
        columns = table_columns[table]
        fields = {f.name for f in dataclasses.fields(model)}
        assert db_only <= columns, (
            f"{table}: db_only allowlist names a non-column: {db_only - columns}"
        )
        assert model_only <= fields, (
            f"{table}: model_only allowlist names a non-field: {model_only - fields}"
        )
