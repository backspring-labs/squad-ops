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

import logging
import os
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.build_profiles import DEFAULT_BUILD_PROFILE, get_profile
from squadops.cycles.task_plan import plan_has_builder_task

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)


def compute_missing_required_files(
    plan: list[TaskEnvelope],
    stored_artifacts: list[tuple[str, ArtifactRef]],
    resolved_config: dict[str, Any],
) -> tuple[str, list[str]] | None:
    """Profile-level required-files check for a completed builder run.

    Args:
        plan: the run's full task plan (used only to detect a builder run).
        stored_artifacts: ``(artifact_id, ArtifactRef)`` for every artifact the
            run emitted — the complete deliverable set at run completion.
        resolved_config: ``{**applied_defaults, **execution_overrides}`` — the
            same merged config the builder handler reads ``build_profile`` from,
            so the fallback matches.

    Returns:
        ``(profile_name, missing_files)`` when the run built a deliverable and
        one or more of the build profile's ``required_files`` is absent from the
        complete emitted set; ``None`` when the run isn't a builder run or every
        required file is present.

    Filenames are compared by basename on both sides — matching the builder
    handler's ``os.path.basename`` normalization — so a required ``Dockerfile``
    is satisfied whether it was emitted at the root or under a subdirectory, and
    a path mismatch never fails a complete deliverable.
    """
    if not plan_has_builder_task(plan):
        return None

    profile_name = resolved_config.get("build_profile", DEFAULT_BUILD_PROFILE)
    try:
        profile = get_profile(profile_name)
    except ValueError:
        # An unknown profile would already have failed the builder task in the
        # handler (get_profile raises there too), so a fail-fast run never
        # reaches completion with one. Defer rather than crash the completeness
        # net on a config error already surfaced upstream.
        logger.warning(
            "required_files completeness check skipped: unknown build profile %r", profile_name
        )
        return None

    emitted = {os.path.basename(ref.filename) for _, ref in stored_artifacts if ref.filename}
    missing = [name for name in profile.required_files if os.path.basename(name) not in emitted]
    if missing:
        return profile_name, missing
    return None
