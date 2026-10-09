#!/usr/bin/env python3
"""Read, in each running container, what a rebuild must have loaded (#1956).

The rows are data, ``scripts/dev/loaded_checks.yaml``: a container, a snippet that prints what only
the new code prints, and that output. Each snippet runs as ``python -`` inside its container
(``docker exec -i``), so this reads the deployed code, never the checkout. A deploy carrying an
older image, or a container a rebuild skipped, fails by row.

Then, unless ``--only`` names one row, it checks that the latest deploy record describes the running
images (``record_deploy.sh --check``, #2193). A service rebuilt after the record was written fails
here, naming the service, so the record every new cycle references is never silently stale.

    python scripts/dev/verify_loaded.py [--only ID]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

CHECKS = Path(__file__).with_name("loaded_checks.yaml")
RECORD_CHECK = Path(__file__).parent / "ops" / "record_deploy.sh"


def judge(expect: str, returncode: int, stdout: str, stderr: str) -> str | None:
    """Why a row failed, or ``None``: the snippet ran, and its last line is the expected output."""
    if returncode != 0:
        return f"the snippet failed ({returncode}): {stderr.strip().splitlines()[-1:] or ['']}"
    lines = stdout.strip().splitlines()
    got = lines[-1].strip() if lines else ""
    return (
        None if got == str(expect).strip() else f"printed {got!r}, expected {str(expect).strip()!r}"
    )


def record_check() -> tuple[bool, str]:
    """Whether the latest deploy record describes the running images, and what the check said.
    A check that could not run is a failure: a record nobody could read is not a record shown true."""
    r = subprocess.run(
        [str(RECORD_CHECK), "--check"], capture_output=True, text=True, timeout=120, check=False
    )
    said = (r.stdout.strip() or r.stderr.strip() or f"exit {r.returncode}").splitlines()[-1]
    return r.returncode == 0, said


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--only", help="run one row by its id")
    a = p.parse_args(argv)
    rows = yaml.safe_load(CHECKS.read_text())["checks"]
    if a.only:
        rows = [row for row in rows if row["id"] == a.only]
        if not rows:
            # A misspelt or unmerged id ran nothing; reporting "1 loaded" would credit it.
            print(f"no loaded check has id {a.only!r} in {CHECKS}", file=sys.stderr)
            return 2
    failed = 0
    for row in rows:
        r = subprocess.run(
            ["docker", "exec", "-i", row["container"], "python", "-"],
            input=row["code"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        why = judge(row["expect"], r.returncode, r.stdout, r.stderr)
        failed += why is not None
        print(
            f"{'ok  ' if why is None else 'FAIL'} #{row['id']} {row['container']}: {row['what']}"
            + (f" — {why}" if why else "")
        )
    print(f"{len(rows) - failed} loaded, {failed} not")
    if not a.only:
        ok, said = record_check()
        print(f"{'ok  ' if ok else 'FAIL'} deploy record: {said}")
        failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
