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


class DBRetryConfig(BaseModel):
    """Retry on a transient database error inside the Postgres adapters (#1976): a connection that
    could not be made, or a transaction Postgres rolled back (a serialization failure or a
    deadlock). Never a whole method, and never a connection lost mid-statement."""

    attempts: int = Field(
        default=3, ge=1, le=10, description="Tries for a transient failure, the first included"
    )
    backoff_seconds: float = Field(
        default=0.05, ge=0, le=5, description="The first pause between tries; it doubles each time"
    )


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
    retry: DBRetryConfig = Field(
        default_factory=DBRetryConfig, description="Retry on a transient database error (#1976)"
    )
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


class QueueConfig(BaseModel):
    """The queue transport's selector (#301, composition-roots.md §6.2).

    Named for the PORT it selects, not ``comms.provider``: ``CommsConfig`` holds three
    independent things — the queue, the A2A transport and Redis — and a selector named for all
    of them would read as choosing all of them. The vendor's own settings stay under the
    vendor's key (``comms.rabbitmq.url``), read by the factory when the selector names it.
    Required with no default (R2): a defaulted selector is a masking fallback.
    """

    provider: Literal["rabbitmq"] = Field(
        ..., description="Queue transport selecting the adapter (required, never defaulted)"
    )


class A2AConfig(BaseModel):
    """The agent-to-agent transport's selector and tunables (#301, §6.3).

    One legal value today, and still required by R2's stated rule: the selector records that
    this deployment's agent messaging IS the HTTP transport. A second value is added when a
    root needs one, not speculatively. The two client timeouts that were constructor defaults
    (``a2a_client.py``) are tunables here with the same defaults (R5).
    """

    provider: Literal["http"] = Field(
        ..., description="A2A transport selecting the adapter (required, never defaulted)"
    )
    timeout_seconds: float = Field(default=180.0, gt=0, description="A2A request timeout")
    agent_card_timeout_seconds: float = Field(
        default=10.0, gt=0, description="Agent-card fetch timeout"
    )


class ChatConfig(BaseModel):
    """Console chat's tunables (SIP-0085; #2175): how much of a session's history a turn carries
    to its agent. The oldest turns are dropped first, and the request counts what it dropped. Then
    its memory records, under their own caps (SIP-0110 §A.3.6's chat budget, #2180)."""

    history_max_turns: int = Field(
        default=20, ge=0, description="Earlier messages a chat turn carries at most"
    )
    history_max_tokens: int = Field(
        default=8000,
        ge=0,
        description="Estimated tokens of history a chat turn carries at most (4 chars a token)",
    )
    memory_max_notes: int = Field(
        default=8,
        ge=0,
        description="Notes a chat turn's memory context carries at most (SIP-0110 §A.3.10, #2180)",
    )
    memory_max_tokens: int = Field(
        default=1500,
        ge=0,
        description=(
            "Estimated tokens of memory records (instructions, preferences, notes) a chat turn "
            "carries at most; a record that doesn't fit is left out whole and listed"
        ),
    )


class CommsDeliveryConfig(BaseModel):
    """How many times an agent runs one dispatched task, and the record that counts them (#1977;
    SIP-Agent-Comms-Delivery-Guarantees §5.1, §5.3 and §5.3a, as amended 2026-10-14)."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Deliveries of one task an agent runs before it quarantines and fails it",
    )
    marker_ttl_seconds: int = Field(
        default=86400,
        ge=60,
        description="How long a task's attempt count and completion mark are kept in Redis",
    )
    dead_letter_queue: str = Field(
        default="comms.dlq", description="Where a task past its attempts is quarantined"
    )


class CommsConfig(BaseModel):
    """Communication services configuration."""

    queue: QueueConfig = Field(..., description="Queue transport selector (required)")
    a2a: A2AConfig = Field(..., description="A2A transport selector and tunables (required)")
    rabbitmq: RabbitMQConfig = Field(..., description="RabbitMQ configuration")
    redis: RedisConfig = Field(..., description="Redis configuration")
    chat: ChatConfig = Field(default_factory=ChatConfig, description="Console chat's tunables")
    delivery: CommsDeliveryConfig = Field(
        default_factory=CommsDeliveryConfig,
        description="A dispatched task's delivery bound (#1977)",
    )


class FilesystemToolConfig(BaseModel):
    """The agent's filesystem adapter selector (#301, §6.4)."""

    provider: Literal["local"] = Field(
        ..., description="Filesystem adapter selecting the implementation (required)"
    )


class ToolsConfig(BaseModel):
    """Agent tool adapters (#301, §6.4). Added because no ``tools`` section existed and the
    agent root bound its filesystem adapter by direct construction."""

    filesystem: FilesystemToolConfig = Field(..., description="Filesystem adapter selector")


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


class SandboxConfig(BaseModel):
    """Ephemeral Application Sandbox configuration (SIP-0102).

    The dormant posture is provider "noop": every execution path in-process and byte-identical
    to pre-0102 behavior. It is named, never defaulted (#1568).
    """

    provider: Literal["noop", "docker"] = Field(
        description="Sandbox provider (required, #1568; the vocabulary is the schema's, R2)"
    )
    environment: str = Field(
        default="fullstack_fastapi_react",
        description="Environment-contract stack id (see squadops.sandbox.environment)",
    )
    workspace_root: Path = Field(
        default=Path("cycle_data/sandbox"),
        description="Root directory for cycle workspaces (bind-mounted into execution units)",
    )
    cache_root: Path | None = Field(
        default=None,
        description=(
            "Read-through download caches (pip/npm) shared across cycles — §4.7: "
            "download caches only, never installed-dependency dirs, never semantic. "
            "None disables cache mounts."
        ),
    )
    image: str = Field(
        default="",
        description=(
            "Override of the environment contract's pinned image (empty = use the "
            "contract's; the actually-used image rides every result as evidence)"
        ),
    )
    app_port: int = Field(
        default=8000, description="Container port the application runtime listens on"
    )
    app_network: str | None = Field(
        default=None,
        description=(
            "The internal network the sandbox service starts apps on, by container name with no "
            "host port (#2451 part 4). Required by the service's root when it runs docker; absent, "
            "as on a host run (the audit scripts), apps publish to loopback."
        ),
    )
    service_url: str = Field(
        default="http://127.0.0.1:8002",
        description="Sandbox service base URL (loopback per the SIP-0102 transport decision)",
    )
    service_token: str = Field(
        default="",
        description=(
            "Bearer token for the sandbox service's narrow API (supports secret:// "
            "references). Interim shared-secret auth; the Keycloak service-identity "
            "(#326) upgrade rides SIP-0102 phase 102.3 when runtime-api becomes the caller."
        ),
    )


class SandboxClientConfig(BaseModel):
    """How the runtime API calls the sandbox service (#2451, ruled by the owner 2026-10-18).

    Its own section, apart from ``SandboxConfig``: that one is the service's (and the
    cycle-create preflight's, which reads it unchanged), and its env reader refuses fields it
    doesn't know. The runtime API requires this section at startup; no other process reads it.
    """

    provider: Literal["none", "http"] = Field(
        description="The runtime API's sandbox client (required where read, #1568): http calls "
        "the sandbox service; none calls nothing, and every caller reads it as unavailable"
    )
    service_url: str = Field(default="", description="The sandbox service's base URL")
    service_token: str = Field(
        default="", description="The sandbox service's bearer token (supports secret://)"
    )
    #: #2586: a declared run's setup steps and its command are each bounded by this on the
    #: service, and the client waits for all of them. 600 s is the container backend's own.
    command_timeout_seconds: float = Field(
        default=600.0,
        gt=0,
        description="The longest one declared step (a product's install or check) may run in "
        "the sandbox; the client waits for every step of a run (#2586)",
    )

    @model_validator(mode="after")
    def _http_names_its_service(self) -> "SandboxClientConfig":
        if self.provider == "http" and not (self.service_url and self.service_token):
            raise ValueError(
                "sandbox_client.provider 'http' names its service: set "
                "SQUADOPS__SANDBOX_CLIENT__SERVICE_URL and SQUADOPS__SANDBOX_CLIENT__SERVICE_TOKEN"
            )
        return self


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
    #: #2498: the identity provider's own, which its container reads from .env. No service reads it,
    #: so a profile carries none, and no service mounts it.
    password: str | None = None
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
    provider: Literal["keycloak", "disabled"] = Field(
        description="Auth provider (required, #1568; the vocabulary is the schema's, R2)"
    )
    oidc: OIDCConfig | None = Field(default=None, description="OIDC provider configuration")
    console: ConsoleAuthConfig | None = Field(
        default=None, description="Console OIDC configuration (Phase 3a)"
    )
    service_clients: dict[str, ServiceClientConfig] = Field(
        default_factory=dict, description="Named service client configurations"
    )
    agent_client: ServiceClientConfig | None = Field(
        default=None,
        description=(
            "Client credentials an agent container uses for outbound calls to "
            "runtime-api (heartbeats via POST /api/v1/agents/status, #326). "
            "First-class field (not a service_clients entry) so it is addressable "
            "via SQUADOPS__AUTH__AGENT_CLIENT__* env vars; requires oidc.issuer_url "
            "for the token endpoint. Independent of `enabled`, which governs "
            "inbound request validation only."
        ),
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
        if self.enabled and self.provider != "disabled" and self.oidc is None:
            raise ValueError(
                "oidc configuration is required when auth is enabled and provider != 'disabled'"
            )
        if self.enabled and self.provider == "keycloak" and self.keycloak is None:
            pass  # keycloak operational config is optional — only needed for deploy profiles


class CyclesConfig(BaseModel):
    """Cycle registry configuration."""

    #: #1568: a runtime API started without this key ran an in-memory registry and lost every
    #: cycle at restart. Required; never defaulted.
    registry_provider: Literal["memory", "postgres"] = Field(
        description="Cycle registry provider (required, #1568)",
    )
    squad_profile_provider: Literal["config", "postgres"] = Field(
        description="Squad profile provider (SIP-0075; required, #1568)",
    )
    #: SIP-0112 FR-03 (#2408): ``config`` reads config/projects.yaml, the only authority before
    #: the cutover; ``postgres`` is the writable registry, the only one after it;
    #: ``postgres_read_only`` is that registry with its writes gated off, the rollback (R3).
    #: Required, so a deploy names which is authoritative rather than inheriting it.
    project_registry_provider: Literal["config", "postgres", "postgres_read_only"] = Field(
        description="Project registry provider (SIP-0112 FR-03; required, #1568)",
    )
    inert_cycle_threshold: int = Field(
        default=3,
        ge=1,
        description=(
            "SIP-0096 §9 N: consecutive not-executed cycles before a stable "
            "framework check is surfaced as inert (#684)"
        ),
    )


class ProjectsConfig(BaseModel):
    """What a Project registration may name as its repository (SIP-0112, the owner's R5).

    Empty is the safe default for both: any ``https``/``ssh`` host, and no local path at all,
    since a path on a caller's machine authorizes nothing on the server's.
    """

    locator_allowed_hosts: list[str] = Field(
        default_factory=list,
        description="Hosts a registration's repository may live on; empty allows any (R5)",
    )
    locator_local_roots: list[str] = Field(
        default_factory=list,
        description="Absolute directories under which a local repository path is allowed (R5)",
    )
    #: E.4.2: the managed clones' cache. The external repository stays authoritative, and a lost
    #: clone is fetched again (§B.3), but a run's captured change and a private product's clone
    #: can't be: compose mounts the default path from ./data/repo_cache, so a redeploy keeps them
    #: (#2588).
    clone_cache_root: Path = Field(
        default=Path("cycle_data/repo_cache"),
        description="Where the managed clones of registered products are kept (SIP-0112 FR-05)",
    )
    git_timeout_seconds: float = Field(
        default=300.0, gt=0, description="The longest one clone, fetch or read may take"
    )
    #: #2575: a reference resolver's ``bind`` runs under the campaign launcher's single lock, so
    #: one family that hangs would stall every campaign. The repository family's slowest call is a
    #: ``git cat-file`` in the managed clone, which never clones or fetches (#2565).
    reference_resolver_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description=(
            "The longest one reference resolver call (a bind, a read, or whether a project binds "
            "nothing) may take before it is a fault (#2575)"
        ),
    )
    #: E.4.3: who a captured candidate's commit names. The .invalid address is no one's mailbox,
    #: so a deploy that contributes under its own identity says so here.
    committer_name: str = Field(
        default="SquadOps", description="The name a squad's captured commit is made under"
    )
    committer_email: str = Field(
        default="squadops@squadops.invalid",
        description="The email a squad's captured commit is made under",
    )
    #: E.4.3's review_request contributions: each Project's token, scoped by its owner to that
    #: one repository (contents and pull requests). Written as secret:// references, which the
    #: loader resolves; a Project with none contributes nothing by review request.
    review_request_tokens: dict[str, str] = Field(
        default_factory=dict,
        description="Project ID to its review-request token, each a secret:// reference",
    )


class SchedulerConfig(BaseModel):
    """Duty-transition scheduler configuration (SIP-0089 §2.4).

    The in-process `DutyScheduler` opens/closes duty windows by requesting
    transitions through the `RuntimeCoordinator`. It is **opt-in** (`enabled`
    defaults false) so a deployment activates duty mode deliberately. The
    scheduler is a single central writer of `mode`; running more than one
    runtime-api instance with it enabled would create two writers (see the
    single-writer note at the bootstrap call site).
    """

    enabled: bool = Field(
        default=False,
        description="Activate the in-process duty-transition scheduler (SIP-0089 §2.4)",
    )
    poll_interval_seconds: int = Field(
        default=30,
        ge=1,
        description="Seconds between duty-window scheduler ticks",
    )


class RuntimeConfig(BaseModel):
    """Agent runtime-state configuration (SIP-0089)."""

    scheduler: SchedulerConfig = Field(
        default_factory=SchedulerConfig,
        description="Duty-transition scheduler configuration (SIP-0089 §2.4)",
    )


class DispatchConfig(BaseModel):
    """The orchestrator's side of a dispatched task (#1147).

    ``task_timeout`` is how long a task may run before the orchestrator calls the agent
    hung — several LLM calls, file I/O, a whole test-suite execution. It is a different
    quantity from ``llm.timeout``, which bounds one HTTP call to the model, and until
    #1147 both were read from ``SQUADOPS__LLM__TIMEOUT``.

    **Required where tasks are dispatched, never inherited (1.8.2 plan §3.2 item 15).** Until
    1.8.2 an unset value followed ``llm.timeout``, so raising the model-call timeout for a
    long emission silently raised the hung-agent detector with it; deploy B″ ran that way at
    1,800 s. The value is absent in a process that dispatches nothing (every agent), and
    ``AppConfig.task_timeout_seconds`` refuses where it is read. Compose refuses to start the
    runtime API without it.
    """

    task_timeout: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Seconds the orchestrator waits for a dispatched task before calling the agent "
            "hung (SQUADOPS__DISPATCH__TASK_TIMEOUT). Required by the runtime API, which "
            "dispatches; absent in processes that do not. Never follows llm.timeout."
        ),
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
    """LLM provider configuration.

    ``provider`` is **required** (#1157, SIP-0106 Ruling 3): a selector at a
    composition seam is never defaulted. Two adapters were in the tree while the
    factory silently returned Ollama for every caller — a missing value must fail
    at config load exactly as a misspelt one fails in the factory. Every deploy
    surface writes ``SQUADOPS__LLM__PROVIDER`` explicitly; nothing infers it.
    """

    provider: Literal["ollama", "vllm", "atlas", "tensorfold"] = Field(
        description="LLM provider selecting the adapter (required; the vocabulary is the schema's, R2)",
    )
    url: str = Field(
        description=(
            "LLM API URL (required, never defaulted, #2249): a host Ollama through the Docker host "
            "gateway, the Spark's container at http://ollama:11434"
        ),
    )
    api_key: str | None = Field(
        default=None,
        description=(
            "Bearer token for a provider that requires one (Atlas bound off localhost does; "
            "Ollama does not). Write it as a secret:// reference — the loader resolves it."
        ),
    )
    model: str | None = Field(default=None, description="Default LLM model name")
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

    #: The telemetry selector: ``otel``, ``console`` or ``null``, the names
    #: ``adapters.telemetry.factory`` accepts. Required schema-wide (#1568): #1449 refused it only
    #: where composed, which left a second mechanism beside every other selector's.
    backend: Literal["otel", "console", "null"] = Field(
        description="Telemetry backend selector (required, #1568)"
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

    #: #1568: a Literal, so a misspelled provider fails at config load. As a plain ``str`` it
    #: reached the agent root's renderer ``try``, whose broad ``except`` logged it and ran the
    #: agent with no renderer (the #1110 blind-retry shape) instead of refusing the deploy.
    asset_source_provider: Literal["filesystem", "langfuse"] = Field(
        description="Prompt asset source provider (required, #1568)",
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

    # Core infrastructure. The database is the runtime API's: an agent never connects to it, so it
    # declares none and holds no credential that reaches it (#2457). ``database()`` requires it.
    db: DBConfig | None = Field(
        default=None, description="Database configuration: the runtime API's, absent in an agent"
    )
    comms: CommsConfig = Field(..., description="Communication services configuration")

    # Runtime API
    runtime_api_url: str = Field(default="http://runtime-api:8001", description="Runtime API URL")

    # Secrets and auth
    secrets: SecretsConfig | None = Field(
        default=None, description="Secrets management configuration (optional)"
    )
    auth: AuthConfig = Field(
        ...,
        description="Authentication configuration (SIP-0062) (carries a required selector, #1568)",
    )

    # Cycles
    cycles: CyclesConfig = Field(
        ..., description="Cycle registry configuration (carries a required selector, #1568)"
    )

    # Projects (SIP-0112: what a registration may name as its repository)
    projects: ProjectsConfig = Field(
        default_factory=ProjectsConfig, description="Project registration rules (SIP-0112 R5)"
    )

    # Runtime (SIP-0089: agent runtime state, duty scheduler)
    runtime: RuntimeConfig = Field(
        default_factory=RuntimeConfig, description="Agent runtime-state configuration (SIP-0089)"
    )

    # Orchestration
    prefect: PrefectConfig = Field(
        default_factory=PrefectConfig, description="Prefect configuration"
    )

    # LLM
    llm: LLMConfig = Field(description="LLM configuration (required: it names the provider)")
    tools: ToolsConfig = Field(..., description="Agent tool adapter selectors (required, #301)")
    dispatch: DispatchConfig = Field(
        default_factory=DispatchConfig,
        description="Orchestrator-side dispatch bounds (#1147)",
    )

    def task_timeout_seconds(self) -> float:
        """The orchestrator's per-task wait: ``dispatch.task_timeout``, required here, at the
        one place it is read (1.8.2 plan §3.2 item 15; #1147 separated it from llm.timeout)."""
        if self.dispatch.task_timeout is None:
            raise ValueError(
                "dispatch.task_timeout is required where tasks are dispatched: set "
                "SQUADOPS__DISPATCH__TASK_TIMEOUT (seconds). It no longer follows llm.timeout "
                "(1.8.2 plan §3.2 item 15)."
            )
        return float(self.dispatch.task_timeout)

    def database(self) -> DBConfig:
        """The database, required at the places a pool is made: the runtime API and its scripts.
        An agent declares none, so it holds no credential that reaches the held-out scenarios'
        tables, or any other (#2457, IR-4)."""
        if self.db is None:
            raise ValueError(
                "this process connects to Postgres and has no database configured: set "
                "SQUADOPS__DB__URL. Only the runtime API and its scripts declare one (#2457)."
            )
        return self.db

    # Prompts (SIP-0084)
    prompts: PromptsConfig = Field(
        ..., description="Prompt asset source configuration (carries a required selector, #1568)"
    )

    # Agent
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent configuration")

    # Cycle data
    cycle_data: CycleDataConfig = Field(
        default_factory=CycleDataConfig, description="Cycle data configuration"
    )

    # Telemetry
    telemetry: TelemetryConfig = Field(
        ..., description="Telemetry configuration (carries a required selector, #1568)"
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

    # Application sandbox (SIP-0102)
    sandbox: SandboxConfig = Field(
        ...,
        description="Ephemeral Application Sandbox configuration (SIP-0102; required selector, #1568)",
    )
    # The runtime API's client of the sandbox service (#2451). Optional here because only the
    # runtime API reads it, and it refuses to start without it (``create_sandbox_client``).
    sandbox_client: SandboxClientConfig | None = Field(
        default=None, description="The runtime API's sandbox client (#2451)"
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
