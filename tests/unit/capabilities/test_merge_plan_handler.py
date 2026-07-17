"""Tests for ``GovernanceMergePlanHandler`` (SIP-0093 PR 93.3).

The handler is the runtime-route cutover: it consumes proposer outcomes
via ``prior_outputs`` and produces ``implementation_plan.yaml`` +
``merge_decisions.yaml``. Two execution paths:

1. **Multi-role merge** (`merge_proposals`) — deterministic application
   of §5.8 rules over the surviving proposals.
2. **Sole-author fallback** (`PlanAuthoringService.produce_plan`) — when
   no proposals are available (empty contributors OR all configured
   proposals failed).

The worked-example test is the deterministic-merge regression anchor —
if it breaks, SIP-0093's merge semantics broke. The RC-26 cross-product
tests guard the authoring_mode/sole_author_reason/proposal_completeness
invariant.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers._plan_merger import merge_proposals
from squadops.capabilities.handlers.planning_tasks import GovernanceMergePlanHandler
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.merge_decisions import MergeDecisions
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
from squadops.cycles.plan_guidance import PlanGuidance
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Fixtures: brief + proposals matching SIP-0093 §5.8's worked example
# ---------------------------------------------------------------------------


_BRIEF_YAML = """\
version: 1
brief_id: brief-merge-001
objective_summary: |
  User-CRUD API with duplicate-join 409 handling.
accepted_stack:
  backend: "FastAPI"
must_cover_requirements:
  - "POST /runs/{id}/join returns 409 on duplicate join"
scope_cuts: []
risk_areas:
  - "duplicate-join concurrency"
"""


_DEV_PROPOSAL_YAML = """\
version: 1
proposal_id: prop-dev-merge-001
source_brief_id: brief-merge-001
proposing_role: development
scope_statement: |
  Backend implementation of /runs/{id}/join.
tasks:
  - task_type: development.develop
    role: dev
    focus: "api join"
    description: |
      Implement POST /runs/{id}/join with 409 on duplicate.
    expected_artifacts:
      - "backend/routes.py"
    acceptance_criteria:
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths:
          - ["POST", "/runs/{id}/join"]
        severity: error
    depends_on_focus: []
"""


_QA_PROPOSAL_YAML = """\
version: 1
proposal_id: prop-qa-merge-001
source_brief_id: brief-merge-001
proposing_role: qa
scope_statement: |
  Test coverage for /runs/{id}/join including 409 path.
tasks:
  - task_type: qa.test
    role: qa
    focus: "backend join tests"
    description: |
      Pytest functions verifying 409 on duplicate join.
    expected_artifacts:
      - "tests/test_backend.py"
    acceptance_criteria:
      - check: regex_match
        file: tests/test_backend.py
        pattern: "status_code\\\\s*=\\\\s*409"
        count_min: 1
        severity: error
    depends_on_focus:
      - "dev:api join"
"""


_GUIDANCE_YAML = """\
version: 1
guidance_id: guidance-merge-001
source_brief_id: brief-merge-001
proposing_role: strategy
priority_guidance:
  - area: backend_api
    priority: high
    rationale: "Brief flags duplicate-join concurrency — prioritize backend API."
must_not_skip:
  - "duplicate-join 409 handling"
"""


@pytest.fixture()
def brief():
    return PlanAuthoringBrief.from_yaml(_BRIEF_YAML)


@pytest.fixture()
def dev_proposal():
    return ProposedRoleTasks.from_yaml(_DEV_PROPOSAL_YAML)


@pytest.fixture()
def qa_proposal():
    return ProposedRoleTasks.from_yaml(_QA_PROPOSAL_YAML)


@pytest.fixture()
def strategy_guidance():
    return PlanGuidance.from_yaml(_GUIDANCE_YAML)


# ---------------------------------------------------------------------------
# Worked example (§5.8) — the central regression anchor
# ---------------------------------------------------------------------------


class TestWorkedExample:
    """SIP-0093 §5.8 worked example.

    Neo proposes `dev.api.join` with `endpoint_defined`.
    Eve proposes `qa.backend.join_tests` with `regex_match` and
    `depends_on_focus: ["dev:api join"]`.

    Merger result must:
      - Emit two canonical tasks with task_index 0 (dev) and 1 (qa).
      - Resolve qa's symbolic dep to depends_on: [0].
      - Record both as merge_action: accepted with correct proposed_by.

    If this test breaks, the SIP-0093 deterministic-merge semantics broke."""

    def test_two_canonical_tasks_emitted_with_resolved_dependency(
        self, brief, dev_proposal, qa_proposal
    ):
        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="test_proj",
            cycle_id="cyc_test",
            prd_hash="abc123",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )

        # Two canonical tasks
        assert len(plan.tasks) == 2

        dev_task = plan.tasks[0]
        qa_task = plan.tasks[1]

        # Dev task: index 0, owned by dev, carries endpoint_defined criterion
        assert dev_task.task_index == 0
        assert dev_task.task_type == "development.develop"
        assert dev_task.role == "dev"
        assert dev_task.focus == "api join"
        assert dev_task.depends_on == []
        assert any(
            hasattr(c, "check") and c.check == "endpoint_defined"
            for c in dev_task.acceptance_criteria
        )

        # QA task: index 1, owned by qa, carries regex_match, depends_on=[0]
        assert qa_task.task_index == 1
        assert qa_task.task_type == "qa.test"
        assert qa_task.role == "qa"
        assert qa_task.focus == "backend join tests"
        assert qa_task.depends_on == [0]  # resolved from "dev:api join"
        assert any(
            hasattr(c, "check") and c.check == "regex_match" for c in qa_task.acceptance_criteria
        )

    def test_merge_decisions_provenance_recorded(self, brief, dev_proposal, qa_proposal):
        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="test_proj",
            cycle_id="cyc_test",
            prd_hash="abc123",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )

        assert decisions.authoring_mode == "multi_role"
        assert decisions.sole_author_reason is None
        assert decisions.proposal_completeness == "complete"
        assert len(decisions.canonical_tasks) == 2

        assert decisions.canonical_tasks[0].proposed_by == ["development"]
        assert decisions.canonical_tasks[0].merge_action == "accepted"
        assert decisions.canonical_tasks[1].proposed_by == ["qa"]
        assert decisions.canonical_tasks[1].merge_action == "accepted"

    def test_serialized_plan_round_trips(self, brief, dev_proposal, qa_proposal):
        """Emitted implementation_plan.yaml must parse back to the same
        shape via ImplementationPlan.from_yaml — guards against subtle
        YAML serialization drift (typed-check shape, depends_on int list).
        """
        from squadops.capabilities.handlers._plan_merger import emit_plan_yaml

        plan, _ = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="test_proj",
            cycle_id="cyc_test",
            prd_hash="abc123",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )
        plan_yaml = emit_plan_yaml(plan)
        reparsed = ImplementationPlan.from_yaml(plan_yaml)

        assert len(reparsed.tasks) == 2
        assert reparsed.tasks[1].depends_on == [0]
        assert reparsed.project_id == "test_proj"

    def test_serialized_decisions_round_trip(self, brief, dev_proposal, qa_proposal):
        from squadops.capabilities.handlers._plan_merger import (
            emit_merge_decisions_yaml,
        )

        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="test_proj",
            cycle_id="cyc_test",
            prd_hash="abc123",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )
        decisions_yaml = emit_merge_decisions_yaml(decisions)
        reparsed = MergeDecisions.from_yaml(decisions_yaml)

        assert reparsed.authoring_mode == "multi_role"
        assert reparsed.brief_id == "brief-merge-001"
        assert len(reparsed.canonical_tasks) == 2


# ---------------------------------------------------------------------------
# RC-26 invariant: authoring_mode ⇔ sole_author_reason ⇔ proposal_completeness
# ---------------------------------------------------------------------------


class TestAuthoringModeInvariant:
    """The merger must emit valid RC-26 combinations across all four
    success/failure patterns. Each cell is a separate test so a regression
    pinpoints the broken path."""

    def test_all_proposals_succeed_multi_role_complete(
        self, brief, dev_proposal, qa_proposal, strategy_guidance
    ):
        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=strategy_guidance,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development", "qa", "strategy"],
            missing_proposals=[],
        )
        assert decisions.authoring_mode == "multi_role"
        assert decisions.sole_author_reason is None
        assert decisions.proposal_completeness == "complete"

    def test_some_proposals_fail_multi_role_partial(self, brief, dev_proposal):
        """Dev proposal arrives; qa + strategy missing. The merge still
        proceeds because at least one proposal survived. proposal_completeness
        must be 'partial', not 'complete'."""
        from squadops.cycles.merge_decisions import MissingProposal

        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=None,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development", "qa", "strategy"],
            missing_proposals=[
                MissingProposal(role="qa", failure_reason="llm_error"),
                MissingProposal(role="strategy", failure_reason="timeout"),
            ],
        )
        assert decisions.authoring_mode == "multi_role"
        assert decisions.sole_author_reason is None
        assert decisions.proposal_completeness == "partial"
        assert "QA coverage warning" in decisions.operator_notes
        assert "Ordering/priority warning" in decisions.operator_notes

    def test_emitted_yaml_passes_rc26_parser_validation(self, brief, dev_proposal, qa_proposal):
        """The merger's emitted merge_decisions.yaml must round-trip through
        MergeDecisions.from_yaml — which enforces RC-26 at parse time. This
        guards against the merger constructing internally-valid Python
        objects whose serialized form violates the invariant."""
        from squadops.capabilities.handlers._plan_merger import (
            emit_merge_decisions_yaml,
        )

        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )
        # Round-trip — raises ValueError if RC-26 violated
        reparsed = MergeDecisions.from_yaml(emit_merge_decisions_yaml(decisions))
        assert reparsed.authoring_mode == decisions.authoring_mode


# ---------------------------------------------------------------------------
# Brief-conflict handling (§5.8 rule 1)
# ---------------------------------------------------------------------------


class TestBriefConflicts:
    """Warning → accepted; blocking → escalated. Each maps to a distinct
    BriefConflictDisposition and (for blocking) an operator_notes entry."""

    def test_warning_brief_conflict_accepted(self, brief):
        proposal_yaml = (
            _DEV_PROPOSAL_YAML.rstrip("\n")
            + """
brief_conflicts:
  - brief_field: accepted_stack
    proposed_change: Use SQLite instead of in-memory.
    reason: PRD requires persistence.
    severity: warning
    affected_proposal_task_keys: ["dev:api join"]
"""
        )
        dev_proposal = ProposedRoleTasks.from_yaml(proposal_yaml)
        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=None,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development"],
            missing_proposals=[],
        )
        assert len(decisions.brief_conflicts_disposition) == 1
        d = decisions.brief_conflicts_disposition[0]
        assert d.severity == "warning"
        assert d.disposition == "accepted"
        # Warning conflicts do NOT escalate to operator_notes
        assert "escalated" not in decisions.operator_notes.lower()

    def test_blocking_brief_conflict_escalated_to_operator(self, brief):
        proposal_yaml = (
            _DEV_PROPOSAL_YAML.rstrip("\n")
            + """
brief_conflicts:
  - brief_field: must_cover_requirements
    proposed_change: PRD adds a requirement the brief omitted.
    reason: PRD says X; brief is missing it.
    severity: blocking
"""
        )
        dev_proposal = ProposedRoleTasks.from_yaml(proposal_yaml)
        _plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=None,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development"],
            missing_proposals=[],
        )
        d = decisions.brief_conflicts_disposition[0]
        assert d.disposition == "escalated_to_operator"
        # Blocking conflicts MUST appear in operator_notes for gate visibility
        assert "Brief conflict escalated" in decisions.operator_notes
        assert "must_cover_requirements" in decisions.operator_notes


# ---------------------------------------------------------------------------
# Dependency resolution + gap-fill candidates (§5.8 rules 5, 7)
# ---------------------------------------------------------------------------


class TestDependencyResolution:
    """depends_on_focus resolution is the worked-example's central
    operation. Unresolved keys surface as operator notes rather than
    silent drops — the merger never invents tasks."""

    def test_known_focus_key_resolves_to_index(self, brief, dev_proposal, qa_proposal):
        plan, _ = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )
        assert plan.tasks[1].depends_on == [0]

    def test_unknown_focus_key_flagged_in_operator_notes(self, brief):
        """qa references dev:nonexistent — dev didn't propose that
        component. Rev 1 surfaces it as an operator note, doesn't
        auto-fill."""
        qa_proposal_yaml = _QA_PROPOSAL_YAML.replace(
            'depends_on_focus:\n      - "dev:api join"',
            'depends_on_focus:\n      - "dev:nonexistent"',
        )
        qa_proposal = ProposedRoleTasks.from_yaml(qa_proposal_yaml)

        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=None,  # No dev proposal — qa has dangling reference
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["qa"],
            missing_proposals=[],
        )
        # qa task has empty depends_on (unresolved key dropped, not silently added)
        assert plan.tasks[0].depends_on == []
        # Unresolved dep surfaces in operator_notes
        assert "Unresolved cross-proposal dependency" in decisions.operator_notes
        assert "dev:nonexistent" in decisions.operator_notes


# ---------------------------------------------------------------------------
# Dependency-key normalization (issue #189): role display-name vs role-id
# ---------------------------------------------------------------------------

# Dev proposal with an INTRA-proposal dependency expressed via the role
# DISPLAY name ("development:") rather than the role id ("dev:") — exactly the
# shape the SIP-0093 dev proposer emitted in cyc_1bbe424095fc, which dropped
# every dev->dev edge before the #189 fix.
_DEV_PROPOSAL_DISPLAYNAME_DEP_YAML = """\
version: 1
proposal_id: prop-dev-189
source_brief_id: brief-merge-001
proposing_role: development
scope_statement: |
  Backend models + endpoint, endpoint depends on models.
tasks:
  - task_type: development.develop
    role: dev
    focus: "Backend models and schemas"
    description: |
      Pydantic models for the run domain.
    expected_artifacts:
      - "backend/models.py"
    depends_on_focus: []
  - task_type: development.develop
    role: dev
    focus: "FastAPI endpoints"
    description: |
      Wire endpoints; needs the models task.
    expected_artifacts:
      - "backend/main.py"
    depends_on_focus:
      - "development:Backend models and schemas"
"""


class TestDependencyKeyNormalization:
    """#189: a ``depends_on_focus`` reference using the role DISPLAY name
    (``development:``/``strategy:``) or a different case must still resolve
    against the produced ``{role_id}:{focus.lower()}`` key. Only genuinely
    absent focuses (hallucinated targets) stay gap_fill candidates."""

    def test_intra_dev_display_name_self_reference_resolves(self, brief):
        """The cyc_1bbe424095fc regression: dev's own endpoint task depends on
        its own models task via ``development:Backend models and schemas``.
        Before #189 this dropped to ``depends_on: []``; now it resolves."""
        dev_proposal = ProposedRoleTasks.from_yaml(_DEV_PROPOSAL_DISPLAYNAME_DEP_YAML)
        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=None,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development"],
            missing_proposals=[],
        )
        assert plan.tasks[0].focus == "Backend models and schemas"
        assert plan.tasks[1].focus == "FastAPI endpoints"
        # Endpoint task resolves its display-name dependency to the models index.
        assert plan.tasks[1].depends_on == [0]
        assert "Unresolved cross-proposal dependency" not in decisions.operator_notes

    def test_cross_role_display_name_prefix_resolves(self, brief, dev_proposal):
        """qa references the dev task as ``development:api join`` (display name)
        — must resolve to the dev task index, not drop to a gap_fill note."""
        qa_proposal_yaml = _QA_PROPOSAL_YAML.replace(
            'depends_on_focus:\n      - "dev:api join"',
            'depends_on_focus:\n      - "development:api join"',
        )
        qa_proposal = ProposedRoleTasks.from_yaml(qa_proposal_yaml)
        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development", "qa"],
            missing_proposals=[],
        )
        assert plan.tasks[1].depends_on == [0]
        assert "Unresolved cross-proposal dependency" not in decisions.operator_notes

    def test_hallucinated_focus_gap_fills_with_normalized_key(self, brief):
        """A truly absent focus stays a gap_fill candidate even when the
        reference used a display-name prefix — and the operator note reports
        the NORMALIZED ``dev:`` key, not the raw ``development:`` form, so the
        note reads in the same vocabulary as the produced keys."""
        qa_proposal_yaml = _QA_PROPOSAL_YAML.replace(
            'depends_on_focus:\n      - "dev:api join"',
            'depends_on_focus:\n      - "development:nonexistent"',
        )
        qa_proposal = ProposedRoleTasks.from_yaml(qa_proposal_yaml)
        plan, decisions = merge_proposals(
            brief=brief,
            dev_proposal=None,
            qa_proposal=qa_proposal,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["qa"],
            missing_proposals=[],
        )
        assert plan.tasks[0].depends_on == []
        assert "Unresolved cross-proposal dependency" in decisions.operator_notes
        assert "dev:nonexistent" in decisions.operator_notes
        assert "development:nonexistent" not in decisions.operator_notes


# ---------------------------------------------------------------------------
# Domain-owner rule (§5.8 rule 2)
# ---------------------------------------------------------------------------


class TestDomainOwnership:
    """Dev tasks belong to dev; qa tasks belong to qa. A proposer that
    encroaches on another domain has its encroaching tasks dropped."""

    def test_dev_proposing_qa_task_is_dropped(self, brief):
        """Dev proposal includes a qa.test task — domain rule drops it."""
        rogue_dev_yaml = """\
version: 1
proposal_id: prop-dev-rogue
source_brief_id: brief-merge-001
proposing_role: development
scope_statement: |
  Dev with an out-of-domain qa task.
tasks:
  - task_type: development.develop
    role: dev
    focus: "models"
    description: "models"
    depends_on_focus: []
  - task_type: qa.test
    role: dev
    focus: "tests"
    description: "tests proposed by dev (rogue)"
    depends_on_focus: []
"""
        dev_proposal = ProposedRoleTasks.from_yaml(rogue_dev_yaml)
        plan, _ = merge_proposals(
            brief=brief,
            dev_proposal=dev_proposal,
            qa_proposal=None,
            strategy_guidance=None,
            project_id="p",
            cycle_id="c",
            prd_hash="h",
            configured_contributors=["development"],
            missing_proposals=[],
        )
        # Only the dev task survived
        assert len(plan.tasks) == 1
        assert plan.tasks[0].task_type == "development.develop"


# ---------------------------------------------------------------------------
# Handler integration: handle() reads prior_outputs and produces both
# artifacts in the HandlerResult.
# ---------------------------------------------------------------------------


def _make_merger_context():
    """Mock ExecutionContext for the handler. The merger is deterministic
    in the multi-role path — no LLM call. Sole-author tests inject an LLM
    mock for the PlanAuthoringService fallback."""
    llm = AsyncMock()
    llm.default_model = "test-model"
    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "system prompt (unused in deterministic merge)"
    prompt_service.assemble.return_value = assembled
    prompt_service.get_system_prompt.return_value = assembled

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None
    ports.request_renderer = None  # merger deterministic; no user prompt

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    ctx.project_id = "test_proj"
    ctx.cycle_id = "cyc_test"
    return ctx


async def test_handler_emits_both_artifacts_on_multi_role_merge():
    ctx = _make_merger_context()
    handler = GovernanceMergePlanHandler()

    inputs = {
        "prd": "PRD",
        "resolved_config": {"plan_authoring_contributors": ["development", "qa"]},
        "prior_outputs": {
            "lead": {
                "brief_outcome": {
                    "status": "success",
                    "yaml_content": _BRIEF_YAML,
                },
            },
            "dev": {
                "proposal_outcome": {
                    "status": "success",
                    "proposing_role": "development",
                    "yaml_content": _DEV_PROPOSAL_YAML,
                },
            },
            "qa": {
                "proposal_outcome": {
                    "status": "success",
                    "proposing_role": "qa",
                    "yaml_content": _QA_PROPOSAL_YAML,
                },
            },
        },
    }

    result = await handler.handle(ctx, inputs)
    assert result.success is True
    artifact_names = [a["name"] for a in result.outputs["artifacts"]]
    assert artifact_names == ["implementation_plan.yaml", "merge_decisions.yaml"]

    # Round-trip both artifacts
    plan = ImplementationPlan.from_yaml(result.outputs["artifacts"][0]["content"])
    decisions = MergeDecisions.from_yaml(result.outputs["artifacts"][1]["content"])
    assert len(plan.tasks) == 2
    assert decisions.authoring_mode == "multi_role"


async def test_handler_emits_interface_manifest_when_a_proposer_supplies_it():
    # SIP-0099 99.2: a proposer's outcome carrying interface_manifest_yaml makes the
    # merger emit a THIRD sibling artifact, verbatim — the merger does not validate it.
    ctx = _make_merger_context()
    handler = GovernanceMergePlanHandler()
    interface_yaml = (
        "version: 1\nkind: interface_manifest\nproject_id: group_run\n"
        "stack: fullstack_fastapi_react\n"
    )

    inputs = {
        "prd": "PRD",
        "resolved_config": {"plan_authoring_contributors": ["development", "qa"]},
        "prior_outputs": {
            "lead": {"brief_outcome": {"status": "success", "yaml_content": _BRIEF_YAML}},
            "dev": {
                "proposal_outcome": {
                    "status": "success",
                    "proposing_role": "development",
                    "yaml_content": _DEV_PROPOSAL_YAML,
                    "interface_manifest_yaml": interface_yaml,
                },
            },
            "qa": {
                "proposal_outcome": {
                    "status": "success",
                    "proposing_role": "qa",
                    "yaml_content": _QA_PROPOSAL_YAML,
                },
            },
        },
    }

    result = await handler.handle(ctx, inputs)
    assert result.success is True
    artifacts = {a["name"]: a for a in result.outputs["artifacts"]}
    assert set(artifacts) == {
        "implementation_plan.yaml",
        "merge_decisions.yaml",
        "interface_manifest.yaml",
    }
    iface = artifacts["interface_manifest.yaml"]
    assert iface["type"] == "interface_manifest"
    assert iface["content"] == interface_yaml  # carried verbatim


async def test_handler_fails_loudly_when_brief_missing():
    """The brief is mandatory upstream context. Missing brief = wiring
    bug, not a recoverable runtime condition. Surface explicitly."""
    ctx = _make_merger_context()
    handler = GovernanceMergePlanHandler()

    inputs = {
        "prd": "PRD",
        "resolved_config": {"plan_authoring_contributors": ["development", "qa"]},
        "prior_outputs": {},  # no brief
    }

    result = await handler.handle(ctx, inputs)
    assert result.success is False
    assert "plan_authoring_brief" in (result.error or "")
