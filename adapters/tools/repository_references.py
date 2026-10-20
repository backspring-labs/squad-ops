"""The repository family's reference resolver (SIP-0112 §8.2 contract 6, §B.5.1; E.4.4): the
T16 port, over the managed clone's.

SIP-0110 binds an instruction's ``@current`` references when the instruction is bound to a unit,
through one resolver per family (``squadops.ports.memory.references``, #2179 T16). This is the
repository family's. ``repo:file:<path>@current`` binds to ``repo:file:<path>@<commit>``, at the
commit the unit's source context pins, never at the branch's head. That way a unit's instructions
and the commands they describe come from the same commit. The content's digest is recorded with the
binding, and a read at the bound commit whose content no longer matches it is refused. A reference
names a text file: one that isn't text is refused when it's bound, not first when it's read. A path
with whitespace can't be referenced, since the records refuse whitespace in a reference.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from squadops.cycles.models import ProjectNotFoundError
from squadops.ports.memory.references import (
    BindingContext,
    BoundReference,
    ReferenceResolverPort,
    ReferenceUnresolved,
)
from squadops.projects.models import SourceUnavailable

REPOSITORY_FAMILY = "repo"

#: A file in the product's tree, by its path from the root: the family's one kind.
_FILE = re.compile(r"^repo:file:(?P<path>[^@]+)@(?P<revision>[^@]+)$")

#: The managed clone's reasons that are about the reference: the commit or path isn't one, or git
#: found no such file there. Every other reason (a timeout, no git) is about the deploy, and says
#: nothing of whether the reference binds, so it's raised as a fault for the caller to repeat
#: rather than kept unbound (SIP-0110 §5ae).
_REFUSALS = frozenset({"not_a_commit", "path_refused", "read"})


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _text(ref: str, content: bytes) -> str:
    try:
        return content.decode()
    except UnicodeDecodeError as e:
        raise ReferenceUnresolved(f"{ref}: not text ({e.reason})") from e


def _path_of(ref: str) -> str:
    match = _FILE.match(ref)
    if match is None:
        raise ReferenceUnresolved(f"{ref!r} is not a repository reference (repo:file:<path>@…)")
    return match["path"]


class RepositoryReferenceResolver(ReferenceResolverPort):
    """Binds and reads a product file through the managed clone (``SourceRepositoryPort``), and
    answers from the Project registry whether a project has a repository to bind in at all."""

    family = REPOSITORY_FAMILY

    def __init__(self, repository: Any, projects: Any) -> None:
        self._repository = repository
        self._projects = projects

    async def binds_nothing_for(self, project_id: str) -> str | None:
        """SIP-0110 §5ac: a sample application has no repository, so no unit of it binds a
        repository reference. Read from the registry, never from whether a clone exists yet: a
        registered external Project that hasn't been validated has no clone, but a repository."""
        try:
            project = await self._projects.get_project(project_id)
        except ProjectNotFoundError:
            return f"no Project {project_id} is registered"
        if project.source is None:
            return "it is a sample application, with no source repository"
        return None

    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        path = _path_of(ref)
        if ctx.source_commit is None:
            # §B.5.1: never a default commit. A sample application has no source context, and a
            # Campaign has none of its own: each of its cycles binds at its own (SIP-0110 §5ad).
            raise ReferenceUnresolved(
                f"{ref}: {ctx.unit_kind} {ctx.unit_id} pins no source commit to bind it at"
            )
        commit = ctx.source_commit
        content = await self._file(ctx, commit, path)
        _text(ref, content)
        return BoundReference(f"repo:file:{path}@{commit}", commit, _digest(content))

    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        path = _path_of(bound.ref)
        content = await self._file(ctx, bound.revision, path)
        if _digest(content) != bound.digest:
            raise ReferenceUnresolved(
                f"{bound.ref}: the content at {bound.revision[:12]} no longer matches the digest "
                f"bound ({bound.digest})"
            )
        return _text(bound.ref, content)

    async def _file(self, ctx: BindingContext, commit: str, path: str) -> bytes:
        try:
            return await self._repository.file_at(ctx.project_id, commit, path)
        except SourceUnavailable as e:
            if e.reason not in _REFUSALS:
                raise
            raise ReferenceUnresolved(f"{path} at {commit[:12]}: {e}") from e
