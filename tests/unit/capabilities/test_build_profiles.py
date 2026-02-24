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
