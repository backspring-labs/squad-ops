"""Tests for PlanDelta frozen dataclass (SIP-0079 §7.6)."""

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.cycles.plan_delta import PlanDelta

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


def _make_delta(**overrides) -> PlanDelta:
    defaults = {
        "delta_id": "delta-001",
        "run_id": "run-001",
        "correction_path": "patch",
        "trigger": "semantic_failure after task-003",
        "failure_classification": "work_product",
        "analysis_summary": "Output did not meet acceptance criteria",
        "decision_rationale": "Patch and retry with refined prompt",
        "changes": ("add: task-004 — repair the output",),
        "affected_task_types": ("development.build",),
        "created_at": NOW,
    }
    defaults.update(overrides)
    return PlanDelta(**defaults)


class TestPlanDelta:
    def test_frozen_immutability(self):
        pd = _make_delta()
        with pytest.raises(dataclasses.FrozenInstanceError):
            pd.delta_id = "changed"  # type: ignore[misc]

    def test_all_fields_accessible(self):
        pd = _make_delta()
        assert pd.delta_id == "delta-001"
        assert pd.run_id == "run-001"
        assert pd.correction_path == "patch"
        assert pd.trigger == "semantic_failure after task-003"
        assert pd.failure_classification == "work_product"
        assert pd.analysis_summary == "Output did not meet acceptance criteria"
        assert pd.decision_rationale == "Patch and retry with refined prompt"
        assert pd.changes == ("add: task-004 — repair the output",)
        assert pd.affected_task_types == ("development.build",)
        assert pd.created_at == NOW

    def test_to_dict_round_trip(self):
        pd = _make_delta()
        d = pd.to_dict()
        restored = PlanDelta.from_dict(d)
        assert restored == pd

    def test_to_dict_serializes_datetime_as_iso(self):
        pd = _make_delta()
        d = pd.to_dict()
        assert isinstance(d["created_at"], str)

    def test_from_dict_coerces_lists_to_tuples(self):
        d = {
            "delta_id": "d1",
            "run_id": "r1",
            "correction_path": "continue",
            "trigger": "failure",
            "failure_classification": "execution",
            "analysis_summary": "summary",
            "decision_rationale": "rationale",
            "changes": ["c1", "c2"],
            "affected_task_types": ["t1"],
            "created_at": NOW.isoformat(),
        }
        pd = PlanDelta.from_dict(d)
        assert isinstance(pd.changes, tuple)
        assert isinstance(pd.affected_task_types, tuple)

    # --- Validation tests ---

    def test_empty_failure_classification_rejected(self):
        with pytest.raises(ValueError, match="failure_classification"):
            _make_delta(failure_classification="")

    def test_empty_analysis_summary_rejected(self):
        with pytest.raises(ValueError, match="analysis_summary"):
            _make_delta(analysis_summary="")

    def test_empty_decision_rationale_rejected(self):
        with pytest.raises(ValueError, match="decision_rationale"):
            _make_delta(decision_rationale="")

    def test_patch_requires_changes(self):
        with pytest.raises(ValueError, match="changes must be non-empty"):
            _make_delta(correction_path="patch", changes=())

    def test_rewind_requires_changes(self):
        with pytest.raises(ValueError, match="changes must be non-empty"):
            _make_delta(correction_path="rewind", changes=())

    def test_continue_allows_empty_changes(self):
        pd = _make_delta(correction_path="continue", changes=())
        assert pd.changes == ()

    def test_abort_allows_empty_changes(self):
        pd = _make_delta(correction_path="abort", changes=())
        assert pd.changes == ()
