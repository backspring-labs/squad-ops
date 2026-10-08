#!/usr/bin/env python3
"""The exposure report (SIP-0110 §0.10): each build run once, with the exposures that fed it and its
app-build indicators, the exposures with no build to report by state, and each target's absence
rate with the supplied and unsupplied series apart.

Observed only: the indicators never enter an assessment or a rate, and none of "no downstream
build", "pending" or "evidence missing" reads as a build failure. Read-only against the deploy's
Postgres.

    PYTHONPATH=<tree>/src:<tree> python scripts/dev/memory_exposure_report.py \\
        --dsn "$DSN" --project group_run
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def _pending(runs) -> bool:
    """The cycle can still build: a run not ended, or a completed framing whose gate is undecided."""
    from squadops.cycles.models import RunStatus, WorkloadType

    ended = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
    if any(r.status not in ended for r in runs):
        return True
    latest = max(runs, key=lambda r: r.run_number, default=None)
    return bool(
        latest is not None
        and latest.workload_type == WorkloadType.FRAMING
        and latest.status == RunStatus.COMPLETED
        and not latest.gate_decisions
    )


async def report(dsn: str, project: str) -> int:
    from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
    from adapters.persistence.pool import create_pool
    from squadops.campaigns.gate import RETURNING_DECISIONS
    from squadops.campaigns.models import ControlOperation, ControlOutcome
    from squadops.memory.assessment import target_absence_rates
    from squadops.memory.indicators import (
        BuildState,
        build_run_of,
        indicators_of,
        once_per_build,
    )

    returning = {d.value for d in RETURNING_DECISIONS}
    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    try:
        store = PostgresCrossCycleMemoryStore(pool=pool)
        registry = PostgresCycleRegistry(pool=pool)
        campaigns = PostgresCampaignRegistry(pool)
        exposures = await store.list_project_exposures(project)
        by_cycle: dict[str, list] = {}
        for e in exposures:
            by_cycle.setdefault(e.cycle_id, []).append(e)
        builds, indicators = [], {}
        for cycle_id, fed in sorted(by_cycle.items()):
            cycle = await registry.get_cycle(cycle_id)
            runs = await registry.list_runs(cycle_id)
            log = await campaigns.control_log(cycle.campaign_id) if cycle.campaign_id else []
            applied = [e for e in log if e.outcome is ControlOutcome.APPLIED]
            returned = {
                e.target
                for e in applied
                if e.operation is ControlOperation.RULE and e.binding.get("decision") in returning
            } | {r.run_id for r in runs if any(d.decision in returning for d in r.gate_decisions)}
            promoted = any(
                e.operation is ControlOperation.PROMOTE and e.target == cycle_id for e in applied
            )
            ended = cycle.cancelled or not _pending(runs)
            for e in fed:
                b = build_run_of(e, runs, returned=e.run_id in returned, cycle_ended=ended)
                builds.append(b)
                if b.state is BuildState.BUILT and b.run_id and b.run_id not in indicators:
                    summary = await registry.get_run_loop_summary(b.run_id)
                    verification = await registry.get_run_verification_summary(b.run_id)
                    indicators[b.run_id] = indicators_of(
                        b.run_id,
                        summary,
                        str(verification.verdict) if verification else None,
                        promoted if cycle.campaign_id else None,
                    )
        result = once_per_build(builds, indicators)
        print(f"== {project}: {len(exposures)} exposures, {len(result.builds)} build runs")
        for row in result.builds:
            i = row.indicators
            assert i is not None
            green = "never" if i.rounds_to_green is None else str(i.rounds_to_green)
            accepted = "-" if i.accepted is None else ("promoted" if i.accepted else "not promoted")
            print(
                f"  {row.run_id}  verdict={i.verdict}  failed_rounds={i.failed_rounds}  "
                f"refunded={i.refunded_rounds}  rounds_to_green={green}  increment={accepted}  "
                f"exposures={len(row.exposures)}"
            )
        for state, ids in result.unbuilt.items():
            print(f"  {state.value}: {len(ids)} exposures (none of them a build failure)")
        print("target absence (supplied / unsupplied series apart):")
        rates = target_absence_rates(await store.list_assessments(project))
        if not rates:
            print("  none assessed")
        for r in rates:
            series = "supplied" if r.supplied else "unsupplied"
            print(
                f"  {r.pattern_id} {series}: {r.absent}/{r.assessed} absent "
                f"(n/a {r.not_applicable}, unassessed {r.unassessed})"
            )
        return 0
    finally:
        await pool.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--project", required=True)
    args = ap.parse_args()
    return asyncio.run(report(args.dsn, args.project))


if __name__ == "__main__":
    sys.exit(main())
