"""``GET /api/v1/campaigns/{id}/backlog`` (SIP-0115 §4, §8.1; SIP-0109 §24cy), entered at the route
with the runtime's error handlers over the route tests' world: a repository-backed Project (Tally)
whose goal set has two revisions, and a Campaign on it."""

from __future__ import annotations

import pytest

from squadops.auth.models import Role
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.cycles.models import GateDecisionValue
from squadops.projects.goal_set import Change, ChangeKind
from tests.fixtures.goal_set import ACCEPTED_TREE, GoalSetStore, backlog_document, proposed
from tests.unit.api.test_campaign_repository_creation import _objective, _on, _Projects
from tests.unit.api.test_campaign_routes import _identity, _World
from tests.unit.campaigns.builders import move

pytestmark = pytest.mark.auth

CID = "cmp_api000000001"


@pytest.fixture
def world() -> _World:
    world = _World()
    world.client.app.state.project_registry = _Projects()
    store = GoalSetStore()
    store.write("prj-tally", backlog_document("B-1", "B-2"))
    store.write("prj-tally", backlog_document("B-2", "B-1", "B-3"))
    world.client.app.state.goal_set_registry = store
    return world


def _campaign(world, revision="current"):
    goals = {"goal_set": "prj-tally", "revision": revision}
    resp = _on(world, "prj-tally", objective=_objective(goals=goals))
    assert resp.status_code == 201, resp.json()


async def _submitted(world, item: str, revision: int) -> None:
    """A proposal naming ``item`` at the increment gate, as the executor submits one."""
    registry = world.campaigns
    start = move(CampaignState.CALIBRATING, "s", operation=ControlOperation.START)
    await registry.transition(CID, start)
    await registry.transition(CID, move(CampaignState.AT_PROPOSAL, "d"))
    await registry.transition(
        CID,
        CampaignTransition(
            operation=ControlOperation.SUBMIT, actor="squadops", actor_role="executor",
            reason="at the gate", idempotency_key="submit:run_1",
            next_state=CampaignState.AWAITING_RULING, target="run_1",
            binding={
                "proposal_id": "prop_1", "version": 1, "content_hash": "c",
                "baseline_tree": "t", "cycle_id": "cyc_1", "backlog_item": item,
                "goals_revision": revision,
            },
            submitted=SubmittedProposal(ProposalBinding("prop_1", 1, "c", "t"), "cyc_1", "run_1"),
        ),
    )  # fmt: skip


async def test_the_backlog_reads_the_latest_revision_and_the_campaigns_own_log(world):
    """Wiring. Bugs caught: the route reading the first revision rather than the latest for a
    ``current`` Campaign; the submission's item not read from the control log, so a proposed item
    reads pending; or the next item computed from the wrong revision's order."""
    _campaign(world)
    await _submitted(world, "B-2", 2)

    body = world.client.get(f"/api/v1/campaigns/{CID}/backlog").json()

    assert (body["revision"], body["reads"], body["done"]) == (2, "current", False)
    assert [(i["item_id"], i["status"], i["position"]) for i in body["items"]] == [
        ("B-2", "proposed", 1),
        ("B-1", "pending", 2),
        ("B-3", "pending", 3),
    ]
    assert body["next_item"] == "B-1"


async def test_a_split_parent_reaches_the_body_removed_with_its_parts(world):
    """Slice 3 (#2886), §5.5a at the route. Bug caught: ``split_into`` derived but not mapped
    into the response, so the console and the crew read a split as a plain removal."""
    _campaign(world)
    registry = world.campaigns
    await registry.transition(
        CID, move(CampaignState.CALIBRATING, "s", operation=ControlOperation.START)
    )
    await registry.transition(
        CID,
        move(CampaignState.CALIBRATING, "p", operation=ControlOperation.PROMOTE,
             accepted=AcceptedTree(ACCEPTED_TREE, "cyc_cal")),
    )  # fmt: skip
    await registry.transition(CID, move(CampaignState.AT_PROPOSAL, "d"))
    await proposed(registry, CID, "B-1", revision=2, ruled=GateDecisionValue.RETURNED_FOR_REVISION)
    store = world.client.app.state.goal_set_registry
    store.write(
        "prj-tally",
        backlog_document("B-2", "B-1a", "B-1b", "B-3"),
        change=Change(ChangeKind.ITEM_SPLIT, "B-1", split_into=("B-1a", "B-1b")),
    )

    body = world.client.get(f"/api/v1/campaigns/{CID}/backlog").json()

    assert body["revision"] == 3
    assert [(i["item_id"], i["status"], i["position"], i["split_into"]) for i in body["items"]] == [
        ("B-2", "pending", 1, []),
        ("B-1a", "pending", 2, []),
        ("B-1b", "pending", 3, []),
        ("B-3", "pending", 4, []),
        ("B-1", "removed", None, ["B-1a", "B-1b"]),
    ]


def test_a_pinned_campaign_reads_its_revision_not_the_latest(world):
    """§5.5: ``revision: N`` pins one revision for the Campaign's life. Bug caught: a pinned
    Campaign reading an edit the owner made since."""
    _campaign(world, revision=1)

    body = world.client.get(f"/api/v1/campaigns/{CID}/backlog").json()

    assert (body["revision"], body["reads"]) == (1, "pinned")
    assert [i["item_id"] for i in body["items"]] == ["B-1", "B-2"]


@pytest.mark.parametrize(
    ("setup", "status", "code"),
    [
        ("no goals", 404, "CAMPAIGN_HAS_NO_GOAL_SET"),
        ("unknown campaign", 404, "CAMPAIGN_NOT_FOUND"),
        ("no read scope", 403, None),
    ],
)
def test_the_backlog_is_refused_in_the_envelope(world, setup, status, code):
    """Bugs caught: a requirements Campaign answered with an empty backlog that reads as done; a
    500 for an unknown id; or the backlog readable without ``campaigns:read``."""
    if setup == "no goals":
        assert _on(world, "prj-tally").status_code == 201
    elif setup == "no read scope":
        _campaign(world)
        world.as_(_identity(Role.AGENT))

    resp = world.client.get(f"/api/v1/campaigns/{CID}/backlog")

    assert resp.status_code == status, resp.json()
    if code:
        assert resp.json()["detail"]["error"]["code"] == code
