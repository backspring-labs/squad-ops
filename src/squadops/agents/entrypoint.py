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

        logger.info(
            "Initializing agent runner",
            extra={"role": role, "agent_id": self.agent_id},
        )

    async def start(self) -> None:
        """Start the agent.

        Bootstraps the system, connects to queue, and starts consuming tasks.
        """
        try:
            # Bootstrap system
            self.system = await self._create_system()
            logger.info(
                "System bootstrapped",
                extra={
                    "skills": len(self.system.skill_registry.list_skills()),
                    "handlers": len(self.system.handler_registry.list_capabilities()),
                },
            )

            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

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

        # Shutdown system
        if self.system:
            await self.system.shutdown()

        logger.info("Agent stopped", extra={"agent_id": self.agent_id})

    async def _create_system(self) -> SquadOpsSystem:
        """Create and configure the SquadOps system.

        Creates all port adapters and bootstraps the system.
        """
        from squadops.bootstrap import create_system, SystemConfig
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
        from adapters.llm.factory import create_llm_provider
        from adapters.memory.factory import create_memory_provider
        from adapters.tools.local_filesystem import LocalFileSystemAdapter

        # For ports without adapters yet, use no-op implementations
        from squadops.ports.comms import NoOpQueuePort
        from squadops.ports.prompts import PromptService
        from adapters.prompts import create_prompt_repository
        from adapters.telemetry.factory import create_telemetry_provider

        # Create LLM adapter
        llm = create_llm_provider(
            base_url=config.llm.url,
            model=config.llm.model,
            timeout=config.llm.timeout,
        )

        # Create memory adapter
        memory = create_memory_provider(
            provider_type="lancedb",
            db_path=os.getenv("MEMORY_DB_PATH", "/app/data/memory_db"),
        )

        # Create prompt service
        prompt_repo = create_prompt_repository()
        prompt_service = PromptService(prompt_repo)

        # Create telemetry (metrics + events)
        metrics, events = create_telemetry_provider(config.telemetry)

        # Create filesystem adapter
        filesystem = LocalFileSystemAdapter(
            root_path=os.getenv("SQUADOPS_BASE_PATH", "/app"),
        )

        # Queue port - use NoOp for now, will be replaced with real adapter
        queue = NoOpQueuePort()

        return {
            "llm": llm,
            "memory": memory,
            "prompt_service": prompt_service,
            "queue": queue,
            "metrics": metrics,
            "events": events,
            "filesystem": filesystem,
        }

    async def _consume_tasks(self) -> None:
        """Consume tasks from the queue.

        Connects to RabbitMQ and processes incoming tasks through the orchestrator.
        """
        logger.info(
            "Starting task consumer",
            extra={"agent_id": self.agent_id, "role": self.role},
        )

        # For now, just wait for shutdown
        # TODO: Implement actual queue consumption when QueuePort adapter is ready
        while not self._shutdown_event.is_set():
            await asyncio.sleep(1)

        logger.info("Task consumer stopped")

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
            except asyncio.TimeoutError:
                pass  # Continue loop

    async def _send_heartbeat(self) -> None:
        """Send a single heartbeat."""
        # TODO: Implement actual heartbeat sending via HeartbeatReporter
        logger.debug("Heartbeat", extra={"agent_id": self.agent_id})


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
