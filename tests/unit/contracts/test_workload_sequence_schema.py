"""Tests for SIP-0076 workload_sequence in cycle request profile schema (Phase 4).

Covers ACs 13, 20.
"""

from __future__ import annotations

import pytest

from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestWorkloadSequenceKey:
    """AC 13: workload_sequence is accepted in CRP defaults."""

    def test_workload_sequence_accepted(self):
        profile = CycleRequestProfile(
            name="test",
            defaults={
                "squad_profile_id": "full-squad",
                "workload_sequence": [
                    {"type": "planning", "gate": "progress_plan_review"},
                    {"type": "implementation", "gate": None},
                ],
            },
        )
        assert "workload_sequence" in profile.defaults

    def test_without_workload_sequence_still_valid(self):
        profile = CycleRequestProfile(
            name="test",
            defaults={"squad_profile_id": "full-squad"},
        )
        assert "workload_sequence" not in profile.defaults


class TestAutoGateValue:
    """Auto gate sentinel is accepted by schema validation."""

    def test_auto_gate_accepted(self):
        profile = CycleRequestProfile(
            name="test",
            defaults={
                "workload_sequence": [
                    {"type": "planning", "gate": "progress_approval_required"},
                    {"type": "implementation", "gate": "auto"},
                    {"type": "wrapup", "gate": None},
                ],
            },
        )
        seq = profile.defaults["workload_sequence"]
        assert seq[1]["gate"] == "auto"


class TestGateNameValidation:
    """AC 20: Gate names in workload_sequence must use progress_/promote_ prefix."""

    def test_invalid_prefix_rejected(self):
        with pytest.raises(Exception, match="must start with"):
            CycleRequestProfile(
                name="test",
                defaults={
                    "workload_sequence": [
                        {"type": "planning", "gate": "my_custom_gate"},
                    ],
                },
            )

    def test_case_sensitive_rejection(self):
        """D18: Gate prefix validation is case-sensitive."""
        with pytest.raises(Exception, match="must start with"):
            CycleRequestProfile(
                name="test",
                defaults={
                    "workload_sequence": [
                        {"type": "planning", "gate": "Progress_plan_review"},
                    ],
                },
            )

    def test_multiple_entries_all_validated(self):
        """Second entry with bad gate is caught."""
        with pytest.raises(Exception, match="must start with"):
            CycleRequestProfile(
                name="test",
                defaults={
                    "workload_sequence": [
                        {"type": "planning", "gate": "progress_plan_review"},
                        {"type": "implementation", "gate": "bad_gate"},
                    ],
                },
            )
