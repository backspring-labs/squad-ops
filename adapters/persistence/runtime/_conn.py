"""
Shared connection helper for the runtime persistence adapters (SIP-0089 §4.5/D25).

A runtime port method either runs inside a caller-supplied unit-of-work
connection — the ``conn=`` the coordinator threads from
:meth:`RuntimeTransactionPort.begin` so several writes commit atomically — or, when
none is given, acquires its own connection from the pool. This helper centralizes
that either/or so every adapter stays backward-compatible when not part of a
transaction and never opens its own (auto-committing) connection over a
caller's open transaction.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import asyncpg


@asynccontextmanager
async def acquire(pool: asyncpg.Pool, conn: Any | None) -> AsyncIterator[Any]:
    """Yield ``conn`` if the caller supplied one (UoW-shared), else one from ``pool``.

    A supplied ``conn`` is *not* closed here — the unit of work that opened it
    owns its lifecycle (commit/abort). A pool-acquired connection is released on
    exit as usual.
    """
    if conn is not None:
        yield conn
    else:
        async with pool.acquire() as owned:
            yield owned
