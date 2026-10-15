"""Retry on a transient database error (#1976): what is run again, and what never is.

What bugs would these catch? A transaction Postgres rolled back left failed when running it again
would have succeeded; a retry that never ends; and the dangerous one, a statement re-sent after
its connection was lost, when the write may already have committed.
"""

from __future__ import annotations

import asyncpg
import pytest

from adapters.persistence.transient import TransientRetry

NO_PAUSE = TransientRetry(attempts=3, backoff_seconds=0.0)


class _Transaction:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    async def __aenter__(self) -> None:
        self._conn.transactions += 1

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _Conn:
    def __init__(self) -> None:
        self.transactions = 0

    def transaction(self, **_options: object) -> _Transaction:
        return _Transaction(self)


class _Acquire:
    def __init__(self, pool: _Pool) -> None:
        self._pool = pool

    async def __aenter__(self) -> _Conn:
        self._pool.takes += 1
        if self._pool.refusals:
            raise self._pool.refusals.pop(0)
        return self._pool.conn

    async def __aexit__(self, *exc: object) -> bool:
        self._pool.released += 1
        return False


class _Pool:
    """asyncpg's shape: ``acquire()`` is an async context manager, not a coroutine."""

    def __init__(self, *refusals: BaseException) -> None:
        self.conn = _Conn()
        self.refusals = list(refusals)
        self.takes = 0
        self.released = 0

    def acquire(self) -> _Acquire:
        return _Acquire(self)


def _failing(*errors: BaseException, then: object = "done"):
    calls: list[int] = []

    async def work(conn: _Conn) -> object:
        calls.append(conn.transactions)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return then

    return work, calls


@pytest.mark.parametrize(
    "error",
    [asyncpg.SerializationError("40001"), asyncpg.DeadlockDetectedError("40P01")],
    ids=["serialization", "deadlock"],
)
async def test_a_transaction_postgres_rolled_back_runs_again_from_its_start(error):
    pool = _Pool()
    work, calls = _failing(error)

    assert await NO_PAUSE.transaction(pool, work) == "done"
    # Each try ran in its own transaction, on a connection taken and returned each time.
    assert (calls, pool.takes, pool.released) == ([1, 2], 2, 2)


async def test_a_rollback_on_every_try_raises_the_last_and_stops():
    work, calls = _failing(*(asyncpg.SerializationError(f"try {n}") for n in (1, 2, 3, 4)))

    with pytest.raises(asyncpg.SerializationError, match="try 3"):
        await NO_PAUSE.transaction(_Pool(), work)
    assert len(calls) == 3


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.ConnectionDoesNotExistError("connection was closed in the middle of operation"),
        asyncpg.UniqueViolationError("23505"),
        OSError("connection reset"),
    ],
    ids=["lost-mid-statement", "not-transient", "os-error-after-taking"],
)
async def test_an_error_after_the_connection_was_taken_is_never_retried(error):
    """A lost connection may have committed the write; a constraint is not transient. Neither is
    run again, even an ``OSError``, which is retried only when taking the connection."""
    pool = _Pool()
    work, calls = _failing(error)

    with pytest.raises(type(error)):
        await NO_PAUSE.transaction(pool, work)
    assert (len(calls), pool.takes) == (1, 1)


async def test_a_connection_that_could_not_be_made_is_taken_again_and_nothing_ran_twice():
    pool = _Pool(ConnectionRefusedError("refused"), asyncpg.CannotConnectNowError("57P03"))
    work, calls = _failing()

    assert await NO_PAUSE.transaction(pool, work) == "done"
    assert (pool.takes, len(calls), pool.released) == (3, 1, 1)


async def test_a_connection_never_made_raises_once_the_tries_are_spent():
    pool = _Pool(*(asyncpg.TooManyConnectionsError("53300") for _ in range(3)))

    with pytest.raises(asyncpg.TooManyConnectionsError):
        async with NO_PAUSE.acquire(pool):
            pytest.fail("no connection was made")
    assert pool.takes == 3


@pytest.mark.parametrize(
    ("attempts", "backoff"), [(0, 0.0), (3, -0.1)], ids=["no-attempts", "negative-pause"]
)
def test_a_retry_that_could_never_run_or_would_not_wait_is_refused(attempts, backoff):
    with pytest.raises(ValueError):
        TransientRetry(attempts=attempts, backoff_seconds=backoff)


def test_the_registry_factory_builds_the_retry_from_the_config_and_requires_it():
    """#1976, wiring: the runtime API hands the factory its ``db.retry`` section. Bugs caught: the
    configured attempts and pause dropped for a hardcoded policy, or a Postgres registry built with
    no retry at all."""
    from unittest.mock import MagicMock

    from adapters.cycles.factory import create_cycle_registry
    from squadops.config.schema import DBRetryConfig

    registry = create_cycle_registry(
        "postgres", pool=MagicMock(), retry=DBRetryConfig(attempts=4, backoff_seconds=0.2)
    )

    assert registry._retry == TransientRetry(attempts=4, backoff_seconds=0.2)
    with pytest.raises(ValueError, match="retry is required"):
        create_cycle_registry("postgres", pool=MagicMock())
