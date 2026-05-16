"""Tests for SIP-0093 PR 93.2 proposer handlers.

Three handlers, three failure surfaces, one happy path each. The handlers
share a base (``_ProposeBaseHandler``), so the structural assertions
(registration, brief-id matching, RC-23 failure shape, parse retries)
test the base behavior once per concrete handler rather than testing the
base class directly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import get_all_handlers
from squadops.capabilities.handlers.planning_tasks import (
    DevelopmentProposePlanTasksHandler,
    QaProposePlanTasksHandler,
    StrategyProposePlanGuidanceHandler,
)
from squadops.cycles.plan_guidance import PlanGuidance
from squadops.cycles.proposal_failure import ProposalFailure
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


_BRIEF_YAML = """\
version: 1
brief_id: brief-test-001
objective_summary: |
  Build a simple user-CRUD API with backend persistence and a basic UI.
accepted_stack:
  frontend: "React+Vite"
  backend: "FastAPI+SQLite"
must_cover_requirements:
  - "POST /users creates a new user and returns 201"
  - "GET /users/{id} returns 404 when not found"
scope_cuts:
  - "Admin dashboards deferred to follow-up cycle"
risk_areas:
  - "auth integration"
  - "data integrity on concurrent writes"
"""


_DEV_PROPOSAL_RESPONSE = """\
Looking at the brief, here are the dev tasks:

```yaml:proposed_plan_tasks.yaml
version: 1
proposal_id: prop-dev-001
source_brief_id: brief-test-001
proposing_role: development
scope_statement: |
  Backend implementation: user model, CRUD routes.
tasks:
  - task_type: development.develop
    role: dev
    focus: "Backend user model"
    description: |
      Define the User Pydantic model with id and email fields.
    expected_artifacts:
      - "backend/models.py"
    acceptance_criteria:
      - check: field_present
        file: backend/models.py
        class_name: User
        fields: [id, email]
        severity: error
    depends_on_focus: []
  - task_type: development.develop
    role: dev
    focus: "User CRUD routes"
    description: |
      Implement POST / GET / DELETE user endpoints.
    expected_artifacts:
      - "backend/main.py"
    acceptance_criteria:
      - check: endpoint_defined
        file: backend/main.py
        methods_paths:
          - ["POST", "/users"]
          - ["GET", "/users/{id}"]
        severity: error
    depends_on_focus:
      - "dev:backend user model"
```
"""


_QA_PROPOSAL_RESPONSE = """\
```yaml:proposed_plan_tasks.yaml
version: 1
proposal_id: prop-qa-001
source_brief_id: brief-test-001
proposing_role: qa
scope_statement: |
  Test coverage for user CRUD endpoints including 404 path.
tasks:
  - task_type: qa.test
    role: qa
    focus: "User CRUD pytest suite"
    description: |
      pytest functions exercising POST, GET, DELETE, and 404 on missing id.
    expected_artifacts:
      - "backend/tests/test_users.py"
    acceptance_criteria:
      - check: regex_match
        file: backend/tests/test_users.py
        pattern: "def test_"
        count_min: 4
        severity: error
    depends_on_focus:
      - "dev:user crud routes"
```
"""


_STRATEGY_GUIDANCE_RESPONSE = """\
```yaml:plan_guidance.yaml
version: 1
guidance_id: guidance-strategy-001
source_brief_id: brief-test-001
proposing_role: strategy
priority_guidance:
  - area: backend_api
    priority: high
    rationale: "API surface is the integration anchor for this build."
must_not_skip:
  - "404 handling on GET /users/{id}"
defer_if_time_constrained:
  - "frontend polish"
```
"""


def _make_context(llm_response: str):
    """Build a minimal ExecutionContext mock with a renderer mock.

    Proposer handlers (PR 93.2) require ``request_renderer`` — no inline
    fallback (no migration baggage from older test contexts). The renderer
    mock returns a deterministic ``RenderedRequest`` so the LLM call
    receives a stable user prompt regardless of variable contents; tests
    assert on inputs via ``render.call_args`` and on outputs via the
    parsed proposal/guidance artifact.
    """
    llm = AsyncMock()
    llm.chat_stream_with_usage.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "system prompt for proposer"
    assembled.assembly_hash = "deadbeef"
    prompt_service.assemble.return_value = assembled

    renderer = AsyncMock()
    rendered = MagicMock()
    rendered.content = "user prompt (rendered)"
    rendered.template_id = "request.placeholder"
    rendered.template_version = "1"
    renderer.render.return_value = rendered

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None
    ports.request_renderer = renderer

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    ctx.project_id = "test_proj"
    ctx.cycle_id = "cyc_test"
    return ctx


def _seeded_inputs(prior_outputs_extra: dict | None = None) -> dict:
    prior_outputs = {
        "artifact_contents": {
            "plan_authoring_brief.yaml": _BRIEF_YAML,
            "planning_artifact.md": "## Plan\n\nLooks good.",
        },
    }
    if prior_outputs_extra:
        prior_outputs.update(prior_outputs_extra)
    return {
        "prd": "Build a simple user-CRUD API",
        "profile_roles": ["lead", "dev", "qa", "strat"],
        "prior_outputs": prior_outputs,
        "resolved_config": {},
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    """Each proposer handler must be registered in bootstrap so direct
    dispatch resolves it. PR 93.3's cutover only adds the steps to
    PLANNING_TASK_STEPS; registration is here in PR 93.2."""

    @pytest.mark.parametrize(
        "handler_cls,expected_roles",
        [
            (DevelopmentProposePlanTasksHandler, ("dev",)),
            (QaProposePlanTasksHandler, ("qa",)),
            (StrategyProposePlanGuidanceHandler, ("strat",)),
        ],
    )
    def test_handler_registered_with_correct_role(self, handler_cls, expected_roles):
        registered = {
            entry[0].__name__: entry[1] for entry in get_all_handlers()
        }
        assert handler_cls.__name__ in registered, (
            f"{handler_cls.__name__} not in bootstrap handler registry"
        )
        assert registered[handler_cls.__name__] == expected_roles


# ---------------------------------------------------------------------------
# Happy path: each handler produces its expected artifact for a seeded LLM response
# ---------------------------------------------------------------------------


async def test_dev_proposer_emits_parseable_proposal():
    ctx = _make_context(_DEV_PROPOSAL_RESPONSE)
    handler = DevelopmentProposePlanTasksHandler()

    result = await handler.handle(ctx, _seeded_inputs())

    assert result.success is True
    artifact = result.outputs["artifacts"][0]
    assert artifact["name"] == "proposed_plan_tasks.yaml"
    assert artifact["media_type"] == "text/yaml"
    assert artifact["type"] == "proposed_plan_tasks"

    parsed = ProposedRoleTasks.from_yaml(artifact["content"])
    assert parsed.proposing_role == "development"
    assert parsed.source_brief_id == "brief-test-001"
    assert len(parsed.tasks) == 2
    assert parsed.tasks[0].focus == "Backend user model"
    assert parsed.tasks[1].depends_on_focus == ["dev:backend user model"]


async def test_qa_proposer_emits_parseable_proposal():
    ctx = _make_context(_QA_PROPOSAL_RESPONSE)
    handler = QaProposePlanTasksHandler()

    result = await handler.handle(ctx, _seeded_inputs())

    assert result.success is True
    artifact = result.outputs["artifacts"][0]
    assert artifact["name"] == "proposed_plan_tasks.yaml"
    parsed = ProposedRoleTasks.from_yaml(artifact["content"])
    assert parsed.proposing_role == "qa"
    assert parsed.source_brief_id == "brief-test-001"
    assert parsed.tasks[0].depends_on_focus == ["dev:user crud routes"]


async def test_strategy_proposer_emits_parseable_guidance():
    ctx = _make_context(_STRATEGY_GUIDANCE_RESPONSE)
    handler = StrategyProposePlanGuidanceHandler()

    result = await handler.handle(ctx, _seeded_inputs())

    assert result.success is True
    artifact = result.outputs["artifacts"][0]
    assert artifact["name"] == "plan_guidance.yaml"
    assert artifact["type"] == "plan_guidance"

    parsed = PlanGuidance.from_yaml(artifact["content"])
    assert parsed.proposing_role == "strategy"
    assert parsed.source_brief_id == "brief-test-001"
    assert parsed.must_not_skip == ["404 handling on GET /users/{id}"]


# ---------------------------------------------------------------------------
# RC-23: structured failure record, not exception, on retry exhaustion
# ---------------------------------------------------------------------------


class TestRC23FailureRecord:
    """When a proposer can't produce a parseable artifact within the retry
    budget, it must emit a structured ProposalFailure artifact rather than
    raising. The cycle continues; the merger reads the failure record as
    'this role's proposal is missing' and produces a MissingProposal entry
    in merge_decisions.yaml accordingly."""

    @pytest.mark.parametrize(
        "handler_cls,proposer_role,failure_artifact_name",
        [
            (
                DevelopmentProposePlanTasksHandler,
                "development",
                "development_propose_plan_tasks_failure.yaml",
            ),
            (
                QaProposePlanTasksHandler,
                "qa",
                "qa_propose_plan_tasks_failure.yaml",
            ),
            (
                StrategyProposePlanGuidanceHandler,
                "strategy",
                "strategy_propose_plan_guidance_failure.yaml",
            ),
        ],
    )
    async def test_unparseable_response_emits_failure_record(
        self, handler_cls, proposer_role, failure_artifact_name
    ):
        ctx = _make_context("No fenced YAML at all here.")
        handler = handler_cls()
        inputs = _seeded_inputs()
        inputs["resolved_config"]["proposal_max_attempts"] = 1  # don't burn time retrying

        result = await handler.handle(ctx, inputs)

        # HandlerResult.success is True — the cycle keeps moving. The failure
        # is captured inside the artifact, not at the HandlerResult layer.
        assert result.success is True
        artifact = result.outputs["artifacts"][0]
        assert artifact["name"] == failure_artifact_name
        assert artifact["type"] == "proposal_failure"

        failure = ProposalFailure.from_yaml(artifact["content"])
        assert failure.proposer_role == proposer_role
        assert failure.failure_reason in {"malformed_yaml", "schema_validation_error"}
        assert failure.details  # non-empty

    @pytest.mark.parametrize(
        "handler_cls",
        [
            DevelopmentProposePlanTasksHandler,
            QaProposePlanTasksHandler,
            StrategyProposePlanGuidanceHandler,
        ],
    )
    async def test_no_exception_on_repeated_failure(self, handler_cls):
        """Multiple retries that all fail must not propagate as an exception
        — the entire point of RC-23 is that proposer failure doesn't kill
        the cycle."""
        ctx = _make_context("garbage response that won't parse")
        handler = handler_cls()
        inputs = _seeded_inputs()
        inputs["resolved_config"]["proposal_max_attempts"] = 3

        # Must not raise.
        result = await handler.handle(ctx, inputs)
        assert result.success is True
        assert result.outputs["artifacts"][0]["type"] == "proposal_failure"


# ---------------------------------------------------------------------------
# Brief-id matching (RC-22 immutability invariant at proposer layer)
# ---------------------------------------------------------------------------


class TestBriefIdMatching:
    """The merger relies on every proposal citing the same brief_id as the
    upstream brief. A mismatch indicates either a corrupted proposal or a
    proposer running against a stale brief — either way, drop it cleanly
    rather than merging a divergent worldview."""

    @pytest.mark.parametrize(
        "handler_cls,response",
        [
            (DevelopmentProposePlanTasksHandler, _DEV_PROPOSAL_RESPONSE),
            (QaProposePlanTasksHandler, _QA_PROPOSAL_RESPONSE),
            (StrategyProposePlanGuidanceHandler, _STRATEGY_GUIDANCE_RESPONSE),
        ],
    )
    async def test_brief_id_mismatch_produces_failure_record(self, handler_cls, response):
        # Tamper with the response to cite a different brief_id than the upstream.
        tampered = response.replace("brief-test-001", "brief-fake-999")
        ctx = _make_context(tampered)
        handler = handler_cls()
        inputs = _seeded_inputs()
        inputs["resolved_config"]["proposal_max_attempts"] = 1

        result = await handler.handle(ctx, inputs)
        assert result.success is True

        artifact = result.outputs["artifacts"][0]
        assert artifact["type"] == "proposal_failure"
        failure = ProposalFailure.from_yaml(artifact["content"])
        assert failure.failure_reason == "mismatched_brief_id"
        assert "brief-test-001" in failure.details
        assert "brief-fake-999" in failure.details


# ---------------------------------------------------------------------------
# Prompt registry integration (the issue #140 discipline applied to PR 93.2)
# ---------------------------------------------------------------------------


class TestPromptRegistryIntegration:
    """PR 93.2 was authored after issue #140's prompt-registry cleanup
    lesson. These tests guard against future drift back toward inline
    prompts. Each handler MUST route its user prompt through the registry
    and assemble its system prompt with the appropriate task_type
    fragment."""

    @pytest.mark.parametrize(
        "handler_cls,expected_template,expected_task_type",
        [
            (
                DevelopmentProposePlanTasksHandler,
                "request.development_propose_plan_tasks",
                "development.propose_plan_tasks",
            ),
            (
                QaProposePlanTasksHandler,
                "request.qa_propose_plan_tasks",
                "qa.propose_plan_tasks",
            ),
            (
                StrategyProposePlanGuidanceHandler,
                "request.strategy_propose_plan_guidance",
                "strategy.propose_plan_guidance",
            ),
        ],
    )
    async def test_handler_uses_registered_template_and_task_type(
        self, handler_cls, expected_template, expected_task_type
    ):
        ctx = _make_context(_DEV_PROPOSAL_RESPONSE)  # response unused for these assertions
        handler = handler_cls()

        await handler.handle(ctx, _seeded_inputs())

        ctx.ports.request_renderer.render.assert_called_once()
        template_id = ctx.ports.request_renderer.render.call_args.args[0]
        assert template_id == expected_template

        ctx.ports.prompt_service.assemble.assert_called_once_with(
            role=handler._role,
            hook="agent_start",
            task_type=expected_task_type,
        )

    async def test_brief_content_surfaced_to_template(self):
        ctx = _make_context(_DEV_PROPOSAL_RESPONSE)
        handler = DevelopmentProposePlanTasksHandler()

        await handler.handle(ctx, _seeded_inputs())

        variables = ctx.ports.request_renderer.render.call_args.args[1]
        assert "brief_content" in variables
        assert "brief_id: brief-test-001" in variables["brief_content"]
        assert variables["source_brief_id"] == "brief-test-001"
        assert variables["proposal_id"]  # non-empty

    async def test_renderer_required_no_inline_fallback(self):
        """No silent fall-through to inline construction (lesson from #140)."""
        ctx = _make_context(_DEV_PROPOSAL_RESPONSE)
        ctx.ports.request_renderer = None
        handler = DevelopmentProposePlanTasksHandler()

        result = await handler.handle(ctx, _seeded_inputs())

        # Surfaces as a structured failure rather than raising or silently
        # constructing an inline prompt.
        assert result.success is True
        artifact = result.outputs["artifacts"][0]
        assert artifact["type"] == "proposal_failure"
        failure = ProposalFailure.from_yaml(artifact["content"])
        assert failure.failure_reason == "llm_error"
        assert "request_renderer" in failure.details
