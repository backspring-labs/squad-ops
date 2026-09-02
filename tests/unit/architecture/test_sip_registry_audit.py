"""The SIP registry audit runs in the regression gate (#1144).

``scripts/maintainer/audit_sip_registry.py`` found every defect #1144 lists — nine
frontmatter statuses disagreeing with the folder, nine timestamps it misjudged, four
proposals with prose in a date field, twenty-four proposals with no index anywhere — and
was wired to nothing: no workflow, no test, no cut step invoked it, so the findings
accumulated unreported. Same class as #1061 (a checklist step missed at six cuts), same
answer: a guard, not discipline.

Two rules over the real tree, read from the audit's own result rather than re-derived:
1. No critical and no data-quality finding. Data quality is asserted at zero rather than
   against a budget because the count is zero on this commit; a regression is a named
   finding in the failure message, with the cleanup command where one exists.
2. Every SIP file has a registry row — the registry is the index of *all* SIPs, which is
   what makes its counts and the published site's agree (the issue's option (a)).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_contracts]

REPO_ROOT = Path(__file__).resolve().parents[3]
_MAINTAINER = REPO_ROOT / "scripts" / "maintainer"


def _audit_module():
    if str(_MAINTAINER) not in sys.path:
        sys.path.insert(0, str(_MAINTAINER))
    return importlib.import_module("audit_sip_registry")


@pytest.fixture(scope="module")
def audit_result() -> dict:
    return _audit_module().audit_registry()


def _lines(findings: list[dict]) -> str:
    return "\n".join(f"  - {f['type']}: {f['message']}" for f in findings)


def test_the_registry_has_no_critical_or_data_quality_findings(audit_result: dict):
    issues = audit_result["issues"]
    assert issues["critical"] == [], "critical registry findings:\n" + _lines(issues["critical"])
    assert issues["data_quality"] == [], (
        "SIP registry data-quality findings (run scripts/maintainer/audit_sip_registry.py; "
        "cleanup_sip_registry.py fixes most of them):\n" + _lines(issues["data_quality"])
    )


def test_every_sip_file_is_indexed_in_the_registry(audit_result: dict):
    """A proposal missing its row is the silent-omission #1144 measured as 7 vs 31."""
    indexed = {
        Path(row["path"]).name
        for row in audit_result["registry"].get("sips", [])
        if row.get("path")
    }
    unindexed = sorted(set(audit_result["all_files"]) - indexed)
    assert unindexed == [], (
        "SIP files with no registry row — run "
        "`python scripts/maintainer/cleanup_sip_registry.py --index-proposals`:\n  "
        + "\n  ".join(unindexed)
    )
