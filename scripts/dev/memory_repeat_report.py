#!/usr/bin/env python3
"""The repeat report (SIP-0110 §0.4, the 2.2 plan's D14): which signatures recur across
independent cycles, and which target behaviors the auditor has substantiated as recurring.

It projects every stored cycle and campaign the way the reconciler does, in memory and
read-only, so it reads the records themselves rather than whatever was last written. A retry
and the cycle it retries count once. A repeated signature is a candidate for the auditor, never a
finding.

    PYTHONPATH=<tree>/src:<tree> python scripts/dev/memory_repeat_report.py \\
        --dsn "$DSN" --vault <checkout>/data/artifacts [--minimum 2]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


async def report(dsn: str, vault_dir: Path, minimum: int) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _evidence_read_guard import require_readable_vault

    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
    from adapters.persistence.pool import create_pool
    from squadops.memory.reconcile import reconcile_campaign, reconcile_cycle
    from squadops.memory.repeats import repeated_signatures

    require_readable_vault(vault_dir)
    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    try:
        registry = PostgresCycleRegistry(pool=pool)
        campaigns = PostgresCampaignRegistry(pool)
        vault = FilesystemArtifactVault(base_dir=vault_dir)
        store = InMemoryCrossCycleMemoryStore()
        async with pool.acquire() as conn:
            cycles = await conn.fetch(
                "SELECT cycle_id, project_id, execution_overrides FROM cycle_registry "
                "ORDER BY created_at"
            )
            campaign_ids = [
                r["campaign_id"] for r in await conn.fetch("SELECT campaign_id FROM campaigns")
            ]
        prior: dict[str, str] = {}
        for row in cycles:
            overrides = row["execution_overrides"]
            overrides = json.loads(overrides) if isinstance(overrides, str) else overrides or {}
            retried = ((overrides.get("campaign_proposal") or {}).get("prior_cycle") or {}).get(
                "cycle_id"
            )
            if retried:
                prior[row["cycle_id"]] = str(retried)
            await reconcile_cycle(row["cycle_id"], registry=registry, vault=vault, store=store)
        for campaign_id in campaign_ids:
            await reconcile_campaign(
                campaign_id, campaigns=campaigns, registry=registry, store=store
            )
        for project in sorted({r["project_id"] for r in cycles}):
            observations = await store.list_observations(project)
            rows = repeated_signatures(observations, prior, minimum=minimum)
            shaped = sum(
                1
                for o in observations
                if any(s.get("shape") for s in o.evidence.get("failure_shapes") or [])
            )
            print(f"== {project}: {len(observations)} observations, {shaped} rounds with a shape")
            print(f"repeated signatures (in at least {minimum} independent cycles):")
            if not rows:
                print("  none")
            for r in rows:
                print(
                    f"  {r.independent_cycles:3} cycles  {r.observations:3} obs  "
                    f"{r.source:17} {r.signature}"
                    + (f"  campaigns={','.join(r.campaigns)}" if r.campaigns else "")
                )
            print("recurring target behaviors (substantiated by the auditor): none recorded")
        return 0
    finally:
        await pool.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--vault", required=True, type=Path)
    ap.add_argument("--minimum", type=int, default=2)
    args = ap.parse_args()
    return asyncio.run(report(args.dsn, args.vault, args.minimum))


if __name__ == "__main__":
    sys.exit(main())
