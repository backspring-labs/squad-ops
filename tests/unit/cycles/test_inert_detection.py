"""#684 (SIP-0096 §9) — inert-check detection: chronic not-executed streaks.

The design-gate bindings these tests enforce: only real-subject execution
resets a streak (absence pauses — the §9 disappearance/rename rule), only the
stable framework vocabulary participates, detection is derived on read from
persisted summaries (the multi-cycle real-store sequence below — the evidence
matrix's verification row), and a history-read failure yields empty inert,
never a failed roll-up.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.inert_detection import (
    INERT_CYCLE_THRESHOLD_DEFAULT,
    cycle_check_state,
    detect_inert_checks,
)
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import (
    RunVerdict,
    RunVerificationSummary,
    UnverifiedCheck,
)

pytestmark = [pytest.mark.domain_cycles]


def _state(executed=(), not_executed=()):
    return (frozenset(executed), frozenset(not_executed))


class TestDetectInertChecks:
    def test_streak_reaching_threshold_is_inert(self):
        # newest-first: three consecutive not-executed reports of a stable check
        states = [_state(not_executed=["tests_pass"])] * 3
        assert detect_inert_checks(states) == ("tests_pass",)

    def test_below_threshold_not_flagged(self):
        states = [_state(not_executed=["tests_pass"])] * 2
        assert detect_inert_checks(states) == ()

    def test_execution_resets_the_streak(self):
        # an execution between reports ends the streak before it reaches N
        states = [
            _state(not_executed=["tests_pass"]),
            _state(executed=["tests_pass"]),
            _state(not_executed=["tests_pass"]),
            _state(not_executed=["tests_pass"]),
        ]
        assert detect_inert_checks(states) == ()

    def test_absence_pauses_without_resetting(self):
        # §9: the counter resets ONLY on real execution — cycles where the
        # check is absent (disappeared/renamed/reclassified) pause the streak
        states = [
            _state(not_executed=["frontend_build"]),
            _state(),  # check absent — no reset
            _state(not_executed=["frontend_build"]),
            _state(),
            _state(not_executed=["frontend_build"]),
        ]
        assert detect_inert_checks(states) == ("frontend_build",)

    def test_current_cycle_execution_wins(self):
        # chronic history, but the perspective cycle executed the real subject
        states = [_state(executed=["tests_pass"])] + [_state(not_executed=["tests_pass"])] * 5
        assert detect_inert_checks(states) == ()

    def test_chronic_check_absent_now_stays_inert(self):
        # absent in the perspective cycle but chronic before — still inert
        # until a real execution clears it (absence never resets)
        states = [_state()] + [_state(not_executed=["required_files"])] * 3
        assert detect_inert_checks(states) == ("required_files",)

    def test_non_stable_ids_are_invisible(self):
        # plan-authored typed checks have per-cycle identity (§6.3) — excluded
        states = [_state(not_executed=["acceptance:api_returns_json"])] * 5
        assert detect_inert_checks(states) == ()

    def test_threshold_override(self):
        states = [_state(not_executed=["tests_pass"])] * 2
        assert detect_inert_checks(states, threshold=2) == ("tests_pass",)

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            detect_inert_checks([], threshold=0)


class TestCycleCheckState:
    def test_executed_supersedes_not_executed_within_a_cycle(self):
        # same reconciliation as the roll-up: a framing run's subject_missing
        # row is superseded by the impl run's real execution (#444)
        framing = RunVerificationSummary(
            verdict=RunVerdict.ACCEPTED,
            verified=(),
            failed=(),
            unverified=(UnverifiedCheck("tests_pass", "subject_missing", required=False),),
            required_unmet=(),
            executed_count=0,
            passed_count=0,
        )
        impl = RunVerificationSummary(
            verdict=RunVerdict.ACCEPTED,
            verified=("tests_pass",),
            failed=(),
            unverified=(),
            required_unmet=(),
            executed_count=1,
            passed_count=1,
        )
        executed, not_executed = cycle_check_state([framing, impl])
        assert "tests_pass" in executed
        assert "tests_pass" not in not_executed

    def test_no_summaries_is_absent_for_everything(self):
        assert cycle_check_state([]) == (frozenset(), frozenset())


# ---------------------------------------------------------------------------
# Multi-cycle real-store sequence (the evidence matrix's verification row):
# detection through resolve_cycle_outcome against the memory registry — real
# persisted summaries across cycles, not mocks.
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
_POLICY = TaskFlowPolicy(mode="sequential", gates=())


def _cycle(i: int, *, squad_profile="full", request_profile="selftest") -> Cycle:
    return Cycle(
        cycle_id=f"cyc_{i:03d}",
        project_id="proj_inert",
        created_at=_T0 + timedelta(hours=i),
        created_by="test",
        prd_ref=None,
        squad_profile_id=squad_profile,
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=_POLICY,
        build_strategy="fresh",
        request_profile=request_profile,
    )


def _summary(*, verified=(), not_executed=()) -> RunVerificationSummary:
    return RunVerificationSummary(
        verdict=RunVerdict.ACCEPTED,
        verified=tuple(verified),
        failed=(),
        unverified=tuple(
            UnverifiedCheck(cid, "missing_tooling", required=False) for cid in not_executed
        ),
        required_unmet=(),
        executed_count=len(verified),
        passed_count=len(verified),
    )


class TestInertRealStoreSequence:
    @staticmethod
    async def _add_cycle(registry, i, summary, **cycle_kw):
        cycle = _cycle(i, **cycle_kw)
        await registry.create_cycle(cycle)
        run = Run(
            run_id=f"run_{i:03d}",
            cycle_id=cycle.cycle_id,
            run_number=1,
            status="queued",
            initiated_by="test",
            resolved_config_hash="h",
        )
        await registry.create_run(run)
        await registry.record_run_verification_summary(run.run_id, summary)
        return cycle

    @pytest.fixture
    def registry(self):
        from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

        return MemoryCycleRegistry()

    async def test_three_chronic_cycles_flag_inert(self, registry):
        chronic = _summary(verified=["tests_pass"], not_executed=["frontend_build"])
        for i in range(3):
            newest = await self._add_cycle(registry, i, chronic)

        outcome = await resolve_cycle_outcome(registry, newest.cycle_id)

        assert outcome.inert == ("frontend_build",)
        assert "tests_pass" not in outcome.inert  # executes every cycle
        assert outcome.verdict is RunVerdict.ACCEPTED  # disclosure-only, never gates

    async def test_real_execution_clears_the_flag(self, registry):
        chronic = _summary(not_executed=["frontend_build"])
        for i in range(3):
            await self._add_cycle(registry, i, chronic)
        newest = await self._add_cycle(registry, 3, _summary(verified=["frontend_build"]))

        outcome = await resolve_cycle_outcome(registry, newest.cycle_id)

        assert outcome.inert == ()

    async def test_other_profile_cycles_are_outside_the_series(self, registry):
        # two chronic cycles on the perspective profile + interleaved chronic
        # cycles on ANOTHER profile: the series has only 2 reports → not inert
        # (cross-profile history must never accrue a streak — applicability differs)
        chronic = _summary(not_executed=["frontend_build"])
        await self._add_cycle(registry, 0, chronic)
        await self._add_cycle(registry, 1, chronic, squad_profile="lite", request_profile=None)
        await self._add_cycle(registry, 2, chronic, squad_profile="lite", request_profile=None)
        newest = await self._add_cycle(registry, 3, chronic)

        outcome = await resolve_cycle_outcome(registry, newest.cycle_id)

        assert outcome.inert == ()

    async def test_history_read_failure_yields_empty_inert(self, registry, monkeypatch):
        newest = await self._add_cycle(registry, 0, _summary(not_executed=["frontend_build"]))

        async def _boom(*a, **kw):
            raise RuntimeError("history unavailable")

        monkeypatch.setattr(registry, "list_cycles", _boom)
        outcome = await resolve_cycle_outcome(registry, newest.cycle_id)

        assert outcome.inert == ()  # containment: disclosure-only enrichment
        assert outcome.verdict is RunVerdict.ACCEPTED  # roll-up itself unharmed

    async def test_threshold_parameter_is_honored(self, registry):
        chronic = _summary(not_executed=["frontend_build"])
        for i in range(2):
            newest = await self._add_cycle(registry, i, chronic)

        strict = await resolve_cycle_outcome(registry, newest.cycle_id, inert_threshold=2)
        default = await resolve_cycle_outcome(registry, newest.cycle_id)

        assert strict.inert == ("frontend_build",)
        assert default.inert == ()  # config-default N=3 not yet reached


def test_config_default_matches_module_constant():
    """Drift guard: the SQUADOPS__CYCLES__INERT_CYCLE_THRESHOLD schema default
    and the module constant are the same declared N — a config edit that
    diverges them would make deployments and library use disagree silently."""
    from squadops.config.schema import CyclesConfig

    assert CyclesConfig().inert_cycle_threshold == INERT_CYCLE_THRESHOLD_DEFAULT


def test_outcome_dto_carries_inert():
    """#684 API threading: the roll-up's inert list survives into the DTO."""
    from squadops.api.routes.cycles.mapping import _cycle_outcome_to_dto
    from squadops.cycles.verification_integrity import CycleOutcome

    dto = _cycle_outcome_to_dto(
        CycleOutcome(
            verdict=RunVerdict.ACCEPTED,
            verified=("tests_pass",),
            failed=(),
            unverified=(),
            run_count=3,
            inert=("frontend_build",),
        )
    )
    assert dto.inert == ["frontend_build"]
