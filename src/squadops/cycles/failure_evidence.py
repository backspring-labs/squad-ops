"""Failure-evidence assembly for the correction protocol (pure formatting).

Hoisted verbatim from ``DispatchedFlowExecutor`` (SIP-0097 §6.5 slice 1):
these build the structured payloads the correction chain reasons over and
have no adapter dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from squadops.cycles.acceptance_check_spec import CHECK_CONTRACT_ASSERTIONS
from squadops.cycles.emission_integrity import extraction_loss_suspected
from squadops.cycles.verification_integrity import ResultStatus

if TYPE_CHECKING:
    from squadops.tasks.models import TaskEnvelope, TaskResult


def build_failure_evidence(
    envelope: TaskEnvelope,
    result: TaskResult,
    *,
    prior_plan_deltas_count: int,
) -> dict[str, Any]:
    """Assemble the failure-evidence payload handed to data.analyze_failure.

    Issue #84 follow-up: the data role was previously handed only
    `error` + `outcome_class` and had to guess at the failure shape;
    downstream
    correction-decision then picked rewind on content failures because
    it had no indication that a patch would suffice. Pull through the
    failed handler's structured `validation_result` + preliminary
    `failure_classification` + rejected artifact summaries so the
    analyzer reasons about concrete checks instead of free-text
    error strings. Each rejected-artifact content snippet is capped
    at 1500 chars so a multi-file failure doesn't bloat the prompt.
    """
    result_outputs = result.outputs or {}
    validation_result = result_outputs.get("validation_result") or {}
    rejected_artifacts: list[dict[str, Any]] = []
    for art in result_outputs.get("artifacts", []) or []:
        content = art.get("content", "")
        if isinstance(content, str):
            size = len(content)
            snippet = content[:1500]
        else:
            size = 0
            snippet = ""
        rejected_artifacts.append(
            {
                "name": art.get("name", ""),
                "type": art.get("type", ""),
                "size": size,
                "content_snippet": snippet,
            }
        )
    evidence = {
        "failed_task_id": envelope.task_id,
        "failed_task_type": envelope.task_type,
        "error": result.error or "",
        "outcome_class": result_outputs.get("outcome_class", ""),
        "preliminary_failure_classification": result_outputs.get("failure_classification", ""),
        "validation_result": {
            "passed": validation_result.get("passed"),
            "summary": validation_result.get("summary", ""),
            "missing_components": validation_result.get("missing_components", []),
            "checks": validation_result.get("checks", []),
        },
        "rejected_artifacts": rejected_artifacts,
        "prior_plan_deltas_count": prior_plan_deltas_count,
    }
    # #566/#568: the zero-extraction marker travels into evidence so the locus
    # classifier (and the analyzer) see "no artifact was ever produced" as a
    # machine fact instead of inferring a work-product story from its absence.
    emission_failure = result_outputs.get("emission_failure")
    if isinstance(emission_failure, dict):
        evidence["emission_failure"] = emission_failure
    # #431: generated-vs-stored accounting + the gap rule. The flag is the
    # machine fact that the diagnostic inputs themselves are suspect — a
    # partial extraction loss must never be diagnosed as a work-product
    # failure from the fraction that survived.
    emission_stats = result_outputs.get("emission_stats")
    if isinstance(emission_stats, dict):
        evidence["emission_stats"] = emission_stats
        if extraction_loss_suspected(emission_stats):
            evidence["extraction_loss"] = True
    # #687: hoist app-side tracebacks off the probe rows to the evidence top
    # level — the analyzer's prompt renders the evidence dict, and the stack
    # trace is THE diagnosis for a behavioral failure (shk-2: two attempts
    # burned on guessed causes while the NameError sat unread).
    app_tracebacks = [
        {"check": row.get("check", ""), "traceback": row["app_traceback"]}
        for row in (validation_result.get("checks") or [])
        if isinstance(row, dict) and row.get("app_traceback")
    ]
    if app_tracebacks:
        evidence["app_tracebacks"] = app_tracebacks[:_MAX_APP_TRACEBACKS]
    # SIP-0104 P5: the scaffold evidence summary rides the same transport as the two
    # markers above — it is diagnostic, not a verification check, so it must never
    # enter validation_result.checks (roll 1 measured that mistake: an informational
    # row aggregated as an unverified check). The locus classifier reads the classes
    # from here, and the analyzer's prompt renders the whole evidence dict, so the
    # per-failure owner/route rows reach the diagnosis too.
    scaffold_evidence = result_outputs.get("scaffold_evidence")
    if isinstance(scaffold_evidence, dict):
        evidence["scaffold_evidence"] = scaffold_evidence
    evidence["failure_category"] = derive_failure_category(evidence)
    return evidence


# Bounded: distinct failing probes usually share one root cause; three
# tracebacks names it without turning the evidence into a log dump.
_MAX_APP_TRACEBACKS = 3


class FailureEvidenceCategory:
    """What kind of fact the failure evidence carries (1.5 A3 taxonomy).

    The shared vocabulary of the #687+#431 pair — deterministic, derived from
    machine signals already in the evidence, never from prose. The analyzer,
    the locus classifier, and (via evidence persistence) replay all read the
    same answer to "what actually failed here?", so an infrastructure failure
    can never masquerade as a work-product failure just because the diagnostic
    inputs sat downstream of the infrastructure that failed.

    Constants-class pattern (``TaskOutcome``). Categories with no detectable
    signal yet are declared, not guessed: ``EXTRACTION_LOSS`` gains its signal
    with #431's emission stats; ``VERIFICATION_INFRA_FAILURE`` with the
    runner-side reasons already in evidence rows.
    """

    # The app/product executed its checks and failed them — the ordinary case.
    EXECUTED_AND_FAILED = "executed_and_failed"
    # The app executed and errored — an app_traceback names the cause (#687).
    APP_ERROR = "app_error"
    # The emission was extracted but materially truncated (#431 gap rule).
    EXTRACTION_LOSS = "extraction_loss"
    # Zero extraction — no artifact was ever produced (#566 marker).
    EMISSION_ABSENT = "emission_absent"
    # The subject never booted; behavioral checks never ran.
    SANDBOX_PREEXEC_FAILURE = "sandbox_preexec_failure"
    # The verification machinery itself failed (runner/env), not the product.
    VERIFICATION_INFRA_FAILURE = "verification_infra_failure"
    # Nothing machine-readable survived to classify from.
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"


def derive_failure_category(evidence: dict[str, Any]) -> str:
    """Deterministic category from the evidence's machine signals (A3).

    Precedence is the diagnosis-integrity order: infrastructure/emission facts
    first (they invalidate downstream product signals — the #431 lesson),
    then the app's own error, then ordinary check failures.
    """
    if isinstance(evidence.get("emission_failure"), dict):
        return FailureEvidenceCategory.EMISSION_ABSENT
    if evidence.get("extraction_loss") is True:
        return FailureEvidenceCategory.EXTRACTION_LOSS
    checks = (evidence.get("validation_result") or {}).get("checks") or []
    rows = [r for r in checks if isinstance(r, dict)]
    if evidence.get("app_tracebacks"):
        return FailureEvidenceCategory.APP_ERROR
    skipped_boot = [
        r
        for r in rows
        if r.get("status") == ResultStatus.SKIPPED
        and "subject did not boot" in str(r.get("reason", ""))
    ]
    if skipped_boot:
        return FailureEvidenceCategory.SANDBOX_PREEXEC_FAILURE
    if any(
        r.get("passed") is False or r.get("status") in (ResultStatus.FAILED, ResultStatus.ERROR)
        for r in rows
    ):
        return FailureEvidenceCategory.EXECUTED_AND_FAILED
    return FailureEvidenceCategory.EVIDENCE_UNAVAILABLE


class FailureLocus:
    """Where a failed task's defect lives, relative to the task itself (#568).

    Constants-class pattern like ``TaskOutcome``. Drives repair routing: a task
    whose OWN emitted artifact is missing/unparseable/uncollectable should be
    repaired by its own role (re-produce the artifact); only a failure in the
    SUBJECT under test/verification belongs to the subject's producing role.
    For ``qa.test``: OWN_ARTIFACT = the test suite itself is broken (eve
    re-authors); SUBJECT = the suite ran and the app failed it (dev repairs).
    """

    OWN_ARTIFACT = "own_artifact"
    SUBJECT = "subject"
    UNKNOWN = "unknown"


# pytest exit codes that mean the SUITE ITSELF is the defect — collection
# errors in the test files (2), no tests collected (5). Exit 1 (tests ran,
# some failed) is the subject's failure. Exit 3 (pytest internal error) stays
# UNKNOWN. Exit 4 (usage error) ALSO stays UNKNOWN → default dev chain:
# pf-35 corr-01/02 proved it ambiguous — conftest/app-import failures (an
# accepted routes.py importing names the frozen models.py never defined)
# surface as exit 4, and classifying that own-artifact sent the qa role to
# re-author a suite that could never fix the app's broken import. Ambiguity
# falls toward the dev chain, per the same guard rationale as test-gaming.
_SUITE_DEFECT_EXIT_CODES = frozenset({2, 5})


def classify_failure_locus(failure_evidence: Any) -> str:
    """Deterministic failure-locus classification from evidence alone (#568).

    Conservative by design (the test-gaming guard): only explicit machine
    signals produce ``OWN_ARTIFACT``; ambiguity returns ``UNKNOWN``, which
    routes to the default (dev) repair chain — never toward a qa re-author
    that could "fix" an app bug by rewriting the tests.
    """
    if not isinstance(failure_evidence, dict):
        return FailureLocus.UNKNOWN

    # Zero-extraction marker (#566): the task produced no artifact at all.
    if isinstance(failure_evidence.get("emission_failure"), dict):
        return FailureLocus.OWN_ARTIFACT

    # #431: partial extraction loss — the emission never arrived whole, so the
    # defect belongs to the producing task's own re-emission (with #528's
    # parser fixes, a re-emit can succeed), NEVER to behavioral repair of the
    # subject: repairing app source against evidence derived from a truncated
    # artifact is exactly the budget burn this flag exists to stop.
    if failure_evidence.get("extraction_loss") is True:
        return FailureLocus.OWN_ARTIFACT

    validation_result = failure_evidence.get("validation_result") or {}
    checks = [row for row in validation_result.get("checks") or [] if isinstance(row, dict)]
    # Own-artifact signals scan FIRST, regardless of row order (#629 D4): when the
    # suite both contradicts the contract AND fails, repairing the app against a
    # contract-contradicting suite is exactly the pf-54 budget burn — the
    # tests_pass row must not route to the dev chain before these are consulted.
    for row in checks:
        check = row.get("check")
        if check == "expected_artifacts" and row.get("passed") is False:
            # The task's own named output files are missing from its emission.
            return FailureLocus.OWN_ARTIFACT
        # #629: the frozen contract says the suite's own assertions are wrong
        # (status pinned by a probe, asserted differently — or a pinned path
        # requested through an undeclared prefix). Safe from the test-gaming
        # guard: the signal comes from the contract, not from the app failing
        # the suite — for qa.test, OWN_ARTIFACT = eve re-authors the suite.
        if check == f"acceptance:{CHECK_CONTRACT_ASSERTIONS}" and row.get("passed") is False:
            return FailureLocus.OWN_ARTIFACT
    scaffold_locus = _locus_from_scaffold_classification(failure_evidence)
    if scaffold_locus is not None:
        return scaffold_locus
    for row in checks:
        if row.get("check") == "tests_pass" and row.get("passed") is False:
            locus = _locus_from_tests_pass_row(row)
            if locus is not None:
                return locus
    return FailureLocus.UNKNOWN


def _locus_from_scaffold_classification(failure_evidence: dict[str, Any]) -> str | None:
    """SIP-0104 P5: the scaffold classification is finer than tests_pass semantics —
    consulted first when present. app_contract wins over fill (the shell's frozen
    assertion says the APP violated the contract; repairing the app is the §5 route and
    the conservative direction); all-fill routes to the fill author. The generator
    (scaffold_invalid) and infrastructure classes deliberately return None — neither is
    an LLM-repairable locus, so the legacy signals (or UNKNOWN) decide."""
    summary = failure_evidence.get("scaffold_evidence")
    if not isinstance(summary, dict):
        return None
    from squadops.cycles.scaffold_evidence import (
        CLASS_APP_CONTRACT,
        CLASS_FILL,
        CLASS_INFRASTRUCTURE,
        CLASS_SCAFFOLD_INVALID,
    )

    classes = summary.get("failure_classes") or {}
    if classes.get(CLASS_APP_CONTRACT):
        return FailureLocus.SUBJECT
    if (
        classes.get(CLASS_FILL)
        and not classes.get(CLASS_SCAFFOLD_INVALID)
        and not classes.get(CLASS_INFRASTRUCTURE)
    ):
        return FailureLocus.OWN_ARTIFACT
    return None


def _locus_from_tests_pass_row(row: dict[str, Any]) -> str | None:
    """Locus signal from a failed ``tests_pass`` row, or None (keep scanning).

    #626: prefer the runner's OWN suite-health verdict (test_runner owns
    test-framework knowledge; vitest cannot express suite-broken through exit
    codes, so pytest exit semantics misrouted every frontend suite defect to
    the dev chain — pf-53). Absent/None falls back to the legacy pytest
    exit-code table.

    #665: the verdict is read BEFORE the executed guard. A suite that never
    ran because it does not exist (zero collectable files) is the producing
    role's own artifact, but the old executed gate skipped every own-artifact
    signal for exactly that case — fay-13's missing suite (executed:false,
    exit -1) fell to UNKNOWN and five dev-chain repairs churned on files only
    the qa role could author.
    """
    suite_broken = row.get("suite_broken")
    if suite_broken is True:
        return FailureLocus.OWN_ARTIFACT
    if not row.get("executed"):
        # Every other never-executed case (env/runner errors, timeouts,
        # legacy rows with no verdict) stays ambiguous → dev chain.
        return None
    if suite_broken is False:
        return FailureLocus.SUBJECT
    exit_code = row.get("exit_code")
    if exit_code in _SUITE_DEFECT_EXIT_CODES:
        return FailureLocus.OWN_ARTIFACT
    if exit_code == 1:
        return FailureLocus.SUBJECT
    return None


def compose_failure_trigger(
    envelope: TaskEnvelope,
    failure_evidence: dict[str, Any],
) -> str:
    """Issue #114: compose the plan_delta `trigger` string.

    When the failure traces to a blocking typed-acceptance check trip
    (an evaluation row with check prefix ``acceptance:``, severity
    ``error``, and ``passed: False``), emit the extended shape
    ``typed_check_failed:<task_type>:<task_index>:<check_index>`` so
    the SIP-0092 gate evaluator can attribute corrections to specific
    check failures without re-deriving them from prose.

    Otherwise returns the legacy shape ``task_failure:<task_type>``
    (e.g. development.develop returned no valid code, RabbitMQ
    timeout, JSON parse error — none of which are typed-check trips).
    Both shapes coexist and consumers must handle both.
    """
    legacy = f"task_failure:{envelope.task_type}"
    validation_result = failure_evidence.get("validation_result") or {}
    checks = validation_result.get("checks") or []
    for row in checks:
        if not isinstance(row, dict):
            continue
        check_name = row.get("check", "")
        if not isinstance(check_name, str) or not check_name.startswith("acceptance:"):
            continue
        if row.get("passed", True):
            continue
        if row.get("severity") != "error":
            continue
        task_index = row.get("task_index")
        check_index = row.get("check_index")
        if task_index is None or check_index is None:
            # Identity fields missing (legacy data, monolithic flow).
            # Fall back to legacy shape rather than emit a malformed
            # trigger downstream consumers would have to special-case.
            continue
        return f"typed_check_failed:{envelope.task_type}:{task_index}:{check_index}"
    return legacy
