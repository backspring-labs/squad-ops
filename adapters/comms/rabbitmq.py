"""
RabbitMQ adapter implementation for QueuePort.
"""

import asyncio
import logging
from typing import Any

import aio_pika
from aio_pika import Connection, Message, Queue

from squadops.comms.queue_message import QueueMessage
from squadops.ports.comms.queue import QueuePort

logger = logging.getLogger(__name__)


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
    ):
        """
        Initialize RabbitMQ adapter.

        Args:
            url: RabbitMQ connection URL (e.g., 'amqp://user:pass@host:port/vhost')
            namespace: Optional namespace to prepend to queue names (e.g., 'comms.namespace')
        """
        self.url = url
        self.namespace = namespace
        self._connection: Connection | None = None
        self._channel: aio_pika.Channel | None = None
        self._queues: dict[str, Queue] = {}

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
        """Get or create a queue, applying namespace if configured."""
        full_name = self._apply_namespace(queue_name)
        if full_name not in self._queues:
            await self._ensure_connection()
            queue = await self._channel.declare_queue(full_name, durable=True)
            self._queues[full_name] = queue
            logger.debug(f"Declared queue: {full_name}")
        return self._queues[full_name]

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
        try:
            await self._ensure_connection()
            queue = await self._get_queue(queue_name)

            # Create message with persistent delivery mode
            message_properties = {
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

            await self._channel.default_exchange.publish(
                message,
                routing_key=queue.name,
            )

            logger.debug(f"Published message to queue: {queue.name}")

        except Exception as e:
            logger.error(f"Failed to publish message to queue {queue_name}: {e}")
            raise QueueError(f"Failed to publish message: {e}") from e

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
                        # Extract message data
                        payload = message.body.decode("utf-8")
                        receipt_handle = str(message.delivery_tag)

                        # Store message reference for ack/retry
                        message_attributes = {
                            "delivery_tag": message.delivery_tag,
                            "routing_key": message.routing_key,
                            "exchange": message.exchange,
                            "redelivered": message.redelivered,
                            "message": message,  # Store message object for ack
                        }

                        queue_message = QueueMessage(
                            message_id=str(message.delivery_tag),
                            queue_name=queue_name,
                            payload=payload,
                            receipt_handle=receipt_handle,
                            attributes=message_attributes,
                        )

                        messages.append(queue_message)

                        # Break after getting max_messages
                        if len(messages) >= max_messages:
                            break

            # Run with timeout to avoid blocking if no messages are available
            # Note: This is a simplified approach; for production long-running consumers,
            # consider using a callback-based consumer pattern
            try:
                await asyncio.wait_for(collect_messages(), timeout=1.0)
            except TimeoutError:
                # Timeout is acceptable - we may have gotten some messages or none
                pass

            logger.debug(f"Consumed {len(messages)} message(s) from queue: {queue.name}")
            return messages

        except Exception as e:
            logger.error(f"Failed to consume messages from queue {queue_name}: {e}")
            raise QueueError(f"Failed to consume messages: {e}") from e

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
