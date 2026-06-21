"""Unit tests for RabbitMQAdapter cache-recovery and consume_blocking.

Targets the stale-Queue-cache and consumer-tag-churn bugs that caused
``cycle_results_*`` replies to be lost during long waits (see fix branch
``fix/cycle-results-channel-recovery``). Uses MagicMock-backed channels so
no broker is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.comms.rabbitmq import QueueError, RabbitMQAdapter
from squadops.ports.comms.queue import REPLY_QUEUE_DECLARE_ARGS

pytestmark = [pytest.mark.unit]


def _make_adapter_with_channel(channel_obj) -> RabbitMQAdapter:
    """Build an adapter with pre-wired connection/channel mocks."""
    adapter = RabbitMQAdapter(url="amqp://test", namespace=None)
    conn = MagicMock()
    conn.is_closed = False
    adapter._connection = conn
    adapter._channel = channel_obj
    return adapter


class TestQueueCacheInvalidation:
    """Cached Queue handles are bound to a channel; if the channel is
    swapped (RobustChannel reconnect) the cache must re-declare."""

    async def test_get_queue_redeclares_when_channel_changes(self) -> None:
        """Regression: a cached Queue tied to a closed channel produced
        ``Channel was not opened`` even after RobustChannel reconnected.
        ``_get_queue`` must detect the channel swap and re-declare."""
        ch1 = MagicMock()
        ch1.is_closed = False
        old_queue = MagicMock()
        old_queue.channel = ch1
        ch1.declare_queue = AsyncMock(return_value=old_queue)

        adapter = _make_adapter_with_channel(ch1)
        first = await adapter._get_queue("cycle_results_run_x")
        assert first is old_queue
        ch1.declare_queue.assert_awaited_once()

        # Simulate RobustChannel reconnect: the adapter now holds a fresh
        # channel object. The cached queue is bound to the old one.
        ch2 = MagicMock()
        ch2.is_closed = False
        new_queue = MagicMock()
        new_queue.channel = ch2
        ch2.declare_queue = AsyncMock(return_value=new_queue)
        adapter._channel = ch2

        second = await adapter._get_queue("cycle_results_run_x")

        assert second is new_queue
        ch2.declare_queue.assert_awaited_once_with("cycle_results_run_x", durable=True)

    async def test_invalidate_queue_drops_cached_handle(self) -> None:
        """``invalidate_queue`` must remove the cached Queue so the next
        ``_get_queue`` call re-declares — the recovery hook used by long-
        running poll loops after a transient channel error."""
        ch = MagicMock()
        ch.is_closed = False
        original = MagicMock()
        original.channel = ch
        replacement = MagicMock()
        replacement.channel = ch
        ch.declare_queue = AsyncMock(side_effect=[original, replacement])

        adapter = _make_adapter_with_channel(ch)
        first = await adapter._get_queue("reply_q")
        assert first is original

        await adapter.invalidate_queue("reply_q")

        # After invalidation, next call must re-declare and return the new handle.
        second = await adapter._get_queue("reply_q")
        assert second is replacement
        assert ch.declare_queue.await_count == 2

    async def test_invalidate_queue_unknown_name_is_noop(self) -> None:
        """Invalidating a queue that was never cached must not raise — recovery
        paths can call this defensively."""
        ch = MagicMock()
        ch.is_closed = False
        adapter = _make_adapter_with_channel(ch)

        # Must not raise, even though no cache entry exists.
        await adapter.invalidate_queue("never_cached")
        assert "never_cached" not in adapter._queues


class TestEnsureQueue:
    """``ensure_queue`` eagerly declares a queue the adapter would otherwise
    only create lazily on first consume — needed for ``{agent_id}_results``
    reply queues, which agents publish to but never consume from (SIP-0094)."""

    async def test_declares_with_shared_args(self) -> None:
        """``ensure_queue`` declares the named queue using the single-sourced
        ``REPLY_QUEUE_DECLARE_ARGS`` — not a hardcoded arg set that could drift
        and trip a durable-queue ``PRECONDITION_FAILED`` redeclare."""
        ch = MagicMock()
        ch.is_closed = False
        declared = MagicMock()
        declared.channel = ch
        ch.declare_queue = AsyncMock(return_value=declared)

        adapter = _make_adapter_with_channel(ch)
        await adapter.ensure_queue("neo_results")

        ch.declare_queue.assert_awaited_once_with("neo_results", **REPLY_QUEUE_DECLARE_ARGS)

    async def test_results_and_comms_declare_with_identical_args(self) -> None:
        """D3 single-source invariant: the reply queue and the comms queue must
        be declared with byte-identical args. A drift between the two paths is
        exactly what causes the broker to reject a durable redeclare."""
        ch = MagicMock()
        ch.is_closed = False

        def _fresh_queue(name, **_kw):
            q = MagicMock()
            q.channel = ch
            q.name = name
            return q

        ch.declare_queue = AsyncMock(side_effect=_fresh_queue)

        adapter = _make_adapter_with_channel(ch)
        await adapter.ensure_queue("neo_results")  # reply queue path
        await adapter._get_queue("neo_comms")  # comms queue path

        results_call, comms_call = ch.declare_queue.await_args_list
        assert results_call.args == ("neo_results",)
        assert comms_call.args == ("neo_comms",)
        assert results_call.kwargs == comms_call.kwargs == REPLY_QUEUE_DECLARE_ARGS

    async def test_redeclares_after_channel_swap(self) -> None:
        """Edge: after a RobustChannel reconnect the reply queue is cached on a
        dead channel. ``ensure_queue`` must re-declare on the live channel — the
        stale-handle failure class SIP-0094 eliminates."""
        ch1 = MagicMock()
        ch1.is_closed = False
        q1 = MagicMock()
        q1.channel = ch1
        ch1.declare_queue = AsyncMock(return_value=q1)

        adapter = _make_adapter_with_channel(ch1)
        await adapter.ensure_queue("neo_results")
        ch1.declare_queue.assert_awaited_once()

        # RobustChannel reconnect: adapter now holds a fresh channel.
        ch2 = MagicMock()
        ch2.is_closed = False
        q2 = MagicMock()
        q2.channel = ch2
        ch2.declare_queue = AsyncMock(return_value=q2)
        adapter._channel = ch2

        await adapter.ensure_queue("neo_results")
        ch2.declare_queue.assert_awaited_once_with("neo_results", **REPLY_QUEUE_DECLARE_ARGS)


class TestConsumeBlockingErrorWrapping:
    """``consume_blocking`` must wrap broker errors in QueueError so callers
    can recover (invalidate cache, retry) instead of crashing on raw
    aio_pika exceptions."""

    async def test_raises_queue_error_on_broker_failure(self) -> None:
        """If the underlying channel/iterator raises mid-consume, the caller
        sees a typed ``QueueError`` — not a leaky aio_pika exception."""
        ch = MagicMock()
        ch.is_closed = False
        broken_queue = MagicMock()
        broken_queue.channel = ch
        broken_queue.name = "reply_q"

        # Raise a realistic broker-side error from iterator setup.
        def explode(*_a, **_kw):
            raise RuntimeError("Channel was not opened")

        broken_queue.iterator = explode
        ch.declare_queue = AsyncMock(return_value=broken_queue)

        adapter = _make_adapter_with_channel(ch)

        with pytest.raises(QueueError) as exc_info:
            await adapter.consume_blocking("reply_q", timeout=0.05, max_messages=1)

        assert "Channel was not opened" in str(exc_info.value)
