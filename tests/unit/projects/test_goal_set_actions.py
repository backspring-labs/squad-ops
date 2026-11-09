"""Slice 3's actions on a goal set (SIP-0115 §5.4, §5.5a, §6, Q41; #2886): the goal set's own
actions, and recording them as revisions under §6's rule for who may. The goal set is invented
(``tests/fixtures/goal_set.py``), never a held-out suite's."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.models import CampaignOutcome, CampaignState, ControlOperation
from squadops.cycles.models import (
    GateDecisionValue,
    GoalSetNotFoundError,
    Project,
    RegistrationKeyConflictError,
    StaleGoalSetRevisionError,
)
from squadops.projects.goal_set import (
    BacklogItemNotFound,
    CandidateNotFound,
    Change,
    ChangeKind,
    GoalSetInvalid,
    add_candidate,
    drop_candidate,
    parse_change,
    parse_goal_set,
    promote_candidate,
    split_item,
)
from squadops.projects.goal_set_actions import (
    ActionWrite,
    Actor,
    BacklogItemInProgress,
    NotDelegated,
    not_within,
    record_candidate,
    record_drop,
    record_promotion,
    record_split,
)
from tests.fixtures.goal_set import GoalSetStore, goal_set_document, proposed, started
from tests.unit.campaigns.builders import move

NOW = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
PROJECT = "prj-lantern"
OWNER = Actor("owner", owner=True)
OPERATOR = Actor("campaign-supervisor-principal", owner=False)


def _goal_set():
    return parse_goal_set(goal_set_document())


def _ids(goal_set) -> list[str]:
    return [i.id for i in goal_set.backlog]


class TestPromote:
    def test_a_promoted_candidate_keeps_its_id_and_is_appended_by_default(self):
        """§10a, Q41. Bugs caught: the candidate's id re-minted on promotion, so its history
        (its evidence, the cycle that found it) is lost; the candidate left in ``candidates``
        beside its item, which the goal set then refuses; the default put at the front."""
        promoted, at = promote_candidate(_goal_set(), "C-1", serves=["ER-week", "ER-log"])

        assert (_ids(promoted), at) == (["B-1", "B-2", "C-1"], 3)
        item = promoted.backlog[-1]
        assert (item.title, item.description, item.serves, item.size) == (
            "Edit a session",
            "Found when a typo could not be fixed",
            ("ER-week", "ER-log"),
            None,
        )
        assert promoted.candidates == ()

    @pytest.mark.parametrize(
        ("position", "order"),
        [(1, ["C-1", "B-1", "B-2"]), (2, ["B-1", "C-1", "B-2"]), (3, ["B-1", "B-2", "C-1"])],
    )
    def test_a_position_is_the_items_place_in_the_order_from_one(self, position, order):
        promoted, at = promote_candidate(_goal_set(), "C-1", serves=["ER-week"], position=position)

        assert (_ids(promoted), at) == (order, position)

    @pytest.mark.parametrize(
        ("candidate", "serves", "position", "error", "field"),
        [
            ("C-9", ["ER-week"], None, CandidateNotFound, None),
            ("C-1", [], None, GoalSetInvalid, "serves"),
            ("C-1", ["ER-gone"], None, GoalSetInvalid, "serves"),
            ("C-1", ["ER-week", "ER-week"], None, GoalSetInvalid, "serves"),
            ("C-1", ["ER-week"], 0, GoalSetInvalid, "position"),
            ("C-1", ["ER-week"], 4, GoalSetInvalid, "position"),
        ],
        ids=[
            "no such candidate",
            "serves nothing",
            "serves an unknown result",
            "serves a result twice",
            "position 0",
            "position past the end",
        ],
    )
    def test_a_promotion_is_refused_naming_what_is_wrong(
        self, candidate, serves, position, error, field
    ):
        """Bug caught: an item promoted serving nothing or an unknown result, which the goal set
        refuses on its next whole-document write, long after; a position past the end read as
        the end."""
        with pytest.raises(error) as e:
            promote_candidate(_goal_set(), candidate, serves=serves, position=position)
        if field is not None:
            assert e.value.field == field


class TestAddAndDrop:
    def test_a_candidate_is_added_at_the_end_and_found_at_the_write_when_it_says_no_time(self):
        """Bug caught: a candidate with no ``found_at`` refused, or stamped with a time the
        retry can't reproduce (the hash is over the request, so the store replays it)."""
        added = add_candidate(
            _goal_set(),
            {"id": "C-2", "title": "Delete a session", "found_by": "operator"},
            found_at=NOW,
        )
        kept = add_candidate(
            _goal_set(),
            {
                "id": "C-2",
                "title": "t",
                "found_by": "operator",
                "found_at": "2026-11-01T00:00:00+00:00",
            },
            found_at=NOW,
        )

        assert [c.id for c in added.candidates] == ["C-1", "C-2"]
        assert added.candidates[-1].found_at == NOW
        assert kept.candidates[-1].found_at == datetime(2026, 11, 1, tzinfo=UTC)

    @pytest.mark.parametrize(
        ("candidate", "field"),
        [
            ({"id": "B-1", "title": "t", "found_by": "operator"}, "candidates"),
            ({"id": "C-1", "title": "t", "found_by": "operator"}, "candidates"),
            (
                {"id": "C-2", "title": "t", "found_by": "operator", "serves": ["ER-log"]},
                "candidate",
            ),
            ({"id": "C-2", "title": "t"}, "candidate.found_by"),
        ],
        ids=["an item's id", "a candidate's id", "an unknown field", "no finder"],
    )
    def test_an_added_candidate_is_refused_naming_its_field(self, candidate, field):
        """Bug caught: a candidate sharing a backlog item's id (then promotion names two
        things), or a misspelt field silently dropped."""
        with pytest.raises(GoalSetInvalid) as e:
            add_candidate(_goal_set(), candidate, found_at=NOW)
        assert e.value.field == field

    def test_a_drop_removes_the_candidate_and_nothing_else(self):
        dropped = drop_candidate(_goal_set(), "C-1")

        assert dropped.candidates == ()
        assert dropped.backlog == _goal_set().backlog
        with pytest.raises(CandidateNotFound):
            drop_candidate(_goal_set(), "C-9")


class TestSplit:
    def test_the_parts_take_the_parents_place_in_order_and_inherit_what_it_served(self):
        """§5.5a. Bugs caught: the parts appended at the end rather than in the parent's place
        (which changes every later item's priority, the owner's); a part saying nothing of
        ``serves`` refused or left serving nothing; the parent kept beside its parts."""
        split = split_item(
            _goal_set(),
            "B-1",
            [
                {"id": "B-1a", "title": "Record a session's book"},
                {"id": "B-1b", "title": "Record its minutes", "serves": ["ER-week"], "size": "s"},
            ],
        )

        assert _ids(split) == ["B-1a", "B-1b", "B-2"]
        assert [i.serves for i in split.backlog[:2]] == [("ER-log",), ("ER-week",)]
        assert split.backlog[1].size == "s"
        assert split.candidates == _goal_set().candidates

    @pytest.mark.parametrize(
        ("item", "into", "error", "field"),
        [
            (
                "B-9",
                [{"id": "a", "title": "t"}, {"id": "b", "title": "t"}],
                BacklogItemNotFound,
                None,
            ),
            ("B-1", [{"id": "a", "title": "t"}], GoalSetInvalid, "into"),
            ("B-1", {"id": "a", "title": "t"}, GoalSetInvalid, "into"),
            ("B-1", [{"id": "a", "title": "t"}, {"id": "a", "title": "u"}], GoalSetInvalid, "into"),
            (
                "B-1",
                [{"id": "a", "title": "t"}, {"id": "B-2", "title": "u"}],
                GoalSetInvalid,
                "into",
            ),
            (
                "B-1",
                [{"id": "a", "title": "t"}, {"id": "B-1", "title": "u"}],
                GoalSetInvalid,
                "into",
            ),
            (
                "B-1",
                [{"id": "a", "title": "t"}, {"id": "C-1", "title": "u"}],
                GoalSetInvalid,
                "into",
            ),
            (
                "B-1",
                [{"id": "a", "title": "t"}, {"id": "b", "title": "u", "serves": ["ER-gone"]}],
                GoalSetInvalid,
                "into[1].serves",
            ),
            ("B-1", [{"id": "a", "title": "t"}, {"id": "b"}], GoalSetInvalid, "into[1].title"),
        ],
        ids=[
            "no such item",
            "one part",
            "not a list",
            "two parts with one id",
            "a part with another item's id",
            "a part with the parent's id",
            "a part with a candidate's id",
            "a part serving an unknown result",
            "a part with no title",
        ],
    )
    def test_a_split_is_refused_naming_what_is_wrong(self, item, into, error, field):
        """Bugs caught: a one-part split that renames an item and reads as a split; a part
        reusing the parent's id, so the view reads the parent as still present rather than
        ``removed`` with its parts; a part's unknown result caught only by the next whole write."""
        with pytest.raises(error) as e:
            split_item(_goal_set(), item, into)
        if field is not None:
            assert e.value.field == field


class TestChange:
    def test_a_change_reads_back_from_its_document_and_refuses_an_unknown_kind(self):
        """Bug caught: a field lost in the store's round trip (``split_into``, the Campaign), so
        the view can't tell a split from a removal; a misspelt kind read as an edit."""
        change = Change(
            ChangeKind.ITEM_SPLIT, "B-1", split_into=("B-1a", "B-1b"), campaign_id="cmp_1"
        )
        assert parse_change(change.to_document()) == change
        assert parse_change({"kind": "candidate_dropped", "subject": "C-1"}) == Change(
            ChangeKind.CANDIDATE_DROPPED, "C-1"
        )
        with pytest.raises(GoalSetInvalid, match="change.kind"):
            parse_change({"kind": "candidate_promotd", "subject": "C-1"})


# --- recording an action (who may, Q41; the live check, §5.5a; the store's rules) ---


@pytest.fixture
def projects():
    registry = AsyncMock()
    registry.get_project.return_value = Project(
        project_id=PROJECT, name="Lantern", description="", created_at=NOW
    )
    return registry


@pytest.fixture
def goal_sets():
    store = GoalSetStore()
    store.write(PROJECT, goal_set_document())
    return store


@pytest.fixture
def campaigns():
    return MemoryCampaignRegistry()


def _write(actor: Actor, *, campaign_id: str | None = None, key: str = "k-1", **changes):
    values = dict(
        actor=actor,
        expected_revision=1,
        reason="the operator found it blocks the weekly total",
        idempotency_key=key,
        source_ref="https://chat.example.invalid/thread/7",
        campaign_id=campaign_id,
        now=NOW,
    )
    values.update(changes)
    return ActionWrite(**values)


@pytest.mark.parametrize(
    ("actor", "project_id", "goals", "created_by", "grant", "completed", "refused"),
    [
        (OPERATOR, PROJECT, True, "owner", True, False, None),
        (OPERATOR, PROJECT, True, OPERATOR.principal, True, False, None),
        (OPERATOR, PROJECT, True, OPERATOR.principal, False, False, "the owner hasn't granted"),
        (OPERATOR, PROJECT, True, "owner", False, False, "the owner hasn't granted"),
        (OWNER, PROJECT, True, "owner", False, False, None),
        (OPERATOR, "prj-other", True, "owner", True, False, "is on Project prj-other"),
        (OWNER, "prj-other", True, "owner", False, False, "is on Project prj-other"),
        (OPERATOR, PROJECT, False, "owner", False, False, "names no goal set"),
        (OPERATOR, PROJECT, True, "owner", True, True, "has completed (aborted)"),
        (OWNER, PROJECT, True, "owner", False, True, "has completed (aborted)"),
    ],
    ids=[
        "the operator, granted, on the owner's Campaign",
        "the operator, granted, on its broker's Campaign",
        "the operator on a Campaign it created, no grant",
        "the operator on the owner's Campaign, no grant",
        "the owner needs no grant",
        "the operator, granted, on another Project's Campaign",
        "the owner naming another Project's Campaign",
        "a requirements Campaign",
        "the operator, granted, on a completed Campaign",
        "the owner naming a completed Campaign",
    ],
)
async def test_who_may_act_within_a_campaign(
    actor, project_id, goals, created_by, grant, completed, refused, campaigns
):
    """Q41 as the owner ruled it on 2026-11-04 (§10c). Bugs caught: the operator acting within a
    Campaign it created for itself with no grant, the defect the owner's review of PR #2908 found;
    a Campaign the owner created read as a grant; the operator refused on its broker's Campaign once
    granted; the owner asked for a grant; a grant carrying across Projects, or past the
    Campaign's life."""
    await started(
        campaigns, "cmp_1", created_by=created_by, granted=grant, project_id=project_id, goals=goals
    )
    if completed:
        await campaigns.transition(
            "cmp_1",
            move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
                 outcome=CampaignOutcome.ABORTED),
        )  # fmt: skip

    reason = not_within(
        await campaigns.get_campaign("cmp_1"),
        project_id=PROJECT,
        actor=actor,
        log=await campaigns.control_log("cmp_1"),
    )

    if refused is None:
        assert reason is None
    else:
        assert reason is not None and refused in reason


class TestRecordPromotion:
    async def test_the_owner_needs_no_campaign_and_the_revision_names_the_action(
        self, projects, goal_sets, campaigns
    ):
        """Bugs caught: the owner asked for a Campaign; the revision written with no ``change``,
        so the history reads the promotion as an edit; the author not the acting principal."""
        written, replayed = await record_promotion(
            PROJECT,
            "C-1",
            serves=["ER-week"],
            position=1,
            write=_write(OWNER),
            projects=projects,
            goal_sets=goal_sets,
            campaigns=campaigns,
        )

        assert (written.revision, written.author, replayed) == (2, "owner", False)
        assert written.change == Change(ChangeKind.CANDIDATE_PROMOTED, "C-1", position=1)
        assert (written.reason, written.source_ref) == (
            "the operator found it blocks the weekly total",
            "https://chat.example.invalid/thread/7",
        )
        assert _ids(written.goal_set) == ["C-1", "B-1", "B-2"]
        assert await goal_sets.get_revision(PROJECT) == written

    async def test_the_operator_promotes_within_the_owners_campaign_and_only_appends(
        self, projects, goal_sets, campaigns
    ):
        """Q41. Bugs caught: the operator promoting with no Campaign named; or putting the item
        anywhere but the end, which reorders the owner's backlog; the Campaign not recorded."""
        await started(campaigns, "cmp_owner", created_by="owner", granted=True)

        with pytest.raises(NotDelegated, match="name campaign_id"):
            await record_promotion(
                PROJECT, "C-1", serves=["ER-week"], position=None, write=_write(OPERATOR),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip
        with pytest.raises(NotDelegated, match="position 1 is a reorder"):
            await record_promotion(
                PROJECT, "C-1", serves=["ER-week"], position=1,
                write=_write(OPERATOR, campaign_id="cmp_owner"),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip
        written, _ = await record_promotion(
            PROJECT, "C-1", serves=["ER-week"], position=3,
            write=_write(OPERATOR, campaign_id="cmp_owner"),
            projects=projects, goal_sets=goal_sets, campaigns=campaigns,
        )  # fmt: skip

        assert written.author == "campaign-supervisor-principal"
        assert written.change == Change(
            ChangeKind.CANDIDATE_PROMOTED, "C-1", position=3, campaign_id="cmp_owner"
        )
        assert _ids(written.goal_set) == ["B-1", "B-2", "C-1"]

    async def test_a_grant_lets_the_operator_act_within_its_own_campaign_for_that_campaigns_life(
        self, projects, goal_sets, campaigns
    ):
        """§10c: the grant lasts the Campaign's life. Bugs caught: the operator's broker's own
        Campaign refused once granted (the operator locked out of every Campaign it runs); a
        completed Campaign still delegating, so the operator curates the backlog with no Campaign
        running."""
        await started(
            campaigns, "cmp_operator", created_by="campaign-supervisor-principal", granted=True
        )
        await started(campaigns, "cmp_done", created_by="owner", granted=True)
        await campaigns.transition(
            "cmp_done",
            move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
                 outcome=CampaignOutcome.ABORTED),
        )  # fmt: skip

        with pytest.raises(NotDelegated, match="cmp_done has completed \\(aborted\\)"):
            await record_drop(
                PROJECT, "C-1", write=_write(OPERATOR, campaign_id="cmp_done"),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip
        assert (await goal_sets.get_revision(PROJECT)).revision == 1
        written, _ = await record_drop(
            PROJECT, "C-1", write=_write(OPERATOR, campaign_id="cmp_operator"),
            projects=projects, goal_sets=goal_sets, campaigns=campaigns,
        )  # fmt: skip

        assert (written.revision, written.author) == (2, "campaign-supervisor-principal")
        assert written.change == Change(
            ChangeKind.CANDIDATE_DROPPED, "C-1", campaign_id="cmp_operator"
        )

    async def test_a_retry_replays_and_the_same_key_with_another_request_conflicts(
        self, projects, goal_sets, campaigns
    ):
        """Bug caught: the action recomputed against the latest revision on a retry (the one it
        just wrote), so the retry is refused as stale or as a key conflict rather than replayed
        (the second review of PR #2899, P2)."""
        first, _ = await record_promotion(
            PROJECT, "C-1", serves=["ER-week"], position=None, write=_write(OWNER),
            projects=projects, goal_sets=goal_sets, campaigns=campaigns,
        )  # fmt: skip
        again, replayed = await record_promotion(
            PROJECT, "C-1", serves=["ER-week"], position=None, write=_write(OWNER),
            projects=projects, goal_sets=goal_sets, campaigns=campaigns,
        )  # fmt: skip

        assert (again, replayed) == (first, True)
        assert len(goal_sets.revisions[PROJECT]) == 2
        with pytest.raises(RegistrationKeyConflictError):
            await record_promotion(
                PROJECT, "C-1", serves=["ER-log"], position=None, write=_write(OWNER),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip

    @pytest.mark.parametrize("action", ["promote", "drop", "split"])
    async def test_a_retry_replays_though_its_campaign_has_since_completed(
        self, action, projects, goal_sets, campaigns
    ):
        """The retry contract outlives the Campaign (the review of PR #2908). Bug caught: the
        delegated act committed, its response was lost, the Campaign completed, and the retry was
        refused 403 at the eligibility check, so the operator reads a write that happened as refused.
        A new key on the same Campaign is still refused."""
        await started(campaigns, "cmp_1", created_by="owner", granted=True)
        stores = dict(projects=projects, goal_sets=goal_sets, campaigns=campaigns)
        into = [{"id": "B-1a", "title": "the book"}, {"id": "B-1b", "title": "the minutes"}]

        def act(write):
            if action == "promote":
                return record_promotion(
                    PROJECT, "C-1", serves=["ER-week"], position=None, write=write, **stores
                )
            if action == "drop":
                return record_drop(PROJECT, "C-1", write=write, **stores)
            return record_split(PROJECT, "B-1", into, write=write, **stores)

        first, _ = await act(_write(OPERATOR, campaign_id="cmp_1"))
        await campaigns.transition(
            "cmp_1",
            move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
                 outcome=CampaignOutcome.ABORTED),
        )  # fmt: skip

        again, replayed = await act(_write(OPERATOR, campaign_id="cmp_1"))

        assert (again, replayed) == (first, True)
        assert len(goal_sets.revisions[PROJECT]) == 2
        with pytest.raises(NotDelegated, match="has completed"):
            await act(_write(OPERATOR, campaign_id="cmp_1", key="k-2", expected_revision=2))

    @pytest.mark.parametrize(
        ("expected_revision", "error"),
        [(0, GoalSetNotFoundError), (2, GoalSetNotFoundError), (1, StaleGoalSetRevisionError)],
        ids=["no goal set yet", "a revision not written", "a revision another writer passed"],
    )
    async def test_an_action_against_the_wrong_revision_is_refused(
        self, expected_revision, error, projects, goal_sets, campaigns
    ):
        """Bug caught: an action against revision 1 written over a revision 2 someone else wrote
        since, dropping their change."""
        if error is StaleGoalSetRevisionError:
            goal_sets.write(PROJECT, goal_set_document())

        with pytest.raises(error):
            await record_drop(
                PROJECT, "C-1", write=_write(OWNER, expected_revision=expected_revision),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip


class TestRecordCandidate:
    async def test_the_operator_adds_a_candidate_with_no_campaign_and_a_retry_keeps_its_time(
        self, projects, goal_sets
    ):
        """§6: adding needs no delegation. Bugs caught: the operator refused; the second write of a
        retried request minting a new ``found_at``, so it is refused as a key conflict."""
        candidate = {"id": "C-2", "title": "Delete a session", "found_by": "operator"}
        first, _ = await record_candidate(
            PROJECT, candidate, _write(OPERATOR), projects=projects, goal_sets=goal_sets
        )
        again, replayed = await record_candidate(
            PROJECT, candidate, _write(OPERATOR, now=NOW.replace(hour=10)),
            projects=projects, goal_sets=goal_sets,
        )  # fmt: skip

        assert first.change == Change(ChangeKind.CANDIDATE_ADDED, "C-2")
        assert first.goal_set.candidates[-1].found_at == NOW
        assert (again, replayed) == (first, True)


class TestRecordSplit:
    @pytest.mark.parametrize(
        ("history", "refused"),
        [
            ("never proposed", False),
            ("proposed", True),
            ("in_increment", True),
            ("proposed then returned", False),
            ("proposed in a completed campaign", False),
            ("in a requirements campaign", False),
        ],
    )
    async def test_a_split_waits_while_a_live_campaign_has_the_item_proposed_or_building(
        self, history, refused, projects, goal_sets, campaigns
    ):
        """§5.5a. Bugs caught: an item split while its increment builds, so its acceptance is
        credited to an item that is gone (not ``accepted (removed in rN)``: the split's parts are
        new items); a returned proposal, or a completed Campaign's, still holding the split."""
        if history != "never proposed":
            await started(
                campaigns,
                "cmp_1",
                created_by="owner",
                goals=history != "in a requirements campaign",
            )
        if history in ("proposed", "proposed in a completed campaign"):
            await proposed(campaigns, "cmp_1", "B-1")
        if history == "in_increment":
            await proposed(campaigns, "cmp_1", "B-1", ruled=GateDecisionValue.APPROVED)
        if history == "proposed then returned":
            await proposed(campaigns, "cmp_1", "B-1", ruled=GateDecisionValue.RETURNED_FOR_REVISION)
        if history == "proposed in a completed campaign":
            await campaigns.transition(
                "cmp_1",
                move(CampaignState.COMPLETED, "end", operation=ControlOperation.ABORT,
                     outcome=CampaignOutcome.ABORTED),
            )  # fmt: skip
        into = [{"id": "B-1a", "title": "the book"}, {"id": "B-1b", "title": "the minutes"}]

        if refused:
            with pytest.raises(BacklogItemInProgress, match=f"B-1 is {history} in campaign cmp_1"):
                await record_split(
                    PROJECT, "B-1", into, write=_write(OWNER),
                    projects=projects, goal_sets=goal_sets, campaigns=campaigns,
                )  # fmt: skip
            assert (await goal_sets.get_revision(PROJECT)).revision == 1
        else:
            written, _ = await record_split(
                PROJECT, "B-1", into, write=_write(OWNER),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip
            assert written.change == Change(
                ChangeKind.ITEM_SPLIT, "B-1", split_into=("B-1a", "B-1b")
            )
            assert _ids(written.goal_set) == ["B-1a", "B-1b", "B-2"]

    async def test_a_proposal_arriving_during_a_split_lands_after_its_revision(
        self, projects, goal_sets, campaigns
    ):
        """§5.5a across the two stores (the review of PR #2908). Bug caught: the guard read the
        Campaign's log and the revision was written separately, so a proposal submitted between
        them read ``proposed`` on an item the split had just removed, and nothing would tell the
        ruling. Held, the submission waits; once it lands the item is gone, which is what
        ``goals_revised`` returns it for."""
        await started(campaigns, "cmp_1", created_by="owner", granted=True)
        into = [{"id": "B-1a", "title": "the book"}, {"id": "B-1b", "title": "the minutes"}]
        written = goal_sets.record_revision
        submission: list[asyncio.Task] = []

        async def racing(revision, **kwargs):
            submission.append(asyncio.create_task(proposed(campaigns, "cmp_1", "B-1")))
            for _ in range(20):
                await asyncio.sleep(0)
            assert not submission[0].done()
            assert [e.operation for e in await campaigns.control_log("cmp_1")][-1] != (
                ControlOperation.SUBMIT
            )
            return await written(revision, **kwargs)

        goal_sets.record_revision = racing
        revision, _ = await record_split(
            PROJECT, "B-1", into, write=_write(OWNER),
            projects=projects, goal_sets=goal_sets, campaigns=campaigns,
        )  # fmt: skip
        await submission[0]

        assert _ids(revision.goal_set) == ["B-1a", "B-1b", "B-2"]
        assert [e.operation for e in await campaigns.control_log("cmp_1")][-1] is (
            ControlOperation.SUBMIT
        )

    async def test_the_operator_splits_within_the_owners_campaign_and_the_revision_names_it(
        self, projects, goal_sets, campaigns
    ):
        await started(campaigns, "cmp_owner", created_by="owner", granted=True)
        into = [{"id": "B-1a", "title": "the book"}, {"id": "B-1b", "title": "the minutes"}]

        with pytest.raises(NotDelegated):
            await record_split(
                PROJECT, "B-1", into, write=_write(OPERATOR),
                projects=projects, goal_sets=goal_sets, campaigns=campaigns,
            )  # fmt: skip
        written, _ = await record_split(
            PROJECT, "B-1", into, write=_write(OPERATOR, campaign_id="cmp_owner"),
            projects=projects, goal_sets=goal_sets, campaigns=campaigns,
        )  # fmt: skip

        assert written.author == "campaign-supervisor-principal"
        assert written.change is not None and written.change.campaign_id == "cmp_owner"
