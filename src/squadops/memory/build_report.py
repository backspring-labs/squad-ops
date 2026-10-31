"""Which builds a set of exposures fed, and those builds' indicators, read from the cycle and campaign
records (SIP-0110 §0.10; #2182).

The exposure report (``scripts/dev/memory_exposure_report.py``) and a memory record's uses (the console's
record view, Appendix A §3.11) read the same builds the same way, so the reading lives here once. The
rules that decide a build and its indicators are ``squadops.memory.indicators``, pure; this reads the
records they decide from.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from squadops.campaigns.gate import RETURNING_DECISIONS
from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.cycles.models import CycleNotFoundError, Run, RunStatus, WorkloadType
from squadops.memory.declarations import arm_of
from squadops.memory.exposures import Exposure
from squadops.memory.indicators import (
    BuildIndicators,
    BuildState,
    IndicatorReport,
    build_run_of,
    indicators_of,
    once_per_build,
)

if TYPE_CHECKING:
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort

_ENDED = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})
_RETURNING = frozenset(d.value for d in RETURNING_DECISIONS)


async def declared_arms(cycle_ids: Iterable[str], *, cycles: CycleRegistryPort) -> dict[str, str]:
    """Each cycle's arm, from its own declaration (Appendix A §3.7), never from what its recalls
    answered. A cycle the registry no longer holds, or whose declaration can't be read, is left
    out, so its exposures report no arm rather than a guessed one."""
    arms: dict[str, str] = {}
    for cycle_id in sorted(set(cycle_ids)):
        try:
            cycle = await cycles.get_cycle(cycle_id)
            arms[cycle_id] = arm_of(cycle.resolved_config())
        except (CycleNotFoundError, ValueError):
            continue
    return arms


def can_still_build(runs: Sequence[Run]) -> bool:
    """The cycle can still build: a run not ended, or a completed framing whose gate is undecided."""
    if any(r.status not in _ENDED for r in runs):
        return True
    latest = max(runs, key=lambda r: r.run_number, default=None)
    return bool(
        latest is not None
        and latest.workload_type == WorkloadType.FRAMING
        and latest.status == RunStatus.COMPLETED
        and not latest.gate_decisions
    )


async def exposure_builds(
    exposures: Iterable[Exposure],
    *,
    cycles: CycleRegistryPort,
    campaigns: CampaignRegistryPort,
) -> IndicatorReport:
    """Each build the exposures fed, once, with its indicators; and the exposures with no build to
    report, by state (§0.10). A returned output fed no build: a proposal version ruled returned or
    rejected, or a framing a gate sent back. In a campaign, the build's acceptance is whether its
    cycle was promoted."""
    by_cycle: dict[str, list[Exposure]] = {}
    for exposure in exposures:
        by_cycle.setdefault(exposure.cycle_id, []).append(exposure)
    builds = []
    indicators: dict[str, BuildIndicators | None] = {}
    for cycle_id, fed in sorted(by_cycle.items()):
        cycle = await cycles.get_cycle(cycle_id)
        runs = await cycles.list_runs(cycle_id)
        log = await campaigns.control_log(cycle.campaign_id) if cycle.campaign_id else []
        applied = [e for e in log if e.outcome is ControlOutcome.APPLIED]
        returned = {
            e.target
            for e in applied
            if e.operation is ControlOperation.RULE and e.binding.get("decision") in _RETURNING
        } | {r.run_id for r in runs if any(d.decision in _RETURNING for d in r.gate_decisions)}
        promoted = any(
            e.operation is ControlOperation.PROMOTE and e.target == cycle_id for e in applied
        )
        ended = cycle.cancelled or not can_still_build(runs)
        for exposure in fed:
            build = build_run_of(
                exposure, runs, returned=exposure.run_id in returned, cycle_ended=ended
            )
            builds.append(build)
            if build.state is BuildState.BUILT and build.run_id and build.run_id not in indicators:
                summary = await cycles.get_run_loop_summary(build.run_id)
                verification = await cycles.get_run_verification_summary(build.run_id)
                indicators[build.run_id] = indicators_of(
                    build.run_id,
                    summary,
                    str(verification.verdict) if verification else None,
                    promoted if cycle.campaign_id else None,
                )
    return once_per_build(builds, indicators)
