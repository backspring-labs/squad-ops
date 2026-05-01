"""Typed-acceptance evaluation for cycle task handlers (SIP-0092 M1.3).

This module owns the FC3 typed-acceptance pipeline that
``DevelopmentDevelopHandler._validate_focused`` invokes during
focused-mode validation. It was extracted from
``cycle_tasks.py`` to keep that module's complexity in check
(SIP-0092 M1 follow-up); behavior is preserved exactly.

Responsibilities (per RC-9 / RC-9a / RC-9b / RC-12a):

* Materialize in-memory artifacts to a temp workspace so
  filesystem-bound evaluators (e.g. ``command_exit_zero``) can
  chroot against real files.
* Dispatch each ``TypedCheck`` to its registered evaluator while
  honoring the ``typed_acceptance`` and ``command_acceptance_checks``
  config gates.
* Produce per-check records and contribute to ``missing`` using the
  severity x status blocking matrix: only ``severity == "error"``
  AND ``status in {"failed", "error"}`` blocks.
* Track per-criterion evaluator-error counts (RC-9b, 2-strikes):
  the third occurrence stops being fed back through the self-eval
  prompt and is escalated via WARNING log instead.

The per-criterion error counter is owned by the caller (one dict
per ``handle()`` invocation) and threaded through here. This module
holds no module-level mutable state.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_checks import CheckOutcome, get_check
from squadops.cycles.implementation_plan import TypedCheck

logger = logging.getLogger(__name__)


_BLOCKING_STATUSES = frozenset({"failed", "error"})


async def evaluate_typed_acceptance(
    inputs: dict[str, Any],
    artifacts: list[dict],
    checks: list[dict],
    missing: list[str],
    typed_error_counts: dict[str, int],
) -> None:
    """Evaluate typed acceptance criteria, mutating ``checks`` and ``missing`` in place.

    Implements RC-9 (severity x status blocking matrix), RC-9a (error-vs-
    failed wording distinction), RC-9b (per-criterion error count with
    2-strikes escalation), RC-12a (skipped-not-error for unset stack).
    """
    criteria = inputs.get("acceptance_criteria", [])
    typed_criteria = [c for c in criteria if isinstance(c, TypedCheck)]
    prose_criteria = [c for c in criteria if not isinstance(c, TypedCheck)]

    # Prose strings stay informational, evidence-only — same as Rev 1's
    # included_in_evidence behavior. They never block.
    if prose_criteria:
        checks.append({
            "check": "acceptance_criteria_prose",
            "criteria": prose_criteria,
            "evaluation": "included_in_evidence",
            "passed": True,
        })

    if not typed_criteria:
        return

    resolved_config = inputs.get("resolved_config", {})
    typed_acceptance_enabled = resolved_config.get("typed_acceptance", True)
    command_acceptance_enabled = resolved_config.get("command_acceptance_checks", True)
    stack = resolved_config.get("stack")

    with tempfile.TemporaryDirectory(prefix="squadops-typed-acc-") as tmpdir_str:
        workspace_root = Path(tmpdir_str)
        materialize_artifacts(artifacts, workspace_root)

        for criterion in typed_criteria:
            outcome = await evaluate_typed_check(
                criterion,
                workspace_root,
                stack=stack,
                typed_acceptance_enabled=typed_acceptance_enabled,
                command_acceptance_enabled=command_acceptance_enabled,
            )
            checks.append(_build_check_record(criterion, outcome))
            _accumulate_missing(criterion, outcome, missing, typed_error_counts)


def _build_check_record(criterion: TypedCheck, outcome: CheckOutcome) -> dict[str, Any]:
    """Build the per-check record appended to ``ValidationResult.checks``.

    The ``passed`` flag preserves compatibility with the legacy
    all-checks-pass aggregator: only ``severity == "error"`` AND a
    blocking status (``failed`` or ``error``) counts as not-passed.
    """
    return {
        "check": f"acceptance:{criterion.check}",
        "severity": criterion.severity,
        "params": criterion.params,
        "description": criterion.description,
        "status": outcome.status,
        "actual": outcome.actual,
        "reason": outcome.reason,
        "passed": not (
            criterion.severity == "error" and outcome.status in _BLOCKING_STATUSES
        ),
    }


def _accumulate_missing(
    criterion: TypedCheck,
    outcome: CheckOutcome,
    missing: list[str],
    typed_error_counts: dict[str, int],
) -> None:
    """Append blocking failures to ``missing``, tracking RC-9b error counts.

    RC-9: severity AND status are independent dimensions; only
    ``severity == "error"`` combined with a blocking status mutates
    ``missing``. ``status in {"passed", "skipped"}`` never blocks.
    """
    if criterion.severity != "error":
        return
    if outcome.status == "failed":
        # RC-9a: app-incompleteness wording.
        label = criterion.description or criterion.check
        missing.append(f"acceptance:{label}")
        return
    if outcome.status == "error":
        fp = criterion.fingerprint()
        prior = typed_error_counts.get(fp, 0)
        if prior < 2:
            # RC-9a: evaluator-error wording, distinct from app-incomplete.
            missing.append(f"evaluator-error:{criterion.check}: {outcome.reason}")
        else:
            escalate_persistent_evaluator_error(criterion, outcome)
        typed_error_counts[fp] = prior + 1


def materialize_artifacts(artifacts: list[dict], workspace_root: Path) -> None:
    """Write in-memory artifacts to disk under ``workspace_root``.

    Skips entries whose ``name`` is missing or escapes the workspace —
    the typed-check evaluators apply their own ``_safe_resolve`` chroot
    on top of this, but it is cheaper to refuse here than to
    materialize a malformed file just to fail evaluation.
    """
    root_resolved = workspace_root.resolve()
    for art in artifacts:
        name = art.get("name")
        content = art.get("content", "")
        if not isinstance(name, str) or not name:
            continue
        if Path(name).is_absolute():
            continue
        target = (workspace_root / name).resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(str(content), encoding="utf-8")


async def evaluate_typed_check(
    criterion: TypedCheck,
    workspace_root: Path,
    *,
    stack: str | None,
    typed_acceptance_enabled: bool,
    command_acceptance_enabled: bool,
) -> CheckOutcome:
    """Dispatch a typed criterion to its registered evaluator, honoring config gates."""
    if not typed_acceptance_enabled:
        return CheckOutcome.skipped(reason="typed_acceptance_disabled")
    if criterion.check == "command_exit_zero" and not command_acceptance_enabled:
        return CheckOutcome.skipped(reason="command_acceptance_checks_disabled")
    try:
        evaluator = get_check(criterion.check)
    except KeyError:
        # Should not happen — parser already enforces vocabulary — but
        # treat as evaluator-error rather than crashing the cycle.
        return CheckOutcome.error(reason="no_evaluator_registered")
    return await evaluator.evaluate(criterion.params, workspace_root, stack=stack)


def escalate_persistent_evaluator_error(
    criterion: TypedCheck, outcome: CheckOutcome
) -> None:
    """RC-9b: surface a persistent evaluator error outside the self-eval feedback loop.

    Logged at WARNING with structured fields; the correction protocol
    and operator-facing surfaces consume the log. A first-class
    escalation channel is a follow-up if/when the prompt-feedback
    suppression proves insufficient.
    """
    logger.warning(
        "typed_check_evaluator_error_escalated",
        extra={
            "check": criterion.check,
            "severity": criterion.severity,
            "fingerprint": criterion.fingerprint(),
            "reason": outcome.reason,
            "actual": outcome.actual,
        },
    )
