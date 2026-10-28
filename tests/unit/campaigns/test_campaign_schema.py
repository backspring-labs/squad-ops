"""The campaign migrations' CHECK lists are the Python enums' values (infra/migrations README, D3).

Bug caught: a member added to an enum (a new control operation, a new cycle kind) without its
migration — every write of it would fail at the database, on the live deploy, with the unit
tests green on the memory adapter.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

import pytest

from squadops.campaigns.box import LeaseHolder
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntentState,
    RefusalReason,
)

_MIGRATIONS = Path(__file__).resolve().parents[3] / "infra" / "migrations"


def _check_values(sql: str, column: str) -> set[str]:
    """The quoted values of the first ``CHECK (<column> IN (...))`` in a migration. A later
    migration that replaces a list states it whole, as its table's own constraint."""
    match = re.search(rf"CHECK \({column} IN \((.*?)\)\)", sql, re.DOTALL)
    assert match, f"no CHECK list for {column}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


@pytest.mark.parametrize(
    ("migration", "column", "enum"),
    [
        ("1600_campaigns.sql", "state", CampaignState),
        ("1600_campaigns.sql", "outcome", CampaignOutcome),
        # Replaced whole by 1640 (the increment gate's submit, stale_binding, illegal_ruling).
        # Replaced whole again by 1650 (the owner's start), 1660 (the classification), 1680
        # (the ruling bound), 1690 (the box lease and a blocked launch, #1802) and 1695 (a
        # launch the cycle-create path refused, #1971), and later by 1790 and 1791 (SIP-0110's
        # re-binding and instruction) and 2000 (a campaign branch's rebase, §24cd point 2).
        ("2000_campaign_branch_rebased.sql", "operation", ControlOperation),
        # Replaced whole by 2000 (a superseded repair or retry, §24cd point 2).
        ("2000_campaign_branch_rebased.sql", "state", LaunchIntentState),
        ("1690_box_lease.sql", "refusal", RefusalReason),
        ("1690_box_lease.sql", "holder", LeaseHolder),
        ("1600_campaigns.sql", "cycle_kind", CycleKind),
        ("1610_cycle_campaign_columns.sql", "kind", CycleKind),
    ],
)
def test_a_check_list_holds_exactly_its_enums_values(migration, column, enum: type[StrEnum]):
    sql = (_MIGRATIONS / migration).read_text()
    assert _check_values(sql, column) == {m.value for m in enum}


def test_the_control_logs_outcome_and_the_intents_state_match_their_enums():
    sql = (_MIGRATIONS / "1600_campaigns.sql").read_text()
    lists = [set(re.findall(r"'([^']+)'", m)) for m in re.findall(r"IN \(([^()]*)\)", sql)]
    assert {m.value for m in ControlOutcome} in lists
    # 2000 adds ``superseded`` to the intents' states; 1600's list stays as it was written.
    assert {m.value for m in LaunchIntentState} - {LaunchIntentState.SUPERSEDED.value} in lists


def test_a_column_with_no_check_list_is_reported_not_passed():
    with pytest.raises(AssertionError, match="no CHECK list for nonexistent"):
        _check_values("CREATE TABLE t (state TEXT);", "nonexistent")
