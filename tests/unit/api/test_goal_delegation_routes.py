"""``POST /api/v1/campaigns/{id}/goal-delegation`` (SIP-0115 Q41, §10c; SIP-0109 §24dd), entered at
the routes the CLI calls, with the real authorization adapter and the runtime's error handlers: the
owner's grant, and the operator's promotion, drop and split that read it. The refusal of the
supervisor's own grant is the whole of the ruling: it can create a Campaign, and must not be able
to authorize itself on one."""

from __future__ import annotations

from dataclasses import replace

import pytest

from squadops.api.routes.cycles.goal_sets import router as goal_sets_router
from squadops.auth.models import Role
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOutcome,
)
from tests.fixtures.goal_set import GoalSetStore, goal_set_document
from tests.unit.api.test_campaign_repository_creation import _objective, _on, _Projects
from tests.unit.api.test_campaign_routes import _identity, _World
from tests.unit.campaigns.builders import move

pytestmark = pytest.mark.auth

CID = "cmp_api000000001"
GRANT = f"/api/v1/campaigns/{CID}/goal-delegation"
GOAL_SET = "/api/v1/projects/prj-tally/goal-set"
OWNER = _identity(Role.ADMIN, user="the-owner")
OPERATOR = _identity(Role.CAMPAIGN_SUPERVISOR, user="operator-client")


@pytest.fixture
def world() -> _World:
    world = _World()
    app = world.client.app
    app.include_router(goal_sets_router)
    projects = _Projects()
    projects.projects["prj-other"] = replace(projects.projects["prj-tally"], project_id="prj-other")
    app.state.project_registry = projects
    store = GoalSetStore()
    store.write("prj-tally", goal_set_document())
    store.write("prj-other", goal_set_document())
    app.state.goal_set_registry = store
    return world


def _campaign_by_the_operator(world, project_id: str = "prj-tally") -> None:
    goals = {"goal_set": project_id, "revision": "current"}
    resp = world.as_(OPERATOR) and _on(world, project_id, objective=_objective(goals=goals))
    assert resp.status_code == 201, resp.json()


def _grant(world, key: str = "g-1", **body):
    return world.client.post(
        GRANT, json={"reason": "the owner approved it", "idempotency_key": key, **body}
    )


def _promote(world, key: str = "p-1"):
    return world.client.post(
        f"{GOAL_SET}/candidates/C-1/promote",
        json={
            "idempotency_key": key,
            "expected_revision": 1,
            "reason": "it blocks the weekly total",
            "serves": ["ER-week"],
            "campaign_id": CID,
        },
    )


def _code(resp) -> tuple[int, str]:
    return resp.status_code, resp.json()["detail"]["error"]["code"]


async def _grants(world, outcome=ControlOutcome.APPLIED) -> list:
    return [
        e
        for e in await world.campaigns.control_log(CID)
        if e.operation is ControlOperation.GOAL_DELEGATION_GRANTED and e.outcome is outcome
    ]


async def _complete(world) -> None:
    await world.campaigns.transition(
        CID,
        move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
             outcome=CampaignOutcome.ABORTED),
    )  # fmt: skip


def _revisions(world, project_id: str = "prj-tally") -> list:
    return world.client.app.state.goal_set_registry.revisions[project_id]


async def test_the_operator_cannot_authorize_itself_on_a_campaign_it_created_until_the_owner_grants(
    world,
):
    """The ruling, end to end at the routes (anti-pattern 6a). Bugs caught: the operator acting within
    a Campaign it created for itself, the defect the owner's review of PR #2908 found; the grant
    route left on a scope the supervisor holds, or a refused grant writing a row that then
    authorizes it; the owner's grant not reaching the operator's check; the revision not naming the
    Campaign the act was within."""
    _campaign_by_the_operator(world)

    refused = _promote(world)
    assert _code(refused) == (403, "NOT_DELEGATED")
    assert f"squadops campaigns delegate {CID}" in refused.json()["detail"]["error"]["message"]
    assert len(_revisions(world)) == 1

    assert _code(_grant(world)) == (403, "FORBIDDEN")
    log = await world.campaigns.control_log(CID)
    assert [e for e in log if e.operation is ControlOperation.GOAL_DELEGATION_GRANTED] == []
    assert _code(_promote(world, "p-2")) == (403, "NOT_DELEGATED")

    granted = world.as_(OWNER) and _grant(world, source_ref="https://chat.example.invalid/t/7")
    assert granted.status_code == 201, granted.json()
    body = granted.json()
    assert (body["replayed"], body["entry"]["operation"], body["entry"]["actor"]) == (
        False,
        "goal_delegation_granted",
        "the-owner",
    )
    assert body["entry"]["binding"] == {
        "goal_set": "prj-tally",
        "source_ref": "https://chat.example.invalid/t/7",
    }
    assert body["campaign"]["state"] == "draft"

    promoted = world.as_(OPERATOR) and _promote(world, "p-3")
    assert promoted.status_code == 201, promoted.json()
    written = _revisions(world)[-1]
    assert (written.revision, written.author, written.change.campaign_id) == (
        2,
        "operator-client",
        CID,
    )
    assert promoted.json()["revision"]["change"]["campaign_id"] == CID


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (Role.ADMIN, 201),
        (Role.CAMPAIGN_SUPERVISOR, 403),
        (Role.CAMPAIGN_TRIAGE, 403),
        (Role.OPERATOR, 403),
        (Role.VIEWER, 403),
    ],
)
async def test_only_the_owners_scope_grants_and_a_refusal_applies_nothing(world, role, status):
    """Bug caught: the route on ``campaigns:manage`` or ``:supervise``, which the operator holds, so
    the grant is no check on the operator at all."""
    _campaign_by_the_operator(world)

    resp = world.as_(_identity(role)) and _grant(world)

    assert resp.status_code == status, resp.json()
    assert len(await _grants(world)) == (1 if status == 201 else 0)


async def test_a_repeat_replays_and_a_committed_grant_still_replays_after_the_campaign_closed(
    world,
):
    """Bug caught: a retry writing a second row, or a retry of a committed grant refused once the
    Campaign closed, so the owner reads a grant on the log as one that failed."""
    _campaign_by_the_operator(world)
    world.as_(OWNER)
    first = _grant(world)

    again = _grant(world)
    await _complete(world)
    after_the_close = _grant(world)

    for repeat in (again, after_the_close):
        assert (repeat.status_code, repeat.json()["replayed"]) == (201, True)
        assert repeat.json()["entry"]["entry_id"] == first.json()["entry"]["entry_id"]
    assert len(await _grants(world)) == 1


async def test_a_completed_campaign_refuses_a_grant_and_the_operator_stays_refused(world):
    """Bug caught: a grant accepted as a record after the close, which a completed Campaign's
    other records are; the operator's check reading it."""
    _campaign_by_the_operator(world)
    await _complete(world)

    resp = world.as_(OWNER) and _grant(world)

    assert _code(resp) == (409, "CONTROL_OPERATION_REFUSED")
    assert resp.json()["detail"]["error"]["details"]["refusal"] == "campaign_completed"
    assert await _grants(world) == []
    assert len(await _grants(world, ControlOutcome.REFUSED)) == 1
    assert _code(world.as_(OPERATOR) and _promote(world)) == (403, "NOT_DELEGATED")


async def test_a_grant_on_another_projects_campaign_delegates_nothing_here(world):
    """Bug caught: the check reading the grant and not the Campaign's Project, so a grant on one
    Project's Campaign lets the operator curate another's goal set."""
    _campaign_by_the_operator(world, "prj-other")
    assert (world.as_(OWNER) and _grant(world)).status_code == 201

    refused = world.as_(OPERATOR) and _promote(world)

    assert _code(refused) == (403, "NOT_DELEGATED")
    assert "is on Project prj-other" in refused.json()["detail"]["error"]["message"]
    assert len(_revisions(world)) == 1


@pytest.mark.parametrize(
    ("setup", "status", "code"),
    [
        ("unknown", 404, "CAMPAIGN_NOT_FOUND"),
        ("requirements", 404, "CAMPAIGN_HAS_NO_GOAL_SET"),
        ("bad state", 422, "VALIDATION_ERROR"),
        ("blank reason", 422, "VALIDATION_ERROR"),
    ],
)
async def test_a_grant_is_refused_in_the_envelope_and_applies_nothing(world, setup, status, code):
    """Bugs caught: a 500 for an unknown id, a misspelt state or a blank reason; a grant on a
    requirements Campaign, which reads as a delegation over a goal set it doesn't name."""
    if setup == "requirements":
        assert _on(world, "prj-tally").status_code == 201
    elif setup != "unknown":
        _campaign_by_the_operator(world)
    world.as_(OWNER)
    extra = {"expected_state": "nowhere"} if setup == "bad state" else {}
    if setup == "blank reason":
        extra = {"reason": "  "}

    resp = _grant(world, **extra)

    assert resp.status_code == status, resp.json()
    assert resp.json()["detail"]["error"]["code"] == code
    if setup != "unknown":
        assert await _grants(world) == []
