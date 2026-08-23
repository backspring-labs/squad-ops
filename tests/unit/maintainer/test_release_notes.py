"""Tests for the release-notes extractor (#1061).

What bug would these catch? A release published with the wrong body, an empty
body, or the wrong version's content — none of which is visible until after the
Release is public, because the workflow runs on a tag push with no review step.
The extractor is the only thing standing between a heading-format change and a
silently wrong public artifact.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "release_notes", REPO_ROOT / "scripts" / "maintainer" / "release_notes.py"
)
release_notes = importlib.util.module_from_spec(_spec)
sys.modules["release_notes"] = release_notes
_spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [Unreleased]

Work in flight.

## [1.6.1] — 2026-08-22

Patch line body.

- item one
- item two

## [1.6.0] - 2026-08-21

Authorship body, hyphen-dashed heading.

## [1.5.0] — 2026-08-07

Older body.
"""

ROADMAP = """# Roadmap

### v1.6.1 (2026-08-22) — Current — the correction-loop patch line
### v1.6.0 (2026-08-21) — the Authorship release
### v1.4.9 (2026-01-01) —
"""


class TestChangelogBody:
    def test_extracts_only_the_requested_version(self):
        body = release_notes.changelog_body("1.6.1", CHANGELOG)
        assert body.startswith("Patch line body.")
        assert "item two" in body
        # the next section must not bleed in — the failure that would ship one
        # release carrying the previous release's notes
        assert "Authorship body" not in body
        assert "## [1.6.0]" not in body

    def test_handles_both_dash_styles(self):
        """The file's history contains em-dash and hyphen headings; both must parse."""
        assert release_notes.changelog_body("1.6.0", CHANGELOG).startswith("Authorship body")

    def test_last_section_runs_to_end_of_file(self):
        assert release_notes.changelog_body("1.5.0", CHANGELOG) == "Older body."

    def test_unreleased_is_not_matched_as_a_version(self):
        with pytest.raises(release_notes.NotFound):
            release_notes.changelog_body("Unreleased", CHANGELOG)

    def test_missing_version_raises_rather_than_returning_empty(self):
        with pytest.raises(release_notes.NotFound, match="no section for 9.9.9"):
            release_notes.changelog_body("9.9.9", CHANGELOG)

    def test_empty_section_raises(self):
        text = "## [2.0.0] — 2026-09-01\n\n## [1.9.9] — 2026-08-01\n\nbody\n"
        with pytest.raises(release_notes.NotFound, match="is empty"):
            release_notes.changelog_body("2.0.0", text)


class TestReleaseTitle:
    def test_uses_the_roadmap_name(self):
        assert release_notes.release_title("1.6.0", ROADMAP) == "v1.6.0 — the Authorship release"

    def test_strips_the_transient_current_marker(self):
        """'Current' moves every release; it is not part of the release's name."""
        assert release_notes.release_title("1.6.1", ROADMAP) == (
            "v1.6.1 — the correction-loop patch line"
        )

    def test_falls_back_to_bare_version_when_roadmap_is_silent(self):
        assert release_notes.release_title("1.2.3", ROADMAP) == "v1.2.3"

    def test_empty_roadmap_name_falls_back(self):
        assert release_notes.release_title("1.4.9", ROADMAP) == "v1.4.9"


class TestAgainstTheRealFiles:
    """The extractor must work on this repo's actual CHANGELOG and ROADMAP —
    a fixture that drifts from the real file shape proves nothing."""

    def test_current_version_resolves(self):
        import re

        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
        body = release_notes.changelog_body(
            version, (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        )
        title = release_notes.release_title(
            version, (REPO_ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        )
        assert body.strip()
        assert title.startswith(f"v{version}")
