"""Failure-evidence assembly for the correction protocol (pure formatting).

Hoisted verbatim from ``DispatchedFlowExecutor`` (SIP-0097 §6.5 slice 1):
these build the structured payloads the correction chain reasons over and
have no adapter dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    return evidence


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


# pytest exit codes that mean the SUITE could not run as a suite — collection
# errors/interruption (2), usage error (4), no tests collected (5). Exit 1
# (tests ran, some failed) is the subject's failure; 3 (pytest internal error)
# stays UNKNOWN — neither artifact nor subject is implicated deterministically.
_SUITE_DEFECT_EXIT_CODES = frozenset({2, 4, 5})


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

    validation_result = failure_evidence.get("validation_result") or {}
    checks = validation_result.get("checks") or []
    for row in checks:
        if not isinstance(row, dict):
            continue
        check = row.get("check")
        if check == "expected_artifacts" and row.get("passed") is False:
            # The task's own named output files are missing from its emission.
            return FailureLocus.OWN_ARTIFACT
        if check == "tests_pass" and row.get("passed") is False and row.get("executed"):
            exit_code = row.get("exit_code")
            if exit_code in _SUITE_DEFECT_EXIT_CODES:
                return FailureLocus.OWN_ARTIFACT
            if exit_code == 1:
                return FailureLocus.SUBJECT
    return FailureLocus.UNKNOWN


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
