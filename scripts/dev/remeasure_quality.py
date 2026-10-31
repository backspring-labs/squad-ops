"""Prediction 4's reading (SIP-0113 §7; #2416): re-measure one cycle's unchanged tree, and report each
quality measure's spread.

The tree is the one the evaluation service reads for the cycle (``evaluated_tree_refs``), started
the way the service starts it, and measured by the same runner call with no scenarios: Lighthouse
and axe on the delivery's own declared pages, and #1937's lint. It also takes §10j's seeded reading:
a second instance, seeded from the Project's declared quality seed and measured on every page
(SIP-0113 §10n). The readings and each one's spread (``squadops.outcomes.quality_spread``) go to
stdout as JSON, for the window's record.

**Nothing is written** unless ``--record PROVENANCE`` names the series. Then each re-measure is
written as a ``quality_remeasures`` row (§10n ruling 1) against the cycle's latest evaluation,
through a pool opened for that alone, after measuring. Never an evaluation record: a re-measure
there would replace the cycle's real record in every package rebuilt after.

Runs in the runtime image as root, with the runtime's own config, and through its sandbox client:

    docker exec -i -u root squadops-runtime-api python - CYCLE_ID [TIMES] [--record PROVENANCE] \\
        [--fault "$(cat SPEC.json)"] < scripts/dev/remeasure_quality.py \\
        > var/window/remeasure-CYCLE_ID.json

TIMES is how many re-measures (at least 2; 3 when not given). Exit 0 when every re-measure started
and the spread was read, 1 otherwise.

``--fault SPEC`` is §10y's positive control (#1251's rule): a diagnostic, never a reading. The
cycle's tree is changed by the spec's edits before it is started, each replacing the one occurrence
of its ``old`` text in a file of the tree, and a spec that doesn't apply is refused before anything
runs. Each round measures the tree the edits were made to, then the faulted tree, through the same
runner call, and the output compares round n with round n (``fault_deltas``). The output names it a
diagnostic, under the faulted tree's own identity, with the tree it was made from. Nothing is
written to the store: ``--record`` with ``--fault`` is refused, since a faulted reading filed
against the cycle's evaluation would join its series.

    SPEC = {"diagnostic": "<what it injects>", "edits": [{"path", "old", "new"}]}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

USAGE = "remeasure_quality.py CYCLE_ID [TIMES] [--record PROVENANCE | --fault SPEC_JSON]"


def faulted_tree(tree: Mapping[str, bytes], edits: Sequence[Mapping[str, str]]) -> dict[str, bytes]:
    """``tree`` with ``edits`` applied in order. Refused when an edit's path isn't in the tree, or
    its ``old`` text isn't in the file exactly once."""
    out = dict(tree)
    for edit in edits:
        path, old = edit["path"], edit["old"].encode()
        if path not in out:
            raise ValueError(f"{path} isn't in the tree")
        found = out[path].count(old) if old else 0
        if found != 1:
            raise ValueError(f"an edit's text must occur once in {path}; it occurs {found} times")
        out[path] = out[path].replace(old, edit.get("new", "").encode())
    return out


def _fault_spec(text: str) -> dict:
    spec = json.loads(text)
    edits = spec.get("edits") if isinstance(spec, dict) else None
    if (
        not isinstance(spec, dict)
        or not spec.get("diagnostic")
        or not edits
        or not all(isinstance(e, dict) and e.get("path") and e.get("old") for e in edits)
    ):
        raise argparse.ArgumentTypeError(
            "a fault names its diagnostic and its edits, each with a path and old text"
        )
    return spec


def _spreads(read: Any) -> list[dict]:
    return [
        {"measure": s.measure, "page": s.page, "values": list(s.values), "spread": s.spread}
        for s in read.spreads
    ]


def _failing_spreads(read: Any) -> list[dict]:
    """§10y's failing-id lists across the rounds, for S1: each round's list and whether all agree."""
    return [
        {
            "measure": f.measure,
            "page": f.page,
            "values": [list(v) if v is not None else None for v in f.values],
            "stable": f.stable,
        }
        for f in read.failing
    ]


def _fault_round(read: Any) -> dict:
    """One round's faulted tree against the tree it was made from: every measure compared, moved
    or not, since the control predicts exact values."""
    return {
        "made_from": read.against_tree,
        "deltas": [[d.measure, d.page, d.before, d.after, d.delta] for d in read.deltas],
        "failing": [
            [f.measure, f.page, list(f.introduced), list(f.resolved)] for f in read.failing
        ],
        "not_compared": [list(pair) for pair in read.not_compared],
    }


async def readings_of(
    runner: Any,
    tree: Mapping[str, bytes],
    *,
    stack: str | None,
    pages: tuple[str, ...],
    planned: Any,
    plan: Any,
    times: int,
    fault: Mapping[str, Any] | None = None,
) -> tuple[dict, list, bool]:
    """``times`` re-measures of ``tree`` through the runner's own call, or with ``fault``, of the
    faulted tree beside the tree it was made from, round by round. The output's document, the
    readings a ``--record`` writes, and whether every instance started."""
    from squadops.campaigns.evaluator_trees import FileTree
    from squadops.outcomes.quality_deltas import diagnostic_deltas
    from squadops.outcomes.quality_spread import quality_spread
    from squadops.scenarios.evaluate import lint_of, quality_of, seeded_of

    identity = FileTree.of(tree).identity
    faulted = faulted_tree(tree, fault["edits"]) if fault is not None else None
    measured = FileTree.of(faulted).identity if faulted is not None else identity

    async def once(files: Mapping[str, bytes], tree_identity: str) -> tuple:
        evaluated = await runner.evaluate_tree(
            tree=dict(files),
            tree_identity=tree_identity,
            executable=(),
            stack=stack,
            declared=None,
            scenarios=[],
            environment={},
            pages=pages,
            **({"seed": plan} if plan is not None else {}),
        )
        reading = (
            quality_of(pages, None, evaluated),
            lint_of(True, None, evaluated),
            seeded_of(planned, None, evaluated),
        )
        return reading, evaluated.started

    readings: list = []
    made_from: list = []
    started = True
    for _ in range(times):
        if faulted is not None:
            base, up = await once(tree, identity)
            made_from.append(base)
            started = started and up
        reading, up = await once(faulted if faulted is not None else tree, measured)
        readings.append(reading)
        started = started and up

    spread = quality_spread([(q, lint) for q, lint, _ in readings])
    seeded_spread = quality_spread([(s, None) for _, _, s in readings])
    doc: dict[str, Any] = {
        "tree_identity": measured,
        "re_measures": spread.readings,
        "evaluator": spread.evaluator,
        "readings": [
            {
                "quality": q.as_dict() if q else None,
                "lint": lint.as_dict() if lint else None,
                "quality_seeded": s.as_dict() if s else None,
            }
            for q, lint, s in readings
        ],
        "seeded_spreads": _spreads(seeded_spread),
        "seeded_failing_spreads": _failing_spreads(seeded_spread),
        "seeded_not_compared": [list(pair) for pair in seeded_spread.not_compared],
        "spreads": _spreads(spread),
        "failing_spreads": _failing_spreads(spread),
        "not_compared": [list(pair) for pair in spread.not_compared],
    }
    if fault is not None:
        doc["diagnostic"] = {
            "what": fault["diagnostic"],
            "made_from": identity,
            "edited": sorted({e["path"] for e in fault["edits"]}),
        }
        doc["made_from_readings"] = [
            {"quality": q.as_dict() if q else None, "quality_seeded": s.as_dict() if s else None}
            for q, _, s in made_from
        ]
        doc["fault_deltas"] = [
            _fault_round(diagnostic_deltas((q, s), (bq, bs), made_from_tree=identity))
            for (q, _, s), (bq, _, bs) in zip(readings, made_from, strict=True)
        ]
    return doc, readings, started


async def record_remeasures(
    store: Any, cycle: Any, identity: str, provenance: str, readings: list, measured_at: Any
) -> list:
    """Each re-measure written as its own row (§10n ruling 1), against the cycle's latest
    evaluation: the tree the evaluation read, or nothing is written. Refused when the cycle has no
    evaluation to re-measure, or when the tree measured isn't the one it evaluated."""
    from squadops.scenarios.evaluation import QualityRemeasure, new_remeasure_id

    evaluations = await store.evaluations_for_cycle(cycle.cycle_id)
    if not evaluations:
        raise ValueError(f"{cycle.cycle_id} has no evaluation to re-measure")
    evaluation = max(evaluations, key=lambda r: r.evaluated_at)
    if evaluation.evaluated_tree_identity != identity:
        raise ValueError(
            f"{cycle.cycle_id}'s evaluation read {evaluation.evaluated_tree_identity}, and this "
            f"re-measured {identity}"
        )
    written = [
        QualityRemeasure(
            remeasure_id=new_remeasure_id(),
            evaluation_id=evaluation.evaluation_id,
            project_id=evaluation.project_id,
            campaign_id=evaluation.campaign_id,
            cycle_id=cycle.cycle_id,
            evaluated_tree_identity=identity,
            previous_accepted_tree_identity=evaluation.previous_accepted_tree_identity,
            provenance=provenance,
            round=n,
            measured_at=measured_at,
            quality=quality,
            lint=lint,
            quality_seeded=seeded,
        )
        for n, (quality, lint, seeded) in enumerate(readings, start=1)
    ]
    for remeasure in written:
        await store.save_remeasure(remeasure)
    return written


async def main(
    cycle_id: str, times: int, record: str | None = None, fault: Mapping[str, Any] | None = None
) -> int:
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.persistence.pool import create_pool
    from adapters.persistence.transient import TransientRetry
    from adapters.sandbox.factory import create_scenario_runner
    from squadops.bootstrap.secrets import secret_provider_for
    from squadops.campaigns.evaluator_trees import FileTree
    from squadops.campaigns.increment_tree import evaluated_tree_refs
    from squadops.config.loader import load_config
    from squadops.config.schema import DBRetryConfig
    from squadops.scenarios.evaluate import declared_pages, delivered_manifest, planned_seed

    if record and fault is not None:
        raise ValueError("a diagnostic is never a reading: --fault writes nothing, so no --record")

    config = load_config(secret_provider_factory=secret_provider_for)
    pool = await create_pool(
        config.database().url,
        min_size=1,
        max_size=2,
        server_settings={"default_transaction_read_only": "on"},
    )
    try:
        cycle = await PostgresCycleRegistry(
            pool=pool, retry=TransientRetry.of(DBRetryConfig())
        ).get_cycle(cycle_id)
    finally:
        await pool.close()
    vault = FilesystemArtifactVault(base_dir="/app/data/artifacts")
    refs = await evaluated_tree_refs(vault, cycle)
    tree = {path: (await vault.retrieve(art))[1] for path, art in refs.items()}
    identity = FileTree.of(tree).identity
    manifest = await delivered_manifest(vault, cycle)
    pages = declared_pages(manifest, None)
    # §10j, §10n: the seeded reading beside §10f's, planned as the evaluation plans it.
    planned, plan = planned_seed(cycle.project_id, manifest, blueprint=True, serves_pages=True)
    stack = cycle.resolved_config().get("build_profile")
    runner = create_scenario_runner(config.sandbox_client)
    if runner is None:
        print(json.dumps({"cycle_id": cycle_id, "error": "the deploy has no scenario runner"}))
        return 1

    read, readings, started = await readings_of(
        runner,
        tree,
        stack=stack,
        pages=pages,
        planned=planned,
        plan=plan,
        times=times,
        fault=fault,
    )
    doc = {"cycle_id": cycle_id, "stack": stack, "pages": list(pages), **read}
    if record and started and fault is None:
        from datetime import UTC, datetime

        from adapters.scenarios.postgres_scenario_store import PostgresScenarioStore

        # Opened only now, after measuring, for the re-measure rows alone.
        writer = await create_pool(config.database().url, min_size=1, max_size=1)
        try:
            written = await record_remeasures(
                PostgresScenarioStore(writer), cycle, identity, record, readings, datetime.now(UTC)
            )
        finally:
            await writer.close()
        doc["recorded"] = {"provenance": record, "remeasures": [r.remeasure_id for r in written]}
    print(json.dumps(doc, indent=2))
    return 0 if started else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage=USAGE)
    parser.add_argument("cycle_id", nargs="?")
    parser.add_argument("times", nargs="?", type=int, default=3)
    parser.add_argument("--record", default=None)
    parser.add_argument("--fault", type=_fault_spec, default=None)
    args = parser.parse_args()
    if not args.cycle_id:
        sys.exit(f"usage: {USAGE}")
    if args.record and args.fault is not None:
        parser.error("a diagnostic is never a reading: --fault writes nothing, so no --record")
    sys.exit(asyncio.run(main(args.cycle_id, args.times, args.record, args.fault)))
