"""A check's findings, read from its whole output (#2609; ``squadops.sandbox.findings``), on real
output: continuum's ruff findings at the brownfield demonstration's commits, a pytest run with
failures and errors, a pytest collection error and a ruff tool error.

What bugs would these catch?
- a failing run the reader can't account for read as clean, so the baseline's failures vanish and
  read as an improvement (a collection error, a tool error, a summary the rows don't add up to);
- a finding keyed by its line, so an edit above it makes it new;
- the two ruff output formats read differently;
- stage 6's three new findings missed, or stage 3's change read as adding one;
- a pytest run that ran fewer tests compared as if it ran them all;
- two readers, or two versions, compared;
- a reading that doesn't round-trip, or one with a reader nobody declared.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.sandbox.findings import (
    MAX_KEYS,
    READERS,
    FindingsReading,
    UnknownReader,
    comparable,
    grown,
    read,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "findings"


def _out(name: str) -> str:
    return (FIXTURES / name).read_text()


def _ruff(name: str) -> FindingsReading:
    return read("ruff", _out(name), "", 1)


def test_continuums_findings_read_alike_in_either_ruff_format():
    full = _ruff("continuum-ba8fa68b-ruff-full.txt")
    concise = _ruff("continuum-ba8fa68b-ruff-concise.txt")

    assert full.readable and concise.readable
    assert full.counts == concise.counts
    assert (sum(full.counts.values()), len(full.counts)) == (59, 42)
    assert full.counts["I001 src/continuum/adapters/web/api.py"] == 1


@pytest.mark.parametrize(
    ("baseline", "candidate", "expected"),
    [
        (
            "continuum-ba8fa68b-ruff-concise.txt",
            "continuum-0c814a7c-ruff-concise.txt",
            {
                "E501 tests/test_cli_inspect_version.py": (0, 1),
                "F401 tests/test_cli_inspect_version.py": (0, 1),
                "I001 src/continuum/cli.py": (0, 1),
            },
        ),
        ("continuum-43369054-ruff-concise.txt", "continuum-2f6b3baa-ruff-concise.txt", {}),
    ],
    ids=["stage-6-adds-three", "stage-3-adds-none"],
)
def test_the_demonstrations_changes_read_as_ruff_counted_them(baseline, candidate, expected):
    before, after = _ruff(baseline), _ruff(candidate)

    assert comparable(before, after) is None
    assert grown(before, after) == expected


def test_a_pytest_run_keys_its_failures_and_errors_by_node_and_counts_what_it_ran():
    reading = read("pytest", _out("pytest-failures.txt"), "", 1)

    assert reading.readable
    assert reading.counts == {
        "ERROR tests/test_c.py::test_uses": 1,
        "FAILED tests/test_a.py::test_bad": 1,
        "FAILED tests/test_c.py::test_param[2]": 1,
    }
    assert reading.collected == 5


@pytest.mark.parametrize(
    ("reader", "stdout", "exit_code", "reason"),
    [
        ("ruff", _out("ruff-exit2-unknown-selector.txt"), 2, "ruff exited 2"),
        ("ruff", "src/a.py:1:1: F401 `os` imported but unused\nFound 2 errors.\n", 1, "found 2"),
        ("ruff", "something went wrong\n", 1, "no finding was read"),
        ("pytest", _out("pytest-collection-error.txt"), 2, "pytest exited 2"),
        ("pytest", "FAILED tests/t.py::test_a - boom\n", 1, "no summary"),
        ("pytest", "FAILED tests/t.py::test_a - boom\n2 failed in 0.1s\n", 1, "2 failing"),
        ("lines", "\n\n", 3, "no output"),
    ],
    ids=[
        "ruff-tool-error",
        "ruff-rows-short-of-its-summary",
        "ruff-failed-unread",
        "pytest-collection-error",
        "pytest-no-summary",
        "pytest-rows-short-of-its-summary",
        "lines-failed-silent",
    ],
)
def test_a_run_the_reader_cant_account_for_is_unreadable_never_clean(
    reader, stdout, exit_code, reason
):
    reading = read(reader, stdout, "", exit_code)

    assert not reading.readable
    assert reason in reading.reason
    assert reading.counts == {}


@pytest.mark.parametrize("name", ["ruff-syntax-error-full.txt", "ruff-syntax-error-concise.txt"])
def test_a_syntax_error_is_keyed_as_ruff_counts_it_never_left_unread(name):
    """The Spark lane's G4 on #2620. Bug caught: ruff's syntax errors, which carry no rule code and
    which its "Found" line counts, left unkeyed, so a candidate that breaks a file reads unreadable
    rather than as the finding it added."""
    reading = _ruff(name)

    assert reading.readable
    assert reading.counts == {"invalid-syntax src/broken.py": 2, "F401 src/ok.py": 1}


@pytest.mark.parametrize(
    ("reader", "stdout", "collected"),
    [("ruff", "All checks passed!\n", None), ("pytest", "5 passed in 0.10s\n", 5),
     ("lines", "", None)],
    ids=["ruff", "pytest", "lines"],
)  # fmt: skip
def test_a_run_that_passed_reads_with_no_findings(reader, stdout, collected):
    """Bug caught: a passing check's stored reading saying it was a tool error."""
    reading = read(reader, stdout, "", 0)

    assert (reading.readable, reading.counts, reading.collected) == (True, {}, collected)


def test_more_distinct_findings_than_the_bound_is_unreadable_never_a_partial_count():
    stdout = "".join(f"src/m{n}.py:1:1: F401 unused\n" for n in range(MAX_KEYS + 1))

    reading = read("ruff", stdout, "", 1)

    assert not reading.readable and "too many findings" in reading.reason


def test_a_lines_reading_keys_a_line_with_its_digits_replaced():
    reading = read("lines", "lint: 3 problems in a.js:12\n", "", 1)

    assert reading.counts == {"lint: # problems in a.js:#": 1}


def _reading(reader="ruff", version=1, readable=True, counts=None, collected=None):
    return FindingsReading(reader, version, readable, None, counts or {"F401 a.py": 1}, collected)


@pytest.mark.parametrize(
    ("baseline", "candidate", "why"),
    [
        (_reading(), _reading(reader="lines"), "read by lines v1"),
        (_reading(), _reading(version=2), "read by ruff v2"),
        (_reading(), _reading(readable=False), "the candidate is unreadable"),
        (_reading(readable=False), _reading(), "the baseline is unreadable"),
        (
            _reading("pytest", collected=40),
            _reading("pytest", collected=39),
            "ran 39 tests, fewer than its baseline's 40",
        ),
    ],
    ids=["another-reader", "another-version", "candidate-unread", "baseline-unread", "fewer-tests"],
)
def test_two_readings_compare_only_like_with_like(baseline, candidate, why):
    assert why in comparable(baseline, candidate)


def test_a_reading_round_trips_and_one_with_an_undeclared_reader_is_refused():
    reading = read("pytest", _out("pytest-failures.txt"), "", 1)

    assert FindingsReading.from_dict(reading.as_dict()) == reading
    with pytest.raises(UnknownReader):
        read("eslint", "", "", 1)
    with pytest.raises(UnknownReader):
        FindingsReading.from_dict({**reading.as_dict(), "reader": "eslint"})
    with pytest.raises(ValueError, match="positive integers"):
        FindingsReading.from_dict({**reading.as_dict(), "counts": {"FAILED x": 0}})
    for bad in ("5", -1, True):
        with pytest.raises(ValueError, match="collected"):
            FindingsReading.from_dict({**reading.as_dict(), "collected": bad})
    with pytest.raises(ValueError, match="classes"):
        FindingsReading.from_dict({**reading.as_dict(), "classes": {"FAILED uncounted": "Error"}})
    assert set(READERS) == {"ruff", "pytest", "lines", "vitest"}


# ---- SIP-0109 §24ci (a): each failure's exception class, and a vitest reader (#2757) ----------
# pytest-classes*.txt is pytest 9.0.2's output, `pytest -q -p no:cacheprovider` with --tb's default,
# `short` and `no`, over an invented module of nine tests: an assertion, one with a message, an
# AttributeError in the test, an import of a module only a candidate would have, a fixture that
# raises, a name long enough that the short summary drops its message, pytest.fail, and a
# parametrized method that fails one case. vitest-2.1.9-*.txt is vitest 2.1.9 run by a product's own
# `npm --prefix frontend test --silent` (`"test": "vitest run"`) with no TTY, as the sandbox runs a
# check, over invented files: the whole suite (`default`, and `ci` with CI=true, which colours it),
# and one file at a time through `-- <name>`, as H.7's one-file argv does.

_PROBE = "tests/test_probe.py::"
_ALL_CLASSES = {
    f"ERROR {_PROBE}test_needs_a_broken_fixture": "RuntimeError",
    f"FAILED {_PROBE}TestShelfList::test_counts[2]": "AssertionError",
    f"FAILED {_PROBE}test_a_test_whose_name_is_long_enough_to_push_the_short_summary_past_eighty"
    "_columns_of_width": "AssertionError",
    f"FAILED {_PROBE}test_asserts_a_value": "AssertionError",
    f"FAILED {_PROBE}test_asserts_with_a_message": "AssertionError",
    f"FAILED {_PROBE}test_fails_explicitly": "Failed",
    f"FAILED {_PROBE}test_imports_what_only_the_candidate_has": "ModuleNotFoundError",
    f"FAILED {_PROBE}test_raises_inside_the_app": "AttributeError",
}


@pytest.mark.parametrize(
    ("name", "unread"),
    [
        ("pytest-classes.txt", set()),
        # --tb=short prints no crash line: a bare assert's E line names no class.
        ("pytest-classes-tb-short.txt", {f"FAILED {_PROBE}TestShelfList::test_counts[2]"}),
        ("pytest-classes-tb-no.txt", set(_ALL_CLASSES)),
    ],
    ids=["tb-auto", "tb-short", "tb-no"],
)
def test_pytest_carries_each_failures_class_from_its_report_and_never_guesses_one(name, unread):
    """Bugs caught: a class read from the short summary, which pytest cuts at 80 columns
    ("Module…", or nothing past a long node id); an import failure read as an assertion; a class
    guessed where the report prints none, so an unread failure reads as the test's own."""
    reading = read("pytest", _out(name), "", 1)

    assert reading.readable and set(reading.counts) == set(_ALL_CLASSES)
    assert reading.classes == {k: v for k, v in _ALL_CLASSES.items() if k not in unread}


def test_a_class_two_tests_name_alike_could_be_is_left_unread():
    """The edge: one test name in two files, so a section's head names either. Bug caught: the
    class of one file's failure given to the other's."""
    report = (
        "=================================== FAILURES ===================================\n"
        "___________________________________ test_x ___________________________________\n"
        "tests/a/test_m.py:3: ImportError\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/a/test_m.py::test_x\nFAILED tests/b/test_m.py::test_x\n"
        "2 failed in 0.01s\n"
    )

    reading = read("pytest", report, "", 1)

    assert (reading.readable, reading.classes) == (True, {})


def _vitest(name: str, exit_code: int) -> FindingsReading:
    return read(
        "vitest", _out(f"vitest-2.1.9-{name}.stdout.txt"), _out(f"vitest-2.1.9-{name}.stderr.txt"),
        exit_code,
    )  # fmt: skip


_ASSERTING = "FAILED src/__tests__/asserting.test.js > "


def test_vitest_keys_each_failure_by_its_file_and_name_path_with_its_class():
    """#2757. Bugs caught: a test-id reader that splits a name holding " > " ("when saved >
    twice"); a file that never loaded read as clean, or as a test's own failure; the colours a CI
    run adds read as other keys."""
    reading = _vitest("default", 1)

    assert (reading.readable, reading.collected) == (True, 7)
    assert reading.counts == {
        "ERROR src/__tests__/missing.test.js": 1,
        f"{_ASSERTING}Book form > refuses an empty title": 1,
        f"{_ASSERTING}Book form > when saved > twice > names the duplicate": 1,
        f"{_ASSERTING}Book form > throws inside the app": 1,
        f"{_ASSERTING}Setup that breaks > never reaches its body": 1,
    }
    assert reading.classes == {
        "ERROR src/__tests__/missing.test.js": "Error",
        f"{_ASSERTING}Book form > refuses an empty title": "AssertionError",
        f"{_ASSERTING}Book form > when saved > twice > names the duplicate": "AssertionError",
        f"{_ASSERTING}Book form > throws inside the app": "TypeError",
        # vitest gives a beforeEach failure to its test: it reads as the test's own (H.10).
        f"{_ASSERTING}Setup that breaks > never reaches its body": "TypeError",
    }
    assert _vitest("ci", 1) == reading


@pytest.mark.parametrize(
    ("name", "exit_code", "counts", "collected"),
    [
        ("passing", 0, {}, 2),
        ("skipping", 0, {}, 3),
        ("missing", 1, {"ERROR src/__tests__/missing.test.js": 1}, 0),
    ],
    ids=["one-file-passing", "skipped-and-todo-counted", "a-file-that-never-loaded"],
)
def test_vitest_reads_one_file_as_the_one_file_argv_runs_it(name, exit_code, counts, collected):
    reading = _vitest(name, exit_code)

    assert (reading.readable, reading.counts, reading.collected) == (True, counts, collected)


_SUMMARY = " Test Files  1 failed (1)\n      Tests  1 failed | 1 passed (2)\n"
_ONE_FAILED = "⎯⎯ Failed Tests 1 ⎯⎯\n\n FAIL  src/a.test.js > shows it\nAssertionError: no\n"


@pytest.mark.parametrize(
    ("stdout", "stderr", "exit_code", "reason"),
    [
        (_out("vitest-2.1.9-nofile.stdout.txt"), _out("vitest-2.1.9-nofile.stderr.txt"), 1,
         "no summary"),
        (_SUMMARY, "", 1, "summary has 1 failed, and 0 rows"),
        (_SUMMARY + "     Errors  1 error\n", _ONE_FAILED, 1, "unhandled errors"),
        (_SUMMARY, _ONE_FAILED.replace("Tests 1", "Tests 2"), 1, "summary has 1 failed"),
        (_SUMMARY, _ONE_FAILED + "⎯⎯ Failed Suites 1 ⎯⎯\n", 1, "1 failed suites, and 0 rows"),
        (_SUMMARY, _ONE_FAILED, 0, "exited 0, and 1 failures read"),
        (_SUMMARY, _ONE_FAILED, 2, "vitest exited 2"),
    ],
    ids=["no-test-files", "failures-unread", "unhandled-errors", "section-short-of-its-count",
         "suites-short-of-their-count", "exit-0-with-failures", "a-tool-error"],
)  # fmt: skip
def test_a_vitest_run_it_cant_account_for_is_unreadable_never_clean(
    stdout, stderr, exit_code, reason
):
    """Bugs caught: "No test files found" read as clean; a run vitest itself says may hold false
    results read as true; failures the summary counts and no row names, so they vanish."""
    reading = read("vitest", stdout, stderr, exit_code)

    assert not reading.readable
    assert reason in reading.reason
    assert reading.counts == {}


def test_a_reading_with_classes_round_trips_and_one_without_is_stored_as_before():
    """Bug caught: every stored reading's document changed by an empty ``classes`` key, or the
    classes lost crossing the sandbox's boundary (``as_dict``, then ``from_dict``)."""
    with_classes = _vitest("default", 1)
    without = read("ruff", "All checks passed!\n", "", 0)

    assert FindingsReading.from_dict(with_classes.as_dict()) == with_classes
    assert FindingsReading.from_dict(with_classes.as_dict()).classes == with_classes.classes
    assert "classes" not in without.as_dict()


@pytest.mark.parametrize(
    ("reader", "stdout", "stderr", "exit_code", "collected", "passed"),
    [
        ("pytest", _out("pytest-classes.txt"), "", 1, 10, 2),
        ("vitest", _out("vitest-2.1.9-asserting.stdout.txt"),
         _out("vitest-2.1.9-asserting.stderr.txt"), 1, 5, 1),
        ("vitest", _out("vitest-2.1.9-skipping.stdout.txt"),
         _out("vitest-2.1.9-skipping.stderr.txt"), 0, 3, 1),
        ("pytest", "3 skipped in 0.01s\n", "", 0, 3, 0),
    ],
    ids=["pytest-failing", "vitest-failing", "vitest-skipping-and-todo", "pytest-all-skipped"],
)  # fmt: skip
def test_a_test_runners_reading_says_how_many_of_its_tests_passed(
    reader, stdout, stderr, exit_code, collected, passed
):
    """SIP-0109 §24cl item 13: a run that collected tests and failed none may have run none.
    Bugs caught: a skipped or todo test counted as passed, so a frozen criterion whose tests never
    ran reads held; the pass count lost on the way to the runtime, so every criterion blocks."""
    reading = read(reader, stdout, stderr, exit_code)

    assert (reading.readable, reading.collected, reading.passed) == (True, collected, passed)
    assert FindingsReading.from_dict(reading.as_dict()).passed == passed


@pytest.mark.parametrize("bad", [-1, True, "2"], ids=["negative", "a-bool", "a-string"])
def test_a_stored_pass_count_that_isnt_one_is_refused_and_one_stored_before_reads_as_before(bad):
    """The count is additive: a reading stored before it has none and reads back unchanged, and
    one that isn't a count is refused, never read as zero. Ruff names no tests, so has none."""
    old = {"reader": "pytest", "version": 1, "readable": True, "counts": {}, "collected": 2}

    assert FindingsReading.from_dict(old).passed is None
    assert "passed" not in FindingsReading.from_dict(old).as_dict()
    assert read("ruff", "", "", 0).passed is None
    with pytest.raises(ValueError, match="passed tests are a count"):
        FindingsReading.from_dict({**old, "passed": bad})
