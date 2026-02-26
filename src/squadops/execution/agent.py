"""
SquadOps 1.0 execution layer: DI-first BaseAgent.

Constraints:
- This module MUST NOT import from `_v0_legacy/`.
- Runtime dependencies (secrets, db, heartbeat) are provided via dependency injection.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from squadops.core.secrets import SecretManager
from squadops.ports.db import DbRuntime
from squadops.ports.observability.heartbeat import AgentHeartbeatReporter
from squadops.ports.prompts.service import PromptService
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """Minimal 1.0 request envelope for in-process dispatch."""

    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    """
    Minimal 1.0 BaseAgent.

    This class intentionally does NOT implement the legacy runtime loop (RabbitMQ/Redis/LLM).
    It provides:
    - dependency-injected access to Secrets + DB + Heartbeats
    - a small in-process action dispatcher scaffold
    - standardized identity (`agent_id`) for logging/telemetry
    """

    def __init__(
        self,
        *,
        secret_manager: SecretManager,
        db_runtime: DbRuntime,
        heartbeat_reporter: AgentHeartbeatReporter,
        agent_id: str,
        prompt_service: PromptService | None = None,
        llm_observability: LLMObservabilityPort | None = None,
    ) -> None:
        self.secret_manager = secret_manager
        self.db_runtime = db_runtime
        self.heartbeat_reporter = heartbeat_reporter
        self.agent_id = agent_id
        self.prompt_service = prompt_service

        # SIP-0061: Always inject NoOp when None — self.llm_observability is never None
        if llm_observability is None:
            from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter

            llm_observability = NoOpLLMObservabilityAdapter()
        self.llm_observability = llm_observability

        logger.info("agent_initialized", extra={"agent_id": self.agent_id})

    def dispatch(self, request: AgentRequest) -> Any:
        """
        Dispatch a request to an action handler.

        Default behavior: find a method named `on_<action>` (normalized) and call it.
        Subclasses can override this for more advanced routing.
        """
        if not request.action or not isinstance(request.action, str):
            raise ValueError("request.action must be a non-empty string")

        handler_name = f"on_{request.action.strip().lower().replace('-', '_')}"
        handler: Callable[[AgentRequest], Any] | None = getattr(self, handler_name, None)
        if handler is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} does not implement handler '{handler_name}' "
                f"for action '{request.action}'"
            )
        return handler(request)

    def resolve(self, value: str) -> str:
        """
        Resolve secret references in a string via the injected SecretManager.

        This is a convenience wrapper used by the 1.0 agents; it keeps agent code
        consistent and makes tests/readability nicer.
        """
        return self.secret_manager.resolve(value)

    def health_check(self):
        """
        Run the injected DbRuntime health check.

        Returns:
            squadops.ports.db.HealthResult
        """
        return self.db_runtime.health_check()

    async def send_heartbeat(
        self,
        *,
        lifecycle_state: str,
        current_task_id: str | None = None,
        version: str | None = None,
        tps: float | None = None,
        memory_count: int | None = None,
    ) -> None:
        """
        Send a status heartbeat via the injected reporter (dashboard compatibility).
        """
        await self.heartbeat_reporter.send_status(
            agent_id=self.agent_id,
            lifecycle_state=lifecycle_state,
            current_task_id=current_task_id,
            version=version,
            tps=tps,
            memory_count=memory_count,
        )

    def get_system_prompt(self) -> str:
        """
        Get assembled system prompt for this agent's role.

        Uses the injected PromptService to assemble a deterministic,
        versioned prompt based on the agent's role (derived from agent_id).

        Returns:
            Assembled prompt content, or empty string if no service configured.
        """
        if self.prompt_service is None:
            return ""
        # Extract role from agent_id (e.g., "lead-001" -> "lead")
        role = self.agent_id.split("-")[0] if "-" in self.agent_id else self.agent_id
        assembled = self.prompt_service.get_system_prompt(role)
        return assembled.content
