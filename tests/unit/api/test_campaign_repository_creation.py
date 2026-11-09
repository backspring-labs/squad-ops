"""What a Campaign must declare at its creation on its Project's kind (SIP-0109 §24bv point 5, the
2.5 plan's D10 point 3; SIP-0112 H.11).

Entered at ``POST /api/v1/campaigns``, the route ``squadops campaigns create`` calls, over the
route tests' world with the Project registry holding the shared fixture's Tally (a repository-backed
Project) and group_run (a sample application).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from squadops.cycles.models import GoalSetNotFoundError, Project, ProjectNotFoundError
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from tests.unit.api.test_campaign_routes import _POLICY, _create, _World

pytestmark = pytest.mark.auth

_REQUIREMENTS = "repo:file:README.md@current"


class _Projects:
    def __init__(self) -> None:
        self.projects = {
            "prj-tally": Project(
                project_id="prj-tally",
                name="Tally",
                description="the shared fixture",
                created_at=datetime(2026, 10, 18, tzinfo=UTC),
                lifecycle_status=ProjectLifecycleStatus.READY,
                source=ProjectSource("file:///srv/tally.git", "refs/heads/main", "review_request"),
            ),
            "group_run": Project(
                project_id="group_run",
                name="group_run",
                description="a sample application",
                created_at=datetime(2026, 10, 18, tzinfo=UTC),
            ),
        }

    async def get_project(self, project_id):
        try:
            return self.projects[project_id]
        except KeyError:
            raise ProjectNotFoundError(project_id) from None


class _GoalSets:
    """The Projects' goal sets: Tally's has three revisions written; group_run's has none."""

    def __init__(self) -> None:
        self.latest = {"prj-tally": 3}

    async def get_revision(self, project_id, revision=None):
        if project_id not in self.latest:
            raise GoalSetNotFoundError(project_id)
        return SimpleNamespace(project_id=project_id, revision=self.latest[project_id])


@pytest.fixture
def world() -> _World:
    world = _World()
    world.client.app.state.project_registry = _Projects()
    world.client.app.state.goal_set_registry = _GoalSets()
    return world


def _objective(**extra) -> dict:
    return {
        "statement": "the report gains totals",
        "allowed_scope": ["tally/**"],
        "measurement": "one accepted increment",
        "target_accepted_increments": 1,
        "work_class": {"prd_tier": "tier-1", "attendance": "attended"},
        **extra,
    }


def _on(world, project_id, *, objective=None, **policy):
    return _create(
        world,
        project_id=project_id,
        objective=objective or _objective(requirements=_REQUIREMENTS),
        policy={**_POLICY, "proposal_profile": "campaign-increment-source", **policy},
    )


@pytest.mark.parametrize(
    ("project_id", "objective", "policy", "named"),
    [
        ("prj-tally", _objective(), {}, "objective.requirements or objective.goals is required"),
        (
            "prj-tally",
            None,
            {"proposal_profile": "campaign-increment"},
            "policy.proposal_profile: the Campaign's increments would seed",
        ),
        ("prj-tally", None, {"stack": "fullstack_fastapi_react"}, "policy.stack: the Campaign's"),
        (
            "prj-tally",
            _objective(requirements="repo:file:docs/prd.md@abc1234"),
            {},
            "is neither repo:file:<path>@current",
        ),
        ("group_run", None, {}, "only a repository-backed Project's Campaign reads"),
    ],
    ids=[
        "no requirements source",
        "a stacked increment profile",
        "a declared stack",
        "a fixed revision",
        "a sample application naming one",
    ],
)
def test_a_campaign_its_projects_kind_refuses_is_refused_at_creation_naming_the_field(
    world, project_id, objective, policy, named
):
    """Bugs caught: a repository-backed Campaign created with no requirements source, whose every
    proposal run then fails reading none; one whose increments seed a stack's skeleton beside the
    product (``seeds_skeleton``, H.11), refused only at its first launch; a requirements source at
    a fixed revision, which an increment that edits the PRD would never be shown; or a sample
    application's Campaign carrying a source nothing reads."""
    resp = _on(world, project_id, objective=objective, **policy)

    assert resp.status_code == 422, resp.json()
    assert named in resp.json()["detail"]["error"]["message"]
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == 404


def test_a_repository_backed_campaign_with_its_source_and_a_stackless_profile_is_created(world):
    """Bug caught: the requirements source dropped between the request and the stored campaign,
    so the launch writes no ``objective.requirements`` for the proposal to read."""
    resp = _on(world, "prj-tally")

    assert resp.status_code == 201, resp.json()
    read = world.client.get("/api/v1/campaigns/cmp_api000000001").json()
    assert read["objective"]["requirements"] == _REQUIREMENTS


def test_a_project_the_registry_doesnt_hold_is_left_to_the_start(world):
    """The edge: the start reads the Project's state, and refuses one it can't (§24cc). Bug caught:
    creation turning an unknown Project into a 500, or a refusal the start would make anyway."""
    assert _on(world, "prj-unknown").status_code == 201


def _goals(revision="current", goal_set="prj-tally") -> dict:
    return {"goal_set": goal_set, "revision": revision}


@pytest.mark.parametrize(
    ("project_id", "objective", "named"),
    [
        (
            "prj-tally",
            _objective(requirements=_REQUIREMENTS, goals=_goals()),
            "names goals or requirements, never both",
        ),
        ("prj-tally", _objective(goals=_goals(revision=4)), "goal set has revisions 1 to 3"),
        ("prj-tally", _objective(goals=_goals(revision=0)), "is a revision number"),
        ("prj-tally", _objective(goals=_goals(goal_set="group_run")), "is not this Campaign's"),
        ("prj-tally", _objective(stop_when="backlog_done"), "objective names no goals"),
        ("group_run", _objective(goals=_goals(goal_set="group_run")), "is a sample application"),
    ],
    ids=[
        "both goals and requirements",
        "a pinned revision the goal set doesn't hold",
        "revision zero",
        "another Project's goal set",
        "stop_when without goals",
        "a sample application naming goals",
    ],
)
def test_a_goal_set_campaign_its_project_cant_back_is_refused_at_creation(
    world, project_id, objective, named
):
    """SIP-0115 §5.1. Bugs caught: a Campaign naming both sources, so which one its proposal reads
    is a guess; one pinned to a revision never written, whose first proposal fails reading it; a
    definition copied from another Project and read against this one's goals; ``backlog_done``
    with no backlog to read, which would never stop it; a sample application carrying a goal set
    nothing reads."""
    resp = _on(world, project_id, objective=objective)

    assert resp.status_code == 422, resp.json()
    assert named in resp.json()["detail"]["error"]["message"]
    assert world.client.get("/api/v1/campaigns/cmp_api000000001").status_code == 404


def test_a_project_with_no_goal_set_refuses_a_campaign_naming_one(world):
    """The edge: no revision written at all. Bug caught: the registry's not-found surfacing as a
    404 for the Campaign, or a Campaign created whose every proposal then fails."""
    del world.client.app.state.goal_set_registry.latest["prj-tally"]

    resp = _on(world, "prj-tally", objective=_objective(goals=_goals()))

    assert resp.status_code == 422, resp.json()
    assert "has no goal set written" in resp.json()["detail"]["error"]["message"]


@pytest.mark.parametrize("revision", ["current", 2])
def test_a_goal_set_campaign_is_created_with_its_binding_and_stop_rule_read_back(world, revision):
    """Bug caught: ``goals`` or ``stop_when`` dropped between the request and the stored
    campaign, so its proposals read no goal set and ``backlog_done`` never stops it."""
    resp = _on(
        world,
        "prj-tally",
        objective=_objective(goals=_goals(revision), stop_when="backlog_done"),
    )

    assert resp.status_code == 201, resp.json()
    read = world.client.get("/api/v1/campaigns/cmp_api000000001").json()["objective"]
    assert read["goals"] == {"goal_set": "prj-tally", "revision": revision}
    assert read["stop_when"] == "backlog_done"
    assert read["requirements"] is None
