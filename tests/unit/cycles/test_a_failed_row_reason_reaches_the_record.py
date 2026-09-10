"""A `passed: False` row's reason must survive to `failed_detail` (#1472).

Found by the 1.7.5 deploy-A' checkpoint pair, AFTER #1468 had already put the reason on the
`frontend_build` row and after that fix was verified loaded on the deploy. The run was still
rejected with `reason: ""`, because the reason was being dropped one layer further down: the
generic `_from_passed_row` built its `CheckResult` without a `reason=` on the FAILED branch,
so nothing a producer supplied could reach the record.

**This is a WIRING test, deliberately.** #1468 shipped with unit tests that handed the row
builder its input and asserted the row — which proved the seam and said nothing about whether
the reason reached the record. The live cycle then found exactly the gap those tests could not
see. So this one enters where the cycle enters, at `normalize_task_checks(outputs)`, runs the
real `aggregate_verification`, and asserts on `failed_detail` — the artifact a human actually
reads when a roll is rejected.

Bug classes guarded:

- **a required check rejecting a run with an unreadable reason.** `failed_detail` reads
  `CheckResult.reason`; a normalizer that never sets it makes every producer's diagnosis
  unreachable, however carefully the producer composed it;
- **the fix regressing to one check.** #510 closed this hole for `tests_pass` alone, via a
  dedicated normalizer. Anything reporting through a boolean `passed` row kept it. The
  parametrized case below covers a framework check that is NOT `tests_pass`, so a future
  narrowing fails here;
- **a passing row growing a reason**, which would make every green check look like a
  diagnosis.
"""

from __future__ import annotations

import pytest

from squadops.cycles.verification_integrity import aggregate_verification
from squadops.cycles.verification_normalize import normalize_task_checks

pytestmark = [pytest.mark.unit]


def _outputs(check: str, *, passed: bool, reason: str | None) -> dict:
    """One task's outputs in the shape the qa.test handler actually emits."""
    row: dict = {"check": check, "passed": passed}
    if reason is not None:
        row["reason"] = reason
    return {"validation_result": {"checks": [row]}}


def _failed_detail(check: str, *, passed: bool, reason: str | None):
    results = normalize_task_checks(_outputs(check, passed=passed, reason=reason), subject="t1")
    return aggregate_verification(results, required_check_ids=[check]).failed_detail


@pytest.mark.parametrize("check", ["frontend_build", "container_packaging", "required_files"])
def test_a_failing_rows_reason_reaches_failed_detail(check):
    """The whole point: what the producer said is what the record shows. Parametrized across
    checks so the fix cannot narrow back to the single one that prompted it."""
    detail = _failed_detail(check, passed=False, reason="exit_code 1: could not resolve './x'")

    assert [d.check_id for d in detail] == [check]
    assert detail[0].reason == "exit_code 1: could not resolve './x'"
    assert detail[0].required is True


def test_a_failing_row_without_a_reason_still_records_the_failure():
    """A producer that supplies nothing must still fail — the fix carries a reason, it does
    not invent one, and it must not swallow the failure when there is none to carry."""
    detail = _failed_detail("frontend_build", passed=False, reason=None)

    assert [d.check_id for d in detail] == ["frontend_build"]
    assert detail[0].reason == ""


def test_a_passing_row_produces_no_failed_detail_at_all():
    """The control. A reason on a green check would read as a diagnosis of a healthy run."""
    assert _failed_detail("frontend_build", passed=True, reason="ignored") == ()


def test_the_not_executed_path_is_unchanged():
    """#407's skip path already honored `reason` and must keep doing so — it is how a
    required frontend_build blocks on missing tooling instead of reading green (#306)."""
    outputs = {
        "validation_result": {
            "checks": [{"check": "frontend_build", "executed": False, "reason": "missing_tooling"}]
        }
    }
    results = normalize_task_checks(outputs, subject="t1")

    assert [r.reason for r in results] == ["missing_tooling"]
