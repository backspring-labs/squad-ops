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


async def test_rolls_up_persisted_summaries_worst_verdict_wins():
    registry = AsyncMock()
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
    registry.list_run_verification_summaries = AsyncMock(return_value=[])

    outcome = await resolve_cycle_outcome(registry, "cyc_x")

    assert outcome.verdict is RunVerdict.ACCEPTED  # zero runs = zero adverse evidence
    assert outcome.run_count == 0
