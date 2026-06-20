"""Tests for ProposedRoleTasks (SIP-0093)."""

from __future__ import annotations

import pytest

from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.proposed_role_tasks import (
    ProposedRoleTasks,
    ProposedTask,
    canonicalize_dep_ref,
    focus_key,
    role_to_id,
)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# focus_key
# ---------------------------------------------------------------------------


class TestFocusKey:
    """Cross-proposal dependency references must resolve regardless of
    how proposers format the focus string. Two proposers writing
    `"backend api"` and `"Backend  API "` must produce the same key,
    otherwise the merger's dependency resolution silently drops edges.
    """

    @pytest.mark.parametrize(
        "role,focus,expected",
        [
            ("dev", "backend api", "dev:backend api"),
            ("Dev", "Backend API", "dev:backend api"),
            ("dev", "  backend  api  ", "dev:backend api"),
            ("DEV", "Backend\tAPI", "dev:backend api"),
        ],
    )
    def test_normalizes_role_and_focus(self, role, focus, expected):
        assert focus_key(role, focus) == expected

    def test_distinct_roles_produce_distinct_keys(self):
        assert focus_key("dev", "tests") != focus_key("qa", "tests")

    @pytest.mark.parametrize(
        "display,role_id",
        [("development", "dev"), ("strategy", "strat"), ("Development", "dev")],
    )
    def test_display_name_prefix_collapses_to_role_id(self, display, role_id):
        # #189: a proposer that writes the role DISPLAY name must produce the
        # same key as one that writes the role id, or dependency edges drop.
        assert focus_key(display, "Backend Models") == focus_key(role_id, "Backend Models")

    def test_role_id_and_unknown_role_pass_through(self):
        # qa/builder/data are identical in both vocabularies — no aliasing.
        assert role_to_id("qa") == "qa"
        assert role_to_id("builder") == "builder"
        assert role_to_id("development") == "dev"
        assert role_to_id("strategy") == "strat"


class TestCanonicalizeDepRef:
    """#189: a raw ``depends_on_focus`` reference string must normalize the
    same way :func:`focus_key` normalizes a produced task's key, so the
    resolve side and produce side can't drift."""

    def test_display_name_ref_matches_produced_key(self):
        assert canonicalize_dep_ref("development:Backend Models") == focus_key(
            "dev", "backend  models"
        )

    def test_already_canonical_ref_is_idempotent(self):
        assert canonicalize_dep_ref("dev:backend api") == "dev:backend api"

    def test_bare_string_without_colon_treated_as_focus(self):
        # No role prefix → the whole string is a (normalized) focus.
        assert canonicalize_dep_ref("Backend  Models") == "backend models"


# ---------------------------------------------------------------------------
# from_yaml — happy path
# ---------------------------------------------------------------------------


_VALID_PROPOSAL = """\
version: 1
proposing_role: qa
proposal_id: prop-qa-001
source_brief_id: brief-test-001
scope_statement: |
  QA coverage for backend endpoints.
tasks:
  - task_type: qa.test
    role: qa
    focus: "backend pytest suite"
    description: "Cover the user CRUD endpoints with pytest"
    expected_artifacts:
      - "backend/tests/test_api.py"
    acceptance_criteria:
      - check: regex_match
        file: "backend/tests/test_api.py"
        pattern: "def test_"
        count_min: 5
    depends_on_focus:
      - "dev:backend api"
"""


class TestFromYAMLHappy:
    def test_parses_valid_proposal(self):
        proposal = ProposedRoleTasks.from_yaml(_VALID_PROPOSAL)

        assert proposal.version == 1
        assert proposal.proposing_role == "qa"
        assert len(proposal.tasks) == 1
        task = proposal.tasks[0]
        assert isinstance(task, ProposedTask)
        assert task.task_type == "qa.test"
        assert task.focus == "backend pytest suite"
        assert task.expected_artifacts == ["backend/tests/test_api.py"]
        # Typed-check entries get parsed into TypedCheck instances —
        # the same parser the canonical ImplementationPlan uses.
        assert len(task.acceptance_criteria) == 1
        check = task.acceptance_criteria[0]
        assert isinstance(check, TypedCheck)
        assert check.check == "regex_match"
        assert task.depends_on_focus == ["dev:backend api"]

    def test_empty_tasks_list_valid(self):
        """A role that fails to find anything to propose returns an
        empty list. The merger absorbs the empty proposal (per
        SIP-0093 §5.4 fall-back) — the parser shouldn't reject it."""
        proposal = ProposedRoleTasks.from_yaml(
            "version: 1\n"
            "proposing_role: strat\n"
            "proposal_id: prop-strat-001\n"
            "source_brief_id: brief-test-001\n"
            "scope_statement: 'Strategy proposal — no tasks'\n"
            "tasks: []\n"
        )
        assert proposal.tasks == []

    def test_task_keys_round_trip(self):
        proposal = ProposedRoleTasks.from_yaml(_VALID_PROPOSAL)
        assert proposal.task_keys() == ["qa:backend pytest suite"]


# ---------------------------------------------------------------------------
# from_yaml — error paths
# ---------------------------------------------------------------------------


class TestFromYAMLErrors:
    """Each error case maps to a real failure mode the merger has to
    handle. Catching the malformed proposal at parse time means the
    merger can drop it cleanly rather than absorb a half-formed task
    list and corrupt the canonical plan."""

    def test_missing_version_rejected(self):
        with pytest.raises(ValueError, match="version"):
            ProposedRoleTasks.from_yaml("proposing_role: qa\ntasks: []\n")

    def test_missing_proposing_role_rejected(self):
        with pytest.raises(ValueError, match="proposing_role"):
            ProposedRoleTasks.from_yaml("version: 1\ntasks: []\n")

    def test_empty_proposing_role_rejected(self):
        with pytest.raises(ValueError, match="proposing_role"):
            ProposedRoleTasks.from_yaml(
                'version: 1\n'
                'proposing_role: ""\n'
                'proposal_id: prop-1\n'
                'source_brief_id: brief-1\n'
                "scope_statement: 'x'\n"
                'tasks: []\n'
            )

    def test_non_int_version_rejected(self):
        with pytest.raises(ValueError, match="version"):
            ProposedRoleTasks.from_yaml(
                'version: "1"\n'
                'proposing_role: qa\n'
                'proposal_id: prop-1\n'
                'source_brief_id: brief-1\n'
                "scope_statement: 'x'\n"
                'tasks: []\n'
            )

    def test_malformed_yaml_rejected(self):
        with pytest.raises(ValueError, match="Malformed proposal YAML"):
            ProposedRoleTasks.from_yaml("version: 1\nproposing_role: qa\ntasks: [unclosed")

    def test_top_level_not_mapping_rejected(self):
        with pytest.raises(ValueError, match="mapping"):
            ProposedRoleTasks.from_yaml("- just\n- a\n- list\n")

    def test_task_missing_focus_rejected(self):
        bad = """\
version: 1
proposing_role: qa
proposal_id: prop-1
source_brief_id: brief-1
scope_statement: x
tasks:
  - task_type: qa.test
    role: qa
    description: "no focus"
"""
        with pytest.raises(ValueError, match="focus"):
            ProposedRoleTasks.from_yaml(bad)

    def test_duplicate_focus_within_proposal_rejected(self):
        """If the same proposer emits two tasks with the same role+focus
        the merger's dependency resolution can't disambiguate. Reject
        at parse time so the malformation surfaces immediately."""
        bad = """\
version: 1
proposing_role: dev
proposal_id: prop-1
source_brief_id: brief-1
scope_statement: x
tasks:
  - task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "..."
  - task_type: development.develop
    role: dev
    focus: "backend  models"
    description: "...also models?"
"""
        with pytest.raises(ValueError, match="collides"):
            ProposedRoleTasks.from_yaml(bad)

    def test_depends_on_focus_must_be_list(self):
        bad = """\
version: 1
proposing_role: qa
proposal_id: prop-1
source_brief_id: brief-1
scope_statement: x
tasks:
  - task_type: qa.test
    role: qa
    focus: "smoke"
    description: "..."
    depends_on_focus: "dev:backend"
"""
        with pytest.raises(ValueError, match="depends_on_focus"):
            ProposedRoleTasks.from_yaml(bad)

    def test_acceptance_criteria_must_be_list(self):
        bad = """\
version: 1
proposing_role: qa
proposal_id: prop-1
source_brief_id: brief-1
scope_statement: x
tasks:
  - task_type: qa.test
    role: qa
    focus: "smoke"
    description: "..."
    acceptance_criteria: "tests pass"
"""
        with pytest.raises(ValueError, match="acceptance_criteria"):
            ProposedRoleTasks.from_yaml(bad)
