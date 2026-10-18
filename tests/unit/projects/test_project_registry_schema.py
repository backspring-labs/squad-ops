"""Migration 1800's CHECK lists are the Python enums' values (SIP-0112, #2408).

Bug caught: a lifecycle status or provenance added on one side only. A status the table refuses
fails its first write in production; one the enum lacks makes every read of that row raise.
"""

import re
from pathlib import Path

import pytest

from squadops.projects.models import ProjectLifecycleStatus, ProjectProvenance

MIGRATION = (
    Path(__file__).resolve().parents[3] / "infra" / "migrations" / "1800_project_records.sql"
)


def _check_values(column: str) -> set[str]:
    match = re.search(rf"CHECK \({column} IN \(([^)]*)\)\)", MIGRATION.read_text())
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
