"""Prefect task-scoped log forwarder (SIP-0087).

Bridges Python `logging` records into Prefect's ``POST /api/logs/`` endpoint so
the Prefect UI shows per-task log streams instead of "Waiting for logs...".

Design (matches the LangFuse adapter's buffered, best-effort pattern):
- Background asyncio task drains a bounded queue every ``flush_interval`` or
  when it hits ``batch_max_size``.
- On POST failure, the batch is dropped and a single WARN is emitted per outage
  window — producers never block on telemetry, and an outage cannot grow queue
  memory without bound.
- A ``PrefectLogHandler`` (``logging.Handler``) filters by logger-name prefix
  and minimum level before enqueueing, pulls ``flow_run_id`` / ``task_run_id``
  from a contextvar, and posts to the forwarder.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Correlation contextvar — carries Prefect run IDs for the current async task
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrefectRunIds:
    """Prefect flow/task run identifiers scoped to the current async context."""

    flow_run_id: str | None = None
    task_run_id: str | None = None


_EMPTY_IDS = PrefectRunIds()
_prefect_run_ids: ContextVar[PrefectRunIds | None] = ContextVar(
    "squadops_prefect_run_ids", default=None
)


def get_prefect_run_ids() -> PrefectRunIds:
    """Return the current context's Prefect run IDs (empty if unset)."""
    return _prefect_run_ids.get() or _EMPTY_IDS


@contextmanager
def prefect_run_context(*, flow_run_id: str | None = None, task_run_id: str | None = None):
    """Scope Prefect run IDs to a block of code.

    The handler pulls these from the contextvar at ``emit`` time, so any log
    emitted inside this ``with`` block (including from coroutines spawned via
    ``asyncio.create_task`` — contextvars copy at task creation) gets tagged
    with the matching ``flow_run_id`` / ``task_run_id``.
    """
    current = get_prefect_run_ids()
    merged = PrefectRunIds(
        flow_run_id=flow_run_id if flow_run_id is not None else current.flow_run_id,
        task_run_id=task_run_id if task_run_id is not None else current.task_run_id,
    )
    token = _prefect_run_ids.set(merged)
    try:
        yield merged
    finally:
        _prefect_run_ids.reset(token)


# ---------------------------------------------------------------------------
# Forwarder
# ---------------------------------------------------------------------------


@dataclass
class _LogBatchStats:
    dropped_on_overflow: int = 0
    dropped_on_failure: int = 0
    posted: int = 0


class PrefectLogForwarder:
    """Async batching client for Prefect's ``POST /api/logs/`` endpoint.

    Not thread-safe. Must be used from a single asyncio event loop.
    """

    def __init__(
        self,
        api_url: str,
        *,
        flush_interval: float = 1.0,
        batch_max_size: int = 50,
        queue_max_size: int = 2000,
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._flush_interval = flush_interval
        self._batch_max_size = batch_max_size
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_max_size)
        self._client = client if client is not None else httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._flush_task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._in_outage = False
        self._stats = _LogBatchStats()

    @property
    def stats(self) -> _LogBatchStats:
        return self._stats

    def start(self) -> None:
        """Start the background flush loop. Idempotent."""
        if self._flush_task is None or self._flush_task.done():
            self._stopping.clear()
            self._flush_task = asyncio.create_task(
                self._flush_loop(), name="prefect-log-forwarder-flush"
            )

    def enqueue(self, record: dict[str, Any]) -> None:
        """Put a log record dict on the queue. Non-blocking.

        If the queue is full we drop the record and increment a counter —
        better than blocking the producer (the whole point of this adapter
        is to stay off the critical path).
        """
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            self._stats.dropped_on_overflow += 1

    async def _drain_batch(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        while len(batch) < self._batch_max_size:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch

    async def _flush_once(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        try:
            resp = await self._client.post(f"{self._api_url}/logs/", json=batch)
            resp.raise_for_status()
            self._stats.posted += len(batch)
            if self._in_outage:
                logger.info("Prefect log forwarder recovered; resuming deliveries")
                self._in_outage = False
        except Exception as exc:
            self._stats.dropped_on_failure += len(batch)
            if not self._in_outage:
                logger.warning(
                    "Prefect log forwarder POST /logs failed (%s); dropping batch of %d "
                    "and suppressing further warnings until recovery",
                    exc.__class__.__name__,
                    len(batch),
                )
                self._in_outage = True

    async def _flush_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._flush_interval)
            except TimeoutError:
                pass
            batch = await self._drain_batch()
            await self._flush_once(batch)

    async def close(self, *, timeout: float = 2.0) -> None:
        """Stop the flush loop, drain remaining records, close the client."""
        self._stopping.set()
        if self._flush_task is not None:
            try:
                await asyncio.wait_for(self._flush_task, timeout=timeout)
            except (TimeoutError, asyncio.CancelledError):
                self._flush_task.cancel()
        # Final drain — best-effort.
        remaining = await self._drain_batch()
        if remaining:
            try:
                await asyncio.wait_for(self._flush_once(remaining), timeout=timeout)
            except TimeoutError:
                self._stats.dropped_on_failure += len(remaining)
        if self._owns_client:
            await self._client.aclose()


# ---------------------------------------------------------------------------
# Logging handler
# ---------------------------------------------------------------------------


@dataclass
class LogHandlerFilters:
    allowed_prefixes: tuple[str, ...] = ("squadops", "adapters")
    min_level: int = logging.INFO


class PrefectLogHandler(logging.Handler):
    """``logging.Handler`` that forwards records to a ``PrefectLogForwarder``.

    Filter order (cheapest first):
    1. ``record.levelno < min_level`` — drop.
    2. ``record.name`` doesn't start with any allowed prefix — drop.
    3. No ``flow_run_id`` and no ``task_run_id`` in context — drop (system log).
    4. Enqueue to forwarder.

    Per the SIP: enqueue is non-blocking and never raises; a broken forwarder
    degrades to ``handleError`` (silent by default in production).
    """

    def __init__(
        self,
        forwarder: PrefectLogForwarder,
        filters: LogHandlerFilters | None = None,
    ) -> None:
        super().__init__(level=(filters.min_level if filters else logging.INFO))
        self._forwarder = forwarder
        self._filters = filters or LogHandlerFilters()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < self._filters.min_level:
                return
            if not any(
                record.name == p or record.name.startswith(f"{p}.")
                for p in self._filters.allowed_prefixes
            ):
                return
            ids = get_prefect_run_ids()
            if ids.flow_run_id is None and ids.task_run_id is None:
                return
            payload: dict[str, Any] = {
                "name": record.name,
                "level": record.levelno,
                "message": self.format(record),
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            }
            if ids.flow_run_id is not None:
                payload["flow_run_id"] = ids.flow_run_id
            if ids.task_run_id is not None:
                payload["task_run_id"] = ids.task_run_id
            self._forwarder.enqueue(payload)
        except Exception:
            self.handleError(record)


__all__ = [
    "LogHandlerFilters",
    "PrefectLogForwarder",
    "PrefectLogHandler",
    "PrefectRunIds",
    "get_prefect_run_ids",
    "prefect_run_context",
]
