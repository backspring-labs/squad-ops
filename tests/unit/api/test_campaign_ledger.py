"""The proposal ledger and the supervisor's classification (SIP-0109 §9.4).

Entered at ``POST …/classifications`` and ``GET …/ledger`` over the memory registry, after the
increment gate's own rows (submission, ruling) and the completion boundary's decision were
written by the code that writes them live.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.continuation import ContinuationDecision, CycleEnding, PendingAction
from squadops.campaigns.gate import RETURNING_DECISIONS, ruling_transition, submission
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.campaigns.progress import decision_transition
from squadops.cycles.models import GateDecisionValue
from tests.unit.campaigns.builders import campaign, move

pytestmark = pytest.mark.auth

CID = "cmp_ledger000001"
V1 = ProposalBinding("prop_cap", 1, "hash-v1", "sha-accepted")
V2 = ProposalBinding("prop_cap", 2, "hash-v2", "sha-accepted")


def _rule(decision, binding, run_id, key):
    return ruling_transition(
        decision,
        binding,
        run_id=run_id,
        actor="crew-sup",
        actor_role="campaign-supervisor",
        reason=f"{decision} on v{binding.version}",
        idempotency_key=key,
        # SIP-0109 §24bi: a return names what went wrong.
        classification="scope_too_large" if decision in RETURNING_DECISIONS else None,
    )


@pytest.fixture
async def world():
    campaigns = MemoryCampaignRegistry()
    role = {"now": Role.CAMPAIGN_SUPERVISOR}
    app = FastAPI()

    class Inject(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.identity = Identity(
                user_id="crew-sup",
                display_name="s",
                roles=(role["now"],),
                scopes=tuple(sorted(scopes_for_roles((role["now"],)))),
                identity_type=IdentityType.SERVICE,
            )
            return await call_next(request)

    app.add_middleware(Inject)
    app.include_router(campaigns_router)
    register_domain_error_handlers(app)
    app.state.campaign_registry = campaigns
    app.state.authz_port = KeycloakAuthzAdapter()

    await campaigns.create_campaign(
        campaign(CID), actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    for to, key, extra in (
        (CampaignState.CALIBRATING, "cal", {}),
        (
            CampaignState.CALIBRATING,
            "promote",
            {"operation": ControlOperation.PROMOTE, "accepted": AcceptedTree("sha-accepted", "c0")},
        ),
        (CampaignState.AT_PROPOSAL, "propose", {}),
    ):
        await campaigns.transition(CID, move(to, key, **extra))
    s = CampaignState
    await campaigns.transition(CID, submission(s.AT_PROPOSAL, SubmittedProposal(V1, "cyc_1", "r1")))
    await campaigns.transition(CID, _rule(GateDecisionValue.RETURNED_FOR_REVISION, V1, "r1", "k1"))
    await campaigns.transition(CID, submission(s.AT_PROPOSAL, SubmittedProposal(V2, "cyc_1", "r2")))
    await campaigns.transition(CID, _rule(GateDecisionValue.APPROVED, V2, "r2", "k2"))
    stored = await campaigns.get_campaign(CID)
    await campaigns.transition(
        CID,
        decision_transition(
            stored,
            ContinuationDecision("cyc_1", 14, action=PendingAction.ESCALATE),
            ending=CycleEnding.ASSESSED,
            verdict=None,
            launch=None,
        ),
    )
    return TestClient(app), campaigns, role


def _classify(client, version, value="scope_too_large", key="c1"):
    return client.post(
        f"/api/v1/campaigns/{CID}/classifications",
        json={
            "proposal_id": "prop_cap",
            "version": version,
            "classification": value,
            "reason": "the delta reaches three views",
            "idempotency_key": key,
        },
    )


async def test_the_ledger_holds_each_version_its_ruling_its_outcome_and_its_classification(world):
    """§9.4. Bugs caught: a revised proposal's earlier version lost from the record, the
    cycle's outcome attached to a version the build never ran, or the classification landing
    on no version."""
    client, _campaigns, _role = world

    assert _classify(client, 1).status_code == 200
    v1, v2 = client.get(f"/api/v1/campaigns/{CID}/ledger").json()

    assert (v1["version"], v1["content_hash"], v1["run_id"]) == (1, "hash-v1", "r1")
    assert v1["ruling"]["decision"] == "returned_for_revision"
    assert v1["outcome"] is None
    assert v1["classification"]["classification"] == "scope_too_large"
    assert (v2["ruling"]["decision"], v2["ruling"]["actor"]) == ("approved", "crew-sup")
    assert v2["outcome"] == {"row": 14, "ending": "assessed", "action": "escalate"}
    assert v2["classification"] is None


@pytest.mark.parametrize(
    ("version", "value", "role", "status"),
    [
        (7, "scope_too_large", Role.CAMPAIGN_SUPERVISOR, 422),  # never submitted
        (1, "bad_luck", Role.CAMPAIGN_SUPERVISOR, 422),  # not a classification
        (1, "scope_too_large", Role.CAMPAIGN_TRIAGE, 403),  # read-only seat
    ],
)
async def test_a_classification_the_ledger_could_not_hold_is_refused(
    world, version, value, role, status
):
    client, campaigns, seat = world
    seat["now"] = role
    rows = len(await campaigns.control_log(CID))

    assert _classify(client, version, value).status_code == status
    assert len(await campaigns.control_log(CID)) == rows


async def test_a_proposal_is_classified_after_the_campaign_has_ended(world):
    """§9.4 is read the morning after. Bug caught: classification refused on a completed
    campaign, so the night's last proposal can never be classified."""
    client, campaigns, _role = world
    await campaigns.transition(
        CID,
        move(
            CampaignState.COMPLETED,
            "abort",
            operation=ControlOperation.ABORT,
            outcome=CampaignOutcome.ABORTED,
        ),
    )

    assert _classify(client, 2, "sound_proposal_built_badly", key="c2").status_code == 200
    assert (
        client.get(f"/api/v1/campaigns/{CID}/ledger").json()[1]["classification"]["classification"]
        == "sound_proposal_built_badly"
    )
