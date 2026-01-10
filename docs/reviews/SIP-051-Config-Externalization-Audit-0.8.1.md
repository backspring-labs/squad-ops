# SIP-051 Config Externalization Audit (0.8.1)

**Date**: 2024-12-20  
**Version**: 0.8.1  
**Auditor**: Automated SIP-051 Compliance Review

## Executive Summary

This audit reviews the SquadOps codebase for compliance with SIP-051: Config Profiles and Validation. The audit identified **165 instances** of direct environment variable reads (`os.getenv`, `os.environ`), with the majority being legitimate uses (strict mode flags, test setup, or non-config system information). However, **47 findings** require migration to the centralized config system.

### Key Findings

- ✅ **Old config modules removed**: No remaining imports from `config.unified_config` or `config.deployment_config`
- ✅ **No dotenv usage**: No `load_dotenv` or `dotenv` imports found
- ⚠️ **47 config reads to migrate**: Runtime services and agents reading config directly
- ⚠️ **Schema gaps**: Missing telemetry, observability, and deployment tooling config
- ✅ **Redaction & fingerprint**: Properly implemented and used in startup logging
- ⚠️ **YAML gaps**: Missing observability service URLs and telemetry config

### Compliance Status

**Overall**: ~70% compliant. Core infrastructure (DB, RabbitMQ, Redis, Prefect, LLM) is centralized. Remaining gaps are in:
- Telemetry/observability configuration
- Health-check service discovery URLs
- Deployment tooling (Docker, file manager defaults)

---

## Findings Table

| Finding | File:Line | Current Usage | Target Config Key | Layer | Classification | Action |
|---------|-----------|---------------|-------------------|-------|----------------|--------|
| **SQUADOPS_STRICT_CONFIG** | Multiple (47 instances) | Reading strict mode flag | N/A (loader internal) | env | **Allowed** | Keep as-is - this is the loader's own config |
| **SQUADOPS_PROFILE** | `infra/config/loader.py:48` | Profile selection | N/A (loader internal) | env | **Allowed** | Keep as-is - this is the loader's own config |
| **TELEMETRY_BACKEND** | `agents/telemetry/router.py:61` | Telemetry backend override | `config.telemetry.backend` | env | **Must migrate** | Add to schema, migrate |
| **OTEL_EXPORTER_OTLP_ENDPOINT** | `agents/telemetry/router.py:128` | OTLP endpoint | `config.telemetry.otlp_endpoint` | env | **Must migrate** | Add to schema, migrate |
| **PROMETHEUS_METRICS_PORT** | `agents/telemetry/router.py:133`, `agents/base_agent.py:1988` | Prometheus port | `config.telemetry.prometheus_port` | defaults/base | **Must migrate** | Add to schema, migrate |
| **AWS_REGION** | `agents/telemetry/router.py:142` | AWS region for telemetry | `config.telemetry.aws.region` | profile/env | **Must migrate** | Add to schema, migrate |
| **CLOUDWATCH_LOGS_GROUP** | `agents/telemetry/router.py:143` | CloudWatch logs group | `config.telemetry.aws.cloudwatch_logs_group` | profile/env | **Must migrate** | Add to schema, migrate |
| **XRAY_TRACING_ENABLED** | `agents/telemetry/router.py:144` | X-Ray tracing flag | `config.telemetry.aws.xray_tracing_enabled` | profile/env | **Must migrate** | Add to schema, migrate |
| **AZURE_CONNECTION_STRING** | `agents/telemetry/router.py:147` | Azure connection string | `config.telemetry.azure.connection_string` | profile/env | **Must migrate** | Add to schema, migrate |
| **AZURE_INSTRUMENTATION_KEY** | `agents/telemetry/router.py:148` | Azure instrumentation key | `config.telemetry.azure.instrumentation_key` | profile/env | **Must migrate** | Add to schema, migrate |
| **GCP_PROJECT_ID** | `agents/telemetry/router.py:151` | GCP project ID | `config.telemetry.gcp.project_id` | profile/env | **Must migrate** | Add to schema, migrate |
| **GOOGLE_APPLICATION_CREDENTIALS** | `agents/telemetry/router.py:152` | GCP credentials path | `config.telemetry.gcp.credentials_path` | profile/env | **Must migrate** | Add to schema, migrate |
| **OLLAMA_URL** | `agents/llm/router.py:76`, `agents/llm/providers/ollama.py:39` | LLM URL override | `config.llm.url` | env | **Must migrate** | Already in schema, migrate code |
| **USE_LOCAL_LLM** | `agents/llm/router.py:152` | Local LLM flag | `config.llm.use_local` | env | **Must migrate** | Already in schema, migrate code |
| **INSTANCES_FILE** | `infra/health-check/main.py:478` | Agent instances file path | `config.agent.instances_file` | defaults/base | **Must migrate** | Add to schema, migrate |
| **PROMETHEUS_URL** | `infra/health-check/main.py:872` | Prometheus service URL | `config.observability.prometheus.url` | defaults/base | **Must migrate** | Add to schema, migrate |
| **GRAFANA_URL** | `infra/health-check/main.py:916` | Grafana service URL | `config.observability.grafana.url` | defaults/base | **Must migrate** | Add to schema, migrate |
| **OTEL_COLLECTOR_URL** | `infra/health-check/main.py:957` | OTel collector URL | `config.observability.otel.url` | defaults/base | **Must migrate** | Add to schema, migrate |
| **OTEL_COLLECTOR_HEALTH_URL** | `infra/health-check/main.py:958` | OTel health URL | `config.observability.otel.health_url` | defaults/base | **Must migrate** | Add to schema, migrate |
| **OTEL_COLLECTOR_ZPAGES_URL** | `infra/health-check/main.py:989` | OTel zpages URL | `config.observability.otel.zpages_url` | defaults/base | **Must migrate** | Add to schema, migrate |
| **OTEL_COLLECTOR_VERSION** | `infra/health-check/main.py:1042,1050,1061` | OTel version | `config.observability.otel.version` | defaults/base | **Must migrate** | Add to schema, migrate |
| **HEARTBEAT_TIMEOUT_WINDOW_SECONDS** | `infra/health-check/main.py:1113,1286` | Heartbeat timeout | `config.agent.heartbeat_timeout_window` | defaults/base | **Must migrate** | Add to schema, migrate |
| **RECONCILIATION_INTERVAL_SECONDS** | `infra/health-check/main.py:1269` | Reconciliation interval | `config.agent.reconciliation_interval` | defaults/base | **Must migrate** | Add to schema, migrate |
| **HEALTH_CHECK_URL** | `agents/base_agent.py:1446` | Health check service URL | `config.runtime_api_url` (or new field) | defaults/base | **Must migrate** | Use existing or add new field |
| **HOSTNAME** | `agents/base_agent.py:621` | Container hostname | N/A | - | **False positive** | System info, not config |
| **ALLOWED_EXTENSIONS** | `agents/tools/file_manager.py:308`, `agents/roles/dev/file_manager.py:308` | File extension allowlist | `config.deployment.file_manager.allowed_extensions` | defaults/base | **Must migrate** | Add to schema, migrate |
| **MAX_FILE_SIZE** | `agents/tools/file_manager.py:322`, `agents/roles/dev/file_manager.py:322` | Max file size | `config.deployment.file_manager.max_file_size` | defaults/base | **Must migrate** | Add to schema, migrate |
| **WARM_BOOT_DIR** | `agents/tools/file_manager.py:350`, `agents/roles/dev/file_manager.py:350` | Warm boot directory | `config.deployment.warm_boot_dir` | defaults/base | **Must migrate** | Add to schema, migrate |
| **DOCKER_NETWORK_NAME** | `agents/tools/docker_manager.py:78`, `agents/roles/dev/docker_manager.py:78` | Docker network name | `config.deployment.docker.network_name` | defaults/base | **Must migrate** | Add to schema, migrate |
| **DEFAULT_APP_PORT** | `agents/tools/docker_manager.py:79`, `agents/roles/dev/docker_manager.py:79` | Default app port | `config.deployment.docker.default_port` | defaults/base | **Must migrate** | Add to schema, migrate |
| **DOCKER_RESTART_POLICY** | `agents/tools/docker_manager.py:80`, `agents/roles/dev/docker_manager.py:80` | Docker restart policy | `config.deployment.docker.restart_policy` | defaults/base | **Must migrate** | Add to schema, migrate |
| **PREFECT_API_URL** (env set) | `agents/tasks/prefect_adapter.py:106` | Setting Prefect env var | N/A | - | **False positive** | Setting env for Prefect client, not reading config |
| **PREFECT_API_KEY** (env set) | `agents/tasks/prefect_adapter.py:108` | Setting Prefect env var | N/A | - | **False positive** | Setting env for Prefect client, not reading config |
| **Test env vars** | `tests/integration/*.py` (multiple) | Test setup | N/A | - | **Allowed** | Test fixtures, keep as-is |
| **SQUADOPS_MAINTAINER** | `scripts/maintainer/update_sip_status.py:43` | Maintainer flag | N/A | - | **Allowed** | Script tooling, keep as-is |
| **USER** | `scripts/maintainer/update_sip_status.py:247` | System user | N/A | - | **False positive** | System info, not config |
| **CLI args** | `infra/config/loader.py:305` | CLI parsing for --profile, --strict-config | N/A | - | **Allowed** | Loader's own CLI interface, keep as-is |

---

## Schema Completeness Analysis

### ✅ Already in Schema

- `db.*` - Database configuration
- `comms.rabbitmq.*` - RabbitMQ configuration
- `comms.redis.*` - Redis configuration
- `prefect.*` - Prefect configuration
- `llm.*` - LLM configuration (but code still reads `OLLAMA_URL` and `USE_LOCAL_LLM` directly)
- `agent.id`, `agent.role` - Basic agent config
- `cycle_data.root` - Cycle data storage
- `runtime_api_url` - Runtime API URL
- `tasks_backend` - Task backend selection

### ❌ Missing from Schema

#### 1. Telemetry Configuration
```python
class TelemetryConfig(BaseModel):
    """Telemetry and observability configuration."""
    backend: str | None = Field(default=None, description="Telemetry backend override")
    otlp_endpoint: str | None = Field(default=None, description="OTLP exporter endpoint")
    prometheus_port: int = Field(default=8888, ge=1, le=65535, description="Prometheus metrics port")
    
    # AWS-specific
    aws: AWSTelemetryConfig | None = Field(default=None, description="AWS telemetry config")
    
    # Azure-specific
    azure: AzureTelemetryConfig | None = Field(default=None, description="Azure telemetry config")
    
    # GCP-specific
    gcp: GCPTelemetryConfig | None = Field(default=None, description="GCP telemetry config")

class AWSTelemetryConfig(BaseModel):
    region: str | None = None
    cloudwatch_logs_group: str = Field(default="squadops/agents")
    xray_tracing_enabled: bool = Field(default=True)

class AzureTelemetryConfig(BaseModel):
    connection_string: str | None = None
    instrumentation_key: str | None = None

class GCPTelemetryConfig(BaseModel):
    project_id: str | None = None
    credentials_path: str | None = None
```

#### 2. Observability Service URLs
```python
class ObservabilityConfig(BaseModel):
    """Observability service URLs for health checks."""
    prometheus: ServiceConfig = Field(default_factory=lambda: ServiceConfig(url="http://prometheus:9090"))
    grafana: ServiceConfig = Field(default_factory=lambda: ServiceConfig(url="http://grafana:3000"))
    otel: OTelConfig = Field(default_factory=OTelConfig)

class ServiceConfig(BaseModel):
    url: str

class OTelConfig(BaseModel):
    url: str = Field(default="http://otel-collector:4318")
    health_url: str = Field(default="http://otel-collector:13133")
    zpages_url: str = Field(default="http://otel-collector:55679")
    version: str | None = None
```

#### 3. Agent Lifecycle Configuration
```python
class AgentConfig(BaseModel):
    """Agent-specific configuration."""
    id: str = Field(default="unknown_agent", description="Agent identifier")
    role: str = Field(default="unknown", description="Agent role")
    display_name: str | None = Field(default=None, description="Agent display name")
    instances_file: Path = Field(default=Path("agents/instances/instances.yaml"), description="Agent instances file path")
    heartbeat_timeout_window: int = Field(default=90, ge=1, description="Heartbeat timeout window in seconds")
    reconciliation_interval: int = Field(default=45, ge=1, description="Reconciliation interval in seconds")
```

#### 4. Deployment Tooling Configuration
```python
class DeploymentConfig(BaseModel):
    """Deployment and infrastructure tooling configuration."""
    file_manager: FileManagerConfig = Field(default_factory=FileManagerConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    warm_boot_dir: Path = Field(default=Path("/app/warm-boot"), description="Warm boot directory")

class FileManagerConfig(BaseModel):
    allowed_extensions: list[str] = Field(default_factory=lambda: [".md", ".py", ".js", ".html", ".css", ".json", ".yaml", ".yml"])
    max_file_size: int = Field(default=10485760, ge=1, description="Maximum file size in bytes (10MB)")

class DockerConfig(BaseModel):
    network_name: str = Field(default="squad-ops_squadnet", description="Docker network name")
    default_port: int = Field(default=8080, ge=1, le=65535, description="Default application port")
    restart_policy: str = Field(default="unless-stopped", description="Docker restart policy")
```

---

## YAML File Gaps

### `config/defaults.yaml` - Missing Entries

```yaml
# Telemetry configuration
telemetry:
  prometheus_port: 8888

# Observability service URLs
observability:
  prometheus:
    url: "http://prometheus:9090"
  grafana:
    url: "http://grafana:3000"
  otel:
    url: "http://otel-collector:4318"
    health_url: "http://otel-collector:13133"
    zpages_url: "http://otel-collector:55679"

# Agent lifecycle configuration
agent:
  instances_file: "agents/instances/instances.yaml"
  heartbeat_timeout_window: 90
  reconciliation_interval: 45

# Deployment tooling
deployment:
  file_manager:
    allowed_extensions: [".md", ".py", ".js", ".html", ".css", ".json", ".yaml", ".yml"]
    max_file_size: 10485760
  docker:
    network_name: "squad-ops_squadnet"
    default_port: 8080
    restart_policy: "unless-stopped"
  warm_boot_dir: "/app/warm-boot"
```

### `config/base.yaml` - Missing Entries

Same as defaults.yaml (base.yaml should mirror defaults for non-secret common settings).

### `config/profiles/*.yaml` - Missing Entries

Profile-specific overrides may be needed for:
- `observability.*` URLs (different per environment)
- `telemetry.aws.*`, `telemetry.azure.*`, `telemetry.gcp.*` (cloud-specific)

### `.env.example` - Missing Documentation

Should document:
```bash
# Telemetry
SQUADOPS__TELEMETRY__BACKEND=opentelemetry
SQUADOPS__TELEMETRY__OTLP_ENDPOINT=http://localhost:4317
SQUADOPS__TELEMETRY__PROMETHEUS_PORT=8888

# Observability (for health-check service)
SQUADOPS__OBSERVABILITY__PROMETHEUS__URL=http://prometheus:9090
SQUADOPS__OBSERVABILITY__GRAFANA__URL=http://grafana:3000
SQUADOPS__OBSERVABILITY__OTEL__URL=http://otel-collector:4318

# Agent lifecycle
SQUADOPS__AGENT__INSTANCES_FILE=agents/instances/instances.yaml
SQUADOPS__AGENT__HEARTBEAT_TIMEOUT_WINDOW=90
SQUADOPS__AGENT__RECONCILIATION_INTERVAL=45

# Deployment tooling
SQUADOPS__DEPLOYMENT__FILE_MANAGER__ALLOWED_EXTENSIONS=.md,.py,.js
SQUADOPS__DEPLOYMENT__FILE_MANAGER__MAX_FILE_SIZE=10485760
SQUADOPS__DEPLOYMENT__DOCKER__NETWORK_NAME=squad-ops_squadnet
SQUADOPS__DEPLOYMENT__DOCKER__DEFAULT_PORT=8080
```

---

## Redaction & Fingerprint Verification

### ✅ Startup Logging Status

| Service | Profile Logged | Strict Mode Logged | Fingerprint Logged | Status |
|----------|----------------|-------------------|-------------------|--------|
| `infra/runtime-api/main.py` | ✅ (via load_config) | ✅ | ✅ | **Compliant** |
| `agents/base_agent.py` | ❌ | ❌ | ✅ | **Partial** - Missing profile/strict logging |
| `infra/health-check/main.py` | ❌ | ❌ | ❌ | **Non-compliant** - No config logging |

### Redaction Implementation

✅ **Properly implemented** in `infra/config/redaction.py`:
- Key-based redaction (password, secret, token, api_key, etc.)
- DSN/URL redaction (postgresql://, amqp://, redis://, http://, https://)
- Nested dictionary support
- List support

### Fingerprint Implementation

✅ **Properly implemented** in `infra/config/fingerprint.py`:
- Uses redacted config before hashing
- Deterministic ordering (sort_keys=True)
- SHA256 hash (first 16 chars)
- Prefixed with "cfg-"

### Recommendations

1. **Add profile/strict logging to `agents/base_agent.py`**:
   ```python
   logger.info(f"Configuration profile: {self.config._profile} (strict={strict_mode})")
   logger.info(f"Configuration fingerprint: {fingerprint}")
   ```

2. **Add config logging to `infra/health-check/main.py`**:
   ```python
   logger.info(f"Configuration profile: {config._profile} (strict={strict_mode})")
   redacted_config = redact_config(config.model_dump())
   fingerprint = config_fingerprint(redacted_config)
   logger.info(f"Configuration fingerprint: {fingerprint}")
   ```

---

## Prioritized TODO List

### Phase 1: Schema Extensions (Dependencies: None)

1. **Add TelemetryConfig to schema.py**
   - Create `TelemetryConfig`, `AWSTelemetryConfig`, `AzureTelemetryConfig`, `GCPTelemetryConfig` models
   - Add `telemetry: TelemetryConfig` field to `AppConfig`
   - **Files**: `infra/config/schema.py`

2. **Add ObservabilityConfig to schema.py**
   - Create `ObservabilityConfig`, `ServiceConfig`, `OTelConfig` models
   - Add `observability: ObservabilityConfig` field to `AppConfig`
   - **Files**: `infra/config/schema.py`

3. **Extend AgentConfig in schema.py**
   - Add `instances_file`, `heartbeat_timeout_window`, `reconciliation_interval` fields
   - **Files**: `infra/config/schema.py`

4. **Add DeploymentConfig to schema.py**
   - Create `DeploymentConfig`, `FileManagerConfig`, `DockerConfig` models
   - Add `deployment: DeploymentConfig` field to `AppConfig`
   - **Files**: `infra/config/schema.py`

### Phase 2: YAML Updates (Dependencies: Phase 1)

5. **Update defaults.yaml**
   - Add telemetry, observability, agent lifecycle, and deployment defaults
   - **Files**: `config/defaults.yaml`

6. **Update base.yaml**
   - Mirror defaults.yaml entries (non-secret common settings)
   - **Files**: `config/base.yaml`

7. **Update profile YAMLs**
   - Add environment-specific observability URLs if needed
   - Add cloud-specific telemetry configs for dev/stage/prod
   - **Files**: `config/profiles/*.yaml`

8. **Create/update .env.example**
   - Document all new env var overrides
   - **Files**: `.env.example`

### Phase 3: Code Migrations (Dependencies: Phase 1, Phase 2)

9. **Migrate telemetry/router.py**
   - Replace `os.getenv('TELEMETRY_BACKEND')` → `config.telemetry.backend`
   - Replace `os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')` → `config.telemetry.otlp_endpoint`
   - Replace `os.getenv('PROMETHEUS_METRICS_PORT')` → `config.telemetry.prometheus_port`
   - Replace AWS/Azure/GCP env reads → `config.telemetry.aws.*`, etc.
   - **Files**: `agents/telemetry/router.py`

10. **Migrate llm/router.py**
    - Replace `os.getenv('OLLAMA_URL')` → `config.llm.url`
    - Replace `os.getenv('USE_LOCAL_LLM')` → `config.llm.use_local`
    - **Files**: `agents/llm/router.py`, `agents/llm/providers/ollama.py`

11. **Migrate health-check/main.py**
    - Replace `os.getenv('INSTANCES_FILE')` → `config.agent.instances_file`
    - Replace `os.getenv('PROMETHEUS_URL')` → `config.observability.prometheus.url`
    - Replace `os.getenv('GRAFANA_URL')` → `config.observability.grafana.url`
    - Replace `os.getenv('OTEL_COLLECTOR_*')` → `config.observability.otel.*`
    - Replace `os.getenv('HEARTBEAT_TIMEOUT_WINDOW_SECONDS')` → `config.agent.heartbeat_timeout_window`
    - Replace `os.getenv('RECONCILIATION_INTERVAL_SECONDS')` → `config.agent.reconciliation_interval`
    - Add config logging (profile, strict, fingerprint)
    - **Files**: `infra/health-check/main.py`

12. **Migrate base_agent.py**
    - Replace `os.getenv('PROMETHEUS_METRICS_PORT')` → `config.telemetry.prometheus_port`
    - Replace `os.getenv('HEALTH_CHECK_URL')` → Use `config.runtime_api_url` or new field
    - Add profile/strict logging
    - **Files**: `agents/base_agent.py`

13. **Migrate file_manager.py (tools and roles/dev)**
    - Replace `os.getenv('ALLOWED_EXTENSIONS')` → `config.deployment.file_manager.allowed_extensions`
    - Replace `os.getenv('MAX_FILE_SIZE')` → `config.deployment.file_manager.max_file_size`
    - Replace `os.getenv('WARM_BOOT_DIR')` → `config.deployment.warm_boot_dir`
    - **Files**: `agents/tools/file_manager.py`, `agents/roles/dev/file_manager.py`

14. **Migrate docker_manager.py (tools and roles/dev)**
    - Replace `os.getenv('DOCKER_NETWORK_NAME')` → `config.deployment.docker.network_name`
    - Replace `os.getenv('DEFAULT_APP_PORT')` → `config.deployment.docker.default_port`
    - Replace `os.getenv('DOCKER_RESTART_POLICY')` → `config.deployment.docker.restart_policy`
    - **Files**: `agents/tools/docker_manager.py`, `agents/roles/dev/docker_manager.py`

### Phase 4: Testing (Dependencies: Phase 3)

15. **Add unit tests for new config keys**
    - Test telemetry config loading
    - Test observability config loading
    - Test agent lifecycle config loading
    - Test deployment config loading
    - **Files**: `tests/unit/test_config_loader.py`

16. **Add integration tests for profile switching**
    - Test observability URLs change per profile
    - Test telemetry config changes per profile
    - **Files**: `tests/integration/test_config_profiles.py`

17. **Add regression tests**
    - Test that all migrated code paths use AppConfig
    - Test that no new `os.getenv` calls are added for config
    - **Files**: New test file or extend existing

---

## Test Gaps & Recommendations

### Current Test Coverage

✅ **Existing tests**:
- `tests/unit/test_config_loader.py` - Tests loader, precedence, validation, redaction, fingerprinting
- `tests/integration/test_config_profiles.py` - Tests runtime-api startup, strict mode, redacted logging

### Missing Test Coverage

1. **Telemetry config loading**
   - Test AWS/Azure/GCP telemetry configs load correctly
   - Test OTLP endpoint override
   - Test Prometheus port override

2. **Observability config loading**
   - Test service URLs load from defaults/base/profile
   - Test OTel config structure

3. **Agent lifecycle config**
   - Test instances_file path resolution
   - Test heartbeat/reconciliation intervals

4. **Deployment config**
   - Test file manager defaults
   - Test Docker defaults

5. **Profile-specific overrides**
   - Test dev/stage/prod profiles have different observability URLs
   - Test cloud telemetry configs per profile

6. **Regression prevention**
   - Lint rule or test that fails if new `os.getenv` calls are added in runtime code
   - Test that all config reads go through AppConfig

### Recommended Test Additions

```python
# tests/unit/test_config_telemetry.py
def test_telemetry_config_loading():
    """Test telemetry configuration loads correctly"""
    config = load_config()
    assert config.telemetry.prometheus_port == 8888
    assert config.telemetry.backend is None  # default

def test_telemetry_aws_config():
    """Test AWS telemetry config structure"""
    config = load_config()
    if config.telemetry.aws:
        assert config.telemetry.aws.region is not None
        assert config.telemetry.aws.cloudwatch_logs_group == "squadops/agents"

# tests/integration/test_observability_config.py
def test_observability_urls_per_profile():
    """Test observability URLs change per profile"""
    local_config = load_config(profile="local")
    dev_config = load_config(profile="dev")
    # Assert URLs differ per profile if configured

# tests/unit/test_config_regression.py
def test_no_direct_env_reads():
    """Regression test: ensure no new os.getenv calls in runtime code"""
    # Use AST parsing to find os.getenv calls in agents/, infra/ (excluding tests)
    # Fail if new ones are found
```

---

## Summary Statistics

- **Total findings**: 165
- **Must migrate**: 47
- **Allowed exceptions**: 115 (strict mode flags, test setup, system info)
- **False positives**: 3 (HOSTNAME, USER, env var setting)
- **Schema gaps**: 4 major areas (telemetry, observability, agent lifecycle, deployment)
- **YAML gaps**: ~15 missing entries across defaults/base/profiles
- **Code compliance**: ~70% (core infra done, telemetry/observability/tooling pending)

---

## Conclusion

SIP-051 implementation is **substantially complete** for core infrastructure (database, messaging, orchestration, LLM). Remaining work focuses on:

1. **Telemetry/observability configuration** - Not yet centralized
2. **Health-check service discovery** - Using direct env reads
3. **Deployment tooling defaults** - File manager and Docker configs

The audit recommends completing schema extensions first, then YAML updates, followed by code migrations, and finally comprehensive testing. This ensures a clean, dependency-ordered implementation that maintains backward compatibility during the transition.

**Estimated effort**: 2-3 days for schema + YAML, 1-2 days for code migrations, 1 day for testing.

