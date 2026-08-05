"""#724 class-closing guard — no direct ``applied_defaults`` config reads.

The #426/#724 defect class: a runtime surface reads ``applied_defaults``
directly while dispatch honors ``execution_overrides`` via the single merge
(``Cycle.resolved_config()`` / ``models.resolve_config``), so an operator's
override is silently ignored by exactly one reader (the 1.4.4 exhibit:
``time_budget_seconds`` set via overrides, run used the profile default).

This guard closes the CLASS, not the instance: any ``applied_defaults.get(``
or ``applied_defaults[`` read in ``src/`` or ``adapters/`` outside the merge
definition itself fails here. Attribute-level passes (DTO provenance
exposure, config hashing, registry persistence, the SIP-0083 forwarding-
overrides machinery) are legitimately about the *parts* rather than the
effective config and are out of this guard's (textual) scope — the design
table on #724 enumerates them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_cycles]

_REPO = Path(__file__).resolve().parents[3]
_SCAN_ROOTS = (_REPO / "src" / "squadops", _REPO / "adapters")
_READ_PATTERN = re.compile(r"applied_defaults(?:\.get\(|\[)")

# The single merge definition is the ONE place allowed to read the dict.
_ALLOWED = {_REPO / "src" / "squadops" / "cycles" / "models.py"}


def test_no_direct_applied_defaults_reads_outside_the_merge():
    offenders: list[str] = []
    for root in _SCAN_ROOTS:
        for path in root.rglob("*.py"):
            if path in _ALLOWED:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _READ_PATTERN.search(line) and not line.lstrip().startswith("#"):
                    offenders.append(f"{path.relative_to(_REPO)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Direct applied_defaults read(s) found — route effective-config reads "
        "through cycle.resolved_config() / models.resolve_config (#724, #426):\n"
        + "\n".join(offenders)
    )
