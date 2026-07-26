"""Plan-time proof that authored checks on frozen files can actually pass.

A bind-mode plan may hang typed checks on files the *scaffold* owns. Those files are
not a guess: the interface manifest expands to them deterministically, byte for byte,
before any agent runs. So a check aimed at one of them is decidable at authoring time —
run it against the skeleton the run will actually contain and see.

When such a check fails, the plan is unwinnable and nothing downstream can rescue it.
Frozen-file emissions are restored by scaffold ownership enforcement, so the repair
loop's only move — rewrite the file — is undone before the check re-runs. The task
fails identically on every correction attempt until the budget is spent.

pf-42 is the motivating case. Its plan asserted ``field_present`` for a ``RunEvent``
field named ``meeting_location`` on the frozen ``backend/models.py``; the manifest
declares that field as ``location``. A second task asserted ``import_present`` for
``backend.routes`` on the frozen ``backend/main.py``, which imports ``from .routes``.
Both are error-severity, both target files no agent may change, and both were provable
in under a second — but the plan was gated on human review, so the only thing that
would have caught them was someone reading a 317-line YAML closely enough to notice a
field name that reads perfectly plausibly.

This is the same shape as the rest of the bind-mode nets (SIP-0098 98.3): the system
holds the authoritative answer and the check is written against a guess. Here the
authoritative answer is on disk in milliseconds.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from squadops.capabilities.scaffold import InterfaceManifest, materialize
from squadops.cycles.acceptance_checks import get_check
from squadops.cycles.implementation_plan import TypedCheck

if TYPE_CHECKING:  # pragma: no cover - typing only
    from squadops.cycles.implementation_plan import ImplementationPlan
    from squadops.cycles.verification_contract import VerificationContract

logger = logging.getLogger(__name__)


async def frozen_check_violations(
    plan: ImplementationPlan,
    contract: VerificationContract,
    manifest_content: str,
) -> list[str]:
    """Return one error per error-severity typed check that a frozen file cannot satisfy.

    Only ``severity=error`` checks are considered — a warning cannot block a build
    (RC-9), so a warning that fails costs nothing and is not worth rejecting a plan for.

    Only ``status == "failed"`` rejects. An evaluator that *errors* (unreadable file,
    a bug in a checker) has proved nothing about the plan, and rejecting on it would let
    one broken checker block every plan in the system. Those are logged and skipped —
    the same check still runs for real at task verification, where fail-closed applies.

    Args:
        plan: The authored implementation plan.
        contract: The bound verification contract, whose ``frozen_files`` name the
            scaffold-owned surface.
        manifest_content: The interface manifest YAML this run's skeleton expands from.

    Returns:
        List of validation error strings (empty = nothing provably unwinnable).
    """
    frozen = {ff.path for ff in contract.frozen_files}
    targeted = [
        (task, check)
        for task in plan.tasks
        for check in task.acceptance_criteria
        if isinstance(check, TypedCheck)
        and check.severity == "error"
        and check.params.get("file") in frozen
    ]
    if not targeted:
        return []

    try:
        manifest = InterfaceManifest.from_yaml(manifest_content)
    except Exception:
        # The manifest has its own validation net upstream; a parse failure there is
        # reported by that net, not silently re-reported as a plan defect here.
        logger.warning("frozen-check validation skipped: interface manifest did not parse")
        return []

    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="frozen-check-") as tmp:
        root = Path(tmp)
        try:
            materialize(manifest, root)
        except Exception:
            logger.warning("frozen-check validation skipped: skeleton did not materialize")
            return []

        for task, check in targeted:
            path = check.params.get("file")
            try:
                outcome = await get_check(check.check).evaluate(
                    dict(check.params), root, stack=manifest.stack
                )
            except Exception:
                logger.warning(
                    "frozen-check validation: %s on %r raised; not treating as a plan defect",
                    check.check,
                    path,
                )
                continue

            if outcome.status != "failed":
                continue

            errors.append(
                f"Task {task.task_index} ({task.focus}): {check.check} on {path!r} can never "
                f"pass — that file is frozen (scaffold-owned), and the skeleton it will "
                f"actually contain fails this check ({outcome.reason}"
                f"{_detail(outcome)}). No repair can fix it: a frozen-file emission is "
                f"restored before the check re-runs, so this fails identically on every "
                f"correction attempt until the budget is spent. Assert what the scaffold "
                f"declares, or drop the check"
            )

    return errors


def _detail(outcome) -> str:
    """Render the actionable part of an outcome — what is missing versus what is there."""
    actual = getattr(outcome, "actual", None)
    if not isinstance(actual, dict):
        return ""
    missing = actual.get("missing")
    declared = actual.get("declared")
    if missing and declared:
        return f"; missing {sorted(missing)}, file declares {sorted(declared)}"
    if missing:
        return f"; missing {sorted(missing)}"
    return ""
