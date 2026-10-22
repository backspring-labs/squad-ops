"""What a campaign's evidence package carries of its outcome evaluations (SIP-0113 §4.4; #2418)."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime, timedelta

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.outcomes.campaign_package import campaign_outcomes
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioOutcome,
    ScenarioResult,
)
from squadops.scenarios.models import CampaignSuitePin, parse_suite
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    PageMeasure,
    QualityReading,
    QualityStatus,
)
from squadops.scenarios.suites import approve_suite, draft_suite

T0 = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
CID = "cmp_outcomes0001"
CAL, INC1, INC2 = "a" * 64, "b" * 64, "c" * 64
TAG = "squadops-evaluator:test"
GOAL = "A full run refuses a second runner, and its list keeps only the first."
SUITE = parse_suite(
    {
        "name": "held out",
        "scenarios": [
            {
                "scenario_id": "capacity",
                "goal": GOAL,
                "surfaces": [{"kind": "http_endpoint", "method": "POST", "path": "/runs"}],
                "steps": [{"action": "http", "method": "POST", "path": "/runs/held-out-step"}],
                "checks": [{"check": "status", "step": 1, "equals": 201}],
            }
        ],
    }
)


def _quality(performance: float) -> QualityReading:
    scores = {"performance": performance, "accessibility": 0.96, "best_practices": 0.78}
    return QualityReading(
        QualityStatus.MEASURED,
        pages=(PageMeasure("/", scores, {"critical": 0, "serious": 0, "moderate": 2, "minor": 0}),),
        evaluator=TAG,
    )


def _lint(total: int) -> LintReading:
    reading = {
        "tools": {"ruff": "ruff 0.16.6"},
        "total": total,
        "by_rule": {"ruff:E501": total},
        "unavailable": {},
    }
    return LintReading(QualityStatus.MEASURED, reading=reading, evaluator=TAG)


def _record(
    cycle, tree, built_on, result, *, at=T0, suite=SUITE, quality=None, lint=None, campaign_id=CID
):
    [scenario] = suite.scenarios
    outcome = ScenarioOutcome(
        scenario.scenario_id,
        scenario.version,
        scenario.goal,
        Applicability.APPLICABLE,
        result,
        first_failing_step=1 if result is ScenarioResult.FAILED else None,
    )
    return EvaluationRecord(
        evaluation_id=f"evl_{cycle}_{at.minute}",
        project_id="group_run",
        campaign_id=campaign_id,
        cycle_id=cycle,
        evaluated_tree_identity=tree,
        previous_accepted_tree_identity=built_on,
        suite_digest=suite.digest,
        outcomes=(outcome,),
        evaluated_at=at,
        quality=quality or _quality(0.93),
        lint=lint or _lint(10),
    )


@pytest.fixture
async def store():
    store = MemoryScenarioStore()
    await draft_suite(store, SUITE, actor="supervisor", at=T0)
    await approve_suite(store, SUITE.digest, actor="owner", at=T0)
    await store.save_pin(CampaignSuitePin(CID, SUITE.digest, pinned_by="owner", pinned_at=T0))
    return store


async def test_each_cycle_carries_its_contribution_quality_and_moves_against_both_trees(store):
    """§4.4 and §4.2, read at the package. Bug caught: an increment's reading taken against the
    wrong tree, the latest re-evaluation ignored, a record of another suite read as this one's, or
    a later increment's slide against the baseline never shown."""
    other = parse_suite(
        {"name": "other", "scenarios": [{**SUITE.scenarios[0].content(), "scenario_id": "other"}]}
    )
    await draft_suite(store, other, actor="supervisor", at=T0)
    for record in (
        _record("cyc_cal", CAL, None, ScenarioResult.FAILED),
        _record("cyc_inc1", INC1, CAL, ScenarioResult.FAILED, at=T0, quality=_quality(0.90)),
        _record(
            "cyc_inc1",
            INC1,
            CAL,
            ScenarioResult.PASSED,
            at=T0 + timedelta(minutes=5),
            quality=_quality(0.88),
        ),
        _record("cyc_inc2", INC2, INC1, ScenarioResult.PASSED, lint=_lint(13)),
        _record(
            "cyc_inc2", INC2, INC1, ScenarioResult.FAILED, suite=other, at=T0 + timedelta(minutes=9)
        ),
    ):
        await store.save_evaluation(record)

    section = await campaign_outcomes(store, CID, ["cyc_cal", "cyc_inc1", "cyc_inc2", "cyc_none"])

    cal, inc1, inc2, none = section["cycles"]
    assert section["suite_digest"] == SUITE.digest
    assert cal["contribution"]["reading"] == "neutral" and "vs_baseline" not in cal
    assert inc1["evaluation"] == "evl_cyc_inc1_5"
    assert inc1["contribution"] == {
        "reading": "contributed",
        "newly_passing": ["capacity"],
        "regressed": [],
        "unverified": [],
    }
    assert inc1["vs_previous"]["moved"] == [["lighthouse:performance", "/", 0.93, 0.88, -0.05]]
    assert inc2["scenarios"] == [["capacity", "passed", None]]
    assert inc2["vs_previous"]["moved"] == [
        ["lighthouse:performance", "/", 0.88, 0.93, 0.05],
        ["lint:total", None, 10, 13, 3],
        ["lint:ruff:E501", None, 10, 13, 3],
    ]
    assert inc2["vs_baseline"]["moved"] == [
        ["lint:total", None, 10, 13, 3],
        ["lint:ruff:E501", None, 10, 13, 3],
    ]
    assert none == {"cycle_id": "cyc_none", "evaluation": None}


async def test_the_package_never_carries_a_scenarios_goal_or_steps(store):
    """Held out (§4.1; IR-4): the package is a vault artifact the owner reads, and phase 1 lets no
    goal or step out of the store. Bug caught: the record's outcomes serialized whole, goal and
    all, into a project artifact."""
    await store.save_evaluation(_record("cyc_cal", CAL, None, ScenarioResult.PASSED))

    text = json.dumps(await campaign_outcomes(store, CID, ["cyc_cal"]))

    assert GOAL not in text and "held-out-step" not in text and "capacity" in text


@pytest.mark.parametrize(
    ("records", "expected"),
    [
        (
            [_record("cyc_inc1", INC1, CAL, ScenarioResult.PASSED)],
            {"reading": None, "unread_because": "no record of the tree it built on"},
        ),
    ],
    ids=["its-previous-tree-unrecorded"],
)
async def test_a_reading_with_nothing_to_read_against_says_so(store, records, expected):
    """Bug caught: an increment whose base was never evaluated read as if it were a calibration,
    so everything it passes reads as newly passing."""
    for record in records:
        await store.save_evaluation(record)

    [section] = (await campaign_outcomes(store, CID, ["cyc_inc1"]))["cycles"]

    assert section["contribution"] == expected
    assert "vs_previous" not in section


async def test_a_reading_written_with_no_campaign_never_stands_in_for_the_campaigns_record(store):
    """§10p ruling 13's reading tool writes records with no campaign, under any approved suite.
    Bug caught: a later reading of the campaign's own suite replacing its record in the package,
    which then reports a tree the campaign never evaluated."""
    own = _record("cyc_cal", "a" * 64, None, ScenarioResult.PASSED)
    later = T0 + timedelta(minutes=5)
    reading = _record("cyc_cal", "f" * 64, None, ScenarioResult.FAILED, at=later, campaign_id=None)
    for record in (own, reading):
        await store.save_evaluation(record)

    [section] = (await campaign_outcomes(store, CID, ["cyc_cal"]))["cycles"]

    assert (section["evaluation"], section["tree"]) == (own.evaluation_id, "a" * 64)


async def test_a_campaign_with_no_suite_pinned_has_no_section():
    assert await campaign_outcomes(MemoryScenarioStore(), CID, ["cyc_cal"]) is None


async def test_a_not_measured_side_is_named_not_moved(store):
    for record in (
        _record("cyc_cal", CAL, None, ScenarioResult.PASSED),
        _record(
            "cyc_inc1",
            INC1,
            CAL,
            ScenarioResult.PASSED,
            quality=QualityReading.not_measured(NotMeasured.START_FAILED),
        ),
    ):
        await store.save_evaluation(record)

    [_, inc1] = (await campaign_outcomes(store, CID, ["cyc_cal", "cyc_inc1"]))["cycles"]

    assert inc1["vs_previous"]["not_compared"] == [
        ["lighthouse and axe", "lighthouse and axe: not_measured after (start_failed)"]
    ]


async def test_a_cycle_says_how_many_of_its_page_scenarios_found_no_control(store):
    """SIP-0113 §10p ruling 4 (#2564 step 5): ``control_absent`` is unverified, never failed, so a
    page scenario whose names match no delivery would hide a job. The package and the digest say
    how many did, of those a browser read. Bug caught: the rate missing, counted over scenarios
    no browser read, or added to a package with no page scenario, which would move its identity."""
    from squadops.campaigns.evidence import _outcome_lines

    def outcome(sid, result, reason=None, runner=None):
        return ScenarioOutcome(
            sid, "v" * 64, f"{sid}'s goal", Applicability.APPLICABLE, result,
            blocked_reason=reason, runner=runner,
        )  # fmt: skip

    browser, blocked = "evaluator:4 HeadlessChrome/155", ScenarioResult.BLOCKED_UNVERIFIED
    paged = dataclasses.replace(
        _record("cyc_cal", CAL, None, ScenarioResult.PASSED),
        outcomes=(
            outcome("over-http", ScenarioResult.PASSED),
            outcome("joined-on-the-page", ScenarioResult.PASSED, runner=browser),
            outcome("named-otherwise", blocked, BlockedReason.CONTROL_ABSENT, runner=browser),
            outcome("no-browser-ran", blocked, BlockedReason.BROWSER_UNAVAILABLE),
        ),
    )
    await store.save_evaluation(paged)
    await store.save_evaluation(_record("cyc_inc1", INC1, CAL, ScenarioResult.PASSED))

    section = await campaign_outcomes(store, CID, ["cyc_cal", "cyc_inc1"])

    cal, inc1 = section["cycles"]
    assert cal["page_controls"] == {"read_in_a_browser": 2, "control_absent": 1}
    assert "page_controls" not in inc1
    lines = _outcome_lines({"suite_digest": SUITE.digest, "cycles": section["cycles"]})
    assert "  - page scenarios: 1 of 2 found no control by any of their names" in lines
