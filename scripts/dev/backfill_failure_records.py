#!/usr/bin/env python3
"""Backfill the failure records of every stored cycle that ended before they existed (SIP-0109
§14, criterion 12d, §24a item 4; #1710).

For each cycle with no record set whose last run has ended, this runs the same function a
cycle's ending runs (``record_cycle_failures``), so the records come from the one producer. It
then proves criterion 12d on every cycle it wrote: the attribution recomputed from the persisted
records equals the one computed before the write.

Dry run by default: it reports what it would write and writes nothing. ``--write`` needs
``--backup-file``, naming the dump taken for this run (``scripts/dev/ops/backup_db.sh``). A
write without one is refused, because the records are append-only and a wrong set cannot be
deleted, only superseded.

    PYTHONPATH=<tree>/src:<tree> python scripts/dev/backfill_failure_records.py \\
        --dsn "$DSN" --vault <checkout>/data/artifacts [--write --backup-file <dump>]
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from pathlib import Path


def _canonical(reading) -> str:
    return json.dumps(dataclasses.asdict(reading), sort_keys=True, default=str)


async def backfill(dsn: str, vault_dir: Path, *, write: bool) -> dict:
    from adapters.cycles.cycle_evidence import assess_cycle, record_cycle_failures
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.persistence.pool import create_pool
    from squadops.cycles.cycle_assessment import AssessorIdentity

    if not (vault_dir / "_index.json").is_file():
        raise SystemExit(
            f"no vault index at {vault_dir}: refusing to construct a vault that writes"
        )

    settings = {} if write else {"default_transaction_read_only": "on"}
    pool = await create_pool(dsn, min_size=1, max_size=2, server_settings=settings)
    assessor = AssessorIdentity(framework_version="backfill", git_sha="backfill")
    report: dict = {"written": [], "skipped_recorded": 0, "skipped_not_ended": [], "mismatch": []}
    try:
        registry = PostgresCycleRegistry(pool=pool)
        vault = FilesystemArtifactVault(base_dir=vault_dir)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT c.cycle_id, "
                "(SELECT r.run_id FROM cycle_runs r WHERE r.cycle_id = c.cycle_id "
                " ORDER BY r.run_number DESC LIMIT 1) AS last_run_id "
                "FROM cycle_registry c ORDER BY c.created_at, c.cycle_id"
            )
        for row in rows:
            cycle_id, last_run_id = row["cycle_id"], row["last_run_id"]
            if await registry.get_failure_records(cycle_id) is not None:
                report["skipped_recorded"] += 1
                continue
            if last_run_id is None:
                report["skipped_not_ended"].append(cycle_id)
                continue
            before = (await assess_cycle(registry, vault, cycle_id, assessor=assessor)).attribution
            if not write:
                report["written"].append({"cycle_id": cycle_id, "would_write": True})
                continue
            records = await record_cycle_failures(registry, vault, cycle_id, last_run_id)
            if records is None:
                report["skipped_not_ended"].append(cycle_id)
                continue
            after = (await assess_cycle(registry, vault, cycle_id, assessor=assessor)).attribution
            entry = {"cycle_id": cycle_id, "records": len(records)}
            report["written"].append(entry)
            if _canonical(before) != _canonical(after):
                report["mismatch"].append(cycle_id)
        return report
    finally:
        await pool.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--vault", required=True, type=Path)
    ap.add_argument("--write", action="store_true", help="write the records (default: dry run)")
    ap.add_argument(
        "--backup-file", type=Path, help="the dump taken for this run (required to write)"
    )
    args = ap.parse_args(argv)
    if args.write and not (args.backup_file and args.backup_file.is_file()):
        print("refused: --write needs --backup-file naming an existing dump", file=sys.stderr)
        return 2
    report = asyncio.run(backfill(args.dsn, args.vault, write=args.write))
    summary = {
        "mode": "write" if args.write else "dry-run",
        "written": len(report["written"]),
        "records": sum(e.get("records", 0) for e in report["written"]),
        "skipped_recorded": report["skipped_recorded"],
        "skipped_not_ended": len(report["skipped_not_ended"]),
        "attribution_mismatches": report["mismatch"],
    }
    json.dump(summary, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 1 if report["mismatch"] else 0


if __name__ == "__main__":
    sys.exit(main())
