#!/usr/bin/env python3
"""Before a push or a post: no held-out scenario step value in what it adds.

The remedy for the 2.4 window's prediction 2, as the owner ruled it on 2026-10-21: a held-out
value had reached a public file as example data. CI can't catch that, because the suite lives
outside every repository. So this
runs where the suite is, before a push, and reads the same markers the sweep does
(``heldout_sweep.markers``): each string a step sends and each one a check expects, the goal left
out.

It reads the lines a git range adds (``--range``, ``origin/main...HEAD`` when not given) and every
text file named with ``--text`` (a pull request's body, a comment, before it's posted). A value is
matched in each form ``heldout_sweep.forms`` names, and it answers with counts and each found
marker's keyed hash, scenario and step. **Never a value, never a line.**

    python scripts/dev/heldout_text_scan.py --suite ~/squadops-heldout/2-4-window/group_run-suite.yaml \\
        [--suite …] [--range origin/main...HEAD] [--text body.md …]

It exits 0 when nothing is found, 1 when a marker is, and 2 when a suite can't be read or the range
can't be diffed. A suite's revisions are each named with ``--suite``, since a value an earlier
revision held is still that suite's.

**As a git hook:** ``scripts/dev/hooks/pre-push`` runs it for each ref pushed, when
``SQUADOPS_HELDOUT_SUITES`` names the suites (colon-separated), and does nothing otherwise. A clone
without the suite pushes as before. To install it in a checkout that holds the suite:

    ln -s ../../scripts/dev/hooks/pre-push .git/hooks/pre-push
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_SWEEP = Path(__file__).resolve().parent / "heldout_sweep.py"


def _sweep() -> Any:
    """The sweep's own marker reading, so the two can never disagree about what a marker is."""
    spec = importlib.util.spec_from_file_location("heldout_sweep", _SWEEP)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("heldout_sweep", module)
    spec.loader.exec_module(module)
    return module


def suite_markers(paths: list[Path]) -> dict[str, dict[str, str]]:
    """Every marker of every suite named, by its keyed id. Raises ``ValueError`` naming the file,
    never quoting it, when one can't be read."""
    import yaml

    from squadops.scenarios.models import parse_suite

    sweep = _sweep()
    found: dict[str, dict[str, str]] = {}
    for path in paths:
        try:
            suite = parse_suite(yaml.safe_load(path.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001 — named by file, never by content
            raise ValueError(f"{path}: the suite doesn't parse ({type(e).__name__})") from None
        for mid, marker in sweep.markers(suite).items():
            found.setdefault(mid, marker)
    return found


def added_lines(range_: str, cwd: Path | None = None) -> str:
    """The lines ``range_`` adds, without the diff's own headers."""
    out = subprocess.run(
        ["git", "diff", "--no-color", "--unified=0", range_],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if out.returncode != 0:
        raise ValueError(f"git diff {range_} failed: {out.stderr.strip().splitlines()[-1:]}")
    return "\n".join(
        line[1:]
        for line in out.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def hits(markers: dict[str, dict[str, str]], text: str) -> list[dict[str, str]]:
    """Each marker found in ``text``, in any of its stored forms: its id, scenario and step only."""
    forms = _sweep().forms
    return [
        {"marker": mid, "scenario": m["scenario"], "where": m["where"]}
        for mid, m in sorted(markers.items())
        if any(form in text for form in forms(m["value"]))
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--suite", type=Path, action="append", required=True)
    p.add_argument("--range", default="origin/main...HEAD")
    p.add_argument("--no-range", action="store_true", help="scan only the --text files")
    p.add_argument("--text", type=Path, action="append", default=[])
    a = p.parse_args(argv)
    try:
        markers = suite_markers(a.suite)
        sources = {} if a.no_range else {f"git diff {a.range}": added_lines(a.range)}
        for path in a.text:
            sources[str(path)] = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    report = {
        "markers": len(markers),
        "sources": {name: hits(markers, text) for name, text in sources.items()},
    }
    found = sum(len(h) for h in report["sources"].values())
    report["found"] = found
    print(json.dumps(report, indent=2))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
