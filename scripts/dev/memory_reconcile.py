#!/usr/bin/env python3
"""Project every stored cycle and campaign into Cross-Cycle Memory's observations (SIP-0110 §0.3;
slice 3a, #2096).

It runs the same reconciliation the runtime will run beside each run's finalization and each
ruling, over the whole history. That is also how a crash between a record's commit and its
projection is recovered. Projecting a record twice adds nothing, so it can be run again at any time.

Dry run by default: it projects into memory and reports what it found, writing nothing.
``--write`` stores the observations. They are additive and keyed by their source record, so a
rerun never duplicates one.

    PYTHONPATH=<tree>/src:<tree> python scripts/dev/memory_reconcile.py \\
        --dsn "$DSN" --vault <checkout>/data/artifacts [--write]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path


async def reconcile_all(dsn: str, vault_dir: Path, *, write: bool) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # the guard sits beside this script
    from _evidence_read_guard import require_readable_vault

    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.memory.cross_cycle import (
        InMemoryCrossCycleMemoryStore,
        PostgresCrossCycleMemoryStore,
    )
    from adapters.persistence.pool import create_pool
    from squadops.memory.observations import ineligibility
    from squadops.memory.reconcile import reconcile_campaign, reconcile_cycle

    require_readable_vault(vault_dir)
    settings = {} if write else {"default_transaction_read_only": "on"}
    pool = await create_pool(dsn, min_size=1, max_size=2, server_settings=settings)
    try:
        registry = PostgresCycleRegistry(pool=pool)
        campaigns = PostgresCampaignRegistry(pool)
        vault = FilesystemArtifactVault(base_dir=vault_dir)
        store = (
            PostgresCrossCycleMemoryStore(pool=pool) if write else InMemoryCrossCycleMemoryStore()
        )
        async with pool.acquire() as conn:
            cycle_rows = await conn.fetch(
                "SELECT cycle_id, project_id FROM cycle_registry ORDER BY created_at"
            )
            campaign_ids = [
                r["campaign_id"]
                for r in await conn.fetch("SELECT campaign_id FROM campaigns ORDER BY created_at")
            ]
        ineligible: Counter[str] = Counter()
        new = 0
        projects = set()
        for row in cycle_rows:
            projects.add(row["project_id"])
            reason = ineligibility(await registry.get_cycle(row["cycle_id"]))
            if reason is not None:
                ineligible[reason] += 1
                continue
            new += await reconcile_cycle(
                row["cycle_id"], registry=registry, vault=vault, store=store
            )
        for campaign_id in campaign_ids:
            new += await reconcile_campaign(
                campaign_id, campaigns=campaigns, registry=registry, store=store
            )
        by_source: Counter[str] = Counter()
        by_class: Counter[str] = Counter()
        for project in sorted(projects):
            for o in await store.list_observations(project):
                by_source[o.source.value] += 1
                key = f"{o.source.value}: {o.classification.vocabulary}={','.join(o.classification.values) or '-'}"
                by_class[key] += 1
        return {
            "mode": "write" if write else "dry run",
            "cycles": len(cycle_rows),
            "campaigns": len(campaign_ids),
            "ineligible_cycles": dict(ineligible),
            "new": new,
            "by_source": dict(by_source),
            "by_class": dict(by_class.most_common()),
        }
    finally:
        await pool.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--vault", required=True, type=Path)
    ap.add_argument(
        "--write", action="store_true", help="store the observations (default: dry run)"
    )
    args = ap.parse_args()
    report = asyncio.run(reconcile_all(args.dsn, args.vault, write=args.write))
    for key in ("mode", "cycles", "campaigns", "ineligible_cycles", "new", "by_source"):
        print(f"{key}: {report[key]}")
    print("by_class:")
    for key, count in report["by_class"].items():
        print(f"  {count:5}  {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
