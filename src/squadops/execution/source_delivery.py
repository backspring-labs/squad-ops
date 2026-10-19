"""A source-backed run's delivery: its candidate, verified and captured (SIP-0112 E.4.3; FR-06,
FR-20; contract 3).

Once the plan's tasks are done, the run's change to the product is known. It is delivered in
three steps:
1. **The candidate.** The pinned commit's tree is seeded into a sandbox workspace
   (``git_checkout``, mapped ``seeded``). The squad's accepted changes are applied to it as one
   patch (``agent_patch``), cutting the candidate revision. Its ID is checked against the one
   the run computes from the same content, so the tree verified is the tree delivered.
2. **Verification.** The product's own checks run against the candidate through X-3a. They are
   attributed against the inherited baseline, which must be the one at the pinned commit and
   Development Configuration revision (squadops.projects.verification).
3. **Capture,** for an accepted candidate. The revision is read back from the sandbox, committed
   in the managed clone on the pinned commit (``refs/squadops/<cycle>/<run>``), and read back
   from Git to the same tree identity. It is mapped ``captured``, and the commit's patch is
   kept as the run's ``patch_export`` contribution.

The squad's change is the files its source and test authors produced, at their latest accepted
content, that differ from the checkout's. A file it rewrites keeps the checkout's CRLF line
endings when the original used them throughout. A run's own documents (plans, reports) are
never part of the product.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.campaigns.evaluator_trees import FileTree
from squadops.cycles.emission_integrity import EMISSION_STATUS_FAILED
from squadops.cycles.models import ArtifactRef, Cycle
from squadops.cycles.task_plan import REPAIR_TASK_TYPES
from squadops.projects.checkout import SOURCE_CHECKOUT
from squadops.projects.configuration import baseline_tree
from squadops.projects.verification import ACCEPTED, SourceVerification, attributed
from squadops.projects.workspaces import SourceMapping, run_checks, seed_project_tree
from squadops.sandbox.models import RevisionOrigin, WorkspaceRevision, content_bytes
from squadops.tasks.task_types import authors_qa_suite, authors_source

SOURCE_VERIFICATION_TYPE = "source_verification"
SOURCE_VERIFICATION_FILENAME = "source_verification.json"
SOURCE_PATCH_TYPE = "source_patch"
SOURCE_PATCH_FILENAME = "source_change.patch"


class SourceDeliveryRefused(RuntimeError):
    """A source-backed run whose change can't be verified or captured, with the reason."""


@dataclass(frozen=True)
class SourceDelivery:
    verification: SourceVerification
    artifact_ids: tuple[str, ...]
    captured_commit: str | None = None


def squad_changes(
    stored_artifacts: list[tuple[str, ArtifactRef]],
    contents: Mapping[str, bytes],
    checkout: Mapping[str, bytes],
) -> dict[str, bytes]:
    """The product files the squad changed or added: each path's latest accepted content from a
    source or test author, where it differs from the checkout's. ``contents`` maps artifact ID
    to its bytes."""
    latest: dict[str, str] = {}
    for art_id, ref in stored_artifacts:
        producer = ref.metadata.get("producing_task_type", "")
        # As the executor's own resolution reads the workspace: a failed emission is never
        # input, and a repair candidate is unaccepted until it is re-stored as the task's own.
        if ref.metadata.get("emission_status") == EMISSION_STATUS_FAILED:
            continue
        if producer in REPAIR_TASK_TYPES or producer == SOURCE_CHECKOUT:
            continue
        if authors_source(producer) or authors_qa_suite(producer):
            latest[ref.filename] = art_id
    changes = {}
    for path, art_id in sorted(latest.items()):
        content = _line_endings_of(checkout.get(path), contents[art_id])
        if checkout.get(path) != content:
            changes[path] = content
    return changes


def _line_endings_of(original: bytes | None, emitted: bytes) -> bytes:
    if not original or b"\r\n" not in original or original.count(b"\n") != original.count(b"\r\n"):
        return emitted
    return emitted.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


async def deliver_source_change(
    cycle: Cycle,
    run_id: str,
    stored_artifacts: list[tuple[str, ArtifactRef]],
    *,
    vault: Any,
    registry: Any,
    repository: Any,
    sandbox: Any,
) -> SourceDelivery:
    """Verify the run's change against the inherited baseline, and capture it when accepted."""
    context = cycle.source_context
    if context is None:
        raise ValueError(f"cycle {cycle.cycle_id} pins no source: it is not source-backed")
    if repository is None or sandbox is None:
        raise SourceDeliveryRefused(
            "a source-backed run is verified in the sandbox and captured in the managed clone, "
            "and this runtime has " + ("neither" if repository is sandbox else "only one")
        )
    commit = context.development_baseline_commit
    project = await registry.get_project(cycle.project_id)
    configuration = await registry.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    baseline = await registry.get_inherited_baseline(cycle.project_id)
    if (baseline.commit, baseline.development_configuration_revision) != (
        commit,
        context.development_configuration_revision,
    ):
        raise SourceDeliveryRefused(
            f"the inherited baseline is at {baseline.commit}, revision "
            f"{baseline.development_configuration_revision}; the run pins {commit}, revision "
            f"{context.development_configuration_revision}: a candidate is compared only with "
            "the baseline of the tree it changed (FR-20)"
        )
    checkout = await baseline_tree(
        repository, cycle.project_id, context.repo_uri, project.source.base_ref, commit
    )
    contents = {}
    for art_id, _ref in stored_artifacts:
        _stored, contents[art_id] = await vault.retrieve(art_id)
    changes = squad_changes(stored_artifacts, contents, checkout.files)
    if not changes:
        raise SourceDeliveryRefused("the run changed no file of the product")
    binary = sorted(p for p in changes if _is_binary(checkout.files.get(p)))
    if binary:
        raise SourceDeliveryRefused(
            f"the run wrote text over binary files, which 2.4 doesn't edit: {', '.join(binary)}"
        )

    candidate_files = {**checkout.files, **changes}
    tree_identity = FileTree.of(candidate_files).identity
    workspace_id = f"src-{run_id}-{tree_identity[:12]}"
    seeded = await seed_project_tree(
        project,
        commit,
        workspace_id,
        registry=registry,
        repository=repository,
        sandbox=sandbox,
        cycle_id=cycle.cycle_id,
        tree=checkout,
    )
    patched = await sandbox.apply_workspace_patch(base=seeded, files=changes)
    candidate = WorkspaceRevision(
        revision_id=patched.new_revision_id,
        cycle_id=workspace_id,
        origin=RevisionOrigin.AGENT_PATCH,
        parent_revision_id=seeded.revision_id,
    )
    expected = WorkspaceRevision.cut(
        cycle_id=workspace_id,
        origin=RevisionOrigin.AGENT_PATCH,
        files=candidate_files,
        executable=checkout.executable,
    )
    if candidate.revision_id != expected.revision_id:
        raise SourceDeliveryRefused(
            f"the sandbox cut {candidate.revision_id} for the candidate, and its content is "
            f"{expected.revision_id}: the tree it would verify isn't the one the run changed"
        )

    results, environment = await run_checks(sandbox, candidate, configuration.commands)
    verification = SourceVerification(
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        baseline_commit=commit,
        development_configuration_revision=configuration.revision,
        candidate_revision_id=candidate.revision_id,
        candidate_tree_identity=tree_identity,
        changed_paths=tuple(sorted(changes)),
        environment=environment,
        checks=attributed(results, baseline),
    )
    ids = [
        await _store(
            vault,
            cycle,
            run_id,
            SOURCE_VERIFICATION_FILENAME,
            json.dumps(verification.to_document(), indent=1).encode(),
            SOURCE_VERIFICATION_TYPE,
            "application/json",
        )
    ]
    if verification.verdict != ACCEPTED:
        return SourceDelivery(verification, tuple(ids))

    new_commit, captured = await _capture(
        cycle, run_id, candidate, commit, verification, repository, sandbox
    )
    if captured != tree_identity:
        raise SourceDeliveryRefused(
            f"the captured commit's tree is {captured}, and the candidate verified is "
            f"{tree_identity}: the commit is not the change that was verified"
        )
    await registry.record_source_mapping(
        SourceMapping(
            project_id=cycle.project_id,
            workspace_id=workspace_id,
            direction="captured",
            commit=new_commit,
            sandbox_revision_id=candidate.revision_id,
            tree_identity=tree_identity,
            cycle_id=cycle.cycle_id,
            campaign_id=cycle.campaign_id,
        )
    )
    patch = await repository.export_patch(cycle.project_id, new_commit)
    ids.append(
        await _store(
            vault,
            cycle,
            run_id,
            SOURCE_PATCH_FILENAME,
            patch,
            SOURCE_PATCH_TYPE,
            "text/x-patch",
            {"captured_commit": new_commit, "parent_commit": commit},
        )
    )
    return SourceDelivery(verification, tuple(ids), captured_commit=new_commit)


def _capture_ref(cycle: Cycle, run_id: str) -> str:
    return f"refs/squadops/{cycle.cycle_id}/{run_id}"


async def _capture(
    cycle: Cycle,
    run_id: str,
    candidate: WorkspaceRevision,
    parent: str,
    verification: SourceVerification,
    repository: Any,
    sandbox: Any,
) -> tuple[str, str]:
    """Commit the candidate as the sandbox holds it; return the commit and the tree identity
    Git holds for it."""
    content = await sandbox.read_workspace_revision(candidate)
    files = {path: content_bytes(c) for path, c in content.files.items()}
    commit = await repository.commit_tree(
        cycle.project_id,
        parent=parent,
        files=files,
        executable=content.executable,
        ref=_capture_ref(cycle, run_id),
        message=_message(cycle, run_id, parent, verification),
    )
    committed = await repository.tree_at(cycle.project_id, commit)
    return commit, FileTree.of(committed.files).identity


def _message(cycle: Cycle, run_id: str, parent: str, verification: SourceVerification) -> str:
    changed = verification.changed_paths
    shown = ", ".join(changed[:5]) + (f" and {len(changed) - 5} more" if len(changed) > 5 else "")
    return (
        f"SquadOps cycle {cycle.cycle_id}: {shown}\n\n"
        f"Developed by a SquadOps squad in run {run_id}, from {parent}.\n"
        f"The product's own checks: {verification.summary()}.\n"
    )


def _is_binary(content: bytes | None) -> bool:
    if content is None:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


async def _store(
    vault: Any,
    cycle: Cycle,
    run_id: str,
    filename: str,
    content: bytes,
    artifact_type: str,
    media_type: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        artifact_type=artifact_type,
        filename=filename,
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type=media_type,
        created_at=datetime.now(UTC),
        metadata={"source_delivery": True, **(metadata or {})},
    )
    await vault.store(ref, content)
    return ref.artifact_id
