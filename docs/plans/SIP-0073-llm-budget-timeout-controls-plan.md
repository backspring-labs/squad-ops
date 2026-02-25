# SIP-0073: LLM Budget and Timeout Controls — Implementation Plan

## Context

The pipeline was validated on qwen2.5:7b with short scaffold PRDs (SIP-0072). Moving to longer cycles on DGX Spark with larger models exposes five gaps: no prompt size awareness, hardcoded `max_tokens=4000`, fixed 60s LLM timeout, fixed 60s test runner timeout, and no model context metadata. The SIP at `sips/proposed/SIP-LLM-Budget-and-Timeout-Controls.md` defines the solution. This plan implements it.

All four LLM call sites in `cycle_tasks.py` use the same pattern: `await context.ports.llm.chat(messages)` with no model, no max_tokens, no timeout. The `chat()` port interface only accepts `messages` and `model`. The `generate()` method already supports `max_tokens` and `timeout_seconds` via `LLMRequest`, so the Ollama adapter already knows how to handle these — `chat()` just needs the same parameters surfaced.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Promote SIP to accepted as SIP-0073 before writing code | Governance: accepted status signals commitment |
| D2 | V1 scope: Dev + QA handlers only; Builder uses adapter defaults | Per SIP §5.1; Builder reads `BuildProfile`, not `DevelopmentCapability` |
| D3 | `_guard_prompt_size()` returns truncated prompt or raises; no structured return object | Structured logging at call site sufficient for V1 observability |
| D4 | Model registry is code-defined dict, exact match with `strip()` only | Per SIP §5.3; no alias/tag normalization in V1 |
| D5 | Impossible fit → structured task failure, not silent truncation | Per SIP §5.7; operator must see the failure to take corrective action |
| D6 | Timeout responsibility split: handlers resolve effective timeout from config, pass as `timeout_seconds` to `chat()`; adapters use it or fall back to `self._timeout` | Keeps adapters free of config-policy logic; consistent across providers |
| D7 | `generation_timeout` flows via `_APPLIED_DEFAULTS_EXTRA_KEYS` in cycle request profile schema; handlers fall back to 300 if absent | `generate_task_plan()` has no access to `app_config`; profile-based injection is the clean path |
| D8 | Prompt guard helpers extracted to `src/squadops/capabilities/handlers/prompt_guard.py` | Dedicated module improves testability and avoids awkward imports from `cycle_tasks.py` |
| D9 | Prompt overflow returns structured failure as JSON string with fixed keys | Prevents drift between handler implementations, tests, and observability; machine-parseable for future telemetry |
| D10 | `LLMConfig.generation_timeout` deferred to follow-up — V1 timeout is profile-driven + handler fallback only | `generate_task_plan()` has no access to `app_config`; adding dead config creates confusion |

---

## Phase 0: SIP Acceptance + Feature Branch

Follows the standard SIP contributor workflow (see CLAUDE.md § SIP System).

### 0.1 Accept the SIP on main

The SIP has already been proposed at `sips/proposed/SIP-LLM-Budget-and-Timeout-Controls.md`. After design review is complete, a maintainer accepts it on main:

```bash
export SQUADOPS_MAINTAINER=1
python scripts/maintainer/update_sip_status.py \
  sips/proposed/SIP-LLM-Budget-and-Timeout-Controls.md accepted
git add sips/ && git commit -m "chore: accept SIP-0073 — LLM Budget and Timeout Controls"
```

This assigns SIP number 0073, moves the file to `sips/accepted/SIP-0073-LLM-Budget-Timeout-Controls.md`, and updates `sips/registry.yaml`. The accepted SIP is now on main as the approved spec.

### 0.2 Create feature branch from main

```bash
git checkout -b feature/sip-0073-llm-budget-timeout-controls
```

The branch starts from a main that already contains the accepted SIP. All implementation commits go on this branch.

---

## Phase 1: LLM Port Interface + Model Registry

### 1.1 Extend `chat()` signature

**Modified file:** `src/squadops/ports/llm/provider.py`

```python
@abstractmethod
async def chat(
    self,
    messages: list[ChatMessage],
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
) -> ChatMessage:
```

All new params default to `None` — adapter uses its own defaults when not provided.

### 1.2 Update Ollama adapter

**Modified file:** `adapters/llm/ollama.py`

Update `chat()` method (currently lines 117-157) to accept and use the new params:

- `max_tokens` → maps to `"num_predict"` in Ollama payload options (same as `generate()` line 81)
- `temperature` → maps to `"temperature"` in options
- `timeout_seconds` → overrides `self._timeout` for this call (same pattern as `generate()` line 73)

### 1.3 Model context registry

**New file:** `src/squadops/llm/model_registry.py`

- `ModelSpec` frozen dataclass: `name`, `context_window`, `default_max_completion`
- `MODEL_SPECS` dict with V1 entries: `qwen2.5:7b` (8K/4K), `qwen2.5:32b` (32K/8K), `qwen2.5:72b` (128K/16K), `llama3:70b` (128K/16K)
- `get_model_spec(name)` → exact match with `strip()`, returns `None` for unknown
- Registry keys must exactly match `LLMConfig.model` values used in active profiles (e.g., `qwen2.5:7b`, not `qwen2.5-7b`)

### 1.4 LLMConfig extension — DEFERRED (D10)

`LLMConfig.generation_timeout` is **not added in V1**. The runtime path derives effective generation timeout from cycle request profile `defaults.generation_timeout` (Phase 3.4) with a handler fallback of 300s. Adding a config field that nothing reads would create "looks configurable but does nothing" behavior.

A follow-up patch can wire `AppConfig.llm.generation_timeout` into config resolution once `generate_task_plan()` or the executor has access to `app_config`.

### 1.5 Phase 1 tests

**Modified file:** `tests/unit/llm/test_ports.py` — verify `chat()` accepts new params in ABC

**Modified file:** `tests/unit/llm/test_ollama_adapter.py` — test `chat()` with `max_tokens`, `temperature`, `timeout_seconds`

**New file:** `tests/unit/llm/test_model_registry.py`
- Known model lookup returns correct spec
- Unknown model returns `None`
- Whitespace stripped
- All specs have `context_window > default_max_completion`

**Modified file:** `tests/unit/conftest.py` — update `mock_ollama` and any mock LLM fixtures to accept new `chat()` params

---

## Phase 2: Capability Fields + Prompt Guard

### 2.1 DevelopmentCapability extension

**Modified file:** `src/squadops/capabilities/dev_capabilities.py`

Add two fields to `DevelopmentCapability`:

```python
max_completion_tokens: int = 4000
test_timeout_seconds: int = 60
```

V1 values:
- `python_cli`: 4000 / 60
- `python_api`: 6000 / 60
- `react_app`: 8000 / 120
- `fullstack_fastapi_react`: 12000 / 180

### 2.2 Prompt size guard

**New file:** `src/squadops/capabilities/handlers/prompt_guard.py` (D8)

Extracted to a dedicated module for clean testability:

```python
_CHARS_PER_TOKEN_ESTIMATE = 4

def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE

def _guard_prompt_size(
    system_prompt: str,
    user_prompt: str,
    max_completion_tokens: int,
    context_window: int | None,
) -> str:
    """Guard prompt against context window overflow.

    Truncates '## Prior Analysis from Upstream Roles' section if needed.
    Raises ValueError if prompt still can't fit after truncation.
    Returns (possibly truncated) user_prompt.
    """
```

Algorithm per SIP §5.6:
1. If `context_window` is `None` → return unchanged (debug log)
2. `available = context_window - max_completion_tokens`
3. If `available <= 0` → **early fail** with structured JSON diagnostics (degenerate headroom — bad registry values, oversized capability budget, or invalid config). Skip truncation attempts since they cannot succeed.
4. `estimated = _estimate_tokens(system_prompt + "\n\n" + user_prompt)` (separator approximates real payload shape)
5. If fits → return unchanged
6. Find `## Prior Analysis from Upstream Roles` section via **case-sensitive exact heading match** on `"## Prior Analysis from Upstream Roles"` (this is the literal heading produced by `_build_user_prompt()`). Truncate first match only.
7. Re-estimate; if still doesn't fit → raise `ValueError` with structured JSON diagnostics (D9)

**Structured failure payload (D9):**

When prompt overflow is impossible to resolve, the `ValueError` message is a **JSON string** with fixed keys. Tests can `json.loads(str(exc))` to assert on individual fields. Logs and future telemetry can parse reliably.

```python
import json
raise ValueError(json.dumps({
    "error_code": "PROMPT_EXCEEDS_CONTEXT_WINDOW",
    "estimated_prompt_tokens": estimated,
    "effective_completion_tokens": max_completion_tokens,
    "context_window": context_window,
    "available_prompt_tokens": available,
    "truncation_attempted": True,  # or False for early-fail / no section found
    "truncated_sections": ["## Prior Analysis from Upstream Roles"],  # or []
}))
```

Handlers catch the `ValueError` and return `HandlerResult(success=False, error=str(exc))` — the JSON string flows through as-is.

### 2.3 Phase 2 tests

**Modified file:** `tests/unit/capabilities/test_dev_capabilities.py`
- All capabilities have `max_completion_tokens > 0`
- All capabilities have `test_timeout_seconds > 0`
- `fullstack_fastapi_react` has higher values than `python_cli`

**New file:** `tests/unit/capabilities/test_prompt_guard.py`
- Prompt within budget → unchanged
- Prompt exceeds budget → prior outputs truncated, PRD preserved
- Impossible fit after truncation → `ValueError` with JSON payload (`json.loads(str(exc))` returns dict with all required keys)
- Degenerate headroom (`context_window <= max_completion_tokens`) → early `ValueError` with `truncation_attempted=False`
- Unknown context window (`None`) → unchanged, debug log
- No prior section present and prompt fits → unchanged (no truncation needed)
- No truncatable section present and prompt overflows → `ValueError` with `truncation_attempted=False`, `truncated_sections=[]`
- `_estimate_tokens()` returns correct heuristic values
- All `ValueError` payloads are valid JSON with fixed keys: `error_code`, `estimated_prompt_tokens`, `effective_completion_tokens`, `context_window`, `available_prompt_tokens`, `truncation_attempted`, `truncated_sections`

---

## Phase 3: Handler Wiring

### 3.1 DevelopmentDevelopHandler

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

In `handle()` (around line 439-463), after building system/user prompts:

1. Read capability (already done at line 395)
2. Read model name: `context.ports.llm.default_model` (guaranteed by `LLMPort` ABC, returns `"unknown"` by default)
3. Look up `model_spec = get_model_spec(model_name)` — returns `None` for unknown models
4. Compute `max_tokens`: if model known, `min(capability.max_completion_tokens, model_spec.default_max_completion)`; if unknown, use `capability.max_completion_tokens` only
5. Guard prompt: `user_prompt = _guard_prompt_size(system_prompt, user_prompt, max_tokens, context_window)` (imported from `prompt_guard` module)
6. Resolve effective timeout: `resolved_config.get("generation_timeout", 300)` — **handler responsibility** (D6)
7. Call: `await context.ports.llm.chat(messages, max_tokens=max_tokens, timeout_seconds=effective_timeout)` — adapter receives `timeout_seconds`, uses it or falls back to `self._timeout`
8. On `ValueError` from guard → return `HandlerResult(success=False, ...)` with structured error diagnostics (D9)

**Timeout responsibility split (D6):**
- **Handler** resolves the effective timeout from `resolved_config` (profile-injected or fallback 300)
- **Handler** passes it as `timeout_seconds` to `chat()`
- **Adapter** uses provided `timeout_seconds` if non-None, otherwise uses `self._timeout`
- Adapter never interprets config semantics like `generation_timeout`

### 3.2 QATestHandler

**Modified file:** `src/squadops/capabilities/handlers/cycle_tasks.py`

Same pattern as Dev handler. `QATestHandler.handle()` has a single `chat()` call (line 731) — that is the only LLM call that gets budgeting + prompt guard. The test runner is subprocess-based, not LLM-driven.

1. Capability already resolved at line 679-682
2. Budget + guard + call with `max_tokens` and `timeout_seconds` (same responsibility split as Dev handler)
3. Pass `capability.test_timeout_seconds` to test runner (around line 777)

### 3.3 BuilderAssembleHandler — NO CHANGES (D2)

Builder uses `BuildProfile`, not `DevelopmentCapability`. It continues to call `chat(messages)` with adapter defaults. Future SIP may add builder-specific budgets.

### 3.4 Generation timeout injection (D7)

`generate_task_plan()` receives `cycle`, `run`, `profile` — it has no access to `app_config`. The clean injection path is the cycle request profile schema.

**Modified file:** `src/squadops/contracts/cycle_request_profiles/schema.py`

Add `"generation_timeout"` to `_APPLIED_DEFAULTS_EXTRA_KEYS`:
```python
_APPLIED_DEFAULTS_EXTRA_KEYS = {
    "build_tasks", "plan_tasks", "pulse_checks", "cadence_policy",
    "build_profile", "dev_capability", "generation_timeout",
}
```

Profiles can set `generation_timeout` in their `defaults` block. Handlers read it from `resolved_config.get("generation_timeout", 300)` with a hardcoded fallback of 300 when not present. No changes needed to `task_plan.py`.

### 3.5 Phase 3 tests

**Modified file:** `tests/unit/capabilities/test_build_handlers.py`

DevelopmentDevelopHandler:
- With `python_cli` capability → `chat()` called with `max_tokens=4000`
- With `fullstack_fastapi_react` → `chat()` called with `max_tokens=12000`
- With model spec capping (e.g., 7b model) → `max_tokens` reduced to model's limit
- Without `resolved_config` → defaults to `python_cli` budget (existing default capability resolution: `resolved_config.get("dev_capability", "python_cli")`)
- Without `resolved_config.dev_capability` key → same default, not a failure
- Prompt exceeds context window → `HandlerResult(success=False)` with structured error (error_code, estimated tokens, context window, truncation_attempted)

QATestHandler:
- `chat()` called with capability's `max_tokens`
- Test runner called with `capability.test_timeout_seconds`
- `fullstack_fastapi_react` → test runner gets `timeout_seconds=180`

BuilderAssembleHandler:
- `chat()` called WITHOUT `max_tokens` (adapter defaults) — verify no regression

---

## Phase 4: Schema Key + Docs + Version

### 4.1 Schema key

Already done in Phase 3.4 — `generation_timeout` added to `_APPLIED_DEFAULTS_EXTRA_KEYS`.

### 4.2 Copy plan to docs/plans

Copy this plan to `docs/plans/SIP-0073-llm-budget-timeout-controls-plan.md`.

### 4.3 Version bump

Bump version in `pyproject.toml` and `src/squadops/__init__.py` (0.9.12 → 0.9.13 or 1.0.0 depending on timing). Perform version bump in the final merge-prep commit to keep implementation commits clean and reduce conflicts.

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `sips/proposed/SIP-LLM-Budget-and-Timeout-Controls.md` | Promoted to `sips/accepted/SIP-0073-...` |
| `sips/registry.yaml` | New entry for SIP-0073 |
| `src/squadops/ports/llm/provider.py` | Extend `chat()` signature |
| `adapters/llm/ollama.py` | Pass new params to Ollama API |
| `src/squadops/llm/model_registry.py` | **New** — model spec registry |
| `src/squadops/capabilities/dev_capabilities.py` | Add `max_completion_tokens`, `test_timeout_seconds` |
| `src/squadops/capabilities/handlers/prompt_guard.py` | **New** — `_estimate_tokens()`, `_guard_prompt_size()` |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | Handler wiring (import from `prompt_guard`, budget + timeout logic) |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | Add `generation_timeout` to `_APPLIED_DEFAULTS_EXTRA_KEYS` |
| `docs/plans/SIP-0073-llm-budget-timeout-controls-plan.md` | **New** — this plan |
| `tests/unit/llm/test_model_registry.py` | **New** |
| `tests/unit/llm/test_ports.py` | Behavior-based tests: concrete adapter/mock accepts new optional params |
| `tests/unit/llm/test_ollama_adapter.py` | Test `chat()` with `max_tokens`, `temperature`, `timeout_seconds` |
| `tests/unit/capabilities/test_prompt_guard.py` | **New** |
| `tests/unit/capabilities/test_dev_capabilities.py` | New field assertions |
| `tests/unit/capabilities/test_build_handlers.py` | Token budget + timeout assertions |
| `tests/unit/conftest.py` | Update mock LLM fixtures |

---

## Verification

```bash
# 1. All new + existing tests pass
./scripts/dev/run_new_arch_tests.sh -v

# 2. Affected tests pass
./scripts/dev/run_affected_tests.sh --branch

# 3. Lint clean
ruff check . --fix && ruff format .

# 4. Rebuild and deploy (when ready for E2E)
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api agents

# 5. Run scaffold cycle to verify no regression
squadops cycles create group_run \
  --squad-profile full-squad-with-builder \
  --profile pcr-scaffold \
  --prd examples/group_run/prd-scaffold.md
# Verify: same behavior as pre-SIP-0073 (backward compat)
```
