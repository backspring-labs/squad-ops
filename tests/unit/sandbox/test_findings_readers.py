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
    assert set(READERS) == {"ruff", "pytest", "lines"}
