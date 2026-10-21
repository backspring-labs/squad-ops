"""#2593: which proposals a fresh proposal is shown as never approved, by their last ruling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.campaigns.unapproved_proposals import (
    unapproved_lines,
    unapproved_proposal,
    unapproved_rulings,
)


def _rule(proposal_id, version, decision, outcome=ControlOutcome.APPLIED, reason="r"):
    return SimpleNamespace(
        operation=ControlOperation.RULE,
        outcome=outcome,
        reason=reason,
        target=f"run_{proposal_id}_{version}",
        binding={"proposal_id": proposal_id, "version": version, "decision": decision},
    )


def _decide():
    return SimpleNamespace(
        operation=ControlOperation.DECIDE, outcome=ControlOutcome.APPLIED, reason="", binding={}
    )


@pytest.mark.parametrize(
    ("log", "shown"),
    [
        ([_rule("p1", 1, "rejected")], [("p1", 1)]),
        ([_rule("p1", 1, "returned_for_revision"), _rule("p1", 2, "approved")], []),
        (
            [_rule("p1", 1, "returned_for_revision"), _rule("p1", 2, "approved_with_refinements")],
            [],
        ),
        (
            [_rule("p1", 1, "returned_for_revision"), _rule("p1", 2, "returned_for_revision")],
            [("p1", 2)],
        ),
        ([_rule("p1", 1, "approved", outcome=ControlOutcome.REFUSED)], []),
        (
            [
                _rule("p1", 1, "rejected"),
                _decide(),
                _rule("p2", 1, "approved"),
                _rule("p3", 1, "rejected"),
            ],
            [("p1", 1), ("p3", 1)],
        ),
    ],
    ids=[
        "a-rejection",
        "returned-then-approved",
        "returned-then-approved-with-refinements",
        "revisions-spent",
        "a-refused-ruling-rules-nothing",
        "in-the-order-ruled-and-the-approved-left-out",
    ],
)
def test_each_proposal_never_approved_is_shown_by_its_last_ruling(log, shown):
    """Bugs caught: an approved proposal's earlier return shown as if it still stood (the next
    proposal steered off a change that was built); a proposal whose revisions were spent left
    out, though it ended rejected (§9.5); a refused row read as a ruling."""
    assert [
        (e.binding["proposal_id"], e.binding["version"]) for e in unapproved_rulings(log)
    ] == shown


def test_a_ruling_whose_request_cannot_be_read_is_shown_with_its_reason_alone():
    """Edge: the change request unreadable. Bug caught: the ruling dropped with it, when the
    reason is the part the proposer could not see before."""
    entry = _rule("p1", 1, "rejected", reason="Tier 2 before Tier 1.")

    shown = unapproved_proposal(entry, None)

    assert shown == {
        "proposal_id": "p1",
        "version": 1,
        "decision": "rejected",
        "reason": "Tier 2 before Tier 1.",
    }
    assert unapproved_lines([shown]) == (
        "- `p1` version 1, rejected. The supervisor's reason: Tier 2 before Tier 1."
    )
