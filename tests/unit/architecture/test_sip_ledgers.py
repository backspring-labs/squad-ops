"""The SIP delivery ledgers and the portfolio, guarded (#1969; the owner's rule of 2026-10-04,
CLAUDE.md "SIP System").

The 2026-10-04 audit found eight accepted SIPs with no current delivery record, a header still
targeting "v1.6" months after v1.6.0, and placements recorded only in release plans, which are
superseded at the cut. The ledger rule was written down that day. This is its guard, so the rule
is not held by memory.

Rules, over the real tree:
1. every accepted SIP has a ``Delivery ledger``;
2. every *placed* row names a release and an issue that is open (``sips/open-issues.json``, a
   cache so this runs offline: ``scripts/maintainer/refresh_open_issues.py`` refreshes it);
3. every accepted and proposed SIP has a row in ``sips/PORTFOLIO.md``;
4. every row's status is in the vocabulary: shipped, placed, unplaced, dropped, or deferred to
   N.x (ruled <date>);
5. a *shipped* row names a tag or a PR;
6. no SIP header names a tagged release as a target it has not shipped;
7. on a ``release/*`` branch, no ledger is "current as of" a date before the latest release;
8. (#1979) each SIP's placed rows and its open ``sip:NNNN`` issues match, with no orphan either
   way. ``scripts/maintainer/sync_sip_labels.py`` applies the labels.

The ledgers are read through ``scripts/maintainer/sip_ledgers.py``, the one parser the label sync
and the cut's sweep also use.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_contracts]

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "maintainer"))
import sip_ledgers  # noqa: E402

SIPS = sip_ledgers.SIPS
_VOCABULARY = sip_ledgers.VOCABULARY
_RULED = re.compile(r"ruled \d{4}-\d{2}-\d{2}")
_TAG_OR_PR = re.compile(r"\bv\d+\.\d+\.\d+\b|#\d+")
_RELEASE = re.compile(r"\b\d+\.\d+(?:\.\d+)?\b")


def _sips(*folders: str) -> list[Path]:
    return sorted(p for f in folders for p in (SIPS / f).glob("*.md"))


def _rows(path: Path) -> list[tuple[str, str, str]]:
    return [(r.part, r.status_cell, r.where) for r in sip_ledgers.rows(path)]


def _status(cell: str) -> str:
    return sip_ledgers.Row("", cell, "").status


def _tagged() -> set[str]:
    """Released versions, from the CHANGELOG's headings: CI's checkout carries no tags."""
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return set(re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M))


def _violations(rule) -> list[str]:
    return [
        f"{p.relative_to(REPO_ROOT)}: {msg}"
        for p in _sips("accepted", "proposed")
        for msg in rule(p)
    ]


def test_every_accepted_sip_keeps_a_delivery_ledger():
    missing = [p.name for p in _sips("accepted") if not _rows(p)]
    assert missing == [], f"accepted SIPs with no Delivery ledger table: {missing}"


def test_every_ledger_row_uses_the_vocabulary():
    def rule(path):
        for part, status, _ in _rows(path):
            s = _status(status)
            if not s.startswith(_VOCABULARY):
                yield f"row {part!r}: status {status!r} is not one of {', '.join(_VOCABULARY)}"
            elif s.startswith("deferred to") and not _RULED.search(s):
                yield f"row {part!r}: a deferral names its ruling, 'deferred to N.x (ruled <date>)'"

    assert _violations(rule) == [], "\n".join(_violations(rule))


def test_a_shipped_row_names_a_tag_or_a_pr():
    def rule(path):
        for part, status, where in _rows(path):
            if _status(status).startswith("shipped") and not _TAG_OR_PR.search(f"{status} {where}"):
                yield f"row {part!r}: shipped, but names no tag (vX.Y.Z) or PR (#N)"

    assert _violations(rule) == [], "\n".join(_violations(rule))


def test_a_placed_row_names_a_release_and_an_open_issue():
    cache = sip_ledgers.open_issues()
    open_issues = set(cache["open"])

    def rule(path):
        for part, status, where in _rows(path):
            if not _status(status).startswith("placed"):
                continue
            issues = sip_ledgers.Row(part, status, where).issues
            if not _RELEASE.search(where) or not issues:
                yield f"row {part!r}: placed rows name a release and the issue tracking it"
            elif not issues & open_issues:
                yield (
                    f"row {part!r}: names {sorted(issues)}, none open in sips/open-issues.json "
                    f"(refreshed {cache['refreshed']}): ship or re-place the row, or refresh the "
                    "cache with scripts/maintainer/refresh_open_issues.py"
                )

    assert _violations(rule) == [], "\n".join(_violations(rule))


def test_every_accepted_and_proposed_sip_has_a_portfolio_row():
    portfolio = (SIPS / "PORTFOLIO.md").read_text(encoding="utf-8")
    accepted = portfolio[portfolio.index("## 1.") : portfolio.index("## 2.")]
    proposed = portfolio[portfolio.index("## 2.") : portfolio.index("## 3.")]

    def norm(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    missing = [p.name for p in _sips("accepted") if p.name[4:8] not in accepted]
    for p in _sips("proposed"):
        number = re.match(r"SIP-(\d{4})", p.stem)
        named = (
            number.group(1) in proposed
            if number
            else norm(re.sub(r"^(SIP|IDEA)-", "", p.stem)) in norm(proposed)
        )
        if not named:
            missing.append(p.name)
    assert missing == [], f"SIPs with no row in sips/PORTFOLIO.md: {missing}"


def _target_paragraphs(text: str) -> list[str]:
    """Each ``**Target:**`` / ``**Targets:**`` paragraph, joined to one line and ended by a blank
    line, the next bold header field or a list. A SIP's header is not always above its first
    heading (SIP-0102's sits under ``## Status``)."""
    out, current = [], None
    for line in text.splitlines():
        if re.match(r"\*\*Targets?:\*\*", line.strip()):
            current = [line.strip()]
            out.append(current)
        elif current is not None and line.strip() and not line.strip().startswith(("**", "- ")):
            current.append(line.strip())
        else:
            current = None
    return [" ".join(p) for p in out]


def test_no_header_names_a_released_version_as_a_target_it_has_not_shipped():
    """ "Targets: v1.6" survived months after v1.6.0. Each clause of a target paragraph (split at
    ``;``) that names a released line says it shipped there; one that is still a target names the
    next placement instead."""
    tagged = {".".join(v.split(".")[:2]) for v in _tagged()}

    def rule(path):
        for paragraph in _target_paragraphs(path.read_text(encoding="utf-8")):
            for clause in paragraph.split(";"):
                released = sorted(set(re.findall(r"\bv?(\d+\.\d+)\b", clause)) & tagged)
                if released and not re.search(r"shipped", clause, re.I):
                    yield f"targets released line(s) {', '.join(released)}: {clause.strip()[:110]}"

    assert _violations(rule) == [], "\n".join(_violations(rule))


def _branch() -> str:
    for var in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        if os.environ.get(var):
            return os.environ[var]
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def test_a_release_branch_refreshes_every_ledger():
    """Rule 7, at the cut only: on ``release/*`` no ledger is current as of a date before the
    latest release's, so the cut's SIP sweep (CLAUDE.md step 5) re-reads every ledger."""
    if not _branch().startswith("release/"):
        pytest.skip("checked on a release/* branch only")
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    latest = re.search(r"^## \[\d+\.\d+\.\d+\] — (\d{4}-\d{2}-\d{2})", changelog, re.M).group(1)

    def rule(path):
        heading = sip_ledgers.ledger_heading(path)
        if heading is not None:
            dated = re.search(r"\d{4}-\d{2}-\d{2}", heading)
            if dated is None or dated.group(0) < latest:
                yield f"ledger current as of {dated.group(0) if dated else 'no date'}, before {latest}"

    assert _violations(rule) == [], "\n".join(_violations(rule))


def test_placed_rows_and_sip_labelled_issues_match():
    """#1979. Bugs caught: an issue carrying a SIP part with no label (so closing it never asks
    for the ledger change), and a labelled issue no row names (a part the ledger forgot).

    The second direction asks for *a* row, not a placed one. The PR that ships a part moves its
    row to shipped while the issue is still open (it closes when that PR merges), so requiring a
    placed row would fail exactly the PR doing the right thing: #2017 shipped #1967's row, and
    this rule then failed on a tree where nothing was wrong."""
    cache = sip_ledgers.open_issues()["open"]
    mismatches = []
    for path in sip_ledgers.accepted():
        label = f"sip:{sip_ledgers.sip_number(path)}"
        placed = {n for n in sip_ledgers.placed_issues(path) if n in cache}
        named = {n for row in sip_ledgers.rows(path) for n in row.issues}
        labelled = {n for n, labels in cache.items() if label in labels}
        for n in sorted(placed - labelled):
            mismatches.append(f"{path.name}: placed row names #{n}, which lacks {label}")
        for n in sorted(labelled - named):
            mismatches.append(f"{path.name}: #{n} carries {label}, but no row names it")
    assert mismatches == [], (
        "\n".join(mismatches) + "\n(run scripts/maintainer/sync_sip_labels.py, then "
        "refresh_open_issues.py)"
    )
