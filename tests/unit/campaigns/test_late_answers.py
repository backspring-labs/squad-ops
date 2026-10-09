"""A late answer reaches a plan only by being carried, and only to the same question (SIP-0109
§24bm, correcting §24bl).

What bugs would these catch? A late answer matched to a different question because the two share
a decision id (an author's ids recur across a project's framings); one free text standing for
several questions; a carried answer that the plan later changed, still read as answered; and a
manifest re-dumped when nothing in it was answered.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from squadops.campaigns.escalation import (
    RecordedAnswer,
    same_question,
    uncarried,
)
from squadops.cycles.manifest_authoring import (
    LATE_ANSWER_WARRANT,
    cited_late_answers,
    open_decisions,
    resolve_late_answers,
)

pytestmark = [pytest.mark.domain_orchestration]

AT = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
#: Shakeout 4's calibration manifest: it left ``run-list-ordering`` open.
_OPEN = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "campaigns"
    / "manifest-cyc_cc0909f2689a-open-question.yaml"
).read_text()
[(DECISION, QUESTION)] = open_decisions(_OPEN)


def _held(answer: str = "newest first", question: str = QUESTION, esc: str = "esc_aaaaaaaaaaaa"):
    return RecordedAnswer(DECISION, question, answer, "human:owner", AT, esc)


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Which order does the runs list use?", "which order does the  runs list use", True),
        ("Which order does the runs list use?", "Does the runs list page?", False),
        ("", "", False),
    ],
    ids=["case, spacing and punctuation aside", "another question", "no question"],
)
def test_two_questions_are_the_same_only_when_their_words_are(a, b, same):
    assert same_question(a, b) is same


def test_a_compatible_late_answer_is_carried_and_an_incompatible_one_leaves_the_manifest_alone():
    """Bugs caught: the answer to another question carried because the decision id matched; a
    manifest re-dumped (keys, quoting) when nothing was resolved."""
    carried = resolve_late_answers(_OPEN, {DECISION: _held()})
    other_question = resolve_late_answers(
        _OPEN, {DECISION: _held(question="Does the runs list page?")}
    )

    [decision] = [d for d in yaml.safe_load(carried)["decisions"] if d["id"] == DECISION]
    assert decision["choice"] == "newest first"
    assert decision["warrant"].startswith(f"{LATE_ANSWER_WARRANT}esc_aaaaaaaaaaaa by human:owner")
    assert "unresolved" not in decision and "question" not in decision
    assert open_decisions(carried) == ()
    assert cited_late_answers(carried) == {DECISION: ("newest first", "esc_aaaaaaaaaaaa")}
    assert other_question == _OPEN
    assert resolve_late_answers(_OPEN, {}) == _OPEN


def test_a_plan_carries_a_late_answer_only_while_its_choice_is_that_answer():
    """The owner's example: a historical "descending" never authorizes an ascending plan. Bugs
    caught: a changed choice read as answered; a citation of an escalation that holds no answer for
    the decision read as answered."""
    on_record = {DECISION: _held("descending")}

    assert uncarried({DECISION: ("descending", "esc_aaaaaaaaaaaa")}, on_record) == []
    [(changed, why)] = uncarried({DECISION: ("ascending", "esc_aaaaaaaaaaaa")}, on_record)
    [(_, unknown)] = uncarried({DECISION: ("descending", "esc_bbbbbbbbbbbb")}, on_record)

    assert changed == DECISION and "'ascending' is not the late answer it cites" in why
    assert "not on record for this decision" in unknown


def test_the_latest_answer_for_a_decision_is_the_one_on_record():
    """Bug caught: an older answer to a decision winning over a newer one, so a later launch
    carries a superseded choice."""
    from squadops.campaigns.escalation import Escalation, EscalationState, recorded_answers

    def esc(eid, answers, at):
        return Escalation(
            escalation_id=eid,
            run_id="run_x",
            cycle_id="cyc_x",
            gate_name="progress_plan_review",
            opened_at=AT,
            failed=(),
            questions=(QUESTION,),
            state=EscalationState.EXPIRED,
            decision_ids=(DECISION,),
            answers=answers,
            answered_by="human:owner",
            answered_at=at,
        )

    from unittest.mock import patch

    older = esc("esc_old000000000", {DECISION: "oldest first"}, AT)
    newer = esc("esc_new000000000", {DECISION: "newest first"}, AT + timedelta(days=1))
    with patch("squadops.campaigns.escalation.escalations", side_effect=[[newer], [older]]):
        found = recorded_answers([([], None), ([], None)])

    assert (found[DECISION].answer, found[DECISION].question) == ("newest first", QUESTION)
    assert found[DECISION].escalation_id == "esc_new000000000"
