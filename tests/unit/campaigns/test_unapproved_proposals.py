"""#2593: which proposals a fresh proposal is shown as never approved, by their last ruling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.campaigns.unapproved_proposals import (
    MOST_RECENT,
    unapproved_lines,
    unapproved_proposal,
    unapproved_rulings,
)


def _rule(proposal_id, version, decision, outcome=ControlOutcome.APPLIED, reason="r", tree="t1"):
    return SimpleNamespace(
        operation=ControlOperation.RULE,
        outcome=outcome,
        reason=reason,
        target=f"run_{proposal_id}_{version}",
        binding={
            "proposal_id": proposal_id,
            "version": version,
            "decision": decision,
            "baseline_tree": tree,
        },
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
            [_rule("p1", 1, "returned_for_revision"), _rule("p1", 2, "returned_for_revision")],
            [("p1", 2)],
        ),
        (
            [_rule("p1", 1, "rejected"), _rule("p1", 1, "approved", ControlOutcome.REFUSED)],
            [("p1", 1)],
        ),
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
        "revisions-spent",
        "a-refused-approval-approves-nothing",
        "in-the-order-ruled-and-the-approved-left-out",
    ],
)
def test_each_proposal_never_approved_is_shown_by_its_last_ruling(log, shown):
    """Bugs caught: an approved proposal's earlier return shown as if it still stood (the next
    proposal steered off a change that was built); a proposal whose revisions were spent left
    out, though it ended rejected (§9.5); a refused approval read as approving."""
    assert [
        (e.binding["proposal_id"], e.binding["version"]) for e in unapproved_rulings(log)
    ] == shown


def test_only_the_most_recent_are_shown():
    """Edge: a long campaign. Bug caught: every rejection it ever ruled riding every later
    proposal's prompt, the oldest ruled on an application long since changed."""
    log = [_rule(f"p{n}", 1, "rejected") for n in range(MOST_RECENT + 2)]

    shown = unapproved_rulings(log)

    assert [e.binding["proposal_id"] for e in shown] == [f"p{n}" for n in range(2, MOST_RECENT + 2)]


def test_a_ruling_on_an_earlier_application_says_so_and_its_run_stored_no_request():
    """Edge: the run stored no change request, and the ruling was made before a later increment
    was accepted. Bugs caught: the ruling dropped with the request, though the reason is what
    the proposer could not see before; or an old ruling shown as if made on today's
    application, which the change it rejected may since have joined."""
    entry = _rule("p1", 1, "rejected", reason="Tier 2 before\nTier 1.", tree="t-old")

    shown = unapproved_proposal(entry, None, current_tree="t-now")

    assert shown == {
        "proposal_id": "p1",
        "version": 1,
        "decision": "rejected",
        "reason": "Tier 2 before\nTier 1.",
        "ruled_on_current_application": False,
    }
    assert unapproved_lines([shown]) == (
        "- `p1` version 1, rejected, ruled on an earlier application. "
        "The supervisor's reason: Tier 2 before Tier 1."
    )
