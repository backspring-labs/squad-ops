"""SIP-0096 §6.5 / AC#12 (#682) — the operator gate waiver.

The normative claims under test: a waiver is never implicit (explicit approval
+ non-empty reason), it can only name checks the run actually disclosed as
unverified (it records ABOVE evidence, never touches a check that ran), and
the roll-up carries it beside an unaltered verdict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import GateDecision, validate_waiver_request
from squadops.cycles.verification_integrity import (
    RunVerdict,
    UnverifiedCheck,
    WaivedCheck,
    aggregate_cycle_outcome,
)

pytestmark = [pytest.mark.domain_cycles]


class TestValidateWaiverRequest:
    _UNVERIFIED = {"tests_pass", "frontend_build"}

    def test_valid_waiver_passes(self):
        assert (
            validate_waiver_request(
                "approved", ["tests_pass"], "node absent on runner", self._UNVERIFIED
            )
            is None
        )

    def test_no_waiver_fields_is_an_ordinary_decision(self):
        assert validate_waiver_request("rejected", [], None, None) is None

    def test_waiver_requires_approved_decision(self):
        err = validate_waiver_request("rejected", ["tests_pass"], "r", self._UNVERIFIED)
        assert err is not None and "approved" in err

    def test_waiver_requires_a_reason(self):
        # §6.5: a waiver is never implicit
        err = validate_waiver_request("approved", ["tests_pass"], "  ", self._UNVERIFIED)
        assert err is not None and "reason" in err

    def test_reason_without_checks_is_rejected(self):
        err = validate_waiver_request("approved", [], "why", self._UNVERIFIED)
        assert err is not None and "waived_checks" in err

    def test_waiving_a_check_that_ran_is_rejected(self):
        # the evidence-mutation guard: only unverified checks are waivable
        err = validate_waiver_request(
            "approved", ["tests_pass", "no_stub_fallback_tests"], "r", self._UNVERIFIED
        )
        assert err is not None and "no_stub_fallback_tests" in err

    def test_no_summary_means_nothing_to_waive_against(self):
        err = validate_waiver_request("approved", ["tests_pass"], "r", None)
        assert err is not None and "summary" in err


class TestGateDecisionCompat:
    def test_pre_682_construction_still_valid(self):
        # every existing call site builds decisions without the new fields
        gd = GateDecision(
            gate_name="g", decision="approved", decided_by="op", decided_at=datetime.now(UTC)
        )
        assert gd.waived_checks == ()
        assert gd.waiver_reason is None


class TestOutcomeCarriesWaivers:
    def test_waiver_sits_beside_an_unaltered_verdict(self):
        # §6.5: the verdict is the UN-WAIVED evidence verdict — a waived
        # blocked_unverified cycle still reads blocked_unverified
        from squadops.cycles.verification_integrity import RunVerificationSummary

        summary = RunVerificationSummary(
            verdict=RunVerdict.BLOCKED_UNVERIFIED,
            verified=(),
            failed=(),
            unverified=(UnverifiedCheck("tests_pass", "missing_tooling", required=True),),
            required_unmet=("tests_pass",),
            executed_count=0,
            passed_count=0,
        )
        waived = [WaivedCheck("tests_pass", "node absent on runner", waived_by="op")]
        outcome = aggregate_cycle_outcome([summary], waived=waived)
        assert outcome.verdict is RunVerdict.BLOCKED_UNVERIFIED  # never altered
        assert outcome.waived == tuple(waived)  # recorded beside it

    async def test_resolve_cycle_outcome_collects_waivers_from_gate_decisions(self):
        from squadops.cycles.cycle_outcome import resolve_cycle_outcome

        registry = AsyncMock()
        registry.list_run_verification_summaries.return_value = []
        cycle = MagicMock()
        cycle.execution_overrides = {}
        registry.get_cycle.return_value = cycle
        run = MagicMock()
        run.gate_decisions = [
            GateDecision(
                gate_name="progress_review",
                decision="approved",
                decided_by="operator",
                decided_at=datetime.now(UTC),
                waived_checks=("tests_pass",),
                waiver_reason="node absent on runner",
            )
        ]
        registry.list_runs.return_value = [run]

        outcome = await resolve_cycle_outcome(registry, "cyc_1")

        assert outcome.waived == (
            WaivedCheck("tests_pass", "node absent on runner", waived_by="operator"),
        )
