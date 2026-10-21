"""Validating a registered Project: is its source reachable, and can a Cycle's sandbox carry it?
(SIP-0112 FR-01 item 7, FR-02, §B.6; E.4.2; the owner's R4.)

READY means the source was reached at the base ref and its tree is one the sandbox can seed. It
does not mean the product passes its own checks: that is the inherited baseline's to record
(FR-20), and a failing check doesn't keep a Project from being READY. A source that can't be
reached, or a tree the sandbox can't carry whole (a tracked symlink or submodule), leaves it
FAILED_REGISTRATION with the reason, and an explicit retry validates it again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.projects.models import ProjectLifecycleStatus, ProjectSource, SourceUnavailable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from squadops.cycles.models import Project
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.source_repository import SourceRepositoryPort


async def validate_project(
    project_id: str,
    *,
    registry: ProjectRegistryPort,
    repository: SourceRepositoryPort,
    actor: str,
    idempotency_key: str,
    tokens: Mapping[str, str] | None = None,
) -> tuple[Project, bool]:
    """Reach the Project's source through the managed clone and record what was found. A READY
    Project is re-validated (E.4.4): its development baseline moves to the upstream's commit, the
    reconciliation a drift finding asks for. A private repository is reached with the Project's
    token in ``tokens``, for this fetch only."""
    project = await registry.get_project(project_id)
    if project.source is None:
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import ProjectStateConflictError

        raise ProjectStateConflictError(
            f"Project {project_id} is a sample application in the image: it has no external "
            "source to validate"
        )
    token = (tokens or {}).get(project_id)
    if project.lifecycle_status == ProjectLifecycleStatus.READY:
        return await _revalidate(
            project, project.source, registry, repository, actor, idempotency_key, token
        )
    commit, diagnostic = None, None
    try:
        resolved = await repository.sync(
            project_id,
            project.source.repo_uri,
            project.source.base_ref,
            token=token,
        )
        gaps = (await repository.tree_at(project_id, resolved)).capability_gaps
    except SourceUnavailable as e:
        diagnostic = f"{e.reason}: {e}"
    else:
        if gaps:
            diagnostic = "capability gap: the sandbox cannot carry " + "; ".join(gaps)
        else:
            commit = resolved
    return await registry.record_validation(
        project_id,
        commit=commit,
        diagnostic=diagnostic,
        actor=actor,
        idempotency_key=idempotency_key,
    )


async def _revalidate(
    project: Project,
    source: ProjectSource,
    registry: ProjectRegistryPort,
    repository: SourceRepositoryPort,
    actor: str,
    idempotency_key: str,
    token: str | None,
) -> tuple[Project, bool]:
    """FR-21's reconciliation: adopt the upstream's commit as the development baseline. A source
    that can't be reached, or a tree the sandbox can't carry, is raised, never recorded: a READY
    Project isn't demoted by a fetch that failed, and it stays READY at the baseline it has.
    Units already prepared keep the commit they pinned (contract 1). New ones pin the new
    commit, and are refused until a Development Configuration and an inherited baseline are
    recorded there."""
    resolved = await repository.sync(
        project.project_id, source.repo_uri, source.base_ref, token=token
    )
    gaps = (await repository.tree_at(project.project_id, resolved)).capability_gaps
    if gaps:
        raise SourceUnavailable(
            "capability gap: the sandbox cannot carry " + "; ".join(gaps), reason="capability_gap"
        )
    if resolved == project.development_baseline_commit:
        return project, False  # the upstream is the baseline: nothing to adopt
    return await registry.record_validation(
        project.project_id,
        commit=resolved,
        diagnostic=None,
        actor=actor,
        idempotency_key=idempotency_key,
    )
