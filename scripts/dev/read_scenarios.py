"""§10p ruling 13's reading tool (SIP-0113; #2564 step 6): evaluate named cycles against a named
suite N times, each through the evaluation service's own path (``evaluate_cycle``), and write each
record with no campaign.

Writing them changes no campaign's reading. A campaign's package reads only the records of the
suite its campaign pinned (``campaign_outcomes``), and a cycle's end evaluates only against that
pin (``CampaignCycleEvaluator``). Each record names the tree its cycle built on as the cycle's own
evaluation does (``built_on_identity``).

``--fault SPEC`` adds a diagnostic, never a reading (ruling 13; #1251's rule): the spec's cycle,
its tree changed by the spec's edits, evaluated by the same path. Each edit replaces the one
occurrence of its ``old`` text in a file of the tree. The edits are applied where the tree is read
(the vault), so nothing else in the path changes, and a spec that doesn't apply is refused before
anything runs. Its records are written under the faulted tree's own identity, and the output names
them a diagnostic, with the tree they were made from.

The output (stdout, JSON) holds what a campaign's package shows of a record, with each outcome's
first failing step, runner and step seconds. Never a goal or evidence, which are held out: the
output goes to the window's records, and from there to the line's Release.

Runs in the runtime image as root, with the runtime's own config and sandbox client:

    docker exec -i -u root squadops-runtime-api python - SUITE_DIGEST [CYCLE_ID ...] \\
        [--times N] [--fault "$(cat SPEC.json)"] < scripts/dev/read_scenarios.py \\
        > var/window/<reading>.json

SPEC is ``{"diagnostic": "<what it removes>", "cycle_id": ..., "edits": [{"path", "old", "new"}]}``.
TIMES is how many evaluations of each tree (1 when not given). Exit 0 when every evaluation
started its tree, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import evaluated_tree_refs
from squadops.scenarios.campaign_cycles import built_on_identity
from squadops.scenarios.evaluate import evaluate_cycle
from squadops.scenarios.evaluation import BlockedReason, EvaluationRecord

USAGE = "read_scenarios.py SUITE_DIGEST [CYCLE_ID ...] [--times N] [--fault SPEC_JSON]"
#: The blocked reasons that say an evaluation never started its tree.
NOT_STARTED = frozenset({BlockedReason.NO_RUNNER, BlockedReason.START_FAILED})


class FaultedVault:
    """``vault`` with some of its artifacts read as ``contents`` instead: a diagnostic tree's
    edited files. Every other read passes through."""

    def __init__(self, vault: Any, contents: Mapping[str, bytes]) -> None:
        self._vault, self._contents = vault, dict(contents)

    async def retrieve(self, artifact_id: str) -> tuple[Any, bytes]:
        ref, content = await self._vault.retrieve(artifact_id)
        return ref, self._contents.get(artifact_id, content)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._vault, name)


async def faulted(
    vault: Any, cycle: Any, edits: Sequence[Mapping[str, str]]
) -> tuple[FaultedVault, str]:
    """The vault with ``cycle``'s tree read through ``edits`` in order, and the identity of the
    tree they were made from. Refused when an edit's path isn't in the tree or shares its file
    with another path, or its ``old`` text isn't in the file exactly once."""
    refs = await evaluated_tree_refs(vault, cycle)
    tree = {path: (await vault.retrieve(artifact))[1] for path, artifact in refs.items()}
    contents: dict[str, bytes] = {}
    for edit in edits:
        path, old = edit["path"], edit["old"].encode()
        artifact = refs.get(path)
        if artifact is None:
            raise ValueError(f"{path} isn't in {cycle.cycle_id}'s tree")
        if list(refs.values()).count(artifact) > 1:
            raise ValueError(f"{path} shares its file with another path, so an edit changes both")
        text = contents[artifact] if artifact in contents else tree[path]
        if not old or text.count(old) != 1:
            found = text.count(old) if old else 0
            raise ValueError(f"an edit's text must occur once in {path}; it occurs {found} times")
        contents[artifact] = text.replace(old, edit.get("new", "").encode())
    return FaultedVault(vault, contents), FileTree.of(tree).identity


def _outcomes(record: EvaluationRecord) -> list[dict]:
    """What the package shows of each outcome, with its step and timings: never its goal."""
    return [
        {
            "scenario_id": o.scenario_id,
            "version": o.version,
            "result": o.result.value if o.result else o.applicability.value,
            "blocked_reason": o.blocked_reason.value if o.blocked_reason else None,
            "first_failing_step": o.first_failing_step,
            "runner": o.runner,
            "step_seconds": list(o.step_seconds),
        }
        for o in record.outcomes
    ]


async def read(
    *,
    store: Any,
    runner: Any,
    vault: Any,
    campaigns: Any,
    cycles: Sequence[Any],
    suite_digest: str,
    times: int,
    fault: tuple[Any, Mapping[str, Any]] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict:
    """Each of ``cycles`` evaluated ``times`` times against ``suite_digest``, then ``fault``'s
    cycle with its spec's edits, as many: every record written, with no campaign."""
    trees: list[tuple[Any, Any, dict | None]] = [(cycle, vault, None) for cycle in cycles]
    if fault is not None:
        cycle, spec = fault
        source, made_from = await faulted(vault, cycle, spec["edits"])
        named = {
            "what": spec["diagnostic"],
            "made_from": made_from,
            "edited": sorted({e["path"] for e in spec["edits"]}),
        }
        trees.append((cycle, source, named))
    readings = []
    for cycle, source, diagnostic in trees:
        built_on = await built_on_identity(campaigns, cycle)
        for n in range(1, times + 1):
            record = await evaluate_cycle(
                store=store,
                runner=runner,
                vault=source,
                cycle=cycle,
                suite_digest=suite_digest,
                campaign_id=None,
                previous_accepted_tree_identity=built_on,
                evaluated_at=clock(),
            )
            reading = {
                "cycle_id": cycle.cycle_id,
                "round": n,
                "evaluation": record.evaluation_id,
                "tree": record.evaluated_tree_identity,
                "built_on": built_on,
                "started": not any(o.blocked_reason in NOT_STARTED for o in record.outcomes),
                "outcomes": _outcomes(record),
            }
            if diagnostic is not None:
                reading["diagnostic"] = diagnostic
            readings.append(reading)
    return {"suite_digest": suite_digest, "times": times, "readings": readings}


def _fault_spec(text: str) -> dict:
    spec = json.loads(text)
    edits = spec.get("edits") if isinstance(spec, dict) else None
    if (
        not isinstance(spec, dict)
        or not spec.get("diagnostic")
        or not spec.get("cycle_id")
        or not edits
        or not all(isinstance(e, dict) and e.get("path") and e.get("old") for e in edits)
    ):
        raise argparse.ArgumentTypeError(
            "a fault names its diagnostic, its cycle_id and its edits, each with a path and old text"
        )
    return spec


def parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(usage=USAGE)
    parser.add_argument("suite_digest")
    parser.add_argument("cycle_ids", nargs="*")
    parser.add_argument("--times", type=int, default=1)
    parser.add_argument("--fault", type=_fault_spec, default=None)
    args = parser.parse_args(argv)
    if not args.cycle_ids and args.fault is None:
        parser.error("name a cycle or a fault")
    if args.times < 1:
        parser.error("--times is at least 1")
    return args


async def main(args: argparse.Namespace) -> int:
    from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
    from adapters.cycles.postgres_campaign_registry import PostgresCampaignRegistry
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.persistence.pool import create_pool
    from adapters.persistence.transient import TransientRetry
    from adapters.sandbox.factory import create_scenario_runner
    from adapters.scenarios.postgres_scenario_store import PostgresScenarioStore
    from squadops.bootstrap.secrets import secret_provider_for
    from squadops.config.loader import load_config
    from squadops.config.schema import DBRetryConfig

    config = load_config(secret_provider_factory=secret_provider_for)
    runner = create_scenario_runner(config.sandbox_client)
    if runner is None:
        print(json.dumps({"error": "the deploy has no scenario runner"}))
        return 1
    pool = await create_pool(config.database().url, min_size=1, max_size=2)
    try:
        registry = PostgresCycleRegistry(pool=pool, retry=TransientRetry.of(DBRetryConfig()))
        cycles = [await registry.get_cycle(cycle_id) for cycle_id in args.cycle_ids]
        fault = None
        if args.fault is not None:
            fault = (await registry.get_cycle(args.fault["cycle_id"]), args.fault)
        doc = await read(
            store=PostgresScenarioStore(pool),
            runner=runner,
            vault=FilesystemArtifactVault(base_dir="/app/data/artifacts"),
            campaigns=PostgresCampaignRegistry(pool),
            cycles=cycles,
            suite_digest=args.suite_digest,
            times=args.times,
            fault=fault,
        )
    finally:
        await pool.close()
    print(json.dumps(doc, indent=2))
    return 0 if all(r["started"] for r in doc["readings"]) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse(sys.argv[1:]))))
