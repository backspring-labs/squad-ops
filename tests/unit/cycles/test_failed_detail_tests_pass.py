"""#2086: a failed ``tests_pass`` round keeps why it failed.

#2028 kept a failed row's ``detail``, ``actual.stderr_tail`` or ``reason``, and a ``tests_pass`` row
carries none of them: its account is its failing cases and any runtime error the run caught. 2.1
rebuild 2's Next.js regression (``cyc_d94c3742bb88``) recorded ``failed_detail: []`` for its one
``tests_pass`` round, which is the bug these catch. The row is built by the runner's own builder
from a vitest report, as the qa task builds it.
"""

from __future__ import annotations

from squadops.capabilities.handlers.test_runner import (
    RunTestsResult,
    failed_tests_pass_row,
    parse_vitest_failure_rows,
)
from squadops.cycles.run_loop_summary import FAILED_DETAIL_LIMIT, failed_detail_of

_SUITE = "app/__tests__/runs.test.tsx"


def _report(*cases: tuple[str, str, int]) -> dict:
    return {
        "testResults": [
            {
                "name": f"/tmp/qa_node_x/{_SUITE}",
                "status": "failed",
                "assertionResults": [
                    {
                        "title": title,
                        "status": "failed",
                        "location": {"line": line - 3, "column": 3},
                        "failureMessages": [f"{message}\n    at /tmp/qa_node_x/{_SUITE}:{line}:9"],
                    }
                    for title, message, line in cases
                ],
            }
        ]
    }


def _row(report: dict, **result) -> dict:
    rows = parse_vitest_failure_rows(report, "/tmp/qa_node_x", [_SUITE])
    return failed_tests_pass_row(
        RunTestsResult(
            executed=True, exit_code=1, runner="vitest", test_failures=tuple(rows), **result
        )
    )


def test_a_failed_tests_pass_round_keeps_each_failing_case_and_the_runtime_error():
    row = _row(
        _report(("joins a run", "AssertionError: expected 'Full' to be 'Joined'", 42)),
        unhandled_errors=("TypeError: Cannot read properties of undefined (reading 'id')",),
    )

    [(check, text)] = failed_detail_of([row])

    assert check == "tests_pass"
    assert f"{_SUITE}:42 joins a run: AssertionError: expected 'Full' to be 'Joined'" in text
    assert "TypeError: Cannot read properties of undefined (reading 'id')" in text


def test_a_long_account_keeps_its_first_cases():
    """The first failing cases are where a reader starts, so a long account keeps the head."""
    many = [(f"case {n}", "AssertionError: " + "x" * 400, 10 + n) for n in range(12)]
    [(_, text)] = failed_detail_of([_row(_report(*many))])

    assert len(text) <= FAILED_DETAIL_LIMIT
    assert text.startswith(f"{_SUITE}:10 case 0:")


def test_a_row_with_its_own_reason_keeps_that_reason():
    """The control: #2028's fields still come first."""
    row = {"check": "frontend_build", "passed": False, "reason": "bundler exited 1: x.css missing"}

    assert failed_detail_of([row]) == (("frontend_build", "bundler exited 1: x.css missing"),)
