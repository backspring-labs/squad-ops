"""Tests for GovernanceReviewHandler manifest production (SIP-0086 Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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


def _make_context(
    project_id: str = "group_run",
    cycle_id: str = "cyc_test",
) -> MagicMock:
    ctx = MagicMock()
    ctx.ports.prompt_service.get_system_prompt.return_value = _FakeAssembled()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock()
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.request_renderer = None
    ctx.correlation_context = None
    # Issue #109: cycle_id / project_id need to be real strings for the
    # manifest identifier rewrite step. MagicMock auto-attrs would
    # stringify to <MagicMock ...> and break the YAML.
    ctx.project_id = project_id
    ctx.cycle_id = cycle_id
    return ctx


def _make_inputs(
    implementation_plan: bool = True,
    min_subtasks: int = 3,
    max_subtasks: int = 15,
) -> dict[str, Any]:
    return {
        "prd": "Build a group run app with FastAPI and React.",
        "prior_outputs": {"strat": "Strategy analysis content"},
        "resolved_config": {
            "implementation_plan": implementation_plan,
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
        response_content = "## Governance Review\nThe plan looks good.\n\n" + VALID_MANIFEST_BLOCK
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(response_content)

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

    async def test_review_only_when_implementation_plan_disabled(self):
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "## Governance Review\nLooks good."
        )

        result = await handler.handle(ctx, _make_inputs(implementation_plan=False))

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


class TestManifestIdentifierRewrite:
    """Issue #109: project_id / cycle_id / prd_hash must be authoritative.

    Max (especially under small models) fabricates plausible-looking but
    incorrect identifiers (`group_run_mvp`, `cycle_v03`, `a1b2c3d4e5f6`).
    The handler must overwrite the LLM-emitted values with the cycle's
    real identifiers before persisting the manifest, AND substitute
    those values into the prompt so the LLM doesn't have to invent them.
    """

    async def test_rewrites_fabricated_project_id(self):
        import hashlib

        handler = GovernanceReviewHandler()
        ctx = _make_context(project_id="group_run", cycle_id="cyc_real_001")
        # LLM emits a fabricated project_id (the cyc_4cac11018af7 failure mode)
        fabricated_block = (
            VALID_MANIFEST_BLOCK.replace("project_id: group_run", "project_id: group_run_mvp")
            .replace("cycle_id: cyc_test", "cycle_id: cycle_v03")
            .replace("prd_hash: abc123", "prd_hash: a1b2c3d4e5f6")
        )
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + fabricated_block
        )

        result = await handler.handle(ctx, _make_inputs())

        assert result.success
        manifest_yaml = result.outputs["artifacts"][1]["content"]
        prd = "Build a group run app with FastAPI and React."
        expected_hash = hashlib.sha256(prd.encode()).hexdigest()
        assert "project_id: group_run\n" in manifest_yaml
        assert "cycle_id: cyc_real_001\n" in manifest_yaml
        assert f"prd_hash: {expected_hash}\n" in manifest_yaml
        # Fabricated values are gone.
        assert "group_run_mvp" not in manifest_yaml
        assert "cycle_v03" not in manifest_yaml
        assert "a1b2c3d4e5f6" not in manifest_yaml

    async def test_keeps_correct_identifiers_unchanged(self):
        """When the LLM happens to emit the right values, the rewrite is a no-op
        (no warnings about mismatch in the wild)."""
        import hashlib

        handler = GovernanceReviewHandler()
        ctx = _make_context(project_id="group_run", cycle_id="cyc_real_001")
        prd = "Build a group run app with FastAPI and React."
        good_hash = hashlib.sha256(prd.encode()).hexdigest()
        good_block = (
            VALID_MANIFEST_BLOCK.replace("project_id: group_run", "project_id: group_run")
            .replace("cycle_id: cyc_test", "cycle_id: cyc_real_001")
            .replace("prd_hash: abc123", f"prd_hash: {good_hash}")
        )
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + good_block
        )

        result = await handler.handle(ctx, _make_inputs())

        assert result.success
        manifest_yaml = result.outputs["artifacts"][1]["content"]
        assert "project_id: group_run\n" in manifest_yaml
        assert "cycle_id: cyc_real_001\n" in manifest_yaml
        assert f"prd_hash: {good_hash}\n" in manifest_yaml

    async def test_prompt_substitutes_authoritative_identifiers(self):
        """The prompt sent to the LLM must contain the real project_id /
        cycle_id / prd_hash so Max doesn't fall back to fabricating them."""
        import hashlib

        handler = GovernanceReviewHandler()
        ctx = _make_context(project_id="group_run", cycle_id="cyc_real_001")
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        await handler.handle(ctx, _make_inputs())

        sent_messages = ctx.ports.llm.chat_stream_with_usage.call_args.args[0]
        user_prompt = next(m for m in sent_messages if m.role == "user").content
        prd = "Build a group run app with FastAPI and React."
        expected_hash = hashlib.sha256(prd.encode()).hexdigest()
        assert "project_id: group_run\n" in user_prompt
        assert "cycle_id: cyc_real_001\n" in user_prompt
        assert f"prd_hash: {expected_hash}\n" in user_prompt
        # The literal `<placeholder>` strings are gone — that was the bug
        # in #109 where the LLM saw `<project_id>` and invented values.
        assert "<project_id>" not in user_prompt
        assert "<cycle_id>" not in user_prompt
        assert "<sha256 of PRD>" not in user_prompt

    async def test_falls_back_when_context_identifiers_missing(self):
        """Defensive: handler shouldn't crash if context has empty
        project_id / cycle_id (e.g. a misconfigured test or an envelope
        that lost its metadata). LLM-emitted values pass through and
        the manifest is still parseable."""
        handler = GovernanceReviewHandler()
        ctx = _make_context(project_id="", cycle_id="")
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        result = await handler.handle(ctx, _make_inputs())

        assert result.success
        manifest_yaml = result.outputs["artifacts"][1]["content"]
        # Original LLM-emitted identifiers preserved (no rewrite).
        assert "project_id: group_run\n" in manifest_yaml
        assert "cycle_id: cyc_test\n" in manifest_yaml


class TestPRDCoverageDiscipline:
    """Issue #112: prompt extension must instruct Max to perform PRD ↔
    acceptance_criteria coverage and pick the right typed-check shape per
    sub-requirement, with the full procedure and a worked example."""

    def test_extension_has_coverage_section_header(self):
        ext = GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION
        assert "PRD Coverage Discipline" in ext, (
            "Coverage section header missing — Max won't know to perform the pass"
        )
        assert "load-bearing" in ext, (
            "Section must signal load-bearing intent so the LLM doesn't skip it"
        )

    def test_extension_enumerates_subrequirement_shapes(self):
        ext = GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION
        for shape in (
            "required markdown sections",
            "required model fields",
            "required API endpoints",
            "required config keys",
        ):
            normalized = shape.lower()
            assert normalized in ext.lower(), f"Sub-requirement shape missing: {shape}"

    def test_extension_maps_shape_to_typed_check(self):
        ext = GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION
        # Each shape must point at the correct typed-check primitive so the
        # LLM doesn't fall back to bare prose strings.
        assert "regex_match" in ext
        assert "field_present" in ext
        assert "endpoint_defined" in ext
        assert "import_present" in ext

    def test_extension_includes_qa_handoff_worked_example(self):
        """The recurring defect this fixes (4 of 5 SIP-0092 gate cycles) was
        a missing `## Expected Behavior` section check. The worked example
        must show that exact case so Max can pattern-match against it."""
        ext = GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION
        assert "## How to Test" in ext
        assert "## Expected Behavior" in ext
        assert "qa_handoff.md" in ext
        # Show the typed-check syntax, not prose
        assert 'pattern: "## How to Test"' in ext
        assert "count_min: 1" in ext

    def test_extension_warns_against_loose_pattern_matching(self):
        """Pattern-only checks like `how to test|how to run` match running
        prose and were the proximate cause of the qa_handoff defect.
        The prompt must call this anti-pattern out explicitly."""
        ext = GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION
        assert "how to test|how to run" in ext
        assert "NOT" in ext or "not sufficient" in ext.lower()

    def test_extension_requires_audit_trail_in_review(self):
        """Coverage decisions must be visible in the review document so the
        gate evaluator can audit per-deliverable typed-check coverage without
        diffing the manifest YAML against the PRD by hand."""
        ext = GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION
        assert "PRD Coverage" in ext
        assert "audit trail" in ext.lower()

    async def test_prompt_extension_reaches_llm_call(self):
        """End-to-end: the coverage discipline text actually lands in the
        user prompt sent to the LLM (regression guard against a refactor
        that builds the prompt without including the extension)."""
        handler = GovernanceReviewHandler()
        ctx = _make_context()
        ctx.ports.llm.chat_stream_with_usage.return_value = _make_llm_response(
            "Review.\n\n" + VALID_MANIFEST_BLOCK
        )

        await handler.handle(ctx, _make_inputs())

        call_args = ctx.ports.llm.chat_stream_with_usage.call_args
        messages = call_args[0][0]
        user_content = next(m.content for m in messages if m.role == "user")
        assert "PRD Coverage Discipline" in user_content
        assert "## Expected Behavior" in user_content
