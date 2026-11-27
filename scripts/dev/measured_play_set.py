#!/usr/bin/env python3
"""Play one measured set through this box's runtime, and compare two (the 2.9 plan's item 13).

# Platform: local-spark for `play` (the box whose runtime the Studio worker serves, inside its
# runtime-api container). `compare` and `host-bar` read documents and run anywhere.

The certification window's case 13 compares two sets of plays of one frozen scenario on the
product's pinned baseline: a before set and an after set
(`docs/plans/verification-sets/2-9-0-certification-preregistration.md`). `play` plays one set and
prints its record. `compare` reads two records and says whether they are a matched pair, and how
much the median fell. `host-bar` reads a `host_quiet_reading.py` document against the bar a
set's start and end must meet.

**What a play's times are read from.**
- *Claim to completion:* the runtime's own record of the operation, from its attempt's
  `claimed_at` to its `settled_at`. This is the time the 20% target is read on.
- *Queue wait:* from the operation's `created_at` to that `claimed_at`.
- *Each stage:* the play's `stages.json` evidence item, which the worker's runner writes.
- *Outside the stages:* claim to completion less the stages' sum. It is the worker staging the
  tree, the result's delivery and the runtime's acceptance. Nothing times those apart.

**How a play is queued.** On the runtime's worker registry, with the request a cycle's own
verification builds: every text file of the pinned commit, and the frozen scenario. The agents'
route can't be used, since it serves only a task's current send. One attempt each: an
interrupted play is recorded as it ended, never retried into a second time.

**Who owns the plays.** An operation names an owner so that a cancel can reach it (SIP-0117
R5.30). A measured set is no cycle, so it owns its plays under its own name, and this tool is
the only thing that can cancel them. It does, on any exit, for every play it queued that has no
result.

    docker cp scripts/dev/measured_play_set.py squadops-runtime-api:/tmp/
    docker cp scenario.json squadops-runtime-api:/tmp/
    docker exec -w /app squadops-runtime-api python /tmp/measured_play_set.py play --dry-run ...
    docker exec -w /app squadops-runtime-api python /tmp/measured_play_set.py play \\
        --label 2.9-before --project <project> --commit <full sha> \\
        --scenario /tmp/scenario.json --scenario-digest sha256:<frozen digest> --plays 20 \\
        > var/measured-sets/2.9-before.json
    python scripts/dev/measured_play_set.py compare before.json after.json
    python scripts/dev/measured_play_set.py host-bar start reading.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from squadops.remote_execution.models import RemoteOperationRequest, RemoteOperationResult
from squadops.remote_execution.workers import Attempt, Enqueued, QueuedOperation

SET_SCHEMA = "squadops.measured-play-set/1"
STAGES_NAME = "stages.json"
#: What ``origin`` says of a measured set's plays. ``cycle_id`` is the key an owner is read
#: from; the value is the set's own name, and no cycle (see the module's docstring).
OWNER_PREFIX = "measured-set:"
#: The target of the 2.9 plan's ruling D6: the median falls by at least this fraction.
TARGET_CUT = 0.20

#: The bar a measured set's host readings must meet (the pre-registration's amendment 13a).
#: At a set's start: the Mac is settled and nothing but Studio and the worker is at work.
START_BAR = {
    "load_1m_under": 2.0,
    "load_15m_under": 3.0,
    "memory_free_percent_at_least": 70,
    "other_cpu_percent_under": 100.0,
}


# --------------------------------------------------------------------------- one play's record


def play_record(index: int, operation: QueuedOperation, attempt: Attempt | None) -> dict[str, Any]:
    """What one play's records say of it. A time that can't be read is ``None``, never zero."""
    result = operation.result
    claimed_at = attempt.claimed_at if attempt is not None else None
    stages = _stages(result)
    staged = round(sum(stages["stages"].values()), 3) if stages is not None else None
    held = _seconds(claimed_at, operation.settled_at)
    ran_with = dict(result.ran_with) if result is not None else {}
    return {
        "index": index,
        "operation_id": operation.operation_id,
        "status": result.status.value if result is not None else "no_result",
        "reason": result.reason if result is not None else "",
        "outcomes": [[r.assertion_id, r.outcome.value] for r in result.records] if result else [],
        "queued_at": _iso(operation.created_at),
        "claimed_at": _iso(claimed_at),
        "settled_at": _iso(operation.settled_at),
        "queue_wait_s": _seconds(operation.created_at, claimed_at),
        "claim_to_completion_s": held,
        "stages": stages["stages"] if stages is not None else None,
        "waits": stages.get("waits") if stages is not None else None,
        "transactions": stages.get("transactions") if stages is not None else None,
        "stages_total_s": staged,
        "outside_stages_s": (
            round(held - staged, 3) if held is not None and staged is not None else None
        ),
        "source_revision": operation.request.source_revision,
        "served_by": ran_with.get("served_by"),
        "qualified_by": ran_with.get("qualified_by"),
        "played": {
            key.removeprefix("played."): value
            for key, value in sorted(ran_with.items())
            if key.startswith("played.")
        },
    }


def _stages(result: RemoteOperationResult | None) -> dict[str, Any] | None:
    """The play's ``stages.json``, or ``None`` when it carries none or one that can't be read."""
    for item in result.evidence if result is not None else ():
        if item.name == STAGES_NAME:
            try:
                document = json.loads(item.content)
            except ValueError:
                return None
            stages = document.get("stages") if isinstance(document, dict) else None
            if isinstance(stages, dict) and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in stages.values()
            ):
                return document
            return None
    return None


def _seconds(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds(), 3)


def _iso(at: datetime | None) -> str | None:
    return at.astimezone(UTC).isoformat(timespec="milliseconds") if at is not None else None


# ----------------------------------------------------------------------------- the set's record


def nearest_rank(values: Sequence[float], fraction: float) -> float:
    """The nearest-rank percentile: of 20 values, the 95th is the 19th. Of one, itself."""
    if not values:
        raise ValueError("no values to rank")
    ordered = sorted(values)
    return ordered[max(1, math.ceil(fraction * len(ordered))) - 1]


def summary(plays: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The set's readout. Non-execution is counted beside completion, by status."""
    by_status: dict[str, int] = {}
    for play in plays:
        by_status[play["status"]] = by_status.get(play["status"], 0) + 1
    completed = [p for p in plays if p["status"] == "completed"]
    held = [p["claim_to_completion_s"] for p in completed if p["claim_to_completion_s"] is not None]
    stage_names = sorted({name for p in completed for name in (p["stages"] or {})})
    span = _span_hours(plays)
    return {
        "plays": len(plays),
        "by_status": dict(sorted(by_status.items())),
        "claim_to_completion_s": (
            {
                "median": round(statistics.median(held), 3),
                "p95": nearest_rank(held, 0.95),
                "min": min(held),
                "max": max(held),
                "read_on": len(held),
            }
            if held
            else None
        ),
        "plays_per_hour": round(len(completed) / span, 2) if completed and span else None,
        "stage_median_s": {
            name: round(
                statistics.median(p["stages"][name] for p in completed if name in p["stages"]), 3
            )
            for name in stage_names
        },
        "outside_stages_median_s": _median(p["outside_stages_s"] for p in completed),
        "queue_wait_median_s": _median(p["queue_wait_s"] for p in completed),
        "begun_again": sum(1 for p in completed if (p["transactions"] or 1) > 1),
        "without_stages": sum(1 for p in completed if p["stages"] is None),
        "qualified_by": sorted({p["qualified_by"] or "unnamed" for p in completed}),
        "served_by": sorted({p["served_by"] or "unnamed" for p in completed}),
        "source_revisions": sorted({p["source_revision"] for p in plays}),
    }


def _median(values: Any) -> float | None:
    read = [v for v in values if v is not None]
    return round(statistics.median(read), 3) if read else None


def _span_hours(plays: Sequence[Mapping[str, Any]]) -> float | None:
    queued = [p["queued_at"] for p in plays if p["queued_at"]]
    settled = [p["settled_at"] for p in plays if p["settled_at"]]
    if not queued or not settled:
        return None
    seconds = (
        datetime.fromisoformat(max(settled)) - datetime.fromisoformat(min(queued))
    ).total_seconds()
    return seconds / 3600 if seconds > 0 else None


def set_document(
    label: str,
    *,
    project: str,
    commit: str,
    scenario_name: str,
    scenario_digest: str,
    asked: int,
    plays: Sequence[Mapping[str, Any]],
    stopped: str = "",
) -> dict[str, Any]:
    return {
        "schema": SET_SCHEMA,
        "label": label,
        "project": project,
        "commit": commit,
        "scenario": {"name": scenario_name, "digest": scenario_digest},
        "plays_asked": asked,
        "stopped": stopped,
        "summary": summary(plays),
        "plays": list(plays),
    }


# ------------------------------------------------------------------------------ two sets, read


def compare(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Case 13's reading of two set records: whether they are a matched pair by what the
    records hold, whether each play's outcomes are unchanged, and how far the median fell.

    The host readings are not in a set's record: ``host_bar`` reads those, and a pair is
    matched only when they meet it too. ``unmatched_because`` names every reason found here.
    """
    unmatched = []
    for what, read in (
        ("scenario", lambda d: d["scenario"]["digest"]),
        ("commit", lambda d: d["commit"]),
        ("plays asked", lambda d: d["plays_asked"]),
        ("source revisions", lambda d: d["summary"]["source_revisions"]),
    ):
        if read(before) != read(after):
            unmatched.append(f"{what} differ: {read(before)!r} before, {read(after)!r} after")
    for name, document in (("before", before), ("after", after)):
        proved = document["summary"]["qualified_by"]
        if len(proved) != 1 or proved == ["unnamed"]:
            unmatched.append(f"the {name} set names {proved} as its qualification, not one")
        if document["stopped"]:
            unmatched.append(f"the {name} set stopped early: {document['stopped']}")
        incomplete = {s: n for s, n in document["summary"]["by_status"].items() if s != "completed"}
        if incomplete:
            unmatched.append(f"the {name} set has plays that didn't complete: {incomplete}")
    if not unmatched and before["summary"]["qualified_by"] != after["summary"]["qualified_by"]:
        unmatched.append(
            f"the sets ran on different qualifications: {before['summary']['qualified_by'][0]} "
            f"before, {after['summary']['qualified_by'][0]} after"
        )
    differing = [
        b["index"]
        for b, a in zip(before["plays"], after["plays"], strict=False)
        if b["outcomes"] != a["outcomes"] or b["status"] != a["status"]
    ]
    medians = [d["summary"]["claim_to_completion_s"] for d in (before, after)]
    cut = None
    if all(m is not None for m in medians) and medians[0]["median"] > 0:
        cut = round((medians[0]["median"] - medians[1]["median"]) / medians[0]["median"], 4)
    return {
        "matched": not unmatched,
        "unmatched_because": unmatched,
        "outcomes_unchanged": not differing and len(before["plays"]) == len(after["plays"]),
        "plays_whose_outcomes_differ": differing,
        "median_before_s": medians[0]["median"] if medians[0] else None,
        "median_after_s": medians[1]["median"] if medians[1] else None,
        "p95_before_s": medians[0]["p95"] if medians[0] else None,
        "p95_after_s": medians[1]["p95"] if medians[1] else None,
        "median_cut": cut,
        "target_cut": TARGET_CUT,
        "target_met": cut is not None and cut >= TARGET_CUT,
        "stage_median_before_s": before["summary"]["stage_median_s"],
        "stage_median_after_s": after["summary"]["stage_median_s"],
    }


def host_bar(reading: Mapping[str, Any], when: str) -> list[str]:
    """Why a ``host_quiet_reading.py`` document misses the bar for a set's ``start`` or
    ``end``: empty when it meets it. A reading that wasn't taken misses, by name: an unread
    Mac is not a quiet one.

    At the end only what can't be the set's own doing is held: no container, no model. A set
    of plays raises the load and Studio's memory by itself."""
    if when not in ("start", "end"):
        raise ValueError(f"when is {when!r}: start or end")
    checks = (_containers, _models) if when == "end" else (*_ALWAYS, *_AT_START)
    return [miss for check in checks for miss in check(reading)]


def _containers(reading: Mapping[str, Any]) -> list[str]:
    docker = reading.get("docker")
    if not isinstance(docker, Mapping) or "answers" not in docker:
        return ["docker wasn't read"]
    if docker["answers"] and docker.get("containers_running") != 0:
        return [f"{docker.get('containers_running')} containers are running"]
    return []


def _models(reading: Mapping[str, Any]) -> list[str]:
    models = reading.get("models_loaded")
    if not isinstance(models, list):
        return [f"the loaded models weren't read: {models}"]
    return [f"{len(models)} models are loaded"] if models else []


def _load(reading: Mapping[str, Any]) -> list[str]:
    load = reading.get("load_average")
    if not (isinstance(load, list) and len(load) == 3):
        return [f"the load average wasn't read: {load}"]
    misses = []
    if not load[0] < START_BAR["load_1m_under"]:
        misses.append(f"the 1-minute load is {load[0]}, not under 2.0")
    if not load[2] < START_BAR["load_15m_under"]:
        misses.append(f"the 15-minute load is {load[2]}, not under 3.0")
    return misses


def _free_memory(reading: Mapping[str, Any]) -> list[str]:
    free = reading.get("memory_free_percent")
    if not isinstance(free, int) or isinstance(free, bool):
        return [f"the free memory wasn't read: {free}"]
    if free < START_BAR["memory_free_percent_at_least"]:
        return [f"free memory is {free}%, under 70%"]
    return []


def _other_processes(reading: Mapping[str, Any]) -> list[str]:
    processes = reading.get("processes")
    other = processes.get("other") if isinstance(processes, Mapping) else None
    if not isinstance(other, Mapping) or "cpu_percent" not in other:
        return ["the other processes weren't read"]
    if not other["cpu_percent"] < START_BAR["other_cpu_percent_under"]:
        return [f"other processes use {other['cpu_percent']}% CPU, not under 100%"]
    return []


_ALWAYS = (_containers, _models)
_AT_START = (_load, _free_memory, _other_processes)


# ------------------------------------------------------------------------------ playing the set


async def run_set(
    registry: Any,
    store: Any,
    requests: Sequence[RemoteOperationRequest],
    owner: Mapping[str, str],
    *,
    play_timeout_seconds: float,
    gap_seconds: float = 0.0,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    said: Callable[[str], None] = lambda line: print(line, file=sys.stderr, flush=True),
) -> tuple[list[dict[str, Any]], str]:
    """Each request played in turn, one at a time: its record, and why the set stopped early
    (empty when every request was played).

    The set stops at the first request nothing could be queued for: a set with a hole in it
    isn't the set that was registered. Every operation queued here that has no result when
    this returns or raises is asked to stop."""
    plays: list[dict[str, Any]] = []
    queued_ids: list[str] = []
    stopped = ""
    try:
        for index, request in enumerate(requests, start=1):
            queued = await registry.enqueue(request, owner, max_attempts=1, only_with_worker=True)
            if not isinstance(queued, Enqueued):
                stopped = f"play {index} wasn't queued: {queued}"
                break
            operation_id = queued.operation.operation_id
            queued_ids.append(operation_id)
            operation = await _settled(
                registry, operation_id, play_timeout_seconds, poll_seconds, sleep
            )
            async with store.exclusive() as tx:
                attempt = (
                    await tx.attempt(operation_id, operation.attempt) if operation.attempt else None
                )
            record = play_record(index, operation, attempt)
            plays.append(record)
            said(
                f"play {index}/{len(requests)}: {record['status']} "
                f"claim-to-completion {record['claim_to_completion_s']} s"
            )
            if operation.result is None:
                stopped = f"play {index} had no result within {play_timeout_seconds:g} s"
                break
            if gap_seconds and index < len(requests):
                await sleep(gap_seconds)
    finally:
        for operation_id in queued_ids:
            if (await registry.operation(operation_id)).result is None:
                await registry.cancel(operation_id)
    return plays, stopped


async def _settled(
    registry: Any,
    operation_id: str,
    timeout_seconds: float,
    poll_seconds: float,
    sleep: Callable[[float], Awaitable[None]],
) -> QueuedOperation:
    """The operation once it has a result, or as it stands when the time runs out."""
    waited = 0.0
    while True:
        operation = await registry.operation(operation_id)
        if operation.result is not None or waited >= timeout_seconds:
            return operation
        await sleep(poll_seconds)
        waited += poll_seconds


def set_requests(
    label: str,
    run: str,
    plays: int,
    *,
    source_files: Mapping[str, str],
    scenario: Any,
    provider: str,
    operation: str,
) -> list[RemoteOperationRequest]:
    """The set's requests: one frozen scenario on one staged tree, each its own task and send.
    ``run`` tells this run of the label from an earlier one, whose sends the registry still
    holds and would answer with."""
    from squadops.remote_execution.scenario import staged_revision

    revision = staged_revision(dict(source_files))
    return [
        RemoteOperationRequest(
            contract="game.scenario_verification",
            mode="play",
            provider=provider,
            operation=operation,
            location="worker",
            source_revision=revision,
            source_files=dict(source_files),
            scenario=scenario,
            task_id=f"{OWNER_PREFIX}{label}:{run}:play-{index:02d}",
            dispatch_id=f"{OWNER_PREFIX}{label}:{run}:play-{index:02d}:send-1",
        )
        for index in range(1, plays + 1)
    ]


def staged_text(files: Mapping[str, bytes]) -> tuple[dict[str, str], list[str]]:
    """The checkout's text files, and the paths of every other file: the wire stages text, as
    a cycle's own verification does (``campaigns.scenario_runs``)."""
    staged, left = {}, []
    for path, content in files.items():
        try:
            staged[path] = content.decode("utf-8")
        except UnicodeDecodeError:
            left.append(path)
    return staged, sorted(left)


# --------------------------------------------------------------------------------- composition


async def _play(args: argparse.Namespace) -> int:
    """The runtime's own ports, built from the container's config as the runtime builds them."""
    from adapters.cycles.factory import create_project_registry
    from adapters.persistence.pool import create_pool
    from adapters.remote_execution.factory import create_worker_registry_store
    from adapters.remote_execution.game_dev_roblox_studio.runner import OPERATION, PROVIDER
    from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
    from adapters.tools.factory import create_source_repository
    from squadops.bootstrap.secrets import secret_provider_for
    from squadops.config import load_config
    from squadops.projects.configuration import baseline_tree
    from squadops.projects.registration import LocatorPolicy
    from squadops.remote_execution.registry import WorkerRegistry
    from squadops.remote_execution.scenario import frozen_scenario

    scenario_file = Path(args.scenario)
    scenario = frozen_scenario(json.loads(scenario_file.read_text(encoding="utf-8")), VOCABULARY)
    if scenario.digest != args.scenario_digest:
        print(
            f"the scenario at {scenario_file} freezes to {scenario.digest}, and the registered "
            f"one is {args.scenario_digest}: nothing was played",
            file=sys.stderr,
        )
        return 2
    config = load_config(secret_provider_factory=secret_provider_for)
    if config.cycles.registry_provider != "postgres":
        print("this runtime's registry isn't in Postgres, so no worker would see the set",
              file=sys.stderr)  # fmt: skip
        return 2
    pool = await create_pool(config.database().url, min_size=1, max_size=2)
    try:
        provider = config.cycles.project_registry_provider
        projects = create_project_registry(
            provider, **({"pool": pool} if provider != "config" else {})
        )
        repository = create_source_repository(
            cache_root=config.projects.clone_cache_root,
            policy=LocatorPolicy.of(
                config.projects.locator_allowed_hosts, config.projects.locator_local_roots
            ),
            timeout_seconds=config.projects.git_timeout_seconds,
            committer_name=config.projects.committer_name,
            committer_email=config.projects.committer_email,
        )
        project = await projects.get_project(args.project)
        checkout = await baseline_tree(
            repository, args.project, project.source.repo_uri, project.source.base_ref, args.commit
        )
        staged, not_staged = staged_text(checkout.files)
        store = create_worker_registry_store("postgres", pool=pool)
        registry = WorkerRegistry(store)
        if args.dry_run:
            # Everything the set needs, read and said, and nothing queued.
            no_worker = await registry.no_worker_for(PROVIDER, OPERATION)
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "scenario": {"name": scenario_file.name, "digest": scenario.digest},
                        "commit": checkout.commit,
                        "files_staged": len(staged),
                        "files_not_staged": len(not_staged),
                        "worker": "serving" if no_worker is None else no_worker.reason,
                    },
                    indent=2,
                )
            )
            return 0 if no_worker is None else 1
        run = uuid.uuid4().hex[:8]
        requests = set_requests(
            args.label, run, args.plays,
            source_files=staged, scenario=scenario, provider=PROVIDER, operation=OPERATION,
        )  # fmt: skip
        plays, stopped = await run_set(
            registry,
            store,
            requests,
            {"cycle_id": f"{OWNER_PREFIX}{args.label}:{run}", "requester": "measured_play_set"},
            play_timeout_seconds=args.play_timeout_seconds,
            gap_seconds=args.gap_seconds,
        )
    finally:
        await pool.close()
    document = set_document(
        args.label,
        project=args.project,
        commit=checkout.commit,
        scenario_name=scenario_file.name,
        scenario_digest=scenario.digest,
        asked=args.plays,
        plays=plays,
        stopped=stopped,
    )
    document["files_not_staged"] = len(not_staged)
    print(json.dumps(document, indent=2))
    return 1 if stopped else 0


def _read(path: str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} holds no JSON object")
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    play = commands.add_parser("play", help="play one set through this box's runtime")
    play.add_argument("--label", required=True, help="the set's name, e.g. 2.9-before")
    play.add_argument("--project", required=True)
    play.add_argument("--commit", required=True, help="the pinned baseline commit, in full")
    play.add_argument("--scenario", required=True, help="the scenario's JSON file")
    play.add_argument("--scenario-digest", required=True, help="its registered frozen digest")
    play.add_argument("--plays", required=True, type=int)
    play.add_argument("--play-timeout-seconds", type=float, default=600.0)
    play.add_argument("--gap-seconds", type=float, default=0.0)
    play.add_argument(
        "--dry-run",
        action="store_true",
        help="read the scenario, the tree and whether a worker serves it, and queue nothing",
    )
    pair = commands.add_parser("compare", help="read a before set's record and an after set's")
    pair.add_argument("before")
    pair.add_argument("after")
    bar = commands.add_parser("host-bar", help="read a host reading against a set's bar")
    bar.add_argument("when", choices=("start", "end"))
    bar.add_argument("reading")
    args = parser.parse_args(argv)
    if args.command == "play":
        if args.plays < 1:
            parser.error("--plays is at least 1")
        return asyncio.run(_play(args))
    if args.command == "compare":
        reading = compare(_read(args.before), _read(args.after))
        print(json.dumps(reading, indent=2))
        return 0 if reading["matched"] and reading["outcomes_unchanged"] else 1
    misses = host_bar(_read(args.reading), args.when)
    print(json.dumps({"when": args.when, "meets_the_bar": not misses, "misses": misses}, indent=2))
    return 0 if not misses else 1


if __name__ == "__main__":
    sys.exit(main())
