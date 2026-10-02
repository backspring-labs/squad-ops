#!/usr/bin/env python3
"""Every stored cycle's attribution, as canonical JSON, read-only (SIP-0109 §18 step 1a, #1710).

A change to how the attribution is computed proves itself behaviour-neutral by running this on
the tree before the change and the tree after, against the same registry and vault, and diffing
the two outputs:

    PYTHONPATH=<tree>/src:<tree> python scripts/dev/attribution_snapshot.py \\
        --dsn "$DSN" --vault <checkout>/data/artifacts > attribution-<tree>.json

Each cycle's outcome and evidence are assembled exactly as the assessment route assembles them
(``adapters.cycles.cycle_evidence.assess_cycle``), through the runtime's own adapters. The database
session is read-only (``default_transaction_read_only``), so the script cannot write the registry.
A cycle whose evidence cannot be assembled is reported with its error, never skipped: a snapshot
that silently drops cycles would compare equal while proving nothing about them.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from pathlib import Path


def _jsonable(reading) -> dict:
    return json.loads(json.dumps(dataclasses.asdict(reading), sort_keys=True, default=str))


async def snapshot(dsn: str, vault_dir: Path) -> dict[str, dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # the guard sits beside this script
    from _evidence_read_guard import UnreadableEvidence, require_readable_vault

    from adapters.cycles.cycle_evidence import assemble_cycle_evidence
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.persistence.pool import create_pool
    from squadops.cycles.cycle_assessment import AssessorIdentity, assess
    from squadops.cycles.cycle_outcome import resolve_cycle_outcome

    require_readable_vault(vault_dir)
    unreadable = UnreadableEvidence()

    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    try:
        registry = PostgresCycleRegistry(pool=pool)
        vault = FilesystemArtifactVault(base_dir=vault_dir)
        assessor = AssessorIdentity(framework_version="snapshot", git_sha="snapshot")
        async with pool.acquire() as conn:
            cycle_ids = [
                r["cycle_id"]
                for r in await conn.fetch(
                    "SELECT cycle_id FROM cycle_registry ORDER BY created_at, cycle_id"
                )
            ]
        out: dict[str, dict] = {}
        for cycle_id in cycle_ids:
            unreadable.reset()
            try:
                outcome = await resolve_cycle_outcome(registry, cycle_id)
                evidence = await assemble_cycle_evidence(registry, vault, cycle_id)
                out[cycle_id] = _jsonable(assess(outcome, evidence, assessor=assessor).attribution)
            except Exception as exc:  # noqa: BLE001 — reported per cycle, never dropped
                out[cycle_id] = {"error": f"{type(exc).__name__}: {exc}"}
            missed = unreadable.reset()
            if missed:
                # An attribution read with artifacts missing is not this cycle's attribution.
                out[cycle_id] = {"error": f"evidence unreadable: {len(missed)} artifact(s)"}
        return out
    finally:
        await pool.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", required=True, help="the registry's DSN (opened read-only)")
    ap.add_argument("--vault", required=True, type=Path, help="the artifact vault's directory")
    args = ap.parse_args(argv)
    result = asyncio.run(snapshot(args.dsn, args.vault))
    json.dump(result, sys.stdout, sort_keys=True, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
