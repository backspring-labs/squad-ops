"""Tests for SIP-0076 domain model additions (Phase 1).

Covers ACs 1, 2, 4, 6, 7.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from squadops.cycles.models import (
    ArtifactRef,
    GateDecisionValue,
    PromotionStatus,
    Run,
    ValidationError,
    WorkloadType,
    validate_workload_type,
)


# ---------------------------------------------------------------------------
# WorkloadType constants (AC 2)
# ---------------------------------------------------------------------------


class TestWorkloadTypeConstants:
    def test_planning(self):
        assert WorkloadType.PLANNING == "planning"

    def test_implementation(self):
        assert WorkloadType.IMPLEMENTATION == "implementation"

    def test_evaluation(self):
        assert WorkloadType.EVALUATION == "evaluation"

    def test_refinement(self):
        assert WorkloadType.REFINEMENT == "refinement"


# ---------------------------------------------------------------------------
# PromotionStatus constants (AC 7)
# ---------------------------------------------------------------------------


class TestPromotionStatusConstants:
    def test_working(self):
        assert PromotionStatus.WORKING == "working"

    def test_promoted(self):
        assert PromotionStatus.PROMOTED == "promoted"


# ---------------------------------------------------------------------------
# GateDecisionValue expanded enum (AC 4)
# ---------------------------------------------------------------------------


class TestGateDecisionValueExpanded:
    def test_approved(self):
        assert GateDecisionValue.APPROVED == "approved"

    def test_approved_with_refinements(self):
        assert GateDecisionValue.APPROVED_WITH_REFINEMENTS == "approved_with_refinements"

    def test_returned_for_revision(self):
        assert GateDecisionValue.RETURNED_FOR_REVISION == "returned_for_revision"

    def test_rejected(self):
        assert GateDecisionValue.REJECTED == "rejected"

    def test_all_four_are_valid_strenum(self):
        assert len(GateDecisionValue) == 4
        for member in GateDecisionValue:
            assert isinstance(member, str)


# ---------------------------------------------------------------------------
# Run.workload_type field (AC 1)
# ---------------------------------------------------------------------------


class TestRunWorkloadType:
    def _make_run(self, **kwargs) -> Run:
        defaults = {
            "run_id": "run-1",
            "cycle_id": "cyc-1",
            "run_number": 1,
            "status": "queued",
            "initiated_by": "api",
            "resolved_config_hash": "abc123",
        }
        defaults.update(kwargs)
        return Run(**defaults)

    def test_default_is_none(self):
        run = self._make_run()
        assert run.workload_type is None

    def test_explicit_workload_type(self):
        run = self._make_run(workload_type="planning")
        assert run.workload_type == "planning"

    def test_custom_workload_type(self):
        run = self._make_run(workload_type="my_custom_phase")
        assert run.workload_type == "my_custom_phase"

    def test_existing_construction_still_works(self):
        """Backward compat: Run without workload_type works unchanged."""
        run = Run(
            run_id="r1",
            cycle_id="c1",
            run_number=1,
            status="queued",
            initiated_by="api",
            resolved_config_hash="hash",
        )
        assert run.workload_type is None
        assert run.run_id == "r1"


# ---------------------------------------------------------------------------
# ArtifactRef.promotion_status field (AC 6)
# ---------------------------------------------------------------------------


class TestArtifactRefPromotionStatus:
    def _make_artifact(self, **kwargs) -> ArtifactRef:
        defaults = {
            "artifact_id": "art-1",
            "project_id": "proj-1",
            "artifact_type": "code",
            "filename": "main.py",
            "content_hash": "sha256:abc",
            "size_bytes": 100,
            "media_type": "text/plain",
            "created_at": datetime.now(tz=timezone.utc),
        }
        defaults.update(kwargs)
        return ArtifactRef(**defaults)

    def test_default_is_working(self):
        artifact = self._make_artifact()
        assert artifact.promotion_status == "working"

    def test_explicit_promoted(self):
        artifact = self._make_artifact(promotion_status="promoted")
        assert artifact.promotion_status == "promoted"

    def test_existing_construction_still_works(self):
        """Backward compat: ArtifactRef without promotion_status works unchanged."""
        artifact = ArtifactRef(
            artifact_id="a1",
            project_id="p1",
            artifact_type="code",
            filename="f.py",
            content_hash="h",
            size_bytes=10,
            media_type="text/plain",
            created_at=datetime.now(tz=timezone.utc),
        )
        assert artifact.promotion_status == "working"
        assert artifact.artifact_id == "a1"


# ---------------------------------------------------------------------------
# validate_workload_type() helper
# ---------------------------------------------------------------------------


class TestValidateWorkloadType:
    def test_none_is_valid(self):
        assert validate_workload_type(None) is None

    def test_normal_string(self):
        assert validate_workload_type("planning") == "planning"

    def test_trims_whitespace(self):
        assert validate_workload_type("  planning  ") == "planning"

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            validate_workload_type("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            validate_workload_type("   ")

    def test_preserves_case(self):
        assert validate_workload_type("Planning") == "Planning"
