"""A campaign pins its scenario suite at creation (SIP-0113 §4.7, phase 1; SIP-0109 §24bt; #2413).

Entered at ``POST /api/v1/campaigns``, contract 2's wiring: the pin is read back from Outcome
Evaluation's own record, and refused suites create nothing.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.models import CampaignState
from squadops.scenarios.models import CampaignSuitePin, parse_suite
from squadops.scenarios.suites import approve_suite, draft_suite
from tests.unit.api.test_campaign_routes import _create, _World
from tests.unit.campaigns.builders import move
from tests.unit.scenarios.suite_fixtures import SUITE, suite_doc

pytestmark = pytest.mark.auth

T0 = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)


def _world(*, approve: bool = True):
    world = _World()
    store = MemoryScenarioStore()
    world.client.app.state.scenario_store = store
    suite = parse_suite(SUITE)
    asyncio.run(draft_suite(store, suite, actor="supervisor", at=T0))
    if approve:
        asyncio.run(approve_suite(store, suite.digest, actor="owner", at=T0))
    return world, store, suite.digest


def test_a_campaign_created_with_an_approved_suite_is_pinned_to_it_and_a_replay_keeps_it():
    """§4.7. Bug caught: the suite named at creation never recorded, so the campaign's
    increments are evaluated by nothing; or a retried creation pinning a second time."""
    world, store, digest = _world()

    first = _create(world, scenario_suite=digest)
    replay = _create(world, scenario_suite=digest)

    pin = asyncio.run(store.get_pin("cmp_api000000001"))
    assert (first.status_code, replay.status_code, replay.json()["replayed"]) == (201, 201, True)
    assert (pin.suite_digest, pin.pinned_by) == (digest, "owner")


def test_a_retried_creation_naming_another_suite_is_refused_and_keeps_the_first():
    """Bug caught: a campaign's pinned suite moved by a retry that named a different one."""
    world, store, digest = _world()
    other = parse_suite(suite_doc(scenarios=SUITE["scenarios"][:1]))
    asyncio.run(draft_suite(store, other, actor="supervisor", at=T0))
    asyncio.run(approve_suite(store, other.digest, actor="owner", at=T0))
    _create(world, scenario_suite=digest)

    resp = _create(world, scenario_suite=other.digest)

    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
        409,
        "SUITE_ALREADY_PINNED",
    )
    assert asyncio.run(store.get_pin("cmp_api000000001")).suite_digest == digest


@pytest.mark.parametrize(
    ("named", "code"), [("draft", "SUITE_NOT_APPROVED"), ("unknown", "SUITE_NOT_FOUND")]
)
def test_a_suite_that_cannot_be_pinned_creates_no_campaign(named, code):
    """D2: approved before use. Bug caught: a campaign created on a draft or a digest nothing
    holds, whose increments then report against a suite nobody approved; or the store's typed
    code flattened to a generic validation error the caller can't act on (#2448's review)."""
    world, store, digest = _world(approve=False)

    resp = _create(world, scenario_suite=digest if named == "draft" else "f" * 64)

    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (422, code)
    assert "scenario_suite" in resp.json()["detail"]["error"]["message"]
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == 404
    assert asyncio.run(store.get_pin("cmp_api000000001")) is None


def test_a_campaign_created_without_a_suite_pins_nothing():
    """Optional (§4.7). Bug caught: every creation made to name a suite, or a pin invented."""
    world, store, _ = _world()

    assert _create(world).status_code == 201
    assert asyncio.run(store.get_pin("cmp_api000000001")) is None


def test_a_misspelled_suite_field_is_refused_not_ignored():
    """Contract 2: an unknown field is refused. Bug caught: ``scenario_suit`` dropped silently, so
    the campaign is created with no suite pinned and its increments are evaluated by nothing."""
    world, store, digest = _world()

    resp = _create(world, scenario_suit=digest)

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "extra_forbidden"
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == 404


@pytest.mark.parametrize(
    ("moved", "outcome"), [(False, (201, "pinned")), (True, (409, "SUITE_PIN_PAST_DRAFT"))]
)
def test_a_retried_creation_adds_a_suite_only_while_the_campaign_is_a_draft(moved, outcome):
    """The creation's replay hash doesn't carry the suite (#2448's review). Bug caught: a retry
    under the same key attaching a suite to a campaign created without one, after it has started;
    or the recovery refused, where a first creation's pin failed while it was still a draft."""
    world, store, digest = _world()
    assert _create(world).status_code == 201
    if moved:
        asyncio.run(
            world.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
        )

    resp = _create(world, scenario_suite=digest)

    pin = asyncio.run(store.get_pin("cmp_api000000001"))
    got = "pinned" if resp.status_code == 201 else resp.json()["detail"]["error"]["code"]
    assert (resp.status_code, got) == outcome
    assert (pin is not None) is (not moved)


def test_a_refused_pin_leaves_the_created_campaign_projected():
    """Bug caught: the pin refused after the creation committed, with the projection after it,
    so the campaign exists and is never projected; and a replay projects nothing (#2448's
    review)."""
    world, store, digest = _world()
    # A pin the store already holds for the id, so the first, committed creation's pin refuses.
    asyncio.run(store.save_pin(CampaignSuitePin("cmp_api000000001", "e" * 64, "owner", T0)))

    resp = _create(world, scenario_suite=digest)

    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
        409,
        "SUITE_ALREADY_PINNED",
    )
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == 200
    assert [e.action for e in world.audit.events] == ["campaign.create"]
