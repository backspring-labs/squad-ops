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

_pkg_spec = importlib.util.spec_from_file_location(
    "build_release_package", REPO_ROOT / "scripts" / "maintainer" / "build_release_package.py"
)
build_release_package = importlib.util.module_from_spec(_pkg_spec)
sys.modules["build_release_package"] = build_release_package
_pkg_spec.loader.exec_module(build_release_package)

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


class TestCycleEvidenceCapture:
    """#1076: the capture must not report success while capturing nothing.

    `cycle_evidence`'s docstring promised that "an unreachable API and a cycle that
    genuinely produced nothing must not look the same later". It did not keep that
    promise, and the failure was invisible in exactly the way the promise warns about:
    the guard caught only `JSONDecodeError`, so `{"detail": "Not Found"}` — perfectly
    valid JSON — was recorded as `captured: True` with every field null.

    That is what hid three other defects (wrong route, no auth header, wrong roll-up
    field name) for as long as the script existed. These tests are on the disclosure,
    because the disclosure is what makes the rest findable.
    """

    @staticmethod
    def _capture(monkeypatch, payload: str):
        brp = build_release_package

        monkeypatch.setattr(brp, "run", lambda *a, **k: payload)
        monkeypatch.setattr(brp, "_bearer_token", lambda: "tok")
        return brp.cycle_evidence(["cyc_1"], "http://api", "proj")[0]

    def test_a_json_error_body_is_recorded_as_absent_not_captured(self, monkeypatch):
        """The bug, exactly. A 404's JSON body must never read as a captured cycle."""
        got = self._capture(monkeypatch, '{"detail": "Not Found"}')
        assert got["captured"] is False
        assert "Not Found" in got["reason"]

    def test_unparseable_output_is_absent_with_its_reason(self, monkeypatch):
        got = self._capture(monkeypatch, "curl: (7) connection refused")
        assert got["captured"] is False
        assert "did not answer" in got["reason"]

    def test_a_cycle_with_no_rollup_is_absent_not_a_null_verdict(self, monkeypatch):
        """A real cycle that never produced a roll-up is genuinely absent evidence —
        recording it as captured-with-nulls is the same lie in a different shape."""
        got = self._capture(monkeypatch, '{"status": "completed", "cycle_outcome": null}')
        assert got["captured"] is False
        assert "no verification roll-up" in got["reason"]

    def test_a_real_rollup_is_captured_from_cycle_outcome(self, monkeypatch):
        """Reads `cycle_outcome`, the field the API actually returns — the script read
        `outcome`, which is always absent, so every capture was empty."""
        payload = (
            '{"status": "completed", "runs": [1, 2],'
            ' "cycle_outcome": {"verdict": "accepted", "run_count": 4,'
            ' "verified": ["b", "a", "a"], "failed": [], "required_unmet": [],'
            ' "unverified": [{"check_id": "x"}]}}'
        )
        got = self._capture(monkeypatch, payload)
        assert got["captured"] is True
        assert got["verdict"] == "accepted"
        assert got["run_count"] == 4
        assert got["verified"] == ["a", "b"]
        assert got["unverified"] == ["x"]

    def test_the_request_is_project_scoped_and_authorized(self, monkeypatch):
        """The route is `/api/v1/projects/{project}/cycles/{id}` and the API rejects an
        unauthenticated call — the script used the unscoped path and sent no header, so
        every capture 404'd before any field mapping mattered."""
        brp = build_release_package

        seen: dict = {}

        def _fake_run(*args, **kwargs):
            seen["args"] = args
            return '{"cycle_outcome": {"verdict": "accepted", "run_count": 1}}'

        monkeypatch.setattr(brp, "run", _fake_run)
        monkeypatch.setattr(brp, "_bearer_token", lambda: "tok-123")
        brp.cycle_evidence(["cyc_1"], "http://api", "proj")

        assert "http://api/api/v1/projects/proj/cycles/cyc_1" in seen["args"]
        assert "Authorization: Bearer tok-123" in seen["args"]

    def test_a_missing_token_says_so_in_the_reason(self, monkeypatch):
        """The maintainer needs to know WHICH failure this was — an expired login and a
        genuinely absent cycle want different responses."""
        brp = build_release_package

        monkeypatch.setattr(brp, "run", lambda *a, **k: '{"detail": "Missing header"}')
        monkeypatch.setattr(brp, "_bearer_token", lambda: "")
        got = brp.cycle_evidence(["cyc_1"], "http://api", "proj")[0]
        assert got["captured"] is False
        assert "squadops login" in got["reason"]
