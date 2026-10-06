#!/usr/bin/env python3
"""mypy as a ratchet (#1988): no new type error, and the baseline only shrinks.

mypy was configured and never ran; one run on main found 415 errors, among them real defects
(#1982). Fixing them all at once is not the point. Stopping new ones is: this compares a run
against ``scripts/dev/mypy_baseline.json``, keyed by file, error code and message (never line, so
an edit above an error does not move it), with a count per key.

    python scripts/dev/mypy_ratchet.py            # check: fails on a new error, or a stale baseline
    python scripts/dev/mypy_ratchet.py --update   # rewrite the baseline after fixing errors
    python scripts/dev/mypy_ratchet.py --init     # write the first baseline (none may exist)

A check fails when a key's count rises (a new error) and when it falls without the baseline
following (a fixed error still listed), so the committed baseline is always exactly today's
errors and can only shrink. ``--update`` refuses to add an error: a new one is fixed, or, if
mypy is wrong about it, silenced at the line with ``# type: ignore[<code>]`` and a reason.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("mypy_baseline.json")
TARGETS = ("src/squadops", "adapters")
_ERROR = re.compile(r"^(?P<path>[^:]+):\d+: error: (?P<message>.*?)\s+\[(?P<code>[a-z-]+)\]$")
_LITERAL = re.compile(r"Literal\[([^\[\]]*)\]")


def canonical(message: str) -> str:
    """A message with each ``Literal[...]``'s members sorted. mypy prints a narrowed literal union
    in an order that varies between processes (string hashing), so one error read as both new and
    fixed on its first CI run."""
    return _LITERAL.sub(lambda m: "Literal[" + ", ".join(sorted(m[1].split(", "))) + "]", message)


def current() -> Counter:
    out = subprocess.run(
        [sys.executable, "-m", "mypy", *TARGETS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    errors: Counter = Counter()
    for line in out.stdout.splitlines():
        m = _ERROR.match(line)
        if m:
            errors["\t".join((m["path"], m["code"], canonical(m["message"])))] += 1
    if out.returncode not in (0, 1) or (out.returncode == 1 and not errors):
        sys.exit(f"mypy did not run cleanly:\n{out.stdout[-2000:]}\n{out.stderr[-2000:]}")
    return errors


def load() -> Counter:
    return (
        Counter(json.loads(BASELINE.read_text(encoding="utf-8")))
        if BASELINE.exists()
        else Counter()
    )


def save(errors: Counter) -> None:
    BASELINE.write_text(json.dumps(dict(sorted(errors.items())), indent=0) + "\n", encoding="utf-8")


def compare(now: Counter, baseline: Counter) -> tuple[list[str], list[str]]:
    """(new errors, fixed errors the baseline still lists), as readable lines."""
    new = [
        f"{k.replace(chr(9), ' | ')}  (+{now[k] - baseline[k]})"
        for k in now
        if now[k] > baseline[k]
    ]
    fixed = [
        f"{k.replace(chr(9), ' | ')}  (-{baseline[k] - now[k]})"
        for k in baseline
        if baseline[k] > now[k]
    ]
    return sorted(new), sorted(fixed)


def main(argv: list[str]) -> int:
    if "--init" in argv:
        if BASELINE.exists():
            print(f"refused: {BASELINE.name} exists; --update shrinks it, nothing adds to it")
            return 1
        now = current()
        save(now)
        print(f"baseline written: {sum(now.values())} errors in {len(now)} keys")
        return 0
    now, baseline = current(), load()
    new, fixed = compare(now, baseline)
    if "--update" in argv:
        if new:
            print(
                "refused: --update never adds an error. New since the baseline:", *new, sep="\n  "
            )
            return 1
        save(now)
        print(
            f"baseline: {sum(now.values())} errors ({sum(baseline.values()) - sum(now.values())} fewer)"
        )
        return 0
    if new:
        print(
            "mypy: new type errors (fix them, or ignore one at its line with a reason):",
            *new,
            sep="\n  ",
        )
    if fixed:
        print("mypy: errors fixed but still in the baseline (run --update):", *fixed, sep="\n  ")
    if new or fixed:
        return 1
    print(f"mypy ratchet: {sum(now.values())} errors, all in the baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
