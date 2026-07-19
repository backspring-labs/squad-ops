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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_evaluation import (
    evaluate_criterion,
    split_acceptance_criteria,
)
from squadops.cycles.implementation_plan import TypedCheck

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


def rebase_artifact_paths(
    artifacts: list[dict[str, Any]], expected_paths: list[str] | tuple[str, ...]
) -> list[dict[str, Any]]:
    """Deterministically re-home a repair artifact onto its expected path (#507).

    Repair handlers re-derive the layout from prose and can emit the right file
    under the wrong directory (roll cyc_22b14aeda70f: every repair landed
    ``app/routes.py`` while the scaffold, contract, and typed checks target
    ``backend/routes.py``) — the overlay then appends a net-new file instead of
    superseding, typed patch verification runs against the un-patched original,
    and a content-correct, QA-validated repair is discarded by re-dispatch. The
    target path is not the model's to choose: when an emitted ``name`` is not an
    expected path and exactly one expected path shares its basename, the entry
    is rewritten to that path. Ambiguous or unmatched names pass through
    unchanged (conservative — never a false re-home).
    """
    expected = [p for p in expected_paths if isinstance(p, str) and p]
    by_base: dict[str, list[str]] = {}
    for p in expected:
        by_base.setdefault(Path(p).name, []).append(p)
    out: list[dict[str, Any]] = []
    for art in artifacts:
        name = art.get("name")
        if isinstance(name, str) and name and name not in expected:
            candidates = by_base.get(Path(name).name, [])
            if len(candidates) == 1 and candidates[0] != name:
                logger.info("patch_rebase: repair artifact %r re-homed to %r", name, candidates[0])
                art = {**art, "name": candidates[0]}
        out.append(art)
    return out


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
    """Extract TypedCheck entries via the shared seam (#420).

    Prose strings are informational and never block — dropped. Returns None
    when any row fails to parse: an unintelligible contract must fall
    back to re-dispatch, not silently verify against a subset of itself.
    """
    split = split_acceptance_criteria(criteria)
    if split.unparseable:
        logger.warning(
            "patch_verification: %d unparseable criteria — unverifiable",
            len(split.unparseable),
        )
        return None
    return list(split.typed)


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
            outcome = await evaluate_criterion(
                criterion,
                workspace_root,
                stack=stack,
                typed_acceptance_enabled=typed_acceptance_enabled,
                command_acceptance_enabled=command_acceptance_enabled,
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
