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
    # #856: two renders now — the manifest template, then the unconditional authoring
    # rules appendix. The first is the one under test.
    assert ctx.ports.request_renderer.render.call_count == 2
    call_args = ctx.ports.request_renderer.render.call_args_list[0]
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


async def test_produce_plan_filters_builder_assemble_by_squad_capability():
    """End-to-end guard for the capability filter (cyc_0024e1a0b6b5 failure).

    The plan-authoring prompt must NOT offer ``builder.assemble`` when the
    squad has no builder role — otherwise the LLM authors a builder.assemble
    task that aborts at dispatch with 'No handler for capability:
    builder.assemble', as happened on a no-builder squad (the former
    full-squad). A builder-equipped squad must still be offered it. The
    rendered template variables (which carry
    the available-task-types list and builder example) are the surface.
    """
    base = {
        "prd": "Build a simple user-CRUD API",
        "resolved_config": {
            "implementation_plan": True,
            "min_build_subtasks": 3,
            "max_build_subtasks": 15,
        },
    }

    ctx_no_builder = _make_context()
    await produce_plan(
        ctx_no_builder,
        {**base, "profile_roles": ["lead", "dev", "qa"]},
        planning_content="## Plan",
        resolved_config=base["resolved_config"],
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )
    no_builder_render = str(ctx_no_builder.ports.request_renderer.render.call_args_list[0])
    assert "builder.assemble" not in no_builder_render

    # #426: the builder role alone no longer suffices — the offer also
    # requires a configured build_profile (see the offer tests below).
    ctx_builder = _make_context()
    await produce_plan(
        ctx_builder,
        {**base, "profile_roles": ["lead", "dev", "builder", "qa"]},
        planning_content="## Plan",
        resolved_config={**base["resolved_config"], "build_profile": "python_cli_builder"},
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )
    builder_render = str(ctx_builder.ports.request_renderer.render.call_args_list[0])
    assert "builder.assemble" in builder_render


# ---------------------------------------------------------------------------
# Command-safelist enforcement at the authoring boundary (#422)
# ---------------------------------------------------------------------------

_SAFELIST_PLAN_TEMPLATE = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend"
    description: "Build the backend"
    expected_artifacts:
      - "backend/main.py"
    acceptance_criteria:
      - check: command_exit_zero
        description: "command check"
        argv: {argv}
    depends_on: []
summary:
  total_tasks: 1
"""


def test_validate_manifest_candidate_feeds_safelist_error_back():
    """A merger-authored plan with an unrunnable command must produce
    corrective error_msg (retry feedback), not a valid manifest — the live
    failure was cyc_bc325a67417d dying at evaluation on `npm test`."""
    from squadops.capabilities.handlers._plan_authoring_service import (
        _validate_manifest_candidate,
    )

    yaml_content = _SAFELIST_PLAN_TEMPLATE.format(argv='["npm", "test"]')
    manifest, error_msg = _validate_manifest_candidate(yaml_content, 1, 15, ["dev"])
    assert manifest is None
    assert "safelist" in error_msg
    assert "py_compile" in error_msg  # feedback must teach an allowed form


def test_validate_manifest_candidate_accepts_safelisted_command():
    from squadops.capabilities.handlers._plan_authoring_service import (
        _validate_manifest_candidate,
    )

    yaml_content = _SAFELIST_PLAN_TEMPLATE.format(
        argv='["python", "-m", "py_compile", "backend/main.py"]'
    )
    manifest, error_msg = _validate_manifest_candidate(yaml_content, 1, 15, ["dev"])
    assert error_msg is None
    assert manifest is not None


# ---------------------------------------------------------------------------
# #426 — the builder offer keys off config, not squad composition alone
# ---------------------------------------------------------------------------


async def _render_vars_for(profile_roles, resolved_config):
    ctx = _make_context()
    await produce_plan(
        ctx,
        {"prd": "Build it", "profile_roles": profile_roles, "resolved_config": resolved_config},
        planning_content="## Plan",
        resolved_config=resolved_config,
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )
    call = ctx.ports.request_renderer.render.call_args_list[0]
    return call.args[1]


async def test_builder_squad_without_build_profile_is_not_offered_builder_tasks():
    """#426: lite/full squads on a profile with no build_profile authored
    builder.assemble plans that generate_task_plan then refused — a
    deterministically dead plan, knowable at framing time. The offer (task
    vocabulary AND the guideline/example prose) must key off config too."""
    variables = await _render_vars_for(
        ["lead", "dev", "qa", "builder"], {"implementation_plan": True}
    )
    assert "builder.assemble" not in variables["task_types_section"]
    assert variables["builder_guideline"] == ""


async def test_builder_squad_with_build_profile_is_offered_builder_tasks():
    variables = await _render_vars_for(
        ["lead", "dev", "qa", "builder"],
        {"implementation_plan": True, "build_profile": "fullstack_fastapi_react"},
    )
    assert "builder.assemble" in variables["task_types_section"]
    assert "builder.assemble" in variables["builder_guideline"]


# ---------------------------------------------------------------------------
# #846 — the sole author receives the contract's surfaces
#
# This path authors the plan that reaches implementation whenever no
# ``plan_authoring_contributors`` are configured, which is the default for every CRP
# but ``validation-multirole``. Until #846 it was the ONLY authoring path never given
# the criteria index or the frozen-surface index: the proposers rendered both, and the
# proposers were not running.
#
# Measured on VS's Next.js re-roll (`cyc_0edb55919384`, `authoring_mode: sole_author`,
# every task `gap_filled`): 0 criteria_refs in the emitted plan, 3 frozen files claimed
# as deliverables, 8 invented paths, 3 fill slots claimed by no task.
# ---------------------------------------------------------------------------


def _rendered_prompt(ctx) -> str:
    """The user message the LLM actually saw."""
    return ctx.ports.llm.chat_stream_with_usage.call_args[0][0][1].content


async def _fake_render(template_id, variables):
    """Render each template distinguishably, so the assertions can tell them apart.

    The shared fixture returns one canned string for every template; the appendices have
    to be separable from the base prompt or "the index reached the LLM" is unfalsifiable.
    """
    out = MagicMock()
    out.template_id = template_id
    out.template_version = "1"
    if template_id == "request.governance_review_plan_manifest":
        out.content = "user prompt (rendered from request.governance_review_plan_manifest)"
    else:
        out.content = "\n\n[{}]\n{}".format(template_id, "\n".join(variables.values()))
    return out


async def test_sole_author_prompt_carries_the_criteria_and_frozen_indexes(seeded_inputs):
    """Both surfaces reach the LLM, not merely the inputs dict.

    Asserting on the message the model received is the point: the contract was reaching
    `inject_contract_inputs` correctly all along and stopping one layer short, so a test
    that checked injection would have passed while the author stayed blind.
    """
    ctx = _make_context()
    seeded_inputs = {
        **seeded_inputs,
        "contract_criteria_index": "- app/api/runs/route.ts: bind vc-runs (frontend_compiles)",
        "frozen_surface_index": "- `lib/store.ts`\n- `package.json`",
    }

    ctx.ports.request_renderer.render.side_effect = None
    ctx.ports.request_renderer.render.side_effect = _fake_render

    result = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="planning",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test",
        chat_kwargs={},
    )
    assert result is not None

    prompt = _rendered_prompt(ctx)
    assert "app/api/runs/route.ts" in prompt, "the fill-slot criteria index never arrived"
    assert "lib/store.ts" in prompt, "the frozen-surface index never arrived"


async def test_author_mode_prompt_is_unchanged_without_a_contract(seeded_inputs):
    """No contract, no appendices — author-mode cycles stay byte-identical.

    The polarity guard for the fix above: appending unconditionally would have changed
    every contract-less cycle's prompt, which is the class of silent behavior change the
    plan-context golden exists to catch.
    """
    ctx = _make_context()
    ctx.ports.request_renderer.render.side_effect = _fake_render

    await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="planning",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test",
        chat_kwargs={},
    )

    prompt = _rendered_prompt(ctx)
    # #856 made the authoring-rules appendix unconditional, so exact equality with the base
    # prompt is no longer the right assertion — what this guards is that no CONTRACT
    # appendix appears when there is no contract.
    assert "request.plan_bind_criteria_appendix" not in prompt
    assert "request.plan_frozen_surface_appendix" not in prompt


async def test_an_empty_index_is_not_rendered_as_an_empty_section(seeded_inputs):
    """A present-but-empty key must behave like an absent one.

    `frozen_surface_index_lines` returns [] for a stack whose skeleton is all fill slots,
    and `"\\n".join([])` is `""`. Rendering the appendix's prose over no data would tell
    an author "these files are frozen:" followed by nothing.
    """
    ctx = _make_context()
    ctx.ports.request_renderer.render.side_effect = _fake_render

    await produce_plan(
        ctx,
        {**seeded_inputs, "contract_criteria_index": "", "frozen_surface_index": ""},
        planning_content="planning",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test",
        chat_kwargs={},
    )

    prompt = _rendered_prompt(ctx)
    assert "request.plan_bind_criteria_appendix" not in prompt
    assert "request.plan_frozen_surface_appendix" not in prompt


# ---------------------------------------------------------------------------
# #856 — the sole author is shown the rules its plan is validated against
# ---------------------------------------------------------------------------


async def test_sole_author_prompt_carries_the_plan_authoring_rules(seeded_inputs):
    """VS roll 5 (`cyc_d430f25fd01d`) was rejected by a rule the author never saw.

    Its `qa.test` task declared `expected_artifacts: ['__tests__/qa_execution_report.md']`
    — a report, no test file — and `validate_check_applicability` refused it. The rule
    covering that case, `qa-tests-must-be-discoverable`, states the correct form in its own
    second sentence. `_authoring_rules_section` was rendered by the proposers and the brief
    author and by nothing on this path, which is the path that writes the plan on every CRP
    except `validation-multirole`.

    Asserted on the message the LLM received, not on the render call: the question the
    failure turned on is whether the rules reached the model, and a call-count assertion
    passes against a render whose output is dropped.
    """
    ctx = _make_context()
    ctx.ports.request_renderer.render.side_effect = _fake_render

    await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="planning",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test",
        chat_kwargs={},
    )

    prompt = _rendered_prompt(ctx)
    assert "request.plan_authoring_rules_appendix" in prompt, (
        "the sole author must be shown the plan-shape rules its output is validated "
        "against — the validator knowing a rule the author never sees is #686's defect"
    )


async def test_the_rules_precede_the_cycle_specific_surfaces(seeded_inputs):
    """Ordering is deliberate, not incidental: general rules, then this cycle's contract.

    Both are appended to the same prompt, and a reader that meets the fill-slot list before
    the rule about what a qa task may declare has to hold the specifics without the frame.
    Pinned so a later append does not silently invert it.
    """
    ctx = _make_context()
    ctx.ports.request_renderer.render.side_effect = _fake_render

    await produce_plan(
        ctx,
        {**seeded_inputs, "contract_criteria_index": "- app/api/runs/route.ts: bind vc-runs"},
        planning_content="planning",
        resolved_config=seeded_inputs["resolved_config"],
        role="lead",
        handler_name="test",
        chat_kwargs={},
    )

    prompt = _rendered_prompt(ctx)
    assert prompt.index("request.plan_authoring_rules_appendix") < prompt.index(
        "request.plan_bind_criteria_appendix"
    )


async def test_builder_guideline_and_example_carry_the_profile_floor():
    """#890: rolls 15/16 both reproduced the builder example's
    expected_artifacts verbatim — qa_handoff.md only, no Dockerfile — so the
    example must SHOW the profile's required-files floor (the same list
    validate_builder_floor rejects on), not hedge it in description prose."""
    variables = await _render_vars_for(
        ["lead", "dev", "qa", "builder"],
        {"implementation_plan": True, "build_profile": "nextjs_ts"},
    )

    assert "Dockerfile, qa_handoff.md" in variables["builder_guideline"]
    assert "floor" in variables["builder_guideline"]
    assert '- "Dockerfile"' in variables["builder_example"]
    assert '- "qa_handoff.md"' in variables["builder_example"]


async def test_unknown_profile_keeps_generic_example():
    """A profile the registry cannot resolve renders no floor line and the
    example falls back to the pre-#890 qa_handoff.md shape — the offer gate
    and #426's nets own the misconfiguration, not this surface."""
    variables = await _render_vars_for(
        ["lead", "dev", "qa", "builder"],
        {"implementation_plan": True, "build_profile": "no_such_profile"},
    )

    assert "floor" not in variables["builder_guideline"]
    assert '- "qa_handoff.md"' in variables["builder_example"]
    assert '- "Dockerfile"' not in variables["builder_example"]


# ---------------------------------------------------------------------------
# #1172 — the manifest loop is observable
#
# This path had no telemetry: merge_plan called the LLM and emitted nothing, so
# the capability that gates whether a cycle can start building was the one
# capability LangFuse could not see. Diagnosing an Atlas failure on 2026-08-29
# required the engine's own request dump and container logs, neither of which
# survives a rebuild — and the same failure on the Ollama arm would have left no
# evidence at all.
# ---------------------------------------------------------------------------


def _recording_context(responses: list[str]):
    """A context whose LLM returns each seeded response in turn and whose
    observability port captures the records it is handed."""
    ctx = _make_context()
    captured: list = []
    obs = MagicMock()
    obs.record_generation.side_effect = lambda _c, record, _l: captured.append(record)
    ctx.ports.llm_observability = obs
    ctx.correlation_context = MagicMock()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        side_effect=[
            MagicMock(
                content=body,
                completion_tokens=100 + i,
                prompt_tokens=900 + i,
                total_tokens=1000 + i,
                tokens_per_second=12.5,
            )
            for i, body in enumerate(responses)
        ]
    )
    return ctx, captured


async def test_every_manifest_attempt_is_recorded_with_its_verdict(seeded_inputs):
    """One record per attempt, each carrying which attempt it was and what the
    validator said — not a roll-up. A roll-up hides the repair loop, and the
    repair loop is what a non-converging merge_plan consists of: eight attempts
    behind a record that shows one task."""
    ctx, captured = _recording_context(["no fenced block here at all", _SEEDED_LLM_RESPONSE])

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config={**seeded_inputs["resolved_config"], "manifest_max_attempts": 2},
        role="lead",
        handler_name="test_harness",
        chat_kwargs={"model": "test-model", "reasoning": "high"},
    )

    assert artifact is not None, "the second attempt seeds a valid manifest"
    assert [r.attempt for r in captured] == [1, 2], "one record per attempt, in order"
    assert captured[0].outcome != "accepted", "the failed attempt records the rejection"
    assert captured[1].outcome == "accepted"
    assert captured[0].outcome, "the validator's reason is the record's outcome, not a bare flag"


async def test_recorded_attempt_carries_usage_and_reasoning(seeded_inputs):
    """The record is built through the seam, so token usage and the declared
    reasoning level travel with it — the two things #1171 lost and the two that
    make a budget-exhaustion failure legible after the fact."""
    ctx, captured = _recording_context([_SEEDED_LLM_RESPONSE])

    await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config={**seeded_inputs["resolved_config"], "manifest_max_attempts": 1},
        role="lead",
        handler_name="test_harness",
        chat_kwargs={"model": "test-model", "reasoning": "high"},
    )

    assert len(captured) == 1
    record = captured[0]
    assert record.completion_tokens == 100
    assert record.tokens_per_second == 12.5
    assert record.reasoning == "high"
    assert record.model == "test-model"


async def test_authoring_survives_a_failing_observability_port(seeded_inputs):
    """Observability is best-effort: a recorder that raises must not fail a run
    that produced a valid plan."""
    ctx, _ = _recording_context([_SEEDED_LLM_RESPONSE])
    ctx.ports.llm_observability.record_generation.side_effect = RuntimeError("langfuse down")

    artifact = await produce_plan(
        ctx,
        seeded_inputs,
        planning_content="## Plan",
        resolved_config={**seeded_inputs["resolved_config"], "manifest_max_attempts": 1},
        role="lead",
        handler_name="test_harness",
        chat_kwargs={},
    )

    assert artifact is not None, "a broken recorder must not lose a valid plan"
