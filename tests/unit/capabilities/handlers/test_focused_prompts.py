"""Tests for focused prompt paths in build handlers (SIP-0086 Phase 4a/4b)."""

from __future__ import annotations

from typing import Any

import pytest

from squadops.capabilities.handlers.cycle_tasks import (
    DevelopmentDevelopHandler,
    QATestHandler,
)


# ---------------------------------------------------------------------------
# DevelopmentDevelopHandler focused prompt (Phase 4a)
# ---------------------------------------------------------------------------


class TestDevFocusedPrompt:
    def _make_inputs(self, **overrides) -> dict[str, Any]:
        defaults = {
            "prd": "Build a group run app with FastAPI and React.",
            "subtask_focus": "Backend models",
            "subtask_description": "Create Pydantic models for RunEvent and Participant.",
            "expected_artifacts": ["backend/models.py", "backend/repository.py"],
            "acceptance_criteria": [
                "RunEvent has id and title fields",
                "Repository supports CRUD",
            ],
            "artifact_contents": {
                "strategy_analysis.md": "Strategy content here",
            },
            "resolved_config": {},
        }
        defaults.update(overrides)
        return defaults

    def test_focused_prompt_includes_subtask_focus(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "## Build Task: Backend models" in prompt

    def test_focused_prompt_includes_description(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "Create Pydantic models for RunEvent and Participant" in prompt

    def test_focused_prompt_includes_expected_output_files(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "- `backend/models.py`" in prompt
        assert "- `backend/repository.py`" in prompt

    def test_focused_prompt_includes_acceptance_criteria(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "### Acceptance Criteria" in prompt
        assert "- RunEvent has id and title fields" in prompt
        assert "- Repository supports CRUD" in prompt

    def test_focused_prompt_includes_prior_artifacts(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "### Prior Artifacts" in prompt
        assert "strategy_analysis.md" in prompt
        assert "Strategy content here" in prompt

    def test_focused_prompt_includes_prd(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "Build a group run app" in prompt

    def test_focused_prompt_no_acceptance_criteria_omits_section(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(
            self._make_inputs(acceptance_criteria=[])
        )

        assert "### Acceptance Criteria" not in prompt

    def test_focused_prompt_no_prior_artifacts_omits_section(self):
        handler = DevelopmentDevelopHandler()
        prompt = handler._build_focused_prompt(
            self._make_inputs(artifact_contents={})
        )

        assert "### Prior Artifacts" not in prompt

    def test_rc6_legacy_prompt_has_no_subtask_fields(self):
        """RC-6: When subtask_focus is absent, focused path is not activated."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {}
        # Legacy prompt path
        prompt = handler._build_user_prompt(
            prd="Build an app",
            prior_outputs=None,
        )

        assert "## Build Task:" not in prompt
        assert "Expected Output Files" not in prompt


# ---------------------------------------------------------------------------
# QATestHandler focused prompt (Phase 4b)
# ---------------------------------------------------------------------------


class TestQAFocusedPrompt:
    def _make_inputs(self, **overrides) -> dict[str, Any]:
        defaults = {
            "prd": "Build a group run app.",
            "subtask_focus": "Backend tests",
            "subtask_description": "Write pytest tests for API endpoints.",
            "expected_artifacts": ["tests/test_api.py"],
            "acceptance_criteria": ["Tests cover all 5 endpoints"],
            "artifact_contents": {
                "backend/main.py": "from fastapi import FastAPI\napp = FastAPI()",
            },
            "resolved_config": {},
        }
        defaults.update(overrides)
        return defaults

    def test_focused_prompt_includes_qa_task_focus(self):
        handler = QATestHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "## QA Task: Backend tests" in prompt

    def test_focused_prompt_includes_acceptance_criteria(self):
        handler = QATestHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "- Tests cover all 5 endpoints" in prompt

    def test_focused_prompt_includes_source_artifacts(self):
        handler = QATestHandler()
        prompt = handler._build_focused_prompt(self._make_inputs())

        assert "backend/main.py" in prompt
        assert "FastAPI" in prompt

    def test_rc6_legacy_prompt_has_no_subtask_fields(self):
        """RC-6: When subtask_focus is absent, focused path is not activated."""
        handler = QATestHandler()
        prompt = handler._build_user_prompt(
            prd="Build an app",
            prior_outputs=None,
        )

        assert "## QA Task:" not in prompt
        assert "Expected Output Files" not in prompt
