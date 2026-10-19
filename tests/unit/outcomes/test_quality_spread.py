"""Each quality measure's spread on an unchanged tree, re-measured (SIP-0113 §7, prediction 4;
#2416)."""

from __future__ import annotations

import pytest

from squadops.outcomes.contribution import NotComparable
from squadops.outcomes.quality_spread import quality_spread
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    PageMeasure,
    QualityReading,
    QualityStatus,
)

TAG = "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-2"
AXE = {"critical": 0, "serious": 0, "moderate": 2, "minor": 0}


def _page(path: str = "/", performance: float = 0.93, error: str | None = None) -> PageMeasure:
    if error:
        return PageMeasure(path, error=error)
    scores = {"performance": performance, "accessibility": 0.96, "best_practices": 0.78}
    return PageMeasure(path, lighthouse=scores, axe=AXE)


def _quality(*pages: PageMeasure, evaluator: str = TAG) -> QualityReading:
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


def _spreads(result) -> dict:
    return {(s.measure, s.page): (s.values, s.spread) for s in result.spreads}


def test_a_measure_that_moves_on_an_unchanged_tree_reads_its_spread():
    """Prediction 4's reading. Bug caught: the spread read from the first and last re-measure only,
    or a measure that never moved missing from the record instead of reading zero."""
    result = quality_spread(
        [
            (_quality(_page(performance=0.93)), _lint({"F401": 1})),
            (_quality(_page(performance=0.88)), _lint({"F401": 1})),
            (_quality(_page(performance=0.91)), _lint({"F401": 1})),
        ]
    )

    spreads = _spreads(result)
    assert spreads[("lighthouse:performance", "/")] == ((0.93, 0.88, 0.91), 0.05)
    assert spreads[("axe:moderate", "/")] == ((2, 2, 2), 0)
    assert spreads[("lint:total", None)] == ((1, 1, 1), 0)
    assert (result.readings, result.evaluator, result.not_compared) == (3, TAG, ())


def test_a_page_one_re_measure_couldnt_score_is_named_not_spread():
    """Bug caught: a page that errored once read as a spread of zero on the other two, so a flaky
    page looks like a stable one."""
    result = quality_spread(
        [
            (_quality(_page("/"), _page("/runs")), _lint({})),
            (_quality(_page("/"), _page("/runs", error="answered 500")), _lint({})),
        ]
    )

    pages = {page for _, page in _spreads(result)}
    assert pages == {"/", None}
    assert (
        "lighthouse:performance on /runs",
        "not scored in every re-measure",
    ) in result.not_compared


def test_a_rule_found_in_one_re_measure_counts_zero_where_it_is_absent():
    """Bug caught: a lint rule that fires on one run and not the next dropped from the spread,
    hiding exactly the noise the tolerance needs."""
    result = quality_spread([(None, _lint({"E501": 2})), (None, _lint({}))])

    spreads = _spreads(result)
    assert spreads[("lint:E501", None)] == ((2, 0), 2)
    assert spreads[("lint:total", None)] == ((2, 0), 2)
    assert ("lighthouse and axe", "lighthouse and axe: not recorded in re-measure 1") in (
        result.not_compared
    )


@pytest.mark.parametrize(
    ("readings", "named"),
    [
        (
            [(None, _lint({}, unavailable={"eslint": "timed out"})), (None, _lint({}))],
            ("lint", "a tool couldn't run in a re-measure"),
        ),
        (
            [(None, _lint({}, tools={"ruff": "ruff 0.16.6"})), (None, _lint({}))],
            ("lint", "the re-measures were read by different tools"),
        ),
        (
            [
                (QualityReading(QualityStatus.NOT_MEASURED, reason=NotMeasured.START_FAILED), None),
                (_quality(_page()), None),
            ],
            ("lighthouse and axe", "lighthouse and axe: not_measured in re-measure 1 (start_failed)"),
        ),
    ],
    ids=["a-tool-unavailable", "different-tools", "a-re-measure-not-measured"],
)  # fmt: skip
def test_a_measure_not_read_alike_every_time_takes_no_part(readings, named):
    """Bug caught: lint compared across a run where ESLint timed out (every JS finding reads as a
    spread), or a start that failed once read as a page's scores falling to nothing."""
    result = quality_spread(readings)

    assert named in result.not_compared


def test_re_measures_by_different_evaluators_are_refused():
    """The image's tag is each measure's version. Bug caught: a Lighthouse upgrade between two
    re-measures read as the measure's own noise, widening the tolerance phase 2 would gate on."""
    with pytest.raises(NotComparable, match="one evaluator"):
        quality_spread(
            [
                (_quality(_page()), None),
                (_quality(_page(), evaluator="squadops-evaluator:lighthouse13.6"), None),
            ]
        )


def test_one_re_measure_is_no_spread():
    """Bug caught: a single reading reported as a spread of zero, a tolerance with no evidence
    behind it."""
    with pytest.raises(ValueError, match="two re-measures or more"):
        quality_spread([(_quality(_page()), _lint({}))])
