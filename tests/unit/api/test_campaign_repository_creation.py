"""What a Campaign must declare at its creation on its Project's kind (SIP-0109 §24bv point 5, the
2.5 plan's D10 point 3; SIP-0112 H.11).

Entered at ``POST /api/v1/campaigns``, the route ``squadops campaigns create`` calls, over the
route tests' world with the Project registry holding the shared fixture's Tally (a repository-backed
Project) and group_run (a sample application).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.cycles.models import Project, ProjectNotFoundError
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


@pytest.fixture
def world() -> _World:
    world = _World()
    world.client.app.state.project_registry = _Projects()
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
        ("prj-tally", _objective(), {}, "objective.requirements is required"),
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
