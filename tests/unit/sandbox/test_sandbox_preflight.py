"""Sandbox preflight reconciliation (SIP-0102 — phase 102.2c)."""

import pytest

from squadops.bootstrap.setup import checks as doctor_checks
from squadops.sandbox.environment import FULLSTACK_FASTAPI_REACT
from squadops.sandbox.preflight import sandbox_environment_decision

EXPECTED = "contract-abc"
GOOD_REPORT = {"contract_id": EXPECTED, "image": "img:pinned", "image_present": True}


class TestDecisionRules:
    def test_dormant_provider_contributes_nothing(self):
        """Bug caught: the inert posture broken — a noop deployment blocked or
        warned by sandbox preflight it never opted into."""
        decision = sandbox_environment_decision(
            provider="noop", expected_contract_id=None, report=None
        )
        assert not decision.rejected and not decision.warnings

    def test_unknown_environment_blocks(self):
        """Bug caught: a configured-but-contractless stack dispatching anyway —
        every sandbox op would be an unprovided-command stall at task time."""
        decision = sandbox_environment_decision(
            provider="docker", expected_contract_id=None, report=GOOD_REPORT
        )
        assert [f.code for f in decision.blocking] == ["sandbox_environment_unknown"]

    def test_unreachable_service_warns_and_allows(self):
        """Bug caught: blocking on missing evidence — SIP-0095 §6.2's doctrine
        is warn-and-allow when the service cannot be queried."""
        decision = sandbox_environment_decision(
            provider="docker", expected_contract_id=EXPECTED, report=None
        )
        assert not decision.rejected
        assert [f.code for f in decision.warnings] == ["sandbox_unverifiable"]

    def test_contract_skew_blocks(self):
        """Bug caught: the roll-4 class at create time — a service running an
        older contract than the tree expects would execute wrong commands and
        stamp wrong identity on every result."""
        decision = sandbox_environment_decision(
            provider="docker",
            expected_contract_id=EXPECTED,
            report={**GOOD_REPORT, "contract_id": "contract-OLD"},
        )
        assert [f.code for f in decision.blocking] == ["sandbox_contract_mismatch"]

    def test_missing_image_blocks_with_the_build_remedy(self):
        """Bug caught: dispatching into a host without the environment image —
        three cycles stalled pre-builder on exactly this class (#306 lineage)."""
        decision = sandbox_environment_decision(
            provider="docker",
            expected_contract_id=EXPECTED,
            report={**GOOD_REPORT, "image_present": False},
        )
        assert [f.code for f in decision.blocking] == ["sandbox_image_missing"]
        assert "build_sandbox_env_image.sh" in decision.blocking[0].message

    def test_unverifiable_image_warns_and_allows(self):
        """Bug caught: a daemon hiccup during preflight rejecting a cycle the
        environment could actually run."""
        decision = sandbox_environment_decision(
            provider="docker",
            expected_contract_id=EXPECTED,
            report={**GOOD_REPORT, "image_present": None},
        )
        assert not decision.rejected
        assert [f.code for f in decision.warnings] == ["sandbox_image_unverifiable"]

    def test_matching_environment_is_clean(self):
        """Bug caught: false findings on a healthy environment — preflight
        noise that trains operators to ignore it."""
        decision = sandbox_environment_decision(
            provider="docker", expected_contract_id=EXPECTED, report=GOOD_REPORT
        )
        assert not decision.rejected and not decision.warnings


class TestDoctorCategory:
    """The doctor renders the SAME decision (exit-criterion parity)."""

    def test_dormant_config_is_a_passing_check(self, monkeypatch):
        monkeypatch.delenv("SQUADOPS__SANDBOX__PROVIDER", raising=False)
        results = doctor_checks._collect_sandbox_checks(profile=None)
        assert [(r.name, r.passed) for r in results] == [("sandbox_dormant", True)]

    def test_missing_image_is_a_failing_check_with_fix_command(self, monkeypatch):
        """Bug caught: doctor and create-time preflight disagreeing about the
        same environment (the exit criterion demands the same finding)."""
        monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "docker")
        monkeypatch.setattr(
            doctor_checks,
            "_fetch_sandbox_report",
            lambda url: {
                "contract_id": FULLSTACK_FASTAPI_REACT.contract_id(),
                "image": FULLSTACK_FASTAPI_REACT.image,
                "image_present": False,
            },
        )
        results = doctor_checks._collect_sandbox_checks(profile=None)
        assert [(r.name, r.passed) for r in results] == [("sandbox_image_missing", False)]
        assert results[0].fix_command == "./scripts/dev/build_sandbox_env_image.sh"

    def test_unreachable_service_is_heuristic_not_hard_failure(self, monkeypatch):
        """Bug caught: doctor exiting 1 on unverifiable evidence — parity with
        warn-and-allow requires heuristic, which doctor never counts as a
        hard failure."""
        monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "docker")
        monkeypatch.setattr(doctor_checks, "_fetch_sandbox_report", lambda url: None)
        results = doctor_checks._collect_sandbox_checks(profile=None)
        assert [(r.name, r.heuristic) for r in results] == [("sandbox_unverifiable", True)]

    def test_healthy_environment_is_a_passing_check(self, monkeypatch):
        monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "docker")
        monkeypatch.setattr(
            doctor_checks,
            "_fetch_sandbox_report",
            lambda url: {
                "contract_id": FULLSTACK_FASTAPI_REACT.contract_id(),
                "image": FULLSTACK_FASTAPI_REACT.image,
                "image_present": True,
            },
        )
        results = doctor_checks._collect_sandbox_checks(profile=None)
        assert [(r.name, r.passed) for r in results] == [("sandbox_environment", True)]


@pytest.fixture(autouse=True)
def _clean_sandbox_env(monkeypatch):
    """Doctor collector reads live env — isolate every test from the host."""
    for key in list(__import__("os").environ):
        if key.startswith("SQUADOPS__SANDBOX__"):
            monkeypatch.delenv(key, raising=False)
