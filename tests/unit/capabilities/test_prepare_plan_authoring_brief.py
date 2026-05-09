"""Tests for ``GovernancePreparePlanAuthoringBriefHandler`` (SIP-0093 PR 93.0).

The handler is registered in this PR but not yet wired into
``PLANNING_TASK_STEPS`` (cutover happens in 93.3). These tests exercise it
in isolation: brief production from seeded LLM responses, parse-failure
handling, and the artifact's YAML media-type / type.
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


_VALID_BRIEF_LLM_RESPONSE = """\
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


def _make_context(llm_response: str = _VALID_BRIEF_LLM_RESPONSE):
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
        "prior_outputs": {
            "data": "context",
            "strat": "objective frame",
            "dev": "design plan",
            "qa": "test strategy",
        },
        "resolved_config": {},
    }


# ---------------------------------------------------------------------------
# Class attributes (kept tight per CLAUDE.md guidance — paired with behavior tests)
# ---------------------------------------------------------------------------


def test_handler_registered_in_bootstrap():
    """Without registration the cutover PR (93.3) couldn't dispatch the
    handler. Confirms the import + HANDLER_CONFIGS entry both landed."""
    classes = [c for c, _ in HANDLER_CONFIGS]
    assert GovernancePreparePlanAuthoringBriefHandler in classes


# ---------------------------------------------------------------------------
# Behavior
# ---------------------------------------------------------------------------


async def test_handler_produces_parseable_brief_artifact(seeded_inputs):
    """A seeded LLM response produces an artifact that parses round-trip
    via ``PlanAuthoringBrief.from_yaml``."""
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(_make_context(), seeded_inputs)

    assert result.success is True
    artifacts = result.outputs["artifacts"]
    assert len(artifacts) == 1

    artifact = artifacts[0]
    assert artifact["name"] == "plan_authoring_brief.yaml"
    assert artifact["media_type"] == "text/yaml"
    assert artifact["type"] == "plan_authoring_brief"

    brief = PlanAuthoringBrief.from_yaml(artifact["content"])
    assert brief.brief_id == "br_seeded_001"
    assert brief.must_cover_requirements == [
        "5 user CRUD endpoints",
        "Duplicate-create returns 409",
    ]
    assert brief.accepted_stack["framework"] == "fastapi"


async def test_handler_returns_failure_on_unparseable_llm_response(seeded_inputs):
    """When the LLM emits something that can't parse as a brief, the
    handler returns a structured failure naming ``plan_authoring_brief.yaml``
    so the cycle's correction loop has a specific signal — not a silent
    pass with garbage content."""
    bad_response = "This isn't a YAML brief — just prose.\n"
    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(_make_context(llm_response=bad_response), seeded_inputs)

    assert result.success is False
    assert result.outputs == {}
    assert "plan_authoring_brief.yaml" in (result.error or "")


async def test_handler_returns_failure_on_missing_required_field(seeded_inputs):
    """A YAML response missing a required brief field surfaces the field
    name in the failure error, not just a generic 'parse error'."""
    missing_risk_areas = "\n".join(
        line for line in _VALID_BRIEF_LLM_RESPONSE.splitlines() if not line.startswith("risk_areas")
    )
    # Drop the bullet list under risk_areas too.
    missing_risk_areas = (
        "\n".join(
            line
            for line in missing_risk_areas.splitlines()
            if line != '  - "Concurrent create/delete races"'
        )
        + "\n"
    )

    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(_make_context(llm_response=missing_risk_areas), seeded_inputs)

    assert result.success is False
    assert "risk_areas" in (result.error or "")


async def test_handler_propagates_llm_failure_without_attempting_parse(seeded_inputs):
    """If the underlying LLM call fails (network/timeout), the base
    handler's failure surfaces unchanged — the brief-parse step never
    runs and doesn't mask the real error."""
    from squadops.llm.exceptions import LLMError

    ctx = _make_context()
    ctx.ports.llm.chat_stream_with_usage.side_effect = LLMError("network timeout")

    handler = GovernancePreparePlanAuthoringBriefHandler()
    result = await handler.handle(ctx, seeded_inputs)

    assert result.success is False
    # Surfaced as the LLM error, not a brief-parse error.
    assert "network timeout" in (result.error or "")
    assert "plan_authoring_brief.yaml" not in (result.error or "")
