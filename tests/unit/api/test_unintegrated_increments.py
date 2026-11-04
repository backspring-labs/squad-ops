"""``GET /api/v1/projects/{id}/unintegrated-increments`` (SIP-0109 §24dc, #2863): the accepted
Campaign work its Project's integrated commit doesn't carry yet, the signal the crew's supervisor
gates a draft on.

Entered at the route, as the runtime mounts it, over ``test_close_contribution``'s world: Tally, a
real managed clone and real deliveries, a Campaign closed by its accepted increment, and its
contribution opened (or not) at the close. The product's merge is made in the fixture's own
repository, as the owner makes it on the forge.
"""

from __future__ import annotations

import dataclasses

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.factory import create_project_registry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.projects import router as projects_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.models import (
    Campaign,
    CampaignGoals,
    CampaignState,
    ControlOperation,
    CycleKind,
)
from squadops.campaigns.unintegrated import unintegrated_increments
from squadops.cycles.models import Project
from squadops.projects.contribution import CAMPAIGN_RUN, Contribution
from tests.fixtures.goal_set import GoalSetStore, backlog_document
from tests.fixtures.shared_contract.repository import _git
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.builders import T0, campaign
from tests.unit.campaigns.test_campaign_branch import NOW
from tests.unit.campaigns.test_close_contribution import (
    BRANCH,
    CID,
    URL,
    _intent,
    _row,
    _World,
)

PATH = f"/api/v1/projects/{PROJECT}/unintegrated-increments"
INCREMENT = "cyc_inc000000001"
#: The merge's identity, as the fixture's own commits name theirs: none comes from the host.
_OWNER = {
    "GIT_AUTHOR_NAME": "Tally Owner",
    "GIT_AUTHOR_EMAIL": "owner@tally.example.invalid",
    "GIT_COMMITTER_NAME": "Tally Owner",
    "GIT_COMMITTER_EMAIL": "owner@tally.example.invalid",
}


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


def _merged(world: _World) -> str:
    """The owner merges the review request on the product, by a merge commit, and the Project's
    clone fetches it. Returns the merge."""
    _git(world.repo.path, "merge", "-q", "--no-ff", "-m", "merge the campaign", BRANCH, env=_OWNER)
    return _git(world.repo.path, "rev-parse", "HEAD").strip()


async def _integrated_at(world: _World, commit: str) -> None:
    """The Project re-validated at ``commit``: its integrated commit, as E.4.4 moves it."""
    await world.clones.sync(PROJECT, str(world.repo.path), "refs/heads/main")
    world.projects.project = dataclasses.replace(
        world.projects.project, integrated_upstream_commit=commit
    )


async def test_an_opened_contribution_reads_pending_until_the_integrated_commit_carries_it(
    tmp_path,
):
    """The wiring and the standing's one path to empty. Bugs caught:
    - a contributed increment missing from the set, so a draft starts without it (campaign 5);
    - the standing read from the contribution alone, so a merge that is synced still lists;
    - a merged contribution listed after the Project's commit carries it: the gate never opens;
    - the review request's address missing, so the supervisor can't say what it waits on."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()
    await _integrated_at(world, world.repo.second_commit)
    client = world.client()
    opened = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": "tok"})
    assert opened.status_code == 201, opened.text

    pending = client.get(PATH)
    merge = _merged(world)
    world.book.recorded[0] = dataclasses.replace(
        world.book.recorded[0], state="integrated", integrated_commit=merge
    )
    not_synced = client.get(PATH)
    await _integrated_at(world, merge)
    integrated = client.get(PATH)

    assert pending.status_code == 200, pending.text
    [item] = pending.json()
    commit = (await world.campaigns.get_campaign(CID)).accepted.commit
    assert item == {
        "campaign_id": CID,
        "campaign_state": "completed",
        "cycle_id": INCREMENT,
        "title": None,
        "commit": commit,
        "standing": "contribution_pending",
        "review_url": URL,
    }
    assert [i["standing"] for i in not_synced.json()] == ["merged_not_synced"]
    assert integrated.json() == []


async def test_an_increment_never_contributed_stands_not_contributed(tmp_path):
    """The Campaign closed and the supervisor hasn't opened its contribution. Bug caught: an
    accepted increment with no contribution left out of the set, since nothing names it but its
    Campaign's log."""
    world = _World(tmp_path)
    await world.started()
    await world.accepted_with_criterion()

    body = world.client().get(PATH).json()

    assert [(i["cycle_id"], i["standing"], i["review_url"]) for i in body] == [
        (INCREMENT, "not_contributed", None)
    ]


async def test_a_campaign_with_no_accepted_increment_lists_nothing(tmp_path):
    """The empty set a gate reads. Bug caught: a calibration's promotion read as an increment, so
    a Campaign that accepted nothing blocks every draft."""
    world = _World(tmp_path)
    await world.started(target=2)

    resp = world.client().get(PATH)

    assert (resp.status_code, resp.json()) == (200, [])


class _Log:
    """A campaign registry's reads, over rows as the registry commits them."""

    def __init__(self, held: Campaign, rows: list, intents: list) -> None:
        self.held, self.rows, self.intents = held, rows, intents

    async def list_campaigns(self, project_id, *, limit=None, offset=0):
        return [self.held]

    async def control_log(self, campaign_id):
        return list(self.rows)

    async def launch_intents(self, campaign_id):
        return list(self.intents)


class _Clone:
    """The managed clone's ancestry, as a table: ``carried`` holds what the integrated commit
    has in its history."""

    def __init__(self, carried: set[str]) -> None:
        self.carried = carried

    async def is_ancestor(self, project_id, ancestor, descendant):
        return ancestor in self.carried


def _goal_set_world():
    """A goal-set Campaign that accepted B-1 by a repair of its increment and B-2 by its own
    increment: submitted, approved and promoted, as its rows are committed."""

    def row(seq, operation, binding, target=None):
        return dataclasses.replace(
            _row(seq, operation, binding), target=target, actor_role="supervisor"
        )

    def submitted(seq, proposal, cycle, item):
        return row(seq, ControlOperation.SUBMIT, {
            "proposal_id": proposal, "version": 1, "content_hash": "c", "baseline_tree": "t",
            "cycle_id": cycle, "backlog_item": item, "goals_revision": 1,
        }, target=f"run_{proposal}")  # fmt: skip

    def approved(seq, proposal):
        return row(seq, ControlOperation.RULE, {
            "proposal_id": proposal, "version": 1, "decision": "approved", "reason": "go",
        })  # fmt: skip

    def promoted(seq, cycle, commit):
        return row(seq, ControlOperation.PROMOTE, {"cycle_id": cycle, "commit": commit}, cycle)

    rows = [
        row(1, ControlOperation.PROMOTE, {"calibration_record_id": "rec", "commit": "c0"}, "rec"),
        submitted(2, "prop_1", "cyc_inc1", "B-1"), approved(3, "prop_1"),
        promoted(4, "cyc_rep1", "a1"),
        submitted(5, "prop_2", "cyc_inc2", "B-2"), approved(6, "prop_2"),
        promoted(7, "cyc_inc2", "b1"),
    ]  # fmt: skip
    repair = dataclasses.replace(
        _intent("cyc_rep1", CycleKind.REPAIR),
        cycle_request={"body": {"execution_overrides": {"campaign_proposal": {
            "proposal_id": "prop_1", "version": 1, "continues": "cyc_inc1"}}}},
    )  # fmt: skip
    intents = [_intent("cyc_inc1", CycleKind.INCREMENT), repair,
               _intent("cyc_inc2", CycleKind.INCREMENT)]  # fmt: skip
    held = campaign(
        CID,
        project_id=PROJECT,
        state=CampaignState.BUILDING,
        objective=dataclasses.replace(
            campaign(CID).objective, goals=CampaignGoals(PROJECT, "current")
        ),
    )
    goal_sets = GoalSetStore()
    goal_sets.write(PROJECT, backlog_document("B-1", "B-2", "B-3"))
    return held, _Log(held, rows, intents), goal_sets


@pytest.mark.parametrize(
    ("contribution", "carried", "expected"),
    [
        # nothing contributed: both listed, each titled by the item its proposal served
        (None, set(), [("cyc_rep1", "Item B-1", "not_contributed"),
                       ("cyc_inc2", "Item B-2", "not_contributed")]),
        # closed on the forge without merging: the work isn't in, so not contributed
        ("closed", set(), [("cyc_rep1", "Item B-1", "not_contributed"),
                           ("cyc_inc2", "Item B-2", "not_contributed")]),
        # the integrated commit carries the first only, as a merge of part of the branch would
        ("pending", {"a1"}, [("cyc_inc2", "Item B-2", "contribution_pending")]),
        # a squash merge: the increments' commits are never ancestors, the merge commit is
        ("integrated", {"squash"}, []),
    ],
)  # fmt: skip
async def test_each_increment_stands_by_its_contribution_and_the_integrated_commit(
    contribution, carried, expected
):
    """The reading, on rows as the registry commits them. Bugs caught:
    - a repair's acceptance titled by nothing, since its own cycle submitted no proposal;
    - a closed contribution read as pending, so the gate waits on a request nobody will merge;
    - one increment carried hiding the rest, or the set read from the contribution alone;
    - a squash merge never read as integrated, so the gate never opens."""
    held, log, goal_sets = _goal_set_world()
    project = Project(
        project_id=PROJECT, name="Tally", description="", created_at=T0,
        integrated_upstream_commit="u" * 40,
    )  # fmt: skip
    recorded = []
    if contribution is not None:
        recorded.append(
            Contribution(
                project_id=PROJECT, cycle_id=CID, run_id=CAMPAIGN_RUN, commit="r1",
                parent_commit="c0", mode="review_request", state=contribution, branch=BRANCH,
                review_url=URL, contributed_by="squadops", contributed_at=NOW,
                integrated_commit="squash" if contribution == "integrated" else None,
            )
        )  # fmt: skip

    listed = await unintegrated_increments(
        project,
        campaigns=log,
        contributions=recorded,
        repository=_Clone(carried),
        goal_sets=goal_sets,
    )

    assert [(i.cycle_id, i.title, i.standing.value) for i in listed] == expected


def _per_run(cycle_id: str, state: str, integrated: str | None = None) -> Contribution:
    """A contribution through ``POST /api/v1/projects/{id}/contributions``: one run's change."""
    return Contribution(
        project_id=PROJECT, cycle_id=cycle_id, run_id="run_x", commit="r9", parent_commit="c0",
        mode="review_request", state=state, branch=f"squadops/{cycle_id}",
        review_url=f"https://forge.example.invalid/pull/{cycle_id}", contributed_by="owner",
        contributed_at=NOW, integrated_commit=integrated,
    )  # fmt: skip


async def test_an_increment_contributed_by_its_own_run_stands_by_that_record():
    """PR #2920's review, finding 2. The per-run route is a contribution too: an increment
    contributed through it, squash-merged and synced, is integrated, and another pending there
    is pending. Bugs caught: per-run records dropped by the campaign filter, so integrated work
    reads ``not_contributed`` and the gate never opens; a record matched to the wrong cycle."""
    _held, log, goal_sets = _goal_set_world()
    project = Project(
        project_id=PROJECT, name="Tally", description="", created_at=T0,
        integrated_upstream_commit="u" * 40,
    )  # fmt: skip

    listed = await unintegrated_increments(
        project,
        campaigns=log,
        contributions=[
            _per_run("cyc_rep1", "integrated", "squash1"),
            _per_run("cyc_inc2", "pending"),
        ],
        repository=_Clone({"squash1"}),
        goal_sets=goal_sets,
    )

    assert [(i.cycle_id, i.standing.value, i.review_url) for i in listed] == [
        ("cyc_inc2", "contribution_pending", "https://forge.example.invalid/pull/cyc_inc2")
    ]


@pytest.mark.parametrize(
    ("project_id", "status", "code"),
    [
        ("group_run", 409, "NO_SOURCE_REPOSITORY"),  # a sample application
        ("prj-nosuch", 404, "PROJECT_NOT_FOUND"),
    ],
)
def test_a_project_with_no_repository_and_an_unknown_one_are_refused(project_id, status, code):
    """Bugs caught: a sample application answered with an empty list, which a gate reads as
    "everything integrated"; an unknown Project answered with a 500 or an empty list."""
    app = FastAPI()

    class InjectIdentity(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            roles = (Role.CAMPAIGN_SUPERVISOR,)
            request.state.identity = Identity(
                user_id="supervisor", display_name="supervisor", roles=roles,
                scopes=tuple(sorted(scopes_for_roles(roles))), identity_type=IdentityType.HUMAN,
            )  # fmt: skip
            return await call_next(request)

    app.add_middleware(InjectIdentity)
    app.include_router(projects_router)
    register_domain_error_handlers(app)
    app.state.project_registry = create_project_registry("config")
    app.state.authz_port = KeycloakAuthzAdapter()

    resp = TestClient(app).get(f"/api/v1/projects/{project_id}/unintegrated-increments")

    assert resp.status_code == status, resp.text
    assert resp.json()["detail"]["error"]["code"] == code
