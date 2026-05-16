"""Tests for SIP-0093 PR 93.1 extensions to ProposedRoleTasks.

The existing test file covers the original PR #125 surface. This file covers
the new required-field surface, brief-conflict parsing, and the RC-24
integer-rejection rule on ``depends_on_focus``.
"""

from __future__ import annotations

import pytest

from squadops.cycles.proposed_role_tasks import (
    BriefConflict,
    ProposedRoleTasks,
)

pytestmark = [pytest.mark.domain_orchestration]


# Minimal valid proposal that includes every Rev 1 required field, used as
# the mutation base for each error test. Tasks list is empty so failures
# surface against the field under test rather than against task structure.
_BASE_VALID = """\
version: 1
proposing_role: dev
proposal_id: prop-dev-001
source_brief_id: brief-test-001
scope_statement: |
  Dev contributions for the user CRUD feature.
tasks: []
"""


# ---------------------------------------------------------------------------
# New required fields enforced
# ---------------------------------------------------------------------------


class TestNewRequiredFields:
    """Each new Rev 1 required field must raise ValueError when missing
    or when present-but-empty. These are the fields the merger relies on
    to tie a proposal back to the immutable brief (RC-22) and to track
    proposal provenance — silently parsing without them would leak
    untraceable proposals into the merge."""

    def test_missing_proposal_id_rejected(self):
        bad = (
            "version: 1\n"
            "proposing_role: dev\n"
            "source_brief_id: brief-1\n"
            "scope_statement: x\n"
            "tasks: []\n"
        )
        with pytest.raises(ValueError, match="proposal_id"):
            ProposedRoleTasks.from_yaml(bad)

    def test_missing_source_brief_id_rejected(self):
        bad = (
            "version: 1\n"
            "proposing_role: dev\n"
            "proposal_id: prop-1\n"
            "scope_statement: x\n"
            "tasks: []\n"
        )
        with pytest.raises(ValueError, match="source_brief_id"):
            ProposedRoleTasks.from_yaml(bad)

    def test_missing_scope_statement_rejected(self):
        bad = (
            "version: 1\n"
            "proposing_role: dev\n"
            "proposal_id: prop-1\n"
            "source_brief_id: brief-1\n"
            "tasks: []\n"
        )
        with pytest.raises(ValueError, match="scope_statement"):
            ProposedRoleTasks.from_yaml(bad)

    @pytest.mark.parametrize(
        "field,bad_value,error_match",
        [
            ("proposal_id", '""', "proposal_id"),
            ("source_brief_id", '""', "source_brief_id"),
            ("scope_statement", '""', "scope_statement"),
            ("scope_statement", '"   "', "scope_statement"),  # whitespace-only also rejected
        ],
    )
    def test_empty_required_field_rejected(self, field, bad_value, error_match):
        # Build YAML by replacing the field's value with the empty/blank version.
        lines = _BASE_VALID.splitlines(keepends=True)
        out_lines = []
        for line in lines:
            if line.startswith(f"{field}:") or line.startswith(f"{field} ") or line.startswith(f"{field}\n"):
                continue
            out_lines.append(line)
        bad = "".join(out_lines) + f"{field}: {bad_value}\n"
        with pytest.raises(ValueError, match=error_match):
            ProposedRoleTasks.from_yaml(bad)


# ---------------------------------------------------------------------------
# Brief conflicts parsing
# ---------------------------------------------------------------------------


class TestBriefConflicts:
    """Brief conflicts are how proposers escalate spec disagreements with the
    shared brief (SIP-0093 §5.5). They must parse with both severities and
    reject unknown severities — the merger's escalation behavior branches on
    severity, so a typo there would silently downgrade a blocking conflict."""

    def test_parses_warning_and_blocking(self):
        yaml_doc = _BASE_VALID + """
brief_conflicts:
  - brief_field: accepted_stack
    proposed_change: Use SQLite instead of in-memory
    reason: PRD requires persistence across app restart
    severity: blocking
    affected_proposal_task_keys: [dev:repository, qa:persistence tests]
  - brief_field: scope_cuts
    proposed_change: Drop the typeahead suggestion feature
    reason: Out of scope for MVP
    severity: warning
"""
        proposal = ProposedRoleTasks.from_yaml(yaml_doc)
        assert len(proposal.brief_conflicts) == 2

        blocking = proposal.brief_conflicts[0]
        assert isinstance(blocking, BriefConflict)
        assert blocking.brief_field == "accepted_stack"
        assert blocking.severity == "blocking"
        assert blocking.affected_proposal_task_keys == [
            "dev:repository",
            "qa:persistence tests",
        ]

        warning = proposal.brief_conflicts[1]
        assert warning.severity == "warning"
        assert warning.affected_proposal_task_keys == []

    def test_unknown_severity_rejected(self):
        yaml_doc = _BASE_VALID + """
brief_conflicts:
  - brief_field: accepted_stack
    proposed_change: foo
    reason: bar
    severity: critical
"""
        with pytest.raises(ValueError, match="severity"):
            ProposedRoleTasks.from_yaml(yaml_doc)

    def test_missing_brief_field_rejected(self):
        yaml_doc = _BASE_VALID + """
brief_conflicts:
  - proposed_change: foo
    reason: bar
    severity: warning
"""
        with pytest.raises(ValueError, match="brief_field"):
            ProposedRoleTasks.from_yaml(yaml_doc)

    def test_default_empty_list(self):
        proposal = ProposedRoleTasks.from_yaml(_BASE_VALID)
        assert proposal.brief_conflicts == []


# ---------------------------------------------------------------------------
# RC-24: integer entries in depends_on_focus rejected
# ---------------------------------------------------------------------------


class TestDependsOnFocusRC24:
    """Proposers must use ``{role}:{focus}`` strings — never raw integer
    task indices. If a proposer leaked an integer, the merger's dependency
    resolution would silently mis-wire because integers happen to coerce to
    strings cleanly. Reject at parse time so the malformation surfaces."""

    def test_integer_entry_rejected(self):
        bad = (
            _BASE_VALID.replace("tasks: []\n", "")
            + """tasks:
  - task_type: qa.test
    role: qa
    focus: integration smoke
    description: smoke the running app
    depends_on_focus: [3]
"""
        )
        with pytest.raises(ValueError, match="RC-24"):
            ProposedRoleTasks.from_yaml(bad)

    def test_string_entry_parses(self):
        good = (
            _BASE_VALID.replace("tasks: []\n", "")
            + """tasks:
  - task_type: qa.test
    role: qa
    focus: integration smoke
    description: smoke the running app
    depends_on_focus: ["dev:backend api"]
"""
        )
        proposal = ProposedRoleTasks.from_yaml(good)
        assert proposal.tasks[0].depends_on_focus == ["dev:backend api"]

    def test_bool_entry_rejected(self):
        """``isinstance(True, int)`` is True in Python — without an explicit
        bool guard, a YAML ``true`` would bypass the integer check."""
        bad = (
            _BASE_VALID.replace("tasks: []\n", "")
            + """tasks:
  - task_type: qa.test
    role: qa
    focus: integration smoke
    description: smoke the running app
    depends_on_focus: [true]
"""
        )
        with pytest.raises(ValueError, match="RC-24"):
            ProposedRoleTasks.from_yaml(bad)


# ---------------------------------------------------------------------------
# Optional Rev 1 fields round-trip
# ---------------------------------------------------------------------------


class TestOptionalFieldsRoundTrip:
    """Recommended optional fields must parse cleanly when present and
    default to sensible empty values when absent. The merger relies on
    presence-or-absence to know which dimensions a proposer surfaced."""

    def test_optional_fields_default_empty(self):
        proposal = ProposedRoleTasks.from_yaml(_BASE_VALID)
        assert proposal.source_artifact_refs == []
        assert proposal.assumptions == []
        assert proposal.risks == []
        assert proposal.gaps_not_covered == []
        assert proposal.confidence == ""

    def test_optional_fields_parse_when_present(self):
        yaml_doc = _BASE_VALID + """
source_artifact_refs:
  - planning_artifact.md
  - design.md
assumptions:
  - Auth provider is Keycloak per the brief.
risks:
  - Persistence layer choice unresolved.
gaps_not_covered:
  - Frontend smoke tests deferred to qa.
confidence: medium
"""
        proposal = ProposedRoleTasks.from_yaml(yaml_doc)
        assert proposal.source_artifact_refs == ["planning_artifact.md", "design.md"]
        assert proposal.assumptions == ["Auth provider is Keycloak per the brief."]
        assert proposal.risks == ["Persistence layer choice unresolved."]
        assert proposal.gaps_not_covered == ["Frontend smoke tests deferred to qa."]
        assert proposal.confidence == "medium"
