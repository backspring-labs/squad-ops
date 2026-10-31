"""Where a source-backed plan's authors may not plan work, composed into their inputs with the run's
plan, before the first dispatch (SIP-0112 H.4, H.8).

A blocking gap of the Project's derived profile that is confined to paths refuses a plan that writes
there, at both plan gates (``ImplementationPlan.validate_blocking_gaps``). The plan's authors are
shown those paths first (#686: teach, then enforce): each task ``authors_plan`` names gets them on
its own inputs, as the index ``request.plan_blocking_gaps_appendix`` renders. An unconfined gap
refused the Cycle at create, so only confined ones reach here.

**A cycle with no source, or a pin whose baseline has no profile, adds no key,** so its authors'
inputs are the ones they had before H.4.
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
    index = blocked_paths_index(await read_profile(cycle))
    if index is None:
        return envelopes
    composed = list(envelopes)
    for i in authors:
        inputs = {**envelopes[i].inputs, BLOCKED_PATHS_INPUT: index}
        composed[i] = dataclasses.replace(envelopes[i], inputs=inputs)
    return composed


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
