"""#435 (1.5 A4) — failure-signature model + progress-aware termination.

The design-gate bindings these tests enforce: candidate presence alone can
never fire termination (89% of production deltas carry one — the M2→M3 gate
evaluation's finding), evidence text never alters a signature, and partial
reduction counts as progress. shk-4 is the canonical true positive.
"""

from __future__ import annotations

import pytest

from squadops.cycles.correction_signature import (
    MOVEMENT_EXPANSION,
    MOVEMENT_NEW,
    MOVEMENT_PROGRESS,
    MOVEMENT_REPEAT,
    MOVEMENT_SHIFTED,
    classify_movement,
    failure_signature,
    render_signature,
    should_terminate_plan_defect,
)

pytestmark = [pytest.mark.domain_cycles]


def _evidence(checks: list[dict], **extra) -> dict:
    return {"validation_result": {"passed": False, "checks": checks}, **extra}


_TESTS_FAIL_ROW = {
    "check": "tests_pass",
    "passed": False,
    "status": "failed",
    "reason": "exit 1",
    "file": "backend/tests/test_integration.js",
}


class TestFailureSignature:
    def test_failing_rows_become_elements(self):
        sig = failure_signature(
            _evidence([_TESTS_FAIL_ROW, {"check": "non_stub_files", "passed": True}])
        )
        assert sig == frozenset({("tests_pass", "backend/tests/test_integration.js", "exit 1")})

    def test_evidence_text_never_alters_the_signature(self):
        # a re-described identical failure must still repeat: tracebacks,
        # snippets, and summaries are outside the signature by construction
        a = _evidence([_TESTS_FAIL_ROW], app_tracebacks=[{"check": "x", "traceback": "T1"}])
        b = _evidence(
            [dict(_TESTS_FAIL_ROW)],
            app_tracebacks=[{"check": "x", "traceback": "T2 wholly different"}],
        )
        assert failure_signature(a) == failure_signature(b)

    def test_infra_rounds_have_no_signature(self):
        # A3 owns infra routing; these rounds are invisible to convergence
        assert failure_signature(_evidence([_TESTS_FAIL_ROW], extraction_loss=True)) is None
        assert (
            failure_signature(
                _evidence([_TESTS_FAIL_ROW], emission_failure={"reason": "no_fenced_blocks"})
            )
            is None
        )

    def test_no_failing_rows_is_none(self):
        assert failure_signature(_evidence([{"check": "c", "passed": True}])) is None
        assert failure_signature({}) is None


class TestMovement:
    _S = frozenset({("a", "f1", "r"), ("b", "f2", "r")})

    def test_classes(self):
        assert classify_movement(None, self._S) == MOVEMENT_NEW
        assert classify_movement(self._S, frozenset(self._S)) == MOVEMENT_REPEAT
        assert classify_movement(self._S, frozenset({("a", "f1", "r")})) == MOVEMENT_PROGRESS
        assert classify_movement(self._S, self._S | {("c", "f3", "r")}) == MOVEMENT_EXPANSION
        assert (
            classify_movement(self._S, frozenset({("a", "f1", "r"), ("z", "f9", "r")}))
            == MOVEMENT_SHIFTED
        )


class TestTerminationRule:
    _SIG = frozenset({("tests_pass", "backend/tests/test_integration.js", "exit 1")})

    def test_shk4_shape_terminates(self):
        # the canonical true positive: identical signature, candidates both rounds
        assert should_terminate_plan_defect(
            self._SIG, frozenset(self._SIG), "tighten_acceptance", "tighten_acceptance"
        )

    @pytest.mark.parametrize(
        ("prev_cand", "curr_cand"),
        [
            ("none", "tighten_acceptance"),
            ("tighten_acceptance", "none"),
            ("none", "none"),
            (None, "add_task"),
        ],
    )
    def test_candidate_missing_on_either_side_never_fires(self, prev_cand, curr_cand):
        # the false-positive guard: candidates are pervasive; the signature
        # repeat does the selecting, the candidates only confirm
        assert not should_terminate_plan_defect(
            self._SIG, frozenset(self._SIG), prev_cand, curr_cand
        )

    def test_first_round_never_fires(self):
        # the gate evaluation's false-positive population: single-round
        # candidate cycles that then converge
        assert not should_terminate_plan_defect(None, self._SIG, None, "tighten_acceptance")

    def test_progress_and_expansion_never_fire(self):
        smaller = frozenset({("tests_pass", "backend/tests/test_integration.js", "exit 1")})
        bigger = smaller | {("frontend_build", "", "failed")}
        assert not should_terminate_plan_defect(bigger, smaller, "add_task", "add_task")  # progress
        assert not should_terminate_plan_defect(
            smaller, bigger, "add_task", "add_task"
        )  # expansion — exact equality only, conservative by design

    def test_render_is_stable_and_sorted(self):
        sig = frozenset({("b", "f2", "r2"), ("a", "f1", "r1")})
        assert render_signature(sig) == ("a|f1|r1", "b|f2|r2")


class TestSuiteHealthDiscriminator:
    """#878 (minimum): the runner's structured suite_broken verdict joins the
    tests_pass reason token. Roll 15 (run_783f50a2d564): round 0 = suite RAN,
    assertions failed; round 1 = "No test files found" (suite_broken=True) —
    two different defects collapsed into one `tests_pass||failed` element and
    the run was terminated as a false exact-repeat, one round before the #886
    own-artifact routing would have repaired the second failure.
    """

    def test_behavioral_vs_discovery_rounds_are_not_a_repeat(self):
        ran = _evidence([{**_TESTS_FAIL_ROW, "reason": "failed", "suite_broken": False}])
        broken = _evidence([{**_TESTS_FAIL_ROW, "reason": "failed", "suite_broken": True}])
        sig_ran, sig_broken = failure_signature(ran), failure_signature(broken)

        assert sig_ran != sig_broken
        # the roll-15 shape: candidates on both rounds must STILL not fire
        assert not should_terminate_plan_defect(
            sig_ran, sig_broken, "tighten_acceptance", "tighten_acceptance"
        )

    def test_same_health_repeat_still_terminates(self):
        """The shk-4 true positive is preserved: two suite-ran rounds with the
        same aggregate reason remain an exact repeat."""
        a = failure_signature(
            _evidence([{**_TESTS_FAIL_ROW, "reason": "failed", "suite_broken": False}])
        )
        b = failure_signature(
            _evidence([{**_TESTS_FAIL_ROW, "reason": "failed", "suite_broken": False}])
        )

        assert a == b
        assert should_terminate_plan_defect(a, b, "tighten_acceptance", "add_task")

    def test_legacy_rows_without_verdict_are_byte_identical(self):
        """Absent suite_broken (None / pre-#626 rows, non-suite checks) the
        element must not change — signatures recorded before this fix still
        compare correctly against ones recorded after."""
        sig = failure_signature(_evidence([_TESTS_FAIL_ROW]))

        assert sig == frozenset({("tests_pass", "backend/tests/test_integration.js", "exit 1")})
