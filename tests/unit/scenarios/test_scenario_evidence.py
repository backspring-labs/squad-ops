"""A page scenario's evidence, as it may leave the sandbox (SIP-0113 §10p ruling 8; #2564 step 4).

What bugs would these catch?
- an evaluation's secret written into the store through an error the page logged, a request it
  failed, or a control's name, or through a screenshot of a page that showed it (Q40);
- one scenario's evidence crowding out the rest, or an evaluation's growing without bound;
- a screenshot that isn't base64 stored as whatever it decodes to;
- the stored bytes not the bytes the record's sha256 names.
"""

from __future__ import annotations

import base64

from squadops.scenarios.evidence import (
    EVALUATION_CAP,
    SCENARIO_CAP,
    ScenarioEvidence,
    kept,
)

SECRET = "tok-Moonrise-Relay"


def _item(scenario_id="s", *, png=b"\x89PNG small", **kw) -> ScenarioEvidence:
    fields = {
        "nodes": ({"name": f"Join {SECRET}", "visible": True, "disabled": False},),
        "errors": (f"console: 401 for {SECRET}",),
        "failed_requests": (f"GET /x?t={SECRET}: failed",),
        **kw,
    }
    return ScenarioEvidence(
        scenario_id=scenario_id, step=3, screenshot=png, role="button", **fields
    )


def _scrub(text: str) -> str:
    return text.replace(SECRET, "[redacted]")


def test_text_is_scrubbed_and_a_resolved_secret_costs_the_screenshot():
    [out] = kept([_item()], scrub=_scrub, secret_resolved=True)

    assert SECRET not in repr(out.details())
    assert out.screenshot is None
    assert out.withheld == ("screenshot: the evaluation resolved a secret",)


def test_with_no_secret_the_screenshot_is_kept_whole():
    [out] = kept([_item()], scrub=_scrub, secret_resolved=False)

    assert (out.screenshot, out.withheld) == (b"\x89PNG small", ())


def test_the_caps_drop_a_screenshot_first_then_nodes_and_keep_every_scenarios_text():
    big = b"x" * (SCENARIO_CAP + 1)
    huge_nodes = tuple({"name": "n" * 1000} for _ in range(SCENARIO_CAP // 1000 + 1))
    near_cap = b"y" * (SCENARIO_CAP - 4096)
    items = [_item("a", png=big), _item("b", png=None, nodes=huge_nodes)]
    items += [_item(f"c{i}", png=near_cap) for i in range(EVALUATION_CAP // SCENARIO_CAP + 1)]

    out = kept(items, scrub=_scrub, secret_resolved=False)

    assert (out[0].screenshot, out[0].withheld) == (None, ("screenshot: over the scenario's cap",))
    assert (out[1].nodes, out[1].withheld) == ((), ("nodes: over the scenario's cap",))
    assert all(o.size <= SCENARIO_CAP for o in out)
    assert sum(o.size for o in out) <= EVALUATION_CAP
    assert out[-1].withheld == ("screenshot: over the evaluation's cap",)
    assert all(o.errors for o in out)


def test_a_screenshot_that_isnt_base64_is_withheld_and_the_round_trip_keeps_its_sha256():
    bad = ScenarioEvidence.from_wire("s", {"step": 2, "png_b64": "%%not-base64%%"})
    wire = _item().to_wire()
    back = ScenarioEvidence.from_wire("s", wire)

    assert (bad.screenshot, bad.withheld) == (None, ("screenshot: not base64",))
    assert back == _item() and back.sha256 == _item().sha256
    assert base64.b64decode(wire["png_b64"]) == b"\x89PNG small"


async def test_the_cuts_purge_removes_only_evidence_of_evaluations_made_before_it():
    """§10p ruling 8: kept for the line, purged at its cut. Bug caught: the purge removing the
    next line's evidence too, or counting what it didn't remove."""
    from datetime import UTC, datetime, timedelta

    from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
    from squadops.scenarios.evaluation import EvaluationRecord
    from squadops.scenarios.models import parse_suite
    from squadops.scenarios.suites import draft_suite
    from tests.unit.scenarios.suite_fixtures import SUITE

    cut = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    store, suite = MemoryScenarioStore(), parse_suite(SUITE)
    await draft_suite(store, suite, actor="supervisor", at=cut)
    for evaluation_id, at in (
        ("evl_before00000", cut - timedelta(days=1)),
        ("evl_after000000", cut),
    ):
        await store.save_evaluation(
            EvaluationRecord(
                evaluation_id=evaluation_id, project_id="group_run", campaign_id=None,
                cycle_id="cyc_x", evaluated_tree_identity="a" * 64,
                previous_accepted_tree_identity=None, suite_digest=suite.digest, outcomes=(),
                evaluated_at=at,
            )
        )  # fmt: skip
        await store.save_evidence(evaluation_id, [_item("s1"), _item("s2")])

    purged = await store.purge_evidence(cut)

    assert purged == 2
    assert await store.evidence_for("evl_before00000") == []
    assert len(await store.evidence_for("evl_after000000")) == 2
