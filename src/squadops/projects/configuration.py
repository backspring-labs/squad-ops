"""Recording a Project's Development Configuration (SIP-0112 §B.5, §B.5.1, E.4.2).

A submission names the product's commands: its checks and its start declaration. The record adds
what SquadOps finds:
- the commit it is recorded against, the Project's development baseline;
- the repository's instruction sources at that commit, each with its digest.

So the commands and the instructions that describe them come from the same commit (§B.5.1). A
Project must be READY: its source has been reached, and its baseline commit is known.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from squadops.projects.development_configuration import (
    ConfigurationInvalid,
    DevelopmentConfiguration,
    discover_instruction_sources,
    parse_technical,
    submission_digest,
)
from squadops.projects.models import CheckoutTree, SourceUnavailable
from squadops.stacks.scaffold import is_scaffoldable_stack, scaffoldable_stacks

if TYPE_CHECKING:
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.source_repository import SourceRepositoryPort


async def configure_project(
    project_id: str,
    submission: Mapping[str, Any],
    *,
    expected_revision: int,
    registry: ProjectRegistryPort,
    repository: SourceRepositoryPort,
    actor: str,
    idempotency_key: str,
) -> tuple[DevelopmentConfiguration, bool]:
    """Validate ``submission`` (its ``technical`` block, and optionally ``quality``), find the
    instruction sources at the baseline commit, and record the next revision."""
    project = await registry.get_project(project_id)
    commit = project.development_baseline_commit
    if not project.lifecycle_status.accepts_cycles or project.source is None or commit is None:
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import ProjectStateConflictError

        raise ProjectStateConflictError(
            f"Project {project_id} is {project.lifecycle_status.value}: a Development "
            "Configuration is recorded for a registered Project whose source has been reached"
        )
    project_type, target, stack, commands = parse_technical(_mapping(submission, "technical"))
    await _check_stack(registry, project_id, stack)
    tree = await baseline_tree(
        repository, project_id, project.source.repo_uri, project.source.base_ref, commit
    )
    quality = submission.get("quality") or {}
    configuration = DevelopmentConfiguration(
        project_id=project_id,
        revision=expected_revision + 1,
        validated_at_commit=commit,
        project_type=project_type,
        target=target,
        stack=stack,
        commands=commands,
        instruction_sources=discover_instruction_sources(tree.files, commit),
        quality_contract_ref=quality.get("contract_ref"),
    )
    return await registry.record_development_configuration(
        configuration,
        actor=actor,
        idempotency_key=idempotency_key,
        request_hash=submission_digest(
            {"project_id": project_id, "expected_revision": expected_revision, **submission}
        ),
    )


async def baseline_tree(
    repository: SourceRepositoryPort, project_id: str, locator: str, ref: str, commit: str
) -> CheckoutTree:
    """The tree at the baseline commit. The managed clone is a cache, lost with its container,
    so a missing clone is fetched again and the commit read from it (§B.3)."""
    try:
        return await repository.tree_at(project_id, commit)
    except SourceUnavailable as e:
        if e.reason not in ("not_cloned", "read"):
            raise
    await repository.sync(project_id, locator, ref)
    return await repository.tree_at(project_id, commit)


def _mapping(doc: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = doc.get(key)
    if not isinstance(value, Mapping):
        raise ConfigurationInvalid(key, "required, a mapping")
    return value


async def _check_stack(registry: ProjectRegistryPort, project_id: str, stack: str | None) -> None:
    """§B.4.1: ``stack`` names a SIP-0105 blueprint, and a greenfield Project names the one it
    was initialized on (E.4.6). Checked as it's submitted; a recorded revision is read as it was
    recorded."""
    if stack is not None and not is_scaffoldable_stack(stack):
        raise ConfigurationInvalid(
            "technical.stack",
            f"{stack!r} is not a SIP-0105 blueprint ({', '.join(scaffoldable_stacks())})",
        )
    initialization = await registry.get_initialization(project_id)
    if initialization is not None and stack != initialization.stack:
        raise ConfigurationInvalid(
            "technical.stack",
            f"Project {project_id} was initialized on the {initialization.stack} blueprint, "
            "which its Development Configuration names",
        )
