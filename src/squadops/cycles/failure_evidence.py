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
    return {
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
