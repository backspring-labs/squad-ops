"""
SquadOps Runtime API - Task and cycle management.

SIP-0048: Runtime API for task management, execution cycles, and memory operations.
Part of SIP-0.8.8 migration from _v0_legacy/infra/runtime-api/main.py

Usage:
    uvicorn squadops.api.runtime.main:app --host 0.0.0.0 --port 8001
"""

import asyncio
import logging
import os
from urllib.parse import urlparse

import aio_pika
import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from squadops import __version__ as SQUADOPS_VERSION
from squadops.config import config_fingerprint, load_config, redact_config

from .deps import (
    set_audit_port,
    set_auth_ports,
    set_cycle_ports,
    set_health_checker,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SquadOps Runtime API",
    version=SQUADOPS_VERSION,
    description="SIP-0048: Runtime API for task management and execution cycles",
)

# Load configuration with profile selection and validation
strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
config = load_config(strict=strict_mode)

# Extract configuration values
POSTGRES_URL = config.db.url
RABBITMQ_URL = config.comms.rabbitmq.url

# Log configuration at startup (SIP-051 requirement)
config_dict = config.model_dump()
redacted_config_dict = redact_config(config_dict)
fingerprint = config_fingerprint(redacted_config_dict)
logger.info(f"Configuration fingerprint: {fingerprint} (strict={strict_mode})")


def _extract_origin(uri: str) -> str:
    """Extract scheme://host:port from a URI (no path)."""
    parsed = urlparse(uri)
    origin = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        origin += f":{parsed.port}"
    return origin


# SIP-0062 Phase 3a: CORS middleware for browser-based clients
# Middleware is added in reverse order because Starlette processes them LIFO.
# CORS must be outermost (added LAST) so it adds headers to ALL responses,
# including 401s from AuthMiddleware. Order: Auth → RequestID → CORS (outermost).
auth_config = config.auth
_cors_origins: set[str] = set()
if auth_config.console:
    _cors_origins.add(_extract_origin(auth_config.console.redirect_uri))
    if auth_config.console.post_logout_redirect_uri:
        _cors_origins.add(_extract_origin(auth_config.console.post_logout_redirect_uri))

from squadops.api.middleware.auth import AuthMiddleware, RequestIDMiddleware

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
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# SIP-0062 Phase 3a: Include auth routes
from squadops.api.routes.auth import router as auth_router

app.include_router(auth_router)

# SIP-0064: Include cycle execution routes
from squadops.api.routes.cycles import (
    artifacts_router,
    cycle_request_profiles_router,
    cycles_router,
    models_router,
    profiles_router,
    projects_router,
    runs_router,
)

app.include_router(projects_router)
app.include_router(cycles_router)
app.include_router(runs_router)
app.include_router(profiles_router)
app.include_router(artifacts_router)
app.include_router(cycle_request_profiles_router)  # SIP-0074
app.include_router(models_router)  # SIP-0074

# Platform health routes (replaces legacy health-check service)
from squadops.api.routes.platform_health import router as platform_health_router

app.include_router(platform_health_router)

# Global connection pool (for memory endpoints only)
pool: asyncpg.Pool | None = None

# Global RabbitMQ connection and channel (for task publishing)
rabbitmq_connection: aio_pika.Connection | None = None
rabbitmq_channel: aio_pika.Channel | None = None

# PrefectReporter for shutdown cleanup
_prefect_reporter = None

# Redis client + health checker for platform health routes
_redis_client = None
_health_checker_instance = None
_reconciliation_task = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and message queue connections."""
    global pool, rabbitmq_connection, rabbitmq_channel

    # Initialize PostgreSQL pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)

    # Initialize RabbitMQ connection (persistent, like agents do)
    try:
        logger.info("Attempting to connect to RabbitMQ...")
        rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
        rabbitmq_channel = await rabbitmq_connection.channel()
        logger.info("RabbitMQ connection established during startup")
    except Exception as e:
        # Log error but don't fail startup - connection will be retried on first use
        logger.error(f"Failed to initialize RabbitMQ connection during startup: {e}", exc_info=True)

    # Initialize auth adapters (SIP-0062)
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

    # Initialize audit adapter (SIP-0062 Phase 3b)
    try:
        from adapters.audit.factory import create_audit_provider

        audit = create_audit_provider("logging")
        set_audit_port(audit)
        logger.info("Audit adapter initialized")
    except Exception as e:
        logger.error(f"Failed to initialize audit adapter during startup: {e}")

    # Initialize service token clients (SIP-0062 Phase 3b)
    try:
        auth_config = config.auth
        if auth_config.service_clients and auth_config.oidc:
            from adapters.auth.factory import create_service_token_client

            for svc_name, svc_config in auth_config.service_clients.items():
                # secret_manager=None is correct: config loader pre-resolves
                # all secret:// references before AppConfig is created.
                create_service_token_client(
                    svc_name,
                    svc_config,
                    auth_config.oidc,
                    secret_manager=None,
                )
                logger.info("Service token client initialized: %s", svc_name)
    except Exception as e:
        logger.error(f"Failed to initialize service token clients: {e}")

    # Apply database migrations (idempotent, SIP-Postgres-Cycle-Registry §1.4)
    try:
        from pathlib import Path

        from squadops.api.runtime.migrations import apply_migrations

        migrations_dir = Path(config.db.migrations_dir)
        applied = await apply_migrations(pool, migrations_dir)
        if applied:
            logger.info("Applied %d migration(s) from %s", applied, migrations_dir)
    except Exception as e:
        logger.error("Failed to apply migrations during startup: %s", e)

    # Initialize SIP-0064 cycle ports + SIP-0066 orchestrator bootstrap
    try:
        from adapters.cycles.factory import (
            create_artifact_vault,
            create_cycle_registry,
            create_flow_executor,
            create_project_registry,
            create_squad_profile_port,
        )

        project_registry = create_project_registry("config")
        cycle_registry = create_cycle_registry(
            config.cycles.registry_provider,
            **({"pool": pool} if config.cycles.registry_provider == "postgres" else {}),
        )
        squad_profile = create_squad_profile_port("config")
        artifact_vault = create_artifact_vault("filesystem")

        # Distributed executor: dispatch tasks to agent containers via RabbitMQ.
        # Each agent uses its own LLM model and PromptService — no orchestrator
        # or handler registry needed in the runtime-api container.
        from adapters.comms.rabbitmq import RabbitMQAdapter
        from adapters.telemetry.factory import create_llm_observability_provider

        queue_adapter = RabbitMQAdapter(url=RABBITMQ_URL)
        llm_obs = create_llm_observability_provider(config=config.langfuse)

        # Create PrefectReporter with module-level ref for shutdown cleanup
        global _prefect_reporter
        if config.prefect.api_url:
            from adapters.cycles.prefect_reporter import PrefectReporter

            _prefect_reporter = PrefectReporter(api_url=config.prefect.api_url)

        flow_executor = create_flow_executor(
            "distributed",
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            squad_profile=squad_profile,
            project_registry=project_registry,
            queue=queue_adapter,
            llm_observability=llm_obs,
            prefect_reporter=_prefect_reporter,
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

    # Initialize platform health checker (replaces legacy health-check service)
    global _redis_client, _health_checker_instance, _reconciliation_task
    try:
        import redis.asyncio as aioredis

        from squadops.api.runtime.health_checker import HealthChecker

        redis_url = config.comms.redis.url
        _redis_client = aioredis.from_url(redis_url)
        _health_checker_instance = HealthChecker(
            pg_pool=pool,
            redis_client=_redis_client,
            config=config,
        )
        await _health_checker_instance.init_connections()
        set_health_checker(_health_checker_instance)
        _reconciliation_task = asyncio.create_task(_health_checker_instance.reconciliation_loop())
        logger.info("Platform health checker initialized")
    except Exception as e:
        logger.error(f"Failed to initialize health checker: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections."""
    global pool, rabbitmq_connection
    if _health_checker_instance:
        _health_checker_instance._reconciliation_running = False
    if _reconciliation_task:
        _reconciliation_task.cancel()
    if _health_checker_instance:
        await _health_checker_instance.close()
    if _redis_client:
        await _redis_client.aclose()
    if pool:
        await pool.close()
    if rabbitmq_connection:
        await rabbitmq_connection.close()
    if _prefect_reporter:
        await _prefect_reporter.close()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "runtime-api", "version": SQUADOPS_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
