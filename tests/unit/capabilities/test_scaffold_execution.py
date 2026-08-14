"""The Gate 2 dynamic classifier corpus (SIP-0104 P2).

The classifier is the gate's judgment: which vitest failures are the *expected* wall of
stub assertion failures, and which are the mechanical class that means the generator shipped
a broken shell. Misclassifying in either direction is expensive — expected-as-mechanical
fails every valid scaffold; mechanical-as-expected ships the exact roll-14 tail this SIP
exists to end.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from squadops.capabilities.handlers.scaffold_execution import (
    SkeletonExecutionVerdict,
    classify_vitest_report,
    run_skeleton_execution_gate,
)

_SHELL_A = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
_SHELL_B = "__tests__/scaffold/vs-get-api-runs.scaffold.test.ts"


def _suite(path: str, results: list[dict], status: str = "failed", message: str = "") -> dict:
    return {
        "name": f"/tmp/ws/{path}",
        "status": status,
        "message": message,
        "assertionResults": results,
    }


def _failed(title: str, *messages: str) -> dict:
    return {"status": "failed", "title": title, "failureMessages": list(messages)}


def _report(*suites: dict) -> dict:
    return {"testResults": list(suites)}


class TestClassifier:
    @pytest.mark.parametrize(
        ("message", "expected_kind"),
        [
            # Measured (node:20-alpine, vitest 1.6, 2026-08-14): chai emits the BARE
            # message. The prefixed form is kept for reporter variants that do prefix.
            ("expected 500 to be 201 // Object.is equality", "assertion"),
            ("AssertionError: expected 500 to be 201", "assertion"),
            ("expected [ ] to have a length of 1 but got +0", "assertion"),
            ("TypeError: routeApiRuns.GET is not a function", "mechanical"),
            ("ReferenceError: Requests is not defined", "mechanical"),
            # Measured (defect gate run, 2026-08-14): vitest strips the error-name
            # prefix from a thrown ReferenceError too — the bare message is all there
            # is. A blocklist of error-name prefixes would have read this as expected;
            # the assertion-shape allowlist is what catches it.
            ("Requests is not defined", "mechanical"),
            ("SyntaxError: Unexpected token", "mechanical"),
            # Unknown shape → mechanical: the safe misclassification direction.
            ("something entirely unrecognized", "mechanical"),
        ],
    )
    def test_failure_shape_classification(self, message, expected_kind):
        verdict = classify_vitest_report(
            _report(_suite(_SHELL_A, [_failed("t", message)])), [_SHELL_A]
        )
        if expected_kind == "assertion":
            assert verdict.scaffold_valid and verdict.assertion_failures == 1
        else:
            assert not verdict.scaffold_valid and verdict.mechanical_failures

    def test_stub_assertion_failures_are_expected_and_the_scaffold_is_valid(self):
        """The bare skeleton MUST fail its shells (SIP-0098 §7) — that is not a defect."""
        verdict = classify_vitest_report(
            _report(
                _suite(
                    _SHELL_A,
                    [_failed("POST -> 201", "expected 500 to be 201 // Object.is equality")],
                ),
                _suite(
                    _SHELL_B,
                    [_failed("GET -> 200", "expected 500 to be 200 // Object.is equality")],
                ),
            ),
            [_SHELL_A, _SHELL_B],
        )
        assert verdict.scaffold_valid
        assert verdict.assertion_failures == 2
        assert verdict.mechanical_failures == ()

    def test_a_type_error_is_mechanical_and_names_the_shell(self):
        verdict = classify_vitest_report(
            _report(
                _suite(
                    _SHELL_A,
                    [_failed("POST -> 201", "expected 500 to be 201 // Object.is equality")],
                ),
                _suite(
                    _SHELL_B,
                    [_failed("GET -> 200", "TypeError: routeApiRuns.GET is not a function")],
                ),
            ),
            [_SHELL_A, _SHELL_B],
        )
        assert not verdict.scaffold_valid
        assert verdict.assertion_failures == 1
        assert any(_SHELL_B in f and "TypeError" in f for f in verdict.mechanical_failures)

    def test_a_suite_that_dies_before_any_test_is_mechanical(self):
        """The collection-level class: unresolved import / transform crash — the suite
        reports failed with zero assertion results and a message."""
        verdict = classify_vitest_report(
            _report(
                _suite(_SHELL_A, [], message="Failed to resolve import '@/app/api/run/route'"),
            ),
            [_SHELL_A],
        )
        assert not verdict.scaffold_valid
        assert any(
            "suite failed to run" in f and "Failed to resolve" in f
            for f in verdict.mechanical_failures
        )

    def test_a_shell_the_runner_never_saw_is_mechanical(self):
        """Silent non-collection must not read as valid — a missing shell is missing
        coverage that every other signal would report as green (the #884 class)."""
        verdict = classify_vitest_report(
            _report(_suite(_SHELL_A, [_failed("t", "expected 500 to be 200")])),
            [_SHELL_A, _SHELL_B],
        )
        assert not verdict.scaffold_valid
        assert verdict.missing_files == (_SHELL_B,)
        assert any("never collected" in f for f in verdict.mechanical_failures)

    def test_passing_shells_are_valid(self):
        """Against a developed app the shells pass — passing is never a gate failure."""
        verdict = classify_vitest_report(
            _report(
                _suite(
                    _SHELL_A,
                    [{"status": "passed", "title": "t", "failureMessages": []}],
                    status="passed",
                ),
            ),
            [_SHELL_A],
        )
        assert verdict.scaffold_valid
        assert verdict.assertion_failures == 0

    def test_non_scaffold_suites_are_outside_the_gate(self):
        """The harness proof and authored tests are the suite run's business; their
        failures must not condemn the generator."""
        verdict = classify_vitest_report(
            _report(
                _suite(_SHELL_A, [_failed("t", "expected 500 to be 200")]),
                _suite("__tests__/harness.test.ts", [_failed("h", "TypeError: boom")]),
            ),
            [_SHELL_A],
        )
        assert verdict.scaffold_valid

    def test_a_failure_with_no_message_is_mechanical_not_ignored(self):
        verdict = classify_vitest_report(
            _report(_suite(_SHELL_A, [_failed("t")])),
            [_SHELL_A],
        )
        assert not verdict.scaffold_valid
        assert any("no failure message" in f for f in verdict.mechanical_failures)

    def test_mixed_messages_where_any_is_non_assertion_are_mechanical(self):
        verdict = classify_vitest_report(
            _report(
                _suite(
                    _SHELL_A,
                    [
                        _failed(
                            "t",
                            "expected 500 to be 200",
                            "ReferenceError: Requests is not defined",
                        )
                    ],
                )
            ),
            [_SHELL_A],
        )
        assert not verdict.scaffold_valid


class TestRunnerLevelFailures:
    async def test_missing_node_toolchain_is_infrastructure_not_a_verdict(self):
        """A broken toolchain must never condemn a correct generator (§5: infrastructure,
        not scaffold-invalid)."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("npm")):
            verdict = await run_skeleton_execution_gate(
                [{"name": "package.json", "content": "{}"}],
                [{"name": _SHELL_A, "content": "// shell"}],
            )
        assert verdict == SkeletonExecutionVerdict(
            executed=False, error="npm not found — Node.js is not installed"
        )

    def test_summary_states_the_outcome_plainly(self):
        valid = classify_vitest_report(
            _report(_suite(_SHELL_A, [_failed("t", "expected 500 to be 200")])), [_SHELL_A]
        )
        assert "1 expected stub assertion failure" in valid.summary
        invalid = classify_vitest_report(_report(), [_SHELL_A])
        assert "scaffold-invalid" in invalid.summary and "never collected" in invalid.summary
        not_run = SkeletonExecutionVerdict(executed=False, error="npm not found")
        assert "did not run" in not_run.summary
