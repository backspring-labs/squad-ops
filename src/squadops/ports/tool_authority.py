"""The authority that governs a provider's operations (SIP-0116 §8, SIP-0117 R4.2, R4.6).

A skillset requests a tool; it grants nothing. Whether the request is within the authority that
already governs the operation is the provider's to say: its deny list, its argument and target
validation, its compatibility checks (for Studio, the product's eligibility rules). A provider
registers its authority at the composition root, keyed by its name, and cycle creation asks it
of every tool the cycle's work requires. A provider that registers none governs nothing, so its
tools are refused: carrying a skillset never authorizes an operation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from squadops.capabilities.skillsets import ToolRequest


@dataclass(frozen=True)
class BrokenRule:
    """A rule of the provider's authority a tool request breaks, and why."""

    rule: str
    why: str


@dataclass(frozen=True)
class ProductView:
    """The repository-backed product a cycle is created on, as its run is seeded with it (SIP-0116
    §17n, #3042): the tree at the cycle's pinned commit, read once through the checkout a run is
    seeded from, with the same filter and limits, and the footprint the cycle is held to.

    - ``paths``: every file the checkout seeds a run with.
    - ``text(path)``: a file's text, decoded only when asked, so an authority that reads paths
      alone decodes nothing.
    - ``footprint``: the paths and globs the cycle's ruled change request lets it touch, or
      ``None`` when the cycle holds no change request yet: an increment's proposal run authors
      it, so an increment's own cycle has none at creation. A repair or a retry carries the ruled
      one, and one that can't be read refuses creation rather than reading as ``None``.

    An authority asked about a cycle with no repository-backed product (a sample application) is
    given ``None`` for the view, never a view of nothing."""

    project_id: str
    commit: str
    paths: tuple[str, ...]
    footprint: tuple[str, ...] | None
    _read: Callable[[str], Awaitable[str]] = field(repr=False, compare=False)

    async def text(self, path: str) -> str:
        if path not in self.paths:
            raise KeyError(f"{path} is not in Project {self.project_id}'s tree at {self.commit}")
        return await self._read(path)


class ToolAuthorityPort(Protocol):
    """One provider's authority over the operations it runs."""

    async def broken_rules(
        self,
        tool: ToolRequest,
        *,
        project_id: str | None,
        config: Mapping[str, Any],
        product: ProductView | None,
    ) -> list[BrokenRule]:
        """Each rule ``tool`` breaks for a cycle of ``config`` on ``project_id``, or ``[]``.
        ``product`` is the repository-backed product the cycle runs on, or ``None`` when it runs
        on none (§17n)."""
        ...
