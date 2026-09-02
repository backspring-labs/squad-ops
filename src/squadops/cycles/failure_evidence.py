"""Failure-evidence assembly for the correction protocol (pure formatting).

Hoisted verbatim from ``DispatchedFlowExecutor`` (SIP-0097 §6.5 slice 1):
these build the structured payloads the correction chain reasons over and
have no adapter dependencies.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from squadops.cycles.acceptance_check_spec import (
    CHECK_ADDITIVE_CONTAINMENT,
    CHECK_ASSERTION_KINDS,
    CHECK_CONTRACT_ASSERTIONS,
    CHECK_DOM_ANCHOR_QUERIES,
)
from squadops.cycles.check_registry import (
    CHECK_NO_SELF_MOCKING_TESTS,
    CHECK_NO_STUB_FALLBACK_TESTS,
)
from squadops.cycles.emission_integrity import extraction_loss_suspected
from squadops.cycles.verification_integrity import ResultStatus
from squadops.cycles.verification_normalize import row_is_blocking_failure

#: Check rows whose failure means the suite contradicts a declaration (the contract's
#: pinned statuses, the manifest's field kinds, the manifest's DOM anchors — #668) — the
#: suite's own defect, by construction.
_DECLARATION_OWNED_SUITE_CHECKS: frozenset[str] = frozenset(
    {
        f"acceptance:{CHECK_CONTRACT_ASSERTIONS}",
        f"acceptance:{CHECK_ASSERTION_KINDS}",
        f"acceptance:{CHECK_DOM_ANCHOR_QUERIES}",
    }
)


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
    # #1055: the dev-side sibling. Carried explicitly for the same reason
    # scaffold_evidence is — the analyzer renders the whole evidence dict, so a finding
    # that never enters it is one the diagnosis cannot use. Arm A's lead had to invent
    # a mechanism ("a local shadow store") because nothing told it what the handlers
    # actually did wrong.
    source_containment = result_outputs.get("source_containment")
    if isinstance(source_containment, list) and source_containment:
        evidence["source_containment"] = list(source_containment)
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
    if any(row_is_blocking_failure(r) for r in rows):
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
    if any(_own_artifact_row(row) for row in checks):
        return FailureLocus.OWN_ARTIFACT
    # #1123: a failing case that could not find an anchor NO view declares is a qa-side
    # defect no application can satisfy — read from the suite's source (the anchor row's
    # unknown_anchors, #668) and only then matched to the runner's failing case, so the
    # verdict alone never routes.
    if absent_anchor_cases(failure_evidence):
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


def failing_cases_from_evidence(failure_evidence: Any) -> list[dict[str, Any]]:
    """The runner's failing cases on the failed task's ``tests_pass`` row(s), in order."""
    if not isinstance(failure_evidence, dict):
        return []
    rows = (failure_evidence.get("validation_result") or {}).get("checks") or []
    return [
        case
        for row in rows
        if isinstance(row, dict) and row.get("check") == "tests_pass"
        for case in row.get("failing_cases") or []
        if isinstance(case, dict)
    ]


_TESTID_IN_MESSAGE = re.compile(r"""data-testid=["']([^"']+)["']""")


def absent_anchor_cases(failure_evidence: Any) -> list[dict[str, Any]]:
    """The runner's failing cases whose message names an anchor no view declares (#1123).

    Two rows meet: the ``dom_anchor_queries`` row (#668) banks ``unknown_anchors`` off the
    suite's own bytes; the ``tests_pass`` row carries ``failing_cases`` from the runner.
    A case that says ``Unable to find an element by: [data-testid="x"]`` for an ``x`` in
    that set asserts a surface the manifest never promised — the suite's defect, never
    the view's. A declared anchor the view failed to render stays the dev chain's.
    """
    if not isinstance(failure_evidence, dict):
        return []
    rows = [
        r
        for r in (failure_evidence.get("validation_result") or {}).get("checks") or []
        if isinstance(r, dict)
    ]
    unknown: set[str] = set()
    for row in rows:
        if row.get("check") == f"acceptance:{CHECK_DOM_ANCHOR_QUERIES}":
            unknown.update(str(a) for a in (row.get("actual") or {}).get("unknown_anchors") or [])
    if not unknown:
        return []
    cases: list[dict[str, Any]] = []
    for row in rows:
        if row.get("check") != "tests_pass" or row.get("passed") is not False:
            continue
        for case in row.get("failing_cases") or []:
            if not isinstance(case, dict):
                continue
            named = set(_TESTID_IN_MESSAGE.findall(str(case.get("message") or "")))
            if named & unknown:
                cases.append({**case, "absent_anchors": sorted(named & unknown)})
    return cases


def _own_artifact_row(row: dict[str, Any]) -> bool:
    """A check row that names the task's OWN emission as the defect (#568's own-artifact
    signals), each safe from the test-gaming guard because none is the app's verdict."""
    check = row.get("check")
    if check == "expected_artifacts" and row.get("passed") is False:
        # The task's own named output files are missing from its emission.
        return True
    # #629: the frozen contract says the suite's own assertions are wrong (status pinned
    # by a probe, asserted differently — or a pinned path requested through an undeclared
    # prefix). #1153: the manifest says the suite's own literal cannot be the declared
    # kind. Both safe from the test-gaming guard: the signal comes from a declaration, not
    # from the app failing the suite — for qa.test, OWN_ARTIFACT = the qa role re-authors.
    if check in _DECLARATION_OWNED_SUITE_CHECKS and row.get("passed") is False:
        return True
    # #988: the suite never invoked the application — it mocked the route module, or
    # replaced the fetch seam and imported no route at all (#915), or hid the entrypoint
    # behind an ImportError stub and tested the reconstruction (#276). Such a suite's
    # verdict on the app carries no information about the app, so routing its failure to
    # the dev chain spends the repair budget rewriting working code against evidence
    # produced by a test of itself. The pre-V7 shakedown did exactly that and exhausted
    # its attempts; roll 6's delivered app passed a hand boot audit while the cycle
    # rejected it. Structural — read off the suite's own source — so it cannot be
    # produced BY an app defect.
    # #1022 joins them at the emission seam: the suite fetched a live server or invoked
    # nothing of the application — read off its bytes against the stack's declaration.
    if (
        check
        in (CHECK_NO_SELF_MOCKING_TESTS, CHECK_NO_STUB_FALLBACK_TESTS, CHECK_ADDITIVE_CONTAINMENT)
        and row.get("passed") is False
    ):
        return True
    # #1130: the runner says the suite raised in its own frame before any application
    # code ran (a NameError in the test module, an argument-binding TypeError at a call
    # into the harness) and the stack says the file is the qa role's. 1.6.5 roll 3
    # carried exactly this — three tests dying on ``TestClient.delete(json=…)`` — and
    # every repair went to backend/routes.py because an executed pytest exit 1 reads as
    # "the app failed the suite". A machine fact about where the exception was raised,
    # not the app's verdict.
    return check == "tests_pass" and bool(_qa_owned_defects(row))


def _qa_owned_defects(tests_pass_row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        d
        for d in tests_pass_row.get("suite_defects") or []
        if isinstance(d, dict) and d.get("qa_owned") is True
    ]


def qa_owned_suite_defects(failure_evidence: Any) -> list[dict[str, Any]]:
    """The suite's own-frame failures the stack attributes to the qa role (#1130).

    Read from the ``tests_pass`` rows the runner built (``failed_tests_pass_row``); each
    entry is ``{file, title, line, exception, message, qa_owned}``. The repair router
    targets their files; the classifier routes on their presence.
    """
    if not isinstance(failure_evidence, dict):
        return []
    rows = (failure_evidence.get("validation_result") or {}).get("checks") or []
    return [
        d
        for row in rows
        if isinstance(row, dict) and row.get("check") == "tests_pass"
        for d in _qa_owned_defects(row)
    ]


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
