"""The Luau runner contract's reader (#2906; SIP-0117 R5.13).

Entered at ``findings.read``, which the sandbox applies to a check's whole output. The output is
what a product's ``tests/run.luau`` prints under the contract: a ``PASS`` line for each passing
test, a tagged ``FAIL`` line for each failure, and one ``Tests:`` summary.

What bugs would these catch?
- A failure to load what a test tests (``[setup]``) keyed as the test's own, so a require failure
  reads as discriminating.
- The product's own code raising (``[error]``) read as setup, so the test that catches a
  regression never discriminates.
- A pass credited by its absence among the failures: a summary whose passed count no ``PASS``
  lines account for read as readable.
- Output whose lines don't add up to its summary, or whose exit says otherwise, read as clean.
- A test's own print read as a result.
"""

from __future__ import annotations

import pytest

from squadops.sandbox.findings import ERROR, FAILED, LUAU, read

SPEC = "tests/Scoreboard.spec.luau"


def _output(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def test_each_failure_is_keyed_by_its_tag_and_the_summary_is_read():
    stdout = _output(
        "the shop opened",  # a test's own print
        "PASS: not a result line",
        f"PASS {SPEC} > award clamps at the cap",
        f"FAIL {SPEC} > leader is the top scorer [assertion] expected ada, got bob",
        f"FAIL {SPEC} > a tie keeps the first [error] attempt to index nil with 'score'",
        f"FAIL {SPEC} > resets on a new round [setup] before hook: require failed",
        "FAIL tests/Round.spec.luau [setup] module Round not found",
        "Tests: 1 passed, 1 failed, 1 errored, 2 setup, 5 total",
    )

    reading = read(LUAU, stdout, "", 1)

    assert reading.readable, reading.reason
    assert dict(reading.counts) == {
        f"{FAILED} {SPEC} > leader is the top scorer": 1,
        f"{FAILED} {SPEC} > a tie keeps the first": 1,
        f"{ERROR} {SPEC} > resets on a new round": 1,
        f"{ERROR} tests/Round.spec.luau": 1,
    }
    assert dict(reading.classes) == {
        f"{FAILED} {SPEC} > leader is the top scorer": "assertion",
        f"{FAILED} {SPEC} > a tie keeps the first": "error",
        f"{ERROR} {SPEC} > resets on a new round": "setup",
        f"{ERROR} tests/Round.spec.luau": "setup",
    }
    assert (reading.collected, reading.passed) == (5, 1)
    # #3089: each pass by its id, as its failures are keyed, so acceptance credits it by name.
    assert reading.passing == {f"{SPEC} > award clamps at the cap"}


def test_a_clean_run_reads_its_passes_and_no_failures():
    stdout = _output(
        f"PASS {SPEC} > award clamps at the cap",
        f"PASS {SPEC} > leader is the top scorer",
        "Tests: 2 passed, 0 failed, 0 errored, 0 setup, 2 total",
    )

    reading = read(LUAU, stdout, "", 0)

    assert (reading.readable, dict(reading.counts), reading.collected, reading.passed) == (
        True, {}, 2, 2
    )  # fmt: skip


_PASS = f"PASS {SPEC} > award clamps at the cap"
_ASSERTED = f"FAIL {SPEC} > leader is the top scorer [assertion] expected ada"


@pytest.mark.parametrize(
    ("lines", "exit_code", "says"),
    [
        ((_PASS,), 0, "printed 0 Tests: summaries"),
        (
            (_PASS, "Tests: 1 passed, 0 failed, 0 errored, 0 setup, 1 total") * 2,
            0,
            "printed 2 Tests: summaries",
        ),
        # A pass no PASS line names: never credited by its absence among the failures.
        (("Tests: 1 passed, 0 failed, 0 errored, 0 setup, 1 total",), 0, "and 0 PASS lines"),
        ((_PASS, "Tests: 1 passed, 1 failed, 0 errored, 0 setup, 2 total"), 1, "1 assertion"),
        ((_PASS, _ASSERTED, "Tests: 1 passed, 1 failed, 0 errored, 0 setup, 3 total"), 1, "add up to 2, not its total 3"),
        ((_PASS, _ASSERTED, "Tests: 1 passed, 1 failed, 0 errored, 0 setup, 2 total"), 0, "exited 0"),
        ((_PASS, "Tests: 1 passed, 0 failed, 0 errored, 0 setup, 1 total"), 2, "exited 2"),
    ],
    ids=[
        "no-summary", "two-summaries", "pass-unnamed", "failure-unnamed", "total-short",
        "exit-disagrees", "unfinished",
    ],
)  # fmt: skip
def test_output_that_doesnt_add_up_is_unreadable_never_clean(lines, exit_code, says):
    reading = read(LUAU, _output(*lines), "", exit_code)

    assert not reading.readable
    assert says in reading.reason
    assert reading.counts == {}


# ---- what each tag means at Campaign acceptance (§24ci (a)) ---------------------------------

_SUMMARY = "Tests: {p} passed, {f} failed, {e} errored, {s} setup, {t} total"
_NAME = "leader is the top scorer"


def _baseline(tag: str):
    return read(
        LUAU,
        _output(f"FAIL {SPEC} > {_NAME} [{tag}] it went wrong", _SUMMARY.format(
            p=0, f=int(tag == "assertion"), e=int(tag == "error"), s=int(tag == "setup"), t=1
        )),
        "",
        1,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("tag", "reason"),
    [
        ("assertion", "discriminates"),
        # The product's own code raised: the test reached it, so its failure is its own.
        ("error", "discriminates"),
        # Loading what it tests failed: the test never reached its assertion.
        ("setup", "only_setup_failures"),
    ],
)
def test_a_criterion_discriminates_on_its_tests_own_failures_never_on_setup(tag, reason):
    from squadops.campaigns.acceptance import discrimination_on_runner

    candidate = read(
        LUAU, _output(f"PASS {SPEC} > {_NAME}", _SUMMARY.format(p=1, f=0, e=0, s=0, t=1)), "", 0
    )

    found = discrimination_on_runner("C-1", LUAU, _baseline(tag), candidate)

    assert str(found.reason) == reason
    assert found.discriminating == ((f"{SPEC} > {_NAME}",) if reason == "discriminates" else ())
