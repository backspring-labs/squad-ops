"""Retry on a transient database error (#1976): work Postgres rolled back, or a connection that was
never made. The retry lives inside the adapter, so its callers never see one.

It happens in two places, because they differ in what is safe to run again:
- **Taking a connection** (``acquire``): a connection that could not be made, or taken from the
  pool, ran nothing, so taking it is tried again.
- **A transaction** (``transaction``): Postgres rolls a serialization failure or a deadlock back
  whole (SQLSTATE 40001, 40P01), so the transaction runs again from its first statement.

What is never retried:
- **A connection lost after a statement was sent,** because a write may have committed and running
  it again could apply it twice.
- **A whole method,** because one that wrote and then failed reading back would write again.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Taking a connection failed before anything ran on it: refused or unreachable (``OSError``), the
#: server starting or stopping (57P03), or out of connections (53300).
CONNECT_FAILURES: tuple[type[BaseException], ...] = (
    OSError,
    asyncpg.CannotConnectNowError,
    asyncpg.TooManyConnectionsError,
    asyncpg.ConnectionFailureError,
)

#: Postgres rolled the transaction back whole.
ROLLED_BACK: tuple[type[BaseException], ...] = (
    asyncpg.SerializationError,
    asyncpg.DeadlockDetectedError,
)


@dataclass(frozen=True)
class TransientRetry:
    """How often a transient failure is tried (``attempts``, the first included), and the first
    pause between tries, which doubles each time (``backoff_seconds``)."""

    attempts: int
    backoff_seconds: float

    @classmethod
    def of(cls, config: Any) -> TransientRetry:
        """From a ``db.retry`` config section (``squadops.config.schema.DBRetryConfig``): the one
        way a policy is built, so its defaults live in the config alone."""
        return cls(config.attempts, config.backoff_seconds)

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError(f"attempts must be at least 1, got {self.attempts}")
        if self.backoff_seconds < 0:
            raise ValueError(f"backoff_seconds must not be negative, got {self.backoff_seconds}")

    async def _pause(self, attempt: int, error: BaseException, where: str) -> None:
        logger.warning(
            "db_transient_retry",
            extra={"where": where, "attempt": attempt, "error": type(error).__name__},
        )
        await asyncio.sleep(self.backoff_seconds * 2 ** (attempt - 1))

    @contextlib.asynccontextmanager
    async def acquire(self, pool: Any) -> AsyncIterator[Any]:
        """A connection from ``pool``, taking it again when it could not be made."""
        async with contextlib.AsyncExitStack() as stack:
            for attempt in range(1, self.attempts + 1):
                try:
                    conn = await stack.enter_async_context(pool.acquire())
                    break
                except CONNECT_FAILURES as error:
                    if attempt == self.attempts:
                        raise
                    await self._pause(attempt, error, "acquire")
            yield conn

    async def transaction(
        self,
        pool: Any,
        work: Callable[[Any], Awaitable[T]],
        *,
        isolation: str | None = None,
        lost_race: tuple[type[BaseException], ...] = (),
    ) -> T:
        """``work(conn)`` inside one transaction, run again from its start when Postgres rolled it
        back. ``work`` must do nothing outside the connection it is handed. ``lost_race`` names the
        caller's own errors that mean the same: the transaction lost a race and rolled back, so
        running it again on a fresh snapshot can succeed."""
        options = {"isolation": isolation} if isolation else {}
        retried = ROLLED_BACK + lost_race
        for attempt in range(1, self.attempts + 1):
            try:
                async with self.acquire(pool) as conn, conn.transaction(**options):
                    return await work(conn)
            except retried as error:
                if attempt == self.attempts:
                    raise
                await self._pause(attempt, error, "transaction")
        raise AssertionError("unreachable: the last attempt returns or raises")
