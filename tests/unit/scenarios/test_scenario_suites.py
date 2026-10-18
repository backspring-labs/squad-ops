"""What the scenario store may hold, and when (SIP-0113 §4.1, §4.7; the 2.4 plan's D2; #2413)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.scenarios.models import SuiteState, parse_suite
from squadops.scenarios.suites import (
    SuiteRefused,
    approve_suite,
    draft_suite,
    pin_campaign_suite,
)
from tests.unit.scenarios.suite_fixtures import SUITE, suite_doc

T0 = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)


async def test_a_suite_is_drafted_once_approved_once_and_pinned_once():
    """D2. Bug caught: a redraft of the same content resetting its approval, an approval moving
    its approver on a retry, or a campaign re-pinned to a second suite after it was created."""
    store = MemoryScenarioStore()
    suite = parse_suite(SUITE)

    drafted = await draft_suite(store, suite, actor="supervisor", at=T0)
    approved = await approve_suite(store, suite.digest, actor="owner", at=T0)
    redrafted = await draft_suite(store, suite, actor="someone-else", at=T0)
    reapproved = await approve_suite(store, suite.digest, actor="someone-else", at=T0)
    pin = await pin_campaign_suite(store, "cmp_1", suite.digest, actor="owner", at=T0)
    replayed = await pin_campaign_suite(store, "cmp_1", suite.digest, actor="owner", at=T0)

    assert (drafted.state, drafted.drafted_by) == (SuiteState.DRAFT, "supervisor")
    assert redrafted == reapproved == approved
    assert (approved.state, approved.approved_by) == (SuiteState.APPROVED, "owner")
    assert replayed == pin
    other = parse_suite(suite_doc(scenarios=SUITE["scenarios"][:1]))
    await draft_suite(store, other, actor="supervisor", at=T0)
    await approve_suite(store, other.digest, actor="owner", at=T0)
    with pytest.raises(SuiteRefused) as refused:
        await pin_campaign_suite(store, "cmp_1", other.digest, actor="owner", at=T0)
    assert refused.value.code == "SUITE_ALREADY_PINNED"


@pytest.mark.parametrize(
    ("approve", "code"),
    [(False, "SUITE_NOT_APPROVED"), (None, "SUITE_NOT_FOUND")],
    ids=["a-draft", "never-drafted"],
)
async def test_a_suite_the_owner_has_not_approved_cannot_be_pinned(approve, code):
    """D2: the owner approves the suite before use. Bug caught: a campaign evaluated by a draft
    nobody approved, or by a digest nothing holds."""
    store = MemoryScenarioStore()
    suite = parse_suite(SUITE)
    if approve is not None:
        await draft_suite(store, suite, actor="supervisor", at=T0)

    with pytest.raises(SuiteRefused) as refused:
        await pin_campaign_suite(store, "cmp_1", suite.digest, actor="owner", at=T0)

    assert refused.value.code == code
    assert await store.get_pin("cmp_1") is None
