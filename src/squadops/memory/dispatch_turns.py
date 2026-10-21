"""A unit's dispatches, ordered against what changes their binding (#2545; SIP-0110 §5v, §5w).

A dispatch reads what it is handed, then discloses it as its exposure. A re-binding, or a task
instruction added after admission, reads the exposures to see whether a dispatch was handed what it
changes, then writes. Each check holds only if nothing composes in between: a dispatch that read the
binding before the write and disclosed after the check is handed what the check said no dispatch
had, and the change goes forward over it.

So both take the unit's turn: a dispatch from its read to its disclosure, and a change from its
check to its write. One unit's turn never waits on another's.

The turns are this process's. The runtime API composes every dispatch and serves every change, and
its image runs one server process (``test_dispatch_turns.py`` guards the command). A second process
would need the store to order them instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from squadops.memory.recall import UnitKind

#: How long a dispatch or a change waits for its unit's turn. A change holds it through its reference
#: bindings, each bounded by its resolver, so a turn held longer than this is one never given back.
TURN_WAIT_SECONDS = 300.0


class DispatchTurnUnavailable(RuntimeError):
    """The unit's turn wasn't given within ``TURN_WAIT_SECONDS``: nothing was read or written."""


class DispatchTurns:
    """Each unit's turn, made when first asked for and dropped when no one holds or awaits it."""

    def __init__(self, *, wait_seconds: float = TURN_WAIT_SECONDS) -> None:
        self._wait_seconds = wait_seconds
        self._turns: dict[tuple[UnitKind, str], asyncio.Lock] = {}
        self._wanted: dict[tuple[UnitKind, str], int] = {}

    @asynccontextmanager
    async def held(self, unit_kind: UnitKind, unit_id: str) -> AsyncIterator[None]:
        key = (UnitKind(unit_kind), unit_id)
        turn = self._turns.get(key)
        if turn is None:
            turn = self._turns[key] = asyncio.Lock()
        self._wanted[key] = self._wanted.get(key, 0) + 1
        try:
            try:
                await asyncio.wait_for(turn.acquire(), self._wait_seconds)
            except TimeoutError:
                raise DispatchTurnUnavailable(
                    f"{key[0].value} {unit_id}'s dispatch turn wasn't given within "
                    f"{self._wait_seconds:.0f}s"
                ) from None
            try:
                yield
            finally:
                turn.release()
        finally:
            self._wanted[key] -= 1
            if not self._wanted[key]:
                del self._wanted[key], self._turns[key]

    def __len__(self) -> int:
        """The units with a turn held or awaited."""
        return len(self._turns)
