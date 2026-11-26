"""Where a source-backed plan's authors may not plan work, composed into their inputs with the run's
plan, before the first dispatch (SIP-0112 H.4, H.8).

A blocking gap of the Project's derived profile that is confined to paths refuses a plan that writes
there, at both plan gates (``ImplementationPlan.validate_blocking_gaps``). The plan's authors are
shown those paths first (#686: teach, then enforce): each task ``authors_plan`` names gets them on
its own inputs, as the index ``request.plan_blocking_gaps_appendix`` renders. An unconfined gap
refused the Cycle at create, so only confined ones reach here.

**The paths the product's owner reserves are shown the same way** (SIP-0112 H.35, #3155): a plan
that writes one is refused by ``ImplementationPlan.validate_reserved_paths``, and its authors get
the declared entries as ``request.plan_reserved_paths_appendix`` renders them.

**What each of the product's test runners collects is shown the same way** (SIP-0112 H.4 point
3, #3182): a plan whose ``qa.test`` names a file none collects is refused by
``ImplementationPlan.validate_qa_suite_collected``, and its authors get each runner's roots and
file-name pattern as ``request.plan_test_runners_appendix`` renders them.

**A cycle with no source, or a pin whose baseline has no profile, adds no key,** so its authors'
inputs are the ones they had before H.4. A product that reserves no path adds none for them.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable
from typing import Any

from squadops.cycles.models import Cycle
from squadops.projects.derived_profile import BLOCKING, DerivedProfile
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import authors_plan

BLOCKED_PATHS_INPUT = "blocked_paths_index"
RESERVED_PATHS_INPUT = "reserved_paths_index"
TEST_RUNNERS_INPUT = "test_runners_index"


async def with_blocked_paths(
    read_profile: Callable[[Cycle], Awaitable[Any]],
    envelopes: list[TaskEnvelope],
    *,
    cycle: Cycle,
) -> list[TaskEnvelope]:
    """``envelopes`` with the blocked paths on each plan author's inputs, read once for the run."""
    authors = [i for i, e in enumerate(envelopes) if authors_plan(e.task_type)]
    if not authors or cycle.source_context is None:
        return envelopes
    profile = await read_profile(cycle)
    shown = {
        key: index
        for key, index in (
            (BLOCKED_PATHS_INPUT, blocked_paths_index(profile)),
            (RESERVED_PATHS_INPUT, reserved_paths_index(profile)),
            (TEST_RUNNERS_INPUT, runner_collection_index(profile)),
        )
        if index is not None
    }
    if not shown:
        return envelopes
    composed = list(envelopes)
    for i in authors:
        composed[i] = dataclasses.replace(envelopes[i], inputs={**envelopes[i].inputs, **shown})
    return composed


def runner_collection_index(profile: DerivedProfile | None) -> str | None:
    """What each of the product's test runners collects, one line per runner, with the support
    files on record after them, or ``None`` for a product
    whose profile names none. The lines ``validate_qa_suite_collected`` is read against."""
    if profile is None or not profile.runners:
        return None
    lines = [
        f"- `{r.runner}`: a file named `{r.file_pattern}` under "
        + ", ".join(f"`{root}`" for root in r.roots)
        for r in profile.runners
    ]
    if profile.test_support_files:
        lines.append(
            "- support files the suites already share, which a `qa.test` may also change: "
            + ", ".join(f"`{path}`" for path in profile.test_support_files)
        )
    return "\n".join(lines)


def reserved_paths_index(profile: DerivedProfile | None) -> str | None:
    """Each path the product's owner reserves, as one line, or ``None`` when it reserves none."""
    if profile is None or not profile.reserved_paths:
        return None
    return "\n".join(f"- `{entry}`" for entry in profile.reserved_paths)


def blocked_paths_index(profile: DerivedProfile | None) -> str | None:
    """Each confined gap that stops the work, as one line: where, which, why, and what closes it."""
    if profile is None:
        return None
    lines = [
        f"- `{', '.join(g.paths)}`: {g.id}{f' ({g.subject})' if g.subject else ''}. {g.reason}. "
        f"It closes with: {g.closes_by}."
        for g in profile.gaps
        if g.kind == BLOCKING and g.stops == "work" and "**" not in g.paths
    ]
    return "\n".join(lines) or None
