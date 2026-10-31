"""``/api/v1/intervention-ledgers/{campaign_id}`` (SIP-0113 §4.3; #2417), entered with a real
campaign's control log: created, paused by the owner, resumed."""

from __future__ import annotations

import pytest

from adapters.outcomes.memory_ledger import MemoryInterventionLedger
from squadops.api.routes.outcomes import router
from squadops.auth.models import Role
from squadops.campaigns.models import CampaignState
from tests.unit.api.test_campaign_routes import _control, _create, _identity, _World
from tests.unit.campaigns.builders import move

pytestmark = pytest.mark.auth

LEDGER = "/api/v1/intervention-ledgers/cmp_api000000001"


@pytest.fixture
async def world() -> _World:
    w = _World()
    w.client.app.include_router(router)
    w.client.app.state.intervention_ledger = MemoryInterventionLedger()
    assert _create(w).status_code == 201
    await w.campaigns.transition("cmp_api000000001", move(CampaignState.CALIBRATING, "k-run"))
    assert _control(w, "pause", "p-1").status_code == 200
    assert _control(w, "resume", "r-1").status_code == 200
    return w


def test_the_owners_pause_and_resume_are_unclassified_until_the_supervisor_classifies_them(world):
    """Wiring, §7 prediction 5. Bug caught: the ledger reading a control log other than the
    campaign's, the creation counted as an intervention, or a classification that doesn't reach
    the ledger's read."""
    before = world.client.get(LEDGER).json()
    pause, resume = (e["entry_id"] for e in before["entries"])
    world.as_(_identity(Role.CAMPAIGN_SUPERVISOR, user="supervisor"))
    classified = [
        world.client.post(
            f"{LEDGER}/classifications",
            json={"entry_id": entry, "reason": "verification", "severity": "unblock",
                  "squad_could_resolve": False},
        )
        for entry in (pause, resume)
    ]  # fmt: skip

    after = world.client.get(LEDGER).json()

    assert [e["operation"] for e in before["entries"]] == ["pause", "resume"]
    assert (before["unclassified"], before["matches_the_control_log"]) == ([pause, resume], False)
    assert [c.status_code for c in classified] == [201, 201]
    assert (after["unclassified"], after["matches_the_control_log"]) == ([], True)
    assert after["entries"][0]["classification"]["classified_by"] == "supervisor"


@pytest.mark.parametrize(
    ("seat", "body", "status"),
    [
        (Role.CAMPAIGN_SUPERVISOR, {"reason": "tool", "severity": "advisory"}, 422),
        (Role.CAMPAIGN_TRIAGE, {"reason": "tool", "severity": "advisory"}, 403),
        (Role.AGENT, {"reason": "tool", "severity": "advisory"}, 403),
    ],
    ids=["the-creation-row", "triage-reads-only", "an-agent"],
)
def test_only_the_supervisor_classifies_and_only_an_intervention(world, seat, body, status):
    """Bug caught: the creation row classified as an intervention, or a seat that only reads
    (or a squad agent) writing the ledger."""
    create_row = next(
        e["entry_id"]
        for e in world.client.get("/api/v1/campaigns/cmp_api000000001/control-log").json()
        if e["operation"] == "create"
    )
    world.as_(_identity(seat, user=seat))

    resp = world.client.post(f"{LEDGER}/classifications", json={"entry_id": create_row, **body})

    assert resp.status_code == status


def test_an_unknown_campaign_has_no_ledger(world):
    resp = world.client.get("/api/v1/intervention-ledgers/cmp_nosuchcamp001")
    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (404, "CAMPAIGN_NOT_FOUND")
