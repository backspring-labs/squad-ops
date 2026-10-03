"""The reference increment's per-mechanism report (SIP-0109 §11a; #1804), read from real records.

Each fixture is a live cycle's record as the runtime API returns it: what the report must read is
what a cycle actually writes, never a shape this file invents.
"""

from __future__ import annotations

import json
from pathlib import Path

from squadops.campaigns.reference import mechanism_report

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"


def _record(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


def test_a_framing_that_never_passed_is_reported_as_refused_and_nothing_after_it_as_run():
    """Shakeout 2's increment (``cyc_b5043d62d2f0``): three framings refused at the plan gate.
    Bugs caught: a mechanism that never ran (repair, discrimination) reported as passed, or as
    an empty success; a refusal reported without its reasons."""
    report = mechanism_report(_record("record-cyc_b5043d62d2f0-refused-framings.json"), None, None)

    framing = report["delta_framing"]
    assert framing["attempts"] == 3
    assert [g["decision"] for g in framing["gates"]] == ["rejected"] * 3
    assert all(g["decided_by"] == "system:plan_validation" for g in framing["gates"])
    assert "builder.assemble declares 'assembly_notes.md'" in framing["gates"][-1]["notes"]
    assert report["scoped_repair"]["ran"] is False
    for mechanism in ("accumulated_acceptance", "baseline_discrimination", "route_rendering"):
        assert report[mechanism]["read"] is False
    assert report["verdict"]["increment"] is None


def test_a_built_increment_reports_its_repair_from_the_assessment_in_three_states():
    """The reference increment (``cyc_d4438834b2c3``): framing refused then approved, a build
    whose correction repeated its failure, and no evaluation. Bugs caught: the approved framing
    counted as refused; an indicator asked with none (``asked_none``) read as unrecorded, or an
    unrecorded one as none; the repair reported without what its rounds did."""
    report = mechanism_report(
        _record("record-cyc_d4438834b2c3-reference-failed-build.json"),
        _record("assessment-cyc_d4438834b2c3.json"),
        None,
    )

    assert [(g["decision"], g["decided_by"]) for g in report["delta_framing"]["gates"]] == [
        ("rejected", "system:plan_validation"),
        ("approved", "system:no_open_questions"),
    ]
    repair = report["scoped_repair"]
    assert repair["ran"] is True
    assert [m["movement"] for m in repair["correction_movements"]] == ["new", "repeat"]
    assert repair["refunded_rounds"] == "none"  # asked_none, never "not recorded"
    assert repair["primary_cause"] == "handoff_or_convergence_failure"
    assert report["verdict"] == {"increment": None, "unmet": [], "blocked": [], "cycle": "rejected"}


def test_an_unreadable_assessment_is_reported_as_unread_not_as_a_quiet_repair():
    """Bug caught: a repair whose record could not be read reported as one that did nothing."""
    report = mechanism_report(
        _record("record-cyc_d4438834b2c3-reference-failed-build.json"), None, None
    )

    assert report["scoped_repair"] == {"ran": True, "reason": "the assessment could not be read"}
