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


def test_an_evaluated_increment_reports_each_mechanism_from_its_evaluation():
    """The completed reference increment (``cyc_257539e64218``), the first evaluated on a live
    stack: its routes rendered, and every criterion was ``not_run`` (#1880, the candidate lacked
    the qa suites). Bugs caught: an unrun criterion read as unmet or as met; a route judged on an
    anchor it did not show; an evaluation's verdict replaced by the cycle's, which was accepted."""
    report = mechanism_report(
        _record("record-cyc_257539e64218-reference-evaluated.json"),
        _record("assessment-cyc_257539e64218.json"),
        _record("evaluation-cyc_257539e64218.json"),
    )

    assert [g["decision"] for g in report["delta_framing"]["gates"]] == ["approved"]
    assert [
        (d["criterion_id"], d["met"], d["reason"])
        for d in report["baseline_discrimination"]["rows"]
    ] == [("C1", False, "not_run"), ("C2", False, "not_run"), ("C3", False, "not_run")]
    routes = {r["path"]: r for r in report["route_rendering"]["rows"]}
    assert {path: r["held"] for path, r in routes.items()} == {
        "/": "held",
        "/runs/:run_id": "held",
        "/runs/new": "held",
    }
    assert "capacity-status" in routes["/runs/:run_id"]["not_shown"]
    assert report["accumulated_acceptance"]["note"] == "no frozen criteria were pinned"
    assert report["verdict"]["increment"] == "blocked_unverified"
    assert report["verdict"]["cycle"] == "accepted"
