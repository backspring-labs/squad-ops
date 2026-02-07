"""
Dev (developer) 1.0 role shim.

Instance identity MUST be provided via `agent_id` at construction time.
"""

from __future__ import annotations

import time

from squadops.core.secrets import SecretManager
from squadops.execution.agent import AgentRequest, BaseAgent
from squadops.execution.observability import build_generation_record
from squadops.ports.db import DbRuntime
from squadops.ports.observability.heartbeat import AgentHeartbeatReporter
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
from squadops.telemetry.models import (
    CorrelationContext,
    PromptLayer,
    PromptLayerMetadata,
    StructuredEvent,
)


class DevAgent(BaseAgent):
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

    def on_execute(self, request: AgentRequest) -> dict:
        """Execute a development task with LLM observability instrumentation.

        Demonstrates the SIP-0061 paired instrumentation pattern:
        task.assigned → start_task_span → LLM call → record_generation → end_task_span
        """
        envelope = request.payload.get("envelope")
        if envelope is None:
            return {"status": "error", "message": "no envelope in payload"}

        # Build correlation context from envelope
        ctx_task = CorrelationContext.from_envelope(
            envelope=envelope, agent_id=self.agent_id, agent_role="dev"
        )

        # Task assigned
        self.llm_observability.record_event(
            ctx_task,
            StructuredEvent(
                name="task.assigned",
                message=f"Task {getattr(envelope, 'task_id', 'unknown')} assigned to {self.agent_id}",
            ),
        )

        # Start task span
        self.llm_observability.start_task_span(ctx_task)
        self.llm_observability.record_event(
            ctx_task,
            StructuredEvent(
                name="task.started",
                message=f"Task {getattr(envelope, 'task_id', 'unknown')} started",
            ),
        )

        try:
            # LLM call + paired generation recording
            # (placeholder — real LLM calls will be wired when LLMPort is integrated)
            llm_response = request.payload.get("llm_response")
            if llm_response is not None:
                model = request.payload.get("model", "unknown")
                prompt_text = request.payload.get("prompt_text", "")

                start = time.monotonic()
                # In production: response = await self.llm.generate(prompt)
                latency_ms = (time.monotonic() - start) * 1000

                record = build_generation_record(
                    llm_response=llm_response,
                    model=model,
                    prompt_text=prompt_text,
                    latency_ms=latency_ms,
                )
                layers = PromptLayerMetadata(
                    prompt_layer_set_id=request.payload.get("prompt_layer_set_id", "PLS-dev"),
                    layers=(
                        PromptLayer(layer_type="system", layer_id="system-dev"),
                        PromptLayer(layer_type="task", layer_id="task-dev"),
                    ),
                )
                self.llm_observability.record_generation(ctx_task, record, layers)

            # Task completed
            self.llm_observability.record_event(
                ctx_task,
                StructuredEvent(
                    name="task.completed",
                    message=f"Task {getattr(envelope, 'task_id', 'unknown')} completed",
                ),
            )
            return {"status": "ok"}

        except Exception as exc:
            # Task failed
            self.llm_observability.record_event(
                ctx_task,
                StructuredEvent(
                    name="task.failed",
                    message=f"Task {getattr(envelope, 'task_id', 'unknown')} failed: {exc}",
                    level="error",
                ),
            )
            raise

        finally:
            self.llm_observability.end_task_span(ctx_task)
