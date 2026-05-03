"""Unit tests for build profile registry (SIP-0071).

Tests BuildProfile dataclass, get_profile() lookup, constants, and
profile immutability.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.build_profiles import (
    ARTIFACT_MODE_MULTI_FILE,
    BUILD_PROFILES,
    QA_HANDOFF_REQUIRED_SECTIONS,
    ROUTING_BUILDER_PRESENT,
    ROUTING_FALLBACK_NO_BUILDER,
    BuildProfile,
    get_profile,
)

pytestmark = [pytest.mark.domain_capabilities]


class TestGetProfile:
    def test_returns_correct_profile(self):
        profile = get_profile("python_cli_builder")
        assert profile.name == "python_cli_builder"

    def test_raises_value_error_for_unknown_name(self):
        with pytest.raises(ValueError, match="Unknown build profile"):
            get_profile("nonexistent_profile")

    def test_error_message_lists_available_profiles(self):
        with pytest.raises(ValueError, match="python_cli_builder"):
            get_profile("bad_name")


class TestBuildProfileImmutability:
    def test_frozen_dataclass_rejects_mutation(self):
        profile = get_profile("python_cli_builder")
        with pytest.raises(AttributeError):
            profile.name = "hacked"

    def test_frozen_dataclass_rejects_field_assignment(self):
        profile = get_profile("python_cli_builder")
        with pytest.raises(AttributeError):
            profile.artifact_output_mode = "single_file"


class TestPythonCliBuilderProfile:
    def test_required_files_include_dockerfile(self):
        profile = get_profile("python_cli_builder")
        assert "Dockerfile" in profile.required_files

    def test_required_files_include_requirements_txt(self):
        profile = get_profile("python_cli_builder")
        assert "requirements.txt" in profile.required_files

    def test_required_files_include_main_entry(self):
        profile = get_profile("python_cli_builder")
        assert "__main__.py" in profile.required_files

    def test_artifact_output_mode_is_multi_file(self):
        profile = get_profile("python_cli_builder")
        assert profile.artifact_output_mode == ARTIFACT_MODE_MULTI_FILE

    def test_has_system_prompt_template(self):
        profile = get_profile("python_cli_builder")
        assert len(profile.system_prompt_template) > 0


class TestQAHandoffConstants:
    def test_required_sections_has_how_to_run(self):
        assert "## How to Run" in QA_HANDOFF_REQUIRED_SECTIONS

    def test_required_sections_has_how_to_test(self):
        assert "## How to Test" in QA_HANDOFF_REQUIRED_SECTIONS

    def test_required_sections_has_expected_behavior(self):
        assert "## Expected Behavior" in QA_HANDOFF_REQUIRED_SECTIONS

    def test_required_sections_count(self):
        assert len(QA_HANDOFF_REQUIRED_SECTIONS) == 3


class TestRoutingConstants:
    def test_routing_builder_present_is_string(self):
        assert isinstance(ROUTING_BUILDER_PRESENT, str)
        assert ROUTING_BUILDER_PRESENT == "builder_role_present"

    def test_routing_fallback_is_string(self):
        assert isinstance(ROUTING_FALLBACK_NO_BUILDER, str)
        assert ROUTING_FALLBACK_NO_BUILDER == "fallback_no_builder"


class TestStaticWebBuilderProfile:
    def test_loads_by_name(self):
        profile = get_profile("static_web_builder")
        assert profile.name == "static_web_builder"

    def test_required_files_include_index_html(self):
        profile = get_profile("static_web_builder")
        assert "index.html" in profile.required_files

    def test_required_files_include_styles_css(self):
        profile = get_profile("static_web_builder")
        assert "styles.css" in profile.required_files

    def test_required_files_include_main_js(self):
        profile = get_profile("static_web_builder")
        assert "main.js" in profile.required_files

    def test_artifact_output_mode_is_multi_file(self):
        profile = get_profile("static_web_builder")
        assert profile.artifact_output_mode == ARTIFACT_MODE_MULTI_FILE

    def test_has_system_prompt_template(self):
        profile = get_profile("static_web_builder")
        assert len(profile.system_prompt_template) > 0


class TestWebAppBuilderProfile:
    def test_loads_by_name(self):
        profile = get_profile("web_app_builder")
        assert profile.name == "web_app_builder"

    def test_required_files_include_app_py(self):
        profile = get_profile("web_app_builder")
        assert "app.py" in profile.required_files

    def test_required_files_include_index_html(self):
        profile = get_profile("web_app_builder")
        assert "index.html" in profile.required_files

    def test_required_files_include_requirements(self):
        profile = get_profile("web_app_builder")
        assert "requirements.txt" in profile.required_files

    def test_has_system_prompt_template(self):
        profile = get_profile("web_app_builder")
        assert len(profile.system_prompt_template) > 0


class TestFullstackFastapiReactProfile:
    def test_loads_by_name(self):
        profile = get_profile("fullstack_fastapi_react")
        assert profile.name == "fullstack_fastapi_react"

    def test_required_files_include_dockerfile(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "Dockerfile" in profile.required_files

    def test_docker_compose_is_optional(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "docker-compose.yaml" in profile.optional_files

    def test_required_files_include_qa_handoff(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "qa_handoff.md" in profile.required_files

    def test_optional_files_include_start_sh(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "start.sh" in profile.optional_files

    def test_has_system_prompt_template(self):
        profile = get_profile("fullstack_fastapi_react")
        assert "fullstack" in profile.system_prompt_template.lower()

    def test_validation_rules_mention_multi_stage(self):
        profile = get_profile("fullstack_fastapi_react")
        assert any("multi-stage" in r for r in profile.validation_rules)

    def test_artifact_output_mode_is_multi_file(self):
        profile = get_profile("fullstack_fastapi_react")
        assert profile.artifact_output_mode == ARTIFACT_MODE_MULTI_FILE


class TestBuildProfilesRegistry:
    def test_registry_has_four_profiles(self):
        assert len(BUILD_PROFILES) == 4

    def test_all_profiles_are_build_profile_instances(self):
        for name, profile in BUILD_PROFILES.items():
            assert isinstance(profile, BuildProfile), f"{name} is not a BuildProfile"

    def test_all_profiles_have_qa_handoff_expectations(self):
        for name, profile in BUILD_PROFILES.items():
            assert len(profile.qa_handoff_expectations) > 0, (
                f"{name} has no qa_handoff_expectations"
            )


class TestProfileSourceOfTruthInvariants:
    """Issue #92: required_files/optional_files are the single source of truth.

    The narrative `system_prompt_template` must NOT enumerate filenames; the
    full prompt seen by the LLM is composed via `full_system_prompt` from
    the validator's required/optional tuples. These invariants catch any
    re-introduced drift between the prompt the LLM sees and the validator
    that grades its output.
    """

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_qa_handoff_md_in_required_files(self, name, profile):
        """The validator unconditionally rejects builder output without
        qa_handoff.md (cycle_tasks.py:_validate_builder_output). Every
        profile must list it in required_files so the prompt asks for it.
        """
        assert "qa_handoff.md" in profile.required_files, (
            f"{name}: validator demands qa_handoff.md but profile doesn't list it"
        )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_required_and_optional_disjoint(self, name, profile):
        """A filename must appear in exactly one of required_files or
        optional_files. Duplicates were a real source of LLM confusion.
        """
        required_set = set(profile.required_files)
        optional_set = set(profile.optional_files)
        overlap = required_set & optional_set
        assert not overlap, f"{name}: files appear in both required and optional: {sorted(overlap)}"

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_full_system_prompt_lists_every_required_file(self, name, profile):
        """The composed system prompt the LLM sees must mention every
        required file by name. Otherwise the LLM is being graded on a file
        it was never asked to produce.
        """
        prompt = profile.full_system_prompt
        for required in profile.required_files:
            assert required in prompt, (
                f"{name}: required file {required!r} not mentioned in full_system_prompt"
            )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_full_system_prompt_lists_every_optional_file(self, name, profile):
        """Optional files should be advertised so the LLM knows it MAY
        produce them. Without this, optional files become invisible.
        """
        prompt = profile.full_system_prompt
        for optional in profile.optional_files:
            assert optional in prompt, (
                f"{name}: optional file {optional!r} not mentioned in full_system_prompt"
            )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_narrative_template_does_not_enumerate_filenames(self, name, profile):
        """The narrative `system_prompt_template` must NOT enumerate
        filenames — the file list comes from required_files/optional_files
        via `full_system_prompt`. If a filename leaks into the narrative,
        the prompt has two sources of truth again.

        Heuristic: any token containing a recognized file extension or
        a literal known structural file (Dockerfile) appearing in the
        narrative template is a violation. We allow extensions only inside
        backticked code-block languages (e.g. ```python:foo) by stripping
        those before scanning.
        """
        import re

        narrative = profile.system_prompt_template
        # Strip backticked code/format tokens — those describe the output
        # FORMAT (```dockerfile:Dockerfile), not enumerate which files.
        # We only care about filenames that appear as literal prose.
        stripped = re.sub(r"`[^`]*`", "", narrative)

        # Forbidden patterns: anything that looks like a file with an
        # extension, or known extension-less structural files.
        forbidden = []
        # Simple file-with-extension regex (word chars + dot + 2-5 letter ext)
        for match in re.finditer(r"\b[\w./-]+\.[a-zA-Z]{2,5}\b", stripped):
            forbidden.append(match.group(0))
        for sentinel in ("Dockerfile", "Makefile"):
            if sentinel in stripped:
                forbidden.append(sentinel)

        assert not forbidden, (
            f"{name}: narrative system_prompt_template enumerates filenames "
            f"{forbidden!r}; move them to required_files/optional_files so the "
            f"prompt and validator share one source of truth (issue #92)."
        )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_full_system_prompt_lists_qa_handoff_sections(self, name, profile):
        """The composed prompt must surface every required QA handoff
        section. Otherwise the LLM doesn't know what shape qa_handoff.md
        must take.
        """
        prompt = profile.full_system_prompt
        for section in profile.qa_handoff_expectations:
            assert section in prompt, (
                f"{name}: qa_handoff section {section!r} missing from full_system_prompt"
            )

    @pytest.mark.parametrize("name,profile", list(BUILD_PROFILES.items()))
    def test_qa_handoff_sections_marked_non_negotiable(self, name, profile):
        """Cycle-1 evidence (cyc_11367982fd06): when the plan task description
        names different qa_handoff sections than the validator requires, Bob
        follows the more specific user-prompt task and the validator rejects
        on a missing canonical section.

        The system prompt MUST frame the validator's required sections as
        non-negotiable so the user prompt's task description cannot quietly
        override them. We assert on the explicit framing language and on
        the worked-skeleton example.
        """
        prompt = profile.full_system_prompt
        # Headline framing: the section list is mandatory, not advisory.
        assert "NON-NEGOTIABLE" in prompt, (
            f"{name}: qa_handoff section header lost the NON-NEGOTIABLE marker"
        )
        assert "mandatory" in prompt.lower(), (
            f"{name}: missing 'mandatory' framing for qa_handoff sections"
        )
        # Tells Bob extra task-requested sections are welcome ON TOP of required.
        assert "additional sections" in prompt.lower(), (
            f"{name}: prompt should explicitly allow additional sections "
            "beyond the required set, otherwise Bob may drop task-specific "
            "sections in favor of the required ones"
        )
        # Worked skeleton showing exact heading text in a fenced qa_handoff block.
        assert "```markdown:qa_handoff.md" in prompt, (
            f"{name}: prompt missing the worked qa_handoff.md skeleton example"
        )


class TestSystemPromptForFiles:
    """Issue #107: when framing decomposes builder work, the active task's
    expected_artifacts is the source of truth for what must be emitted.
    `system_prompt_for_files(scope)` produces a prompt scoped to that
    subset; `full_system_prompt` (no scope) preserves the legacy
    profile-wide behavior for tasks framing didn't decompose."""

    def _profile(self):
        from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES

        return BUILD_PROFILES["fullstack_fastapi_react"]

    def test_full_system_prompt_unchanged_by_default(self):
        # Legacy callers that read full_system_prompt should still get the
        # profile-wide prompt with every required file + qa_handoff block.
        profile = self._profile()
        prompt = profile.full_system_prompt
        for required in profile.required_files:
            assert f"`{required}`" in prompt
        assert "qa_handoff.md required sections (NON-NEGOTIABLE)" in prompt

    def test_scoped_prompt_lists_only_task_required_files(self):
        # Cycle 3 task 8 scope: manifests + scripts, NO qa_handoff.
        profile = self._profile()
        scope = ("package.json", "vite.config.js", "Dockerfile")
        prompt = profile.system_prompt_for_files(scope)

        for name in scope:
            assert f"`{name}`" in prompt
        # Profile-required qa_handoff is intentionally absent — task 9 owns it.
        assert "`qa_handoff.md`" not in prompt
        assert "qa_handoff.md required sections" not in prompt
        assert "```markdown:qa_handoff.md" not in prompt

    def test_scoped_prompt_includes_qa_handoff_block_when_in_scope(self):
        # Cycle 3 task 9 scope: qa_handoff documentation only.
        profile = self._profile()
        prompt = profile.system_prompt_for_files(("qa_handoff.md",))

        assert "`qa_handoff.md`" in prompt
        assert "qa_handoff.md required sections (NON-NEGOTIABLE)" in prompt
        assert "```markdown:qa_handoff.md" in prompt
        # And the OTHER profile-required files are NOT listed when not in scope.
        assert "`Dockerfile`" not in prompt

    def test_none_scope_falls_back_to_profile_required(self):
        # Tasks framing didn't decompose pass through with no scope.
        profile = self._profile()
        prompt_none = profile.system_prompt_for_files(None)
        prompt_full = profile.full_system_prompt
        assert prompt_none == prompt_full

    def test_empty_scope_falls_back_to_profile_required(self):
        profile = self._profile()
        prompt_empty = profile.system_prompt_for_files(())
        prompt_full = profile.full_system_prompt
        assert prompt_empty == prompt_full
