"""Deterministic correction-path policy (#447, pf-45).

The correction *decision* is LLM judgment; this layer bounds it with evidence
the model cannot overrule. First anchor (#447): a ``continue`` that would
discard a REQUIRED check which **executed and failed** is escalated to
``patch`` — an executed failure names the work product by definition, and a
narrative rationale cannot outvote it while the current chain's repair slot
is unspent. Environment failures (``executed: false`` — subject_missing,
runner errors) are exempt: repairing correct code against harness config
burns budget for nothing (the attempt-3.5 case, where ``continue`` was
right). ``abort`` is never overridden — it is a deliberate hard stop.

Second anchor (pf-45): a ``rewind`` on a **work_product** classification is
escalated to ``patch`` while the chain's repair slot is unspent. Rewind is
implemented as run death (the executor raises "Rewinding to checkpoint"),
so accepting it discards every remaining correction attempt. On pf-45 the
analyzer correctly diagnosed a one-token defect — ``pace`` for the frozen
model's ``pace_target`` — squarely in a fill slot, exactly what the repair
path exists for; the lead called it "systemic contract violations", chose
rewind, and the run died with four of five attempts unused. A narrative
escalation of severity cannot outvote a classification that says the code
is reachable by a patch. Non-work_product classifications (environment,
infrastructure, unknown) keep their rewind: patching correct code against
a broken world is the opposite failure.

This module is the intended home for the #435 convergence policy
(signature strikes, progress requirement, artifact-delta guard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Correction paths the guard may escalate. ``abort`` is deliberately absent.
_ESCALATABLE_PATHS = frozenset({"continue", "rewind"})

#: ``data.analyze_failure``'s classification meaning "the defect is in emitted
#: code" — the one classification whose rewind a patch can always substitute for.
_WORK_PRODUCT_CLASSIFICATION = "work_product"


@dataclass(frozen=True)
class CorrectionPathResolution:
    """The policy's final word on a correction path.

    ``overridden_from`` is set when the guard escalated the decision;
    ``override_reason`` names which anchor fired (event-payload vocabulary);
    ``failed_required_checks`` carries the evidence when anchor 1 justified it.
    """

    path: str
    overridden_from: str | None = None
    override_reason: str = ""
    failed_required_checks: tuple[str, ...] = field(default_factory=tuple)


def _executed_failed_required(
    failure_evidence: dict[str, Any],
    required_check_ids: frozenset[str],
) -> tuple[str, ...]:
    """Required checks that executed and failed, from the evidence payload.

    A check entry counts iff its ``check`` id is required, ``passed`` is
    explicitly False, and ``executed`` is not False (absent means the check
    ran — the executed path omits the key; env-skips set ``executed: False``).
    """
    checks = (failure_evidence.get("validation_result") or {}).get("checks") or []
    hits: list[str] = []
    for entry in checks:
        if not isinstance(entry, dict):
            continue
        check_id = entry.get("check")
        if (
            isinstance(check_id, str)
            and check_id in required_check_ids
            and entry.get("passed") is False
            and entry.get("executed") is not False
        ):
            hits.append(check_id)
    return tuple(sorted(set(hits)))


def resolve_correction_path(
    decision_path: str,
    failure_evidence: dict[str, Any],
    resolved_config: dict[str, Any],
    *,
    classification: str = "",
) -> CorrectionPathResolution:
    """Apply the deterministic guard to the LLM-chosen correction path.

    Args:
        decision_path: ``correction_path`` from the governance decision handler.
        failure_evidence: the payload handed to ``data.analyze_failure``
            (``build_failure_evidence`` shape).
        resolved_config: the cycle's effective config via the #426 single
            merge (``Cycle.resolved_config()``, #724) — ``required_checks``.
        classification: the analyzer's failure classification. Only consulted for
            the rewind anchor; "" (older callers, missing analysis) never fires it.

    Returns:
        The path to act on, with override provenance when the guard fired.
    """
    if decision_path not in _ESCALATABLE_PATHS:
        return CorrectionPathResolution(path=decision_path)

    if decision_path == "rewind":
        if classification == _WORK_PRODUCT_CLASSIFICATION:
            return CorrectionPathResolution(
                path="patch",
                overridden_from="rewind",
                override_reason="work_product_rewind_with_unspent_repair",
            )
        return CorrectionPathResolution(path=decision_path)

    required = frozenset(resolved_config.get("required_checks") or [])
    if not required:
        return CorrectionPathResolution(path=decision_path)

    failed_required = _executed_failed_required(failure_evidence, required)
    if not failed_required:
        return CorrectionPathResolution(path=decision_path)

    return CorrectionPathResolution(
        path="patch",
        overridden_from=decision_path,
        override_reason="executed_failed_required_checks",
        failed_required_checks=failed_required,
    )
