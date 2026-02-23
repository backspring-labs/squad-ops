"""Pulse-check profile tests (SIP-0070 Phase 4).

Validates that reference pulse-check profiles load, parse, round-trip
through parse_pulse_checks(), and use only valid template variables.
"""

import pytest

from squadops.capabilities.acceptance import validate_template_variables
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.pulse_models import parse_pulse_checks

pytestmark = [pytest.mark.domain_pulse_checks, pytest.mark.domain_contracts]


# ---------------------------------------------------------------------------
# pulse-check profile
# ---------------------------------------------------------------------------


class TestPulseCheckProfile:
    def test_loads_successfully(self):
        profile = load_profile("pulse-check")
        assert profile.name == "pulse-check"

    def test_has_pulse_checks(self):
        profile = load_profile("pulse-check")
        assert "pulse_checks" in profile.defaults
        assert len(profile.defaults["pulse_checks"]) == 1

    def test_has_cadence_policy(self):
        profile = load_profile("pulse-check")
        assert "cadence_policy" in profile.defaults
        policy = profile.defaults["cadence_policy"]
        assert policy["max_tasks_per_pulse"] == 5
        assert policy["max_pulse_seconds"] == 600

    def test_parse_pulse_checks_round_trip(self):
        profile = load_profile("pulse-check")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        assert len(defs) == 1
        assert defs[0].suite_id == "post_dev_smoke"
        assert defs[0].binding_mode == "milestone"
        assert defs[0].boundary_id == "post_dev"
        assert len(defs[0].checks) == 2

    def test_all_check_templates_use_valid_variables(self):
        """Every check target in the profile uses only known template variables."""
        profile = load_profile("pulse-check")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        for defn in defs:
            for check in defn.checks:
                if check.target:
                    bad = validate_template_variables(check.target)
                    assert bad == [], (
                        f"Suite {defn.suite_id} check target {check.target!r} "
                        f"uses unknown variables: {bad}"
                    )


# ---------------------------------------------------------------------------
# pulse-check-build profile
# ---------------------------------------------------------------------------


class TestPulseCheckBuildProfile:
    def test_loads_successfully(self):
        profile = load_profile("pulse-check-build")
        assert profile.name == "pulse-check-build"

    def test_has_two_suites(self):
        profile = load_profile("pulse-check-build")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        assert len(defs) == 2

    def test_suite_ids(self):
        profile = load_profile("pulse-check-build")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        suite_ids = {d.suite_id for d in defs}
        assert suite_ids == {"post_dev_smoke", "post_build_verify"}

    def test_build_suite_uses_command_exit_code(self):
        profile = load_profile("pulse-check-build")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        build_suite = [d for d in defs if d.suite_id == "post_build_verify"][0]
        assert build_suite.checks[0].check_type.value == "command_exit_code"

    def test_has_build_tasks(self):
        profile = load_profile("pulse-check-build")
        assert "build_tasks" in profile.defaults
        assert "development.develop" in profile.defaults["build_tasks"]

    def test_has_gate(self):
        profile = load_profile("pulse-check-build")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) == 1
        assert gates[0]["name"] == "plan-review"

    def test_all_check_templates_use_valid_variables(self):
        """Every check target in the profile uses only known template variables."""
        profile = load_profile("pulse-check-build")
        defs = parse_pulse_checks(profile.defaults["pulse_checks"])
        for defn in defs:
            for check in defn.checks:
                if check.target:
                    bad = validate_template_variables(check.target)
                    assert bad == [], (
                        f"Suite {defn.suite_id} check target {check.target!r} "
                        f"uses unknown variables: {bad}"
                    )


# ---------------------------------------------------------------------------
# Template variable validation
# ---------------------------------------------------------------------------


class TestTemplateVariableValidation:
    def test_unknown_variable_rejected_at_parse_time(self):
        """parse_pulse_checks() rejects unknown template variables."""
        raw = [
            {
                "suite_id": "bad_template",
                "boundary_id": "post_dev",
                "checks": [
                    {"check_type": "file_exists", "target": "{bogus_var}/output.md"}
                ],
            }
        ]
        with pytest.raises(ValueError, match="bogus_var"):
            parse_pulse_checks(raw)

    def test_known_variables_accepted(self):
        """Known variables (run_id, cycle_id, etc.) pass validation."""
        raw = [
            {
                "suite_id": "ok_template",
                "boundary_id": "post_dev",
                "checks": [
                    {
                        "check_type": "file_exists",
                        "target": "{run_root}/{run_id}/{cycle_id}/out.md",
                    }
                ],
            }
        ]
        defs = parse_pulse_checks(raw)
        assert len(defs) == 1

    def test_vars_dot_prefix_accepted(self):
        """Dot-path variables like {vars.foo} pass validation."""
        raw = [
            {
                "suite_id": "vars_ok",
                "boundary_id": "post_dev",
                "checks": [
                    {
                        "check_type": "file_exists",
                        "target": "{vars.output_dir}/report.md",
                    }
                ],
            }
        ]
        defs = parse_pulse_checks(raw)
        assert len(defs) == 1

    def test_literal_path_no_templates_accepted(self):
        """Paths with no template variables are accepted."""
        raw = [
            {
                "suite_id": "literal",
                "boundary_id": "post_dev",
                "checks": [
                    {"check_type": "file_exists", "target": "output.md"}
                ],
            }
        ]
        defs = parse_pulse_checks(raw)
        assert len(defs) == 1


# ---------------------------------------------------------------------------
# Proof rejection
# ---------------------------------------------------------------------------


class TestProofRejection:
    def test_proof_suite_class_rejected(self):
        """parse_pulse_checks() rejects suite_class='proof' at load time."""
        raw = [
            {
                "suite_id": "bad_proof",
                "boundary_id": "post_dev",
                "suite_class": "proof",
                "checks": [{"check_type": "file_exists", "target": "out.txt"}],
            }
        ]
        with pytest.raises(ValueError, match="proof"):
            parse_pulse_checks(raw)
