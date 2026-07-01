"""
RabbitMQ adapter implementation for QueuePort.
"""

import asyncio
import inspect
import logging
from typing import Any

import aio_pika
from aio_pika import Connection, Message, Queue

from squadops.comms.queue_message import QueueMessage
from squadops.ports.comms.queue import (
    REPLY_QUEUE_DECLARE_ARGS,
    QueuePort,
    SubscriptionCallback,
    SubscriptionHandle,
)

logger = logging.getLogger(__name__)

# SIP-0094 D6/§7: pause before re-establishing a dropped long-lived
# subscription, so a flapping channel doesn't spin a tight reconnect loop.
_SUBSCRIBE_RECONNECT_BACKOFF = 0.5

# #245: a publish issued inside connect_robust's reconnect window hits a stale
# channel ("Channel was not opened") and, with a single attempt, lost the
# message. Unlike subscribe (a long-lived loop), a publish is a bounded
# operation: retry a small number of times with backoff — invalidating the
# stale Queue handle between tries so the next attempt re-declares against the
# live channel — then surface QueueError so the caller is never blocked forever.
_PUBLISH_MAX_ATTEMPTS = 3
_PUBLISH_RETRY_BACKOFF = 0.5
# #158: default poll window for the bounded consume() wait (how long a single
# collect_messages() cycle blocks before returning). Tunable via the constructor.
_DEFAULT_CONSUME_POLL_TIMEOUT = 1.0


class QueueError(Exception):
    """Base exception for queue operations."""

    pass


class RabbitMQAdapter(QueuePort):
    """
    RabbitMQ implementation of QueuePort.

    Handles connection management, queue operations, and message acknowledgment.
    Supports namespace prefixing for queue names.
    """

    def __init__(
        self,
        url: str,
        namespace: str | None = None,
        consume_poll_timeout_seconds: float = _DEFAULT_CONSUME_POLL_TIMEOUT,
    ):
        """
        Initialize RabbitMQ adapter.

        Args:
            url: RabbitMQ connection URL (e.g., 'amqp://user:pass@host:port/vhost')
            namespace: Optional namespace to prepend to queue names (e.g., 'comms.namespace')
            consume_poll_timeout_seconds: Bounded wait per consume() poll cycle (#158).
        """
        self.url = url
        self.namespace = namespace
        self._consume_poll_timeout = consume_poll_timeout_seconds
        self._connection: Connection | None = None
        self._channel: aio_pika.Channel | None = None
        self._queues: dict[str, Queue] = {}
        # SIP-0094 D7: count of times a long-lived subscription had to
        # re-establish after its channel dropped. Surfaced via health() so a
        # flapping reply channel is observable rather than silent.
        self._resubscribe_total = 0

    async def _ensure_connection(self) -> None:
        """Ensure RabbitMQ connection and channel are established."""
        if self._connection is None or self._connection.is_closed:
            self._connection = await aio_pika.connect_robust(self.url)
            logger.info("RabbitMQ connection established")

        if self._channel is None or self._channel.is_closed:
            self._channel = await self._connection.channel()
            logger.debug("RabbitMQ channel created")

    def _apply_namespace(self, queue_name: str) -> str:
        """Apply namespace prefix to queue name if configured."""
        if self.namespace:
            return f"{self.namespace}.{queue_name}"
        return queue_name

    async def _get_queue(self, queue_name: str) -> Queue:
        """Get or create a queue, applying namespace if configured.

        Cached Queue handles are bound to the channel they were declared on.
        If the underlying channel reconnects (RobustChannel) the cached
        handle can become stale and operations against it raise
        ``Channel was not opened``. We track which channel each cached
        queue is bound to and re-declare on mismatch.
        """
        full_name = self._apply_namespace(queue_name)
        await self._ensure_connection()

        cached = self._queues.get(full_name)
        if cached is not None and getattr(cached, "channel", None) is self._channel:
            return cached

        queue = await self._channel.declare_queue(full_name, **REPLY_QUEUE_DECLARE_ARGS)
        self._queues[full_name] = queue
        logger.debug(f"Declared queue: {full_name}")
        return queue

    async def ensure_queue(self, queue_name: str) -> None:
        """Idempotently declare ``queue_name`` with the shared
        :data:`REPLY_QUEUE_DECLARE_ARGS` (SIP-0094 D3).

        Thin wrapper over :meth:`_get_queue`, so the reply queue is declared
        with byte-identical args to the agent comms queue. Agents call this at
        startup for their ``{agent_id}_replies`` queue — which they only ever
        publish to, never consume from — so the lazy declaration on
        :meth:`consume` never creates it.
        """
        await self._get_queue(queue_name)

    async def invalidate_queue(self, queue_name: str) -> None:
        """Drop the cached Queue handle for ``queue_name``.

        Called by long-running consume loops after a transient failure
        (e.g. ``Channel was not opened``) so the next call re-declares
        against the current channel.
        """
        full_name = self._apply_namespace(queue_name)
        self._queues.pop(full_name, None)

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
        # Build the message once; only the transport send is retried. A bad
        # payload fails here, before the loop, so it is never retried.
        message_properties: dict[str, Any] = {
            "delivery_mode": aio_pika.DeliveryMode.PERSISTENT,
        }

        # Handle delay using TTL and Dead Letter Exchange
        # Note: For production, consider using rabbitmq-delayed-message-exchange plugin
        if delay_seconds is not None and delay_seconds > 0:
            # Use TTL with DLX for delayed delivery
            # This is a simplified approach; full implementation would use delayed exchange plugin
            # aio_pika expects expiration as int (milliseconds) or timedelta
            message_properties["expiration"] = delay_seconds * 1000  # TTL in milliseconds

        message = Message(
            body=payload.encode("utf-8"),
            **message_properties,
        )

        last_exc: Exception | None = None
        for attempt in range(1, _PUBLISH_MAX_ATTEMPTS + 1):
            try:
                await self._ensure_connection()
                queue = await self._get_queue(queue_name)

                await self._channel.default_exchange.publish(
                    message,
                    routing_key=queue.name,
                )

                if attempt > 1:
                    logger.info(
                        "Published message to queue %s on attempt %d/%d",
                        queue.name,
                        attempt,
                        _PUBLISH_MAX_ATTEMPTS,
                    )
                else:
                    logger.debug("Published message to queue: %s", queue.name)
                return

            except asyncio.CancelledError:
                raise
            except Exception as e:
                # A drop inside connect_robust's reconnect window leaves a stale
                # channel/Queue handle. Drop the cached handle so the next attempt
                # re-declares against the live channel (the _get_queue channel-swap
                # path), back off, and retry.
                last_exc = e
                await self.invalidate_queue(queue_name)
                if attempt < _PUBLISH_MAX_ATTEMPTS:
                    logger.warning(
                        "publish to %s failed (attempt %d/%d): %s; retrying",
                        queue_name,
                        attempt,
                        _PUBLISH_MAX_ATTEMPTS,
                        e,
                    )
                    await asyncio.sleep(_PUBLISH_RETRY_BACKOFF * attempt)

        logger.error(
            "Failed to publish message to queue %s after %d attempts: %s",
            queue_name,
            _PUBLISH_MAX_ATTEMPTS,
            last_exc,
        )
        raise QueueError(f"Failed to publish message: {last_exc}") from last_exc

    @staticmethod
    def _to_queue_message(
        message: aio_pika.abc.AbstractIncomingMessage, queue_name: str
    ) -> QueueMessage:
        """Build a canonical :class:`QueueMessage` from an aio_pika delivery.

        Single-sources the field/attribute mapping shared by :meth:`consume`,
        :meth:`consume_blocking`, and :meth:`subscribe`. The raw aio_pika
        message is stashed in ``attributes["message"]`` so :meth:`ack` /
        :meth:`retry` can act on it later.
        """
        return QueueMessage(
            message_id=str(message.delivery_tag),
            queue_name=queue_name,
            payload=message.body.decode("utf-8"),
            receipt_handle=str(message.delivery_tag),
            attributes={
                "delivery_tag": message.delivery_tag,
                "routing_key": message.routing_key,
                "exchange": message.exchange,
                "redelivered": message.redelivered,
                "message": message,  # Store message object for ack
            },
        )

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
        try:
            await self._ensure_connection()
            queue = await self._get_queue(queue_name)

            messages = []

            # Use iterator with timeout wrapper to avoid blocking indefinitely
            # This approach collects messages up to max_messages, then breaks
            async def collect_messages():
                async with queue.iterator(no_ack=False) as queue_iter:
                    async for message in queue_iter:
                        messages.append(self._to_queue_message(message, queue_name))

                        # Break after getting max_messages
                        if len(messages) >= max_messages:
                            break

            # Run with timeout to avoid blocking if no messages are available
            # Note: This is a simplified approach; for production long-running consumers,
            # consider using a callback-based consumer pattern
            try:
                await asyncio.wait_for(collect_messages(), timeout=self._consume_poll_timeout)
            except TimeoutError:
                # Timeout is acceptable - we may have gotten some messages or none
                pass

            logger.debug(f"Consumed {len(messages)} message(s) from queue: {queue.name}")
            return messages

        except Exception as e:
            logger.error(f"Failed to consume messages from queue {queue_name}: {e}")
            raise QueueError(f"Failed to consume messages: {e}") from e

    async def consume_blocking(
        self, queue_name: str, timeout: float, max_messages: int = 1
    ) -> list[QueueMessage]:
        """Hold a single consumer registration on ``queue_name`` for up to
        ``timeout`` seconds, returning as soon as ``max_messages`` arrive.

        This avoids the consumer-tag churn of repeatedly calling :meth:`consume`
        in a poll loop, which on busy/empty queues can race with arriving
        messages (a message dispatched to a consumer tag that's about to be
        canceled may not be redelivered to the next short-lived iterator).
        """
        try:
            await self._ensure_connection()
            queue = await self._get_queue(queue_name)

            messages: list[QueueMessage] = []

            async def collect_messages():
                async with queue.iterator(no_ack=False) as queue_iter:
                    async for message in queue_iter:
                        messages.append(self._to_queue_message(message, queue_name))
                        if len(messages) >= max_messages:
                            break

            try:
                await asyncio.wait_for(collect_messages(), timeout=timeout)
            except TimeoutError:
                pass

            logger.debug(f"consume_blocking returned {len(messages)} message(s) from {queue.name}")
            return messages

        except Exception as e:
            logger.error(f"Failed to consume_blocking from queue {queue_name}: {e}")
            raise QueueError(f"Failed to consume_blocking: {e}") from e

    async def subscribe(
        self,
        queue_name: str,
        *,
        on_message: SubscriptionCallback,
    ) -> SubscriptionHandle:
        """Native long-lived subscription on ``queue_name`` (SIP-0094 §7).

        This is **the** SIP-0094 fix: instead of opening a fresh short-lived
        consumer per reply wait (which races arriving messages against
        consumer-tag teardown), it holds a single ``queue.iterator`` consumer
        for the whole subscription and routes every delivery to ``on_message``.

        **Channel-close resubscribe (the riskiest part).** The shared
        RobustChannel can be replaced under us on reconnect, which strands a
        long-lived consumer bound to the dead channel. The reconnect loop here
        treats any termination of the iterator — an exception from a dropped
        channel, or a clean end — as a signal to re-establish: it invalidates
        the cached (stale) Queue handle, re-declares against the live channel
        (the ``_get_queue`` channel-swap path), and re-opens the consumer,
        bumping :attr:`_resubscribe_total` (D7) so flapping is observable. The
        iterator surfacing the channel failure is what drives this, which is
        why a separate ``add_close_callback`` re-consume isn't used — that would
        race RobustChannel's own consumer restoration and double-subscribe.

        Callback exceptions are isolated (D12): a raising ``on_message`` is
        logged, the message is still acked (reply messages are never
        redelivered), and the consumer keeps running. The queue is declared
        before consuming (D9).

        Args:
            queue_name: Queue to subscribe to.
            on_message: Sync or async callable invoked with each QueueMessage.

        Returns:
            A :class:`SubscriptionHandle`; ``await handle.cancel()`` cancels the
            consumer and tears down the loop.
        """
        await self.ensure_queue(queue_name)

        async def _run() -> None:
            first_attempt = True
            while True:
                if not first_attempt:
                    # Re-establishing after a drop or clean end: drop the stale
                    # cached handle, back off, and count the resubscribe.
                    self._resubscribe_total += 1
                    await self.invalidate_queue(queue_name)
                    logger.info(
                        "subscribe: re-establishing subscription to %s (resubscribe #%d)",
                        queue_name,
                        self._resubscribe_total,
                    )
                    await asyncio.sleep(_SUBSCRIBE_RECONNECT_BACKOFF)
                first_attempt = False

                try:
                    await self._ensure_connection()
                    queue = await self._get_queue(queue_name)
                    async with queue.iterator(no_ack=False) as queue_iter:
                        async for message in queue_iter:
                            await self._dispatch_subscription_delivery(
                                message, on_message, queue_name
                            )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(
                        "subscribe: subscription to %s dropped (%s); will resubscribe",
                        queue_name,
                        exc,
                    )
                    continue
                # Iterator ended without error (consumer cancelled server-side):
                # loop back to re-establish rather than silently stop.
                logger.info("subscribe: iterator on %s ended; will resubscribe", queue_name)

        task = asyncio.create_task(_run(), name=f"rabbitmq-subscribe:{queue_name}")
        return SubscriptionHandle(task, queue_name)

    async def _dispatch_subscription_delivery(
        self,
        message: aio_pika.abc.AbstractIncomingMessage,
        on_message: SubscriptionCallback,
        queue_name: str,
    ) -> None:
        """Route one native delivery to the callback (D12 isolation), then ack.

        Mirrors the default ``subscribe`` policy: callback failures are logged
        and the message is acked anyway (reply messages are not redelivered),
        so a single bad invocation never tears down the consumer.
        """
        queue_message = self._to_queue_message(message, queue_name)
        try:
            result = on_message(queue_message)
            if inspect.isawaitable(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("subscribe: callback raised on %s; acking and continuing", queue_name)
        try:
            await message.ack()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("subscribe: ack failed on %s", queue_name)

    async def ack(self, message: QueueMessage) -> None:
        """
        Acknowledge a message, removing it from the queue.

        Args:
            message: QueueMessage to acknowledge

        Raises:
            QueueError: If acknowledgment fails
        """
        try:
            # Extract stored message object
            stored_message = message.attributes.get("message")
            if stored_message is None:
                raise QueueError(
                    "Message object not found in attributes (message may have expired)"
                )

            # Acknowledge the message
            await stored_message.ack()
            logger.debug(f"Acknowledged message: {message.message_id}")

        except Exception as e:
            logger.error(f"Failed to acknowledge message {message.message_id}: {e}")
            raise QueueError(f"Failed to acknowledge message: {e}") from e

    async def retry(self, message: QueueMessage, delay_seconds: int) -> None:
        """
        Retry a message by republishing it with a delay.

        Args:
            message: QueueMessage to retry
            delay_seconds: Delay before message becomes available again

        Raises:
            QueueError: If retry fails
        """
        try:
            # Republish the message with delay
            await self.publish(message.queue_name, message.payload, delay_seconds=delay_seconds)

            # Acknowledge the original message
            await self.ack(message)

            logger.debug(f"Retried message {message.message_id} with {delay_seconds}s delay")

        except Exception as e:
            logger.error(f"Failed to retry message {message.message_id}: {e}")
            raise QueueError(f"Failed to retry message: {e}") from e

    async def health(self) -> dict[str, Any]:
        """
        Check the health status of the queue provider.

        Returns:
            Dictionary with health status information
        """
        try:
            await self._ensure_connection()

            # Check connection and channel state
            is_connected = self._connection is not None and not self._connection.is_closed
            has_channel = self._channel is not None and not self._channel.is_closed

            status = "healthy" if (is_connected and has_channel) else "unhealthy"

            return {
                "status": status,
                "connected": is_connected,
                "channel_ready": has_channel,
                "provider": "rabbitmq",
                "resubscribe_total": self._resubscribe_total,
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "channel_ready": False,
                "provider": "rabbitmq",
                "error": str(e),
            }

    def capabilities(self) -> dict[str, bool]:
        """
        Return the capabilities supported by this queue provider.

        Returns:
            Dictionary with capability flags
        """
        return {
            "delay": True,  # Supported via TTL+DLX (or delayed exchange plugin)
            "fifo": False,  # RabbitMQ does not guarantee FIFO ordering
            "priority": True,  # Supported via priority queues
        }

    async def close(self) -> None:
        """Close the RabbitMQ connection and channel."""
        try:
            if self._channel and not self._channel.is_closed:
                await self._channel.close()
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
            logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
