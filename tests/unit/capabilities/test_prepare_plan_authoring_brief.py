"""Tests for ``GovernancePreparePlanAuthoringBriefHandler`` (SIP-0093 PR 93.0).

The handler runs an LLM call with ``retry_yaml_call`` (mirroring the proposer
handlers): each attempt is fence-stripped before ``PlanAuthoringBrief.from_yaml``
validates it. These tests exercise the success path, the fence-stripping that
production LLMs require, retry-then-succeed, and exhaustion failure modes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS
from squadops.capabilities.handlers.planning_tasks import (
    GovernancePreparePlanAuthoringBriefHandler,
)
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief

pytestmark = [pytest.mark.domain_capabilities]


_VALID_BRIEF_YAML = """\
version: 1
brief_id: br_seeded_001
objective_summary: |
  Build a small FastAPI service exposing user CRUD with persistence
  via in-memory repository.
accepted_stack:
  language: python
  framework: fastapi
must_cover_requirements:
  - "5 user CRUD endpoints"
  - "Duplicate-create returns 409"
scope_cuts:
  - "No real auth"
risk_areas:
  - "Concurrent create/delete races"
"""

# Production-shape LLM response: YAML inside a typed fence. This is the form
# qwen3:27b actually emits (and the form that broke the cycle before the
# retry/fence-strip wiring).
_VALID_BRIEF_FENCED_RESPONSE = (
    "Here's the brief.\n\n"
    "```yaml:plan_authoring_brief.yaml\n"
    f"{_VALID_BRIEF_YAML}"
    "```\n"
)


def _make_context(llm_response: str | list[str] = _VALID_BRIEF_FENCED_RESPONSE):
    """Build a stub ExecutionContext.

    ``llm_response`` accepts a string (returned every call) or a list of
    strings (consumed one per call, for retry tests).
    """
    llm = AsyncMock()
    if isinstance(llm_response, list):
        llm.chat_stream_with_usage.side_effect = [
            MagicMock(content=r) for r in llm_response
        ]
    else:
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
        "prior_outputs": {
            "data": "context",
            "strat": "objective frame",
            "dev": "design plan",
            "qa": "test strategy",
        },
        "resolved_config": {},
    }


def test_handler_registered_in_bootstrap():
    """Without registration the cutover PR (93.3) couldn't dispatch the
    handler. Confirms the import + HANDLER_CONFIGS entry both landed."""
    classes = [c for c, _ in HANDLER_CONFIGS]
    assert GovernancePreparePlanAuthoringBriefHandler in classes


# ---------------------------------------------------------------------------
# Success: fenced output is the production shape; bare YAML inside a typed
# fence (``yaml:plan_authoring_brief.yaml``) is what real LLMs emit and what
# broke the cycle pre-fix.
# ---------------------------------------------------------------------------


async def test_handler_extracts_yaml_from_typed_fence(seeded_inputs):
    """The LLM wraps YAML in ```yaml:plan_authoring_brief.yaml``` — the
    artifact's stored content must be the unwrapped YAML (no leading fence
    line) so downstream callers can ``from_yaml`` it directly."""
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(_make_context(), seeded_inputs)

    assert result.success is True
    artifact = result.outputs["artifacts"][0]
    assert artifact["name"] == "plan_authoring_brief.yaml"
    assert artifact["media_type"] == "text/yaml"
    assert artifact["type"] == "plan_authoring_brief"
    assert not artifact["content"].startswith("```")

    brief = PlanAuthoringBrief.from_yaml(artifact["content"])
    assert brief.brief_id == "br_seeded_001"
    assert brief.must_cover_requirements == [
        "5 user CRUD endpoints",
        "Duplicate-create returns 409",
    ]
    assert brief.accepted_stack["framework"] == "fastapi"

    # brief_outcome carries the same unwrapped content for the merger.
    assert result.outputs["brief_outcome"]["status"] == "success"
    assert result.outputs["brief_outcome"]["yaml_content"] == artifact["content"]


async def test_handler_extracts_yaml_from_bare_yaml_fence(seeded_inputs):
    """LLMs sometimes drop the filename slot and emit just ```yaml``` —
    the handler must still extract the body."""
    bare_fenced = f"```yaml\n{_VALID_BRIEF_YAML}```\n"
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(_make_context(llm_response=bare_fenced), seeded_inputs)

    assert result.success is True
    brief = PlanAuthoringBrief.from_yaml(result.outputs["artifacts"][0]["content"])
    assert brief.brief_id == "br_seeded_001"


# ---------------------------------------------------------------------------
# Retry: a malformed first attempt followed by a valid second attempt should
# succeed without the cycle seeing the failure.
# ---------------------------------------------------------------------------


async def test_handler_retries_after_unparseable_first_attempt(seeded_inputs):
    """First attempt: prose, no fenced YAML → retry. Second attempt: valid
    fenced brief → success. Confirms retry budget actually buys recovery."""
    responses = [
        "I forgot to fence the YAML, sorry.",
        _VALID_BRIEF_FENCED_RESPONSE,
    ]
    ctx = _make_context(llm_response=responses)
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(ctx, seeded_inputs)

    assert result.success is True
    assert ctx.ports.llm.chat_stream_with_usage.call_count == 2
    brief = PlanAuthoringBrief.from_yaml(result.outputs["artifacts"][0]["content"])
    assert brief.brief_id == "br_seeded_001"


async def test_handler_respects_configured_max_attempts(seeded_inputs):
    """``brief_max_attempts`` from resolved_config caps retries. Setting it
    to 1 means a single bad emission is terminal."""
    seeded_inputs["resolved_config"]["brief_max_attempts"] = 1
    ctx = _make_context(llm_response="not yaml at all")
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(ctx, seeded_inputs)

    assert result.success is False
    assert ctx.ports.llm.chat_stream_with_usage.call_count == 1


# ---------------------------------------------------------------------------
# Hard failures: the retry budget runs out, or the LLM call itself fails.
# ---------------------------------------------------------------------------


async def test_handler_returns_failure_when_no_fenced_yaml_in_any_attempt(seeded_inputs):
    """When every attempt emits prose with no fenced YAML, the handler
    returns ``success=False`` naming the artifact so the cycle's
    correction loop has a specific signal (not silent garbage)."""
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(
        _make_context(llm_response="This isn't a YAML brief — just prose.\n"),
        seeded_inputs,
    )

    assert result.success is False
    assert result.outputs == {}
    assert "plan_authoring_brief.yaml" in (result.error or "")


async def test_handler_returns_failure_when_brief_missing_required_field(seeded_inputs):
    """YAML parses but omits a required field. The error surfaces the
    field name (``risk_areas``) so the corrective feedback is actionable."""
    missing_risk_areas = "\n".join(
        line for line in _VALID_BRIEF_YAML.splitlines() if not line.startswith("risk_areas")
    )
    missing_risk_areas = (
        "\n".join(
            line
            for line in missing_risk_areas.splitlines()
            if line != '  - "Concurrent create/delete races"'
        )
        + "\n"
    )
    fenced_response = f"```yaml:plan_authoring_brief.yaml\n{missing_risk_areas}```\n"
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(
        _make_context(llm_response=fenced_response), seeded_inputs
    )

    assert result.success is False
    assert "risk_areas" in (result.error or "")


async def test_handler_returns_failure_on_llm_error(seeded_inputs):
    """If the LLM call itself raises (network/timeout), the handler
    returns a structured failure. The retry loop swallows the LLMError
    on each attempt, so the surfaced error is the retry-exhausted form
    rather than the raw exception — but the artifact name is still in it
    so the cycle can route correctly."""
    from squadops.llm.exceptions import LLMError

    ctx = _make_context()
    ctx.ports.llm.chat_stream_with_usage.side_effect = LLMError("network timeout")

    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(ctx, seeded_inputs)

    assert result.success is False
    assert "plan_authoring_brief.yaml" in (result.error or "")
    assert "network timeout" in (result.error or "")
