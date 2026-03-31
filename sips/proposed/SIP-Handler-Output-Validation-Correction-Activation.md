---
title: Build Convergence Loop — Dynamic Task Decomposition, Output Validation & Correction Activation
status: proposed
author: SquadOps Architecture
created_at: '2026-03-31T00:00:00Z'
---
# SIP-XXXX: Build Convergence Loop — Dynamic Task Decomposition, Output Validation & Correction Activation

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-03-31
**Revision:** 2

---

## 1. Abstract

SquadOps cycles targeting non-trivial builds (full-stack apps, multi-component systems) cannot succeed with the current static task plan. The `build` profile generates exactly two build tasks — one `development.develop` and one `qa.test` — regardless of PRD complexity. Each task makes a single LLM call. A 1-hour cycle timebox intended for a full-stack FastAPI + React app completed in 22 seconds, producing 15% of the required output and declaring success.

This SIP addresses three compounding gaps:

1. **Static task plans** — The task planner (`generate_task_plan()`) selects from hardcoded step lists. It does not inspect the PRD or implementation plan. A 10-endpoint full-stack app and a single-file script receive the same two build tasks.

2. **No output validation** — Build handlers return `success=True` after a single LLM call if any fenced code blocks exist. There is no check against the PRD, the design plan, or expected artifact types.

3. **Inert correction protocol** — SIP-0079's correction infrastructure (outcome classification, correction protocol, repair tasks, plan deltas) is fully implemented but never activates because handlers never emit failure signals.

The SIP introduces **dynamic build task decomposition** (Max decomposes the build into focused subtasks during planning), **output validation** (handlers check completeness before declaring success), and **outcome classification wiring** (semantic failures activate the existing correction protocol). Together, these turn a 22-second single-pass build into a multi-task convergence loop that fills the cycle timebox with productive, incremental work.

---

## 2. Problem Statement

### 2.1 Observed Failure

On 2026-03-31, a `group_run` cycle was submitted with the `build` request profile targeting a full-stack FastAPI + React MVP (PRD v0.3, ~470 lines of detailed requirements). The `development.develop` task ran for **22 seconds**, produced 3 Python files (80 lines total, backend only), and returned `success=True`. No React frontend was generated. No correction protocol fired. The run completed as "successful."

The PRD explicitly required:
- FastAPI backend with 5 endpoints
- React (Vite) frontend with 3 views
- Backend tests
- QA handoff artifact

The handler produced approximately 15% of the required output and declared victory.

### 2.2 Root Cause Chain

The failure is a four-link chain where each link depends on the previous:

1. **Single-pass execution** — `DevelopmentDevelopHandler.handle()` (`cycle_tasks.py:519–678`) makes exactly one `chat_stream_with_usage()` call. There is no iteration, re-query, or follow-up. A shallow or truncated LLM response becomes the final output.

2. **Mechanical success criteria** — The handler's only completeness check is whether `extract_fenced_files()` returns a non-empty list (`cycle_tasks.py:623`). If the LLM produces even one fenced code block, the handler returns `success=True`. There is no validation against the PRD, the implementation plan, or the expected artifact types.

3. **No `outcome_class` emission** — Build handlers never set `outcome_class` in their output dict. The `TaskOutcome` constants (`task_outcome.py:10–22`) — `SUCCESS`, `RETRYABLE_FAILURE`, `SEMANTIC_FAILURE`, `NEEDS_REPAIR`, `NEEDS_REPLAN` — exist but are never referenced by any handler.

4. **Correction protocol never activates** — `_handle_task_outcome()` (`distributed_flow_executor.py:1153–1238`) reads `outcome_class` from handler outputs. When it's absent and the task succeeded, the D5 fallback table classifies it as success. The correction protocol (`_run_correction_protocol()`, lines 1656–1899), repair tasks (`development.repair`, `qa.validate_repair`), and plan deltas are never triggered.

**Result:** The full SIP-0079 correction infrastructure — outcome classification, retry limits, correction protocol, repair tasks, plan deltas, checkpoint/resume — is implemented and passing tests, but is unreachable from normal execution because handlers never emit failure signals for incomplete work.

### 2.3 The Structural Problem: Static Task Plans

Even if handlers validated perfectly and the correction protocol fired, the architecture has a deeper issue: **the task planner does not decompose work.**

`generate_task_plan()` (`task_plan.py:209–293`) selects from hardcoded step lists:

```python
BUILD_TASK_STEPS = [
    ("development.develop", "dev"),   # One task for ALL development
    ("qa.test", "qa"),                # One task for ALL testing
]
```

For the `build` profile, the planning phase produces 5 tasks (strategy, design, validate, report, review) and the build phase produces **2 tasks**. The entire development effort — backend models, API endpoints, frontend shell, React components, integration config, tests — is compressed into a single `development.develop` envelope sent to Neo.

This is asking one LLM call to do the work of a dozen focused calls. Even with perfect validation and correction, the system would cycle between "attempt everything → fail validation → correct → attempt everything again" rather than making incremental progress.

**What's needed:** The planning phase should produce a **build task manifest** — an ordered list of focused subtasks — and the executor should expand that manifest into multiple `development.develop` envelopes, each building on the artifacts of the previous one.

### 2.4 Scope of Impact

This affects three layers:

| Layer | Component | Issue |
|-------|-----------|-------|
| **Task planning** | `generate_task_plan()` in `task_plan.py` | Static step lists; no PRD-aware decomposition |
| **Build handlers** | `DevelopmentDevelopHandler`, `QATestHandler` in `cycle_tasks.py` | Single LLM call, no output validation, always succeeds if code blocks exist |
| **Correction routing** | `_handle_task_outcome()` in `distributed_flow_executor.py` | Correction protocol never activates because handlers never emit failure signals |

Planning handlers (`strategy.analyze_prd`, `governance.review`) are not directly affected but `governance.review` gains a new responsibility: producing the build task manifest.

---

## 3. Design Principles

### 3.1 Validate at the handler, not the executor

The handler has the semantic context (PRD, implementation plan, prior artifacts) needed to judge output quality. The executor manages flow control and correction routing. Output validation belongs in the handler; correction decisions belong in the executor. This preserves SIP-0079's separation: "Prefect owns attempts, SquadOps owns intent."

### 3.2 Graduated response

Not every incomplete output requires the full correction protocol. A handler should attempt self-correction first (re-query the LLM) before escalating to `SEMANTIC_FAILURE`. This avoids burning correction budget on problems a follow-up prompt can fix.

### 3.3 Observable, not opaque

Every validation decision — what was checked, what failed, what was attempted — must be captured in handler evidence so operators can diagnose false positives and tune thresholds.

### 3.4 Profile-configurable

Validation strictness and self-evaluation passes should be controllable via `applied_defaults` so operators can tune behavior per cycle without code changes. Short selftest cycles may skip self-evaluation; 1-hour build cycles should use it.

### 3.5 Decompose at planning time, not build time

Work decomposition is a planning decision, not a runtime decision. Max (lead) decomposes the build during the planning phase when the full PRD and design plan are available. The executor consumes the manifest; it does not invent tasks. This keeps the executor deterministic and the planning phase auditable.

### 3.6 Incremental artifact accumulation

Each subtask receives all artifacts from prior subtasks. The first subtask starts from the PRD and design plan; the fifth subtask starts from the PRD, design plan, and four prior subtasks' outputs. This is how the existing artifact chain works (`prior_outputs`, `artifact_contents` in `_enrich_envelope()`). Decomposition leverages it rather than inventing a new mechanism.

### 3.7 Backward compatible

Handlers that do not opt into validation continue to work as before. Existing profiles without validation keys produce the current behavior. When no build task manifest is present, `generate_task_plan()` falls back to the current static step lists. No breaking changes to the TaskResult, HandlerResult, or TaskEnvelope contracts.

---

## 4. Goals

1. **Dynamic build task decomposition** — Max produces a build task manifest during planning that decomposes the build into focused subtasks. The executor expands this manifest into multiple `development.develop` and `qa.test` envelopes.
2. **Fill the timebox** — A 1-hour cycle targeting a full-stack app generates 8–15 focused build tasks, not 2. Each task makes incremental progress, accumulating artifacts across the sequence.
3. **Output validation** — Build handlers validate output completeness against the PRD and their subtask scope before returning success.
4. **Correction protocol activation** — Handlers emit `outcome_class: SEMANTIC_FAILURE` when validation fails, activating the SIP-0079 correction protocol for the first time.
5. **Self-evaluation pass** — Handlers support an optional second LLM call to self-correct before escalating to the correction protocol.
6. **Profile-configurable** — Decomposition depth, validation strictness, and self-evaluation are controllable via `applied_defaults`.
7. **Observable** — All decomposition decisions, validation results, and self-evaluation attempts are recorded in evidence and artifacts.

---

## 5. Non-Goals

- Changing the correction protocol itself (SIP-0079 scope).
- Adding handler-level multi-turn conversation loops (agentic iteration). Self-evaluation is a single follow-up pass, not an unbounded loop.
- Validating code correctness by executing it (sandbox execution is a future SIP).
- Modifying the planning task step sequence (strategy, design, validate, report, review remain unchanged).
- Agentic task creation at runtime — the manifest is produced at planning time and fixed at gate approval.

---

## 6. Design

### 6.1 Dynamic Build Task Decomposition

#### 6.1.1 Overview

The planning phase currently ends with `governance.review` (Max), which produces a governance review document and triggers the plan-review gate. This SIP extends `governance.review` to also produce a **build task manifest** — a structured artifact that decomposes the upcoming build into focused subtasks.

After the gate is approved, `generate_task_plan()` reads the manifest and expands it into multiple `development.develop` and `qa.test` envelopes instead of using the hardcoded `BUILD_TASK_STEPS`.

```
CURRENT FLOW:
  Planning: strategy → design → validate → report → review → [GATE]
  Build:    development.develop (1 task) → qa.test (1 task)

PROPOSED FLOW:
  Planning: strategy → design → validate → report → review (+ manifest) → [GATE]
  Build:    dev.develop #1 → dev.develop #2 → ... → dev.develop #N → qa.test #1 → ... → qa.test #M
            (each focused on a specific component, each receiving prior artifacts)
```

#### 6.1.2 Build Task Manifest Schema

The manifest is a structured artifact produced by the `governance.review` handler (Max) and stored in the artifact vault. It is a YAML document with the following schema:

```yaml
# build_task_manifest.yaml
version: 1
project_id: group_run
cycle_id: cyc_xxx
prd_hash: sha256_of_prd_content

# Ordered list of build subtasks
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend data models and in-memory repository"
    description: |
      Create Pydantic models for RunEvent and Participant.
      Implement in-memory repository with CRUD operations.
      Include __init__.py with model exports.
    expected_artifacts:
      - "backend/models.py"
      - "backend/repository.py"
      - "backend/__init__.py"
    depends_on: []  # No prior build artifacts needed

  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend API endpoints"
    description: |
      Create FastAPI app with 5 endpoints: GET /runs, POST /runs,
      GET /runs/{id}, POST /runs/{id}/join, POST /runs/{id}/leave.
      Wire to repository. Add validation and error responses.
    expected_artifacts:
      - "backend/main.py"
      - "backend/routes.py"
    depends_on: [0]  # Needs models and repository

  - task_index: 2
    task_type: development.develop
    role: dev
    focus: "Frontend shell and routing"
    description: |
      Create React (Vite) project structure. Set up React Router
      with routes for list, create, and detail views. Create App
      shell component.
    expected_artifacts:
      - "frontend/package.json"
      - "frontend/index.html"
      - "frontend/src/App.jsx"
      - "frontend/src/main.jsx"
    depends_on: []  # Independent of backend artifacts

  - task_index: 3
    task_type: development.develop
    role: dev
    focus: "Frontend components — list and create views"
    description: |
      Implement RunsList component (fetches GET /runs, displays list).
      Implement CreateRun component (form, POST /runs).
      Wire to backend API via fetch().
    expected_artifacts:
      - "frontend/src/components/RunsList.jsx"
      - "frontend/src/components/CreateRun.jsx"
    depends_on: [1, 2]  # Needs API contract and frontend shell

  - task_index: 4
    task_type: development.develop
    role: dev
    focus: "Frontend components — detail view with join/leave"
    description: |
      Implement RunDetail component (fetches GET /runs/{id}).
      Add join form (POST /runs/{id}/join) and leave action
      (POST /runs/{id}/leave). Handle duplicate-name error display.
    expected_artifacts:
      - "frontend/src/components/RunDetail.jsx"
    depends_on: [1, 2]  # Needs API contract and frontend shell

  - task_index: 5
    task_type: development.develop
    role: dev
    focus: "Integration configuration"
    description: |
      Add CORS middleware to FastAPI backend.
      Add Vite proxy config or document startup instructions.
      Create requirements.txt for backend.
    expected_artifacts:
      - "backend/requirements.txt"
      - "frontend/vite.config.js"
    depends_on: [1, 2]  # Needs both backend and frontend structure

  - task_index: 6
    task_type: qa.test
    role: qa
    focus: "Backend API tests"
    description: |
      Write pytest tests for all 5 endpoints.
      Cover happy path, validation errors, not-found, and
      duplicate participant name rejection.
    expected_artifacts:
      - "tests/test_api.py"
    depends_on: [0, 1]  # Needs backend implementation

  - task_index: 7
    task_type: qa.test
    role: qa
    focus: "QA handoff artifact"
    description: |
      Produce qa_handoff.md with: how to run backend, how to run
      frontend, how to test, expected behavior, implemented scope,
      known limitations.
    expected_artifacts:
      - "qa_handoff.md"
    depends_on: [0, 1, 2, 3, 4, 5, 6]  # Needs full picture

# Metadata for the executor
summary:
  total_dev_tasks: 6
  total_qa_tasks: 2
  total_tasks: 8
  estimated_layers: [backend, frontend, test, config]
```

#### 6.1.3 Manifest Production — GovernanceReviewHandler Extension

The `governance.review` handler (Max) currently produces a governance review document. This SIP extends it to also produce the build task manifest when `build_tasks` is enabled in the cycle config.

Max receives the full planning context: the PRD, strategy analysis, design plan, validation plan, and data report. He uses this to decompose the build into focused subtasks.

**Prompt extension for governance.review:**

```
In addition to your governance review, produce a build task manifest that decomposes
the upcoming build into focused subtasks. Each subtask should:

1. Have a clear, narrow focus (e.g., "Backend data models" not "Build the app")
2. List the specific files it should produce
3. Declare dependencies on prior subtasks
4. Be completable in a single focused LLM generation (~2-10 minutes)

Decomposition guidelines:
- Separate backend and frontend into distinct tasks
- Separate models/data from API endpoints/routes
- Separate UI shell/routing from individual view components
- Put integration config (CORS, proxy, requirements) in its own task
- Put tests after the code they test
- Put QA handoff last

Output the manifest as a YAML code block with filename: build_task_manifest.yaml
```

The manifest is extracted via `extract_fenced_files()` (same mechanism as code artifacts), validated against the schema, and stored as a `document` type artifact.

#### 6.1.4 Manifest Consumption — generate_task_plan() Extension

`generate_task_plan()` is extended to check for a build task manifest in the cycle's artifacts before falling back to static step lists:

```python
def generate_task_plan(cycle: Cycle, run: Run, profile: SquadProfile,
                       manifest: BuildTaskManifest | None = None) -> list[TaskEnvelope]:
    """Generate a task plan for a cycle run.
    
    When a build task manifest is provided (from governance.review),
    expands manifest tasks into envelopes instead of using static
    BUILD_TASK_STEPS. Falls back to static steps when no manifest exists.
    """
    # ... existing workload type / legacy resolution ...
    
    if manifest is not None and include_build:
        # Replace static build steps with manifest-derived steps
        build_steps = [
            (task.task_type, task.role)
            for task in manifest.tasks
        ]
        # Replace BUILD_TASK_STEPS in the step list
        steps = [s for s in steps if s not in BUILD_TASK_STEPS]
        steps.extend(build_steps)
```

Each manifest task becomes a `TaskEnvelope` with:
- `task_type`: from manifest (e.g., `development.develop`)
- `inputs.subtask_focus`: the `focus` field from the manifest
- `inputs.subtask_description`: the `description` field
- `inputs.expected_artifacts`: the expected file list
- `inputs.subtask_index`: position in the manifest
- Standard lineage fields (correlation_id, causation_id chained to previous task)

#### 6.1.5 Handler Prompt Adaptation

When `DevelopmentDevelopHandler` receives a task with `subtask_focus` in its inputs, it adapts the prompt:

```python
# In _build_user_prompt()
subtask_focus = inputs.get("subtask_focus")
subtask_desc = inputs.get("subtask_description")
expected_files = inputs.get("expected_artifacts", [])

if subtask_focus:
    # Focused prompt — build only this component
    prompt = (
        f"## Build Task: {subtask_focus}\n\n"
        f"{subtask_desc}\n\n"
        f"### Expected Output Files\n"
        + "\n".join(f"- `{f}`" for f in expected_files) + "\n\n"
        f"### Context\n"
        f"PRD:\n{prd}\n\n"
    )
    if prior_artifacts:
        prompt += (
            f"### Prior Artifacts (already built — do not reproduce)\n"
            + "\n".join(
                f"**{name}:**\n```\n{content}\n```"
                for name, content in prior_artifacts.items()
            )
        )
    prompt += (
        "\n\nProduce ONLY the files listed in Expected Output Files. "
        "Use fenced code blocks with ```language:path/to/file``` format. "
        "Do not reproduce files from prior artifacts."
    )
else:
    # Legacy monolithic prompt (unchanged)
    prompt = self._build_legacy_user_prompt(context, prd, prior_outputs, ...)
```

This is critical: focused prompts produce better output than monolithic "build everything" prompts because the LLM can concentrate its context window on one component at a time.

#### 6.1.6 Executor: Manifest Loading After Gate Approval

After a gate is approved and the executor resumes, it loads the manifest from the run's artifacts:

```python
# In _execute_sequential(), after gate approval resumes execution

# Check for build task manifest in collected artifacts
manifest = None
for art_id, art_ref in stored_artifacts:
    if art_ref.filename == "build_task_manifest.yaml":
        content = await self._artifact_vault.fetch(art_id)
        manifest = BuildTaskManifest.from_yaml(content)
        break

if manifest:
    # Regenerate task plan with manifest
    remaining_envelopes = generate_task_plan(cycle, run, profile, manifest=manifest)
    # Filter out already-completed tasks
    remaining_envelopes = [
        e for e in remaining_envelopes
        if e.task_id not in completed_task_ids
    ]
```

#### 6.1.7 Manifest Validation

The manifest is validated at two points:

1. **At production time** (in `governance.review` handler): Schema validation ensures required fields are present, task_types are valid, role mappings exist in the squad profile, and dependency indices are valid.

2. **At consumption time** (in `generate_task_plan()`): Cross-validation ensures task_types map to registered handlers and agent_ids resolve in the profile.

```python
@dataclass
class BuildTaskManifest:
    version: int
    project_id: str
    cycle_id: str
    prd_hash: str
    tasks: list[ManifestTask]
    summary: ManifestSummary
    
    @classmethod
    def from_yaml(cls, content: str) -> BuildTaskManifest:
        """Parse and validate manifest from YAML string."""
        data = yaml.safe_load(content)
        # Validate version, required fields, dependency DAG (no cycles)
        ...
    
    def validate_against_profile(self, profile: SquadProfile) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        available_roles = {a.role for a in profile.agents if a.enabled}
        for task in self.tasks:
            if task.role not in available_roles:
                errors.append(f"Task {task.task_index}: role '{task.role}' not in profile")
        return errors
```

#### 6.1.8 Example: group_run Cycle With Decomposition

Replaying the 2026-03-31 cycle with this SIP:

**Planning phase** (unchanged timing):
1. `strategy.analyze_prd` (Nat) → strategy analysis
2. `development.design` (Neo) → implementation plan
3. `qa.validate` (Eve) → validation plan
4. `data.report` (Data) → data report
5. `governance.review` (Max) → governance review **+ build_task_manifest.yaml**

**Gate pause** — Operator reviews the manifest alongside the governance review. Can see exactly what the squad plans to build and in what order. Approves gate.

**Build phase** (manifest-driven, ~8 tasks instead of 2):
1. `development.develop` #0 (Neo) — Backend models + repository → `models.py`, `repository.py` (~3 min)
2. `development.develop` #1 (Neo) — Backend API endpoints → `main.py`, `routes.py` (~5 min)
3. `development.develop` #2 (Neo) — Frontend shell + routing → `package.json`, `App.jsx`, `main.jsx` (~3 min)
4. `development.develop` #3 (Neo) — Frontend list + create views → `RunsList.jsx`, `CreateRun.jsx` (~5 min)
5. `development.develop` #4 (Neo) — Frontend detail + join/leave → `RunDetail.jsx` (~5 min)
6. `development.develop` #5 (Neo) — Integration config → `requirements.txt`, `vite.config.js` (~2 min)
7. `qa.test` #0 (Eve) — Backend tests → `test_api.py` (~5 min)
8. `qa.test` #1 (Eve) — QA handoff → `qa_handoff.md` (~3 min)

**Total estimated build time: ~31 minutes** — well within a 1-hour timebox, with room for correction protocol if any subtask fails validation.

Each subtask receives artifacts from all prior subtasks via the existing `_enrich_envelope()` → `artifact_contents` mechanism. Task #4 (frontend detail view) can see the backend API from task #1 and the frontend shell from task #2.

#### 6.1.9 Fallback Behavior

When no manifest is present (legacy profiles, selftest, benchmark), `generate_task_plan()` falls back to the existing static `BUILD_TASK_STEPS`. This preserves backward compatibility with all current profiles.

The `build` and `implementation` profiles gain manifest support by default. The `selftest` and `benchmark` profiles do not produce manifests (no governance.review in their planning).

#### 6.1.10 Configuration Keys for Decomposition

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `build_manifest` | `bool` | `true` | Enable build task manifest production in `governance.review`. `false` = static step lists. |
| `max_build_subtasks` | `int` | `15` | Maximum subtasks in manifest. Prevents unbounded decomposition. |
| `min_build_subtasks` | `int` | `3` | Minimum subtasks. Forces decomposition for non-trivial builds. Manifest with fewer tasks is rejected and falls back to static steps. |

---

### 6.2 Output Validation Framework

Add a `_validate_output()` method to `_CycleTaskHandler` (base class for all cycle task handlers) that build handlers override to implement domain-specific validation.

```python
# In _CycleTaskHandler (base class)

@dataclass
class ValidationResult:
    """Outcome of handler output validation."""
    passed: bool
    checks: list[dict]          # Individual check results
    missing_components: list[str]  # What's absent
    coverage_ratio: float       # 0.0–1.0 estimated completeness
    summary: str                # Human-readable summary

async def _validate_output(
    self,
    context: ExecutionContext,
    inputs: dict[str, Any],
    artifacts: list[dict],
    raw_response: str,
) -> ValidationResult:
    """Validate handler output against requirements. Override in subclasses."""
    return ValidationResult(passed=True, checks=[], missing_components=[], 
                            coverage_ratio=1.0, summary="No validation configured")
```

### 6.3 DevelopmentDevelopHandler Validation

The `development.develop` handler validates output against three criteria:

#### Check 1: Required Component Coverage

Parse the PRD and implementation plan to identify required components. Compare against generated artifacts.

```python
async def _validate_output(self, context, inputs, artifacts, raw_response):
    checks = []
    missing = []
    
    prd = inputs.get("prd", "")
    impl_plan = await self._resolve_with_vault_fallback(inputs, "implementation_plan")
    artifact_names = [a["name"] for a in artifacts]
    
    # C1: Stack coverage — does the output contain artifacts for each required stack layer?
    expected_layers = self._detect_expected_layers(prd, impl_plan)
    # e.g., {"backend": ["*.py", "main.py"], "frontend": ["*.jsx", "*.tsx", "*.html"], "config": ["requirements.txt", "package.json"]}
    
    present_layers = set()
    for name in artifact_names:
        for layer, patterns in expected_layers.items():
            if any(fnmatch(name, p) or name.endswith(tuple(exts)) for p, exts in patterns):
                present_layers.add(layer)
    
    missing_layers = set(expected_layers.keys()) - present_layers
    if missing_layers:
        missing.extend(f"stack_layer:{layer}" for layer in missing_layers)
    
    checks.append({
        "check": "stack_coverage",
        "expected": list(expected_layers.keys()),
        "present": list(present_layers),
        "missing": list(missing_layers),
        "passed": len(missing_layers) == 0,
    })
```

#### Check 2: Artifact Count Threshold

A full-stack app requires a minimum number of files. A 3-file output for a PRD requesting 5 endpoints + 3 views + tests is obviously incomplete.

```python
    # C2: Minimum artifact count — heuristic based on PRD complexity
    min_artifacts = self._estimate_min_artifacts(prd, impl_plan)
    checks.append({
        "check": "artifact_count",
        "expected_min": min_artifacts,
        "actual": len(artifacts),
        "passed": len(artifacts) >= min_artifacts,
    })
```

#### Check 3: Structural Completeness

For each generated file, check that it's not a stub (e.g., empty `__init__.py` files are fine, but a 74-byte `board.py` with only a comment is not).

```python
    # C3: Non-stub files — files beyond boilerplate must have meaningful content
    stub_threshold_bytes = 100  # Files below this are checked for stub patterns
    stub_patterns = ["# This file is kept empty", "# TODO", "pass\n", "# placeholder"]
    
    stubs = []
    for art in artifacts:
        content = art.get("content", "")
        name = art["name"]
        if len(content) < stub_threshold_bytes and not name.endswith("__init__.py"):
            if any(pat in content for pat in stub_patterns) or not content.strip():
                stubs.append(name)
    
    checks.append({
        "check": "non_stub_files",
        "stubs_found": stubs,
        "passed": len(stubs) == 0,
    })
```

#### Validation Decision

```python
    # Compute coverage ratio
    passed_count = sum(1 for c in checks if c["passed"])
    coverage_ratio = passed_count / len(checks) if checks else 1.0
    
    # Validation passes only if all checks pass
    passed = all(c["passed"] for c in checks)
    
    summary_parts = []
    if missing_layers:
        summary_parts.append(f"Missing stack layers: {', '.join(missing_layers)}")
    if stubs:
        summary_parts.append(f"Stub files: {', '.join(stubs)}")
    if len(artifacts) < min_artifacts:
        summary_parts.append(f"Only {len(artifacts)} artifacts, expected >= {min_artifacts}")
    
    return ValidationResult(
        passed=passed,
        checks=checks,
        missing_components=missing,
        coverage_ratio=coverage_ratio,
        summary="; ".join(summary_parts) or "All checks passed",
    )
```

### 6.4 QATestHandler Validation

The `qa.test` handler validates:

1. **Test file presence** — At least one test file with actual test functions (not just imports).
2. **Coverage of source artifacts** — Test files should reference or import the source files from the prior `development.develop` step.
3. **Test report presence** — If a test report artifact is produced, check it contains actual pass/fail results, not just a template.

### 6.5 Self-Evaluation Pass

Before returning `SEMANTIC_FAILURE`, a handler may attempt one self-correction pass — a second LLM call that provides the validation failures as context and asks the model to complete the missing components.

```python
# In _CycleTaskHandler.handle() — after initial LLM call and validation

validation = await self._validate_output(context, inputs, artifacts, raw_response)

if not validation.passed:
    # Check if self-evaluation is enabled and budget remains
    max_self_eval = resolved_config.get("max_self_eval_passes", 1)
    self_eval_count = 0
    
    while not validation.passed and self_eval_count < max_self_eval:
        self_eval_count += 1
        
        # Build follow-up prompt with validation feedback
        followup_prompt = self._build_self_eval_prompt(
            original_prompt=user_prompt,
            validation=validation,
            prior_response=raw_response,
            artifacts=artifacts,
        )
        
        # Second LLM call
        followup_response = await context.ports.llm.chat_stream_with_usage(
            [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
                ChatMessage(role="assistant", content=raw_response),
                ChatMessage(role="user", content=followup_prompt),
            ],
            **chat_kwargs,
        )
        
        # Merge new artifacts with existing
        new_extracted = extract_fenced_files(followup_response.content)
        artifacts = self._merge_artifacts(artifacts, new_extracted)
        raw_response = followup_response.content
        
        # Re-validate
        validation = await self._validate_output(context, inputs, artifacts, raw_response)
    
    # Record self-evaluation evidence
    evidence["self_eval_passes"] = self_eval_count
    evidence["self_eval_final_validation"] = asdict(validation)
```

#### Self-Evaluation Prompt Structure

```python
def _build_self_eval_prompt(self, original_prompt, validation, prior_response, artifacts):
    artifact_names = [a["name"] for a in artifacts]
    return (
        "Your previous response was incomplete. Here is what's missing:\n\n"
        f"**Validation Summary:** {validation.summary}\n\n"
        f"**Missing Components:** {', '.join(validation.missing_components)}\n\n"
        f"**Files You Already Produced:** {', '.join(artifact_names)}\n\n"
        "Please produce ONLY the missing files. Use the same fenced code block format "
        "(```language:path/to/file```). Do not reproduce files you already generated."
    )
```

### 6.6 Outcome Classification Wiring

After validation (and optional self-evaluation), the handler classifies the outcome:

```python
# After validation and self-eval exhausted

if validation.passed:
    outputs["outcome_class"] = TaskOutcome.SUCCESS
    return HandlerResult(success=True, outputs=outputs, _evidence=evidence)
else:
    outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE
    outputs["failure_classification"] = FailureClassification.WORK_PRODUCT
    outputs["validation_result"] = {
        "checks": validation.checks,
        "missing_components": validation.missing_components,
        "coverage_ratio": validation.coverage_ratio,
        "summary": validation.summary,
    }
    evidence["validation_result"] = outputs["validation_result"]
    
    return HandlerResult(
        success=False,
        outputs=outputs,
        _evidence=evidence,
        error=f"Output validation failed: {validation.summary}",
    )
```

This causes `_handle_task_outcome()` in the executor to:
1. Read `outcome_class = SEMANTIC_FAILURE`
2. Skip retry (semantic failures are not retryable)
3. Call `_run_correction_protocol()` with the failure evidence
4. Correction protocol dispatches `data.analyze_failure` → `governance.correction_decision`
5. If decision is `patch`: dispatch `development.repair` + `qa.validate_repair`

### 6.7 Artifact Merge Strategy

When self-evaluation produces additional files, they must be merged with the original output:

```python
def _merge_artifacts(self, existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge new artifacts into existing, replacing files with same name."""
    by_name = {a["name"]: a for a in existing}
    for art in new:
        by_name[art["name"]] = art  # New version replaces old
    return list(by_name.values())
```

### 6.8 Stack Layer Detection

The `_detect_expected_layers()` method parses the PRD for technology stack indicators:

```python
_STACK_INDICATORS = {
    "backend": {
        "keywords": ["fastapi", "flask", "django", "uvicorn", "backend", "api endpoint"],
        "extensions": [".py"],
        "marker_files": ["main.py", "app.py", "server.py", "requirements.txt"],
    },
    "frontend": {
        "keywords": ["react", "vue", "vite", "frontend", "jsx", "tsx", "component"],
        "extensions": [".jsx", ".tsx", ".js", ".ts", ".html", ".css"],
        "marker_files": ["package.json", "index.html", "App.jsx", "App.tsx"],
    },
    "test": {
        "keywords": ["pytest", "test", "jest", "vitest"],
        "extensions": [".py", ".js", ".ts"],
        "marker_files": ["test_*.py", "*.test.js", "*.test.ts"],
    },
    "config": {
        "keywords": ["requirements.txt", "package.json", "dockerfile", "docker-compose"],
        "extensions": [".txt", ".json", ".yaml", ".yml", ".toml"],
        "marker_files": ["requirements.txt", "package.json", "pyproject.toml"],
    },
}

def _detect_expected_layers(self, prd: str, impl_plan: str | None) -> dict[str, list[str]]:
    """Detect required stack layers from PRD and implementation plan text."""
    combined = (prd + "\n" + (impl_plan or "")).lower()
    expected = {}
    for layer, indicators in self._STACK_INDICATORS.items():
        if any(kw in combined for kw in indicators["keywords"]):
            expected[layer] = indicators["extensions"]
    return expected
```

### 6.9 Configuration Keys

Add to `_APPLIED_DEFAULTS_EXTRA_KEYS` in `schema.py`:

**Decomposition keys (§6.1):**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `build_manifest` | `bool` | `true` | Enable build task manifest production in `governance.review` |
| `max_build_subtasks` | `int` | `15` | Maximum subtasks in manifest |
| `min_build_subtasks` | `int` | `3` | Minimum subtasks; manifest below this is rejected |

**Validation keys (§6.2–6.5):**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output_validation` | `bool` | `true` | Enable output validation in build handlers |
| `max_self_eval_passes` | `int` | `1` | Max self-evaluation LLM calls before escalating. `0` disables. |
| `min_artifact_count` | `int \| None` | `None` | Override automatic minimum artifact count estimation. `None` = auto-detect. |
| `stub_threshold_bytes` | `int` | `100` | Files below this size (excluding `__init__.py`) are checked for stub patterns |

#### Profile Examples

**`build` profile (updated):**
```yaml
defaults:
  build_manifest: true
  output_validation: true
  max_self_eval_passes: 1
  max_build_subtasks: 12
```

**`implementation` profile (updated):**
```yaml
defaults:
  build_manifest: true
  output_validation: true
  max_self_eval_passes: 2
  max_build_subtasks: 15
  max_correction_attempts: 2
  time_budget_seconds: 7200
```

**`selftest` profile (unchanged):**
```yaml
defaults:
  build_manifest: false
  output_validation: false
```

---

## 7. Expected Behavior: group_run Cycle With This SIP

Replaying the 2026-03-31 cycle with this SIP active:

### Planning Phase (~10 minutes, unchanged)
1. `strategy.analyze_prd` (Nat) → strategy analysis
2. `development.design` (Neo) → implementation plan
3. `qa.validate` (Eve) → validation plan
4. `data.report` (Data) → data report
5. `governance.review` (Max) → governance review + **build_task_manifest.yaml** (8 subtasks)

### Gate Pause
Operator reviews the manifest. Sees the decomposition: 6 dev tasks (backend models, API, frontend shell, list/create views, detail view, integration config) + 2 QA tasks (backend tests, QA handoff). Approves gate.

### Build Phase (~35 minutes, manifest-driven)
1. **dev.develop #0** — "Backend models + repository" → Neo produces `models.py`, `repository.py`, `__init__.py`. Validation checks: subtask expected_artifacts present? Non-stub? → **Pass**. Checkpoint.
2. **dev.develop #1** — "Backend API endpoints" → Neo receives prior artifacts, produces `main.py`, `routes.py`. Validation: expected files present, imports `models.py` correctly → **Pass**. Checkpoint.
3. **dev.develop #2** — "Frontend shell + routing" → Neo produces `package.json`, `App.jsx`, `main.jsx`, `index.html`. → **Pass**. Checkpoint.
4. **dev.develop #3** — "Frontend list + create views" → Neo receives backend API + frontend shell, produces `RunsList.jsx`, `CreateRun.jsx` with `fetch()` calls to correct endpoints. → **Pass**. Checkpoint.
5. **dev.develop #4** — "Frontend detail + join/leave" → Produces `RunDetail.jsx`. Self-eval fires because join form is missing error handling. Follow-up prompt adds duplicate-name error display. → **Pass after self-eval**. Checkpoint.
6. **dev.develop #5** — "Integration config" → Produces `requirements.txt`, `vite.config.js` with CORS proxy. → **Pass**. Checkpoint.
7. **qa.test #0** — "Backend tests" → Eve produces `test_api.py` covering all 5 endpoints + validation errors. → **Pass**. Checkpoint.
8. **qa.test #1** — "QA handoff" → Eve produces `qa_handoff.md` with startup instructions, test commands, scope summary. → **Pass**. Checkpoint.

### Run Completes
- **Total build artifacts:** ~15 files across backend, frontend, tests, config
- **Total build time:** ~35 minutes (vs. 22 seconds previously)
- **Correction protocol:** Not needed (self-eval handled the one partial output)
- **If subtask #4 had failed validation even after self-eval:** Handler emits `SEMANTIC_FAILURE` → correction protocol fires → Data analyzes → Max decides `patch` → `development.repair` produces fixed `RunDetail.jsx` → `qa.validate_repair` confirms fix → resume at subtask #5

**Net effect:** The cycle fills the timebox with incremental, focused work. Each subtask builds on prior artifacts. Validation catches incomplete output early. The correction protocol is available as a safety net but rarely needed because focused prompts produce better output than monolithic ones.

---

## 8. Implementation Plan

### Phase 1: Build Task Manifest Model & Schema

| Step | File | Change |
|------|------|--------|
| 1a | `src/squadops/cycles/build_manifest.py` (new) | `BuildTaskManifest`, `ManifestTask`, `ManifestSummary` dataclasses with `from_yaml()` parser and `validate_against_profile()` |
| 1b | `src/squadops/cycles/build_manifest.py` | YAML schema validation, dependency DAG cycle detection, subtask count bounds |
| 1c | `schema.py` | Add `build_manifest`, `max_build_subtasks`, `min_build_subtasks` to `_APPLIED_DEFAULTS_EXTRA_KEYS` |

### Phase 2: Manifest Production (governance.review)

| Step | File | Change |
|------|------|--------|
| 2a | `cycle_tasks.py` | Extend `GovernanceReviewHandler` prompt to request build task manifest when `build_manifest: true` |
| 2b | `cycle_tasks.py` | Extract manifest YAML from fenced response, validate, store as artifact |
| 2c | `cycle_tasks.py` | Fallback: if manifest extraction fails or is below `min_build_subtasks`, log warning and continue without manifest (executor falls back to static steps) |

### Phase 3: Manifest Consumption (task planner + executor)

| Step | File | Change |
|------|------|--------|
| 3a | `task_plan.py` | Add `manifest` parameter to `generate_task_plan()`. When present, expand manifest tasks into envelopes replacing static `BUILD_TASK_STEPS` |
| 3b | `task_plan.py` | Populate `subtask_focus`, `subtask_description`, `expected_artifacts`, `subtask_index` in envelope inputs |
| 3c | `distributed_flow_executor.py` | After gate approval, load manifest from artifact vault and pass to `generate_task_plan()` for remaining build tasks |
| 3d | `distributed_flow_executor.py` | Ensure `_enrich_envelope()` includes artifacts from all prior subtasks (existing mechanism, verify it works with N subtasks) |

### Phase 4: Handler Prompt Adaptation

| Step | File | Change |
|------|------|--------|
| 4a | `cycle_tasks.py` | In `DevelopmentDevelopHandler._build_user_prompt()`, detect `subtask_focus` in inputs and switch to focused prompt |
| 4b | `cycle_tasks.py` | In `QATestHandler._build_user_prompt()`, detect `subtask_focus` and scope test generation to specific source artifacts |
| 4c | `cycle_tasks.py` | Preserve legacy monolithic prompt path when no `subtask_focus` present |

### Phase 5: Output Validation Framework

| Step | File | Change |
|------|------|--------|
| 5a | `cycle_tasks.py` | Add `ValidationResult` dataclass and `_validate_output()` base method to `_CycleTaskHandler` |
| 5b | `cycle_tasks.py` | Implement `_validate_output()` in `DevelopmentDevelopHandler` — when `subtask_focus` present, validate against `expected_artifacts`; when absent, validate against PRD stack layers (C1/C2/C3 checks) |
| 5c | `cycle_tasks.py` | Implement `_validate_output()` in `QATestHandler` with test-specific checks |
| 5d | `cycle_tasks.py` | Wire validation call in `handle()` after `extract_fenced_files()` |

### Phase 6: Outcome Classification Wiring

| Step | File | Change |
|------|------|--------|
| 6a | `cycle_tasks.py` | Import `TaskOutcome`, `FailureClassification` in handler module |
| 6b | `cycle_tasks.py` | Set `outputs["outcome_class"]` based on validation result |
| 6c | `cycle_tasks.py` | Set `outputs["failure_classification"]` for failed validations |
| 6d | `cycle_tasks.py` | Include `validation_result` in outputs and evidence |

### Phase 7: Self-Evaluation Pass

| Step | File | Change |
|------|------|--------|
| 7a | `cycle_tasks.py` | Add `_build_self_eval_prompt()` to `_CycleTaskHandler` |
| 7b | `cycle_tasks.py` | Add `_merge_artifacts()` to `_CycleTaskHandler` |
| 7c | `cycle_tasks.py` | Wire self-evaluation loop in `handle()` between validation failure and outcome classification |
| 7d | `cycle_tasks.py` | Record self-eval evidence (pass count, final validation) |

### Phase 8: Profile Updates

| Step | File | Change |
|------|------|--------|
| 8a | `profiles/build.yaml` | Add `build_manifest: true`, `output_validation: true`, `max_self_eval_passes: 1` |
| 8b | `profiles/implementation.yaml` | Add `build_manifest: true`, `output_validation: true`, `max_self_eval_passes: 2` |
| 8c | `profiles/selftest.yaml` | Add `build_manifest: false`, `output_validation: false` |
| 8d | `schema.py` | Add all new keys to `_APPLIED_DEFAULTS_EXTRA_KEYS` |

### Phase 9: Tests

| Step | What |
|------|------|
| 9a | Unit tests for `BuildTaskManifest.from_yaml()` — valid manifests, malformed YAML, dependency cycles, bounds violations |
| 9b | Unit tests for `generate_task_plan()` with manifest — verify correct envelope count, inputs, lineage chaining |
| 9c | Unit tests for `_validate_output()` with known-good and known-bad artifact sets (both focused and monolithic modes) |
| 9d | Unit tests for `_detect_expected_layers()` with various PRD texts |
| 9e | Unit tests for `_merge_artifacts()` |
| 9f | Integration test: `governance.review` produces valid manifest from PRD |
| 9g | Integration test: handler returns `SEMANTIC_FAILURE` when output is incomplete |
| 9h | Integration test: self-evaluation produces additional artifacts and re-validates |
| 9i | End-to-end: verify correction protocol activates on handler semantic failure |
| 9j | End-to-end: full cycle with manifest decomposition produces expected artifact count |

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Max produces a poor manifest** (wrong decomposition, missing components, bad dependencies) | Build phase executes wrong plan; wasted time budget | Gate pause lets operator review manifest before approving. Manifest validation rejects malformed YAML and dependency cycles. `min_build_subtasks` catches trivially shallow manifests. |
| **Manifest decomposition too granular** (20+ tiny tasks) | Overhead of task dispatch + artifact handoff dominates build time | `max_build_subtasks` (default 15) bounds this. Each task should target 2–10 minutes of LLM work. |
| **Manifest decomposition too coarse** (3 large tasks, same as current) | Doesn't solve the core problem; back to monolithic prompts | `min_build_subtasks` (default 3) rejects trivially shallow manifests. Prompt instructs Max to target component-level granularity. |
| **Later subtasks drift from earlier artifacts** (e.g., frontend uses wrong API paths) | Integration failures | Each subtask receives all prior artifacts via `_enrich_envelope()`. Focused prompts explicitly reference prior artifacts. |
| **Manifest YAML extraction fails** (LLM doesn't produce valid YAML) | No manifest available | Graceful fallback to static `BUILD_TASK_STEPS`. Warning logged. Operator can retry the planning phase. |
| **False positive validation failures** (valid output flagged as incomplete) | Unnecessary correction cycles | Conservative defaults; `output_validation: false` escape hatch; evidence logging for tuning |
| **Self-evaluation produces conflicting artifacts** | Merge overwrites correct files with worse versions | Merge replaces by filename only; operator can set `max_self_eval_passes: 0` to disable |
| **Correction protocol overwhelmed** by frequent semantic failures | Run exhausts correction budget quickly | Existing `max_correction_attempts` (default 2) bounds this; focused subtasks + self-eval reduce failure rate vs. monolithic tasks |
| **Increased token cost** per cycle (more LLM calls) | Higher compute spend | Focused prompts are smaller than monolithic prompts. Total tokens may be comparable. Self-eval bounded (default 1 pass). |

---

## 10. Future Work

- **Sandbox execution validation** — Run generated code in a container to verify it starts and passes tests. This would replace heuristic checks with empirical validation.
- **Agentic iteration loops** — Multi-turn handler conversations where the agent reasons about its own output across multiple exchanges. This SIP's self-evaluation is a stepping stone.
- **Cross-handler validation** — QA handler validates that its tests actually exercise the code from the dev handler, not just that test files exist.
- **Adaptive thresholds** — Learn minimum artifact counts and expected layers from successful past cycles instead of heuristic estimation.

---

## 11. References

- **SIP-0079** — Implementation Run Contract & Correction Protocol (defines correction protocol, outcome classification, checkpoint/resume)
- **SIP-0078** — Planning Workload Protocol (workload type branching, planning task steps)
- **SIP-0071** — Builder Role (builder-aware task routing)
- **SIP-0070** — Pulse Checks and Verification Framework (bounded pulse repair)
- **SIP-0068** — Enhanced Agent Build Capabilities (build handler architecture)
- **SIP-0066** — Distributed Cycle Execution Pipeline (task dispatch, sequential execution)
- `src/squadops/cycles/task_plan.py` — Static task plan generator (the component being extended)
- `src/squadops/capabilities/handlers/cycle_tasks.py` — Build handler implementations
- `src/squadops/cycles/task_outcome.py` — TaskOutcome and FailureClassification constants
- `adapters/cycles/distributed_flow_executor.py` — Correction protocol and sequential executor logic
