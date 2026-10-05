#!/usr/bin/env python3
"""Refresh ``sips/open-issues.json``: the open issue numbers the SIP ledger guard reads (#1969).

The guard (``tests/unit/architecture/test_sip_ledgers.py``) checks that every *placed* ledger row
names an open issue, and must run offline, so it reads this cache. Run it when the guard reports
an issue it does not know, or after closing issues a ledger names:

    python scripts/maintainer/refresh_open_issues.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "sips" / "open-issues.json"


def main() -> int:
    out = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--limit", "1000", "--json", "number"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if out.returncode != 0:
        print(f"gh issue list failed: {out.stderr.strip()}", file=sys.stderr)
        return 1
    numbers = sorted(int(i["number"]) for i in json.loads(out.stdout))
    refreshed = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
    CACHE.write_text(json.dumps({"refreshed": refreshed, "open": numbers}) + "\n")
    print(f"{CACHE.name}: {len(numbers)} open issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
