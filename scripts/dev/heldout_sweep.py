#!/usr/bin/env python3
"""Prediction 2's sweep (the 2.4 window's pre-registration §4; SIP-0113): no held-out scenario step
reaches anywhere the squad or the product can see.

The markers are the suite's own step values: each string a step sends (its ``json``, ``headers`` and
query string) and each a check expects (``equals``, ``in``, ``contains``, ``where``), at least
``MIN_LEN`` characters with a letter in it. The goal is left out, since goals are visible by design
(D2(1)). The suite is read from its file outside the repository, and its digest must be the pinned
one, so the sweep can't search for another revision's values.

**No value leaves a matcher.** Each target is searched where it lives, with the markers inside the
matcher's program on stdin, and answers with counts. The output names a marker by a keyed hash of
its value (the key made fresh for each run and never written, so an id can't be checked against a
guessed value), its scenario and the step or check it came from: never the value, never a goal,
never a file's content.

**A value is searched in every form a store writes it in:** as is, JSON-escaped with and without
ASCII escaping, and each of those with COPY's doubled backslashes. LangFuse keeps a long prompt whole
only gzip+base64 in its metadata (#1756), so each such blob is decoded and searched too.

The places searched, as §4 lists them:
- **the deploy's databases** (`squadops`, `langfuse`, `postgres`), dumped and matched by table: the
  stored authoring envelopes, the task envelopes, the runs' records, Prefect's tables and LangFuse's
  generations. The suite's own store (`scenario_suites`) is left out, since it is where the suite
  lives; the evaluator's own records (`scenario_evaluations`) are searched, and reported apart;
- **the vault's files** for the window's cycles: every artifact, the products' delivered trees
  included;
- **every agent container the compose file defines,** the runtime API's and the sandbox service's,
  under the directories their work writes, with the sandbox's workspaces among them. Never ``/run``,
  where the secrets are mounted.

**An unsearched place is not a clean one.** A database that didn't dump, a container that didn't
answer, a root that doesn't exist, a walk that read no file, an agent the compose file defines that
isn't running, or no window cycle to walk, is reported and exits 1, as a found marker does.

Run on the Spark after the window's last campaign, before any later deploy, as the supervisor:

    python scripts/dev/heldout_sweep.py --suite ~/squadops-heldout/2-4-window/group_run-suite.yaml \\
        --digest db69fd37 --campaign cmp_… cmp_… > var/window/2-4-0/p2-sweep.json

Exits 0 when no marker is found outside the suite's own store and the evaluator's records and every
place was searched, 1 otherwise, and 2 when the suite isn't the pinned one or doesn't parse.

**``--goals`` searches for the goals instead** (SIP-0113 §10t ruling 7). A campaign's proposal is
shown each goal's statement (§4.5), so a statement belongs only in the proposal task's own records
and the evaluator's. Each goal is a marker. A table with a ``task_type`` column is counted by task
type, and LangFuse's observations by the task span each hangs under (its own name, or its
parent's: every generation's parent is a ``task-…`` span), so the proposal's rows are told from any
other role's. Only ``EXCUSED_FOR_GOALS`` and the evaluator's records aren't counted as found. Each
goal must also be found there at least once (``goals_not_found_in_proposals``): a search that finds
no goal where the proposal was shown them didn't search for what it claims.

**Beyond the deploy,** ``--host-root`` walks a directory on the host with the same walker: the
campaign's log archive (``var/campaigns/<campaign>/``), which a Release attaches.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import hmac
import json
import re
import secrets
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from squadops.scenarios.markers import distinctive, forms, suite_markers

ROOT = Path(__file__).resolve().parents[2]
#: The suite's own store: where the values are supposed to be. A page scenario's evidence is held
#: out with it (SIP-0113 §10p ruling 9): its screenshot and the errors it kept can show the values.
OWN_STORE = frozenset({"scenario_suites", "scenario_evidence"})
#: The evaluator's own records: searched and reported apart, since they're not the squad's.
EVALUATOR_RECORDS = frozenset({"scenario_evaluations"})
DATABASES = ("squadops", "langfuse", "postgres")
AGENT_ROOTS = ("/app", "/tmp", "/root", "/home")
SERVICE_ROOTS = {
    "squadops-runtime-api": ("/tmp", "/app/cycle_data", "/root"),
    "squadops-sandbox-service": ("/tmp", "/app", "/root"),
}
#: A run's own key, so a marker id can't be checked against a guessed value. Never written.
_KEY = secrets.token_bytes(32)

_COPY = re.compile(r"^COPY (?:public\.)?\"?([A-Za-z0-9_]+)\"? ")
_COPY_COLUMNS = re.compile(r"\(([^)]*)\) FROM stdin")
#: --goals: the task whose inputs and prompt show the goals (§4.5), and the column that names it.
PROPOSAL_TASK = "strategy.propose_increment"
TASK_COLUMN = "task_type"
#: LangFuse's observations, attributed to the task span each hangs under: ``(id, name, parent)``.
SPANS = {"observations": ("id", "name", "parent_observation_id")}
#: The label of a ``SPANS`` row that hangs under no task span.
NO_TASK_SPAN = "no_task_span"
#: Where a goal's statement is the proposal's own (the places the dumps show its prompt is kept):
#: its authoring envelopes and its LangFuse generations.
EXCUSED_FOR_GOALS = frozenset(
    {f"authoring_envelopes[{PROPOSAL_TASK}]", f"observations[{PROPOSAL_TASK}]"}
)
_FULL_TEXT = re.compile(r'"data"\s*:\s*"([A-Za-z0-9+/=]{16,})"')


def marker_id(value: str) -> str:
    return hmac.new(_KEY, value.encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def markers(suite: Any) -> dict[str, dict[str, str]]:
    """Each distinct marker of ``suite`` (a ``ScenarioSuite``), by its id: its value, and the first
    scenario and step or check it was found in (``squadops.scenarios.markers``, the one definition
    the runtime holds a proposal's goals back by too)."""
    return {
        marker_id(value): {"value": value, "scenario": scenario, "where": where}
        for value, (scenario, where) in suite_markers(suite).items()
    }


def goal_markers(suite: Any) -> dict[str, dict[str, str]]:
    """--goals: each scenario's goal, by its id, as ``markers`` gives each step value."""
    return {
        marker_id(s.goal): {"value": s.goal, "scenario": s.scenario_id, "where": "goal"}
        for s in suite.scenarios
        if distinctive(s.goal)
    }


def _full_texts(line: str) -> list[str]:
    """Each gzip+base64 full prompt in ``line`` (#1756), decoded; a blob that isn't one is skipped."""
    if "gzip+base64" not in line:
        return []
    texts = []
    for blob in _FULL_TEXT.findall(line):
        try:
            texts.append(gzip.decompress(base64.b64decode(blob, validate=True)).decode("utf-8"))
        except (ValueError, OSError, EOFError):
            continue
    return texts


def _span_task(name: str) -> str | None:
    """The task type a ``task-<task_id>`` span names: its last dotted segment
    (``task-task-<run>-000-strategy.propose_increment``). A task id from before #1934 was random hex
    and names none, so its rows hang under no task span, and a baseline sweep holds them."""
    if not name.startswith("task-"):
        return None
    return next((part for part in reversed(name.split("-")) if "." in part), None)


def match_dump(
    lines: Iterable[str], values: dict[str, str], *, split_by: str | None = None
) -> dict[str, Counter]:
    """Each table of a ``pg_dump --data-only`` stream, and how often each marker id occurs in its
    rows, in any of its forms, and in any full prompt a row holds. A row is attributed to the
    ``COPY`` block it sits in; with ``split_by``, to ``table[value]`` when the table has that
    column, and a ``SPANS`` table's row to ``table[task]`` by the task span it hangs under
    (``table[no_task_span]`` when it hangs under none)."""
    searched = {mid: forms(v) for mid, v in values.items()}
    hits: dict[str, Counter] = {}
    names: dict[str, str] = {}
    deferred: list[tuple[str, str, str, str, int]] = []
    table, at, span = "-", None, None
    for line in lines:
        start = _COPY.match(line)
        if start:
            table = start.group(1)
            listed = _COPY_COLUMNS.search(line)
            columns = [c.strip().strip('"') for c in listed.group(1).split(",")] if listed else []
            at = columns.index(split_by) if split_by in columns else None
            wanted = SPANS.get(table) if split_by else None
            span = (
                tuple(columns.index(c) for c in wanted)
                if wanted and all(c in columns for c in wanted)
                else None
            )
            continue
        if line.startswith("\\."):
            table, at, span = "-", None, None
            continue
        fields = line.rstrip("\n").split("\t") if (at is not None or span) else []
        if span and len(fields) > max(span):
            names[fields[span[0]]] = fields[span[1]]
        key = table
        if at is not None:
            key = f"{table}[{fields[at]}]" if at < len(fields) else table
        texts = [line, *_full_texts(line)]
        for mid, variants in searched.items():
            n = sum(text.count(f) for text in texts for f in variants)
            if not n:
                continue
            if span and len(fields) > max(span):
                deferred.append((table, fields[span[1]], fields[span[2]], mid, n))
            else:
                hits.setdefault(key, Counter())[mid] += n
    for table, name, parent, mid, n in deferred:
        task = _span_task(name) or _span_task(names.get(parent, "")) or NO_TASK_SPAN
        hits.setdefault(f"{table}[{task}]", Counter())[mid] += n
    return hits


#: Runs inside a container: walks the roots in argv, matches every file against the markers (each
#: in all its forms, inlined below), and prints only paths and marker ids. Standard library only.
WALKER = r"""
import json, os, sys
VALUES = {}
encoded = {mid: [f.encode("utf-8") for f in fs] for mid, fs in VALUES.items()}
hits, files, skipped, too_big, missing = {}, 0, 0, 0, []
for root in sys.argv[1:]:
    if not os.path.isdir(root):
        missing.append(root)
        continue
    for here, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.join(here, d).startswith(("/proc", "/sys", "/dev", "/run"))]
        for name in names:
            path = os.path.join(here, name)
            try:
                if not os.path.isfile(path) or os.path.islink(path):
                    skipped += 1
                    continue
                if os.path.getsize(path) > 50_000_000:
                    too_big += 1
                    continue
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                skipped += 1
                continue
            files += 1
            found = sorted(mid for mid, fs in encoded.items() if any(f in data for f in fs))
            if found:
                hits[path] = found
print(json.dumps({"files": files, "skipped": skipped, "too_big": too_big, "missing_roots": missing, "hits": hits}))
"""


def _walker_program(values: dict[str, str]) -> str:
    """The walker with its markers' forms inlined as a literal, since its stdin is the program
    itself. Written without ASCII escaping, so a value outside the BMP stays one character."""
    inlined = json.dumps({mid: forms(v) for mid, v in values.items()}, ensure_ascii=False)
    return WALKER.replace("VALUES = {}", f"VALUES = {inlined}", 1)


def walk(container: str, roots: Iterable[str], values: dict[str, str]) -> dict:
    """Run the walker in ``container`` over ``roots``. The program, markers included, reaches the
    container on stdin only: never in argv, which ``ps`` shows. Any failure is reported as an
    unsearched container, never raised, so one container can't lose the sweep's report."""
    try:
        done = subprocess.run(
            ["docker", "exec", "-i", "-u", "root", container, "python3", "-", *roots],
            input=_walker_program(values),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": f"the walker didn't run: {type(e).__name__}"}
    if done.returncode != 0:
        return {"error": f"the walker exited {done.returncode}: {done.stderr.strip()[-300:]}"}
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"error": "the walker's answer wasn't JSON"}


def walk_host(roots: Iterable[str], values: dict[str, str]) -> dict:
    """The walker run on the host over ``roots``, as ``walk`` runs it in a container."""
    try:
        done = subprocess.run(
            [sys.executable, "-", *roots],
            input=_walker_program(values),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": f"the walker didn't run: {type(e).__name__}"}
    if done.returncode != 0:
        return {"error": f"the walker exited {done.returncode}: {done.stderr.strip()[-300:]}"}
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"error": "the walker's answer wasn't JSON"}


def dump_command(db: str) -> list[str]:
    """The dump the sweep reads ``db`` from: its data, without the suite's own store."""
    return ["docker", "exec", "squadops-postgres", "pg_dump", "-U", "squadops", "-d", db,
            "--data-only", *[f"--exclude-table=public.{t}" for t in sorted(OWN_STORE)]]  # fmt: skip


def sweep_databases(values: dict[str, str], *, split_by: str | None = None) -> dict:
    out: dict[str, Any] = {}
    for db in DATABASES:
        try:
            dump = subprocess.Popen(
                dump_command(db), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace",
            )  # fmt: skip
            assert dump.stdout is not None
            hits = match_dump(dump.stdout, values, split_by=split_by)
            code = dump.wait()
        except OSError as e:
            out[db] = {"error": f"pg_dump didn't run: {type(e).__name__}"}
            continue
        if code != 0:
            err = dump.stderr.read() if dump.stderr else ""
            out[db] = {"error": f"pg_dump exited {code}: {err.strip()[-300:]}"}
            continue
        out[db] = {"tables": {t: dict(c) for t, c in sorted(hits.items())}}
    return out


def window_cycles(campaigns: Iterable[str]) -> list[str]:
    """The window's cycles, by its campaigns. A campaign id that isn't one is refused, never
    dropped, since dropping it would leave its cycles unwalked."""
    campaigns = list(campaigns)
    bad = [c for c in campaigns if not re.fullmatch(r"cmp_[0-9a-f]{12}", c)]
    if bad:
        raise ValueError(f"not campaign ids: {bad}")
    if not campaigns:
        return []
    ids = ",".join(f"'{c}'" for c in campaigns)
    done = subprocess.run(
        ["docker", "exec", "squadops-postgres", "psql", "-U", "squadops", "-d", "squadops", "-tAc",
         f"select cycle_id from cycle_registry where campaign_id in ({ids}) order by cycle_id"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def expected_agents(compose: Path = ROOT / "docker-compose.yml") -> list[str]:
    """The agent containers the compose file defines: each service built from the agents' image."""
    import yaml

    services = (yaml.safe_load(compose.read_text(encoding="utf-8")) or {}).get("services", {})
    names = []
    for name, service in services.items():
        build = service.get("build")
        dockerfile = build.get("dockerfile") if isinstance(build, dict) else None
        if dockerfile and "agents" in str(dockerfile):
            names.append(service.get("container_name") or name)
    return sorted(names)


def running_containers() -> set[str]:
    done = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=True
    )
    return {line.strip() for line in done.stdout.splitlines() if line.strip()}


def found_outside(report: dict, *, goals: bool = False) -> list[str]:
    """Every place a marker was found that it shouldn't be, or that couldn't be searched. With
    ``goals``, ``EXCUSED_FOR_GOALS`` isn't."""
    bad = list(report.get("unsearched", []))
    for db, result in report["databases"].items():
        if "error" in result:
            bad.append(f"database {db}: not searched ({result['error']})")
            continue
        for table, counts in result["tables"].items():
            proposals = goals and table in EXCUSED_FOR_GOALS
            if table not in EVALUATOR_RECORDS and not proposals and counts:
                bad.append(f"database {db}, table {table}: {sorted(counts)}")
    for container, result in {**report["containers"], **report.get("host", {})}.items():
        if "error" in result:
            bad.append(f"container {container}: not searched ({result['error']})")
            continue
        if result.get("missing_roots"):
            bad.append(f"container {container}: roots not there {result['missing_roots']}")
        if not result.get("files"):
            bad.append(f"container {container}: no file read")
        bad += [f"container {container}: {path} {mids}" for path, mids in result["hits"].items()]
    return bad


def sweep(
    values: dict[str, str],
    campaigns: list[str],
    *,
    split_by: str | None = None,
    host_roots: Sequence[str] = (),
) -> dict[str, Any]:
    """Every target searched for ``values``, each failure kept in the report."""
    report: dict[str, Any] = {"unsearched": [], "containers": {}}
    if host_roots:
        report["host"] = {"host": walk_host(host_roots, values)}
    report["databases"] = sweep_databases(values, split_by=split_by)
    try:
        cycles = window_cycles(campaigns)
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        cycles = []
        report["unsearched"].append(f"the window's cycles: {type(e).__name__}: {e}")
    report["window_cycles"] = cycles
    if cycles:
        # The cycles' own artifacts, and the project's unattached ones: a campaign's package and
        # digest have no cycle, and a Release attaches them.
        report["containers"]["squadops-runtime-api (vault)"] = walk(
            "squadops-runtime-api",
            [f"/app/data/artifacts/group_run/{c}" for c in cycles]
            + ["/app/data/artifacts/group_run/_unattached"],
            values,
        )
    else:
        report["unsearched"].append("the vault: no window cycle to walk")
    for container, roots in SERVICE_ROOTS.items():
        report["containers"][container] = walk(container, roots, values)
    try:
        running = running_containers()
    except (OSError, subprocess.CalledProcessError) as e:
        running = set()
        report["unsearched"].append(f"the running containers: {type(e).__name__}")
    for agent in expected_agents():
        if agent in running:
            report["containers"][agent] = walk(agent, AGENT_ROOTS, values)
        else:
            report["unsearched"].append(f"agent {agent}: not running")
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--suite", type=Path, required=True, help="the held-out suite's YAML")
    p.add_argument("--digest", required=True, help="the pinned suite's digest, or its prefix")
    p.add_argument("--campaign", nargs="*", default=[], help="the window's campaigns")
    p.add_argument(
        "--host-root",
        action="append",
        default=[],
        help="a host directory to walk too: the campaign's log archive (var/campaigns/<campaign>)",
    )
    p.add_argument(
        "--goals",
        action="store_true",
        help="search for the goals' statements, not the step values (SIP-0113 §10t ruling 7)",
    )
    a = p.parse_args(argv)

    import yaml

    from squadops.scenarios.models import parse_suite

    try:
        suite = parse_suite(yaml.safe_load(a.suite.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001 — its message could quote the suite, so it's not shown
        print(f"the suite file doesn't parse ({type(e).__name__}); not searched", file=sys.stderr)
        return 2
    if not suite.digest.startswith(a.digest):
        print(
            f"the suite's digest is {suite.digest[:12]}, not the pinned {a.digest}", file=sys.stderr
        )
        return 2
    found = goal_markers(suite) if a.goals else markers(suite)
    values = {mid: m["value"] for mid, m in found.items()}
    report = sweep(
        values, a.campaign, split_by=TASK_COLUMN if a.goals else None, host_roots=a.host_root
    )
    if a.goals:
        report["mode"] = "goals"
        # The positive control: each goal, where the proposal was shown it.
        shown = {
            mid
            for result in report["databases"].values()
            for table, counts in (result.get("tables") or {}).items()
            if table in EXCUSED_FOR_GOALS
            for mid in counts
        }
        report["goals_not_found_in_proposals"] = sorted(set(values) - shown)
    report |= {
        "suite_digest": suite.digest,
        "markers": len(values),
        "scenarios": len(suite.scenarios),
        "scenarios_without_a_marker": sum(
            1 for s in suite.scenarios if s.scenario_id not in {m["scenario"] for m in found.values()}
        ),
        "marker_provenance": {mid: {"scenario": m["scenario"], "where": m["where"]}
                              for mid, m in found.items()},
    }  # fmt: skip
    outside = found_outside(report, goals=a.goals)
    report["found_outside"] = outside
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if outside else 0


if __name__ == "__main__":
    raise SystemExit(main())
