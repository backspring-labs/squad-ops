"""Docs-drift guards (#336).

Version/doc drift shipped three separate times despite the sync rule in
CLAUDE.md: CLAUDE.md + README stuck at 1.0.5 through the 1.1.x releases,
the ROADMAP stats block stuck at 1.0.6 through 1.2.0 (#335), and accepted
SIP-0091 self-targeting the feature-free stabilization minor. The pattern:
what a test enforces stays true; what discipline enforces drifts. These
guards put the ratchet in the regression gate.

Three rules:
1. Every version marker (CLAUDE.md / README.md / docs/ROADMAP.md) equals
   the pyproject.toml version — a release bump physically cannot ship with
   a stale marker.
2. Every ``**Targets:** vX.Y`` line in an accepted SIP names an even minor
   (feature SIPs ⇒ feature releases, per the even/odd convention #281),
   unless the line itself says "stabilization" — the escape hatch for
   structural SIPs like SIP-0097 that legitimately land on odd minors.
3. Repo paths referenced from the living planning docs (ROADMAP + the
   docs/plans/ set) exist in the tree — committed docs must not cite files
   that live only in someone's working copy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# Line-anchored so SIP body prose like "Targets observed ..." (SIP-0092's
# acceptance-check tables) can never false-positive.
TARGETS_RE = re.compile(r"^\*\*Targets:\*\* *v(\d+)\.(\d+)(.*)$", re.MULTILINE)

# Backtick-quoted repo-relative doc paths, e.g. `docs/plans/foo.md`.
DOC_REF_RE = re.compile(r"`((?:docs|sips)/[A-Za-z0-9._/\-]+\.md)`")


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _pyproject_version() -> str:
    match = re.search(r'^version = "(\d+\.\d+\.\d+)"', _read("pyproject.toml"), re.MULTILINE)
    assert match, "pyproject.toml has no version field"
    return match.group(1)


def _odd_target_offenders(sip_text: str) -> list[str]:
    """Return the ``**Targets:**`` lines that violate even/odd parity.

    A line offends when it targets an odd minor and does not declare itself
    stabilization work.
    """
    offenders = []
    for match in TARGETS_RE.finditer(sip_text):
        minor = int(match.group(2))
        line = match.group(0)
        if minor % 2 == 1 and "stabilization" not in line.lower():
            offenders.append(line.strip())
    return offenders


class TestVersionMarkersInSync:
    """Rule 1: the four documents' version markers equal pyproject.toml."""

    @pytest.mark.parametrize(
        ("rel_path", "pattern"),
        [
            ("CLAUDE.md", r"\*\*Framework Version\*\*: (\d+\.\d+\.\d+)"),
            ("README.md", r"\*\*Current Status\*\*: v(\d+\.\d+\.\d+)"),
            ("README.md", r"\*\*Framework Version\*\*: (\d+\.\d+\.\d+)"),
            ("README.md", r"\*\*Current\*\*: v(\d+\.\d+\.\d+)"),
            ("docs/ROADMAP.md", r"### v(\d+\.\d+\.\d+) \([0-9-]+\) — Current"),
            ("docs/ROADMAP.md", r"\*\*Framework version\*\*: (\d+\.\d+\.\d+)"),
        ],
        ids=[
            "claude-md",
            "readme-current-status",
            "readme-framework-version",
            "readme-version-history-current",
            "roadmap-current-header",
            "roadmap-stats-version",
        ],
    )
    def test_marker_matches_pyproject(self, rel_path: str, pattern: str) -> None:
        """Bug caught: a release bump that edits pyproject but misses one of
        the doc markers (the 1.0.5-through-1.1.x and 1.0.6-through-1.2.0
        incidents) — the marker must exist AND carry the current version."""
        expected = _pyproject_version()
        found = re.findall(pattern, _read(rel_path))
        assert found, f"{rel_path}: version marker /{pattern}/ not found — was it reworded?"
        stale = [version for version in found if version != expected]
        assert not stale, (
            f"{rel_path}: marker /{pattern}/ says {stale} but pyproject.toml says {expected} — "
            "sync the doc (see CLAUDE.md 'Versioning & Release Cadence')"
        )


class TestAcceptedSipTargetsParity:
    """Rule 2: accepted SIPs target even minors unless declared stabilization."""

    def test_no_accepted_sip_targets_an_odd_minor(self) -> None:
        """Bug caught: the SIP-0091 incident — an accepted feature SIP whose
        Targets line names a stabilization (odd) release the parity rule
        forbids it from shipping in."""
        offenders = {
            sip.name: lines
            for sip in sorted((REPO_ROOT / "sips" / "accepted").glob("*.md"))
            if (lines := _odd_target_offenders(sip.read_text(encoding="utf-8")))
        }
        assert not offenders, (
            f"accepted SIPs target odd (feature-free) minors: {offenders} — "
            "remap to the next even minor (#281), or mark the line 'stabilization' "
            "if it is genuinely structural work"
        )

    def test_odd_target_detected_in_synthetic_sip(self) -> None:
        """Guards the guard: the exact SIP-0091 header shape must be flagged."""
        text = "**Revision:** 2\n**Targets:** v1.3\n**Depends on:** x\n"
        assert _odd_target_offenders(text) == ["**Targets:** v1.3"]

    @pytest.mark.parametrize(
        ("text", "reason"),
        [
            ("**Targets:** v1.4 (feature minor)\n", "even minor is allowed"),
            ("**Targets:** v1.5 (stabilization — structural refactor)\n", "declared stabilization"),
            ("| x | Targets observed v1.3 failures |\n", "prose mention, not a Targets header"),
        ],
        ids=["even-minor", "stabilization-escape", "body-prose"],
    )
    def test_non_offending_shapes_pass(self, text: str, reason: str) -> None:
        """Bug caught: an over-eager regex flagging SIP-0092-style body prose
        or the legitimate stabilization escape hatch."""
        assert _odd_target_offenders(text) == [], reason


SIP_NUMBER_RE = re.compile(r"SIP-(\d{4})")

# Historical plan docs reference SIP drafts by their pre-numbering names, and
# a couple reference companion docs that were never committed. Frozen as-is
# 2026-07-08 (#336): these are dated execution records, not living docs — we
# don't rewrite them, but nothing new may join this list.
LEGACY_DANGLING_REFS = frozenset(
    {
        "docs/plans/SIP-0.8.8-implementation-plan.md -> sips/proposed/SIP-Agent-Migration-0-8-8.md",
        "docs/plans/SIP-0073-llm-budget-timeout-controls-plan.md -> sips/proposed/SIP-LLM-Budget-and-Timeout-Controls.md",
        "docs/plans/SIP-0089-agent-runtime-state-plan.md -> sips/proposed/SIP-Agent-Runtime-Modes.md",
        "docs/plans/SIP-0089-agent-runtime-state-plan.md -> docs/plans/SIP-0067-postgres-cycle-registry-plan.md",
        "docs/plans/SIP-0092-implementation-plan-improvement-plan.md -> docs/plans/SIP-0092-gate-M2-evaluation.md",
        "docs/plans/SIP-Console-Cycle-Operations-UX-plan.md -> sips/proposed/SIP-Console-Cycle-Operations-UX.md",
        "docs/plans/SIP-build-capabilities-plan.md -> sips/proposed/SIP-Enhanced-Agent-Build-Capabilities.md",
        "docs/plans/SIP-console-control-plane-plan.md -> sips/proposed/SIP-SquadOps-Console-Control-Plane-UI.md",
        "docs/plans/SIP-postgres-cycle-registry-plan.md -> sips/proposed/SIP-Postgres-Cycle-Registry.md",
        "docs/plans/SIP-time-budget-awareness-planning-prompts-plan.md -> sips/proposed/SIP-Time-Budget-Awareness-Planning-Prompts.md",
    }
)


def _ref_resolves(ref: str, sip_files: dict[str, set[str]]) -> bool:
    """True if a referenced repo path exists, treating `sips/` references as
    lifecycle-aware: a SIP moves proposed → accepted → implemented (renamed
    with its number on acceptance), so a numbered reference resolves if that
    SIP number exists at ANY stage, and an unnumbered draft reference
    resolves if its basename exists anywhere under sips/."""
    if (REPO_ROOT / ref).exists():
        return True
    if not ref.startswith("sips/"):
        return False
    basename = ref.rsplit("/", 1)[-1]
    number_match = SIP_NUMBER_RE.search(basename)
    if number_match:
        return number_match.group(1) in sip_files["numbers"]
    return basename in sip_files["basenames"]


class TestReferencedDocPathsExist:
    """Rule 3: living planning docs only reference files that exist."""

    def test_roadmap_and_plans_reference_existing_files(self) -> None:
        """Bug caught: the #335 item-3 incident — ROADMAP's proposal table and
        the reconciliation doc citing drafts that existed only in a local
        working tree, so every fresh clone got dangling links."""
        scope = ["docs/ROADMAP.md"] + sorted(
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "docs" / "plans").glob("*.md")
        )
        all_sips = list((REPO_ROOT / "sips").rglob("SIP-*.md"))
        sip_files = {
            "numbers": {m.group(1) for p in all_sips if (m := SIP_NUMBER_RE.search(p.name))},
            "basenames": {p.name for p in all_sips},
        }
        dangling = []
        for rel_path in scope:
            for ref in DOC_REF_RE.findall(_read(rel_path)):
                entry = f"{rel_path} -> {ref}"
                if not _ref_resolves(ref, sip_files) and entry not in LEGACY_DANGLING_REFS:
                    dangling.append(entry)
        assert not dangling, (
            "committed docs reference paths missing from the tree "
            f"(commit the file or update the reference): {dangling}"
        )

    def test_dangling_ref_detected(self) -> None:
        """Guards the guard: a path that exists at no lifecycle stage must not
        resolve, while a stage-moved SIP reference must."""
        sip_files = {"numbers": {"0094"}, "basenames": {"SIP-Draft-Thing.md"}}
        assert not _ref_resolves("docs/plans/never-written.md", sip_files)
        assert not _ref_resolves("sips/proposed/SIP-Never-Filed.md", sip_files)
        assert _ref_resolves("sips/accepted/SIP-0094-Old-Name.md", sip_files)
        assert _ref_resolves("sips/proposed/SIP-Draft-Thing.md", sip_files)
