"""Cycle lineage: which cycles belong to one series (1.8.0 plan §3.5, the lineage seam).

**Extracted, not designed.** This is the series rule inert-check detection (SIP-0096 §9, #684)
has applied since it shipped, given a name so a second reader uses the same identity rather
than re-deriving it. The rule was an inline filter in ``cycle_outcome._collect_inert``; that
walk now calls ``prior_in_series`` and its output is unchanged.

**The identity.** Two cycles are in one series when they share a project, a squad profile and
a request profile. The scope is strict on purpose: a check's applicability differs across
profiles, so history from another profile would accrue not-executed streaks against checks
that were never meant to run there (a false inert). ``request_profile`` is compared as stored,
so a cycle created before it existed (``None``) is in a series only with other such cycles.

**Readers.** Inert detection reads it now. SIP-0108's ``CycleAssessment`` baseline comparison
is the second reader, when the scorecard lands. Campaign (2.0) may enrich the derivation behind
``series_for`` with its objective envelope; a consumer reads ``SeriesKey`` and does not migrate.

Code lineage is not part of the key. ``Cycle.framework_version`` and ``framework_git_sha``
(#80) say which code a cycle ran on, which a comparison slices by within a series; they do
not decide membership.

Pure functions over ``Cycle`` records. The registry read stays with each reader, and the read
inert detection uses today is anchored at the project's newest cycles, not at the cycle being
assessed, so a historical cycle's priors can be missing from it (#1526). A reader over
history should not copy that read.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.cycles.models import Cycle


@dataclass(frozen=True)
class SeriesKey:
    """The identity a cycle's series is keyed on."""

    project_id: str
    squad_profile_id: str
    request_profile: str | None


def series_for(cycle: Cycle) -> SeriesKey:
    """The series ``cycle`` belongs to."""
    return SeriesKey(
        project_id=cycle.project_id,
        squad_profile_id=cycle.squad_profile_id,
        request_profile=cycle.request_profile,
    )


def prior_in_series(
    cycle: Cycle, candidates: Iterable[Cycle], *, limit: int | None = None
) -> list[Cycle]:
    """The candidates in ``cycle``'s series created strictly before it, in the order given.

    ``cycle`` itself is excluded, as is any candidate created at the same instant or later.
    Order is preserved, so a registry's newest-first listing yields the nearest priors first.
    ``limit`` bounds the result *after* filtering: a window of the series, never a window of
    the candidates that the filter then shrinks.
    """
    key = series_for(cycle)
    prior = [
        c
        for c in candidates
        if c.cycle_id != cycle.cycle_id and c.created_at < cycle.created_at and series_for(c) == key
    ]
    return prior if limit is None else prior[:limit]
