"""Cross-Cycle Memory's lesson routes (SIP-0110 §0.6–§0.7; slice 3d, #2096), entered at the HTTP surface
with the real authorization adapter, over the in-memory store.

What bugs would these catch? Anyone but the owner approving or revoking a lesson (the stop list's
"approving any lesson is the owner's"); an approval stored without the combined check §0.6 requires;
a revocation that names none of the running units holding it; a draft citing evidence the store
never recorded.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from squadops.api.routes.memory import memory_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.models import ControlOperation
from squadops.memory.lessons import UnitKind
from squadops.memory.observations import observe_proposal_rulings
from squadops.memory.pinning import pin_unit
from tests.unit.memory.test_observations import _entry

pytestmark = pytest.mark.auth

BASE = "/api/v1/projects/group_run"
WHERE = {
    "task_types": ["strategy.propose_increment"],
    "roles": ["strat"],
    "stacks": ["fullstack_fastapi_react"],
    "model_families": ["qwen3.8"],
}


def _identity(role: str) -> Identity:
    return Identity(
        user_id=f"user-{role}",
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.HUMAN,
    )


class _World:
    def __init__(self) -> None:
        self.store = InMemoryCrossCycleMemoryStore()
        self.identity = _identity(Role.ADMIN)
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(memory_router)
        app.state.memory_store = self.store
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def draft(self, target: str = "criterion_already_satisfied", **change):
        body = {
            "target_behavior": target,
            "text": "Name the manifest element the criterion checks.",
            "applicability": WHERE,
            "template_id": "lesson.criterion_already_satisfied",
            "template_version": "1",
            "drafter_model": "claude-opus",
            "drafter_version": "5.5",
            "cited_observations": [self.cited],
            **change,
        }
        return self.client.post(f"{BASE}/lessons", json=body)

    def approve(self, revision_id: str, checked=(), verdict="no_conflict", **change):
        body = {
            "ruling": "the owner, 2026-10-09: approve it",
            "replay_check": {"reference": "replay/arm-a-vs-b", "result": "absent 5/6 vs 1/6"},
            "combined_check": {
                "revision_ids": list(checked),
                "verdict": verdict,
                "reference": "auditor/combined",
            },
            **change,
        }
        return self.client.post(f"{BASE}/lessons/{revision_id}/approvals", json=body)


@pytest.fixture
async def world() -> _World:
    w = _World()
    bind = {"proposal_id": "prop_1", "version": 1, "decision": "returned_for_revision"}
    [observed] = observe_proposal_rulings(
        "cmp_1", "group_run", [_entry(1, ControlOperation.RULE, bind)]
    )
    await w.store.record_observations([observed])
    w.cited = observed.source_id
    return w


@pytest.mark.parametrize(
    ("role", "route", "status"),
    [
        (Role.VIEWER, "list", 200),
        (Role.CAMPAIGN_TRIAGE, "list", 200),
        (Role.OPERATOR, "draft", 403),
        (Role.CAMPAIGN_SUPERVISOR, "draft", 403),
        (Role.CAMPAIGN_SUPERVISOR, "approve", 403),
        (Role.OPERATOR, "approve", 403),
        (Role.ADMIN, "approve", 201),
    ],
)
async def test_approving_a_lesson_is_the_owners_alone(world, role, route, status):
    """Bug caught: the crew's supervisor, or an operator who writes cycles, approving a lesson into
    every later unit's prompts (the stop list: approving any lesson is the owner's)."""
    revision_id = world.draft().json()["revision_id"]
    world.identity = _identity(role)

    resp = {
        "list": lambda: world.client.get(f"{BASE}/lessons"),
        "draft": lambda: world.draft("another_behavior"),
        "approve": lambda: world.approve(revision_id),
    }[route]()

    assert resp.status_code == status


async def test_a_draft_is_approved_only_with_a_combined_check_of_what_it_would_be_supplied_beside(
    world,
):
    """§0.15 combined guidance through the routes. Bug caught: an approval stored when a lesson
    already approved for the same tasks was never checked beside it."""
    held = world.draft("criterion_names_no_element").json()["revision_id"]
    assert world.approve(held).status_code == 201
    draft = world.draft().json()

    together = world.client.get(f"{BASE}/lessons/{draft['revision_id']}/supplied-together").json()
    refused = world.approve(draft["revision_id"])
    approved = world.approve(draft["revision_id"], checked=together["revision_ids"])

    assert (draft["revision"], together["revision_ids"]) == (1, [held])
    assert (
        refused.status_code == 422 and "not covered" in refused.json()["detail"]["error"]["message"]
    )
    assert approved.status_code == 201
    assert approved.json()["approved_by"] == "user-admin"
    listed = {x["revision_id"]: x for x in world.client.get(f"{BASE}/lessons").json()}
    assert len(listed[draft["revision_id"]]["approvals"]) == 1


async def test_a_revocation_names_the_running_units_that_hold_it_and_stands_once(world):
    """§0.7, D9. Bugs caught: a revocation that says nothing of the units running with the lesson
    pinned, so their measurements are read as if it never happened; or a second revocation
    rewriting who revoked it and why."""
    revision_id = world.draft().json()["revision_id"]
    approval_id = world.approve(revision_id).json()["approval_id"]
    await pin_unit(
        world.store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_running",
        project_id="group_run",
        pinned_at=datetime.now(UTC),
        disabled=False,
    )

    first = world.client.post(f"{BASE}/approvals/{approval_id}/revocation", json={"reason": "harm"})
    again = world.client.post(f"{BASE}/approvals/{approval_id}/revocation", json={"reason": "x"})

    body = first.json()
    assert first.status_code == 200
    assert [u["unit_id"] for u in body["units_holding_it"]] == ["cmp_running"]
    assert (body["approval"]["revoked_by"], body["approval"]["revocation_reason"]) == (
        "user-admin",
        "harm",
    )
    assert "halt or restart" in body["next"]
    assert again.status_code == 409


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"cited_observations": ["proposal_ruling:cmp_x:e9"]}, "not recorded"),
        ({"applicability": {**WHERE, "model_families": [""]}}, "an applicability names its"),
        ({"text": " "}, "names its text"),
    ],
)
async def test_a_draft_the_rules_refuse_is_a_422_and_stores_nothing(world, change, message):
    resp = world.draft(**change)

    assert resp.status_code == 422
    assert message in resp.json()["detail"]["error"]["message"]
    assert world.client.get(f"{BASE}/lessons").json() == []


async def test_an_exposures_target_is_assessed_and_the_rate_reads_the_supplied_series(world):
    """§0.10 through the routes. Bugs caught: an absence recorded where the work was left out;
    the supplied flag taken from the caller rather than the exposure's own intervention, so the
    memory-on series could be filled by assertion."""
    from squadops.memory.exposures import Exposure
    from squadops.memory.lessons import RecallDisposition, Recalled
    from squadops.memory.recall import RecallQuery

    exposure = Exposure(
        run_id="run_p",
        task_id="task-prop",
        cycle_id="cyc_inc",
        agent_id="nat",
        seam="proposal_writing",
        query=RecallQuery("group_run", "strategy.propose_increment", "strat"),
        recalled={
            **Recalled("snp_x", RecallDisposition.SUPPLIED).exposure(),
            "intervention": [{"revision_id": "pat_a@1"}],
        },
        recorded_at=datetime.now(UTC),
    )
    await world.store.record_exposure(exposure)
    path = f"{BASE}/exposures/{exposure.exposure_id}/assessments"
    body = {"pattern_id": "pat_a", "rubric": "lesson.r@1", "evidence": "change_request v1"}

    leaving_work_out = world.client.post(path, json={**body, "state": "absent"})
    absent = world.client.post(path, json={**body, "state": "absent", "required_work_done": True})
    rates = world.client.get(f"{BASE}/lessons/absence-rates").json()
    listed = world.client.get(f"{BASE}/exposures", params={"run_id": "run_p"}).json()

    assert leaving_work_out.status_code == 422
    assert absent.status_code == 201 and absent.json()["supplied"] is True
    assert rates == [
        {
            "pattern_id": "pat_a",
            "supplied": True,
            "absent": 1,
            "assessed": 1,
            "not_applicable": 0,
            "unassessed": 0,
            "rate": 1.0,
        }
    ]
    assert [a["state"] for a in listed[0]["assessments"]] == ["absent"]
