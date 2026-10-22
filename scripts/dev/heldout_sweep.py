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
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[2]
#: A shorter value is too likely to be a word anyone would write.
MIN_LEN = 6
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
_FULL_TEXT = re.compile(r'"data"\s*:\s*"([A-Za-z0-9+/=]{16,})"')


def marker_id(value: str) -> str:
    return hmac.new(_KEY, value.encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def forms(value: str) -> list[str]:
    """``value`` as each store writes it: as is, JSON-escaped (ASCII and not), and each of those
    with COPY's doubled backslashes. Distinct, in that order."""
    out: list[str] = []
    for form in (value, json.dumps(value)[1:-1], json.dumps(value, ensure_ascii=False)[1:-1]):
        for f in (form, form.replace("\\", "\\\\")):
            if f not in out:
                out.append(f)
    return out


def _strings(value: Any) -> Iterator[str]:
    """Every string leaf of ``value``. A mapping's keys are names (a concept, a field), not values."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _strings(v)


def _query_values(path: Any) -> list[str]:
    if not isinstance(path, str) or "?" not in path:
        return []
    return [v for _, v in parse_qsl(urlsplit(path).query, keep_blank_values=False)]


#: A pattern's characters that aren't literal text (SIP-0113 §10p ruling 9).
_PATTERN_SYNTAX = frozenset(".^$*+?()[]{}|")
_GROUP_PREFIX = re.compile(r"\(\?(?:[:=!]|<[=!])")


def _literal_runs(pattern: Any) -> list[str]:
    """The literal text inside a browser check's pattern, run by run: an escaped punctuation mark
    is its own character, and a class (``\\d``, ``\\s``) or any other syntax ends a run. So a run
    title a scenario looks for is a marker, and the pattern's syntax around it isn't."""
    if not isinstance(pattern, str):
        return []
    pattern = _GROUP_PREFIX.sub("(", pattern)  # (?: (?= (?! (?<= (?<! open a group, nothing else
    runs, run, i = [], [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            nxt = pattern[i + 1]
            if nxt.isalnum():
                runs.append("".join(run))
                run = []
            else:
                run.append(nxt)
            i += 2
            continue
        if c in _PATTERN_SYNTAX:
            runs.append("".join(run))
            run = []
        else:
            run.append(c)
        i += 1
    runs.append("".join(run))
    return [r.strip() for r in runs if r.strip()]


def _browser_values(item: Any) -> list[Any]:
    """What a browser step types (``value``), and the text a step or a check finds its control by
    (``text``, its ``near``'s included). Never a target's candidate names: they are drafted from the
    deliveries' own labels (§10p ruling 3), so a delivery holding one is no leak."""
    found: list[Any] = [item.get("value")]
    target = item.get("target")
    while isinstance(target, dict):
        found.append(target.get("text"))
        target = target.get("near")
    return found


def _distinctive(value: str) -> bool:
    stripped = value.strip()
    return len(stripped) >= MIN_LEN and any(c.isalpha() for c in stripped)


def markers(suite: Any) -> dict[str, dict[str, str]]:
    """Each distinct marker of ``suite`` (a ``ScenarioSuite``), by its id: its value, and the first
    scenario and step or check it was found in."""
    found: dict[str, dict[str, str]] = {}
    for scenario in suite.scenarios:
        sources: list[tuple[str, Any]] = []
        for n, step in enumerate(scenario.steps, start=1):
            sources += [
                (f"step {n}", step.get("json")),
                (f"step {n}", step.get("headers")),
                (f"step {n}", _query_values(step.get("path"))),
                *((f"step {n}", v) for v in _browser_values(step)),
            ]
        for n, check in enumerate(scenario.checks, start=1):
            sources += [(f"check {n}", check.get(k)) for k in ("equals", "in", "contains", "where")]
            sources += [(f"check {n}", v) for v in _browser_values(check)]
            patterns = [check.get("pattern"), *(check.get("patterns") or ())]
            sources += [(f"check {n}", _literal_runs(p)) for p in patterns]
        for where, value in sources:
            for text in _strings(value):
                if _distinctive(text):
                    found.setdefault(
                        marker_id(text),
                        {"value": text, "scenario": scenario.scenario_id, "where": where},
                    )
    return found


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


def match_dump(lines: Iterable[str], values: dict[str, str]) -> dict[str, Counter]:
    """Each table of a ``pg_dump --data-only`` stream, and how often each marker id occurs in its
    rows, in any of its forms, and in any full prompt a row holds. A row is attributed to the
    ``COPY`` block it sits in."""
    searched = {mid: forms(v) for mid, v in values.items()}
    hits: dict[str, Counter] = {}
    table = "-"
    for line in lines:
        start = _COPY.match(line)
        if start:
            table = start.group(1)
            continue
        if line.startswith("\\."):
            table = "-"
            continue
        texts = [line, *_full_texts(line)]
        for mid, variants in searched.items():
            n = sum(text.count(f) for text in texts for f in variants)
            if n:
                hits.setdefault(table, Counter())[mid] += n
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


def dump_command(db: str) -> list[str]:
    """The dump the sweep reads ``db`` from: its data, without the suite's own store."""
    return ["docker", "exec", "squadops-postgres", "pg_dump", "-U", "squadops", "-d", db,
            "--data-only", *[f"--exclude-table=public.{t}" for t in sorted(OWN_STORE)]]  # fmt: skip


def sweep_databases(values: dict[str, str]) -> dict:
    out: dict[str, Any] = {}
    for db in DATABASES:
        try:
            dump = subprocess.Popen(
                dump_command(db), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace",
            )  # fmt: skip
            assert dump.stdout is not None
            hits = match_dump(dump.stdout, values)
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


def found_outside(report: dict) -> list[str]:
    """Every place a marker was found that it shouldn't be, or that couldn't be searched."""
    bad = list(report.get("unsearched", []))
    for db, result in report["databases"].items():
        if "error" in result:
            bad.append(f"database {db}: not searched ({result['error']})")
            continue
        for table, counts in result["tables"].items():
            if table not in EVALUATOR_RECORDS and counts:
                bad.append(f"database {db}, table {table}: {sorted(counts)}")
    for container, result in report["containers"].items():
        if "error" in result:
            bad.append(f"container {container}: not searched ({result['error']})")
            continue
        if result.get("missing_roots"):
            bad.append(f"container {container}: roots not there {result['missing_roots']}")
        if not result.get("files"):
            bad.append(f"container {container}: no file read")
        bad += [f"container {container}: {path} {mids}" for path, mids in result["hits"].items()]
    return bad


def sweep(values: dict[str, str], campaigns: list[str]) -> dict[str, Any]:
    """Every target searched for ``values``, each failure kept in the report."""
    report: dict[str, Any] = {"unsearched": [], "containers": {}}
    report["databases"] = sweep_databases(values)
    try:
        cycles = window_cycles(campaigns)
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        cycles = []
        report["unsearched"].append(f"the window's cycles: {type(e).__name__}: {e}")
    report["window_cycles"] = cycles
    if cycles:
        report["containers"]["squadops-runtime-api (vault)"] = walk(
            "squadops-runtime-api", [f"/app/data/artifacts/group_run/{c}" for c in cycles], values
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
    found = markers(suite)
    values = {mid: m["value"] for mid, m in found.items()}
    report = sweep(values, a.campaign)
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
    outside = found_outside(report)
    report["found_outside"] = outside
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if outside else 0


if __name__ == "__main__":
    raise SystemExit(main())
