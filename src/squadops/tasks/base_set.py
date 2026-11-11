"""The base set: the capabilities a cycle has with no requirement (SIP-0116 §6.3).

Explicit and versioned, so that registering a handler enables nothing. ``base@1`` is what
every cycle was offered before a stack could require anything: the three task types a
planner may put in a plan. The steps the fixed step tables dispatch are in every cycle by
those tables and are not listed here.

A new plannable task type is its own proposal, and it joins a cycle's offered set through a
requirement, never by being added to an existing version of the base set. A changed base set
is a new version, and a cycle's skillset record names the version it ran under.
"""

from __future__ import annotations

from squadops.tasks.task_types import TaskType

BASE_SET_VERSION = "base@1"

#: The plannable task types of each base-set version.
BASE_SETS: dict[str, frozenset[TaskType]] = {
    "base@1": frozenset(
        {
            TaskType.DEVELOPMENT_DEVELOP,
            TaskType.QA_TEST,
            TaskType.BUILDER_ASSEMBLE,
        }
    ),
}


def base_plannable_task_types(version: str = BASE_SET_VERSION) -> frozenset[TaskType]:
    """The task types ``version`` of the base set lets a planner offer. An unknown version
    raises: a record naming one was written by a deploy this one can't read."""
    try:
        return BASE_SETS[version]
    except KeyError:
        raise ValueError(
            f"Unknown base set {version!r}. Known: {', '.join(sorted(BASE_SETS))}"
        ) from None
