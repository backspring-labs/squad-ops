"""The campaign's safety guarantees, read from its evidence package (SIP-0113 §4.6; #2418).

The owner ruled (2026-10-19) that AOR's *every safety guarantee intact* means the 2.0 set's seven
(``docs/plans/2-0-0-preregistration.md`` §3). Read live, before these tests were written, over the
Spark's 51 stored packages: 48 intact, the 2.0 set's two among them, and 3 not read, each a campaign
stored before #1887 recorded a promotion's tree.
"""

from __future__ import annotations

import pytest

from squadops.campaigns.safety_guarantees import (
    GuaranteeStatus,
    all_intact,
    build_bound_to_ruling,
    no_duplicate_launch,
    no_launch_beside_crew,
    no_lost_ruling,
    no_partial_promotion,
    no_stale_ruling,
    package_complete,
    safety_guarantees,
)

CAL_TREE, INC_TREE = "a" * 64, "b" * 64
H, V, N = GuaranteeStatus.HELD, GuaranteeStatus.VIOLATED, GuaranteeStatus.NOT_READ


def _row(seq, operation, binding=None, *, outcome="applied", launch_id=None):
    return {
        "seq": seq,
        "operation": operation,
        "outcome": outcome,
        "binding": binding or {},
        "launch_id": launch_id,
    }


def _promote(seq, cycle, tree, **extra):
    return _row(
        seq, "promote", {"cycle_id": cycle, "identity": tree, "tree_ref": f"art_{seq}", **extra}
    )


def _submit(seq, version, cycle="cyc_inc", content="h1"):
    return _row(
        seq,
        "submit",
        {"proposal_id": "prop_1", "version": version, "content_hash": content, "cycle_id": cycle},
    )


def _rule(seq, version, decision="approved", tree=CAL_TREE, content="h1"):
    return _row(
        seq,
        "rule",
        {
            "proposal_id": "prop_1",
            "version": version,
            "content_hash": content,
            "decision": decision,
            "baseline_tree": tree,
        },
    )


def _launch(cycle, kind, version=1):
    block = {"proposal_id": "prop_1", "version": version, "baseline_tree": CAL_TREE}
    body = {"execution_overrides": {"campaign_proposal": block}} if kind != "calibration" else {}
    return {"cycle_id": cycle, "cycle_kind": kind, "cycle_request": {"body": body}}


def _cycle(cycle, kind, *, built=True):
    runs = [{"run_id": f"run_{cycle}", "workload_type": "implementation"}] if built else []
    return {"cycle_id": cycle, "kind": kind, "assessment": {}, "revision_forms": runs}


def _doc(rows, *, cycles=None, launches=None, state="completed", outcomes=None, interventions=None):
    return {
        "campaign": {"state": state},
        "control_log": rows,
        "cycles": cycles
        if cycles is not None
        else [_cycle("cyc_cal", "calibration"), _cycle("cyc_inc", "increment")],
        "launches": launches
        if launches is not None
        else [_launch("cyc_cal", "calibration"), _launch("cyc_inc", "increment")],
        "outcomes": outcomes,
    }


#: A calibration promoted, then an increment proposed, approved against its tree, and built.
GOOD = [
    _row(1, "mark_launched", {"cycle_id": "cyc_cal"}, launch_id="lnc_1"),
    _promote(2, "cyc_cal", CAL_TREE),
    _row(3, "mark_launched", {"cycle_id": "cyc_inc"}, launch_id="lnc_2"),
    _submit(4, 1),
    _rule(5, 1),
    _promote(6, "cyc_inc", INC_TREE),
    _row(7, "decide", {"cycle_id": "cyc_inc"}),
]


def test_a_campaign_that_kept_every_guarantee_reads_all_seven_held():
    readings = safety_guarantees(_doc(GOOD))

    assert [r.status for r in readings] == [H] * 7
    assert all_intact(readings) is True


@pytest.mark.parametrize(
    ("rows", "cycles", "launches", "status", "said"),
    [
        ([r for r in GOOD if r["operation"] != "rule"], None, None, V, "no approving ruling"),
        (
            [*GOOD[:3], _submit(4, 1), _rule(5, 1, tree=INC_TREE), *GOOD[5:]],
            None,
            None,
            V,
            "the accepted tree was",
        ),
        (
            GOOD,
            None,
            [_launch("cyc_cal", "calibration"), {"cycle_id": "cyc_inc"}],
            N,
            "names no proposal",
        ),
        (
            [*GOOD, _row(8, "mark_launched", {"cycle_id": "cyc_rty"}, launch_id="lnc_3")],
            [*_doc(GOOD)["cycles"], _cycle("cyc_rty", "retry")],
            [*_doc(GOOD)["launches"], _launch("cyc_rty", "retry", version=2)],
            V,
            "cyc_rty",
        ),
    ],
    ids=[
        "built-unapproved",
        "ruled-on-a-stale-tree",
        "a-launch-with-no-block",
        "a-retry-on-another-version",
    ],
)
def test_a_build_needs_an_approving_ruling_bound_to_the_accepted_tree(
    rows, cycles, launches, status, said
):
    """Bug caught: a build read as approved when no ruling covered it, a ruling on a tree the
    campaign had moved past read as bound, or a retry's build credited to an approval of another
    version."""
    reading = build_bound_to_ruling(_doc(rows, cycles=cycles, launches=launches))

    assert reading.status is status and said in " ".join(reading.evidence)


def test_a_calibration_builds_with_no_ruling():
    """A calibration has no proposal: reading it as unapproved would read every campaign violated."""
    rows = [
        _row(1, "mark_launched", {"cycle_id": "cyc_cal"}, launch_id="lnc_1"),
        _promote(2, "cyc_cal", CAL_TREE),
    ]

    assert build_bound_to_ruling(_doc(rows, cycles=[_cycle("cyc_cal", "calibration")])).status is H


@pytest.mark.parametrize(
    ("rows", "said"),
    [
        (
            [*GOOD[:3], _submit(4, 1), _submit(5, 2, content="h2"), _rule(6, 1)],
            "the version submitted then was v2",
        ),
        ([*GOOD[:5], _rule(6, 1, decision="rejected")], "was ruled approved and rejected"),
        ([*GOOD[:3], _rule(4, 1)], "never submitted"),
    ],
    ids=["a-stale-version", "conflicting-rulings", "an-unsubmitted-proposal"],
)
def test_a_stale_or_conflicting_ruling_honoured_is_a_violation(rows, said):
    reading = no_stale_ruling(_doc(rows))

    assert reading.status is V and said in " ".join(reading.evidence)


@pytest.mark.parametrize(
    ("rows", "state", "status"),
    [
        ([*GOOD[:4]], "completed", V),
        ([*GOOD[:4], _row(5, "abort")], "completed", H),
        ([*GOOD[:4], _submit(5, 2, content="h2"), _rule(6, 2, content="h2")], "completed", H),
        ([*GOOD[:4]], "awaiting_ruling", N),
    ],
    ids=["unanswered-at-close", "aborted-while-awaiting", "superseded", "still-running"],
)
def test_a_submitted_version_left_unanswered_at_close_is_a_lost_ruling(rows, state, status):
    """Read live: an abort while a version awaits its ruling ends it (cmp_35fb81f0ec50). Bug
    caught: that abort read as a lost ruling, or a campaign still awaiting its ruling read as one."""
    assert no_lost_ruling(_doc(rows, state=state)).status is status


def test_one_intent_launching_two_cycles_is_a_duplicate_launch():
    rows = [*GOOD, _row(8, "mark_launched", {"cycle_id": "cyc_other"}, launch_id="lnc_2")]

    reading = no_duplicate_launch(_doc(rows))

    assert reading.status is V and "lnc_2" in reading.evidence[0]


@pytest.mark.parametrize(
    ("promotion", "status"),
    [
        (_promote(2, "cyc_cal", CAL_TREE, tree_ref=""), V),
        (
            _promote(
                2, "cyc_cal", CAL_TREE, frozen_criteria=[{"criterion_id": "C1", "bundle_ref": ""}]
            ),
            V,
        ),
        (_row(2, "promote", {"cycle_id": "cyc_cal", "identity": CAL_TREE}), N),
    ],
    ids=["no-tree-ref", "a-criterion-with-no-bundle", "stored-before-1887"],
)
def test_a_partial_promotion_is_a_violation_and_one_from_before_1887_isnt_read(promotion, status):
    """Read live: three campaigns from 2026-10-02 and -03 promoted before #1887 recorded a tree.
    Bug caught: those read as violated, or a promotion that lost its tree read as held."""
    assert no_partial_promotion(_doc([*GOOD[:1], promotion])).status is status


@pytest.mark.parametrize(
    ("lease", "status"),
    [([_row(2, "lease_acquire")], V), ([_row(2, "lease_acquire"), _row(3, "lease_release")], H)],
    ids=["launched-under-the-lease", "launched-after-it"],
)
def test_a_launch_while_the_supervisor_holds_the_box_is_a_violation(lease, status):
    rows = [*lease, _row(10, "mark_launched", {"cycle_id": "cyc_inc"}, launch_id="lnc_2")]

    assert no_launch_beside_crew(_doc(rows)).status is status


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"cycles": [_cycle("cyc_cal", "calibration")]}, V),
        (
            {
                "cycles": [
                    _cycle("cyc_cal", "calibration"),
                    {**_cycle("cyc_inc", "increment"), "assessment": {"unreadable": "x"}},
                ]
            },
            V,
        ),
        ({"outcomes": {"unreadable": "KeyError"}}, V),
        ({"state": "calibrating"}, N),
    ],
    ids=[
        "a-launched-cycle-missing",
        "an-unreadable-assessment",
        "unreadable-outcomes",
        "not-closed",
    ],
)
def test_the_package_is_complete_at_close(change, status):
    assert package_complete(_doc(GOOD, **change)).status is status


def test_one_unread_guarantee_is_never_read_as_all_intact():
    """§4.6: a measure that didn't run is never counted as held. Bug caught: a campaign whose
    promotions predate #1887 counted toward AOR as intact."""
    old = [*GOOD[:1], _row(2, "promote", {"cycle_id": "cyc_cal", "identity": CAL_TREE}), *GOOD[2:]]

    assert all_intact(safety_guarantees(_doc(old))) is None
    assert (
        all_intact(safety_guarantees(_doc([r for r in GOOD if r["operation"] != "rule"]))) is False
    )


REBASED_TREE = "c" * 64


@pytest.mark.parametrize(
    ("ruled_on", "status"),
    [(REBASED_TREE, H), (CAL_TREE, V)],
    ids=["ruled-on-the-rebased-tree", "ruled-on-the-tree-the-rebase-replaced"],
)
def test_a_rebase_moves_the_accepted_tree_a_ruling_must_bind_to(ruled_on, status):
    """SIP-0109 §24bv point 4: a branch's rebase moves the accepted tree as a promotion does, so
    the proposal after it is ruled on the rebased tree. Bugs caught: a ruling on the rebased tree
    read as stale (every increment after upstream moves reads violated); or one on the tree the
    rebase replaced read as bound."""
    rows = [
        _row(1, "mark_launched", {"cycle_id": "cyc_cal"}, launch_id="lnc_1"),
        _promote(2, "cyc_cal", CAL_TREE),
        _row(3, "branch_rebased", {"identity": REBASED_TREE, "commit": "d" * 40}),
        _row(4, "mark_launched", {"cycle_id": "cyc_inc"}, launch_id="lnc_2"),
        _submit(5, 1),
        _rule(6, 1, tree=ruled_on),
        _promote(7, "cyc_inc", INC_TREE),
    ]

    assert build_bound_to_ruling(_doc(rows)).status is status
