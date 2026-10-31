"""Each quality measure's delta, per increment (SIP-0113 §4.2; #2416).

A reading of two evaluation records, never written by a model: the increment's tree against the
tree it was built on, or against the campaign's baseline, the calibration's reading. Reported beside
the contribution reading and never changing it (§4.4). Reporting-only: no row, gate or prompt reads
it.

Only like is compared with like:
- **Lighthouse and axe,** per page that both trees declare and that both scored. A page only one tree
  declares, or one that answered an error on either, is named as not compared.
- **Lint,** by rule, when both trees were read by the same tools with none unavailable.
- **A measure recorded not measured or not applicable on either side** is named as not compared, with
  why. It is never a delta of zero (§4.2: neither is evidence).
- **Two readings by different evaluators** (the image's tag is each measure's version) are not compared:
  a tool's change would read as the code's.
- **§10y's finer reading** (``-7`` on), on a page both trees scored with it: axe's nodes by impact and
  ``best_practices_app`` as differences, in ``MeasureDelta``; each failing-id list as the ids
  introduced and resolved, in ``FailingDelta``. A list that is null on either side (its category
  scored null, an audit having errored) is named as not compared, so an errored audit is never read
  as resolved. Reporting-only, and the proposal is shown none of it (``proposal_reader``).

What counts as a baseline *held* is not decided here. It needs a tolerance, and the tolerance comes from
each measure's spread on an unchanged tree (§7, prediction 4), read in the window.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from squadops.outcomes.contribution import NotComparable
from squadops.scenarios.evaluation import EvaluationRecord, QualityRemeasure
from squadops.scenarios.quality import (
    AXE_IMPACTS,
    FAILING_LISTS,
    LIGHTHOUSE_CATEGORIES,
    LintReading,
    PageMeasure,
    QualityReading,
    QualityStatus,
)


class Against:
    """What an increment's measures are compared with."""

    #: The accepted tree it was built on.
    PREVIOUS = "previous"
    #: The campaign's baseline: the calibration's reading (§4.2), a cycle's, or on a
    #: repository-backed Project its calibration record's (§10l). Either built on nothing.
    BASELINE = "baseline"
    #: A diagnostic's: the tree its edits were made to (§10y's positive control, #1251's rule).
    MADE_FROM = "made_from"


@dataclass(frozen=True)
class MeasureDelta:
    """One measure's move: ``lighthouse:performance`` on a page, ``axe:serious`` on a page, or
    ``lint:total`` and ``lint:<rule>`` over the tree (``page`` is ``None``)."""

    measure: str
    page: str | None
    before: float | int
    after: float | int

    @property
    def delta(self) -> float | int:
        return round(self.after - self.before, 6)


@dataclass(frozen=True)
class FailingDelta:
    """§10y: one failing-id list's move on a page (``failing:accessibility``, ``failing:axe``, …):
    the ids the increment introduced and the ids it resolved. Lighthouse's and axe's own ids,
    never page or suite content."""

    measure: str
    page: str
    before: tuple[str, ...]
    after: tuple[str, ...]

    @property
    def introduced(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.after) - set(self.before)))

    @property
    def resolved(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.before) - set(self.after)))

    @property
    def moved(self) -> bool:
        return set(self.before) != set(self.after)


@dataclass(frozen=True)
class QualityDeltas:
    """The increment's measures against ``against``'s tree, and what couldn't be compared."""

    against: str
    against_tree: str
    deltas: tuple[MeasureDelta, ...]
    #: ``(what, why)``: a measure, or a page, that took no part.
    not_compared: tuple[tuple[str, str], ...]
    #: §10y: each failing-id list compared, by page. Empty where neither tree has the finer reading.
    failing: tuple[FailingDelta, ...] = ()


#: What a delta reads: an evaluation's readings, or a re-measure's (§10n ruling 1).
Measured = EvaluationRecord | QualityRemeasure


def _check(current: Measured, other: Measured, against: str) -> None:
    if type(current) is not type(other):
        # §10n ruling 1: a re-measure is taken later, on another deploy; read against an
        # evaluation, it would measure the deploys, not the increment.
        raise NotComparable(
            "a re-measure compares with a re-measure, and an evaluation with an evaluation"
        )
    if (
        isinstance(current, QualityRemeasure)
        and isinstance(other, QualityRemeasure)
        and current.provenance != other.provenance
    ):
        raise NotComparable(
            f"re-measures of two series: {other.provenance!r} and {current.provenance!r}"
        )
    if against == Against.PREVIOUS:
        if other.evaluated_tree_identity != current.previous_accepted_tree_identity:
            raise NotComparable(
                f"the increment was built on {current.previous_accepted_tree_identity}, and the "
                f"other record evaluated {other.evaluated_tree_identity}"
            )
    elif against == Against.BASELINE:
        if other.previous_accepted_tree_identity is not None or (
            other.campaign_id is None or other.campaign_id != current.campaign_id
        ):
            raise NotComparable(
                "a baseline is the calibration's reading in the same campaign: a record that "
                "built on nothing, of the increment's campaign"
            )
    else:
        raise ValueError(f"compared against {against!r}: previous or baseline")


def _why_not(name: str, before, after) -> str | None:
    for side, reading in (("before", before), ("after", after)):
        if reading is None:
            return f"{name}: not recorded {side}"
        if reading.status is not QualityStatus.MEASURED:
            reason = reading.reason.value if reading.reason else reading.status.value
            return f"{name}: {reading.status.value} {side} ({reason})"
    if before.evaluator != after.evaluator:
        return f"{name}: measured by {before.evaluator} before and {after.evaluator} after"
    return None


def _seeded_apart(before, after) -> str | None:
    """Why two seeded readings can't be compared beyond what ``_why_not`` reads: another seed, or
    another plan of it (§10n ruling 5)."""
    was, now = (before.seed or {}).get("version"), (after.seed or {}).get("version")
    if was != now:
        return f"seeded lighthouse and axe: seeded by {was} before and {now} after"
    return None


@dataclass
class _Read:
    deltas: list[MeasureDelta]
    failing: list[FailingDelta]
    skipped: list[tuple[str, str]]


def _null_side(before: object, after: object, why: str) -> str:
    sides = [side for side, value in (("before", before), ("after", after)) if value is None]
    return f"null {' and '.join(sides)} ({why})"


def _finer_deltas(b: PageMeasure, a: PageMeasure, path: str, prefix: str, read: _Read) -> None:
    """§10y's measures on one page both trees scored, like with like: a measure null on either
    side is named, never a delta."""
    if not (b.finer and a.finer):
        if b.finer != a.finer:
            read.skipped.append((f"{prefix}page {path}", "the finer reading on one tree only"))
        return
    for impact in AXE_IMPACTS:
        read.deltas.append(
            MeasureDelta(
                f"{prefix}axe_nodes:{impact}",
                path,
                (b.axe_nodes or {})[impact],
                (a.axe_nodes or {})[impact],
            )
        )
    measure = f"{prefix}lighthouse:best_practices_app"
    x, y = b.best_practices_app, a.best_practices_app
    if x is not None and y is not None:
        read.deltas.append(MeasureDelta(measure, path, x, y))
    else:
        why = b.best_practices_app_error or a.best_practices_app_error or "no reading"
        read.skipped.append((f"{measure} on {path}", _null_side(x, y, why)))
    for name in FAILING_LISTS:
        measure = f"{prefix}failing:{name}"
        was, now = (b.failing or {}).get(name), (a.failing or {}).get(name)
        if was is not None and now is not None:
            read.failing.append(FailingDelta(measure, path, tuple(was), tuple(now)))
        else:
            read.skipped.append(
                (f"{measure} on {path}", _null_side(was, now, "its category scored null"))
            )


def _page_deltas(before: QualityReading, after: QualityReading, prefix: str = "") -> _Read:
    read = _Read([], [], [])
    was = {p.path: p for p in before.pages}
    now = {p.path: p for p in after.pages}
    for path in sorted(was.keys() ^ now.keys()):
        read.skipped.append((f"{prefix}page {path}", "declared by one tree only"))
    for path in sorted(was.keys() & now.keys()):
        b, a = was[path], now[path]
        if b.error or a.error:
            read.skipped.append((f"{prefix}page {path}", f"not scored: {b.error or a.error}"))
            continue
        for category in LIGHTHOUSE_CATEGORIES:
            x, y = (b.lighthouse or {}).get(category), (a.lighthouse or {}).get(category)
            if x is not None and y is not None:
                read.deltas.append(MeasureDelta(f"{prefix}lighthouse:{category}", path, x, y))
        for impact in AXE_IMPACTS:
            x, y = (b.axe or {}).get(impact), (a.axe or {}).get(impact)
            if x is not None and y is not None:
                read.deltas.append(MeasureDelta(f"{prefix}axe:{impact}", path, x, y))
        _finer_deltas(b, a, path, prefix, read)
    return read


def _lint_deltas(
    before: LintReading, after: LintReading
) -> tuple[list[MeasureDelta], list[tuple[str, str]]]:
    b: Mapping = before.reading or {}
    a: Mapping = after.reading or {}
    if b.get("unavailable") or a.get("unavailable"):
        return [], [("lint", "a tool couldn't run on one tree")]
    if b.get("tools") != a.get("tools"):
        return [], [("lint", f"read by {b.get('tools')} before and {a.get('tools')} after")]
    rules = sorted(set(b.get("by_rule", {})) | set(a.get("by_rule", {})))
    deltas = [MeasureDelta("lint:total", None, b.get("total", 0), a.get("total", 0))]
    deltas += [
        MeasureDelta(f"lint:{rule}", None, b["by_rule"].get(rule, 0), a["by_rule"].get(rule, 0))
        for rule in rules
    ]
    return deltas, []


def quality_deltas(current: Measured, other: Measured, *, against: str) -> QualityDeltas:
    """``current``'s measures against ``other``'s: the tree it was built on (``previous``), or
    the campaign's calibration (``baseline``). Refused when ``other`` isn't that record."""
    _check(current, other, against)
    read = _Read([], [], [])
    _pages_into(read, other.quality, current.quality)
    s_before, s_after = other.quality_seeded, current.quality_seeded
    if s_before is not None or s_after is not None:
        # §10j, §10n: seeded with seeded only, at one seed and plan. Two records with no seeded
        # reading say nothing of it, as before it existed.
        _pages_into(read, s_before, s_after, seeded=True)
    l_before, l_after = other.lint, current.lint
    why = _why_not("lint", l_before, l_after)
    if why or l_before is None or l_after is None:
        read.skipped.append(("lint", why or "not recorded"))
    else:
        found, missed = _lint_deltas(l_before, l_after)
        read.deltas += found
        read.skipped += missed
    return QualityDeltas(
        against=against,
        against_tree=other.evaluated_tree_identity,
        deltas=tuple(read.deltas),
        not_compared=tuple(read.skipped),
        failing=tuple(read.failing),
    )


def _pages_into(
    read: _Read,
    before: QualityReading | None,
    after: QualityReading | None,
    *,
    seeded: bool = False,
) -> None:
    """Lighthouse and axe, or the seeded reading's, compared into ``read``, or named as not."""
    name = "seeded lighthouse and axe" if seeded else "lighthouse and axe"
    # ``_why_not`` names a reading that's missing; the ``None`` tests narrow the types for it.
    why = _why_not(name, before, after)
    if seeded and not why:
        why = _seeded_apart(before, after)
    if why or before is None or after is None:
        read.skipped.append((name, why or "not recorded"))
        return
    found = _page_deltas(before, after, prefix="seeded:" if seeded else "")
    read.deltas += found.deltas
    read.failing += found.failing
    read.skipped += found.skipped


def diagnostic_deltas(
    faulted: tuple[QualityReading | None, QualityReading | None],
    made_from: tuple[QualityReading | None, QualityReading | None],
    *,
    made_from_tree: str,
) -> QualityDeltas:
    """§10y's positive control (#1251's rule): a faulted tree's ``(quality, seeded)`` readings
    against those of the tree its edits were made to, by the same like-with-like rules. A
    diagnostic, never a reading: nothing that reads an increment calls this."""
    read = _Read([], [], [])
    _pages_into(read, made_from[0], faulted[0])
    if made_from[1] is not None or faulted[1] is not None:
        _pages_into(read, made_from[1], faulted[1], seeded=True)
    return QualityDeltas(
        against=Against.MADE_FROM,
        against_tree=made_from_tree,
        deltas=tuple(read.deltas),
        not_compared=tuple(read.skipped),
        failing=tuple(read.failing),
    )
