"""Unit tests for the default `QueuePort.subscribe()` primitive (SIP-0094 D6).

These exercise the concrete default subscription loop directly: delivery,
ack-after-delivery, queue declaration (D9), sync vs async callbacks, callback
exception isolation (D12), cancellation, and the NoOp inheritance path. Pure
comms-domain — no adapter/factory imports — so it runs in the gated `comms`
regression dir.
"""

import asyncio

import pytest

from squadops.comms.queue_message import QueueMessage
from squadops.ports.comms.noop import NoOpQueuePort
from squadops.ports.comms.queue import QueuePort


def _msg(i: int, queue: str = "agent-x_replies") -> QueueMessage:
    """Build a QueueMessage with a recognizable id for delivery assertions."""
    return QueueMessage(
        message_id=f"m{i}",
        queue_name=queue,
        payload=f'{{"i":{i}}}',
        receipt_handle=f"h{i}",
        attributes={},
    )


class RecordingQueueProvider(QueuePort):
    """QueuePort that drains a controllable inbox and records ack/declare calls.

    Inherits the concrete default ``subscribe()`` / ``consume_blocking()`` from
    QueuePort — that default loop is exactly what these tests exercise.
    """

    def __init__(self, to_deliver: list[QueueMessage] | None = None):
        self._inbox: list[QueueMessage] = list(to_deliver or [])
        self.acked: list[QueueMessage] = []
        self.ensured: list[str] = []

    async def publish(
        self, queue_name: str, payload: str, delay_seconds: int | None = None
    ) -> None:
        self._inbox.append(
            QueueMessage(
                message_id=f"pub{len(self._inbox)}",
                queue_name=queue_name,
                payload=payload,
                receipt_handle="r",
                attributes={},
            )
        )

    async def consume(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        out = self._inbox[:max_messages]
        del self._inbox[:max_messages]
        return out

    async def ack(self, message: QueueMessage) -> None:
        self.acked.append(message)

    async def retry(self, message: QueueMessage, delay_seconds: int) -> None:
        pass

    async def health(self) -> dict:
        return {"status": "healthy", "connected": True}

    def capabilities(self) -> dict[str, bool]:
        return {"delay": False, "fifo": True, "priority": False}

    async def ensure_queue(self, queue_name: str) -> None:
        self.ensured.append(queue_name)


@pytest.mark.unit
class TestQueuePortSubscribe:
    """Default `subscribe()` primitive (SIP-0094 D6 poll loop, D12 isolation)."""

    @pytest.mark.asyncio
    async def test_subscribe_delivers_acks_and_declares_first(self):
        """A queued message reaches the callback, is acked, and the queue is
        declared (D9) before any consume happens."""
        provider = RecordingQueueProvider([_msg(1)])
        received: list[QueueMessage] = []
        done = asyncio.Event()

        async def on_message(m: QueueMessage) -> None:
            received.append(m)
            done.set()

        handle = await provider.subscribe("agent-x_replies", on_message=on_message)
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await handle.cancel()

        assert [m.message_id for m in received] == ["m1"]
        assert [m.message_id for m in provider.acked] == ["m1"]
        # D9: ensure_queue ran before consuming so the subscriber never assumes
        # a peer pre-declared the reply queue.
        assert provider.ensured == ["agent-x_replies"]
        assert handle.active is False

    @pytest.mark.asyncio
    async def test_subscribe_supports_sync_callback(self):
        """A plain sync callback works — the cutover (94.3) resolves a Future
        synchronously, so subscribe must not assume coroutines."""
        provider = RecordingQueueProvider([_msg(7)])
        received: list[QueueMessage] = []

        handle = await provider.subscribe("q", on_message=lambda m: received.append(m))
        for _ in range(40):
            if received:
                break
            await asyncio.sleep(0.05)
        await handle.cancel()

        assert [m.message_id for m in received] == ["m7"]
        assert [m.message_id for m in provider.acked] == ["m7"]

    @pytest.mark.asyncio
    async def test_subscribe_callback_exception_does_not_stop_loop(self):
        """D12: a raising callback is isolated — the next message is still
        delivered, and the failed message is acked (no poison redelivery)."""
        provider = RecordingQueueProvider([_msg(1), _msg(2)])
        received: list[QueueMessage] = []
        second = asyncio.Event()

        async def on_message(m: QueueMessage) -> None:
            if m.message_id == "m1":
                raise RuntimeError("boom")
            received.append(m)
            second.set()

        handle = await provider.subscribe("q", on_message=on_message)
        await asyncio.wait_for(second.wait(), timeout=2.0)
        await handle.cancel()

        # m2 delivered despite m1 raising -> loop survived the exception.
        assert [m.message_id for m in received] == ["m2"]
        # Both acked, including the one whose callback raised.
        assert {m.message_id for m in provider.acked} == {"m1", "m2"}

    @pytest.mark.asyncio
    async def test_subscribe_cancel_stops_delivery(self):
        """After cancel() the loop is gone: messages published afterward are
        never delivered, and cancel() is idempotent."""
        provider = RecordingQueueProvider([])
        received: list[QueueMessage] = []

        handle = await provider.subscribe("q", on_message=lambda m: received.append(m))
        await asyncio.sleep(0.1)  # let the loop spin at least once
        await handle.cancel()
        assert handle.active is False

        # Anything that arrives after cancellation must not be consumed.
        provider._inbox.append(_msg(99))
        await asyncio.sleep(0.6)
        assert received == []
        assert provider.acked == []

        # Idempotent second cancel must not raise.
        await handle.cancel()
        assert handle.active is False

    @pytest.mark.asyncio
    async def test_noop_subscribe_never_delivers_and_cancels_clean(self):
        """NoOpQueuePort inherits the default (D6): it never fires the callback
        (its consume returns nothing) yet stays a usable, cancellable target."""
        provider = NoOpQueuePort()
        received: list[QueueMessage] = []

        handle = await provider.subscribe(
            "agent-x_replies", on_message=lambda m: received.append(m)
        )
        await asyncio.sleep(0.6)  # spans more than one poll cycle

        assert received == []
        assert handle.active is True

        await handle.cancel()
        assert handle.active is False
