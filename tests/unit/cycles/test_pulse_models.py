"""
Unit tests for pulse verification domain models (SIP-0070 Phase 1.4).

Tests:
- CADENCE_BOUNDARY_ID constant
- CadencePolicy defaults and immutability
- PulseCheckDefinition fields and binding modes
- PulseDecision / SuiteOutcome enums
- PulseVerificationRecord construction
- parse_pulse_checks() validation: suite_class, binding_mode, suite_id, cadence enforcement
"""

import pytest

from squadops.capabilities.models import CheckType
from squadops.cycles.pulse_models import (
    CADENCE_BOUNDARY_ID,
    CadencePolicy,
    PulseCheckDefinition,
    PulseDecision,
    PulseVerificationRecord,
    SuiteOutcome,
    parse_pulse_checks,
)

pytestmark = [pytest.mark.domain_pulse_checks]


class TestCadenceBoundaryId:
    def test_constant_value(self):
        assert CADENCE_BOUNDARY_ID == "cadence"


class TestCadencePolicy:
    def test_defaults(self):
        policy = CadencePolicy()
        assert policy.max_pulse_seconds == 600
        assert policy.max_tasks_per_pulse == 5

    def test_custom_values(self):
        policy = CadencePolicy(max_pulse_seconds=300, max_tasks_per_pulse=3)
        assert policy.max_pulse_seconds == 300
        assert policy.max_tasks_per_pulse == 3

    def test_frozen(self):
        policy = CadencePolicy()
        with pytest.raises(AttributeError):
            policy.max_pulse_seconds = 999


class TestPulseDecisionEnum:
    def test_values(self):
        assert PulseDecision.PASS.value == "pass"
        assert PulseDecision.FAIL.value == "fail"
        assert PulseDecision.EXHAUSTED.value == "exhausted"


class TestSuiteOutcomeEnum:
    def test_values(self):
        assert SuiteOutcome.PASS.value == "pass"
        assert SuiteOutcome.FAIL.value == "fail"
        assert SuiteOutcome.SKIP.value == "skip"


class TestPulseCheckDefinition:
    def test_construction_with_defaults(self):
        defn = PulseCheckDefinition(
            suite_id="smoke",
            boundary_id="post_dev",
        )
        assert defn.suite_id == "smoke"
        assert defn.boundary_id == "post_dev"
        assert defn.binding_mode == "milestone"
        assert defn.suite_class == "guardrail"
        assert defn.checks == ()
        assert defn.after_task_types == ()
        assert defn.max_suite_seconds == 30
        assert defn.max_check_seconds == 10

    def test_frozen(self):
        defn = PulseCheckDefinition(suite_id="s", boundary_id="b")
        with pytest.raises(AttributeError):
            defn.suite_id = "other"

    def test_cadence_binding_mode(self):
        defn = PulseCheckDefinition(
            suite_id="heartbeat",
            boundary_id=CADENCE_BOUNDARY_ID,
            binding_mode="cadence",
        )
        assert defn.binding_mode == "cadence"
        assert defn.boundary_id == CADENCE_BOUNDARY_ID


class TestPulseVerificationRecord:
    def test_construction(self):
        record = PulseVerificationRecord(
            suite_id="smoke",
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run-001",
            suite_outcome=SuiteOutcome.PASS,
        )
        assert record.suite_id == "smoke"
        assert record.boundary_id == "post_dev"
        assert record.cadence_interval_id == 1
        assert record.suite_outcome == SuiteOutcome.PASS
        assert record.repair_attempt_number == 0
        assert record.check_results == ()
        assert record.repair_task_refs == ()

    def test_with_check_results(self):
        record = PulseVerificationRecord(
            suite_id="smoke",
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run-001",
            suite_outcome=SuiteOutcome.FAIL,
            check_results=({"check": "file_exists", "passed": False},),
            notes="file missing",
        )
        assert len(record.check_results) == 1
        assert record.notes == "file missing"

    def test_frozen(self):
        record = PulseVerificationRecord(
            suite_id="s",
            boundary_id="b",
            cadence_interval_id=0,
            run_id="r",
            suite_outcome=SuiteOutcome.PASS,
        )
        with pytest.raises(AttributeError):
            record.suite_outcome = SuiteOutcome.FAIL


class TestParsePulseChecks:
    def test_valid_milestone(self):
        raw = [
            {
                "suite_id": "post_dev_smoke",
                "boundary_id": "post_dev",
                "suite_class": "guardrail",
                "after_task_types": ["development"],
                "checks": [
                    {"check_type": "file_exists", "target": "output/code.py"},
                ],
            }
        ]
        result = parse_pulse_checks(raw)
        assert len(result) == 1
        assert result[0].suite_id == "post_dev_smoke"
        assert result[0].boundary_id == "post_dev"
        assert result[0].binding_mode == "milestone"
        assert len(result[0].checks) == 1
        assert result[0].checks[0].check_type == CheckType.FILE_EXISTS

    def test_valid_cadence(self):
        raw = [
            {
                "suite_id": "heartbeat",
                "boundary_id": "cadence",
                "binding_mode": "cadence",
                "checks": [
                    {"check_type": "file_exists", "target": "status.txt"},
                ],
            }
        ]
        result = parse_pulse_checks(raw)
        assert result[0].binding_mode == "cadence"
        assert result[0].boundary_id == CADENCE_BOUNDARY_ID

    def test_proof_rejected(self):
        raw = [
            {
                "suite_id": "formal",
                "boundary_id": "post_dev",
                "suite_class": "proof",
                "checks": [],
            }
        ]
        with pytest.raises(ValueError, match="proof"):
            parse_pulse_checks(raw)

    def test_unknown_binding_mode_rejected(self):
        raw = [
            {
                "suite_id": "s1",
                "boundary_id": "b1",
                "binding_mode": "unknown",
                "checks": [],
            }
        ]
        with pytest.raises(ValueError, match="binding_mode"):
            parse_pulse_checks(raw)

    def test_cadence_wrong_boundary_id_rejected(self):
        """D5a: cadence binding mode requires boundary_id == CADENCE_BOUNDARY_ID."""
        raw = [
            {
                "suite_id": "s1",
                "boundary_id": "post_dev",
                "binding_mode": "cadence",
                "checks": [],
            }
        ]
        with pytest.raises(ValueError, match="cadence"):
            parse_pulse_checks(raw)

    def test_duplicate_suite_id_rejected(self):
        raw = [
            {"suite_id": "dupe", "boundary_id": "a", "checks": []},
            {"suite_id": "dupe", "boundary_id": "b", "checks": []},
        ]
        with pytest.raises(ValueError, match="duplicate"):
            parse_pulse_checks(raw)

    def test_missing_suite_id_rejected(self):
        raw = [{"boundary_id": "post_dev", "checks": []}]
        with pytest.raises(ValueError, match="suite_id"):
            parse_pulse_checks(raw)

    def test_missing_boundary_id_rejected(self):
        raw = [{"suite_id": "s1", "checks": []}]
        with pytest.raises(ValueError, match="boundary_id"):
            parse_pulse_checks(raw)

    def test_multiple_suites(self):
        raw = [
            {"suite_id": "s1", "boundary_id": "post_dev", "checks": []},
            {"suite_id": "s2", "boundary_id": "post_build", "checks": []},
            {
                "suite_id": "hb",
                "boundary_id": "cadence",
                "binding_mode": "cadence",
                "checks": [],
            },
        ]
        result = parse_pulse_checks(raw)
        assert len(result) == 3

    def test_command_list_converted_to_tuple(self):
        raw = [
            {
                "suite_id": "cmd",
                "boundary_id": "post_dev",
                "checks": [
                    {
                        "check_type": "command_exit_code",
                        "target": "",
                        "command": ["python", "-c", "print('hi')"],
                    }
                ],
            }
        ]
        result = parse_pulse_checks(raw)
        assert isinstance(result[0].checks[0].command, tuple)

    def test_env_list_converted_to_tuple(self):
        raw = [
            {
                "suite_id": "envcheck",
                "boundary_id": "post_dev",
                "checks": [
                    {
                        "check_type": "command_exit_code",
                        "target": "",
                        "command": ["echo"],
                        "env": [["MY_VAR", "val"]],
                    }
                ],
            }
        ]
        result = parse_pulse_checks(raw)
        assert result[0].checks[0].env == (("MY_VAR", "val"),)

    def test_custom_timeouts(self):
        raw = [
            {
                "suite_id": "slow",
                "boundary_id": "post_dev",
                "max_suite_seconds": 60,
                "max_check_seconds": 20,
                "checks": [],
            }
        ]
        result = parse_pulse_checks(raw)
        assert result[0].max_suite_seconds == 60
        assert result[0].max_check_seconds == 20
