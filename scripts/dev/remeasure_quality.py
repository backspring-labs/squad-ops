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
        < scripts/dev/remeasure_quality.py > var/window/remeasure-CYCLE_ID.json

TIMES is how many re-measures (at least 2; 3 when not given). Exit 0 when every re-measure started
and the spread was read, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any


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


async def main(cycle_id: str, times: int, record: str | None = None) -> int:
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
    from squadops.outcomes.quality_spread import quality_spread
    from squadops.scenarios.evaluate import (
        declared_pages,
        delivered_manifest,
        lint_of,
        planned_seed,
        quality_of,
        seeded_of,
    )

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

    readings, started = [], True
    for _ in range(times):
        evaluated = await runner.evaluate_tree(
            tree=tree,
            tree_identity=identity,
            executable=(),
            stack=stack,
            declared=None,
            scenarios=[],
            environment={},
            pages=pages,
            **({"seed": plan} if plan is not None else {}),
        )
        started = started and evaluated.started
        readings.append(
            (
                quality_of(pages, None, evaluated),
                lint_of(True, None, evaluated),
                seeded_of(planned, None, evaluated),
            )
        )

    spread = quality_spread([(q, lint) for q, lint, _ in readings])
    seeded_spread = quality_spread([(s, None) for _, _, s in readings])
    doc = {
        "cycle_id": cycle_id,
        "tree_identity": identity,
        "stack": stack,
        "pages": list(pages),
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
        "seeded_spreads": [
            {"measure": x.measure, "page": x.page, "values": list(x.values), "spread": x.spread}
            for x in seeded_spread.spreads
        ],
        "seeded_not_compared": [list(pair) for pair in seeded_spread.not_compared],
        "spreads": [
            {
                "measure": s.measure,
                "page": s.page,
                "values": list(s.values),
                "spread": s.spread,
            }
            for s in spread.spreads
        ],
        "not_compared": [list(pair) for pair in spread.not_compared],
    }
    if record and started:
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
    parser = argparse.ArgumentParser(
        usage="remeasure_quality.py CYCLE_ID [TIMES] [--record PROVENANCE]"
    )
    parser.add_argument("cycle_id", nargs="?")
    parser.add_argument("times", nargs="?", type=int, default=3)
    parser.add_argument("--record", default=None)
    args = parser.parse_args()
    if not args.cycle_id:
        sys.exit("usage: remeasure_quality.py CYCLE_ID [TIMES] [--record PROVENANCE]")
    sys.exit(asyncio.run(main(args.cycle_id, args.times, args.record)))
