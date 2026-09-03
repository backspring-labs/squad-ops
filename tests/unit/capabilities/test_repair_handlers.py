"""Tests for repair task handlers (SIP-0070 Phase 3).

Covers:
- 4 repair handlers: construction, capability_id, role, artifact_name
- _build_user_prompt(): verification context injection, upstream output filtering
- handle(): LLM success + failure paths (inherited from _CycleTaskHandler)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.impl.repair_handlers import QATestRepairHandler
from squadops.capabilities.handlers.repair_tasks import (
    DataAnalyzeVerificationHandler,
    DevelopmentRepairHandler,
    GovernanceRootCauseHandler,
    StrategyCorrectivePlanHandler,
)
from squadops.capabilities.reasoning_policy import REASONING_BY_CAPABILITY

pytestmark = [pytest.mark.domain_pulse_checks]


# ---------------------------------------------------------------------------
# Construction + class attributes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------


class TestRepairBuildUserPrompt:
    def test_verification_context_injected(self):
        h = DataAnalyzeVerificationHandler()
        prompt = h._build_user_prompt(
            prd="Build a widget",
            prior_outputs={
                "verification_context": "Boundary: post_dev\nFailed suites: ['s1']",
            },
        )
        assert "## Verification Failure Context" in prompt
        assert "Boundary: post_dev" in prompt
        assert "Failed suites: ['s1']" in prompt

    def test_no_verification_context_omits_section(self):
        h = GovernanceRootCauseHandler()
        prompt = h._build_user_prompt(
            prd="Build a widget",
            prior_outputs={"data": {"summary": "analysis output"}},
        )
        assert "## Verification Failure Context" not in prompt
        assert "## Prior Analysis from Upstream Roles" in prompt

    def test_upstream_outputs_exclude_verification_context(self):
        h = StrategyCorrectivePlanHandler()
        prompt = h._build_user_prompt(
            prd="Build a widget",
            prior_outputs={
                "verification_context": "some context",
                "data": {"summary": "analysis"},
                "lead": {"summary": "root cause"},
            },
        )
        # verification_context should not appear in "Prior Analysis" section
        assert "## Prior Analysis from Upstream Roles" in prompt
        assert "### data" in prompt
        assert "### lead" in prompt
        # verification_context appears in its dedicated section, not upstream
        sections = prompt.split("## Prior Analysis from Upstream Roles")
        assert "verification_context" not in sections[1]

    def test_prd_always_present(self):
        h = DevelopmentRepairHandler()
        prompt = h._build_user_prompt(prd="Fix the bug", prior_outputs=None)
        assert "## Product Requirements Document" in prompt
        assert "Fix the bug" in prompt
        assert "dev" in prompt  # role reference

    def test_empty_prior_outputs(self):
        h = DataAnalyzeVerificationHandler()
        prompt = h._build_user_prompt(prd="PRD text", prior_outputs={})
        assert "## Product Requirements Document" in prompt
        assert "## Verification Failure Context" not in prompt
        assert "## Prior Analysis" not in prompt

    def test_none_prior_outputs(self):
        h = GovernanceRootCauseHandler()
        prompt = h._build_user_prompt(prd="PRD text", prior_outputs=None)
        assert "## Product Requirements Document" in prompt

    def test_only_verification_context_no_upstream_section(self):
        """When prior_outputs has only verification_context, no upstream section appears."""
        h = StrategyCorrectivePlanHandler()
        prompt = h._build_user_prompt(
            prd="Build it",
            prior_outputs={"verification_context": "boundary failed"},
        )
        assert "## Verification Failure Context" in prompt
        assert "## Prior Analysis from Upstream Roles" not in prompt

    def test_all_handlers_produce_distinct_prompts_with_role(self):
        """Each handler injects its own role name into the prompt."""
        for handler_cls, expected_role in [
            (DataAnalyzeVerificationHandler, "data"),
            (GovernanceRootCauseHandler, "lead"),
            (StrategyCorrectivePlanHandler, "strat"),
            (DevelopmentRepairHandler, "dev"),
        ]:
            h = handler_cls()
            prompt = h._build_user_prompt(prd="PRD", prior_outputs=None)
            assert f"your {expected_role} analysis" in prompt


# ---------------------------------------------------------------------------
# handle() — LLM success + failure
# ---------------------------------------------------------------------------


def _make_context(llm_response="Repair analysis content"):
    """Build a minimal ExecutionContext mock for handler tests."""
    llm = AsyncMock()
    llm.chat.return_value = MagicMock(content=llm_response)
    llm.chat_stream_with_usage.return_value = MagicMock(content=llm_response)
    llm.default_model = "test-model"

    prompt_service = MagicMock()
    prompt_service.get_system_prompt.return_value = MagicMock(content="system prompt")

    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service = prompt_service
    ports.llm_observability = None
    ports.request_renderer = None

    ctx = MagicMock()
    ctx.ports = ports
    ctx.correlation_context = None
    return ctx


class TestRepairEmissionClamp:
    """#1011: repair handlers ride the base ``_build_chat_kwargs`` path, which
    previously passed ``max_tokens`` only when agent overrides carried
    ``max_completion_tokens`` — the registry's per-model completion clamp never
    applied, so a dev repair emitted 12,314 tokens under an 8,192-clamped model
    (V38 shakedown #2) while develop/qa tasks on the same model were clamped."""

    def test_registry_clamp_applies_without_override(self):
        """The bug this catches: a repair on a registry-known model runs at the
        capability ceiling instead of the model's completion clamp.

        #1173 changed what the clamp is: ``default_max_completion`` budgets the
        OUTPUT, and the thinking a capability declares is added on top, because
        thinking is billed against the same wire budget and then discarded.
        ``development.correction_repair`` declares MEDIUM — but this model's dial is
        a TOGGLE, so the level it declares and the thinking it gets are different
        things, and the headroom is keyed on the latter."""
        from squadops.llm.model_registry import get_model_spec, thinking_headroom

        h = DevelopmentRepairHandler()
        spec = get_model_spec("qwen3.8:27b")
        assert spec is not None  # premise: the V38 arm is registered (#1008)
        kwargs = h._build_chat_kwargs({"agent_model": "qwen3.8:27b", "agent_config_overrides": {}})
        assert kwargs["max_tokens"] == spec.default_max_completion + thinking_headroom(
            kwargs.get("reasoning"), spec
        )
        assert kwargs["max_tokens"] > spec.default_max_completion, (
            "this handler declares a reasoning level, so it must get room to think "
            "on top of its output budget"
        )

    def test_explicit_override_still_wins(self):
        """A profile that deliberately raises (or lowers) the budget keeps
        authority — the clamp is a default, not a ceiling on operators."""
        h = DevelopmentRepairHandler()
        kwargs = h._build_chat_kwargs(
            {
                "agent_model": "qwen3.8:27b",
                "agent_config_overrides": {"max_completion_tokens": 12_000},
            }
        )
        assert kwargs["max_tokens"] == 12_000

    def test_unknown_model_keeps_prior_behavior(self):
        """No registry entry → no invented budget: max_tokens stays absent,
        exactly the pre-#1011 behavior (the #1008 lesson runs the other way —
        an UNregistered model is a registry gap to fix, not a clamp to guess)."""
        h = DevelopmentRepairHandler()
        kwargs = h._build_chat_kwargs(
            {"agent_model": "totally-unregistered:1b", "agent_config_overrides": {}}
        )
        assert "max_tokens" not in kwargs

    async def test_clamp_reaches_the_llm_call(self):
        """Flow half: the resolved budget arrives at chat_stream_with_usage —
        wiring, not just the kwargs builder. Output clamp plus declared thinking
        headroom, the two having been computed independently until #1173."""
        from squadops.llm.model_registry import get_model_spec, thinking_headroom

        h = DevelopmentRepairHandler()
        ctx = _make_context(llm_response="repaired")
        await h.handle(
            ctx,
            {
                "prd": "Build a widget",
                "agent_model": "qwen3.8:27b",
                "agent_config_overrides": {},
                "prior_outputs": {},
            },
        )
        call = ctx.ports.llm.chat_stream_with_usage.call_args
        spec = get_model_spec("qwen3.8:27b")
        assert call.kwargs["max_tokens"] == spec.default_max_completion + thinking_headroom(
            call.kwargs.get("reasoning"), spec
        )


class TestRepairHandlerHandle:
    async def test_llm_success_returns_artifact(self):
        h = DataAnalyzeVerificationHandler()
        ctx = _make_context(llm_response="Verification analysis: all good")
        result = await h.handle(
            ctx,
            {
                "prd": "Build a widget",
                "prior_outputs": {"verification_context": "failure context"},
            },
        )
        assert result.success is True
        artifacts = result.outputs["artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "verification_analysis.md"
        assert artifacts[0]["content"] == "Verification analysis: all good"

    async def test_llm_failure_returns_error(self):
        from squadops.llm.exceptions import LLMError

        h = GovernanceRootCauseHandler()
        ctx = _make_context()
        ctx.ports.llm.chat.side_effect = LLMError("model overloaded")
        ctx.ports.llm.chat_stream_with_usage.side_effect = LLMError("model overloaded")
        result = await h.handle(ctx, {"prd": "Build a widget"})
        assert result.success is False
        assert "model overloaded" in result.error

    async def test_each_handler_uses_correct_artifact_name(self):
        ctx = _make_context(llm_response="output")
        for handler_cls, expected_name in [
            (DataAnalyzeVerificationHandler, "verification_analysis.md"),
            (GovernanceRootCauseHandler, "root_cause_analysis.md"),
            (StrategyCorrectivePlanHandler, "corrective_plan.md"),
            (DevelopmentRepairHandler, "repair_output.md"),
        ]:
            h = handler_cls()
            result = await h.handle(ctx, {"prd": "test"})
            assert result.success is True
            assert result.outputs["artifacts"][0]["name"] == expected_name


class TestModelSurfaceReachesTheRepairPrompt:
    """The pure lines are useless unless they land in the prompt the repair agent reads.

    This is the #588 lesson in test form: that fix was correct and wired to a code path
    nothing used, so it changed no outcome until the wiring was fixed. Assert the whole
    path — manifest → failure_evidence → rendered prompt text.
    """

    @staticmethod
    def _manifest():
        from pathlib import Path

        from squadops.capabilities.scaffold import InterfaceManifest

        path = (
            Path(__file__).resolve().parents[3]
            / "examples"
            / "03_group_run"
            / "interface_manifest.yaml"
        )
        return InterfaceManifest.from_yaml(path.read_text(encoding="utf-8"))

    def test_evidence_lines_render_into_the_failure_summary(self):
        from squadops.capabilities.handlers.impl.repair_handlers import _format_failure_summary
        from squadops.capabilities.scaffold import model_surface_instructions

        evidence = {"model_surface": model_surface_instructions(self._manifest())}

        rendered = _format_failure_summary(evidence, None)

        assert "MODEL SURFACE (authoritative" in rendered
        # the real names the pf-41 repairs failed to use
        for real in ("RunEvent", "RunEventCreate", "Participant", "ParticipantName"):
            assert real in rendered

    def test_absent_evidence_renders_no_section(self):
        """Author-mode runs carry no manifest, so the block must not appear at all —
        an empty authoritative header would be noise in every non-scaffold repair."""
        from squadops.capabilities.handlers.impl.repair_handlers import _format_failure_summary

        assert "MODEL SURFACE" not in _format_failure_summary({"error": "boom"}, None)

    def test_correction_runner_populates_the_evidence_key(self):
        """The executor-side half: the runner must actually put the lines on the
        envelope's failure_evidence, or the renderer above never sees them."""
        from types import SimpleNamespace

        from adapters.cycles.correction_runner import _inject_deterministic_evidence

        manifest = self._manifest()
        evidence: dict = {}
        _inject_deterministic_evidence(
            failure_evidence=evidence,
            interface_manifest=manifest,
            artifact_contents={},
            scaffold_enforcement_carry=[],
            envelope=SimpleNamespace(inputs={}),
        )

        assert evidence.get("model_surface"), "model_surface must be injected for a bound run"
        assert "RunEvent" in " ".join(evidence["model_surface"])


class TestPriorRepairRejectionReachesThePrompt:
    """#870: the rejected-repair record renders as an authoritative block."""

    def test_rejection_entries_render_into_the_failure_summary(self):
        """Bug caught: evidence threaded to the envelope but rendered by nothing
        (#849's declared-read-by-nothing shape) — the repair agent still re-rolls
        blind while the carry claims otherwise."""
        from squadops.capabilities.handlers.impl.repair_handlers import _format_failure_summary

        evidence = {
            "error": "tests failed",
            "prior_repair_rejections": [
                "correction attempt 2: repaired suite retest FAILED — frontend build "
                "failed (exit 1)"
            ],
        }
        rendered = _format_failure_summary(evidence, None)
        assert "PRIOR REPAIR REJECTED" in rendered
        assert "frontend build failed (exit 1)" in rendered

    def test_absent_rejections_render_no_block(self):
        from squadops.capabilities.handlers.impl.repair_handlers import _format_failure_summary

        assert "PRIOR REPAIR REJECTED" not in _format_failure_summary({"error": "x"}, None)


class TestRepairReasoningLevel:
    """#927 on the base ``_build_chat_kwargs`` path every repair handler rides:
    the capability's declared level reaches ``chat()``, clamped by the model's
    dial. The bug: a repair generating with the model's own posture — the
    12,314-token repair #1011 clamped was mostly thinking."""

    def test_dev_repair_sends_its_declared_level_on_a_switchable_model(self):
        kwargs = DevelopmentRepairHandler()._build_chat_kwargs(
            {"agent_model": "qwen3.8:27b", "agent_config_overrides": {}}
        )
        assert kwargs["reasoning"] == REASONING_BY_CAPABILITY["development.correction_repair"]

    def test_qa_repair_sends_its_declared_level_too(self):
        """Same invariant as the dev repair above: this file tests the WIRING, and the
        value is the declaration's business (`test_reasoning_policy`).

        It used to pin ``"none"`` outright, on the reading that a qa repair transcribes a
        failing assertion into a correct one. The 1.7.1 rolls falsified that: the repair
        handler produced two of the sixteen contentless emissions (225 and 149 chars, no
        fence), the same shape as the authoring path, and #1268 moved both. Pinning the
        value in two places is how one of them ends up describing a wire that changed.
        """
        kwargs = QATestRepairHandler()._build_chat_kwargs(
            {"agent_model": "qwen3.8:27b", "agent_config_overrides": {}}
        )
        assert kwargs["reasoning"] == REASONING_BY_CAPABILITY["qa.test_repair"]

    def test_profile_override_wins(self):
        kwargs = DevelopmentRepairHandler()._build_chat_kwargs(
            {"agent_model": "qwen3.8:27b", "agent_config_overrides": {"reasoning": "none"}}
        )
        assert kwargs["reasoning"] == "none"

    @pytest.mark.parametrize("model", ["qwen2.5:7b", "totally-unregistered:1b"])
    def test_no_level_for_a_model_without_the_dial(self, model):
        kwargs = DevelopmentRepairHandler()._build_chat_kwargs(
            {"agent_model": model, "agent_config_overrides": {}}
        )
        assert "reasoning" not in kwargs

    async def test_level_reaches_the_llm_call(self):
        """Wiring half: the resolved level arrives at chat_stream_with_usage."""
        h = DevelopmentRepairHandler()
        ctx = _make_context(llm_response="repaired")
        await h.handle(
            ctx,
            {
                "prd": "p",
                "agent_model": "qwen3.8:27b",
                "agent_config_overrides": {},
                "failure_context": "traceback",
            },
        )
        call_kwargs = ctx.ports.llm.chat_stream_with_usage.call_args.kwargs
        assert call_kwargs["reasoning"] == "medium"


# ---------------------------------------------------------------------------
# #1229 — the repair evaluates its own patch where the toolchain lives
# ---------------------------------------------------------------------------


class TestTheRepairEvaluatesItsOwnPatch:
    """Bug caught: a repair verified only in runtime-api, which has no node, so on the
    Next.js stack no blocking check ever executed and three rounds ended ``unverifiable``
    (``cyc_05abfc7c1f00``). The repair now runs the failed task's typed criteria — the
    framework-injected family included — on its own patched tree and ships the rows."""

    async def test_typed_check_rows_ride_with_the_patch(self):
        from squadops.capabilities.handlers.impl.repair_handlers import (
            DevelopmentCorrectionRepairHandler,
        )

        h = DevelopmentCorrectionRepairHandler()
        ctx = _make_context(
            "```python:backend/routes.py\ndef create_run():\n    return RunEvent()\n```\n"
        )
        result = await h.handle(
            ctx,
            {
                "prd": "x",
                "resolved_config": {"build_profile": "fullstack_fastapi_react"},
                "acceptance_criteria": [],
                "expected_artifacts": ["backend/routes.py"],
                "workspace_revision_id": "rev-1",
            },
        )
        assert result.success is True, "the rows are evidence for the verifier, not a verdict"
        evidence = result.outputs["repair_typed_checks"]
        assert evidence["environment"] == f"agent:{h._role}"
        assert evidence["workspace_revision_id"] == "rev-1"
        rows = {r["check"]: r for r in evidence["checks"]}
        assert rows["acceptance:undefined_names"]["status"] == "failed"
        assert "RunEvent" in rows["acceptance:undefined_names"]["reason"]
        assert rows["acceptance:undefined_names"]["params"] == {"file": "backend/routes.py"}

    async def test_an_empty_emission_carries_no_rows(self):
        from squadops.capabilities.handlers.impl.repair_handlers import (
            DevelopmentCorrectionRepairHandler,
        )

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(
            _make_context(""),
            {"prd": "x", "resolved_config": {}, "expected_artifacts": ["backend/routes.py"]},
        )
        assert "repair_typed_checks" not in result.outputs


class TestTheRepairEvaluatesOnTheVerifiersTree:
    """#1264: the verifier overlays the failed task's own files beneath the patch; the
    repair's agent-side evaluation must see the same tree. Replayed from the React shakeout
    on 06408dfe (cyc_4ec4ad5e2ca1): a dev repair of a qa failure evaluated the suite's
    criteria on a tree without the suite — every row `file_not_found`, the fix refused
    twice. Bug caught: the two environments judging different trees."""

    _REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"

    def _inputs(self, *, with_failed_artifacts: bool) -> dict:
        from squadops.capabilities.context_assembly import REPAIR_FAILED_ARTIFACTS_KEY

        suite = (self._REPLAYS / "1-7-1-react-shakeout-5-qa-round-0-test_runs.py.txt").read_text(
            encoding="utf-8"
        )
        inputs = {
            "prd": "x",
            "resolved_config": {"build_profile": "fullstack_fastapi_react"},
            "acceptance_criteria": [
                {
                    "check": "function_defined",
                    "params": {
                        "file": "backend/tests/test_runs.py",
                        "name_prefix": "test_",
                        "min_count": 8,
                    },
                }
            ],
            "expected_artifacts": ["backend/routes.py"],
            "workspace_revision_id": "rev-1",
        }
        if with_failed_artifacts:
            inputs[REPAIR_FAILED_ARTIFACTS_KEY] = [
                {"name": "backend/tests/test_runs.py", "content": suite}
            ]
        return inputs

    def _patch(self) -> str:
        route = (
            self._REPLAYS / "1-7-1-react-shakeout-5-repair-01-backend-routes.py.txt"
        ).read_text(encoding="utf-8")
        return f"```python:backend/routes.py\n{route}```\n"

    async def test_the_failed_tasks_files_are_beneath_the_patch(self):
        from squadops.capabilities.handlers.impl.repair_handlers import (
            DevelopmentCorrectionRepairHandler,
        )

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(
            _make_context(self._patch()), self._inputs(with_failed_artifacts=True)
        )
        rows = {r["check"]: r for r in result.outputs["repair_typed_checks"]["checks"]}
        assert rows["acceptance:function_defined"]["status"] == "passed"
        assert rows["acceptance:function_defined"]["actual"]["matched_count"] >= 8

    async def test_without_them_the_suites_criterion_cannot_see_the_suite(self):
        """The control — the shakeout's shape: the row is `file_not_found`, which the
        verifier's backstop (#1259/#1264) discounts, but only the tree makes it evidence."""
        from squadops.capabilities.handlers.impl.repair_handlers import (
            DevelopmentCorrectionRepairHandler,
        )

        h = DevelopmentCorrectionRepairHandler()
        result = await h.handle(
            _make_context(self._patch()), self._inputs(with_failed_artifacts=False)
        )
        rows = {r["check"]: r for r in result.outputs["repair_typed_checks"]["checks"]}
        assert (
            rows["acceptance:function_defined"]["status"],
            rows["acceptance:function_defined"]["reason"],
        ) == (
            "failed",
            "file_not_found",
        )
