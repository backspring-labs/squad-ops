"""A calibration record as the campaign's own shapes read it (SIP-0109 §24bv point 1, §24cc).

The start route's tests (``tests/unit/api/test_campaign_calibration_record.py``) enter where a
record is written. These hold what every later reader of it relies on: the decision row 5 makes
of it, the accepted tree that names it, and the launch that refuses it.
"""

from __future__ import annotations

import pytest

from squadops.campaigns import lifecycle
from squadops.campaigns.continuation import (
    CampaignLimit,
    Guard,
    PendingAction,
    calibration_record_decision,
)
from squadops.campaigns.launch_requests import increment_launch
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    CampaignTransition,
    ControlOperation,
)
from tests.unit.campaigns.builders import campaign, policy

RECORD = "calrec_0123456789ab"


@pytest.mark.parametrize(
    ("limits", "elapsed_s", "guard", "paused_by"),
    [
        # Every limit at its floor: a record counted as a cycle, its tokens or an unaccepted
        # increment would stop or pause the campaign before its first increment.
        (dict(max_cycles=1, max_unaccepted_increments=1, budget_tokens=1), 0, Guard.PROCEED, None),
        # The elapsed time runs from the start, record or not.
        (dict(max_elapsed_s=60), 60, Guard.PAUSED, CampaignLimit.ELAPSED_TIME),
    ],
    ids=["no-limit-counts-the-record", "the-elapsed-time-still-runs"],
)
def test_row_5_proposes_on_a_record_which_counts_toward_no_limit(
    limits, elapsed_s, guard, paused_by
):
    """§24bv point 1's rows. Bugs caught: the record counted toward row 4's limits or step 3's
    guards as a cycle would be, so a campaign allowed one cycle ends exhausted on its record; or
    the elapsed time read from anything but the start, so a campaign past its time proposes."""
    decision = calibration_record_decision(
        campaign(policy=policy(**limits)), RECORD, elapsed_s=elapsed_s
    )

    assert (decision.cycle_id, decision.row, decision.action) == (RECORD, 5, PendingAction.PROPOSE)
    assert (decision.guard, decision.paused_by) == (guard, paused_by)


@pytest.mark.parametrize(
    "names",
    [{}, {"cycle_id": "cyc_cal", "calibration_record_id": RECORD}, {"calibration_record_id": " "}],
    ids=["neither", "both", "a-blank-record"],
)
def test_an_accepted_tree_names_exactly_one_cycle_or_record(names):
    """§24cc. Bug caught: a tree naming both, which every cycle reader then reads as the cycle's
    while the record's commit is what was accepted; or neither, which reads as no tree at all."""
    with pytest.raises(ValueError, match="AcceptedTree"):
        AcceptedTree("sha-tree", **names)


def test_an_increment_on_a_records_tree_is_launched_on_the_branch_and_never_on_a_vault_cycle():
    """§24cc's last line of refusal, as §24bv point 5 changes it. Bugs caught: a proposal on a
    record's tree launched with ``accepted_cycle_id`` empty and a manifest, which every increment
    seam reads as a vault cycle's, so its promotion composes the tree on nothing; or a record with
    no commit read as a branch. A record names its commit, so its increment is the branch's."""
    on_a_record = campaign(
        accepted=AcceptedTree("sha-tree", calibration_record_id=RECORD, commit="c" * 40)
    )
    no_commit = campaign(accepted=AcceptedTree("sha-tree", calibration_record_id=RECORD))

    block = increment_launch(on_a_record, None).cycle_request["body"]["execution_overrides"][
        "campaign_proposal"
    ]
    with pytest.raises(ValueError, match="no interface manifest to be given"):
        increment_launch(on_a_record, "version: 1\n")
    with pytest.raises(ValueError, match=f"calibration record {RECORD}"):
        increment_launch(no_commit, "version: 1\n")

    assert block["basis"] == "campaign_branch"
    assert not {"accepted_cycle_id", "baseline_manifest", "baseline_tree"} & set(block)


def test_a_cycles_promotion_hashes_as_it_did_before_a_tree_could_name_a_record():
    """§12a across the upgrade. The hash is the one ``origin/main`` (4b982d6d) computes for this
    promotion. Bug caught: the new field entering every promotion's hash, so a promotion
    committed before the upgrade is refused as a conflicting key when it is re-heard after it,
    and the cycle's decision is never written."""
    promotion = CampaignTransition(
        operation=ControlOperation.PROMOTE,
        actor="squadops",
        actor_role="completion",
        reason="cycle cyc_cal accepted: its 2 delivered files",
        idempotency_key="promote:cyc_cal:sha-cal",
        next_state=CampaignState.CALIBRATING,
        target="cyc_cal",
        binding={"cycle_id": "cyc_cal", "identity": "sha-cal"},
        accepted=AcceptedTree("sha-cal", "cyc_cal"),
    )

    assert lifecycle.transition_request_hash(promotion) == (
        "a7e44b087b4bcd5077213daa252d2901a563a9592c9d5b9397d4bcd5a919a52d"
    )
