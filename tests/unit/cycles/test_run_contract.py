"""Tests for RunContract frozen dataclass (SIP-0079 §7.1)."""

import dataclasses

import pytest

from squadops.cycles.run_contract import RunContract

pytestmark = [pytest.mark.domain_orchestration]


def _make_contract(**overrides) -> RunContract:
    defaults = {
        "objective": "Build the auth module",
        "acceptance_criteria": ("tests pass", "code reviewed"),
        "non_goals": ("mobile support",),
        "time_budget_seconds": 3600,
        "stop_conditions": ("3 consecutive failures",),
        "required_artifacts": ("source_code", "test_report"),
        "plan_artifact_ref": "art-plan-001",
    }
    defaults.update(overrides)
    return RunContract(**defaults)


class TestRunContract:
    def test_frozen_immutability(self):
        rc = _make_contract()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rc.objective = "changed"  # type: ignore[misc]

    def test_all_fields_accessible(self):
        rc = _make_contract()
        assert rc.objective == "Build the auth module"
        assert rc.acceptance_criteria == ("tests pass", "code reviewed")
        assert rc.non_goals == ("mobile support",)
        assert rc.time_budget_seconds == 3600
        assert rc.stop_conditions == ("3 consecutive failures",)
        assert rc.required_artifacts == ("source_code", "test_report")
        assert rc.plan_artifact_ref == "art-plan-001"

    def test_source_gate_decision_defaults_none(self):
        rc = _make_contract()
        assert rc.source_gate_decision is None

    def test_source_gate_decision_set(self):
        rc = _make_contract(source_gate_decision="approved")
        assert rc.source_gate_decision == "approved"

    def test_to_dict_round_trip(self):
        rc = _make_contract(source_gate_decision="approved")
        d = rc.to_dict()
        restored = RunContract.from_dict(d)
        assert restored == rc

    def test_from_dict_coerces_lists_to_tuples(self):
        d = {
            "objective": "Build it",
            "acceptance_criteria": ["a", "b"],
            "non_goals": ["x"],
            "time_budget_seconds": 1800,
            "stop_conditions": ["stop"],
            "required_artifacts": ["code"],
            "plan_artifact_ref": "art-001",
        }
        rc = RunContract.from_dict(d)
        assert isinstance(rc.acceptance_criteria, tuple)
        assert isinstance(rc.non_goals, tuple)
        assert isinstance(rc.stop_conditions, tuple)
        assert isinstance(rc.required_artifacts, tuple)

    def test_dataclasses_replace(self):
        rc = _make_contract()
        modified = dataclasses.replace(rc, objective="New objective")
        assert modified.objective == "New objective"
        assert rc.objective == "Build the auth module"
