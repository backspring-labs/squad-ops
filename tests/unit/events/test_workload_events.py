"""Tests for SIP-0083 workload event types.

Verifies the 3 new workload event type constants exist, follow naming
conventions, and are included in EventType.all().
"""

from __future__ import annotations

import pytest

from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_events]


class TestWorkloadEventTypes:
    """SIP-0083 workload event type constants."""

    def test_workload_events_included_in_all_with_correct_values(self):
        """All 3 workload events are in EventType.all() with entity.transition format."""
        all_types = EventType.all()
        expected = {
            "workload.completed",
            "workload.gate_awaiting",
            "workload.advanced",
        }
        workload_types = {t for t in all_types if t.startswith("workload.")}
        assert workload_types == expected
