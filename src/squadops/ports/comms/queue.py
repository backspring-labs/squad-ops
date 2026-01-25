"""
Port interface for queue providers.
Defines the contract that any queue transport provider must satisfy.
"""

from abc import ABC, abstractmethod
from typing import Any

from squadops.comms.queue_message import QueueMessage


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
