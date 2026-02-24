# Stack-Aware Development Capabilities — Implementation Plan

## Context

The build pipeline (SIP-0068 + SIP-0071) hardcodes Python-only behavior at every stage: the dev handler prompts for Python packages, `_EXT_MAP` only classifies `.py` as source, the QA handler filters on `.py` only, and `test_runner.py` only runs pytest. To build fullstack apps like `group_run` (FastAPI + React/Vite), each handler needs stack-aware prompting, file classification, and test execution.

The SIP at `sips/accepted/SIP-0072-Stack-Aware-Development-Capabilities.md` defines a `DevelopmentCapability` registry that controls handler behavior via a `dev_capability` key in `resolved_config`. This plan implements that SIP.

The pipeline shape is unchanged: `development.develop → builder.assemble → qa.test`. No new task types, no model changes. Stack awareness is purely registry-driven within existing handlers.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | `DevelopmentCapability` is a frozen dataclass in new file `src/squadops/capabilities/dev_capabilities.py`, analogous to `BuildProfile` in `build_profiles.py` | Same registry pattern; `get_capability()` mirrors `get_profile()`. Module is a capability registry consumed by handlers, not a handler itself — placed at `capabilities/` level, not `capabilities/handlers/` |
| D2 | `python_cli` capability reproduces current hardcoded behavior exactly — its `system_prompt_supplement` and `file_structure_guidance` contain the same text as lines 352–380 and 420–426 of `cycle_tasks.py` | Zero regression: absent `dev_capability` falls back to `python_cli` |
| D3 | Unknown `dev_capability` value raises `ValueError` in `get_capability()` — handler returns structured task failure with diagnostics | Same pattern as `get_profile()` in `build_profiles.py:152-170`; prevents silent wrong-stack output from typos |
| D4 | `test_file_patterns` field on `DevelopmentCapability` drives test exclusion via `fnmatch` + `__tests__/` path check | Replaces `not key.startswith("test_")` which is Python-only |
| D5 | `TEST_FRAMEWORK_PYTEST`, `TEST_FRAMEWORK_VITEST`, `TEST_FRAMEWORK_BOTH` are module-level string constants | Avoids string drift across registry, handlers, and tests |
| D6 | `run_node_tests()` accepts `target_dir` parameter, not just `workspace` | Fullstack projects have `package.json` in `frontend/`, not root |
| D7 | Frontend test execution is non-blocking — failures do not change run success/failure | Node.js may not be available in agent containers; test generation is required, execution is best-effort |
| D8 | `BuilderAssembleHandler._get_assembly_inputs()` extension list is static (not capability-driven) | Bob always needs to see all source and config files regardless of stack to produce correct packaging |
| D9 | `QATestHandler._build_user_prompt()` uses capability's `test_prompt_supplement` to select pytest vs vitest vs both | Replaces hardcoded pytest instructions |
| D10 | `QATestHandler` system prompt suffix uses `capability.test_prompt_supplement` instead of hardcoded pytest text | Mirrors D9 for the system prompt path |
| D11 | `DevelopmentDevelopHandler.handle()` stores `resolved_config` as `self._resolved_config` at the start, making it available to `_build_user_prompt()` without passing as a parameter | Single access pattern; consistent with how `BuilderAssembleHandler` already reads `resolved_config` |
| D12 | `run_fullstack_tests()` takes no `test_framework` parameter — it always runs both pytest and vitest | The function inherently means "run both stacks"; framework selection happens in the caller |
| D13 | Backend pytest result controls blocking pass/fail; frontend vitest result is recorded as non-blocking diagnostics | V1 merge policy: combined `TestRunResult` preserves both outputs but only backend failures flip overall result to failure |

---

## Phase 1: Development Capability Registry + File Classification

### 1.1 Development capability registry

**New file:** `src/squadops/capabilities/dev_capabilities.py`

```python
TEST_FRAMEWORK_PYTEST = "pytest"
TEST_FRAMEWORK_VITEST = "vitest"
TEST_FRAMEWORK_BOTH = "both"

@dataclass(frozen=True)
class DevelopmentCapability:
    name: str
    system_prompt_supplement: str
    file_structure_guidance: str
    example_structure: str
    expected_extensions: tuple[str, ...]
    test_framework: str
    test_prompt_supplement: str
    source_filter: tuple[str, ...]
    test_file_patterns: tuple[str, ...]

DEV_CAPABILITIES: dict[str, DevelopmentCapability] = { ... }

def get_capability(name: str) -> DevelopmentCapability:
    """Resolve capability by name. Raises ValueError if unknown."""
```

V1 registry entries:

| Name | `expected_extensions` | `test_framework` | `source_filter` | `test_file_patterns` |
|------|-----------------------|-------------------|-----------------|----------------------|
| `python_cli` | `(".py",)` | `TEST_FRAMEWORK_PYTEST` | `(".py",)` | `("test_*.py", "*_test.py")` |
| `python_api` | `(".py",)` | `TEST_FRAMEWORK_PYTEST` | `(".py",)` | `("test_*.py", "*_test.py")` |
| `react_app` | `(".js", ".jsx", ".html", ".css")` | `TEST_FRAMEWORK_VITEST` | `(".js", ".jsx")` | `("*.test.js", "*.test.jsx", "*.spec.js", "*.spec.jsx")` |
| `fullstack_fastapi_react` | `(".py", ".js", ".jsx", ".html", ".css")` | `TEST_FRAMEWORK_BOTH` | `(".py", ".js", ".jsx")` | union of Python + JS patterns |

The `python_cli` `system_prompt_supplement` and `file_structure_guidance` must reproduce the current hardcoded text from `DevelopmentDevelopHandler._build_user_prompt()` (lines 352–380) and `handle()` (lines 420–426) exactly — this is the zero-regression anchor (D2).

The `python_api` capability is similar but replaces `__init__.py`/`__main__.py`/relative imports guidance with FastAPI-specific guidance (`main.py`, `models.py`, `uvicorn`, `requirements.txt`). Note: `python_api` is included for immediate near-term use (standalone API projects) but is not exercised by the `group_run` fullstack validation scenario. A minimal unit test proving capability resolution and prompt selection is sufficient for V1 coverage.

The `react_app` capability provides React/Vite-specific guidance (ES module imports, `package.json` with react/vite deps, `vite.config.js`).

The `fullstack_fastapi_react` capability instructs Neo to produce two directory trees (`backend/` and `frontend/`) and includes guidance for both stacks. Its `example_structure` shows the concrete file tree from the SIP §5.2.

### 1.2 File classification expansion

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

Expand `_EXT_MAP` (line 232) with:

```python
".js":  ("source", "text/javascript"),
".jsx": ("source", "text/javascript"),
".ts":  ("source", "text/typescript"),
".tsx": ("source", "text/typescript"),
".mjs": ("source", "text/javascript"),
".css": ("source", "text/css"),
".html": ("source", "text/html"),
```

Note: `.ts`/`.tsx` classification is included as forward-compatible file handling only. TypeScript generation and test support are not required in V1 cycle success criteria. These entries ensure that if a model produces TypeScript files they are classified correctly rather than dropped, but no capability in V1 prompts for TypeScript output.

Expand `_FILENAME_MAP` (line 243) with:

```python
"package.json":    ("config", "application/json"),
"vite.config.js":  ("config", "text/javascript"),
"tsconfig.json":   ("config", "application/json"),
```

### 1.3 Schema key registration

**Modified file:** `src/squadops/contracts/cycle_request_profiles/schema.py`

Add `"dev_capability"` to `_APPLIED_DEFAULTS_EXTRA_KEYS` (line 20):

```python
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    "build_tasks", "plan_tasks", "pulse_checks", "cadence_policy",
    "build_profile", "dev_capability",
}
```

### 1.4 Phase 1 tests

**New file:** `tests/unit/capabilities/test_dev_capabilities.py`

- `get_capability("python_cli")` returns the default capability
- `get_capability("fullstack_fastapi_react")` returns fullstack capability
- `get_capability("python_api")` returns valid capability with FastAPI-specific prompt content
- `get_capability("nonexistent")` raises `ValueError` with available capabilities listed
- `DevelopmentCapability` is frozen (mutation raises `AttributeError`)
- All V1 capabilities have non-empty `system_prompt_supplement`, `source_filter`, `test_file_patterns`
- `python_cli` capability's `system_prompt_supplement` contains "Python package" (verifies D2 content match)
- `TEST_FRAMEWORK_*` constants are exported and used by all registry entries

**Modified file:** `tests/unit/capabilities/test_build_handlers.py`

- `_classify_file("app.js")` returns `("source", "text/javascript")`
- `_classify_file("App.jsx")` returns `("source", "text/javascript")`
- `_classify_file("styles.css")` returns `("source", "text/css")`
- `_classify_file("index.html")` returns `("source", "text/html")`
- `_classify_file("package.json")` returns `("config", "application/json")` (filename map)
- `_classify_file("vite.config.js")` returns `("config", "text/javascript")` (filename map)
- Existing `.py` classification unchanged

**New file:** `tests/unit/contracts/test_crp_schema_dev_capability.py`

- `"dev_capability"` is in `_APPLIED_DEFAULTS_EXTRA_KEYS`
- `CycleRequestProfile(name="x", defaults={"dev_capability": "fullstack_fastapi_react"})` does not raise
- Existing keys (`build_tasks`, `plan_tasks`, `build_profile`, etc.) still present

---

## Phase 2: Handler Stack Awareness

### 2.1 DevelopmentDevelopHandler

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

In `handle()`: Store `resolved_config` as `self._resolved_config` at the start of the method, before any other processing. This makes it available to `_build_user_prompt()` without passing as a parameter (D11).

In `_build_user_prompt()` (lines 352–380): Replace the hardcoded Python prompt block with capability-driven content:

```python
def _build_user_prompt(self, prd, prior_outputs, impl_plan=None, strategy=None):
    capability = get_capability(
        self._resolved_config.get("dev_capability", "python_cli")
    )
    parts = [f"## Product Requirements Document\n\n{prd}"]
    if impl_plan:
        parts.append(f"\n\n## Implementation Plan\n\n{impl_plan}")
    if strategy:
        parts.append(f"\n\n## Strategy Analysis\n\n{strategy}")
    if prior_outputs:
        parts.append("\n\n## Prior Analysis from Upstream Roles\n")
        for role, summary in prior_outputs.items():
            parts.append(f"### {role}\n{summary}\n")
    parts.append(capability.file_structure_guidance)
    parts.append(f"\n\nTarget file structure:\n{capability.example_structure}")
    return "\n".join(parts)
```

In `handle()` (lines 419–426): Replace hardcoded system prompt suffix:

```python
capability = get_capability(
    self._resolved_config.get("dev_capability", "python_cli")
)
system_prompt = (
    assembled.content
    + "\n\n" + capability.system_prompt_supplement
    + "\n\nEmit each file as a fenced code block: ```<lang>:<path>\n"
    "Paths must be clean relative paths with no colons or spaces."
)
```

### 2.2 QATestHandler

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

Add `_is_test_file()` helper (module-level):

```python
from fnmatch import fnmatch
from pathlib import PurePosixPath

def _is_test_file(path: str, patterns: tuple[str, ...]) -> bool:
    """V1 uses filename pattern matching via fnmatch plus a path-segment
    special case for __tests__/ (directory-based JS convention)."""
    name = PurePosixPath(path).name
    return any(fnmatch(name, pat) for pat in patterns) or "/__tests__/" in path
```

Replace `_get_source_artifacts()` (lines 602–609):

```python
def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
    capability = get_capability(
        inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
    )
    contents = inputs.get("artifact_contents", {})
    sources = {}
    for key, value in contents.items():
        if any(key.endswith(ext) for ext in capability.source_filter):
            if not _is_test_file(key, capability.test_file_patterns):
                sources[key] = value
    return sources
```

Replace `_build_user_prompt()` (lines 611–659): Use capability's `test_prompt_supplement` instead of hardcoded pytest instructions (D9). The source files section should use the correct language fence (not always `python`).

Replace system prompt suffix (lines 696–701) using capability's `test_prompt_supplement` (D10):

```python
capability = get_capability(
    inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
)
system_prompt = (
    assembled.content
    + "\n\n" + capability.test_prompt_supplement
    + "\nEmit each file as a fenced code block: ```<lang>:<path>\n"
    "Paths must be clean relative paths — no colons, no spaces."
)
```

### 2.3 BuilderAssembleHandler assembly inputs

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

Rename `BuilderAssembleHandler._get_source_artifacts()` to `_get_assembly_inputs()` (D8). The helper collects all files Bob needs for packaging context — source, config, and documentation — so the name should reflect that broader scope.

Expand the extension list (line 924–931) with JS/TS/HTML/CSS extensions (static, not capability-driven):

```python
def _get_assembly_inputs(self, inputs: dict[str, Any]) -> dict[str, str]:
    contents = inputs.get("artifact_contents", {})
    result = {}
    for key, value in contents.items():
        if key.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
                         ".mjs", ".txt", ".yaml", ".yml", ".toml", ".json", ".md")):
            result[key] = value
    return result
```

### 2.4 Phase 2 tests

**Modified file:** `tests/unit/capabilities/test_build_handlers.py`

DevelopmentDevelopHandler tests:
- With `resolved_config: {"dev_capability": "python_cli"}` → prompt contains "Python package" (existing behavior)
- With `resolved_config: {"dev_capability": "fullstack_fastapi_react"}` → prompt contains "backend/" and "frontend/", does NOT contain "__init__.py" or "python -m"
- With `resolved_config: {"dev_capability": "unknown_stack"}` → `result.success is False`, error contains "Unknown" and available capabilities
- Without `resolved_config` key → defaults to `python_cli` (backward compat)

QATestHandler tests:
- `_get_source_artifacts()` with `python_cli` capability: picks up `.py` files, excludes `test_*.py`
- `_get_source_artifacts()` with `fullstack_fastapi_react` capability: picks up `.py` AND `.jsx` files, excludes `App.test.jsx` and `test_api.py`
- `_is_test_file("tests/test_api.py", ("test_*.py",))` → `True`
- `_is_test_file("App.test.jsx", ("*.test.jsx",))` → `True`
- `_is_test_file("frontend/src/__tests__/App.test.jsx", ...)` → `True` (path check)
- `_is_test_file("App.jsx", ...)` → `False`
- System prompt contains "vitest" when capability is `react_app`

BuilderAssembleHandler tests:
- `_get_assembly_inputs()` picks up `.jsx`, `.html`, `.css`, `.md`, `.json` files (verify broad extension set)

---

## Phase 3: Test Runner + Build Profile + Cycle Request Profile

### 3.1 Test runner expansion

**Modified file:** `src/squadops/capabilities/handlers/test_runner.py`

Add `run_node_tests()`:

```python
async def run_node_tests(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    target_dir: str | None = None,
    timeout_seconds: int = 60,
) -> TestRunResult:
    """Run vitest in a Node workspace.

    Materializes files, runs npm install then npx vitest run.
    target_dir: subdirectory within workspace where package.json lives
    (e.g., "frontend" for fullstack projects).
    """
```

Implementation follows `run_generated_tests()` patterns:
- `tempfile.mkdtemp(prefix="qa_node_")`
- `_materialize_files()` for source + test files
- Resolve cwd: `workspace / target_dir` if provided, else `workspace`
- Check for `package.json` in cwd — if absent, return `TestRunResult(executed=False, error="No package.json found")`
- `npm install --no-audit --no-fund` (subprocess, timeout)
- `npx vitest run --reporter=verbose` (subprocess, timeout)
- Same stdout/stderr truncation (`_STDOUT_LIMIT`), timeout handling, cleanup
- Never raises — always returns `TestRunResult`

**V1 fallback semantics:** If Node/npm is unavailable (binary not found) or `npm install` fails (network error, dependency resolution failure), `run_node_tests()` returns `TestRunResult(executed=False, error="<diagnostic message>")` with a clear reason string. No retry loops, no alternate package manager attempts. The non-blocking policy (D7) ensures this does not fail the cycle.

Add `run_fullstack_tests()` orchestrator (D12):

```python
async def run_fullstack_tests(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> TestRunResult:
    """Run both pytest (backend) and vitest (frontend) tests.

    Splits files by path prefix (backend/ vs frontend/), runs both
    test suites, merges results per the V1 merge policy (D13).
    """
```

- Splits files by path prefix (`backend/` vs `frontend/`)
- Runs `run_generated_tests()` on backend files (pytest)
- Runs `run_node_tests()` on frontend files with `target_dir="frontend"` (vitest)
- Never raises — always returns `TestRunResult`

**V1 merge policy (D13):**
- Backend pytest result controls blocking pass/fail — if pytest fails, the combined result is a failure
- Frontend vitest result is recorded as non-blocking diagnostics — vitest failure/skip/not-executed does NOT flip the combined result to failure
- Combined `TestRunResult` preserves both outputs (stdout concatenated with clear section headers)
- Combined exit code is the backend exit code only
- If backend pytest is not executed (no backend files), fall through to vitest-only behavior (still non-blocking)

Frontend test execution (vitest) is non-blocking — failures do not prevent cycle success (D7).

### 3.2 Fullstack build profile

**Modified file:** `src/squadops/capabilities/handlers/build_profiles.py`

Add to `BUILD_PROFILES`:

```python
"fullstack_fastapi_react": BuildProfile(
    name="fullstack_fastapi_react",
    system_prompt_template=(
        "You are assembling a fullstack web application with a FastAPI backend "
        "and a React (Vite) frontend.\n\n"
        "Produce the following artifacts:\n"
        "1. A multi-stage Dockerfile: Python base for backend, Node build stage "
        "   for frontend static assets, final stage serves both.\n"
        "2. A docker-compose.yaml for local development (backend on :8000, "
        "   frontend dev server on :5173, with proxy config).\n"
        "3. A startup script (start.sh) that runs both services.\n"
        "4. CORS configuration notes for the backend.\n"
        "5. A qa_handoff.md covering how to run, test, and verify both stacks.\n\n"
        "The source code from the development step is provided as context. "
        "Do not regenerate application code — focus on packaging, configuration, "
        "and operational readiness."
    ),
    required_files=("Dockerfile", "docker-compose.yaml", "qa_handoff.md"),
    optional_files=("start.sh", ".env.example", "nginx.conf"),
    validation_rules=(
        "Dockerfile must use multi-stage build",
        "docker-compose.yaml must define backend and frontend services",
        "qa_handoff.md must include startup and test instructions for both stacks",
    ),
),
```

### 3.3 Cycle request profile

**New file:** `src/squadops/contracts/cycle_request_profiles/profiles/fullstack-fastapi-react.yaml`

This is the **canonical reusable profile** for the fullstack FastAPI + React capability path. It is referenced by `--profile fullstack-fastapi-react` in CLI commands.

```yaml
name: fullstack-fastapi-react
description: >
  Fullstack FastAPI + React (Vite) build with builder assembly.
  Neo produces backend/ and frontend/ source code, Bob assembles
  packaging artifacts, Eve generates tests for both stacks.
defaults:
  build_strategy: fresh
  dev_capability: fullstack_fastapi_react
  build_profile: fullstack_fastapi_react
  task_flow_policy:
    mode: sequential
    gates:
      - name: plan-review
        description: >
          Review planning artifacts before building the fullstack app.
        after_task_types:
          - governance.review
  expected_artifact_types:
    - document
    - source
    - test
    - config
  build_tasks:
    - development.develop
    - builder.assemble
    - qa.test
  notes: "Fullstack FastAPI + React (Vite) — stack-aware development capabilities"
```

### 3.4 QATestHandler wiring to test runner

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

In `QATestHandler.handle()`, around line 777 where `run_generated_tests()` is called: read `dev_capability` from `resolved_config` and select the right runner:

```python
capability = get_capability(
    inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
)
if capability.test_framework == TEST_FRAMEWORK_PYTEST:
    test_result = await run_generated_tests(source_file_records, test_file_records)
elif capability.test_framework == TEST_FRAMEWORK_VITEST:
    test_result = await run_node_tests(source_file_records, test_file_records)
elif capability.test_framework == TEST_FRAMEWORK_BOTH:
    test_result = await run_fullstack_tests(source_file_records, test_file_records)
```

### 3.5 Phase 3 tests

**New file:** `tests/unit/capabilities/test_node_test_runner.py`

- `run_node_tests()` with no `package.json` → `TestRunResult(executed=False)`
- `run_node_tests()` with mocked subprocess → captures stdout/stderr, returns exit code
- `run_node_tests()` timeout → process killed, `executed=False`
- `run_node_tests()` with Node/npm unavailable (FileNotFoundError) → `TestRunResult(executed=False)` with diagnostic
- `run_node_tests()` with `npm install` failure → `TestRunResult(executed=False)` with diagnostic
- `run_fullstack_tests()` runs both pytest and vitest, merges results
- `run_fullstack_tests()` with vitest failure but pytest success → combined result is success (D13 merge policy)
- `run_fullstack_tests()` with pytest failure → combined result is failure regardless of vitest outcome

Note: Node.js tests use mocked subprocess (unlike Python test runner tests which run real pytest). `npm`/`npx` may not be available in CI.

**Modified file:** `tests/unit/capabilities/test_build_profiles.py`

- `BUILD_PROFILES` has exactly 4 profiles (was 3)
- `get_profile("fullstack_fastapi_react")` returns valid profile
- Profile has `required_files` including `"Dockerfile"`, `"docker-compose.yaml"`, `"qa_handoff.md"`

**New file:** `tests/unit/contracts/test_fullstack_profile.py`

- `load_profile("fullstack-fastapi-react")` returns valid `CycleRequestProfile`
- Profile defaults include `dev_capability: "fullstack_fastapi_react"`
- Profile defaults include `build_profile: "fullstack_fastapi_react"`
- `build_tasks` list is `["development.develop", "builder.assemble", "qa.test"]`
- Has plan-review gate after `governance.review`

---

## Phase 4: Capability Validation on group_run

### 4.1 Update group_run example

**Modified file:** `examples/group_run/pcr.yaml`

Add `dev_capability: fullstack_fastapi_react` to defaults. This is an **example-specific profile** for the group_run sample app. It may carry additional example-specific overrides (e.g., `experiment_context`) that the canonical reusable profile does not.

**Modified file:** `examples/group_run/pcr-scaffold.yaml`

Already has `dev_capability: fullstack_fastapi_react` — verify it references the new profile correctly.

### 4.2 Integration validation

Not automated tests — manual cycle execution.

**Profile roles:**
- `pcr-scaffold` (via `--profile pcr-scaffold`) — example-specific smoke test profile that uses `prd-scaffold.md` for minimal validation
- `fullstack-fastapi-react` (via `--profile fullstack-fastapi-react`) — canonical reusable profile for full-scope fullstack cycles

```bash
# Rebuild with new capabilities
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api agents

# 1. Scaffold smoke test (validates pipeline with minimal scope)
squadops cycles create group_run \
  --squad-profile full-squad-with-builder \
  --profile pcr-scaffold \
  --prd examples/group_run/prd-scaffold.md

# 2. Full-scope validation (uses canonical reusable profile)
squadops cycles create group_run \
  --squad-profile full-squad-with-builder \
  --profile fullstack-fastapi-react \
  --prd examples/group_run/prd.md
```

### 4.3 Version bump and SIP promotion

After all phases pass verification:

**Version bump:** `0.9.11` → `0.9.12` (patch bump — new capability surface, no breaking changes to existing behavior).

```bash
export SQUADOPS_MAINTAINER=1
python scripts/maintainer/version_cli.py bump 0.9.12
```

**SIP promotion:** Move SIP-0072 from accepted to implemented.

```bash
export SQUADOPS_MAINTAINER=1
python scripts/maintainer/update_sip_status.py \
  sips/accepted/SIP-0072-Stack-Aware-Development-Capabilities.md implemented
```

Both are committed in the final PR alongside the implementation code.

---

## Rollback Strategy

If regressions appear after Phase 2 or 3, operational use reverts to `python_cli` default behavior:

1. Remove `dev_capability` from active cycle request profiles (both the reusable `fullstack-fastapi-react.yaml` profile and example-specific `pcr.yaml`/`pcr-scaffold.yaml` files)
2. Without `dev_capability` in `resolved_config`, all handlers fall back to `python_cli` (D2) — no code changes required for safe fallback
3. The registry module, file classification expansions, and test runner additions remain in the codebase for incremental fixes without affecting existing Python-only cycles
4. If deeper rollback is needed, revert the Phase 2 handler changes (capability branching) while preserving Phase 1 (registry + classification) as inert infrastructure

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `src/squadops/capabilities/dev_capabilities.py` | **New** — `DevelopmentCapability` registry, `get_capability()`, V1 entries |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | `_EXT_MAP`/`_FILENAME_MAP` expansion; `_is_test_file()` helper; `DevelopmentDevelopHandler` reads capability via `self._resolved_config`; `QATestHandler` reads capability for source filter + prompt + test runner selection; `BuilderAssembleHandler._get_source_artifacts()` renamed to `_get_assembly_inputs()` with expanded extensions |
| `src/squadops/capabilities/handlers/test_runner.py` | `run_node_tests()`, `run_fullstack_tests()` |
| `src/squadops/capabilities/handlers/build_profiles.py` | Add `fullstack_fastapi_react` profile |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | Add `"dev_capability"` to `_APPLIED_DEFAULTS_EXTRA_KEYS` |
| `src/squadops/contracts/cycle_request_profiles/profiles/fullstack-fastapi-react.yaml` | **New** — fullstack cycle request profile |
| `examples/group_run/pcr.yaml` | Add `dev_capability` key |
| `tests/unit/capabilities/test_dev_capabilities.py` | **New** — registry tests (including `python_api` resolution) |
| `tests/unit/capabilities/test_build_handlers.py` | Capability selection tests, `_classify_file` expansion tests, `_is_test_file` tests |
| `tests/unit/capabilities/test_node_test_runner.py` | **New** — Node.js test runner tests, fullstack merge policy tests |
| `tests/unit/capabilities/test_build_profiles.py` | Updated profile count, fullstack profile tests |
| `tests/unit/contracts/test_crp_schema_dev_capability.py` | **New** — schema key tests |
| `tests/unit/contracts/test_fullstack_profile.py` | **New** — profile YAML contract tests |

**Unchanged files:**
- `src/squadops/bootstrap/handlers.py` — same handlers, same task types
- `src/squadops/cycles/task_plan.py` — same pipeline shape
- `adapters/cycles/distributed_flow_executor.py` — artifact filter already works with `"source"` type
- `src/squadops/api/` — all DTOs already stack-agnostic
- `src/squadops/cli/` — `_BUILD_ARTIFACT_TYPES` already covers `"source"`

---

## Verification

```bash
# 1. All new + existing tests pass
./scripts/dev/run_new_arch_tests.sh -v

# 2. Affected tests pass
./scripts/dev/run_affected_tests.sh --branch

# 3. Lint clean
ruff check . --fix && ruff format .

# 4. Integration: scaffold cycle
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api agents
squadops cycles create group_run \
  --squad-profile full-squad-with-builder \
  --profile pcr-scaffold \
  --prd examples/group_run/prd-scaffold.md
# Verify: Neo produces backend/*.py + frontend/*.jsx
# Verify: Bob produces Dockerfile + qa_handoff.md
# Verify: Eve produces test files for both stacks

# 5. Non-blocking frontend test verification
# If Node tooling is unavailable in the agent container, verify:
# - QA/test execution records a diagnostic indicating frontend tests were skipped/not-executed
# - Cycle does not fail solely due to frontend test execution absence
# - Backend pytest results still control overall pass/fail
```
