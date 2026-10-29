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

    section = await campaign_outcomes(
        store, CID, ["cyc_cal", "cyc_inc1", "cyc_inc2", "cyc_none"], named_goals={}
    )

    cal, inc1, inc2, none = section["cycles"]
    assert section["suite_digest"] == SUITE.digest
    # A sample application's calibration is a cycle: no record's baseline (§10l) is named.
    assert "baseline" not in section
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

    text = json.dumps(await campaign_outcomes(store, CID, ["cyc_cal"], named_goals={}))

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

    [section] = (await campaign_outcomes(store, CID, ["cyc_inc1"], named_goals={}))["cycles"]

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

    [section] = (await campaign_outcomes(store, CID, ["cyc_cal"], named_goals={}))["cycles"]

    assert (section["evaluation"], section["tree"]) == (own.evaluation_id, "a" * 64)


async def test_a_campaign_with_no_suite_pinned_has_no_section():
    assert await campaign_outcomes(MemoryScenarioStore(), CID, ["cyc_cal"], named_goals={}) is None


RECORD = "calrec_outcomes001"


def _baseline_reading(result, **kw) -> EvaluationRecord:
    """§10l: a repository-backed campaign's calibration record's reading: no cycle, no previous."""
    return dataclasses.replace(
        _record("cyc_none", CAL, None, result, **kw), cycle_id=None, calibration_record_id=RECORD
    )


async def test_a_repository_backed_campaigns_baseline_is_its_records_reading(store):
    """§10l: the record's reading stands where the calibration cycle's did. Bugs caught: the first
    increment's contribution unread for want of a record of its tree; its deltas against the
    baseline never taken; a later increment compared with something other than the record's."""
    for record in (
        _baseline_reading(ScenarioResult.FAILED),
        _record("cyc_inc1", INC1, CAL, ScenarioResult.PASSED, lint=_lint(12)),
        _record("cyc_inc2", INC2, INC1, ScenarioResult.PASSED, lint=_lint(13)),
    ):
        await store.save_evaluation(record)

    section = await campaign_outcomes(
        store, CID, ["cyc_inc1", "cyc_inc2"], named_goals={}, calibration_record_id=RECORD
    )

    baseline = section["baseline"]
    assert (baseline["calibration_record_id"], baseline["evaluation"], baseline["tree"]) == (
        RECORD,
        "evl_cyc_none_0",
        CAL,
    )
    assert baseline["scenarios"] == [["capacity", "failed", None]]
    assert "unread_because" not in baseline
    inc1, inc2 = section["cycles"]
    assert inc1["contribution"]["newly_passing"] == ["capacity"]
    assert inc1["vs_baseline"]["moved"] == inc1["vs_previous"]["moved"]
    assert inc2["vs_baseline"]["against_tree"] == CAL
    assert inc2["vs_baseline"]["moved"][0] == ["lint:total", None, 10, 13, 3]


def _ran_nothing() -> EvaluationRecord:
    """A baseline reading of a product with no start declaration: every scenario blocked, every
    measure not taken."""
    [scenario] = SUITE.scenarios
    blocked = ScenarioOutcome(
        scenario.scenario_id,
        scenario.version,
        scenario.goal,
        Applicability.APPLICABLE,
        ScenarioResult.BLOCKED_UNVERIFIED,
        blocked_reason=BlockedReason.NO_START_DECLARATION,
    )
    return dataclasses.replace(
        _baseline_reading(ScenarioResult.PASSED),
        outcomes=(blocked,),
        quality=QualityReading.not_measured(NotMeasured.NO_START_DECLARATION),
        lint=LintReading.not_measured(NotMeasured.NOT_A_SCAFFOLD_STACK),
    )


@pytest.mark.parametrize(
    ("baseline", "unread"),
    [
        (None, "no baseline reading"),
        (_ran_nothing, "no baseline reading: nothing ran on its tree (no_start_declaration)"),
    ],
    ids=["no-reading-written", "a-reading-that-ran-nothing"],
)
async def test_with_no_baseline_reading_the_deltas_say_so(store, baseline, unread):
    """§10l: "the Campaign's deltas then say 'no baseline reading', never a delta of zero". Bugs
    caught: the deltas left out, so an absent baseline reads as nothing having moved; a reading
    that ran nothing compared as if measured; the record's absence read from a cycle's record."""
    if baseline is not None:
        await store.save_evaluation(baseline())
    await store.save_evaluation(_record("cyc_inc1", INC1, CAL, ScenarioResult.PASSED))

    section = await campaign_outcomes(
        store, CID, ["cyc_inc1"], named_goals={}, calibration_record_id=RECORD
    )

    assert section["baseline"]["unread_because"] == unread
    assert section["baseline"]["evaluation"] == (None if baseline is None else "evl_cyc_none_0")
    [inc1] = section["cycles"]
    assert inc1["vs_baseline"] == {"unread_because": unread}


async def test_a_cycle_that_built_on_nothing_is_never_a_repository_backed_campaigns_baseline(
    store,
):
    """§10l: on such a campaign the baseline is the record's reading alone. Bug caught: a cycle's
    record naming no previous tree (one pinned at nothing) read as the baseline, so every later
    increment is compared with a tree the campaign never accepted."""
    for record in (
        _record("cyc_inc0", INC1, None, ScenarioResult.PASSED),
        _record("cyc_inc1", INC2, INC1, ScenarioResult.PASSED),
    ):
        await store.save_evaluation(record)

    section = await campaign_outcomes(
        store, CID, ["cyc_inc0", "cyc_inc1"], named_goals={}, calibration_record_id=RECORD
    )

    assert section["baseline"]["evaluation"] is None
    assert [c["vs_baseline"] for c in section["cycles"]] == [
        {"unread_because": "no baseline reading"}
    ] * 2


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

    [_, inc1] = (await campaign_outcomes(store, CID, ["cyc_cal", "cyc_inc1"], named_goals={}))[
        "cycles"
    ]

    assert inc1["vs_previous"]["not_compared"] == [
        ["lighthouse and axe", "lighthouse and axe: not_measured after (start_failed)"]
    ]


def _finer(serious: int, axe: tuple[str, ...]) -> QualityReading:
    """§10y: a -7 page with its finer reading. Invented counts and ids."""
    [page] = _quality(0.93).pages
    finer = dataclasses.replace(
        page,
        axe_nodes={"critical": 0, "serious": serious, "moderate": 2, "minor": 0},
        failing={
            "accessibility": (),
            "best_practices": (),
            "environment": ("is-on-https", "redirects-http"),
            "axe": axe,
        },
        errored={"accessibility": (), "best_practices": (), "environment": ()},
        best_practices_app=1.0,
    )
    return QualityReading(QualityStatus.MEASURED, pages=(finer,), evaluator=TAG)


async def test_the_finer_reading_moves_beside_todays_measures_and_an_older_section_keeps_its_shape(
    store,
):
    """§10y, reporting-only. Bug caught: the failing ids left out of the package, so no reader
    sees which rule an increment introduced; or a section of two trees read before -7 gaining
    keys, so a package rebuilt from them changes shape."""
    for record in (
        _record("cyc_cal", CAL, None, ScenarioResult.PASSED, quality=_finer(0, ("region",))),
        _record(
            "cyc_inc1",
            INC1,
            CAL,
            ScenarioResult.PASSED,
            quality=_finer(2, ("color-contrast", "region")),
        ),
        _record("cyc_inc2", INC2, INC1, ScenarioResult.PASSED),
    ):
        await store.save_evaluation(record)

    _, inc1, inc2 = (
        await campaign_outcomes(store, CID, ["cyc_cal", "cyc_inc1", "cyc_inc2"], named_goals={})
    )["cycles"]

    assert inc1["vs_previous"]["moved"] == [["axe_nodes:serious", "/", 0, 2, 2]]
    assert inc1["vs_previous"]["failing_moved"] == [["failing:axe", "/", ["color-contrast"], []]]
    assert inc1["vs_previous"]["failing_unmoved"] == 3
    assert inc1["quality"]["pages"][0]["best_practices_app"] == 1.0
    # Read before -7 against a -7 reading: the same evaluator tag here, so only the finer
    # reading's absence on one side is named.
    assert "failing_moved" not in inc2["vs_previous"]
    assert ["page /", "the finer reading on one tree only"] in inc2["vs_previous"]["not_compared"]

    from squadops.campaigns.evidence import _outcome_lines

    lines = _outcome_lines({"suite_digest": SUITE.digest, "cycles": [inc1, inc2]})
    assert (
        "  - quality: measured on 1 of 1 pages; best practices raw 0.78, the app's without the "
        "environment's audits 1; lint: 10 findings"
    ) in lines
    assert (
        "  - against the tree it built on: axe_nodes:serious on / +2; failing:axe on / "
        "+color-contrast"
    ) in lines
    # A page read before -7 says what it said before.
    assert "  - quality: measured on 1 of 1 pages; lint: 10 findings" in lines


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

    section = await campaign_outcomes(store, CID, ["cyc_cal", "cyc_inc1"], named_goals={})

    cal, inc1 = section["cycles"]
    assert cal["page_controls"] == {"read_in_a_browser": 2, "control_absent": 1}
    assert "page_controls" not in inc1
    lines = _outcome_lines({"suite_digest": SUITE.digest, "cycles": section["cycles"]})
    assert "  - page scenarios: 1 of 2 found no control by any of their names" in lines


async def test_an_increments_named_goals_are_read_against_the_tree_it_was_built_on(store):
    """SIP-0113 §4.5, at the package's section. Bugs caught: a named goal read against the
    baseline or a later tree, a goal's statement carried beside its id, and a cycle that named
    none given the key."""
    for record in (
        _record("cyc_cal", CAL, None, ScenarioResult.FAILED),
        _record("cyc_inc1", INC1, CAL, ScenarioResult.PASSED),
        _record("cyc_inc2", INC2, INC1, ScenarioResult.FAILED),
    ):
        await store.save_evaluation(record)

    section = await campaign_outcomes(
        store,
        CID,
        ["cyc_cal", "cyc_inc1", "cyc_inc2", "cyc_none"],
        named_goals={"cyc_inc1": ("capacity",), "cyc_inc2": ("capacity",), "cyc_none": ("x",)},
    )

    cal, inc1, inc2, none = section["cycles"]
    assert "named_goals" not in cal
    assert inc1["named_goals"] == {"capacity": "moved"}
    assert inc2["named_goals"] == {"capacity": "regressed"}
    assert none["named_goals"] == {"x": "not evaluated"}
    assert GOAL not in json.dumps(section)
