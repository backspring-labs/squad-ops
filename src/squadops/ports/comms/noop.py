"""
No-op queue port implementation.

Used for testing and development without a real queue backend.
"""

from __future__ import annotations

import logging
from typing import Any

from squadops.comms.queue_message import QueueMessage
from squadops.ports.comms.queue import QueuePort

logger = logging.getLogger(__name__)


class NoOpQueuePort(QueuePort):
    """No-op queue port that logs operations but doesn't persist.

    Useful for:
    - Unit testing without RabbitMQ
    - Development/debugging
    - Initial bootstrapping before queue adapter is ready
    """

    def __init__(self):
        """Initialize the no-op queue port."""
        self._message_buffer: list[QueueMessage] = []
        logger.debug("NoOpQueuePort initialized")

    async def publish(
        self, queue_name: str, payload: str, delay_seconds: int | None = None
    ) -> None:
        """Log publish operation without actually sending.

        Args:
            queue_name: Name of the queue
            payload: Message payload
            delay_seconds: Optional delay. Rejected when non-zero, matching the
                shipped providers (#572) — a null object that accepts an
                operation every real provider refuses makes a test exercise the
                branch production never takes.

        Raises:
            NotImplementedError: If a non-zero ``delay_seconds`` is requested.
        """
        if delay_seconds is not None and delay_seconds > 0:
            raise NotImplementedError(
                f"Delayed delivery is not supported (delay_seconds={delay_seconds}); "
                f"capabilities()['delay'] is False."
            )
        logger.debug(
            "NoOp publish",
            extra={
                "queue_name": queue_name,
                "payload_length": len(payload),
                "delay_seconds": delay_seconds,
            },
        )

    async def consume(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        """Return empty list (no messages in no-op mode).

        Args:
            queue_name: Name of the queue
            max_messages: Maximum messages to retrieve

        Returns:
            Empty list
        """
        logger.debug(
            "NoOp consume",
            extra={"queue_name": queue_name, "max_messages": max_messages},
        )
        return []

    async def ack(self, message: QueueMessage) -> None:
        """Log ack operation.

        Args:
            message: Message to acknowledge
        """
        logger.debug("NoOp ack", extra={"message_id": message.message_id})

    async def retry(self, message: QueueMessage, delay_seconds: int) -> None:
        """Log retry operation.

        Args:
            message: Message to retry
            delay_seconds: Retry delay
        """
        logger.debug(
            "NoOp retry",
            extra={"message_id": message.message_id, "delay_seconds": delay_seconds},
        )

    async def health(self) -> dict[str, Any]:
        """Return healthy status.

        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy",
            "connected": True,
            "provider": "noop",
        }

    def capabilities(self) -> dict[str, bool]:
        """Return capabilities, matching what the shipped providers actually do.

        A null object may deliver nothing, but its *flags* are still read by
        callers deciding which branch to take. Advertising delay/priority here
        while every real provider reports False (#572) would route tests down a
        path production never takes. ``fifo`` stays True: it gates no operation,
        so nothing can be built on it.

        Returns:
            Capabilities dictionary
        """
        return {
            "delay": False,
            "fifo": True,
            "priority": False,
        }
