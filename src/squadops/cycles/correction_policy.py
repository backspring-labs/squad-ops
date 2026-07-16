"""Deterministic correction-path policy (#447).

The correction *decision* is LLM judgment; this layer bounds it with evidence
the model cannot overrule. First anchor (#447): a ``continue`` that would
discard a REQUIRED check which **executed and failed** is escalated to
``patch`` — an executed failure names the work product by definition, and a
narrative rationale cannot outvote it while the current chain's repair slot
is unspent. Environment failures (``executed: false`` — subject_missing,
runner errors) are exempt: repairing correct code against harness config
burns budget for nothing (the attempt-3.5 case, where ``continue`` was
right). ``abort`` is never overridden — it is a deliberate hard stop.

This module is the intended home for the #435 convergence policy
(signature strikes, progress requirement, artifact-delta guard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Correction paths the guard may escalate. ``abort`` is deliberately absent.
_ESCALATABLE_PATHS = frozenset({"continue"})


@dataclass(frozen=True)
class CorrectionPathResolution:
    """The policy's final word on a correction path.

    ``overridden_from`` is set when the guard escalated the decision;
    ``failed_required_checks`` carries the evidence that justified it.
    """

    path: str
    overridden_from: str | None = None
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
    applied_defaults: dict[str, Any],
) -> CorrectionPathResolution:
    """Apply the deterministic guard to the LLM-chosen correction path.

    Args:
        decision_path: ``correction_path`` from the governance decision handler.
        failure_evidence: the payload handed to ``data.analyze_failure``
            (``build_failure_evidence`` shape).
        applied_defaults: the cycle's resolved defaults (``required_checks``).

    Returns:
        The path to act on, with override provenance when the guard fired.
    """
    if decision_path not in _ESCALATABLE_PATHS:
        return CorrectionPathResolution(path=decision_path)

    required = frozenset(applied_defaults.get("required_checks") or [])
    if not required:
        return CorrectionPathResolution(path=decision_path)

    failed_required = _executed_failed_required(failure_evidence, required)
    if not failed_required:
        return CorrectionPathResolution(path=decision_path)

    return CorrectionPathResolution(
        path="patch",
        overridden_from=decision_path,
        failed_required_checks=failed_required,
    )
