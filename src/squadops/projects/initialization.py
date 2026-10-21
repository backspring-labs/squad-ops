"""A greenfield product's first commit, at the destination its owner approved (SIP-0112 FR-01,
UC-B; E.4.6).

A greenfield Project is registered like an existing product, against a repository the owner made
and left empty. SquadOps never creates the repository: it binds the pre-provisioned one (FR-01
step 4, narrowed by amendment H.1). Initializing it is the owner's act, once per Project:
- the layout comes from a SIP-0105 blueprint, rendered from the approved interface manifest, as
  the scaffold renders it for a sample application's run, and nothing else is written;
- it becomes the branch's first commit, pushed with the owner's token for that act, never forced,
  and refused when the branch already has a commit.

From there the product goes through the lifecycle an existing product does: validation reaches its
source, its Development Configuration names the blueprint (§B.4.1), its baseline is captured, and
its Cycles contribute by its own process.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from squadops.projects.development_configuration import submission_digest
from squadops.projects.models import ProjectLifecycleStatus
from squadops.stacks.scaffold import InterfaceManifest, expand

#: A Project whose source hasn't been reached: registered, or failed validation on an empty branch.
INITIALIZABLE = (ProjectLifecycleStatus.REGISTERING, ProjectLifecycleStatus.FAILED_REGISTRATION)
_HEADS = "refs/heads/"


class InitializationRefused(RuntimeError):
    """An initialization that can't be made, with the reason. Nothing left the deploy."""


@dataclass(frozen=True)
class ProjectInitialization:
    project_id: str
    commit: str
    branch: str
    stack: str
    #: sha256 of the manifest as submitted: the record of which approved structure was rendered
    manifest_digest: str
    manifest: str
    files: tuple[str, ...]
    initialized_by: str
    initialized_at: datetime

    def to_document(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "commit": self.commit,
            "branch": self.branch,
            "stack": self.stack,
            "manifest_digest": self.manifest_digest,
            "files": list(self.files),
            "initialized_by": self.initialized_by,
            "initialized_at": self.initialized_at.isoformat(),
        }


def initial_tree(manifest: InterfaceManifest) -> tuple[dict[str, bytes], frozenset[str]]:
    """The blueprint's layout for ``manifest``, and which of its files are executable."""
    files = {f["name"]: f["content"].encode() for f in expand(manifest)}
    return files, frozenset(p for p in files if p.endswith(".sh"))


def read_manifest(project_id: str, text: str) -> InterfaceManifest:
    """The approved interface manifest, refused when it doesn't name this Project or can't be
    scaffolded: a greenfield layout is never guessed."""
    try:
        manifest = InterfaceManifest.from_yaml(text)
    except (ValueError, TypeError, KeyError) as e:
        raise InitializationRefused(f"the interface manifest doesn't parse: {e}") from e
    if manifest.project_id != project_id:
        raise InitializationRefused(
            f"the interface manifest is for {manifest.project_id!r}, not Project {project_id}"
        )
    problems = manifest.lint()
    if problems:
        raise InitializationRefused(
            "the interface manifest can't be scaffolded: " + "; ".join(problems)
        )
    return manifest


async def initialize_project(
    project_id: str,
    manifest_text: str,
    *,
    registry: Any,
    repository: Any,
    tokens: Mapping[str, str],
    actor: str,
    idempotency_key: str,
    now: datetime,
) -> tuple[ProjectInitialization, bool]:
    """Render the blueprint's layout from ``manifest_text``, push it as the Project's first
    commit, and record it. A Project initialized already is answered with its record when the
    manifest is the same one, and refused when it isn't."""
    project = await registry.get_project(project_id)
    if project.source is None:
        raise InitializationRefused(
            f"Project {project_id} is a sample application: it has no repository to initialize"
        )
    digest = f"sha256:{hashlib.sha256(manifest_text.encode()).hexdigest()}"
    existing = await registry.get_initialization(project_id)
    if existing is not None:
        if existing.manifest_digest != digest:
            raise InitializationRefused(
                f"Project {project_id} was initialized at {existing.commit[:12]} from another "
                "manifest: a Project's first commit is made once"
            )
        return existing, True
    if project.lifecycle_status not in INITIALIZABLE or project.development_baseline_commit:
        raise InitializationRefused(
            f"Project {project_id} is {project.lifecycle_status.value}, its source reached: "
            "only a Project whose branch has no commit yet is initialized"
        )
    if not project.source.base_ref.startswith(_HEADS):
        raise InitializationRefused(
            f"a first commit goes to a branch, and the Project's base is {project.source.base_ref}"
        )
    token = tokens.get(project_id)
    if not token:
        raise InitializationRefused(
            f"no token for Project {project_id}: pass the owner's own with the request "
            "(`squadops projects initialize --token-from-gh`), or the deploy names one "
            "(projects.review_request_tokens)"
        )
    manifest = read_manifest(project_id, manifest_text)
    files, executable = initial_tree(manifest)
    commit = await repository.initialize(
        project_id,
        project.source.repo_uri,
        ref=project.source.base_ref,
        files=files,
        executable=executable,
        message=_message(project.name, manifest.stack, digest),
        # The registration's time, so a retry of this request makes the same commit.
        committed_at=int(project.created_at.timestamp()),
        token=token,
    )
    initialization = ProjectInitialization(
        project_id=project_id,
        commit=commit,
        branch=project.source.base_ref.removeprefix(_HEADS),
        stack=manifest.stack,
        manifest_digest=digest,
        manifest=manifest_text,
        files=tuple(sorted(files)),
        initialized_by=actor,
        initialized_at=now,
    )
    return await registry.record_initialization(
        initialization,
        idempotency_key=idempotency_key,
        request_hash=submission_digest({"project_id": project_id, "manifest_digest": digest}),
    )


def _message(name: str, stack: str, digest: str) -> str:
    return (
        f"Start {name} on the {stack} blueprint\n\n"
        f"The layout SquadOps scaffolds for {stack} (SIP-0105), rendered from the approved "
        f"interface manifest ({digest}). The product is developed from here through its own "
        "lifecycle (SIP-0112 E.4.6).\n"
    )
