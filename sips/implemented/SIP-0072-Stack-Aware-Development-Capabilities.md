---
title: Stack-Aware Development Capabilities
status: implemented
author: Jason Ladd
created_at: '2026-02-22T00:00:00Z'
sip_number: 72
updated_at: '2026-02-23T09:59:51.569928Z'
---
# SIP-00XX: Stack-Aware Development Capabilities

**Status:** Proposed
**Created:** 2026-02-22
**Owner:** SquadOps Core
**Target Release:** v0.9.12
**Related:** SIP-0068 (Build Capabilities), SIP-0071 (Builder Role), SIP-0066 (Cycle Execution Pipeline)

---

## 1. Intent

Add a **development capability** abstraction so that the build pipeline (SIP-0068) can produce artifacts beyond Python CLI apps — specifically FastAPI backends, React/Vite frontends, and fullstack combinations. The abstraction is a registry-driven mechanism: `DevelopmentCapability` objects control prompting, file classification, test generation, and test execution per tech stack, selected via a `dev_capability` key in cycle request profile defaults.

This SIP primarily introduces stack-aware development handler capabilities, with required supporting integrations in QA prompting, test runner behavior, builder profile selection, and cycle request profile defaults.

The result: `squadops cycles create group_run --profile fullstack-fastapi-react` produces a FastAPI backend and React frontend that a reviewer can start locally.

---

## 2. Problem Statement

The build pipeline (SIP-0068 + SIP-0071) assumes Python-only output at every stage:

| Component | Python-Only Assumption |
|-----------|----------------------|
| `DevelopmentDevelopHandler` | System prompt hardcodes "generating source code as a Python package", relative imports, `__main__.py` entrypoint |
| `_EXT_MAP` | Only `.py` maps to `("source", "text/x-python")` — `.js`, `.jsx`, `.css`, `.html` all fall through to `("source", "application/octet-stream")` |
| `QATestHandler._get_source_artifacts()` | Filters with `key.endswith(".py")` — JS/JSX/TS files are invisible to Eve |
| `QATestHandler` system prompt | Hardcodes "generating pytest test files" |
| `test_runner.py` | Runs `python -m pytest . --tb=short -q` only — no npm/vitest support |
| `BuilderAssembleHandler._get_source_artifacts()` | Filters with `key.endswith((".py", ".txt", ".yaml", ...))` — JS/JSX/HTML/CSS files are invisible to Bob |
| `BuildProfile` registry | Three profiles (`python_cli_builder`, `static_web_builder`, `web_app_builder`) — none for FastAPI+React |

To build fullstack apps like `group_run` (FastAPI + React/Vite per the PRD), every handler in the pipeline needs stack-aware prompting and file handling. The pipeline shape itself — `development.develop → builder.assemble → qa.test` — is correct and unchanged.

---

## 3. Goals

1. **Development capability registry**: A registry-driven mechanism configured via `dev_capability` in cycle request profile defaults that selects stack-appropriate prompts, file classifications, and test strategies without hardcoding any single language.
2. **V1 capabilities**: `python_cli`, `python_api`, `react_app`, `fullstack_fastapi_react` — each with tailored system prompt supplements, expected file extensions, and example file structures.
3. **File classification expansion**: `_EXT_MAP` recognizes JS/JSX/TS/TSX/CSS/HTML as `source` and `package.json`/`vite.config.js`/`tsconfig.json` as `config`.
4. **Stack-aware QA**: `QATestHandler` filters source artifacts and generates test prompts appropriate to the capability (pytest for Python, vitest for React, both for fullstack).
5. **Node.js test execution**: `test_runner.py` supports `npx vitest run` (after `npm install`) alongside pytest, orchestrated by capability.
6. **Fullstack build profile**: Bob receives a `fullstack_fastapi_react` profile for multi-stage Dockerfile assembly.
7. **Fullstack cycle request profile**: Ready-to-use `fullstack-fastapi-react.yaml` profile for apps like `group_run`.

---

## 4. Non-Goals

- New pipeline stages or task types — the existing `development.develop → builder.assemble → qa.test` flow is unchanged.
- Separate dev steps per stack (e.g., `development.develop_backend` then `development.develop_frontend`) — a single `development.develop` step is sufficient for 1-hour cycles.
- Runtime code execution during development — `test_runner.py` handles post-build testing only.
- Iterative repair loops (fix-and-retry on test failure) — separate concern.
- Time budget management within the 1-hour cycle — out of scope.
- TypeScript enforcement — JSX/JS is the default for React in 1-hour cycles; TS is supported via file classification but not mandated.
- Automated cross-stack API contract validation — schema sync, OpenAPI-based client validation, or contract diffing between backend and frontend is out of scope for V1. API/UI alignment is verified through implementation plan discipline and QA validation.

---

## 5. Design

### 5.1 Development Capability Registry

New file: `src/squadops/capabilities/handlers/dev_capabilities.py`

A registry analogous to `build_profiles.py` but controlling the **development handler** (Neo) and **QA handler** (Eve). Each capability defines stack-specific behavior:

```python
# Stable constants for test_framework field — avoids string drift in
# registry definitions, handler branching, and tests.
TEST_FRAMEWORK_PYTEST = "pytest"
TEST_FRAMEWORK_VITEST = "vitest"
TEST_FRAMEWORK_BOTH = "both"

@dataclass(frozen=True)
class DevelopmentCapability:
    name: str
    system_prompt_supplement: str   # appended to Neo's role prompt
    file_structure_guidance: str    # import rules, package conventions
    example_structure: str          # concrete file tree example
    expected_extensions: tuple[str, ...]  # file types Neo should produce
    test_framework: str             # TEST_FRAMEWORK_PYTEST | _VITEST | _BOTH
    test_prompt_supplement: str     # appended to Eve's role prompt
    source_filter: tuple[str, ...]  # extensions for _get_source_artifacts
    test_file_patterns: tuple[str, ...]  # patterns that identify test files
```

**V1 capabilities:**

| Name | Stack | Neo produces | Eve tests with |
|------|-------|-------------|----------------|
| `python_cli` | Python | Python package with `__main__.py` | pytest |
| `python_api` | FastAPI | `main.py`, `models.py`, `requirements.txt` | pytest (TestClient) |
| `react_app` | React+Vite | `App.jsx`, `index.html`, `package.json`, `vite.config.js` | vitest |
| `fullstack_fastapi_react` | FastAPI + React | `backend/` and `frontend/` directories | both |

**Selection semantics:**
- If `dev_capability` is **absent** from `resolved_config`: fall back to `python_cli`, preserving current behavior.
- If `dev_capability` is **present but unknown** (not in the registry): `get_capability()` raises `ValueError`. The handler returns a structured task failure with diagnostics (capability name, available capabilities). This prevents configuration typos from silently producing wrong-stack output.

### 5.2 Capability Field Details

**`system_prompt_supplement`**: Replaces the current hardcoded Python prompt suffix in `DevelopmentDevelopHandler`. For `fullstack_fastapi_react`, this instructs Neo to produce two directory trees (`backend/` and `frontend/`) with appropriate conventions for each stack.

**`file_structure_guidance`**: Stack-specific import and packaging rules. For `python_api`: "Use `from models import ...` relative imports, include a `requirements.txt` with `fastapi` and `uvicorn`." For `react_app`: "Use ES module imports, include `package.json` with react/vite dependencies."

**`example_structure`**: A concrete file tree that appears in the prompt. Neo performs better when shown the exact output shape. For `fullstack_fastapi_react`:

```
backend/
├── main.py
├── models.py
├── routes.py
└── requirements.txt
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── App.jsx
    ├── main.jsx
    └── components/
        └── RunList.jsx
```

**`expected_extensions`**: Used for validation — if Neo's output contains no files matching these extensions, the handler fails fast (same pattern as SIP-0068 §5.3).

**`test_framework`**: Drives test runner selection in `test_runner.py` and Eve's prompt.

**`source_filter`**: Tuple of extensions used by `QATestHandler._get_source_artifacts()` to identify which artifacts are "source code" for testing. For `python_cli`: `(".py",)`. For `fullstack_fastapi_react`: `(".py", ".js", ".jsx")`.

**`test_file_patterns`**: Tuple of filename/path patterns used to **exclude** test files from source artifact selection. The current `startswith("test_")` check is Python-specific; JS/TS ecosystems use different conventions. V1 exclusion patterns per capability:

| Capability | `test_file_patterns` (excluded from source selection) |
|-----------|------------------------------------------------------|
| `python_cli`, `python_api` | `("test_*.py", "*_test.py")` |
| `react_app` | `("*.test.js", "*.test.jsx", "*.spec.js", "*.spec.jsx", "__tests__/*")` |
| `fullstack_fastapi_react` | Union of Python and JS patterns |

`_get_source_artifacts()` uses `test_file_patterns` via `fnmatch` (or equivalent) instead of the current `not key.startswith("test_")` check. This prevents frontend test files from being accidentally treated as primary source artifacts in QA prompts.

### 5.3 DevelopmentDevelopHandler Changes

`src/squadops/capabilities/handlers/cycle_tasks.py` — `DevelopmentDevelopHandler`:

Current code (lines 419–426) hardcodes the Python prompt suffix:

```python
system_prompt = (
    assembled.content
    + "\n\nYou are generating source code as a Python package. "
    "Emit each file as a fenced code block: ```<lang>:<path>\n"
    ...
)
```

Changed to:

```python
capability = get_capability(
    inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
)
system_prompt = (
    assembled.content
    + "\n\n" + capability.system_prompt_supplement
    + "\n\n" + capability.file_structure_guidance
    + "\n\nTarget file structure:\n" + capability.example_structure
    + "\n\nEmit each file as a fenced code block: ```<lang>:<path>\n"
    "Paths must be clean relative paths with no colons or spaces."
)
```

The user prompt template (lines 352–380) also needs capability-driven changes: replace Python-specific pre-flight checklist items (stdlib verification, relative imports, `__main__.py`) with capability-appropriate checks.

All existing behavior is preserved: vault fallback, fenced code parsing, LangFuse tracing, fail-fast on empty extraction.

### 5.4 File Classification Expansion

`src/squadops/capabilities/handlers/cycle_tasks.py` — `_EXT_MAP` and `_FILENAME_MAP`:

```python
_EXT_MAP: dict[str, tuple[str, str]] = {
    # Python
    ".py": ("source", "text/x-python"),
    # JavaScript / TypeScript
    ".js": ("source", "text/javascript"),
    ".jsx": ("source", "text/javascript"),
    ".ts": ("source", "text/typescript"),
    ".tsx": ("source", "text/typescript"),
    ".mjs": ("source", "text/javascript"),
    # Web
    ".css": ("source", "text/css"),
    ".html": ("source", "text/html"),
    # Config / data
    ".md": ("document", "text/markdown"),
    ".txt": ("config", "text/plain"),
    ".yaml": ("config", "text/yaml"),
    ".yml": ("config", "text/yaml"),
    ".toml": ("config", "application/toml"),
    ".json": ("config", "application/json"),
}

_FILENAME_MAP: dict[str, tuple[str, str]] = {
    "requirements.txt": ("config", "text/plain"),
    "package.json": ("config", "application/json"),
    "vite.config.js": ("config", "text/javascript"),
    "tsconfig.json": ("config", "application/json"),
}
```

This is a pure addition. Existing Python classifications are unchanged. JS/JSX/TS/TSX files are now classified as `"source"` instead of falling through to `_DEFAULT_TYPE` with `application/octet-stream`.

### 5.5 QATestHandler Stack Awareness

`src/squadops/capabilities/handlers/cycle_tasks.py` — `QATestHandler`:

**`_get_source_artifacts()`** (lines 602–609): Replace the hardcoded `.py` filter with capability-driven filtering:

```python
from fnmatch import fnmatch
from pathlib import PurePosixPath

def _is_test_file(path: str, patterns: tuple[str, ...]) -> bool:
    """Check if path matches any test file pattern.

    V1 uses two matching strategies:
    - Filename pattern matching via fnmatch (e.g., "test_*.py", "*.test.jsx")
    - Path segment matching for directory-based conventions (e.g., __tests__/)
    The __tests__/ check is a path-segment special case because fnmatch operates
    on filenames only; directory-based test conventions require path inspection.
    """
    name = PurePosixPath(path).name
    return any(fnmatch(name, pat) for pat in patterns) or "/__tests__/" in path

def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
    """Get non-test source artifacts filtered by dev capability."""
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

**System prompt suffix** (lines 696–701): Replace the hardcoded pytest prompt with the capability's `test_prompt_supplement`:

```python
system_prompt = (
    assembled.content
    + "\n\n" + capability.test_prompt_supplement
    + "\nEmit each file as a fenced code block: ```<lang>:<path>\n"
    "Paths must be clean relative paths — no colons, no spaces."
)
```

For `fullstack_fastapi_react`, the test prompt instructs Eve to generate:
- Backend tests: `tests/test_api.py` using pytest + `httpx.AsyncClient` or `TestClient`
- Frontend test stubs: `frontend/src/__tests__/App.test.jsx` using vitest

**Frontend test generation vs execution**: These are separate capabilities with different V1 guarantees:
- **Frontend test generation** (required in V1): Eve always produces test files for JS sources when the capability includes vitest. These files are stored as artifacts regardless of execution outcome.
- **Frontend test execution** (invokable in V1, non-blocking): `run_node_tests()` attempts vitest execution when Node.js is available. Execution failures or unavailability do not block cycle success. The test artifact records the execution result (or reason for skipping).

### 5.6 Test Runner Expansion

`src/squadops/capabilities/handlers/test_runner.py`:

Add `run_node_tests()` for vitest execution (with `npm install` for dependency setup):

```python
async def run_node_tests(
    workspace: Path,
    timeout_seconds: int = 60,
) -> TestRunResult:
    """Run vitest in a Node workspace.

    Detects package.json in workspace, runs npm install (dependency setup)
    then npx vitest run (test execution).
    """
    package_json = workspace / "package.json"
    if not package_json.exists():
        return TestRunResult(executed=False, reason="No package.json found")

    # Install dependencies
    install_proc = await asyncio.create_subprocess_exec(
        "npm", "install", "--no-audit", "--no-fund",
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(install_proc.wait(), timeout=timeout_seconds)

    # Run tests
    proc = await asyncio.create_subprocess_exec(
        "npx", "vitest", "run", "--reporter=verbose",
        cwd=workspace,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    ...
```

`run_generated_tests()` is extended to orchestrate by capability:

| Capability | Test execution |
|-----------|---------------|
| `python_cli`, `python_api` | pytest in `workspace` |
| `react_app` | vitest in `workspace` |
| `fullstack_fastapi_react` | pytest in `workspace/backend/`, vitest in `workspace/frontend/`, merge results |

**Fullstack workspace path semantics**: For `fullstack_fastapi_react`, the test runner targets subdirectories rather than the workspace root. `run_node_tests()` accepts a `target_dir` parameter (defaults to `workspace`). The orchestrator passes `workspace / "frontend"` for fullstack capabilities. Similarly, pytest targets `workspace / "backend"`. This prevents mismatches when `package.json` exists only in `frontend/`.

The existing timeout and output capture patterns (`_STDOUT_LIMIT`, `TestRunResult`) are reused. Frontend test execution (vitest) is supported and invokable in V1 but non-blocking — failures do not prevent cycle success.

### 5.7 Fullstack Build Profile

`src/squadops/capabilities/handlers/build_profiles.py` — new profile:

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
    required_files=(
        "Dockerfile",
        "docker-compose.yaml",
        "qa_handoff.md",
    ),
    optional_files=(
        "start.sh",
        ".env.example",
        "nginx.conf",
    ),
    validation_rules=(
        "Dockerfile must use multi-stage build",
        "docker-compose.yaml must define backend and frontend services",
        "qa_handoff.md must include startup and test instructions for both stacks",
    ),
),
```

Bob's job for fullstack: produce packaging and operational artifacts that make Neo's code runnable. This is the same division of responsibility as existing profiles — Bob packages, he does not write application code.

### 5.8 Cycle Request Profile for Fullstack

New profile: `src/squadops/contracts/cycle_request_profiles/profiles/fullstack-fastapi-react.yaml`

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

The `group_run` example's `pcr.yaml` is updated to reference this profile or inline the `dev_capability` key.

### 5.9 Schema Key Registration

`src/squadops/contracts/cycle_request_profiles/schema.py`:

Add `"dev_capability"` to `_APPLIED_DEFAULTS_EXTRA_KEYS`:

```python
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    "build_tasks", "plan_tasks", "pulse_checks", "cadence_policy",
    "build_profile", "dev_capability",
}
```

This allows the `dev_capability` key in cycle request profile `defaults` without triggering the unknown-key validator.

### 5.10 Pipeline — No Structural Changes

The pipeline shape is unchanged:

```
Group 1 (plan):
  strategy.analyze_prd    → Nat   → strategy_analysis.md
  development.implement   → Neo   → implementation_plan.md
  qa.validate             → Eve   → validation_plan.md
  data.report             → Data  → data_report.md
  governance.review       → Max   → governance_review.md

  [gate: plan-review]

Group 2 (build):
  development.develop     → Neo   → source files (backend/*.py + frontend/*.jsx)
  builder.assemble        → Bob   → Dockerfile, docker-compose.yaml, qa_handoff.md
  qa.test                 → Eve   → test files (pytest + vitest)
```

No new task types. The dev capability and build profile are config that flows through `resolved_config` to change handler behavior within the existing pipeline shape.

### 5.11 BuilderAssembleHandler Source Filter

`BuilderAssembleHandler._get_source_artifacts()` (line 929) has its own hardcoded extension filter: `key.endswith((".py", ".txt", ".yaml", ".yml", ".toml", ".json", ".md"))`. This is separate from `_EXT_MAP` and independently excludes JS/JSX/HTML/CSS files from Bob's context.

This filter is updated to include the expanded extensions so Bob can see the frontend source code he needs to package:

```python
def _get_source_artifacts(self, inputs: dict[str, Any]) -> dict[str, str]:
    """Get all source/config artifacts from artifact_contents."""
    contents = inputs.get("artifact_contents", {})
    sources = {}
    for key, value in contents.items():
        if key.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
                         ".mjs", ".txt", ".yaml", ".yml", ".toml", ".json", ".md")):
            sources[key] = value
    return sources
```

This is a static extension — not capability-driven — because Bob always needs to see all source files regardless of stack in order to produce correct packaging artifacts.

### 5.12 Artifact Flow — No Structural Changes

`_BUILD_ARTIFACT_FILTER` in `distributed_flow_executor.py` already passes `source` and `config` artifacts from prior tasks to subsequent ones. With the expanded `_EXT_MAP` (§5.4), JS/JSX files are classified as `"source"` instead of falling through to `_DEFAULT_TYPE`. This means they flow through the existing artifact filter to Bob and Eve without any changes to the executor.

### 5.13 Runtime API and CLI — No Changes Required

The runtime API layer is already stack-agnostic:
- `artifact_type` and `media_type` are bare `str` fields in all DTOs — no enum or allowlist constraints.
- `applied_defaults` is a free-form `dict` passed through without key inspection. The `dev_capability` key flows from cycle request profile → CLI → API → `Cycle` domain object → `resolved_config` → handlers with no API-layer changes.

The CLI `runs assemble` command filters on `_BUILD_ARTIFACT_TYPES = {"source", "test", "config"}`. Since this SIP classifies JS/JSX files as `"source"` (not a new artifact type), the existing set covers all new file types. No CLI changes required.

---

## 6. Backward Compatibility

- **Existing cycles unaffected**: When `dev_capability` is absent from `resolved_config`, all handlers fall back to `python_cli` — which reproduces the current hardcoded Python behavior exactly.
- **Existing _EXT_MAP entries unchanged**: New extensions are purely additive. Python file classification is identical.
- **Existing build profiles unchanged**: The three existing profiles (`python_cli_builder`, `static_web_builder`, `web_app_builder`) are not modified.
- **Existing test runner unchanged**: `run_generated_tests()` continues to run pytest by default when no capability is specified.
- **No model changes**: No new fields on `Cycle`, `Run`, `Gate`, or `TaskEnvelope`. The `dev_capability` key lives in `applied_defaults` via the cycle request profile, same as `build_tasks` and `build_profile`.

---

## 7. Implementation Phases

### Phase 1: Development Capability Registry + File Classification

- Create `dev_capabilities.py` with `DevelopmentCapability` dataclass and V1 registry
- Implement `get_capability()` lookup with `python_cli` fallback
- Expand `_EXT_MAP` and `_FILENAME_MAP` with JS/JSX/TS/TSX/CSS/HTML entries
- Add `"dev_capability"` to `_APPLIED_DEFAULTS_EXTRA_KEYS` in schema
- Unit tests for registry (resolve, fallback, validation) and expanded file classification

### Phase 2: Handler Stack Awareness

- Modify `DevelopmentDevelopHandler` to read capability and use dynamic prompt
- Modify `QATestHandler._get_source_artifacts()` to use capability's `source_filter`
- Modify `QATestHandler` system prompt to use capability's `test_prompt_supplement`
- Verify existing Python-only tests still pass (capability fallback = `python_cli`)
- Unit tests for capability selection from `resolved_config`

### Phase 3: Test Runner + Build Profile

- Add `run_node_tests()` to `test_runner.py`
- Extend `run_generated_tests()` to orchestrate by capability
- Add `fullstack_fastapi_react` build profile to `build_profiles.py`
- Create `fullstack-fastapi-react.yaml` cycle request profile
- Unit tests for Node.js test runner (mock subprocess), fullstack build profile, profile loading

### Phase 4: Capability Validation on `group_run` Sample Cycle

- Update `examples/group_run/pcr.yaml` to use fullstack profile
- Integration validation: run `group_run` cycle with fullstack profile
- Verify development source artifacts contain both Python and React code
- Verify Bob produces builder packaging artifacts (multi-stage Dockerfile, `qa_handoff.md`)
- Verify Eve generates test artifacts for both stacks

---

## 8. Open Questions

1. **Node.js availability in agent containers**: Agent Docker images are Python-based. Running `npm install` and `npx vitest run` requires Node.js in the container. Options: (a) add Node.js to agent base image, (b) use a multi-stage test runner that shells out to a Node container, (c) skip vitest execution and only validate test file structure. Recommendation: option (a) for simplicity — add `node` and `npm` to the agent Dockerfile. This increases base image size and build time but reduces runtime complexity and improves reliability for mixed Python/Node test execution in fullstack capabilities.

2. **Single-step fullstack generation quality**: Can a single `development.develop` call produce coherent backend + frontend code with correct API contracts between them? The implementation plan from Group 1 should define the API shape, but LLM output quality may vary. Mitigation: the `example_structure` in the capability prompt anchors the output format.

3. **Frontend test value in 1-hour cycles**: Vitest tests for React components require jsdom/happy-dom setup. In a 1-hour cycle, frontend test stubs may not add meaningful validation. The SIP includes them as best-effort (non-blocking) — cycle success does not require frontend tests to pass.

4. **Capability extensibility**: Should capabilities be loadable from external YAML/JSON files (like build profiles could be), or is a Python registry sufficient for V1? Recommendation: Python registry for V1, YAML-driven extension as a future enhancement.

---

## 9. Success Criteria

1. `DevelopmentDevelopHandler` produces FastAPI backend files when `dev_capability` is `python_api`.
2. `DevelopmentDevelopHandler` produces both `backend/` and `frontend/` directories when `dev_capability` is `fullstack_fastapi_react`.
3. `.jsx`, `.js`, `.css`, `.html` files are classified as `"source"` by `_EXT_MAP` and flow through artifact filters to Bob and Eve.
4. `QATestHandler` generates pytest tests for Python sources and vitest test stubs for JS sources when the capability is `fullstack_fastapi_react`.
5. `test_runner.py` can invoke `npx vitest run` when a `package.json` is present in the target directory. Vitest execution failures do not block cycle success in V1.
6. `fullstack_fastapi_react` build profile produces a multi-stage Dockerfile and `qa_handoff.md`.
7. `fullstack-fastapi-react.yaml` cycle request profile loads and validates without errors.
8. Existing `python_cli` behavior is unchanged — all existing tests pass without modification.
9. `squadops cycles create group_run --profile fullstack-fastapi-react` produces a run whose development source artifacts include both `backend/main.py` and `frontend/src/App.jsx`, and whose builder packaging artifacts include a multi-stage Dockerfile and `qa_handoff.md`.
10. The combined development source artifacts and builder-produced packaging artifacts support local startup and QA execution following the `qa_handoff.md` instructions.
