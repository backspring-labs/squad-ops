"""
Platform health checker — extracted from legacy health_app.py.

Provides infrastructure health probes and agent status management
for the runtime-api service. All external HTTP probes use httpx.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import yaml

from squadops.api.runtime.agent_labels import get_role_label

logger = logging.getLogger(__name__)


class HealthChecker:
    """Runs health checks against platform infrastructure and manages agent status."""

    def __init__(
        self,
        *,
        pg_pool: asyncpg.Pool,
        redis_client: Any | None = None,
        config: Any,
    ) -> None:
        self.pg_pool = pg_pool
        self.redis_client = redis_client
        self._config = config
        self._instances_cache: dict[str, dict[str, Any]] | None = None
        self._instances_cache_mtime: float | None = None
        self._reconciliation_running = True
        self._http_client: httpx.AsyncClient | None = None

    async def init_connections(self) -> None:
        """Create shared HTTP client for health probes."""
        self._http_client = httpx.AsyncClient(timeout=5.0)

    async def close(self) -> None:
        """Close resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    # ── Instances YAML ──────────────────────────────────────────────────

    def _load_instances(self) -> dict[str, dict[str, Any]]:
        """Load agent instances from instances.yaml with file-mtime caching."""
        try:
            instances_path = Path(self._config.agent.instances_file)
            if not instances_path.exists():
                logger.warning("Instances file not found: %s, using defaults", instances_path)
                return self._get_default_instances()

            current_mtime = instances_path.stat().st_mtime
            if self._instances_cache is not None and self._instances_cache_mtime == current_mtime:
                return self._instances_cache

            with open(instances_path) as f:
                data = yaml.safe_load(f)

            instances: dict[str, dict[str, Any]] = {}
            for instance in data.get("instances", []):
                if instance.get("enabled", False):
                    agent_id = instance.get("id")
                    if agent_id:
                        instances[agent_id] = {
                            "display_name": instance.get("display_name", agent_id.title()),
                            "role": instance.get("role", "unknown"),
                            "description": instance.get("description", ""),
                        }

            self._instances_cache = instances
            self._instances_cache_mtime = current_mtime
            logger.info("Loaded %d agent instances from %s", len(instances), instances_path)
            return instances
        except Exception as e:
            logger.error("Failed to load instances.yaml: %s, using defaults", e)
            return self._get_default_instances()

    def _get_instances_order(self) -> list[str]:
        """Return agent_ids in instances.yaml order."""
        try:
            instances_path = Path(self._config.agent.instances_file)
            if not instances_path.exists():
                return []
            with open(instances_path) as f:
                data = yaml.safe_load(f)
            return [
                inst["id"]
                for inst in data.get("instances", [])
                if inst.get("enabled", False) and inst.get("id")
            ]
        except Exception as e:
            logger.error("Failed to get instances order: %s", e)
            return []

    def _get_default_instances(self) -> dict[str, dict[str, Any]]:
        """Empty fallback — platform code has no hardcoded agent names."""
        return {}

    def _get_display_name(self, agent_id: str) -> str:
        instances = self._load_instances()
        info = instances.get(agent_id)
        return info["display_name"] if info else agent_id.title()

    # ── Network status derivation ───────────────────────────────────────

    def _compute_network_status(self, last_heartbeat: datetime | None) -> str:
        if last_heartbeat is None:
            return "offline"
        timeout = self._config.agent.heartbeat_timeout_window
        elapsed = (datetime.utcnow() - last_heartbeat).total_seconds()
        return "online" if elapsed <= timeout else "offline"

    # ── Agent status from DB ────────────────────────────────────────────

    async def get_agent_status(self) -> list[dict[str, Any]]:
        """Return agent status list, merging DB rows with instances.yaml metadata."""
        try:
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT agent_id, lifecycle_state, version, tps, memory_count, "
                    "last_heartbeat, current_task_id FROM agent_status"
                )

            instances = self._load_instances()
            instances_order = self._get_instances_order()
            rows_by_id = {row["agent_id"]: row for row in rows}

            agents: list[dict[str, Any]] = []

            def _build_agent_dict(agent_id: str, row: Any) -> dict[str, Any]:
                network_status = self._compute_network_status(row["last_heartbeat"])
                if network_status == "offline":
                    lifecycle_state = "UNKNOWN"
                else:
                    lifecycle_state = row["lifecycle_state"] or "UNKNOWN"
                info = instances.get(agent_id, {})
                role = info.get("role", "unknown")
                return {
                    "agent_id": agent_id,
                    "agent_name": info.get("display_name", agent_id.title()),
                    "role": role,
                    "role_label": get_role_label(role),
                    "network_status": network_status,
                    "lifecycle_state": lifecycle_state,
                    "version": row["version"] or "0.0.0",
                    "tps": row["tps"],
                    "memory_count": row["memory_count"] if row["memory_count"] is not None else 0,
                    "last_seen": (
                        row["last_heartbeat"].isoformat() + "Z" if row["last_heartbeat"] else None
                    ),
                    "current_task_id": row["current_task_id"],
                }

            for aid in instances_order:
                if aid in rows_by_id:
                    agents.append(_build_agent_dict(aid, rows_by_id[aid]))
            for aid in sorted(rows_by_id):
                if aid not in instances_order:
                    agents.append(_build_agent_dict(aid, rows_by_id[aid]))

            return agents
        except Exception as e:
            logger.error("Failed to get agent status: %s", e, exc_info=True)
            instances = self._load_instances()
            return [
                {
                    "agent_id": aid,
                    "agent_name": info["display_name"],
                    "role": info.get("role", "unknown"),
                    "role_label": get_role_label(info.get("role", "unknown")),
                    "network_status": "offline",
                    "lifecycle_state": "UNKNOWN",
                    "version": "0.0.0",
                    "tps": 0,
                    "memory_count": 0,
                    "last_seen": None,
                    "current_task_id": None,
                }
                for aid, info in instances.items()
            ]

    async def update_agent_status_in_db(self, agent_status: dict[str, Any]) -> dict[str, Any]:
        """Upsert agent heartbeat row."""
        now = datetime.utcnow()
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_status
                (agent_id, network_status, lifecycle_state, last_heartbeat, current_task_id, version, tps, memory_count, updated_at)
                VALUES ($1, 'online', $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (agent_id)
                DO UPDATE SET
                    network_status = 'online',
                    lifecycle_state = $2, last_heartbeat = $3, current_task_id = $4,
                    version = $5, tps = $6, memory_count = $7, updated_at = $8
                """,
                agent_status["agent_id"],
                agent_status["lifecycle_state"],
                now,
                agent_status.get("current_task_id"),
                agent_status.get("version"),
                agent_status.get("tps", 0),
                agent_status.get("memory_count", 0) or 0,
                now,
            )
        return {"status": "updated", "agent_id": agent_status["agent_id"]}

    # ── Reconciliation loop ─────────────────────────────────────────────

    async def reconciliation_loop(self) -> None:
        """Periodic background task to recompute network_status for offline agents."""
        interval = self._config.agent.reconciliation_interval
        while self._reconciliation_running:
            try:
                await asyncio.sleep(interval)
                timeout = self._config.agent.heartbeat_timeout_window
                now = datetime.utcnow()

                async with self.pg_pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT agent_id, last_heartbeat, lifecycle_state, network_status "
                        "FROM agent_status"
                    )
                    for row in rows:
                        hb = row["last_heartbeat"]
                        computed = (
                            "online" if hb and (now - hb).total_seconds() <= timeout else "offline"
                        )
                        stored = row.get("network_status")
                        need_lifecycle = (
                            computed == "offline" and row.get("lifecycle_state") != "UNKNOWN"
                        )

                        if computed != stored or need_lifecycle:
                            if need_lifecycle:
                                await conn.execute(
                                    "UPDATE agent_status SET network_status=$1, lifecycle_state=$2, "
                                    "updated_at=$3 WHERE agent_id=$4",
                                    computed,
                                    "UNKNOWN",
                                    now,
                                    row["agent_id"],
                                )
                            else:
                                await conn.execute(
                                    "UPDATE agent_status SET network_status=$1, updated_at=$2 "
                                    "WHERE agent_id=$3",
                                    computed,
                                    now,
                                    row["agent_id"],
                                )
            except Exception as e:
                logger.error("Reconciliation loop error: %s", e, exc_info=True)
                await asyncio.sleep(10)

    # ── Infrastructure health probes ────────────────────────────────────

    async def check_rabbitmq(self) -> dict[str, Any]:
        """Check RabbitMQ via management API."""
        try:
            rmq_url = self._config.comms.rabbitmq.url
            # Extract credentials and host from amqp URL
            url_parts = rmq_url.replace("amqp://", "").split("@")
            version = "Unknown"
            notes = "API responding"
            if len(url_parts) == 2:
                import base64

                creds = url_parts[0]
                host_port = url_parts[1].split("/")[0]
                mgmt_url = f"http://{host_port.replace(':5672', ':15672')}/api/overview"
                auth_string = base64.b64encode(creds.encode()).decode()
                resp = await self._client.get(
                    mgmt_url, headers={"Authorization": f"Basic {auth_string}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    version = data.get("rabbitmq_version", "Unknown")
                    notes = "Management API responding"

            return {
                "component": "RabbitMQ",
                "type": "Message Broker",
                "status": "online",
                "version": version,
                "purpose": "Handles inter-agent communication",
                "notes": notes,
            }
        except Exception as e:
            return {
                "component": "RabbitMQ",
                "type": "Message Broker",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Handles inter-agent communication",
                "notes": f"Error: {e}",
            }

    async def check_postgres(self) -> dict[str, Any]:
        try:
            async with self.pg_pool.acquire() as conn:
                version_result = await conn.fetchval("SELECT version()")
                count = await conn.fetchval("SELECT COUNT(*) FROM agent_status")
                version = "Unknown"
                if version_result:
                    m = re.search(r"PostgreSQL (\d+\.\d+)", version_result)
                    if m:
                        version = m.group(1)
            return {
                "component": "PostgreSQL",
                "type": "Relational DB",
                "status": "online",
                "version": version,
                "purpose": "Persistent data and logs",
                "notes": f"{count} agents registered",
            }
        except Exception as e:
            return {
                "component": "PostgreSQL",
                "type": "Relational DB",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Persistent data and logs",
                "notes": f"Error: {e}",
            }

    async def check_redis(self) -> dict[str, Any]:
        try:
            if not self.redis_client:
                raise RuntimeError("Redis client not configured")
            await self.redis_client.ping()
            info = await self.redis_client.info()
            return {
                "component": "Redis",
                "type": "Cache & Pub/Sub",
                "status": "online",
                "version": info.get("redis_version", "Unknown"),
                "purpose": "Caching, state sync, pub/sub backbone",
                "notes": f"Memory used: {info.get('used_memory_human', 'Unknown')}",
            }
        except Exception as e:
            return {
                "component": "Redis",
                "type": "Cache & Pub/Sub",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Caching, state sync, pub/sub backbone",
                "notes": f"Error: {e}",
            }

    async def check_prefect(self) -> dict[str, Any]:
        try:
            prefect_url = self._config.prefect.api_url
            resp = await self._client.get(f"{prefect_url}/health")
            if resp.status_code == 200:
                version = "Unknown"
                try:
                    vr = await self._client.get(f"{prefect_url}/version")
                    if vr.status_code == 200:
                        version = vr.text.strip('"')
                except Exception:
                    pass
                return {
                    "component": "Prefect Server",
                    "type": "Orchestration Engine",
                    "status": "online",
                    "version": version,
                    "purpose": "Task orchestration and state management",
                    "notes": "API responding",
                }
            raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            return {
                "component": "Prefect Server",
                "type": "Orchestration Engine",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Task orchestration and state management",
                "notes": f"Error: {e}",
            }

    async def check_prometheus(self) -> dict[str, Any]:
        try:
            url = self._config.observability.prometheus.url
            resp = await self._client.get(f"{url}/-/healthy")
            if resp.status_code == 200:
                version = "Unknown"
                try:
                    vr = await self._client.get(f"{url}/api/v1/status/buildinfo")
                    if vr.status_code == 200:
                        v = vr.json().get("data", {}).get("version")
                        if v:
                            version = v
                except Exception:
                    pass
                return {
                    "component": "Prometheus",
                    "type": "Metrics Storage",
                    "status": "online",
                    "version": version,
                    "purpose": "Time-series metrics database and query engine",
                    "notes": "Health endpoint responding",
                }
            raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            return {
                "component": "Prometheus",
                "type": "Metrics Storage",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Time-series metrics database and query engine",
                "notes": f"Error: {e}",
            }

    async def check_grafana(self) -> dict[str, Any]:
        try:
            url = self._config.observability.grafana.url
            resp = await self._client.get(f"{url}/api/health")
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "Unknown")
                db_status = data.get("database", "unknown")
                return {
                    "component": "Grafana",
                    "type": "Visualization Platform",
                    "status": "online" if db_status == "ok" else "degraded",
                    "version": version,
                    "purpose": "Metrics visualization and dashboards",
                    "notes": f"API responding, database: {db_status}",
                }
            raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            return {
                "component": "Grafana",
                "type": "Visualization Platform",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Metrics visualization and dashboards",
                "notes": f"Error: {e}",
            }

    async def check_otel_collector(self) -> dict[str, Any]:
        try:
            otel_url = self._config.observability.otel.url
            health_url = self._config.observability.otel.health_url
            zpages_url = self._config.observability.otel.zpages_url
            version = "Unknown"
            status = "online"
            notes = "OTLP endpoint responding"

            # Health check endpoint
            try:
                resp = await self._client.get(f"{health_url}/")
                if resp.status_code == 200:
                    notes = "Health check endpoint responding"
            except Exception:
                pass

            # Version from zPages
            try:
                resp = await self._client.get(f"{zpages_url}/debug/servicez")
                if resp.status_code == 200:
                    html = resp.text
                    m = re.search(
                        r"<b>Version</b>.*?([0-9]+\.[0-9]+\.[0-9]+)",
                        html,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if m and re.match(r"^\d+\.\d+\.\d+$", m.group(1)):
                        version = m.group(1)
            except Exception:
                config_version = self._config.observability.otel.version
                if config_version:
                    version = config_version

            # Verify OTLP endpoint
            resp = await self._client.post(f"{otel_url}/v1/metrics", json={})
            if resp.status_code in (200, 400, 405):
                return {
                    "component": "OpenTelemetry Collector",
                    "type": "Telemetry Gateway",
                    "status": status,
                    "version": version,
                    "purpose": "Collect, process, and export telemetry data (OTLP)",
                    "notes": notes,
                }
            raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            return {
                "component": "OpenTelemetry Collector",
                "type": "Telemetry Gateway",
                "status": "offline",
                "version": "Unknown",
                "purpose": "Collect, process, and export telemetry data (OTLP)",
                "notes": f"Error: {e}",
            }

    async def check_langfuse(self) -> dict[str, Any]:
        try:
            url = self._config.langfuse.host
            resp = await self._client.get(f"{url}/api/public/health")
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "Unknown")
                api_status = data.get("status", "unknown")
                return {
                    "component": "LangFuse",
                    "type": "LLM Observability",
                    "status": "online" if api_status == "OK" else "degraded",
                    "version": version,
                    "purpose": "LLM call tracking and tracing (SIP-0061)",
                    "notes": f"API responding, status: {api_status}",
                }
            raise RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            return {
                "component": "LangFuse",
                "type": "LLM Observability",
                "status": "offline",
                "version": "Unknown",
                "purpose": "LLM call tracking and tracing (SIP-0061)",
                "notes": f"Error: {e}",
            }

    async def check_keycloak(self) -> dict[str, Any]:
        try:
            auth_config = self._config.auth
            if not auth_config.enabled or auth_config.provider == "disabled":
                return {
                    "component": "Keycloak",
                    "type": "Identity Provider",
                    "status": "disabled",
                    "version": "N/A",
                    "purpose": "OIDC authentication (SIP-0062)",
                    "notes": "Auth disabled or provider=disabled",
                }
            if auth_config.oidc is None:
                return {
                    "component": "Keycloak",
                    "type": "Identity Provider",
                    "status": "not configured",
                    "version": "N/A",
                    "purpose": "OIDC authentication (SIP-0062)",
                    "notes": "OIDC config not set",
                }

            issuer_url = auth_config.oidc.issuer_url.rstrip("/")
            base_url = issuer_url.split("/realms/")[0] if "/realms/" in issuer_url else issuer_url
            discovery_url = f"{issuer_url}/.well-known/openid-configuration"

            try:
                resp = await self._client.get(discovery_url)
                if resp.status_code == 200:
                    discovery = resp.json()
                    issuer = discovery.get("issuer", "")
                    realm = issuer.rsplit("/realms/", 1)[-1] if "/realms/" in issuer else "unknown"
                    version = await self._fetch_keycloak_version(base_url)
                    return {
                        "component": "Keycloak",
                        "type": "Identity Provider",
                        "status": "online",
                        "version": version,
                        "purpose": "OIDC authentication (SIP-0062)",
                        "notes": f"Realm: {realm}, OIDC discovery OK",
                    }
            except Exception:
                pass

            # Fallback: health endpoint
            try:
                resp = await self._client.get(f"{base_url}/health/ready")
                if resp.status_code == 200:
                    version = await self._fetch_keycloak_version(base_url)
                    return {
                        "component": "Keycloak",
                        "type": "Identity Provider",
                        "status": "online",
                        "version": version,
                        "purpose": "OIDC authentication (SIP-0062)",
                        "notes": "Health endpoint responding",
                    }
            except Exception:
                pass

            raise RuntimeError("Both OIDC discovery and health endpoints unreachable")
        except Exception as e:
            return {
                "component": "Keycloak",
                "type": "Identity Provider",
                "status": "offline",
                "version": "Unknown",
                "purpose": "OIDC authentication (SIP-0062)",
                "notes": f"Error: {e}",
            }

    async def _fetch_keycloak_version(self, base_url: str) -> str:
        """Best-effort Keycloak version fetch via admin API."""
        try:
            import os

            kc_cfg = getattr(self._config.auth, "keycloak", None)
            if kc_cfg and kc_cfg.admin:
                admin_user = kc_cfg.admin.username
                admin_pass = kc_cfg.admin.password
            else:
                admin_user = os.environ.get("SQUADOPS__AUTH__KEYCLOAK__ADMIN__USERNAME")
                admin_pass = os.environ.get("SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD")
            if not admin_user or not admin_pass:
                return "Unknown"

            token_url = f"{base_url}/realms/master/protocol/openid-connect/token"
            resp = await self._client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": admin_user,
                    "password": admin_pass,
                },
            )
            if resp.status_code != 200:
                return "Unknown"
            admin_token = resp.json().get("access_token")
            if not admin_token:
                return "Unknown"

            info_resp = await self._client.get(
                f"{base_url}/admin/serverinfo",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if info_resp.status_code != 200:
                return "Unknown"
            return info_resp.json().get("systemInfo", {}).get("version", "Unknown")
        except Exception:
            return "Unknown"
