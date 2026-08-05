"""#683 (SIP-0096 §10/§14) — the CycleOutcome-derived confidence ceiling.

The normative claim under test: wrap-up prose can never claim above what the
structured evidence supports (§6.6(4)), on EVERY path — including the
no-outcome path, which fails closed to inconclusive rather than falling back
to prose.
"""

from __future__ import annotations

import pytest

from squadops.cycles.wrapup_models import (
    CONFIDENCE_RANK,
    ConfidenceClassification,
    confidence_ceiling,
    verification_evidence_summary,
)

pytestmark = [pytest.mark.domain_cycles]


def _outcome(verdict="accepted", **kw) -> dict:
    base = {
        "verdict": verdict,
        "verified": ["tests_pass"],
        "failed": [],
        "unverified": [],
        "required_unmet": [],
        "run_count": 2,
        "waived": [],
    }
    base.update(kw)
    return base


class TestConfidenceCeiling:
    def test_accepted_all_verified_is_verified_complete(self):
        ceiling, _ = confidence_ceiling(_outcome())
        assert ceiling == ConfidenceClassification.VERIFIED_COMPLETE

    def test_accepted_with_disclosures_caps_at_caveats(self):
        ceiling, basis = confidence_ceiling(
            _outcome(
                unverified=[
                    {"check_id": "frontend_build", "reason": "missing_tooling", "required": False}
                ]
            )
        )
        assert ceiling == ConfidenceClassification.COMPLETE_WITH_CAVEATS
        assert "unverified" in basis

    def test_rejected_caps_at_partial_completion(self):
        ceiling, basis = confidence_ceiling(_outcome("rejected", failed=["tests_pass"]))
        assert ceiling == ConfidenceClassification.PARTIAL_COMPLETION
        assert "tests_pass" in basis

    def test_blocked_unwaived_caps_at_not_sufficiently_verified(self):
        ceiling, basis = confidence_ceiling(
            _outcome(
                "blocked_unverified",
                required_unmet=["tests_pass"],
                unverified=[
                    {"check_id": "tests_pass", "reason": "missing_tooling", "required": True}
                ],
            )
        )
        assert ceiling == ConfidenceClassification.NOT_SUFFICIENTLY_VERIFIED
        assert "tests_pass" in basis

    def test_blocked_fully_waived_allows_caveats(self):
        # §6.5: an operator accept-with-waiver IS the caveat
        ceiling, basis = confidence_ceiling(
            _outcome(
                "blocked_unverified",
                required_unmet=["tests_pass"],
                waived=[{"check_id": "tests_pass", "reason": "node absent", "waived_by": "op"}],
            )
        )
        assert ceiling == ConfidenceClassification.COMPLETE_WITH_CAVEATS
        assert "waived" in basis

    def test_absent_outcome_fails_closed_to_inconclusive(self):
        # "on every path": a wrap-up that never received the outcome cannot
        # let prose stand — inconclusive is the honest maximum
        for missing in (None, {}):
            ceiling, basis = confidence_ceiling(missing)
            assert ceiling == ConfidenceClassification.INCONCLUSIVE
            assert "unavailable" in basis

    def test_zero_runs_is_inconclusive(self):
        ceiling, _ = confidence_ceiling(_outcome(run_count=0))
        assert ceiling == ConfidenceClassification.INCONCLUSIVE

    def test_rank_covers_every_classification(self):
        # a new classification without a rank would crash enforcement
        from squadops.cycles.wrapup_models import ConfidenceClassification as C

        values = {
            getattr(C, name)
            for name in dir(C)
            if not name.startswith("_") and isinstance(getattr(C, name), str)
        }
        assert set(CONFIDENCE_RANK) == values


class TestEvidenceSummary:
    def test_summary_states_the_ceiling(self):
        text = verification_evidence_summary(_outcome("rejected", failed=["tests_pass"]))
        assert "maximum honest confidence: partial_completion" in text
        assert "verdict: rejected" in text

    def test_summary_discloses_inert_and_tolerates_its_absence(self):
        # #684: chronic checks reach the wrap-up prompt; a pre-#684 outcome
        # dict without the key still renders (fail-open to 'none', never a crash)
        text = verification_evidence_summary(_outcome(inert=["frontend_build"]))
        assert "inert: frontend_build" in text
        assert "inert: none" in verification_evidence_summary(_outcome())


class TestExecutorWrapupInjection:
    """#683 threading: a wrap-up run's prior_outputs carry the structured
    evidence; non-wrap-up runs are untouched; derivation failure never kills
    the run (absence fails closed at the handler)."""

    @staticmethod
    def _envelope(task_type: str):
        from unittest.mock import MagicMock

        e = MagicMock()
        e.task_type = task_type
        return e

    @staticmethod
    def _executor_with(outcome_summaries):
        from unittest.mock import AsyncMock, MagicMock

        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        registry = AsyncMock()
        registry.list_run_verification_summaries.return_value = outcome_summaries
        cycle = MagicMock()
        cycle.execution_overrides = {}
        registry.get_cycle.return_value = cycle
        registry.list_runs.return_value = []
        return DispatchedFlowExecutor(cycle_registry=registry)

    async def test_wrapup_plan_gets_evidence(self):
        from unittest.mock import MagicMock

        executor = self._executor_with([])
        prior: dict = {}
        cycle = MagicMock()
        cycle.cycle_id = "cyc_1"
        cycle.execution_overrides = {}

        await executor._inject_wrapup_evidence(
            [self._envelope("governance.closeout_decision")], cycle, prior
        )

        evidence = prior["verification_evidence"]
        assert "maximum honest confidence" in evidence["summary"]
        assert evidence["outcome"]["run_count"] == 0

    async def test_non_wrapup_plan_untouched(self):
        from unittest.mock import MagicMock

        executor = self._executor_with([])
        prior: dict = {}
        await executor._inject_wrapup_evidence(
            [self._envelope("development.develop")], MagicMock(), prior
        )
        assert prior == {}

    async def test_derivation_failure_never_raises(self):
        from unittest.mock import AsyncMock, MagicMock

        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        registry = AsyncMock()
        registry.list_run_verification_summaries.side_effect = RuntimeError("db down")
        executor = DispatchedFlowExecutor(cycle_registry=registry)
        prior: dict = {}
        cycle = MagicMock()
        cycle.cycle_id = "cyc_1"

        await executor._inject_wrapup_evidence(
            [self._envelope("qa.assess_outcomes")], cycle, prior
        )  # no raise; handler fails closed on absence
        assert "verification_evidence" not in prior
