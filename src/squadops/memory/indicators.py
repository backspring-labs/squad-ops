"""The app-build indicators beside each exposure (SIP-0110 §0.10; slice 3d, #2096).

Every exposure, ``memory_disabled`` ones included, is joined to the build its output fed: the
implementation run of the exposure's cycle. That build's indicators are recorded:
- its correction rounds, failed and refunded (``run_loop_summaries``);
- the rounds it took to reach green, or that it did not;
- its acceptance: the run's verdict, and in a campaign the increment's promotion.

**Counted once per build, with its state.** One run feeds many exposures (its plan writing, its build
authoring, its repairs), so the indicators are reported once per distinct build run, never once per
exposure. An exposure's build is in one of four states: **built**, with its indicators; **no
downstream build** (a returned proposal, a framing that never reached implementation); **pending**
(the cycle has not built yet); or **evidence missing**. None of the last three reads as a build
failure.

Observed only: these never enter an exposure's assessment or the ``target_absence_rate``, since a
green build says nothing about whether a target was present. Pure: the report script reads the
records.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from squadops.cycles.models import Run, RunStatus, WorkloadType
from squadops.cycles.run_loop_summary import RunLoopSummary
from squadops.cycles.verification_integrity import RunVerdict
from squadops.memory.exposures import Exposure

#: A run's statuses that end it.
_ENDED = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})


class BuildState(StrEnum):
    BUILT = "built"
    NO_DOWNSTREAM_BUILD = "no_downstream_build"
    PENDING = "pending"
    EVIDENCE_MISSING = "evidence_missing"


@dataclass(frozen=True)
class BuildIndicators:
    """One build run's indicators, observed."""

    run_id: str
    failed_rounds: int
    refunded_rounds: int
    verdict: str
    #: The failed rounds before the verdict was green, or ``None`` when it never was.
    rounds_to_green: int | None
    #: In a campaign, whether the increment was promoted; ``None`` for a standalone cycle.
    accepted: bool | None


@dataclass(frozen=True)
class ExposureBuild:
    exposure_id: str
    state: BuildState
    run_id: str | None


def build_run_of(
    exposure: Exposure, runs: Sequence[Run], *, returned: bool, cycle_ended: bool
) -> ExposureBuild:
    """The build the exposure's output fed: its own run when that is the implementation, else the
    latest implementation run of its cycle. ``runs`` are the cycle's.

    ``returned``: the exposure's own output was sent back (a proposal version ruled returned or
    rejected, a framing refused at its plan gate). It fed no build, whatever a later version of it
    went on to build, so that build is never credited to it."""
    if returned:
        return ExposureBuild(exposure.exposure_id, BuildState.NO_DOWNSTREAM_BUILD, None)
    builds = [r for r in runs if r.workload_type == WorkloadType.IMPLEMENTATION]
    own = next((r for r in builds if r.run_id == exposure.run_id), None)
    build = own or (max(builds, key=lambda r: r.run_number) if builds else None)
    if build is None:
        state = BuildState.NO_DOWNSTREAM_BUILD if cycle_ended else BuildState.PENDING
        return ExposureBuild(exposure.exposure_id, state, None)
    if build.status not in _ENDED:
        return ExposureBuild(exposure.exposure_id, BuildState.PENDING, build.run_id)
    return ExposureBuild(exposure.exposure_id, BuildState.BUILT, build.run_id)


def indicators_of(
    run_id: str, summary: RunLoopSummary | None, verdict: str | None, accepted: bool | None
) -> BuildIndicators | None:
    """A built run's indicators, or ``None`` when its evidence is missing (no loop summary with its
    rounds recorded, or no verdict): the exposure is then ``evidence_missing``, not a failure."""
    if summary is None or summary.round_failures is None or not verdict:
        return None
    failed = len(summary.round_failures)
    return BuildIndicators(
        run_id=run_id,
        failed_rounds=failed,
        refunded_rounds=len(summary.refunded_rounds),
        verdict=verdict,
        rounds_to_green=failed if verdict == RunVerdict.ACCEPTED else None,
        accepted=accepted,
    )


@dataclass(frozen=True)
class BuildRow:
    """One distinct build run, the exposures that fed it, and its indicators."""

    run_id: str
    exposures: tuple[str, ...]
    indicators: BuildIndicators | None


@dataclass(frozen=True)
class IndicatorReport:
    builds: tuple[BuildRow, ...]
    #: Exposures with no build to report, by state: none of these is a build failure.
    unbuilt: Mapping[BuildState, tuple[str, ...]]


def once_per_build(
    builds: Iterable[ExposureBuild], indicators: Mapping[str, BuildIndicators | None]
) -> IndicatorReport:
    """Each build run once, with every exposure that fed it; an exposure whose build is pending,
    absent or missing its evidence is reported as that."""
    fed: dict[str, list[str]] = {}
    unbuilt: dict[BuildState, list[str]] = {}
    for b in builds:
        if b.state is BuildState.BUILT and b.run_id is not None and indicators.get(b.run_id):
            fed.setdefault(b.run_id, []).append(b.exposure_id)
            continue
        state = BuildState.EVIDENCE_MISSING if b.state is BuildState.BUILT else b.state
        unbuilt.setdefault(state, []).append(b.exposure_id)
    return IndicatorReport(
        builds=tuple(
            BuildRow(run_id, tuple(sorted(exposures)), indicators[run_id])
            for run_id, exposures in sorted(fed.items())
        ),
        unbuilt={state: tuple(sorted(ids)) for state, ids in sorted(unbuilt.items())},
    )
