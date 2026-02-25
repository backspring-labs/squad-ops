---
title: LLM Budget and Timeout Controls
status: accepted
author: SquadOps Core
created_at: '2026-02-23'
updated_at: '2026-02-24T20:49:01.185765Z'
sip_number: 73
---
# SIP: LLM Budget and Timeout Controls

**Status:** Proposed \
**Created:** 2026-02-23 \
**Owner:** SquadOps Core \
**Target Release:** v1.0 \
**Related:** SIP-0068 (Build Capabilities), SIP-0071 (Builder Role), SIP-0072 (Stack-Aware Dev Capabilities)

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-23 | Initial proposal |
| 2   | 2026-02-23 | Tightenings: handler scope, budgeting algorithm, impossible-fit policy, timeout precedence, migration completeness, registry semantics, heuristic framing |

---

## 1. Abstract

Cycle task handlers currently send prompts to the LLM with no awareness of context window limits, hardcoded completion token caps, and timeout values that don't scale across models. This SIP introduces per-handler token budgeting, prompt size guards, configurable timeouts, and model context metadata so the pipeline can run longer cycles on larger models without silent truncation or false timeout failures.

---

## 2. Problem Statement

The pipeline was validated on qwen2.5:7b with short scaffold PRDs. Moving to longer cycles on beefier hardware (e.g., DGX Spark with 70B+ models) exposes five gaps:

1. **No prompt size awareness.** A 2000-line PRD with 3 phases of prior role outputs can produce 15K+ token prompts. The 7B model's 8K context is blown; larger models may silently truncate input. No handler checks prompt size before calling the LLM.

2. **Hardcoded `max_tokens=4000`.** The `LLMRequest` default is never overridden. A fullstack app with 10+ files needs more; a plan review needs far fewer. The `chat()` port interface doesn't even accept `max_tokens`, so handlers *can't* control it.

3. **Fixed LLM timeout (60s).** `LLMConfig.timeout=60` works for 7B but is too short for a 70B model generating a full application. There's no distinction between health check timeouts (should be fast) and generation timeouts (should be patient).

4. **Fixed test runner timeout (60s).** `npm install` + vitest on a real project will exceed 60 seconds. The timeout isn't configurable via capability or config.

5. **No model metadata.** Handlers don't know the context window size of the target model, so they can't make informed decisions about prompt construction or completion budgets.

---

## 3. Goals

1. **Extend the `chat()` port interface** with optional `max_tokens`, `temperature`, and `timeout_seconds` parameters so handlers can control generation behavior.
2. **Per-handler token budgets** driven by `DevelopmentCapability` fields for Development and QA handlers — each capability declares its expected completion size and handlers pass it through.
3. **Prompt size guard** — handlers estimate prompt token count before calling the LLM and take corrective action (truncate prior outputs, log warning, or fail) if over threshold.
4. **Configurable generation timeout** — `LLMConfig` gets a `generation_timeout` field separate from health/connectivity timeouts, with explicit precedence rules.
5. **Configurable test runner timeout** — `DevelopmentCapability` gets a `test_timeout_seconds` field; QA handler passes it to the test runner.
6. **Model context metadata** — a lightweight registry mapping model names to context window sizes, so handlers can budget tokens against known limits.

---

## 4. Non-Goals

- **Token-level billing or cost tracking.** LangFuse already captures token counts for observability. This SIP is about *preventing failures*, not accounting.
- **Streaming or chunked generation.** The pipeline processes complete responses. Streaming is a separate concern.
- **Automatic model selection.** Handlers don't pick models — that's config-driven. This SIP gives handlers *awareness* of the configured model's limits.
- **Prompt compression or summarization.** If a prompt exceeds the budget, the V1 strategy is to truncate prior outputs with a warning, not to summarize them.
- **Rate limiting or quota enforcement.** Out of scope for this SIP.
- **Exact tokenizer integration per model/provider.** Heuristic character-based estimation is sufficient for V1 prompt budgeting guardrails. Exact token counting with provider-specific tokenizers is out of scope.

---

## 5. Design

### 5.1 V1 Handler Scope

Capability-driven token budgets and prompt guards apply to the handlers that use stack-aware generation and test flows in V1:

- **`DevelopmentDevelopHandler`** — reads `max_completion_tokens` from `DevelopmentCapability`
- **`QATestHandler`** — reads `max_completion_tokens` and `test_timeout_seconds` from `DevelopmentCapability`

Handlers **not** in scope for V1 capability-driven budgets:

- **`BuilderAssembleHandler`** — uses `BuildProfile`, not `DevelopmentCapability`. Uses `LLMConfig` defaults for timeout and the adapter's default `max_tokens`.
- **Strategy, planning, and other non-dev handlers** — use `LLMConfig` defaults / adapter defaults. No capability override in V1.

Future SIPs may introduce role-specific budget policies for builder, strategy, and planning handlers as longer cycles expose their needs.

### 5.2 LLM Port Interface Extension

Extend `LLMPort.chat()` with optional request parameters:

```python
class LLMPort(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatMessage:
        """Chat with the LLM using message history."""
```

When parameters are `None`, the adapter uses its defaults (preserving current behavior). The Ollama adapter maps `max_tokens` to `num_predict` and `timeout_seconds` to the httpx timeout.

### 5.3 Model Context Registry

New module `src/squadops/llm/model_registry.py`:

```python
@dataclass(frozen=True)
class ModelSpec:
    name: str
    context_window: int          # Total tokens (prompt + completion)
    default_max_completion: int  # Recommended max_tokens for generation

MODEL_SPECS: dict[str, ModelSpec] = {
    "qwen2.5:7b":  ModelSpec("qwen2.5:7b",  context_window=8192,   default_max_completion=4000),
    "qwen2.5:32b": ModelSpec("qwen2.5:32b",  context_window=32768,  default_max_completion=8000),
    "qwen2.5:72b": ModelSpec("qwen2.5:72b",  context_window=131072, default_max_completion=16000),
    "llama3:70b":   ModelSpec("llama3:70b",   context_window=131072, default_max_completion=16000),
}

def get_model_spec(model_name: str) -> ModelSpec | None:
    """Look up model spec by name. Exact match with strip() only.

    Returns None for unknown models — handlers fall back to
    capability defaults with no context window enforcement.
    """
    return MODEL_SPECS.get(model_name.strip() if model_name else None)
```

This is intentionally a simple dict — not a config file. New models are added by code change. Unknown models return `None` and handlers fall back to conservative defaults.

**Lookup semantics:** V1 uses exact string match only (with leading/trailing whitespace stripped). No alias resolution, no tag normalization (e.g., `qwen2.5:7b-instruct` would not match `qwen2.5:7b`). If the configured model name doesn't match a registry key, the handler proceeds without context window enforcement.

**Registry values** are initial operational defaults for guardrails and may be tuned as local testing validates effective limits per deployed model configuration.

### 5.4 DevelopmentCapability Token Budget Fields

Add to `DevelopmentCapability`:

```python
@dataclass(frozen=True)
class DevelopmentCapability:
    # ... existing fields ...
    max_completion_tokens: int = 4000
    test_timeout_seconds: int = 60
```

V1 values per capability:

| Capability | `max_completion_tokens` | `test_timeout_seconds` |
|------------|------------------------|----------------------|
| `python_cli` | `4000` | `60` |
| `python_api` | `6000` | `60` |
| `react_app` | `8000` | `120` |
| `fullstack_fastapi_react` | `12000` | `180` |

These are starting points — the budgeting algorithm (§5.6) caps the actual value if the model can't support it.

**Note:** In V1, QA test timeout policy is derived from the same stack capability metadata as development generation behavior. Future work may separate QA execution policy from development capability if the two diverge in practice.

### 5.5 LLMConfig Timeout Fields

Extend `LLMConfig`:

```python
class LLMConfig(BaseModel):
    url: str = Field(default="http://host.docker.internal:11434")
    model: str | None = Field(default=None)
    use_local: bool = Field(default=True)
    timeout: int = Field(default=60, ge=1, description="Default request timeout (seconds)")
    generation_timeout: int = Field(
        default=300, ge=10,
        description="Timeout for LLM generation calls (seconds). Should be higher than timeout."
    )
```

**Timeout precedence rules (V1):**

1. **Handler-provided `timeout_seconds`** (passed to `chat()`) takes highest precedence for that call.
2. If handler passes `None`, the adapter uses **`generation_timeout`** from `LLMConfig` for generation calls. The caller (handler) is responsible for passing the generation timeout — the adapter does not distinguish generation from health calls.
3. **`timeout`** remains the default for health checks, connectivity probes, and any call where no explicit timeout is provided.

This means "generation vs health" is determined by the caller, not inferred by the adapter.

### 5.6 Prompt Size Guard and Budgeting Algorithm

Add a module-level helper in `cycle_tasks.py`. V1 prompt guard lives in `cycle_tasks.py` for locality with the handlers that use it; it may be extracted into a shared utility module if reused by additional handlers in the future.

Token estimation uses a **conservative heuristic guardrail** (character count / estimated chars-per-token). This is not intended for exact token accounting, billing, or provider tokenizer parity — it exists to prevent obvious context window overflows.

```python
# Conservative heuristic: 1 token ~= 4 characters for English text.
# Intentionally approximate — exact counts vary by model tokenizer.
_CHARS_PER_TOKEN_ESTIMATE = 4

def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE
```

**V1 Budgeting Algorithm (deterministic order):**

Handlers execute the following steps before each LLM call:

```
Step 1: SELECT completion budget
         completion_budget = capability.max_completion_tokens

Step 2: CAP by model limit (if known)
         if model_spec and completion_budget > model_spec.default_max_completion:
             completion_budget = model_spec.default_max_completion

Step 3: RESERVE completion headroom
         available_for_prompt = context_window - completion_budget
         (if context_window is unknown, skip to Step 5)

Step 4: GUARD prompt size
         estimated_prompt_tokens = estimate_tokens(system_prompt + user_prompt)
         if estimated_prompt_tokens <= available_for_prompt:
             → proceed (no truncation)
         else:
             → truncate "## Prior Analysis from Upstream Roles" section
             → re-estimate after truncation

Step 5: CHECK impossible fit
         if estimated_prompt_tokens > available_for_prompt after truncation:
             → return structured task failure (see §5.7)

Step 6: CALL LLM
         chat(messages, max_tokens=completion_budget, timeout_seconds=generation_timeout)
```

If no `context_window` is known (unknown model), Steps 3–5 are skipped. The handler logs a debug message and proceeds with the capability's completion budget unchecked.

### 5.7 Impossible Prompt Fit — Structured Task Failure

If the prompt still exceeds the available context window after all allowed truncation (Step 5), the handler **does not call the LLM**. Instead it returns a structured task failure with diagnostics:

```python
return TaskResult(
    success=False,
    error_code="PROMPT_EXCEEDS_CONTEXT_WINDOW",
    error_message=(
        f"Prompt ({estimated_prompt_tokens} est. tokens) exceeds available context "
        f"({available_for_prompt} tokens) after truncation. "
        f"Context window: {context_window}, completion budget: {completion_budget}."
    ),
    metadata={
        "estimated_prompt_tokens": estimated_prompt_tokens,
        "completion_budget": completion_budget,
        "context_window": context_window,
        "truncated_sections": truncated_sections,  # list of section names removed
    },
)
```

This is preferred over silent hard truncation because:
- It makes the failure visible and diagnosable
- The operator can respond by reducing PRD size, switching to a larger model, or adjusting capability budgets
- Silent truncation hides quality regressions that are difficult to trace

### 5.8 Handler Wiring

Each in-scope handler's `handle()` method reads the budget from the capability and model spec:

```python
capability = get_capability(
    inputs.get("resolved_config", {}).get("dev_capability", "python_cli")
)
model_spec = get_model_spec(model_name)  # may be None

# Step 1-2: Select and cap completion budget
max_tokens = capability.max_completion_tokens
if model_spec and max_tokens > model_spec.default_max_completion:
    max_tokens = model_spec.default_max_completion

# Step 3-5: Guard prompt size
context_window = model_spec.context_window if model_spec else None
user_prompt = _guard_prompt_size(system_prompt, user_prompt, max_tokens, context_window)
# _guard_prompt_size returns truncated prompt or raises for impossible fit

# Step 6: Call LLM with budget
response = await context.ports.llm.chat(
    messages,
    max_tokens=max_tokens,
    timeout_seconds=generation_timeout,
)
```

QA handler passes `capability.test_timeout_seconds` to the test runner:

```python
test_result = await run_generated_tests(
    source_file_records,
    test_file_records,
    timeout_seconds=capability.test_timeout_seconds,
)
```

---

## 6. Migration

**Fully backward compatible.** All new parameters have defaults that reproduce current behavior:

- `chat()` new params default to `None` (adapter uses existing defaults)
- `max_completion_tokens=4000` matches current `LLMRequest` default
- `test_timeout_seconds=60` matches current test runner default
- `generation_timeout=300` is longer than current `timeout=60` but only used for generation calls
- Unknown models return `None` from registry — handlers fall back to capability defaults with no context window enforcement

No config file changes required. Existing cycle request profiles work unchanged.

**Implementation note:** All concrete `LLMPort` implementations, fake adapters, mocks, and test doubles must be updated to accept the new optional `chat()` parameters, even if they ignore them in V1. This includes:

- `adapters/llm/ollama.py` — production adapter
- Any mock/fake `LLMPort` in test fixtures (e.g., `tests/unit/conftest.py`)
- NoOp adapter if one exists for the LLM port

The new parameters are keyword-only with `None` defaults, so existing call sites that don't pass them will continue to work. But the ABC signature change requires all subclasses to match.

---

## 7. Testing

### 7.1 Model Registry Tests
- `get_model_spec("qwen2.5:7b")` returns correct spec
- `get_model_spec("unknown_model")` returns `None`
- `get_model_spec("  qwen2.5:7b  ")` returns correct spec (strip)
- All registered models have `context_window > default_max_completion`

### 7.2 Prompt Guard Tests
- Prompt within budget → returned unchanged
- Prompt exceeds budget → prior outputs truncated, PRD preserved
- Prompt exceeds budget after truncation → structured task failure with diagnostics
- Unknown context window → returned unchanged with debug log
- Empty prior outputs → no truncation needed
- Structured logging emitted on truncation (warning level) and on skip (debug level)

### 7.3 LLM Port Interface Tests
- `chat()` with `max_tokens=None` → adapter uses default (backward compat)
- `chat()` with `max_tokens=8000` → adapter passes to LLM
- `chat()` with `timeout_seconds=300` → adapter uses specified timeout
- All mock/fake LLMPort implementations accept new params without error

### 7.4 Handler Integration Tests
- Handler with `python_cli` capability → `max_tokens=4000`
- Handler with `fullstack_fastapi_react` → `max_tokens=12000`
- Handler with model spec capping → `max_tokens` reduced to model's `default_max_completion`
- QA handler passes `test_timeout_seconds` from capability to test runner
- Builder handler does NOT read `DevelopmentCapability` — uses adapter defaults

### 7.5 Config Tests
- `LLMConfig` with `generation_timeout=300` → valid
- `LLMConfig` with `generation_timeout=5` → rejected (below minimum)
- Default config backward compatible

---

## 8. Files Modified (Estimated)

| File | Change |
|------|--------|
| `src/squadops/ports/llm/provider.py` | Extend `chat()` signature |
| `adapters/llm/ollama.py` | Pass new params to Ollama API |
| `src/squadops/llm/model_registry.py` | **New** — model spec registry |
| `src/squadops/capabilities/dev_capabilities.py` | Add `max_completion_tokens`, `test_timeout_seconds` fields |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | `_estimate_tokens()`, `_guard_prompt_size()`, handler wiring for Dev + QA |
| `src/squadops/config/schema.py` | Add `generation_timeout` to `LLMConfig` |
| `tests/unit/llm/test_model_registry.py` | **New** |
| `tests/unit/capabilities/test_prompt_guard.py` | **New** |
| `tests/unit/capabilities/test_build_handlers.py` | Token budget + timeout assertions |
| `tests/unit/capabilities/test_dev_capabilities.py` | New field assertions |
| Test fixtures / mock LLM ports | Update `chat()` signature to accept new params |
