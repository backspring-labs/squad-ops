"""Tests for GovernanceReviewHandler manifest production (SIP-0086 Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle_tasks import GovernanceReviewHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_MANIFEST_BLOCK = """\
```yaml:implementation_plan.yaml
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "Create models"
    expected_artifacts:
      - "backend/models.py"
    acceptance_criteria:
      - "Models exist"
    depends_on: []
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend API"
    description: "Create endpoints"
    expected_artifacts:
      - "backend/main.py"
    depends_on: [0]
  - task_index: 2
    task_type: qa.test
    role: qa
    focus: "Tests"
    description: "Write tests"
    expected_artifacts:
      - "tests/test_api.py"
    depends_on: [0, 1]
summary:
  total_dev_tasks: 2
  total_qa_tasks: 1
  total_tasks: 3
  estimated_layers: [backend, test]
```"""


def _make_llm_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.tokens_per_second = None
    resp.prompt_tokens = 100
    resp.completion_tokens = 200
    resp.total_tokens = 300
    return resp


@dataclass
class _FakeAssembled:
    content: str = "You are the lead agent."
    assembly_hash: str = "hash123"


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.ports.prompt_service.get_system_prompt.return_value = _FakeAssembled()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock()
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.request_renderer = None
    ctx.correlation_context = None
    return ctx


def _make_inputs(
    build_plan: bool = True,
    min_subtasks: int = 3,
    max_subtasks: int = 15,
) -> dict[str, Any]:
    return {
        "prd": "Build a group run app with FastAPI and React.",
        "prior_outputs": {"strat": "Strategy analysis content"},
        "resolved_config": {
            "build_plan": build_plan,
            "min_build_subtasks": min_subtasks,
            "max_build_subtasks": max_subtasks,
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGovernanceReviewManifest:
    async def test_produces_governance_review_and_manifest(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        response_content = (
            "## Governance Review\nThe plan looks good.\n\n" + VALID_MANIFEST_BLOCK
        )
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            response_content
        )

        result = await handler.handle(ctx, _make_inputs())

        assert result.success
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 2

        review = artifacts[0]
        assert review["name"] == "governance_review.md"
        assert review["type"] == "document"

        manifest = artifacts[1]
        assert manifest["name"] == "implementation_plan.yaml"
        assert manifest["type"] == "control_implementation_plan"

    async def test_review_only_when_build_plan_disabled(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "## Governance Review\nLooks good."
        )

        result = await handler.handle(ctx, _make_inputs(build_plan=False))

        assert result.success
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "governance_review.md"

    async def test_graceful_fallback_no_yaml_block(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "## Governance Review\nNo manifest here."
        )

        result = await handler.handle(ctx, _make_inputs())

        assert result.success
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1  # Only governance review

    async def test_graceful_fallback_malformed_yaml(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        bad_manifest = "```yaml:implementation_plan.yaml\n{{invalid yaml\n```"
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + bad_manifest
        )

        result = await handler.handle(ctx, _make_inputs())

        assert result.success
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1

    async def test_graceful_fallback_below_min_subtasks(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        # VALID_MANIFEST_BLOCK has 3 tasks, set min to 5
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        result = await handler.handle(ctx, _make_inputs(min_subtasks=5))

        assert result.success
        assert len(result.outputs["artifacts"]) == 1

    async def test_graceful_fallback_above_max_subtasks(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        # VALID_MANIFEST_BLOCK has 3 tasks, set max to 2
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        result = await handler.handle(ctx, _make_inputs(max_subtasks=2))

        assert result.success
        assert len(result.outputs["artifacts"]) == 1

    async def test_manifest_artifact_has_correct_media_type(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        result = await handler.handle(ctx, _make_inputs())

        manifest = result.outputs["artifacts"][1]
        assert manifest["media_type"] == "text/yaml"
        assert manifest["type"] == "control_implementation_plan"

    async def test_prd_hash_mismatch_logs_warning_but_accepts(self):
        """PRD hash is informational — mismatch logs warning but doesn't reject."""
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        # VALID_MANIFEST_BLOCK has prd_hash: abc123, which won't match SHA-256 of PRD
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        result = await handler.handle(ctx, _make_inputs())

        # Manifest is accepted despite hash mismatch (warning logged)
        assert result.success
        assert len(result.outputs["artifacts"]) == 2

    async def test_llm_failure_returns_error(self):
        from squadops.llm.exceptions import LLMError

        handler = GovernanceReviewHandler()
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.side_effect = LLMError("timeout")

        result = await handler.handle(ctx, _make_inputs())

        assert not result.success
        assert "timeout" in result.error
