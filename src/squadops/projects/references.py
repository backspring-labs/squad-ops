"""A repository reference resolved at a unit's pinned commit (SIP-0112 §8.2 contract 6, §B.5.1;
E.4.4).

SIP-0110 binds project instructions when a unit is admitted. Where an instruction cites a source
in the product's repository (``CONTRIBUTING.md``, ``AGENTS.md``), that source is a required
reference, and it is read at the commit the unit's source context pins, never at the branch's
head. That way a unit's instructions and the commands they describe come from the same commit.
Its content digest is recorded with the binding. This module is that resolver. Binding it to a
task is SIP-0110's (#2179).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from squadops.projects.source_context import ProjectSourceContext


class ReferenceUnresolved(RuntimeError):
    """A repository reference that can't be read at the pinned commit. SIP-0110 holds the task
    that requires it, with this reason (its §3.6): recording the omission is not enough."""


@dataclass(frozen=True)
class RepositoryReference:
    project_id: str
    path: str
    commit: str
    digest: str
    content: bytes


async def resolve_repository_reference(
    context: ProjectSourceContext, path: str, *, repository: Any
) -> RepositoryReference:
    """``path`` as the unit's pinned commit holds it, with its content digest."""
    # deferred (pair): squadops.projects.models is light, but keep this module port-free at load
    from squadops.projects.models import SourceUnavailable

    commit = context.development_baseline_commit
    try:
        content = await repository.file_at(context.project_id, commit, path)
    except SourceUnavailable as e:
        raise ReferenceUnresolved(f"{path} at {commit[:12]}: {e}") from e
    return RepositoryReference(
        project_id=context.project_id,
        path=path,
        commit=commit,
        digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
        content=content,
    )
