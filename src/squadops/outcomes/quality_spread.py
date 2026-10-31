"""Each quality measure's spread on an unchanged tree, re-measured (SIP-0113 §7, prediction 4; #2416).

The same tree, evaluated again and again, should score the same. Where a measure moves anyway, that
movement is noise, and a baseline can only be read as *held* within it: the tolerance phase 2 would
use is each measure's spread here. A reading of re-measures, never written by a model, and
reporting-only.

Like with like only, as the deltas compare (``quality_deltas``):
- **Lighthouse and axe,** per page and measure that every re-measure scored. A page or a measure
  that one re-measure didn't score is named as not compared, never read as a spread of zero.
- **Lint,** by rule, when every re-measure ran the same tools with none unavailable. A rule one
  re-measure found and another didn't counts as zero where it's absent, as the deltas count it.
- **One evaluator.** The image's tag is each measure's version, so re-measures by different
  evaluators are refused: a tool's change would read as noise.
- **§10y's finer reading,** for S1: axe's nodes by impact and ``best_practices_app`` as spreads,
  and each failing-id list as ``FailingSpread``, compared across the re-measures by set equality.
  A null list is equal only to a null list.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from squadops.outcomes.contribution import NotComparable
from squadops.scenarios.quality import (
    AXE_IMPACTS,
    FAILING_LISTS,
    LIGHTHOUSE_CATEGORIES,
    LintReading,
    QualityReading,
    QualityStatus,
)

Measure = tuple[str, str | None]


@dataclass(frozen=True)
class MeasureSpread:
    """One measure across the re-measures: ``lighthouse:performance`` on a page, ``axe:serious``
    on a page, or ``lint:total`` and ``lint:<rule>`` over the tree (``page`` is ``None``)."""

    measure: str
    page: str | None
    values: tuple[float | int, ...]

    @property
    def spread(self) -> float | int:
        return round(max(self.values) - min(self.values), 6)


@dataclass(frozen=True)
class FailingSpread:
    """§10y: one failing-id list on a page across the re-measures, each sorted, or ``None`` where
    its category scored null. ``stable`` is S1's reading: every re-measure listed the same set."""

    measure: str
    page: str
    values: tuple[tuple[str, ...] | None, ...]

    @property
    def stable(self) -> bool:
        return len({frozenset(v) if v is not None else None for v in self.values}) == 1


@dataclass(frozen=True)
class QualitySpread:
    """The tree's measures across ``readings`` re-measures, and what couldn't be compared."""

    readings: int
    evaluator: str | None
    spreads: tuple[MeasureSpread, ...]
    #: ``(what, why)``: a measure, a page or a tool that took no part.
    not_compared: tuple[tuple[str, str], ...]
    #: §10y: each failing-id list, by page. Empty where no re-measure has the finer reading.
    failing: tuple[FailingSpread, ...] = ()


def _page_values(reading: QualityReading) -> dict[Measure, float | int]:
    values: dict[Measure, float | int] = {}
    for page in reading.pages:
        if page.error:
            continue
        for category in LIGHTHOUSE_CATEGORIES:
            score = (page.lighthouse or {}).get(category)
            if score is not None:
                values[(f"lighthouse:{category}", page.path)] = score
        for impact in AXE_IMPACTS:
            count = (page.axe or {}).get(impact)
            if count is not None:
                values[(f"axe:{impact}", page.path)] = count
        if page.finer:
            for impact in AXE_IMPACTS:
                values[(f"axe_nodes:{impact}", page.path)] = (page.axe_nodes or {})[impact]
            if page.best_practices_app is not None:
                values[("lighthouse:best_practices_app", page.path)] = page.best_practices_app
    return values


def _page_lists(reading: QualityReading) -> dict[Measure, tuple[str, ...] | None]:
    """Each failing-id list a scored page carries, a null one included: it is a value S1 reads."""
    lists: dict[Measure, tuple[str, ...] | None] = {}
    for page in reading.pages:
        if page.error or not page.finer:
            continue
        for name in FAILING_LISTS:
            ids = (page.failing or {}).get(name)
            lists[(f"failing:{name}", page.path)] = tuple(sorted(ids)) if ids is not None else None
    return lists


def _evaluator(readings: Sequence[QualityReading | LintReading | None]) -> str | None:
    evaluators = {r.evaluator for r in readings if r is not None and r.evaluator}
    if len(evaluators) > 1:
        raise NotComparable(f"re-measured by {sorted(evaluators)}: one evaluator, or no spread")
    return next(iter(evaluators), None)


def _not_measured(name: str, readings: Sequence[QualityReading | LintReading | None]) -> str | None:
    for number, reading in enumerate(readings, start=1):
        if reading is None:
            return f"{name}: not recorded in re-measure {number}"
        if reading.status is not QualityStatus.MEASURED:
            reason = reading.reason.value if reading.reason else reading.status.value
            return f"{name}: {reading.status.value} in re-measure {number} ({reason})"
    return None


def _in_every(per_reading: Sequence[Mapping[Measure, object]]) -> tuple[list, list]:
    """The measures every re-measure took, in page order, and the others named as not compared."""
    every = set.intersection(*(set(v) for v in per_reading))
    skipped = sorted(
        (f"{measure} on {page}", "not scored in every re-measure")
        for measure, page in set.union(*(set(v) for v in per_reading)) - every
    )
    return sorted(every, key=lambda m: (m[1] or "", m[0])), skipped


def _quality_spreads(
    readings: Sequence[QualityReading],
) -> tuple[list[MeasureSpread], list[FailingSpread], list[tuple[str, str]]]:
    per_reading = [_page_values(r) for r in readings]
    every, skipped = _in_every(per_reading)
    spreads = [
        MeasureSpread(measure, page, tuple(v[(measure, page)] for v in per_reading))
        for measure, page in every
    ]
    per_lists = [_page_lists(r) for r in readings]
    listed, missed = _in_every(per_lists)
    failing = [
        FailingSpread(measure, page or "", tuple(v[(measure, page)] for v in per_lists))
        for measure, page in listed
    ]
    return spreads, failing, skipped + missed


def _lint_spreads(
    readings: Sequence[LintReading],
) -> tuple[list[MeasureSpread], list[tuple[str, str]]]:
    shapes: list[Mapping] = [r.reading or {} for r in readings]
    if any(s.get("unavailable") for s in shapes):
        return [], [("lint", "a tool couldn't run in a re-measure")]
    if len({repr(s.get("tools")) for s in shapes}) > 1:
        return [], [("lint", "the re-measures were read by different tools")]
    rules = sorted({rule for s in shapes for rule in s.get("by_rule", {})})
    spreads = [MeasureSpread("lint:total", None, tuple(s.get("total", 0) for s in shapes))]
    spreads += [
        MeasureSpread(
            f"lint:{rule}", None, tuple(s.get("by_rule", {}).get(rule, 0) for s in shapes)
        )
        for rule in rules
    ]
    return spreads, []


def quality_spread(
    readings: Sequence[tuple[QualityReading | None, LintReading | None]],
) -> QualitySpread:
    """Each measure's spread across ``readings``: the ``(quality, lint)`` of each re-measure of
    one unchanged tree. Refused with fewer than two, or across evaluators."""
    if len(readings) < 2:
        raise ValueError(f"a spread needs two re-measures or more, not {len(readings)}")
    qualities = [q for q, _ in readings]
    lints = [lint for _, lint in readings]
    evaluator = _evaluator([*qualities, *lints])
    spreads: list[MeasureSpread] = []
    failing: list[FailingSpread] = []
    skipped: list[tuple[str, str]] = []
    why = _not_measured("lighthouse and axe", qualities)
    if why is None:
        found, lists, missed = _quality_spreads([q for q in qualities if q is not None])
        spreads += found
        failing += lists
        skipped += missed
    else:
        skipped.append(("lighthouse and axe", why))
    why = _not_measured("lint", lints)
    if why is None:
        found, missed = _lint_spreads([lint for lint in lints if lint is not None])
        spreads += found
        skipped += missed
    else:
        skipped.append(("lint", why))
    return QualitySpread(
        readings=len(readings),
        evaluator=evaluator,
        spreads=tuple(spreads),
        not_compared=tuple(skipped),
        failing=tuple(failing),
    )
