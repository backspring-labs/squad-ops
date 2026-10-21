"""The reference families a runtime binds with, each call under one time bound (#2575).

A resolver's ``bind`` runs under the campaign launcher's single lock: at a campaign cycle's launch, in
the fill before its first run, and for a campaign's re-binding (SIP-0110 §5ae). Its ``read`` runs at
dispatch. The port states no time bound, so one family that hangs would stall every campaign. The
bound is applied once, where a family is registered: no caller adds its own, and none can register a
family without it.

**An overrun is a fault, never a refusal** (#2575's G4, the MacBook lane). A refusal
(``ReferenceUnresolved``) says the reference doesn't bind; a timeout says nothing about that. So each
call site's rule for a fault holds:
- a campaign cycle's launch repeats on the next drain;
- a re-binding is refused with ``503 CYCLES_UNBOUND``, its snapshot unchanged;
- a task instruction's write is answered as a fault;
- admission names the failure in the reference's ``unbound``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterator, Mapping
from typing import TypeVar

from squadops.memory.references import BindingContext, BoundReference
from squadops.ports.memory.references import ReferenceResolverPort

T = TypeVar("T")


class ResolverTimedOut(TimeoutError):
    """A resolver call that overran its bound: a fault, which its caller repeats or reports."""


class TimeBoundResolver(ReferenceResolverPort):
    """``inner``, with each of its calls bounded to ``seconds``. A ``TimeoutError`` the resolver
    raises itself passes through as its own; only the bound's expiry is ``ResolverTimedOut``."""

    def __init__(self, inner: ReferenceResolverPort, seconds: float) -> None:
        self.family = inner.family
        self._inner = inner
        self._seconds = seconds

    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        return await self._bounded("bind", self._inner.bind(ref, ctx))

    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        return await self._bounded("read", self._inner.read(bound, ctx))

    async def binds_nothing_for(self, project_id: str) -> str | None:
        return await self._bounded("binds_nothing_for", self._inner.binds_nothing_for(project_id))

    async def _bounded(self, call: str, awaitable: Awaitable[T]) -> T:
        bound = asyncio.timeout(self._seconds)
        try:
            async with bound:
                return await awaitable
        except TimeoutError as e:
            if not bound.expired():
                raise
            raise ResolverTimedOut(
                f"the {self.family} resolver's {call} overran its {self._seconds:g} s bound"
            ) from e


class ReferenceResolvers(Mapping[str, ReferenceResolverPort]):
    """The runtime's resolvers, by family. Read as the mapping every binder takes, and filled only
    through ``register``, which puts each family under the bound. It takes no item assignment, so a
    family can't be registered without its bound."""

    def __init__(self, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError(f"a resolver's time bound must be positive, not {timeout_seconds}")
        self._seconds = timeout_seconds
        self._families: dict[str, ReferenceResolverPort] = {}

    def register(self, resolver: ReferenceResolverPort) -> None:
        if resolver.family in self._families:
            raise ValueError(f"the {resolver.family} family has a resolver registered already")
        self._families[resolver.family] = TimeBoundResolver(resolver, self._seconds)

    def __getitem__(self, family: str) -> ReferenceResolverPort:
        return self._families[family]

    def __iter__(self) -> Iterator[str]:
        return iter(self._families)

    def __len__(self) -> int:
        return len(self._families)
