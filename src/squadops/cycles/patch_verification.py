"""Behavioral verification of correction-loop patches (#389).

After a ``patch`` correction, the executor used to re-dispatch the failed
task to "re-run the check" (#374). For generative tasks that re-dispatch
does not re-run the *check* — it re-runs the *generator*, which re-rolls
the artifacts from scratch and discards the repair. Field evidence
(cyc_6841d75f167c, #389): every repair passed validation, every re-roll
reintroduced the defect, and the correction budget starved on one task.

This module keeps #374's principle — the verdict is the re-executed check,
never an LLM judgment — but re-runs the failed task's typed acceptance
criteria directly against the repaired artifacts. Pure evaluation
(criteria + artifacts → verdict); no dispatch, no I/O beyond a temp
workspace for the check evaluators.

The executor treats the three verdicts as:
    PASSED       — accept the patched artifacts as the task's outputs.
    FAILED       — repair didn't satisfy the contract; re-enter correction.
    UNVERIFIABLE — checks can't run here (no typed criteria, evaluator
                   error, malformed criterion); fall back to the pre-#389
                   re-dispatch path. Conservative: worst case is the old
                   behavior, never a false accept.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_checks import CheckOutcome, get_check
from squadops.cycles.implementation_plan import TypedCheck, _parse_acceptance_criteria

logger = logging.getLogger(__name__)

# Verdict vocabulary (module constants, not an enum — matches the
# correction_path string convention of the surrounding loop).
PATCH_PASSED = "passed"
PATCH_FAILED = "failed"
PATCH_UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class PatchCheckRecord:
    """One typed criterion's outcome against the patched workspace."""

    check: str
    severity: str
    status: str  # CheckOutcome status: passed | failed | error | skipped
    description: str = ""
    reason: str | None = None
    actual: str | None = None

    def to_check_row(self) -> dict[str, Any]:
        """Render in the handler-emitted ``checks`` row shape.

        The ``acceptance:`` prefix and ``status`` key are what
        ``normalize_task_checks`` (§6.1) keys on, so a patch-verified task
        records the same executed evidence a first-try pass would.
        """
        return {
            "check": f"acceptance:{self.check}",
            "severity": self.severity,
            "description": self.description,
            "status": self.status,
            "reason": self.reason,
            "actual": self.actual,
            "passed": not (self.severity == "error" and self.status in {"failed", "error"}),
            "patch_verified": True,
        }


@dataclass(frozen=True)
class PatchVerification:
    """Aggregate verdict over all typed criteria."""

    status: str  # PATCH_PASSED | PATCH_FAILED | PATCH_UNVERIFIABLE
    checks: tuple[PatchCheckRecord, ...] = ()
    reason: str | None = None


def overlay_artifacts(
    base: list[dict[str, Any]] | None, patches: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Merge artifact dicts by ``name``; a patch supersedes the base entry.

    Order: base order preserved, net-new patch files appended in patch order.
    Entries without a usable ``name`` are dropped (they can't land in a
    workspace anyway).
    """
    merged: dict[str, dict[str, Any]] = {}
    for art in list(base or []) + list(patches or []):
        name = art.get("name")
        if isinstance(name, str) and name:
            merged[name] = art
    return list(merged.values())


def materialize_artifacts(artifacts: list[dict], workspace_root: Path) -> None:
    """Write in-memory artifact dicts to disk under ``workspace_root``.

    Skips entries whose ``name`` is missing, absolute, or escapes the
    workspace — the typed-check evaluators apply their own ``_safe_resolve``
    chroot on top, but it is cheaper to refuse here than to materialize a
    malformed file just to fail evaluation.
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


def _coerce_typed_criteria(criteria: list[Any]) -> list[TypedCheck] | None:
    """Extract TypedCheck entries, re-parsing dict rows (deserialized envelopes).

    Prose strings are informational and never block — dropped. Returns None
    when any dict row fails to parse: an unintelligible contract must fall
    back to re-dispatch, not silently verify against a subset of itself.
    """
    typed: list[TypedCheck] = []
    for item in criteria:
        if isinstance(item, TypedCheck):
            typed.append(item)
        elif isinstance(item, Mapping):
            try:
                parsed = _parse_acceptance_criteria([dict(item)], task_index=-1)
            except ValueError:
                logger.warning(
                    "patch_verification: unparseable criterion %r — unverifiable", item
                )
                return None
            typed.extend(c for c in parsed if isinstance(c, TypedCheck))
        # str → prose, informational only
    return typed


async def verify_patched_artifacts(
    criteria: list[Any],
    artifacts: list[dict[str, Any]],
    *,
    stack: str | None = None,
    typed_acceptance_enabled: bool = True,
    command_acceptance_enabled: bool = True,
) -> PatchVerification:
    """Re-run the failed task's typed acceptance criteria against *artifacts*.

    Mirrors the handler-side RC-9 blocking matrix: only ``severity=error``
    criteria can block; ``skipped`` never blocks. Any evaluator ``error`` on
    a blocking criterion makes the whole patch UNVERIFIABLE (the executor
    environment may lack tooling the agent container has — never guess).
    """
    typed = _coerce_typed_criteria(criteria)
    if typed is None:
        return PatchVerification(status=PATCH_UNVERIFIABLE, reason="unparseable_criteria")
    if not typed:
        return PatchVerification(status=PATCH_UNVERIFIABLE, reason="no_typed_criteria")

    records: list[PatchCheckRecord] = []
    blocking_failure = False
    blocking_passed = 0
    with tempfile.TemporaryDirectory(prefix="squadops-patch-verify-") as tmpdir:
        workspace_root = Path(tmpdir)
        materialize_artifacts(artifacts, workspace_root)

        for criterion in typed:
            if not typed_acceptance_enabled:
                outcome = CheckOutcome.skipped(reason="typed_acceptance_disabled")
            elif criterion.check == "command_exit_zero" and not command_acceptance_enabled:
                outcome = CheckOutcome.skipped(reason="command_acceptance_checks_disabled")
            else:
                try:
                    evaluator = get_check(criterion.check)
                except KeyError:
                    outcome = CheckOutcome.error(reason="no_evaluator_registered")
                else:
                    outcome = await evaluator.evaluate(
                        criterion.params, workspace_root, stack=stack
                    )

            records.append(
                PatchCheckRecord(
                    check=criterion.check,
                    severity=criterion.severity,
                    status=outcome.status,
                    description=criterion.description or "",
                    reason=outcome.reason,
                    actual=outcome.actual,
                )
            )

            if criterion.severity != "error":
                continue
            if outcome.status == "error":
                # Evaluator couldn't run in this environment — the whole
                # verification is untrustworthy, not just this row.
                return PatchVerification(
                    status=PATCH_UNVERIFIABLE,
                    checks=tuple(records),
                    reason=f"evaluator_error:{criterion.check}",
                )
            if outcome.status == "failed":
                blocking_failure = True
            elif outcome.status == "passed":
                blocking_passed += 1

    if blocking_failure:
        return PatchVerification(status=PATCH_FAILED, checks=tuple(records))
    if blocking_passed == 0:
        # Every blocking criterion was skipped (disabled config, unset stack).
        # Accepting a patch requires positive executed evidence — "nothing
        # failed because nothing ran" is the false-green shape (§6.2).
        return PatchVerification(
            status=PATCH_UNVERIFIABLE,
            checks=tuple(records),
            reason="no_executed_blocking_checks",
        )
    return PatchVerification(status=PATCH_PASSED, checks=tuple(records))
