"""Tests for focused prompt paths in build handlers (SIP-0086 Phase 4a/4b)."""

from __future__ import annotations

from typing import Any

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

    async def test_focused_prompt_includes_subtask_focus(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs())

        assert "## Build Task: Backend models" in prompt

    async def test_focused_prompt_includes_description(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs())

        assert "Create Pydantic models for RunEvent and Participant" in prompt

    async def test_focused_prompt_includes_expected_output_files(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs())

        assert "- `backend/models.py`" in prompt
        assert "- `backend/repository.py`" in prompt

    async def test_focused_prompt_includes_acceptance_criteria(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs())

        assert "### Acceptance Criteria" in prompt
        assert "- RunEvent has id and title fields" in prompt
        assert "- Repository supports CRUD" in prompt

    async def test_focused_prompt_includes_prior_artifacts(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs())

        assert "### Prior Artifacts" in prompt
        assert "strategy_analysis.md" in prompt
        assert "Strategy content here" in prompt

    async def test_focused_prompt_includes_prd(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs())

        assert "Build a group run app" in prompt

    async def test_focused_prompt_no_acceptance_criteria_omits_section(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs(acceptance_criteria=[]))

        assert "### Acceptance Criteria" not in prompt

    async def test_focused_prompt_no_prior_artifacts_omits_section(self):
        handler = DevelopmentDevelopHandler()
        prompt = await handler._build_focused_prompt(self._make_inputs(artifact_contents={}))

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


# ---------------------------------------------------------------------------
# Dev focused prompt — RENDERED path (#588)
# ---------------------------------------------------------------------------


class TestDevFocusedPromptRendered:
    """The rendered path is the one production uses, and it was the one carrying
    the defect: plan tasks always set ``subtask_focus``, so ``_build_focused_prompt``
    is the ONLY prompt a plan-driven dev task sees — and it previously omitted both
    the SIP-0099 fill-only instruction (wired only into the monolithic path a
    plan-driven cycle never takes) and the manifest-derived error seam.

    These drive the REAL renderer against the REAL asset files, so handler/asset
    drift — an undeclared variable, a renamed placeholder — fails here rather than
    silently rendering an empty section in production.
    """

    @staticmethod
    def _renderer():
        from adapters.prompts.factory import DEFAULT_TEMPLATES_PATH, create_prompt_asset_source
        from squadops.prompts.renderer import RequestTemplateRenderer

        return RequestTemplateRenderer(
            asset_source=create_prompt_asset_source(
                provider="filesystem", templates_path=DEFAULT_TEMPLATES_PATH
            )
        )

    def _inputs(self, **overrides) -> dict[str, Any]:
        defaults = {
            "prd": "Build a group run app.",
            "subtask_focus": "Backend routes",
            "subtask_description": "Implement the run endpoints.",
            "expected_artifacts": ["backend/routes.py"],
            "acceptance_criteria": [
                "Endpoints round-trip end to end.",
                {
                    "check": "function_defined",
                    "file": "backend/routes.py",
                    "name_prefix": "create_",
                    "min_count": 2,
                },
            ],
            "artifact_contents": {},
            "resolved_config": {"build_profile": "fullstack_fastapi_react"},
        }
        defaults.update(overrides)
        return defaults

    async def test_typed_criteria_render_as_expectations_not_dict_soup(self):
        """Bug caught: the initial author receives TypedChecks as `f"- {dict}"`
        repr soup, so exact expectations only ever reach it via the repair
        prompt — the #585 wall, on the dev role."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "fullstack_fastapi_react"}
        prompt = await handler._build_focused_prompt(self._inputs(), self._renderer())

        assert "Contract Expectations (authoritative" in prompt
        assert "'check': 'function_defined'" not in prompt, "typed criterion leaked as a dict repr"
        assert "{" not in prompt.split("### Context")[0].split("Contract Expectations")[1]
        # Narrative prose survives, demoted below the authoritative block.
        assert "Acceptance Criteria (narrative)" in prompt
        assert "Endpoints round-trip end to end." in prompt
        assert prompt.index("Contract Expectations") < prompt.index(
            "Acceptance Criteria (narrative)"
        )

    async def test_scaffolded_stack_gets_the_fill_only_instruction(self):
        """Bug caught: THE #588 defect — a plan-driven dev task is never told the
        scaffold surface is frozen, so it rewrites entry/model files (three frozen
        emissions in pf-37's seven dev tasks) and pays corrections to undo them."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "fullstack_fastapi_react"}
        prompt = await handler._build_focused_prompt(self._inputs(), self._renderer())

        assert "Fill-only" in prompt
        assert "frozen" in prompt.lower()
        assert "backend/main.py" in prompt

    async def test_error_contract_lines_reach_the_initial_author(self):
        """Bug caught: the ApiError raise convention reaches repairs but not the
        first author, so every roll re-emits `ApiError(status_code=, detail=)`,
        TypeErrors at request time, and 500s every error path past every typed
        check (pf-28/33/34, and pf-37's routes.py)."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "fullstack_fastapi_react"}
        inputs = self._inputs(
            error_contract=[
                "on failure raise `ApiError(code, message)` (imported from `.errors`)",
                "valid error codes: `run_not_found` → 404",
            ]
        )
        prompt = await handler._build_focused_prompt(inputs, self._renderer())

        assert "ERROR CONTRACT (authoritative" in prompt
        assert "ApiError(code, message)" in prompt
        assert "run_not_found` → 404" in prompt

    async def test_model_surface_lines_reach_the_initial_author(self):
        """pf-45: the field vocabulary reaches repairs but not the first author, so the
        dev guessed `pace` for the frozen model's `pace_target` and every POST /runs
        raised into a 500 — through import- and compile-level checks untouched."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "fullstack_fastapi_react"}
        inputs = self._inputs(
            model_surface=[
                "`backend/models.py` defines EXACTLY: `RunEvent(id, title, pace_target)`",
                "`backend/store.py` already defines `run_event_store` — import it",
            ]
        )
        prompt = await handler._build_focused_prompt(inputs, self._renderer())

        assert "MODEL SURFACE (authoritative" in prompt
        assert "pace_target" in prompt
        assert "run_event_store" in prompt

    async def test_non_scaffolded_stack_omits_scaffold_sections(self):
        """Bug caught: rendering fill-only/error-contract unconditionally would
        instruct an unscaffolded cycle to preserve a skeleton that isn't there."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "python_cli"}
        inputs = self._inputs(resolved_config={"build_profile": "python_cli"})
        prompt = await handler._build_focused_prompt(inputs, self._renderer())

        assert "Fill-only" not in prompt
        assert "ERROR CONTRACT" not in prompt
        assert "## Build Task: Backend routes" in prompt

    async def test_no_typed_criteria_omits_the_expectations_block(self):
        """Bug caught: a dangling authoritative header with nothing under it
        reads as 'there are no requirements'."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "fullstack_fastapi_react"}
        inputs = self._inputs(acceptance_criteria=["Just prose."])
        prompt = await handler._build_focused_prompt(inputs, self._renderer())

        assert "Contract Expectations" not in prompt
        assert "Just prose." in prompt

    async def test_prior_artifacts_carry_the_do_not_reproduce_instruction(self):
        """Bug caught: dropping the prior-artifacts framing makes the author
        re-emit files it was only meant to read interfaces from."""
        handler = DevelopmentDevelopHandler()
        handler._resolved_config = {"build_profile": "fullstack_fastapi_react"}
        inputs = self._inputs(artifact_contents={"backend/models.py": "class RunEvent: ..."})
        prompt = await handler._build_focused_prompt(inputs, self._renderer())

        assert "do not reproduce" in prompt.lower()
        assert "class RunEvent: ..." in prompt
