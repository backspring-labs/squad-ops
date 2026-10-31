#!/usr/bin/env python3
"""The exposure report (SIP-0110 §0.10): each build run once, with the exposures that fed it, its
app-build indicators and its arm, the exposures with no build to report by state, and each target's
absence rate with the supplied and unsupplied series apart. Then the lesson-text signal in the units
that withheld the lessons (Appendix A §3.7, T9): reviewed, never failed.

With ``--pair A B``, it reads two cycles as a paired comparison's arms instead (§3.7, T16): the pair
is valid when both were handed the same project instruction revisions, the same task instructions
and the same bound reference revisions, and invalid otherwise, with every difference named. An
invalid pair exits 1.

Observed only: the indicators never enter an assessment or a rate, and none of "no downstream
build", "pending" or "evidence missing" reads as a build failure. Read-only against the deploy's
Postgres.

    PYTHONPATH=<tree>/src:<tree> python scripts/dev/memory_exposure_report.py \\
        --dsn "$DSN" --project group_run
    PYTHONPATH=<tree>/src:<tree> python scripts/dev/memory_exposure_report.py \\
        --dsn "$DSN" --project prj-shelfnote --pair cyc_a cyc_b
"""

from __future__ import annotations

import argparse
import asyncio
import sys


async def report(dsn: str, project: str) -> int:
    from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
    from adapters.persistence.pool import create_pool
    from adapters.persistence.transient import TransientRetry
    from squadops.config.schema import DBRetryConfig
    from squadops.memory.assessment import target_absence_rates
    from squadops.memory.build_report import declared_arms, exposure_builds
    from squadops.memory.lesson_text import withheld_lesson_signals

    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    try:
        store = PostgresCrossCycleMemoryStore(pool=pool)
        registry = PostgresCycleRegistry(pool=pool, retry=TransientRetry.of(DBRetryConfig()))
        campaigns = PostgresCampaignRegistry(pool)
        exposures = await store.list_project_exposures(project)
        result = await exposure_builds(exposures, cycles=registry, campaigns=campaigns)
        by_id = {e.exposure_id: e for e in exposures}
        arms = await declared_arms((e.cycle_id for e in exposures), cycles=registry)
        print(f"== {project}: {len(exposures)} exposures, {len(result.builds)} build runs")
        for row in result.builds:
            i = row.indicators
            assert i is not None
            green = "never" if i.rounds_to_green is None else str(i.rounds_to_green)
            accepted = "-" if i.accepted is None else ("promoted" if i.accepted else "not promoted")
            print(
                f"  {row.run_id}  verdict={i.verdict}  failed_rounds={i.failed_rounds}  "
                f"refunded={i.refunded_rounds}  rounds_to_green={green}  increment={accepted}  "
                f"exposures={len(row.exposures)}  "
                f"arm={', '.join(sorted({arms.get(by_id[x].cycle_id, 'unread') for x in row.exposures}))}"
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
        signals = await withheld_lesson_signals(
            exposures, project_id=project, cycles=registry, store=store
        )
        print(
            "lesson text in units that withheld the lessons (a signal to review, never a failure):"
        )
        if not signals:
            print("  none")
        for s in signals:
            print(f"  {s.run_id} {s.task_id} ({s.seam}, {s.captured_at}): {s.revision_id}")
        return 0
    finally:
        await pool.close()


async def pair(dsn: str, project: str, a: str, b: str) -> int:
    """Two cycles read as a pair's arms: 0 when valid, 1 when invalid, every difference named."""
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
    from adapters.memory.records import PostgresMemoryRecords
    from adapters.persistence.pool import create_pool
    from adapters.persistence.transient import TransientRetry
    from squadops.config.schema import DBRetryConfig
    from squadops.memory.pairs import pair_differences, read_arm

    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    try:
        ports = {
            "store": PostgresCrossCycleMemoryStore(pool=pool),
            "records": PostgresMemoryRecords(pool),
            "cycles": PostgresCycleRegistry(pool=pool, retry=TransientRetry.of(DBRetryConfig())),
        }
        arms = [await read_arm(c, project_id=project, **ports) for c in (a, b)]
    finally:
        await pool.close()
    found = pair_differences(*arms)
    if not found:
        print(f"pair {a} {b}: valid, handed the same instructions and bound revisions")
        return 0
    print(f"pair {a} {b}: invalid, handed different bindings")
    for line in found:
        print(f"  {line}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--pair", nargs=2, metavar=("CYCLE_A", "CYCLE_B"))
    args = ap.parse_args()
    if args.pair:
        return asyncio.run(pair(args.dsn, args.project, *args.pair))
    return asyncio.run(report(args.dsn, args.project))


if __name__ == "__main__":
    sys.exit(main())
