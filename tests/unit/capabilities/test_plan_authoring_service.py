"""Tests for ``PlanAuthoringService.produce_plan`` (SIP-0093 PR 93.0).

The service is the function-style extraction of ``_produce_plan`` from
``GovernanceReviewPlanHandler``. PR 93.0's gate is that this extraction is
byte-identical to the inline behavior given the same seeded LLM responses;
the cutover PR (93.3) will make the merger the only consumer.

Two regression anchors live here:

1. **Verbatim-equivalence** — ``produce_plan(...)`` returns the expected
   manifest artifact for a seeded LLM response, with the parsed
   ``ImplementationPlan`` matching the seeded YAML.
2. **PR-93.0 side-effect absence** — running ``GovernanceReviewPlanHandler``
   end-to-end produces ``planning_artifact.md`` plus ``implementation_plan.yaml``
   only; no ``plan_authoring_brief.yaml``, no ``proposed_plan_tasks.yaml``,
   no ``plan_guidance.yaml``, no ``merge_decisions.yaml``. Confirms the
   service extraction didn't accidentally wire SIP-0093 artifacts into the
   pre-cutover route.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers._plan_authoring_service import produce_plan
from squadops.capabilities.handlers.planning_tasks import GovernanceReviewPlanHandler
from squadops.cycles.implementation_plan import ImplementationPlan

pytestmark = [pytest.mark.domain_capabilities]


# A valid implementation_plan.yaml payload the seeded LLM returns. Three
# tasks (within the default 3-15 bound) and roles within the dev/qa profile.
_SEEDED_MANIFEST_YAML = """\
version: 1
project_id: test_proj
cycle_id: cyc_test
prd_hash: deadbeef
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: |
      Define User dataclass.
    expected_artifacts:
      - "backend/models.py"
    acceptance_criteria:
      - "User class with id and email"
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend API"
    description: |
      Wire FastAPI routes.
    expected_artifacts:
      - "backend/main.py"
    acceptance_criteria:
      - "GET /users returns list"
    depends_on: [0]
  - task_index: 2
    task_type: qa.test
    role: qa
    focus: "Backend tests"
    description: |
      Cover the routes.
    expected_artifacts:
      - "tests/test_backend.py"
    acceptance_criteria:
      - "Three test functions"
    depends_on: [1]
summary:
  total_dev_tasks: 2
  total_qa_tasks: 1
  total_tasks: 3
  estimated_layers: [backend, test]
"""

_SEEDED_LLM_RESPONSE = (
    "Here's the manifest:\n\n```yaml:implementation_plan.yaml\n" + _SEEDED_MANIFEST_YAML + "```\n"
)


def _make_context(llm_response: str = _SEEDED_LLM_RESPONSE):
    """Build a minimal ExecutionContext mock matching the planning-handler tests' shape.

    The renderer mock returns a ``RenderedRequest`` whose content is a
    deterministic stand-in for the registered manifest template. The actual
    rendered bytes don't matter for these tests — the LLM mock returns the
    seeded response regardless of user prompt — but the call must succeed
    and surface ``template_id`` for downstream observability.
    """
    llm = AsyncMock()
    llm.chat_stream_with_usage.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "system prompt"
    prompt_service.assemble.return_value = assembled
    prompt_service.get_system_prompt.return_value = assembled

    renderer = AsyncMock()
    rendered = MagicMock()
    rendered.content = "user prompt (rendered from request.governance_review_plan_manifest)"
    rendered.template_id = "request.governance_review_plan_manifest"
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


@pytest.fixture()
def seeded_inputs():
    return {
        "prd": "Build a simple user-CRUD API",
        "profile_roles": ["lead", "dev", "qa"],
        "resolved_config": {
            "implementation_plan": True,
            "min_build_subtasks": 3,
            "max_build_subtasks": 15,
        },
    }


# ---------------------------------------------------------------------------
# Parsed-equivalence regression anchor (issue #140)
#
# PR 93.0 originally claimed verbatim equivalence on the assembled prompt
# bytes. Issue #140 / SIP-0084 cleanup externalized the manifest user prompt
# to a registered template and switched the system prompt to a
# ``task_type.governance.review_plan_manifest`` fragment — so the assembled
# bytes intentionally changed. The regression anchor shifts from
# *verbatim* (same bytes in/out) to *parsed* (same seeded LLM response
# yields the same parsed ``ImplementationPlan`` shape).
# ---------------------------------------------------------------------------


async def test_produce_plan_returns_parseable_manifest_artifact(seeded_inputs):
    """The service produces an ``implementation_plan.yaml`` artifact whose
    content parses back to the seeded ``ImplementationPlan`` shape.

    Parsed-equivalence anchor: seeded LLM response → identical parsed plan.
    The assembled prompt bytes are no longer the regression surface."""
    ctx = _make_context()

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan\n\nLooks good.",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is not None, "service must return an artifact for a valid seeded response"
    assert artifact["name"] == "implementation_plan.yaml"
    assert artifact["media_type"] == "text/yaml"
    assert artifact["type"] == "control_implementation_plan"

    parsed = ImplementationPlan.from_yaml(artifact["content"])
    assert len(parsed.tasks) == 3
    assert [t.task_type for t in parsed.tasks] == [
        "development.develop",
        "development.develop",
        "qa.test",
    ]
    assert [t.role for t in parsed.tasks] == ["dev", "dev", "qa"]
    assert parsed.tasks[2].depends_on == [1]


async def test_produce_plan_authoritative_identifiers_overwrite_seeded_values(
    seeded_inputs,
):
    """Issue #109 invariant: even if the LLM emits fabricated identifiers,
    the service rewrites project_id/cycle_id/prd_hash with authoritative
    context values. Tests the rewrite happens through the extracted path."""
    fabricated = _SEEDED_LLM_RESPONSE.replace(
        "project_id: test_proj", "project_id: fake_proj"
    ).replace("cycle_id: cyc_test", "cycle_id: cyc_fake")

    ctx = _make_context(llm_response=fabricated)

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is not None
    parsed = ImplementationPlan.from_yaml(artifact["content"])
    assert parsed.project_id == "test_proj"
    assert parsed.cycle_id == "cyc_test"


async def test_produce_plan_returns_none_when_llm_response_unparseable(seeded_inputs):
    """Graceful fallback (RC-4): when the LLM repeatedly produces unusable
    output, ``produce_plan`` returns ``None`` rather than raising."""
    ctx = _make_context(llm_response="No fenced YAML at all here.")

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config={
            **seeded_inputs["resolved_config"],
            "manifest_max_attempts": 1,  # don't waste time retrying
        },
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is None


async def test_produce_plan_returns_none_when_llm_call_raises(seeded_inputs):
    """LLM-level exceptions are caught and exhaust the retry budget into a
    graceful ``None`` (cycles continue with static task steps)."""
    ctx = _make_context()
    ctx.ports.llm.chat_stream_with_usage.side_effect = RuntimeError("network down")

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config={
            **seeded_inputs["resolved_config"],
            "manifest_max_attempts": 1,
        },
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is None


# ---------------------------------------------------------------------------
# Cutover anchor (SIP-0093 PR 93.3) — review_plan no longer authors the plan
# ---------------------------------------------------------------------------


async def test_governance_review_plan_emits_only_planning_artifact_post_cutover():
    """``GovernanceReviewPlanHandler.handle()`` emits **only** the planning
    artifact after the SIP-0093 PR 93.3 cutover.

    Before 93.3: the handler emitted both ``planning_artifact.md`` and
    ``implementation_plan.yaml`` (the latter via the inline
    ``_produce_plan`` method, since removed).

    After 93.3: the merger (``governance.merge_plan``) runs upstream of
    review_plan and emits both ``implementation_plan.yaml`` and
    ``merge_decisions.yaml``. The review handler is sign-off only — its
    artifact is just the consolidated planning narrative with frontmatter.

    This test was the PR-93.0 side-effect-absence anchor; in 93.3 it
    becomes the cutover regression anchor. If a future PR reintroduces
    implementation_plan.yaml here, the cutover broke.
    """
    planning_artifact = "---\nreadiness: go\nsufficiency_score: 4\n---\n\n## Plan\n\nLooks good.\n"
    ctx = _make_context()
    ctx.ports.llm.chat_stream_with_usage.side_effect = [
        MagicMock(content=planning_artifact),
    ]

    handler = GovernanceReviewPlanHandler()
    result = await handler.handle(
        ctx,
        {
            "prd": "Build user CRUD",
            "profile_roles": ["lead", "dev", "qa"],
            "prior_outputs": {"data": "...", "strat": "..."},
            "resolved_config": {
                # implementation_plan flag is now ignored — the merger
                # always runs. Setting it does NOT cause this handler to
                # author a plan.
                "implementation_plan": True,
            },
        },
    )

    assert result.success is True
    artifact_names = [a["name"] for a in result.outputs["artifacts"]]
    assert artifact_names == ["planning_artifact.md"], (
        f"Cutover regression: review_plan emitted {artifact_names!r}. "
        "After SIP-0093 PR 93.3 it must emit only planning_artifact.md; "
        "implementation_plan.yaml comes from governance.merge_plan upstream."
    )
    # Only one LLM call (the planning-artifact synthesis). The pre-93.3
    # path made a second call for manifest authoring.
    assert ctx.ports.llm.chat_stream_with_usage.await_count == 1
    # The merger's artifacts come from upstream — never from this handler.
    upstream_only = {
        "plan_authoring_brief.yaml",
        "proposed_plan_tasks.yaml",
        "plan_guidance.yaml",
        "merge_decisions.yaml",
        "implementation_plan.yaml",  # now upstream too
    }
    assert upstream_only.isdisjoint(artifact_names), (
        f"Cutover regression: review_plan emitted an upstream artifact; "
        f"found: {set(artifact_names) & upstream_only}"
    )


# ---------------------------------------------------------------------------
# Issue #140 — SIP-0084 prompt-registry integration assertions
# ---------------------------------------------------------------------------


async def test_produce_plan_renders_manifest_template(seeded_inputs):
    """Regression anchor for issue #140 F1: the manifest user prompt MUST be
    sourced from the registered ``request.governance_review_plan_manifest``
    template. If a future refactor reintroduces an inline f-string, the
    renderer mock is never called and this test fails loudly."""
    ctx = _make_context()

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is not None
    ctx.ports.request_renderer.render.assert_called_once()
    call_args = ctx.ports.request_renderer.render.call_args
    assert call_args.args[0] == "request.governance_review_plan_manifest"

    variables = call_args.args[1]
    # Required variables surface from the call-site, not from the renderer's
    # template parsing — this guards against silent drops if the template
    # changes its required surface.
    for required in (
        "prd",
        "planning_content",
        "typed_acceptance_section",
        "prd_coverage_discipline",
        "project_id",
        "cycle_id",
        "prd_hash",
        "total_tasks_expr",
    ):
        assert required in variables, f"renderer call missing required variable: {required}"

    # Identifiers must flow through verbatim — issue #109 invariant preserved
    # through the registry path.
    assert variables["project_id"] == "test_proj"
    assert variables["cycle_id"] == "cyc_test"


async def test_produce_plan_assembles_system_prompt_with_task_type(seeded_inputs):
    """Regression anchor for issue #140 F2: the manifest LLM call's system
    prompt MUST go through ``prompt_service.assemble(...)`` with the
    ``governance.review_plan_manifest`` task_type fragment, not
    ``get_system_prompt(role)`` which strips the task-type layer."""
    ctx = _make_context()

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is not None
    ctx.ports.prompt_service.assemble.assert_called_once_with(
        role="lead",
        hook="agent_start",
        task_type="governance.review_plan_manifest",
    )
    ctx.ports.prompt_service.get_system_prompt.assert_not_called()


async def test_produce_plan_inline_fallback_when_renderer_absent(seeded_inputs):
    """SIP-0084 migration accommodation: when ``request_renderer`` is not
    injected on the context, the service falls back to constructing the
    user prompt inline. The fallback's content is kept in sync with the
    registered template at
    ``src/squadops/prompts/request_templates/request.governance_review_plan_manifest.md``.

    The fallback exists only because the broader planning-handler test
    suite uses ``request_renderer = None``. Production cycles always inject
    a renderer; when those test contexts migrate to renderer mocks, the
    fallback can be removed.
    """
    ctx = _make_context()
    ctx.ports.request_renderer = None  # exercise the fallback path

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    # The fallback still produces a parseable manifest. This is the contract
    # the broader test suite relies on.
    assert artifact is not None
    assert artifact["name"] == "implementation_plan.yaml"
    parsed = ImplementationPlan.from_yaml(artifact["content"])
    assert len(parsed.tasks) == 3

    # The inline path must still inspect the user prompt for content that
    # downstream tests depend on (PRD coverage discipline section).
    call_args = ctx.ports.llm.chat_stream_with_usage.call_args
    messages = call_args.args[0]
    user_prompt = next(m.content for m in messages if m.role == "user")
    assert "## PRD" in user_prompt
    assert "implementation_plan.yaml" in user_prompt
