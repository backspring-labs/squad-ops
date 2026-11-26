"""The worker registry's CHECK lists are the vocabularies in code (D3; SIP-0117 R5.4).

Bug caught: a value added to an enum and not to its column's CHECK. The memory store takes it,
every unit test passes, and the first deployed write of it is refused by Postgres.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadops.remote_execution import leasing
from squadops.remote_execution.workers import AttemptOutcome, FenceRefusal, OperationState

_MIGRATIONS = Path(__file__).resolve().parents[3] / "infra" / "migrations"
#: The registry's migrations, in the order they are applied. A later one that declares a
#: column's list again replaces it (2302 re-declares ``outcome``, #3236).
_SQL = [path.read_text() for path in sorted(_MIGRATIONS.glob("23??_remote_*.sql"))]


def _check_values(column: str) -> set[str]:
    declared = []
    for sql in _SQL:
        found = re.findall(rf"CHECK \({column} IN \(([^)]*)\)\)", sql)
        assert len(found) <= 1, f"{column}: {len(found)} CHECK lists in one migration"
        declared.extend(found)
    assert declared, f"{column}: 0 CHECK lists, and a migration declares each column's"
    return set(re.findall(r"'([^']*)'", declared[-1]))


@pytest.mark.parametrize(
    ("column", "vocabulary"),
    [
        ("runtime_status", set(leasing.RUNTIME_STATUSES)),
        ("state", {member.value for member in OperationState}),
        ("outcome", {member.value for member in AttemptOutcome}),
        ("refusal", {member.value for member in FenceRefusal}),
    ],
    ids=["runtime_status", "state", "outcome", "refusal"],
)
def test_each_check_list_is_its_vocabulary(column, vocabulary):
    assert _check_values(column) == vocabulary


def test_a_column_with_no_check_list_is_reported_and_never_read_as_empty():
    with pytest.raises(AssertionError, match="worker_id: 0 CHECK lists"):
        _check_values("worker_id")
