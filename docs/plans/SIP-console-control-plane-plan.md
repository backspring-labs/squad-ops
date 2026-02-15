# SquadOps Console Control-Plane UI — Implementation Plan

> **SIP**: `sips/proposals/SIP-SquadOps-Console-Control-Plane-UI.md`
> **Target**: v0.9.8
> **Prerequisite**: This plan assumes the v0.9.8 API surface from SIP-0064, SIP-0065, and SIP-0062 is already present and deployed.

## Context

SquadOps has a fully functional API (SIP-0064), CLI (SIP-0065), Keycloak auth (SIP-0062), and observability stack (Prefect + Langfuse). The missing piece is an operator-facing UI. Continuum is a plugin-driven control-plane shell (SvelteKit + FastAPI + Web Components) designed for exactly this purpose, maintained as an independent upstream repo and pinned via `continuum.lock`. This plan implements the SIP by deploying Continuum as a branded "SquadOps Console" Docker container with 7 domain plugins.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Continuum is fetched from the upstream git repo at a ref recorded in `continuum.lock`. Allowed ref types: 40-char SHA, annotated tag, or branch name (e.g., `main`). Branch refs resolve to a deterministic SHA at build time (see §1.1 fetch logic). No host-path injection, no `CONTINUUM_PATH`. CI/release builds may forbid branch refs; branches are allowed for local dev. Updating Continuum is an intentional, versioned action: change `continuum.lock` ref in a reviewable PR. | Reproducible builds pinned to exact ref; branch allowed for dev velocity; Continuum stays an independent repo with its own versioning; no vendored copies to maintain |
| D2 | Plugins at `continuum-plugins/squadops.{name}/` in squad-ops repo root | Mirrors `adapters/` convention for non-core code; SIP §2 D2 |
| D3 | Plugin `dist/` directories NOT checked into git | Built during Docker build and local dev script; `.gitignore` covers `continuum-plugins/*/dist/` |
| D4 | SvelteKit shell built into `/app/web/build/` in container, served via `StaticFiles(html=True)` | SPA fallback for client-side routing |
| D5 | Auth BFF endpoints (`/auth/login`, `/auth/callback`, `/auth/refresh`, `/auth/logout`) live in console backend, not Continuum core | No upstream shell modification; SIP §7.2 BFF pattern |
| D6 | In-memory session dict for BFF refresh tokens (keyed by httpOnly `session_id` cookie). Console restart invalidates all sessions (users must re-login). Multi-instance deployments are out of scope until Redis-backed sessions. | Acceptable for single-instance v0.9.8; Redis follow-up documented |
| D7 | Plugin Web Components read `window.__SQUADOPS_CONFIG__` for API base URLs. All browser `fetch()` calls MUST use `SQUADOPS_API_PUBLIC_URL` (never internal Docker URLs). Command handlers MUST use `SQUADOPS_API_URL` (internal Docker network, never public URLs). When Phase 4 proxy exists, observability plugins switch to relative `/prefect/...` and `/langfuse/...` paths. | Injected into shell HTML at build time; strict internal/external URL separation |
| D8 | Command handlers are async Python functions registered on `CommandBus` via `main.py` wiring. Console backend uses client-credentials to obtain a service token and attaches `Authorization: Bearer <service_token>` on all internal runtime-api calls via `httpx.AsyncClient`. | Handlers call Runtime API via `httpx.AsyncClient` with internal Docker URL; service token ensures auth works even when runtime-api requires authentication |
| D9 | `SQUADOPS_API_URL` (internal Docker network) for command handlers; `SQUADOPS_API_PUBLIC_URL` (browser-reachable) for `window.__SQUADOPS_CONFIG__`. All command handlers MUST use internal `SQUADOPS_API_URL` only. All browser fetches MUST use `SQUADOPS_API_PUBLIC_URL` only. | Separate internal vs external URL concerns |
| D10 | `squadops.home` is `required = true`; all other plugins `required = false`. Home failure → runtime enters FAILED state (console not READY, returns 503). Other plugin failures → DEGRADED state (console still serves remaining plugins). These semantics are final — if Home should degrade instead, change to `required = false`. | Clear lifecycle contract; no contradiction between required flag and behavior |
| D11 | Inter-component communication via `window.dispatchEvent(new CustomEvent('squadops:...'))` | Web Components have no shared framework; custom events are the standard pattern |
| D12 | Console branding via CSS variable overrides injected in shell HTML | No Continuum core changes; `--continuum-accent-primary` etc. overridden |
| D13 | Caddy (not nginx) for Phase 4 reverse proxy. Caddy routes `/auth/userinfo` to runtime-api; all other `/auth/*` endpoints are handled by console-backend BFF. | Simpler config, automatic HTTPS, HTTP/2; auth routing exception is explicit |
| D14 | Polling intervals: home 30s, cycles 15s, agents 10s, observability 60s, system 30s. Home summary caps per-project follow-up requests to first 10 projects and shows "+N more" if exceeded. | Balance between freshness and API load; prevents fanout explosion |
| D15 | Tests: Python unit tests for `__init__.py` registration + command handlers; smoke tests for Docker boot. Each plugin UI directory MUST include `package-lock.json`; builds fail fast if missing (`npm ci` requires it). | Playwright browser tests are a Phase 4+ follow-up; lockfiles ensure deterministic JS builds |

---

## Phase 1: Shell Deployment + Auth

### 1.1 Dockerfile

**New file**: `docker/console/Dockerfile`

Multi-stage build:
- **Stage 0** (`alpine/git`): Fetch Continuum source at pinned ref.
  - Read `CONTINUUM_GIT_URL` and `CONTINUUM_REF` from build args (values sourced from `continuum.lock` via `.env.console`)
  - **Fetch logic** (deterministic checkout for all ref types):
    - If `CONTINUUM_REF` matches `/^[0-9a-f]{40}$/` (SHA): `git init /continuum && cd /continuum && git remote add origin ${CONTINUUM_GIT_URL} && git fetch --depth 1 origin ${CONTINUUM_REF} && git checkout FETCH_HEAD`
    - Else if `CONTINUUM_REF` contains `tag` or has no `/` and doesn't match a known branch pattern (tag): `TAG_REF="${CONTINUUM_REF#refs/tags/}" && git init /continuum && cd /continuum && git remote add origin ${CONTINUUM_GIT_URL} && git fetch --depth 1 origin "refs/tags/${TAG_REF}" && git checkout FETCH_HEAD`
    - Else (branch name, e.g., `main`): `git init /continuum && cd /continuum && git remote add origin ${CONTINUUM_GIT_URL} && git fetch --depth 1 origin ${CONTINUUM_REF} && git checkout "origin/${CONTINUUM_REF}"`. Print resolved SHA in build logs: `echo "Resolved ${CONTINUUM_REF} → $(git rev-parse HEAD)"`. Optionally persist resolved SHA to `/continuum/.resolved_sha` for traceability.
  - **Guardrail**: CI/release builds may forbid branch refs; branches are allowed for local dev.
  - Output: `/continuum/` directory with exact pinned source
- **Stage 1** (`node:20-slim`): Copy Continuum `web/` from Stage 0, `npm ci && npm run build` → SvelteKit static build
- **Stage 2** (`node:20-slim`): Copy all `continuum-plugins/squadops.*/ui/` directories, build each with `npm ci && npm run build` → `dist/plugin.js` per plugin. Each plugin UI directory MUST include `package-lock.json`; builds fail fast if missing (`npm ci` requires it).
- **Stage 3** (`python:3.11-slim`): Runtime image
  - Install Continuum Python package from Stage 0 source (`pip install /continuum` — pinned, immutable). No editable installs in production; Continuum changes require bumping `continuum.lock` ref.
  - Copy console application code (`main.py`, `auth_bff.py`)
  - Copy built shell from Stage 1 → `/app/web/build/`
  - Copy plugin Python code (`__init__.py`, `plugin.toml`) + built `dist/` from Stage 2 → `/app/plugins/`
  - Expose 4040, healthcheck on `/health`
  - CMD: `uvicorn main:app --host 0.0.0.0 --port 4040`

**`continuum.lock`** (new file in repo root):
```yaml
continuum:
  git_url: <CONTINUUM_GIT_URL>
  ref: main                  # 40-char SHA, annotated tag, or branch name
  resolved_sha: ""           # populated at build time for traceability (branch refs only)
  version: "0.1.0"           # optional semantic version for human readability
  updated_at: "2026-02-14"
```
Any Continuum upgrade is expressed as a change to `continuum.lock` (ref/version) in the same PR. A helper script (`scripts/dev/gen_console_env.sh`) parses the lock file and generates `.env.console` containing `CONTINUUM_GIT_URL` and `CONTINUUM_REF`. `docker-compose.yml` loads `.env.console` so Docker build args always match `continuum.lock`. No other mechanism for propagating build args is used.

### 1.2 Console Entry Point

**New file**: `docker/console/main.py`

Thin FastAPI wrapper around Continuum:
- `lifespan`: create `ContinuumRuntime(plugins_dir="./plugins")`, call `runtime.boot()`, register command handlers. Command handler registration uses `ContinuumRuntime` extension hooks (e.g., `runtime.command_bus.register_handler()`). If no public extension point exists, handlers are registered directly on the command bus instance in the console wrapper only — no Continuum core changes.
- Include `continuum_api_router` (serves `/health`, `/api/registry`, `/plugins/{id}/assets/{path}`, `/api/commands/execute`)
- Include `auth_bff_router` (serves `/auth/*`)
- CORS middleware for dev (localhost:4040, localhost:5173, localhost:8001)
- Mount `StaticFiles(directory="./web/build", html=True)` **last** for SPA fallback
- Inject `window.__SQUADOPS_CONFIG__` into shell HTML via Jinja2 template or post-build script

### 1.3 Auth BFF Module

**New file**: `docker/console/auth_bff.py`

FastAPI router with `/auth` prefix:
- `GET /auth/login` — generates `state`, `code_verifier`, and `code_challenge` (S256). Stores `{state: {code_verifier, created_at}}` in `_pending_logins` dict (TTL 10 minutes). Returns JSON `{auth_url}` containing the Keycloak authorization URL (including `state`, `code_challenge`, `code_challenge_method=S256`). The shell reads `auth_url` and performs `window.location = auth_url` to redirect the browser. Each `/auth/login` call opportunistically purges expired `_pending_logins` entries.
- `GET /auth/callback` — accepts `code` + `state` as query params (standard OAuth redirect). Looks up `code_verifier` from `_pending_logins[state]` and deletes the entry. If `state` is missing or expired, returns 400. Exchanges authorization code + `code_verifier` for tokens at Keycloak token endpoint; stores refresh token server-side in `_sessions` dict; sets `session_id` cookie (httpOnly, Secure in prod, SameSite=Lax, Path=/); returns access token + expires_in to browser. No refresh token is ever returned to the browser.
- `POST /auth/refresh` — requires `session_id` cookie; calls Keycloak token endpoint with stored refresh token; updates stored token; returns new access token + expires_in
- `POST /auth/logout` — revokes refresh token at Keycloak, clears session and cookie

Environment: `KEYCLOAK_URL` (internal), `KEYCLOAK_PUBLIC_URL` (browser-facing), `CONSOLE_CLIENT_ID`, `CONSOLE_REDIRECT_URI`

### 1.4 docker-compose.yml

Build-time Continuum pinning is sourced from `continuum.lock`. A small helper (`scripts/dev/gen_console_env.sh`) parses the lock file and generates `.env.console` containing:
```
CONTINUUM_GIT_URL=<url from continuum.lock>
CONTINUUM_REF=<ref from continuum.lock>
```
`docker-compose.yml` loads this env file for console builds so the Dockerfile build args always match `continuum.lock`. The helper MUST be run before `docker-compose build` (the build script in §1.8 calls it automatically).

**Modify**: Add `squadops-console` service:
- Build context: `.`, dockerfile: `docker/console/Dockerfile`, args: `CONTINUUM_GIT_URL`, `CONTINUUM_REF` (sourced from `.env.console`)
- Port: `4040:4040`
- Environment: `SQUADOPS_API_URL`, `SQUADOPS_API_PUBLIC_URL`, `PREFECT_API_URL`, `PREFECT_API_PUBLIC_URL`, `LANGFUSE_API_URL`, `LANGFUSE_API_PUBLIC_URL`, `KEYCLOAK_URL`, `KEYCLOAK_PUBLIC_URL`, `CONSOLE_CLIENT_ID`, `CONSOLE_REDIRECT_URI`
- Depends on: `runtime-api`
- Network: `squadnet`

### 1.5 Plugin: `squadops.home`

**New directory**: `continuum-plugins/squadops.home/`

**`plugin.toml`**:
- `required = true`
- Nav: "Home", icon `home`, priority 999, target signal perspective
- Panel: `squadops-home-summary` in `ui.slot.main`, perspective `signal`, priority 999

**`__init__.py`**: `register(ctx)` — 1 nav + 1 panel contribution

**Svelte component** — `HomeSummary.svelte` (`<squadops-home-summary>`):
- Fetches `GET /api/v1/projects`, then per-project `GET /api/v1/projects/{id}/cycles?status=active` (capped to first 10 projects; shows "+N more" if exceeded), and `GET /health/agents`
- Renders summary cards: active cycles count, recent runs (last 5 with status badges), agent status (5 agents), alert badges (failed runs, pending gates)
- Polls every 30s via `setInterval` in `onMount`

**Vite config**: Standard lib build (`formats: ['es']`, `outDir: '../dist'`, `customElement: true`)

### 1.6 Plugin: `squadops.system`

**New directory**: `continuum-plugins/squadops.system/`

**`plugin.toml`**:
- Nav: "Systems", icon `settings`, priority 400, target systems perspective
- 3 panels: `squadops-system-health` (priority 800), `squadops-system-plugins` (priority 600), `squadops-system-infra` (priority 400) — all in `ui.slot.main`, perspective `systems`
- Command: `squadops.health_check` (safe)

**`__init__.py`**: `register(ctx)` — 1 nav + 3 panels + 1 command

**Svelte components**:
- `SystemHealth.svelte` — fetches console self-health from `GET /health` (console backend at localhost:4040) and runtime infrastructure from `GET {apiBaseUrl}/health/infra` (Runtime API). Renders service health grid (pg, rabbit, redis, prefect, langfuse, keycloak) plus console lifecycle state.
- `SystemPlugins.svelte` — fetches `GET /api/registry` (console backend); renders plugin status table with load state, contribution counts
- `SystemInfra.svelte` — fetches `GET {apiBaseUrl}/health/infra` (Runtime API); detailed infrastructure cards with connectivity details

### 1.7 Console Branding

Inject into shell HTML:
- `window.__SQUADOPS_CONFIG__` object with API base URLs
- CSS overrides: `--continuum-accent-primary: #6366f1` (SquadOps indigo) and other brand colors
- SquadOps SVG logo replacing Continuum logo in header

### 1.8 Plugin Auth Client (`apiFetch`)

The shell owns an in-memory `access_token` (never persisted to `localStorage`, `sessionStorage`, or cookies) and exposes `window.squadops.apiFetch()` as the single authorized HTTP client for Runtime API calls. The shell initializes `window.squadops` on boot before any plugin loads.

**Cross-bundle sharing model**: `window.squadops.apiFetch = apiFetch`. Plugins call `window.squadops.apiFetch(url, options)`. The shell is the only owner of the in-memory token and refresh logic. No ES module imports across plugin bundles.

`window.squadops.apiFetch(url, options)` behaves like `fetch()` but:
- Adds `Authorization: Bearer <access_token>` to every request
- On HTTP 401, calls `POST /auth/refresh` (cookie-based), updates the in-memory `access_token`, and retries the original request exactly once
- If refresh fails (401/403 from Keycloak), clears the token, fetches `GET /auth/login` to obtain `auth_url`, and performs `window.location = auth_url` to redirect to Keycloak

Plugins MUST NOT store tokens in `localStorage`, `sessionStorage`, or cookies. Plugins MUST NOT call Runtime API directly via raw `fetch()` — always use `window.squadops.apiFetch()`. This avoids cross-bundle module resolution; the shell is the single owner of token state.

### 1.9 Build Script

**New file**: `scripts/dev/build_console_plugins.sh`

Iterates `continuum-plugins/squadops.*/ui/`, runs `npm ci && npm run build` for each. Used for local development.

### 1.10 Phase 1 Tests

**New files** in `tests/unit/console/`:
- `test_home_plugin.py` (~6 tests) — validates `register(ctx)` produces expected nav + panel contributions
- `test_system_plugin.py` (~8 tests) — validates 1 nav + 3 panels + 1 command
- `test_auth_bff.py` (~10 tests) — callback, refresh, logout flows with mocked httpx; session management; expired session handling
- `test_console_main.py` (~4 tests) — app creation, lifespan, static file mounting

**New file** in `tests/smoke/`:
- `test_console_boot.py` (~3 tests) — container boots, `/health` returns READY, `/api/registry` includes both Phase 1 plugins, `/plugins/squadops.home/assets/plugin.js` returns 200

---

## Phase 2: Core Operations

### 2.1 Plugin: `squadops.cycles`

**New directory**: `continuum-plugins/squadops.cycles/`

**`plugin.toml`**:
- Nav: "Cycles", icon `zap`, priority 800, target signal perspective
- 3 panels: `squadops-cycles-list` (800), `squadops-cycles-run-timeline` (700), `squadops-cycles-run-detail` (600) — all `ui.slot.main`, perspective `signal`
- 6 commands: `create_cycle` (safe), `create_run` (safe), `cancel_cycle` (confirm), `cancel_run` (confirm), `gate_approve` (safe), `gate_reject` (confirm)

**`__init__.py`**: `register(ctx)` — 1 nav + 3 panels + 6 commands

**Svelte components**:
- `CyclesList.svelte` — fetches projects then cycles per project; filterable table; click row dispatches `squadops:select-cycle` custom event; polls 15s
- `CyclesRunTimeline.svelte` — listens for `squadops:select-cycle`; fetches runs for selected cycle; visual timeline with status badges; click run dispatches `squadops:select-run`
- `CyclesRunDetail.svelte` — listens for `squadops:select-run`; shows full run info (status, timestamps, config hash, gate decisions, artifact refs); gate decision panel with Approve/Reject buttons that dispatch commands via `POST /api/commands/execute`

**Command handlers** (wired in `main.py`):
- `squadops_create_cycle` → `POST /api/v1/projects/{project_id}/cycles`
- `squadops_create_run` → `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs`
- `squadops_cancel_cycle` → `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/cancel`
- `squadops_cancel_run` → `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/cancel`
- `squadops_gate_approve` → `POST .../gates/{gate_name}` with `{"decision": "approved"}`
- `squadops_gate_reject` → `POST .../gates/{gate_name}` with `{"decision": "rejected"}`

All handlers use `httpx.AsyncClient(base_url=SQUADOPS_API_URL)` with `Authorization: Bearer <service_token>` obtained via client-credentials grant (see D8).

### 2.2 Plugin: `squadops.projects`

**New directory**: `continuum-plugins/squadops.projects/`

**`plugin.toml`**:
- Nav: "Projects", icon `folder`, priority 600, target discovery perspective
- 2 panels: `squadops-projects-list` (800), `squadops-projects-profiles` (600) — `ui.slot.main`, perspective `discovery`
- 1 command: `set_active_profile` (confirm)

**`__init__.py`**: `register(ctx)` — 1 nav + 2 panels + 1 command

**Svelte components**:
- `ProjectsList.svelte` — fetches `GET /api/v1/projects`; table with project_id, name, description, tags; click dispatches `squadops:select-project`
- `ProjectsProfiles.svelte` — fetches `GET /api/v1/squad-profiles` and `GET /api/v1/squad-profiles/active`; profile list with active badge; agent config detail (model, role, enabled per agent); "Set Active" button

**Command handler**: `squadops_set_active_profile` → `POST /api/v1/squad-profiles/active`

### 2.3 Phase 2 Tests

**New files** in `tests/unit/console/`:
- `test_cycles_plugin.py` (~8 tests) — 1 nav + 3 panels + 6 commands
- `test_projects_plugin.py` (~6 tests) — 1 nav + 2 panels + 1 command
- `test_cycle_command_handlers.py` (~12 tests) — mocked httpx tests for all 6 cycle commands (success, API error, validation)

---

## Phase 3: Monitoring

### 3.1 Plugin: `squadops.artifacts`

**New directory**: `continuum-plugins/squadops.artifacts/`

**`plugin.toml`**:
- No nav entry
- 3 panels: `squadops-artifacts-list` (`ui.slot.main`, signal, 400), `squadops-artifacts-browser` (`ui.slot.main`, discovery, 500), `squadops-artifacts-detail` (`ui.slot.right_rail`, signal, 500)
- 3 commands: `ingest_artifact` (safe), `set_baseline` (confirm), `download_artifact` (safe)

**Svelte components**:
- `ArtifactsList.svelte` — fetches project artifacts; filterable by project, cycle, type; renders filename, size, media_type, created_at
- `ArtifactsBrowser.svelte` — full-page in discovery perspective; baseline management (lists baselines per project, promotion UI)
- `ArtifactsDetail.svelte` — right rail card; metadata, content hash, download button

**Command handlers**:
- `squadops_ingest_artifact` → `POST /api/v1/projects/{project_id}/artifacts/ingest` (multipart)
- `squadops_set_baseline` → `POST /api/v1/projects/{project_id}/baseline/{artifact_type}`
- `squadops_download_artifact` → `GET /api/v1/artifacts/{artifact_id}/download`

### 3.2 Plugin: `squadops.agents`

**New directory**: `continuum-plugins/squadops.agents/`

**`plugin.toml`**:
- No nav entry, no commands (view-only)
- 2 panels: `squadops-agents-status` (`ui.slot.right_rail`, signal, 800), `squadops-agents-tasks` (`ui.slot.main`, signal, 300)

**Svelte components**:
- `AgentsStatus.svelte` — fetches agent list + per-agent state; 5 agent cards (Max/Neo/Nat/Eve/Data) with lifecycle state, current task; polls 10s
- `AgentsTasks.svelte` — fetches `GET /api/v1/tasks/agent/{name}` per agent; table grouped by agent

### 3.3 Plugin: `squadops.observability`

**New directory**: `continuum-plugins/squadops.observability/`

**`plugin.toml`**:
- No nav entry, no commands
- 3 panels: `squadops-obs-flow-metrics` (`ui.slot.main`, signal, 200), `squadops-obs-llm-traces` (`ui.slot.main`, signal, 100), `squadops-obs-cost-summary` (`ui.slot.right_rail`, signal, 300)

**Svelte components**:
- `FlowMetrics.svelte` — fetches `POST {prefectBaseUrl}/api/flow_runs/filter`; completed/failed counts, average duration; shows "Service unavailable" on error. Phase 3 uses public URLs (`PREFECT_API_PUBLIC_URL`); Phase 4 switches to relative `/prefect/...` paths via reverse proxy.
- `LlmTraces.svelte` — fetches `GET {langfuseBaseUrl}/api/public/traces`; generation count, latency, token usage; shows "Service unavailable" on error. Phase 3 uses public URLs (`LANGFUSE_API_PUBLIC_URL`); Phase 4 switches to relative `/langfuse/...` paths.
- `CostSummary.svelte` — fetches Langfuse daily metrics; token counts, cost estimates. Same URL transition as LlmTraces.

### 3.4 Phase 3 Tests

**New files** in `tests/unit/console/`:
- `test_artifacts_plugin.py` (~8 tests) — 3 panels + 3 commands
- `test_agents_plugin.py` (~4 tests) — 2 panels, 0 commands
- `test_observability_plugin.py` (~6 tests) — 3 panels, degradation behavior

---

## Phase 4: Production Hardening

### 4.1 Reverse Proxy

**New file**: `docker/console/Caddyfile`

Routes (order matters — most specific first):
- `/api/v1/*` → `runtime-api:8001`
- `/auth/userinfo` → `runtime-api:8001` (explicit exception: only this `/auth/*` path goes to runtime-api)
- `/auth/*` → `console-backend:4040` (BFF handles login, callback, refresh, logout)
- `/health/infra` → `runtime-api:8001`
- `/health/agents*` → `runtime-api:8001` (matches both `/health/agents` and `/health/agents/*`; use `handle_path /health/agents* { reverse_proxy runtime-api:8001 }`)
- `/prefect/*` → `prefect-server:4200` (strip prefix)
- `/langfuse/*` → `langfuse:3000` (strip prefix)
- Everything else → `console-backend:4040`

CSP headers: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`

### 4.2 Health-Check App Demolition

- Remove `health-check` service from `docker-compose.yml`
- Mark `src/squadops/api/health_app.py` as deprecated (keep for rollback, do not delete)
- Verify all Appendix B parity items covered by `squadops.system` plugin

### 4.3 docker-compose.yml Update

- Add Caddy service at port 4040 (replaces direct console port exposure)
- Console backend moves to internal-only port
- Update documentation port references

### 4.4 Phase 4 Tests

- Reverse proxy routing verification
- CSP header presence
- Single-origin (no CORS needed)
- Health-check parity (Appendix B checklist)

---

## Files Summary

| File | Phase | Action |
|------|-------|--------|
| `continuum.lock` | 1 | New |
| `docker/console/Dockerfile` | 1 | New |
| `docker/console/main.py` | 1 | New |
| `docker/console/auth_bff.py` | 1 | New |
| `docker/console/requirements.txt` | 1 | New |
| `docker-compose.yml` | 1, 4 | Modify |
| `.gitignore` | 1 | Modify (add `.env.console`, `continuum-plugins/*/dist/`) |
| `scripts/dev/gen_console_env.sh` | 1 | New |
| `scripts/dev/build_console_plugins.sh` | 1 | New |
| `continuum-plugins/squadops.home/*` (6 files) | 1 | New |
| `continuum-plugins/squadops.system/*` (8 files) | 1 | New |
| `continuum-plugins/squadops.cycles/*` (8 files) | 2 | New |
| `continuum-plugins/squadops.projects/*` (7 files) | 2 | New |
| `continuum-plugins/squadops.artifacts/*` (8 files) | 3 | New |
| `continuum-plugins/squadops.agents/*` (7 files) | 3 | New |
| `continuum-plugins/squadops.observability/*` (8 files) | 3 | New |
| `docker/console/Caddyfile` | 4 | New |
| `tests/unit/console/test_home_plugin.py` | 1 | New |
| `tests/unit/console/test_system_plugin.py` | 1 | New |
| `tests/unit/console/test_auth_bff.py` | 1 | New |
| `tests/unit/console/test_console_main.py` | 1 | New |
| `tests/smoke/test_console_boot.py` | 1 | New |
| `tests/unit/console/test_cycles_plugin.py` | 2 | New |
| `tests/unit/console/test_projects_plugin.py` | 2 | New |
| `tests/unit/console/test_cycle_command_handlers.py` | 2 | New |
| `tests/unit/console/test_artifacts_plugin.py` | 3 | New |
| `tests/unit/console/test_agents_plugin.py` | 3 | New |
| `tests/unit/console/test_observability_plugin.py` | 3 | New |

**Total new files**: ~70 (plugin manifests, Python, Svelte, configs, tests)
**Estimated new tests**: ~75

---

## Key Reuse Points

| What | Where | How Used |
|------|-------|----------|
| `ContinuumRuntime` | `continuum/src/continuum/app/runtime.py` (at pinned ref) | Console `main.py` creates and boots it |
| `continuum_api_router` | `continuum/src/continuum/adapters/web/api.py` (at pinned ref) | Mounted in console `main.py` for `/api/registry`, `/plugins/*`, `/health` |
| `CommandBus` | `continuum/src/continuum/app/command_bus.py` (at pinned ref) | Command handlers registered for plugin write operations |
| Sample plugin pattern | `continuum/plugins/continuum.sample_signal/` (at pinned ref) | Template for all 7 plugin structures |
| Vite plugin build | `continuum/plugins/continuum.sample_signal/ui/vite.config.js` (at pinned ref) | Replicated for each plugin UI |
| Runtime API endpoints | `src/squadops/api/routes/cycles/*.py` | Plugin fetch() targets and command handler targets |
| Auth middleware | `src/squadops/api/middleware/auth.py` | Console BFF tokens passed as Bearer headers to Runtime API |
| Health infra endpoint | `src/squadops/api/routes/health.py` | System plugin health grid data source |

---

## Verification

### Phase 1
```bash
# Build and start
docker-compose build squadops-console
docker-compose up -d squadops-console

# Verify boot
curl http://localhost:4040/health  # → lifecycle_state: ready
curl http://localhost:4040/api/registry | jq '.plugins | length'  # → 2

# Verify plugins loaded
curl http://localhost:4040/api/registry | jq '.plugins[].id'
# → squadops.home, squadops.system

# Verify plugin assets served
curl -I http://localhost:4040/plugins/squadops.home/assets/plugin.js  # → 200

# Verify auth flow
# 1. Open http://localhost:4040 in browser
# 2. Click login → redirects to Keycloak
# 3. Authenticate → redirects back with access token
# 4. Home dashboard shows live data

# Unit tests
pytest tests/unit/console/ -v
```

### Phase 2
```bash
# Full cycle lifecycle via UI:
# 1. Open Cycles perspective
# 2. Cmd+K → "Create Cycle" → fill form → execute
# 3. Run appears in timeline as QUEUED → RUNNING
# 4. Gate appears → click "Approve"
# 5. Run completes → status updates to COMPLETED

# Verify command handlers by observing runtime-api side effects
curl http://localhost:8001/api/v1/projects/play_game/cycles | jq '.[0].cycle_id'  # → cycle created via UI
# Verify command execution logged in console container stdout:
docker logs squadops-console 2>&1 | grep "command_executed"
```

### Phase 3
```bash
# Verify all 7 plugins loaded
curl http://localhost:4040/api/registry | jq '.plugins | length'  # → 7

# Artifact workflow
# 1. Open artifact browser → ingest file → verify in list
# 2. Download artifact → verify content matches

# Observability panels
# If Prefect/Langfuse running → metrics render
# If down → "Service unavailable" state shown
```

### Phase 4
```bash
# Verify single-origin routing
curl http://localhost:4040/api/v1/projects  # → proxied to runtime-api
curl -I http://localhost:4040/ | grep Content-Security-Policy  # → present

# Verify health-check removed
curl http://localhost:8000/health  # → connection refused

# Run full regression
./scripts/dev/run_new_arch_tests.sh -v
```

---

## Appendix: Console Required API Surface

Every endpoint a plugin calls, classified by status. All endpoints are expected to exist for v0.9.8; two endpoints are optional and MUST degrade gracefully if missing (marked with `*` below).

| Method | Path | Plugin | Source | Status |
|--------|------|--------|--------|--------|
| `GET` | `/api/v1/projects` | home, cycles, projects, artifacts | `routes/cycles/projects.py` | EXISTS |
| `GET` | `/api/v1/projects/{id}` | projects | `routes/cycles/projects.py` | EXISTS |
| `POST` | `/api/v1/projects/{id}/cycles` | cycles | `routes/cycles/cycles.py` | EXISTS |
| `GET` | `/api/v1/projects/{id}/cycles` | home, cycles | `routes/cycles/cycles.py` | EXISTS |
| `GET` | `/api/v1/projects/{id}/cycles/{id}` | cycles | `routes/cycles/cycles.py` | EXISTS |
| `POST` | `/api/v1/.../cycles/{id}/cancel` | cycles | `routes/cycles/cycles.py` | EXISTS |
| `POST` | `/api/v1/.../cycles/{id}/runs` | cycles | `routes/cycles/runs.py` | EXISTS |
| `GET` | `/api/v1/.../cycles/{id}/runs` | cycles | `routes/cycles/runs.py` | EXISTS |
| `GET` | `/api/v1/.../runs/{id}` | cycles | `routes/cycles/runs.py` | EXISTS |
| `POST` | `/api/v1/.../runs/{id}/cancel` | cycles | `routes/cycles/runs.py` | EXISTS |
| `POST` | `/api/v1/.../runs/{id}/gates/{name}` | cycles | `routes/cycles/runs.py` | EXISTS |
| `GET` | `/api/v1/squad-profiles` | projects | `routes/cycles/profiles.py` | EXISTS |
| `GET` | `/api/v1/squad-profiles/active` | projects | `routes/cycles/profiles.py` | EXISTS |
| `POST` | `/api/v1/squad-profiles/active` | projects | `routes/cycles/profiles.py` | EXISTS |
| `GET` | `/api/v1/squad-profiles/{id}` | projects | `routes/cycles/profiles.py` | EXISTS |
| `POST` | `/api/v1/.../artifacts/ingest` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `GET` | `/api/v1/artifacts/{id}` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `GET` | `/api/v1/artifacts/{id}/download` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `GET` | `/api/v1/projects/{id}/artifacts` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `POST` | `/api/v1/.../baseline/{type}` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `GET` | `/api/v1/.../baseline/{type}` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `GET` | `/api/v1/.../baseline` | artifacts | `routes/cycles/artifacts.py` | EXISTS |
| `GET` | `/api/v1/agents` | agents | `routes/agents.py` | EXISTS |
| `GET` | `/api/v1/agents/{id}/state` | agents | `routes/agents.py` | EXISTS |
| `GET` | `/api/v1/tasks/agent/{name}` | agents | `runtime/main.py` | EXISTS * |
| `GET` | `/health` | system | `routes/health.py` | EXISTS |
| `GET` | `/health/infra` | system | `routes/health.py` | EXISTS |
| `GET` | `/health/agents` | home, agents | `routes/agents.py` | EXISTS * |
| `GET` | `/auth/userinfo` | home (user context) | `routes/auth.py` | EXISTS |

**\* Optional endpoints (graceful degradation required)**:
1. `GET /api/v1/tasks/agent/{name}` — used by `squadops.agents` plugin
2. `GET /health/agents` — used by `squadops.home` and `squadops.agents` plugins

These two endpoints may not be present in all Runtime API deployments. Plugins that call them MUST treat a 404 or connection error as "data unavailable" and render a placeholder (e.g., "Agent data unavailable") rather than failing. Their absence MUST NOT block console READY state or prevent other panels from rendering.
