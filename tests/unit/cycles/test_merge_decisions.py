"""Tests for ``MergeDecisions`` (SIP-0093 §5.7).

The merger's audit artifact carries every load-bearing invariant for the
post-cutover framing pipeline. The parser enforces them so downstream
consumers (gate package, observability, M3 applier) can trust the shape
without re-checking.

Coverage:

- Required-field surface enforced.
- RC-26 invariant (``authoring_mode`` ⇔ ``sole_author_reason`` ⇔
  ``proposal_completeness``) enforced in all four cross-product cells.
- ``canonical_tasks.task_index`` is unique-and-contiguous from 0.
- ``merge_action`` and ``disposition`` enum values bounded.
- ``MissingProposal`` and ``BriefConflictDisposition`` parse with their
  full required surface.
"""

from __future__ import annotations

import pytest

from squadops.cycles.merge_decisions import (
    BriefConflictDisposition,
    CanonicalTaskProvenance,
    MergeDecisions,
    MissingProposal,
    _validate_rc26,
)

pytestmark = [pytest.mark.domain_orchestration]


_VALID_MULTI_ROLE = """\
version: 1
target_plan_id: plan-cyc-test
brief_id: brief-test-001
proposal_ids: [prop-dev-001, prop-qa-001]
guidance_ids: [guidance-strategy-001]
authoring_mode: multi_role
sole_author_reason: null
proposal_completeness: complete
missing_proposals: []
canonical_tasks:
  - task_index: 0
    source_proposal_task_keys: [dev:backend api]
    proposed_by: [development]
    merge_action: accepted
    reason: "Single dev proposal, no conflicts."
  - task_index: 1
    source_proposal_task_keys: [qa:integration smoke]
    proposed_by: [qa]
    merge_action: accepted
    reason: "Standalone qa task."
brief_conflicts_disposition: []
operator_notes: ""
"""


_VALID_SOLE_AUTHOR = """\
version: 1
target_plan_id: plan-cyc-test
brief_id: brief-test-001
proposal_ids: []
guidance_ids: []
authoring_mode: sole_author
sole_author_reason: no_contributors_configured
proposal_completeness: sole_author
missing_proposals: []
canonical_tasks:
  - task_index: 0
    source_proposal_task_keys: []
    proposed_by: []
    merge_action: gap_filled
    reason: "Sole-author fallback via PlanAuthoringService."
brief_conflicts_disposition: []
operator_notes: ""
"""


# ---------------------------------------------------------------------------
# Happy path — both authoring modes
# ---------------------------------------------------------------------------


class TestFromYAMLHappy:
    def test_parses_multi_role_decisions(self):
        md = MergeDecisions.from_yaml(_VALID_MULTI_ROLE)
        assert md.version == 1
        assert md.target_plan_id == "plan-cyc-test"
        assert md.brief_id == "brief-test-001"
        assert md.proposal_ids == ["prop-dev-001", "prop-qa-001"]
        assert md.authoring_mode == "multi_role"
        assert md.sole_author_reason is None
        assert md.proposal_completeness == "complete"

        assert len(md.canonical_tasks) == 2
        t0 = md.canonical_tasks[0]
        assert isinstance(t0, CanonicalTaskProvenance)
        assert t0.task_index == 0
        assert t0.source_proposal_task_keys == ["dev:backend api"]
        assert t0.proposed_by == ["development"]
        assert t0.merge_action == "accepted"

    def test_parses_sole_author_decisions(self):
        md = MergeDecisions.from_yaml(_VALID_SOLE_AUTHOR)
        assert md.authoring_mode == "sole_author"
        assert md.sole_author_reason == "no_contributors_configured"
        assert md.proposal_completeness == "sole_author"
        assert md.canonical_tasks[0].merge_action == "gap_filled"

    def test_parses_with_missing_proposals(self):
        """Partial-completeness multi_role records each role that failed,
        so the operator console can surface "qa didn't propose" without
        re-deriving it from artifact absence."""
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "proposal_completeness: complete",
            "proposal_completeness: partial",
        ).replace(
            "missing_proposals: []",
            (
                "missing_proposals:\n"
                "  - role: qa\n"
                "    failure_reason: llm_error\n"
                "  - role: strategy\n"
                "    failure_reason: timeout"
            ),
        )
        md = MergeDecisions.from_yaml(yaml_doc)
        assert len(md.missing_proposals) == 2
        assert md.missing_proposals[0] == MissingProposal(
            role="qa", failure_reason="llm_error"
        )

    def test_parses_with_brief_conflicts_disposition(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "brief_conflicts_disposition: []",
            (
                "brief_conflicts_disposition:\n"
                "  - brief_field: accepted_stack\n"
                "    severity: blocking\n"
                "    disposition: escalated_to_operator\n"
                "    reason: PRD requires persistence; conflict surfaced to operator."
            ),
        )
        md = MergeDecisions.from_yaml(yaml_doc)
        assert len(md.brief_conflicts_disposition) == 1
        d = md.brief_conflicts_disposition[0]
        assert isinstance(d, BriefConflictDisposition)
        assert d.severity == "blocking"
        assert d.disposition == "escalated_to_operator"


# ---------------------------------------------------------------------------
# RC-26 invariant enforcement
# ---------------------------------------------------------------------------


class TestRC26Invariant:
    """The four combinations the parser must distinguish:

    1. multi_role + sole_author_reason=null + completeness in {complete, partial} → valid
    2. multi_role + sole_author_reason=set → invalid (the rejection path tested below)
    3. multi_role + completeness=sole_author → invalid
    4. sole_author + sole_author_reason=null → invalid
    5. sole_author + completeness != sole_author → invalid
    6. sole_author + sole_author_reason in valid set + completeness=sole_author → valid

    Each invalid combination is one rule the merger relies on at construction
    time; testing each separately keeps regressions diagnostic."""

    def test_multi_role_with_sole_author_reason_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "sole_author_reason: null",
            "sole_author_reason: no_contributors_configured",
        )
        with pytest.raises(ValueError, match="multi_role.*sole_author_reason"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_multi_role_with_sole_author_completeness_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "proposal_completeness: complete",
            "proposal_completeness: sole_author",
        )
        with pytest.raises(ValueError, match="multi_role.*proposal_completeness"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_sole_author_with_null_reason_rejected(self):
        yaml_doc = _VALID_SOLE_AUTHOR.replace(
            "sole_author_reason: no_contributors_configured",
            "sole_author_reason: null",
        )
        with pytest.raises(ValueError, match="sole_author.*sole_author_reason"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_sole_author_with_non_sole_author_completeness_rejected(self):
        yaml_doc = _VALID_SOLE_AUTHOR.replace(
            "proposal_completeness: sole_author",
            "proposal_completeness: partial",
        )
        with pytest.raises(ValueError, match="sole_author.*proposal_completeness"):
            MergeDecisions.from_yaml(yaml_doc)

    @pytest.mark.parametrize("reason", ["unknown", "user_quit", "manual_override"])
    def test_unknown_sole_author_reason_rejected(self, reason):
        yaml_doc = _VALID_SOLE_AUTHOR.replace(
            "sole_author_reason: no_contributors_configured",
            f"sole_author_reason: {reason}",
        )
        with pytest.raises(ValueError, match="sole_author_reason"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_rc26_validator_callable_directly(self):
        """The merger constructs MergeDecisions in code (PR 93.3); the
        invariant function must be callable outside the parser so the
        constructor path can pre-validate."""
        # valid combinations don't raise
        _validate_rc26("multi_role", None, "complete")
        _validate_rc26("multi_role", None, "partial")
        _validate_rc26("sole_author", "no_contributors_configured", "sole_author")
        _validate_rc26("sole_author", "all_proposals_failed", "sole_author")

        with pytest.raises(ValueError):
            _validate_rc26("multi_role", "all_proposals_failed", "complete")


# ---------------------------------------------------------------------------
# task_index unique-and-contiguous from 0
# ---------------------------------------------------------------------------


class TestCanonicalTaskIndices:
    def test_non_contiguous_indices_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "  - task_index: 0\n",
            "  - task_index: 5\n",
        )
        with pytest.raises(ValueError, match="contiguous"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_duplicate_indices_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "  - task_index: 1\n",
            "  - task_index: 0\n",
        )
        with pytest.raises(ValueError, match="contiguous"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_non_int_task_index_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "  - task_index: 0\n",
            '  - task_index: "first"\n',
        )
        with pytest.raises(ValueError, match="task_index"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_empty_canonical_tasks_valid(self):
        """An edge case: a sole-author cycle with no canonical tasks at all
        (e.g., the merger ran and decided every proposal was redundant).
        Parser should accept it; the merger surfaces the pathology
        elsewhere if it's actually a problem."""
        yaml_doc = _VALID_SOLE_AUTHOR.replace(
            "canonical_tasks:\n  - task_index: 0\n    source_proposal_task_keys: []\n    proposed_by: []\n    merge_action: gap_filled\n    reason: \"Sole-author fallback via PlanAuthoringService.\"\n",
            "canonical_tasks: []\n",
        )
        md = MergeDecisions.from_yaml(yaml_doc)
        assert md.canonical_tasks == []


# ---------------------------------------------------------------------------
# Enum validations
# ---------------------------------------------------------------------------


class TestEnumValidation:
    @pytest.mark.parametrize(
        "bad_action", ["replaced", "rejected", "ACCEPTED", ""]
    )
    def test_unknown_merge_action_rejected(self, bad_action):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "    merge_action: accepted\n    reason: \"Single dev proposal, no conflicts.\"",
            f"    merge_action: {bad_action}\n    reason: foo",
        )
        with pytest.raises(ValueError, match="merge_action"):
            MergeDecisions.from_yaml(yaml_doc)

    @pytest.mark.parametrize(
        "bad_disposition", ["deferred", "fixed", "ESCALATED"]
    )
    def test_unknown_disposition_rejected(self, bad_disposition):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "brief_conflicts_disposition: []",
            (
                "brief_conflicts_disposition:\n"
                "  - brief_field: accepted_stack\n"
                "    severity: warning\n"
                f"    disposition: {bad_disposition}\n"
                "    reason: x"
            ),
        )
        with pytest.raises(ValueError, match="disposition"):
            MergeDecisions.from_yaml(yaml_doc)

    @pytest.mark.parametrize("bad_severity", ["critical", "info", "ERROR"])
    def test_unknown_severity_rejected(self, bad_severity):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "brief_conflicts_disposition: []",
            (
                "brief_conflicts_disposition:\n"
                "  - brief_field: accepted_stack\n"
                f"    severity: {bad_severity}\n"
                "    disposition: rejected\n"
                "    reason: x"
            ),
        )
        with pytest.raises(ValueError, match="severity"):
            MergeDecisions.from_yaml(yaml_doc)


# ---------------------------------------------------------------------------
# Required-field surface
# ---------------------------------------------------------------------------


class TestRequiredFields:
    @pytest.mark.parametrize(
        "missing_field",
        ["version", "target_plan_id", "brief_id", "authoring_mode", "proposal_completeness"],
    )
    def test_required_field_missing_rejected(self, missing_field):
        lines = _VALID_MULTI_ROLE.splitlines(keepends=True)
        filtered = [line for line in lines if not line.startswith(f"{missing_field}:")]
        bad = "".join(filtered)
        with pytest.raises(ValueError, match=missing_field):
            MergeDecisions.from_yaml(bad)

    def test_canonical_task_missing_reason_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            '    merge_action: accepted\n    reason: "Single dev proposal, no conflicts."',
            "    merge_action: accepted",
        )
        with pytest.raises(ValueError, match="reason"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_missing_proposal_entry_missing_failure_reason_rejected(self):
        yaml_doc = _VALID_MULTI_ROLE.replace(
            "missing_proposals: []",
            "missing_proposals:\n  - role: qa",
        )
        with pytest.raises(ValueError, match="failure_reason"):
            MergeDecisions.from_yaml(yaml_doc)

    def test_malformed_yaml_rejected(self):
        with pytest.raises(ValueError, match="Malformed"):
            MergeDecisions.from_yaml("version: 1\ntarget_plan_id: [unclosed")
