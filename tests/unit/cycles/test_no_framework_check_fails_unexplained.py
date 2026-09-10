"""No framework check may fail with an empty reason (#1472).

The guard for a defect family that cost the 1.7.5 line two deploys. `failed_detail` reads
`CheckResult.reason`; a required check that rejects a roll while leaving it empty is a verdict
nobody can act on, and the 1.7.5 deploy-A pair produced exactly that twice — once on each
stack — while the boot audit built and booted the same application.

The family had two layers, both closed here, and this module exists so a third cannot open:

* the NORMALIZER dropped `reason` on the failed branch, so nothing a producer supplied
  survived (#1472);
* eight PRODUCERS never set one, so opening the channel alone would have left it empty for
  them. `_derived_failure_reason` composes one from the row's own evidence.

Bug classes guarded:

- **a new framework check landing with no reason.** Parametrized over the live
  `FRAMEWORK_CHECKS` registry rather than a hand-listed set, so a check added later is
  covered the day it registers, which is the gap `_COUNTING_SETS` had for three release lines;
- **the derived reason becoming non-deterministic**, which would put a traversal-order change
  into `correction_signature` and make every round read as SHIFTED — A4 would never terminate
  and the run would burn its whole budget;
- **the derived reason swallowing the producer's own**, which would discard the better text.
"""

from __future__ import annotations

import pytest

from squadops.cycles.check_registry import FRAMEWORK_CHECKS
from squadops.cycles.correction_signature import failure_signature
from squadops.cycles.verification_integrity import aggregate_verification
from squadops.cycles.verification_normalize import normalize_task_checks

pytestmark = [pytest.mark.unit]


def _detail(row: dict, outputs: dict | None = None):
    """Normalize one task's outputs the way the cycle does, then aggregate.

    `tests_pass` is deliberately special: it is the ONE framework check with a dedicated
    normalizer (#510), reading `test_result` rather than a `validation_result` row. Feeding it
    a row shape it never receives would make this guard pass while testing nothing.
    """
    payload = outputs if outputs is not None else {"validation_result": {"checks": [row]}}
    results = normalize_task_checks(payload, subject="t1")
    return aggregate_verification(results, required_check_ids=[row["check"]]).failed_detail


#: One realistic FAILING row per framework check, in the shape its producer actually emits.
#: Values are what the producer carries — the point is that none of them sets `reason`.
_FAILING_ROWS = {
    "required_files": {"passed": False, "missing": ["Dockerfile"], "required": ["Dockerfile"]},
    "frontend_build": {"passed": False, "exit_code": 1, "reason": "frontend build failed (exit 1)"},
    # its own normalizer (#510), so it is fed the shape that normalizer actually reads
    "tests_pass": {
        "test_result": {
            "executed": True,
            "tests_passed": False,
            "exit_code": 1,
            "summary": "2 failed",
        }
    },
    "no_stub_fallback_tests": {"passed": False, "offenders": ["t.py::test_x"]},
    "no_self_mocking_tests": {"passed": False, "offenders": ["t.py::test_y"]},
}


@pytest.mark.parametrize("check", sorted(FRAMEWORK_CHECKS))
def test_every_framework_check_explains_its_own_failure(check):
    """The registry is the parameter source, so a check added later cannot skip this."""
    assert check in _FAILING_ROWS, (
        f"{check!r} is a framework check with no failing row here — add one, and make sure it "
        "can state why it failed"
    )
    spec = _FAILING_ROWS[check]
    outputs = {"test_result": spec["test_result"]} if "test_result" in spec else None
    detail = _detail(
        {"check": check, **{k: v for k, v in spec.items() if k != "test_result"}}, outputs
    )

    assert [d.check_id for d in detail] == [check]
    assert detail[0].reason, f"{check} failed with an empty reason — undiagnosable from evidence"


def test_a_producers_own_reason_is_preferred_over_the_derived_one():
    """The derived reason is a FALLBACK. Overwriting a producer's text would discard the
    better message — `frontend_build` composes an exit code and a summary."""
    detail = _detail(
        {
            "check": "frontend_build",
            "passed": False,
            "exit_code": 1,
            "reason": "frontend build failed (exit 1)",
            "detail": "Could not resolve './x'",
        }
    )

    assert detail[0].reason == "frontend build failed (exit 1)"


def test_the_derived_reason_is_byte_identical_across_key_and_member_order():
    """Determinism, because this feeds correction_signature. Two rounds reporting the same
    failure must render identically or a genuine repeat reads as a shift, A4 never terminates,
    and the run burns its whole budget."""
    a = {
        "check": "required_files",
        "passed": False,
        "missing": ["b.py", "a.py"],
        "required": ["a.py", "b.py"],
    }
    b = {
        "check": "required_files",
        "passed": False,
        "required": ["b.py", "a.py"],
        "missing": ["a.py", "b.py"],
    }

    assert _detail(a)[0].reason == _detail(b)[0].reason


def test_fixing_some_of_the_failures_moves_the_signature():
    """The intended flip side: a repair that fixes two of three missing files must read as
    PROGRESS, not as the collapsed repeat that cost the deploy-A rolls."""

    def ev(r):
        return {"validation_result": {"checks": [r]}}

    before = {"check": "required_files", "passed": False, "missing": ["a.py", "b.py", "c.py"]}
    after = {"check": "required_files", "passed": False, "missing": ["c.py"]}

    assert failure_signature(ev(before)) != failure_signature(ev(after))


def test_a_row_with_no_evidence_at_all_reports_no_invented_reason():
    """An absent reason is honest when the producer carried nothing; restating the status as
    prose would look like evidence and be none."""
    detail = _detail({"check": "required_files", "passed": False})

    assert detail[0].reason == ""


def test_a_long_evidence_list_is_bounded():
    """This rides on a signature and into a stored record; an unbounded file list belongs in
    neither."""
    detail = _detail(
        {"check": "required_files", "passed": False, "missing": [f"f{i}.py" for i in range(50)]}
    )

    assert len(detail[0].reason) <= 500
    assert "more" in detail[0].reason


class TestTheDerivedReasonRespectsThePerFailureSplit:
    """A row that failure_signature SPLITS must not also get a derived reason (#1472).

    Caught on the deploy-A" React roll, in my own fix. `failing_tests` was excluded from the
    derivation by name, and `failing_cases` and `suite_defects` — which co-vary with exactly
    the same failure set — walked straight back in. A repair that fixed two of three failures
    then read as SHIFTED instead of PROGRESS, which is the precise defect the exclusion was
    added to prevent.

    Naming co-varying fields one at a time is the wrong shape: the list grows and the next
    field silently reopens it. The rule is that a row carrying per-failure identities already
    HAS its discrimination and needs no derived token.
    """

    @staticmethod
    def _suite_row(tests, cases):
        return {
            "check": "tests_pass",
            "passed": False,
            "exit_code": 1,
            "runner": "pytest",
            "suite_broken": False,
            "tests_passed": False,
            "failing_tests": tests,
            "failing_cases": cases,
            "suite_defects": [],
        }

    def test_a_partial_repair_of_a_split_row_still_reads_as_progress(self):
        def ev(r):
            return {"validation_result": {"checks": [r]}}

        both = failure_signature(ev(self._suite_row(("a::x", "a::y", "a::z"), ["x", "y", "z"])))
        one = failure_signature(ev(self._suite_row(("a::x",), ["x"])))

        assert one < both, (
            "a partial repair stopped being a strict subset — PROGRESS became SHIFTED"
        )

    def test_an_unsplit_row_still_gets_its_derived_reason(self):
        """The control: the fallback must keep working where it was actually needed. Without
        this, 'skip when split' could be over-applied and silently disable the whole fix."""
        detail = _detail({"check": "required_files", "passed": False, "missing": ["Dockerfile"]})

        assert detail[0].reason == "missing=[Dockerfile]"
