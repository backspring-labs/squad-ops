"""A goal-set Campaign's proposal at its ruling (SIP-0115 §5.5a; SIP-0109 §24cy).

Entered at ``POST …/runs/{r}/gates/progress_increment_ruling``, the route ``squadops runs gate``
calls, over the increment-gate route tests' world: the proposal at the gate names backlog item
``B-1``, created under goal-set revision 1. What the ruling leaves on the control log, the run and
the campaign is read back.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.campaigns.models import CampaignGoals, CampaignState
from tests.fixtures.goal_set import GoalSetStore, backlog_document
from tests.unit.api import test_increment_gate_route as gate_route
from tests.unit.campaigns.builders import campaign

pytestmark = pytest.mark.auth

CID = gate_route.CID
_R1 = backlog_document("B-1", "B-2")


def _with_result_changed() -> dict:
    doc = backlog_document("B-1", "B-2")
    doc["expected_results"][1]["statement"] = "The week's total minutes are shown, by book"
    return doc


async def _world(revision, *later: dict) -> gate_route._World:
    """The route world, its campaign on goal set revision ``revision``, at the gate with B-1."""
    world = gate_route._World()
    goals = CampaignGoals(goal_set="group_run", revision=revision)
    built = campaign(CID)
    built = dataclasses.replace(built, objective=dataclasses.replace(built.objective, goals=goals))
    store = GoalSetStore()
    store.write("group_run", _R1)
    for doc in later:
        store.write("group_run", doc)
    world.client.app.state.goal_set_registry = store
    await world.campaigns.create_campaign(
        built, actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await gate_route.at_the_gate(world, {"backlog_item": "B-1", "goals_revision": 1})
    return world


@pytest.mark.parametrize(
    ("revision", "later", "decision", "classification", "returned"),
    [
        ("current", (), "approved", None, None),
        ("current", (backlog_document("B-2", "B-1"),), "approved", None, "B-2 is"),
        ("current", (_with_result_changed(),), "approved", None, "an expected result"),
        (
            "current",
            (backlog_document("B-2", "B-1"),),
            "rejected",
            "scope_too_large",
            "B-2 is",
        ),
        (1, (backlog_document("B-2", "B-1"),), "approved", None, None),
        ("current", (backlog_document("B-1", "B-2", "B-3"),), "approved", None, None),
    ],
    ids=[
        "no later revision",
        "reordered past its item",
        "its result changed",
        "a rejection of a moved item",
        "a pinned campaign",
        "an item added after it",
    ],
)
async def test_a_proposal_whose_item_a_later_revision_moved_is_returned_as_goals_revised(
    revision, later, decision, classification, returned
):
    """§5.5a. Bugs caught: an approval building an item the owner has since moved down or whose
    expected results changed, so the increment is judged against goals nobody holds now; a
    rejection of such a proposal counted toward ``max_rejected_proposals_in_row``, though nothing
    was wrong with it; a pinned Campaign returned for an edit it never reads; or a revision that
    leaves the item first (an item appended) costing a ruling."""
    world = await _world(revision, *later)

    resp = world.rule(decision=decision, classification=classification)

    assert resp.status_code == 200, resp.json()
    [rule] = [e for e in await world.campaigns.control_log(CID) if e.operation == "rule"]
    gate = await world.gate_decisions()
    state = (await world.campaigns.get_campaign(CID)).state
    if returned is None:
        assert rule.binding["decision"] == decision
        assert "returned_as" not in rule.binding
        assert gate == [(gate_route.INCREMENT_RULING_GATE, decision)]
        return
    assert (rule.binding["decision"], rule.binding["returned_as"]) == (
        "returned_for_revision",
        "goals_revised",
    )
    assert rule.binding["requested"] == decision
    assert "classification" not in rule.binding
    assert returned in rule.reason and rule.reason.startswith("goals_revised: ")
    assert gate == [(gate_route.INCREMENT_RULING_GATE, "returned_for_revision")]
    run = await world.cycles.get_run("run_prop")
    assert run.gate_decisions[0].notes == rule.reason
    assert state is CampaignState.AT_PROPOSAL


async def test_a_proposal_named_no_item_is_ruled_as_asked():
    """The edge: a Campaign with no goal set, whose submission names no item. Bug caught: the
    goal-set check raising for it (no goal set to read), so no ruling on it records."""
    world = gate_route._World()
    world.client.app.state.goal_set_registry = GoalSetStore()
    await world.campaigns.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await gate_route.at_the_gate(world)

    assert world.rule().status_code == 200
    assert await world.gate_decisions() == [(gate_route.INCREMENT_RULING_GATE, "approved")]
