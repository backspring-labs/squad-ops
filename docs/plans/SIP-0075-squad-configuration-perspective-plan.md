# SIP-0075: Squad Configuration Perspective — Implementation Plan

## Context

SIP-0075 adds squad profile CRUD (Postgres-backed with YAML seeding), model management via Ollama proxy, `config_overrides` wiring through to `chat()` calls, experiment comparison, and a new console perspective. The SIP is accepted at `sips/accepted/SIP-0075-Squad-Configuration-Perspective.md`. Branch: `feature/sip-0075-squad-configuration-perspective`.

### Key Invariants

These rules apply across all phases:

1. **Postgres is authoritative after startup.** When `squad_profile_provider="postgres"`, Postgres is the single runtime source for squad profiles after startup seeding. YAML is seed/import input only, not the active runtime source of truth. Runtime CRUD changes are never written back to YAML.

2. **YAML seeds are one-shot.** Once a YAML-seeded profile has been recorded in `squad_profiles_seed_log`, subsequent YAML edits do not auto-update the Postgres row. Updating a seeded profile thereafter must happen via CRUD/API/CLI or an explicit future reseed/import action.

3. **Profile IDs are immutable and server-generated.** `profile_id` is generated server-side by slugifying `name` on create/clone. User-supplied IDs are not accepted in V1. On collision, reject with 409 Conflict — the operator picks a different name. No silent suffix appending. Renaming changes `name`, never `profile_id`. This keeps cycle snapshot references stable.

4. **`config_overrides` keys are hard-validated.** Unknown override keys are a 422 validation error, not a warning. Only model availability (unpulled models) produces warnings. This prevents `config_overrides` from becoming a shadow config system.

5. **Comparison uses historical snapshot truth.** The Compare tab reads profile/model information from the cycle's persisted `squad_profile_snapshot_ref` and run metadata captured at execution time, not from the current active profile. Profile edits after cycle creation do not retroactively change comparison data.

6. **CLI command group naming.** `squad-profiles` is the canonical CLI group for squad profile CRUD. `request-profiles` remains the group for cycle request profiles. Neither is shortened or aliased.

---

## Phase 1: Squad Profile Persistence + CRUD API + CLI

### 1.1 DDL Migration

**Create** `infra/migrations/003_squad_profiles.sql`

```sql
CREATE TABLE IF NOT EXISTS squad_profiles (
    profile_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1, is_active BOOLEAN NOT NULL DEFAULT FALSE,
    agents JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_squad_profiles_active ON squad_profiles (is_active) WHERE is_active = TRUE;
CREATE TABLE IF NOT EXISTS squad_profiles_seed_log (
    profile_id TEXT PRIMARY KEY, seeded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 1.2 Domain Model Additions

**Modify** `src/squadops/cycles/models.py` — add exceptions + constant:
- `ProfileNotFoundError(CycleError)`, `ActiveProfileDeletionError(CycleError)`, `ProfileValidationError(CycleError)`
- `ALLOWED_CONFIG_OVERRIDE_KEYS = frozenset({"temperature", "max_completion_tokens", "timeout_seconds"})`
- `is_active` stays OUT of the `SquadProfile` frozen dataclass — storage concern only

### 1.3 Profile Utilities

**Create** `src/squadops/cycles/profile_utils.py`
- `slugify_profile_name(name) -> str` — lowercase, hyphens, max 64 chars
- `validate_profile_id(profile_id) -> None` — raise `ProfileValidationError` if invalid
- `validate_config_overrides(overrides) -> list[str]` — return list of unknown keys
- `validate_agent_entries(agents) -> list[str]` — reject empty `model` strings, empty `agent_id`, duplicate agent_ids

### 1.4 Port Interface Extension

**Modify** `src/squadops/ports/cycles/squad_profile.py` — add abstract methods:
- `create_profile(profile) -> SquadProfile`
- `update_profile(profile_id, name, description, agents) -> SquadProfile`
- `delete_profile(profile_id) -> None` (raises `ActiveProfileDeletionError`)
- `activate_profile(profile_id) -> SquadProfile` (atomic deactivate old + activate new; returns the newly active profile for immediate UI refresh)
- `get_active_profile_id() -> str | None`
- `seed_profiles(profiles, active_id) -> int`

**Modify** `adapters/cycles/config_squad_profile.py` — add stubs that raise `CycleError("Read-only: config provider does not support CRUD")` for all new methods.

### 1.5 Postgres Adapter

**Create** `adapters/cycles/postgres_squad_profile.py`

Follow `postgres_cycle_registry.py` pattern: constructor takes `asyncpg.Pool`, `_row_to_profile()` helper, parameterized SQL.

Key behaviors:
- `activate_profile`: single transaction — `UPDATE SET is_active=FALSE WHERE is_active=TRUE` then `UPDATE SET is_active=TRUE WHERE profile_id=$1`
- `seed_profiles`: for each YAML profile, check seed_log first. If profile_id in seed_log → skip. Otherwise INSERT seed_log + INSERT squad_profiles (both ON CONFLICT DO NOTHING)
- `agents` column: serialize `AgentProfileEntry` tuples as JSONB list-of-dicts
- `update_profile`: `version = version + 1`, `updated_at = NOW()`

**Modify** `adapters/cycles/factory.py` — add `"postgres"` branch to `create_squad_profile_port()`.

### 1.6 Config + Startup Wiring

**Modify** `src/squadops/config/schema.py` — add `squad_profile_provider: str = "config"` to `CyclesConfig`.

**Modify** `src/squadops/api/runtime/deps.py` — add `_llm_port`, `set_llm_port()`, `get_llm_port()` (needed for model validation warnings).

**Modify** `src/squadops/api/runtime/main.py` (~line 247):
1. Read `config.cycles.squad_profile_provider`
2. When `"postgres"`: create Postgres adapter, seed from YAML via ConfigSquadProfile, call `seed_profiles()`
3. Create OllamaAdapter and register via `set_llm_port()` for model endpoints

### 1.7 API Layer

**Modify** `src/squadops/api/routes/cycles/dtos.py`:
- Add `AgentProfileEntryRequest`, `ProfileCreateRequest`, `ProfileUpdateRequest`, `ProfileCloneRequest`
- Add `is_active: bool = False`, `updated_at: datetime | None = None`, `warnings: list[str]` to `SquadProfileResponse`

**Modify** `src/squadops/api/routes/cycles/mapping.py`:
- `profile_to_response()` takes `is_active: bool`, `warnings: list[str]` params

**Modify** `src/squadops/api/routes/cycles/errors.py` — add new error types to `_ERROR_MAP`.

**Modify** `src/squadops/api/routes/cycles/profiles.py` — add endpoints:
- `POST /` — create (validate overrides as hard 422, validate `model` non-empty, generate warnings for unpulled models only when Ollama is reachable — if Ollama is unreachable, skip model validation entirely and log it, do not silently produce zero warnings as if validation passed)
- `PUT /{id}` — update (increment version)
- `POST /{id}/clone` — clone with new name/ID
- `DELETE /{id}` — delete (reject if active)
- `POST /{id}/activate` — atomic activation
- Enrich existing `list` and `get` endpoints with `is_active` flag

### 1.8 CLI

**Modify** `src/squadops/cli/client.py` — add `put()` and `delete()` methods to `APIClient`.

**Modify** `src/squadops/cli/commands/profiles.py` — add commands:
- `create --file <yaml>` — import profile from YAML
- `clone <id> --name <name>`
- `activate <id>`
- `delete <id>`
- Print warnings from response to stderr

### 1.9 Phase 1 Tests

| Test File | What |
|-----------|------|
| `tests/unit/cycles/test_profile_utils.py` | slugify, validate_profile_id, validate_config_overrides |
| `tests/unit/cycles/test_postgres_squad_profile.py` | Adapter with mock asyncpg.Pool — CRUD, activation atomicity, seed log |
| `tests/unit/cycles/test_squad_profile_port.py` | Port contract tests (parametrized abstract methods) |
| `tests/unit/api/test_squad_profile_routes.py` | All CRUD endpoints, warnings, validation errors |
| `tests/unit/cli/test_profiles_crud.py` | New CLI commands |

---

## Phase 2: Model Management API + CLI

### 2.1 Pull Job Tracker

**Create** `src/squadops/api/runtime/pull_tracker.py`
- `PullJob` dataclass: `pull_id, model_name, status, error, started_at, completed_at`
- In-memory dict `_pull_jobs: dict[str, PullJob]`
- Functions: `create_pull_job()`, `get_pull_job()`, `complete_pull_job()`, `fail_pull_job()`
- **Restart behavior:** Pull job state is in-memory only in V1. Runtime restart clears all pull job tracking. Clients should treat unknown `pull_id` after restart as expired/lost state. API returns 404 with `"Pull job not found or expired"` for missing `pull_id`.

### 2.2 Ollama Adapter Extensions

**Modify** `adapters/llm/ollama.py` — add concrete methods (not on abstract port):
- `pull_model(name) -> dict` — POST `/api/pull` with `stream: false`, 600s timeout
- `delete_model(name) -> dict` — DELETE `/api/delete`
- `list_pulled_models() -> list[dict]` — GET `/api/tags` with full metadata (size, modified_at)

### 2.3 API + DTOs

**Modify** `src/squadops/api/routes/cycles/dtos.py`:
- `PulledModelResponse` (name, size_bytes, modified_at, `in_active_profile: bool`, `used_by_active_profile: list[str]`, registry_spec) — field names are precise: "in active profile" not the ambiguous "in use"
- `PullModelRequest` (name)
- `PullStatusResponse` (pull_id, model_name, status, error)

**Modify** `src/squadops/api/routes/cycles/models.py` — add endpoints:
- `GET /api/v1/models/pulled` — list with `in_active_profile`/`used_by_active_profile` cross-ref against active profile only
- `POST /api/v1/models/pull` — spawn background task, return 202 + `pull_id`
- `GET /api/v1/models/pull/{pull_id}/status` — poll from in-memory tracker
- `DELETE /api/v1/models/{name}` — proxy to Ollama

### 2.4 CLI

**Create** `src/squadops/cli/commands/models.py` — new Typer app:
- `pulled` — table of pulled models
- `pull <name>` — POST + poll status with spinner
- `remove <name>` — DELETE with confirmation

**Modify** `src/squadops/cli/main.py` — register `models` command group.

### 2.5 Phase 2 Tests

| Test File | What |
|-----------|------|
| `tests/unit/api/test_pull_tracker.py` | In-memory pull job lifecycle |
| `tests/unit/api/test_models_api.py` | Pulled list with cross-ref, pull 202, status polling, delete |
| `tests/unit/llm/test_ollama_pull_delete.py` | pull_model/delete_model with mocked httpx |
| `tests/unit/cli/test_models_commands.py` | pulled, pull, remove CLI commands |

---

## Phase 3: Config Overrides Wiring

### 3.1 Task Plan Injection

**Modify** `src/squadops/cycles/task_plan.py`:
- New helper: `_resolve_agent_config(profile, role) -> (agent_id, model, config_overrides)`
- Inject `agent_model` and `agent_config_overrides` into each TaskEnvelope's `inputs` dict
- Replaces existing `_resolve_agent_id()` (now returns 3 values)

**Resolution semantics (no silent fallbacks):**
- Missing *required* role (strat, dev, qa, data, lead) in profile: raise `CycleError` at plan generation time. The operator selected this profile — a missing core role is a configuration error, not something to silently work around.
- Missing *optional* role (builder) in profile: skip — builder steps are already excluded when no builder role is present (existing `_has_builder_role` check).
- `REQUIRED_PLAN_ROLES = frozenset({"strat", "dev", "qa", "data", "lead"})` — defined in `task_plan.py`, checked before envelope generation.
- Empty `model` string: rejected at API validation on profile create/update (`model` must be non-empty). Task plan treats empty string as `None` → adapter uses `default_model`, but this path should never occur with API-validated profiles.
- Missing/empty `config_overrides`: use `{}` — no overrides applied, fully backward compatible. This is safe because "no overrides" is the intentional default.

### 3.2 Base Handler Update

**Modify** `src/squadops/capabilities/handlers/cycle_tasks.py` — `_CycleTaskHandler.handle()` (line 86-107):
- Read `agent_overrides = inputs.get("agent_config_overrides", {})`
- Read `agent_model = inputs.get("agent_model") or None`
- Build `chat_kwargs` from overrides (temperature, max_tokens, timeout_seconds, model)
- Change `context.ports.llm.chat(messages)` → `context.ports.llm.chat(messages, **chat_kwargs)`

### 3.3 Build Handler Updates

**Same file** — `DevelopmentDevelopHandler.handle()` and `QATestHandler.handle()`:

Precedence (lowest → highest):
1. Model defaults (from model_spec)
2. Capability defaults (max_completion_tokens)
3. `config_overrides` from squad profile
4. `applied_defaults` from cycle request profile (generation_timeout already handled)

Changes:
- Use `agent_model` for model_spec lookup instead of `context.ports.llm.default_model`
- Apply `config_overrides["max_completion_tokens"]` after capability/model_spec resolution
- Pass `temperature` and `model` to `chat()` from overrides
- Update LangFuse generation records to use resolved model name

`BuilderAssembleHandler` — V1 boundary: builder consumes only `model` and `temperature` from squad profile overrides. `max_completion_tokens` and `timeout_seconds` are NOT wired for builder in V1 (per SIP-0073 D2). Do not add these later without an explicit design decision.

### 3.4 Phase 3 Tests

| Test File | What |
|-----------|------|
| `tests/unit/cycles/test_task_plan_overrides.py` | agent_model + agent_config_overrides in envelopes |
| Modify `tests/unit/capabilities/test_cycle_task_handlers.py` | Overrides flow to chat(), precedence, backward compat |

---

## Phase 4: Console Perspective + Icon Refresh

### 4.1 Icon Refresh

| Plugin | File(s) | Old | New |
|--------|---------|-----|-----|
| squadops.home | `plugin.toml` + `__init__.py` | `activity` | `home` |
| squadops.cycles | `plugin.toml` + `__init__.py` | `clock` | `refresh-cw` |
| squadops.projects | `plugin.toml` + `__init__.py` | `compass` | `folder` |

### 4.2 New Plugin: `squadops.squad`

**Create** `console/continuum-plugins/squadops.squad/` — full plugin:
- `plugin.toml` — id `squadops.squad`, icon `users`, priority 700
- `__init__.py` — register nav + panel
- `ui/package.json`, `ui/vite.config.js` — standard Svelte 5 + Vite setup
- `ui/src/index.js` — exports

### 4.3 Perspective Registration

**Modify** `console/app/main.py` — add `PerspectiveSpec(id="squad", ...)` alongside "cycles".

### 4.4 Svelte Components

| Component | Element Name | Purpose |
|-----------|-------------|---------|
| `SquadPerspective.svelte` | `squadops-squad-perspective` | Tab nav: Health, Profiles, Models, Compare |
| `AgentHealthTab.svelte` | `squadops-squad-agent-health` | Agent table with "Configured Model" column (from active profile, not runtime truth — column header says "Configured Model" explicitly) |
| `SquadProfilesTab.svelte` | `squadops-squad-profiles` | Profile list + CRUD actions |
| `ProfileEditForm.svelte` | `squadops-squad-profile-form` | Create/edit form with model dropdowns + override editors |
| `ModelsTab.svelte` | `squadops-squad-models` | Pulled models browser + pull form |
| `CompareTab.svelte` | `squadops-squad-compare` | Side-by-side cycle comparison (reads from cycle's persisted snapshot, not current active profile) |

All follow existing patterns: `$state()`, `$derived()`, `window.squadops.apiFetch()`, `--continuum-*` CSS vars, graceful degradation.

**Empty states (first-run UX):**
- No squad profiles → CTA: "Create your first squad profile" / "Import from YAML"
- No pulled models → CTA: "Pull a model to get started" + note that model selection may be limited
- No comparison data → guidance: "Run cycles with different profiles to compare results"
- Agent Health with no agents → "No agents reporting" (existing behavior from data-driven fix)

### 4.5 Phase 4 Tests

- Plugin registration tests (verify `register()` creates correct contributions)
- Command handler proxy tests in `console/app/main.py`

---

## Verification

```bash
# 1. Run regression suite
./scripts/dev/run_new_arch_tests.sh -v

# 2. Rebuild runtime-api + console
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api

# 3. Verify DDL applied
docker exec squadops-postgres psql -U squadops -c "\dt squad_profiles*"

# 4. API smoke tests
curl localhost:8001/api/v1/squad-profiles | jq '.[0] | {profile_id, is_active}'
curl localhost:8001/api/v1/models/pulled | jq '.[0] | {name, in_use}'
curl -X POST localhost:8001/api/v1/squad-profiles -H 'Content-Type: application/json' \
  -d '{"name":"test-profile","agents":[{"agent_id":"neo","role":"dev","model":"qwen2.5:7b"}]}' | jq

# 5. CLI smoke tests
squadops squad-profiles list
squadops models pulled

# 6. Grep for hardcoded agent names (should find ZERO in platform source, excluding tests/examples)
grep -rn '"Max"\|"Neo"\|"Nat"\|"Eve"\|"Bob"' src/ adapters/ console/ \
  --include='*.py' --include='*.svelte' \
  --exclude-dir=tests --exclude-dir=examples

# 7. Console — open browser, verify Squad perspective with all 4 tabs
```
