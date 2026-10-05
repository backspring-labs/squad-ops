"""#1959: replaying a campaign increment carries exactly its approved inputs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "replay_increment.py"
_spec = importlib.util.spec_from_file_location("replay_increment", _SCRIPT)
replay = importlib.util.module_from_spec(_spec)
sys.modules["replay_increment"] = replay
_spec.loader.exec_module(replay)


def _rec(art_id, kind, created, promoted=True):
    return {
        "artifact_id": art_id,
        "artifact_type": kind,
        "created_at": created,
        "promotion_status": "promoted" if promoted else None,
    }


def test_the_seeds_are_the_latest_promoted_of_each_type():
    """Bugs caught: a replay carrying the refused first version of a change request the ruling
    returned (an older promoted artifact, or an unpromoted newer one), so it replays a request
    nobody approved."""
    records = [
        _rec("art_cr_v1", "change_request", "t1"),
        _rec("art_cr_v2", "change_request", "t3"),
        _rec("art_cr_draft", "change_request", "t4", promoted=False),
        _rec("art_man", "interface_manifest", "t3"),
        _rec("art_con", "verification_contract", "t3"),
        _rec("art_log", "document", "t5"),
    ]

    assert replay.approved_seeds(records) == {
        "interface_manifest": "art_man",
        "change_request": "art_cr_v2",
        "verification_contract": "art_con",
    }


def test_a_run_missing_a_seed_is_refused():
    with pytest.raises(SystemExit, match="promoted no verification_contract"):
        replay.approved_seeds(
            [_rec("a", "change_request", "t"), _rec("b", "interface_manifest", "t")]
        )


def test_the_request_carries_the_source_block_and_seeds_outside_any_campaign():
    """Bugs caught: a replay that re-derives its baseline or frozen criteria (so it is not the
    same increment), or one created inside the source campaign."""
    block = {
        "proposal_id": "prop_1",
        "version": 2,
        "baseline_tree": "sha-tree",
        "accepted_cycle_id": "cyc_accepted",
        "baseline_manifest": "api: {}",
        "objective": {"statement": "s", "allowed_scope": ["backend/**"], "measurement": "m"},
        "prior_criteria": ["T1"],
        "frozen_criteria": [{"criterion_id": "T1", "bundle_ref": "art_b1"}],
        "max_revisions": 2,
    }
    seeds = {
        "interface_manifest": "art_m",
        "change_request": "art_c",
        "verification_contract": "art_k",
    }

    body = replay.replay_request(
        "cyc_inc", block, seeds, squad_profile_id="full-38", campaign="cmp_1"
    )

    overrides = body["execution_overrides"]
    assert body["request_profile"] == "campaign-reference"
    assert overrides["plan_artifact_refs"] == ["art_m", "art_c"]
    assert overrides["contract_ref"] == "art_k"
    replayed = overrides["campaign_proposal"]
    assert {k: replayed[k] for k in ("baseline_tree", "accepted_cycle_id", "frozen_criteria")} == {
        k: block[k] for k in ("baseline_tree", "accepted_cycle_id", "frozen_criteria")
    }
    assert replayed["proposal_id"] == "prop_1-replay"
    assert "campaign_id" not in body
    assert "cyc_inc" in body["notes"]


def test_a_cycle_that_is_not_an_increment_is_refused():
    with pytest.raises(SystemExit, match="not an increment"):
        replay.replay_request(
            "cyc_cal", {"proposal_id": "p"}, {}, squad_profile_id="f", campaign="c"
        )
