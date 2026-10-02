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


async def test_only_the_owners_seat_materializes_a_package(world):
    client, vault, role = world
    role["now"] = Role.CAMPAIGN_SUPERVISOR

    assert client.post(f"/api/v1/campaigns/{CID}/package").status_code == 403
    assert vault.stored == {}
