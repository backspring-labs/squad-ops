#!/usr/bin/env python3
"""Before a held-out suite is drafted, refuse a marker already public (#2617; SIP-0113 §4.1).

A step's or a check's value that the repository's files or history, or the vault's stored
deliveries, already hold can't discriminate a leak: the squad can write it from what it sees, and a
sweep that finds it says nothing about the suite. At the 2.4 window's close, 9 of the 10 markers
found outside the suite's store were that kind, and the reading that set them apart was post hoc.
So the check runs at draft time, where the suite lives, and the author replaces each value it
names before the owner reviews the suite:

    python scripts/dev/heldout_public_check.py --suite ~/squadops-heldout/<window>/group_run-suite.yaml

**What it reads:** the markers, as the sweep reads them (``squadops.scenarios.markers``), never a
goal. It searches for each in every form a store writes it in:
- every file the repository tracks, at HEAD;
- the repository's history, every commit's patch (``git log --all -p``);
- every file under the vault (``data/artifacts``).

**What it prints:** each found marker by its keyed id (a key fresh for each run), its scenario and
the step or check it came from, and where it was found: tracked paths, a count of commits, vault
paths. **Never a value.** All matching is in this process, so no value is ever in an argument list
(``ps`` shows those).

**An unsearched place is not a clean one:** a vault that isn't there fails the check, unless
``--no-vault`` says so (a clone that holds no vault).

Exits 0 when no marker is found and every place was searched, 1 otherwise, and 2 when the suite
can't be read.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_SWEEP = Path(__file__).resolve().parent / "heldout_sweep.py"
#: A file larger than this is a binary or a bundle, not something an author wrote.
MAX_BYTES = 10 * 1024 * 1024
#: How many places of each kind the report names, beside its count.
NAMED = 5


def _sweep() -> Any:
    """The sweep's own marker reading and keyed ids, so the two never disagree about a marker."""
    spec = importlib.util.spec_from_file_location("heldout_sweep", _SWEEP)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("heldout_sweep", module)
    spec.loader.exec_module(module)
    return module


class Matcher:
    """Every marker's every form in one pattern, so a line is searched once."""

    def __init__(self, values: dict[str, str], forms: Any) -> None:
        self._owner: dict[str, set[str]] = {}
        for mid, value in values.items():
            for form in forms(value):
                self._owner.setdefault(form, set()).add(mid)
        alternatives = sorted(self._owner, key=len, reverse=True)
        self._pattern = re.compile("|".join(map(re.escape, alternatives))) if alternatives else None

    def found(self, text: str) -> set[str]:
        if self._pattern is None:
            return set()
        hits: set[str] = set()
        for match in self._pattern.finditer(text):
            hits |= self._owner[match.group(0)]
        return hits


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def tracked(repo: Path, matcher: Matcher) -> dict[str, list[str]]:
    """Each marker id, and the tracked files at HEAD that hold it."""
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode()
    found: dict[str, list[str]] = {}
    for rel in filter(None, listed.split("\0")):
        text = _read(repo / rel)
        for mid in matcher.found(text) if text else ():
            found.setdefault(mid, []).append(rel)
    return found


def history(repo: Path, matcher: Matcher) -> dict[str, set[str]]:
    """Each marker id, and the commits whose patch holds it, any branch."""
    log = subprocess.Popen(
        ["git", "-C", str(repo), "log", "--all", "-p", "--no-color", "--format=commit:%H"],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert log.stdout is not None
    found: dict[str, set[str]] = {}
    commit = ""
    for line in log.stdout:
        if line.startswith("commit:"):
            commit = line[7:].strip()
            continue
        for mid in matcher.found(line):
            found.setdefault(mid, set()).add(commit)
    if log.wait() != 0:
        raise RuntimeError(f"git log exited {log.returncode}")
    return found


def vault(root: Path, matcher: Matcher) -> dict[str, list[str]]:
    """Each marker id, and the vault's files that hold it."""
    found: dict[str, list[str]] = {}
    for directory, _dirs, files in os.walk(root):
        for name in files:
            path = Path(directory) / name
            text = _read(path)
            for mid in matcher.found(text) if text else ():
                found.setdefault(mid, []).append(str(path.relative_to(root)))
    return found


def report(
    markers: dict[str, dict[str, str]],
    places: Iterable[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    found: dict[str, dict[str, Any]] = {}
    for kind, hits in places:
        for mid, where in hits.items():
            entry = found.setdefault(
                mid, {"scenario": markers[mid]["scenario"], "where": markers[mid]["where"]}
            )
            entry[f"{kind}_count"] = len(where)
            if kind != "history":
                entry[kind] = sorted(where)[:NAMED]
    return {"markers": len(markers), "found": dict(sorted(found.items()))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--suite", type=Path, required=True, help="the draft suite's YAML")
    p.add_argument("--repo", type=Path, default=ROOT, help="the repository (default: this one)")
    p.add_argument(
        "--vault", type=Path, default=ROOT / "data" / "artifacts", help="the vault's directory"
    )
    p.add_argument("--no-vault", action="store_true", help="this clone holds no vault")
    a = p.parse_args(argv)

    import yaml

    from squadops.scenarios.models import parse_suite

    try:
        suite = parse_suite(yaml.safe_load(a.suite.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001 — its message could quote the suite, so it's not shown
        print(f"the suite file doesn't parse ({type(e).__name__}); not checked", file=sys.stderr)
        return 2
    sweep = _sweep()
    markers = sweep.markers(suite)
    matcher = Matcher({mid: m["value"] for mid, m in markers.items()}, sweep.forms)
    places = [("tracked", tracked(a.repo, matcher)), ("history", history(a.repo, matcher))]
    unsearched = []
    if a.vault.is_dir():
        places.append(("vault", vault(a.vault, matcher)))
    elif not a.no_vault:
        unsearched.append(f"the vault: {a.vault} isn't there")
    out = report(markers, places) | {"unsearched": unsearched}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 1 if out["found"] or unsearched else 0


if __name__ == "__main__":
    raise SystemExit(main())
