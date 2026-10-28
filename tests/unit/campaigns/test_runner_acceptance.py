"""§8.2 and §8.1 on a repository-backed product's own runner (SIP-0109 §24bv point 3, §24ci (a)),
read from real pytest 9 and vitest 2.1.9 output through the readers that carry each failure's
class (``tests/fixtures/findings``; how each was made is in ``test_findings_readers.py``).

What bugs would these catch?
- a criterion counted as discriminating because its file failed to import, or its suite never
  loaded, on the baseline: the failure §24ci (a) and #2602 rule out;
- a failure whose class the output didn't print read as the test's own;
- a runner with no test-id reader read whole, and a criterion accepted on it;
- a candidate run that ran fewer tests read as passing the ones it never ran;
- a frozen criterion credited on a run nobody could read, or one that ran no test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.campaigns.acceptance import (
    NO_READER_EXIT_ZERO,
    Discrimination,
    DiscriminationReason,
    Held,
    IncrementVerdict,
    discrimination_on_runner,
    held_on_runner,
    increment_acceptance,
)
from squadops.sandbox.findings import FindingsReading, read

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "findings"
R = DiscriminationReason


def _out(name: str) -> str:
    return (FIXTURES / name).read_text()


def _pytest(name: str) -> FindingsReading:
    return read("pytest", _out(name), "", 1)


def _vitest(name: str, exit_code: int) -> FindingsReading:
    return read(
        "vitest", _out(f"vitest-2.1.9-{name}.stdout.txt"), _out(f"vitest-2.1.9-{name}.stderr.txt"),
        exit_code,
    )  # fmt: skip


_ALL_PASS = read("pytest", "10 passed in 0.10s\n", "", 0)
_P = "tests/test_probe.py::"


@pytest.mark.parametrize(
    ("test_ids", "baseline", "candidate", "expected"),
    [
        (
            "pytest", _pytest("pytest-classes.txt"), _ALL_PASS,
            Discrimination("c1", True, R.DISCRIMINATES, (
                f"{_P}TestShelfList::test_counts[2]",
                f"{_P}test_a_test_whose_name_is_long_enough_to_push_the_short_summary_past_eighty"
                "_columns_of_width",
                f"{_P}test_asserts_a_value",
                f"{_P}test_asserts_with_a_message",
                f"{_P}test_fails_explicitly",
                f"{_P}test_raises_inside_the_app",
            )),
        ),
        ("pytest", _pytest("pytest-classes-tb-no.txt"), _ALL_PASS,
         Discrimination("c1", False, R.ONLY_SETUP_FAILURES)),
        ("vitest", _vitest("missing", 1), read("vitest", " Tests  1 passed (1)\n", "", 0),
         Discrimination("c1", False, R.ONLY_SETUP_FAILURES)),
        ("pytest", _pytest("pytest-classes.txt"), _pytest("pytest-classes.txt"),
         Discrimination("c1", False, R.FAILS_ON_CANDIDATE)),
        ("pytest", _ALL_PASS, _ALL_PASS, Discrimination("c1", False, R.NO_BASELINE_FAILURE)),
        (None, _pytest("pytest-classes.txt"), _ALL_PASS,
         Discrimination("c1", False, R.NO_TEST_ID_READER)),
        ("pytest", _pytest("pytest-classes.txt"), read("pytest", "9 passed in 0.1s\n", "", 0),
         Discrimination("c1", False, R.NOT_RUN)),
        ("pytest", _pytest("pytest-classes.txt"), read("pytest", "", "", 2),
         Discrimination("c1", False, R.NOT_RUN)),
        ("vitest", _pytest("pytest-classes.txt"), _ALL_PASS,
         Discrimination("c1", False, R.NOT_RUN)),
    ],
    ids=[
        "assertions-and-the-apps-errors-discriminate-imports-and-fixtures-dont",
        "no-class-printed-is-never-the-tests-own",
        "a-vitest-file-that-never-loaded",
        "fails-on-the-candidate-too",
        "nothing-failed-on-the-baseline",
        "a-runner-with-no-test-id-reader",
        "the-candidate-ran-fewer-tests",
        "the-candidate-unreadable",
        "read-by-another-reader",
    ],
)  # fmt: skip
def test_a_criterion_discriminates_on_a_products_runner_only_for_the_intended_reason(
    test_ids, baseline, candidate, expected
):
    assert discrimination_on_runner("c1", test_ids, baseline, candidate) == expected


def test_a_vitest_criterion_discriminates_by_its_assertions_and_not_by_a_reference_error():
    """The vitest reading's classes, end to end: real output's AssertionError and TypeError
    failures discriminate, and a ReferenceError (JavaScript's NameError, the suite's own) doesn't.
    Bug caught: vitest's classes read from the wrong line, so every failure reads as setup, or
    none does."""
    baseline = _vitest("asserting", 1)
    passed = read("vitest", " Tests  5 passed (5)\n", "", 0)
    referenced = FindingsReading(
        "vitest", 1, True, None,
        {"FAILED src/a.test.js > shows the shelf": 1}, 1,
        {"FAILED src/a.test.js > shows the shelf": "ReferenceError"},
    )  # fmt: skip

    found = discrimination_on_runner("c1", "vitest", baseline, passed)

    assert found.met and len(found.discriminating) == 4
    assert "src/__tests__/asserting.test.js > Book form > refuses an empty title" in (
        found.discriminating
    )
    assert discrimination_on_runner("c2", "vitest", referenced, passed).reason is (
        R.ONLY_SETUP_FAILURES
    )


def test_an_unread_discrimination_blocks_the_increment_and_never_reads_as_unmet():
    """§24ci (a)'s cost, as the owner ruled it: a Campaign whose criterion runs only on a runner
    with no test-id reader accepts no criterion. Bug caught: the criterion accepted, or the
    increment rejected as if its squad had failed a criterion nobody could read."""
    unread = discrimination_on_runner("c1", None, _ALL_PASS, _ALL_PASS)

    acceptance = increment_acceptance((unread,), (), ())

    assert acceptance.verdict is IncrementVerdict.BLOCKED_UNVERIFIED
    assert (acceptance.unmet, acceptance.blocked) == (
        (),
        ("criterion c1: its runner names no test",),
    )


@pytest.mark.parametrize(
    ("address", "test_ids", "exit_code", "reading", "held"),
    [
        (None, "pytest", 0, _ALL_PASS, (Held.BLOCKED_UNVERIFIED, "the verifier bundle is missing")),
        ("b1", "pytest", None, None, (Held.BLOCKED_UNVERIFIED, "the bundle never executed")),
        ("b1", "pytest", 0, _ALL_PASS, (Held.HELD, "")),
        ("b1", "vitest", 1, _vitest("missing", 1),
         (Held.BROKEN, "src/__tests__/missing.test.js")),
        ("b1", "vitest", 0, read("vitest", " Tests  no tests\n", "", 0),
         (Held.BLOCKED_UNVERIFIED, "the runner ran none of its tests")),
        ("b1", "pytest", 2, read("pytest", "", "", 2),
         (Held.BLOCKED_UNVERIFIED, "its run is unread: pytest exited 2: the run didn't finish its tests")),
        ("b1", None, 0, None, (Held.BLOCKED_UNVERIFIED, NO_READER_EXIT_ZERO)),
        ("b1", None, 1, None, (Held.BROKEN, "its test file exited 1 (read whole: no test-id reader)")),
        ("b1", "pytest", 0, read("pytest", "1 passed, 2 skipped in 0.02s\n", "", 0),
         (Held.BLOCKED_UNVERIFIED,
          "2 of its 3 tests didn't run to a pass (skipped, or expected to fail)")),
        ("b1", "pytest", 0, read("pytest", "3 skipped in 0.01s\n", "", 0),
         (Held.BLOCKED_UNVERIFIED,
          "3 of its 3 tests didn't run to a pass (skipped, or expected to fail)")),
        ("b1", "vitest", 0, read("vitest", " Tests  1 passed | 1 skipped (2)\n", "", 0),
         (Held.BLOCKED_UNVERIFIED,
          "1 of its 2 tests didn't run to a pass (skipped, or expected to fail)")),
        ("b1", "pytest", 0, FindingsReading("pytest", 1, True, None, {}, 2),
         (Held.BLOCKED_UNVERIFIED, "its reading doesn't say how many of its tests passed")),
    ],
    ids=["no-bundle", "never-ran", "held", "a-file-that-no-longer-loads", "ran-no-test",
         "unreadable", "no-reader-exit-0", "no-reader-failed", "pytest-some-skipped",
         "pytest-all-skipped", "vitest-one-skipped", "a-reading-with-no-pass-count"],
)  # fmt: skip
def test_a_frozen_criterion_holds_on_a_products_runner_only_on_a_run_that_was_read(
    address, test_ids, exit_code, reading, held
):
    assert held_on_runner(address, test_ids, exit_code, reading) == held
