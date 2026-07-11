"""Normalize task-result verification evidence into ``CheckResult`` (SIP-0096 Phase 2).

The Phase-1 pure core (`verification_integrity`) is deliberately producer-agnostic:
it classifies a normalized ``CheckResult`` and never knows the shape of any
producer. This module is the **producer adapter** the Phase-1 design deferred —
it maps a completed task's ``outputs`` (the qa/dev handlers' ``validation_result``
checks + ``test_result``) into ``CheckResult`` objects the executor records on the
``RunLedger``. Pure (dict → list[CheckResult]); no I/O.

Two producer shapes are folded here (both land in ``outputs`` and flow back to the
executor at the dispatch seam):

- **SIP-0092 typed-acceptance rows** (`check` = ``acceptance:<name>``) — emitted for
  *every* criterion, carrying a ``CheckOutcome`` ``status`` (passed/failed/skipped/
  error) directly. Per-cycle identity (§6.3): disclosed, not required-addressable.
- **Framework test-spine checks** — ``tests_pass`` and ``no_stub_fallback_tests`` are
  appended to ``checks`` **only on failure**, so a passing run records no row. Relying
  on the row alone would make a green run look like "no result" and — once the check
  is required (Phase 2 slice 4) — falsely block it. So ``tests_pass`` is synthesized
  from the always-present ``test_result`` dict, and the §6.6.1 stub signal
  (``no_stub_fallback_tests`` failing) marks that synthesized pass as a stub so it
  cannot credit.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from squadops.cycles.verification_integrity import (
    CheckProvenance,
    CheckResult,
    NotExecutedReason,
    ResultStatus,
)

# Framework test-spine check identities (stable, §6.3 required-addressable).
CHECK_TESTS_PASS = "tests_pass"
CHECK_NO_STUB = "no_stub_fallback_tests"


def normalize_task_checks(
    outputs: Mapping[str, Any], *, subject: str | None = None
) -> list[CheckResult]:
    """Map one completed task's ``outputs`` into recordable ``CheckResult``s (§6.1).

    ``subject`` is the producing plan-task id (``envelope.task_id``); it is stamped
    on every result so aggregation can supersede a repaired-and-re-run check to its
    final state per ``(check_id, subject)`` (§6.5, #379) — the same task re-verified
    collapses to its final outcome, while distinct tasks emitting the same
    ``check_id`` (e.g. ``tests_pass``) stay independent. ``None`` leaves the results
    un-identified (each counts on its own).

    Robust by construction — a malformed row is skipped, never raised, because this
    runs in the executor's per-task path and must never break task execution.
    Returns an empty list for tasks that carry no verification evidence.
    """
    results: list[CheckResult] = []
    validation = outputs.get("validation_result")
    checks = validation.get("checks") if isinstance(validation, Mapping) else None
    test_result = outputs.get("test_result")

    stub_detected = False
    for row in checks or ():
        if not isinstance(row, Mapping):
            continue
        cid = row.get("check")
        if not cid or not isinstance(cid, str):
            continue
        if cid == CHECK_TESTS_PASS:
            # Failure-only row; the real signal is synthesized from test_result
            # below (richer + present on a passing run). Skip to avoid double-record.
            continue
        if cid == CHECK_NO_STUB:
            # Present only when stubs were found → the stub check executed-and-failed,
            # and its presence flags the synthesized tests_pass as a stub (§6.6.1).
            stub_detected = True
            results.append(CheckResult(check_id=cid, status=ResultStatus.FAILED))
            continue
        if "status" in row:
            # Typed-acceptance row: carries a CheckOutcome status verbatim.
            results.append(
                CheckResult(
                    check_id=cid,
                    status=str(row.get("status") or ""),
                    reason=_str_or_none(row.get("reason")),
                )
            )
        else:
            # Generic boolean-passed row (e.g. non_stub_files): executed unless it
            # explicitly says otherwise.
            results.append(_from_passed_row(cid, row))

    if isinstance(test_result, Mapping):
        results.append(_tests_pass_from_result(test_result, is_stub=stub_detected))

    if subject is not None:
        results = [dataclasses.replace(r, subject=subject) for r in results]
    return results


def _from_passed_row(cid: str, row: Mapping[str, Any]) -> CheckResult:
    """Normalize a check row that carries a boolean ``passed`` (no ``status``)."""
    if row.get("executed") is False:
        return CheckResult(
            check_id=cid, status=ResultStatus.SKIPPED, reason=NotExecutedReason.SUBJECT_MISSING
        )
    status = ResultStatus.PASSED if row.get("passed") else ResultStatus.FAILED
    return CheckResult(check_id=cid, status=status)


def _tests_pass_from_result(tr: Mapping[str, Any], *, is_stub: bool) -> CheckResult:
    """Synthesize the ``tests_pass`` check from the always-present ``test_result``.

    ``executed=False`` → not-executed (reason mapped from the runner error);
    ``executed`` + exit 0 → passed; ``executed`` + non-zero → failed. ``is_stub``
    carries the §6.6.1 signal so a stub-backed pass is classified not-executed.
    """
    if not tr.get("executed", False):
        return CheckResult(
            check_id=CHECK_TESTS_PASS,
            status=ResultStatus.SKIPPED,
            reason=_not_executed_reason(tr),
        )
    tests_passed = tr.get("tests_passed")
    if tests_passed is None:
        tests_passed = tr.get("exit_code", 1) == 0
    return CheckResult(
        check_id=CHECK_TESTS_PASS,
        status=ResultStatus.PASSED if tests_passed else ResultStatus.FAILED,
        is_stub=is_stub,
        provenance=CheckProvenance(exit_code=_int_or_none(tr.get("exit_code"))),
    )


def _not_executed_reason(tr: Mapping[str, Any]) -> str:
    """Map a runner error string to a §7 not-executed reason (best-effort)."""
    err = str(tr.get("error") or "").lower()
    if "import" in err:
        return NotExecutedReason.IMPORT_ERROR
    if "not found" in err or "no module" in err or "command" in err:
        return NotExecutedReason.MISSING_TOOLING
    return NotExecutedReason.SUBJECT_MISSING


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None
