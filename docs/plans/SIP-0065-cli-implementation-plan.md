# SIP-0065: CLI for Cycle Execution + CycleRequestProfiles — Implementation Plan

## Context

SIP-0065 (accepted) adds a Typer-based CLI (`squadops`) and CycleRequestProfiles (CRP) contract packs to SquadOps v0.9.4. The CLI is the first real consumer of the SIP-0064 API surface, operating against the runtime-api (port 8001). CRP provides defaults and interactive prompts for Cycle creation.

SIP spec: `sips/accepted/SIP-0065-CLI-for-Cycle-Execution.md`
Depends on: SIP-0064 (Cycle Execution API Foundation, implemented in v0.9.3)

---

## Key Discoveries from Exploration

1. **Runtime-API health endpoint** (`GET /health` on port 8001) returns `{"status": "healthy", "service": "runtime-api", "version": "0.9.3"}`. The `squadops status` command should use this, NOT `/health/infra` (which is on the health-check service, port 8000). The SIP references `/health/infra` — we'll use `/health` instead since CLI talks to runtime-api.

2. **`applied_defaults` gap** — The server's `create_cycle` route (line 64 of `cycles.py`) currently sets `applied_defaults = {}` as a placeholder. The CLI will be the first client to actually populate this field from CRP defaults.

3. **`CycleCreateRequest` DTO** does NOT have an `applied_defaults` field — defaults are set server-side as `{}`. The CLI must send `applied_defaults` as part of the request body, which means **we need to add `applied_defaults` to `CycleCreateRequest`** in the server DTO.

4. **Artifact ingest** uses `multipart/form-data` with fields: `file` (UploadFile), `artifact_type` (Form), `filename` (Form), `media_type` (Form). CLI must use `httpx` multipart upload matching this exactly.

5. **`compute_config_hash()`** in `src/squadops/cycles/lifecycle.py` uses `json.dumps(obj, sort_keys=True, separators=(",", ":"))` — the CLI must import and reuse this function directly (not reimplement).

6. **Baseline endpoints** use slightly different URL pattern than SIP-0065 spec: actual is `POST /projects/{id}/baseline/{type}` (singular), not `baselines` (plural). CLI must match.

---

## Decisions (binding for implementation)

**D1) Sync httpx, not async.** Typer command handlers are synchronous. The CLI uses `httpx.Client` (sync), not `httpx.AsyncClient`. No `asyncio.run()` wrappers. This simplifies every command handler and all tests.

**D2) `applied_defaults` DTO is a hard prerequisite.** Before Phase 3, `CycleCreateRequest` must accept `applied_defaults: dict = Field(default_factory=dict)`. The default `{}` preserves backward compatibility for non-CLI clients. The server uses `body.applied_defaults` (not a hardcoded `{}`).

**D3) `squadops status` targets runtime-api `/health` (port 8001).** Not the health-check service `/health/infra` (port 8000). The existing `GET /health` endpoint already returns `{"status": "healthy", "service": "runtime-api", "version": "..."}`. No new endpoint needed.

**D4) Auth input hierarchy:** CLI flag (`--token`) > env var (`$SQUADOPS_TOKEN`) > config file (`config.toml [auth].token_env`). Each layer overrides the one below.

**D5) Verb consistency across all command groups.** Canonical verbs: `list`, `show`, `create`, `cancel`, `get`, `set`. Aliases: `ls` → `list`, `cat` → `show`. No mixed vocabulary.

**D6) Records-only scope in help text.** Commands that sound like they "do something" (`cycles create`, `runs retry`) must include explicit help text: *"Creates an experiment record. Does not trigger task execution (deferred to a future release)."*

**D7) Global flags flow via `typer.Context.obj`.** The `@app.callback()` stores `--format`, `--json`, `--quiet` in a shared dict on `ctx.obj`. All commands access flags via `ctx.obj["format"]`, etc. Output helpers and the client factory read from this dict — commands never parse globals themselves. If `--json` is set, it forces `format="json"` regardless of `--format` value (precedence rule).

**D8) Gate decision wire vocabulary: past tense.** CLI flags are imperative (`--approve`, `--reject`). The wire payload uses past tense (`"approved"`, `"rejected"`) to match `GateDecisionValue` enum and `GateDecisionRequest` DTO (`decision: Literal["approved", "rejected"]`). The CLI maps `--approve → "approved"`, `--reject → "rejected"` before sending. Tests assert the exact JSON `{"decision": "approved", "notes": ...}`.

**D9) CRP can safely import `CycleCreateRequest`.** `dtos.py` imports only stdlib + Pydantic (no FastAPI). Zero circular import risk — nothing in `api/routes/cycles/` imports from `contracts/`. The CRP validator uses `CycleCreateRequest.model_fields.keys()` to enforce known-key constraints at profile load time.

**D10) `APIClient` accepts injected `httpx.Client` for testability.** Constructor signature: `APIClient(config, client: httpx.Client | None = None)`. Production: client is created internally. Integration tests: inject `starlette.testclient.TestClient(app=fastapi_app)` (which IS a sync `httpx.Client` subclass). This avoids async/sync mismatch — `httpx.ASGITransport` is async-only, but `TestClient` handles the ASGI bridge internally.

---

## Phase 1: CycleRequestProfiles (CRP) Contract Pack

CRP is a value-object contract pack — not a domain entity, not an API resource. It ships with the CLI under `src/squadops/contracts/`.

### 1.1 CRP Schema — `src/squadops/contracts/cycle_request_profiles/schema.py` (NEW)

Pydantic model for validating CRP YAML profiles:

```python
class PromptMeta(BaseModel):
    label: str
    help_text: str = ""
    choices: list[str] = Field(default_factory=list)

class CycleRequestProfile(BaseModel):
    name: str               # Profile display name
    description: str = ""
    defaults: dict = Field(default_factory=dict)
    prompts: dict[str, PromptMeta] = Field(default_factory=dict)

    @validator("defaults")
    def validate_known_keys(cls, v):
        # Fail fast if defaults contain keys not in CycleCreateRequest
        allowed = set(CycleCreateRequest.model_fields.keys())
        unknown = set(v.keys()) - allowed
        if unknown:
            raise ValueError(f"Unknown default keys: {unknown}")
        return v
```

This validator ensures CRP profiles stay in sync with the server DTO. When fields are added/removed from `CycleCreateRequest`, stale profiles fail loudly at load time. Import is safe (D9): `dtos.py` depends only on stdlib + Pydantic, no FastAPI, no circular risk.

### 1.2 CRP Loader — `src/squadops/contracts/cycle_request_profiles/__init__.py` (NEW)

```python
def load_profile(name: str = "default") -> CycleRequestProfile: ...
def list_profiles() -> list[str]: ...
def compute_overrides(defaults: dict, user_values: dict) -> dict: ...
    # Returns ONLY fields where user_values differ from defaults (§5.3 critical rule)
def merge_config(defaults: dict, overrides: dict) -> dict: ...
    # Single canonical merge: {**defaults, **overrides}
    # Used by CRP logic, request building, AND tests — prevents divergence
```

`merge_config()` is the single named helper for the merge rule. The CLI, CRP logic, and tests all call this — never inline `{**d, **o}`. This matches `compute_config_hash()` in `lifecycle.py` which does the same merge internally.

Profiles loaded from `src/squadops/contracts/cycle_request_profiles/profiles/*.yaml` using `importlib.resources` for package-safe path resolution.

### 1.3 CRP Profile YAML Files (NEW)

- `profiles/default.yaml` — Standard defaults (build_strategy=fresh, mode=sequential, etc.)
- `profiles/benchmark.yaml` — Benchmark defaults (expected_artifact_types includes metrics)
- `profiles/selftest.yaml` — Self-test defaults (hello_squad project, minimal config)

Defaults must use the same field names as `CycleCreateRequest` DTO.

### 1.4 Unit Tests — `tests/unit/contracts/` (NEW)

~15 tests:
- All bundled profiles load and validate against schema
- `list_profiles()` returns ["default", "benchmark", "selftest"]
- `load_profile("default")` returns valid CycleRequestProfile
- `load_profile("nonexistent")` raises FileNotFoundError
- `compute_overrides()` returns empty dict when user values match defaults
- `compute_overrides()` returns only changed fields
- `compute_overrides()` does NOT include fields equal to defaults (§5.3 bidirectional rule)
- Golden hash test: `compute_config_hash(defaults, compute_overrides(defaults, user_values))` is deterministic
- Profile with unknown default key fails validation at load time
- `merge_config()` used consistently (no inline `{**d, **o}`)

### 1.5 Phase 1 Exit Criteria

- [ ] CRP schema validates all bundled profiles
- [ ] Loader resolves profiles by name from package resources
- [ ] Override diff computation follows §5.3 critical rule exactly
- [ ] ~15 tests passing

---

## Phase 2: CLI Infrastructure (config, client, output, exit codes)

### 2.1 Exit Codes — `src/squadops/cli/exit_codes.py` (NEW)

Constants matching SIP-0065 §6.6:

```python
SUCCESS = 0
GENERAL_ERROR = 1
VALIDATION_ERROR = 10   # API 422
AUTH_ERROR = 11          # API 401/403
NOT_FOUND = 12           # API 404
CONFLICT = 13            # API 409
NETWORK_ERROR = 20       # Unreachable/timeout
```

### 2.2 Config — `src/squadops/cli/config.py` (NEW)

Loads `~/.config/squadops/config.toml` (or `$XDG_CONFIG_HOME/squadops/config.toml`):

```python
@dataclass
class CLIConfig:
    base_url: str = "http://localhost:8001"
    timeout: int = 30
    auth_mode: str = "token"       # "token" only in v0.9.4
    token_env: str = "SQUADOPS_TOKEN"
    output_format: str = "table"   # "table" | "json"
    tls_verify: bool = True        # TLS cert verification (disable with --no-tls-verify for dev only)

def load_config() -> CLIConfig: ...
    # Falls back to defaults if no config file exists
```

Uses `tomllib` (stdlib in 3.11+). No external dependency needed.

**Auth input hierarchy** (D4): CLI flag > env var > config file. Resolution order:
1. `--token <value>` flag (highest priority)
2. `$SQUADOPS_TOKEN` env var (or whatever `config.token_env` specifies)
3. `config.toml [auth].token_env` (lowest priority, just names the env var)

If no token is found at any level, requests are sent without `Authorization` header (server decides whether to reject).

### 2.3 API Client — `src/squadops/cli/client.py` (NEW)

Thin **synchronous** `httpx.Client` wrapper (D1) with error-to-exit-code mapping:

```python
class APIClient:
    def __init__(self, config: CLIConfig, client: httpx.Client | None = None): ...
        # D10: accepts optional injected client for testability
        # Production: creates httpx.Client with:
        #   base_url=config.base_url
        #   timeout=config.timeout
        #   verify=config.tls_verify
        #   headers={"User-Agent": f"squadops-cli/{__version__}"}
        #   + Authorization header if token resolved via D4 hierarchy
        # Tests: inject starlette.testclient.TestClient(app=fastapi_app)
        #   (TestClient is a sync httpx.Client subclass — handles ASGI bridge)

    # All methods are synchronous — no async, no asyncio.run()
    def get(self, path: str) -> dict: ...
    def post(self, path: str, json: dict | None = None) -> dict: ...
    def upload(self, path: str, file_path: Path, fields: dict) -> dict: ...
    def download(self, path: str) -> tuple[bytes, str]: ...  # (content, filename)

class CLIError(Exception):
    def __init__(self, message: str, exit_code: int, detail: dict | None = None): ...
```

**Error-to-exit-code mapping:**

| Condition | Exit code | stderr output |
|-----------|-----------|---------------|
| `httpx.ConnectError` | 20 | `Error: cannot reach {base_url} — connection refused` |
| `httpx.TimeoutException` | 20 | `Error: request to {base_url} timed out after {timeout}s` |
| HTTP 401/403 | 11 | `Error: authentication failed — {error.message}` |
| HTTP 404 | 12 | `Error: not found — {error.message}` |
| HTTP 409 | 13 | `Error: conflict — {error.message}` |
| HTTP 422 | 10 | `Error: validation failed — {error.message}` + `details` if present |
| HTTP 413 | 10 | `Error: file too large (max 50 MB)` |
| JSON parse failure | 1 | `Error: unexpected response (HTTP {status}) — {first 200 chars}` |

If the API response includes a `request_id` header (from `RequestIDMiddleware`), append it to stderr output for correlation.

Auth: resolved per D4 hierarchy. `User-Agent: squadops-cli/{version}` header included on all requests for server-side observability.

### 2.4 Output — `src/squadops/cli/output.py` (NEW)

```python
def print_table(headers: list[str], rows: list[list[str]], *, quiet: bool = False) -> None: ...
def print_detail(data: dict, *, quiet: bool = False) -> None: ...
def print_json(data: Any) -> None: ...
def print_error(message: str) -> None: ...
def print_success(message: str) -> None: ...
```

Uses `rich.table.Table` for table output, `rich.console.Console` for styled output. When `quiet=True`, prints raw tab-separated values (no chrome).

### 2.5 Unit Tests — `tests/unit/cli/test_config.py`, `test_exit_codes.py`, `test_output.py`, `test_client.py` (NEW)

~30 tests:
- Config loads from TOML file
- Config falls back to defaults when no file exists
- Config respects `$XDG_CONFIG_HOME`
- Config auth hierarchy: flag overrides env var overrides config file (D4)
- Exit code constants match SIP-0065 §6.6
- API client is synchronous (`httpx.Client`, not `AsyncClient`)
- API client maps HTTP status codes to correct exit codes
- API client handles network errors (connect timeout, DNS failure)
- API client sends auth header when token resolved
- API client omits auth header when no token at any level
- API client includes `User-Agent: squadops-cli/{version}` header
- API client respects `tls_verify=False` for dev
- API client stderr: structured error → shows message + request_id
- API client stderr: timeout → shows base_url + timeout value
- API client stderr: JSON parse failure → shows status + raw snippet
- API client accepts injected httpx.Client (D10) — uses it instead of creating one
- API client with no injected client creates its own httpx.Client
- Global flags: `--json` sets ctx.obj["format"] = "json" even when `--format table` (D7)
- Global flags: ctx.obj["quiet"] propagates to commands
- Output: table formatting produces expected output
- Output: JSON formatting produces valid JSON
- Output: quiet mode suppresses table chrome

### 2.6 Phase 2 Exit Criteria

- [ ] Config loads from TOML with defaults fallback
- [ ] API client handles all error categories with correct exit codes
- [ ] Output module supports table, JSON, and quiet modes
- [ ] ~25 tests passing

---

## Phase 3: CLI Commands

### 3.1 Main App — `src/squadops/cli/main.py` (NEW)

```python
import typer

app = typer.Typer(name="squadops", help="SquadOps CLI for cycle execution management")

# Global options callback — stores flags in ctx.obj (D7)
@app.callback()
def main(
    ctx: typer.Context,
    format: str = typer.Option("table", "--format", help="Output format: table|json"),
    json_flag: bool = typer.Option(False, "--json", help="Shorthand for --format json"),
    quiet: bool = typer.Option(False, "--quiet", help="Minimal output for scripting"),
):
    ctx.ensure_object(dict)
    ctx.obj["format"] = "json" if json_flag else format  # --json wins (D7)
    ctx.obj["quiet"] = quiet

# Commands read flags via ctx.obj:
#   ctx = typer.Context  (injected by Typer)
#   fmt = ctx.obj["format"]
#   quiet = ctx.obj["quiet"]
# Output helpers accept these as params — commands are thin dispatch.

# Register command groups
app.add_typer(projects_app, name="projects")
app.add_typer(cycles_app, name="cycles")
app.add_typer(runs_app, name="runs")
app.add_typer(profiles_app, name="squad-profiles")
app.add_typer(artifacts_app, name="artifacts")
app.add_typer(baseline_app, name="baseline")
```

### 3.2 Meta Commands — `src/squadops/cli/commands/meta.py` (NEW)

```python
@app.command()
def version():
    """Show CLI version."""
    # Imports squadops.__version__ — local only, no server call

@app.command()
def status():
    """Check API connectivity."""
    # Hits GET /health on runtime-api (port 8001)
    # Reports: reachable/unreachable, response time, server version from response
```

Note: `GET /health` on runtime-api returns `{"status": "healthy", "service": "runtime-api", "version": "0.9.3"}` so we CAN report server version without a new endpoint.

### 3.3 Project Commands — `src/squadops/cli/commands/projects.py` (NEW)

```
squadops projects list          → GET /api/v1/projects
squadops projects show <id>     → GET /api/v1/projects/{id}
```

Aliases: `ls` for `list`, `cat` for `show`.

### 3.4 Cycle Commands — `src/squadops/cli/commands/cycles.py` (NEW)

```
squadops cycles create <project_id> [--profile <name>] [--set key=value ...] [--prd <id>] [--notes "..."]
    → Loads CRP profile, computes overrides, POST /api/v1/projects/{id}/cycles

squadops cycles list <project_id> [--status ...]
    → GET /api/v1/projects/{id}/cycles?status=...

squadops cycles show <project_id> <cycle_id>
    → GET /api/v1/projects/{id}/cycles/{cycle_id}

squadops cycles cancel <project_id> <cycle_id>
    → POST /api/v1/projects/{id}/cycles/{cycle_id}/cancel
```

Help text for `create` and `retry` must include records-only disclaimer (D6): *"Creates an experiment record. Does not trigger task execution (deferred to a future release)."*

The `create` command is the most complex:
1. Load CRP profile (default or `--profile <name>`)
2. Parse `--set key=value` flags into user_values dict
3. Merge CRP defaults with user_values
4. Compute overrides via `compute_overrides(defaults, merged)`
5. Compute local hash via `compute_config_hash(defaults, overrides)`
6. POST to API with `applied_defaults`, `execution_overrides`, and other fields
7. Verify `response.resolved_config_hash == local_hash` (log warning if mismatch)

### 3.5 Run Commands — `src/squadops/cli/commands/runs.py` (NEW)

```
squadops runs list <project_id> <cycle_id>
    → GET /api/v1/projects/{id}/cycles/{cycle_id}/runs

squadops runs show <project_id> <cycle_id> <run_id>
    → GET /api/v1/projects/{id}/cycles/{cycle_id}/runs/{run_id}

squadops runs retry <project_id> <cycle_id>
    → POST /api/v1/projects/{id}/cycles/{cycle_id}/runs

squadops runs cancel <project_id> <cycle_id> <run_id>
    → POST /api/v1/projects/{id}/cycles/{cycle_id}/runs/{run_id}/cancel

squadops runs gate <project_id> <cycle_id> <run_id> <gate_name> --approve|--reject [--notes "..."]
    → POST /api/v1/projects/{id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}
    → Wire mapping (D8): --approve → {"decision": "approved", "notes": ...}
                          --reject  → {"decision": "rejected", "notes": ...}
    → Matches GateDecisionRequest DTO: decision: Literal["approved", "rejected"]
```

### 3.6 Profile Commands — `src/squadops/cli/commands/profiles.py` (NEW)

```
squadops squad-profiles list     → GET /api/v1/squad-profiles
squadops squad-profiles show <id> → GET /api/v1/squad-profiles/{id}
squadops squad-profiles active   → GET /api/v1/squad-profiles/active
squadops squad-profiles set-active <id> → POST /api/v1/squad-profiles/active
```

### 3.7 Artifact Commands — `src/squadops/cli/commands/artifacts.py` (NEW)

```
squadops artifacts ingest --project <id> --type <type> --file <path>
    → POST /api/v1/projects/{id}/artifacts/ingest (multipart/form-data)
    → Fields: file (binary), artifact_type (form), filename (form), media_type (form)
    → media_type inferred from file extension via mimetypes.guess_type()

squadops artifacts get <artifact_id>
    → GET /api/v1/artifacts/{id}

squadops artifacts download <artifact_id> --out <path>
    → GET /api/v1/artifacts/{id}/download

squadops artifacts list --project <id> [--cycle <cycle_id>] [--type <type>]
    → Selection rule: if --cycle provided → GET /api/v1/projects/{id}/cycles/{cycle_id}/artifacts
                      else               → GET /api/v1/projects/{id}/artifacts?artifact_type=<type>
    → Both endpoints exist. --type filter only applies to project-scoped endpoint.
```

### 3.8 Baseline Commands — `src/squadops/cli/commands/artifacts.py` (same file)

```
squadops baseline set <project_id> <artifact_type> <artifact_id>
    → POST /api/v1/projects/{id}/baseline/{type}

squadops baseline get <project_id> <artifact_type>
    → GET /api/v1/projects/{id}/baseline/{type}

squadops baseline list <project_id>
    → GET /api/v1/projects/{id}/baseline
    → Returns dict keyed by artifact_type → ArtifactResponse
```

Note: baseline routes use singular `baseline` (not `baselines`) — matches actual server routes. All three baseline endpoints confirmed to exist in `artifacts.py`.

### 3.9 Command Aliases

Register `ls` and `cat` aliases for `list` and `show` subcommands in each command group via Typer's `rich_help_panel` or by registering duplicate commands.

### 3.10 Server-Side DTO Change

**`src/squadops/api/routes/cycles/dtos.py`** — Add `applied_defaults` to `CycleCreateRequest`:

```python
class CycleCreateRequest(BaseModel):
    applied_defaults: dict = Field(default_factory=dict)  # NEW: CRP defaults from CLI
    # ... existing fields unchanged
```

**`src/squadops/api/routes/cycles/cycles.py`** — Use `body.applied_defaults` instead of hardcoded `{}`:

```python
applied_defaults = body.applied_defaults  # Was: applied_defaults = {}
```

### 3.11 Unit Tests — `tests/unit/cli/test_commands_*.py` (NEW)

~40 tests using `typer.testing.CliRunner`:

**test_commands_meta.py** (~4 tests):
- `version` prints version string
- `status` with reachable server shows "connected"
- `status` with unreachable server shows "unreachable" and exits 20

**test_commands_projects.py** (~5 tests):
- `projects list` displays table
- `projects list --json` outputs valid JSON
- `projects show <id>` displays detail
- `projects show unknown` exits 12

**test_commands_cycles.py** (~12 tests):
- `cycles create` with default profile sends correct request body
- `cycles create --profile benchmark` uses benchmark defaults
- `cycles create --set build_strategy=incremental` puts override in execution_overrides
- `cycles create` hash round-trip: local hash matches response hash
- `cycles list` displays table with status column
- `cycles list --status active` sends query param
- `cycles show` displays cycle detail with runs
- `cycles cancel` sends cancel request
- `cycles create` with unknown project exits 12

**test_commands_runs.py** (~8 tests):
- `runs list` displays table
- `runs show` displays run detail
- `runs retry` creates new run
- `runs cancel` sends cancel request
- `runs gate --approve` sends JSON `{"decision": "approved"}` (D8 wire mapping)
- `runs gate --reject` sends JSON `{"decision": "rejected"}` (D8 wire mapping)
- `runs gate` without --approve or --reject exits 2 (usage error)
- `runs gate` on terminal run exits 13

**test_commands_profiles.py** (~4 tests):
- `squad-profiles list` displays table
- `squad-profiles active` displays active profile
- `squad-profiles set-active` sends request

**test_commands_artifacts.py** (~7 tests):
- `artifacts ingest` sends multipart upload with correct fields
- `artifacts get` displays metadata
- `artifacts download` saves file to --out path
- `artifacts list` displays table
- `baseline set` sends promote request
- `baseline get` displays baseline
- `baseline list` displays all baselines

### 3.12 Phase 3 Exit Criteria

- [ ] All 6 command groups registered and functional
- [ ] `cycles create` correctly applies CRP defaults and computes overrides
- [ ] Command aliases (`ls`/`cat`) work
- [ ] `--json`, `--quiet`, `--format` global flags work
- [ ] Server DTO accepts `applied_defaults` from CLI
- [ ] ~40 tests passing

---

## Phase 4: Packaging, Integration Tests, Regression

### 4.1 pyproject.toml Changes (MODIFY)

```toml
[project.scripts]
squadops = "squadops.cli.main:app"

[project.optional-dependencies]
langfuse = ["langfuse>=2.0"]
cli = ["typer>=0.9", "httpx>=0.25", "rich>=13.0"]
```

New test markers (MUST be registered — `--strict-markers` is enabled, unregistered markers cause collection errors):
```toml
# Add to [tool.pytest.ini_options] markers = [...] in pyproject.toml
"domain_cli: CLI domain tests",
"domain_contracts: Contract domain tests",
```

### 4.2 Package Init Files (NEW)

- `src/squadops/cli/__init__.py` — empty or re-exports `app`
- `src/squadops/cli/commands/__init__.py` — empty
- `src/squadops/contracts/__init__.py` — empty
- `src/squadops/contracts/cycle_request_profiles/__init__.py` — loader (see Phase 1)

### 4.3 Integration Tests — `tests/unit/cli/test_integration.py` (NEW)

~10 tests using Starlette `TestClient` against the FastAPI app with real in-memory adapters (no mocks, no network).

**Injection point (D10):** `APIClient(config, client=TestClient(app=fastapi_app))`. `starlette.testclient.TestClient` is a sync `httpx.Client` subclass that handles the ASGI bridge internally — no async/sync mismatch. Unit command tests use `typer.testing.CliRunner` with the `APIClient` patched to use the injected `TestClient`.

```python
# Integration test fixture pattern
from starlette.testclient import TestClient as StarletteTestClient
from squadops.api.runtime.main import app as fastapi_app

@pytest.fixture
def api_client(test_config):
    http_client = StarletteTestClient(fastapi_app, base_url="http://test")
    return APIClient(config=test_config, client=http_client)
```

Marked with `@pytest.mark.domain_cli` (registered in pyproject.toml, required by `--strict-markers`).

- Create cycle via CLI runner → GET via API → verify fields match
- `cycles create` with CRP defaults → verify `applied_defaults` stored on Cycle
- `cycles create --set key=value` → verify `execution_overrides` contains only changed fields
- Hash round-trip golden test (§8.4): CLI hash == server hash after create
- `artifacts ingest` via CLI → `artifacts get` → verify metadata matches
- `runs gate --approve` → verify gate decision stored
- Error code mapping: unknown project → exit 12, cancel terminal run → exit 13
- `--json` output is valid JSON and contains expected keys

### 4.4 CRP Contract Tests — `tests/unit/contracts/test_crp_contract.py` (NEW)

~5 tests:
- All bundled profiles produce valid `CycleCreateRequest` payloads
- Golden hash: `compute_config_hash(D, O)` from lifecycle matches CLI-computed hash
- Profile defaults don't contain unknown fields (validated against DTO)

### 4.5 Phase 4 Exit Criteria

- [ ] `pip install -e ".[cli]"` installs typer, httpx, rich
- [ ] `squadops --help` works after install
- [ ] Integration tests pass with real adapters
- [ ] Hash round-trip golden test passes
- [ ] `run_new_arch_tests.sh` passes (912+ existing + ~95 new tests)
- [ ] New markers registered in pyproject.toml

---

## Files Created/Modified Summary

| File | Action | Phase |
|------|--------|-------|
| `src/squadops/contracts/__init__.py` | NEW | 1 |
| `src/squadops/contracts/cycle_request_profiles/__init__.py` | NEW — loader | 1 |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | NEW — Pydantic model | 1 |
| `src/squadops/contracts/cycle_request_profiles/profiles/default.yaml` | NEW | 1 |
| `src/squadops/contracts/cycle_request_profiles/profiles/benchmark.yaml` | NEW | 1 |
| `src/squadops/contracts/cycle_request_profiles/profiles/selftest.yaml` | NEW | 1 |
| `tests/unit/contracts/__init__.py` | NEW | 1 |
| `tests/unit/contracts/test_crp.py` | NEW — ~15 tests | 1 |
| `src/squadops/cli/__init__.py` | NEW | 2 |
| `src/squadops/cli/exit_codes.py` | NEW | 2 |
| `src/squadops/cli/config.py` | NEW | 2 |
| `src/squadops/cli/client.py` | NEW | 2 |
| `src/squadops/cli/output.py` | NEW | 2 |
| `tests/unit/cli/__init__.py` | NEW | 2 |
| `tests/unit/cli/test_config.py` | NEW | 2 |
| `tests/unit/cli/test_exit_codes.py` | NEW | 2 |
| `tests/unit/cli/test_client.py` | NEW | 2 |
| `tests/unit/cli/test_output.py` | NEW | 2 |
| `src/squadops/cli/main.py` | NEW — Typer app | 3 |
| `src/squadops/cli/commands/__init__.py` | NEW | 3 |
| `src/squadops/cli/commands/meta.py` | NEW | 3 |
| `src/squadops/cli/commands/projects.py` | NEW | 3 |
| `src/squadops/cli/commands/cycles.py` | NEW | 3 |
| `src/squadops/cli/commands/runs.py` | NEW | 3 |
| `src/squadops/cli/commands/profiles.py` | NEW | 3 |
| `src/squadops/cli/commands/artifacts.py` | NEW — includes baseline | 3 |
| `src/squadops/api/routes/cycles/dtos.py` | MODIFY — add `applied_defaults` | 3 |
| `src/squadops/api/routes/cycles/cycles.py` | MODIFY — use `body.applied_defaults` | 3 |
| `tests/unit/cli/test_commands_meta.py` | NEW | 3 |
| `tests/unit/cli/test_commands_projects.py` | NEW | 3 |
| `tests/unit/cli/test_commands_cycles.py` | NEW | 3 |
| `tests/unit/cli/test_commands_runs.py` | NEW | 3 |
| `tests/unit/cli/test_commands_profiles.py` | NEW | 3 |
| `tests/unit/cli/test_commands_artifacts.py` | NEW | 3 |
| `pyproject.toml` | MODIFY — scripts, cli deps, markers | 4 |
| `tests/unit/cli/test_integration.py` | NEW — ~10 tests | 4 |
| `tests/unit/contracts/test_crp_contract.py` | NEW — ~5 tests | 4 |

**Total: ~32 new files, 3 modified files, ~105 new tests**

---

## Verification

### Phase 1
```bash
pytest tests/unit/contracts/ -v
```

### Phase 2
```bash
pytest tests/unit/cli/test_config.py tests/unit/cli/test_exit_codes.py tests/unit/cli/test_client.py tests/unit/cli/test_output.py -v
```

### Phase 3
```bash
pytest tests/unit/cli/test_commands_*.py -v
```

### Phase 4
```bash
pip install -e ".[cli]"
squadops --help
squadops version
pytest tests/unit/cli/ tests/unit/contracts/ -v
./scripts/dev/run_new_arch_tests.sh -v  # Full regression (912+ existing + ~95 new)
```
