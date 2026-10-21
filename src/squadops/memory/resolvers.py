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
- admission names the failure in the reference's ``unbound``. A standalone cycle admitted while its
  family overruns keeps that reference unbound for its life, as it does for any other fault there.

**After an overrun, the family fails fast for one bound's length.** Its calls raise
``ResolverTimedOut`` at once, without calling it. A hung family is then one bound under the lock, not
one per pending launch, cycle fill or reconciliation (the second read of #2579).

**The bound frees the wait, not the thread.** The repository family runs git in
``asyncio.to_thread``, and that thread keeps going until git's own bound
(``ProjectsConfig.git_timeout_seconds``). Failing fast keeps the threads an overrunning family leaves
to about one per two bounds, a handful against git's 300 s (the G4's reading, acceptable for 2.4).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from typing import TypeVar

from squadops.memory.references import BindingContext, BoundReference
from squadops.ports.memory.references import ReferenceResolverPort

T = TypeVar("T")


class ResolverTimedOut(TimeoutError):
    """A resolver call that overran its bound, or was refused while its family fails fast: a
    fault, which its caller repeats or reports."""


class TimeBoundResolver(ReferenceResolverPort):
    """``inner``, with each of its calls bounded to ``seconds``, failing fast for ``seconds`` after
    an overrun. A ``TimeoutError`` the resolver raises itself passes through as its own; only the
    bound's expiry is ``ResolverTimedOut``."""

    def __init__(
        self,
        inner: ReferenceResolverPort,
        seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.family = inner.family
        self._inner = inner
        self._seconds = seconds
        self._clock = clock
        #: After an overrun, calls fail fast until this moment.
        self._failing_until = 0.0

    async def bind(self, ref: str, ctx: BindingContext) -> BoundReference:
        return await self._bounded("bind", lambda: self._inner.bind(ref, ctx))

    async def read(self, bound: BoundReference, ctx: BindingContext) -> str:
        return await self._bounded("read", lambda: self._inner.read(bound, ctx))

    async def binds_nothing_for(self, project_id: str) -> str | None:
        return await self._bounded(
            "binds_nothing_for", lambda: self._inner.binds_nothing_for(project_id)
        )

    async def _bounded(self, call: str, start: Callable[[], Awaitable[T]]) -> T:
        if self._clock() < self._failing_until:
            raise ResolverTimedOut(
                f"the {self.family} resolver overran its {self._seconds:g} s bound within the "
                f"last {self._seconds:g} s, so its {call} is refused until then"
            )
        bound = asyncio.timeout(self._seconds)
        try:
            async with bound:
                return await start()
        except TimeoutError as e:
            if not bound.expired():
                raise
            self._failing_until = self._clock() + self._seconds
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
