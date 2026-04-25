"""
Pydantic models for SquadOps configuration schema.
"""

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TasksBackend(StrEnum):
    """Task backend selection."""

    SQL = "sql"
    PREFECT = "prefect"


class SSLMode(StrEnum):
    """SSL/TLS connection mode."""

    DISABLE = "disable"
    REQUIRE = "require"
    VERIFY_FULL = "verify-full"


class MigrationMode(StrEnum):
    """Migration execution mode."""

    OFF = "off"
    STARTUP = "startup"
    JOB = "job"


class ConnectionMode(StrEnum):
    """Database connection mode."""

    DIRECT = "direct"
    PROXY = "proxy"


class SSLConfig(BaseModel):
    """SSL/TLS configuration for database connections."""

    mode: SSLMode = Field(
        default=SSLMode.DISABLE, description="SSL mode (disable, require, verify-full)"
    )
    ca_bundle_path: Path | None = Field(
        default=None, description="Path to CA bundle file (optional)"
    )


class PoolConfig(BaseModel):
    """Connection pool configuration."""

    size: int = Field(default=5, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, description="Max pool overflow connections")
    timeout_seconds: int = Field(default=30, ge=1, description="Pool timeout in seconds")


class MigrationConfig(BaseModel):
    """Migration execution configuration."""

    mode: MigrationMode = Field(
        default=MigrationMode.OFF, description="Migration mode (off, startup, job)"
    )


class DBConfig(BaseModel):
    """Database configuration."""

    # Legacy fields (maintained for backward compatibility)
    url: str | None = Field(default=None, description="PostgreSQL connection URL (legacy, use dsn)")
    pool_size: int = Field(
        default=5, ge=1, le=100, description="Connection pool size (legacy, use pool.size)"
    )
    max_overflow: int = Field(
        default=10,
        ge=0,
        description="Max pool overflow connections (legacy, use pool.max_overflow)",
    )
    pool_timeout: int = Field(
        default=30, ge=1, description="Pool timeout in seconds (legacy, use pool.timeout_seconds)"
    )
    echo: bool = Field(default=False, description="Enable SQL query logging")

    # SIP-0.8.3: New deployment profile contract fields
    dsn: str | None = Field(
        default=None,
        description="Full PostgreSQL connection string (supports secret:// references)",
    )
    ssl: SSLConfig | None = Field(default=None, description="SSL/TLS configuration")
    pool: PoolConfig | None = Field(default=None, description="Connection pool configuration")
    migrations: MigrationConfig | None = Field(
        default=None, description="Migration execution configuration"
    )
    connection: ConnectionMode | None = Field(
        default=None, description="Connection mode (direct, proxy)"
    )
    migrations_dir: str = Field(
        default="infra/migrations",
        description="Path to SQL migrations directory",
    )

    @field_validator("dsn", "url", mode="before")
    @classmethod
    def validate_dsn_or_url(cls, v: Any, info: Any) -> Any:
        """Ensure at least one of dsn or url is provided."""
        return v

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation and backward compatibility."""
        # Validate that at least one of dsn or url is provided
        if self.dsn is None and self.url is None:
            raise ValueError("Either 'dsn' or 'url' must be provided for database configuration")

        # If dsn is not provided, use url as fallback (backward compatibility)
        if self.dsn is None and self.url is not None:
            self.dsn = self.url

        # If pool config is not provided, use legacy fields (backward compatibility)
        if self.pool is None:
            self.pool = PoolConfig(
                size=self.pool_size,
                max_overflow=self.max_overflow,
                timeout_seconds=self.pool_timeout,
            )

        # If ssl config is not provided, use default
        if self.ssl is None:
            self.ssl = SSLConfig()

        # If migrations config is not provided, use default
        if self.migrations is None:
            self.migrations = MigrationConfig()

        # If connection mode is not provided, default to direct
        if self.connection is None:
            self.connection = ConnectionMode.DIRECT


class RabbitMQConfig(BaseModel):
    """RabbitMQ configuration."""

    url: str = Field(..., description="RabbitMQ connection URL (amqp://...)")
    host: str = Field(default="rabbitmq", description="RabbitMQ host")
    port: int = Field(default=5672, ge=1, le=65535, description="RabbitMQ port")
    user: str = Field(default="squadops", description="RabbitMQ username")
    password: str | None = Field(
        default=None, description="RabbitMQ password (use secret:// reference)"
    )
    vhost: str = Field(default="/", description="RabbitMQ virtual host")


class RedisConfig(BaseModel):
    """Redis configuration."""

    url: str = Field(..., description="Redis connection URL (redis://...)")
    host: str = Field(default="redis", description="Redis host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    db: int = Field(default=0, ge=0, description="Redis database number")


class CommsConfig(BaseModel):
    """Communication services configuration."""

    rabbitmq: RabbitMQConfig = Field(..., description="RabbitMQ configuration")
    redis: RedisConfig = Field(..., description="Redis configuration")


class SecretsConfig(BaseModel):
    """Secrets management configuration."""

    provider: Literal["env", "file", "docker_secret"] = Field(
        ..., description="Secrets provider (required)"
    )
    env_prefix: str | None = Field(
        default=None,
        description="Environment variable prefix (defaults to SQUADOPS_ for env provider, normalized to end with _)",
    )
    file_dir: Path | None = Field(
        default=None, description="File provider directory (required if provider=file)"
    )
    name_map: dict[str, str] | None = Field(
        default=None, description="Logical name to provider key mapping"
    )

    @field_validator("file_dir")
    @classmethod
    def validate_file_dir(cls, v, info):
        """Validate that file_dir is provided when provider=file."""
        if info.data.get("provider") == "file" and v is None:
            raise ValueError("file_dir is required when provider=file")
        return v


class OIDCConfig(BaseModel):
    """OIDC provider configuration (SIP-0062)."""

    issuer_url: str = Field(
        ..., description="OIDC issuer URL (e.g. http://keycloak:8080/realms/squadops)"
    )
    issuer_public_url: str | None = Field(
        default=None,
        description="Browser-facing issuer URL (e.g. http://localhost:8180/realms/squadops). "
        "Defaults to issuer_url if not set. Required when issuer_url uses a Docker-internal hostname.",
    )
    audience: str = Field(..., description="Expected token audience (client ID)")
    jwks_url: str | None = Field(
        default=None,
        description="JWKS endpoint URL (defaults to {issuer_url}/protocol/openid-connect/certs)",
    )
    roles_claim_path: str = Field(
        default="realm_access.roles",
        description="Dot-delimited path to roles in JWT claims",
    )
    jwks_cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="JWKS cache TTL in seconds"
    )
    jwks_forced_refresh_min_interval_seconds: int = Field(
        default=30,
        ge=5,
        description="Minimum interval between forced JWKS refreshes (stampede protection)",
    )
    clock_skew_seconds: int = Field(
        default=60, ge=0, description="Allowed clock skew for token expiry checks"
    )


class ConsoleAuthConfig(BaseModel):
    """Console OIDC configuration — deferred to Phase 3a (SIP-0062)."""

    client_id: str = Field(..., description="OIDC client ID for console (public client)")
    redirect_uri: str = Field(
        default="http://localhost:3000/auth/callback",
        description="OAuth2 redirect URI",
    )
    post_logout_redirect_uri: str = Field(
        default="http://localhost:3000",
        description="Post-logout redirect URI",
    )


class ServiceClientConfig(BaseModel):
    """Service-to-service client credentials (SIP-0062)."""

    client_id: str = Field(..., description="Service client ID")
    client_secret: str = Field(
        ..., description="Service client secret (supports secret:// references)"
    )


class KeycloakTokenPolicyConfig(BaseModel):
    """Keycloak token lifetime policy (SIP-0063)."""

    access_token_minutes: int = Field(default=10, ge=1)
    refresh_token_minutes: int = Field(default=1440, ge=1)
    refresh_token_rotation: bool = True


class KeycloakSessionPolicyConfig(BaseModel):
    """Keycloak session timeout policy (SIP-0063)."""

    idle_minutes: int = Field(default=30, ge=1)
    max_minutes: int = Field(default=480, ge=1)


class KeycloakTotpPolicyConfig(BaseModel):
    """Keycloak TOTP policy (SIP-0063)."""

    algorithm: str = "HmacSHA1"
    digits: int = Field(default=6, ge=6, le=8)
    period: int = Field(default=30, ge=20, le=60)


class KeycloakSecurityConfig(BaseModel):
    """Keycloak security settings (SIP-0063)."""

    mfa_required_for_admin: bool = True
    mfa_required_for_operator: bool = True
    mfa_method: str = "totp"  # "totp" | "webauthn" | "totp+webauthn"
    totp_policy: KeycloakTotpPolicyConfig = Field(default_factory=KeycloakTotpPolicyConfig)
    brute_force_protection: bool = True
    max_login_failures: int = Field(default=5, ge=1)
    wait_increment_seconds: int = Field(default=60, ge=1)
    max_wait_seconds: int = Field(default=900, ge=1)


class KeycloakLoggingConfig(BaseModel):
    """Keycloak event logging settings (SIP-0063)."""

    admin_events_enabled: bool = True
    login_events_enabled: bool = True


class KeycloakAdminConfig(BaseModel):
    """Keycloak admin account configuration (SIP-0063)."""

    username: str = "admin"
    password: str  # Supports secret:// references
    allowed_networks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cidr_networks(self) -> "KeycloakAdminConfig":
        """Validate allowed_networks entries are valid CIDRs."""
        import ipaddress

        for cidr in self.allowed_networks:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as e:
                raise ValueError(f"Invalid CIDR in allowed_networks: {cidr!r} — {e}") from e
        return self


class KeycloakOperationalConfig(BaseModel):
    """Keycloak operational deployment configuration (SIP-0063)."""

    realm: str = "squadops-dev"
    base_url: str = "http://localhost:8180"
    public_url: str | None = None
    db_dsn: str | None = None  # secret:// ref
    proxy_mode: str = "none"  # "none" | "edge" | "reencrypt" | "passthrough"
    external_tls_termination: bool = False
    hostname_strict: bool = False
    admin: KeycloakAdminConfig
    token_policy: KeycloakTokenPolicyConfig = Field(default_factory=KeycloakTokenPolicyConfig)
    session_policy: KeycloakSessionPolicyConfig = Field(default_factory=KeycloakSessionPolicyConfig)
    security: KeycloakSecurityConfig = Field(default_factory=KeycloakSecurityConfig)
    logging: KeycloakLoggingConfig = Field(default_factory=KeycloakLoggingConfig)

    def model_post_init(self, __context: Any) -> None:
        """Cross-field validation for deployed (non-dev) environments."""
        _LOOPBACK = ("localhost", "127.0.0.1", "::1")
        is_deployed = self.realm != "squadops-dev"

        if is_deployed:
            if self.db_dsn is None:
                raise ValueError("db_dsn required for deployed realms")
            if self.proxy_mode == "none":
                raise ValueError("proxy_mode must not be 'none' for deployed realms")
            if not self.hostname_strict:
                raise ValueError("hostname_strict must be true for deployed realms")
            if self.public_url and not self.public_url.startswith("https://"):
                raise ValueError("public_url must use HTTPS for deployed realms")
            if any(lb in self.base_url for lb in _LOOPBACK):
                raise ValueError("base_url must not reference loopback for deployed realms")

        # Proxy + TLS mutual consistency
        if self.proxy_mode == "edge" and not self.external_tls_termination:
            raise ValueError("external_tls_termination must be true when proxy_mode is 'edge'")
        if self.proxy_mode == "none" and self.external_tls_termination:
            raise ValueError("external_tls_termination must be false when proxy_mode is 'none'")
        if self.external_tls_termination and not self.public_url:
            raise ValueError("public_url required when external_tls_termination is true")
        if self.proxy_mode in ("edge", "reencrypt", "passthrough") and not self.public_url:
            raise ValueError("public_url required when proxy_mode is not 'none'")


class AuthConfig(BaseModel):
    """Authentication and authorization configuration (SIP-0062)."""

    enabled: bool = Field(default=True, description="Enable authentication")
    provider: str = Field(default="keycloak", description="Auth provider: 'keycloak' or 'disabled'")
    oidc: OIDCConfig | None = Field(default=None, description="OIDC provider configuration")
    console: ConsoleAuthConfig | None = Field(
        default=None, description="Console OIDC configuration (Phase 3a)"
    )
    service_clients: dict[str, ServiceClientConfig] = Field(
        default_factory=dict, description="Named service client configurations"
    )
    roles_mode: str = Field(
        default="realm", description="Role extraction mode: 'realm' or 'client'"
    )
    roles_client_id: str | None = Field(
        default=None,
        description="Client ID for role extraction when roles_mode='client'",
    )
    expose_docs: bool = Field(
        default=False,
        description="Allow unauthenticated access to /docs and /openapi.json",
    )
    keycloak: KeycloakOperationalConfig | None = Field(
        default=None, description="Keycloak operational configuration (SIP-0063)"
    )

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        if self.roles_mode == "client" and not self.roles_client_id:
            raise ValueError("roles_client_id is required when roles_mode='client'")
        if self.enabled and self.provider not in ("keycloak", "disabled"):
            raise ValueError(f"Unknown auth provider: {self.provider}")
        if self.enabled and self.provider != "disabled" and self.oidc is None:
            raise ValueError(
                "oidc configuration is required when auth is enabled and provider != 'disabled'"
            )
        if self.enabled and self.provider == "keycloak" and self.keycloak is None:
            pass  # keycloak operational config is optional — only needed for deploy profiles


class CyclesConfig(BaseModel):
    """Cycle registry configuration."""

    registry_provider: str = Field(
        default="memory",
        description="Cycle registry provider: 'memory' or 'postgres'",
    )
    squad_profile_provider: str = Field(
        default="config",
        description="Squad profile provider: 'config' or 'postgres' (SIP-0075)",
    )


class PrefectConfig(BaseModel):
    """Prefect orchestration configuration."""

    api_url: str = Field(default="http://prefect-server:4200/api", description="Prefect API URL")
    api_key: str | None = Field(
        default=None, description="Prefect API key (use secret:// reference)"
    )
    timeout: int = Field(default=30, ge=1, description="Prefect API timeout in seconds")
    log_forwarding: bool = Field(
        default=True,
        description="Forward squadops/adapters log records to Prefect /api/logs (SIP-0087)",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum log level forwarded to Prefect (SIP-0087)",
    )


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    url: str = Field(
        default="http://host.docker.internal:11434", description="LLM API URL (Ollama)"
    )
    model: str | None = Field(default=None, description="Default LLM model name")
    use_local: bool = Field(default=True, description="Use local LLM provider")
    timeout: int = Field(default=180, ge=1, description="LLM request timeout in seconds")


class AgentConfig(BaseModel):
    """Agent-specific configuration."""

    id: str = Field(default="unknown_agent", description="Agent identifier")
    role: str = Field(default="unknown", description="Agent role")
    display_name: str | None = Field(default=None, description="Agent display name")
    instances_file: Path = Field(
        default=Path("agents/instances/instances.yaml"), description="Agent instances file path"
    )
    heartbeat_timeout_window: int = Field(
        default=90, ge=1, description="Heartbeat timeout window in seconds"
    )
    reconciliation_interval: int = Field(
        default=45, ge=1, description="Reconciliation interval in seconds"
    )
    a2a_messaging_enabled: bool = Field(
        default=False, description="Enable A2A messaging for this agent (SIP-0085)"
    )
    a2a_port: int = Field(default=8080, ge=1024, le=65535, description="A2A messaging server port")

    @field_validator("instances_file", mode="before")
    @classmethod
    def validate_instances_file_path(cls, v: Any) -> Any:
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v


class CycleDataConfig(BaseModel):
    """Cycle data storage configuration."""

    root: Path = Field(default=Path("cycle_data"), description="Root directory for cycle data")


class AWSTelemetryConfig(BaseModel):
    """AWS-specific telemetry configuration."""

    region: str | None = Field(default=None, description="AWS region")
    cloudwatch_logs_group: str = Field(
        default="squadops/agents", description="CloudWatch logs group"
    )
    xray_tracing_enabled: bool = Field(default=True, description="Enable X-Ray tracing")


class AzureTelemetryConfig(BaseModel):
    """Azure-specific telemetry configuration."""

    connection_string: str | None = Field(default=None, description="Azure connection string")
    instrumentation_key: str | None = Field(default=None, description="Azure instrumentation key")


class GCPTelemetryConfig(BaseModel):
    """GCP-specific telemetry configuration."""

    project_id: str | None = Field(default=None, description="GCP project ID")
    credentials_path: str | None = Field(default=None, description="Path to GCP credentials JSON")


class TelemetryConfig(BaseModel):
    """Telemetry and observability configuration."""

    backend: str | None = Field(
        default=None, description="Telemetry backend override (opentelemetry, aws, azure, gcp)"
    )
    otlp_endpoint: str | None = Field(default=None, description="OTLP exporter endpoint")
    prometheus_port: int = Field(
        default=8888, ge=1, le=65535, description="Prometheus metrics port"
    )
    aws: AWSTelemetryConfig | None = Field(default=None, description="AWS telemetry config")
    azure: AzureTelemetryConfig | None = Field(default=None, description="Azure telemetry config")
    gcp: GCPTelemetryConfig | None = Field(default=None, description="GCP telemetry config")


class PromptsConfig(BaseModel):
    """Prompt asset source configuration (SIP-0084).

    Controls whether handlers resolve request templates from the local
    filesystem or from Langfuse's prompt management API.
    """

    asset_source_provider: str = Field(
        default="filesystem",
        description="Prompt asset source provider: 'filesystem' or 'langfuse'",
    )


class LangFuseConfig(BaseModel):
    """LangFuse LLM observability configuration (SIP-0061).

    Sibling to TelemetryConfig, NOT nested inside it.
    """

    enabled: bool = Field(default=False, description="Enable LangFuse integration")
    host: str = Field(default="http://localhost:3000", description="LangFuse host URL")
    public_key: str = Field(
        default="", description="LangFuse public key (supports secret:// references)"
    )
    secret_key: str = Field(
        default="", description="LangFuse secret key (supports secret:// references)"
    )
    redaction_mode: str = Field(
        default="standard",
        description="Redaction mode: 'standard' or 'strict' (recommended for prod)",
    )
    sample_rate_percent: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Generation sampling rate (0-100). Applies to record_generation only; spans/events always emit.",
    )
    flush_interval_seconds: int = Field(
        default=5, ge=1, description="Background flush interval in seconds"
    )
    buffer_max_size: int = Field(
        default=1000, ge=1, description="Maximum buffer size before drop-oldest overflow"
    )
    shutdown_flush_timeout_seconds: int = Field(
        default=5, ge=1, description="Max time budget for shutdown flush"
    )


class ServiceConfig(BaseModel):
    """Generic service URL configuration."""

    url: str = Field(..., description="Service URL")


class OTelConfig(BaseModel):
    """OpenTelemetry Collector configuration."""

    url: str = Field(default="http://otel-collector:4318", description="OTLP endpoint URL")
    health_url: str = Field(default="http://otel-collector:13133", description="Health check URL")
    zpages_url: str = Field(default="http://otel-collector:55679", description="ZPages URL")
    version: str | None = Field(default=None, description="OTel Collector version")


class ObservabilityConfig(BaseModel):
    """Observability service URLs for health checks."""

    prometheus: ServiceConfig = Field(
        default_factory=lambda: ServiceConfig(url="http://prometheus:9090")
    )
    grafana: ServiceConfig = Field(default_factory=lambda: ServiceConfig(url="http://grafana:3000"))
    otel: OTelConfig = Field(default_factory=OTelConfig)
    health_check: ServiceConfig = Field(
        default_factory=lambda: ServiceConfig(url="http://health-check:8000"),
        description="Health check service URL",
    )


class FileManagerConfig(BaseModel):
    """File manager configuration."""

    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".md", ".py", ".js", ".html", ".css", ".json", ".yaml", ".yml"],
        description="Allowed file extensions",
    )
    max_file_size: int = Field(
        default=10485760, ge=1, description="Maximum file size in bytes (10MB)"
    )


class DockerConfig(BaseModel):
    """Docker deployment configuration."""

    network_name: str = Field(default="squad-ops_squadnet", description="Docker network name")
    default_port: int = Field(default=8080, ge=1, le=65535, description="Default application port")
    restart_policy: str = Field(default="unless-stopped", description="Docker restart policy")


class DeploymentConfig(BaseModel):
    """Deployment and infrastructure tooling configuration."""

    file_manager: FileManagerConfig = Field(default_factory=FileManagerConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)


class AppConfig(BaseModel):
    """Main application configuration model."""

    # Core infrastructure
    db: DBConfig = Field(..., description="Database configuration")
    comms: CommsConfig = Field(..., description="Communication services configuration")

    # Runtime API
    runtime_api_url: str = Field(default="http://runtime-api:8001", description="Runtime API URL")

    # Task management
    tasks_backend: TasksBackend = Field(
        default=TasksBackend.PREFECT, description="Task backend selection"
    )

    # Secrets and auth
    secrets: SecretsConfig | None = Field(
        default=None, description="Secrets management configuration (optional)"
    )
    auth: AuthConfig = Field(
        default_factory=AuthConfig, description="Authentication configuration (SIP-0062)"
    )

    # Cycles
    cycles: CyclesConfig = Field(
        default_factory=CyclesConfig, description="Cycle registry configuration"
    )

    # Orchestration
    prefect: PrefectConfig = Field(
        default_factory=PrefectConfig, description="Prefect configuration"
    )

    # LLM
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")

    # Prompts (SIP-0084)
    prompts: PromptsConfig = Field(
        default_factory=PromptsConfig, description="Prompt asset source configuration"
    )

    # Agent
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent configuration")

    # Cycle data
    cycle_data: CycleDataConfig = Field(
        default_factory=CycleDataConfig, description="Cycle data configuration"
    )

    # Telemetry
    telemetry: TelemetryConfig = Field(
        default_factory=TelemetryConfig, description="Telemetry configuration"
    )

    # LangFuse LLM Observability (SIP-0061) — sibling to telemetry, not nested
    langfuse: LangFuseConfig = Field(
        default_factory=LangFuseConfig, description="LangFuse LLM observability configuration"
    )

    # Observability
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig, description="Observability service URLs"
    )

    # Deployment
    deployment: DeploymentConfig = Field(
        default_factory=DeploymentConfig, description="Deployment tooling configuration"
    )

    # Private attributes for runtime state (not part of config validation)
    _profile: str | None = None
    _db_runtime: Any = None

    @field_validator("cycle_data", mode="before")
    @classmethod
    def validate_cycle_data_path(cls, v: Any) -> Any:
        """Convert string paths to Path objects."""
        if isinstance(v, dict) and "root" in v and isinstance(v["root"], str):
            v["root"] = Path(v["root"])
        return v

    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=True)
