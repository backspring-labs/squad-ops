---
title: Squad Configuration Perspective
status: accepted
author: SquadOps Core
created_at: '2026-02-26'
sip_number: 75
updated_at: '2026-02-26T20:41:28.627627Z'
---
# SIP: Squad Configuration Perspective

**Status:** Proposed \
**Created:** 2026-02-26 \
**Owner:** SquadOps Core \
**Target Release:** v0.9.14+ \
**Related:** SIP-0069 (Console Control-Plane UI), SIP-0073 (LLM Budget and Timeout Controls), SIP-0074 (Console Cycle Operations UX)

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-26 | Initial proposal |
| 2   | 2026-02-26 | Tightenings: active-profile semantics, seed deletion policy, profile ID immutability, config_overrides scope, pull job state, model validation warning transport, Agent Health model label, comparison artifact granularity, LangFuse degradation, model endpoint contract, CLI import framing, activation atomicity |
| 3   | 2026-02-26 | Navigation icon refresh: replace abstract icons with universally-recognized Lucide icons across all perspectives |

---

## 1. Abstract

The console has no perspective for managing the squad itself. Agent creation is a build-time activity (Dockerfile, container, queue bindings), but the runtime configuration that determines *how* agents behave in a cycle --- model assignment, parameter tuning, squad composition --- is currently locked in YAML files that require restarts to change. This SIP adds a Squad Configuration perspective to the console and supporting API endpoints for squad profile CRUD, model management via Ollama, and wiring `config_overrides` from profiles through to LLM calls. The goal is a zero-rebuild experimentation loop: pull a model, build a profile, run a cycle, compare results.

---

## 2. Problem Statement

Operators experimenting with squad configurations face friction at every step:

1. **Squad profiles are read-only.** Creating or editing a profile requires editing YAML files in `config/squad-profiles/` and restarting the runtime-api. There is no API for profile CRUD, so neither the console nor the CLI can manage profiles at runtime.

2. **Model swaps require manual steps.** To try a different model, the operator must: (a) SSH or exec into the Ollama host, (b) run `ollama pull <model>`, (c) edit the squad profile YAML, (d) restart. The console and CLI have no visibility into what models are available or pulled.

3. **`config_overrides` are ignored.** `AgentProfileEntry.config_overrides` exists on the domain model and is serialized in the DTO, but nothing in the execution path reads it. An operator who sets `temperature: 0.1` in a profile override sees no effect --- the value is silently discarded.

4. **No experiment comparison.** After running cycles with different profiles, the operator manually cross-references Prefect flow runs and LangFuse traces to compare outcomes. There is no unified view that says "profile A produced these artifacts with this token cost, profile B produced these."

5. **Agent health is scattered.** The home dashboard has a new Active Squad section and the Agents plugin shows status, but there is no single perspective where the operator can see agent health, current model assignments, and profile configuration together.

---

## 3. Goals

1. **Squad Configuration perspective** --- a new console perspective that shows agent health, squad profiles, and model management in one place.

2. **Squad profile CRUD API** --- create, clone, edit, and delete squad profiles via runtime-api. Profiles are persisted to Postgres (not YAML files). Existing YAML-loaded profiles are treated as seed data.

3. **Model management API** --- browse models pulled in Ollama, pull new models, and view model specs (context window, max completion tokens). All via runtime-api proxying to Ollama.

4. **Wire `config_overrides`** --- ensure that `config_overrides` from the active squad profile's `AgentProfileEntry` flow through the executor into handler `chat()` calls, so model parameters (temperature, max_tokens) actually take effect.

5. **Experiment comparison** --- a lightweight comparison view that shows two cycles side-by-side: squad profile used, model assignments, artifacts produced, and aggregate token usage from LangFuse.

6. **CLI parity** --- every new API endpoint is accessible from the CLI.

---

## 4. Non-Goals

- **Agent provisioning.** Creating a new agent (container, Dockerfile, queue bindings, `instances.yaml` entry) remains a build-time operation via `rebuild_and_deploy.sh`. This SIP manages the runtime configuration of existing agents, not their infrastructure.
- **Container lifecycle management.** Start/stop/restart of agent containers is not exposed in the console. Exposing the Docker socket to runtime-api has security implications that warrant a separate SIP.
- **Real-time model download progress.** Model pulls may take minutes. V1 shows a "pulling..." status with polling; WebSocket streaming of pull progress is deferred.
- **Multi-Ollama support.** V1 assumes a single Ollama instance. Routing different agents to different Ollama servers is out of scope.
- **Profile versioning history.** V1 tracks a version integer that increments on edit. Full audit log of profile changes is deferred.

---

## 5. Design

### 5.1 Console Perspective Layout

A new perspective registered as `squad` in the console shell:

```
+---------------------------------------------------------------+
| Squad Configuration                                            |
+---------------------------------------------------------------+
|                                                                 |
| [Agent Health]  [Squad Profiles]  [Models]  [Compare]           |
|                                                                 |
+---------------------------------------------------------------+
```

#### 5.1.0 Navigation Icon Refresh

Adding a new perspective is an opportunity to fix the existing icons. The current set uses abstract icons (`activity`, `compass`) that don't communicate their purpose at a glance. All perspectives adopt clear, universally-recognized Lucide icons:

| Perspective | Current Icon | New Icon | Rationale |
|-------------|-------------|----------|-----------|
| Home | `activity` | `home` | Universal — everyone recognizes the house |
| Cycles | `clock` | `refresh-cw` | Circular arrows — literally a "cycle" |
| Projects | `compass` | `folder` | Standard container for work |
| Squad (new) | — | `users` | People silhouettes — immediately says "squad/team" |
| Settings | `settings` | `settings` | Gear/cog — industry standard, no change needed |

Each plugin's `plugin.toml` and `__init__.py` are updated to reflect the new icon names.

Four tabs within the perspective:

**Agent Health** --- live status of all deployed agents (from `/health/agents`). Shows agent name, role, role label, **configured model** (from active squad profile --- see §5.1.1), network status, lifecycle state, version. This consolidates the existing `AgentsStatus` widget into a richer table view.

**Squad Profiles** --- list, create, clone, edit, delete, and activate squad profiles. Each profile shows its agent roster with model assignments and config overrides.

**Models** --- browse pulled Ollama models, view specs, pull new models. Shows which models are in use by the active profile.

**Compare** --- select two completed cycles and view side-by-side: profile used, model assignments, artifacts, and token usage.

#### 5.1.1 Agent Health Model Column

The "Model" column in Agent Health shows the **configured model from the active squad profile**, not the model actually used by a currently running cycle. The column header reads "Configured Model" to make this distinction clear. If the operator changes the active profile while a cycle is in progress, the Agent Health tab reflects the new configuration, but the running cycle continues with the profile snapshot it was created with. A future enhancement may add a "Last Used Model" column derived from the most recent cycle's profile snapshot.

### 5.2 Squad Profile Persistence

Profiles move from YAML-only to Postgres-backed with YAML seeding:

**Startup behavior:**
1. Runtime-api loads YAML profiles from `config/squad-profiles/` as before.
2. For each YAML profile, if no row exists in `squad_profiles` table with that `profile_id`, insert it (seed).
3. If a row already exists, do NOT overwrite --- Postgres is authoritative after first seed.
4. API CRUD operates on Postgres only.

**Deletion policy:** If a YAML-seeded profile is deleted from Postgres via the API, it is NOT re-seeded on the next restart. The seed logic checks for existing rows by `profile_id`; a deleted row is absent, but the seed only inserts if no row has *ever* existed for that `profile_id`. Implementation: a `squad_profiles_seed_log` table records all `profile_id` values that have been seeded. The seed logic skips any `profile_id` present in the seed log, whether or not the profile itself still exists. This ensures deletes are permanent.

```sql
CREATE TABLE squad_profiles_seed_log (
    profile_id  TEXT PRIMARY KEY,
    seeded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Active profile semantics:** `is_active` designates the **operator default** profile for new cycle creation. It does not influence runtime behavior globally --- it is simply the pre-selected profile in the cycle creation form and CLI. Each cycle persists its chosen `squad_profile_id` and a snapshot at creation time. Changing the active profile has no effect on already-created cycles. The active profile is a convenience for the operator, not a global live switch.

**Schema:**
```sql
CREATE TABLE squad_profiles (
    profile_id     TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    version        INTEGER NOT NULL DEFAULT 1,
    is_active      BOOLEAN NOT NULL DEFAULT FALSE,
    agents         JSONB NOT NULL,        -- serialized list of AgentProfileEntry
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only one active profile at a time
CREATE UNIQUE INDEX idx_squad_profiles_active
    ON squad_profiles (is_active) WHERE is_active = TRUE;
```

**Active profile constraint:** at most one profile has `is_active = TRUE`. Setting a profile active deactivates the current one in a single transaction. If the transaction fails, the previous active profile remains active --- there is no transient dual-active state.

### 5.3 Squad Profile CRUD API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/squad-profiles` | List all profiles (existing, enhanced with `is_active`) |
| GET | `/api/v1/squad-profiles/{id}` | Get single profile |
| GET | `/api/v1/squad-profiles/active` | Get the active profile |
| POST | `/api/v1/squad-profiles` | Create new profile |
| PUT | `/api/v1/squad-profiles/{id}` | Update profile (increments version) |
| POST | `/api/v1/squad-profiles/{id}/clone` | Clone profile with new ID and name |
| DELETE | `/api/v1/squad-profiles/{id}` | Delete profile (cannot delete active) |
| POST | `/api/v1/squad-profiles/{id}/activate` | Set as active profile |

**Profile ID rules:**
- `profile_id` is immutable once created. It cannot be changed via update.
- On create: `profile_id` is generated server-side (slugified from `name`) unless explicitly provided in the request body and validated (lowercase alphanumeric + hyphens, max 64 chars).
- On clone: a new `profile_id` is always generated server-side (from the new `name`).
- Renaming a profile changes `name`, never `profile_id`. This keeps cycle snapshot references stable.

**Create/Update request body:**
```json
{
    "name": "experiment-large-models",
    "description": "All agents on 14b models",
    "agents": [
        {
            "agent_id": "neo",
            "role": "dev",
            "model": "qwen2.5:14b",
            "enabled": true,
            "config_overrides": {
                "temperature": 0.3,
                "max_completion_tokens": 4096
            }
        }
    ]
}
```

**Validation:**
- `agent_id` must correspond to a known agent in `instances.yaml` (deployed agents only).
- `model` is validated against pulled Ollama models. If the model is not currently pulled, the API returns a successful response with a `warnings` array in the response body (see §5.3.1). This is not a hard block --- the operator may pull the model before running a cycle.
- `config_overrides` keys are validated against the allowed set (see §5.5.1). Unknown keys are rejected with a 422 response listing the invalid keys.

#### 5.3.1 Warning Transport

API responses for create and update operations include an optional `warnings` array:

```json
{
    "profile_id": "experiment-large-models",
    "name": "experiment-large-models",
    "warnings": [
        "Model 'qwen2.5:14b' is not currently pulled in Ollama. Pull it before running a cycle."
    ],
    ...
}
```

The console renders warnings as dismissible yellow banners below the form. The CLI prints warnings to stderr. Warnings do not prevent the operation from succeeding.

### 5.4 Model Management API

Runtime-api proxies Ollama's model management endpoints. Two distinct model concepts exist:

- **`/api/v1/models`** = internal model registry/specs. These are the models the platform *knows about* (context window, max completion tokens). Static, curated, read-only.
- **`/api/v1/models/pulled`** = models physically present in the configured Ollama instance. These are the models that can actually be used for inference right now.

A model can exist in one list but not the other: the registry may list a model that hasn't been pulled yet, and Ollama may have a pulled model the registry doesn't describe (in which case specs show as `N/A`).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/models` | List model specs from internal registry (existing) |
| GET | `/api/v1/models/pulled` | List models pulled in Ollama (`/api/tags`) |
| POST | `/api/v1/models/pull` | Pull a model into Ollama (`/api/pull`) |
| DELETE | `/api/v1/models/{name}` | Remove a model from Ollama (`/api/delete`) |

**`GET /api/v1/models/pulled` response:**
```json
[
    {
        "name": "qwen2.5:7b",
        "size_bytes": 4700000000,
        "modified_at": "2026-02-20T10:30:00Z",
        "in_use": true,
        "used_by": ["neo", "nat", "bob"],
        "registry_spec": {
            "context_window": 32768,
            "default_max_completion": 4096
        }
    }
]
```

The `in_use` and `used_by` fields are computed by cross-referencing pulled models with the active squad profile's agent model assignments. `registry_spec` is included if the model exists in the internal registry, `null` otherwise.

**`POST /api/v1/models/pull` request:**
```json
{
    "name": "qwen2.5:14b"
}
```

Pull is a long-running operation. V1 behavior:
1. Runtime-api spawns a background task that calls Ollama `POST /api/pull` with `stream: false` (blocking).
2. Returns `202 Accepted` immediately with a `pull_id` and poll URL.
3. Console polls `GET /api/v1/models/pull/{pull_id}/status` until complete.
4. On completion, the model appears in `GET /api/v1/models/pulled`.

**Pull job state:** V1 tracks pull jobs in an in-memory dict keyed by `pull_id`. If runtime-api restarts during a pull, the pull status is lost and the job shows as `unknown`. This is acceptable for V1 --- the operator can re-pull (Ollama handles idempotent pulls). A future revision may persist pull jobs to Postgres for durability.

### 5.5 Config Overrides Wiring

Currently, `config_overrides` from `AgentProfileEntry` is serialized in the squad profile snapshot but never read during execution. The wiring gap:

```
Squad Profile -> Cycle (squad_profile_snapshot_ref) -> Run -> Executor -> Handler -> chat()
                                                              ^
                                                     config_overrides not resolved here
```

**Fix:** The executor, when dispatching a task to an agent, resolves the agent's `config_overrides` from the squad profile snapshot and merges them into the task's execution context. The handler reads these overrides and passes them to `chat()`:

```python
# In handler, before chat() call:
overrides = task_context.get("config_overrides", {})
response = await self._llm.chat(
    messages=messages,
    model=model,
    temperature=overrides.get("temperature"),
    max_tokens=overrides.get("max_completion_tokens"),
    timeout_seconds=overrides.get("timeout_seconds"),
)
```

**Precedence (lowest to highest):**
1. Model defaults (from model registry)
2. Capability defaults (from `DevelopmentCapability`)
3. Squad profile `config_overrides` (from `AgentProfileEntry`)
4. Cycle-level `applied_defaults` (from cycle request profile)

Higher layers override lower. This means a cycle request profile can override a squad profile's temperature for a specific run.

#### 5.5.1 Allowed Override Keys

V1 restricts `config_overrides` to keys that map directly to LLM call parameters:

| Key | Type | Description |
|-----|------|-------------|
| `temperature` | float | Sampling temperature (0.0 - 2.0) |
| `max_completion_tokens` | int | Maximum completion tokens |
| `timeout_seconds` | float | Per-call timeout in seconds |

Squad profile `config_overrides` do **not** override:
- Handler-specific prompt construction or system prompts
- Guardrail logic (prompt guard, truncation)
- Role or capability selection
- Non-LLM execution parameters (test timeouts, build strategies)

Unknown keys in `config_overrides` are rejected at the API level with a 422 validation error. This prevents `config_overrides` from becoming a shadow configuration system.

### 5.6 Experiment Comparison View

A lightweight comparison tab that lets the operator select two completed cycles and see:

| Column | Cycle A | Cycle B |
|--------|---------|---------|
| Squad Profile | full-squad-7b | full-squad-14b |
| neo model | qwen2.5:7b | qwen2.5:14b |
| eve model | qwen2.5:3b | qwen2.5:7b |
| Artifacts (docs) | 2 | 2 |
| Artifacts (code) | 2 | 2 |
| Artifacts (tests) | 1 | 1 |
| Total tokens | 12,450 | 28,300 |
| Duration | 4m 12s | 8m 45s |
| Status | completed | completed |

**Data sources:**
- Squad profile snapshot from the cycle record
- Artifact count broken down by type (`documentation`, `source`, `test`, `other`) from the artifact vault
- Token usage from LangFuse (via existing `GET /api/v1/cycles/{id}` or a new summary endpoint)
- Duration from run `started_at` / `finished_at`

**LangFuse degradation:** If LangFuse is unreachable or token usage data is unavailable for a cycle, the token columns show `N/A`. The comparison view still works for all other columns (profile, models, artifacts, duration). The Compare tab does not depend on LangFuse availability.

**V1 scope:** read-only comparison of two cycles. No statistical analysis, no charts. Just a clear side-by-side table with artifact breakdown by type.

### 5.7 CLI Parity

| Command | Status | Description |
|---------|--------|-------------|
| `squadops squad-profiles list` | Existing | List squad profiles |
| `squadops squad-profiles show <id>` | Existing | Show profile with agent details |
| `squadops squad-profiles active` | Existing | Show active profile |
| `squadops squad-profiles create --file <yaml>` | **New** | Import profile from YAML definition |
| `squadops squad-profiles clone <id> --name <name>` | **New** | Clone existing profile |
| `squadops squad-profiles activate <id>` | **New** | Set profile as active (replaces `set-active`) |
| `squadops squad-profiles delete <id>` | **New** | Delete profile |
| `squadops models pulled` | **New** | List pulled Ollama models |
| `squadops models pull <name>` | **New** | Pull a model into Ollama |
| `squadops models remove <name>` | **New** | Remove a model from Ollama |

Note: `squadops request-profiles` is already used for cycle request profiles (SIP-0074). `squad-profiles` is already registered as a CLI command group with `list`, `show`, and `active` subcommands. This SIP extends it with `create`, `clone`, `activate`, and `delete`.

The `create --file` flag frames YAML as an import path, not the primary authoring surface. Profiles created via `--file`, the console UI, or the API are all first-class Postgres records thereafter. YAML is seed/import, not the runtime source of truth.

---

## 6. Phasing

### Phase 1: Squad Profile Persistence + CRUD API
- DDL migration for `squad_profiles` and `squad_profiles_seed_log` tables
- YAML seed logic at startup (insert-if-absent, respecting seed log for deleted profiles)
- CRUD endpoints (list, get, create, update, clone, delete, activate)
- Activation atomicity: single transaction deactivates old + activates new
- Profile ID generation (slugified from name, immutable after creation)
- Warning transport for unpulled model references
- Port interface for squad profile storage
- Postgres adapter implementation
- CLI commands: `squad-profiles create/clone/activate/delete`
- Tests: API routes, persistence, seed logic, seed-log deletion permanence, activation atomicity, CLI

### Phase 2: Model Management API
- Ollama proxy endpoints (list pulled, pull, remove)
- `in_use` / `used_by` cross-reference with active profile
- `registry_spec` merge: pulled models enriched with internal registry specs where available
- Pull job tracking (in-memory dict, `pull_id` keyed)
- Pull status polling endpoint
- CLI commands: `models pulled/pull/remove`
- Tests: proxy endpoints, cross-reference logic, pull job lifecycle, CLI

### Phase 3: Config Overrides Wiring
- Executor resolves `config_overrides` from squad profile snapshot
- Merge into task execution context
- Handlers read overrides and pass to `chat()`
- Precedence: model defaults < capability < config_overrides < applied_defaults
- Allowed key validation (temperature, max_completion_tokens, timeout_seconds)
- Tests: override resolution, precedence, unknown key rejection, handler integration

### Phase 4: Console Perspective
- New `squadops.squad` plugin with perspective registration
- Agent Health tab (enhanced `AgentsStatus` with "Configured Model" column from active profile)
- Squad Profiles tab (CRUD forms, agent/model editor, activate button, warning banners)
- Models tab (pulled models browser with registry specs, pull new model form, in-use indicators)
- Compare tab (cycle selector, side-by-side table with artifact type breakdown, LangFuse graceful degradation)
- Tests: component rendering (as applicable to Svelte custom elements)

---

## 7. Data Flow

### Squad Profile CRUD
```
Console / CLI           Runtime API              Postgres
     |                       |                       |
     | POST /squad-profiles  |                       |
     |---------------------->| INSERT INTO            |
     |                       | squad_profiles         |
     |                       |----------------------->|
     |                       |<-- row -               |
     |<-- profile response --|                       |
     |    + warnings[]       |                       |
```

### Model Pull
```
Console / CLI           Runtime API              Ollama
     |                       |                       |
     | POST /models/pull     |                       |
     |  {"name":"qwen:14b"}  |                       |
     |---------------------->| spawn background task  |
     |<-- 202 {pull_id}      |  POST /api/pull        |
     |                       |----------------------->|
     | (poll status)         |                       |
     |---------------------->| check in-memory map    |
     |<-- {status: pulling}  |                       |
     |   ...                 |   ...                  |
     |<-- {status: complete} |                       |
```

### Config Overrides Flow
```
Squad Profile Snapshot
     |
     | agents[i].config_overrides = {temperature: 0.3}
     v
Executor (resolves per-agent overrides)
     |
     | task_context.config_overrides = {temperature: 0.3}
     v
Handler (reads overrides before chat())
     |
     | chat(temperature=0.3, ...)
     v
OllamaAdapter -> Ollama
```

### Active Profile Activation
```
Runtime API              Postgres
     |                       |
     | BEGIN                  |
     | UPDATE SET is_active=FALSE WHERE is_active=TRUE
     |---------------------->|
     | UPDATE SET is_active=TRUE WHERE profile_id=$1
     |---------------------->|
     | COMMIT                |
     |---------------------->|
     |                       |
     | (if COMMIT fails, previous active profile unchanged)
```

---

## 8. Acceptance Criteria

### Happy Path
- **AC-1**: Operator can create a new squad profile from the console with agent/model assignments.
- **AC-2**: Operator can clone an existing profile, change a model assignment, and set it as active.
- **AC-3**: Operator can browse pulled Ollama models and see which are in use by the active profile.
- **AC-4**: Operator can pull a new model from the console without SSH or container access.
- **AC-5**: Setting `config_overrides.temperature: 0.1` in a squad profile causes the agent's LLM calls to use temperature 0.1 in the next cycle.
- **AC-6**: Operator can compare two completed cycles side-by-side showing profile, models, artifacts (by type), and token usage.
- **AC-7**: All CRUD operations are available via both the console and CLI.
- **AC-8**: YAML-defined profiles are seeded into Postgres on first startup and remain editable via the API thereafter.

### Negative Path
- **AC-9**: Deleting the active profile is rejected with a clear error message.
- **AC-10**: Creating a profile that references a non-existent `agent_id` (not in `instances.yaml`) is rejected.
- **AC-11**: Pulling a model that doesn't exist in the Ollama registry returns an error from Ollama, surfaced in the console.
- **AC-12**: `config_overrides` with unknown keys are rejected at the API level with a 422 validation error listing the invalid keys.
- **AC-13**: If Ollama is unreachable, the Models tab shows "Ollama unavailable" and the Agent Health tab still works (it doesn't depend on Ollama).
- **AC-14**: A YAML-seeded profile that is deleted via the API does not reappear after runtime-api restart.
- **AC-15**: Activating a profile atomically switches the active flag --- there is no transient state where zero or two profiles are active.
- **AC-16**: If LangFuse is unavailable, the Compare tab shows `N/A` for token usage but still displays profile, model, artifact, and duration data.
- **AC-17**: Creating a profile with a model not yet pulled in Ollama succeeds with a warning in the response body, surfaced in the console as a dismissible banner.

---

## 9. Migration & Backward Compatibility

- **No breaking changes.** Existing YAML-based profile loading continues to work. YAML files are treated as seed data for Postgres.
- **Existing cycle creation is unaffected.** The `squad_profile_id` in `CycleCreateRequest` resolves against Postgres instead of (or in addition to) the in-memory YAML cache.
- **Existing CLI commands are unchanged.** The `squad-profiles` command group already exists with `list`, `show`, and `active` subcommands. New subcommands (`create`, `clone`, `activate`, `delete`) extend it. The `request-profiles` command group (cycle request profiles) is unaffected.
- **`config_overrides` wiring is additive.** Profiles without `config_overrides` continue to work identically --- the override dict is empty, so no parameters are overridden.
- **Active profile is a default, not a switch.** Changing the active profile does not mutate already-created cycles. Each cycle retains its own `squad_profile_id` and snapshot from creation time.

---

## 10. Future Considerations

- **Ollama library browser** --- show all available models from the Ollama registry (not just pulled ones), with size estimates and descriptions, so operators can discover models without leaving the console.
- **Profile templates** --- pre-built profiles for common experiment patterns (e.g., "all 3b for fast iteration", "all 14b for quality runs", "mixed for cost optimization").
- **A/B profile runs** --- create two cycles from the same PRD with different profiles in a single action, auto-generating the comparison.
- **Cost estimation** --- before running a cycle, show estimated token cost based on profile models and historical usage patterns.
- **Container lifecycle** --- if security concerns are addressed, expose start/stop/restart for agent containers. Requires a separate SIP for Docker socket access policy.
- **Multi-Ollama routing** --- assign different agents to different Ollama instances (e.g., GPU server for large models, CPU for small ones).
- **Profile diff view** --- visual diff between two profiles showing what changed (model swaps, parameter changes, agent additions/removals).
- **"Last Used Model" in Agent Health** --- show the model an agent actually used in its most recent cycle, alongside the configured model from the active profile.
- **Persistent pull job tracking** --- move pull job state from in-memory to Postgres for durability across runtime-api restarts.
