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
import hashlib
from collections.abc import Mapping
from typing import Any

from squadops.cycles.check_registry import (
    CHECK_NO_STUB_FALLBACK_TESTS as CHECK_NO_STUB,
)
from squadops.cycles.check_registry import (
    CHECK_TESTS_PASS,
)
from squadops.cycles.verification_integrity import (
    CheckProvenance,
    CheckResult,
    NotExecutedReason,
    ResultStatus,
)

# Framework test-spine check identities (stable, §6.3 required-addressable) —
# single-sourced from the canonical registry. ``CHECK_NO_STUB`` keeps its short
# local name (re-exported) for the producers/tests that import it here.
__all__ = ["CHECK_NO_STUB", "CHECK_TESTS_PASS", "normalize_task_checks"]


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
            # #1000: this row used to appear ONLY when stubs were found, so presence
            # meant executed-and-failed. Since #989 the producer banks it on every
            # qa validation — pass or fail, with `passed` and `inspected` — so the
            # row's own verdict must be read, exactly like any boolean row. Presence-
            # implies-failure here turned a clean repair-then-pass retest into a
            # phantom failed row, and `elif failed:` rejects on ANY failed check —
            # a false REJECTED on the most common green-roll recovery path (V7
            # launch 3 carried the phantom; a repair-then-pass roll would have been
            # decided by it). Only an actual failure taints the synthesized
            # tests_pass as a stub (§6.6.1).
            if row.get("passed") is False:
                stub_detected = True
            results.append(_from_passed_row(cid, row))
            continue
        if "status" in row:
            # #598: a typed row at a non-blocking severity (RC-9: severity and status
            # are independent; the seam stamps `passed: True` on a warning/info row
            # whatever its status) is disclosure, not acceptance evidence. Recording
            # its executed failure here verbatim would reject the run at §6.2 for a
            # check that was never a criterion — the first advisory row ever produced
            # would have been a false REJECTED. It stays on the task's typed-check
            # evaluation artifact and its `validation_result`, where the per-round
            # record reads it; the ledger holds what the verdict may read.
            if not row_is_blocking_failure(row) and row.get("status") in (
                ResultStatus.FAILED,
                ResultStatus.ERROR,
            ):
                continue
            # Typed-acceptance row: carries a CheckOutcome status verbatim.
            # SIP-0098 98.3: a bind-mode row also carries the contract criterion id.
            results.append(
                CheckResult(
                    check_id=cid,
                    status=str(row.get("status") or ""),
                    reason=_str_or_none(row.get("reason")),
                    criterion_id=_str_or_none(row.get("criterion_id")),
                    # #423: authored-check-the-evaluator-could-not-run marker,
                    # stamped by the typed-acceptance seam; drives the
                    # evaluator_gap disclosure and contract-bound requiredness.
                    evidence_gap=bool(row.get("evidence_gap", False)),
                    provenance=_inspection_provenance(row),
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


def row_is_blocking_failure(row: Mapping[str, Any]) -> bool:
    """Whether a producer check row records a failure the loop may act on.

    One predicate for the three readers that judge a row (the verdict ledger above, the
    correction signature, the failure category). A row that carries ``passed`` is judged
    by it — the typed-acceptance seam derives ``passed`` from severity × status (RC-9),
    so a warning/info row that executed and failed reads ``passed: True`` and is advisory
    (#598). A row with no ``passed`` at all is judged by its ``status``, as before.
    """
    if "passed" in row:
        return row.get("passed") is False
    return row.get("status") in (ResultStatus.FAILED, ResultStatus.ERROR)


def _from_passed_row(cid: str, row: Mapping[str, Any]) -> CheckResult:
    """Normalize a check row that carries a boolean ``passed`` (no ``status``)."""
    provenance = _inspection_provenance(row)
    if row.get("executed") is False:
        # Honor an explicit §7 not-executed reason when the producer supplies one
        # (e.g. frontend_build skipped for missing_tooling, #407); default to
        # subject_missing for producers that only signal executed=False.
        return CheckResult(
            check_id=cid,
            status=ResultStatus.SKIPPED,
            reason=_str_or_none(row.get("reason")) or NotExecutedReason.SUBJECT_MISSING,
            provenance=provenance,
        )
    status = ResultStatus.PASSED if row.get("passed") else ResultStatus.FAILED
    # #1472: carry the producer's reason on the FAILED path too. Until now this branch
    # dropped it unconditionally, so a `passed: False` row's cause never reached
    # `CheckResult.reason` and therefore never reached `failed_detail` — the run's required
    # failure read `reason: ""` however much the producer had supplied.
    #
    # This is #510's fix, generalized. #510 closed exactly this hole for `tests_pass` and
    # said why in `_tests_pass_from_result`: "failed_detail reads CheckResult.reason, and an
    # empty reason made the run's only required failure undiagnosable from evidence." That
    # fix landed on the ONE check with a dedicated normalizer; every framework producer that
    # reports through a boolean `passed` row kept the hole, and `frontend_build` is the one
    # the 1.7.5 deploy-A' pair caught with it — twice, on both stacks.
    #
    # Note the asymmetry this removes, which is the same shape one layer up (#1468): the
    # NOT-EXECUTED branch above has always honored `reason`, so a SKIPPED check explained
    # itself and a FAILED one did not. The useful case was the discarded one.
    return CheckResult(
        check_id=cid,
        status=status,
        reason=None
        if status is ResultStatus.PASSED
        else (_str_or_none(row.get("reason")) or derived_failure_reason(row)),
        provenance=provenance,
    )


#: Row keys that describe the check rather than its outcome. Everything else on a failing row
#: is the producer's evidence and is fair game for a derived reason.
#: ``inspected`` is excluded because ``_inspection_provenance`` already digests it onto
#: CheckProvenance — rendering it twice would put a file list in the SIGNATURE, and a
#: traversal-order change would then read as a shifted failure.
_STRUCTURAL_ROW_KEYS = frozenset(
    {
        "check",
        "passed",
        "executed",
        "status",
        "reason",
        "severity",
        "criterion_id",
        "subject",
        "file",
        "inspected",
        # ALREADY CONSUMED BY correction_signature, and re-rendering them here breaks it.
        # `failing_tests` is the load-bearing one: failure_signature splits it into ONE
        # ELEMENT PER FAILING TEST (#878), so putting the list into the shared token too
        # makes a partial fix stop being a strict subset — PROGRESS silently becomes
        # SHIFTED and A4 re-arms the termination that suite exists to keep selective.
        # `test_the_category_is_constant_within_a_round_so_progress_still_reduces` caught
        # exactly that. `runner`/`exit_code`/`suite_broken` are appended to the token by
        # `_reason_token` itself (#761, #878); rendering them twice is noise, not evidence.
        "failing_tests",
        "runner",
        "exit_code",
        "suite_broken",
    }
)

#: Bounds on a derived reason. It rides on CheckResult.reason, which feeds BOTH the record a
#: human reads and ``correction_signature._reason_token``. Unbounded evidence there would put
#: a whole file list in a signature.
_DERIVED_REASON_ITEMS = 5
_DERIVED_REASON_CHARS = 500


def derived_failure_reason(row: Mapping[str, Any]) -> str | None:
    """A reason composed from a failing row's own evidence, when the producer set none.

    #1472 opened the channel — ``_from_passed_row`` now carries ``reason`` to the record —
    but eight framework producers never set one, so the channel stayed empty for them. Each
    of those rows already holds the facts that make a good reason (``missing``, ``stubs_found``,
    ``expected``/``present``, ``test_files_found``, ``required``); none turns them into the
    field ``failed_detail`` reads. Deriving here fixes every current producer AND every future
    one, where eight per-producer edits would be a checklist that the ninth check silently
    fails. The precedent is ``_failed_tests_reason``, which has composed ``tests_pass``'s
    reason from row fields since #510.

    **Deterministic by construction, because this feeds a signature.** Keys are sorted and
    list members are sorted, so two rounds reporting the same failure render byte-identically
    and a genuine repeat still reads as a repeat. Without that, traversal order alone would
    make every round look SHIFTED, A4 would never terminate, and the run would burn its whole
    budget — the expensive direction, per ``correction_signature``.

    The flip side is intended: a repair that fixes two of three missing files changes the
    rendered set, which reads as MOVEMENT_PROGRESS rather than the collapsed repeat that cost
    the 1.7.5 deploy-A rolls.

    Returns ``None`` when the row carries no evidence at all — an absent reason is honest, and
    inventing "failed" would only restate the status the record already shows.
    """
    parts: list[str] = []
    for key in sorted(row):
        if key in _STRUCTURAL_ROW_KEYS:
            continue
        value = row[key]
        if isinstance(value, (list, tuple)):
            items = sorted(str(v) for v in value)
            shown = ", ".join(items[:_DERIVED_REASON_ITEMS])
            if len(items) > _DERIVED_REASON_ITEMS:
                shown += f", +{len(items) - _DERIVED_REASON_ITEMS} more"
            parts.append(f"{key}=[{shown}]")
        elif isinstance(value, (str, int, float, bool)) or value is None:
            parts.append(f"{key}={value}")
    return "; ".join(parts)[:_DERIVED_REASON_CHARS] or None


def _inspection_provenance(row: Mapping[str, Any]) -> CheckProvenance | None:
    """Bounded provenance for a detector row declaring what it read (#1002, §7).

    ``inspected`` — the file set a detector actually examined (#986) — is a payload
    list, and §7 admits only identifiers, hashes, counts and exit metadata onto
    ``CheckProvenance``. So the boundedness rule is applied *here*, at the producer
    adapter that owns the shape translation, rather than asking every producer to
    pre-digest: the list becomes a digest over its deduplicated, sorted members plus
    that set's cardinality.

    Sorted and deduplicated so the digest identifies the *set*, not the traversal
    order — two attempts that read the same files must compare equal, or the
    disclosure answers a different question than the one asked.

    An absent ``inspected`` key returns ``None`` (this producer declares nothing);
    an **empty** list does not — a detector that inspected zero files is the
    strongest form of the #1002 signal and must survive to the record.
    """
    inspected = row.get("inspected")
    if not isinstance(inspected, (list, tuple)):
        return None
    paths = sorted({p for p in inspected if isinstance(p, str) and p})
    digest = hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()
    return CheckProvenance(subject_ref=digest, subject_count=len(paths))


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
        # #510: a failed suite must disclose WHY in the row itself — failed_detail
        # reads CheckResult.reason, and an empty reason made the run's only
        # required failure undiagnosable from evidence.
        reason=None if tests_passed else _failed_tests_reason(tr),
        is_stub=is_stub,
        provenance=CheckProvenance(exit_code=_int_or_none(tr.get("exit_code"))),
    )


# pytest's documented exit-code semantics. Best-effort annotation only — the
# suite runner is usually pytest, and code 5 ("no tests collected") is the one
# that repeatedly cost live diagnosis time; a non-pytest runner still gets the
# bare exit code plus its own summary.
_PYTEST_EXIT_MEANINGS = {
    1: "test failures",
    2: "execution interrupted",
    3: "internal error",
    4: "usage error",
    5: "no tests collected",
}


def _failed_tests_reason(tr: Mapping[str, Any]) -> str:
    """Compose the disclosed reason for an executed-and-failed suite (#510)."""
    exit_code = _int_or_none(tr.get("exit_code"))
    reason = f"exit_code {exit_code}" if exit_code is not None else "test suite failed"
    meaning = _PYTEST_EXIT_MEANINGS.get(exit_code)
    if meaning:
        reason += f": {meaning}"
    summary = _str_or_none(tr.get("summary"))
    if summary:
        reason += f" — {summary}"
    return reason


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
