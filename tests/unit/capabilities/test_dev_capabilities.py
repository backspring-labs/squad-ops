"""Unit tests for development capability registry (SIP-0072 Phase 1).

Tests DevelopmentCapability dataclass, get_capability() lookup, constants,
and capability immutability. Mirrors test_build_profiles.py pattern.
"""
from __future__ import annotations

import pytest

from squadops.capabilities.dev_capabilities import (
    DEV_CAPABILITIES,
    TEST_FRAMEWORK_BOTH,
    TEST_FRAMEWORK_PYTEST,
    TEST_FRAMEWORK_VITEST,
    DevelopmentCapability,
    get_capability,
)

pytestmark = [pytest.mark.domain_capabilities]


class TestGetCapability:
    def test_returns_correct_capability(self):
        cap = get_capability("python_cli")
        assert cap.name == "python_cli"

    def test_fullstack_capability(self):
        cap = get_capability("fullstack_fastapi_react")
        assert cap.name == "fullstack_fastapi_react"

    def test_python_api_capability(self):
        cap = get_capability("python_api")
        assert cap.name == "python_api"
        assert "FastAPI" in cap.system_prompt_supplement

    def test_react_app_capability(self):
        cap = get_capability("react_app")
        assert cap.name == "react_app"

    def test_raises_value_error_for_unknown_name(self):
        with pytest.raises(ValueError, match="Unknown development capability"):
            get_capability("nonexistent")

    def test_error_message_lists_available_capabilities(self):
        with pytest.raises(ValueError, match="python_cli"):
            get_capability("bad_name")


class TestCapabilityImmutability:
    def test_frozen_dataclass_rejects_mutation(self):
        cap = get_capability("python_cli")
        with pytest.raises(AttributeError):
            cap.name = "hacked"

    def test_frozen_dataclass_rejects_field_assignment(self):
        cap = get_capability("python_cli")
        with pytest.raises(AttributeError):
            cap.test_framework = "jest"


class TestPythonCliCapability:
    """Verifies D2 — python_cli reproduces current hardcoded behavior."""

    def test_system_prompt_contains_python_package(self):
        cap = get_capability("python_cli")
        assert "Python package" in cap.system_prompt_supplement

    def test_file_structure_guidance_contains_init_py(self):
        cap = get_capability("python_cli")
        assert "__init__.py" in cap.file_structure_guidance

    def test_file_structure_guidance_contains_relative_imports(self):
        cap = get_capability("python_cli")
        assert "RELATIVE imports" in cap.file_structure_guidance

    def test_file_structure_guidance_contains_main_entry(self):
        cap = get_capability("python_cli")
        assert "python -m" in cap.file_structure_guidance

    def test_test_framework_is_pytest(self):
        cap = get_capability("python_cli")
        assert cap.test_framework == TEST_FRAMEWORK_PYTEST

    def test_source_filter_is_py_only(self):
        cap = get_capability("python_cli")
        assert cap.source_filter == (".py",)

    def test_test_file_patterns(self):
        cap = get_capability("python_cli")
        assert "test_*.py" in cap.test_file_patterns
        assert "*_test.py" in cap.test_file_patterns


class TestFullstackCapability:
    def test_system_prompt_contains_backend_and_frontend(self):
        cap = get_capability("fullstack_fastapi_react")
        assert "backend/" in cap.system_prompt_supplement
        assert "frontend/" in cap.system_prompt_supplement

    def test_file_structure_guidance_contains_both_stacks(self):
        cap = get_capability("fullstack_fastapi_react")
        assert "backend/" in cap.file_structure_guidance
        assert "frontend/" in cap.file_structure_guidance

    def test_no_init_py_in_guidance(self):
        cap = get_capability("fullstack_fastapi_react")
        assert "__init__.py" not in cap.file_structure_guidance

    def test_test_framework_is_both(self):
        cap = get_capability("fullstack_fastapi_react")
        assert cap.test_framework == TEST_FRAMEWORK_BOTH

    def test_source_filter_includes_py_and_jsx(self):
        cap = get_capability("fullstack_fastapi_react")
        assert ".py" in cap.source_filter
        assert ".jsx" in cap.source_filter
        assert ".js" in cap.source_filter

    def test_test_file_patterns_union(self):
        cap = get_capability("fullstack_fastapi_react")
        # Python patterns
        assert "test_*.py" in cap.test_file_patterns
        # JS patterns
        assert "*.test.jsx" in cap.test_file_patterns

    def test_example_structure_has_both_dirs(self):
        cap = get_capability("fullstack_fastapi_react")
        assert "backend/" in cap.example_structure
        assert "frontend/" in cap.example_structure

    def test_test_prompt_mentions_both_frameworks(self):
        cap = get_capability("fullstack_fastapi_react")
        assert "pytest" in cap.test_prompt_supplement
        assert "vitest" in cap.test_prompt_supplement


class TestReactAppCapability:
    def test_test_framework_is_vitest(self):
        cap = get_capability("react_app")
        assert cap.test_framework == TEST_FRAMEWORK_VITEST

    def test_source_filter_is_js_jsx(self):
        cap = get_capability("react_app")
        assert ".js" in cap.source_filter
        assert ".jsx" in cap.source_filter
        assert ".py" not in cap.source_filter

    def test_test_file_patterns(self):
        cap = get_capability("react_app")
        assert "*.test.js" in cap.test_file_patterns
        assert "*.test.jsx" in cap.test_file_patterns
        assert "*.spec.js" in cap.test_file_patterns
        assert "*.spec.jsx" in cap.test_file_patterns


class TestFrameworkConstants:
    def test_pytest_constant(self):
        assert TEST_FRAMEWORK_PYTEST == "pytest"

    def test_vitest_constant(self):
        assert TEST_FRAMEWORK_VITEST == "vitest"

    def test_both_constant(self):
        assert TEST_FRAMEWORK_BOTH == "both"

    def test_all_capabilities_use_constants(self):
        valid = {TEST_FRAMEWORK_PYTEST, TEST_FRAMEWORK_VITEST, TEST_FRAMEWORK_BOTH}
        for name, cap in DEV_CAPABILITIES.items():
            assert cap.test_framework in valid, f"{name} uses invalid test_framework"


class TestRegistryCompleteness:
    def test_registry_has_four_capabilities(self):
        assert len(DEV_CAPABILITIES) == 4

    def test_all_are_capability_instances(self):
        for name, cap in DEV_CAPABILITIES.items():
            assert isinstance(cap, DevelopmentCapability), f"{name} is not a DevelopmentCapability"

    def test_all_have_non_empty_system_prompt_supplement(self):
        for name, cap in DEV_CAPABILITIES.items():
            assert len(cap.system_prompt_supplement) > 0, f"{name} has empty system_prompt_supplement"

    def test_all_have_non_empty_source_filter(self):
        for name, cap in DEV_CAPABILITIES.items():
            assert len(cap.source_filter) > 0, f"{name} has empty source_filter"

    def test_all_have_non_empty_test_file_patterns(self):
        for name, cap in DEV_CAPABILITIES.items():
            assert len(cap.test_file_patterns) > 0, f"{name} has empty test_file_patterns"
