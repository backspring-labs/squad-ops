---
title: CLI for Cycle Execution + CycleRequestProfiles
status: accepted
author: Jason Ladd
created_at: '2026-02-08T00:00:00Z'
original_filename: SIP_PROPOSAL_0_9_4_CLI_CYCLE_REQUEST_PROFILES.md
sip_number: 65
updated_at: '2026-02-10T00:38:51.316278Z'
---
# SIP-0065
## CLI for Cycle Execution and CycleRequestProfiles (CRP)

**Status:** Accepted
**Target Release:** SquadOps v0.9.4
**Scope:** CLI + request-shaping contracts (CycleRequestProfiles) aligned to SIP-0064 (Cycle/Run model)
**Impact:** Medium–High (new CLI entry point; new contract pack; no new API endpoints required)
**Depends On:** SIP-0064 (Cycle Execution API Foundation, implemented in v0.9.3)

---

## 1. Overview

SIP-0064 established the authoritative execution model: **Project → Cycle → Run → Tasks**, with Cycle as the experiment record and Run as an execution attempt. v0.9.4 adds:

1. A first-class **CLI** (`squadops`) to operate the SIP-0064 API surface.
2. **CycleRequestProfiles (CRP)** — platform-versioned, request-shaping contract packs that provide defaults and interactive prompts for Cycle creation.

The CLI is the first real consumer of the SIP-0064 API. Building it validates the API contract, catches ergonomic gaps, and gives operators immediate value before the control plane UI is built.

---

## 2. Decisions

### 2.1 CycleRequestProfiles are contracts, not entities

- CRP is a **value-object contract pack** used by the CLI to populate defaults and guide interactive prompts.
- CRP is **not** a domain entity, registry, or API resource. There is no `CRPRegistryPort`, no CRP API endpoints.
- CRP ships with the platform/CLI version. There is no independent CRP versioning.
- Cycle remains the **source of truth** for the experiment configuration.

### 2.2 Override Map as Source of Truth (Pattern A)

The CLI submits a minimal Cycle creation request containing:

- Required identity selections (`project_id`, `squad_profile_id`, `prd_ref` optional)
- `execution_overrides` as an explicit delta map of values the user changed from CRP defaults

The server does **not** need to know which CRP profile was used. The server stores:

- `applied_defaults` — the CRP defaults the CLI resolved (immutable per Cycle)
- `execution_overrides` — the explicit deltas the user chose (immutable per Cycle)
- `resolved_config_hash` — `SHA-256(canonical_json(merge(defaults, overrides)))` (per SIP-0064 T5)

This approach is explicit, avoids server-side diff logic, and aligns directly with the existing SIP-0064 Cycle model where `execution_overrides` is already a first-class field.

### 2.3 CLI ships within the existing package

The CLI is tightly coupled to the API domain (same models, same version). It ships as a `console_scripts` entry point in the existing `squadops` package, not as a separate distribution:

```toml
[project.scripts]
squadops = "squadops.cli.main:app"

[project.optional-dependencies]
cli = ["typer>=0.9", "httpx>=0.25", "rich>=13.0"]
```

The entry point resolves to the Typer `app` object in `src/squadops/cli/main.py`. Typer handles `console_scripts` dispatch natively — no wrapper `main()` function is needed.

Install for operators: `pip install squadops[cli]`

This avoids version sync issues between CLI and server packages. **Operators should install the `[cli]` extra in a separate virtualenv** — CLI dependencies (`typer`, `httpx`, `rich`) must not be injected into the server runtime where they are unnecessary.

### 2.4 CLI-authoritative CRP (no server endpoint)

The CLI bundles its own CRP pack. There is no `GET /api/v1/contracts/cycle-request-profiles` endpoint in v0.9.4. The CLI is authoritative for defaults and prompts.

Because `applied_defaults` is client-supplied, the server treats it as **untrusted metadata** — it is stored for analysis but never used to derive execution behavior. All execution parameters are determined by the merged config (`merge(applied_defaults, execution_overrides)`) which the server validates via its own Pydantic DTOs.

If a future version requires server-side CRP parity checking (e.g., multi-version environments), an optional read-only endpoint can be added then. For now, this is unnecessary complexity.

### 2.5 FlowExecutionPort scope: records-only in v0.9.4

The `InProcessFlowExecutor` remains a stub in v0.9.4. Actual task dispatch wiring is deferred to a future release. The CLI operates the **lifecycle record surface** only. Per command:

| Command | Record operation | Calls FlowExecutionPort? |
|---------|-----------------|--------------------------|
| `cycles create` | Creates Cycle + first Run records | No |
| `cycles cancel` | Sets CycleStatus → CANCELLED | No |
| `runs retry` | Creates new Run record | No |
| `runs cancel` | Sets RunStatus → CANCELLED | No |
| `runs gate` | Stores GateDecision on Run | No |
| `artifacts ingest` | Stores ArtifactRef + bytes | No |
| `baseline set` | Updates baseline pointer | No |

The CLI **cannot** (yet):
- Trigger actual task execution via FlowExecutionPort
- Monitor live task progress

This is explicitly documented in CLI help text and `--help` output.

---

## 3. Goals

- Provide an operator-friendly CLI for the full SIP-0064 API surface.
- Reduce request drift by using CRP packs for defaults and interactive prompts.
- Ensure overrides are trackable and comparable across cycles/runs.
- Enable "power-on self test" and benchmarking via built-in projects using the Cycle/Run model.
- Validate API ergonomics before building the control plane UI.

---

## 4. Non-Goals

- No new web UI / SOC control plane behavior (deferred to next SIP).
- No server-side CRP registry or API endpoints.
- No FlowExecutionPort wiring for task dispatch (stub remains).
- No Prefect execution adapter work.

---

## 5. CycleRequestProfiles (CRP)

### 5.1 What a CRP contains (v0.9.4 scope)

A CRP is a named YAML profile that guides Cycle creation. For v0.9.4, each CRP contains only:

- **`defaults`** — suggested values for defaultable Cycle fields (build_strategy, task_flow_policy, expected_artifact_types, etc.)
- **`prompts`** — optional CLI prompt metadata for interactive mode (field labels, help text, choices)

Deferred to future releases:
- `allowed_overrides` with shape constraints (the API's Pydantic DTOs already validate structure; a second constraint layer is premature)
- `required` field declarations (the API already enforces required fields)

### 5.2 Where CRP lives

CRP ships with the platform under a canonical path:

```
src/squadops/contracts/
    cycle_request_profiles/
        __init__.py           # Loader utilities
        schema.py             # Pydantic model for CRP validation
        profiles/
            default.yaml      # Standard defaults
            benchmark.yaml    # Benchmark-focused defaults
            selftest.yaml     # Power-on self-test defaults
```

### 5.3 How defaults vs overrides are computed (normative)

For `POST /api/v1/projects/{project_id}/cycles`:

1. Let `D` = the CRP defaults selected by the user (or `default.yaml` when none specified).
2. Let `R` = the CLI arguments and interactive prompt responses.
3. Compute `O` = the fields in `R` that differ from `D` (the explicit deltas).
4. CLI submits the Cycle creation request with:
   - `applied_defaults = D`
   - `execution_overrides = O`
   - Other required fields (`squad_profile_id`, `prd_ref`, `task_flow_policy`, etc.)
5. Server stores both fields as-is and computes `resolved_config_hash = SHA-256(canonical_json(merge(D, O)))`.

**Critical rule:** `O` contains **exactly** the fields where the user-supplied value differs from `D`. A field whose user-supplied value equals the default MUST NOT appear in `O`. Conversely, any field where the user-supplied value differs from `D` MUST appear in `O`. This ensures analysis can distinguish "accepted default" from "explicitly chosen."

---

## 6. CLI

### 6.1 Packaging

- Module: `src/squadops/cli/` (new package within existing `squadops`)
- Command framework: Typer
- Entry point: `squadops` → `squadops.cli.main:app` (via `console_scripts`)
- Optional dependency group: `pip install squadops[cli]`

### 6.2 Configuration

File: `~/.config/squadops/config.toml` (or `$XDG_CONFIG_HOME/squadops/config.toml`)

```toml
[api]
base_url = "http://localhost:8001"
timeout = 30

[auth]
mode = "token"           # "token" (v0.9.4) | "oidc_device" (stub — not implemented until OIDC CLI flow ships)
token_env = "SQUADOPS_TOKEN"

[output]
format = "table"         # "table" | "json"
```

### 6.3 Core commands

**Meta**
- `squadops version` — show CLI version and (if reachable) server version
- `squadops status` — check API connectivity and version compatibility

**Projects**
- `squadops projects list`
- `squadops projects show <project_id>`

**Cycles**
- `squadops cycles create <project_id> [--prd <artifact_id>] [--profile <crp_name>] [--set key=value ...] [--notes "..."]`
- `squadops cycles list <project_id> [--status active|completed|failed|cancelled]`
- `squadops cycles show <project_id> <cycle_id>`
- `squadops cycles cancel <project_id> <cycle_id>`

**Runs**
- `squadops runs list <project_id> <cycle_id>`
- `squadops runs show <project_id> <cycle_id> <run_id>`
- `squadops runs retry <project_id> <cycle_id> [--set key=value ...]`
- `squadops runs cancel <project_id> <cycle_id> <run_id>`
- `squadops runs gate <project_id> <cycle_id> <run_id> <gate_name> --approve|--reject [--notes "..."]`

**Squad Profiles**
- `squadops squad-profiles list`
- `squadops squad-profiles show <profile_id>`
- `squadops squad-profiles active`
- `squadops squad-profiles set-active <profile_id>`

**Artifacts**
- `squadops artifacts ingest --project <project_id> --type prd --file prd.md`
- `squadops artifacts get <artifact_id>`
- `squadops artifacts download <artifact_id> --out <path>`
- `squadops artifacts list --project <project_id> [--cycle <cycle_id>] [--type prd|code|test_report|...]`
- `squadops baseline get <project_id> <artifact_type>`
- `squadops baseline set <project_id> <artifact_type> <artifact_id>`

### 6.4 Command aliases

For operator convenience, common subcommands have short aliases:

| Canonical | Alias |
|-----------|-------|
| `list` | `ls` |
| `show` | `cat` |

Example: `squadops cycles ls hello_squad` is equivalent to `squadops cycles list hello_squad`.

### 6.5 Output conventions

- Default output: readable table for list commands; structured detail for show commands.
- `--format table|json` flag (global) selects output format. `--json` is a shorthand alias for `--format json`.
- Consistent status indicators using Rich formatting.

### 6.6 Exit codes

Standard shell conventions, with application-specific codes in the 10+ range:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General/unexpected error |
| 2 | Usage/CLI syntax error (Typer handles this) |
| 10 | Validation error (API 422) |
| 11 | Authentication error (API 401/403) |
| 12 | Not found (API 404) |
| 13 | Conflict/illegal state transition (API 409) |
| 20 | Network/timeout error |

---

## 7. API Changes

**None required.** The CLI operates against the existing SIP-0064 API surface as-is. No new endpoints, no modified endpoints.

The only server-side change is ensuring the existing `POST /api/v1/projects/{project_id}/cycles` endpoint stores `applied_defaults` and `execution_overrides` from the request body — which SIP-0064 already implements.

---

## 8. Testing

### 8.1 CLI unit tests

- Config loading and validation
- CRP default application and override diff computation
- `resolved_config_hash` golden tests (same defaults + overrides = same hash, matching server computation)
- JSON and table output formatting
- Exit code mapping for each error category
- Command argument parsing and validation

### 8.2 CLI integration tests

End-to-end tests using httpx against a running runtime-api (or TestClient):

- Create cycle via CLI → verify via API
- List, show, cancel cycles
- Retry run, gate decision (approve/reject), cancel run
- Artifact ingest/download/list, baseline set/get
- Error code mapping: 404 → exit 12, 409 → exit 13, 422 → exit 10
- `--json` output is valid JSON and contains expected fields
- `squadops status` reports connectivity

### 8.3 CRP contract tests

- All bundled CRP profiles are loadable and valid against schema
- Golden tests: `canonical_merge(defaults, overrides)` produces identical `resolved_config_hash` as `compute_config_hash()` from `squadops.cycles.lifecycle`

### 8.4 Hash round-trip golden test

End-to-end test that proves CLI and server compute the same hash:

1. CLI loads CRP defaults `D`, applies overrides `O`, computes `resolved_config_hash` locally.
2. CLI sends `POST /api/v1/projects/{id}/cycles` with `applied_defaults=D`, `execution_overrides=O`.
3. Server stores the Cycle and computes `resolved_config_hash` via `compute_config_hash()`.
4. Test asserts `response.resolved_config_hash == locally_computed_hash`.

This is the canonical proof that the CLI and server agree on the canonical JSON merge and hashing algorithm.

---

## 9. Migration / Compatibility

- No changes to the SIP-0064 data model.
- No changes to existing API endpoints.
- WarmBoot remains frozen legacy (per SIP-0064 §2.1) and is not used by CLI.
- CLI requires `squadops[cli]` optional dependency group.

---

## 10. Files Created/Modified Summary

| File | Action | Notes |
|------|--------|-------|
| `src/squadops/cli/__init__.py` | NEW | CLI package init |
| `src/squadops/cli/main.py` | NEW | Typer app, entry point |
| `src/squadops/cli/config.py` | NEW | Config loading (~/.config/squadops/config.toml) |
| `src/squadops/cli/client.py` | NEW | httpx-based API client |
| `src/squadops/cli/commands/projects.py` | NEW | Project commands |
| `src/squadops/cli/commands/cycles.py` | NEW | Cycle commands |
| `src/squadops/cli/commands/runs.py` | NEW | Run commands |
| `src/squadops/cli/commands/profiles.py` | NEW | Squad profile commands |
| `src/squadops/cli/commands/artifacts.py` | NEW | Artifact + baseline commands |
| `src/squadops/cli/commands/meta.py` | NEW | version, status commands |
| `src/squadops/cli/output.py` | NEW | Table/JSON formatting |
| `src/squadops/cli/exit_codes.py` | NEW | Exit code constants |
| `src/squadops/contracts/cycle_request_profiles/__init__.py` | NEW | CRP loader |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | NEW | CRP Pydantic model |
| `src/squadops/contracts/cycle_request_profiles/profiles/default.yaml` | NEW | Standard defaults |
| `src/squadops/contracts/cycle_request_profiles/profiles/benchmark.yaml` | NEW | Benchmark defaults |
| `src/squadops/contracts/cycle_request_profiles/profiles/selftest.yaml` | NEW | Self-test defaults |
| `pyproject.toml` | MODIFY | Add `[project.scripts]` and `[project.optional-dependencies].cli` |
| `tests/unit/cli/` | NEW | CLI unit tests |
| `tests/unit/contracts/` | NEW | CRP contract tests |

---

## 11. Acceptance Criteria

1. `squadops` CLI can operate all core SIP-0064 flows (projects/cycles/runs/artifacts/profiles) against a running runtime-api.
2. `squadops version` and `squadops status` report CLI version and API connectivity.
3. CRP pack exists in-repo and ships with the CLI under `src/squadops/contracts/`.
4. `squadops cycles create` applies CRP defaults and computes overrides correctly.
5. `applied_defaults` and `execution_overrides` are persisted distinctly on the Cycle for analysis.
6. `resolved_config_hash` is deterministic and matches the server-side computation (golden tests pass).
7. CLI provides both human-readable (table) and JSON outputs.
8. Exit codes follow §6.6 conventions and are stable for scripting.
9. All CLI unit tests and integration tests pass.
10. No changes to SIP-0064 API endpoints or domain models required.
