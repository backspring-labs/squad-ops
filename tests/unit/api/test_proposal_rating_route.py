"""The supervisor's rating of a proposal nothing builds (SIP-0109 §11a; §24af; #1804).

``POST /api/v1/projects/{p}/cycles/{c}/proposal-rating``, entered at the HTTP surface with the
real authorization adapter. The proposal cycle stored shakeout 4's real change request
(``prop_567c4915dbc0``); what the route stores beside it is read back.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles import cycles_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.cycles.models import ArtifactRef, Cycle, TaskFlowPolicy

pytestmark = pytest.mark.auth

NOW = datetime(2026, 10, 3, 6, 0, tzinfo=UTC)
_CHANGE_REQUEST = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "campaigns"
    / "change-request-prop_567c4915dbc0.yaml"
).read_text()
_HASH = yaml.safe_load(_CHANGE_REQUEST)["content_hash"]
_RATING = {
    "content_hash": _HASH,
    "verdict": "would_approve",
    "reason": "one feature, three criteria that each fail on the baseline",
    "ratings": {
        "scope_fit": {"score": 3, "note": "capacity is the PRD's first expansion item"},
        "criteria_discriminability": {"score": 3, "note": "T1-T3 each fail on the baseline"},
        "footprint_size": {"score": 2, "note": "models, errors, routes, two views"},
    },
}


class _Vault:
    def __init__(self, stored: dict) -> None:
        self.stored = dict(stored)

    async def list_artifacts(self, *, cycle_id=None, run_id=None, **_):
        return [r for r, _ in self.stored.values() if cycle_id in (None, r.cycle_id)]

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref


def _change_request_ref(cycle_id: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="art_cr",
        project_id="group_run",
        artifact_type="change_request",
        filename="change_request.yaml",
        content_hash="h",
        size_bytes=len(_CHANGE_REQUEST),
        media_type="text/yaml",
        created_at=NOW,
        cycle_id=cycle_id,
        run_id="run_prop",
    )


class _World:
    def __init__(self, role: str = Role.CAMPAIGN_SUPERVISOR) -> None:
        self.cycles = MemoryCycleRegistry()
        self.vault = _Vault({})
        identity = Identity(
            user_id=f"user-{role}",
            display_name=role,
            roles=(role,),
            scopes=tuple(sorted(scopes_for_roles((role,)))),
            identity_type=IdentityType.HUMAN,
        )
        app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(cycles_router)
        register_domain_error_handlers(app)
        app.state.cycle_registry = self.cycles
        app.state.artifact_vault = self.vault
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    async def proposal_cycle(
        self, cycle_id: str = "cyc_ref_prop", *, campaign_id=None, stored=True
    ):
        await self.cycles.create_cycle(
            Cycle(
                cycle_id=cycle_id,
                project_id="group_run",
                created_at=NOW,
                created_by="owner",
                prd_ref=None,
                squad_profile_id="full-38",
                squad_profile_snapshot_ref="sha256:abc",
                task_flow_policy=TaskFlowPolicy(mode="sequential"),
                build_strategy="fresh",
                request_profile="campaign-proposal",
                campaign_id=campaign_id,
                kind="increment" if campaign_id else None,
            )
        )
        if stored:
            self.vault.stored["art_cr"] = (_change_request_ref(cycle_id), _CHANGE_REQUEST.encode())

    def rate(self, cycle_id: str = "cyc_ref_prop", **changes):
        return self.client.post(
            f"/api/v1/projects/group_run/cycles/{cycle_id}/proposal-rating",
            json={**_RATING, **changes},
        )

    def ratings(self) -> list[tuple[ArtifactRef, dict]]:
        return [
            (r, yaml.safe_load(c))
            for r, c in self.vault.stored.values()
            if r.artifact_type == "proposal_rating"
        ]


async def test_a_rating_is_stored_beside_the_change_request_it_is_bound_to():
    """Bug caught: the rating not stored, stored off the cycle, or stored without the binding
    and the rater, so the report cannot say which document was rated or by whom."""
    w = _World()
    await w.proposal_cycle()

    response = w.rate()

    assert response.status_code == 200, response.text
    assert response.json() == {
        "artifact_id": response.json()["artifact_id"],
        "proposal_id": "prop_567c4915dbc0",
        "version": 1,
        "verdict": "would_approve",
    }
    [(ref, doc)] = w.ratings()
    assert (ref.cycle_id, ref.run_id) == ("cyc_ref_prop", "run_prop")
    assert (doc["content_hash"], doc["verdict"], doc["rated_by"]) == (
        _HASH,
        "would_approve",
        "user-campaign-supervisor",
    )
    assert doc["ratings"]["footprint_size"] == {
        "score": 2,
        "note": "models, errors, routes, two views",
    }


@pytest.mark.parametrize(
    ("changes", "setup", "says"),
    [
        ({"content_hash": "sha-of-another-version"}, {}, "rate the document the cycle stored"),
        ({"verdict": "approved"}, {}, "verdict is one of would_approve"),
        (
            {"ratings": {"scope_fit": {"score": 3, "note": "fits"}}},
            {},
            "missing criteria_discriminability, footprint_size",
        ),
        (
            {"ratings": {**_RATING["ratings"], "scope_fit": {"score": 4, "note": "fits"}}},
            {},
            "scope_fit scores 1, 2 or 3, not 4",
        ),
        ({}, {"campaign_id": "cmp_x"}, "ruled at the increment gate, not rated"),
        ({}, {"stored": False}, "stored no change request to rate"),
    ],
    ids=[
        "stale-hash",
        "a-ruling-verdict",
        "unrated-dimensions",
        "out-of-range",
        "campaign",
        "none",
    ],
)
async def test_a_rating_that_cannot_stand_is_refused_and_nothing_is_stored(changes, setup, says):
    """Bugs caught: a rating of a document other than the one on record (an old rating
    authorizing nothing it read); a ruling's vocabulary or a partial rating accepted; a
    campaign's proposal rated instead of ruled."""
    w = _World()
    await w.proposal_cycle(**setup)

    response = w.rate(**changes)

    assert response.status_code == 422, response.text
    assert says in response.json()["detail"]["error"]["message"]
    assert w.ratings() == []


async def test_only_a_supervisor_rates():
    """Bug caught: an operator's cycle-write scope rating a proposal (§13: rulings and ratings
    are the supervisor's)."""
    w = _World(role=Role.OPERATOR)
    await w.proposal_cycle()

    assert w.rate().status_code == 403
    assert w.ratings() == []
