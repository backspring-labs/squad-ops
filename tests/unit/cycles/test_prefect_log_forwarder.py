"""Tests for adapters.cycles.prefect_log_forwarder (SIP-0087).

Covers:
- ``PrefectLogForwarder`` batching, queue-overflow drops, POST-failure drops,
  outage-recovery WARN suppression, and ``close()`` flush-on-shutdown.
- ``PrefectLogHandler`` level + logger-prefix filters, context-miss drops,
  payload shape for flow-only and task-scoped records. The handler reads
  flow_run_id / task_run_id off the shared CorrelationContext contextvar
  (``squadops.telemetry.context.use_run_ids``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from adapters.cycles.prefect_log_forwarder import (
    LogHandlerFilters,
    PrefectLogForwarder,
    PrefectLogHandler,
)
from squadops.telemetry.context import use_correlation_context, use_run_ids
from squadops.telemetry.models import CorrelationContext

pytestmark = [pytest.mark.domain_orchestration]

PREFECT_URL = "http://prefect-server:4200/api"


def _ok_response() -> httpx.Response:
    return httpx.Response(
        status_code=201,
        json={},
        request=httpx.Request("POST", f"{PREFECT_URL}/logs/"),
    )


def _build_forwarder(
    *,
    flush_interval: float = 0.01,
    batch_max_size: int = 50,
    queue_max_size: int = 1000,
    client: httpx.AsyncClient | None = None,
) -> PrefectLogForwarder:
    return PrefectLogForwarder(
        api_url=PREFECT_URL,
        flush_interval=flush_interval,
        batch_max_size=batch_max_size,
        queue_max_size=queue_max_size,
        client=client or AsyncMock(spec=httpx.AsyncClient),
    )


# ---------------------------------------------------------------------------
# PrefectLogForwarder
# ---------------------------------------------------------------------------


class TestForwarderBatching:
    async def test_batches_and_posts(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_ok_response())
        fw = _build_forwarder(client=client, flush_interval=0.02)
        fw.start()
        try:
            for i in range(5):
                fw.enqueue({"name": "squadops.x", "level": 20, "message": f"m{i}"})
            # Give the flush loop a tick.
            await asyncio.sleep(0.1)
        finally:
            await fw.close(timeout=0.5)

        assert client.post.await_count >= 1
        posted_batches = [call.kwargs["json"] for call in client.post.await_args_list]
        flat = [r for batch in posted_batches for r in batch]
        messages = [r["message"] for r in flat]
        assert set(messages) == {f"m{i}" for i in range(5)}
        # All 5 records posted exactly once.
        assert fw.stats.posted == 5
        assert fw.stats.dropped_on_failure == 0
        assert fw.stats.dropped_on_overflow == 0

    async def test_flushes_remaining_on_close(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_ok_response())
        # Use a long interval so close() is what drives the final flush.
        fw = _build_forwarder(client=client, flush_interval=60.0)
        fw.start()
        fw.enqueue({"name": "squadops.a", "level": 20, "message": "last"})
        await fw.close(timeout=0.5)
        assert fw.stats.posted == 1
        # Final batch was the one posted.
        last_call = client.post.await_args_list[-1]
        assert last_call.kwargs["json"][0]["message"] == "last"

    async def test_batch_max_size_caps_per_request(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_ok_response())
        fw = _build_forwarder(client=client, flush_interval=0.02, batch_max_size=3)
        fw.start()
        try:
            for i in range(7):
                fw.enqueue({"name": "squadops.x", "level": 20, "message": f"m{i}"})
            await asyncio.sleep(0.15)
        finally:
            await fw.close(timeout=0.5)
        for call in client.post.await_args_list:
            assert len(call.kwargs["json"]) <= 3
        assert fw.stats.posted == 7


class TestForwarderBackpressure:
    async def test_overflow_drops_record_without_blocking(self):
        # Queue size 2; flush loop never runs (forwarder not started).
        fw = _build_forwarder(queue_max_size=2)
        fw.enqueue({"name": "squadops.x", "level": 20, "message": "a"})
        fw.enqueue({"name": "squadops.x", "level": 20, "message": "b"})
        fw.enqueue({"name": "squadops.x", "level": 20, "message": "c"})  # dropped
        fw.enqueue({"name": "squadops.x", "level": 20, "message": "d"})  # dropped
        assert fw.stats.dropped_on_overflow == 2


class TestForwarderFailureHandling:
    async def test_post_failure_drops_batch_and_warns_once(self, caplog):
        caplog.set_level(logging.WARNING, logger="adapters.cycles.prefect_log_forwarder")
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        fw = _build_forwarder(client=client, flush_interval=0.01)
        fw.start()
        try:
            for i in range(3):
                fw.enqueue({"name": "squadops.x", "level": 20, "message": f"m{i}"})
            await asyncio.sleep(0.1)
            # Second wave during the same outage — still only one WARN.
            for i in range(3):
                fw.enqueue({"name": "squadops.x", "level": 20, "message": f"n{i}"})
            await asyncio.sleep(0.1)
        finally:
            await fw.close(timeout=0.5)
        assert fw.stats.posted == 0
        assert fw.stats.dropped_on_failure >= 6
        warn_lines = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warn_lines) == 1, f"expected one WARN, got {len(warn_lines)}"
        assert "POST /logs failed" in warn_lines[0].message

    async def test_recovery_after_failure_logs_info(self, caplog):
        caplog.set_level(logging.INFO, logger="adapters.cycles.prefect_log_forwarder")
        responses: list[Any] = [httpx.ConnectError("boom"), _ok_response()]

        async def fake_post(*args, **kwargs):
            nxt = responses.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(side_effect=fake_post)
        fw = _build_forwarder(client=client, flush_interval=0.01)
        fw.start()
        try:
            fw.enqueue({"name": "squadops.x", "level": 20, "message": "pre"})
            await asyncio.sleep(0.1)
            fw.enqueue({"name": "squadops.x", "level": 20, "message": "post"})
            await asyncio.sleep(0.1)
        finally:
            await fw.close(timeout=0.5)
        messages = [r.message for r in caplog.records]
        assert any("recovered" in m for m in messages)


# ---------------------------------------------------------------------------
# PrefectLogHandler
# ---------------------------------------------------------------------------


def _make_record(
    *,
    name: str = "squadops.agents.base",
    level: int = logging.INFO,
    msg: str = "hello",
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=10,
        msg=msg,
        args=None,
        exc_info=None,
    )


class _StubForwarder:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def enqueue(self, record: dict[str, Any]) -> None:
        self.records.append(record)


@pytest.fixture
def active_ctx():
    """Enter a CorrelationContext so ``use_run_ids`` can overlay onto it.

    The handler only reads flow/task IDs off the context; the outer cycle_id
    is irrelevant to what lands in Prefect, but it must be present since
    ``use_run_ids`` now requires an active context.
    """
    with use_correlation_context(CorrelationContext(cycle_id="c-test")):
        yield


class TestHandlerFiltering:
    def test_drops_below_min_level(self, active_ctx):
        fw = _StubForwarder()
        h = PrefectLogHandler(fw, LogHandlerFilters(min_level=logging.INFO))
        with use_run_ids(flow_run_id="f", task_run_id="t"):
            h.emit(_make_record(level=logging.DEBUG))
        assert fw.records == []

    def test_drops_disallowed_logger_prefix(self, active_ctx):
        fw = _StubForwarder()
        h = PrefectLogHandler(fw, LogHandlerFilters(allowed_prefixes=("squadops",)))
        with use_run_ids(flow_run_id="f", task_run_id="t"):
            h.emit(_make_record(name="httpx._client"))
        assert fw.records == []

    def test_prefix_match_does_not_match_false_sibling(self, active_ctx):
        # "squadops_other.x" must not match allowed prefix "squadops".
        fw = _StubForwarder()
        h = PrefectLogHandler(fw, LogHandlerFilters(allowed_prefixes=("squadops",)))
        with use_run_ids(flow_run_id="f", task_run_id="t"):
            h.emit(_make_record(name="squadops_other.x"))
        assert fw.records == []

    def test_drops_when_no_context(self):
        fw = _StubForwarder()
        h = PrefectLogHandler(fw)
        h.emit(_make_record())
        assert fw.records == []

    def test_drops_when_context_has_no_run_ids(self):
        # Context is active but no flow/task IDs overlaid — system log, not
        # task-scoped. Must not leak to Prefect.
        fw = _StubForwarder()
        h = PrefectLogHandler(fw)
        with use_correlation_context(CorrelationContext(cycle_id="c-1")):
            h.emit(_make_record())
        assert fw.records == []


class TestHandlerPayload:
    def test_task_scoped_record_shape(self, active_ctx):
        fw = _StubForwarder()
        h = PrefectLogHandler(fw)
        with use_run_ids(flow_run_id="flow-1", task_run_id="task-1"):
            h.emit(_make_record(msg="running"))
        assert len(fw.records) == 1
        rec = fw.records[0]
        assert rec["message"] == "running"
        assert rec["name"] == "squadops.agents.base"
        assert rec["level"] == logging.INFO
        assert rec["flow_run_id"] == "flow-1"
        assert rec["task_run_id"] == "task-1"
        # Timestamp is parseable ISO-8601.
        from datetime import datetime as _dt

        _dt.fromisoformat(rec["timestamp"])

    def test_flow_only_record_omits_task_run_id(self, active_ctx):
        fw = _StubForwarder()
        h = PrefectLogHandler(fw)
        with use_run_ids(flow_run_id="flow-1"):
            h.emit(_make_record(msg="orchestrator"))
        assert len(fw.records) == 1
        assert fw.records[0]["flow_run_id"] == "flow-1"
        assert "task_run_id" not in fw.records[0]

    def test_adapters_prefix_accepted(self, active_ctx):
        fw = _StubForwarder()
        h = PrefectLogHandler(fw)
        with use_run_ids(task_run_id="t"):
            h.emit(_make_record(name="adapters.llm.ollama"))
        assert len(fw.records) == 1
        assert fw.records[0]["name"] == "adapters.llm.ollama"

    def test_exception_record_includes_traceback(self, active_ctx):
        """``logger.exception(...)`` records must serialize their stack trace
        into ``payload.message`` — otherwise operators see the error text but
        no frames."""
        fw = _StubForwarder()
        h = PrefectLogHandler(fw)
        try:
            raise ValueError("kaboom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="squadops.agents.base",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="handler blew up",
            args=None,
            exc_info=exc_info,
        )
        with use_run_ids(task_run_id="t"):
            h.emit(record)
        assert len(fw.records) == 1
        message = fw.records[0]["message"]
        assert "handler blew up" in message
        assert "ValueError: kaboom" in message
        assert "Traceback" in message


class _BrokenForwarder:
    """Raises on every enqueue — proves handler isolation from forwarder bugs."""

    def enqueue(self, record: dict[str, Any]) -> None:
        raise RuntimeError("forwarder is broken")


class TestHandlerRobustness:
    def test_broken_forwarder_does_not_propagate_exception(self, active_ctx, capsys):
        # A broken enqueue must not raise out of ``emit``; logging.Handler
        # routes it to ``handleError`` which prints to stderr but keeps the
        # producer alive.
        h = PrefectLogHandler(_BrokenForwarder())
        with use_run_ids(task_run_id="t"):
            # Should not raise.
            h.emit(_make_record(msg="still going"))


class TestForwarderThreadSafety:
    async def test_enqueue_from_non_loop_thread_is_safe(self):
        """The LangFuse adapter logs from a background ``threading.Thread``;
        those records pass our prefix filter and end up in ``enqueue`` off
        the loop thread. This test exercises that path to catch races /
        crashes — it asserts all records land and none are dropped."""
        import threading

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=_ok_response())
        fw = _build_forwarder(client=client, flush_interval=0.02)
        fw.start()

        def worker(idx: int) -> None:
            for i in range(20):
                fw.enqueue({"name": "adapters.x", "level": 20, "message": f"w{idx}-{i}"})

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=2.0)
            # Let the flush loop catch up.
            await asyncio.sleep(0.15)
        finally:
            await fw.close(timeout=0.5)

        assert fw.stats.posted == 80
        assert fw.stats.dropped_on_overflow == 0
        assert fw.stats.dropped_on_failure == 0
