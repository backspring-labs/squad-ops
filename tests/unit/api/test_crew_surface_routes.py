"""The crew's surface (SIP-0115 §5.7, §8.5; slice 5, #2888), entered at the routes the crew calls,
with the crew's real roles through the real authorization adapter: the goal set and backlog read
back, a gate's ledger row carries its item and expected results, and an assessment written by the
crew reads back.

The ledger is what a reviewer outside SquadOps reads at a gate (the crew's packet carries its rows
whole), so the gate tests read it there. The goal set is invented
(``tests/fixtures/goal_set.py``)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from squadops.api.routes.cycles.goal_sets import router as goal_sets_router
from squadops.auth.models import Role
from squadops.campaigns.goal_delegation import goal_delegation_transition
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.cycles.models import GateDecisionValue
from squadops.projects.goal_set_assessments import Assessment, AssessmentEvidence, Reading
from tests.fixtures.goal_set import (
    ACCEPTED_TREE,
    GoalSetStore,
    goal_set_document,
    proposed,
    started,
)
from tests.unit.api.test_campaign_repository_creation import _on, _Projects
from tests.unit.api.test_campaign_routes import _identity, _World
from tests.unit.campaigns.builders import move

pytestmark = pytest.mark.auth

CID = "cmp_api000000001"
GOAL_SET = "/api/v1/projects/prj-tally/goal-set"
CAMPAIGN = f"/api/v1/campaigns/{CID}"
OWNER = _identity(Role.ADMIN, user="the-owner")
SUPERVISOR = _identity(Role.CAMPAIGN_SUPERVISOR, user="crew-broker")
TRIAGE = _identity(Role.CAMPAIGN_TRIAGE, user="crew-evidence")
NO_SCOPE = _identity(user="a-stranger")
#: The ledger row's fields before slice 5: a requirements Campaign's rows are exactly these.
ROW_FIELDS = {
    "proposal_id", "version", "content_hash", "baseline_tree", "cycle_id", "run_id",
    "submitted_at", "ruling", "outcome", "classification", "cycles",
}  # fmt: skip
SIGNED = "buzz://campaigns/thread-7/statement-3"


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


def _store(world) -> GoalSetStore:
    return world.client.app.state.goal_set_registry


async def _on_goals(world, **fields) -> None:
    await started(world.campaigns, CID, project_id="prj-tally", **fields)


def _body(key: str = "a-1", **fields) -> dict:
    return {
        "idempotency_key": key,
        "campaign_id": CID,
        "expected_result": "ER-week",
        "goals_revision": 1,
        "log_seq": 0,
        "reading": "not_met",
        "cause": "framework_defect",
        "issue": 2901,
        "evidence": {
            "cycles": ["cyc_0a1b2c"],
            "rulings": ["ctl_7"],
            "evaluations": [{"id": "eval_3", "passed": 2, "failed": 1}],
        },
        "reason": "the total stays at zero because the framework dropped the route",
        "source_ref": SIGNED,
        **fields,
    }


def _assess(world, **fields):
    return world.client.post(f"{GOAL_SET}/assessments", json=_body(**fields))


def _cursor(world) -> int:
    """Where the crew's read stands: the view's ``log_seq``, read before its evidence."""
    return world.client.get(f"{CAMPAIGN}/assessments").json()["log_seq"]


def _written(**fields) -> Assessment:
    """An assessment as the store takes it, for a write landing inside another read."""
    values = {
        "project_id": "prj-tally", "campaign_id": CID, "expected_result": "ER-week",
        "goals_revision": 1, "reading": Reading.MET,
        "evidence": AssessmentEvidence(cycles=("cyc_0a1b2c",)), "reason": "the total shows",
        "author": "crew-broker", "created_at": datetime(2026, 11, 4, 9, 0, tzinfo=UTC),
    }  # fmt: skip
    return Assessment(**{**values, **fields})


def _code(resp) -> tuple[int, str]:
    return resp.status_code, resp.json()["detail"]["error"]["code"]


def _result(world, result_id: str = "ER-week") -> dict:
    body = world.client.get(f"{CAMPAIGN}/assessments").json()
    return next(r for r in body["results"] if r["expected_result"] == result_id)


async def _promoted(world, cycle: str) -> None:
    await world.campaigns.transition(
        CID,
        move(CampaignState.BUILDING, f"p:{cycle}", operation=ControlOperation.PROMOTE,
             target=cycle, accepted=AcceptedTree(ACCEPTED_TREE, cycle)),
    )  # fmt: skip


async def _completed(world) -> None:
    await world.campaigns.transition(
        CID,
        move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
             outcome=CampaignOutcome.ABORTED),
    )  # fmt: skip


async def test_the_crew_reads_the_goal_rules_against_it_and_assesses_it_end_to_end(world):
    """The slice's done-when, at the routes the crew calls (anti-pattern 6a). Bugs caught: a read
    route on a scope one of the crew's principals lacks; the gate's row reaching the reviewer
    without the item or the results; the crew's candidate refused, or its promotion working with
    no grant; an assessment that doesn't read back through the triage principal, or that writes a
    goal-set revision."""
    await _on_goals(world)
    await proposed(world.campaigns, CID, "B-2")

    for reader in (SUPERVISOR, TRIAGE):
        world.as_(reader)
        assert (
            world.client.get(GOAL_SET).json()["goal_set"]["expected_results"][0]["id"] == "ER-log"
        )
        backlog = world.client.get(f"{CAMPAIGN}/backlog").json()
        assert [(i["item_id"], i["status"]) for i in backlog["items"]] == [
            ("B-1", "pending"),
            ("B-2", "proposed"),
        ]
        [row] = world.client.get(f"{CAMPAIGN}/ledger").json()
        assert (row["backlog_item"], row["goals_revision"]) == ("B-2", 1)
        assert row["goal_evidence"] == {
            "goal": "A reader keeps a log of reading sessions and sees their weekly total",
            "item": {
                "id": "B-2",
                "title": "Weekly total",
                "description": "",
                "serves": ["ER-week"],
            },
            "expected_results": [
                {
                    "id": "ER-week",
                    "statement": "The week's total minutes are shown",
                    "surface": {"kind": "page", "ref": "/week"},
                }
            ],
        }

    world.as_(SUPERVISOR)
    added = world.client.post(
        f"{GOAL_SET}/candidates",
        json={
            "idempotency_key": "c-1", "expected_revision": 1, "reason": "found at the gate",
            "source_ref": SIGNED,
            "candidate": {"id": "C-2", "title": "Export the log", "found_by": "crew-broker"},
        },
    )  # fmt: skip
    assert added.status_code == 201, added.json()
    promotion = {
        "idempotency_key": "p-1", "expected_revision": 2, "reason": "it blocks the total",
        "serves": ["ER-week"], "campaign_id": CID,
    }  # fmt: skip
    promote = f"{GOAL_SET}/candidates/C-2/promote"
    assert _code(world.client.post(promote, json=promotion)) == (403, "NOT_DELEGATED")
    held = await world.campaigns.get_campaign(CID)
    await world.campaigns.transition(
        CID,
        goal_delegation_transition(
            held, actor="the-owner", actor_role="admin", reason="the owner approved it",
            idempotency_key="grant",
        ),
    )  # fmt: skip
    promoted = world.client.post(promote, json={**promotion, "idempotency_key": "p-2"})
    assert promoted.status_code == 201, promoted.json()
    assert promoted.json()["revision"]["change"]["campaign_id"] == CID

    written = _assess(world, goals_revision=3)
    assert written.status_code == 201, written.json()
    body = written.json()
    assert (body["replayed"], body["idempotency_key"]) == (False, "a-1")
    recorded = body["assessment"]
    assert (recorded["sequence"], recorded["author"], recorded["source_ref"]) == (
        1,
        "crew-broker",
        SIGNED,
    )
    assert (recorded["reading"], recorded["cause"], recorded["issue"]) == (
        "not_met",
        "framework_defect",
        2901,
    )
    assert len(_store(world).revisions["prj-tally"]) == 3

    world.as_(TRIAGE)
    assert world.client.get(f"{GOAL_SET}/assessments").json() == [recorded]
    view = world.client.get(f"{CAMPAIGN}/assessments").json()
    assert (view["campaign_id"], view["project_id"], view["revision"]) == (CID, "prj-tally", 3)
    last_row = (await world.campaigns.control_log(CID))[-1].seq
    assert view["log_seq"] == last_row
    assert {r["expected_result"]: r["standing"] for r in view["results"]} == {
        "ER-log": "unassessed",
        "ER-week": "current",
        "ER-calm": "unassessed",
    }
    assert _result(world)["assessments"] == [recorded]


@pytest.mark.parametrize(
    "path",
    [
        GOAL_SET,
        f"{GOAL_SET}/revisions",
        f"{GOAL_SET}/assessments",
        f"{CAMPAIGN}/backlog",
        f"{CAMPAIGN}/ledger",
        f"{CAMPAIGN}/assessments",
    ],
)
async def test_a_reader_without_the_scope_is_refused_each_read(world, path):
    """Bug caught: a route of the crew's surface left open to any authenticated token, when a goal
    set and what the crew concluded about it are the Project's."""
    await _on_goals(world)
    world.as_(NO_SCOPE)

    assert _code(world.client.get(path)) == (403, "FORBIDDEN")


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (Role.ADMIN, 201),
        (Role.CAMPAIGN_SUPERVISOR, 201),
        (Role.CAMPAIGN_TRIAGE, 403),
        (Role.OPERATOR, 403),
    ],
)
async def test_who_may_record_one_needs_no_grant(world, role, status):
    """§6's row. Bugs caught: an assessment gated on the owner's Campaign grant, which covers the
    order and not a report, so an ungranted crew can't report; triage, which reads and nothing
    else (#1719), or anyone else, writing one."""
    await _on_goals(world)
    world.as_(_identity(role, user="someone"))

    assert _assess(world).status_code == status


async def test_the_owner_may_record_one_with_no_statement_and_the_crew_may_not(world):
    """Q43: the crew's record is its signed statement, so a crew assessment with none is an
    unattributable claim. The owner's own word needs no link (§6: "where it came from a
    conversation"). Bug caught: either requirement applied to the other."""
    await _on_goals(world)
    world.as_(SUPERVISOR)
    refused = _assess(world, source_ref=None)
    assert _code(refused) == (422, "GOAL_SET_INVALID")
    assert refused.json()["detail"]["error"]["details"]["field"] == "source_ref"

    world.as_(OWNER)
    assert _assess(world, source_ref=None).status_code == 201


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"reading": "mostly"}, "reading"),
        ({"cause": "bad_luck"}, "cause"),
        ({"cause": None, "issue": None}, "cause"),
        ({"reading": "met", "issue": None}, "cause"),
        ({"reading": "unclear", "issue": None}, "cause"),
        ({"cause": "framework_gap", "issue": None}, "issue"),
        ({"cause": "app_work"}, "issue"),
        ({"cause": "needs_owner"}, "issue"),
        ({"issue": 0}, "issue"),
        ({"evidence": {}}, "evidence"),
        ({"evidence": {"cycles": []}}, "evidence"),
        ({"evidence": {"steps": ["open the page"]}}, "evidence"),
        ({"evidence": {"cycles": ["open the page and read 42"]}}, "evidence.cycles[0]"),
        (
            {"evidence": {"evaluations": [{"id": "e", "passed": 1, "failed": 0, "value": "x"}]}},
            "evidence.evaluations[0]",
        ),
        ({"evidence": {"evaluations": [{"id": "e", "passed": -1, "failed": 0}]}},
         "evidence.evaluations[0].passed"),
        ({"expected_result": "ER-nothing"}, "expected_result"),
        ({"goals_revision": 9}, "goals_revision"),
        ({"log_seq": 9999}, "log_seq"),
        ({"supersedes": [7]}, "supersedes"),
        ({"supersedes": [1, 1]}, "supersedes"),
    ],
)  # fmt: skip
async def test_a_bad_assessment_is_refused_naming_its_field_and_writes_nothing(
    world, fields, field
):
    """§5.7's vocabulary and what each reading requires, and §7: nothing in the evidence is free
    text, so a step or a value can't ride in as a citation. Bugs caught: a cause on a ``met``, or
    a shortfall with none, which the owner reads as a decision about whose work it is; a framework
    cause with no issue, or an issue on the squad's own work; an unknown result recorded, with
    nothing to attach to."""
    await _on_goals(world)
    world.as_(SUPERVISOR)

    resp = _assess(world, **fields)

    assert _code(resp) == (422, "GOAL_SET_INVALID")
    assert resp.json()["detail"]["error"]["details"]["field"] == field
    assert _store(world).assessments == {}


@pytest.mark.parametrize(
    "reading", [{"reading": "met"}, {"reading": "unclear"}, {"cause": "app_work"}],
    ids=["met", "unclear", "app_work"],
)  # fmt: skip
async def test_a_reading_with_no_shortfall_or_issue_is_recorded_without_them(world, reading):
    """The other side of the refusals. Bug caught: a rule written so tight that only a framework
    finding can be recorded, when ``met`` is the assessment rung 3 counts on."""
    await _on_goals(world)
    world.as_(SUPERVISOR)
    fields = {"cause": None, "issue": None, **reading}
    if reading.get("cause"):
        fields["reading"] = "not_met"

    resp = _assess(world, **fields)

    assert resp.status_code == 201, resp.json()
    assert resp.json()["assessment"]["issue"] is None


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("unknown", "CAMPAIGN_NOT_FOUND"),
        ("another Project's", "CAMPAIGN_NOT_FOUND"),
        ("requirements", "CAMPAIGN_HAS_NO_GOAL_SET"),
    ],
)
async def test_an_assessment_needs_a_goal_set_campaign_on_this_project(world, setup, code):
    """Bugs caught: an assessment recorded against a Campaign that doesn't exist or belongs to
    another Project, whose log it would then be read beside; or a requirements Campaign, which has
    no expected result to be about. None of them may answer 500 or write a row."""
    if setup == "another Project's":
        await started(world.campaigns, CID, project_id="prj-other")
    elif setup == "requirements":
        await started(world.campaigns, CID, project_id="prj-tally", goals=False)
    world.as_(SUPERVISOR)

    assert _code(_assess(world)) == (404, code)
    assert _store(world).assessments == {}


async def test_the_campaigns_view_is_refused_for_an_unknown_or_a_requirements_campaign(world):
    """Bug caught: a requirements Campaign reading an empty assessment list, which says it was
    assessed against nothing, rather than that it has no goal set."""
    world.as_(TRIAGE)
    assert _code(world.client.get(f"{CAMPAIGN}/assessments")) == (404, "CAMPAIGN_NOT_FOUND")

    await started(world.campaigns, CID, project_id="prj-tally", goals=False)
    assert _code(world.client.get(f"{CAMPAIGN}/assessments")) == (404, "CAMPAIGN_HAS_NO_GOAL_SET")


async def test_unknown_project_and_a_project_with_no_goal_set(world):
    """Bug caught: a 500 from reading a Project's assessments before it exists."""
    world.as_(TRIAGE)

    assert _code(world.client.get("/api/v1/projects/prj-none/goal-set/assessments"))[0] == 404
    assert world.client.get("/api/v1/projects/prj-other/goal-set/assessments").json() == []


async def test_a_retry_replays_after_the_campaign_closed_and_the_goal_set_moved_on(world):
    """Bugs caught: a retry writing a second assessment; a retry refused because the revision it
    read isn't the latest any more or its Campaign ended, when neither undoes the write; a key
    reused for another judgement treated as the same one."""
    await _on_goals(world)
    world.as_(SUPERVISOR)
    first = _assess(world)
    assert first.status_code == 201, first.json()

    await _completed(world)
    _store(world).write("prj-tally", goal_set_document())
    again = _assess(world)

    assert again.status_code == 201, again.json()
    assert (again.json()["replayed"], again.json()["assessment"]) == (
        True,
        first.json()["assessment"],
    )
    assert len(_store(world).assessments["prj-tally"]) == 1
    assert _code(_assess(world, reason="another judgement")) == (409, "IDEMPOTENCY_KEY_CONFLICT")


async def test_a_completed_campaign_takes_a_closing_assessment(world):
    """Bug caught: an assessment refused on a completed Campaign as a delegated act is, when the
    closing interpretation is what the crew writes last (§5.7, Q43)."""
    await _on_goals(world)
    await _completed(world)
    world.as_(SUPERVISOR)

    assert _assess(world).status_code == 201


async def test_a_later_acceptance_at_the_route_makes_it_stale_and_a_new_one_reads_current(world):
    """The position the crew read at and the acceptance the view reads, wired together. Bugs
    caught: the stated ``log_seq`` not reaching the store, so every acceptance reads later; the
    view reading no acceptance at all, so a judgement of the old tree reads current in the
    console."""
    await _on_goals(world)
    await proposed(world.campaigns, CID, "B-2", ruled=GateDecisionValue.APPROVED)
    world.as_(SUPERVISOR)
    assert _assess(world, key="a-1", log_seq=_cursor(world)).status_code == 201
    assert _result(world)["standing"] == "current"

    await _promoted(world, f"cyc_{CID[-4:]}_B-2")

    stale = _result(world)
    assert (stale["standing"], [a["sequence"] for a in stale["assessments"]]) == ("stale", [1])

    fresh_read = {"reading": "met", "cause": None, "issue": None, "log_seq": _cursor(world)}
    assert _assess(world, key="a-2", **fresh_read).status_code == 201
    fresh = _result(world)
    assert (fresh["standing"], [a["sequence"] for a in fresh["assessments"]]) == ("current", [2])


async def test_a_report_of_an_older_read_is_stale_however_late_it_is_written(world):
    """§5.7: an assessment is of what its author read. Bug caught: the position taken at the
    write, so the crew reads, an increment is accepted, the report lands, and a judgement of the
    tree before that increment reads current."""
    await _on_goals(world)
    await proposed(world.campaigns, CID, "B-2", ruled=GateDecisionValue.APPROVED)
    world.as_(SUPERVISOR)
    read_at = _cursor(world)

    await _promoted(world, f"cyc_{CID[-4:]}_B-2")
    assert _assess(world, log_seq=read_at).status_code == 201

    assert _result(world)["standing"] == "stale"


async def test_a_report_must_say_where_it_read(world):
    """Bug caught: a default position, which is the write-time reading back again by omission."""
    await _on_goals(world)
    world.as_(SUPERVISOR)
    body = _body()
    del body["log_seq"]

    assert world.client.post(f"{GOAL_SET}/assessments", json=body).status_code == 422
    assert _store(world).assessments == {}


async def test_a_view_read_during_a_revision_and_its_assessment_landing_still_answers(
    world, monkeypatch
):
    """Revisions read, then a new revision and an assessment naming it commit. Bug caught: reading
    the assessments after the revisions, so one names a revision the read doesn't hold, and the
    view answers 500 until the next read."""
    await _on_goals(world)
    store = _store(world)
    read_revisions = store.list_revisions
    landed = []

    async def then_a_write_lands(project_id):
        found = await read_revisions(project_id)
        if not landed:
            landed.append(True)
            store.write("prj-tally", goal_set_document())
            at = max(r.revision for r in await read_revisions(project_id))
            world.as_(SUPERVISOR)
            await store.record_assessment(
                _written(goals_revision=at), idempotency_key="mid-read", request_hash="h"
            )
        return found

    monkeypatch.setattr(store, "list_revisions", then_a_write_lands)
    world.as_(TRIAGE)

    assert world.client.get(f"{CAMPAIGN}/assessments").status_code == 200


async def test_a_pinned_campaigns_view_defines_each_result_at_the_revision_it_reads(world):
    """The view's text is what the console shows the reading against. Bug caught: the latest
    revision's statement on a pinned Campaign's result, a judgement of "minutes" read as "hours"."""
    changed = goal_set_document()
    changed["expected_results"][1]["statement"] = "The week's total hours are shown"
    _store(world).write("prj-tally", changed)
    await _on_goals(world, revision=1)
    world.as_(SUPERVISOR)

    assert _result(world)["statement"] == "The week's total minutes are shown"
    assert _result(world)["surface"] == {"kind": "page", "ref": "/week"}


async def test_a_conflict_reads_at_the_route_and_a_new_assessment_naming_both_ends_it(world):
    """§5.7. Bugs caught: ``supersedes`` dropped between the body and the store; an assessment
    superseding one of another Campaign or result accepted; the history losing what the view
    leaves out."""
    await _on_goals(world)
    world.as_(SUPERVISOR)
    assert _assess(world, key="a-1").status_code == 201
    world.as_(OWNER)
    assert _assess(world, key="a-2", reading="met", cause=None, issue=None).status_code == 201

    conflict = _result(world)
    assert conflict["standing"] == "conflicting"
    assert [a["author"] for a in conflict["assessments"]] == ["the-owner", "crew-broker"]

    elsewhere = _assess(world, key="a-3", expected_result="ER-log", supersedes=[1])
    assert elsewhere.json()["detail"]["error"]["details"]["field"] == "supersedes"

    ended = _assess(world, key="a-4", reading="met", cause=None, issue=None, supersedes=[1, 2])
    assert ended.status_code == 201, ended.json()
    assert (_result(world)["standing"], len(_result(world)["assessments"])) == ("current", 1)

    history = world.client.get(f"{GOAL_SET}/assessments", params={"expected_result": "ER-week"})
    assert [a["sequence"] for a in history.json()] == [1, 2, 3]


async def test_a_campaigns_view_reads_only_its_own_assessments(world):
    """§5.7: the latest is "in a Campaign", and a log position means nothing in another. Bug
    caught: the view reading the goal set's whole history, so another Campaign's judgement reads
    as this one's, and conflicts with it."""
    await _on_goals(world)
    await started(world.campaigns, "cmp_api000000002", project_id="prj-tally")
    world.as_(SUPERVISOR)
    assert _assess(world, key="a-1", campaign_id="cmp_api000000002").status_code == 201

    assert _result(world) == {
        "expected_result": "ER-week",
        "statement": "The week's total minutes are shown",
        "surface": {"kind": "page", "ref": "/week"},
        "standing": "unassessed",
        "assessments": [],
    }


async def test_the_history_pages_and_filters_before_the_page(world):
    """The lanes' rule (`api-route-lanes.md`, "Paging a list"). Bug caught: a filter applied after
    the page, so a Campaign's first assessments are hidden behind another's."""
    await _on_goals(world)
    await started(world.campaigns, "cmp_api000000002", project_id="prj-tally")
    world.as_(SUPERVISOR)
    assert _assess(world, key="a-1", campaign_id="cmp_api000000002").status_code == 201
    assert _assess(world, key="a-2").status_code == 201
    assert _assess(world, key="a-3", expected_result="ER-log").status_code == 201

    def sequences(**params):
        return [
            a["sequence"] for a in world.client.get(f"{GOAL_SET}/assessments", params=params).json()
        ]

    assert sequences(campaign_id=CID) == [2, 3]
    assert sequences(campaign_id=CID, limit=1) == [2]
    assert sequences(campaign_id=CID, limit=1, offset=1) == [3]
    assert sequences(campaign_id=CID, expected_result="ER-log") == [3]


# --- the gate's evidence (§8.5) ---


async def test_the_plan_gate_carries_it_too_and_a_decided_row_keeps_only_its_item(world):
    """Each plan and increment gate (§8.5). Bugs caught: the evidence on the increment gate only,
    so the plan gate's reviewer judges with no goal; or kept on every decided row, which spends a
    reviewer's bounded request on increments already judged."""
    await _on_goals(world)
    await proposed(world.campaigns, CID, "B-1", ruled=GateDecisionValue.APPROVED)
    world.as_(SUPERVISOR)

    [at_plan_gate] = world.client.get(f"{CAMPAIGN}/ledger").json()
    assert at_plan_gate["goal_evidence"]["item"]["id"] == "B-1"

    await _promoted(world, f"cyc_{CID[-4:]}_B-1")

    [decided] = world.client.get(f"{CAMPAIGN}/ledger").json()
    assert (decided["backlog_item"], decided["goals_revision"]) == ("B-1", 1)
    assert "goal_evidence" not in decided


async def test_the_gate_reads_the_revision_the_proposal_is_bound_to(world):
    """§5.5a: a later revision never changes how a running increment is judged. Bug caught: the
    evidence read at the latest revision, so the reviewer judges against a result the increment
    was never bound to."""
    await _on_goals(world)
    await proposed(world.campaigns, CID, "B-2", ruled=GateDecisionValue.APPROVED)
    revised = goal_set_document()
    revised["expected_results"][1]["statement"] = "The week's total hours are shown"
    _store(world).write("prj-tally", revised)
    world.as_(SUPERVISOR)

    [row] = world.client.get(f"{CAMPAIGN}/ledger").json()

    assert row["goals_revision"] == 1
    assert row["goal_evidence"]["expected_results"][0]["statement"] == (
        "The week's total minutes are shown"
    )


async def test_a_requirements_campaigns_row_is_exactly_as_it_was(world):
    """ "A requirements Campaign's packet is unchanged." Bug caught: the three fields reaching its
    rows as nulls, which the crew's packet carries and its bounded request pays for; or the
    ledger reading a goal set a requirements Campaign doesn't have."""
    world.as_(OWNER)
    assert _on(world, "prj-tally").status_code == 201
    registry = world.campaigns
    start = move(CampaignState.CALIBRATING, "s", operation=ControlOperation.START)
    await registry.transition(CID, start)
    await registry.transition(CID, move(CampaignState.AT_PROPOSAL, "d"))
    binding = ProposalBinding("prop_1", 1, "c", ACCEPTED_TREE)
    await registry.transition(
        CID,
        CampaignTransition(
            operation=ControlOperation.SUBMIT, actor="squadops", actor_role="executor",
            reason="at the gate", idempotency_key="submit:run_1",
            next_state=CampaignState.AWAITING_RULING, target="run_1",
            binding={
                "proposal_id": "prop_1", "version": 1, "content_hash": "c",
                "baseline_tree": ACCEPTED_TREE, "cycle_id": "cyc_1",
            },
            submitted=SubmittedProposal(binding, "cyc_1", "run_1"),
        ),
    )  # fmt: skip
    del _store(world).revisions["prj-tally"]

    [row] = world.client.get(f"{CAMPAIGN}/ledger").json()

    assert set(row) == ROW_FIELDS
