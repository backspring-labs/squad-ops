#!/usr/bin/env python3
"""
SquadOps Agent Entry Point - Container execution bootstrap.

This is the main entry point for agent containers. It:
1. Loads configuration from environment/files
2. Creates adapters for all required ports
3. Bootstraps the SquadOpsSystem
4. Connects to RabbitMQ for task consumption
5. Routes tasks through the orchestrator
6. Manages heartbeats and lifecycle

Usage:
    SQUADOPS_AGENT_ROLE=lead python -m squadops.agents.entrypoint

Part of SIP-0.8.8 Phase 6.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from typing import TYPE_CHECKING

# Configure logging early
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from squadops.bootstrap.system import SquadOpsSystem


def load_instance_config(agent_id: str) -> dict | None:
    """Load instance configuration for the given agent.

    Args:
        agent_id: Agent identifier (e.g., 'max', 'neo')

    Returns:
        Instance configuration dict or None if not found
    """
    from pathlib import Path

    import yaml

    # Try multiple paths for instances.yaml
    search_paths = [
        Path("/app/agents/instances/instances.yaml"),  # Container path
        Path("agents/instances/instances.yaml"),  # Local path
        Path(os.getenv("SQUADOPS_BASE_PATH", ".")) / "agents/instances/instances.yaml",
    ]

    for instances_path in search_paths:
        if instances_path.exists():
            try:
                with open(instances_path) as f:
                    data = yaml.safe_load(f)

                for instance in data.get("instances", []):
                    if instance.get("id") == agent_id:
                        return instance
            except Exception as e:
                logger.warning(f"Failed to load instances from {instances_path}: {e}")

    return None


class AgentRunner:
    """Runs an agent within a container.

    Manages the full lifecycle:
    - System bootstrap
    - Queue connection
    - Task consumption
    - Heartbeat reporting
    - Graceful shutdown
    """

    def __init__(self, role: str, agent_id: str | None = None):
        """Initialize agent runner.

        Args:
            role: Agent role (lead, dev, qa, strat, data)
            agent_id: Optional agent identifier (defaults to role-based)
        """
        self.role = role
        self.agent_id = agent_id or os.getenv("SQUADOPS__AGENT__ID", f"{role}-001")
        self.system: SquadOpsSystem | None = None
        self._shutdown_event = asyncio.Event()
        self._heartbeat_task: asyncio.Task | None = None
        self._heartbeat_reporter = None
        self._lifecycle_state = "STARTING"
        self._queue = None

        # Load instance-specific configuration (required)
        self._instance_config = load_instance_config(self.agent_id)
        if not self._instance_config:
            raise ValueError(
                f"No instance configuration found for agent '{self.agent_id}'. "
                "Ensure the agent is defined in agents/instances/instances.yaml"
            )

        self._display_name = self._instance_config.get("display_name", self.agent_id)
        self._llm_model = self._instance_config.get("model")
        self._description = self._instance_config.get("description", "")

        if not self._llm_model:
            raise ValueError(
                f"No model configured for agent '{self.agent_id}' in instances.yaml. "
                "Each agent must have a 'model' field specified."
            )

        logger.info(
            "Loaded instance config",
            extra={
                "agent_id": self.agent_id,
                "display_name": self._display_name,
                "model": self._llm_model,
                "description": self._description,
            },
        )

        logger.info(
            "Initializing agent runner",
            extra={"role": role, "agent_id": self.agent_id},
        )

    async def start(self) -> None:
        """Start the agent.

        Bootstraps the system, connects to queue, and starts consuming tasks.
        """
        try:
            # Create heartbeat reporter
            from adapters.observability.healthcheck_http import HealthCheckHttpReporter

            self._heartbeat_reporter = HealthCheckHttpReporter()

            # Bootstrap system
            self.system = await self._create_system()
            logger.info(
                "System bootstrapped",
                extra={
                    "skills": len(self.system.skill_registry.list_skills()),
                    "handlers": len(self.system.handler_registry.list_capabilities()),
                },
            )

            # Update lifecycle state to READY and send initial heartbeat
            self._lifecycle_state = "READY"

            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Start A2A messaging server if wired (SIP-0085 P2-RC3)
            if self.system and self.system.ports.messaging is not None:
                await self.system.ports.messaging.start()
                logger.info(
                    "A2A messaging server started",
                    extra={"agent_id": self.agent_id},
                )

            # Start consuming tasks
            await self._consume_tasks()

        except Exception as e:
            logger.exception("Failed to start agent", extra={"error": str(e)})
            raise

    async def stop(self) -> None:
        """Stop the agent gracefully."""
        logger.info("Stopping agent", extra={"agent_id": self.agent_id})

        self._shutdown_event.set()

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop A2A messaging server (SIP-0085)
        if self.system and self.system.ports.messaging is not None:
            await self.system.ports.messaging.stop()
            logger.info("A2A messaging server stopped", extra={"agent_id": self.agent_id})

        # Shutdown system
        if self.system:
            await self.system.shutdown()

        logger.info("Agent stopped", extra={"agent_id": self.agent_id})

    async def _create_system(self) -> SquadOpsSystem:
        """Create and configure the SquadOps system.

        Creates all port adapters and bootstraps the system.
        """
        from squadops.bootstrap import SystemConfig, create_system
        from squadops.config import load_config

        # Load configuration
        config = load_config()

        # Create adapters based on configuration
        ports = await self._create_ports(config)

        # Create system
        system_config = SystemConfig(
            roles=[self.role],
            enable_warmboot=True,
        )

        return create_system(
            **ports,
            config=system_config,
        )

    async def _create_ports(self, config) -> dict:
        """Create all port adapters from configuration.

        Args:
            config: Application configuration

        Returns:
            Dictionary of port instances ready for system creation
        """
        # Import adapter factories
        # Import adapters
        from adapters.comms.rabbitmq import RabbitMQAdapter
        from adapters.llm.factory import create_llm_provider
        from adapters.memory.factory import create_memory_provider
        from adapters.prompts import create_prompt_repository
        from adapters.telemetry.factory import (
            create_llm_observability_provider,
            create_telemetry_provider,
        )
        from adapters.tools.local_filesystem import LocalFileSystemAdapter
        from squadops.prompts.assembler import PromptAssembler

        # Create LLM adapter
        # Priority: instance config model > env var > config
        llm_model = (
            self._llm_model  # From instances.yaml for this agent
            or os.getenv("LLM_MODEL")  # Environment override
            or config.llm.model  # From app config
        )
        if not llm_model:
            raise ValueError(
                f"No LLM model configured for agent '{self.agent_id}'. "
                "Set model in instances.yaml, LLM_MODEL env var, or config.llm.model"
            )
        logger.info(f"Using LLM model: {llm_model}", extra={"agent_id": self.agent_id})
        llm = create_llm_provider(
            base_url=config.llm.url,
            default_model=llm_model,
            timeout_seconds=config.llm.timeout,
        )

        # Create memory adapter
        memory = create_memory_provider(
            provider_type="lancedb",
            db_path=os.getenv("MEMORY_DB_PATH", "/app/data/memory_db"),
        )

        # Create prompt service
        prompt_repo = create_prompt_repository()
        prompt_service = PromptAssembler(prompt_repo)
        self._prompt_service = prompt_service  # Store for use in chat

        # Create request template renderer (SIP-0084)
        request_renderer = None
        try:
            from adapters.prompts.factory import create_prompt_asset_source
            from squadops.prompts.renderer import RequestTemplateRenderer

            provider = config.prompts.asset_source_provider
            if provider == "langfuse":
                asset_source = create_prompt_asset_source(
                    provider="langfuse",
                    public_key=config.langfuse.public_key,
                    secret_key=config.langfuse.secret_key,
                    host=config.langfuse.host,
                )
            else:
                asset_source = create_prompt_asset_source(provider="filesystem")
            request_renderer = RequestTemplateRenderer(asset_source)
            logger.info(
                "Request template renderer initialized",
                extra={"provider": provider, "agent_id": self.agent_id},
            )
        except Exception as exc:
            logger.warning(
                "Failed to create request renderer, using fallback prompts: %s",
                exc,
                extra={"agent_id": self.agent_id},
            )

        # Create telemetry (metrics + events)
        telemetry_backend = config.telemetry.backend if config.telemetry.backend else "otel"
        metrics, events = create_telemetry_provider(telemetry_backend)

        # Create LLM observability (SIP-0061)
        llm_observability = create_llm_observability_provider(config=config.langfuse)

        # Create filesystem adapter
        filesystem = LocalFileSystemAdapter()

        # Create RabbitMQ queue adapter
        rabbitmq_url = config.comms.rabbitmq.url
        queue = RabbitMQAdapter(url=rabbitmq_url)
        self._queue = queue  # Store for use in _consume_tasks

        # Conditionally wire A2A messaging (SIP-0085 P2-RC6)
        messaging = None
        if self._instance_config.get("a2a_messaging_enabled", False):
            try:
                from adapters.comms.a2a_server import (
                    A2AServerAdapter,
                    AgentCardConfig,
                    build_agent_card,
                )
                from adapters.comms.chat_executor import ChatAgentExecutor
                from squadops import __version__ as SQUADOPS_VERSION
                from squadops.agents.base import PortsBundle

                # 1. Build PortsBundle without messaging
                ports_without_messaging = PortsBundle(
                    llm=llm,
                    memory=memory,
                    prompt_service=prompt_service,
                    queue=queue,
                    metrics=metrics,
                    events=events,
                    filesystem=filesystem,
                    llm_observability=llm_observability,
                    request_renderer=request_renderer,
                    messaging=None,
                )

                # 2. Create executor with the bundle
                chat_executor = ChatAgentExecutor(
                    ports=ports_without_messaging,
                    role_id=self.role,
                )

                # 3. Build agent card and create server adapter
                a2a_port = self._instance_config.get("a2a_port", 8080)
                card_config = AgentCardConfig(
                    agent_id=self.agent_id,
                    display_name=self._display_name,
                    description=self._description,
                    version=SQUADOPS_VERSION,
                    port=a2a_port,
                )
                agent_card = build_agent_card(card_config)
                messaging = A2AServerAdapter(
                    agent_card=agent_card,
                    executor=chat_executor,
                    port=a2a_port,
                )

                logger.info(
                    "A2A messaging wired",
                    extra={
                        "agent_id": self.agent_id,
                        "a2a_port": a2a_port,
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Failed to wire A2A messaging: %s",
                    exc,
                    extra={"agent_id": self.agent_id},
                )

        return {
            "llm": llm,
            "memory": memory,
            "prompt_service": prompt_service,
            "queue": queue,
            "metrics": metrics,
            "events": events,
            "filesystem": filesystem,
            "llm_observability": llm_observability,
            "request_renderer": request_renderer,
            "messaging": messaging,
        }

    async def _consume_tasks(self) -> None:
        """Consume tasks from the queue.

        Connects to RabbitMQ and processes incoming tasks through the orchestrator.
        """
        import json

        # Queue name for this agent's communications
        comms_queue = f"{self.agent_id}_comms"

        logger.info(
            "Starting task consumer",
            extra={"agent_id": self.agent_id, "role": self.role, "queue": comms_queue},
        )

        while not self._shutdown_event.is_set():
            try:
                # Consume messages from the comms queue
                messages = await self._queue.consume(comms_queue, max_messages=1)

                for message in messages:
                    try:
                        # Parse the message payload
                        payload = json.loads(message.payload)
                        action = payload.get("action", "")
                        metadata = payload.get("metadata", {})

                        logger.info(
                            "Received message",
                            extra={
                                "agent_id": self.agent_id,
                                "action": action,
                                "message_id": message.message_id,
                            },
                        )

                        # Handle different action types
                        if action == "comms.chat":
                            await self._handle_chat_message(payload, metadata)
                        elif action == "comms.task":
                            await self._handle_task_envelope(payload, metadata)
                        else:
                            logger.warning(
                                f"Unknown action: {action}",
                                extra={"agent_id": self.agent_id},
                            )

                        # Acknowledge the message
                        await self._queue.ack(message)

                    except Exception as e:
                        logger.error(
                            f"Failed to process message: {e}",
                            extra={"agent_id": self.agent_id, "message_id": message.message_id},
                        )
                        # Acknowledge anyway to avoid infinite retries
                        await self._queue.ack(message)

            except Exception as e:
                logger.error(
                    f"Queue consumption error: {e}",
                    extra={"agent_id": self.agent_id},
                )

            # Small delay between consumption cycles
            await asyncio.sleep(0.5)

        # Close queue connection on shutdown
        if self._queue:
            await self._queue.close()

        logger.info("Task consumer stopped")

    def _build_system_prompt(self) -> str:
        """Build system prompt using PromptService for role-specific identity.

        Returns:
            Assembled system prompt with role-specific context

        Raises:
            ValueError: If PromptService is not available or returns invalid prompt
        """
        if not hasattr(self, "_prompt_service") or not self._prompt_service:
            raise ValueError(
                f"PromptService not initialized for agent '{self.agent_id}'. "
                "Cannot build system prompt without proper configuration."
            )

        assembled = self._prompt_service.get_system_prompt(self.role)
        if not assembled or not assembled.content:
            raise ValueError(
                f"No system prompt configured for role '{self.role}'. "
                f"Ensure prompt fragments exist in prompts/fragments/roles/{self.role}/"
            )

        # Add agent-specific context
        agent_context = f"\n\nYou are {self._display_name} (agent ID: {self.agent_id})."
        if self._description:
            agent_context += f"\nRole: {self._description}"

        return assembled.content + agent_context

    async def _handle_chat_message(self, payload: dict, metadata: dict) -> None:
        """Handle incoming chat message from console.

        Args:
            payload: Message payload containing action and message data
            metadata: Message metadata including response_queue and correlation_id
        """
        import json

        message_data = payload.get("payload", {})
        user_message = message_data.get("message", "")
        session_id = message_data.get("session_id", "")
        response_queue = metadata.get("response_queue", "console_responses")
        correlation_id = metadata.get("correlation_id", session_id)

        logger.info(
            f"Processing chat message: {user_message[:50]}...",
            extra={"agent_id": self.agent_id, "session_id": session_id},
        )

        try:
            # Generate response using the LLM
            if self.system and self.system.ports.llm:
                import time
                import uuid

                from squadops.llm.models import LLMRequest

                # Get role-specific system prompt from PromptService
                system_prompt = self._build_system_prompt()

                # Build full prompt with role context and user message
                full_prompt = f"{system_prompt}\n\nUser: {user_message}\n\nAssistant:"

                # Generate response via LLMRequest
                request = LLMRequest(prompt=full_prompt)
                t0 = time.monotonic()
                response = await self.system.ports.llm.generate(request)
                latency_ms = (time.monotonic() - t0) * 1000
                response_text = response.text if hasattr(response, "text") else str(response)

                # Record generation in LangFuse (SIP-0061)
                llm_obs = self.system.ports.llm_observability
                if llm_obs is not None:
                    from squadops.telemetry.models import (
                        CorrelationContext,
                        GenerationRecord,
                        PromptLayer,
                        PromptLayerMetadata,
                    )

                    ctx = CorrelationContext(
                        cycle_id=f"chat-{session_id or correlation_id}",
                        task_id=f"chat-{correlation_id}",
                        agent_id=self.agent_id,
                        agent_role=self.role,
                    )
                    record = GenerationRecord(
                        generation_id=str(uuid.uuid4()),
                        model=self._llm_model,
                        prompt_text=full_prompt,
                        response_text=response_text,
                        latency_ms=latency_ms,
                    )
                    layers = PromptLayerMetadata(
                        prompt_layer_set_id=f"{self.role}-chat",
                        layers=(
                            PromptLayer(layer_type="system", layer_id=f"{self.role}-system"),
                            PromptLayer(layer_type="user", layer_id="console-chat"),
                        ),
                    )
                    # Open trace → task span → generation → close
                    llm_obs.start_cycle_trace(ctx)
                    llm_obs.start_task_span(ctx)
                    llm_obs.record_generation(ctx, record, layers)
                    llm_obs.end_task_span(ctx)
                    llm_obs.end_cycle_trace(ctx)
                    llm_obs.flush()
            else:
                response_text = f"Hello! I'm {self._display_name}. My system is still initializing."

            # Build response message in the format expected by health-check
            from datetime import datetime

            response_message = {
                "action": "comms.chat.response",
                "metadata": {
                    "correlation_id": correlation_id,
                },
                "payload": {
                    "status": "ok",
                    "result": {
                        "response_text": response_text,
                        "agent_name": self.agent_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "available",
                    },
                },
            }

            # Send response to the response queue
            await self._queue.publish(response_queue, json.dumps(response_message))

            logger.info(
                f"Sent chat response to {response_queue}",
                extra={"agent_id": self.agent_id, "session_id": session_id},
            )

        except Exception as e:
            logger.error(
                f"Failed to handle chat message: {e}",
                extra={"agent_id": self.agent_id, "session_id": session_id},
            )

    async def _handle_task_envelope(self, payload: dict, metadata: dict) -> None:
        """Handle incoming task envelope from cycle executor.

        Deserializes the TaskEnvelope, submits to local orchestrator,
        and publishes TaskResult to the reply queue.

        Wraps execution with LangFuse lifecycle (SIP-0061 Option B):
        each agent opens a trace+task span keyed by the shared trace_id
        so all 5 agents' spans merge into one LangFuse trace.
        """
        import json

        from squadops.tasks.models import TaskEnvelope, TaskResult

        envelope_data = payload.get("payload", {})
        reply_queue = metadata.get("reply_queue")

        envelope = TaskEnvelope.from_dict(envelope_data)

        logger.info(
            "Processing task envelope",
            extra={
                "agent_id": self.agent_id,
                "task_id": envelope.task_id,
                "task_type": envelope.task_type,
            },
        )

        # Build correlation context for LangFuse tracing
        from squadops.telemetry.models import CorrelationContext

        ctx = CorrelationContext.from_envelope(
            envelope,
            agent_id=self.agent_id,
            agent_role=self.role,
        )
        llm_obs = self.system.ports.llm_observability if self.system else None

        if llm_obs:
            llm_obs.start_cycle_trace(ctx)
            llm_obs.start_task_span(ctx)

        try:
            if not self.system:
                raise RuntimeError("AgentRunner.system not initialized")
            result = await self.system.orchestrator.submit_task(envelope)
        except Exception as e:
            logger.error(f"Task execution failed: {e}", extra={"task_id": envelope.task_id})
            result = TaskResult(
                task_id=envelope.task_id,
                status="FAILED",
                error=str(e),
            )
        finally:
            if llm_obs:
                llm_obs.end_task_span(ctx)
                llm_obs.end_cycle_trace(ctx)
                llm_obs.flush()

        # Publish result to reply queue
        if reply_queue:
            response = {
                "action": "comms.task.result",
                "metadata": {"correlation_id": envelope.correlation_id},
                "payload": result.to_dict(),
            }
            await self._queue.publish(reply_queue, json.dumps(response))
        else:
            logger.warning(
                "No reply_queue in metadata, result dropped",
                extra={"task_id": envelope.task_id},
            )

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats.

        Reports agent status to the health dashboard.
        """
        heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

        while not self._shutdown_event.is_set():
            try:
                await self._send_heartbeat()
            except Exception as e:
                logger.warning(
                    "Failed to send heartbeat",
                    extra={"error": str(e), "agent_id": self.agent_id},
                )

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=heartbeat_interval,
                )
                break  # Shutdown requested
            except TimeoutError:
                pass  # Continue loop

    async def _send_heartbeat(self) -> None:
        """Send a single heartbeat."""
        if not self._heartbeat_reporter:
            return

        from squadops import __version__ as SQUADOPS_VERSION

        await self._heartbeat_reporter.send_status(
            agent_id=self.agent_id,
            lifecycle_state=self._lifecycle_state,
            version=SQUADOPS_VERSION,
        )
        logger.debug(
            "Heartbeat sent", extra={"agent_id": self.agent_id, "state": self._lifecycle_state}
        )


def setup_signal_handlers(runner: AgentRunner) -> None:
    """Setup signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info(f"Received signal {sig.name}, initiating shutdown")
        loop.create_task(runner.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))


async def main() -> int:
    """Main entry point."""
    # Get role from environment
    role = os.getenv("SQUADOPS_AGENT_ROLE")
    if not role:
        # Try to infer from SQUADOPS__AGENT__ID
        agent_id = os.getenv("SQUADOPS__AGENT__ID", "")
        if agent_id:
            # Map agent IDs to roles (max -> lead, neo -> dev, etc.)
            agent_role_map = {
                "max": "lead",
                "neo": "dev",
                "bob": "builder",
                "eve": "qa",
                "nat": "strat",
                "data": "data",
            }
            role = agent_role_map.get(agent_id.lower(), agent_id.split("-")[0])
        else:
            logger.error("SQUADOPS_AGENT_ROLE or SQUADOPS__AGENT__ID must be set")
            return 1

    logger.info(f"Starting agent with role: {role}")

    runner = AgentRunner(role=role)
    setup_signal_handlers(runner)

    try:
        await runner.start()
        return 0
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await runner.stop()
        return 0
    except Exception as e:
        logger.exception(f"Agent failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
