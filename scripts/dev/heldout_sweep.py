#!/usr/bin/env python3
"""Prediction 2's sweep (the 2.4 window's pre-registration §4; SIP-0113): no held-out scenario step
reaches anywhere the squad or the product can see.

The markers are the suite's own step values: each string a step sends (its ``json`` and ``headers``)
and each a check expects (``equals``, ``in``, ``where``), at least ``MIN_LEN`` characters with a
letter in it. The goal is left out, since goals are visible by design (D2(1)). The suite is read
from its file outside the repository, and its digest must be the pinned one, so the sweep can't
search for another revision's values.

**No value leaves a matcher.** Each target is searched where it lives, with the markers passed on
stdin, and answers with counts. The output names a marker by a hash of its value, its scenario and
the step or check it came from: never the value, never a goal, never a file's content.

The places searched, as §4 lists them:
- **the deploy's databases** (`squadops`, `langfuse`, `postgres`), dumped and matched by table. That
  covers the stored authoring envelopes, the task envelopes, the runs' records and LangFuse's
  generations. The suite's own store (`scenario_suites`) is left out, since it is where the suite
  lives; the evaluator's own records (`scenario_evaluations`) are searched, and reported apart;
- **the vault's files** for the window's cycles: every artifact, the products' delivered trees
  included;
- **the agent containers, the runtime API's and the sandbox service's,** under the directories
  their work writes (``/app``, ``/tmp``, home directories), with the sandbox's workspaces among
  them. Never ``/run``, where the secrets are mounted.

Run on the Spark after the window's last campaign, before any later deploy, as the supervisor:

    python scripts/dev/heldout_sweep.py --suite ~/squadops-heldout/2-4-window/group_run-suite.yaml \\
        --digest db69fd37 --campaign cmp_… cmp_… > var/window/2-4-0/p2-sweep.json

Exits 0 when no marker is found outside the suite's own store and the evaluator's records, and 1
otherwise. A target that can't be searched is reported as such, and also exits 1, since an
unsearched place is not a clean one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

#: A shorter value is too likely to be a word anyone would write.
MIN_LEN = 6
#: The suite's own store: where the values are supposed to be.
OWN_STORE = frozenset({"scenario_suites"})
#: The evaluator's own records: searched and reported apart, since they're not the squad's.
EVALUATOR_RECORDS = frozenset({"scenario_evaluations"})
DATABASES = ("squadops", "langfuse", "postgres")
AGENT_ROOTS = ("/app", "/tmp", "/root", "/home")
SERVICE_ROOTS = {
    "squadops-runtime-api": ("/tmp", "/root"),
    "squadops-sandbox-service": ("/tmp", "/app", "/root"),
}
#: The squad's containers, by their image (``squad-ops-<role>``); the console serves pages only.
_AGENT_IMAGE = re.compile(r"^squad-ops-(?!squadops-console$|runtime-api$|sandbox-service$)")

_COPY = re.compile(r"^COPY (?:public\.)?\"?([A-Za-z0-9_]+)\"? ")


def marker_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


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
            sources += [(f"step {n}", step.get("json")), (f"step {n}", step.get("headers"))]
        for n, check in enumerate(scenario.checks, start=1):
            sources += [(f"check {n}", check.get(k)) for k in ("equals", "in", "where")]
        for where, value in sources:
            for text in _strings(value):
                if _distinctive(text):
                    found.setdefault(
                        marker_id(text),
                        {"value": text, "scenario": scenario.scenario_id, "where": where},
                    )
    return found


def match_dump(lines: Iterable[str], values: dict[str, str]) -> dict[str, Counter]:
    """Each table of a ``pg_dump --data-only`` stream, and how often each marker id occurs in its
    rows. A row is attributed to the ``COPY`` block it sits in."""
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
        for mid, value in values.items():
            if value in line:
                hits.setdefault(table, Counter())[mid] += line.count(value)
    return hits


#: Runs inside a container: walks the roots in argv, matches every file against the markers read
#: from stdin, and prints only paths and marker ids. Kept to the standard library and Python 3.8.
WALKER = r"""
import json, os, sys
values = json.load(sys.stdin)
encoded = {mid: v.encode("utf-8") for mid, v in values.items()}
hits, files, skipped = {}, 0, 0
for root in sys.argv[1:]:
    for here, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.join(here, d).startswith(("/proc", "/sys", "/dev", "/run"))]
        for name in names:
            path = os.path.join(here, name)
            try:
                if not os.path.isfile(path) or os.path.islink(path) or os.path.getsize(path) > 50_000_000:
                    skipped += 1
                    continue
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                skipped += 1
                continue
            files += 1
            found = sorted(mid for mid, v in encoded.items() if v in data)
            if found:
                hits[path] = found
print(json.dumps({"files": files, "skipped": skipped, "hits": hits}))
"""


def _walker_program(values: dict[str, str]) -> str:
    """The walker with its markers inlined as a literal, since its stdin is the program itself."""
    return WALKER.replace("values = json.load(sys.stdin)", f"values = {json.dumps(values)}", 1)


def walk(container: str, roots: Iterable[str], values: dict[str, str]) -> dict:
    """Run the walker in ``container`` over ``roots``. The program, markers included, reaches the
    container on stdin only: never in argv, which ``ps`` shows."""
    done = subprocess.run(
        ["docker", "exec", "-i", "-u", "root", container, "python3", "-", *roots],
        input=_walker_program(values),
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if done.returncode != 0:
        return {"error": f"the walker exited {done.returncode}: {done.stderr.strip()[-300:]}"}
    return json.loads(done.stdout)


def sweep_databases(values: dict[str, str]) -> dict:
    out: dict[str, Any] = {}
    for db in DATABASES:
        dump = subprocess.Popen(
            ["docker", "exec", "squadops-postgres", "pg_dump", "-U", "squadops", "-d", db,
             "--data-only", *[f"--exclude-table=public.{t}" for t in OWN_STORE]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
        )  # fmt: skip
        assert dump.stdout is not None
        hits = match_dump(dump.stdout, values)
        code = dump.wait()
        if code != 0:
            err = dump.stderr.read() if dump.stderr else ""
            out[db] = {"error": f"pg_dump exited {code}: {err.strip()[-300:]}"}
            continue
        out[db] = {"tables": {t: dict(c) for t, c in sorted(hits.items())}}
    return out


def window_cycles(campaigns: Iterable[str]) -> list[str]:
    ids = ",".join(f"'{c}'" for c in campaigns if re.fullmatch(r"cmp_[0-9a-f]{12}", c))
    if not ids:
        return []
    done = subprocess.run(
        ["docker", "exec", "squadops-postgres", "psql", "-U", "squadops", "-d", "squadops", "-tAc",
         f"select cycle_id from cycle_registry where campaign_id in ({ids}) order by cycle_id"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def agent_containers() -> list[str]:
    done = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"], capture_output=True, text=True,
        check=True,
    )  # fmt: skip
    names = []
    for line in done.stdout.splitlines():
        name, _, image = line.partition("\t")
        if _AGENT_IMAGE.match(image) and name.startswith("squadops-"):
            names.append(name)
    return sorted(names)


def found_outside(report: dict) -> list[str]:
    """Every place a marker was found that it shouldn't be, or that couldn't be searched."""
    bad = []
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
        else:
            bad += [
                f"container {container}: {path} {mids}" for path, mids in result["hits"].items()
            ]
    return bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--suite", type=Path, required=True, help="the held-out suite's YAML")
    p.add_argument("--digest", required=True, help="the pinned suite's digest, or its prefix")
    p.add_argument("--campaign", nargs="*", default=[], help="the window's campaigns")
    a = p.parse_args(argv)

    import yaml

    from squadops.scenarios.models import parse_suite

    suite = parse_suite(yaml.safe_load(a.suite.read_text(encoding="utf-8")))
    if not suite.digest.startswith(a.digest):
        print(
            f"the suite's digest is {suite.digest[:12]}, not the pinned {a.digest}", file=sys.stderr
        )
        return 2
    found = markers(suite)
    values = {mid: m["value"] for mid, m in found.items()}
    provenance = {mid: {"scenario": m["scenario"], "where": m["where"]} for mid, m in found.items()}

    cycles = window_cycles(a.campaign)
    vault_roots = [f"/app/data/artifacts/group_run/{c}" for c in cycles]
    report: dict[str, Any] = {
        "suite_digest": suite.digest,
        "markers": len(values),
        "marker_provenance": provenance,
        "window_cycles": cycles,
        "databases": sweep_databases(values),
        "containers": {},
    }
    report["containers"]["squadops-runtime-api (vault)"] = walk(
        "squadops-runtime-api", vault_roots, values
    )
    for container, roots in SERVICE_ROOTS.items():
        report["containers"][container] = walk(container, roots, values)
    for container in agent_containers():
        report["containers"][container] = walk(container, AGENT_ROOTS, values)

    outside = found_outside(report)
    report["found_outside"] = outside
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if outside else 0


if __name__ == "__main__":
    raise SystemExit(main())
