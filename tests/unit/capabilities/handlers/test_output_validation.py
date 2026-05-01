"""Tests for output validation, outcome classification, and self-eval (SIP-0086 Stage B)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from squadops.capabilities.handlers.cycle_tasks import (
    DevelopmentDevelopHandler,
    QATestHandler,
    ValidationResult,
    _CycleTaskHandler,
    _detect_expected_layers,
    _detect_stubs,
    _estimate_min_artifacts,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _art(name: str, content: str = "substantial content here" * 10, **kw) -> dict:
    return {"name": name, "content": content, "type": kw.get("type", "source"), **kw}


def _stub_art(name: str) -> dict:
    return {"name": name, "content": "# TODO", "type": "source"}


# ---------------------------------------------------------------------------
# Phase 5a: ValidationResult + base _validate_output
# ---------------------------------------------------------------------------


class TestValidationResultDefaults:
    async def test_default_passes(self):
        v = ValidationResult(passed=True)
        assert v.passed is True
        assert v.checks == []
        assert v.coverage_ratio == 1.0

    async def test_base_handler_returns_pass(self):
        handler = _CycleTaskHandler()
        result = await handler._validate_output({}, [])
        assert result.passed is True


# ---------------------------------------------------------------------------
# Phase 5b: DevelopmentDevelopHandler focused validation
# ---------------------------------------------------------------------------


class TestDevFocusedValidation:
    def _handler(self) -> DevelopmentDevelopHandler:
        return DevelopmentDevelopHandler()

    async def test_all_expected_artifacts_present_passes(self):
        h = self._handler()
        inputs = {
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py", "repo.py"],
            "acceptance_criteria": ["Models exist"],
        }
        artifacts = [_art("models.py"), _art("repo.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is True
        assert result.summary == "All checks passed"

    async def test_missing_expected_artifact_fails(self):
        h = self._handler()
        inputs = {
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py", "repo.py"],
        }
        artifacts = [_art("models.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False
        assert "repo.py" in result.summary
        assert "file:repo.py" in result.missing_components

    async def test_stub_file_detected_fails(self):
        h = self._handler()
        inputs = {
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
        }
        artifacts = [_stub_art("models.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False
        assert "Stub" in result.summary

    async def test_acceptance_criteria_in_evidence_not_gate(self):
        """RC-8: Acceptance criteria are informational, not pass/fail gates."""
        h = self._handler()
        inputs = {
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
            "acceptance_criteria": ["Models have id field"],
        }
        artifacts = [_art("models.py")]
        result = await h._validate_output(inputs, artifacts)

        # Should pass even though we can't verify acceptance criteria
        assert result.passed is True
        # Prose criteria (non-TypedCheck) captured in evidence as informational
        ac_check = next(c for c in result.checks if c["check"] == "acceptance_criteria_prose")
        assert ac_check["criteria"] == ["Models have id field"]
        assert ac_check["passed"] is True  # Informational, never blocking

    async def test_coverage_ratio_computed(self):
        h = self._handler()
        inputs = {
            "subtask_focus": "test",
            "expected_artifacts": ["a.py", "b.py"],
        }
        artifacts = [_art("a.py")]  # Missing b.py
        result = await h._validate_output(inputs, artifacts)

        # 2 of 3 checks pass (non_stub + acceptance pass, expected_artifacts fails)
        assert 0.0 < result.coverage_ratio < 1.0


# ---------------------------------------------------------------------------
# Phase 5b: DevelopmentDevelopHandler legacy monolithic validation
# ---------------------------------------------------------------------------


class TestDevMonolithicValidation:
    def _handler(self) -> DevelopmentDevelopHandler:
        return DevelopmentDevelopHandler()

    async def test_fastapi_react_prd_expects_backend_and_frontend(self):
        h = self._handler()
        inputs = {"prd": "Build a FastAPI backend and React frontend app."}
        artifacts = [_art("main.py"), _art("App.jsx"), _art("repo.py"),
                     _art("index.html"), _art("package.json"), _art("routes.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is True

    async def test_backend_only_for_fullstack_prd_fails(self):
        h = self._handler()
        inputs = {"prd": "Build a FastAPI backend and React frontend app."}
        artifacts = [_art("main.py"), _art("utils.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False
        assert "frontend" in result.summary.lower()

    async def test_few_artifacts_for_complex_prd_fails(self):
        h = self._handler()
        inputs = {"prd": "Build a FastAPI backend with pytest tests and React frontend."}
        artifacts = [_art("main.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False
        assert "artifacts" in result.summary.lower() or "stack" in result.summary.lower()

    async def test_stub_file_in_monolithic_fails(self):
        h = self._handler()
        inputs = {"prd": "Build a CLI tool."}
        artifacts = [_art("main.py"), _art("utils.py"), _stub_art("board.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False
        assert "Stub" in result.summary

    async def test_backend_only_prd_no_false_frontend(self):
        h = self._handler()
        inputs = {"prd": "Build a FastAPI backend API service."}
        artifacts = [_art("main.py"), _art("routes.py"), _art("models.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is True

    async def test_no_prd_passes(self):
        h = self._handler()
        result = await h._validate_output({"prd": ""}, [_art("main.py")])

        assert result.passed is True

    async def test_summary_is_human_readable(self):
        h = self._handler()
        inputs = {"prd": "Build a React app."}
        artifacts = [_art("main.py")]
        result = await h._validate_output(inputs, artifacts)

        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# Phase 5c: QATestHandler validation
# ---------------------------------------------------------------------------


class TestQAValidation:
    def _handler(self) -> QATestHandler:
        return QATestHandler()

    async def test_focused_expected_artifacts_present_passes(self):
        h = self._handler()
        inputs = {
            "subtask_focus": "Backend tests",
            "expected_artifacts": ["tests/test_api.py"],
        }
        artifacts = [_art("tests/test_api.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is True

    async def test_focused_missing_artifact_fails(self):
        h = self._handler()
        inputs = {
            "subtask_focus": "Backend tests",
            "expected_artifacts": ["tests/test_api.py"],
        }
        artifacts = []
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False

    async def test_legacy_test_file_present_passes(self):
        h = self._handler()
        inputs = {"prd": "Build a CLI tool."}
        artifacts = [_art("test_main.py")]
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is True

    async def test_legacy_no_test_files_fails(self):
        h = self._handler()
        inputs = {"prd": "Build a CLI tool."}
        artifacts = [_art("qa_handoff.md")]  # Not a test file
        result = await h._validate_output(inputs, artifacts)

        assert result.passed is False


# ---------------------------------------------------------------------------
# Phase 5 shared helpers
# ---------------------------------------------------------------------------


class TestDetectStubs:
    async def test_stub_detected(self):
        assert _detect_stubs([{"name": "x.py", "content": "# TODO"}]) == ["x.py"]

    async def test_init_py_skipped(self):
        assert _detect_stubs([{"name": "__init__.py", "content": ""}]) == []

    async def test_substantial_content_passes(self):
        assert _detect_stubs([{"name": "x.py", "content": "x = 1\n" * 50}]) == []


class TestDetectExpectedLayers:
    async def test_fastapi_react_detects_both(self):
        layers = _detect_expected_layers("Build with FastAPI backend and React frontend")
        assert "backend" in layers
        assert "frontend" in layers

    async def test_backend_only(self):
        layers = _detect_expected_layers("Build a FastAPI REST API")
        assert "backend" in layers
        assert "frontend" not in layers


class TestEstimateMinArtifacts:
    async def test_returns_at_least_3(self):
        assert _estimate_min_artifacts("Simple script") >= 3

    async def test_fullstack_higher_than_simple(self):
        simple = _estimate_min_artifacts("Build a CLI script")
        fullstack = _estimate_min_artifacts("Build a FastAPI backend with React frontend and pytest tests")
        assert fullstack > simple


# ---------------------------------------------------------------------------
# Phase 6: Outcome classification
# ---------------------------------------------------------------------------


class TestOutcomeClassification:
    def _make_context(self) -> MagicMock:
        ctx = MagicMock()
        from dataclasses import dataclass

        @dataclass
        class FakeAssembled:
            content: str = "system prompt"
            assembly_hash: str = "hash"

        ctx.ports.prompt_service.get_system_prompt.return_value = FakeAssembled()
        ctx.ports.llm.chat_stream_with_usage = AsyncMock()
        ctx.ports.llm.default_model = "test"
        ctx.ports.request_renderer = None
        ctx.correlation_context = None
        return ctx

    async def test_passed_validation_outcome_success(self):
        from squadops.cycles.task_outcome import TaskOutcome

        handler = DevelopmentDevelopHandler()
        ctx = self._make_context()

        # LLM returns good artifacts matching expected
        content = '```python:models.py\nclass RunEvent:\n    pass\n```'
        resp = MagicMock()
        resp.content = content
        resp.tokens_per_second = None
        resp.prompt_tokens = 10
        resp.completion_tokens = 20
        resp.total_tokens = 30
        ctx.ports.llm.chat_stream_with_usage.return_value = resp

        inputs = {
            "prd": "Build models",
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
            "acceptance_criteria": [],
            "artifact_contents": {},
            "resolved_config": {"output_validation": True},
        }

        result = await handler.handle(ctx, inputs)

        assert result.success is True
        assert result.outputs["outcome_class"] == TaskOutcome.SUCCESS

    async def test_failed_validation_outcome_semantic_failure(self):
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        handler = DevelopmentDevelopHandler()
        ctx = self._make_context()

        # LLM returns wrong file (not matching expected)
        content = '```python:wrong.py\nx = 1\n```'
        resp = MagicMock()
        resp.content = content
        resp.tokens_per_second = None
        resp.prompt_tokens = 10
        resp.completion_tokens = 20
        resp.total_tokens = 30
        ctx.ports.llm.chat_stream_with_usage.return_value = resp

        inputs = {
            "prd": "Build models",
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
            "acceptance_criteria": [],
            "artifact_contents": {},
            "resolved_config": {
                "output_validation": True,
                "max_self_eval_passes": 0,
            },
        }

        result = await handler.handle(ctx, inputs)

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        assert result.outputs["failure_classification"] == FailureClassification.WORK_PRODUCT
        assert "validation_result" in result.outputs


# ---------------------------------------------------------------------------
# Phase 7: Self-eval helpers
# ---------------------------------------------------------------------------


class TestBuildSelfEvalPrompt:
    async def test_includes_validation_summary(self):
        v = ValidationResult(
            passed=False, summary="Missing files: models.py",
            missing_components=["file:models.py"],
        )
        prompt = _CycleTaskHandler._build_self_eval_prompt(v, [_art("utils.py")])

        assert "Missing files: models.py" in prompt

    async def test_includes_missing_components(self):
        v = ValidationResult(
            passed=False, summary="test",
            missing_components=["file:models.py", "file:routes.py"],
        )
        prompt = _CycleTaskHandler._build_self_eval_prompt(v, [])

        assert "file:models.py" in prompt
        assert "file:routes.py" in prompt

    async def test_includes_already_produced_files(self):
        v = ValidationResult(passed=False, summary="test")
        prompt = _CycleTaskHandler._build_self_eval_prompt(v, [_art("utils.py")])

        assert "utils.py" in prompt


class TestMergeArtifacts:
    async def test_adds_new_files(self):
        evidence: dict = {}
        result = _CycleTaskHandler._merge_artifacts(
            [_art("a.py")], [_art("b.py")], evidence
        )

        assert len(result) == 2
        names = [a["name"] for a in result]
        assert "a.py" in names
        assert "b.py" in names

    async def test_replaces_same_name(self):
        evidence: dict = {}
        result = _CycleTaskHandler._merge_artifacts(
            [_art("a.py", content="old")],
            [_art("a.py", content="new")],
            evidence,
        )

        assert len(result) == 1
        assert result[0]["content"] == "new"

    async def test_records_in_evidence(self):
        evidence: dict = {}
        _CycleTaskHandler._merge_artifacts(
            [_art("a.py", content="old")],
            [_art("a.py", content="new"), _art("b.py")],
            evidence,
        )

        log = evidence["self_eval_merge_log"]
        assert len(log) == 2
        replaced = next(e for e in log if e["action"] == "replaced")
        assert replaced["name"] == "a.py"
        added = next(e for e in log if e["action"] == "added")
        assert added["name"] == "b.py"


# ---------------------------------------------------------------------------
# Phase 7b: Self-eval loop integration
# ---------------------------------------------------------------------------


class TestSelfEvalLoop:
    def _make_context(self) -> MagicMock:
        from dataclasses import dataclass

        @dataclass
        class FakeAssembled:
            content: str = "system prompt"
            assembly_hash: str = "hash"

        ctx = MagicMock()
        ctx.ports.prompt_service.get_system_prompt.return_value = FakeAssembled()
        ctx.ports.llm.chat_stream_with_usage = AsyncMock()
        ctx.ports.llm.default_model = "test"
        ctx.ports.request_renderer = None
        ctx.correlation_context = None
        return ctx

    async def test_self_eval_fires_and_fixes(self):
        """Self-eval produces the missing file, validation passes on retry."""
        handler = DevelopmentDevelopHandler()
        ctx = self._make_context()

        # First call: missing models.py, produces wrong.py
        resp1 = MagicMock()
        resp1.content = '```python:wrong.py\nx = 1\n```'
        resp1.tokens_per_second = None
        resp1.prompt_tokens = 10
        resp1.completion_tokens = 20
        resp1.total_tokens = 30

        # Self-eval call: produces models.py
        resp2 = MagicMock()
        resp2.content = '```python:models.py\nclass RunEvent: pass\n```'
        resp2.tokens_per_second = None
        resp2.prompt_tokens = 10
        resp2.completion_tokens = 20
        resp2.total_tokens = 30

        ctx.ports.llm.chat_stream_with_usage.side_effect = [resp1, resp2]

        inputs = {
            "prd": "Build models",
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
            "acceptance_criteria": [],
            "artifact_contents": {},
            "resolved_config": {
                "output_validation": True,
                "max_self_eval_passes": 1,
            },
        }

        result = await handler.handle(ctx, inputs)

        # Should succeed after self-eval
        assert result.success is True
        artifact_names = [a["name"] for a in result.outputs["artifacts"]]
        assert "models.py" in artifact_names
        assert "wrong.py" in artifact_names  # Kept from first pass

    async def test_self_eval_skipped_when_zero(self):
        """max_self_eval_passes=0 skips self-eval, fails immediately."""
        handler = DevelopmentDevelopHandler()
        ctx = self._make_context()

        resp = MagicMock()
        resp.content = '```python:wrong.py\nx = 1\n```'
        resp.tokens_per_second = None
        resp.prompt_tokens = 10
        resp.completion_tokens = 20
        resp.total_tokens = 30
        ctx.ports.llm.chat_stream_with_usage.return_value = resp

        inputs = {
            "prd": "Build models",
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
            "acceptance_criteria": [],
            "artifact_contents": {},
            "resolved_config": {
                "output_validation": True,
                "max_self_eval_passes": 0,
            },
        }

        result = await handler.handle(ctx, inputs)

        assert result.success is False
        # Only 1 LLM call (no self-eval)
        assert ctx.ports.llm.chat_stream_with_usage.call_count == 1

    async def test_self_eval_bounded(self):
        """Self-eval stops after max_self_eval_passes even if still failing."""
        handler = DevelopmentDevelopHandler()
        ctx = self._make_context()

        # All responses produce wrong file
        bad_resp = MagicMock()
        bad_resp.content = '```python:wrong.py\nx = 1\n```'
        bad_resp.tokens_per_second = None
        bad_resp.prompt_tokens = 10
        bad_resp.completion_tokens = 20
        bad_resp.total_tokens = 30
        ctx.ports.llm.chat_stream_with_usage.return_value = bad_resp

        inputs = {
            "prd": "Build models",
            "subtask_focus": "Backend models",
            "expected_artifacts": ["models.py"],
            "acceptance_criteria": [],
            "artifact_contents": {},
            "resolved_config": {
                "output_validation": True,
                "max_self_eval_passes": 2,
            },
        }

        result = await handler.handle(ctx, inputs)

        assert result.success is False
        # 1 initial + 2 self-eval = 3 total calls
        assert ctx.ports.llm.chat_stream_with_usage.call_count == 3


# ---------------------------------------------------------------------------
# SIP-0086 closeout Fix #2: QA test-execution folded into outcome_class.
# Before this fix, QATestHandler emitted outcome_class=SUCCESS whenever
# test files were present, even when pytest collected zero tests or
# actual tests failed. This hid real build failures from the correction
# protocol. See cycle cyc_6483883fe4dd for the field-observed regression.
# ---------------------------------------------------------------------------


class TestQATestExecutionFoldsIntoOutcome:
    def _make_context(self) -> MagicMock:
        from dataclasses import dataclass

        ctx = MagicMock()

        @dataclass
        class FakeAssembled:
            content: str = "system prompt"
            assembly_hash: str = "hash"

        ctx.ports.prompt_service.get_system_prompt.return_value = FakeAssembled()
        ctx.ports.llm.chat_stream_with_usage = AsyncMock()
        ctx.ports.llm.default_model = "test"
        ctx.ports.request_renderer = None
        ctx.correlation_context = None
        return ctx

    def _mock_llm_test_output(self, ctx: MagicMock) -> None:
        """Have Eve emit a plausible test file so artifact validation passes.

        Content must clear _STUB_THRESHOLD_BYTES (100) so the file is not
        flagged as a stub by the legacy QA validator.
        """
        content = (
            "```python:tests/test_sample.py\n"
            "import pytest\n"
            "\n"
            "def test_smoke():\n"
            "    assert 1 + 1 == 2\n"
            "\n"
            "def test_another():\n"
            "    assert isinstance([], list)\n"
            "\n"
            "def test_more():\n"
            "    assert len('abc') == 3\n"
            "```"
        )
        resp = MagicMock()
        resp.content = content
        resp.tokens_per_second = None
        resp.prompt_tokens = 10
        resp.completion_tokens = 20
        resp.total_tokens = 30
        ctx.ports.llm.chat_stream_with_usage.return_value = resp

    def _patched_test_suite(self, handler: QATestHandler, result_kwargs: dict) -> None:
        """Monkeypatch _run_test_suite to return a controlled RunTestsResult."""
        from squadops.capabilities.handlers.test_runner import RunTestsResult

        fake_result = RunTestsResult(**result_kwargs)
        fake_report = {
            "name": "test_report.md",
            "content": "mock report",
            "media_type": "text/markdown",
            "type": "test_report",
        }

        async def _fake_run_test_suite(capability, sources, extracted):
            return fake_result, fake_report

        handler._run_test_suite = _fake_run_test_suite  # type: ignore[assignment]

    def _qa_inputs(self) -> dict[str, Any]:
        return {
            "prd": "Build and test a trivial module",
            "artifact_contents": {"sample.py": "def f():\n    return 1\n"},
            "resolved_config": {
                "output_validation": True,
                "max_self_eval_passes": 0,
                "dev_capability": "python_cli",
            },
        }

    async def test_tests_pass_yields_success(self) -> None:
        from squadops.cycles.task_outcome import TaskOutcome

        handler = QATestHandler()
        ctx = self._make_context()
        self._mock_llm_test_output(ctx)
        self._patched_test_suite(
            handler,
            {"executed": True, "exit_code": 0, "test_file_count": 1, "source_file_count": 1},
        )

        result = await handler.handle(ctx, self._qa_inputs())

        assert result.success is True
        assert result.outputs["outcome_class"] == TaskOutcome.SUCCESS
        assert result.outputs["test_result"]["tests_passed"] is True
        # When outcome is SUCCESS the handler does not set failure_classification
        assert "failure_classification" not in result.outputs

    async def test_tests_fail_yields_semantic_failure(self) -> None:
        from squadops.cycles.task_outcome import FailureClassification, TaskOutcome

        handler = QATestHandler()
        ctx = self._make_context()
        self._mock_llm_test_output(ctx)
        # exit 1 = tests collected but some failed
        self._patched_test_suite(
            handler,
            {"executed": True, "exit_code": 1, "test_file_count": 1, "source_file_count": 1},
        )

        result = await handler.handle(ctx, self._qa_inputs())

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        assert result.outputs["failure_classification"] == FailureClassification.WORK_PRODUCT
        val = result.outputs["validation_result"]
        checks = val["checks"]
        tests_pass_check = next(c for c in checks if c["check"] == "tests_pass")
        assert tests_pass_check["passed"] is False
        assert tests_pass_check["exit_code"] == 1
        assert any("tests_failed:exit_1" in m for m in val["missing_components"])
        assert "Tests failed" in val["summary"]

    async def test_tests_not_collected_yields_semantic_failure(self) -> None:
        """Exit 5 (no tests collected — e.g., import errors) must fail the QA task.

        This is the exact regression from cyc_6483883fe4dd: Eve produced test
        files with broken relative imports; pytest collected zero tests and
        returned exit 5, yet QATestHandler reported outcome_class=success.
        """
        from squadops.cycles.task_outcome import TaskOutcome

        handler = QATestHandler()
        ctx = self._make_context()
        self._mock_llm_test_output(ctx)
        self._patched_test_suite(
            handler,
            {"executed": True, "exit_code": 5, "test_file_count": 1, "source_file_count": 5},
        )

        result = await handler.handle(ctx, self._qa_inputs())

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        val = result.outputs["validation_result"]
        assert any("tests_failed:exit_5" in m for m in val["missing_components"])

    async def test_tests_not_executed_yields_semantic_failure(self) -> None:
        from squadops.cycles.task_outcome import TaskOutcome

        handler = QATestHandler()
        ctx = self._make_context()
        self._mock_llm_test_output(ctx)
        self._patched_test_suite(
            handler,
            {"executed": False, "error": "runner_missing_pytest"},
        )

        result = await handler.handle(ctx, self._qa_inputs())

        assert result.success is False
        assert result.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
        val = result.outputs["validation_result"]
        assert any(
            "tests_not_executed:runner_missing_pytest" in m
            for m in val["missing_components"]
        )

    async def test_validation_disabled_preserves_legacy_pass(self) -> None:
        """When output_validation is off, test failures do NOT fail the handler.

        This keeps SIP-0086 strictly opt-in. Profiles with output_validation=False
        retain pre-SIP-0086 behavior.
        """
        from squadops.cycles.task_outcome import TaskOutcome

        handler = QATestHandler()
        ctx = self._make_context()
        self._mock_llm_test_output(ctx)
        self._patched_test_suite(
            handler,
            {"executed": True, "exit_code": 5, "test_file_count": 1, "source_file_count": 1},
        )

        inputs = self._qa_inputs()
        inputs["resolved_config"]["output_validation"] = False

        result = await handler.handle(ctx, inputs)

        assert result.success is True
        assert result.outputs["outcome_class"] == TaskOutcome.SUCCESS
