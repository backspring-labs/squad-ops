---
title: Enhanced Agent Build Capabilities
status: proposed
author: Jason Ladd
created_at: '2026-02-12T00:00:00Z'
---
# SIP-00XX: Enhanced Agent Build Capabilities

**Status:** Proposed
**Created:** 2026-02-12
**Owner:** SquadOps Core
**Target Release:** v0.9.7
**Related:** SIP-0066 (Cycle Execution Pipeline), SIP-0064 (Cycle API), SIP-0065 (CLI)

---

## 1. Intent

Add build task types (`development.build`, `qa.build_validate`) to the cycle execution pipeline so that agents produce **executable artifacts** — source code, test files, and configuration — not just planning documents. Leverage the existing cycle/run/gate/task-plan model with no new schema constructs. A cycle's PCR template controls whether it runs planning tasks, build tasks, or both.

The result: `squadops cycles create play_game --profile build` produces a directory you can `python main.py` from.

---

## 2. Problem Statement

Today's cycle execution (SIP-0066) runs 5 handlers that each make one LLM call and emit one markdown artifact:

| Agent | Task Type | Current Output |
|-------|-----------|----------------|
| Nat (strat) | `strategy.analyze_prd` | `strategy_analysis.md` |
| Neo (dev) | `development.implement` | `implementation_plan.md` |
| Eve (QA) | `qa.validate` | `validation_plan.md` |
| Data | `data.report` | `data_report.md` |
| Max (lead) | `governance.review` | `governance_review.md` |

Neo produces a *plan* for how to implement the app, not actual code. Eve produces a validation *plan*, not actual tests. The pipeline is architecturally sound but the output is not executable.

The planning artifacts are valuable — they represent structured analysis from each role. The gap is **build tasks** that consume those plans and produce real code.

---

## 3. Goals

1. **Build tasks**: New task types (`development.build`, `qa.build_validate`) that produce executable artifacts.
2. **Three cycle modes via PCR**: Plan-only, build-only, or plan-then-build — all using existing `TaskFlowPolicy` and task plan templates.
3. **Executable output**: Build tasks produce source files (`*.py`), test files (`test_*.py`), and configuration (`requirements.txt`, `README.md`) as typed artifacts.
4. **Runnable assembly**: CLI command assembles build artifacts into a runnable directory.
5. **Three reference apps**: `hello_squad` (trivial), `play_game` (medium), `group_run` (substantial) produce working code.
6. **Run reports**: Completed runs produce a structured report capturing what was built and quality summary.

---

## 4. Non-Goals

- New "stage" schema or `StageSpec` type — cycles already support task groups and gates.
- Multi-file extraction via tool use or function calling (v1 uses fenced code blocks).
- Sandboxed code execution within the pipeline (agents produce code; humans run it).
- Incremental builds that diff against a baseline (future enhancement).
- Renaming existing task types (no migration burden).

---

## 5. Design

### 5.1 Cycle Modes — PCR-Driven, No New Schema

A cycle's task plan is determined by its PCR profile. Three patterns emerge naturally from the existing model:

#### A) Planning-only cycle (existing behavior)

```yaml
# profiles/plan.yaml (this is what today's selftest/default profiles do)
defaults:
  task_flow_policy:
    mode: sequential
    gates: []
```

Task plan template (Group 1 only):
```
strategy.analyze_prd    → Nat   → strategy_analysis.md
development.implement   → Neo   → implementation_plan.md
qa.validate             → Eve   → validation_plan.md
data.report             → Data  → data_report.md
governance.review       → Max   → governance_review.md
```

Existing task types unchanged. No code emission required.

#### B) Build-only cycle

Precondition: inputs include prior plan artifacts from a previous cycle. Build-only cycles MUST provide input plan artifacts via `execution_overrides.plan_artifact_refs: list[str]`. If `plan_artifact_refs` is absent or empty, the run transitions to FAILED and records `error_code=INVALID_INPUT` in the run's failure reason, with a human-readable message describing the missing refs.

```yaml
# profiles/build-only.yaml
defaults:
  task_flow_policy:
    mode: sequential
    gates: []
  build_tasks: [development.build, qa.build_validate]
```

Task plan template (Group 2 only):
```
development.build         → Neo   → source files (*.py)
qa.build_validate         → Eve   → test files (test_*.py)
```

Build handlers resolve plan artifact content from `ArtifactVaultPort` using the refs provided in `plan_artifact_refs`.

#### C) Plan-then-build in one cycle

```yaml
# profiles/build.yaml
defaults:
  task_flow_policy:
    mode: sequential
    gates:
      - name: plan-review
        description: Review planning artifacts before build begins.
        after_task_types: [governance.review]
  build_tasks: [development.build, qa.build_validate]
```

Task plan template (Group 1 + Group 2, gate between):
```
Group 1 (plan):
  strategy.analyze_prd    → Nat   → strategy_analysis.md
  development.implement   → Neo   → implementation_plan.md
  qa.validate             → Eve   → validation_plan.md
  data.report             → Data  → data_report.md
  governance.review       → Max   → governance_review.md

  [gate: plan-review — reject ⇒ run FAILED, Group 2 not executed]

Group 2 (build):
  development.build       → Neo   → source files (*.py)
  qa.build_validate       → Eve   → test files (test_*.py)
```

The plan-review gate is evaluated after the final task in Group 1 (`governance.review`) and before any build tasks are dispatched. Group 2 consumes Group 1 outputs via `artifact_refs` accumulated during Group 1 execution. The gate is optional — omit it for unattended execution.

### 5.2 Why No New Schema

- The executor already supports sequential task ordering + gates + pause/resume.
- "Cycle" is the unit of intent; "run" executes a chosen policy.
- Choosing plan vs. build vs. both is just selecting a different PCR / task plan template.
- The `build_tasks` field in the PCR tells the task plan generator which build task types to append. The generator remains a pure function: `(cycle, run, profile, pcr) → list[TaskEnvelope]`.
- At run start, the selected profile defaults are materialized into `cycle.applied_defaults` so `build_tasks` is available to the task plan generator deterministically.

### 5.3 Build Handlers

Two new handlers, registered alongside the existing five:

#### `DevelopmentBuildHandler` (`development.build`)
- **Input**: PRD + `implementation_plan.md` (resolved from `artifact_refs` via `ArtifactVaultPort`; summaries may also be present in `prior_outputs`) + `strategy_analysis.md`
- **System prompt**: Instructs the LLM to produce complete, runnable source files using fenced code blocks tagged by filename
- **Output format**: Markdown response with tagged fences:
  ````
  ```python:main.py
  # file contents
  ```

  ```python:game.py
  # file contents
  ```
  ````
- **Artifact extraction**: Parser splits response into multiple artifacts, each with:
  - `media_type: text/x-python` (or appropriate for language)
  - `artifact_type: source`
  - Filename preserved from fence tag
- **Failure on parse failure**: If no valid tagged fences are found for expected outputs, the handler returns FAILED and emits a single report artifact `build_warnings.md` describing the parse failure and including the raw LLM response. This fail-fast behavior ensures a "SUCCEEDED" run always contains usable files.
- **Multiple LLM calls**: If the implementation plan defines a file list, the handler MUST generate one file per call in that order. If no file list exists, the handler MUST generate all files in a single call. This deterministic rule makes builds repeatable across models.

#### `QABuildValidateHandler` (`qa.build_validate`)
- **Input**: PRD + `validation_plan.md` + all `source` artifact_refs from `development.build`; handler resolves content via `ArtifactVaultPort`
- **System prompt**: Instructs LLM to produce executable pytest test files that import from the module structure Neo produced
- **Output**: Test files as artifacts with `artifact_type: test`
- **Constraint**: Tests must reference the same filenames/module names from the build step

### 5.4 Fenced Code Block Parser

A utility function extracts multiple files from a single LLM response:

```python
def extract_fenced_files(response: str) -> list[dict]:
    """Parse LLM response containing tagged code fences.

    Recognizes patterns like:
        ```python:filename.py
        <content>
        ```

    Returns list of {"filename": str, "content": str, "language": str}
    """
```

**Fence header format**: MUST be `` ```<lang>:<relative_path> `` with no spaces. `<relative_path>` MUST NOT be absolute and MUST NOT contain `..` segments. If any filename violates this rule, the handler returns FAILED.

If no tagged fences are found, extraction returns an empty list and the handler treats this as a build failure (see §5.3).

### 5.5 Artifact Type Extensions

Current artifact types: `code`, `test_report`, `metrics`, `documentation`.

New types for build tasks:
- `source` — executable source files (`.py`, `.js`, etc.)
- `test` — test files (`test_*.py`)
- `config` — configuration files (`requirements.txt`, `pyproject.toml`)

For build outputs, `source` replaces `code` as the canonical type used by assembly. Existing `code` remains for legacy planning artifacts only — no new artifacts should be emitted with type `code`.

### 5.6 Task Plan Generator Changes

`generate_task_plan()` gains awareness of build tasks. The existing `CYCLE_TASK_STEPS` becomes the plan group. A new `BUILD_TASK_STEPS` list is appended when the cycle's configuration includes build tasks:

```python
PLAN_TASK_STEPS = [
    ("strategy.analyze_prd", "strat"),
    ("development.implement", "dev"),
    ("qa.validate", "qa"),
    ("data.report", "data"),
    ("governance.review", "lead"),
]

BUILD_TASK_STEPS = [
    ("development.build", "dev"),
    ("qa.build_validate", "qa"),
]
```

The generator inspects `cycle.applied_defaults` for a `build_tasks` key. When `build_tasks` is present and non-empty, the generator appends build steps after the planning steps; gates remain defined via `TaskFlowPolicy.after_task_types` and will pause execution before the first build task when configured (e.g., after `governance.review`). If the cycle only specifies build tasks (mode B), only `BUILD_TASK_STEPS` are emitted.

No changes to `TaskFlowPolicy`, `Cycle`, `Run`, or `Gate` models.

### 5.7 Chaining: Plan Artifacts → Build Inputs

The executor already chains `prior_outputs` between sequential tasks. For build tasks, chaining uses the same mechanism with a clear contract:

1. **Required**: `artifact_refs` MUST include the plan artifacts needed for build (`implementation_plan.md` at minimum). Build handlers resolve full artifact content from `ArtifactVaultPort` using these refs.
2. **Optional**: `prior_outputs` summaries are convenience for prompting but are not the source of truth for build inputs. Handlers MUST NOT depend solely on `prior_outputs` for plan content.
3. Build task envelopes receive accumulated `artifact_refs` from all prior tasks in the run.

For mode B (build-only cycle), `execution_overrides.plan_artifact_refs` provides the refs from a prior plan cycle. The executor injects these into the first build task's `artifact_refs`.

### 5.8 Assembly Command

New CLI command to assemble a runnable app from build artifacts:

```bash
squadops runs assemble <cycle_id> <run_id> --out ./output/
```

The output directory name is derived from `cycle.project_id` (present on the Cycle model, line 186 of `cycles/models.py`); the CLI does not require `project_id` as a separate argument.

This command:
1. Fetches all `source`, `test`, and `config` artifacts for the run via the API
2. Writes them to `--out` directory preserving filenames
3. Prints the file tree and any `README.md` content

Assembled output:
```
output/play_game/
├── main.py
├── game.py
├── test_game.py
├── requirements.txt
└── README.md
```

### 5.9 Run Report

After the run reaches a terminal status, the Flow Executor emits `run_report.md` as a final artifact (best-effort; failures to write the report do not change run status). The report summarizes:

- Cycle/run metadata (IDs, status, duration, squad profile)
- Per-task breakdown (task type, agent, duration, artifact names)
- Artifact inventory (count by type, total lines of code)
- Gate decisions (if any)
- Quality notes (extracted from governance review if present)

This is stored as an artifact with `artifact_type: documentation` and can be retrieved via the standard artifact API.

---

## 6. Reference App Progression

### 6.1 hello_squad (Trivial — Smoke Test)

**PRD**: Build a CLI script that prints "Hello from SquadOps!" with the current timestamp and a random motivational quote.

**Expected build output**:
- `hello_squad.py` — single file, <30 lines
- `test_hello_squad.py` — 3-4 basic tests
- `README.md`

**Purpose**: Validates the full pipeline works. Target: <2 minutes on local LLM profile; not a hard requirement. If this fails, nothing else will work.

### 6.2 play_game (Medium — Platform Selftest)

**PRD**: Terminal Tic-Tac-Toe with human vs AI opponent.

**Expected build output**:
- `main.py` — entry point
- `game.py` — game logic (board, win detection, AI move)
- `display.py` — terminal rendering
- `test_game.py` — game logic tests
- `requirements.txt`
- `README.md`

**Purpose**: Validates multi-file code generation, module imports, and testability.

### 6.3 group_run (Substantial — Capability Benchmark)

**PRD**: CLI app for logging running activities (Strava-like). Log runs with distance/time/date, view history, see stats (total distance, average pace, personal records).

**Expected build output**:
- `main.py` — CLI entry point (argparse or typer)
- `models.py` — Run data model
- `storage.py` — JSON file persistence
- `stats.py` — Statistics calculations
- `display.py` — Formatted output
- `test_models.py`, `test_stats.py`, `test_storage.py` — test suite
- `requirements.txt`
- `README.md`

**Purpose**: Validates the squad can produce a multi-module application with data persistence, business logic, and comprehensive tests. This is the benchmark for DGX Spark readiness.

---

## 7. Backward Compatibility

- Existing task types (`development.implement`, `qa.validate`, etc.) are **not renamed**. No migration.
- Cycles created without `build_tasks` in their config execute as plan-only (current behavior). Zero impact on existing cycles or PCR profiles.
- New build task types are purely additive — new handlers registered in the handler registry, new entries in the task plan generator.
- Artifacts produced by build handlers use new types (`source`, `test`, `config`) that don't collide with existing types (`test_report`, `documentation`). The legacy `code` type is retained for reads but no new artifacts should be emitted with type `code`.

---

## 8. Implementation Phases

### Phase 1: Fenced Code Parser + Build Handlers
- Implement `extract_fenced_files()` utility with security validation (no absolute paths, no `..` segments)
- Create `DevelopmentBuildHandler` and `QABuildValidateHandler`
- Register new task types in handler registry
- New artifact types: `source`, `test`, `config`
- Unit tests for parser (valid fences, malformed fences, path traversal rejection) and handlers

### Phase 2: Task Plan Generator + Executor Wiring
- Extend `generate_task_plan()` to append build tasks when configured
- Ensure `artifact_refs` chain from plan tasks to build tasks
- Implement `plan_artifact_refs` injection for build-only cycles
- Create `build.yaml` and `build-only.yaml` PCR profiles
- Wire optional `plan-review` gate between plan and build groups
- Unit tests for task plan generation with build tasks

### Phase 3: Assembly Command + Run Reports
- `squadops runs assemble` CLI command (derives project_id from cycle)
- Post-run report generation (`run_report.md` artifact)
- Unit tests for assembly and report generation

### Phase 4: Reference Apps + Validation
- Create `examples/hello_squad/` (PRD + PCR)
- Update `examples/play_game/` PCR for plan-then-build
- Create `examples/group_run/` (PRD + PCR)
- E2E validation: all three apps build and produce runnable output

---

## 9. Open Questions

1. **LLM output reliability**: Can 7B/8B models (Ollama) reliably produce well-structured fenced code blocks with filename tags? May need prompt engineering iteration or output validation with retry.
2. **File count scaling**: For `group_run` (8+ files), the deterministic rule (§5.3) requires per-file calls when the implementation plan includes a file list. Need to validate this scales within acceptable latency.
3. **Test execution**: Should Eve's tests be automatically executed as a pipeline step, or is that a separate concern? (Non-goal for v1, but natural extension.)

---

## 10. Success Criteria

1. `squadops cycles create hello_squad --profile build` completes and `squadops runs assemble` produces a runnable `hello_squad.py`.
2. `squadops cycles create play_game --profile build` produces a playable Tic-Tac-Toe game.
3. `squadops cycles create group_run --profile build` produces a functional run-tracking CLI.
4. Each run produces a `run_report.md` with timing, artifact inventory, and quality summary.
5. Eve's test artifacts pass for `hello_squad`; `play_game` has at least game-logic tests passing; `group_run` has at least one test suite (models/stats/storage) passing.
6. All existing planning-only cycles continue to work unchanged (zero regression).
7. A build run with malformed LLM output fails fast (no silent "SUCCEEDED" with zero usable files).
