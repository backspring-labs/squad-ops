# Continuum Control Plane — Repo Context Extraction

> Extracted: 2026-02-06 by Claude Code audit
> Purpose: Provide repo-accurate facts for SIP authoring (Control Plane UI via Continuum plugins)

---

# Repo Facts Summary

## SquadOps API Surface
- **Runtime API entrypoint**: `src/squadops/api/runtime/main.py` — FastAPI app on port 8001
- **Health Check app**: `src/squadops/api/health_app.py` — FastAPI app on port 8000 (slated for demolition)
- **Server startup**: `uvicorn squadops.api.runtime.main:app --host 0.0.0.0 --port 8001`
- **DI wiring**: `src/squadops/api/runtime/deps.py` — module-level singletons with setters/getters (no container framework)
- **Adapter initialization**: `src/squadops/api/runtime/main.py:startup_event()` — creates adapters via factory functions, calls `set_*()` on deps module

## Route Modules (Runtime API)
- **Auth**: `src/squadops/api/routes/auth.py` — prefix `/auth`, 1 endpoint (`/auth/userinfo`)
- **Projects**: `src/squadops/api/routes/cycles/projects.py` — prefix `/api/v1/projects`
- **Cycles**: `src/squadops/api/routes/cycles/cycles.py` — prefix `/api/v1/projects/{project_id}/cycles`
- **Runs**: `src/squadops/api/routes/cycles/runs.py` — prefix `/api/v1/projects/{project_id}/cycles/{cycle_id}/runs`
- **Profiles**: `src/squadops/api/routes/cycles/profiles.py` — prefix `/api/v1/squad-profiles`
- **Artifacts**: `src/squadops/api/routes/cycles/artifacts.py` — prefix `/api/v1` (various sub-paths)
- **DTOs**: `src/squadops/api/routes/cycles/dtos.py` — all Pydantic request/response models
- **Error mapping**: `src/squadops/api/routes/cycles/errors.py` — domain exception → HTTP status
- **Response mapping**: `src/squadops/api/routes/cycles/mapping.py` — domain model → DTO conversion
- **Legacy tasks**: `src/squadops/api/runtime/main.py` — 27 inline route handlers for `/api/v1/tasks/*`, `/api/v1/execution-cycles/*`

## Cycle Execution Ports (SIP-0064)
- `CycleRegistryPort` — `src/squadops/ports/cycles/cycle_registry.py` — Cycle + Run CRUD, gate decisions, artifact refs
- `ArtifactVaultPort` — `src/squadops/ports/cycles/artifact_vault.py` — immutable artifact storage + baselines
- `FlowExecutionPort` — `src/squadops/ports/cycles/flow_execution.py` — task flow dispatch (`execute_run`, `cancel_run`)
- `ProjectRegistryPort` — `src/squadops/ports/cycles/project_registry.py` — project CRUD
- `SquadProfilePort` — `src/squadops/ports/cycles/squad_profile.py` — squad profile resolution + snapshots

## Cycle Execution Adapters
- `adapters/cycles/memory_cycle_registry.py` — in-memory `CycleRegistryPort` (current default)
- `adapters/cycles/filesystem_artifact_vault.py` — filesystem `ArtifactVaultPort`
- `adapters/cycles/distributed_flow_executor.py` — RabbitMQ-dispatched `FlowExecutionPort`
- `adapters/cycles/in_process_flow_executor.py` — local `FlowExecutionPort`
- `adapters/cycles/config_project_registry.py` — YAML-file `ProjectRegistryPort`
- `adapters/cycles/config_squad_profile.py` — YAML-file `SquadProfilePort`
- `adapters/cycles/prefect_reporter.py` — Prefect REST API reporter (flow naming, task spans)
- `adapters/cycles/factory.py` — factory functions for all cycle adapters

## Domain Models
- `src/squadops/cycles/models.py` — `Cycle`, `Run`, `Gate`, `GateDecision`, `TaskFlowPolicy`, `ArtifactRef`, `SquadProfile`, `AgentProfileEntry`, `Project` (all frozen dataclasses)
- `src/squadops/cycles/lifecycle.py` — `compute_config_hash()`, `derive_cycle_status()`, run status state machine
- `src/squadops/tasks/models.py` — `TaskEnvelope`, `TaskResult`, `TaskIdentity`
- `src/squadops/tasks/legacy_models.py` — `Task`, `FlowRun`, `TaskState`, `FlowState`, `Artifact`
- `src/squadops/auth/models.py` — `Identity`, `TokenClaims`, `AuthContext`, `AuditEvent`, `Role`, `Scope`

## Auth Mechanism (SIP-0062)
- **Provider**: Keycloak (OIDC)
- **Middleware**: `src/squadops/api/middleware/auth.py` — `AuthMiddleware` (validates Bearer JWT), `RequestIDMiddleware`
- **Token flow**: `Authorization: Bearer <JWT>` → middleware validates via `AuthPort` → injects `Identity` into `request.state.identity`
- **CORS**: derived from `config.auth.console.redirect_uri` at startup
- **Role-based access**: `require_roles()` and `require_scopes()` FastAPI dependencies
- **Allowlisted paths**: `/health`, `/health/infra` (no token needed); `/docs`, `/openapi.json` (conditional)
- **Auth routes**: `GET /auth/userinfo` returns current identity

## Existing UI / Static Hosting (within SquadOps repo)
- **Templates directory**: `src/squadops/api/templates/` — contains only `health_dashboard.html` (Jinja2, part of health_app)
- **Warm-boot apps**: `warm-boot/apps/hello-squad/` and `warm-boot/apps/application/` — plain HTML+JS apps (not framework-based)
- **No SPA framework in SquadOps repo** — SvelteKit shell lives in external Continuum repo (`~/Code/continuum`)
- **No static file serving** configured on the SquadOps runtime API

## Continuum Shell (External Repo)

Continuum is a **plugin-driven control-plane UI shell** that lives in a separate repo: `https://github.com/backspring-labs/continuum` (local clone: `~/Code/continuum`).

### Architecture
- **Backend**: Python FastAPI — plugin discovery, loading, registry resolution, command bus, asset serving
- **Frontend**: SvelteKit + Vite — shell layout, region rendering, dynamic Web Component loading
- **Plugin UI**: Svelte compiled to Web Components (Custom Elements) — zero compile-time coupling to shell

### Runtime Lifecycle
`BOOTING` → `DISCOVERING_PLUGINS` → `LOADING_PLUGINS` → `RESOLVING_REGISTRY` → `READY` (or `DEGRADED`) → `STOPPING` → `STOPPED`

### Perspectives (built-in work modes)
| ID | Label | Route Prefix | Description |
|----|-------|-------------|-------------|
| `signal` | Signal | `/signal` | Monitor signals, metrics, alerts |
| `research` | Research | `/research` | Query and analyze data |
| `time` | Time | `/time` | Scheduling and timeline views |
| `discovery` | Discovery | `/discovery` | Browse and discover capabilities |
| `systems` | Systems | `/systems` | System admin and diagnostics |

### Regions (UI slots — host-defined anchors)
| Slot ID | Cardinality | Description |
|---------|-------------|-------------|
| `ui.slot.left_nav` | MANY | Perspective switcher + action triggers |
| `ui.slot.header` | ONE | Title, search, user profile |
| `ui.slot.main` | MANY | Primary content area (perspective-scoped) |
| `ui.slot.right_rail` | MANY | Secondary panels (activity feeds, lists) |
| `ui.slot.footer` | ONE | Status bar, system info |
| `ui.slot.modal` | MANY | Overlay dialogs (command palette) |
| `ui.slot.drawer` | MANY | Slide-in panels (agent chat, detail views) |
| `ui.slot.toast_stack` | MANY | Transient notifications |

### Plugin Manifest (`plugin.toml`)
```toml
[plugin]
id = "vendor.plugin_name"          # Required: vendor.name format
name = "Display Name"              # Required
version = "1.0.0"                  # Required: semver
description = "What it does"
required = false                   # If true, failure → DEGRADED

[plugin.ui]
tag_prefix = "vendor-plugin-name"  # Required: prefix for custom elements
bundle = "plugin.js"               # Path to built Web Component bundle (in dist/)

[[contributions.nav]]
slot = "ui.slot.left_nav"
label = "My Feature"
icon = "activity"                  # Lucide icon name
priority = 100
[contributions.nav.target]
type = "panel"                     # panel | command | drawer | route
panel_id = "signal"

[[contributions.panel]]
slot = "ui.slot.main"
perspective = "signal"
component = "vendor-plugin-name-panel"  # Custom element tag
priority = 100

[[contributions.command]]
id = "my_command"
label = "Do Something"
action = "my_handler"
danger_level = "safe"              # safe | confirm | danger

[[contributions.drawer]]
id = "my_drawer"
component = "vendor-plugin-name-drawer"
title = "Drawer Title"
width = "400px"
```

### Plugin Python Entrypoint (`__init__.py`)
```python
def register(ctx):
    ctx.register_contribution("panel", {
        "slot": "ui.slot.main",
        "perspective": "signal",
        "component": "my-plugin-panel",
        "priority": 100,
    })
    ctx.register_contribution("command", {
        "id": "my_action",
        "label": "My Action",
        "action": "my_handler",
        "danger_level": "safe",
    })
```
`ctx` provides: `ctx.register_contribution(type, data)`, `ctx.plugin_id`, `ctx.discovery_index`

### Plugin UI (Svelte → Web Component)
```svelte
<svelte:options customElement="vendor-plugin-name-panel" />
<script lang="ts">
  import { onMount } from 'svelte';
  let data = $state([]);
  onMount(async () => {
    const res = await fetch('/api/my-endpoint');
    data = await res.json();
  });
</script>
<div class="panel">Content here</div>
<style>
  .panel { background: var(--continuum-bg-secondary); }
</style>
```

Build: `cd plugins/vendor.plugin_name/ui && npm run build` → outputs `../dist/plugin.js`

### Continuum API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Lifecycle state |
| `/diagnostics` | GET | Plugin status, warnings, errors |
| `/api/registry` | GET | Full resolved registry (perspectives, regions, commands, plugins) |
| `/plugins/{id}/assets/{path}` | GET | Serve plugin UI bundles (path traversal protected) |
| `/api/commands/execute` | POST | Execute command (auth, validation, confirmation, audit) |
| `/api/commands/audit` | GET | Recent command audit log |

### Registry Response Shape
```json
{
  "lifecycle_state": "ready",
  "registry_fingerprint": "a1b2c3d4e5f6g7h8",
  "perspectives": [{"id": "signal", "label": "Signal", ...}],
  "regions": {
    "ui.slot.main": [
      {"type": "panel", "plugin_id": "vendor.plugin", "component": "...", "bundle_url": "/plugins/vendor.plugin/assets/plugin.js", "priority": 200}
    ]
  },
  "commands": [...],
  "plugins": [{"id": "...", "status": "LOADED", "contribution_count": 3, ...}],
  "diagnostics": {"conflicts": [], "missing_required": [], "warnings": []}
}
```

### Command Execution Pipeline
`Request → Lookup → Authorization (capabilities) → Input validation (JSON Schema) → Confirmation check (danger levels) → Dry-run preview → Handler dispatch (timeout-protected) → Audit logging → Response`

### Key Continuum Source Files
```
~/Code/continuum/
├── src/continuum/
│   ├── app/
│   │   ├── runtime.py          # ContinuumRuntime — lifecycle, boot sequence
│   │   ├── registry.py         # build_registry() — slot resolution, cardinality enforcement
│   │   ├── discovery.py        # discover_plugins() — scans plugins/ for plugin.toml
│   │   ├── loader.py           # load_plugins() — imports __init__.py, calls register(ctx)
│   │   └── command_bus.py      # CommandBus — execution, auth, timeout, audit
│   ├── domain/
│   │   ├── perspectives.py     # PerspectiveSpec — 5 built-in perspectives
│   │   ├── regions.py          # RegionSpec — 8 slots with cardinality (ONE/MANY)
│   │   ├── manifest.py         # Pydantic models for plugin.toml parsing + validation
│   │   ├── contributions.py    # DangerLevel enum
│   │   ├── commands.py         # CommandExecuteRequest/Result, AuditEntry
│   │   ├── auth.py             # UserContext, PolicyEngine, PolicyDecision
│   │   └── lifecycle.py        # LifecycleManager, LifecycleState enum
│   └── adapters/web/
│       └── api.py              # FastAPI routes: /health, /api/registry, /plugins/{id}/assets/...
├── web/                        # SvelteKit frontend
│   └── src/lib/
│       ├── components/
│       │   ├── Shell.svelte    # Main layout (header, nav, main, rail, footer, overlays)
│       │   ├── RegionSlot.svelte   # Renders contributions for a slot
│       │   ├── ComponentLoader.svelte  # Dynamic Web Component loader (loading/error states)
│       │   ├── NavItem.svelte
│       │   ├── CommandPalette.svelte
│       │   └── Drawer.svelte
│       ├── stores/
│       │   └── registry.ts    # Svelte stores: registry, perspectives, mainPanels, commands
│       └── services/
│           └── pluginLoader.ts # loadBundle(), waitForElement() — <script> injection
├── plugins/                    # Sample plugins
│   ├── continuum.sample_chat/
│   ├── continuum.sample_signal/
│   └── continuum.sample_systems/
└── scripts/
    └── build-plugins.sh        # Build all plugin UI bundles
```

### CSS Theme Variables (for plugin UIs)
`--continuum-bg-primary`, `--continuum-bg-secondary`, `--continuum-bg-tertiary`, `--continuum-bg-hover`,
`--continuum-text-primary`, `--continuum-text-secondary`, `--continuum-text-muted`,
`--continuum-accent-primary`, `--continuum-accent-success`, `--continuum-accent-warning`, `--continuum-accent-danger`,
`--continuum-border`, `--continuum-radius-sm/md/lg`, `--continuum-space-xs/sm/md/lg`,
`--continuum-font-sans`, `--continuum-font-mono`, `--continuum-font-size-xs/sm/md/lg`

## External Observability APIs (for dashboard data)
- **Prefect** (self-hosted at `:4200/api`): `POST /flow_runs/filter`, `POST /flow_runs/history`, `POST /task_runs/count`
- **Langfuse** (self-hosted at `:3000/api/public`): `GET /traces`, `GET /observations?type=GENERATION`, `GET /metrics/daily`
- **Adapter wiring**: `PrefectReporter` created at startup (`main.py:249-252`), Langfuse adapter via `create_llm_observability_provider()`

## Package & Build Config
- `pyproject.toml` — setuptools, editable install, Python 3.11+
- No frontend build tooling (no Vite, webpack, SvelteKit, npm, pnpm)
- Docker: `docker-compose.yml` for infrastructure services

---

# Copyable Outputs

## Directory Tree (Source — depth 3)

```
src/squadops/
├── __init__.py
├── agents/
│   ├── base.py
│   ├── entrypoint.py
│   ├── exceptions.py
│   ├── factory.py
│   ├── models.py
│   ├── roles/          (lead.py, dev.py, qa.py, strat.py, data.py)
│   └── skills/         (lead/, dev/, qa/, strat/, data/, shared/)
├── api/
│   ├── __init__.py
│   ├── health_app.py         # Port 8000 — slated for demolition
│   ├── health_deps.py
│   ├── mapping.py
│   ├── schemas.py
│   ├── service.py
│   ├── middleware/
│   │   └── auth.py           # AuthMiddleware, RequestIDMiddleware, require_auth/roles/scopes
│   ├── routes/
│   │   ├── auth.py           # /auth/userinfo
│   │   ├── agents.py         # /api/v1/agents (health_app routes)
│   │   ├── console.py        # /console/* (health_app routes)
│   │   ├── health.py         # /health/* (health_app routes)
│   │   ├── warmboot.py       # /warmboot/* (health_app routes)
│   │   └── cycles/
│   │       ├── __init__.py   # Re-exports all routers
│   │       ├── artifacts.py  # /api/v1/.../artifacts
│   │       ├── cycles.py     # /api/v1/projects/{id}/cycles
│   │       ├── dtos.py       # All Pydantic DTOs
│   │       ├── errors.py     # Error mapping
│   │       ├── mapping.py    # Domain → DTO conversion
│   │       ├── profiles.py   # /api/v1/squad-profiles
│   │       ├── projects.py   # /api/v1/projects
│   │       └── runs.py       # /api/v1/.../runs
│   ├── runtime/
│   │   ├── main.py           # Port 8001 — THE runtime API
│   │   └── deps.py           # DI wiring (singleton setters/getters)
│   └── templates/
│       └── health_dashboard.html
├── auth/
│   ├── client_credentials.py
│   └── models.py             # Identity, TokenClaims, AuthContext, AuditEvent
├── bootstrap/
│   ├── handlers.py
│   ├── skills.py
│   └── system.py
├── capabilities/
│   ├── acceptance.py
│   ├── exceptions.py
│   ├── models.py             # CapabilityContract, WorkloadRunReport, TaskRecord
│   ├── runner.py             # WorkloadRunner (DAG execution)
│   ├── handlers/             (governance.py, development.py, qa.py, data.py, warmboot.py)
│   └── manifests/            (contracts/, schemas/, workloads/)
├── cli/
│   ├── auth.py, client.py, config.py, exit_codes.py, main.py, output.py
│   └── commands/             (artifacts.py, cycles.py, projects.py, runs.py, profiles.py, etc.)
├── config/
│   ├── loader.py, schema.py, redaction.py, path_resolver.py, fingerprint.py, errors.py
├── cycles/
│   ├── models.py             # Cycle, Run, Gate, GateDecision, ArtifactRef, SquadProfile
│   ├── lifecycle.py          # Status derivation, config hashing
│   └── task_plan.py
├── orchestration/
│   ├── orchestrator.py       # AgentOrchestrator (in-memory state)
│   ├── handler_registry.py
│   └── handler_executor.py
├── ports/
│   ├── audit.py, db.py, secrets.py
│   ├── auth/                 (authentication.py, authorization.py)
│   ├── capabilities/         (repository.py, executor.py)
│   ├── comms/                (queue.py)
│   ├── cycles/               (cycle_registry.py, artifact_vault.py, flow_execution.py,
│   │                          project_registry.py, squad_profile.py)
│   ├── embeddings/           (provider.py)
│   ├── llm/                  (provider.py)
│   ├── memory/               (store.py)
│   ├── observability/        (healthcheck_reporter.py)
│   ├── prompts/              (service.py)
│   ├── tasks/                (registry.py)
│   ├── telemetry/            (events.py, metrics.py)
│   └── tools/                (filesystem.py, vcs.py, container.py)
└── tasks/
    ├── models.py             # TaskEnvelope, TaskResult (frozen dataclasses)
    ├── legacy_models.py      # Task, FlowRun (Pydantic, DB-mapped)
    ├── types.py              # Compatibility bridge
    └── exceptions.py
```

## Adapters Tree

```
adapters/
├── audit/          (factory.py, logging_adapter.py)
├── auth/           (factory.py, keycloak/auth_adapter.py, keycloak/authz_adapter.py)
├── capabilities/   (factory.py, filesystem.py, aci_executor.py)
├── comms/          (factory.py, rabbitmq.py)
├── cycles/         (factory.py, memory_cycle_registry.py, filesystem_artifact_vault.py,
│                    distributed_flow_executor.py, in_process_flow_executor.py,
│                    config_project_registry.py, config_squad_profile.py, prefect_reporter.py)
├── embeddings/     (factory.py, ollama.py)
├── llm/            (factory.py, ollama.py)
├── memory/         (factory.py, lancedb.py)
├── noop/           (ports.py)
├── observability/  (healthcheck_http.py)
├── persistence/    (factory.py, postgres/runtime.py)
├── prompts/        (factory.py, filesystem.py)
├── secrets/        (factory.py, env.py, file.py, docker.py)
├── tasks/          (factory.py, sql.py, prefect.py)
├── telemetry/      (factory.py, console.py, null.py, otel.py, langfuse/adapter.py, langfuse/redaction.py)
└── tools/          (factory.py, docker.py, git.py, local_filesystem.py)
```

## DI Wiring — deps.py (full file)

```python
# src/squadops/api/runtime/deps.py

# Global adapter instances (initialized at startup)
_adapter: TaskRegistryPort | None = None
_auth_port: AuthPort | None = None
_authz_port: AuthorizationPort | None = None
_audit_port = None

# SIP-0064 cycle port singletons
_project_registry: ProjectRegistryPort | None = None
_cycle_registry: CycleRegistryPort | None = None
_squad_profile: SquadProfilePort | None = None
_artifact_vault: ArtifactVaultPort | None = None
_flow_executor: FlowExecutionPort | None = None

# Setters: set_tasks_adapter(), set_auth_ports(), set_audit_port(), set_cycle_ports()
# Getters: get_project_registry(), get_cycle_registry(), get_squad_profile_port(),
#          get_artifact_vault(), get_flow_executor()
# All getters raise RuntimeError if port is None (T14 invariant)
```

## Runtime API Startup (adapter creation excerpt)

```python
# src/squadops/api/runtime/main.py — startup_event() (lines 136-274)

# PostgreSQL pool
pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)

# RabbitMQ
rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
rabbitmq_channel = await rabbitmq_connection.channel()

# Auth (Keycloak OIDC)
auth_port = create_auth_provider("keycloak", issuer_url=..., audience=..., ...)
authz_port = create_authorization_provider("keycloak", roles_mode=..., ...)
set_auth_ports(auth=auth_port, authz=authz_port)

# Tasks
adapter = create_task_registry_provider("sql", connection_string=POSTGRES_URL)
set_tasks_adapter(adapter)

# Cycle ports (SIP-0064)
project_registry = create_project_registry("config")
cycle_registry = create_cycle_registry("memory")     # <-- in-memory!
squad_profile = create_squad_profile_port("config")
artifact_vault = create_artifact_vault("filesystem")
flow_executor = create_flow_executor("distributed", cycle_registry=..., queue=..., ...)
set_cycle_ports(project_registry=..., cycle_registry=..., ...)
```

## CycleRegistryPort (full interface)

```python
# src/squadops/ports/cycles/cycle_registry.py

class CycleRegistryPort(ABC):
    # Cycle CRUD
    async def create_cycle(self, cycle: Cycle) -> Cycle
    async def get_cycle(self, cycle_id: str) -> Cycle
    async def list_cycles(self, project_id: str, *, status: CycleStatus | None = None) -> list[Cycle]
    async def cancel_cycle(self, cycle_id: str) -> None

    # Run CRUD
    async def create_run(self, run: Run) -> Run
    async def get_run(self, run_id: str) -> Run
    async def list_runs(self, cycle_id: str) -> list[Run]
    async def update_run_status(self, run_id: str, status: RunStatus) -> Run
    async def cancel_run(self, run_id: str) -> None
    async def append_artifact_refs(self, run_id: str, artifact_ids: tuple[str, ...]) -> Run

    # Gate decisions (T11)
    async def record_gate_decision(self, run_id: str, decision: GateDecision) -> Run
```

## ArtifactVaultPort (full interface)

```python
# src/squadops/ports/cycles/artifact_vault.py

class ArtifactVaultPort(ABC):
    async def store(self, artifact: ArtifactRef, content: bytes) -> ArtifactRef
    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]
    async def get_metadata(self, artifact_id: str) -> ArtifactRef
    async def list_artifacts(self, *, project_id=None, cycle_id=None, run_id=None, artifact_type=None) -> list[ArtifactRef]
    async def set_baseline(self, project_id: str, artifact_type: str, artifact_id: str) -> None
    async def get_baseline(self, project_id: str, artifact_type: str) -> ArtifactRef | None
    async def list_baselines(self, project_id: str) -> dict[str, ArtifactRef]
```

## Cycle Domain Models (key shapes)

```python
# src/squadops/cycles/models.py

@dataclass(frozen=True)
class Cycle:
    cycle_id: str
    project_id: str
    created_at: datetime
    created_by: str
    prd_ref: str | None
    squad_profile_id: str
    squad_profile_snapshot_ref: str
    task_flow_policy: TaskFlowPolicy
    build_strategy: str
    applied_defaults: dict
    execution_overrides: dict
    expected_artifact_types: tuple[str, ...]
    experiment_context: dict
    notes: str | None

@dataclass(frozen=True)
class Run:
    run_id: str
    cycle_id: str
    run_number: int
    status: str            # RunStatus enum value
    initiated_by: str
    resolved_config_hash: str
    started_at: datetime | None
    finished_at: datetime | None
    gate_decisions: tuple[GateDecision, ...]
    artifact_refs: tuple[str, ...]

@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    project_id: str
    artifact_type: str
    filename: str
    content_hash: str
    size_bytes: int
    media_type: str
    created_at: datetime
    cycle_id: str | None
    run_id: str | None
    metadata: dict
    vault_uri: str | None
```

## Auth Middleware Flow

```python
# src/squadops/api/middleware/auth.py

# Request lifecycle:
# 1. RequestIDMiddleware: adds X-Request-ID
# 2. AuthMiddleware:
#    - Allowlists: /health, /health/infra (always), /docs (if expose_docs=True)
#    - OPTIONS: always passes through (CORS preflight)
#    - Extracts "Bearer <token>" from Authorization header
#    - Validates via AuthPort.validate_token() → AuthPort.resolve_identity()
#    - Injects Identity into request.state.identity
#    - Emits AuditEvent on success/failure

# Browser client needs: Authorization: Bearer <JWT from Keycloak>
# CORS origins: derived from config.auth.console.redirect_uri at startup
```

## API Route Summary (all endpoints)

```
Runtime API (port 8001):

Auth:
  GET  /auth/userinfo

Projects:
  GET  /api/v1/projects
  POST /api/v1/projects
  GET  /api/v1/projects/{project_id}

Cycles:
  POST /api/v1/projects/{project_id}/cycles
  GET  /api/v1/projects/{project_id}/cycles
  GET  /api/v1/projects/{project_id}/cycles/{cycle_id}
  POST /api/v1/projects/{project_id}/cycles/{cycle_id}/cancel

Runs:
  POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs
  GET  /api/v1/projects/{project_id}/cycles/{cycle_id}/runs
  GET  /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}
  POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/cancel
  POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}

Artifacts:
  POST /api/v1/projects/{project_id}/artifacts/ingest
  GET  /api/v1/artifacts/{artifact_id}
  GET  /api/v1/artifacts/{artifact_id}/download
  GET  /api/v1/projects/{project_id}/artifacts
  GET  /api/v1/projects/{project_id}/cycles/{cycle_id}/artifacts
  POST /api/v1/projects/{project_id}/baseline/{artifact_type}
  GET  /api/v1/projects/{project_id}/baseline/{artifact_type}
  GET  /api/v1/projects/{project_id}/baseline

Profiles:
  GET  /api/v1/squad-profiles
  GET  /api/v1/squad-profiles/{profile_id}
  GET  /api/v1/squad-profiles/active
  POST /api/v1/squad-profiles/active

Legacy tasks (inline in main.py — 27 handlers):
  GET  /api/v1/tasks/ec/{cycle_id}
  GET  /api/v1/tasks/agent/{agent_name}
  GET  /api/v1/tasks/status/{status}
  GET  /api/v1/tasks/summary/{cycle_id}
  POST /api/v1/tasks/start
  PUT  /api/v1/tasks/{task_id}
  POST /api/v1/tasks/{task_id}/complete
  POST /api/v1/tasks/{task_id}/fail
  POST /api/v1/tasks/{task_id}/results
  ... (and more)
```

## Config Profiles

```
config/
├── profiles/
│   ├── local.yaml
│   ├── staging.yaml
│   └── prod.yaml
├── projects.yaml          # Project definitions (used by config_project_registry)
└── squad-profiles.yaml    # Squad profile definitions (used by config_squad_profile)
```

---

# Answers to Questions

## 1) Where should a `/continuum-plugins` folder live in SquadOps for packaging/build?

**Under the console directory: `/console/continuum-plugins/`** — alongside `console/Dockerfile`, `console/Caddyfile`, and `console/app/`. Each plugin follows the Continuum plugin structure:

```
console/continuum-plugins/
  squadops.cycles_dashboard/
    plugin.toml          # Manifest (id = "squadops.cycles_dashboard")
    __init__.py          # register(ctx) — panel + nav contributions
    ui/
      src/
        CyclesList.svelte
        RunTimeline.svelte
        index.js
      vite.config.js
      package.json
    dist/
      plugin.js          # Built Web Component bundle
  squadops.observability/
    plugin.toml
    __init__.py
    ui/src/...
    dist/plugin.js
```

These plugins would be loaded by the Continuum shell either by:
- (a) Symlinking into the Continuum `plugins/` directory
- (b) Configuring Continuum's `plugins_dir` to point at `/console/continuum-plugins/`
- (c) Deploying a merged `plugins/` directory at runtime

## 2) Is Continuum shell built in SvelteKit or React right now, and where does it live?

**SvelteKit + Vite.** Continuum is a fully built plugin-driven control-plane UI shell living at `https://github.com/backspring-labs/continuum` (local: `~/Code/continuum`).

- **Frontend**: SvelteKit app at `~/Code/continuum/web/` — `Shell.svelte` renders header/nav/main/rail/footer, `RegionSlot.svelte` renders contributions per slot, `ComponentLoader.svelte` dynamically loads Web Components from plugin bundles
- **Backend**: Python FastAPI at `~/Code/continuum/src/continuum/` — `ContinuumRuntime` handles lifecycle, plugin discovery (`./plugins/`), registry resolution (slot cardinality + priority ordering), command execution with audit trail
- **Plugin system**: Fully operational — manifests (`plugin.toml`), Python entrypoints (`register(ctx)`), Svelte→Web Component builds, dynamic `<script>` injection
- **3 sample plugins**: `continuum.sample_chat`, `continuum.sample_signal`, `continuum.sample_systems`
- **5 perspectives**: Signal, Research, Time, Discovery, Systems
- **8 UI slots**: left_nav, header, main, right_rail, footer, modal, drawer, toast_stack
- **Command bus**: Execute pipeline with authorization, JSON Schema validation, danger levels, dry-run, timeouts, audit log
- **Keyboard shortcut**: `Cmd+K` opens command palette

Note: Within the *SquadOps* repo itself, there is no Continuum shell code — the shell lives in the external repo. SquadOps plugins would live at `/console/continuum-plugins/` within the SquadOps repo and be loaded by the Continuum shell.

## 3) How does the shell fetch data (direct REST to SquadOps API? proxy? same origin?)

The Continuum shell fetches data via **`fetch()` calls from plugin Web Components**. Each plugin UI component makes direct REST calls. Current pattern from `ComponentLoader.svelte` and sample plugins:

```javascript
// Plugin components fetch from any reachable API
const res = await fetch('/api/my-endpoint');
const data = await res.json();
```

**For SquadOps plugins**, the data sources would be:
- **SquadOps Runtime API** at port 8001 (`/api/v1/...` endpoints) — cycles, runs, artifacts, tasks, agents
- **Prefect API** at port 4200 (`/api/flow_runs/...`) — flow run metrics, task run history
- **Langfuse API** at port 3000 (`/api/public/...`) — LLM traces, generation timing, cost metrics

**Cross-origin considerations**: Continuum shell runs on port 4040 (FastAPI) / port 5173 (Vite dev). SquadOps API runs on port 8001. Either:
- (a) Use absolute URLs (`http://localhost:8001/api/v1/...`) — requires SquadOps CORS to allow the Continuum origin
- (b) Add a proxy route in Continuum backend that forwards to SquadOps API (BFF pattern)
- (c) Deploy both behind the same reverse proxy / origin

CORS is already configured on the SquadOps Runtime API, derived from `config.auth.console.redirect_uri` — this would need updating to include the Continuum shell origin.

## 4) What auth headers/cookies does the API expect from a browser client?

- **Header**: `Authorization: Bearer <JWT>` — JWT obtained from Keycloak OIDC flow
- **No cookies** — the API is stateless, no session cookies
- **CORS**: already supports `allow_credentials=True` for cross-origin requests
- **Keycloak config**: `config.auth.console` section has `redirect_uri`, `post_logout_redirect_uri`, `client_id` fields for browser-based OIDC
- **Auth bypass**: `GET /health` and `GET /health/infra` are always allowlisted (no token needed)
- **Existing OIDC PoC**: SIP-0062 Phase 3a delivered console OIDC configuration and `/auth/userinfo` endpoint, but no JS client was built

## 5) What minimal plugin contract is already available (manifest fields, mount points)?

**Fully operational.** Continuum has a complete plugin system:

**Manifest** (`plugin.toml`, parsed by Pydantic models in `domain/manifest.py`):
- `[plugin]` — `id` (vendor.name), `name`, `version` (semver), `description`, `required` (bool)
- `[plugin.ui]` — `tag_prefix` (regex: `^[a-z][a-z0-9-]*$`), `bundle` (filename in dist/)
- `[[contributions.nav]]` — `slot`, `label`, `icon`, `priority`, `target` (`{type, panel_id|drawer_id|command_id|route}`)
- `[[contributions.panel]]` — `slot`, `perspective`, `component` (custom element tag), `priority`
- `[[contributions.command]]` — `id`, `label`, `icon`, `shortcut`, `action`, `danger_level`
- `[[contributions.drawer]]` — `id`, `component`, `title`, `width`
- `[[contributions.diagnostic]]` — `id`, `label`, `check`

**Mount points** (8 slots defined in `domain/regions.py`):
- `ui.slot.left_nav` (MANY), `ui.slot.header` (ONE), `ui.slot.main` (MANY), `ui.slot.right_rail` (MANY), `ui.slot.footer` (ONE), `ui.slot.modal` (MANY), `ui.slot.drawer` (MANY), `ui.slot.toast_stack` (MANY)

**Perspectives** (5 built-in, scoping for contributions):
- `signal`, `research`, `time`, `discovery`, `systems`

**Registration**: Plugin `__init__.py` exports `register(ctx)` which calls `ctx.register_contribution(type, data)`.

**Resolution**: Registry builder sorts by priority (desc) then discovery_index (asc). ONE-cardinality slots take the highest-priority contribution and log conflicts. MANY-cardinality slots include all contributions ordered.

**Plugin UI loading**: Shell dynamically injects `<script type="module" src="/plugins/{id}/assets/plugin.js">`, waits for `customElements.whenDefined(tag)`, then renders the custom element in the appropriate slot.

## 6) How are assets bundled (Vite, SvelteKit adapter, webpack, etc.)?

**Vite + SvelteKit (in the Continuum repo).** Two separate build contexts:

**Shell build** (`~/Code/continuum/web/`):
- SvelteKit app built with Vite (`svelte.config.js` + `vite.config.ts`)
- Dev: `npm run dev` (Vite HMR at port 5173)
- Prod: `npm run build` (static output)

**Plugin UI builds** (`~/Code/continuum/plugins/{id}/ui/`):
- Each plugin has its own `vite.config.js` and `package.json`
- Svelte components compiled with `customElement: true` to Web Components
- Build: `vite build` → outputs `dist/plugin.js` (ES module)
- Entry: `ui/src/index.js` imports all Svelte components (triggers `customElements.define()`)
- Global script: `./scripts/build-plugins.sh` builds all plugins

**In the SquadOps repo**: No frontend bundling exists. SquadOps plugins for Continuum would live at `/console/continuum-plugins/` with their own `vite.config.js` per plugin, following the same pattern as Continuum sample plugins. These bundles would be copied or symlinked into the Continuum `plugins/` directory for loading.

**Key Vite config pattern for plugin UI**:
```javascript
export default defineConfig({
  plugins: [svelte({ compilerOptions: { customElement: true } })],
  build: {
    lib: { entry: 'src/index.js', formats: ['es'], fileName: 'plugin' },
    outDir: '../dist', emptyOutDir: true,
  },
});
```
