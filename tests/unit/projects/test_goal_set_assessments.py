"""How a Campaign's assessments leave each expected result (SIP-0115 §5.7), read by ``standings``
from assessments and revisions written here. The goal set is invented
(``tests/fixtures/goal_set.py``). What reaches the store, and the refusals, are entered at the
route in ``tests/unit/api/test_operator_surface_routes.py``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.campaigns.backlog import Acceptance
from squadops.projects.goal_set import GoalSetRevision, parse_goal_set
from squadops.projects.goal_set_assessments import (
    Assessment,
    AssessmentEvidence,
    Cause,
    Reading,
    Standing,
    standings,
)
from tests.fixtures.goal_set import goal_set_document

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
ACCEPTED_AT_7 = Acceptance(seq=7, item_id="B-2", serves=("ER-week",))


def _revision(n: int, doc: dict | None = None) -> GoalSetRevision:
    return GoalSetRevision(
        project_id="prj-lantern",
        revision=n,
        goal_set=parse_goal_set(doc or goal_set_document()),
        author="owner",
        reason=f"r{n}",
        created_at=T0,
    )


def _assessment(sequence: int, **fields) -> Assessment:
    values = {
        "project_id": "prj-lantern",
        "campaign_id": "cmp_a",
        "expected_result": "ER-week",
        "goals_revision": 1,
        "reading": Reading.MET,
        "evidence": AssessmentEvidence(cycles=("cyc_1",)),
        "reason": "the total shows",
        "author": "operator",
        "created_at": T0,
        "log_seq": 10,
        "sequence": sequence,
    }
    return Assessment(**{**values, **fields})


def _short(sequence: int, cause: Cause = Cause.APP_WORK, **fields) -> Assessment:
    return _assessment(sequence, reading=Reading.NOT_MET, cause=cause, **fields)


def _of(result_id: str, read, revisions=None, at=1, accepted=()) -> tuple:
    held = standings(read, revisions or [_revision(1)], at, accepted)
    found = next(r for r in held if r.expected_result == result_id)
    return found.standing, [a.sequence for a in found.assessments]


def _changed_statement() -> dict:
    doc = goal_set_document()
    doc["expected_results"][1]["statement"] = "The week's total hours are shown"
    return doc


def _without_the_result() -> dict:
    doc = goal_set_document()
    doc["expected_results"] = doc["expected_results"][:1] + doc["expected_results"][2:]
    doc["backlog"] = doc["backlog"][:1]
    return doc


@pytest.mark.parametrize(
    ("read", "accepted", "expected"),
    [
        ([], (), (Standing.UNASSESSED, [])),
        ([_assessment(1)], (), (Standing.CURRENT, [1])),
        ([_short(1), _assessment(2, supersedes=(1,))], (), (Standing.CURRENT, [2])),
        ([_assessment(1), _assessment(2)], (), (Standing.CURRENT, [2])),
        ([_assessment(1, log_seq=6)], (ACCEPTED_AT_7,), (Standing.STALE, [1])),
        ([_assessment(1, log_seq=7)], (ACCEPTED_AT_7,), (Standing.CURRENT, [1])),
        (
            [_assessment(1, log_seq=6)],
            (Acceptance(7, "B-1", ("ER-log",)),),
            (Standing.CURRENT, [1]),
        ),
        ([_assessment(1), _short(2)], (), (Standing.CONFLICTING, [2, 1])),
        ([_short(1), _short(2, Cause.NEEDS_OWNER)], (), (Standing.CONFLICTING, [2, 1])),
        ([_short(1), _short(2)], (), (Standing.CURRENT, [2])),
        (
            [_assessment(1, log_seq=6), _short(2, log_seq=8)],
            (ACCEPTED_AT_7,),
            (Standing.CURRENT, [2]),
        ),
        (
            [_assessment(1), _short(2), _assessment(3, supersedes=(1, 2))],
            (),
            (Standing.CURRENT, [3]),
        ),
    ],
    ids=[
        "none",
        "one",
        "a later one supersedes",
        "two that agree read the latest",
        "an acceptance after it, of a result it read",
        "the acceptance before it",
        "an acceptance of another result",
        "met against not_met",
        "two causes of one shortfall",
        "one cause twice",
        "an older one the acceptance made stale doesn't conflict",
        "a new one naming both ends the conflict",
    ],
)
def test_each_result_reads_from_its_assessments_and_the_campaigns_acceptances(
    read, accepted, expected
):
    """§5.7's rules. Bugs caught: a superseded assessment still read as the latest; the older of
    two read as the latest; an acceptance of another result making it stale, or the acceptance it
    already saw; a disagreement on the cause alone missed, when the cause is whose work it is; a
    stale one conflicting with the one that replaced it; a conflict that nothing can end."""
    assert _of("ER-week", read, accepted=accepted) == expected


def test_a_revision_that_changed_the_result_makes_it_stale_and_an_unrelated_one_does_not():
    """§5.7. Bugs caught: any later revision read as a change, so a reorder stales every
    assessment; or a changed statement missed, so a judgement of the old result reads current."""
    assessment = _assessment(1)
    reordered = goal_set_document()
    reordered["backlog"].reverse()
    same = [_revision(1), _revision(2, reordered)]
    changed = [_revision(1), _revision(2, _changed_statement())]

    assert _of("ER-week", [assessment], same, at=2) == (Standing.CURRENT, [1])
    assert _of("ER-week", [assessment], changed, at=2) == (Standing.STALE, [1])


def test_a_result_a_later_revision_removed_drops_out_of_the_view():
    """§5.7. Bug caught: an assessment of a result the owner removed still shown as how the goal
    stands, with nothing left for it to be about."""
    revisions = [_revision(1), _revision(2, _without_the_result())]

    read = standings([_assessment(1)], revisions, 2, ())

    assert [r.expected_result for r in read] == ["ER-log", "ER-calm"]
    assert all(r.standing is Standing.UNASSESSED for r in read)


def test_a_standing_carries_the_definition_of_the_revision_it_is_read_at():
    """Bug caught: a pinned Campaign's reading handed out with the latest text, so a viewer shows
    a judgement of "minutes" beside "hours"."""
    revisions = [_revision(1), _revision(2, _changed_statement())]

    pinned = standings([_assessment(1)], revisions, 1, ())
    latest = standings([_assessment(1)], revisions, 2, ())

    assert pinned[1].result.statement == "The week's total minutes are shown"
    assert latest[1].result.statement == "The week's total hours are shown"


def test_a_pinned_campaign_reads_its_own_revision_not_the_latest():
    """Bug caught: a Campaign pinned to r1 reading a result the owner removed in r2 as gone, or
    an assessment of r1 as stale, when r1 is what it was built against (§5.5)."""
    revisions = [_revision(1), _revision(2, _without_the_result())]

    assert _of("ER-week", [_assessment(1)], revisions, at=1) == (Standing.CURRENT, [1])
