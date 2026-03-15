"""A2A server adapter — wraps a2a-sdk into MessagingPort (SIP-0085).

All SDK-specific imports are confined to this module. The adapter owns
HTTP server lifecycle (start/stop/health). Chat logic is injected via
an AgentExecutor, not owned here.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from squadops.ports.comms.messaging import MessagingPort

logger = logging.getLogger(__name__)

_SHUTDOWN_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class AgentCardConfig:
    """Configuration for building an A2A agent card."""

    agent_id: str
    display_name: str
    description: str
    version: str
    host: str = "0.0.0.0"
    port: int = 5000
    url_scheme: str = "http"
    skills: tuple[AgentSkill, ...] = ()


def build_agent_card(config: AgentCardConfig) -> AgentCard:
    """Build an A2A AgentCard from instance configuration.

    Args:
        config: Agent card configuration fields.

    Returns:
        A2A SDK AgentCard instance.
    """
    skills = (
        list(config.skills)
        if config.skills
        else [
            AgentSkill(
                id="chat",
                name="Chat",
                description=config.description,
                tags=["chat", "conversational"],
            ),
        ]
    )

    return AgentCard(
        name=config.display_name,
        description=config.description,
        url=f"{config.url_scheme}://{config.host}:{config.port}",
        version=config.version,
        skills=skills,
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
    )


class A2AServerAdapter(MessagingPort):
    """A2A server adapter implementing MessagingPort.

    Wraps the a2a-sdk's Starlette application and runs it via uvicorn.
    The executor (chat logic) is injected at construction time.
    """

    def __init__(
        self,
        *,
        agent_card: AgentCard,
        executor: Any,
        host: str = "0.0.0.0",
        port: int = 5000,
        log_level: str = "info",
    ) -> None:
        """Initialize the A2A server adapter.

        Args:
            agent_card: A2A agent card for discovery.
            executor: AgentExecutor instance (chat logic).
            host: Bind address.
            port: Bind port.
            log_level: Uvicorn log level (debug, info, warning, error).
        """
        self._agent_card = agent_card
        self._executor = executor
        self._host = host
        self._port = port
        self._log_level = log_level
        self._server: uvicorn.Server | None = None
        self._serve_task: asyncio.Task[None] | None = None

        # Wire SDK components: executor → handler → app
        task_store = InMemoryTaskStore()
        handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=task_store,
        )
        self._app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=handler,
        )

    async def start(self) -> None:
        """Start the A2A HTTP/SSE server as a background task."""
        if self._serve_task is not None:
            logger.warning("A2A server already running on port %d", self._port)
            return

        try:
            config = uvicorn.Config(
                app=self._app.build(),
                host=self._host,
                port=self._port,
                log_level=self._log_level,
            )
            self._server = uvicorn.Server(config)
            self._serve_task = asyncio.create_task(
                self._server.serve(), name=f"a2a-server-{self._port}"
            )
            logger.info("A2A server starting on %s:%d", self._host, self._port)
        except Exception:
            self._server = None
            self._serve_task = None
            logger.exception("Failed to start A2A server on port %d", self._port)
            raise

    async def stop(self) -> None:
        """Stop the A2A server gracefully."""
        if self._server is not None:
            self._server.should_exit = True
        if self._serve_task is not None:
            try:
                await asyncio.wait_for(self._serve_task, timeout=_SHUTDOWN_TIMEOUT_SECONDS)
            except (TimeoutError, asyncio.CancelledError):
                self._serve_task.cancel()
            self._serve_task = None
            self._server = None
            logger.info("A2A server stopped")

    async def health(self) -> dict[str, Any]:
        """Check A2A server health."""
        running = self._serve_task is not None and not self._serve_task.done()
        return {
            "healthy": running,
            "port": self._port,
            "agent_name": self._agent_card.name,
        }
