"""The repository family's reference resolver (SIP-0112 §8.2 contract 6, §B.5.1; E.4.4): the
T16 port, over the managed clone's.

SIP-0110 binds an instruction's ``@current`` references when the instruction is bound to a unit,
through one resolver per family (``squadops.ports.memory.references``, #2179 T16). This is the
repository family's. ``repo:file:<path>@current`` binds to ``repo:file:<path>@<commit>``, at the
commit the unit's source context pins, never at the branch's head. That way a unit's instructions
and the commands they describe come from the same commit. The content's digest is recorded with the
binding, and a read at the bound commit whose content no longer matches it is refused.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

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


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _path_of(ref: str) -> str:
    match = _FILE.match(ref)
    if match is None:
        raise ReferenceUnresolved(f"{ref!r} is not a repository reference (repo:file:<path>@…)")
    return match["path"]


class RepositoryReferenceResolver(ReferenceResolverPort):
    """Binds and reads a product file through the managed clone (``SourceRepositoryPort``)."""

    family = REPOSITORY_FAMILY

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        path = _path_of(ref)
        if ctx.source_commit is None:
            # §B.5.1: never a default commit. A sample application has no source context, and a
            # Campaign has none of its own (the open conflict §B.5.1 names).
            raise ReferenceUnresolved(
                f"{ref}: {ctx.unit_kind} {ctx.unit_id} pins no source commit to bind it at"
            )
        commit = ctx.source_commit
        content = await self._file(ctx, commit, path)
        return BoundReference(f"repo:file:{path}@{commit}", commit, _digest(content))

    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        path = _path_of(bound.ref)
        content = await self._file(ctx, bound.revision, path)
        if _digest(content) != bound.digest:
            raise ReferenceUnresolved(
                f"{bound.ref}: the content at {bound.revision[:12]} no longer matches the digest "
                f"bound ({bound.digest})"
            )
        try:
            return content.decode()
        except UnicodeDecodeError as e:
            raise ReferenceUnresolved(f"{bound.ref}: not text ({e.reason})") from e

    async def _file(self, ctx: BindingContext, commit: str, path: str) -> bytes:
        try:
            return await self._repository.file_at(ctx.project_id, commit, path)
        except SourceUnavailable as e:
            raise ReferenceUnresolved(f"{path} at {commit[:12]}: {e}") from e
