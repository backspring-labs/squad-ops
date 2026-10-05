"""The owner's word: a held action resumed, an escalation ruled (SIP-0109 §10, §19 criterion 12a).

Entered at ``POST /api/v1/campaigns/{id}/resume`` with the real progress service over the memory
campaign registry; the vault holds the accepted cycle's interface manifest. The decisions that
pause or escalate the campaign are written by the completion boundary's own row builder.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.continuation import (
    CampaignLimit,
    ContinuationDecision,
    CycleEnding,
    Guard,
    PendingAction,
)
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    CycleKind,
)
from squadops.campaigns.progress import CampaignProgress, decision_transition
from squadops.cycles.models import ArtifactRef, Cycle, TaskFlowPolicy
from tests.unit.campaigns.builders import campaign, move, policy

CID = "cmp_owner0000001"
NOW = datetime(2026, 10, 2, 16, 0, tzinfo=UTC)
MANIFEST = "version: 1\nentities: []\nendpoints: []\n"
_MANIFEST_REF = ArtifactRef(
    artifact_id="art_manifest",
    project_id="group_run",
    artifact_type="document",
    filename="interface_manifest.yaml",
    content_hash="h",
    size_bytes=1,
    media_type="text/yaml",
    created_at=NOW,
    cycle_id="cyc_cal",
    run_id="run_f",
)


class _Vault:
    async def list_artifacts(self, **_):
        return [_MANIFEST_REF]

    async def retrieve(self, artifact_id):
        return _MANIFEST_REF, MANIFEST.encode()


class _World:
    def __init__(self) -> None:
        self.campaigns = MemoryCampaignRegistry()
        self.launch = AsyncMock()
        self.seat = Role.ADMIN
        app = FastAPI()
        world = self

        class Seat(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = Identity(
                    user_id=world.seat,
                    display_name=world.seat,
                    roles=(world.seat,),
                    scopes=tuple(sorted(scopes_for_roles((world.seat,)))),
                    identity_type=IdentityType.HUMAN,
                )
                return await call_next(request)

        app.add_middleware(Seat)
        app.include_router(campaigns_router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        # The decided increment: a real cycle, launched with no bound change request, so a
        # bound launch reads it and refuses (§10a) rather than reading a mock.
        cycles = AsyncMock()
        cycles.get_cycle.return_value = Cycle(
            cycle_id="cyc_inc",
            project_id="group_run",
            created_at=NOW,
            created_by="campaign-launcher",
            prd_ref=None,
            squad_profile_id="full-38",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            campaign_id=CID,
            kind="increment",
        )
        app.state.campaign_progress = CampaignProgress(
            campaigns=self.campaigns,
            cycles=cycles,
            vault=_Vault(),
            assess=AsyncMock(),
            launch=AsyncMock(),
        )
        app.state.campaign_launch = self.launch
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def resume(self, key: str, **extra):
        return self.client.post(
            f"/api/v1/campaigns/{CID}/resume",
            json={"reason": "the owner's word", "idempotency_key": key, **extra},
        )

    async def decided(self, decision: ContinuationDecision) -> None:
        stored = await self.campaigns.get_campaign(CID)
        await self.campaigns.transition(
            CID,
            decision_transition(
                stored, decision, ending=CycleEnding.ASSESSED, verdict=None, launch=None
            ),
        )


@pytest.fixture
async def world() -> _World:
    w = _World()
    await w.campaigns.create_campaign(
        campaign(CID, policy=policy(proposal_profile="campaign-increment")),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )
    for to, key in ((CampaignState.CALIBRATING, "cal"),):
        await w.campaigns.transition(CID, move(to, key))
    await w.campaigns.transition(
        CID,
        move(
            CampaignState.CALIBRATING,
            "promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-cal", "cyc_cal"),
        ),
    )
    return w


_HELD = ContinuationDecision(
    "cyc_cal",
    5,
    action=PendingAction.PROPOSE,
    guard=Guard.PAUSED,
    paused_by=CampaignLimit.BUDGET,
)
_ESCALATED = ContinuationDecision("cyc_inc", 14, action=PendingAction.ESCALATE)


async def test_a_held_action_is_executed_once_by_the_resume_as_recorded(world):
    """§19 criterion 12a. Bugs caught: the resume returning to the state the limit paused
    (the held launch lost), or a second resume launching it again."""
    await world.decided(_HELD)

    first = world.resume("resume-1")
    second = world.resume("resume-2")

    [launch] = await world.campaigns.launch_intents(CID)
    body = first.json()
    assert first.status_code == 200
    assert body["campaign"]["state"] == "at_proposal"
    assert body["entry"]["binding"] == {"action": "propose", "executes": "held"}
    assert launch.cycle_kind is CycleKind.INCREMENT
    assert (
        launch.cycle_request["body"]["execution_overrides"]["campaign_proposal"]["baseline_tree"]
        == "sha-cal"
    )
    assert second.status_code == 409
    world.launch.drain.assert_awaited_once()


@pytest.mark.parametrize(
    ("decision", "named", "held"),
    [(_HELD, None, "paused by a limit"), (_ESCALATED, "propose", "escalated")],
    ids=["limit-pause", "escalation"],
)
async def test_the_supervisor_cannot_give_the_owners_word(world, decision, named, held):
    """#1940, the owner's rulings of 2026-10-03: "keep escalations with me", "keep limit pauses
    with me". Bugs caught: the manage scope letting the supervisor execute a held launch or rule
    an escalation. The refusal writes nothing, and the owner's word then proceeds."""
    await world.decided(decision)
    rows = len(await world.campaigns.control_log(CID))
    world.seat = Role.CAMPAIGN_SUPERVISOR

    refused = world.resume("sup-1", **({"action": named} if named else {}))

    error = refused.json()["detail"]["error"]
    assert (refused.status_code, error["code"]) == (403, "OWNER_AUTHORITY_REQUIRED")
    assert held in error["message"]
    assert len(await world.campaigns.control_log(CID)) == rows
    assert await world.campaigns.launch_intents(CID) == []
    world.seat = Role.ADMIN
    assert world.resume("owner-1", **({"action": named} if named else {})).status_code == 200


async def test_a_resume_cannot_swap_the_held_action(world):
    await world.decided(_HELD)
    resp = world.resume("resume-1", action="abandon_and_propose")
    assert resp.status_code == 422
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.PAUSED


@pytest.mark.parametrize(
    ("action", "status", "state"),
    [
        (None, 422, CampaignState.ESCALATED),
        ("propose", 200, CampaignState.AT_PROPOSAL),
        ("abandon_and_propose", 200, CampaignState.AT_PROPOSAL),
        # §10a: a cycle with no bound change request cannot be repaired — refused, not pretended.
        ("repair", 422, CampaignState.ESCALATED),
        ("escalate", 422, CampaignState.ESCALATED),
        ("nonsense", 422, CampaignState.ESCALATED),
    ],
)
async def test_an_escalated_campaign_resumes_on_the_action_the_owner_names(
    world, action, status, state
):
    """§10: escalate waits for the owner's ruling, which names the next action and executes it
    at once. Bugs caught: an escalated campaign that only abort can move, or a resume that
    picks an action the owner never named."""
    await world.decided(_ESCALATED)

    resp = world.resume("rule-1", **({"action": action} if action else {}))

    assert resp.status_code == status, resp.json()
    assert (await world.campaigns.get_campaign(CID)).state is state


async def test_an_owner_abandonment_counts_against_the_no_progress_rule(world):
    """§9.5: an abandoned increment is unaccepted, whoever abandoned it. Bug caught: the
    owner's abandonment invisible to the counters, so a campaign abandoning by ruling never
    reaches its no-progress stop."""
    from squadops.campaigns.progress import derive_counters

    await world.decided(_ESCALATED)
    world.resume("rule-1", action="abandon_and_propose")

    counters = derive_counters(
        await world.campaigns.get_campaign(CID),
        await world.campaigns.control_log(CID),
        [],
        ending=CycleEnding.ASSESSED,
        now=NOW,
        objective_met=False,
    )
    assert counters.unaccepted_increments == 1
