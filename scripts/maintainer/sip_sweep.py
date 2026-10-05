#!/usr/bin/env python3
"""Release cut step 5, read from the delivery ledgers (#1980).

The cut's SIP sweep was enforced only by a hand-written ``SIP sweep:`` line in the release PR.
This reads every accepted SIP's ledger and reports:

- **promotable:** SIPs whose every row is shipped or dropped (CLAUDE.md: promoted when every row
  is shipped or dropped);
- **re-place:** rows placed in this release that are still placed, with their issue open (the
  release PR must re-place them);
- **stale:** rows still placed whose issues are all closed (shipped, but the row was not moved).

    python scripts/maintainer/sip_sweep.py 2.1.0            # the report
    python scripts/maintainer/sip_sweep.py 2.1.0 --line     # a suggested `SIP sweep:` line
    python scripts/maintainer/sip_sweep.py 2.1.0 --outstanding   # ids the release PR must name

It reads issue state from ``sips/open-issues.json``, so the release PR refreshes that snapshot
first (``refresh_open_issues.py``): a stale snapshot hides a row whose issue has since closed.

``check_pr_closure.sh`` runs ``--outstanding`` on a ``release/*`` branch: every id it prints
must appear in the PR's ``SIP sweep:`` line, so nothing the ledgers say is left unread at the cut.
``SIP_SWEEP_ROOT`` points it at another tree (the tests).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import sip_ledgers


@dataclass
class Sweep:
    promotable: list[str] = field(default_factory=list)
    replace: list[tuple[str, int]] = field(default_factory=list)
    stale: list[tuple[str, int]] = field(default_factory=list)

    def outstanding(self) -> list[str]:
        """The ids a release PR's sweep line names: each SIP, and each issue."""
        ids = list(self.promotable)
        ids += [f"#{n}" for _, n in self.replace + self.stale]
        return sorted(set(ids))


def sweep(version: str, root: Path | None = None) -> Sweep:
    sips = (root or sip_ledgers.REPO_ROOT) / "sips"
    data = sip_ledgers.open_issues(sips / "open-issues.json")
    open_issues = set(data["open"])
    minor = ".".join(version.split(".")[:2])
    in_release = re.compile(rf"\b{re.escape(minor)}(\.\d+)?\b")
    out = Sweep()
    for path in sorted((sips / "accepted").glob("*.md")):
        name = f"SIP-{sip_ledgers.sip_number(path)}"
        rows = sip_ledgers.rows(path)
        if rows and all(r.status.startswith(("shipped", "dropped")) for r in rows):
            out.promotable.append(name)
        for r in rows:
            if not r.status.startswith("placed") or not r.issues:
                continue
            still_open = r.issues & open_issues
            if not still_open:
                out.stale += [(name, n) for n in sorted(r.issues)]
            elif in_release.search(r.where):
                out.replace += [(name, n) for n in sorted(still_open)]
    return out


def _line(s: Sweep) -> str:
    parts = []
    if s.promotable:
        parts.append("promote " + ", ".join(s.promotable))
    if s.replace:
        parts.append("re-place " + ", ".join(f"{sip} #{n}" for sip, n in s.replace))
    if s.stale:
        parts.append("move to shipped " + ", ".join(f"{sip} #{n}" for sip, n in s.stale))
    return "SIP sweep: " + (
        "; ".join(parts) or "nothing — no SIP is promotable and every ledger is current"
    )


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    root = Path(os.environ["SIP_SWEEP_ROOT"]) if os.environ.get("SIP_SWEEP_ROOT") else None
    s = sweep(argv[0], root)
    if "--outstanding" in argv:
        print("\n".join(s.outstanding()))
    elif "--line" in argv:
        print(_line(s))
    else:
        print(f"promotable: {', '.join(s.promotable) or 'none'}")
        for sip, n in s.replace:
            print(f"re-place: {sip} #{n} (placed in {argv[0]}, still open)")
        for sip, n in s.stale:
            print(f"move to shipped: {sip} #{n} (closed, the row still says placed)")
        print(_line(s))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
