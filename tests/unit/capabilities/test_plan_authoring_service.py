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
    """Build a minimal ExecutionContext mock matching the planning-handler tests' shape."""
    llm = AsyncMock()
    llm.chat_stream_with_usage.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    prompt_service = MagicMock()
    assembled = MagicMock()
    assembled.content = "system prompt"
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
# Verbatim-equivalence regression anchor
# ---------------------------------------------------------------------------


async def test_produce_plan_returns_parseable_manifest_artifact(seeded_inputs):
    """The service produces an ``implementation_plan.yaml`` artifact whose
    content parses back to the seeded ``ImplementationPlan`` shape."""
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
# PR 93.0 side-effect absence — the still-active governance.review_plan path
# must NOT silently emit SIP-0093 artifacts
# ---------------------------------------------------------------------------


async def test_governance_review_plan_emits_only_planning_and_manifest_artifacts():
    """``GovernanceReviewPlanHandler.handle()`` produces exactly two
    artifacts: ``planning_artifact.md`` and ``implementation_plan.yaml``.
    No SIP-0093 brief / proposals / guidance / merge_decisions leak into
    the pre-cutover route."""
    planning_artifact = "---\nreadiness: go\nsufficiency_score: 4\n---\n\n## Plan\n\nLooks good.\n"
    # Two LLM calls happen: first returns the planning artifact, second
    # returns the manifest. Use side_effect to script them in order.
    ctx = _make_context()
    ctx.ports.llm.chat_stream_with_usage.side_effect = [
        MagicMock(content=planning_artifact),
        MagicMock(content=_SEEDED_LLM_RESPONSE),
    ]

    handler = GovernanceReviewPlanHandler()
    result = await handler.handle(
        ctx,
        {
            "prd": "Build user CRUD",
            "profile_roles": ["lead", "dev", "qa"],
            "prior_outputs": {"data": "...", "strat": "..."},
            "resolved_config": {
                "implementation_plan": True,
                "min_build_subtasks": 3,
                "max_build_subtasks": 15,
            },
        },
    )

    assert result.success is True
    artifact_names = [a["name"] for a in result.outputs["artifacts"]]
    assert artifact_names == ["planning_artifact.md", "implementation_plan.yaml"]
    # Explicit absence assertion — none of the SIP-0093 artifacts should leak.
    forbidden_in_pr_93_0 = {
        "plan_authoring_brief.yaml",
        "proposed_plan_tasks.yaml",
        "plan_guidance.yaml",
        "merge_decisions.yaml",
    }
    assert forbidden_in_pr_93_0.isdisjoint(artifact_names), (
        f"Pre-cutover governance.review_plan must not emit SIP-0093 artifacts; "
        f"found: {set(artifact_names) & forbidden_in_pr_93_0}"
    )
