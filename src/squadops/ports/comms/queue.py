"""
Port interface for queue providers.
Defines the contract that any queue transport provider must satisfy.
"""

import asyncio
import inspect
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from squadops.comms.queue_message import QueueMessage

logger = logging.getLogger(__name__)

# SIP-0094 D3: canonical declaration args for agent comms/reply queues
# (`{agent_id}_comms`, `{agent_id}_replies`). Every declaration of these queues
# — agent startup `ensure_queue`, orchestrator `subscribe`, manual creation —
# MUST use these exact args. A mismatch on a durable queue makes the broker
# reject the redeclare with PRECONDITION_FAILED, so this is single-sourced here
# to keep the args from drifting across call sites.
REPLY_QUEUE_DECLARE_ARGS: dict[str, Any] = {"durable": True}

# SIP-0094 D6: how long the default poll-based `subscribe()` blocks on each
# `consume_blocking()` iteration. This does NOT affect delivery latency — a
# waiting message is returned the moment it arrives — it only bounds how often
# an idle loop re-enters consume. The native RabbitMQ override (PR 94.2b)
# holds a real long-lived consumer and ignores this value.
_SUBSCRIBE_POLL_TIMEOUT = 5.0

# A subscription callback may be sync or async; it receives one QueueMessage.
# The reply-router cutover (PR 94.3) resolves a Future synchronously, so the
# sync form must be supported, not just coroutines.
SubscriptionCallback = Callable[[QueueMessage], Awaitable[None] | None]


class SubscriptionHandle:
    """Lifecycle handle for a long-lived queue subscription (SIP-0094 D6).

    Returned by :meth:`QueuePort.subscribe`. Wraps the background task that
    drives delivery; ``await handle.cancel()`` stops it. The handle is the only
    thing a caller needs to retain to tear a subscription down — it never
    exposes the underlying task directly.
    """

    def __init__(self, task: asyncio.Task, queue_name: str) -> None:
        self._task = task
        self.queue_name = queue_name

    @property
    def active(self) -> bool:
        """True while the subscription's background task is still running."""
        return not self._task.done()

    async def cancel(self) -> None:
        """Stop the subscription and wait for its task to unwind.

        Idempotent: calling it on an already-finished subscription is a no-op.
        """
        if self._task.done():
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass


class QueuePort(ABC):
    """Abstract base class for queue transport providers."""

    @abstractmethod
    async def publish(
        self, queue_name: str, payload: str, delay_seconds: int | None = None
    ) -> None:
        """
        Publish a message to a queue.

        Args:
            queue_name: Name of the queue
            payload: Message payload (must be ACI TaskEnvelope JSON)
            delay_seconds: Optional delay before message becomes available (None = immediate)

        Raises:
            QueueError: If publishing fails
        """
        pass

    @abstractmethod
    async def consume(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        """
        Consume messages from a queue.

        Args:
            queue_name: Name of the queue
            max_messages: Maximum number of messages to retrieve (default: 1)

        Returns:
            List of QueueMessage objects

        Raises:
            QueueError: If consumption fails
        """
        pass

    async def consume_blocking(
        self, queue_name: str, timeout: float, max_messages: int = 1
    ) -> list[QueueMessage]:
        """Block on a queue until a message arrives or ``timeout`` elapses.

        Unlike :meth:`consume` (which opens a fresh, short-lived consumer per
        call and returns immediately), this method holds a single consumer
        registration for the whole ``timeout`` window. That is the right
        primitive for request/reply waits where the reply queue is empty for
        most of the wait and a message must be delivered the moment it
        arrives. Implementations should fall back to short-lived polling if
        they cannot subscribe long-term.

        Args:
            queue_name: Name of the queue
            timeout: Max seconds to block; returns empty list if no message
                arrives in this window
            max_messages: Maximum messages to retrieve (default: 1)

        Returns:
            List of QueueMessage objects (possibly empty on timeout)

        Raises:
            QueueError: If consumption fails
        """
        # Default fallback: poll consume() until a message arrives or deadline.
        deadline = time.monotonic() + timeout
        while True:
            messages = await self.consume(queue_name, max_messages=max_messages)
            if messages:
                return messages
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            await asyncio.sleep(min(0.5, remaining))

    async def subscribe(
        self,
        queue_name: str,
        *,
        on_message: SubscriptionCallback,
    ) -> SubscriptionHandle:
        """Deliver every message on ``queue_name`` to ``on_message`` until
        cancelled (SIP-0094 D6).

        This **concrete default** drives a background task that loops on
        :meth:`consume_blocking`, dispatching each delivery to ``on_message``
        (awaited if it returns a coroutine) and acking it. It is the
        subscription primitive for non-RabbitMQ adapters and tests — it is
        explicitly **NOT** the SIP-0094 fix. The RabbitMQ adapter overrides
        this with a native long-lived consumer (PR 94.2b); ``NoOpQueuePort``
        inherits this default and never fires the callback (its ``consume``
        returns no messages).

        Callback exceptions are isolated (SIP-0094 D12): a raising
        ``on_message`` is logged and the message is still acked — reply
        messages are never redelivered, since a failing callback is a
        waiter-side logic error rather than a transport fault, so requeuing
        would only poison-loop — and the loop keeps consuming. A single bad
        callback never terminates the subscription.

        The queue is declared idempotently before consuming (SIP-0094 D9) so a
        subscriber never assumes a peer pre-declared it.

        Args:
            queue_name: Queue to subscribe to.
            on_message: Sync or async callable invoked with each QueueMessage.

        Returns:
            A :class:`SubscriptionHandle`; ``await handle.cancel()`` to stop.

        Raises:
            QueueError: If the queue cannot be declared.
        """
        await self.ensure_queue(queue_name)

        async def _run() -> None:
            while True:
                try:
                    messages = await self.consume_blocking(
                        queue_name, timeout=_SUBSCRIBE_POLL_TIMEOUT, max_messages=1
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("subscribe: consume failed on %s; retrying", queue_name)
                    await asyncio.sleep(1.0)
                    continue

                for message in messages:
                    # D12: isolate callback failures so the durable
                    # subscription survives a single bad invocation.
                    try:
                        result = on_message(message)
                        if inspect.isawaitable(result):
                            await result
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "subscribe: callback raised on %s; acking and continuing",
                            queue_name,
                        )
                    # Ack after the delivery attempt (success OR failure):
                    # reply messages are not redelivered.
                    try:
                        await self.ack(message)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("subscribe: ack failed on %s", queue_name)

        task = asyncio.create_task(_run(), name=f"subscribe:{queue_name}")
        return SubscriptionHandle(task, queue_name)

    async def invalidate_queue(self, queue_name: str) -> None:
        """Drop any cached handle for ``queue_name`` so subsequent operations
        re-resolve against the current channel.

        Useful after a transient ``QueueError`` so the next consume/publish
        re-declares the queue rather than reusing a stale, channel-bound
        handle. Default implementation is a no-op for adapters that don't
        cache.
        """
        return None

    async def ensure_queue(self, queue_name: str) -> None:
        """Idempotently declare ``queue_name`` so it exists before any peer
        addresses it.

        Concrete default is a no-op: adapters that declare lazily on first
        consume (or have no broker at all, e.g. NoOp) need do nothing here.
        Broker-backed adapters override this to declare with
        :data:`REPLY_QUEUE_DECLARE_ARGS` (SIP-0094 D3).

        Agents call this at startup for their ``{agent_id}_replies`` reply
        queue, which they only ever publish to (never consume from), so the
        lazy declaration that covers ``{agent_id}_comms`` never fires for it.
        """
        return None

    @abstractmethod
    async def ack(self, message: QueueMessage) -> None:
        """
        Acknowledge a message, removing it from the queue.

        Args:
            message: QueueMessage to acknowledge

        Raises:
            QueueError: If acknowledgment fails
        """
        pass

    @abstractmethod
    async def retry(self, message: QueueMessage, delay_seconds: int) -> None:
        """
        Retry a message by republishing it with a delay.

        Args:
            message: QueueMessage to retry
            delay_seconds: Delay before message becomes available again

        Raises:
            QueueError: If retry fails
        """
        pass

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """
        Check the health status of the queue provider.

        Returns:
            Dictionary with health status information (e.g., {"status": "healthy", "connected": True})
        """
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """
        Return the capabilities supported by this queue provider.

        Returns:
            Dictionary with capability flags:
            - delay: Whether delayed messages are supported
            - fifo: Whether FIFO ordering is guaranteed
            - priority: Whether message priority is supported
        """
        pass
