"""The per-increment scorecard (#1960), from the evidence package alone.

The 2.0 counted set's campaign 2 (``package-cmp_97a4a15f360f.json``, stored as it was written) is
the real case: three increments, all accepted, the first approved on its second version. A
constructed package carries what the set never did: an abandoned increment with a repair cycle,
and one still open.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from squadops.campaigns.evidence import digest
from squadops.campaigns.scorecard import increment_scorecards

_PACKAGE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "campaigns"
        / "package-cmp_97a4a15f360f.json"
    ).read_text()
)


def test_the_sets_campaign_2_reads_as_its_record_says():
    """Bugs caught: the first increment's returned v1 not counted as a round; a cycle's tokens
    or wall clock dropped; waiting computed from the wrong rows (negative or the whole elapsed)."""
    rows = increment_scorecards(_PACKAGE)

    assert [(r["increment"], r["outcome"], r["proposal_rounds"]) for r in rows] == [
        (1, "accepted", 2),
        (2, "accepted", 1),
        (3, "accepted", 1),
    ]
    first = rows[0]
    assert first["rulings"] == [(1, "returned_for_revision"), (2, "approved")]
    assert first["executing_s"] == pytest.approx(2558.127578)
    assert 0 < first["waiting_s"] < first["elapsed_s"]
    assert first["tokens"] == sum(first["tokens_by_role"].values())
    assert 0 < first["verification_tokens"] < first["tokens"]


def _abandoned_with_a_repair() -> dict:
    """Increment 2 of the set, made to fail: a repair cycle follows it, then it is abandoned."""
    doc = copy.deepcopy(_PACKAGE)
    inc2 = [la for la in doc["launches"] if la["cycle_id"] == "cyc_5c6ad38860f3"][0]
    repair = {**inc2, "launch_id": "lnc_repair", "cycle_kind": "repair", "cycle_id": "cyc_repair"}
    repair["created_at"] = inc2["created_at"].replace("T", "T") + "1"
    doc["launches"].append(repair)
    doc["cycles"].append({**doc["cycles"][2], "cycle_id": "cyc_repair", "kind": "repair"})
    log = doc["control_log"]
    for row in log:
        if row["operation"] == "promote" and row.get("target") == "cyc_5c6ad38860f3":
            row["operation"] = "decide"
            row["binding"] = {"row": 13, "action": "abandon_and_propose"}
    return doc


def test_an_abandoned_increment_counts_its_repair_cycle_and_its_cost():
    """Bugs caught: a repair cycle's cost left out of the increment it repaired, and an abandoned
    increment read as accepted."""
    rows = increment_scorecards(_abandoned_with_a_repair())
    original = increment_scorecards(_PACKAGE)[1]

    assert rows[1]["outcome"] == "abandoned"
    assert rows[1]["repair_retry_cycles"] == 1
    assert rows[1]["tokens"] == 2 * original["tokens"]
    assert rows[1]["criteria_added"] == 0


def test_an_open_increment_has_no_elapsed_time_yet():
    doc = copy.deepcopy(_PACKAGE)
    doc["control_log"] = [
        r
        for r in doc["control_log"]
        if not (r["operation"] in ("promote", "decide") and r.get("target") == "cyc_683247b84a40")
    ]

    last = increment_scorecards(doc)[-1]

    assert (last["outcome"], last["elapsed_s"], last["waiting_s"]) == ("open", None, None)


def test_the_digest_carries_the_table_from_the_package_alone():
    """Wiring: the digest renders it, at the caller the campaign's close uses."""
    text = digest(_PACKAGE)

    assert "## Per increment" in text
    assert "| 1 | `cyc_359d44170982` | accepted |" in text
