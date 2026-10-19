"""A Project's source in the sandbox (SIP-0112 §8.2.2, contract 3; E.4.2).

The managed clone's tree at a pinned commit is seeded into a sandbox workspace as a Git checkout
(X-1, X-2), and the mapping between the commit and the sandbox revision is recorded both ways,
with SIP-0109's tree identity beside them. The three identifiers never stand in for one another.
The sandbox never runs Git; this is the only place a commit and a revision meet.

The inherited baseline (FR-20) runs the product's declared checks against that seeded revision,
each in a disposable copy (X-3a), and records what happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from squadops.campaigns.evaluator_trees import FileTree
from squadops.projects.baseline import (
    CheckResult,
    InheritedBaseline,
    missing_environment,
    result_of,
)
from squadops.projects.configuration import baseline_tree
from squadops.projects.development_configuration import submission_digest
from squadops.sandbox.models import RevisionOrigin

if TYPE_CHECKING:
    from squadops.cycles.models import Project
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.source_repository import SourceRepositoryPort
    from squadops.ports.sandbox import ExecutionSandboxPort
    from squadops.sandbox.models import WorkspaceRevision


class SandboxUnavailable(RuntimeError):
    """The runtime API has no sandbox client (``sandbox_client.provider: none``): nothing can
    be seeded or run, so nothing is recorded as if it had been."""


@dataclass(frozen=True)
class SourceMapping:
    """One tree, named by all three of its identifiers (contracts 3 and 4)."""

    project_id: str
    workspace_id: str
    direction: str  # "seeded" or "captured"
    commit: str
    sandbox_revision_id: str
    tree_identity: str
    cycle_id: str | None = None
    campaign_id: str | None = None


async def seed_project_tree(
    project: Project,
    commit: str,
    workspace_id: str,
    *,
    registry: ProjectRegistryPort,
    repository: SourceRepositoryPort,
    sandbox: ExecutionSandboxPort | None,
    cycle_id: str | None = None,
    campaign_id: str | None = None,
) -> WorkspaceRevision:
    """Seed ``commit``'s tree as ``workspace_id``'s first revision, and record the mapping."""
    if sandbox is None:
        raise SandboxUnavailable("the runtime API has no sandbox client to seed through")
    if project.source is None:
        raise ValueError(f"Project {project.project_id} has no external source to seed")
    tree = await baseline_tree(
        repository, project.project_id, project.source.repo_uri, project.source.base_ref, commit
    )
    if tree.capability_gaps:
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import ProjectStateConflictError

        raise ProjectStateConflictError(
            "capability gap: the sandbox cannot carry " + "; ".join(tree.capability_gaps)
        )
    revision = await sandbox.seed_workspace(
        workspace_id,
        dict(tree.files),
        origin=RevisionOrigin.GIT_CHECKOUT,
        executable=tree.executable,
    )
    await registry.record_source_mapping(
        SourceMapping(
            project_id=project.project_id,
            workspace_id=workspace_id,
            direction="seeded",
            commit=commit,
            sandbox_revision_id=revision.revision_id,
            tree_identity=FileTree.of(tree.files).identity,
            cycle_id=cycle_id,
            campaign_id=campaign_id,
        )
    )
    return revision


async def capture_inherited_baseline(
    project_id: str,
    *,
    registry: ProjectRegistryPort,
    repository: SourceRepositoryPort,
    sandbox: ExecutionSandboxPort | None,
    actor: str,
    idempotency_key: str,
) -> tuple[InheritedBaseline, bool]:
    """Run the current Development Configuration's checks against the Project's pinned,
    unmodified baseline commit, and record the inherited baseline (FR-20)."""
    project = await registry.get_project(project_id)
    commit = project.development_baseline_commit
    configuration = await registry.get_development_configuration(project_id)
    if commit is None or configuration.validated_at_commit != commit:
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import ProjectStateConflictError

        raise ProjectStateConflictError(
            f"Project {project_id}'s Development Configuration revision "
            f"{configuration.revision} was recorded at {configuration.validated_at_commit}, not "
            f"its baseline {commit}: record a revision at the baseline first (FR-21)"
        )
    workspace_id = f"baseline-{project_id}-{commit[:12]}"
    revision = await seed_project_tree(
        project, commit, workspace_id, registry=registry, repository=repository, sandbox=sandbox
    )
    commands = configuration.commands
    results: list[CheckResult] = []
    environment: dict[str, str] = {}
    for check in commands.checks:
        # The sandbox runs a declared check with no environment of its own (X-3a), so a check
        # that declares one is a gap, decided by its declaration.
        gap = missing_environment(check, ())
        if gap is not None:
            results.append(gap)
            continue
        run: Any = await sandbox.run_declared_command(  # type: ignore[union-attr]
            revision=revision, command=check.argv, working_dir=commands.working_directory
        )
        environment = environment or {
            "image": run.image_identity or "unknown",
            "toolchain": run.environment_contract_id or "unknown",
        }
        results.append(result_of(check, run))
    baseline = InheritedBaseline(
        project_id=project_id,
        commit=commit,
        development_configuration_revision=configuration.revision,
        environment=environment or {"image": "unknown", "toolchain": "unknown"},
        checks=tuple(results),
    )
    return await registry.record_inherited_baseline(
        baseline,
        actor=actor,
        idempotency_key=idempotency_key,
        request_hash=submission_digest(
            {"project_id": project_id, "commit": commit, "revision": configuration.revision}
        ),
    )
