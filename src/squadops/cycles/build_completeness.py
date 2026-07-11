"""Deliverable-completeness gate for builder runs (#291).

The per-task builder validator (#107, ``_validate_builder_output``) enforces
only the *active task's* ``task_required_files``. When framing decomposes
builder work across tasks, a file that the build profile requires but no
single task owns is never enforced — so a run could ship green without, e.g.,
the ``Dockerfile`` its own profile mandates (the third #276 symptom, split out
as #291).

This module is the missing net: a pure check run at run completion, when the
full emitted-artifact set is known. It lives in the domain (not the executor)
so the decision logic is unit-testable without driving a whole run, and the
executor only supplies the inputs and acts on the verdict.

Scope: builder deliverable runs only (``plan_has_builder_task``). The generic
``development.develop`` / ``qa.test`` build steps have no build profile and are
intentionally out of scope — see ``_BUILD_TASK_TYPES`` vs
``BUILDER_TASK_TYPE_PREFIX`` in ``task_plan``.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.build_profiles import get_profile
from squadops.cycles.check_registry import CHECK_REQUIRED_FILES
from squadops.cycles.task_plan import plan_has_builder_task
from squadops.cycles.verification_integrity import (
    CheckProvenance,
    CheckResult,
    ResultStatus,
)

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)

# Bound the missing-file digest carried in provenance (§7: bounded, never a
# payload copy). Basenames are short; this caps a pathological deliverable.
_MISSING_DIGEST_MAX = 200


@dataclass(frozen=True)
class RequiredFilesOutcome:
    """Result of evaluating a builder run's ``required_files`` (#291/#399).

    ``missing`` empty ⇒ every required file was emitted. ``check_result`` is the
    SIP-0096 evidence record (§6.1) the executor appends to the ``RunLedger`` so
    a missing-files run's verdict is honestly ``rejected`` rather than reading
    ``accepted`` on zero evidence.
    """

    profile_name: str
    missing: tuple[str, ...]
    check_result: CheckResult


def evaluate_required_files(
    plan: list[TaskEnvelope],
    stored_artifacts: list[tuple[str, ArtifactRef]],
    resolved_config: dict[str, Any],
) -> RequiredFilesOutcome | None:
    """Evaluate ``build_profile.required_files`` against the emitted artifact set.

    Returns ``None`` when the run isn't a builder deliverable run (or its profile
    can't be resolved — deferred, see below); otherwise the profile, the missing
    basenames (empty ⇒ complete), and a normalized ``required_files``
    ``CheckResult`` (passed when complete, failed otherwise, with bounded §7
    provenance: a digest of the emitted set and, on failure, the missing list).

    Filenames are compared by basename on both sides — matching the builder
    handler's ``os.path.basename`` normalization — so a required ``Dockerfile``
    is satisfied whether emitted at the root or under a subdirectory.
    """
    if not plan_has_builder_task(plan):
        return None

    profile_name = resolved_config.get("build_profile")
    if not profile_name:
        # A builder run without build_profile is a misconfiguration that
        # generate_task_plan rejects before dispatch (#392, CycleError → run
        # FAILED), so this is unreachable in a normal run. Defer rather than
        # fabricate a profile to check against — but log, since reaching here
        # means the plan-generation guard was bypassed.
        logger.warning(
            "required_files check skipped: builder run has no build_profile "
            "(should have been rejected at plan generation)"
        )
        return None
    try:
        profile = get_profile(profile_name)
    except ValueError:
        # An unknown profile would already have failed the builder task in the
        # handler (get_profile raises there too), so a fail-fast run never
        # reaches completion with one. Defer rather than crash on a config error
        # already surfaced upstream.
        logger.warning("required_files check skipped: unknown build profile %r", profile_name)
        return None

    emitted = {os.path.basename(ref.filename) for _, ref in stored_artifacts if ref.filename}
    missing = tuple(
        name for name in profile.required_files if os.path.basename(name) not in emitted
    )
    subject_ref = (
        "fileset:" + hashlib.sha256(",".join(sorted(emitted)).encode("utf-8")).hexdigest()[:16]
    )
    check_result = CheckResult(
        check_id=CHECK_REQUIRED_FILES,
        status=ResultStatus.FAILED if missing else ResultStatus.PASSED,
        provenance=CheckProvenance(
            subject_ref=subject_ref,
            output_digest=(",".join(missing)[:_MISSING_DIGEST_MAX] if missing else None),
        ),
    )
    return RequiredFilesOutcome(
        profile_name=profile_name, missing=missing, check_result=check_result
    )


def compute_missing_required_files(
    plan: list[TaskEnvelope],
    stored_artifacts: list[tuple[str, ArtifactRef]],
    resolved_config: dict[str, Any],
) -> tuple[str, list[str]] | None:
    """The #291 deliverable-completeness verdict: ``(profile, missing)`` or ``None``.

    Thin wrapper over :func:`evaluate_required_files` preserving #291's shape —
    ``None`` when the run isn't a builder run **or** every required file is
    present; the profile + missing list only when the deliverable is incomplete.
    """
    outcome = evaluate_required_files(plan, stored_artifacts, resolved_config)
    if outcome is None or not outcome.missing:
        return None
    return outcome.profile_name, list(outcome.missing)
