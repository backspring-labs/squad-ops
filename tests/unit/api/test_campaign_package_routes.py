"""The evidence package at the API (SIP-0109 §14; #1710): an abort materializes it, and the
digest is read back.

Entered at ``POST /api/v1/campaigns/{id}/abort`` and ``GET …/package`` with the real progress
service over the memory registry and a storing vault.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.models import CampaignState
from squadops.campaigns.progress import CampaignProgress
from tests.unit.campaigns.builders import campaign, move

pytestmark = pytest.mark.auth

CID = "cmp_pkgroute0001"


class _Vault:
    def __init__(self) -> None:
        self.stored: dict[str, tuple] = {}

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, *, artifact_type=None, **_):
        return [r for r, _ in self.stored.values() if r.artifact_type == artifact_type]


@pytest.fixture
async def world():
    campaigns, vault = MemoryCampaignRegistry(), _Vault()
    app = FastAPI()
    role = {"now": Role.ADMIN}

    class Inject(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.identity = Identity(
                user_id="u",
                display_name="u",
                roles=(role["now"],),
                scopes=tuple(sorted(scopes_for_roles((role["now"],)))),
                identity_type=IdentityType.HUMAN,
            )
            return await call_next(request)

    app.add_middleware(Inject)
    app.include_router(campaigns_router)
    register_domain_error_handlers(app)
    app.state.campaign_registry = campaigns
    app.state.cycle_registry = MemoryCycleRegistry()
    app.state.artifact_vault = vault
    app.state.campaign_progress = CampaignProgress(
        campaigns=campaigns,
        cycles=MemoryCycleRegistry(),
        vault=vault,
        assess=AsyncMock(),
        launch=AsyncMock(),
        evaluate_outcome=None,
        outcome_section=None,
        intervention_section=None,
        campaign_branch=None,
    )
    app.state.authz_port = KeycloakAuthzAdapter()
    await campaigns.create_campaign(
        campaign(CID), actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    await campaigns.transition(CID, move(CampaignState.CALIBRATING, "cal"))
    return TestClient(app), vault, role


async def test_an_abort_leaves_the_package_and_the_supervisor_reads_its_digest(world):
    """§14: a closed campaign leaves its package, whoever closed it. Bugs caught: an abort —
    the owner's commonest close — leaving nothing to triage, or the digest unreadable by the
    supervisor's read-only seat."""
    client, vault, role = world
    before = client.get(f"/api/v1/campaigns/{CID}/package")

    client.post(
        f"/api/v1/campaigns/{CID}/abort", json={"reason": "stop", "idempotency_key": "abort-1"}
    )
    role["now"] = Role.CAMPAIGN_SUPERVISOR
    after = client.get(f"/api/v1/campaigns/{CID}/package")

    assert before.status_code == 404
    assert after.status_code == 200
    assert f"# Campaign {CID}: completed (aborted)" in after.json()["digest"]
    assert len(vault.stored) == 2


@pytest.mark.parametrize(
    ("seat", "status", "stored"),
    [(Role.CAMPAIGN_SUPERVISOR, 200, 2), (Role.CAMPAIGN_TRIAGE, 403, 0), (Role.OPERATOR, 403, 0)],
)
async def test_the_managing_seats_materialize_a_package_and_no_other(world, seat, status, stored):
    """#1940: the supervisor manages a campaign, its package included. Bugs caught: the
    supervisor still refused, or a read-only seat writing the package."""
    client, vault, role = world
    role["now"] = seat

    assert client.post(f"/api/v1/campaigns/{CID}/package").status_code == status
    assert len(vault.stored) == stored


async def _open_escalation(campaigns, *, ended: str | None = None) -> str:
    """A plan-review escalation on the campaign, ended as ``ended`` (``None`` leaves it pending)."""
    from datetime import UTC, datetime

    from squadops.campaigns.escalation import EscalationIdentity, opening_transition
    from squadops.campaigns.models import CampaignTransition, ControlOperation, CycleKind
    from squadops.campaigns.plan_review_tier import plan_review_tier

    identity = EscalationIdentity(
        CID, "cyc_x", "run_x", "progress_plan_review", None, None, None, "p"
    )
    verdict = plan_review_tier(
        kind=CycleKind.CALIBRATION,
        open_questions=("which order does the runs list use?",),
        footprint=("backend/main.py",),
        allowed_scope=("backend/**",),
        stack="fullstack_fastapi_react",
        refused_framing_runs=(),
        answered_on_record={},
    )
    await campaigns.transition(
        CID,
        opening_transition(
            identity,
            verdict,
            (("list-ordering", "which order does the runs list use?"),),
            datetime(2026, 10, 8, 15, 0, tzinfo=UTC),
        ),
    )
    if ended is not None:
        await campaigns.transition(
            CID,
            CampaignTransition(
                operation=ControlOperation.ESCALATION_CLOSED,
                actor="squadops",
                actor_role="sweep",
                reason="test",
                idempotency_key=f"escalation_closed:{identity.escalation_id}",
                next_state=None,
                target="run_x",
                binding={"escalation_id": identity.escalation_id, "state": ended},
            ),
        )
    return identity.escalation_id


def _answer(client, escalation_id: str):
    return client.post(
        f"/api/v1/campaigns/{CID}/escalations/{escalation_id}/answer",
        json={"answers": {"list-ordering": "insertion order"}, "reason": "late"},
    )


async def test_a_late_answer_on_a_closed_campaign_reaches_its_stored_digest(world):
    """#2305, entered at the answer route on a closed campaign, and read where `campaigns digest`
    reads: the latest STORED package. Bugs caught: the digest still asking for an answer that was
    given, because the close materialized it before the answer; a replayed answer storing another
    package. The digest built from the log never had this defect, which is why its test missed it."""
    client, vault, _role = world
    escalation_id = await _open_escalation(client.app.state.campaign_registry)
    client.post(
        f"/api/v1/campaigns/{CID}/abort", json={"reason": "stop", "idempotency_key": "abort-1"}
    )
    closed = client.get(f"/api/v1/campaigns/{CID}/package").json()["digest"]

    first = _answer(client, escalation_id)
    after = client.get(f"/api/v1/campaigns/{CID}/package").json()["digest"]
    stored = len(vault.stored)
    replay = _answer(client, escalation_id)

    assert f"Escalation `{escalation_id}` cancelled with nobody answering" in closed
    assert first.status_code == 200
    assert "with nobody answering" not in after
    assert "Answered late by human:u: list-ordering: insertion order" in after
    assert replay.json()["replayed"] is True
    assert len(vault.stored) == stored == 4


async def test_a_late_answer_on_an_open_campaign_stores_no_package(world):
    """The edge: an escalation expires while its campaign goes on, and the answer comes before the
    close. Bug caught: a package materialized mid-campaign, as if the answer had closed it. The
    close still materializes it, with the answer in."""
    client, vault, _role = world
    escalation_id = await _open_escalation(client.app.state.campaign_registry, ended="expired")

    resp = _answer(client, escalation_id)

    assert resp.status_code == 200
    assert vault.stored == {}
