"""
Tests for UnknownClassification constants and REQUIRED_REFINEMENT_ROLES (SIP-0078).
"""

import pytest

from squadops.cycles.models import REQUIRED_PLAN_ROLES, REQUIRED_REFINEMENT_ROLES
from squadops.cycles.unknown_classification import UnknownClassification

pytestmark = [pytest.mark.domain_orchestration]


class TestUnknownClassification:
    """UnknownClassification follows the constants class pattern (not enum)."""

    def test_all_values_are_lowercase_strings(self):
        values = [
            UnknownClassification.RESOLVED,
            UnknownClassification.PROTO_VALIDATED,
            UnknownClassification.ACCEPTABLE_RISK,
            UnknownClassification.REQUIRES_HUMAN_DECISION,
            UnknownClassification.BLOCKER,
        ]
        for v in values:
            assert isinstance(v, str)
            assert v == v.lower()

    def test_is_not_enum(self):
        """Constants class, not an enum — matches WorkloadType pattern."""
        assert not hasattr(UnknownClassification, "__members__")

    def test_five_constants(self):
        """Exactly 5 classification levels defined."""
        public_attrs = [
            a
            for a in dir(UnknownClassification)
            if not a.startswith("_") and isinstance(getattr(UnknownClassification, a), str)
        ]
        assert len(public_attrs) == 5


class TestRequiredRefinementRoles:
    """REQUIRED_REFINEMENT_ROLES follows REQUIRED_PLAN_ROLES pattern."""

    def test_contains_lead_and_qa(self):
        assert REQUIRED_REFINEMENT_ROLES == frozenset({"lead", "qa"})

    def test_is_subset_of_plan_roles(self):
        """Refinement roles are a subset of planning roles."""
        assert REQUIRED_REFINEMENT_ROLES <= REQUIRED_PLAN_ROLES
