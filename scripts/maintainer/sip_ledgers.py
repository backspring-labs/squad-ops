"""SIP delivery ledgers, read one way (#1969, #1979, #1980).

The ledger rule (CLAUDE.md "SIP System") has three readers: the guard
(``tests/unit/architecture/test_sip_ledgers.py``), the label sync
(``sync_sip_labels.py``) and the cut's sweep (``sip_sweep.py``). Each reads a ledger table through
here, so the three cannot disagree about what a row says.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIPS = REPO_ROOT / "sips"
OPEN_ISSUES = SIPS / "open-issues.json"
LEDGER = re.compile(r"^## Delivery ledger([^\n]*)\n(.*?)(?=^## |\Z)", re.S | re.M)
VOCABULARY = ("shipped", "placed", "unplaced", "dropped", "deferred to")
_ISSUE = re.compile(r"#(\d+)")


@dataclass(frozen=True)
class Row:
    part: str
    status_cell: str
    where: str

    @property
    def status(self) -> str:
        """The status the cell leads with, markup stripped: ``**placed**: …`` reads ``placed …``."""
        return re.sub(r"[*_`]", "", self.status_cell).strip().lower()

    @property
    def issues(self) -> set[int]:
        return {int(n) for n in _ISSUE.findall(f"{self.status_cell} {self.where}")}


def sip_number(path: Path) -> str | None:
    """``"0109"`` for ``SIP-0109-…``, or ``None`` for an unnumbered proposal."""
    m = re.match(r"SIP-(\d{4})", path.name)
    return m.group(1) if m else None


def rows(path: Path) -> list[Row]:
    """The rows of a SIP's ``Delivery ledger`` table, or ``[]`` when it has none."""
    m = LEDGER.search(path.read_text(encoding="utf-8"))
    if not m:
        return []
    out = []
    for line in m.group(2).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) < 3 or set(cells[0]) <= {"-", " "}:
            continue
        if cells[0].lower() == "part":
            continue
        out.append(Row(cells[0], cells[1], cells[2]))
    return out


def ledger_heading(path: Path) -> str | None:
    """The text after ``## Delivery ledger`` (its "current as of" date), or ``None``."""
    m = LEDGER.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def accepted() -> list[Path]:
    return sorted((SIPS / "accepted").glob("*.md"))


def placed_issues(path: Path) -> set[int]:
    """The issues a SIP's *placed* rows name."""
    return {n for r in rows(path) if r.status.startswith("placed") for n in r.issues}


def open_issues() -> dict:
    """The cache ``refresh_open_issues.py`` writes: ``{"refreshed", "open": {number: [labels]}}``."""
    data = json.loads(OPEN_ISSUES.read_text(encoding="utf-8"))
    data["open"] = {int(k): v for k, v in data["open"].items()}
    return data
