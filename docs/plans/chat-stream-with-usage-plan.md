# Plan: Switch cycle task handlers from `chat()` to `chat_stream()`

## Context
On DGX Spark, the 72b model takes 5-9 minutes per task. With `chat()` using `stream: False`, the entire response is a single HTTP request that sits idle for minutes — risking proxy/client timeouts. `chat_stream()` keeps the connection alive with flowing chunks and eliminates this timeout class entirely. We also want to preserve the t/s observability we just added.

## Problem
1. `chat_stream()` returns `AsyncIterator[str]` — text only, no token metadata
2. Ollama's final streamed chunk (`done: true`) contains `eval_count`, `eval_duration`, `prompt_eval_count` — currently discarded
3. Handlers need token data for `GenerationRecord` / LangFuse observability

## Approach: New `chat_stream_with_usage()` method

Rather than changing the existing `chat_stream()` contract (which is used by A2A chat executor for real-time streaming to users), add a parallel method that accumulates text and captures the final chunk's metadata, returning a `ChatMessage` with full token data — same shape handlers already expect.

### Behavioral contract
- **Internal streaming only** — `chat_stream_with_usage()` uses streaming transport for connection liveness, but returns only the final assembled response. It does not deliver partial chunks to callers.
- **Final assembled response only** — callers receive a single `ChatMessage` after the stream completes. No partial content is ever surfaced as a successful result.
- **Usage metadata is best-effort** — token counts and `tokens_per_second` default to `None` when absent. `tokens_per_second` is computed only when both `eval_count` and `eval_duration` are present and non-zero. A missing final usage chunk never fails the request.
- **Same failure semantics as `chat()`** — if the stream is interrupted, times out, or fails before the final completion chunk, raise the same adapter exceptions (`LLMTimeoutError`, `LLMError`) as `chat()`. Partial text is discarded, never returned as a successful `ChatMessage`.

### Edge cases
| Scenario | Behavior |
|----------|----------|
| Missing final usage metadata | `tokens_per_second`, `prompt_tokens`, `completion_tokens`, `total_tokens` all `None` — generation recording degrades gracefully |
| Interrupted stream (connection drop) | Raise `LLMError` — partial text discarded |
| `timeout_seconds` exceeded during stream | Raise `LLMTimeoutError` — same as `chat()` |
| Empty or role-only chunks mid-stream | Ignored — only non-empty `message.content` text deltas are appended to the output buffer |
| `done: true` chunk with partial fields | Compute what we can, leave the rest `None` |

## Steps

### Step 1: Add `chat_stream_with_usage()` to Ollama adapter
**File:** `adapters/llm/ollama.py`

New async method that:
- Streams via `/api/chat` with `stream: True` (keeps connection alive)
- Accumulates only non-empty assistant text deltas from `message.content` — ignores structural/non-content chunks except the final usage metadata
- Parses the final `done: true` chunk for `eval_count`, `eval_duration`, `prompt_eval_count`
- Returns a `ChatMessage` with full content + token metadata + tokens_per_second
- Logs t/s at INFO level (same as current `chat()`)

```python
async def chat_stream_with_usage(
    self,
    messages: list[ChatMessage],
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
) -> ChatMessage:
    """Stream chat response internally, return complete ChatMessage with usage."""
```

This keeps the same return type as `chat()` — handlers don't change their post-LLM logic at all.

### Step 2: Add `chat_stream_with_usage()` to LLMPort and LLMRouter
**Files:** `src/squadops/ports/llm/provider.py`, `src/squadops/llm/router.py`

Add the method to the port interface with a default implementation that falls back to `chat()` — providers may override, but the default behavior is `return await self.chat(...)`. This keeps non-Ollama adapters working without code changes. Router passes through to the resolved provider.

### Step 3: Switch handler call sites from `chat()` to `chat_stream_with_usage()`
**File:** `src/squadops/capabilities/handlers/cycle_tasks.py`

4 call sites — mechanical replacement:
- `_CycleTaskHandler.handle()`
- `DevelopmentDevelopHandler.handle()`
- `QATestHandler.handle()`
- `BuilderAssembleHandler.handle()`

Each changes from:
```python
response = await context.ports.llm.chat(messages, **chat_kwargs)
```
To:
```python
response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
```

Everything downstream (`response.content`, `response.tokens_per_second`, `_record_generation(chat_response=response)`) stays identical.

### Step 4: Leave existing `chat()` and `chat_stream()` unchanged
- `chat()` — still available for cases that don't need streaming
- `chat_stream()` — still used by A2A `ChatAgentExecutor` for real-time chunk delivery to users

---

### Step 5: Operational profile tuning for Spark
**File:** `config/squad-profiles.yaml`

Drop neo (dev) and nat (strat) from `qwen2.5:72b` to `qwen2.5:32b` in the `spark-squad-with-builder` profile. The 72b model takes 5-9 minutes per task — 32b significantly cuts latency while still producing much better output than 7b. Builder (bob) stays at 72b since assembly is the most context-heavy task.

Note: the streaming transport fix (Steps 1–4) is required regardless of model downsizing, because builder remains at 72b and future tasks on any model may still be long-running. Step 5 is latency reduction, not a correctness fix.

```yaml
  - profile_id: spark-squad-with-builder
    agents:
      - { agent_id: max, role: lead, model: "qwen2.5:7b", enabled: true }
      - { agent_id: neo, role: dev, model: "qwen2.5:32b", enabled: true }      # was 72b
      - { agent_id: nat, role: strat, model: "qwen2.5:32b", enabled: true }     # was 72b
      - { agent_id: bob, role: builder, model: "qwen2.5:72b", enabled: true }
      - { agent_id: eve, role: qa, model: "qwen2.5:7b", enabled: true }
      - { agent_id: data, role: data, model: "qwen2.5:7b", enabled: true }
```

## Cut line
- **Required for merge (correctness fix):** Steps 1–4 (adapter, port, router, call sites)
- **Optional, recommended in same change (performance tuning):** Step 5 (Spark profile 32b)

## Why this approach
- **Zero change to handler post-LLM logic** — same `ChatMessage` return type
- **No change to existing contracts** — `chat()` and `chat_stream()` untouched
- **Token observability preserved** — final chunk metadata flows through
- **Connection stays alive** — streaming prevents idle timeout
- **Fallback safety** — default implementation calls `chat()`, so non-Ollama providers work

## Files to modify
1. `adapters/llm/ollama.py` — add `chat_stream_with_usage()`
2. `src/squadops/ports/llm/provider.py` — add default method with `chat()` fallback
3. `src/squadops/llm/router.py` — add passthrough
4. `src/squadops/capabilities/handlers/cycle_tasks.py` — switch 4 call sites
5. `config/squad-profiles.yaml` — switch dev/strat to 32b in spark profile

## Verification
1. `ruff check . --fix && ruff format .`
2. `./scripts/dev/run_affected_tests.sh --branch`
3. `./scripts/dev/ops/rebuild_and_deploy.sh agents` — rebuild agents
4. Run a cycle on Spark and verify:
   - Agent logs show t/s output (same as before)
   - No HTTP timeout on long model calls
   - LangFuse shows token counts in generation metadata
   - Dev/strat tasks complete faster with 32b vs 72b
5. Verify fallback path: a non-Ollama provider still works through the default `chat()` fallback without code changes
6. Verify graceful degradation: generation recording succeeds when usage metadata is present, and degrades gracefully (fields `None`) when absent
