"""A goal set's backlog as one Campaign stands on it (SIP-0115 §4, §5.3, §5.5a; SIP-0109 §24cy).

The view is derived from the control log alone, so each test writes the rows a Campaign writes
(``submit``, ``rule``, ``decide``, ``promote``, ``resume``, ``abort``, ``branch_rebased``) and reads
the statuses back. The goal set is invented (``tests/fixtures/goal_set.py``), never a held-out
suite's.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import pytest

from squadops.campaigns.backlog import ItemStatus, backlog_view, goals_revised
from squadops.campaigns.models import (
    CampaignState,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
    LaunchIntentState,
)
from squadops.projects.goal_set import Change, ChangeKind, GoalSetRevision, parse_goal_set
from tests.fixtures.goal_set import goal_set_document

T0 = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)


def _document(**changes) -> dict:
    doc = goal_set_document()
    doc["backlog"].append({"id": "B-3", "title": "Monthly total", "serves": ["ER-week"]})
    for key, value in changes.items():
        doc[key] = value
    return doc


def _revision(n: int, doc: dict | None = None) -> GoalSetRevision:
    return GoalSetRevision(
        project_id="prj-lantern",
        revision=n,
        goal_set=parse_goal_set(doc or _document()),
        author="owner",
        reason=f"r{n}",
        created_at=T0,
    )


class _Log:
    """Rows as the registry writes them, in order."""

    def __init__(self) -> None:
        self.rows: list[ControlLogEntry] = []
        self.launches: list[LaunchIntent] = []

    def _row(self, operation, *, target=None, binding=None, actor="squadops", reason="r"):
        seq = len(self.rows) + 1
        self.rows.append(
            ControlLogEntry(
                entry_id=f"ctl_{seq}", campaign_id="cmp_b", seq=seq, operation=operation,
                actor=actor, actor_role="r", reason=reason, target=target,
                idempotency_key=f"k{seq}", request_hash="h", binding=binding or {},
                outcome=ControlOutcome.APPLIED, refusal=None, prior_state=None,
                next_state=CampaignState.AT_PROPOSAL, committed_at=T0 + timedelta(minutes=seq),
            )
        )  # fmt: skip
        return self

    def submit(self, item, cycle, *, proposal=None, version=1, revision=1):
        return self._row(
            ControlOperation.SUBMIT,
            target=f"run_{cycle}_{version}",
            binding={
                "proposal_id": proposal or f"prop_{cycle}", "version": version,
                "content_hash": "c", "baseline_tree": "t", "cycle_id": cycle,
                "backlog_item": item, "goals_revision": revision,
            },
        )  # fmt: skip

    def rule(self, decision, cycle, *, version=1):
        return self._row(
            ControlOperation.RULE,
            target=f"run_{cycle}_{version}",
            binding={"decision": decision, "proposal_id": f"prop_{cycle}", "version": version},
        )

    def decide(self, cycle, row, **binding):
        return self._row(
            ControlOperation.DECIDE,
            target=cycle,
            binding={"cycle_id": cycle, "row": row, **binding},
        )

    def promote(self, cycle):
        return self._row(ControlOperation.PROMOTE, target=cycle, binding={"cycle_id": cycle})

    def resume(self, action, reason="the owner's word"):
        return self._row(
            ControlOperation.RESUME, binding={"action": action}, actor="owner", reason=reason
        )

    def abort(self):
        return self._row(ControlOperation.ABORT, actor="owner", reason="stopping here")

    def launch(self, kind, cycle, proposal_cycle, launch_id=None):
        self.launches.append(
            LaunchIntent(
                launch_id=launch_id or f"lnc_{cycle}", campaign_id="cmp_b",
                decision_entry_id="d", cycle_kind=kind,
                cycle_request={"body": {"execution_overrides": {"campaign_proposal": {
                    "proposal_id": f"prop_{proposal_cycle}", "version": 1}}}},
                state=LaunchIntentState.LAUNCHED if cycle else LaunchIntentState.SUPERSEDED,
                created_at=T0 + timedelta(minutes=len(self.launches)), cycle_id=cycle,
            )
        )  # fmt: skip
        return self


def _statuses(view) -> dict[str, str]:
    return {i.item_id: i.label for i in view.items}


def _approved(log: _Log, item: str, cycle: str) -> _Log:
    return log.submit(item, cycle).rule("approved", cycle)


@pytest.mark.parametrize(
    ("history", "statuses", "next_item"),
    [
        (lambda log: log, ["pending", "pending", "pending"], "B-1"),
        (lambda log: log.submit("B-1", "c1"), ["proposed", "pending", "pending"], "B-2"),
        (lambda log: _approved(log, "B-1", "c1"), ["in_increment", "pending", "pending"], "B-2"),
        (
            lambda log: _approved(log, "B-1", "c1").promote("c1").decide("c1", 7, action="propose"),
            ["accepted", "pending", "pending"],
            "B-2",
        ),
        (
            lambda log: log.submit("B-1", "c1").rule("rejected", "c1"),
            ["pending", "pending", "pending"],
            "B-1",
        ),
        (
            lambda log: log.submit("B-1", "c1").rule("returned_for_revision", "c1"),
            ["pending", "pending", "pending"],
            "B-1",
        ),
        (
            lambda log: _approved(log, "B-1", "c1").decide(
                "c1", 13, action="abandon_and_propose", ending="assessed", verdict="rejected"
            ),
            ["abandoned", "pending", "pending"],
            "B-2",
        ),
        (
            lambda log: (
                _approved(log, "B-1", "c1")
                .decide("c1", 12, action="repair")
                .launch(CycleKind.REPAIR, "c1r", "c1")
                .promote("c1r")
            ),
            ["accepted", "pending", "pending"],
            "B-2",
        ),
        (
            lambda log: (
                _approved(log, "B-1", "c1")
                .decide("c1", 9, action="escalate")
                .resume("abandon_and_propose")
            ),
            ["abandoned", "pending", "pending"],
            "B-2",
        ),
        (
            lambda log: (
                _approved(log, "B-1", "c1").decide("c1", 9, action="escalate").resume("propose")
            ),
            ["pending", "pending", "pending"],
            "B-1",
        ),
        (
            lambda log: (
                _approved(log, "B-1", "c1").decide("c1", 9, action="escalate").resume("repair")
            ),
            ["in_increment", "pending", "pending"],
            "B-2",
        ),
        (
            lambda log: _approved(log, "B-1", "c1").abort(),
            ["abandoned", "pending", "pending"],
            "B-2",
        ),
        (
            lambda log: (
                _approved(log, "B-1", "c1")
                .promote("c1")
                .decide("c1", 7, action="propose")
                .submit("B-2", "c2")
                .rule("approved", "c2")
                .decide("c2", 13, action="abandon_and_propose")
                .submit("B-3", "c3")
                .rule("approved", "c3")
                .promote("c3")
            ),
            ["accepted", "abandoned", "accepted"],
            None,
        ),
    ],
    ids=[
        "nothing proposed",
        "proposed, not ruled",
        "approved and building",
        "accepted",
        "rejected",
        "returned for revision",
        "abandoned at row 13",
        "accepted by its repair",
        "abandoned by the owner's word",
        "the owner proposes afresh instead",
        "the owner repairs it",
        "the campaign aborted mid-increment",
        "abandoned then skipped",
    ],
)
def test_each_items_status_is_read_from_the_control_log(history, statuses, next_item):
    """§4's statuses, each from the rows that make it. Bugs caught: a rejection or a return read
    as a live proposal, so the next proposal skips the item it should retry; a repair's promotion
    not credited to the increment it continues (read by its launch's binding); an abandoned item
    still eligible, so one stuck item holds the Campaign (§5.3); or an owner's word (an
    abandonment, or a fresh proposal in its place) or an abort leaving the item ``in_increment``
    forever."""
    log = history(_Log())

    view = backlog_view([_revision(1)], 1, log.rows, log.launches)

    assert list(_statuses(view).values()) == statuses
    assert (view.next_item.item_id if view.next_item else None) == next_item


def test_an_abandoned_item_names_its_row_and_reason():
    """The view says why (§4: "with the row and reason"). Bug caught: an abandoned item the
    proposer is shown with nothing saying what went wrong, so it can't avoid it."""
    log = _approved(_Log(), "B-1", "c1").decide(
        "c1", 13, action="abandon_and_propose", ending="assessed", verdict="rejected"
    )

    [b1, *_] = backlog_view([_revision(1)], 1, log.rows, log.launches).items

    assert (b1.status, b1.row) == (ItemStatus.ABANDONED, 13)
    assert b1.reason == "§10 row 13: its increment was abandoned (assessed, rejected)"


def test_an_item_the_campaign_ended_on_names_the_rows_cause():
    """A terminal decision's cause reaches the reason. Bug caught (#2911): the ledger's decision
    projection dropped ``cause``, so an item a Campaign failed on read "§10 row 4 (None)" and
    nobody could tell which limit ended it."""
    log = _approved(_Log(), "B-1", "c1").decide(
        "c1", 4, outcome="failure", cause="unaccepted_increments", verdict="rejected"
    )

    [b1, *_] = backlog_view([_revision(1)], 1, log.rows, log.launches).items

    assert (b1.status, b1.row) == (ItemStatus.ABANDONED, 4)
    assert b1.reason == (
        "the campaign ended at §10 row 4 (unaccepted_increments) with its increment unaccepted"
    )


def _without(item_id: str) -> dict:
    doc = _document()
    doc["backlog"] = [b for b in doc["backlog"] if b["id"] != item_id]
    return doc


def _edited(item_id: str, **fields) -> dict:
    doc = _document()
    for b in doc["backlog"]:
        if b["id"] == item_id:
            b.update(fields)
    return doc


def _reordered() -> dict:
    doc = _document()
    doc["backlog"] = list(reversed(doc["backlog"]))
    return doc


def _result_changed() -> dict:
    doc = _document()
    doc["expected_results"][0]["statement"] = (
        "A session is recorded with its book, minutes and date"
    )
    return doc


_ACCEPTED_B1 = lambda log: _approved(log, "B-1", "c1").promote("c1")  # noqa: E731
_ABANDONED_B1 = lambda log: _approved(log, "B-1", "c1").decide(  # noqa: E731
    "c1", 13, action="abandon_and_propose"
)


@pytest.mark.parametrize(
    ("history", "r2", "b1", "next_item"),
    [
        (_ACCEPTED_B1, _without("B-1"), "accepted (removed in r2)", "B-2"),
        (_ACCEPTED_B1, _result_changed(), "accepted (results changed in r2)", "B-2"),
        (_ACCEPTED_B1, _reordered(), "accepted", "B-3"),
        (_ABANDONED_B1, _without("B-1"), "removed", "B-2"),
        (
            _ABANDONED_B1,
            _edited("B-1", description="Record the book by its title"),
            "pending",
            "B-1",
        ),
        (_ABANDONED_B1, _reordered(), "abandoned", "B-3"),
    ],
    ids=[
        "accepted then removed",
        "accepted then its result changed",
        "accepted then moved",
        "abandoned then removed",
        "abandoned then re-queued by an edit",
        "abandoned then only moved",
    ],
)
def test_a_later_revision_reads_against_what_the_campaign_did(history, r2, b1, next_item):
    """§5.5a. Bugs caught: an accepted item reopened by a revision that dropped it or changed its
    results (only a new item or an assessment reopens that question); a removed item that was
    abandoned shown as still abandoned, or vanished with its history; an abandoned item never
    eligible again however the owner edits it, or re-queued by a mere reorder."""
    log = history(_Log())
    revisions = [_revision(1), _revision(2, r2)]

    view = backlog_view(revisions, 2, log.rows, log.launches)

    assert _statuses(view)["B-1"] == b1
    assert view.next_item is not None and view.next_item.item_id == next_item


def _split_b1() -> dict:
    """r2: B-1 split into B-1a and B-1b, which take its place (§5.5a)."""
    doc = _document()
    doc["backlog"][0:1] = [
        {"id": "B-1a", "title": "Record a session's book", "serves": ["ER-log"]},
        {"id": "B-1b", "title": "Record its minutes", "serves": ["ER-log"]},
    ]
    return doc


@pytest.mark.parametrize(
    ("r2", "change", "split_into"),
    [
        (_split_b1(), Change(ChangeKind.ITEM_SPLIT, "B-1", split_into=("B-1a", "B-1b")), ("B-1a", "B-1b")),
        (_without("B-1"), None, ()),
    ],
    ids=["split", "removed by the owner"],
)  # fmt: skip
def test_a_split_parent_reads_removed_naming_its_parts_which_take_its_place(r2, change, split_into):
    """§5.5a (slice 3, #2886): a proposal named B-1, was returned for a split, and r2 split it.
    Bugs caught: the parent not listed, so the proposal that named it reads as naming nothing;
    the parts not ``pending`` at the parent's position (appended, so B-2 is proposed next); a
    plain removal reading as a split, or a split as a plain removal (``split_into`` taken from
    any later revision rather than the one that dropped it)."""
    log = _Log().submit("B-1", "c1").rule("returned_for_revision", "c1")
    revisions = [_revision(1), GoalSetRevision(
        project_id="prj-lantern", revision=2, goal_set=parse_goal_set(r2), author="owner",
        reason="r2", created_at=T0, change=change,
    )]  # fmt: skip

    view = backlog_view(revisions, 2, log.rows, log.launches)

    parent = next(i for i in view.items if i.item_id == "B-1")
    assert (parent.status, parent.position, parent.removed_in, parent.split_into) == (
        ItemStatus.REMOVED,
        None,
        2,
        split_into,
    )
    placed = [(i.item_id, i.status.value, i.position) for i in view.items if i.position]
    if split_into:
        assert placed[:2] == [("B-1a", "pending", 1), ("B-1b", "pending", 2)]
        assert view.next_item is not None and view.next_item.item_id == "B-1a"
    else:
        assert placed[0] == ("B-2", "pending", 1)


def test_an_item_removed_mid_increment_keeps_building_and_is_accepted_as_it_stood():
    """§5.5: "A revision that removes the item an increment is building doesn't stop that
    increment." Bug caught: the item read ``removed`` while its increment runs, so its acceptance
    is credited to nothing."""
    building = _approved(_Log(), "B-1", "c1")
    revisions = [_revision(1), _revision(2, _without("B-1"))]

    assert _statuses(backlog_view(revisions, 2, building.rows))["B-1"] == "in_increment"
    accepted = building.promote("c1")
    assert _statuses(backlog_view(revisions, 2, accepted.rows))["B-1"] == (
        "accepted (removed in r2)"
    )


def test_a_rebase_that_superseded_the_items_repair_returns_it_to_pending():
    """§24cd point 2's ``upstream_moved``: the squad's work didn't fail. Bug caught: the item read
    ``in_increment`` forever after its repair was superseded, so the next proposal skips it."""
    log = _approved(_Log(), "B-1", "c1").decide("c1", 12, action="repair")
    log.launch(CycleKind.REPAIR, None, "c1", launch_id="lnc_superseded")
    log._row(ControlOperation.BRANCH_REBASED, binding={"superseded_launch_id": "lnc_superseded"})

    view = backlog_view([_revision(1)], 1, log.rows, log.launches)

    assert view.next_item is not None and view.next_item.item_id == "B-1"


@pytest.mark.parametrize(
    ("accepted", "r2_adds", "done"),
    [
        (["B-1", "B-2", "B-3"], False, True),
        (["B-1", "B-2"], False, False),
        (["B-1", "B-2", "B-3"], True, False),
    ],
    ids=["every item accepted", "one still pending", "an item added after the last acceptance"],
)
def test_the_backlog_is_done_only_when_every_item_of_the_revision_read_is_accepted(
    accepted, r2_adds, done
):
    """§5.5a's ``backlog_done``. Bugs caught: done with an item pending; and work the owner added
    during the last increment unseen, so the Campaign stops with it unbuilt."""
    log = _Log()
    for n, item in enumerate(accepted, start=1):
        _approved(log, item, f"c{n}").promote(f"c{n}")
    doc = _document()
    if r2_adds:
        doc["backlog"].append({"id": "B-4", "title": "Yearly total", "serves": ["ER-week"]})
    view = backlog_view([_revision(1), _revision(2, doc)], 2, log.rows, log.launches)

    assert view.done is done


def test_the_view_refuses_a_revision_the_goal_set_doesnt_hold():
    """The edge. Bug caught: a pinned revision silently read as the latest."""
    with pytest.raises(ValueError, match="no revision 3"):
        backlog_view([_revision(1)], 3, [])


class TestGoalsRevised:
    """§5.5a at the ruling: a proposal is returned as ``goals_revised`` when a later revision
    moved its item off the front, or changed what it serves."""

    @pytest.mark.parametrize(
        ("latest_doc", "returned"),
        [
            (None, None),
            (_reordered(), "B-1 is no longer the next item, B-3 is"),
            (_result_changed(), "an expected result B-1 serves changed"),
            (_edited("B-2", title="Weekly total, by book"), None),
        ],
        ids=["no later revision", "reordered past it", "its result changed", "another item edited"],
    )
    def test_a_proposal_is_returned_only_when_a_later_revision_moved_or_changed_its_item(
        self, latest_doc, returned
    ):
        """Bugs caught: an approval of a proposal whose item the owner has since moved down
        (the squad builds what the owner deprioritized); or every later revision returning every
        proposal, so an unrelated edit costs a cycle."""
        log = _Log().submit("B-1", "c1")
        bound = _revision(1)
        latest = _revision(2, latest_doc) if latest_doc else bound
        view = backlog_view([bound, latest], latest.revision, log.rows, leaving_out=("prop_c1", 1))

        reason = goals_revised(item_id="B-1", bound=bound, latest=latest, view_at_latest=view)

        if returned is None:
            assert reason is None
        else:
            assert reason is not None and returned in reason


def test_the_proposal_under_ruling_is_left_out_of_the_view_it_is_judged_by():
    """Bug caught: the proposal being ruled on reads its own item as ``proposed``, so its item is
    never the next one and every ruling on a revised goal set returns it."""
    log = _Log().submit("B-1", "c1")
    doc = copy.deepcopy(_document())

    view = backlog_view([_revision(1), _revision(2, doc)], 2, log.rows, leaving_out=("prop_c1", 1))

    assert view.next_item is not None and view.next_item.item_id == "B-1"
