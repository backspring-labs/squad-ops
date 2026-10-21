"""Each quality measure's delta, per increment (SIP-0113 §4.2; #2416)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from squadops.outcomes.contribution import NotComparable
from squadops.outcomes.quality_deltas import Against, MeasureDelta, quality_deltas
from squadops.scenarios.evaluation import EvaluationRecord
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    PageMeasure,
    QualityReading,
    QualityStatus,
)

T0 = datetime(2026, 10, 19, tzinfo=UTC)
CAL, INC1, INC2 = "a" * 64, "b" * 64, "c" * 64
TAG = "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-2"
SCORES = {"performance": 0.93, "accessibility": 0.96, "best_practices": 0.78}
AXE = {"critical": 0, "serious": 0, "moderate": 2, "minor": 0}


def _pages(*pages: PageMeasure, evaluator: str = TAG) -> QualityReading:
    return QualityReading(QualityStatus.MEASURED, pages=pages, evaluator=evaluator)


def _lint(by_rule: dict[str, int], **reading) -> LintReading:
    full = {
        "tools": {"ruff": "ruff 0.16.6", "eslint": "10.12.0"},
        "total": sum(by_rule.values()),
        "by_rule": by_rule,
        "unavailable": {},
        **reading,
    }
    return LintReading(QualityStatus.MEASURED, reading=full, evaluator=TAG)


def _record(tree, built_on, *, quality, lint, campaign="cmp_quality0001") -> EvaluationRecord:
    return EvaluationRecord(
        evaluation_id=f"evl_{tree[:12]}",
        project_id="group_run",
        campaign_id=campaign,
        cycle_id=f"cyc_{tree[:12]}",
        evaluated_tree_identity=tree,
        previous_accepted_tree_identity=built_on,
        suite_digest="d" * 64,
        outcomes=(),
        evaluated_at=T0,
        quality=quality,
        lint=lint,
    )


CALIBRATION = _record(
    CAL,
    None,
    quality=_pages(PageMeasure("/", SCORES, AXE), PageMeasure("/runs/new", SCORES, AXE)),
    lint=_lint({"ruff:E501": 9, "ruff:PLR2004": 44}),
)


def test_an_increments_measures_move_against_the_tree_it_built_on_page_by_page_and_rule_by_rule():
    """Bug caught: a delta taken across different pages, a rule that newly appears read as no
    move, or the lint total taken from one side only."""
    increment = _record(
        INC1,
        CAL,
        quality=_pages(
            PageMeasure("/", {**SCORES, "performance": 0.88}, {**AXE, "serious": 1}),
            PageMeasure("/runs/new", SCORES, AXE),
        ),
        lint=_lint({"ruff:E501": 7, "ruff:PLR2004": 44, "eslint:no-unused-vars": 2}),
    )

    read = quality_deltas(increment, CALIBRATION, against=Against.PREVIOUS)

    moved = {(d.measure, d.page): d.delta for d in read.deltas if d.delta}
    assert moved == {
        ("lighthouse:performance", "/"): -0.05,
        ("axe:serious", "/"): 1,
        ("lint:ruff:E501", None): -2,
        ("lint:eslint:no-unused-vars", None): 2,
    }
    assert MeasureDelta("lint:total", None, 53, 53) in read.deltas
    assert (read.against_tree, read.not_compared) == (CAL, ())


@pytest.mark.parametrize(
    ("change", "skipped"),
    [
        (
            {"quality": _pages(PageMeasure("/", SCORES, AXE), PageMeasure("/runs", SCORES, AXE))},
            {
                ("page /runs", "declared by one tree only"),
                ("page /runs/new", "declared by one tree only"),
            },
        ),
        (
            {
                "quality": _pages(
                    PageMeasure("/", SCORES, AXE),
                    PageMeasure("/runs/new", error="lighthouse: NO_FCP"),
                )
            },
            {("page /runs/new", "not scored: lighthouse: NO_FCP")},
        ),
        (
            {"quality": QualityReading.not_measured(NotMeasured.START_FAILED)},
            {("lighthouse and axe", "lighthouse and axe: not_measured after (start_failed)")},
        ),
        (
            {
                "quality": _pages(
                    PageMeasure("/", SCORES, AXE),
                    PageMeasure("/runs/new", SCORES, AXE),
                    evaluator="e:other",
                )
            },
            {
                (
                    "lighthouse and axe",
                    f"lighthouse and axe: measured by {TAG} before and e:other after",
                )
            },
        ),
        (
            {"lint": _lint({"ruff:E501": 9}, unavailable={"eslint": "eslint ran past 120s"})},
            {("lint", "a tool couldn't run on one tree")},
        ),
        (
            {"lint": None},
            {("lint", "lint: not recorded after")},
        ),
    ],
    ids=[
        "a-page-on-one-tree",
        "a-page-in-error",
        "not-measured",
        "another-evaluator",
        "a-tool-unavailable",
        "no-lint-recorded",
    ],
)
def test_what_isnt_like_for_like_is_named_never_read_as_no_move(change, skipped):
    """§4.2: not measured is never evidence. Bug caught: a start that failed read as every score
    unchanged, a new evaluator's shift read as the code's, or an unscored page as a zero."""
    increment = replace(
        _record(INC1, CAL, quality=CALIBRATION.quality, lint=CALIBRATION.lint), **change
    )

    read = quality_deltas(increment, CALIBRATION, against=Against.PREVIOUS)

    assert skipped <= set(read.not_compared)
    # Nothing that was skipped yields a delta: no skipped page's, and no skipped measure's.
    pages = {what.removeprefix("page ") for what, _ in skipped if what.startswith("page ")}
    assert [d for d in read.deltas if d.page in pages] == []
    if "lighthouse and axe" in {w for w, _ in skipped}:
        assert [d for d in read.deltas if d.page is not None] == []
    if "lint" in {w for w, _ in skipped}:
        assert [d for d in read.deltas if d.measure.startswith("lint:")] == []


def test_an_increment_is_compared_with_its_campaigns_baseline_too():
    """§4.2: the calibration's reading is the baseline. Bug caught: a later increment compared
    with the tree before it only, so a slow slide across increments never shows."""
    second = _record(
        INC2, INC1, quality=CALIBRATION.quality, lint=_lint({"ruff:E501": 12, "ruff:PLR2004": 44})
    )

    read = quality_deltas(second, CALIBRATION, against=Against.BASELINE)

    assert read.against == Against.BASELINE
    assert {d.measure: d.delta for d in read.deltas if d.page is None}["lint:ruff:E501"] == 3


@pytest.mark.parametrize(
    ("current", "other", "against"),
    [
        (_record(INC2, INC1, quality=None, lint=None), CALIBRATION, Against.PREVIOUS),
        (
            _record(INC2, INC1, quality=None, lint=None),
            _record(INC1, CAL, quality=None, lint=None),
            Against.BASELINE,
        ),
        (
            _record(INC1, CAL, quality=None, lint=None, campaign="cmp_other000001"),
            CALIBRATION,
            Against.BASELINE,
        ),
    ],
    ids=[
        "not-the-tree-it-built-on",
        "a-baseline-that-built-on-something",
        "another-campaigns-calibration",
    ],
)
def test_a_record_that_isnt_what_it_is_compared_as_is_refused(current, other, against):
    """Bug caught: deltas against a tree the increment never built on, or a baseline from
    another campaign, reported as this increment's moves."""
    with pytest.raises(NotComparable):
        quality_deltas(current, other, against=against)


# §10j, §10n (#2562): the seeded reading, compared seeded with seeded, at one seed and plan.

SEED_V = "seed:0123456789ab:plan-v1"
#: An increment built on the calibration, its other measures as the calibration's.
INCREMENT = _record(INC1, CAL, quality=CALIBRATION.quality, lint=CALIBRATION.lint)


def _seeded(*pages: PageMeasure, version: str = SEED_V) -> QualityReading:
    return QualityReading(
        QualityStatus.MEASURED, pages=pages, evaluator=TAG, seed={"version": version}
    )


def _detail(score: float, *, url: str) -> PageMeasure:
    """A seeded page, keyed by route and record, loaded at an address its own instance gave it."""
    return PageMeasure("/runs/{id}#at_capacity", {**SCORES, "performance": score}, AXE, url=url)


def test_a_seeded_page_compares_by_route_and_record_whatever_ids_its_instances_gave_it():
    """Bug caught: seeded pages keyed by a filled URL that differs on every instance, so nothing
    compares; or seeded deltas mixed into the empty instance's, under its names."""
    before = replace(CALIBRATION, quality_seeded=_seeded(_detail(0.90, url="/runs/r-17")))
    after = replace(
        INCREMENT,
        previous_accepted_tree_identity=CAL,
        quality_seeded=_seeded(_detail(0.84, url="/runs/r-93")),
    )

    result = quality_deltas(after, before, against=Against.PREVIOUS)

    seeded = [d for d in result.deltas if d.measure.startswith("seeded:")]
    assert (
        MeasureDelta("seeded:lighthouse:performance", "/runs/{id}#at_capacity", 0.90, 0.84)
        in seeded
    )
    assert {d.page for d in seeded} == {"/runs/{id}#at_capacity"}
    assert not any(d.page == "/runs/{id}#at_capacity" for d in result.deltas if d not in seeded)


@pytest.mark.parametrize(
    ("before", "after", "why"),
    [
        (_seeded(version=SEED_V), _seeded(version="seed:fedcba987654:plan-v1"), "seeded by"),
        (None, _seeded(), "not recorded before"),
        (
            QualityReading.not_measured(NotMeasured.SEED_FAILED, "POST /runs answered 500"),
            _seeded(),
            "not_measured before (seed_failed)",
        ),
    ],
    ids=["another-seed", "seeded-on-one-side-only", "a-failed-seed"],
)
def test_seeded_readings_that_arent_like_for_like_are_named_never_read_as_no_move(
    before, after, why
):
    """§10n ruling 5. Bug caught: two seeds' readings, or a seeded one against nothing, read as a
    delta of zero."""
    result = quality_deltas(
        replace(INCREMENT, previous_accepted_tree_identity=CAL, quality_seeded=after),
        replace(CALIBRATION, quality_seeded=before),
        against=Against.PREVIOUS,
    )

    [(what, said)] = [s for s in result.not_compared if s[0] == "seeded lighthouse and axe"]
    assert why in said
    assert not any(d.measure.startswith("seeded:") for d in result.deltas)


def test_two_records_with_no_seeded_reading_say_nothing_of_it():
    """Bug caught: every record written before the seeded reading listed as not compared on it,
    changing what each existing delta says."""
    result = quality_deltas(
        replace(INCREMENT, previous_accepted_tree_identity=CAL), CALIBRATION, against="previous"
    )

    assert not any("seeded" in what for what, _ in result.not_compared)
