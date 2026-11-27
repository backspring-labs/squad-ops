#!/usr/bin/env python3
"""Play the isolation sequence through this box's runtime and read it (the 2.9 plan's item 13).

# Platform: local-spark for `play` (inside the runtime-api container, beside
# `measured_play_set.py`, which it imports). `read` reads a record and runs anywhere.

The certification window's case 12 asks whether one play's state reaches another
(`docs/plans/verification-sets/2-9-0-certification-preregistration.md`, amendment 13b). This
plays a fixed sequence of plays of three trees, all built from the pinned commit:

- **the baseline:** the pinned commit, untouched;
- **the marked tree:** the baseline plus marks its scripts leave when they start (a workspace
  attribute, a value instance, a `_G` key, a key in a module's table, a screen under the player)
  and a module the other trees don't hold;
- **the reading tree:** the baseline plus a reader that says, for each mark, whether it is
  there. The marked tree carries the reader too, after its marks.

A play of the marked tree must read every mark as present: that is what shows the reader can
see one. A play of the reading tree after it must read every mark as absent: that is the
isolation. The sequence puts the reading tree after a completed marked play, after one whose
setup failed, and after one cancelled while it ran, and it queues two plays at once to see that
one waits for the other.

Nothing here is the product's: the marks and the reader are this tool's own lines, named
`squadops_*`, put at the top of the first server script and the first client script the tree
holds. They exist only in a play's staged tree, and are never written to the product.

    docker cp scripts/dev/measured_play_set.py squadops-runtime-api:/tmp/
    docker cp scripts/dev/play_isolation_sequence.py squadops-runtime-api:/tmp/
    docker exec -w /app squadops-runtime-api python /tmp/play_isolation_sequence.py play \\
        --project <project> --commit <full sha> --baseline-scenario /tmp/scenario.json \\
        > var/measured-sets/2.9-isolation.json
    python scripts/dev/play_isolation_sequence.py read var/measured-sets/2.9-isolation.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import measured_play_set as measured  # noqa: E402

from adapters.remote_execution.game_dev_roblox_studio.place import (  # noqa: E402
    SCRIPT_SUFFIXES,
    SYNCED_FOLDERS,
)
from squadops.remote_execution.models import RemoteOperationRequest  # noqa: E402
from squadops.remote_execution.workers import Enqueued, OperationState  # noqa: E402

SEQUENCE_SCHEMA = "squadops.isolation-sequence/1"
OWNER_PREFIX = "isolation-sequence:"
#: The line every inserted block carries, so a diff or a console line reads as this tool's.
PROBE_MARKER = "__squadops_isolation_probe__"
#: A module both the marked and the reading tree hold: its table is where a module's state is
#: marked and read. And one only the marked tree holds: a script left from another tree.
#: Where the provider places scripts, read from the provider: the blocks below name the same
#: three folders by their Studio paths.
SERVER_ROOT = SYNCED_FOLDERS["ServerScriptService.Server"] + "/"
CLIENT_ROOT = SYNCED_FOLDERS["StarterPlayer.StarterPlayerScripts.Client"] + "/"
_SHARED_ROOT = SYNCED_FOLDERS["ReplicatedStorage.Shared"] + "/"
SERVER_SUFFIX = next(suffix for suffix, cls in SCRIPT_SUFFIXES if cls == "Script")
CLIENT_SUFFIX = next(suffix for suffix, cls in SCRIPT_SUFFIXES if cls == "LocalScript")
PROBE_MODULE = _SHARED_ROOT + "SquadopsProbe.luau"
RESIDUE_MODULE = _SHARED_ROOT + "SquadopsProbeResidue.luau"

#: What the reader reports, by the context it reports it in. Each is a workspace attribute
#: `squadops_seen_<name>` holding `present` or `absent`.
SERVER_MARKS = ("attribute", "value", "global", "module", "residue")
CLIENT_MARKS = ("gui", "client_global")

_GUARD = 'if typeof(game) == "Instance" then'
SERVER_MARKS_BLOCK = f"""{_GUARD} -- {PROBE_MARKER}: marks (server)
	workspace:SetAttribute("squadops_mark_attribute", "marked")
	_G.squadops_mark_global = "marked"
	local squadops_value = Instance.new("StringValue")
	squadops_value.Name = "SquadopsMarkValue"
	squadops_value.Value = "marked"
	squadops_value.Parent = workspace
	pcall(function()
		require(game:GetService("ReplicatedStorage").Shared.SquadopsProbe).mark = "marked"
	end)
end"""
SERVER_READER_BLOCK = f"""{_GUARD} -- {PROBE_MARKER}: reader (server)
	local squadops_shared = game:GetService("ReplicatedStorage"):FindFirstChild("Shared")
	local function squadops_seen(value)
		return if value ~= nil then "present" else "absent"
	end
	local squadops_ok, squadops_probe = pcall(function()
		return require(squadops_shared.SquadopsProbe)
	end)
	workspace:SetAttribute("squadops_seen_attribute", squadops_seen(workspace:GetAttribute("squadops_mark_attribute")))
	workspace:SetAttribute("squadops_seen_value", squadops_seen(workspace:FindFirstChild("SquadopsMarkValue")))
	workspace:SetAttribute("squadops_seen_global", squadops_seen(_G.squadops_mark_global))
	workspace:SetAttribute("squadops_seen_module", if squadops_ok then squadops_seen(squadops_probe.mark) else "unread")
	workspace:SetAttribute("squadops_seen_residue", squadops_seen(squadops_shared and squadops_shared:FindFirstChild("SquadopsProbeResidue")))
	workspace:SetAttribute("squadops_seen_done", "server")
end"""
CLIENT_MARKS_BLOCK = f"""{_GUARD} -- {PROBE_MARKER}: marks (client)
	_G.squadops_mark_client_global = "marked"
	local squadops_gui = Instance.new("ScreenGui")
	squadops_gui.Name = "SquadopsMarkGui"
	squadops_gui.Parent = game:GetService("Players").LocalPlayer:WaitForChild("PlayerGui", 20)
end"""
CLIENT_READER_BLOCK = f"""{_GUARD} -- {PROBE_MARKER}: reader (client)
	local squadops_player_gui = game:GetService("Players").LocalPlayer:WaitForChild("PlayerGui", 20)
	local function squadops_seen(value)
		return if value ~= nil then "present" else "absent"
	end
	workspace:SetAttribute("squadops_seen_gui", squadops_seen(squadops_player_gui and squadops_player_gui:FindFirstChild("SquadopsMarkGui")))
	workspace:SetAttribute("squadops_seen_client_global", squadops_seen(_G.squadops_mark_client_global))
	workspace:SetAttribute("squadops_seen_client_done", "client")
end"""
PROBE_MODULE_TEXT = f"-- {PROBE_MARKER}: a table a play may mark\nreturn {{}}\n"
RESIDUE_MODULE_TEXT = f"-- {PROBE_MARKER}: a script only the marked tree holds\nreturn {{}}\n"


# ------------------------------------------------------------------------------------ the trees


def first_script(files: Mapping[str, str], root: str, suffix: str) -> str:
    """The first script of its kind the tree holds, by path. Raises ``ValueError`` when the
    tree holds none: the sequence can't mark a tree with no script to mark."""
    found = sorted(p for p in files if p.startswith(root) and p.endswith(suffix))
    if not found:
        raise ValueError(f"the tree holds no {suffix} script under {root}")
    return found[0]


def opened_with(text: str, block: str) -> str:
    """``text`` with ``block`` after its leading comments and directives, so it runs when the
    script loads and ``--!strict`` stays first."""
    lines = text.split("\n")
    at = next(
        (i for i, line in enumerate(lines) if line.strip() and not line.lstrip().startswith("--")),
        len(lines),
    )
    return "\n".join([*lines[:at], block, *lines[at:]])


def reading_tree(baseline: Mapping[str, str]) -> dict[str, str]:
    """The baseline plus the reader in its first server and client scripts, and the module
    whose table the reader reads."""
    tree = dict(baseline)
    for path in (PROBE_MODULE, RESIDUE_MODULE):
        if path in tree:
            raise ValueError(f"the tree already holds {path}, which the sequence would overwrite")
    server = first_script(tree, SERVER_ROOT, SERVER_SUFFIX)
    client = first_script(tree, CLIENT_ROOT, CLIENT_SUFFIX)
    tree[server] = opened_with(tree[server], SERVER_READER_BLOCK)
    tree[client] = opened_with(tree[client], CLIENT_READER_BLOCK)
    tree[PROBE_MODULE] = PROBE_MODULE_TEXT
    return tree


def marked_tree(baseline: Mapping[str, str]) -> dict[str, str]:
    """The reading tree with the marks put before its reader, and the module only it holds."""
    tree = reading_tree(baseline)
    server = first_script(baseline, SERVER_ROOT, SERVER_SUFFIX)
    client = first_script(baseline, CLIENT_ROOT, CLIENT_SUFFIX)
    tree[server] = opened_with(baseline[server], SERVER_MARKS_BLOCK + "\n" + SERVER_READER_BLOCK)
    tree[client] = opened_with(baseline[client], CLIENT_MARKS_BLOCK + "\n" + CLIENT_READER_BLOCK)
    tree[RESIDUE_MODULE] = RESIDUE_MODULE_TEXT
    return tree


# -------------------------------------------------------------------------------- the scenarios


def _seen(name: str, context: str) -> dict[str, Any]:
    return {
        "kind": "attribute",
        "path": "Workspace",
        "name": f"squadops_seen_{name}",
        "context": context,
    }


def _reader_ran() -> list[dict[str, Any]]:
    return [
        {
            "action": "wait_until",
            "observe": _seen(done, context),
            "expect": {"op": "equals", "value": context},
            "deadline_s": 30,
        }
        for done, context in (("done", "server"), ("client_done", "client"))
    ]


def marks_scenario(scenario_id: str, expected: str) -> dict[str, Any]:
    """A scenario that waits for both readers, then asserts every mark reads ``expected``."""
    assertions = [
        {
            "id": f"{name.replace('_', '-')}-{expected}",
            "observe": _seen(name, context),
            "expect": {"op": "equals", "value": expected},
        }
        for context, names in (("server", SERVER_MARKS), ("client", CLIENT_MARKS))
        for name in names
    ]
    return {
        "schema": "squadops.scenario/1",
        "scenario_id": scenario_id,
        "reader": "roblox-studio/1",
        "setup": _reader_ran(),
        "steps": [],
        "assertions": assertions,
        "named_assertion": assertions[0]["id"],
    }


def unmet_setup_scenario() -> dict[str, Any]:
    """A scenario whose setup can't be met on any tree: its play reads ``setup_failed``."""
    scenario = marks_scenario("isolation-setup-unmet", "present")
    scenario["setup"] = [
        {
            "action": "wait_until",
            "observe": _seen("never_set", "server"),
            "expect": {"op": "equals", "value": "never"},
            "deadline_s": 5,
        }
    ]
    return scenario


# --------------------------------------------------------------------------------- the sequence


@dataclass(frozen=True)
class Step:
    """One play of the sequence. ``cancel_after_s`` cancels it that long after it is claimed.
    ``with_next`` queues the next step before this one is claimed, for the competing pair."""

    name: str
    tree: str
    scenario: str
    cancel_after_s: float | None = None
    with_next: bool = False


SEQUENCE = (
    Step("baseline-first", "baseline", "baseline"),
    Step("marked", "marked", "present"),
    Step("after-a-completed-play", "reading", "absent"),
    Step("marked-setup-fails", "marked", "unmet"),
    Step("after-a-failed-play", "reading", "absent"),
    Step("marked-cancelled", "marked", "present", cancel_after_s=30.0),
    Step("after-an-interrupted-play", "reading", "absent"),
    Step("baseline-again", "baseline", "baseline"),
    Step("competing-marked", "marked", "present", with_next=True),
    Step("competing-reading", "reading", "absent"),
)


def sequence_requests(
    run: str,
    *,
    trees: Mapping[str, Mapping[str, str]],
    scenarios: Mapping[str, Any],
    provider: str,
    operation: str,
    steps: Sequence[Step] = SEQUENCE,
) -> list[RemoteOperationRequest]:
    """Each step's request: its own tree, staged as its own revision, and its own scenario."""
    from squadops.remote_execution.scenario import staged_revision

    return [
        RemoteOperationRequest(
            contract="game.scenario_verification",
            mode="play",
            provider=provider,
            operation=operation,
            location="worker",
            source_revision=staged_revision(dict(trees[step.tree])),
            source_files=dict(trees[step.tree]),
            scenario=scenarios[step.scenario],
            task_id=f"{OWNER_PREFIX}{run}:{index:02d}-{step.name}",
            dispatch_id=f"{OWNER_PREFIX}{run}:{index:02d}-{step.name}:send-1",
        )
        for index, step in enumerate(steps, start=1)
    ]


async def run_sequence(
    registry: Any,
    store: Any,
    steps: Sequence[Step],
    requests: Sequence[RemoteOperationRequest],
    owner: Mapping[str, str],
    *,
    play_timeout_seconds: float,
    poll_seconds: float = 1.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    said: Callable[[str], None] = lambda line: print(line, file=sys.stderr, flush=True),
) -> tuple[list[dict[str, Any]], str]:
    """Each step played in turn: its record, and why the sequence stopped early. A step marked
    ``with_next`` is queued together with the one after it, before either is claimed. Every
    operation queued here that has no result when this returns or raises is asked to stop."""
    plays: list[dict[str, Any]] = []
    queued_ids: list[str] = []
    stopped = ""

    async def queue(index: int) -> str | None:
        queued = await registry.enqueue(
            requests[index], owner, max_attempts=1, only_with_worker=True
        )
        if not isinstance(queued, Enqueued):
            return None
        queued_ids.append(queued.operation.operation_id)
        return queued.operation.operation_id

    async def finish(index: int, operation_id: str) -> bool:
        step = steps[index]
        if step.cancel_after_s is not None:
            await _cancel_once_claimed(
                registry, operation_id, step.cancel_after_s, poll_seconds, sleep
            )
        operation = await measured._settled(
            registry, operation_id, play_timeout_seconds, poll_seconds, sleep
        )
        async with store.exclusive() as tx:
            attempt = (
                await tx.attempt(operation_id, operation.attempt) if operation.attempt else None
            )
        record = {"step": step.name, "tree": step.tree, "scenario": step.scenario}
        record.update(measured.play_record(index + 1, operation, attempt))
        plays.append(record)
        said(f"{index + 1}/{len(steps)} {step.name}: {record['status']}")
        return operation.result is not None

    try:
        index = 0
        while index < len(steps) and not stopped:
            group = [index, index + 1] if steps[index].with_next else [index]
            ids = [await queue(i) for i in group]
            if None in ids:
                stopped = f"step {steps[group[ids.index(None)]].name} wasn't queued"
                break
            for i, operation_id in zip(group, ids, strict=True):
                if not await finish(i, operation_id):
                    stopped = (
                        f"step {steps[i].name} had no result within {play_timeout_seconds:g} s"
                    )
                    break
            index = group[-1] + 1
    finally:
        for operation_id in queued_ids:
            if (await registry.operation(operation_id)).result is None:
                await registry.cancel(operation_id)
    return plays, stopped


async def _cancel_once_claimed(
    registry: Any,
    operation_id: str,
    after_seconds: float,
    poll_seconds: float,
    sleep: Callable[[float], Awaitable[None]],
) -> None:
    """Ask the operation to stop ``after_seconds`` after a worker claims it. One that settles
    before then is left as it ended."""
    held = 0.0
    while True:
        operation = await registry.operation(operation_id)
        if operation.result is not None:
            return
        if operation.state is OperationState.CLAIMED:
            if held >= after_seconds:
                await registry.cancel(operation_id)
                return
            held += poll_seconds
        await sleep(poll_seconds)


# ---------------------------------------------------------------------------------- the reading


def _outcomes(play: Mapping[str, Any]) -> set[str]:
    return {outcome for _, outcome in play["outcomes"]}


def _all(play: Mapping[str, Any], outcome: str) -> bool:
    return play["status"] == "completed" and _outcomes(play) == {outcome}


def _marks_seen(marked: Mapping[str, Any]) -> list[str]:
    if _all(marked, "passed"):
        return []
    return [
        f"the marked play read {marked['status']} with {sorted(_outcomes(marked))}: a reader "
        "that can't see a mark can't show one is absent"
    ]


def _nothing_left(after: Mapping[str, Any]) -> list[str]:
    if _all(after, "passed"):
        return []
    left = [name for name, outcome in after["outcomes"] if outcome != "passed"]
    return [f"{after['step']} read {after['status']}; not read as absent: {left or 'everything'}"]


def _setup_failed(failed: Mapping[str, Any]) -> list[str]:
    if _all(failed, "setup_failed"):
        return []
    return [f"it read {failed['status']} with {sorted(_outcomes(failed))}, not setup_failed"]


def _interrupted(cancelled: Mapping[str, Any]) -> list[str]:
    if cancelled["status"] == "interrupted":
        return []
    return [f"it read {cancelled['status']}, not interrupted"]


def _same_baseline(first: Mapping[str, Any], again: Mapping[str, Any]) -> list[str]:
    why = []
    if not _all(first, "passed"):
        why.append(f"the first baseline read {first['status']} with {sorted(_outcomes(first))}")
    if (first["status"], first["outcomes"]) != (again["status"], again["outcomes"]):
        why.append("the two baseline plays' outcomes differ")
    if first["source_revision"] != again["source_revision"]:
        why.append("the two baseline plays staged different revisions")
    return why


def _one_waited(first: Mapping[str, Any], second: Mapping[str, Any]) -> list[str]:
    why = []
    if not _all(first, "passed"):
        why.append(f"the marked play of the pair read {first['status']}")
    why.extend(_nothing_left(second))
    if not (first["settled_at"] and first["claimed_at"] and second["claimed_at"]):
        return [*why, "the pair's times weren't read"]
    if second["claimed_at"] < first["claimed_at"]:
        # The registry gives the older operation first. Read the other way round, the reading
        # play had nothing of the marked play's to find.
        return [*why, "the reading play was claimed first, so it had no marked play before it"]
    if not second["queued_at"] < first["settled_at"]:
        why.append("the second wasn't queued until the first had settled, so nothing competed")
    if not second["claimed_at"] >= first["settled_at"]:
        why.append("the second was claimed before the first settled")
    return why


#: Each test of the sequence: its name, the steps whose plays it reads, and its check, which
#: returns why it doesn't hold.
STEP_TESTS: tuple[tuple[str, tuple[str, ...], Callable[..., list[str]]], ...] = (
    ("the marks are made, and the reader sees them", ("marked",), _marks_seen),
    ("nothing is left after a completed play", ("after-a-completed-play",), _nothing_left),
    ("the failed play's setup did fail", ("marked-setup-fails",), _setup_failed),
    ("nothing is left after a failed play", ("after-a-failed-play",), _nothing_left),
    ("the cancelled play was interrupted", ("marked-cancelled",), _interrupted),
    ("nothing is left after an interrupted play", ("after-an-interrupted-play",), _nothing_left),
    (
        "the baseline reads the same before and after the candidates",
        ("baseline-first", "baseline-again"),
        _same_baseline,
    ),
    (
        "two plays queued together run one after the other, each on its own tree",
        ("competing-marked", "competing-reading"),
        _one_waited,
    ),
)


def _one_place(plays: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every completed play read the same place baseline, and named it."""
    places = sorted({p["place_baseline"] or "unnamed" for p in plays if p["status"] == "completed"})
    return [] if len(places) == 1 and places != ["unnamed"] else [f"read {places}"]


def _own_revisions(plays: Sequence[Mapping[str, Any]]) -> list[str]:
    """Each completed play ran the revision it was asked for, each tree staged as one revision,
    and no two trees as the same one."""
    why = []
    ran_other = [
        p["step"]
        for p in plays
        if p["status"] == "completed" and p["ran_source_revision"] != p["source_revision"]
    ]
    if ran_other:
        why.append(f"ran a revision other than the one asked: {ran_other}")
    by_tree: dict[str, set[str]] = {}
    for play in plays:
        by_tree.setdefault(play["tree"], set()).add(play["source_revision"])
    mixed = sorted(tree for tree, revisions in by_tree.items() if len(revisions) != 1)
    if mixed:
        why.append(f"one tree staged as more than one revision: {mixed}")
    if len(set().union(*by_tree.values())) < len(by_tree):
        why.append("two trees staged as one revision")
    return why


def read_sequence(document: Mapping[str, Any]) -> dict[str, Any]:
    """Case 12's reading of a sequence's record: each test, whether it holds, and why not.
    A test whose plays the record doesn't hold is not read (``holds`` is ``None``), never
    passed, and a sequence that stopped early is not isolated whatever its tests read."""
    plays = document["plays"]
    by_step = {play["step"]: play for play in plays}
    tests: dict[str, dict[str, Any]] = {}
    for name, needs, check in STEP_TESTS:
        missing = [step for step in needs if step not in by_step]
        if missing:
            tests[name] = {"holds": None, "why": [f"not read: no play of {', '.join(missing)}"]}
            continue
        why = check(*(by_step[step] for step in needs))
        tests[name] = {"holds": not why, "why": why}
    for name, check in (
        ("every completed play read one place baseline", _one_place),
        ("every play ran the revision asked, and each tree is its own", _own_revisions),
    ):
        why = check(plays) if plays else ["not read: no play"]
        tests[name] = {"holds": (not why) if plays else None, "why": why}
    return {
        "isolated": all(t["holds"] is True for t in tests.values()) and not document["stopped"],
        "stopped": document["stopped"],
        "tests": tests,
    }


# --------------------------------------------------------------------------------- composition


async def _play(args: argparse.Namespace) -> int:
    from squadops.remote_execution.scenario import frozen_scenario

    baseline_file = Path(args.baseline_scenario)
    try:
        async with measured.runtime_ports(args.project, args.commit) as ports:
            scenarios = {
                "baseline": frozen_scenario(
                    json.loads(baseline_file.read_text(encoding="utf-8")), ports.vocabulary
                ),
                "present": frozen_scenario(
                    marks_scenario("isolation-marks-present", "present"), ports.vocabulary
                ),
                "absent": frozen_scenario(
                    marks_scenario("isolation-nothing-left", "absent"), ports.vocabulary
                ),
                "unmet": frozen_scenario(unmet_setup_scenario(), ports.vocabulary),
            }
            trees = {
                "baseline": ports.staged,
                "marked": marked_tree(ports.staged),
                "reading": reading_tree(ports.staged),
            }
            run = uuid.uuid4().hex[:8]
            requests = sequence_requests(
                run, trees=trees, scenarios=scenarios,
                provider=ports.provider, operation=ports.operation,
            )  # fmt: skip
            if args.dry_run:
                no_worker = await ports.registry.no_worker_for(ports.provider, ports.operation)
                print(json.dumps({
                    "dry_run": True,
                    "commit": ports.commit,
                    "steps": [s.name for s in SEQUENCE],
                    "revisions": {t: requests[i].source_revision for i, t in
                                  ((0, "baseline"), (1, "marked"), (2, "reading"))},
                    "scenarios": {name: s.digest for name, s in scenarios.items()},
                    "worker": "serving" if no_worker is None else no_worker.reason,
                }, indent=2))  # fmt: skip
                return 0 if no_worker is None else 1
            plays, stopped = await run_sequence(
                ports.registry,
                ports.store,
                SEQUENCE,
                requests,
                {"cycle_id": f"{OWNER_PREFIX}{run}", "requester": "play_isolation_sequence"},
                play_timeout_seconds=args.play_timeout_seconds,
            )
            commit = ports.commit
    except (RuntimeError, ValueError) as e:
        print(f"{e}: nothing was played", file=sys.stderr)
        return 2
    document = {
        "schema": SEQUENCE_SCHEMA,
        "project": args.project,
        "commit": commit,
        "scenarios": {name: s.digest for name, s in scenarios.items()},
        "stopped": stopped,
        "plays": plays,
    }
    document["reading"] = read_sequence(document)
    print(json.dumps(document, indent=2))
    return 0 if document["reading"]["isolated"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    play = commands.add_parser("play", help="play the sequence through this box's runtime")
    play.add_argument("--project", required=True)
    play.add_argument("--commit", required=True, help="the pinned baseline commit, in full")
    play.add_argument("--baseline-scenario", required=True,
                      help="the scenario the baseline's two plays run")  # fmt: skip
    play.add_argument("--play-timeout-seconds", type=float, default=600.0)
    play.add_argument("--dry-run", action="store_true",
                      help="build the trees and the scenarios, and queue nothing")  # fmt: skip
    read = commands.add_parser("read", help="read a sequence's record")
    read.add_argument("record")
    args = parser.parse_args(argv)
    if args.command == "play":
        return asyncio.run(_play(args))
    reading = read_sequence(json.loads(Path(args.record).read_text(encoding="utf-8")))
    print(json.dumps(reading, indent=2))
    return 0 if reading["isolated"] else 1


if __name__ == "__main__":
    sys.exit(main())
