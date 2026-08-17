"""Which check opened the self-eval branch (#946).

Bug this guards: the self-eval branch is the sole trigger for a second model call, and
nothing recorded what opened it. Window roll 1 spent 3,574 completion tokens there — 68%
of the qa task's wall clock — and the run summary afterwards showed 29/29 checks accepted,
so the failure was unreadable from stored state. The only way to learn the cause was to
reconstruct it by hand from artifacts.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle.qa_test import failing_check_names

pytestmark = [pytest.mark.domain_capabilities]


def test_the_failing_check_is_named_not_counted():
    """ "1 check failed" sends a reader back to the artifacts, which is the state this
    exists to end. `expected_artifacts` is the one that matters: under fill mode the
    plan's chosen filename is demoted while this check still hard-requires it (#947)."""
    checks = [
        {"check": "expected_artifacts", "passed": False, "missing": ["__tests__/runs.test.ts"]},
        {"check": "non_stub_files", "passed": True},
    ]
    assert failing_check_names(checks) == ["expected_artifacts"]


def test_an_evidence_gap_is_not_reported_as_the_trigger():
    """Evidence-gap rows are honest non-passes the validator already refuses to fail the
    task on — a correction cannot repair an evaluator limitation. Naming one would send a
    reader chasing a check that caused nothing."""
    checks = [
        {"check": "acceptance:vc-x", "passed": False, "evidence_gap": True},
        {"check": "expected_artifacts", "passed": False},
    ]
    assert failing_check_names(checks) == ["expected_artifacts"]


def test_every_failing_check_is_named_when_several_fail():
    checks = [
        {"check": "expected_artifacts", "passed": False},
        {"check": "non_stub_files", "passed": False},
        {"check": "test_file_presence", "passed": True},
    ]
    assert failing_check_names(checks) == ["expected_artifacts", "non_stub_files"]


@pytest.mark.parametrize(
    "checks,expected",
    [
        ([], []),
        ([{"check": "a", "passed": True}], []),
        # a row with no `passed` key defaults to passing, matching _validate_output's own rule
        ([{"check": "a"}], []),
        # a failing row with no name is still reported rather than silently dropped
        ([{"passed": False}], ["unnamed"]),
    ],
)
def test_edge_shapes(checks, expected):
    assert failing_check_names(checks) == expected
