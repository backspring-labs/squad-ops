# Health Endpoint Migration: health-check → runtime-api

## Context

Console plugins (`squadops.agents`, `squadops.system`, `squadops.home`) fetch health data from the legacy health-check service (port 8000) via cross-origin requests. The health-check service has no CORS headers, so the browser blocks all responses — causing "UNAVAILABLE" agent status and missing infrastructure data in the console.

The health-check service is already deprecated and commented out in `docker-compose.yml`. Additionally, the `HealthCheckHttpReporter` adapter (which agents use to POST heartbeats) defaults to `http://health-check:8000`, meaning **agent heartbeats are silently failing** in the current stack. This plan moves all health endpoints into the runtime-api (which already has CORS, auth, and Postgres), updates the CLI, console proxy, and plugins to use a unified API surface.

**Goal**: Single API surface on runtime-api under `/api/v1/platform/...` for all health/status data. CLI and console plugins consume the same endpoints. No separate health-check service. The simple `/health` liveness probe remains unchanged for Docker/LB use.

---

## New Endpoint Contract

All platform monitoring endpoints use the standard `/api/v1/` prefix, consistent with projects, cycles, runs, etc.

```
GET  /api/v1/platform/infra                          → infrastructure probes (9 components)
GET  /api/v1/platform/agents                         → agent status list
GET  /api/v1/platform/agents/{agent_id}              → single agent status
POST /api/v1/platform/agents/{agent_id}/heartbeat    → agent heartbeat upsert (requires agent key)
```

`/health` remains the simple liveness probe: `{"status": "healthy", "service": "runtime-api", "version": "..."}`.

### Response Schemas

**`GET /api/v1/platform/infra`** — returns `list[InfraComponent]`:
```json
[
  {
    "component": "RabbitMQ",
    "type": "Message Broker",
    "status": "online | offline | degraded",
    "version": "3.12.1",
    "purpose": "Handles inter-agent communication",
    "latency_ms": 42,
    "notes": "0 messages in queue",
    "checked_at": "2026-02-16T12:00:00Z"
  }
]
```

**`GET /api/v1/platform/agents`** — returns `list[AgentStatus]`:
```json
[
  {
    "agent_id": "max",
    "agent_name": "Max",
    "role": "Task Lead - Governance and coordination",
    "network_status": "online | offline",
    "lifecycle_state": "READY | WORKING | BLOCKED | UNKNOWN",
    "version": "0.9.7",
    "tps": 42,
    "memory_count": 128,
    "last_heartbeat_ts": "2026-02-16T12:34:56Z",
    "current_task_id": "task-123"
  }
]
```

**`POST /api/v1/platform/agents/{agent_id}/heartbeat`** — request body:
```json
{
  "lifecycle_state": "READY",
  "current_task_id": null,
  "version": "0.9.7",
  "tps": 42,
  "memory_count": 128
}
```

---

## Phase 1: Extract HealthChecker + New Route Module

### 1A. Create `src/squadops/api/runtime/health_checker.py`

Extract from `src/squadops/api/health_app.py` by symbol:

- **HealthChecker class** with all `check_*` probe methods: `check_rabbitmq`, `check_postgres`, `check_redis`, `check_prefect`, `check_prometheus`, `check_grafana`, `check_otel_collector`, `check_langfuse`, `check_keycloak`
- **Instances helpers**: `_load_instances()`, `_get_instances_order()`, `_get_default_instances()` — instances.yaml loading with mtime-based cache
- **Agent status**: `_compute_network_status()` (heartbeat timeout derivation), `get_agent_status()` (DB query + instances.yaml merge + network_status derivation), `update_agent_status_in_db()` (heartbeat upsert)
- **Reconciliation**: `reconciliation_loop()` — background task for offline detection and lifecycle_state→UNKNOWN transition

**Key changes from original**:
- Constructor takes explicit `pg_pool`, `redis_client`, `http_client`, `config` params (no global state)
- Replace `aiohttp` HTTP checks with `httpx.AsyncClient` (shared instance, passed in constructor)
- Replace `pika.BlockingConnection` in `check_rabbitmq()` with async `aio_pika` probe (already a runtime-api dep)
- Each `check_*` method has a per-check timeout (default 3s); on timeout, returns `status: "degraded"` with `notes: "timeout"`
- Add `latency_ms` and `checked_at` fields to each infra check response
- Read URLs from `config` object instead of module-level globals
- Drop legacy console chat/response consumer code (not health-related)

### 1B. Create `src/squadops/api/routes/platform.py`

New APIRouter with prefix `/api/v1/platform`, tags `["platform"]`:

```
GET  /infra                          → asyncio.gather all check_* with 5s overall timeout
GET  /agents                         → get_agent_status()
GET  /agents/{agent_id}              → single agent lookup
POST /agents/{agent_id}/heartbeat    → heartbeat upsert (requires X-Agent-Key header)
```

**Concurrency guardrails for `/infra`**:
- Per-check timeout: 3s (configurable via `config.agent.health_check_timeout`)
- Overall gather timeout: 5s via `asyncio.wait_for()`
- On timeout: individual check returns `{"status": "degraded", "notes": "timeout"}`
- On overall timeout: return partial results with timed-out checks marked degraded

Move Pydantic models (AgentStatusCreate, AgentStatusUpdate) from `src/squadops/api/routes/agents.py` into this module.

DI: add `_health_checker` singleton to `deps.py` with `set_health_checker()` / `get_health_checker()`.

### 1C. Wire up in `src/squadops/api/runtime/main.py`

In `startup_event()`:
1. Create `redis.asyncio` client from `config.comms.redis.url` (env var `SQUADOPS__COMMS__REDIS__URL` already set)
2. Create shared `httpx.AsyncClient` for health probes (separate from the API client)
3. Create `HealthChecker(pg_pool=pool, redis_client=redis_client, http_client=http_client, config=config)`
4. Launch `reconciliation_loop()` as `asyncio.Task` — store ref for clean cancellation
5. `set_health_checker(health_checker)` in deps

In `shutdown_event()`:
1. Cancel reconciliation task via `task.cancel()` and `await task` (not boolean flag)
2. Close httpx client and redis client

Register router: `app.include_router(platform_router)`

### 1D. Auth posture: split read vs write

In `src/squadops/api/middleware/auth.py`:
- **Reads** (`GET /api/v1/platform/*`): add to `_ALWAYS_ALLOWLISTED` as prefix match — unauthenticated access for CLI and monitoring tools
- **Writes** (`POST .../heartbeat`): require `X-Agent-Key` header checked in the route handler (not middleware). Key sourced from `config.agent.heartbeat_key` env var. In dev/local, if key is empty/unset, heartbeats are accepted without the header (logged as warning).

This separates read access (broad) from write access (agent-key gated) without requiring full OIDC tokens from agents.

### 1E. Update runtime-api dependencies

`src/squadops/api/runtime/requirements.txt` — add explicitly:
- `redis>=5.0.0,<6.0.0` (for `redis.asyncio`)
- `httpx>=0.25.0` (for HTTP-based health probes)

Both already used elsewhere in the project but must be declared explicitly for the runtime-api Docker image.

### 1F. Update heartbeat adapter

`adapters/observability/healthcheck_http.py`:
- Change default base_url from `http://health-check:8000` to `http://runtime-api:8001`
- Change env var from `SQUADOPS_HEALTH_CHECK_URL` to `SQUADOPS_RUNTIME_API_URL` (fallback to old name for backward compat)
- Update POST path from `/health/agents/status` to `/api/v1/platform/agents/{agent_id}/heartbeat`
- Add `X-Agent-Key` header from env var `SQUADOPS_AGENT_KEY` (empty = omitted)
- Replace `aiohttp` with `httpx.AsyncClient` (consistent with project; `aiohttp` only used here)
- Declare `httpx` as an explicit dependency in the adapter's imports

### 1G. Reconciliation loop: ownership and lifecycle

- **runtime-api is the single owner** of offline detection and `network_status` reconciliation
- Reconciliation interval and heartbeat threshold sourced from named config keys: `config.agent.reconciliation_interval` (default 45s) and `config.agent.heartbeat_timeout_window` (default 90s) — these already exist in the config schema
- Shutdown: cancel the `asyncio.Task`, await it, catch `CancelledError` gracefully
- No other service performs offline detection

---

## Phase 2: CLI Update (validates endpoints before UI work)

### 2A. Update `src/squadops/cli/commands/meta.py`

Remove `_fetch_health_data()` helper. Use the authenticated `APIClient` for all calls:

```python
# Infrastructure health (now on runtime-api, same base_url)
try:
    infra_data = client.get("/api/v1/platform/infra")
except CLIError:
    infra_data = None

# Agent status (now on runtime-api, same base_url)
try:
    agents_data = client.get("/api/v1/platform/agents")
except CLIError:
    agents_data = None
```

The `APIClient` already handles auth, timeouts, and base_url — no separate `health_url` needed.

**Actionable failure messages**:
- Connection refused → `"runtime-api unreachable at {base_url}"`
- 401/403 → `"unauthorized — run 'squadops auth login'"`
- Timeout → `"request timed out after {timeout}s"`
- 5xx → `"server error ({status_code})"`

### 2B. Remove `health_url` from `src/squadops/cli/config.py`

- Remove `health_url` field from `CLIConfig` dataclass
- Remove `health_url` parsing from `load_config()`
- All health data now comes from `base_url` (runtime-api)

### 2C. Update CLI tests

`tests/unit/cli/test_commands_meta.py`:
- Remove `health_url` from `MOCK_CONFIG`
- Remove `_fetch_health_data` mock patches
- Mock `APIClient.get()` to return infra/agents data for `/api/v1/platform/infra` and `/api/v1/platform/agents` paths
- Add tests for distinct failure modes: unreachable, unauthorized, timeout, server error

---

## Phase 3: Console Proxy + Plugin Updates

### 3A. Add platform proxy routes in `console/app/main.py`

Add proxy endpoints using `_api_request()`. **Forward status codes and error bodies** — don't mask failures:

```python
@app.get("/api/v1/platform/infra")
async def proxy_platform_infra():
    resp = await _api_request("GET", "/api/v1/platform/infra")
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"))

@app.get("/api/v1/platform/agents")
async def proxy_platform_agents():
    resp = await _api_request("GET", "/api/v1/platform/agents")
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"))
```

This preserves distinct failure modes (401 vs 502 vs 504) so plugins can show meaningful errors.

### 3B. Update `config.js`

Remove `healthBaseUrl` from `window.__SQUADOPS_CONFIG__`. Plugins will use relative same-origin paths.

Remove `HEALTH_CHECK_PUBLIC_URL` import/usage from main.py.

### 3C. Update plugin Svelte components

All plugins switch from `fetch(${healthBase}/health/...)` to same-origin `fetch('/api/v1/platform/...')`:

**`console/continuum-plugins/squadops.agents/ui/src/AgentsStatus.svelte`**:
- Remove `healthBase` config lookup
- Change `fetch(${healthBase}/health/agents)` → `fetch('/api/v1/platform/agents')`

**`console/continuum-plugins/squadops.system/ui/src/SystemHealth.svelte`**:
- Remove `healthBase` config lookup
- Change `fetch(${healthBase}/health/infra)` → `fetch('/api/v1/platform/infra')`

**`console/continuum-plugins/squadops.system/ui/src/SystemInfra.svelte`**:
- Remove `healthBase` config lookup
- Change `fetch(${healthBase}/health/infra)` → `fetch('/api/v1/platform/infra')`

**`console/continuum-plugins/squadops.home/ui/src/HomeSummary.svelte`**:
- Remove `healthBase` config lookup
- Change `fetch(${healthBase}/health/agents)` → `fetch('/api/v1/platform/agents')`

---

## Phase 4: Tests

### 4A. New tests: `tests/unit/api/test_platform_routes.py`

- Test `GET /api/v1/platform/infra` returns list matching InfraComponent schema
- Test `GET /api/v1/platform/agents` returns list matching AgentStatus schema
- Test `POST /api/v1/platform/agents/{id}/heartbeat` creates/updates agent heartbeat
- Test heartbeat without agent key is rejected (when key configured)
- Test heartbeat without agent key is accepted (when key not configured, dev mode)
- Test invalid lifecycle_state returns 400
- Test per-check timeout returns degraded status
- Test overall gather timeout returns partial results
- Mock HealthChecker methods to avoid real connections
- ~10-12 tests

### 4B. New tests: `tests/unit/api/test_health_checker.py`

- Test `_compute_network_status()` with various heartbeat timestamps
- Test `get_agent_status()` merges DB rows with instances.yaml order
- Test individual `check_*` methods with mocked connections (online/offline/timeout)
- Test reconciliation loop updates offline agents to lifecycle_state=UNKNOWN
- Test reconciliation task cancellation on shutdown
- ~10-12 tests

### 4C. Update CLI tests

`tests/unit/cli/test_commands_meta.py`:
- Update mock pattern (APIClient.get instead of _fetch_health_data)
- Add tests for distinct failure messages (unreachable, unauthorized, timeout, server error)

### 4D. Update console tests

`tests/unit/console/test_system_plugin.py`, `test_agents_plugin.py`, `test_home_plugin.py`:
- Update URL assertions to use `/api/v1/platform/...` instead of `${healthBase}/health/...`
- ~5 tests updated

---

## Files Modified

| File | Action |
|------|--------|
| `src/squadops/api/runtime/health_checker.py` | **NEW** — extracted HealthChecker |
| `src/squadops/api/routes/platform.py` | **NEW** — platform route module |
| `src/squadops/api/runtime/main.py` | Wire HealthChecker + redis + reconciliation task |
| `src/squadops/api/runtime/deps.py` | Add `set/get_health_checker()` |
| `src/squadops/api/middleware/auth.py` | Add `/api/v1/platform` prefix to read allowlist |
| `src/squadops/api/runtime/requirements.txt` | Add `redis`, `httpx` explicitly |
| `adapters/observability/healthcheck_http.py` | Default URL → runtime-api, new path, agent key |
| `console/app/main.py` | Add proxy routes (status-code passthrough), remove `HEALTH_CHECK_PUBLIC_URL` |
| `console/continuum-plugins/squadops.agents/ui/src/AgentsStatus.svelte` | Same-origin fetch |
| `console/continuum-plugins/squadops.system/ui/src/SystemHealth.svelte` | Same-origin fetch |
| `console/continuum-plugins/squadops.system/ui/src/SystemInfra.svelte` | Same-origin fetch |
| `console/continuum-plugins/squadops.home/ui/src/HomeSummary.svelte` | Same-origin fetch |
| `src/squadops/cli/commands/meta.py` | Use APIClient, `/api/v1/platform/...` paths, actionable errors |
| `src/squadops/cli/config.py` | Remove `health_url` |
| `tests/unit/cli/test_commands_meta.py` | Update mock pattern, failure mode tests |
| `tests/unit/api/test_platform_routes.py` | **NEW** |
| `tests/unit/api/test_health_checker.py` | **NEW** |
| Console test files | Update URL assertions |

---

## Verification

1. **Unit tests**: `pytest tests/unit/api/test_platform_routes.py tests/unit/api/test_health_checker.py tests/unit/cli/test_commands_meta.py -v`
2. **Regression suite**: `./scripts/dev/run_new_arch_tests.sh -v`
3. **Lint**: `ruff check . --fix && ruff format .`
4. **Manual E2E** (after Docker rebuild):
   - `curl http://localhost:8001/api/v1/platform/infra` → list of 9 component checks with latency_ms
   - `curl http://localhost:8001/api/v1/platform/agents` → list of agent status objects
   - `squadops status` → shows runtime, infrastructure, and agent tables (validates CLI migration)
   - Console at `http://localhost:4040` → Agents sidebar shows status, System page shows infra
   - Agent heartbeats: `docker logs squadops-max` shows no heartbeat errors
   - Timeout behavior: stop redis, verify infra endpoint returns `"degraded"` for Redis within 5s
