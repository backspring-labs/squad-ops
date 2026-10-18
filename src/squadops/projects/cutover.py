"""The registry cutover's refusals (SIP-0112 FR-03, E.5; the owner's R3 on #2408, 2026-10-18).

Both are read at the runtime API's start, over what the writable registry holds:

- **On the writable registry,** every project ``config/projects.yaml`` names is in it, seeded.
  One that is missing would read as 404 for a project that has always existed (IR-1); one held
  by a registered Project of the same ID is a conflict to reconcile explicitly, never a merge.
- **On the config provider,** before the cutover or after a rollback to it, the registry holds
  no registered Project. The config file cannot show one, so a rollback would hide it.

A refusal stops the runtime API: serving with a Project missing is the silent failure.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from squadops.projects.models import ProjectProvenance


@dataclass(frozen=True)
class CutoverProblem:
    project_id: str
    reason: str


class RegistryCutoverRefused(RuntimeError):
    """The runtime API refuses to serve: a Project would be missing, shadowed or hidden."""

    def __init__(self, problems: Iterable[CutoverProblem]) -> None:
        self.problems = tuple(problems)
        named = "; ".join(f"{p.project_id}: {p.reason}" for p in self.problems)
        super().__init__(f"the project registry refuses to serve: {named}")


def problems_after_seeding(
    config_ids: Iterable[str], records: Mapping[str, ProjectProvenance]
) -> list[CutoverProblem]:
    """What stops the writable registry serving, once ``config/projects.yaml`` is seeded."""
    problems = []
    for project_id in config_ids:
        provenance = records.get(project_id)
        if provenance is None:
            problems.append(
                CutoverProblem(
                    project_id, "named by config/projects.yaml, absent from the registry"
                )
            )
        elif provenance is ProjectProvenance.REGISTERED:
            problems.append(
                CutoverProblem(
                    project_id,
                    "named by config/projects.yaml and registered separately: reconcile it",
                )
            )
    return problems


def problems_on_the_config_provider(
    records: Mapping[str, ProjectProvenance],
) -> list[CutoverProblem]:
    """What stops the config provider serving: a registered Project it cannot read."""
    return [
        CutoverProblem(project_id, "registered, and the config provider cannot read it")
        for project_id, provenance in sorted(records.items())
        if provenance is ProjectProvenance.REGISTERED
    ]


def unknown_project_ids(referenced: Iterable[str], records: Mapping[str, object]) -> list[str]:
    """Project IDs that cycles or campaigns hold and the registry doesn't. They are kept and
    reported, never deleted (FR-03): no table enforces a Project foreign key."""
    return sorted(set(referenced) - set(records))
