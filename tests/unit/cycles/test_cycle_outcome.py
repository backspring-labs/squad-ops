"""Tests for resolve_cycle_outcome — derive-on-read CycleOutcome (SIP-0096 Phase 3 slice 2b).

The resolver is thin orchestration (one registry read → the pure aggregate_cycle_outcome,
which is tested in test_verification_integrity.py). These tests verify the wiring: it reads
the cycle's persisted per-run summaries and rolls them up, worst-verdict-wins.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.verification_integrity import RunVerdict, RunVerificationSummary

pytestmark = [pytest.mark.domain_orchestration]


def _run_summary(verdict, *, verified=(), failed=()) -> RunVerificationSummary:
    return RunVerificationSummary(
        verdict=verdict,
        verified=tuple(verified),
        failed=tuple(failed),
        unverified=(),
        required_unmet=(),
        executed_count=len(verified) + len(failed),
        passed_count=len(verified),
    )


def _normal_cycle():
    # a real Cycle always carries a dict here; a bare AsyncMock's truthy
    # attribute would read as a malformed replay declaration (SIP-0101)
    from unittest.mock import MagicMock

    cycle = MagicMock()
    cycle.execution_overrides = {}
    return cycle


async def test_rolls_up_persisted_summaries_worst_verdict_wins():
    registry = AsyncMock()
    registry.get_cycle.return_value = _normal_cycle()
    registry.list_run_verification_summaries = AsyncMock(
        return_value=[
            _run_summary(RunVerdict.ACCEPTED, verified=["tests_pass"]),
            _run_summary(RunVerdict.REJECTED, failed=["frontend_build"]),
        ]
    )

    outcome = await resolve_cycle_outcome(registry, "cyc_x")

    registry.list_run_verification_summaries.assert_awaited_once_with("cyc_x")
    assert outcome.verdict is RunVerdict.REJECTED  # a rejected run drags the cycle down
    assert outcome.run_count == 2
    assert "frontend_build" in outcome.failed
    assert "tests_pass" in outcome.verified


async def test_empty_cycle_rolls_up_to_accepted():
    registry = AsyncMock()
    registry.get_cycle.return_value = _normal_cycle()
    registry.list_run_verification_summaries = AsyncMock(return_value=[])

    outcome = await resolve_cycle_outcome(registry, "cyc_x")

    assert outcome.verdict is RunVerdict.ACCEPTED  # zero runs = zero adverse evidence
    assert outcome.run_count == 0


class TestRequiredNotOwedRoundTrip:
    """#1428: the disclosure field is stored and read back, and a pre-#1428 row without it
    reconstructs unchanged."""

    def _summary(self, **kw):
        from squadops.cycles.verification_integrity import RunVerdict, RunVerificationSummary

        base = dict(
            verdict=RunVerdict.ACCEPTED,
            verified=(),
            failed=(),
            unverified=(),
            required_unmet=(),
            executed_count=0,
            passed_count=0,
        )
        base.update(kw)
        return RunVerificationSummary(**base)

    def test_round_trip_keeps_the_field(self):
        from adapters.cycles.postgres_cycle_registry import (
            _verification_summary_from_dict,
            _verification_summary_to_dict,
        )

        original = self._summary(required_not_owed=("frontend_build", "tests_pass"))
        stored = _verification_summary_to_dict(original)
        assert stored["required_not_owed"] == ["frontend_build", "tests_pass"]
        assert _verification_summary_from_dict(stored).required_not_owed == (
            "frontend_build",
            "tests_pass",
        )

    def test_a_pre_1428_row_reconstructs_with_nothing_not_owed(self):
        """Bug caught: a KeyError on every stored summary from before the field existed,
        which would break the cycle roll-up's read of history."""
        from adapters.cycles.postgres_cycle_registry import (
            _verification_summary_from_dict,
            _verification_summary_to_dict,
        )

        stored = _verification_summary_to_dict(self._summary())
        del stored["required_not_owed"]
        assert _verification_summary_from_dict(stored).required_not_owed == ()


class TestCriteriaKeptOverEnvironmentSkipRoundTrip:
    """#1406: the disclosure survives storage, and a pre-#1406 row reads back unchanged."""

    def _summary(self, **kw):
        from squadops.cycles.verification_integrity import RunVerdict, RunVerificationSummary

        base = dict(
            verdict=RunVerdict.ACCEPTED,
            verified=(),
            failed=(),
            unverified=(),
            required_unmet=(),
            executed_count=0,
            passed_count=0,
        )
        base.update(kw)
        return RunVerificationSummary(**base)

    def test_round_trip_keeps_the_criteria_the_rule_credited(self):
        from adapters.cycles.postgres_cycle_registry import (
            _verification_summary_from_dict,
            _verification_summary_to_dict,
        )

        views = ("vc-view-compiles-run-detail-view", "vc-view-compiles-runs-list-view")
        stored = _verification_summary_to_dict(
            self._summary(criteria_kept_over_environment_skip=views)
        )
        assert stored["criteria_kept_over_environment_skip"] == list(views)
        assert _verification_summary_from_dict(stored).criteria_kept_over_environment_skip == views

    def test_a_pre_1406_row_reconstructs_with_nothing_credited_by_the_rule(self):
        """Bug caught: a KeyError on every summary stored before the field existed, which
        would break the cycle roll-up's read of the 1.7.4 history."""
        from adapters.cycles.postgres_cycle_registry import (
            _verification_summary_from_dict,
            _verification_summary_to_dict,
        )

        stored = _verification_summary_to_dict(self._summary())
        del stored["criteria_kept_over_environment_skip"]
        assert _verification_summary_from_dict(stored).criteria_kept_over_environment_skip == ()
