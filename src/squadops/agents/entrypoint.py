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
from collections.abc import Awaitable, Iterable
from typing import TYPE_CHECKING, Any

from squadops.tasks.models import TaskEnvelope, TaskResultStatus

# Configure logging early.
# LOG_LEVEL (and MEMORY_DB_PATH / HEARTBEAT_INTERVAL below) are bare-env
# *operational* knobs with sensible defaults — deliberately distinct from the
# SQUADOPS__* nested-config convention and NOT the config-masking class #333
# targets: they are optional tuning values, not required data, and a wrong value
# fails visibly rather than fabricating something that looks correct. Required
# identity (agent id / role) is the opposite — never defaulted (see AgentRunner
# and _resolve_role).
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from squadops.bootstrap.system import SquadOpsSystem
    from squadops.comms.queue_message import QueueMessage
    from squadops.ports.observability import LogForwarderPort


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


class _RunCancelledSkip(Exception):
    """A dispatched task this agent dropped because its run was cancelled (#1648)."""


class CancelledRuns:
    """The runs this agent has been told are cancelled, and the task it is running now (#1648).

    A notice names runs; the agent drops a queued task of one before it starts, and cancels
    the one it is running. Entries expire after a day: a run id never recurs, and the set
    must not grow for the life of the container.
    """

    TTL_SECONDS = 24 * 60 * 60

    def __init__(self) -> None:
        self._told_at: dict[str, float] = {}
        self._running: tuple[str, asyncio.Task] | None = None
        self._stopped: set[asyncio.Task] = set()

    def add(self, run_ids: Iterable[str], now: float) -> str | None:
        """Record the notice; cancel the running task if it belongs to one of the runs, and
        return that run's id."""
        for run_id in run_ids:
            self._told_at[run_id] = now
        self._told_at = {r: t for r, t in self._told_at.items() if now - t < self.TTL_SECONDS}
        if self._running is not None and self._running[0] in self._told_at:
            run_id, task = self._running
            self._stopped.add(task)
            task.cancel()
            return run_id
        return None

    def is_cancelled(self, run_id: str | None) -> bool:
        return bool(run_id) and run_id in self._told_at

    async def run(self, run_id: str | None, coro: Awaitable[Any]) -> Any:
        """Run ``coro`` as the current task; raise ``_RunCancelledSkip`` if a notice stopped it."""
        task = asyncio.ensure_future(coro)
        self._running = (run_id, task) if run_id else None
        try:
            return await task
        except asyncio.CancelledError:
            if task in self._stopped:
                raise _RunCancelledSkip from None
            raise
        finally:
            self._running = None
            self._stopped.discard(task)


def declared_task_bound(envelope: TaskEnvelope) -> float:
    """How long this agent lets a dispatched task's handler run: the orchestrator's declared
    per-task wait, which the dispatcher stamps on the envelope (1.8.2 plan §3.2 item 15).

    It was ``llm.timeout``: the model-call timeout bounding a whole task on the agent's side,
    as it once did on the orchestrator's, so the two sides of one hang could end it at
    different times. An envelope that carries no declared wait is refused, never bounded by a
    default: it comes from a runtime API older than this change.
    """
    if envelope.timeout is None:
        raise ValueError(
            f"task {envelope.task_id} carries no declared timeout — a runtime API older than "
            "1.8.2 item 15; refused rather than bounded by llm.timeout"
        )
    return float(envelope.timeout)


class AgentRunner:
    """Runs an agent within a container.

    Manages the full lifecycle:
    - System bootstrap
    - Queue connection
    - Task consumption
    - Heartbeat reporting
    - Graceful shutdown
    """

    def __init__(
        self, role: str, agent_id: str | None = None, served_roles: list[str] | None = None
    ):
        """Initialize agent runner.

        Args:
            role: Agent role (lead, dev, qa, strat, data)
            agent_id: Agent identifier. When omitted it is read from the required
                ``SQUADOPS__AGENT__ID`` env var — never fabricated (identity is not
                defaulted).

        Raises:
            ValueError: if no agent id is provided or set in the environment.
        """
        self.role = role
        #: The step roles this process registers handlers for (SIP-0108 §10i item 2). ``role``
        #: is what the agent IS and drives its prompt and telemetry; this is what it DOES.
        self.served_roles = list(served_roles) if served_roles else [role]
        # Identity is required, never fabricated. Defaulting the id (the former
        # f"{role}-001") masks a missing SQUADOPS__AGENT__ID and misdirects
        # diagnosis to the instance-config load below — which fails with a
        # confusing "no instance configuration for 'lead-001'" instead of naming
        # the real cause (#333, the _get_default_instances() masking class).
        self.agent_id = agent_id or os.getenv("SQUADOPS__AGENT__ID")
        if not self.agent_id:
            raise ValueError(
                "Agent ID is not configured — set SQUADOPS__AGENT__ID. "
                "Agent identity is never defaulted."
            )
        self.system: SquadOpsSystem | None = None
        self._shutdown_event = asyncio.Event()
        self._heartbeat_task: asyncio.Task | None = None
        self._heartbeat_reporter = None
        self._service_token_client = None
        self._lifecycle_state = "STARTING"
        self._queue = None
        self._config = None
        self._log_forwarder: LogForwarderPort | None = None

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
        from squadops.bootstrap.secrets import secret_provider_for
        from squadops.config import load_config

        # Single config load — reused by log-forwarder install and _create_system.
        self._config = load_config(secret_provider_factory=secret_provider_for)

        try:
            # Install the log forwarder before bootstrap so handler/system logs
            # from the rest of startup are routed by the configured backend
            # (SIP-0087). Always-inject pattern — NoOp when disabled.
            self._log_forwarder = await self._create_log_forwarder(self._config)

            # Create heartbeat reporter (authed /api/v1 lane, #326)
            self._heartbeat_reporter = self._create_heartbeat_reporter(self._config)

            # Bootstrap system
            self.system = await self._create_system()
            logger.info(
                "System bootstrapped",
                extra={
                    "handlers": len(self.system.handler_registry.list_task_types()),
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
            # Tear down the log forwarder if startup failed after install,
            # otherwise its flush task and any HTTP client leak.
            if self._log_forwarder is not None:
                try:
                    await self._log_forwarder.aclose()
                finally:
                    self._log_forwarder = None
            raise

    async def _create_log_forwarder(self, config) -> LogForwarderPort:
        """Build the log forwarder via factory (SIP-0087)."""
        from adapters.observability.log_forwarder import create_log_forwarder

        return await create_log_forwarder(config.prefect)

    def _create_heartbeat_reporter(self, config):
        """Build the heartbeat reporter (#326).

        Status writes live on the authed /api/v1 lane: when an agent service
        identity is configured (auth.agent_client + auth.oidc), heartbeats
        carry a Bearer token acquired via client credentials; otherwise they
        go out unauthenticated — valid only for auth-disabled deployments.

        Raises:
            ValueError: agent_client is configured without the oidc section
                needed to reach the token endpoint (misconfiguration must
                surface, not degrade to anonymous heartbeats).
        """
        from adapters.observability.healthcheck_http import HealthCheckHttpReporter

        auth_cfg = config.auth
        token_provider = None
        if auth_cfg.agent_client is not None:
            if auth_cfg.oidc is None:
                raise ValueError(
                    "auth.agent_client is configured but auth.oidc is missing — "
                    "the OIDC issuer_url is required to acquire service tokens. "
                    "Set SQUADOPS__AUTH__OIDC__ISSUER_URL (and AUDIENCE) or unset "
                    "SQUADOPS__AUTH__AGENT_CLIENT__*."
                )
            from adapters.auth.factory import create_service_token_client

            self._service_token_client = create_service_token_client(
                "agent",
                auth_cfg.agent_client,
                auth_cfg.oidc,
            )
            token_provider = self._service_token_client.get_token
            logger.info(
                "Agent service identity configured for heartbeats",
                extra={
                    "agent_id": self.agent_id,
                    "client_id": auth_cfg.agent_client.client_id,
                },
            )

        return HealthCheckHttpReporter(token_provider=token_provider)

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

        # Tear down log forwarder (SIP-0087)
        if self._log_forwarder is not None:
            await self._log_forwarder.aclose()
            self._log_forwarder = None

        # Release the service-token client's HTTP session (#326)
        if self._service_token_client is not None:
            await self._service_token_client.close()
            self._service_token_client = None

        logger.info("Agent stopped", extra={"agent_id": self.agent_id})

    async def _create_system(self) -> SquadOpsSystem:
        """Create and configure the SquadOps system.

        Creates all port adapters and bootstraps the system.
        """
        from squadops.bootstrap import SystemConfig, create_system
        from squadops.config import load_config

        # Reuse config loaded by start(); only load if invoked standalone.
        if self._config is None:
            self._config = load_config()
        config = self._config

        # Create adapters based on configuration
        ports = await self._create_ports(config)

        # Create system
        system_config = SystemConfig(
            role=self.role,
            roles=list(self.served_roles),
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
        from adapters.comms.factory import create_a2a_server, create_queue_adapter
        from adapters.llm.factory import create_llm_provider
        from adapters.memory.factory import create_memory_provider
        from adapters.prompts import create_prompt_repository
        from adapters.telemetry.factory import (
            create_llm_observability_provider,
            create_telemetry_provider,
        )
        from adapters.tools.factory import create_filesystem_provider
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
        # #930: this is the adapter's FALLBACK, not the model the agent will use. Cycle
        # tasks carry a model from the squad profile and every handler resolves
        # `agent_model or context.ports.llm.default_model`, so the profile wins and this
        # value is reached only by a call that names none. Logging it as "Using LLM model"
        # asserted the opposite: on 2026-08-30 the data agent announced
        # "Using LLM model: qwen2.5:3b-instruct" and then ran the whole cycle on a 27B,
        # which is exactly the kind of line someone reads while debugging a model problem.
        logger.info(
            f"LLM fallback model: {llm_model} "
            f"(used only when a task names no model; squad-profile models take precedence)",
            extra={"agent_id": self.agent_id},
        )
        llm = create_llm_provider(
            provider=config.llm.provider,
            base_url=config.llm.url,
            default_model=llm_model,
            timeout_seconds=config.llm.timeout,
            api_key=config.llm.api_key,
        )

        # Create memory adapter
        # #1449: this call named its selector ``provider_type``, a keyword the factory does
        # not have — it fell into ``**config`` and the ``"lancedb"`` default decided.
        memory = create_memory_provider(
            provider="lancedb",
            # Operational default (see the LOG_LEVEL note) — intentional, not
            # masked required config (#333).
            db_path=os.getenv("MEMORY_DB_PATH", "/app/data/memory_db"),
        )

        # Create prompt service
        prompt_repo = create_prompt_repository("filesystem")  # no config field selects it
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
                # #1568: the configured name, never a quiet "filesystem". The schema's Literal
                # refuses an unknown name at config load, so the ``except`` below only ever
                # sees a construction failure (a missing SDK, an unreachable registry).
                asset_source = create_prompt_asset_source(provider=provider)
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

        # #352: when the asset source is the registry, boot refuses a registry that lacks
        # an asset this image ships — outside the try above, because a stale registry is
        # not a degraded renderer to fall back from (that fallback is the #1110 blindness),
        # it is the wrong deploy, and the agent must say so before it takes a task.
        if request_renderer is not None and config.prompts.asset_source_provider == "langfuse":
            from squadops.prompts.registry_check import verify_registry_serves_shipped_assets

            await verify_registry_serves_shipped_assets(
                asset_source, role=self.role, provider="langfuse"
            )

        # Create telemetry (metrics + events). The selector is required by the schema (#1568),
        # so an unset backend never reaches this root.
        metrics, events = create_telemetry_provider(config.telemetry.backend)

        # Create LLM observability (SIP-0061). LangFuse is its only provider and no config
        # field selects it, so the root names it — the artifact vault's shape (#1449).
        llm_observability = create_llm_observability_provider(
            "langfuse",
            config=config.langfuse,
            prompt_asset_provider=config.prompts.asset_source_provider,
        )

        # #301 (§6.4): through the factory, selector required. allowed_roots=None and
        # production_mode=False are the constructor defaults this root relied on when it
        # built the local adapter directly — there is no agent workspace-root
        # configuration today (schema.py's workspace_root is the sandbox's). Named, not
        # changed: tightening the roots is its own decision.
        filesystem = create_filesystem_provider(
            provider=config.tools.filesystem.provider, allowed_roots=None, production_mode=False
        )

        # Create RabbitMQ queue adapter. prefetch_count=1 (#323): the broker
        # hands this agent one unacked comms message at a time, matching the
        # old poll loop's one-at-a-time pickup.
        queue = create_queue_adapter(config.comms, prefetch_count=1)  # #301 (§6.2)
        self._queue = queue  # Store for use in _consume_tasks

        # Conditionally wire A2A messaging (SIP-0085 P2-RC6)
        messaging = None
        if self._instance_config.get("a2a_messaging_enabled", False):
            try:
                from adapters.comms.a2a_server import (
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
                messaging = create_a2a_server(  # #301 (§6.3)
                    config.comms, agent_card=agent_card, executor=chat_executor, port=a2a_port
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
        """Consume comms messages via a persistent push consumer (#323).

        Registers a single long-lived ``subscribe()`` consumer on the agent's
        comms queue — the broker delivers each message the moment it arrives,
        with no per-poll ``basic.consume``/``basic.cancel`` churn — then parks
        until shutdown is requested.
        """
        # Queue name for this agent's communications
        comms_queue = f"{self.agent_id}_comms"
        replies_queue = f"{self.agent_id}_replies"

        logger.info(
            "Starting task consumer",
            extra={"agent_id": self.agent_id, "role": self.role, "queue": comms_queue},
        )

        # SIP-0094 (D9): declare this agent's reply queue before the orchestrator
        # ever addresses it. The agent only publishes to `{agent_id}_replies`
        # (never consumes from it), so the lazy declaration that covers the comms
        # queue won't create it. Idempotent — safe to call on every boot.
        await self._queue.ensure_queue(replies_queue)

        # The subscription layer owns the ack: each delivery is acked after
        # _process_comms_message returns — success or failure — preserving the
        # old poll loop's ack-always policy. subscribe() re-establishes the
        # consumer itself if the channel drops.
        subscription = await self._queue.subscribe(
            comms_queue, on_message=self._process_comms_message
        )
        # #1648: the control queue, consumed beside the comms queue — a cancel notice must
        # reach this agent while its comms consumer is busy with the task it cancels.
        from squadops.comms.run_cancellation import control_queue

        control = await self._queue.subscribe(
            control_queue(self.agent_id), on_message=self._process_control_message
        )

        try:
            await self._shutdown_event.wait()
        finally:
            # Cancel the consumer before closing the connection, so the
            # subscription's resubscribe loop can't race the teardown.
            await control.cancel()
            await subscription.cancel()
            if self._queue:
                await self._queue.close()

        logger.info("Task consumer stopped")

    @property
    def _cancelled_runs(self) -> CancelledRuns:
        # Lazily, so a runner built without __init__ (the tests' fixtures) still has one.
        state = self.__dict__.get("_cancelled_runs_state")
        if state is None:
            state = self.__dict__["_cancelled_runs_state"] = CancelledRuns()
        return state

    async def _process_control_message(self, message: QueueMessage) -> None:
        """A cancel notice for runs this agent may hold (#1648). Never raises, like the comms
        callback: a malformed control message is logged and acked."""
        import json
        import time

        from squadops.comms.run_cancellation import cancelled_run_ids

        try:
            run_ids = cancelled_run_ids(json.loads(message.payload))
        except (ValueError, TypeError):
            logger.warning("control: malformed message dropped", extra={"agent_id": self.agent_id})
            return
        if not run_ids:
            return
        stopped = self._cancelled_runs.add(run_ids, time.monotonic())
        logger.info(
            "run_cancelled notice: runs=%s%s (#1648)",
            ",".join(sorted(run_ids)),
            f" — stopping the running task of {stopped}" if stopped else "",
            extra={"agent_id": self.agent_id},
        )

    async def _process_comms_message(self, message: QueueMessage) -> None:
        """Route one comms delivery to its action handler.

        Callback for the persistent ``subscribe()`` consumer (#323). Never
        raises: failures are logged with agent context and swallowed, so the
        subscription acks the message and keeps consuming — the same outcome
        the old poll loop's ack-on-error path produced. It must not ack
        either; the subscription layer acks every delivery after this returns.
        """
        import json

        try:
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
                # SIP-0094 D12 says a failing callback is acked because requeuing
                # "would only poison-loop". That policy is enforceable only when the
                # callback RETURNS: if the process DIES mid-task the broker never saw an
                # ack, requeues, and the loop D12 forbids arrives through a door D12 does
                # not cover. #1626: the qa agent segfaulted inside a repair handler and was
                # restarted 37 times on the same redelivered message. The provable facts:
                # no handler result ever reached the correction / deadlock (#1221) /
                # repeated-signature machinery, the run stayed `running`, and each
                # restarted agent took the poisoned delivery again. Not every termination
                # mechanism depends on a handler returning — `TaskDispatcher`'s task
                # timeout does not — so the claim is scoped to the rules that consume a
                # handler RESULT.
                #
                # `redelivered` proves only that a prior delivery was NOT ACKNOWLEDGED. It
                # does not prove the work did not happen: the ack follows the callback, so
                # the connection can close before the callback runs, during the work, or
                # AFTER the work and its reply succeeded — and the broker may mark a message
                # redelivered that never reached the prior consumer. The prior delivery's
                # completion is therefore UNKNOWN.
                #
                # With completion unknown the broker layer is the wrong place to decide:
                # re-executing risks unbudgeted duplicate work and, per #1626, can be fatal
                # and unbounded; discarding risks losing work. Recording a typed FAILED for
                # the original task id puts the uncertainty where it can be reasoned about
                # and leaves the retry to the only layer with a budget and a record.
                if message.attributes.get("redelivered"):
                    await self._refuse_redelivered_task(payload, metadata)
                else:
                    await self._handle_task_envelope(payload, metadata)
            else:
                logger.warning(
                    f"Unknown action: {action}",
                    extra={"agent_id": self.agent_id},
                )

        except Exception as e:
            logger.error(
                f"Failed to process message: {e}",
                extra={"agent_id": self.agent_id, "message_id": message.message_id},
            )

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
                        PromptLayer,
                        PromptLayerMetadata,
                        build_generation_record,
                    )

                    ctx = CorrelationContext(
                        cycle_id=f"chat-{session_id or correlation_id}",
                        task_id=f"chat-{correlation_id}",
                        agent_id=self.agent_id,
                        agent_role=self.role,
                    )
                    record = build_generation_record(
                        model=self._llm_model,
                        prompt_text=full_prompt,
                        response_text=response_text,
                        latency_ms=latency_ms,
                        usage=response,
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

    async def _refuse_redelivered_task(self, payload: dict, metadata: dict) -> None:
        """Fail a redelivered task instead of running it again (SIP §5.3a, #1626).

        A redelivery means a prior delivery went unacknowledged — **not** that the work did
        not happen. It may have completed and replied before the connection closed, and the
        broker may mark a message redelivered that never reached the prior consumer. The
        prior delivery's completion is UNKNOWN, so this refuses to decide at the broker
        layer: the round is failed for the original task id and the cycle's recorded budget
        decides any retry. Running it again is what produced #1626's 37 restarts.

        Scope is task dispatch only; `comms.chat` is untouched. The message is acked by the
        subscription layer when this returns, which is what stops the loop.
        """
        import json

        from squadops.tasks.models import TaskResult, TaskResultStatus

        # Read the two fields the refusal needs straight from the envelope dict rather
        # than constructing a TaskEnvelope: the whole point of this path is that the
        # previous attempt died, so it must not itself depend on the envelope being
        # well-formed enough to build. A refusal that throws leaves the cycle with
        # silence, which is the failure it exists to prevent.
        envelope_data = payload.get("payload", {}) or {}
        task_id = str(envelope_data.get("task_id") or "unknown")
        task_type = str(envelope_data.get("task_type") or "unknown")
        correlation_id = envelope_data.get("correlation_id") or metadata.get("correlation_id")
        reply_queue = metadata.get("reply_queue")

        logger.error(
            "redelivered_task_refused: task=%s type=%s — a prior delivery was not "
            "acknowledged, so its completion is UNKNOWN (it may have died, or may have "
            "completed and replied before the ack); refused at the broker layer and failed "
            "for cycle governance to decide (SIP §5.3a, #1626)",
            task_id,
            task_type,
            extra={"agent_id": self.agent_id, "task_id": task_id, "task_type": task_type},
        )

        result = TaskResult(
            task_id=task_id,
            status=TaskResultStatus.FAILED,
            error=(
                "redelivered: a prior delivery of this task was not acknowledged, so its "
                "completion is unknown — it may have died, or may have completed and "
                "replied before the ack. Refused at the broker layer rather than re-run; "
                "the correction budget governs any retry (SIP §5.3a, #1626)"
            ),
        )
        if reply_queue:
            await self._queue.publish(
                reply_queue,
                json.dumps(
                    {
                        "action": "comms.task.result",
                        "metadata": {"correlation_id": correlation_id},
                        "payload": result.to_dict(),
                    }
                ),
            )
        else:
            logger.warning(
                "No reply_queue in metadata, refusal result dropped",
                extra={"task_id": task_id},
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

        # #1648: a task of a run already cancelled is dropped before it runs. Acked (the
        # subscription acks after this returns), never replied to: nothing awaits it.
        from squadops.comms.run_cancellation import RUN_ID_METADATA_KEY

        run_id = (envelope.metadata or {}).get(RUN_ID_METADATA_KEY)
        if self._cancelled_runs.is_cancelled(run_id):
            logger.info(
                "task_skipped: run cancelled task=%s run=%s — dropped before it ran (#1648)",
                envelope.task_id,
                run_id,
                extra={"agent_id": self.agent_id},
            )
            return

        # Build correlation context for LLM-observability tracing and
        # task-scoped log forwarding (SIP-0087).
        from squadops.telemetry.context import use_correlation_context, use_run_ids
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

        # SIP-0087 B1: scope the contextvar so handler logs emitted during
        # submit_task carry flow_run_id / task_run_id. The active log
        # forwarder reads these from the contextvar; when no forwarder is
        # configured the IDs are inert. Envelope fields default to "" when
        # the runtime-api executor has no run IDs to attach.
        flow_run_id = envelope.flow_run_id or None
        task_run_id = envelope.task_run_id or None

        skipped = False
        try:
            if not self.system:
                raise RuntimeError("AgentRunner.system not initialized")
            orchestrator = self.system.orchestrator
            bound = declared_task_bound(envelope)
            with use_correlation_context(ctx):
                # #1648: run as the current task, so a cancel notice for its run stops it here.
                if flow_run_id is not None or task_run_id is not None:
                    with use_run_ids(flow_run_id=flow_run_id, task_run_id=task_run_id):
                        result = await self._cancelled_runs.run(
                            run_id, orchestrator.submit_task(envelope, timeout_seconds=bound)
                        )
                else:
                    result = await self._cancelled_runs.run(
                        run_id, orchestrator.submit_task(envelope, timeout_seconds=bound)
                    )
        except _RunCancelledSkip:
            skipped = True
            logger.info(
                "task_skipped: run cancelled task=%s run=%s — stopped mid-task (#1648)",
                envelope.task_id,
                run_id,
                extra={"agent_id": self.agent_id},
            )
        except Exception as e:
            logger.error(f"Task execution failed: {e}", extra={"task_id": envelope.task_id})
            result = TaskResult(
                task_id=envelope.task_id,
                status=TaskResultStatus.FAILED,
                error=str(e),
                # SIP-0108 §4.1: a handler timeout carries the calls it made before it ran out.
                llm_usage=getattr(e, "llm_usage", None),
            )
        finally:
            if llm_obs:
                llm_obs.end_task_span(ctx)
                llm_obs.end_cycle_trace(ctx)
                llm_obs.flush()

        if skipped:
            return

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
        # Operational default (see the LOG_LEVEL note) — intentional tuning knob,
        # not masked required config (#333).
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


def _resolve_role() -> str | None:
    """Resolve the agent's own role — what this agent IS — for bootstrap.

    Role selection happens before the config loader runs, so it is read from the
    env (``SQUADOPS_AGENT_ROLE`` — a bootstrap selector, deliberately *not* the
    ``SQUADOPS__*`` nested-config convention). When unset it is resolved from the
    authoritative roster (``instances.yaml``) by agent id — **never fabricated**
    from the id string. The former hardcoded ``{id: role}`` map duplicated the
    roster, and its ``id.split("-")[0]`` fallback could mislabel an agent: the same
    identity-masking class as the fabricated-id default (#333).

    This is the identity the system prompt, the telemetry role and the prompt layers
    read. What the process SERVES is :func:`_resolve_served_roles` — a different
    question, and for a generalist agent a different answer.
    """
    role = os.getenv("SQUADOPS_AGENT_ROLE")
    if role:
        return role
    agent_id = os.getenv("SQUADOPS__AGENT__ID")
    instance = load_instance_config(agent_id) if agent_id else None
    return instance.get("role") if instance else None


def _resolve_served_roles(role: str) -> list[str]:
    """The step roles this process serves — which handlers it registers (SIP-0108 §10i item 2).

    The handler registry has always held several roles' handlers; only this resolution
    restricted a process to one, which is why a single agent could not serve the whole plan.
    The roster declares it per instance (``serves_roles``), the same vocabulary a squad
    profile's agent entry uses, so "which roles does this serve" reads the same on both sides.

    ``SQUADOPS_AGENT_SERVES_ROLES`` overrides it as a comma-separated list, the bootstrap
    selector beside ``SQUADOPS_AGENT_ROLE``.

    A roster entry that declares none falls back to the agent's own role, and says so in the
    log: the roster is data an operator edits, and a container that refused to boot over a
    missing list would take a whole deploy down for a field every current entry carries.
    """
    declared = os.getenv("SQUADOPS_AGENT_SERVES_ROLES")
    if declared:
        return [r.strip() for r in declared.split(",") if r.strip()]
    agent_id = os.getenv("SQUADOPS__AGENT__ID")
    instance = load_instance_config(agent_id) if agent_id else None
    roles = list(instance.get("serves_roles") or ()) if instance else []
    if roles:
        return roles
    logger.warning(
        "roster entry for %s declares no `serves_roles`; serving its own role %r only "
        "(SIP-0108 §10i item 2 — declare the list to serve more)",
        agent_id,
        role,
    )
    return [role]


async def main() -> int:
    """Main entry point."""
    role = _resolve_role()
    if not role:
        logger.error(
            "Agent role is not configured — set SQUADOPS_AGENT_ROLE, or ensure the "
            "agent's instances.yaml entry declares a role. Identity is never "
            "fabricated from the id string (#333)."
        )
        return 1

    logger.info(f"Starting agent with role: {role}")

    served = _resolve_served_roles(role)
    if served != [role]:
        logger.info("Agent %s serves roles: %s", role, ", ".join(served))
    runner = AgentRunner(role=role, served_roles=served)
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
