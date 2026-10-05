#!/usr/bin/env python3
"""Label every issue a SIP's ledger places with ``sip:NNNN`` (#1979).

An issue that carries a SIP part was linked to its SIP by prose only, so "what remains for
SIP-0109" was a reading exercise, and a PR could close a SIP part without touching its ledger. The
label makes the link a fact: the ledger guard matches placed rows to labelled issues both ways, and
``check_pr_closure.sh`` asks a PR that closes a ``sip:`` issue to change that SIP's ledger.

Reads every accepted SIP's placed rows (``sip_ledgers.placed_issues``), creates the label when it
is missing, adds it to each placed issue still open, and reports any open issue carrying a ``sip:``
label that no row places. It never removes a label: an orphan is read, not guessed at. Then run
``refresh_open_issues.py`` so the guard's cache sees the result.

    python scripts/maintainer/sync_sip_labels.py [--dry-run]
"""

from __future__ import annotations

import subprocess
import sys

from sip_ledgers import accepted, open_issues, placed_issues, sip_number


def _gh(*args: str) -> bool:
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60).returncode == 0


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    cache = open_issues()["open"]
    status = 0
    for path in accepted():
        number = sip_number(path)
        placed = placed_issues(path)
        label = f"sip:{number}"
        if placed and not dry:
            _gh(
                "label",
                "create",
                label,
                "--color",
                "5319e7",
                "--force",
                "--description",
                f"carries a part of SIP-{number} (its delivery ledger places it)",
            )
        for issue in sorted(placed):
            if issue not in cache:
                print(f"{label}: #{issue} is placed but not open: ship or re-place the row")
                status = 1
            elif label not in cache[issue]:
                print(f"{label}: label #{issue}" + (" (dry run)" if dry else ""))
                if not dry and not _gh("issue", "edit", str(issue), "--add-label", label):
                    print(f"  failed to label #{issue}", file=sys.stderr)
                    status = 1
        for issue, labels in sorted(cache.items()):
            if label in labels and issue not in placed:
                print(f"{label}: #{issue} carries the label but no placed row names it")
                status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
