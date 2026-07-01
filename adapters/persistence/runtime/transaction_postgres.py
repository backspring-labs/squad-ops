"""
Asyncpg RuntimeTransaction adapter (SIP-0089 §4.5/D25).

Implements :class:`RuntimeTransactionPort` over the same asyncpg pool the other
runtime adapters share. ``begin()`` acquires a connection and opens a
``conn.transaction()`` block, yielding the connection as the opaque unit-of-work
handle. Because every participating adapter runs its statement on that same
connection (via ``conn=``), the writes share one transaction: normal exit
commits, an exception aborts and rolls them all back.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from squadops.ports.runtime.transaction import RuntimeTransactionPort

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import asyncpg


class PostgresRuntimeTransaction(RuntimeTransactionPort):
    """Postgres-backed unit of work over the shared asyncpg pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[asyncpg.Connection]:
        async with self._pool.acquire() as conn, conn.transaction():
            yield conn
