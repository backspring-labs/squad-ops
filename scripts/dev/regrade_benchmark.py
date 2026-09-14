#!/usr/bin/env python3
"""Re-grade the benchmark registry from the live stores, read-only (SIP-0108 §4.3).

Reads the committed membership (``docs/benchmark/rolls.yaml``) and each set's pins, then
re-grades every declared roll from the registry and the vault. It prints the preflight (which
rolls are re-gradeable, and why the rest are not) and one line per row. With ``--write`` it
commits the capture to ``docs/benchmark/regrade.json``.

**Capture, not query.** The stores live on one box, and the release-package rule applies: the
evidence is taken where it lives and committed. The capture is what CI checks the acceptance
against (the re-graded 1.7.5 rows agree with that record's headline table). A later re-grade
replaces it deliberately, like a golden.

**Read-only, twice over.**
- The Postgres session is opened with ``default_transaction_read_only=on``, and a write is
  attempted and must be refused before anything is read.
- The vault refuses every index write. The deploy's vault index is written by the containers,
  and may be unreadable to the operator; when it is, the index is rebuilt in memory from the
  metadata files the vault itself indexes, never on disk.

Usage:
    SQUADOPS__DB__URL=postgresql://… .venv/bin/python scripts/dev/regrade_benchmark.py \\
        --vault data/artifacts [--write]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from adapters.cycles.benchmark_regrade import regrade  # noqa: E402
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault  # noqa: E402
from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry  # noqa: E402
from adapters.persistence.pool import create_pool  # noqa: E402
from squadops._version import resolve_version  # noqa: E402
from squadops.cycles.benchmark_registry import (  # noqa: E402
    BENCHMARK_REGISTRY_VERSION,
    benchmark_rolls,
    pins_configs,
    row_record,
)
from squadops.cycles.cycle_assessment import ASSESSMENT_VERSION, AssessorIdentity  # noqa: E402
from squadops.cycles.failure_attribution import ATTRIBUTION_REGISTRY_VERSION  # noqa: E402

MANIFEST = REPO_ROOT / "docs" / "benchmark" / "rolls.yaml"
CAPTURE = REPO_ROOT / "docs" / "benchmark" / "regrade.json"
DSN_ENV = "SQUADOPS__DB__URL"
#: The code that grades: a capture names it, so it refuses uncommitted changes here.
GRADING_PATHS = ("src", "adapters", "docs/benchmark/rolls.yaml")
NO_RUN_SUMMARY_TABLE = "run_loop_summaries absent: migration 1500 is not applied on this deploy"


class RegistryWithoutRunSummaries(PostgresCycleRegistry):
    """A registry whose schema predates the run summary table (migration 1500).

    Such a deploy holds no run summary for any run, so every lookup answers "no row", which is
    what the assessment reads as unaskable. The absence is checked once, by name, before the
    re-grade, and recorded in the capture. No query error is swallowed."""

    async def get_run_loop_summary(self, run_id: str):
        return None


class ReadOnlyVault(FilesystemArtifactVault):
    """The filesystem vault with every index write refused."""

    _memory_index: dict[str, str] | None = None

    def _load_index(self) -> dict[str, str]:
        try:
            return super()._load_index()
        except PermissionError:
            if self._memory_index is None:
                self._memory_index = {
                    meta.parent.name: str(meta.parent.relative_to(self._base_dir))
                    for meta in self._base_dir.rglob("metadata.json")
                }
            return self._memory_index

    def _save_index(self, index: dict[str, str]) -> None:
        raise RuntimeError("the benchmark re-grade never writes the vault")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def grading_sha() -> str:
    """HEAD, marked ``-dirty`` when the grading code has uncommitted changes."""
    sha = _git("rev-parse", "--short", "HEAD")
    return f"{sha}-dirty" if _git("status", "--porcelain", "--", *GRADING_PATHS) else sha


def load_rolls():
    manifest = yaml.safe_load(MANIFEST.read_text())
    configs = {
        path: yaml.safe_load((REPO_ROOT / path).read_text()) for path in pins_configs(manifest)
    }
    return benchmark_rolls(manifest, configs)


async def _read_only_registry(dsn: str):
    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    async with pool.acquire() as conn:
        try:
            await conn.execute("CREATE TEMP TABLE _benchmark_read_only_probe (x int)")
        except Exception as exc:  # noqa: BLE001 - any refusal proves the session read-only
            print(f"session read-only: the probe write was refused ({type(exc).__name__})")
        else:
            await pool.close()
            raise SystemExit("the session accepted a write; refusing to read through it")
        has_run_summaries = await conn.fetchval("SELECT to_regclass('run_loop_summaries')")
    if has_run_summaries is None:
        return pool, RegistryWithoutRunSummaries(pool), [NO_RUN_SUMMARY_TABLE]
    return pool, PostgresCycleRegistry(pool), []


def capture(rows, assessor: AssessorIdentity, store_notes: list[str]) -> dict:
    return {
        "benchmark_registry_version": BENCHMARK_REGISTRY_VERSION,
        "assessment_version": ASSESSMENT_VERSION,
        "attribution_registry_version": ATTRIBUTION_REGISTRY_VERSION,
        "assessor": {
            "framework_version": assessor.framework_version,
            "git_sha": assessor.git_sha,
        },
        "store_notes": store_notes,
        "preflight": {
            "declared": len(rows),
            "by_role": dict(Counter(str(r.roll.role) for r in rows)),
            "gradeable": sum(r.preflight.gradeable for r in rows),
            "refused_by_reason": dict(
                Counter(str(reason) for r in rows for reason in r.preflight.refusals)
            ),
        },
        "rows": [row_record(r) for r in rows],
    }


def _line(record: dict) -> str:
    head = f"{record['set']:<22} {record['role']:<7} {record['roll']:>2} {record['cycle_id']}"
    if not record["gradeable"]:
        return f"{head}  REFUSED {', '.join(record['refusals'])}: {'; '.join(record['refusal_detail'])}"
    ind = record["assessment"]["indicators"]
    crit = ind["criteria_coverage"].get("value") or {}
    attribution = record["assessment"]["attribution"]
    return (
        f"{head}  {ind['verdict'].get('value')!s:<18} "
        f"{crit.get('verified')}/{crit.get('total')}  rounds {ind['correction_rounds'].get('value')}"
        f"  attribution {attribution.get('primary', attribution['state'])}"
        f"  unresolved {len(record['unresolved_refs'])}"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--vault", required=True, help="the deploy's artifact vault directory")
    parser.add_argument(
        "--write", action="store_true", help=f"write {CAPTURE.relative_to(REPO_ROOT)}"
    )
    args = parser.parse_args()

    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        raise SystemExit(f"{DSN_ENV} is required: the registry this re-grade reads")
    assessor = AssessorIdentity(framework_version=resolve_version(), git_sha=grading_sha())
    if args.write and assessor.git_sha.endswith("-dirty"):
        raise SystemExit("refusing --write: the grading code has uncommitted changes")

    rolls = load_rolls()
    pool, registry, store_notes = await _read_only_registry(dsn)
    try:
        rows = await regrade(registry, ReadOnlyVault(args.vault), rolls, assessor=assessor)
    finally:
        await pool.close()

    document = capture(rows, assessor, store_notes)
    for record in document["rows"]:
        print(_line(record))
    print(json.dumps({"store_notes": store_notes, **document["preflight"]}, indent=1))
    if args.write:
        CAPTURE.write_text(json.dumps(document, indent=1, sort_keys=False) + "\n")
        print(f"wrote {CAPTURE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
