"""``/api/v1/scenario-suites`` by role (SIP-0113 §4.1; #2413).

Entered at the routes with each seat's identity. The suite's steps and checks carry a held-out
marker, and the tests read every response for it. Only the owner's review returns them, and a
squad agent's identity is refused everywhere.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.scenarios import evaluations_router, router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from tests.unit.scenarios.suite_fixtures import HELD_OUT, SUITE, suite_doc

pytestmark = pytest.mark.auth


def _identity(role: str) -> Identity:
    return Identity(
        user_id=role,
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.SERVICE if role == Role.AGENT else IdentityType.HUMAN,
    )


class _World:
    def __init__(self) -> None:
        self.store = MemoryScenarioStore()
        self.identity = _identity(Role.ADMIN)
        world = self
        app = FastAPI()

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(router)
        app.include_router(evaluations_router)
        register_domain_error_handlers(app)
        app.state.scenario_store = self.store
        # Without an authorization backend, require_scopes is a no-op: the scopes go unread.
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def as_(self, role: str) -> TestClient:
        self.identity = _identity(role)
        return self.client


def _routes(digest: str) -> list[tuple[str, str]]:
    return [
        ("GET", "/api/v1/scenario-suites"),
        ("GET", f"/api/v1/scenario-suites/{digest}"),
        ("GET", f"/api/v1/scenario-suites/{digest}/content"),
        ("POST", "/api/v1/scenario-suites"),
        ("POST", f"/api/v1/scenario-suites/{digest}/approval"),
        ("GET", "/api/v1/scenario-evaluations/evl_any000000/evidence"),
    ]


def test_the_supervisor_drafts_the_owner_approves_and_only_the_owner_reads_the_steps():
    """D2 and the independence boundary. Bug caught: the supervisor's seat approving its own
    draft, or a summary that carries held-out steps or checks to a seat that only reads goals."""
    w = _World()
    drafted = w.as_(Role.CAMPAIGN_SUPERVISOR).post("/api/v1/scenario-suites", json=SUITE)
    digest = drafted.json()["digest"]

    refused = w.as_(Role.CAMPAIGN_SUPERVISOR).post(f"/api/v1/scenario-suites/{digest}/approval")
    hidden = w.as_(Role.CAMPAIGN_SUPERVISOR).get(f"/api/v1/scenario-suites/{digest}/content")
    approved = w.as_(Role.ADMIN).post(f"/api/v1/scenario-suites/{digest}/approval")
    reviewed = w.as_(Role.ADMIN).get(f"/api/v1/scenario-suites/{digest}/content")
    triage = w.as_(Role.CAMPAIGN_TRIAGE)
    summaries = [
        triage.get("/api/v1/scenario-suites"),
        triage.get(f"/api/v1/scenario-suites/{digest}"),
    ]

    assert (drafted.status_code, drafted.json()["state"]) == (201, "draft")
    assert (refused.status_code, hidden.status_code) == (403, 403)
    assert (approved.status_code, approved.json()["approved_by"]) == (200, Role.ADMIN)
    assert reviewed.status_code == 200 and HELD_OUT in reviewed.text
    for summary in (drafted, approved, *summaries):
        assert summary.status_code in (200, 201)
        assert HELD_OUT not in summary.text
    assert [s["goal"] for s in summaries[1].json()["scenarios"]] == [
        s["goal"] for s in SUITE["scenarios"]
    ]


def test_a_squad_agents_identity_is_refused_on_every_scenario_route():
    """IR-4 at the routes. Bug caught: a scenario route an agent container's service account can
    call, through which a goal or a held-out step reaches a squad role."""
    w = _World()
    digest = w.as_(Role.ADMIN).post("/api/v1/scenario-suites", json=SUITE).json()["digest"]
    agent = w.as_(Role.AGENT)

    answers = {
        (method, path): agent.request(method, path, json=SUITE if method == "POST" else None)
        for method, path in _routes(digest)
    }

    assert {k: r.status_code for k, r in answers.items()} == {k: 403 for k in answers}
    assert not any(HELD_OUT in r.text for r in answers.values())


def _with_a_malformed_browser_step() -> dict:
    doc = suite_doc()
    doc["scenarios"][0]["steps"] = [
        {"action": "visit", "path": "/runs"},
        {"action": "fill", "target": {"role": "textbox", "names": ["Name"]}, "value": HELD_OUT,
         "note": 7},
        {"action": "click", "target": {"role": "button"}, "note": HELD_OUT},
    ]  # fmt: skip
    return doc


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        (suite_doc(scenarios=[]), 422, "SUITE_INVALID"),
        (_with_a_malformed_browser_step(), 422, "SUITE_INVALID"),
        (None, 404, "SUITE_NOT_FOUND"),
    ],
    ids=["an-invalid-suite", "a-malformed-browser-step", "approving-what-nothing-holds"],
)
def test_a_suite_the_store_cannot_take_is_refused_with_its_code(body, status, code):
    """Bug caught: an invalid draft stored, a malformed browser step stored (§10p ruling 9), or an
    approval of a digest nothing holds read as a success. No refusal carries a held-out value."""
    w = _World()
    client = w.as_(Role.ADMIN)
    if body is not None:
        resp = client.post("/api/v1/scenario-suites", json=body)
    else:
        resp = client.post(f"/api/v1/scenario-suites/{'0' * 64}/approval")

    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (status, code)
    assert HELD_OUT not in resp.text
    assert client.get("/api/v1/scenario-suites").json() == []


def test_only_the_owner_reads_an_evaluations_page_evidence():
    """SIP-0113 §10p ruling 8. Bug caught: a screenshot or a logged error of a held-out step read
    by the supervisor's seat, which drafts the next suite, or by triage; or an evaluation that
    doesn't exist answered as one with no evidence."""
    import asyncio
    from datetime import UTC, datetime

    from squadops.scenarios.evaluation import EvaluationRecord
    from squadops.scenarios.evidence import ScenarioEvidence

    w = _World()
    digest = w.as_(Role.ADMIN).post("/api/v1/scenario-suites", json=SUITE).json()["digest"]
    record = EvaluationRecord(
        evaluation_id="evl_page00000001", project_id="group_run", campaign_id=None,
        cycle_id="cyc_page00000001", evaluated_tree_identity="a" * 64,
        previous_accepted_tree_identity=None, suite_digest=digest, outcomes=(),
        evaluated_at=datetime(2026, 10, 22, tzinfo=UTC),
    )  # fmt: skip
    item = ScenarioEvidence("join-from-the-page", 3, b"\x89PNG", "button", (),
                            (f"driver: {HELD_OUT}",), (), ())  # fmt: skip
    asyncio.run(w.store.save_evaluation(record))
    asyncio.run(w.store.save_evidence(record.evaluation_id, [item]))
    path = f"/api/v1/scenario-evaluations/{record.evaluation_id}/evidence"

    owner = w.as_(Role.ADMIN).get(path)
    refused = {
        role: w.as_(role).get(path) for role in (Role.CAMPAIGN_SUPERVISOR, Role.CAMPAIGN_TRIAGE)
    }
    missing = w.as_(Role.ADMIN).get("/api/v1/scenario-evaluations/evl_none00000000/evidence")

    [shown] = owner.json()
    assert owner.status_code == 200 and HELD_OUT in shown["errors"][0]
    assert (shown["sha256"], shown["png_b64"]) == (item.sha256, "iVBORw==")
    assert {r: a.status_code for r, a in refused.items()} == dict.fromkeys(refused, 403)
    assert not any(HELD_OUT in a.text for a in refused.values())
    assert (missing.status_code, missing.json()["detail"]["error"]["code"]) == (
        404,
        "EVALUATION_NOT_FOUND",
    )
