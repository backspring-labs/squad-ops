"""
SquadOps Runtime API - Task and cycle management.

SIP-0048: Runtime API for task management, execution cycles, and memory operations.
Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/main.py

Usage:
    uvicorn --factory squadops.api.runtime.main:build_app --host 0.0.0.0 --port 8001

Composition root (#286, docs/architecture/composition-roots.md §6.5): ``create_app(config)``
is pure composition and reads nothing from the environment; ``build_app()`` is the process
entry that loads configuration and calls it. A bare ``import squadops.api.runtime.main``
performs no configuration load, no secret resolution and no construction.
"""

import asyncio
import logging
import os
from urllib.parse import urlparse

import aio_pika
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.persistence.pool import create_pool
from squadops import __version__ as SQUADOPS_VERSION
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware
from squadops.api.routes.agent_status import router as agent_status_router
from squadops.api.routes.assignments import router as assignments_router
from squadops.api.routes.auth import router as auth_router
from squadops.api.routes.chat import agents_router as chat_agents_router
from squadops.api.routes.chat import chat_router
from squadops.api.routes.cycles import (
    artifacts_router,
    cycle_request_profiles_router,
    cycles_router,
    models_router,
    profiles_router,
    projects_router,
    runs_router,
)
from squadops.api.routes.platform_health import router as platform_health_router
from squadops.bootstrap.secrets import secret_provider_for
from squadops.config import config_fingerprint, load_config, redact_config
from squadops.config.schema import AppConfig

from .deps import (
    set_audit_port,
    set_auth_ports,
    set_cycle_ports,
    set_health_checker,
)
from .logging_setup import configure_logging

# #427: configure application logging before any module-level log fires. uvicorn
# configures only its own loggers and leaves the root logger untouched, so without
# this the executor's in-process logs (including a run's terminal exception) never
# reach stdout and every failure is a black box. Installed at import so it survives
# uvicorn's startup dictConfig (see logging_setup for the why).
configure_logging()

logger = logging.getLogger(__name__)


def _extract_origin(uri: str) -> str:
    """Extract scheme://host:port from a URI (no path)."""
    parsed = urlparse(uri)
    origin = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        origin += f":{parsed.port}"
    return origin


def _add_middleware(app: FastAPI, auth_config) -> None:
    """SIP-0062 Phase 3a. Middleware is added in reverse order because Starlette processes
    them LIFO: CORS must be outermost (added LAST) so it adds headers to ALL responses,
    including 401s from AuthMiddleware. Order: Auth → RequestID → CORS (outermost)."""
    cors_origins: set[str] = set()
    if auth_config.console:
        cors_origins.add(_extract_origin(auth_config.console.redirect_uri))
        if auth_config.console.post_logout_redirect_uri:
            cors_origins.add(_extract_origin(auth_config.console.post_logout_redirect_uri))
    # Inner middleware first (Auth checks tokens)
    if auth_config.enabled:
        app.add_middleware(
            AuthMiddleware,
            auth_port=None,  # Port set at startup via deps; middleware uses deps.get_auth_port()
            provider=auth_config.provider,
            expose_docs=auth_config.expose_docs,
        )
    app.add_middleware(RequestIDMiddleware)
    # CORS outermost (added last) — ensures CORS headers on 401/403 responses too
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


def _include_routers(app: FastAPI) -> None:
    app.include_router(auth_router)  # SIP-0062 Phase 3a
    # SIP-0064: cycle execution routes
    app.include_router(projects_router)
    app.include_router(cycles_router)
    app.include_router(runs_router)
    app.include_router(profiles_router)
    app.include_router(artifacts_router)
    app.include_router(cycle_request_profiles_router)  # SIP-0074
    app.include_router(models_router)  # SIP-0074
    app.include_router(assignments_router)  # SIP-0089 §2.7 (/api/v1)
    app.include_router(platform_health_router)  # replaces the legacy health-check service
    app.include_router(agent_status_router)  # #326: agent status writes, authed /api/v1 lane
    app.include_router(chat_router)  # SIP-0085
    app.include_router(chat_agents_router)


#: Connection and process objects live on ``app.state`` (FastAPI's per-app holder), so an
#: app's connections have the app's lifecycle and nothing else's (§6.5). Declared here so
#: every reader sees the full inventory; ``_startup`` fills them.
_STATE_SLOTS = (
    "pool",  # asyncpg pool (memory endpoints; the one factory, #577)
    "rabbitmq_connection",  # persistent, like agents (task publishing)
    "rabbitmq_channel",
    "workflow_tracker",  # closed on shutdown
    "reply_router",  # SIP-0094 per-agent reply queues; stopped on shutdown (D13)
    "log_forwarder",  # SIP-0087; closed on shutdown
    "redis_client",  # platform health routes
    "health_checker",
    "reconciliation_task",
    "duty_scheduler",  # SIP-0089 §2.4, opt-in; stopped on shutdown
    "runtime_coordinator",  # SIP-0089 §3.5 (#233) single-writer (D16), shared by executor + scheduler
)


def create_app(config: AppConfig) -> FastAPI:
    """Pure composition: the app, its handlers, middleware, routers and lifecycle hooks, from a
    config VALUE. Reads nothing from the environment (#286, §6.5).

    What this does not fix, stated so it is not claimed: the routes read their ports from
    ``deps.py``'s process-wide registry, which ``_startup`` populates — two apps in one
    process share it and the second overwrites the first. #1448 is the follow-on; until it
    lands, "one process, one runtime app" is a stated constraint.
    """
    app = FastAPI(
        title="SquadOps Runtime API",
        version=SQUADOPS_VERSION,
        description="SIP-0048: Runtime API for task management and execution cycles",
    )
    # #576: domain errors become the standard envelope in one place — see api/error_handlers.py.
    register_domain_error_handlers(app)
    _add_middleware(app, config.auth)
    _include_routers(app)
    app.state.config = config
    for slot in _STATE_SLOTS:
        setattr(app.state, slot, None)
    app.add_event_handler("startup", lambda: _startup(app))
    app.add_event_handler("shutdown", lambda: _shutdown(app))
    app.add_api_route("/health", health_check, methods=["GET"])
    return app


def build_app() -> FastAPI:
    """The process entry point: load configuration, then compose. The ONLY place the strict
    flag is read from the environment."""
    strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
    config = load_config(strict=strict_mode, secret_provider_factory=secret_provider_for)
    # Log configuration at startup (SIP-051 requirement)
    fingerprint = config_fingerprint(redact_config(config.model_dump()))
    logger.info(f"Configuration fingerprint: {fingerprint} (strict={strict_mode})")
    return create_app(config)


async def _init_auth_subsystem(config) -> None:
    """Initialize auth, audit, and service token adapters (SIP-0062)."""
    try:
        auth_config = config.auth
        if auth_config.enabled and auth_config.provider != "disabled":
            from adapters.auth.factory import create_auth_provider, create_authorization_provider

            auth_port = create_auth_provider(
                auth_config.provider,
                issuer_url=auth_config.oidc.issuer_url,
                audience=auth_config.oidc.audience,
                jwks_url=auth_config.oidc.jwks_url,
                roles_claim_path=auth_config.oidc.roles_claim_path,
                jwks_cache_ttl_seconds=auth_config.oidc.jwks_cache_ttl_seconds,
                jwks_forced_refresh_min_interval_seconds=auth_config.oidc.jwks_forced_refresh_min_interval_seconds,
                clock_skew_seconds=auth_config.oidc.clock_skew_seconds,
                issuer_public_url=auth_config.oidc.issuer_public_url,
            )
            authz_port = create_authorization_provider(
                auth_config.provider,
                roles_mode=auth_config.roles_mode,
                roles_client_id=auth_config.roles_client_id,
            )
            set_auth_ports(auth=auth_port, authz=authz_port)
            logger.info("Auth adapters initialized (provider=%s)", auth_config.provider)
        elif auth_config.enabled and auth_config.provider == "disabled":
            logger.info("Auth enabled but provider=disabled — protected endpoints return 503")
        else:
            logger.info("Auth disabled — no middleware attached")
    except Exception as e:
        logger.error(f"Failed to initialize auth adapters during startup: {e}")

    try:
        from adapters.audit.factory import create_audit_provider

        audit = create_audit_provider("logging")
        set_audit_port(audit)
        logger.info("Audit adapter initialized")
    except Exception as e:
        logger.error(f"Failed to initialize audit adapter during startup: {e}")

    try:
        auth_config = config.auth
        if auth_config.service_clients and auth_config.oidc:
            from adapters.auth.factory import create_service_token_client

            for svc_name, svc_config in auth_config.service_clients.items():
                create_service_token_client(
                    svc_name,
                    svc_config,
                    auth_config.oidc,
                    secret_manager=None,
                )
                logger.info("Service token client initialized: %s", svc_name)
    except Exception as e:
        logger.error(f"Failed to initialize service token clients: {e}")


async def _init_migrations(config, pool) -> None:
    """Apply database migrations (idempotent)."""
    try:
        from pathlib import Path

        from squadops.api.runtime.migrations import apply_migrations

        migrations_dir = Path(config.db.migrations_dir)
        applied = await apply_migrations(pool, migrations_dir)
        if applied:
            logger.info("Applied %d migration(s) from %s", applied, migrations_dir)
    except Exception as e:
        logger.error("Failed to apply migrations during startup: %s", e)


async def _init_log_forwarding(state, config) -> None:
    """Install the log forwarder via factory (SIP-0087).

    Always-inject pattern — a NoOp adapter is returned when no backend is
    configured, so the rest of the runtime never branches on enablement.
    """
    from adapters.observability.log_forwarder import create_log_forwarder

    state.log_forwarder = await create_log_forwarder(config.prefect)


async def _init_cycle_subsystem(state, config, pool) -> None:
    """Initialize SIP-0064 cycle ports + SIP-0066 orchestrator."""
    try:
        from adapters.cycles.factory import (
            create_artifact_vault,
            create_cycle_registry,
            create_flow_executor,
            create_project_registry,
            create_squad_profile_port,
        )
        from adapters.cycles.workflow_tracker_factory import create_workflow_tracker

        project_registry = create_project_registry("config")
        cycle_registry = create_cycle_registry(
            config.cycles.registry_provider,
            **({"pool": pool} if config.cycles.registry_provider == "postgres" else {}),
        )
        squad_profile_provider = config.cycles.squad_profile_provider
        if squad_profile_provider == "postgres":
            squad_profile = create_squad_profile_port("postgres", pool=pool)
            try:
                from adapters.cycles.config_squad_profile import ConfigSquadProfile

                yaml_source = ConfigSquadProfile()
                yaml_profiles = await yaml_source.list_profiles()
                yaml_active_id = yaml_source._active_profile_id
                seeded = await squad_profile.seed_profiles(yaml_profiles, yaml_active_id)
                if seeded:
                    logger.info("Seeded %d squad profiles from YAML", seeded)
            except Exception as seed_err:
                logger.warning("YAML seed failed (non-fatal): %s", seed_err)
        else:
            squad_profile = create_squad_profile_port("config")
        artifact_vault = create_artifact_vault("filesystem")

        from adapters.comms.rabbitmq import RabbitMQAdapter
        from adapters.telemetry.factory import create_llm_observability_provider

        queue_adapter = RabbitMQAdapter(url=config.comms.rabbitmq.url)
        llm_obs = create_llm_observability_provider(
            config=config.langfuse,
            prompt_asset_provider=config.prompts.asset_source_provider,
        )

        # SIP-0094: per-agent reply-queue router. Holds one long-lived
        # subscription per agent (opened lazily on first dispatch) and resolves
        # task futures. Stopped during shutdown (D13).
        from adapters.cycles.reply_router import ReplyRouter

        state.reply_router = ReplyRouter(queue_adapter)

        state.workflow_tracker = create_workflow_tracker(config.prefect)
        # #77: expose the tracker to the cancel routes so cancelling a cycle/run
        # propagates to Prefect (stops the orphaned flow run).
        from squadops.api.runtime.deps import set_workflow_tracker

        set_workflow_tracker(state.workflow_tracker)

        from adapters.events.factory import create_cycle_event_bus
        from squadops.api.runtime.deps import set_cycle_event_bus

        # Bridges are subscribed inside the factory so the composition root
        # never names ``LLMObservabilityBridge`` / ``WorkflowTrackerBridge``
        # directly — only the ports cross this boundary.
        event_bus = create_cycle_event_bus(
            "in_process",
            source_service="runtime-api",
            source_version=SQUADOPS_VERSION,
            llm_observability=llm_obs,
            workflow_tracker=state.workflow_tracker,
        )
        set_cycle_event_bus(event_bus)

        # SIP-0089 §2.5: wire the reserve-buffer guard live when a Postgres pool
        # is available (the agent_assignments table lives there, migration 1110).
        # Without a pool the guard stays unwired and recruitment is never gated.
        assignment_port = None
        activity_port = None
        focus_lease_port = None
        state_port = None
        if pool is not None:
            from adapters.persistence.runtime.activity_postgres import PostgresRuntimeActivity
            from adapters.persistence.runtime.assignments_postgres import PostgresAssignment
            from adapters.persistence.runtime.focus_lease_postgres import PostgresFocusLease
            from adapters.persistence.runtime.state_postgres import PostgresRuntimeState
            from squadops.api.runtime.deps import set_assignment_port

            assignment_port = PostgresAssignment(pool)
            # SIP-0089 §2.7: same adapter backs the assignment REST surface.
            set_assignment_port(assignment_port)
            # SIP-0089 §4.4: executor-side task-activity instrumentation. The
            # runtime-api process owns the asyncpg pool, so RuntimeActivity is
            # written here (not in agents) as each task is dispatched/replied.
            activity_port = PostgresRuntimeActivity(pool)
            # #373/#529: the lease port for the stranded-lease sweeps. Stateless
            # over the pool, so this instance is interchangeable with the one
            # `create_runtime_coordinator` builds (same precedent as the
            # assignment/activity adapters, which are also built twice).
            focus_lease_port = PostgresFocusLease(pool)
            # #710: the mode half of the same residue. Stateless over the pool,
            # same as the adapters above.
            state_port = PostgresRuntimeState(pool)

        # SIP-0089 §3.5 (#233): the single-writer coordinator (D16), built once
        # here and reused by the duty scheduler (see _init_duty_scheduler) so the
        # executor's recruitment and the scheduler drive the same mode-writer.
        # None when pool-less → recruitment falls back to the §2.5 guard only.
        from squadops.api.runtime.scheduler_bootstrap import create_runtime_coordinator

        state.runtime_coordinator = create_runtime_coordinator(pool)

        # #373/#529/#561: share the runtime ports with the cancel routes, which
        # bypass the executor's finalize path and so have to release the leases
        # and end the activities the cancelled run leaves behind.
        from squadops.api.runtime.deps import set_cancellation_ports

        set_cancellation_ports(state.runtime_coordinator, focus_lease_port, activity_port)

        # Startup hygiene: clear runtime state a dead process left active, before
        # anything recruits against it. Each sweep is best-effort and owns its own
        # wiring gate + terminal predicate (see `startup_reaps`); a held lease
        # (#373) blocks recruitment outright, a live activity row (#672) kills
        # that agent's activity tracking.
        from squadops.api.runtime.startup_reaps import (
            detect_stranded_cycles,
            reap_stranded_activities,
            reap_stranded_leases,
            reap_stranded_modes,
        )

        # Lease first: it returns the agents it clears to ambient, so the mode
        # sweep after it sees only the residue with no lease at all (#710).
        await reap_stranded_leases(cycle_registry, state.runtime_coordinator, focus_lease_port)
        await reap_stranded_modes(state.runtime_coordinator, state_port)
        await reap_stranded_activities(cycle_registry, activity_port)
        # Read-only, last: a post-crash boot immediately names every cycle
        # stranded between workloads and its recovery command (#481).
        await detect_stranded_cycles(cycle_registry, project_registry)

        flow_executor = create_flow_executor(
            "dispatched",
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            squad_profile=squad_profile,
            project_registry=project_registry,
            queue=queue_adapter,
            task_timeout=config.task_timeout_seconds(),  # #1147: not llm.timeout
            llm_observability=llm_obs,
            workflow_tracker=state.workflow_tracker,
            event_bus=event_bus,
            reply_router=state.reply_router,
            assignment_port=assignment_port,
            activity_port=activity_port,
            coordinator=state.runtime_coordinator,
            focus_lease_port=focus_lease_port,
        )

        set_cycle_ports(
            project_registry=project_registry,
            cycle_registry=cycle_registry,
            squad_profile=squad_profile,
            artifact_vault=artifact_vault,
            flow_executor=flow_executor,
        )
        logger.info("SIP-0064 cycle ports + SIP-0066 orchestrator initialized")
    except Exception as e:
        logger.error(f"Failed to initialize cycle ports: {e}")

    # #1157 (the LLM half of #301): the configured provider through the factory, never
    # a directly constructed adapter. Construction is outside the try on purpose — an
    # unknown provider name is a misconfiguration and must stop startup, while the
    # registration below stays non-fatal.
    from adapters.llm.factory import create_llm_provider

    llm_adapter = create_llm_provider(
        provider=config.llm.provider,
        base_url=config.llm.url,
        default_model=config.llm.model or "qwen2.5:7b",
        timeout_seconds=float(config.llm.timeout),
        api_key=config.llm.api_key,
    )
    try:
        from squadops.api.runtime.deps import set_llm_port

        set_llm_port(llm_adapter)
        logger.info("LLM port registered for model management (provider=%s)", config.llm.provider)
    except Exception as e:
        logger.warning("LLM port not registered (non-fatal): %s", e)


async def _init_monitoring(state, config, pool) -> None:
    """Initialize health checker and chat ports."""
    try:
        import redis.asyncio as aioredis

        from adapters.persistence.runtime import PostgresRuntimeActivity, PostgresRuntimeState
        from squadops.api.runtime.health_checker import HealthChecker

        redis_url = config.comms.redis.url
        state.redis_client = aioredis.from_url(redis_url)
        state.health_checker = HealthChecker(
            pg_pool=pool,
            redis_client=state.redis_client,
            config=config,
            runtime_state=PostgresRuntimeState(pool),
            # SIP-0089 §4.7: backs GET /health/agents/{id}/activity.
            activity=PostgresRuntimeActivity(pool),
        )
        await state.health_checker.init_connections()
        set_health_checker(state.health_checker)
        state.reconciliation_task = asyncio.create_task(state.health_checker.reconciliation_loop())
        logger.info("Platform health checker initialized")
    except Exception as e:
        logger.error(f"Failed to initialize health checker: {e}")

    try:
        import yaml

        from adapters.comms.a2a_client import A2AClientAdapter
        from adapters.persistence.chat_repository import ChatRepository
        from squadops.api.runtime.deps import set_chat_ports

        chat_repo = ChatRepository(pool=pool)
        a2a_client = A2AClientAdapter()

        all_agents: dict = {}
        messaging_agents: dict = {}
        instances_path = config.agent.instances_file
        if instances_path.exists():
            with open(instances_path) as f:
                instances_data = yaml.safe_load(f)
            for inst in instances_data.get("instances", []):
                agent_id = inst["id"]
                inst.setdefault("a2a_host", inst.get("host", "localhost"))
                inst.setdefault("a2a_port", config.agent.a2a_port)
                inst.setdefault("display_name", agent_id)
                inst.setdefault("description", "")
                all_agents[agent_id] = inst
                if inst.get("a2a_messaging_enabled", False):
                    messaging_agents[agent_id] = inst

        chat_cache = None
        if state.redis_client:
            from adapters.persistence.chat_cache import ChatSessionCache

            chat_cache = ChatSessionCache(redis=state.redis_client)

        set_chat_ports(
            chat_repo=chat_repo,
            chat_cache=chat_cache,
            a2a_client=a2a_client,
            all_agents=all_agents,
            messaging_agents=messaging_agents,
        )
        logger.info(
            "SIP-0085 chat ports initialized",
            extra={"messaging_agents": list(messaging_agents.keys())},
        )
    except Exception as e:
        logger.error(f"Failed to initialize chat ports: {e}")


async def _init_duty_scheduler(state, config, pool) -> None:
    """Start the duty-transition scheduler when enabled (SIP-0089 §2.4).

    The scheduler is the live driver of ambient↔duty transitions: it polls duty
    assignments and requests window open/close through the coordinator (the sole
    writer of mode, D16). Opt-in via `runtime.scheduler.enabled`; a clean
    shutdown path is provided in `_shutdown` (mirrors the reconciliation
    loop). See `scheduler_bootstrap` for the single-writer constraint.
    """
    try:
        from squadops.api.runtime.scheduler_bootstrap import create_duty_scheduler

        # Reuse the single-writer coordinator built in _init_cycle_subsystem (D16);
        # the scheduler builds its own only if that wiring was skipped.
        state.duty_scheduler = create_duty_scheduler(
            config, pool, coordinator=state.runtime_coordinator
        )
        if state.duty_scheduler is not None:
            await state.duty_scheduler.start()
            logger.info("Duty scheduler started")
    except Exception as e:
        logger.error("Failed to start duty scheduler: %s", e)


async def _startup(app: FastAPI) -> None:
    """Initialize database and message queue connections, then every subsystem, onto
    ``app.state``."""
    state, config = app.state, app.state.config
    state.pool = await create_pool(config.db.url, min_size=1, max_size=10)  # #577: the one factory
    # Initialize RabbitMQ connection (persistent, like agents do)
    try:
        logger.info("Attempting to connect to RabbitMQ...")
        state.rabbitmq_connection = await aio_pika.connect_robust(config.comms.rabbitmq.url)
        state.rabbitmq_channel = await state.rabbitmq_connection.channel()
        logger.info("RabbitMQ connection established during startup")
    except Exception as e:
        # Log error but don't fail startup - connection will be retried on first use
        logger.error(f"Failed to initialize RabbitMQ connection during startup: {e}", exc_info=True)

    await _init_auth_subsystem(config)
    await _init_migrations(config, state.pool)
    await _init_log_forwarding(state, config)
    await _init_cycle_subsystem(state, config, state.pool)
    await _init_monitoring(state, config, state.pool)
    await _init_duty_scheduler(state, config, state.pool)


async def _shutdown(app: FastAPI) -> None:
    """Clean up connections, in the order their dependencies require."""
    state = app.state
    # SIP-0089 §2.4: stop the duty scheduler before the pool closes so its final
    # tick can't race a closing connection.
    if state.duty_scheduler is not None:
        await state.duty_scheduler.stop()
    if state.health_checker:
        state.health_checker._reconciliation_running = False
    if state.reconciliation_task:
        state.reconciliation_task.cancel()
    if state.health_checker:
        await state.health_checker.close()
    if state.redis_client:
        await state.redis_client.aclose()
    if state.pool:
        await state.pool.close()
    if state.rabbitmq_connection:
        await state.rabbitmq_connection.close()
    if state.log_forwarder is not None:
        await state.log_forwarder.aclose()
    # SIP-0094 D13: stop the reply router — once stopped it rejects new
    # registrations, cancels its subscriptions, and fails any pending reply
    # futures with ReplyRouterStopped (in-flight waits resolve as FAILED).
    if state.reply_router is not None:
        await state.reply_router.stop()
    if state.workflow_tracker is not None:
        await state.workflow_tracker.close()


async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "runtime-api", "version": SQUADOPS_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(build_app(), host="0.0.0.0", port=8001)
