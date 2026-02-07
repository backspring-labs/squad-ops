"""
Strategy 1.0 role shim.

Instance identity MUST be provided via `agent_id` at construction time.
"""

from __future__ import annotations

from squadops.core.secrets import SecretManager
from squadops.execution.agent import BaseAgent
from squadops.ports.db import DbRuntime
from squadops.ports.observability.heartbeat import AgentHeartbeatReporter
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort


class StrategyAgent(BaseAgent):
    def __init__(
        self,
        *,
        secret_manager: SecretManager,
        db_runtime: DbRuntime,
        heartbeat_reporter: AgentHeartbeatReporter,
        agent_id: str,
        llm_observability: LLMObservabilityPort | None = None,
    ) -> None:
        super().__init__(
            secret_manager=secret_manager,
            db_runtime=db_runtime,
            heartbeat_reporter=heartbeat_reporter,
            agent_id=agent_id,
            llm_observability=llm_observability,
        )
