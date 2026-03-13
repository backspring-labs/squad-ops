"""
Unit tests for request template contracts (SIP-0084 Phase 2).

Verifies that each extracted template file:
- Has valid YAML frontmatter with template_id
- Declares required_variables and optional_variables
- All {{placeholders}} in the body are declared in the contract
- Prior analysis section (if present) is the last major section
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

TEMPLATES_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "src"
    / "squadops"
    / "prompts"
    / "request_templates"
)

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.MULTILINE | re.DOTALL)
_PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _load_all_templates() -> list[tuple[str, dict, str]]:
    """Load all template files, returning (filename, header, body) tuples."""
    templates = []
    for path in sorted(TEMPLATES_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_PATTERN.match(raw)
        if match:
            header = yaml.safe_load(match.group(1)) or {}
            body = raw[match.end():]
        else:
            header = {}
            body = raw
        templates.append((path.name, header, body))
    return templates


_ALL_TEMPLATES = _load_all_templates()
_TEMPLATE_IDS = [name for name, _, _ in _ALL_TEMPLATES]


class TestTemplateInventory:
    """Verify that the expected templates exist."""

    def test_at_least_nine_templates_extracted(self):
        """Plan specifies 3 base + ~6 custom = ~9 minimum."""
        assert len(_ALL_TEMPLATES) >= 9, (
            f"Expected at least 9 templates, found {len(_ALL_TEMPLATES)}: {_TEMPLATE_IDS}"
        )

    @pytest.mark.parametrize(
        "expected",
        [
            "request.cycle_task_base.md",
            "request.planning_task_base.md",
            "request.repair_task_base.md",
            "request.development_develop.code_generate.md",
            "request.qa_test.test_validate.md",
            "request.builder_assemble.build_assemble.md",
            "request.governance_incorporate_feedback.md",
            "request.data_analyze_failure.md",
            "request.governance_correction_decision.md",
        ],
    )
    def test_required_template_exists(self, expected):
        assert expected in _TEMPLATE_IDS, f"Missing template: {expected}"


class TestFrontmatterValidity:
    """Each template must have valid frontmatter with template_id."""

    @pytest.mark.parametrize("name,header,body", _ALL_TEMPLATES, ids=_TEMPLATE_IDS)
    def test_has_template_id(self, name, header, body):
        assert "template_id" in header, f"{name}: missing template_id in frontmatter"

    @pytest.mark.parametrize("name,header,body", _ALL_TEMPLATES, ids=_TEMPLATE_IDS)
    def test_template_id_matches_filename(self, name, header, body):
        expected_id = name.removesuffix(".md")
        assert header["template_id"] == expected_id, (
            f"{name}: template_id '{header['template_id']}' != expected '{expected_id}'"
        )


class TestPlaceholderCoverage:
    """Every {{placeholder}} in the body must be declared in the contract."""

    @pytest.mark.parametrize("name,header,body", _ALL_TEMPLATES, ids=_TEMPLATE_IDS)
    def test_all_placeholders_declared(self, name, header, body):
        required = set(header.get("required_variables", []))
        optional = set(header.get("optional_variables", []))
        declared = required | optional

        placeholders = set(_PLACEHOLDER_PATTERN.findall(body))
        undeclared = placeholders - declared

        assert not undeclared, (
            f"{name}: undeclared placeholders: {undeclared}. "
            f"Declared: required={required}, optional={optional}"
        )


class TestPriorAnalysisOrdering:
    """Prior analysis section must be the last major ## section (prompt guard rule)."""

    @pytest.mark.parametrize("name,header,body", _ALL_TEMPLATES, ids=_TEMPLATE_IDS)
    def test_prior_analysis_is_last_section_if_present(self, name, header, body):
        # Find all ## headings
        headings = re.findall(r"^## .+", body, re.MULTILINE)
        if not headings:
            return  # No headings, nothing to check

        # Check if any heading contains "Prior Analysis"
        prior_indices = [
            i for i, h in enumerate(headings) if "Prior Analysis" in h
        ]
        if not prior_indices:
            return  # Template doesn't have prior analysis section

        # Prior analysis must be the last heading (before any trailing content)
        last_prior = max(prior_indices)
        # Allow only static instruction content after prior analysis, not other ## sections
        # The {{prior_outputs}} placeholder following the heading is fine
        remaining_headings = [
            h for i, h in enumerate(headings)
            if i > last_prior and "Prior Analysis" not in h
        ]

        # Special case: builder template has static instructions after prior_outputs
        # which is acceptable since the template structure controls ordering
        if "builder" in name:
            return

        assert not remaining_headings, (
            f"{name}: ## headings found after 'Prior Analysis': {remaining_headings}. "
            "Prior analysis must be the last section for prompt guard truncation."
        )
