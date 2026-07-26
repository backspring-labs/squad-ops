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


class TestRewindAnchor:
    """pf-45: a work_product rewind is escalated to patch while the repair slot is unspent.

    Rewind is implemented as run death, so accepting it discards every remaining
    correction attempt. pf-45's analyzer correctly diagnosed a one-token fill-slot defect
    (``pace`` for the frozen model's ``pace_target``); the lead called it "systemic
    contract violations", chose rewind, and the run died with four of five attempts
    unused — on the exact failure shape the repair path was built for.
    """

    def test_work_product_rewind_becomes_patch(self):
        resolution = resolve_correction_path("rewind", {}, {}, classification="work_product")

        assert resolution.path == "patch"
        assert resolution.overridden_from == "rewind"
        assert resolution.override_reason == "work_product_rewind_with_unspent_repair"
        assert resolution.failed_required_checks == ()

    @pytest.mark.parametrize("classification", ["environment", "infrastructure", "unknown", ""])
    def test_non_work_product_rewind_stands(self, classification):
        """Patching correct code against a broken world is the opposite failure."""
        resolution = resolve_correction_path("rewind", {}, {}, classification=classification)

        assert resolution.path == "rewind"
        assert resolution.overridden_from is None

    def test_abort_is_never_overridden_even_for_work_product(self):
        resolution = resolve_correction_path("abort", {}, {}, classification="work_product")

        assert resolution.path == "abort"
        assert resolution.overridden_from is None

    def test_patch_passes_through_untouched(self):
        resolution = resolve_correction_path("patch", {}, {}, classification="work_product")

        assert resolution.path == "patch"
        assert resolution.overridden_from is None

    def test_continue_anchor_still_reports_its_reason(self):
        """Anchor 1's provenance now rides the same field the event payload reads."""
        evidence = {"validation_result": {"checks": [{"check": "tests_pass", "passed": False}]}}
        resolution = resolve_correction_path(
            "continue", evidence, {"required_checks": ["tests_pass"]}
        )

        assert resolution.path == "patch"
        assert resolution.override_reason == "executed_failed_required_checks"
        assert resolution.failed_required_checks == ("tests_pass",)
