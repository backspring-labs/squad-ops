"""Tests for pulse verification runner (src/squadops/cycles/pulse_verification.py).

Covers:
- resolve_milestone_bindings(): prefix matching, last-index semantics, unmatched suites
- collect_cadence_bound_suites(): filters by binding_mode
- run_pulse_verification(): per-suite records with suite_id, boundary_id, cadence_interval_id
- determine_boundary_decision(): all PASS → PASS, any FAIL → FAIL, empty → PASS
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from squadops.capabilities.models import (
    AcceptanceCheck,
    AcceptanceContext,
    AcceptanceResult,
    CheckType,
    ValidationReport,
)
from squadops.cycles.pulse_models import (
    CADENCE_BOUNDARY_ID,
    PulseCheckDefinition,
    PulseDecision,
    PulseVerificationRecord,
    SuiteOutcome,
)
from squadops.cycles.pulse_verification import (
    collect_cadence_bound_suites,
    determine_boundary_decision,
    resolve_milestone_bindings,
    run_pulse_verification,
)
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_pulse_checks]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(task_type: str, task_id: str = "t1") -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        agent_id="neo",
        cycle_id="cyc_001",
        pulse_id="p1",
        project_id="proj_001",
        task_type=task_type,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
    )


def _make_suite(
    suite_id: str,
    boundary_id: str = "post_dev",
    after_task_types: tuple[str, ...] = ("development",),
    binding_mode: str = "milestone",
    checks: tuple[AcceptanceCheck, ...] = (),
) -> PulseCheckDefinition:
    return PulseCheckDefinition(
        suite_id=suite_id,
        boundary_id=boundary_id,
        after_task_types=after_task_types,
        binding_mode=binding_mode,
        checks=checks,
    )


def _make_check(target: str = "output.md") -> AcceptanceCheck:
    return AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target=target)


def _ctx() -> AcceptanceContext:
    return AcceptanceContext(
        run_root="/tmp/test",
        cycle_id="cyc_001",
        workload_id="cyc_001",
        run_id="run_001",
    )


# ---------------------------------------------------------------------------
# resolve_milestone_bindings
# ---------------------------------------------------------------------------


class TestResolveMilestoneBindings:
    def test_prefix_match_single_suite(self):
        plan = [
            _make_envelope("strategy.analyze_prd", "t1"),
            _make_envelope("development.implement", "t2"),
            _make_envelope("qa.validate", "t3"),
        ]
        suite = _make_suite("s1", "post_dev", ("development",))
        bindings, unmatched = resolve_milestone_bindings((suite,), plan)

        assert len(bindings) == 1
        assert 1 in bindings  # last index where development.* matches
        assert bindings[1] == [suite]
        assert unmatched == []

    def test_prefix_match_last_index(self):
        """When multiple tasks match prefix, bind to the last one."""
        plan = [
            _make_envelope("development.implement", "t1"),
            _make_envelope("development.build", "t2"),
            _make_envelope("qa.validate", "t3"),
        ]
        suite = _make_suite("s1", "post_dev", ("development",))
        bindings, _ = resolve_milestone_bindings((suite,), plan)

        assert 1 in bindings  # development.build is last development.* task
        assert 0 not in bindings

    def test_multiple_suites_same_boundary(self):
        plan = [
            _make_envelope("development.implement", "t1"),
            _make_envelope("qa.validate", "t2"),
        ]
        s1 = _make_suite("s1", "post_dev", ("development",))
        s2 = _make_suite("s2", "post_dev_extra", ("development",))
        bindings, _ = resolve_milestone_bindings((s1, s2), plan)

        assert 0 in bindings
        assert len(bindings[0]) == 2

    def test_multiple_suites_different_boundaries(self):
        plan = [
            _make_envelope("strategy.analyze_prd", "t1"),
            _make_envelope("development.implement", "t2"),
            _make_envelope("qa.validate", "t3"),
        ]
        s_dev = _make_suite("s1", "post_dev", ("development",))
        s_qa = _make_suite("s2", "post_qa", ("qa",))
        bindings, _ = resolve_milestone_bindings((s_dev, s_qa), plan)

        assert 1 in bindings  # post_dev at index 1
        assert 2 in bindings  # post_qa at index 2
        assert bindings[1] == [s_dev]
        assert bindings[2] == [s_qa]

    def test_unmatched_suite_returned_separately(self):
        plan = [_make_envelope("development.implement", "t1")]
        suite = _make_suite("s1", "post_qa", ("qa",))
        bindings, unmatched = resolve_milestone_bindings((suite,), plan)

        assert len(bindings) == 0
        assert unmatched == [suite]

    def test_cadence_suites_excluded(self):
        """Cadence-bound suites should not appear in milestone bindings."""
        plan = [_make_envelope("development.implement", "t1")]
        cadence = _make_suite(
            "cad", CADENCE_BOUNDARY_ID, (), "cadence"
        )
        milestone = _make_suite("ms", "post_dev", ("development",))
        bindings, unmatched = resolve_milestone_bindings(
            (cadence, milestone), plan
        )

        assert 0 in bindings
        assert bindings[0] == [milestone]
        assert unmatched == []

    def test_empty_pulse_checks(self):
        plan = [_make_envelope("development.implement")]
        bindings, unmatched = resolve_milestone_bindings((), plan)
        assert bindings == {}
        assert unmatched == []

    def test_empty_plan(self):
        suite = _make_suite("s1", "post_dev", ("development",))
        bindings, unmatched = resolve_milestone_bindings((suite,), [])
        assert bindings == {}
        assert unmatched == [suite]

    def test_boundary_id_from_suite_not_plan(self):
        """boundary_id comes from suite.boundary_id, not derived from plan."""
        plan = [_make_envelope("development.implement", "t1")]
        suite = _make_suite("s1", "my_custom_boundary", ("development",))
        bindings, _ = resolve_milestone_bindings((suite,), plan)

        assert 0 in bindings
        assert bindings[0][0].boundary_id == "my_custom_boundary"

    def test_prefix_requires_dot_delimiter(self):
        """Prefix 'development' must NOT match 'developmentXYZ' (no dot)."""
        plan = [
            _make_envelope("developmentXYZ", "t1"),
            _make_envelope("development.implement", "t2"),
        ]
        suite = _make_suite("s1", "post_dev", ("development",))
        bindings, _ = resolve_milestone_bindings((suite,), plan)

        # Only index 1 (development.implement) matches, not index 0 (developmentXYZ)
        assert 1 in bindings
        assert 0 not in bindings


# ---------------------------------------------------------------------------
# collect_cadence_bound_suites
# ---------------------------------------------------------------------------


class TestCollectCadenceBoundSuites:
    def test_filters_cadence_only(self):
        cadence = _make_suite("cad", CADENCE_BOUNDARY_ID, (), "cadence")
        milestone = _make_suite("ms", "post_dev", ("development",))
        result = collect_cadence_bound_suites((cadence, milestone))
        assert result == [cadence]

    def test_empty_when_no_cadence(self):
        milestone = _make_suite("ms", "post_dev", ("development",))
        assert collect_cadence_bound_suites((milestone,)) == []

    def test_multiple_cadence_suites(self):
        c1 = _make_suite("c1", CADENCE_BOUNDARY_ID, (), "cadence")
        c2 = _make_suite("c2", CADENCE_BOUNDARY_ID, (), "cadence")
        result = collect_cadence_bound_suites((c1, c2))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# run_pulse_verification
# ---------------------------------------------------------------------------


class TestRunPulseVerification:
    async def test_returns_one_record_per_suite(self):
        check = _make_check("output.md")
        s1 = _make_suite("s1", "post_dev", checks=(check,))
        s2 = _make_suite("s2", "post_build", checks=(check,))

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(
                    check=check,
                    passed=True,
                    resolved_path="output.md",
                ),
            )
        )

        records = await run_pulse_verification(
            suites=[s1, s2],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run_001",
        )

        assert len(records) == 2
        assert records[0].suite_id == "s1"
        assert records[1].suite_id == "s2"

    async def test_record_carries_boundary_and_cadence_ids(self):
        check = _make_check()
        suite = _make_suite("s1", "post_dev", checks=(check,))

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(check=check, passed=True, resolved_path="x"),
            )
        )

        records = await run_pulse_verification(
            suites=[suite],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=3,
            run_id="run_001",
        )

        assert records[0].boundary_id == "post_dev"
        assert records[0].cadence_interval_id == 3
        assert records[0].run_id == "run_001"

    async def test_all_pass_yields_pass_outcome(self):
        check = _make_check()
        suite = _make_suite("s1", "post_dev", checks=(check,))

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(check=check, passed=True, resolved_path="x"),
            )
        )

        records = await run_pulse_verification(
            suites=[suite],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run_001",
        )

        assert records[0].suite_outcome == SuiteOutcome.PASS

    async def test_any_fail_yields_fail_outcome(self):
        check = _make_check()
        suite = _make_suite("s1", "post_dev", checks=(check,))

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(check=check, passed=False, resolved_path="x",
                                 error="not found"),
            )
        )

        records = await run_pulse_verification(
            suites=[suite],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run_001",
        )

        assert records[0].suite_outcome == SuiteOutcome.FAIL

    async def test_check_results_serialized(self):
        check = _make_check("output.md")
        suite = _make_suite("s1", "post_dev", checks=(check,))

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(
                    check=check, passed=True, resolved_path="output.md",
                    reason_code=None, metadata={"truncated": False},
                ),
            )
        )

        records = await run_pulse_verification(
            suites=[suite],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run_001",
        )

        cr = records[0].check_results
        assert len(cr) == 1
        assert cr[0]["check_type"] == "file_exists"
        assert cr[0]["passed"] is True
        assert cr[0]["metadata"] == {"truncated": False}

    async def test_repair_attempt_number_propagated(self):
        check = _make_check()
        suite = _make_suite("s1", "post_dev", checks=(check,))

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(check=check, passed=True, resolved_path="x"),
            )
        )

        records = await run_pulse_verification(
            suites=[suite],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run_001",
            repair_attempt_number=2,
        )

        assert records[0].repair_attempt_number == 2

    async def test_engine_called_with_suite_timeouts(self):
        check = _make_check()
        suite = PulseCheckDefinition(
            suite_id="s1",
            boundary_id="post_dev",
            checks=(check,),
            max_suite_seconds=15,
            max_check_seconds=5,
        )

        engine = AsyncMock()
        engine.evaluate_all_async.return_value = ValidationReport(
            results=(
                AcceptanceResult(check=check, passed=True, resolved_path="x"),
            )
        )

        await run_pulse_verification(
            suites=[suite],
            context=_ctx(),
            engine=engine,
            boundary_id="post_dev",
            cadence_interval_id=1,
            run_id="run_001",
        )

        engine.evaluate_all_async.assert_awaited_once_with(
            (check,), _ctx(),
            max_suite_seconds=15,
            max_check_seconds=5,
        )


# ---------------------------------------------------------------------------
# determine_boundary_decision
# ---------------------------------------------------------------------------


class TestDetermineBoundaryDecision:
    def test_all_pass(self):
        records = [
            PulseVerificationRecord(
                suite_id="s1", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.PASS,
            ),
            PulseVerificationRecord(
                suite_id="s2", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.PASS,
            ),
        ]
        assert determine_boundary_decision(records) == PulseDecision.PASS

    def test_any_fail(self):
        records = [
            PulseVerificationRecord(
                suite_id="s1", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.PASS,
            ),
            PulseVerificationRecord(
                suite_id="s2", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.FAIL,
            ),
        ]
        assert determine_boundary_decision(records) == PulseDecision.FAIL

    def test_all_fail(self):
        records = [
            PulseVerificationRecord(
                suite_id="s1", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.FAIL,
            ),
        ]
        assert determine_boundary_decision(records) == PulseDecision.FAIL

    def test_empty_records(self):
        assert determine_boundary_decision([]) == PulseDecision.PASS

    def test_skip_only_is_pass(self):
        """SKIP-only records should yield PASS (no guardrail evidence to block)."""
        records = [
            PulseVerificationRecord(
                suite_id="s1", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.SKIP,
            ),
        ]
        assert determine_boundary_decision(records) == PulseDecision.PASS

    def test_mixed_pass_and_skip(self):
        records = [
            PulseVerificationRecord(
                suite_id="s1", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.PASS,
            ),
            PulseVerificationRecord(
                suite_id="s2", boundary_id="b", cadence_interval_id=1,
                run_id="r", suite_outcome=SuiteOutcome.SKIP,
            ),
        ]
        assert determine_boundary_decision(records) == PulseDecision.PASS
