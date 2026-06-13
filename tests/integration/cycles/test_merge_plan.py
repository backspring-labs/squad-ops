"""SIP-0093 PR 93.3 integration: the merger as the cutover anchor.

Per SIP-0093 §10, **the single most important integration test** is:
"Eve proposes a QA task Neo omitted; merged plan includes it." If this
can't be reproduced, SIP-0093 isn't done. This file lives at the
integration boundary because the assertion crosses three handlers
(brief, dev proposer, qa proposer, merger) plus the merger's
deterministic-merge code path.

Each test runs handlers directly with seeded prior_outputs rather than
the full executor — that keeps the test independent of the
dispatched_flow_executor's pre-resolver wiring (which lives in a
separate adapter and would broaden this PR's blast radius). PR 93.4
covers the gate-package end-to-end with the real executor wiring.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers._plan_merger import merge_proposals
from squadops.capabilities.handlers.planning_tasks import GovernanceMergePlanHandler
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.merge_decisions import MergeDecisions
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

pytestmark = [pytest.mark.integration, pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Scenario fixtures: brief lists "duplicate-join 409 handling" in
# must_cover_requirements; Neo's proposal IMPLEMENTS the route but omits a
# qa task for the 409 path; Eve's proposal FILLS that gap.
# ---------------------------------------------------------------------------


_BRIEF_YAML = """\
version: 1
brief_id: brief-eve-test-001
objective_summary: |
  User-CRUD with run-join endpoint that handles duplicate-join 409.
accepted_stack:
  backend: "FastAPI"
must_cover_requirements:
  - "POST /runs/{id}/join must return 409 on duplicate join from the same user"
  - "GET /runs/{id} returns the run state including current participants"
scope_cuts: []
risk_areas:
  - "duplicate-join concurrency"
"""


# Neo proposes implementation, but does NOT include any qa.test task that
# verifies the 409 path. The brief's must_cover_requirements is unmet on
# the verification side by dev alone.
_DEV_PROPOSAL_YAML = """\
version: 1
proposal_id: prop-dev-eve-test
source_brief_id: brief-eve-test-001
proposing_role: development
scope_statement: |
  Backend implementation of run-join and run-read endpoints.
tasks:
  - task_type: development.develop
    role: dev
    focus: "run join endpoint"
    description: |
      Implement POST /runs/{id}/join — handles duplicate-join with 409.
    expected_artifacts:
      - "backend/routes.py"
    acceptance_criteria:
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths:
          - ["POST", "/runs/{id}/join"]
        severity: error
    depends_on_focus: []
  - task_type: development.develop
    role: dev
    focus: "run read endpoint"
    description: |
      Implement GET /runs/{id}.
    expected_artifacts:
      - "backend/routes.py"
    acceptance_criteria:
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths:
          - ["GET", "/runs/{id}"]
        severity: error
    depends_on_focus: []
"""


# Eve catches the gap. Her qa.test for the 409 path is the task Neo omitted.
_QA_PROPOSAL_YAML = """\
version: 1
proposal_id: prop-qa-eve-test
source_brief_id: brief-eve-test-001
proposing_role: qa
scope_statement: |
  Test coverage including the 409 path the brief flagged as
  must_cover_requirements.
tasks:
  - task_type: qa.test
    role: qa
    focus: "run join 409 tests"
    description: |
      Pytest functions verifying POST /runs/{id}/join returns 409 on
      duplicate-join from the same user.
    expected_artifacts:
      - "backend/tests/test_run_join.py"
    acceptance_criteria:
      - check: regex_match
        file: backend/tests/test_run_join.py
        pattern: "status_code\\\\s*=\\\\s*409"
        count_min: 1
        severity: error
    depends_on_focus:
      - "dev:run join endpoint"
  - task_type: qa.test
    role: qa
    focus: "run read tests"
    description: |
      Pytest functions verifying GET /runs/{id}.
    expected_artifacts:
      - "backend/tests/test_run_read.py"
    acceptance_criteria:
      - check: regex_match
        file: backend/tests/test_run_read.py
        pattern: "def test_"
        count_min: 1
        severity: error
    depends_on_focus:
      - "dev:run read endpoint"
"""


# ---------------------------------------------------------------------------
# The Eve test (SIP-0093 §10 required gate criterion)
# ---------------------------------------------------------------------------


def test_eve_proposes_qa_task_neo_omitted_merged_plan_includes_it():
    """The single most important SIP-0093 integration test.

    Brief lists duplicate-join 409 handling in must_cover_requirements.
    Neo's proposal implements the endpoint but contributes NO qa task
    verifying the 409 path. Eve's proposal includes the qa task that
    fills the gap.

    Assertion: the merged canonical plan contains Eve's qa task,
    correctly wired to depend on Neo's implementation task. If this
    fails, the merger is silently dropping QA-domain contributions —
    which is the entire reason multi-role authoring exists.
    """
    brief = PlanAuthoringBrief.from_yaml(_BRIEF_YAML)
    dev_proposal = ProposedRoleTasks.from_yaml(_DEV_PROPOSAL_YAML)
    qa_proposal = ProposedRoleTasks.from_yaml(_QA_PROPOSAL_YAML)

    plan, decisions = merge_proposals(
        brief=brief,
        dev_proposal=dev_proposal,
        qa_proposal=qa_proposal,
        strategy_guidance=None,
        project_id="proj_eve_test",
        cycle_id="cyc_eve_test",
        prd_hash="eve_hash",
        configured_contributors=["development", "qa"],
        missing_proposals=[],
    )

    # ── Eve's qa task must be in the canonical plan ──────────────────────
    qa_join_focuses = [
        t.focus
        for t in plan.tasks
        if t.task_type == "qa.test" and "join" in t.focus.lower() and "409" in t.description
    ]
    assert qa_join_focuses == ["run join 409 tests"], (
        f"Eve's qa task for the 409 path was dropped during merge. "
        f"Canonical plan qa.test foci: "
        f"{[t.focus for t in plan.tasks if t.task_type == 'qa.test']!r}. "
        "This breaks SIP-0093's gap-catching invariant — multi-role "
        "authoring's central value proposition."
    )

    # ── Eve's qa task's dependency on Neo's dev task must resolve ────────
    eve_qa_task = next(t for t in plan.tasks if t.focus == "run join 409 tests")
    neo_dev_task = next(t for t in plan.tasks if t.focus == "run join endpoint")
    assert neo_dev_task.task_index in eve_qa_task.depends_on, (
        f"Eve's qa task ({eve_qa_task.task_index}) depends on a key "
        f"that should resolve to Neo's dev task ({neo_dev_task.task_index}), "
        f"but depends_on={eve_qa_task.depends_on}"
    )

    # ── merge_decisions records both proposals contributed ───────────────
    assert decisions.authoring_mode == "multi_role"
    assert decisions.proposal_completeness == "complete"
    proposed_by_per_task = [ct.proposed_by for ct in decisions.canonical_tasks]
    assert ["development"] in proposed_by_per_task
    assert ["qa"] in proposed_by_per_task

    # ── operator gets a clean plan: no missing-role warning ──────────────
    assert "warning" not in decisions.operator_notes.lower()


# ---------------------------------------------------------------------------
# Full framing-phase end-to-end via merger handler (no LLM round-trips —
# tests the merger's prior_outputs consumption and HandlerResult shape)
# ---------------------------------------------------------------------------


def _make_merger_ctx():
    llm = AsyncMock()
    llm.default_model = "test-model"
    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "(unused)"
    prompt_service.assemble.return_value = assembled
    prompt_service.get_system_prompt.return_value = assembled

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None
    ports.request_renderer = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    ctx.project_id = "proj_eve_test"
    ctx.cycle_id = "cyc_eve_test"
    return ctx


async def test_merger_handler_end_to_end_with_seeded_prior_outputs():
    """Merger handler reads brief + proposals from prior_outputs and
    emits both artifacts. The shape of prior_outputs here matches what
    the cycle executor builds post-cutover: each role's outputs include
    a non-artifacts payload key the merger consumes."""
    ctx = _make_merger_ctx()
    handler = GovernanceMergePlanHandler()

    inputs = {
        "prd": "Build run-join with 409 handling.",
        "resolved_config": {"plan_authoring_contributors": ["development", "qa"]},
        "prior_outputs": {
            "lead": {
                "brief_outcome": {"status": "success", "yaml_content": _BRIEF_YAML},
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

    plan = ImplementationPlan.from_yaml(result.outputs["artifacts"][0]["content"])
    decisions = MergeDecisions.from_yaml(result.outputs["artifacts"][1]["content"])

    # The Eve assertion at the handler level
    qa_focuses = [t.focus for t in plan.tasks if t.task_type == "qa.test"]
    assert "run join 409 tests" in qa_focuses
    assert decisions.authoring_mode == "multi_role"


# ---------------------------------------------------------------------------
# Cutover regression: GovernanceReviewPlanHandler no longer authors plans
# ---------------------------------------------------------------------------


def test_review_plan_handler_no_longer_calls_plan_authoring_service():
    """Cutover regression. Per the plan doc: 'verify the inline _produce_plan
    invocation in GovernanceReviewPlanHandler is gone (handler does not
    call PlanAuthoringService anywhere in its body after this PR)'.

    Inspecting the source rather than runtime behavior is the cleanest
    guard against regression — a future PR that reintroduces an inline
    plan-authoring call in this handler fails this test immediately."""
    import inspect

    from squadops.capabilities.handlers import planning_tasks
    from squadops.capabilities.handlers.planning_tasks import (
        GovernanceReviewPlanHandler,
    )

    handler_source = inspect.getsource(GovernanceReviewPlanHandler)
    assert "PlanAuthoringService" not in handler_source, (
        "GovernanceReviewPlanHandler reintroduced PlanAuthoringService — "
        "cutover regression. After SIP-0093 PR 93.3, plan authoring lives "
        "in the merger; this handler is sign-off only."
    )
    assert "produce_plan(" not in handler_source, (
        "GovernanceReviewPlanHandler reintroduced an inline produce_plan "
        "call — cutover regression."
    )
    # The handler's _produce_plan method itself must be gone (not just unused)
    assert not hasattr(GovernanceReviewPlanHandler, "_produce_plan"), (
        "GovernanceReviewPlanHandler._produce_plan should be removed by "
        "the cutover. Stale method indicates an incomplete refactor."
    )

    # The merger handler should be importable and importable handlers
    # should include it
    assert hasattr(planning_tasks, "GovernanceMergePlanHandler"), (
        "GovernanceMergePlanHandler not exported — cutover incomplete."
    )
