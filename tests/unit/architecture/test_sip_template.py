"""New SIPs start with an intake check and a delivery ledger (#1981).

Both rules (CLAUDE.md, "SIP System", the owner's of 2026-10-04) depended on the author remembering
them: the 2026-10-04 audit found no proposed SIP with a ledger, and only the day's own draft with an
intake check. ``sips/TEMPLATE.md`` carries both sections; this holds every proposal created after
the rule to them. A ledger at acceptance is ``test_sip_ledgers.py``'s first rule.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.domain_contracts]

SIPS = Path(__file__).resolve().parents[3] / "sips"
#: The rule's date: proposals created on or before it predate it.
_RULE_DATE = "2026-10-04"
_SECTIONS = ("## Intake check", "## Delivery ledger")


def _created(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    meta = yaml.safe_load(m.group(1)) if m else {}
    return str((meta or {}).get("created_at") or "")[:10]


def _missing(text: str) -> list[str]:
    return [s for s in _SECTIONS if not re.search(rf"^{re.escape(s)}\b", text, re.M)]


def test_the_template_carries_both_sections():
    """Bug caught: the template losing a section, so every new SIP starts without it."""
    assert _missing((SIPS / "TEMPLATE.md").read_text(encoding="utf-8")) == []


def test_every_proposal_since_the_rule_has_an_intake_check_and_a_ledger():
    late = [
        f"{p.name}: missing {', '.join(missing)}"
        for p in sorted((SIPS / "proposed").glob("*.md"))
        if _created(p) > _RULE_DATE and (missing := _missing(p.read_text(encoding="utf-8")))
    ]
    assert late == [], "proposals created after the rule, without its sections:\n" + "\n".join(late)


@pytest.mark.parametrize(
    ("text", "missing"),
    [
        ("# x\n\n## Intake check\n\n## Delivery ledger (current as of 2026-10-05)\n", []),
        ("# x\n\n## Delivery ledger\n", ["## Intake check"]),
        ("# x\n\nThe intake check found none.\n", ["## Intake check", "## Delivery ledger"]),
    ],
)
def test_a_section_counts_only_as_a_heading(text, missing):
    """Bug caught: prose that mentions an intake check passing for the section itself."""
    assert _missing(text) == missing
