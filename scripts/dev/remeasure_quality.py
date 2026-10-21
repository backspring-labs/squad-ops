"""Prediction 4's reading (SIP-0113 §7; #2416): re-measure one cycle's unchanged tree, and report each
quality measure's spread.

The tree is the one the evaluation service reads for the cycle (``evaluated_tree_refs``), started
the way the service starts it, and measured by the same runner call with no scenarios: Lighthouse
and axe on the delivery's own declared pages, and #1937's lint. Nothing is written: no evaluation
record, no store row. The readings and the spread (``squadops.outcomes.quality_spread``) go to
stdout as JSON, for the window's record.

Runs in the runtime image as root, with the runtime's own config, and through its sandbox client:

    docker exec -i -u root squadops-runtime-api python - CYCLE_ID [TIMES] \\
        < scripts/dev/remeasure_quality.py > var/window/remeasure-CYCLE_ID.json

TIMES is how many re-measures (at least 2; 3 when not given). Exit 0 when every re-measure started
and the spread was read, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import json
import sys


async def main(cycle_id: str, times: int) -> int:
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
    from squadops.scenarios.evaluate import declared_pages, delivered_manifest, lint_of, quality_of

    config = load_config(secret_provider_factory=secret_provider_for)
    pool = await create_pool(
        config.db.url,
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
    pages = declared_pages(await delivered_manifest(vault, cycle), None)
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
        )
        started = started and evaluated.started
        readings.append((quality_of(pages, None, evaluated), lint_of(True, None, evaluated)))

    spread = quality_spread(readings)
    print(
        json.dumps(
            {
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
                    }
                    for q, lint in readings
                ],
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
            },
            indent=2,
        )
    )
    return 0 if started else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: remeasure_quality.py CYCLE_ID [TIMES]")
    sys.exit(asyncio.run(main(args[0], int(args[1]) if len(args) > 1 else 3)))
