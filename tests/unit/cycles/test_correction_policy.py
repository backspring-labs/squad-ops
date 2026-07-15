"""Tests for the deterministic correction-path policy guard (#447)."""

from __future__ import annotations

import pytest

from squadops.cycles.correction_policy import resolve_correction_path

pytestmark = [pytest.mark.domain_contracts]

DEFAULTS = {"required_checks": ["frontend_build", "tests_pass", "required_files"]}


def _evidence(checks):
    return {"validation_result": {"checks": checks}}


class TestResolveCorrectionPath:
    def test_continue_with_executed_failed_required_escalates_to_patch(self):
        """The attempt-3.6 case: frontend_build ran and failed on a real JSX
        syntax error, yet the lead chose continue with budget unspent."""
        ev = _evidence(
            [
                {"check": "frontend_build", "passed": False},  # ran path omits `executed`
                {"check": "non_stub_files", "passed": True},
            ]
        )
        res = resolve_correction_path("continue", ev, DEFAULTS)
        assert res.path == "patch"
        assert res.overridden_from == "continue"
        assert res.failed_required_checks == ("frontend_build",)

    def test_continue_with_env_skip_failures_stands(self):
        """The attempt-3.5 case: checks failed as environment problems
        (executed: False) — repair can't fix harness config; continue is right."""
        ev = _evidence(
            [
                {"check": "frontend_build", "executed": False, "reason": "no_package_json"},
                {"check": "tests_pass", "executed": False, "passed": False},
            ]
        )
        res = resolve_correction_path("continue", ev, DEFAULTS)
        assert res.path == "continue"
        assert res.overridden_from is None

    def test_continue_with_only_optional_failures_stands(self):
        ev = _evidence([{"check": "no_stub_fallback_tests", "passed": False}])
        res = resolve_correction_path("continue", ev, DEFAULTS)
        assert res.path == "continue"

    def test_patch_passes_through_untouched(self):
        ev = _evidence([{"check": "frontend_build", "passed": False}])
        res = resolve_correction_path("patch", ev, DEFAULTS)
        assert res.path == "patch"
        assert res.overridden_from is None

    def test_abort_is_never_overridden(self):
        ev = _evidence([{"check": "frontend_build", "passed": False}])
        res = resolve_correction_path("abort", ev, DEFAULTS)
        assert res.path == "abort"
        assert res.overridden_from is None

    def test_no_required_checks_configured_stands(self):
        ev = _evidence([{"check": "frontend_build", "passed": False}])
        res = resolve_correction_path("continue", ev, {"required_checks": []})
        assert res.path == "continue"

    def test_malformed_evidence_stands(self):
        for ev in ({}, {"validation_result": None}, _evidence([None, "junk", {}])):
            res = resolve_correction_path("continue", ev, DEFAULTS)
            assert res.path == "continue", ev

    def test_mixed_executed_and_skipped_failures_reports_only_executed(self):
        ev = _evidence(
            [
                {"check": "tests_pass", "executed": True, "passed": False, "exit_code": 1},
                {"check": "frontend_build", "executed": False, "reason": "npm_missing"},
            ]
        )
        res = resolve_correction_path("continue", ev, DEFAULTS)
        assert res.path == "patch"
        assert res.failed_required_checks == ("tests_pass",)
