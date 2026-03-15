"""Messaging port — A2A server lifecycle contract (SIP-0085)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MessagingPort(ABC):
    """Abstract interface for agent messaging server.

    Manages the lifecycle of an A2A-compliant HTTP/SSE server
    running inside an agent container. The chat logic itself
    lives in ChatAgentExecutor, not in this port.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the messaging server."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the messaging server."""
        ...

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check messaging server health."""
        ...
