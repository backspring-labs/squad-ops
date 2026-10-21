"""Migration 1800's CHECK lists are the Python enums' values (SIP-0112, #2408).

Bug caught: a lifecycle status or provenance added on one side only. A status the table refuses
fails its first write in production; one the enum lacks makes every read of that row raise.
"""

import re
from pathlib import Path

import pytest

from squadops.projects.contribution import CONTRIBUTION_MODES_MADE, CONTRIBUTION_STATES
from squadops.projects.models import ProjectLifecycleStatus, ProjectProvenance

MIGRATIONS = Path(__file__).resolve().parents[3] / "infra" / "migrations"
MIGRATION = MIGRATIONS / "1800_project_records.sql"


def _check_values(column: str, migration: Path = MIGRATION) -> set[str]:
    match = re.search(rf"CHECK \({column} IN \(([^)]*)\)\)", migration.read_text())
    assert match, f"no CHECK list for {column}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


@pytest.mark.parametrize(
    ("column", "values"),
    [
        # ACTIVE is derived from active work and never stored (§B.6)
        ("lifecycle_status", {s.value for s in ProjectLifecycleStatus} - {"ACTIVE"}),
        ("provenance", {p.value for p in ProjectProvenance}),
    ],
)
def test_each_check_list_is_its_enum(column, values):
    assert _check_values(column) == values


def test_a_column_with_no_check_list_is_reported_not_passed():
    with pytest.raises(AssertionError, match="no CHECK list for nonexistent"):
        _check_values("nonexistent")


@pytest.mark.parametrize(
    ("column", "values"),
    [("mode", set(CONTRIBUTION_MODES_MADE)), ("state", set(CONTRIBUTION_STATES))],
)
def test_1805s_check_lists_are_what_a_contribution_writes(column, values):
    """Bug caught: a mode 2.4 contributes through, or a state it records, that the table
    refuses on its first write."""
    assert _check_values(column, MIGRATIONS / "1805_project_contributions.sql") == values
