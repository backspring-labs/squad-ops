---
title: SquadOps Console — Control Plane UI via Continuum Plugins
status: accepted
author: J. Ladd
created_at: '2026-02-06T00:00:00Z'
sip_number: 69
updated_at: '2026-02-14T22:19:10.364255Z'
---
# SIP — SquadOps Console: Control Plane UI via Continuum Plugins

> **Status**: Proposed
> **Target release**: v0.9.8
> **Scope**: New subsystem (UI layer)
> **Impact**: Adds operator-facing console; replaces health-check app
> **Depends on**: SIP-0062 (Auth Boundary), SIP-0064 (Cycle API), SIP-0065 (CLI), SIP-0066 (Execution Pipeline), SIP-0067 (Postgres Registry)
> **External dependencies**: [Continuum](https://github.com/backspring-labs/continuum) shell framework, [Switchboard](https://github.com/backspring-labs/switchboard) plugin runtime

---

## 1. Overview

This SIP introduces the **SquadOps Console** — an operator-facing control plane UI deployed as a Docker container alongside existing SquadOps infrastructure. The console is built on the Continuum plugin-driven shell framework, with all SquadOps operational surfaces implemented as Continuum plugins maintained in the SquadOps repository.

The console provides:

- A single-pane operational dashboard for cycle execution, agent monitoring, and observability
- Full CLI parity — every `squadops` CLI command has a UI equivalent
- Keycloak SSO login using the same identity model as the Runtime API (SIP-0062)
- Pluggable, isolated surfaces — plugin failures degrade gracefully without crashing the console
- Auditable operations via Continuum's command bus with danger levels and audit trail

Seven plugins compose the console: **Home**, **Cycles**, **Artifacts**, **Agents**, **Observability**, **Projects**, and **System**. Together they replace the health-check app (port 8000) and provide the operational UI that SquadOps currently lacks.

---

## 2. Decisions & Scope

### D1: Deployment Model — Branded Container

The Continuum shell is packaged into a Docker image branded as "SquadOps Console." The shell framework lives in its own repository (`backspring-labs/continuum`); the SquadOps-specific plugins live in this repository at `continuum-plugins/`. The Docker build combines both into a single deployable container.

**Rationale**: Keeps the shell framework reusable across projects while SquadOps-specific surfaces remain co-located with the domain code they visualize.

### D2: Plugin Location — `continuum-plugins/` at Repo Root

Plugins live at `continuum-plugins/` alongside `src/`, `adapters/`, `config/`. Each plugin is a directory following Continuum's plugin contract: `plugin.toml` manifest, `__init__.py` entrypoint, `ui/` source, `dist/` built bundle.

**Rationale**: Plugins are frontend + registration artifacts, not Python library packages. Keeping them at the repo root (not under `src/`) mirrors the existing `adapters/` and `config/` convention for non-core code.

### D3: Auth — OIDC Authorization Code Flow with PKCE

The console authenticates via Keycloak using the OAuth2 Authorization Code flow with PKCE (Proof Key for Code Exchange). The Keycloak client `squadops-console` is a public client (no client_secret). Token management uses the BFF (Backend-for-Frontend) pattern described in §7.2.

**Rationale**: PKCE is the standard for browser-based public clients. This assumes SIP-0062 Phase 3a is implemented (`auth.console` config + CORS dev support). If not present at v0.9.8, implement as a prerequisite task in Phase 1.

### D4: Cross-Origin Strategy

- **Production**: Reverse proxy (Caddy/nginx) serves console and API from the same origin. Plugin `fetch()` calls use relative URLs (e.g., `/api/v1/...`) routed by the proxy.
- **Local development**: CORS configured on the Runtime API via `auth.console.redirect_uri`. Assumes SIP-0062 Phase 3a CORS support is present; if not, implement as a Phase 1 prerequisite.

**Rationale**: Same-origin in production eliminates CORS complexity and credential handling issues.

### Prerequisites

The following must be present before Phase 1 begins:

| Prerequisite | Source | Required Config/Endpoints |
|-------------|--------|--------------------------|
| `auth.console` config section | SIP-0062 Phase 3a | `client_id`, `redirect_uri`, `post_logout_redirect_uri` |
| CORS middleware on Runtime API | SIP-0062 Phase 3a | Origins derived from `auth.console.redirect_uri` |
| `GET /auth/userinfo` endpoint | SIP-0062 Phase 3a | Returns current `Identity` |
| Keycloak realm with `squadops-console` client | SIP-0063 | Public client, PKCE S256, redirect URIs |
| Runtime API cycle endpoints | SIP-0064 | `/api/v1/projects`, `/cycles`, `/runs`, `/artifacts` |

If any prerequisite is missing, it must be implemented as the first task in Phase 1 before console work begins.

### D5: Plugin UI Technology — Svelte Web Components

Plugin UIs are Svelte components compiled to Web Components (Custom Elements) via Vite. This is Continuum's standard plugin UI pattern — zero compile-time coupling between shell and plugins.

**Rationale**: Continuum's existing build tooling, `ComponentLoader`, and `pluginLoader.ts` already handle dynamic Web Component loading with error states and timeout handling.

### D6: Console Replaces Health-Check App

The `squadops.system` plugin subsumes all health-check app functionality. The health-check app (`src/squadops/api/health_app.py`, port 8000) is deprecated and will be removed after the console reaches production readiness.

**Rationale**: The health-check app is a 2,953-line monolith slated for demolition. The system plugin provides a cleaner, plugin-isolated replacement.

### D7: Full CLI Parity

Every CLI command documented in SIP-0065 has a UI equivalent — either as a Continuum command (for write operations) or a panel view (for read operations). The CLI parity matrix in Section 9 is normative.

**Rationale**: Operators should never need to fall back to the CLI for operations the console supports.

### D8: Observability — Direct REST to Prefect and Langfuse

Plugin components call Prefect (`POST /api/flow_runs/filter`) and Langfuse (`GET /api/public/traces`) REST APIs directly. No backend-for-frontend proxy in V1.

**Constraint**: v0.9.8 assumes Prefect and Langfuse endpoints are reachable from the browser on the same network and require no additional interactive auth. If either service requires auth (API keys, tokens), Phase 3 adds a minimal proxy in the console backend that attaches service credentials server-side. Plugin `fetch()` calls would then use relative URLs (e.g., `/proxy/prefect/...`) routed by the console backend.

**Degradation**: If Prefect or Langfuse returns 401/403 or is unreachable, observability panels display "Service unavailable — check configuration" with the HTTP status code. Other plugins are unaffected.

**Rationale**: Both APIs are self-hosted and on the same network. A proxy adds latency and complexity without security benefit when no auth is needed. The proxy escape hatch is specified here so it can be added without SIP revision.

### D9: Phased Delivery

Four phases leading to the v0.9.8 release. Each phase is a development milestone; the version bumps to 0.9.8 only after all phases are complete.

**Rationale**: Incremental delivery allows validation of the shell deployment and auth flow before building all 7 plugins.

---

## 3. Motivation

SquadOps v0.9.x delivered a complete execution pipeline: cycle API (SIP-0064), CLI (SIP-0065), auth boundary (SIP-0062), Prefect orchestration (SIP-0066), and Postgres persistence (SIP-0067). All operator interaction flows through the CLI or raw API calls. This creates several gaps:

1. **No at-a-glance operational view.** Operators must run multiple CLI commands to understand system state. There is no summary dashboard showing active cycles, recent run outcomes, agent status, or alert conditions.

2. **Gate decisions require CLI + knowledge of IDs.** Approving or rejecting a gate requires `squadops runs gate <project_id> <cycle_id> <run_id> <gate_name> --approve`. A UI with contextual approve/reject buttons reduces friction and error.

3. **Observability is fragmented.** Prefect and Langfuse have their own UIs, but operators must context-switch between three separate tools. An integrated observability surface within the console provides unified monitoring.

4. **Health monitoring is a monolith.** The health-check app (`health_app.py`, 2,953 lines) needs replacement. The console's system plugin provides a cleaner, maintainable alternative.

5. **No visual artifact browsing.** Artifacts (PRDs, code, test reports, build plans) are accessible only via CLI. A browsable artifact viewer with baseline management improves discoverability.

---

## 4. Design Goals

1. **Full CLI parity** — every `squadops` CLI command (SIP-0065) has a UI equivalent
2. **Single-pane operation** — home dashboard summarizes all system state at a glance
3. **Keycloak SSO** — same identity model, roles, and scopes as the Runtime API
4. **Plugin isolation** — plugin failures produce DEGRADED state, never crash the console
5. **Zero shell modification** — all SquadOps surfaces are plugins, not Continuum core changes. Continuum's command bus already provides audit logging via `AuditEntry` (see `command_bus.py`); if audit trail requires extension beyond existing command bus hooks, audit logging will be implemented within SquadOps plugins (plugin-local audit) in v0.9.8 and upstreamed to Continuum later
6. **Deterministic composition** — Continuum's slot/priority resolution governs layout
7. **Auditable operations** — write commands flow through Continuum's existing command bus execution pipeline (lookup → authorization → validation → confirmation → dispatch → audit). No Continuum core changes are required for audit; the pipeline already emits structured `continuum.command.executed` events
8. **Theme consistency** — all plugins use Continuum CSS custom properties
9. **Graceful degradation** — console works even if Prefect or Langfuse are unavailable
10. **Docker-native deployment** — single container, one `docker-compose` service entry

---

## 5. Architecture

### 5.1 System Context

```
┌─────────────────────────────────────────────────────────────┐
│                     Operator Browser                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   SquadOps Console      │
              │   (Continuum Shell)     │
              │   Port 4040             │
              │                         │
              │  ┌───────────────────┐  │
              │  │  7 SquadOps       │  │
              │  │  Plugins          │  │
              │  └───────────────────┘  │
              └────┬─────┬─────┬───────┘
                   │     │     │
         ┌─────────┘     │     └──────────┐
         ▼               ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Runtime API  │ │   Prefect    │ │   Langfuse   │
│ Port 8001    │ │  Port 4200   │ │  Port 3000   │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌──────────────┐
│  Keycloak    │
│  Port 8180   │
└──────────────┘
```

### 5.2 Build and Packaging

```
squad-ops repo                          continuum repo
─────────────                           ──────────────
continuum-plugins/                      src/continuum/    (Python backend)
  squadops.home/                        web/              (SvelteKit shell)
  squadops.cycles/
  squadops.artifacts/                         │
  squadops.agents/                            │
  squadops.observability/                     ▼
  squadops.projects/              ┌──────────────────────┐
  squadops.system/                │  Docker Build        │
         │                        │                      │
         └───────────────────────►│  1. Build shell      │
                                  │  2. Build plugins    │
                                  │  3. Package image    │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  squadops-console:latest
```

### 5.3 Plugin Loading and Lifecycle

At container startup, the Continuum runtime:

1. Scans `plugins/` directory (containing all 7 SquadOps plugins)
2. Parses each `plugin.toml` manifest and validates against schema
3. Imports each `__init__.py` and calls `register(ctx)`
4. Resolves contributions into slots (priority ordering, cardinality enforcement)
5. Serves plugin UI bundles via `/plugins/{id}/assets/plugin.js`
6. Shell fetches `/api/registry` and renders contributions in regions

**Plugin lifecycle states** (managed by Continuum runtime):

```
DISCOVERED → LOADING → LOADED (success) → contributes to registry
                     → FAILED (error)   → excluded from registry
```

- **DISCOVERED**: Manifest found and validated; `__init__.py` not yet imported.
- **LOADING**: `register(ctx)` is being called.
- **LOADED**: Contributions registered successfully. Plugin appears in `/api/registry` and `/diagnostics`.
- **FAILED**: `register(ctx)` threw or manifest invalid. Plugin excluded from registry. Error captured in diagnostics.

**Runtime-level degradation**:
- If any plugin with `required = true` is FAILED → runtime enters **DEGRADED** state.
- If all plugins are LOADED → runtime enters **READY** state.
- DEGRADED state is surfaced in the `squadops.system` plugin diagnostics panel (source: `GET /diagnostics`).
- Plugin failures never crash the console; the shell continues with remaining plugins.

### 5.4 Build Output Convention

Each plugin build MUST emit `dist/plugin.js` (ES module entry) plus any chunk assets under `dist/assets/`. The Continuum server serves files from `plugins/{id}/dist/` via `/plugins/{id}/assets/{path}`. This naming is deterministic — the manifest `bundle` field references `plugin.js` and the server resolves it from the `dist/` directory by convention.

### 5.4 Docker Compose Integration

```yaml
squadops-console:
  build:
    context: .
    dockerfile: docker/console/Dockerfile
  ports:
    - "4040:4040"
  environment:
    - SQUADOPS_API_URL=http://runtime-api:8001
    - PREFECT_API_URL=http://prefect-server:4200
    - LANGFUSE_API_URL=http://langfuse:3000
    - KEYCLOAK_URL=http://keycloak:8080/realms/squadops
    - KEYCLOAK_PUBLIC_URL=http://localhost:8180/realms/squadops
    - CONSOLE_CLIENT_ID=squadops-console
  depends_on:
    - runtime-api
    - keycloak
```

### 5.5 Service Map (after deployment)

| Service | Port | Purpose |
|---------|------|---------|
| **squadops-console** | **4040** | **Control Plane UI (new)** |
| runtime-api | 8001 | SquadOps API |
| keycloak | 8180 | Identity provider |
| prefect-server | 4200 | Workflow orchestration |
| langfuse | 3000 | LLM observability |
| postgres | 5432 | Database |
| rabbitmq | 5672 | Message queue |
| redis | 6379 | Cache |

---

## 6. Plugin Catalog

### 6.1 `squadops.home` — Home Summary Dashboard

**Purpose**: At-a-glance operational summary. The first thing an operator sees after login.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| nav | `ui.slot.left_nav` | — | — | 999 |
| panel | `ui.slot.main` | signal | `squadops-home-summary` | 999 |

**Summary Cards**:
- Active cycles count (with status breakdown)
- Recent runs (last 5, with status badges)
- Agent status (5 agents: online/busy/idle)
- Last build outcome (pass/fail with duration)
- Alert badges (failed runs, pending gates)

**Data Sources**:
- `GET /api/v1/projects` → project count
- `GET /api/v1/projects/{id}/cycles?status=active` → active cycles
- `GET /api/v1/projects/{id}/cycles/{id}/runs` → recent runs
- `POST :4200/api/flow_runs/filter` → last flow run duration/status
- `GET :3000/api/public/metrics/daily` → LLM generation count, avg latency

**CLI Parity**: `squadops status`

---

### 6.2 `squadops.cycles` — Cycle Execution Manager

**Purpose**: Full lifecycle management for cycles and runs. The primary operational surface. Project IDs come from the Runtime API project registry (SIP-0064 `ProjectRegistryPort`); the console does not invent or manage project identity.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| nav | `ui.slot.left_nav` | — | — | 800 |
| panel | `ui.slot.main` | signal | `squadops-cycles-list` | 800 |
| panel | `ui.slot.main` | signal | `squadops-cycles-run-timeline` | 700 |
| panel | `ui.slot.main` | signal | `squadops-cycles-run-detail` | 600 |

**Views**:
- **Cycle list**: Filterable table (project, status). Click to expand runs.
- **Run timeline**: Visual timeline of run statuses for a selected cycle.
- **Run detail**: Full run info including gate decisions, artifact refs, config hash, timestamps.
- **Gate decision panel**: Contextual approve/reject buttons with notes field.

**Commands**:

| Command ID | Label | Danger Level | Action |
|------------|-------|-------------|--------|
| `squadops.create_cycle` | Create Cycle | safe | POST `/api/v1/projects/{id}/cycles` |
| `squadops.create_run` | Start Run | safe | POST `/api/v1/.../runs` |
| `squadops.cancel_cycle` | Cancel Cycle | confirm | POST `/api/v1/.../cancel` |
| `squadops.cancel_run` | Cancel Run | confirm | POST `/api/v1/.../runs/{id}/cancel` |
| `squadops.gate_approve` | Approve Gate | safe | POST `/api/v1/.../gates/{name}` body: `{"decision": "approved"}` |
| `squadops.gate_reject` | Reject Gate | confirm | POST `/api/v1/.../gates/{name}` body: `{"decision": "rejected"}` |

**CLI Parity**: `cycles create`, `cycles list`, `cycles show`, `cycles cancel`, `runs list`, `runs show`, `runs retry`, `runs cancel`, `runs gate --approve/--reject`

---

### 6.3 `squadops.artifacts` — Artifact Browser

**Purpose**: Browse, ingest, and manage artifacts and baselines.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| panel | `ui.slot.main` | signal | `squadops-artifacts-list` | 400 |
| panel | `ui.slot.main` | discovery | `squadops-artifacts-browser` | 500 |
| panel | `ui.slot.right_rail` | signal | `squadops-artifacts-detail` | 500 |

No dedicated nav entry — panels appear in Signal and Discovery perspectives.

**Views**:
- **Artifact list**: Filterable by project, cycle, run, type. Shows filename, size, media type, created_at.
- **Artifact browser**: Full-page view in Discovery perspective with baseline management.
- **Artifact detail**: Right rail card showing metadata, content hash, vault URI.

**Commands**:

| Command ID | Label | Danger Level | Action |
|------------|-------|-------------|--------|
| `squadops.ingest_artifact` | Ingest Artifact | safe | POST `/api/v1/.../artifacts/ingest` (multipart) |
| `squadops.set_baseline` | Set Baseline | confirm | POST `/api/v1/.../baseline/{type}` |
| `squadops.download_artifact` | Download | safe | GET `/api/v1/artifacts/{id}/download` |

**CLI Parity**: `artifacts ingest`, `artifacts get`, `artifacts download`, `artifacts list`, `baseline set`, `baseline get`, `baseline list`

---

### 6.4 `squadops.agents` — Agent Monitor

**Purpose**: Monitor agent health and task assignments. View-only in V1.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| panel | `ui.slot.right_rail` | signal | `squadops-agents-status` | 800 |
| panel | `ui.slot.main` | signal | `squadops-agents-tasks` | 300 |

No dedicated nav entry — panels appear in Signal perspective.

**Views**:
- **Agent status cards**: Right rail showing 5 agents (Max, Neo, Nat, Eve, Data) with role, current task, idle/busy state.
- **Task assignment view**: Table of in-flight and recent tasks grouped by agent.

**Data Sources**:
- `GET /api/v1/tasks/agent/{agent_name}` → per-agent task list
- `GET /api/v1/tasks/status/in_progress` → in-flight tasks
- `GET /api/v1/tasks/summary/{cycle_id}` → task summary per cycle

**CLI Parity**: View-only. No CLI write commands exist for agents.

---

### 6.5 `squadops.observability` — Metrics & Traces

**Purpose**: Integrated Prefect flow metrics and Langfuse LLM trace timing. A new capability not available in the CLI.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| panel | `ui.slot.main` | signal | `squadops-obs-flow-metrics` | 200 |
| panel | `ui.slot.main` | signal | `squadops-obs-llm-traces` | 100 |
| panel | `ui.slot.right_rail` | signal | `squadops-obs-cost-summary` | 300 |

No dedicated nav entry — panels appear in Signal perspective below cycles.

**Views**:
- **Flow metrics**: Completed/failed flow runs over time, average duration, task completion rates. Data from Prefect REST API.
- **LLM traces**: Generation count, average latency, token usage, model distribution. Data from Langfuse REST API.
- **Cost summary**: Right rail card with daily token count, estimated cost, top models.

**Data Sources**:
- `POST :4200/api/flow_runs/filter` → flow run list with status/duration
- `POST :4200/api/flow_runs/history` → time-bucketed flow run stats
- `POST :4200/api/task_runs/count` → completed task count
- `GET :3000/api/public/traces` → LLM trace list
- `GET :3000/api/public/observations?type=GENERATION` → generation details
- `GET :3000/api/public/metrics/daily` → daily aggregated metrics

**Degradation**: If Prefect or Langfuse is unavailable, panels show "Service unavailable" with last-known data timestamp. Other plugins are unaffected.

**CLI Parity**: No CLI equivalent — this is a new observability capability.

---

### 6.6 `squadops.projects` — Project & Profile Manager

**Purpose**: Browse projects, manage squad profiles, view configuration.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| nav | `ui.slot.left_nav` | — | — | 600 |
| panel | `ui.slot.main` | discovery | `squadops-projects-list` | 800 |
| panel | `ui.slot.main` | discovery | `squadops-projects-profiles` | 600 |

**Views**:
- **Project list**: Table of pre-registered projects with tags, PRD path, created date.
- **Profile manager**: Squad profile list, active profile indicator, agent configuration detail (per-agent model, role, enabled state).

**Commands**:

| Command ID | Label | Danger Level | Action |
|------------|-------|-------------|--------|
| `squadops.create_project` | Create Project | safe | POST `/api/v1/projects` |
| `squadops.set_active_profile` | Set Active Profile | confirm | POST `/api/v1/squad-profiles/active` |

**CLI Parity**: `projects list`, `projects show`, `squad-profiles list`, `squad-profiles show`, `squad-profiles active`, `squad-profiles set-active`

---

### 6.7 `squadops.system` — System Health & Diagnostics

**Purpose**: Infrastructure health monitoring, Continuum plugin diagnostics. Replaces health-check app.

**Contributions**:

| Type | Slot | Perspective | Component | Priority |
|------|------|-------------|-----------|----------|
| nav | `ui.slot.left_nav` | — | — | 400 |
| panel | `ui.slot.main` | systems | `squadops-system-health` | 800 |
| panel | `ui.slot.main` | systems | `squadops-system-plugins` | 600 |
| panel | `ui.slot.main` | systems | `squadops-system-infra` | 400 |

**Views**:
- **Service health grid**: Status of all services (runtime-api, postgres, rabbitmq, redis, prefect, langfuse, keycloak) with response time.
- **Plugin diagnostics**: Continuum plugin status table (from `/diagnostics`), registry fingerprint, load times, contribution counts.
- **Infrastructure detail**: Connection pool stats, queue depth, cache hit rates.

**Commands**:

| Command ID | Label | Danger Level | Action |
|------------|-------|-------------|--------|
| `squadops.health_check` | Run Health Check | safe | GET `/health` + GET `/health/infra` |

**CLI Parity**: `squadops status`

---

## 7. Auth Integration

### 7.1 Login Flow

The console implements the OAuth2 Authorization Code flow with PKCE:

```
┌──────────┐                  ┌──────────────┐                  ┌──────────┐
│  Browser  │                  │   Console    │                  │ Keycloak │
└─────┬─────┘                  └──────┬───────┘                  └─────┬────┘
      │  1. Navigate to /             │                                │
      │─────────────────────────────►│                                │
      │  2. No token → redirect       │                                │
      │◄─────────────────────────────│                                │
      │  3. Redirect to Keycloak auth endpoint                        │
      │───────────────────────────────────────────────────────────────►│
      │  4. User authenticates (username/password + MFA if configured) │
      │◄──────────────────────────────────────────────────────────────│
      │  5. Redirect back with authorization code                      │
      │─────────────────────────────►│                                │
      │                               │  6. Exchange code for tokens   │
      │                               │───────────────────────────────►│
      │                               │  7. access_token + refresh     │
      │                               │◄──────────────────────────────│
      │  8. Set tokens, load shell    │                                │
      │◄─────────────────────────────│                                │
      │  9. GET /auth/userinfo        │                                │
      │─────────────────────────────►│  (with Bearer token)           │
      │  10. Identity (roles, scopes) │                                │
      │◄─────────────────────────────│                                │
```

### 7.2 Token Management (BFF Pattern)

The console backend mediates all token operations. The browser never sees or handles the refresh token.

- **Access token**: Stored in JavaScript memory (not localStorage). Short-lived (10 minutes default). Passed as `Authorization: Bearer <token>` to Runtime API calls.
- **Refresh token**: Stored **server-side** in the console backend session (never sent to the browser). The console backend sets an opaque httpOnly secure session cookie that maps to the server-side refresh token.
- **Silent refresh**: Browser calls `POST /auth/refresh` on the console backend 30 seconds before access token expiry. The console backend uses the server-side refresh token to call Keycloak's token endpoint (`grant_type=refresh_token`) and returns a new access token to the browser.
- **Logout**: Browser calls `POST /auth/logout` on the console backend. The backend calls Keycloak's end-session endpoint with the refresh token, destroys the server-side session, and clears the session cookie.

```
Browser                     Console Backend              Keycloak
───────                     ───────────────              ────────
 POST /auth/callback ──────► exchange code ────────────► token endpoint
                            ◄── access + refresh ──────◄
                             store refresh server-side
 ◄── access_token + cookie ──
 ...
 POST /auth/refresh ───────► use stored refresh ───────► token endpoint
                            ◄── new access + refresh ──◄
 ◄── new access_token ──────
 ...
 POST /auth/logout ────────► revoke refresh ───────────► end-session
                             destroy session
 ◄── clear cookie ──────────
```

This ensures the refresh token is never exposed to JavaScript (XSS-safe) while the access token remains available in memory for API calls.

### 7.3 Keycloak Client Configuration

The console uses the existing `auth.console` configuration from SIP-0062:

```yaml
auth:
  console:
    client_id: squadops-console          # Public client (no secret)
    redirect_uri: http://localhost:4040/auth/callback
    post_logout_redirect_uri: http://localhost:4040
```

The Keycloak client must be configured as:
- **Client type**: Public (no client authentication)
- **Valid redirect URIs**: `http://localhost:4040/auth/callback`
- **Valid post-logout redirect URIs**: `http://localhost:4040`
- **Web origins**: `http://localhost:4040`
- **PKCE**: S256 (required)

### 7.4 Role-Based UI Behavior

The console reads the user's roles from the Identity returned by `/auth/userinfo` and adjusts the UI accordingly:

| Role | Behavior |
|------|----------|
| `admin` | All panels visible, all commands available |
| `operator` | All panels visible, write commands available |
| `viewer` | All panels visible, write commands hidden (buttons not rendered) |

Role checks are **UI hints only** — enforcement is server-side via `require_roles()` and `require_scopes()` on the Runtime API (SIP-0062). If a user bypasses the UI and calls a command directly, the API rejects unauthorized requests with HTTP 403.

### 7.5 Scopes Used by Console

| Scope | Used By |
|-------|---------|
| `cycles:read` | Cycles, Runs, Home panels |
| `cycles:write` | Create/cancel cycle, create/cancel run, gate decisions |
| `tasks:read` | Agent monitor, task views |
| `agents:read` | Agent status cards |
| `admin:write` | System health check command |

---

## 8. Left Nav Layout

The left navigation bar shows 4 entries contributed by plugins, ordered by priority:

```
 ┌─────┐
 │  S  │  ← SquadOps logo (shell branding)
 └─────┘
 ───────
  Views
 ───────
 🏠 Home      ← squadops.home      (priority 999)
 ⚡ Cycles    ← squadops.cycles    (priority 800)
 🔍 Projects  ← squadops.projects  (priority 600)
 ⚙️ Systems   ← squadops.system    (priority 400)
 ───────
 Actions
 ───────
 ⌨️ Commands  ← Continuum built-in (Cmd+K palette)
```

Plugins without nav entries (`squadops.artifacts`, `squadops.agents`, `squadops.observability`) contribute panels that appear within the perspectives above.

---

## 9. CLI Parity Matrix (Normative)

> **Stability rule**: This matrix is keyed to **SIP-0065 v0.9.4** CLI surface. If the CLI changes (commands added, renamed, or removed), the parity matrix MUST be updated in the same PR as the CLI change. Exceptions to parity (CLI commands intentionally not exposed in the UI) must be documented in this section with rationale.

Every CLI command from SIP-0065 maps to a UI equivalent:

| CLI Command | Plugin | UI Interaction |
|-------------|--------|----------------|
| `squadops status` | `squadops.home` + `squadops.system` | Home summary cards + System health grid |
| `squadops login` | Shell auth | Keycloak OIDC login flow |
| `squadops logout` | Shell auth | Logout button → Keycloak end-session |
| `squadops version` | `squadops.system` | Footer version display |
| `squadops auth whoami` | Shell header | User context in header right |
| `projects list` | `squadops.projects` | Project list panel |
| `projects show` | `squadops.projects` | Project detail (click row) |
| `cycles create` | `squadops.cycles` | "Create Cycle" command (form dialog) |
| `cycles list` | `squadops.cycles` | Cycle list panel with filters |
| `cycles show` | `squadops.cycles` | Cycle detail (click row) |
| `cycles cancel` | `squadops.cycles` | "Cancel Cycle" command (confirmation) |
| `runs list` | `squadops.cycles` | Run timeline within cycle detail |
| `runs show` | `squadops.cycles` | Run detail panel |
| `runs retry` | `squadops.cycles` | "Start Run" command |
| `runs cancel` | `squadops.cycles` | "Cancel Run" command (confirmation) |
| `runs gate --approve` | `squadops.cycles` | "Approve" button on gate decision panel |
| `runs gate --reject` | `squadops.cycles` | "Reject" button on gate decision panel (confirmation) |
| `runs assemble` | `squadops.cycles` | "Download Build" button on run detail (zips `source` + `test` + `config` artifacts) |
| `squad-profiles list` | `squadops.projects` | Profile list panel |
| `squad-profiles show` | `squadops.projects` | Profile detail (click row) |
| `squad-profiles active` | `squadops.projects` | Active badge on profile list |
| `squad-profiles set-active` | `squadops.projects` | "Set Active" command (confirmation) |
| `artifacts ingest` | `squadops.artifacts` | "Ingest Artifact" command (file upload dialog) |
| `artifacts get` | `squadops.artifacts` | Artifact detail card (click row) |
| `artifacts download` | `squadops.artifacts` | "Download" button on artifact detail |
| `artifacts list` | `squadops.artifacts` | Artifact list panel with filters |
| `baseline set` | `squadops.artifacts` | "Set Baseline" command (confirmation) |
| `baseline get` | `squadops.artifacts` | Baseline viewer in artifact browser |
| `baseline list` | `squadops.artifacts` | Baseline list panel |

---

## 10. Phased Delivery

### Phase 1 — Shell Deployment + Auth

- Docker image build pipeline (Continuum shell + plugin build)
- `docker-compose.yml` service entry for `squadops-console`
- Keycloak OIDC login/logout flow
- `squadops.home` plugin (summary dashboard)
- `squadops.system` plugin (health grid)
- Console branding (logo, title, CSS overrides)

**Acceptance gate**: Console boots, login works, home shows live data from Runtime API.

### Phase 2 — Core Operations

- `squadops.cycles` plugin (full cycle/run/gate management)
- `squadops.projects` plugin (project/profile browsing)
- Command bus wiring for all write operations

**Acceptance gate**: Create cycle → start run → approve gate → observe run status update to completed — all via UI. Command bus audit log contains entries for each write operation.

### Phase 3 — Monitoring

- `squadops.artifacts` plugin (artifact browser + baselines)
- `squadops.agents` plugin (agent status monitoring)
- `squadops.observability` plugin (Prefect + Langfuse metrics)

**Acceptance gate**: Artifact list + download + ingest works via UI. Observability panels render with either live data or "service unavailable" state. All 7 plugins loaded. CLI parity matrix is the target; exceptions (if any) documented in §9 with rationale.

### Phase 4 — Production Hardening

- Health-check app demolition
- Reverse proxy configuration (Caddy/nginx) providing single-origin routing:
  - `http://localhost:4040/` → console shell (static + API)
  - `http://localhost:4040/api/v1/...` → runtime-api:8001
  - `http://localhost:4040/prefect/...` → prefect-server:4200 (if proxied)
  - `http://localhost:4040/langfuse/...` → langfuse:3000 (if proxied)
- Plugin `fetch()` calls use **relative URLs** (e.g., `/api/v1/...`) in production, resolved by the reverse proxy. Environment variable absolute URLs are for local dev only.
- Production CORS and CSP headers
- Console monitoring and alerting

**Acceptance gate**: Health-check app removed, all traffic via single-origin reverse proxy.

---

## 11. Testing Strategy

### 11.1 Smoke Tests

- Console container starts and reaches READY lifecycle state
- All 7 plugins discovered, loaded, and contribute to registry
- Login flow completes and `/auth/userinfo` returns identity
- Home dashboard renders with data from Runtime API

### 11.2 Plugin Unit Tests

Each plugin has unit tests for:
- Manifest schema validation (plugin.toml parses correctly)
- `register(ctx)` produces expected contributions
- Command handlers call correct API endpoints
- Error states handled (API down, auth expired, not found)

### 11.3 Integration Tests

- Full cycle lifecycle via console (create → run → gate → complete)
- Artifact ingestion via file upload dialog
- Profile switch and verification
- Observability panels render with live Prefect/Langfuse data

### 11.4 Contract Tests

- Plugin manifests validate against Continuum manifest schema
- Custom element tag names match `tag_prefix` conventions
- Contribution slot IDs reference valid Continuum regions
- Command danger levels match operation semantics

---

## 12. Non-Goals (v0.9.8)

1. **Mobile-responsive design** — the console is a desktop operator tool
2. **Real-time WebSocket updates** — polling in V1; WebSocket can be added later
3. **Plugin marketplace or distribution** — plugins are built and packaged in the Docker image
4. **Custom user theming** — consistent theme via Continuum CSS variables only
5. **Workflow builder or editor** — the console monitors and operates; it does not orchestrate
6. **Agent chat interface** — listed as a future nav entry but out of scope for this SIP
7. **CRP profile editor** — profiles are edited as YAML files, not via UI in V1

---

## 13. Acceptance Criteria

- **AC-1**: Console boots as a Docker container and loads all 7 plugins to READY state
- **AC-2**: Keycloak OIDC login flow completes; user identity (roles, display name) visible in header
- **AC-3**: Home dashboard displays active cycle count, recent runs, agent status from live API data
- **AC-4**: Full cycle lifecycle executable via UI: create cycle → start run → approve gate → run completes
- **AC-5**: Artifacts are browsable, ingestable (file upload), and downloadable; baselines manageable
- **AC-6**: Prefect flow metrics and Langfuse LLM trace data visible in observability panels
- **AC-7**: CLI parity matrix (Section 9) is 100% covered — every CLI command has a UI equivalent
- **AC-8**: All write operations produce audit trail entries in Continuum command bus
- **AC-9**: Individual plugin failure results in DEGRADED state, not console crash
- **AC-10**: System plugin provides all health-check app monitoring capabilities
- **AC-11**: Viewer role sees read-only panels; operator/admin roles see action buttons
- **AC-12**: `docker-compose up` starts console alongside existing services with no manual configuration

---

## Appendix A: Backend API Surface Assumptions

Every Runtime API endpoint the console depends on, with provenance. Endpoints marked "new" must be implemented before the plugin that uses them.

| Method | Path | Used By Plugin | Source | Status |
|--------|------|---------------|--------|--------|
| `GET` | `/health` | system | SIP-0048 | Exists |
| `GET` | `/health/infra` | system | SIP-0048 | Exists |
| `GET` | `/auth/userinfo` | shell auth | SIP-0062 | Exists |
| `GET` | `/api/v1/projects` | home, projects | SIP-0064 | Exists |
| `POST` | `/api/v1/projects` | projects | SIP-0064 | Exists |
| `GET` | `/api/v1/projects/{id}` | projects | SIP-0064 | Exists |
| `POST` | `/api/v1/projects/{id}/cycles` | cycles | SIP-0064 | Exists |
| `GET` | `/api/v1/projects/{id}/cycles` | home, cycles | SIP-0064 | Exists |
| `GET` | `/api/v1/projects/{id}/cycles/{id}` | cycles | SIP-0064 | Exists |
| `POST` | `/api/v1/projects/{id}/cycles/{id}/cancel` | cycles | SIP-0064 | Exists |
| `POST` | `/api/v1/.../cycles/{id}/runs` | cycles | SIP-0064 | Exists |
| `GET` | `/api/v1/.../cycles/{id}/runs` | home, cycles | SIP-0064 | Exists |
| `GET` | `/api/v1/.../runs/{id}` | cycles | SIP-0064 | Exists |
| `POST` | `/api/v1/.../runs/{id}/cancel` | cycles | SIP-0064 | Exists |
| `POST` | `/api/v1/.../runs/{id}/gates/{name}` | cycles | SIP-0064 | Exists |
| `POST` | `/api/v1/.../artifacts/ingest` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/artifacts/{id}` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/artifacts/{id}/download` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/projects/{id}/artifacts` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/.../cycles/{id}/artifacts` | artifacts | SIP-0064 | Exists |
| `POST` | `/api/v1/.../baseline/{type}` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/.../baseline/{type}` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/.../baseline` | artifacts | SIP-0064 | Exists |
| `GET` | `/api/v1/squad-profiles` | projects | SIP-0064 | Exists |
| `GET` | `/api/v1/squad-profiles/{id}` | projects | SIP-0064 | Exists |
| `GET` | `/api/v1/squad-profiles/active` | projects | SIP-0064 | Exists |
| `POST` | `/api/v1/squad-profiles/active` | projects | SIP-0064 | Exists |
| `GET` | `/api/v1/tasks/agent/{name}` | agents | Legacy (main.py) | Exists |
| `GET` | `/api/v1/tasks/status/{status}` | agents | Legacy (main.py) | Exists |
| `GET` | `/api/v1/tasks/summary/{cycle_id}` | agents | Legacy (main.py) | Exists |
| `POST` | `:4200/api/flow_runs/filter` | home, observability | Prefect API | External |
| `POST` | `:4200/api/flow_runs/history` | observability | Prefect API | External |
| `POST` | `:4200/api/task_runs/count` | observability | Prefect API | External |
| `GET` | `:3000/api/public/traces` | observability | Langfuse API | External |
| `GET` | `:3000/api/public/observations` | observability | Langfuse API | External |
| `GET` | `:3000/api/public/metrics/daily` | home, observability | Langfuse API | External |

All Runtime API endpoints marked "Exists" are verified against the current codebase (SIP-0064 routes + legacy main.py inline handlers). No new backend endpoints are required for this SIP.

---

## Appendix B: Health-Check App Parity Checklist

The `squadops.system` plugin must provide equivalent functionality for these health-check app capabilities before the health-check app (port 8000) can be removed:

| Capability | Health App Source | System Plugin Equivalent |
|-----------|------------------|------------------------|
| Service liveness | `/health` | Health grid (green/red per service) |
| Dependency connectivity (Postgres) | `/health/infra` | Infra panel: pg pool status |
| Dependency connectivity (RabbitMQ) | `/health/infra` | Infra panel: queue connectivity |
| Dependency connectivity (Redis) | `/health/infra` | Infra panel: cache connectivity |
| Runtime version info | `/health` response body | Footer version display |
| Basic runtime stats | `/health/infra` response body | Infra panel: connection counts, uptime |

Any health-check-only diagnostics not listed above are deferred to v0.11.x.
