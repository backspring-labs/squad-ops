#!/usr/bin/env python3
"""The convergence replay (#1764) — the command line.

    SQUADOPS__DB__URL=postgresql://… .venv/bin/python scripts/dev/convergence_replay/cli.py \\
        corpus --vault data/artifacts --out var/convergence-replay/corpus.jsonl

``corpus`` enumerates the stored failing rounds a replay can start from and writes one JSON line
per round, then prints what it refused and why. **Read-only, twice over**, as
``regrade_benchmark.py`` reads the stores: the Postgres session is opened read-only and a write is
attempted and must be refused before anything is read, and nothing is written to the vault.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

from bundle import RefusingQueue, build_bundle  # noqa: E402
from corpus import (  # noqa: E402
    ArtifactMeta,
    Round,
    correction_rounds,
    failed_task_artifacts,
    failures_from_summary,
    join_failures_to_rounds,
    preceding_checkpoint,
)
from read_only_vault import ReadOnlyVault  # noqa: E402

from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry  # noqa: E402
from adapters.persistence.pool import create_pool  # noqa: E402

DSN_ENV = "SQUADOPS__DB__URL"


async def _read_only_pool(dsn: str):
    pool = await create_pool(
        dsn, min_size=1, max_size=2, server_settings={"default_transaction_read_only": "on"}
    )
    async with pool.acquire() as conn:
        try:
            await conn.execute("CREATE TEMP TABLE _convergence_replay_probe (x int)")
        except Exception:  # noqa: BLE001 - any refusal proves the session read-only
            pass
        else:
            await pool.close()
            raise SystemExit("the session accepted a write; refusing to read through it")
    return pool


def _run_artifacts(vault: Path, project: str, cycle: str, run: str) -> list[ArtifactMeta]:
    out = []
    for meta_path in sorted((vault / project / cycle / run).glob("*/metadata.json")):
        meta = json.loads(meta_path.read_text())
        out.append(ArtifactMeta.from_metadata(meta, str(meta_path.parent / meta["filename"])))
    return out


def _provenance(records_root: Path) -> dict[str, tuple[str, str]]:
    """cycle id → (set, role), from the verification-set records the driver wrote."""
    seen: dict[str, tuple[str, str]] = {}
    for record in records_root.glob("*/*.json"):
        try:
            data = json.loads(record.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        cycle = data.get("cycle_id") if isinstance(data, dict) else None
        if cycle:
            role = record.name.split("-")[0]  # roll / shakeout / chain
            seen.setdefault(cycle, (record.parent.name, role))
    return seen


def _stack(cycle) -> str | None:
    return (cycle.execution_overrides or {}).get("build_profile") or (
        cycle.applied_defaults or {}
    ).get("build_profile")


async def build_corpus(dsn: str, vault: Path, records_root: Path) -> tuple[list[Round], dict]:
    pool = await _read_only_pool(dsn)
    registry = PostgresCycleRegistry(pool)
    refused: collections.Counter[str] = collections.Counter()
    kept_paths: collections.Counter[str] = collections.Counter()
    provenance = _provenance(records_root)
    rounds: list[Round] = []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT run_id, summary FROM run_loop_summaries "
                "WHERE jsonb_array_length(coalesce(summary->'round_failures','[]'::jsonb)) > 0 "
                "ORDER BY recorded_at"
            )
        for row in rows:
            run = await registry.get_run(row["run_id"])
            cycle = await registry.get_cycle(run.cycle_id)
            artifacts = _run_artifacts(vault, cycle.project_id, cycle.cycle_id, run.run_id)
            joined = join_failures_to_rounds(
                failures_from_summary(row["summary"]), correction_rounds(artifacts)
            )
            if isinstance(joined, str):
                refused["run's failures and correction rounds do not pair one to one"] += 1
                continue
            checkpoints = [
                (c.checkpoint_index, c.created_at)
                for c in await registry.list_checkpoints(run.run_id)
            ]
            for failure, cround in joined:
                decision = json.loads(Path(cround.decision.path).read_text())
                path = decision.get("correction_path")
                kept_paths[str(path)] += 1
                if path != "patch":
                    refused[f"decision {path}"] += 1
                    continue
                before = cround.analysis.created_at
                rounds.append(
                    Round(
                        project_id=cycle.project_id,
                        cycle_id=cycle.cycle_id,
                        run_id=run.run_id,
                        stack=_stack(cycle),
                        failure=failure,
                        correction_path=path,
                        analysis_id=cround.analysis.artifact_id,
                        decision_id=cround.decision.artifact_id,
                        failed_artifact_ids=failed_task_artifacts(
                            artifacts, failure.task_id, before
                        ),
                        checkpoint_index=preceding_checkpoint(checkpoints, before),
                        provenance=provenance.get(cycle.cycle_id),
                    )
                )
    finally:
        await pool.close()
    return rounds, {"summaries": len(rows), "decisions": dict(kept_paths), "refused": dict(refused)}


async def build_bundles(dsn: str, vault_dir: Path, corpus: Path, out: Path) -> dict:
    """One bundle per corpus round, rebuilt by the executor's own loaders (``bundle.py``)."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
    from adapters.cycles.postgres_squad_profile import PostgresSquadProfile

    pool = await _read_only_pool(dsn)
    registry = PostgresCycleRegistry(pool)
    vault = ReadOnlyVault(vault_dir)
    profiles = PostgresSquadProfile(pool=pool)
    from adapters.cycles.factory import create_project_registry

    executor = DispatchedFlowExecutor(
        # The PRD file resolver reads the project registry the runtime reads (config).
        project_registry=create_project_registry("config"),
        cycle_registry=registry,
        artifact_vault=vault,
        queue=RefusingQueue(),
        squad_profile=profiles,
        task_timeout=1800.0,
    )
    out.mkdir(parents=True, exist_ok=True)
    tally: collections.Counter[str] = collections.Counter()
    try:
        for line in corpus.read_text().splitlines():
            row = json.loads(line)
            key = f"{row['run_id']}-{row['analysis_id']}"
            try:
                bundle = await build_bundle(
                    row, executor=executor, registry=registry, vault=vault, profiles=profiles
                )
            except Exception as exc:  # noqa: BLE001 - a round that cannot be rebuilt is counted, by type
                tally[f"error: {type(exc).__name__}: {str(exc)[:80]}"] += 1
                continue
            if isinstance(bundle, str):
                tally[bundle] += 1
                continue
            (out / f"{key}.json").write_text(bundle.to_json())
            tally["bundled"] += 1
    finally:
        await pool.close()
    return dict(tally)


def run_replay(work: Path, selection: list[str], samples: int, main_checkout: Path) -> int:
    """The registered sample, arms alternating round by round (scoped, then whole-file), each a
    one-off of the qa service: an arm is a process-wide choice, so it is never shared."""
    import subprocess

    harness = Path(__file__).resolve().parent
    for bundle in selection:
        for arm in ("scoped", "whole_file"):
            cmd = [
                "docker", "compose", "run", "--rm", "--no-deps", "-T",
                "-v", f"{harness}:/replay:ro", "-v", f"{work}:/out",
                "eve", "python", "/replay/container.py", "replay",
                "--bundles", "/out/bundles", "--admission", "/out/admission.jsonl",
                "--arm", arm, "--samples", str(samples), "--out", "/out/replay.jsonl",
                "--only", bundle,
            ]  # fmt: skip
            code = subprocess.call(cmd, cwd=main_checkout)
            print(json.dumps({"bundle": bundle, "arm": arm, "exit": code}), flush=True)
    return 0


def report(replay: Path, bundles: Path) -> dict:
    """Per arm and stack: acceptance, regressions, the change a response makes against its size,
    empty responses, time and tokens. Counts, never rates alone (the small-N rule)."""
    stacks = {
        p.name: (json.loads(p.read_text()).get("resolved_config") or {}).get("build_profile")
        for p in bundles.glob("*.json")
    }
    out: dict = {}
    for line in replay.read_text().splitlines():
        r = json.loads(line)
        if r.get("stub"):
            continue
        key = f"{r['arm']} / {stacks.get(r['bundle'])}"
        cell = out.setdefault(
            key,
            {"samples": 0, "accepted": 0, "unrunnable": 0, "empty": 0, "with_regressions": 0,
             "emitted_chars": [], "changed_lines": [], "repair_seconds": []},
        )  # fmt: skip
        cell["samples"] += 1
        if r.get("verdict") == "unrunnable":
            cell["unrunnable"] += 1
            continue
        cell["accepted"] += bool(r.get("accepted"))
        cell["empty"] += bool(r.get("empty"))
        cell["with_regressions"] += bool(r.get("regressions"))
        cell["emitted_chars"].append(r.get("emitted_chars"))
        cell["changed_lines"].append(r.get("changed_lines"))
        cell["repair_seconds"].append(r.get("repair_seconds"))
    for cell in out.values():
        for k in ("emitted_chars", "changed_lines", "repair_seconds"):
            vals = sorted(v for v in cell[k] if v is not None)
            cell[k] = {"median": vals[len(vals) // 2] if vals else None, "n": len(vals)}
    return out


def main(argv: list[str] | None = None) -> int:
    os.chdir(REPO_ROOT)  # the projects' PRD paths are repository-relative
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("corpus", help="enumerate the stored failing rounds a replay can start from")
    p.add_argument("--vault", type=Path, default=REPO_ROOT / "data" / "artifacts")
    p.add_argument("--records", type=Path, default=REPO_ROOT / "var" / "verification_sets")
    p.add_argument("--out", type=Path, required=True)
    b = sub.add_parser("bundle", help="rebuild each corpus round's inputs by the product's code")
    b.add_argument("--vault", type=Path, default=REPO_ROOT / "data" / "artifacts")
    b.add_argument("--corpus", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True, help="a directory, one JSON per round")
    rr = sub.add_parser("run", help="replay the registered sample, arms alternating per round")
    rr.add_argument(
        "--work", type=Path, required=True, help="bundles/, admission.jsonl, replay.jsonl"
    )
    rr.add_argument("--selection", type=Path, required=True, help="one bundle file name per line")
    rr.add_argument("--samples", type=int, default=3)
    rr.add_argument("--main-checkout", type=Path, required=True, help="where docker compose runs")
    rp = sub.add_parser("report", help="summarize the replay per arm and stack")
    rp.add_argument("--work", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.command == "run":
        selection = [s.strip() for s in args.selection.read_text().splitlines() if s.strip()]
        return run_replay(args.work, selection, args.samples, args.main_checkout)
    if args.command == "report":
        summary = report(args.work / "replay.jsonl", args.work / "bundles")
        print(json.dumps(summary, indent=2))
        return 0
    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        raise SystemExit(f"{DSN_ENV} is required: the registry the replay reads")
    if args.command == "bundle":
        print(
            json.dumps(asyncio.run(build_bundles(dsn, args.vault, args.corpus, args.out)), indent=2)
        )
        return 0
    rounds, tally = asyncio.run(build_corpus(dsn, args.vault, args.records))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r.as_row(), default=str) + "\n" for r in rounds))
    print(json.dumps({"rounds": len(rounds), **tally}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
