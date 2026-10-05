"""The #1943 binding replay, tracked (#1956; #1908 precondition 5).

Recomputes each applied PROMOTE's frozen-criteria statements from the deploy's stored data, through
the runtime's own lookup (``CampaignProgress._criteria_stated``), twice, and compares them with the
binding the row committed. A promotion's binding is part of its replay identity, so a lookup that
answers differently across attempts left the campaign undecided (#1943). Read-only: the registry
session is ``default_transaction_read_only`` and the vault is read in place.

Runs in the runtime image as root, with the runtime's own config (``secret://`` references
expanded):

    docker exec -i -u root squadops-runtime-api python - config /app/data/artifacts CAMPAIGN_ID \\
        < scripts/dev/campaign_binding_replay.py

Exit 0 when every promotion's binding is recomputed identically, 1 on any mismatch or no promotion.
"""

from __future__ import annotations

import asyncio
import json
import sys


def mismatches(frozen: list[dict], stated: dict[str, dict]) -> list[str]:
    """Each committed frozen criterion whose recomputed statement or surface differs, by id."""
    out = []
    for f in frozen:
        want = {k: f.get(k) for k in ("statement", "surface")}
        got = stated.get(f["criterion_id"], {})
        if got != want:
            out.append(f"{f['criterion_id']}: committed={want} recomputed={got}")
    return out


async def main(dsn: str, vault_dir: str, campaign_id: str) -> int:
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.persistence.pool import create_pool
    from squadops.campaigns.progress import CampaignProgress

    if dsn == "config":
        from squadops.bootstrap.secrets import secret_provider_for
        from squadops.config.loader import load_config

        dsn = load_config(secret_provider_factory=secret_provider_for).db.url
    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    try:
        cycles = PostgresCycleRegistry(pool=pool)
        lookup = CampaignProgress.__new__(CampaignProgress)
        lookup._vault, lookup._cycles = FilesystemArtifactVault(base_dir=vault_dir), cycles
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT seq, target, binding FROM campaign_control_log WHERE campaign_id=$1 "
                "AND operation='promote' AND outcome='applied' ORDER BY seq",
                campaign_id,
            )
        failures = 0
        for row in rows:
            binding = row["binding"]
            binding = json.loads(binding) if isinstance(binding, str) else binding
            frozen = binding.get("frozen_criteria") or []
            if not frozen:
                print(f"seq {row['seq']} {row['target']}: no frozen criteria (a calibration)")
                continue
            cycle = await cycles.get_cycle(row["target"])
            last = max(await cycles.list_runs(cycle.cycle_id), key=lambda r: r.run_number)
            for attempt in (1, 2):
                found = mismatches(frozen, await lookup._criteria_stated(cycle, last))
                failures += len(found)
                print(
                    f"seq {row['seq']} {row['target']} attempt {attempt}: "
                    + ("; ".join(found) or "SAME")
                )
        print(f"promotes {len(rows)}; mismatches {failures}")
        return 1 if failures or not rows else 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(*sys.argv[1:4])))
