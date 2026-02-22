# Enhanced Agent Build Capabilities — Implementation Plan

## Context

The cycle execution pipeline (SIP-0066) runs 5 handlers that each produce a single markdown planning artifact. Neo writes an `implementation_plan.md`, not actual source code. Eve writes a `validation_plan.md`, not actual tests. The SIP proposal at `sips/proposed/SIP-Enhanced-Agent-Build-Capabilities.md` defines two new task types (`development.build`, `qa.build_validate`) that produce **executable artifacts** — source code, test files, and configuration. This plan implements that SIP.

The design is PCR-driven with no new schema: existing `Cycle`, `Run`, `Gate`, `TaskFlowPolicy` models are unchanged. A `build_tasks` key in `applied_defaults` controls whether build tasks are appended to the task plan.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Build handlers extend `_CycleTaskHandler` (cycle_tasks.py:32) | Same LLM→artifact pattern; override `_build_user_prompt()` and `handle()` for multi-file output |
| D2 | `extract_fenced_files()` is a standalone utility in `src/squadops/capabilities/handlers/fenced_parser.py` | No handler dependency; reusable by tests and CLI |
| D3 | Executor pre-resolves artifact content from vault into `inputs["artifact_contents"]` dict keyed by `ref.filename` (full relative path, not basename). Injected ONLY for build tasks (`development.build`, `qa.build_validate`) and ONLY for required plan artifacts + produced source artifacts; executor must NOT inject arbitrary historical artifacts. Size limit: 512 KB total decoded UTF-8 text (`decode(errors="replace")`) across all selected artifacts. If exceeded, executor injects `artifact_refs` only and passes `ArtifactVaultPort` to the handler via `inputs["artifact_vault"]` for on-demand resolution. | Build handlers need full plan text, not just IDs. Normally pre-resolved to keep handlers simple; vault fallback only for large builds (group_run). Full relative path keys prevent collisions (e.g., `src/models.py` vs `tests/models.py`). |
| D4 | `_ALLOWED_DEFAULT_KEYS` in PCR schema (contracts/cycle_request_profiles/schema.py:16) derives from `CycleCreateRequest` model fields — no change needed if we don't add `build_tasks` as a top-level DTO field | `build_tasks` lives inside `applied_defaults` dict, not as a standalone DTO field. The PCR validator checks top-level keys, not nested dict contents |
| D5 | New artifact types `source`, `test`, `config` are string values in `artifact_type` field of `ArtifactRef` | No enum needed — `artifact_type` is already a free string (models.py:231) |
| D6 | Build-only mode validation: executor checks `execution_overrides.plan_artifact_refs` before dispatching build tasks | If missing/empty → run transitions to FAILED with structured error |
| D7 | Task plan generator decides plan vs build inclusion via: `include_plan = bool(cycle.applied_defaults.get("plan_tasks", True))` and `include_build = bool(cycle.applied_defaults.get("build_tasks"))`. `build_tasks` is a list of task type strings in the PCR YAML; generator treats it as a boolean enable in v1 (presence/non-empty = enabled) and always emits the full `BUILD_TASK_STEPS` sequence. List-driven subset emission is a future enhancement. Build-only profile sets `plan_tasks: false`. | Pinned explicit flags — never infer intent from presence/absence of overrides. Pure function logic, no new fields on Cycle model. List form preserves forward compatibility for selective build steps. |
| D8 | `DevelopmentBuildHandler` uses one LLM call per file when implementation plan contains a file list, otherwise one call for all files | Deterministic rule from SIP §5.3 |
| D9 | Assembly command goes in existing `runs.py` CLI file as `squadops runs assemble <cycle_id> <run_id> --out ./dir` | Fits the runs command group; output subdirectory name = `cycle_id[:12]` by default. If `cycle.project_id` is present and non-empty, use it instead (human-readable). `project_id` is a required field on `Cycle` (models.py:180), but the `cycle_id[:12]` default ensures assembly works even if the API response omits or blanks it. |
| D10 | Run report is emitted by `_execute_sequential()` in a `finally` block after terminal status, best-effort | Stored as `artifact_type: documentation`, filename `run_report.md`. `run_report.md` is `artifact_type=documentation` (legacy category); no new `artifact_type` `report` is introduced in this SIP. |
| D11 | PCR profiles `build.yaml` and `build-only.yaml` go in `src/squadops/contracts/cycle_request_profiles/profiles/` | Same location as existing `default.yaml`, `selftest.yaml`, `benchmark.yaml` |

---

## Phase 1: Fenced Code Parser + Build Handlers

### 1.1 Fenced code block parser

**New file:** `src/squadops/capabilities/handlers/fenced_parser.py`

```python
def extract_fenced_files(response: str) -> list[dict]:
    """Parse ```<lang>:<path> fences → list[{"filename": str, "content": str, "language": str}]

    Security: rejects absolute paths and '..' segments.
    Returns empty list if no tagged fences found; callers MUST treat this as extraction failure for build/test generation.
    """
```

- Regex: `` ^```(\w+):(\S+)\s*$ `` to match fence headers
- Fence headers MUST contain no spaces; any deviation is treated as parse failure (build fails)
- Path validation: reject if starts with `/` or contains `..`
- Content: everything between opening and closing `` ``` ``
- Returns: list of dicts, empty if no matches

### 1.2 Build handlers

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

Add two new handler classes after line 225:

**`DevelopmentBuildHandler`** (`development.build`, role `dev`):
- Overrides `_build_user_prompt()` to construct a build-focused prompt using:
  - PRD from `inputs["prd"]`
  - `implementation_plan.md` content from `inputs["artifact_contents"]` (pre-resolved by executor, D3)
  - `strategy_analysis.md` content from `inputs["artifact_contents"]` (if present)
- **Vault fallback**: If `inputs["artifact_contents"]` is missing required files (e.g., 512KB limit exceeded), handler resolves them using `inputs["artifact_vault"].retrieve()` with artifact IDs from `inputs["artifact_refs"]`. Handler MUST check for `artifact_vault` key before attempting fallback; if neither `artifact_contents` nor `artifact_vault` contains required plan artifacts, return `HandlerResult(success=False, error="Required plan artifacts not available")`.
- System prompt instructs LLM to produce complete, runnable source files using tagged fenced code blocks
- `handle()` overrides base to:
  1. Call LLM (single call or per-file, per D8)
  2. Parse response with `extract_fenced_files()`
  3. If no valid fences → return `HandlerResult(success=False, error="No valid fenced code blocks found")` with a `build_warnings.md` artifact containing the raw response
  4. Each extracted file → artifact with `artifact_type` and `media_type` derived from file extension:
     - `.py` → `source` / `text/x-python`
     - `.md` → `documentation` / `text/markdown`
     - `.txt` → `config` / `text/plain`
     - `.yaml`/`.yml` → `config` / `text/yaml`
     - `.toml` → `config` / `application/toml`
     - `.json` → `config` / `application/json`
     - `requirements.txt` → `config` / `text/plain` (special-cased by filename before extension)
     - Unknown extension → `source` / `application/octet-stream` (conservative default)

**`QABuildValidateHandler`** (`qa.build_validate`, role `qa`):
- Similar pattern but:
  - Reads `validation_plan.md` + all `source` artifacts from `inputs["artifact_contents"]`
  - **Vault fallback**: Same pattern as `DevelopmentBuildHandler` — if `artifact_contents` is missing required files, resolve via `inputs["artifact_vault"]` + `inputs["artifact_refs"]`. If neither source provides required artifacts, return `HandlerResult(success=False, error="Required plan/source artifacts not available")`.
  - System prompt instructs LLM to produce pytest test files that import from the source module structure
  - The handler MUST generate tests that import modules using the assembled file paths (relative package/module names derived from the emitted paths)
  - Each extracted test file → artifact with `artifact_type: "test"`

### 1.3 Handler registration

**Modified file:** `src/squadops/bootstrap/handlers.py`

Add to `HANDLER_CONFIGS` list (after line 73):
```python
(DevelopmentBuildHandler, ("dev",)),
(QABuildValidateHandler, ("qa",)),
```

### 1.4 Tests

**New file:** `tests/unit/capabilities/test_fenced_parser.py` (~15 tests)
- Valid single fence, multiple fences, mixed languages
- Path traversal rejection (`../etc/passwd`, `/absolute/path`)
- Empty input, no tagged fences, malformed fences
- Whitespace handling in fence headers

Minimum required for Phase 1 acceptance: `test_single_fence_extraction`, `test_path_traversal_rejection`, `test_empty_returns_empty_list`.

**New file:** `tests/unit/capabilities/test_build_handlers.py` (~12 tests)
- `DevelopmentBuildHandler`: successful multi-file extraction, single-file, parse failure → FAILED
- `QABuildValidateHandler`: test file generation, correct artifact types
- LangFuse generation recording (when `correlation_context` present)
- Missing required inputs → validation failure

Minimum required for Phase 1 acceptance: `test_dev_build_multi_file`, `test_dev_build_parse_failure_returns_failed`, `test_qa_build_produces_test_artifacts`.

---

## Phase 2: Task Plan Generator + Executor Wiring

### 2.1 Task plan generator

**Modified file:** `src/squadops/cycles/task_plan.py`

Add `BUILD_TASK_STEPS` after `CYCLE_TASK_STEPS` (line 23):
```python
BUILD_TASK_STEPS: list[tuple[str, str]] = [
    ("development.build", "dev"),
    ("qa.build_validate", "qa"),
]
```

Modify `generate_task_plan()` (line 35):
- Compute `include_plan` and `include_build` per D7
- If `include_plan`: emit envelopes for `CYCLE_TASK_STEPS`
- If `include_build`: emit envelopes for `BUILD_TASK_STEPS` (continuing causation chain)
- Gate matching still works: `TaskFlowPolicy.gates[].after_task_types` already supports any task type string

### 2.2 Executor: artifact content pre-resolution

**Modified file:** `adapters/cycles/distributed_flow_executor.py`

In `_execute_sequential()` (line 256), after artifact storage (line 323), add logic to build an `artifact_contents` map. Before dispatching a build task, if the task type starts with `development.build` or `qa.build_validate`:

1. Collect relevant artifact_ids from `all_artifact_refs` using a deterministic filter based on a pinned task_type→artifact provenance map:
   ```python
   _BUILD_ARTIFACT_FILTER = {
       "development.build": {
           "by_producing_task": ["strategy.analyze_prd", "development.implement"],
           # Falls back to artifact_type filter only for build-only runs
           # where producing_task metadata may be absent:
           "by_type_fallback": ["documentation"],
       },
       "qa.build_validate": {
           "by_producing_task": ["qa.validate"],
           "by_type": ["source", "config"],  # all dev-build outputs
       },
   }
   ```
   The executor tracks which task produced each artifact (via the `producing_task_type` field set during `_store_artifact()`). Filter precedence: `by_producing_task` first, then `by_type`/`by_type_fallback` for artifacts without provenance metadata (e.g., injected `plan_artifact_refs` in build-only runs).
   - For `development.build`: include artifacts produced by `strategy.analyze_prd` and `development.implement`
   - For `qa.build_validate`: include artifacts produced by `qa.validate` + all artifacts with `artifact_type in ("source", "config")` (code produced by dev build)
   - Exclude: all other artifacts (data_report, governance_review, run_report, etc.) — never injected into build handlers
2. For each, call `self._artifact_vault.retrieve(artifact_id)` → `(ref, content_bytes)`
3. Build `artifact_contents: dict[str, str]` keyed by `ref.filename` (full relative path, not basename) → `content_bytes.decode(errors="replace")`
4. Inject into enriched envelope: `inputs["artifact_contents"] = artifact_contents`

This uses the existing `ArtifactVaultPort.retrieve()` (artifact_vault.py:18).

### 2.3 Executor: build-only validation

In `execute_run()` (line 82), after generating the task plan:

If `include_build` is true AND `include_plan` is false (`plan_tasks=false`), require `execution_overrides.plan_artifact_refs` to be a non-empty list. If absent or empty → transition run to FAILED and set `run.error_code=INVALID_INPUT` and `run.error_message='plan_artifact_refs required for build-only cycle'`.

For build-only runs, the executor MUST extend the run's working `all_artifact_refs` set with `execution_overrides.plan_artifact_refs` before task dispatch so §2.2 pre-resolution includes them. Then inject the resolved content into the first build task's `artifact_contents`.

### 2.4 PCR profiles

**New file:** `src/squadops/contracts/cycle_request_profiles/profiles/build.yaml`
```yaml
name: build
description: Plan-then-build cycle with optional gate between plan and build phases.
defaults:
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates:
      - name: plan-review
        description: Review planning artifacts before build begins.
        after_task_types:
          - governance.review
  expected_artifact_types:
    - documentation
    - source
    - test
    - config
  build_tasks:
    - development.build
    - qa.build_validate
  experiment_context: {}
  notes: "Plan-then-build cycle"
```

Profile schema must treat `expected_artifact_types` as free strings (no enum). If currently enumerated anywhere, expand allowlist to include `source`, `test`, `config`.

**New file:** `src/squadops/contracts/cycle_request_profiles/profiles/build-only.yaml`
```yaml
name: build-only
description: Build-only cycle that consumes plan artifacts from a prior cycle.
defaults:
  build_strategy: fresh
  task_flow_policy:
    mode: sequential
    gates: []
  expected_artifact_types:
    - source
    - test
    - config
  plan_tasks: false
  build_tasks:
    - development.build
    - qa.build_validate
  experiment_context: {}
  notes: "Build-only cycle — requires plan_artifact_refs in execution_overrides"
```

### 2.5 Fix play_game gate references (correctness)

**Modified file:** `examples/play_game/pcr.yaml`
- Fix `after_task_types` gate references: currently references `code` and `test_report` which are artifact types, not task types — change to `governance.review` for plan-review gate
- This is a correctness fix required before build gating can work

### 2.6 Tests

**New file:** `tests/unit/cycles/test_task_plan_build.py` (~10 tests)
- Plan-only: no build steps when `build_tasks` absent
- Plan+build: 7 envelopes (5 plan + 2 build), correct causation chain
- Build-only: 2 envelopes only, `plan_tasks: false` in applied_defaults
- Gate between plan and build groups

Minimum required for Phase 2 acceptance: `test_plan_only_no_build_steps`, `test_plan_plus_build_7_envelopes`, `test_build_only_2_envelopes`.

**New file:** `tests/unit/cycles/test_executor_build_wiring.py` (~10 tests)
- Artifact content pre-resolution: mock vault, verify `artifact_contents` injected
- Build-only validation: missing `plan_artifact_refs` → FAILED
- Existing plan-only cycles unaffected (regression)

Minimum required for Phase 2 acceptance: `test_artifact_contents_injected_for_build_task`, `test_build_only_missing_refs_fails`.

---

## Phase 3: Assembly Command + Run Reports

### 3.1 Assembly CLI command

**Modified file:** `src/squadops/cli/commands/runs.py`

Add `assemble` command (after `gate_decision`, line 194):
```python
@app.command("assemble")
def assemble_run(
    ctx: typer.Context,
    cycle_id: str = typer.Argument(...),
    run_id: str = typer.Argument(...),
    out: Path = typer.Option("./output", "--out", help="Output directory"),
):
```

Logic:
1. Fetch cycle metadata via API → derive `output_dir_name`: use `cycle.project_id` if present and non-empty, else `cycle_id[:12]`
2. List artifacts for run, filter by `artifact_type in ("source", "test", "config")`
3. Create `out/<output_dir_name>/` directory
4. Download each artifact, write to directory preserving filename
5. Print file tree and README content (if present)

### 3.2 Run report generation

**Modified file:** `adapters/cycles/distributed_flow_executor.py`

Add `_generate_run_report()` method:
- Called in `execute_run()` finally block, after terminal status, wrapped in try/except (best-effort)
- Produces `run_report.md` with: cycle/run metadata, per-task breakdown, artifact inventory, gate decisions, quality notes
- Stored via `_store_artifact()` with `artifact_type: "documentation"`

### 3.3 Tests

**New file:** `tests/unit/cli/test_assemble_command.py` (~8 tests)
- Successful assembly: files written to output directory
- No build artifacts → informative message
- API error handling

Minimum required for Phase 3 acceptance: `test_assemble_writes_files`, `test_assemble_no_build_artifacts`.

**New file:** `tests/unit/cycles/test_run_report.py` (~6 tests)
- Report contains expected sections
- Report generation failure doesn't affect run status
- Empty artifact list → minimal report

Minimum required for Phase 3 acceptance: `test_report_contains_metadata`, `test_report_failure_no_status_change`.

---

## Phase 4: Reference Apps + Validation

### 4.1 hello_squad example

**New directory:** `examples/hello_squad/`
- `prd.md` — "Build a CLI script that prints 'Hello from SquadOps!' with timestamp and motivational quote"
- `pcr.yaml` — build profile, targeting 1 source file + 1 test file

### 4.2 play_game PCR update

**Modified file:** `examples/play_game/pcr.yaml`
- Add `build_tasks: [development.build, qa.build_validate]` to defaults
- Update `expected_artifact_types` to include `source`, `test`, `config`
- Gate fix already applied in Phase 2 (§2.5)

### 4.3 group_run example

**New directory:** `examples/group_run/`
- `prd.md` — "CLI app for logging running activities with distance/time/date, history, stats"
- `pcr.yaml` — build profile, targeting multi-module application

### 4.4 Tests

**New file:** `tests/unit/contracts/test_build_profiles.py` (~6 tests)
- `build.yaml` and `build-only.yaml` load and validate
- Profile defaults contain expected `build_tasks`
- `build-only.yaml` has no gates and sets `plan_tasks: false`

Minimum required for Phase 4 acceptance: `test_build_profile_loads`, `test_build_only_profile_loads`.

---

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `src/squadops/capabilities/handlers/fenced_parser.py` | **New** | 1 |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | Modify: add 2 build handlers | 1 |
| `src/squadops/bootstrap/handlers.py` | Modify: register 2 new handlers | 1 |
| `src/squadops/cycles/task_plan.py` | Modify: add BUILD_TASK_STEPS, update generate_task_plan() | 2 |
| `adapters/cycles/distributed_flow_executor.py` | Modify: artifact content pre-resolution, build-only validation, run report | 2, 3 |
| `src/squadops/contracts/cycle_request_profiles/profiles/build.yaml` | **New** | 2 |
| `src/squadops/contracts/cycle_request_profiles/profiles/build-only.yaml` | **New** | 2 |
| `src/squadops/cli/commands/runs.py` | Modify: add assemble command | 3 |
| `examples/hello_squad/prd.md` | **New** | 4 |
| `examples/hello_squad/pcr.yaml` | **New** | 4 |
| `examples/play_game/pcr.yaml` | Modify: add build_tasks | 4 |
| `examples/group_run/prd.md` | **New** | 4 |
| `examples/group_run/pcr.yaml` | **New** | 4 |
| `tests/unit/capabilities/test_fenced_parser.py` | **New** | 1 |
| `tests/unit/capabilities/test_build_handlers.py` | **New** | 1 |
| `tests/unit/cycles/test_task_plan_build.py` | **New** | 2 |
| `tests/unit/cycles/test_executor_build_wiring.py` | **New** | 2 |
| `tests/unit/cli/test_assemble_command.py` | **New** | 3 |
| `tests/unit/cycles/test_run_report.py` | **New** | 3 |
| `tests/unit/contracts/test_build_profiles.py` | **New** | 4 |

**Estimated new tests:** ~67

---

## Key Reuse Points

These existing functions/classes are reused directly — no reimplementation:

| What | Where | How Used |
|------|-------|----------|
| `_CycleTaskHandler` base class | cycle_tasks.py:32 | Build handlers extend it |
| `HandlerResult` | cycle_tasks.py (imported) | Build handlers return it |
| `HANDLER_CONFIGS` registration | handlers.py:51 | Append 2 new entries |
| `generate_task_plan()` | task_plan.py:35 | Extend with BUILD_TASK_STEPS |
| `_store_artifact()` | distributed_flow_executor.py:470 | Build artifacts stored same way |
| `ArtifactVaultPort.retrieve()` | artifact_vault.py:18 | Pre-resolve content for handlers |
| `CycleRequestProfile` schema | schema.py:27 | Validates new profile YAMLs |
| `load_profile()` | __init__.py:36 | CLI loads build/build-only profiles |
| `APIClient` | client.py | Assembly command uses existing client |
| `CorrelationContext.from_envelope()` | telemetry/models.py:93 | LangFuse tracing in build handlers |

---

## Verification

```bash
# Phase 1: Parser + handlers
pytest tests/unit/capabilities/test_fenced_parser.py -v
pytest tests/unit/capabilities/test_build_handlers.py -v

# Phase 2: Task plan + executor
pytest tests/unit/cycles/test_task_plan_build.py -v
pytest tests/unit/cycles/test_executor_build_wiring.py -v

# Phase 3: Assembly + reports
pytest tests/unit/cli/test_assemble_command.py -v
pytest tests/unit/cycles/test_run_report.py -v

# Phase 4: Profiles + examples
pytest tests/unit/contracts/test_build_profiles.py -v

# Full regression (existing tests still pass)
./scripts/dev/run_new_arch_tests.sh -v

# E2E (requires Ollama + Docker)
# 1. Rebuild: ./scripts/dev/ops/rebuild_and_deploy.sh all
# 2. Plan-then-build:
#    squadops cycles create play_game --squad-profile full-squad --profile build
#    squadops cycles show play_game <cycle_id>
#    squadops runs gate <run_id> --approve    # approve plan-review gate
#    squadops runs assemble <cycle_id> <run_id> --out ./output
#    cd output/play_game && python main.py    # play the game
# 3. Verify LangFuse: 7 generations (5 plan + 2 build) under one trace
# 4. Verify artifacts: source, test, config types in artifact list
# 5. Verify run_report.md: squadops artifacts get <report_artifact_id>
```
