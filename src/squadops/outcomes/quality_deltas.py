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
    LIGHTHOUSE_CATEGORIES,
    LintReading,
    QualityReading,
    QualityStatus,
)


class Against:
    """What an increment's measures are compared with."""

    #: The accepted tree it was built on.
    PREVIOUS = "previous"
    #: The campaign's baseline: the calibration's reading (§4.2).
    BASELINE = "baseline"


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
class QualityDeltas:
    """The increment's measures against ``against``'s tree, and what couldn't be compared."""

    against: str
    against_tree: str
    deltas: tuple[MeasureDelta, ...]
    #: ``(what, why)``: a measure, or a page, that took no part.
    not_compared: tuple[tuple[str, str], ...]


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


def _page_deltas(
    before: QualityReading, after: QualityReading, prefix: str = ""
) -> tuple[list[MeasureDelta], list[tuple[str, str]]]:
    deltas: list[MeasureDelta] = []
    skipped: list[tuple[str, str]] = []
    was = {p.path: p for p in before.pages}
    now = {p.path: p for p in after.pages}
    for path in sorted(was.keys() ^ now.keys()):
        skipped.append((f"{prefix}page {path}", "declared by one tree only"))
    for path in sorted(was.keys() & now.keys()):
        b, a = was[path], now[path]
        if b.error or a.error:
            skipped.append((f"{prefix}page {path}", f"not scored: {b.error or a.error}"))
            continue
        for category in LIGHTHOUSE_CATEGORIES:
            x, y = (b.lighthouse or {}).get(category), (a.lighthouse or {}).get(category)
            if x is not None and y is not None:
                deltas.append(MeasureDelta(f"{prefix}lighthouse:{category}", path, x, y))
        for impact in AXE_IMPACTS:
            x, y = (b.axe or {}).get(impact), (a.axe or {}).get(impact)
            if x is not None and y is not None:
                deltas.append(MeasureDelta(f"{prefix}axe:{impact}", path, x, y))
    return deltas, skipped


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
    deltas: list[MeasureDelta] = []
    skipped: list[tuple[str, str]] = []
    # ``_why_not`` names a reading that's missing; the ``None`` tests narrow the types for it.
    q_before, q_after = other.quality, current.quality
    why = _why_not("lighthouse and axe", q_before, q_after)
    if why or q_before is None or q_after is None:
        skipped.append(("lighthouse and axe", why or "not recorded"))
    else:
        found, missed = _page_deltas(q_before, q_after)
        deltas += found
        skipped += missed
    s_before, s_after = other.quality_seeded, current.quality_seeded
    if s_before is not None or s_after is not None:
        # §10j, §10n: seeded with seeded only, at one seed and plan. Two records with no seeded
        # reading say nothing of it, as before it existed.
        why = _why_not("seeded lighthouse and axe", s_before, s_after) or _seeded_apart(
            s_before, s_after
        )
        if why or s_before is None or s_after is None:
            skipped.append(("seeded lighthouse and axe", why or "not recorded"))
        else:
            found, missed = _page_deltas(s_before, s_after, prefix="seeded:")
            deltas += found
            skipped += missed
    l_before, l_after = other.lint, current.lint
    why = _why_not("lint", l_before, l_after)
    if why or l_before is None or l_after is None:
        skipped.append(("lint", why or "not recorded"))
    else:
        found, missed = _lint_deltas(l_before, l_after)
        deltas += found
        skipped += missed
    return QualityDeltas(
        against=against,
        against_tree=other.evaluated_tree_identity,
        deltas=tuple(deltas),
        not_compared=tuple(skipped),
    )
