# Plan: SIP-0085 Console Messaging Capability for Live Agents via A2A

## Context

SIP-0085 adds a real-time messaging surface to SquadOps. Agent containers that opt into messaging run a lightweight A2A-compliant HTTP/SSE server alongside their existing RabbitMQ task consumer, sharing the same `PortsBundle`. The runtime-API acts as an A2A client proxy, forwarding console chat requests to the targeted agent and streaming responses back via SSE. Chat history is persisted in Postgres with a Redis hot cache.

Joi (comms role) is the first agent to enable messaging by default. The architecture is role-generic — any agent can enable messaging by configuration.

**Branch:** `feature/sip-0085-console-messaging` (off main)
**SIP:** `sips/accepted/SIP-0085-Console-Messaging-Capability-for.md`

### Phase Audit Gates

Each phase pauses for audit before proceeding. Phase 3 is the critical audit gate — the full backend loop must be proven before designing the UI surface.

| Phase | Audit | Gate |
|-------|-------|------|
| 1 | A2A foundation works: server starts, card discoverable, streaming loop proven | Proceed to Phase 2 |
| 2 | Executor streams, dual-surface container runs, prompt fragment wired | Proceed to Phase 3 |
| 3 | **Full backend audit**: API proxy works, persistence proven, curl-testable end-to-end | Plan Phase 4 UI in detail |
| 4 | Chat overlay functional in console | Proceed to Phase 5 |
| 5 | Observability verified, version bump | Ship |

---

## v1 Scope Rules

These rules protect the implementation from scope drift. Anything not listed here is out of scope.

### Source of Truth for Chat History
- **Postgres is authoritative** for persisted chat history.
- **Redis is an opportunistic hot cache.** Failed Redis writes do not fail the conversation. Failed Postgres writes fail the persistence guarantee and must be logged.
- **Runtime-API assembles prior history** from Postgres (via Redis cache) and injects it into the A2A message forwarded to the agent.
- **A2A transport context is transport metadata, not canonical history.** The executor does not rely on A2A SDK context for conversation history — it receives history assembled by the proxy.

### Streaming Contract
- `chat_stream()` on `LLMPort` is a **text-only streaming contract**: `AsyncIterator[str]` yielding plain text chunks.
- Richer streaming semantics (tool events, structured messages, usage metadata, termination reasons) are explicitly deferred. If needed later, a `StreamEvent` model can wrap the iterator without breaking existing consumers.
- Runtime-API relays agent text chunks to the console as SSE `data:` frames. No structured event envelope in v1.

### Console Streaming Method
- `POST /api/chat/{agent_id}` accepts the user message and returns a `StreamingResponse` with `media_type="text/event-stream"`.
- The console consumes this via `fetch()` with streaming body reader (not `EventSource`, which is GET-only).
- There is no separate GET SSE endpoint. One POST, one streaming response.

### Grounding Behavior Rule
- Chat agents answer from injected status summaries only. No deep artifact queries, no evidence traversal.
- **If structured state is insufficient, the agent must answer conservatively**: "I don't have that detail right now." This is a behavior requirement enforced by the system prompt, not just a prompt hint.
- The prompt fragment must include this rule explicitly with the exact phrasing.

### Memory Scope
- Retrieval is best-effort and bounded (max 5 results per query).
- Writes happen only on explicit user intent ("remember this", "note that").
- No automatic extraction. No expectation of rich long-term conversational continuity.
- Memory is secondary to the chat loop — if memory wiring is incomplete at ship time, ship without it and add in a follow-up.

### UI Scope
- **Backend is agent-generic**: any messaging-enabled agent is reachable via the API.
- **Console UI ships Joi-only**: Joi is the default and only presented chat target in the initial release. The agent selector exists but defaults to Joi.

### Out of Scope for v1
- Agent-to-agent conversational coordination
- Broadcast or channel messaging
- Discord or Slack adapters
- Workflow delegation from chat
- Automatic memory extraction
- Push notifications
- Rich streaming event types (tool use, structured messages)

---

## Phase 1: A2A Foundation (Port, Adapters, LLM Streaming)

### Minimum Acceptance for Phase 1
Phase 1 is complete when:
1. An agent-local A2A messaging server can start and stop.
2. An agent card is discoverable at `/.well-known/agent-card.json`.
3. `chat_stream()` exists on `LLMPort` and is implemented in the Ollama adapter.
4. The A2A client adapter can send a message and stream a response through the full loop (agent server → client → SSE chunks).

Everything else in this phase is secondary to these four conditions.

### Runtime Contracts

**P1-RC1 (MessagingPort shape):** `MessagingPort` is an abstract base class in `src/squadops/ports/comms/messaging.py`. It defines the contract for an A2A-capable agent server — start, stop, health. It does NOT define chat logic (that lives in `ChatAgentExecutor`). The port represents the A2A server lifecycle.

**P1-RC2 (chat_stream is text-only):** `chat_stream()` on `LLMPort` returns `AsyncIterator[str]` — plain text chunks only. All parameters match `chat()`: `messages`, `model`, `max_tokens`, `temperature`, `timeout_seconds` — all default `None`. This is intentionally a text-only streaming contract for v1. Richer event types are deferred.

**P1-RC3 (Adapter wraps SDK, not business logic):** The A2A server adapter wraps the SDK's HTTP/SSE application. The adapter owns HTTP server lifecycle (start/stop/health). The executor (chat logic) is injected, not owned by the adapter. All SDK-specific imports and class names are confined to the adapter module.

**P1-RC4 (A2A client decision):** v1 uses raw `httpx` streaming behind the adapter boundary for the client side. The A2A SDK client API may not provide the SSE streaming ergonomics we need, and wrapping raw HTTP is simpler for a proxy use case. The adapter boundary means we can swap to SDK client later without changing callers.

### 1a. MessagingPort interface

**New file:** `src/squadops/ports/comms/messaging.py`

```python
"""Messaging port — A2A server lifecycle contract (SIP-0085)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MessagingPort(ABC):
    """Abstract interface for agent messaging server.

    Manages the lifecycle of an A2A-compliant HTTP/SSE server
    running inside an agent container. The chat logic itself
    lives in ChatAgentExecutor, not in this port.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the messaging server."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the messaging server."""
        ...

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check messaging server health."""
        ...
```

**Modified file:** `src/squadops/ports/comms/__init__.py` — export `MessagingPort`.

### 1b. Add chat_stream() to LLMPort

**Modified file:** `src/squadops/ports/llm/provider.py`

Add after existing `chat()` method:

```python
@abstractmethod
async def chat_stream(
    self,
    messages: list[ChatMessage],
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
) -> AsyncIterator[str]:
    """Stream chat response as plain text chunks.

    Text-only streaming contract (SIP-0085). Returns an async iterator
    of string chunks. Richer event types (tool calls, usage metadata)
    are not supported in this contract.

    Same parameters as chat(). All default None for adapter fallback.
    """
    ...
    yield  # pragma: no cover — makes this a proper async generator for ABC
```

Add `AsyncIterator` to imports from `collections.abc`.

### 1c. Implement chat_stream() in Ollama adapter

**Modified file:** `adapters/llm/ollama.py`

Add `chat_stream()` method after existing `chat()` (around line 173). The existing `chat()` builds a payload against `/api/chat` with `"stream": false`. The streaming variant uses `"stream": true` and reads from httpx's async streaming response.

Refactor: extract `_build_chat_payload()` helper from existing `chat()` to share payload construction. This avoids duplicating model/temperature/max_tokens/options assembly.

```python
async def chat_stream(
    self,
    messages: list[ChatMessage],
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
) -> AsyncIterator[str]:
    """Stream chat response from Ollama."""
    resolved_model = model or self._default_model
    payload = self._build_chat_payload(
        messages, resolved_model, max_tokens, temperature, stream=True,
    )
    timeout = httpx.Timeout(timeout_seconds or self._default_timeout)

    async with self._client.stream(
        "POST", f"{self._base_url}/api/chat", json=payload, timeout=timeout,
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
```

**Implementation note:** Verify Ollama `/api/chat` with `stream: true` returns newline-delimited JSON with `message.content` field at implementation time.

### 1d. A2A server adapter

**New file:** `adapters/comms/a2a_server.py`

Wraps the A2A SDK server components. All SDK-specific imports are confined to this module.

The adapter:
- Accepts an agent card (discovery metadata) and an executor (chat logic) at construction
- Owns HTTP server lifecycle via uvicorn
- Implements `MessagingPort` (start/stop/health)

**Implementation note:** The exact SDK class names (`A2AStarletteApplication`, `AgentExecutor`, `AgentCard`, etc.) must be verified against the installed `a2a-sdk` version at the start of Phase 1. The adapter structure is stable regardless of SDK naming — it wraps whatever the SDK provides for "build an HTTP/SSE app from an executor and card."

Includes `build_agent_card()` helper that constructs the SDK agent card type from instance config fields (agent_id, display_name, description, role, version, port).

### 1e. A2A client adapter

**New file:** `adapters/comms/a2a_client.py`

v1 uses raw `httpx` streaming behind the adapter boundary. The client:
- Sends a POST with JSON body to the agent's A2A endpoint
- Reads the SSE stream (`text/event-stream`) and yields `data:` payloads
- Fetches agent cards via GET `/.well-known/agent-card.json`
- Is stateless per-request — session state lives in Redis/Postgres

The adapter boundary means this can be swapped to SDK client later without changing callers.

### 1f. Requirements update

**Modified file:** `requirements/agents.txt` (or wherever agent dependencies are declared)

Add:
```
a2a-sdk[http-server]>=0.3.0
```

Verify compatibility with existing `httpx`, `pydantic`, `starlette` versions.

### 1g. Tests

| Test file | Tests | What bug would this catch? |
|-----------|-------|---------------------------|
| `tests/unit/ports/test_messaging_port.py` | Port contract test — ABC not instantiable | Accidental concrete base class |
| `tests/unit/llm/test_chat_stream.py` | `chat_stream()` yields chunks in order, handles empty chunks, raises on timeout | Streaming bugs, missing error handling |
| `tests/unit/adapters/test_a2a_server.py` | Adapter construction, start/stop lifecycle, health states | Server lifecycle mismanagement |
| `tests/unit/adapters/test_a2a_client.py` | SSE `data:` parsing, agent card fetch, connection error handling, timeout | Client streaming bugs, error propagation |

---

## Phase 2: Chat Executor and Agent Wiring

### Runtime Contracts

**P2-RC1 (Role-generic executor):** `ChatAgentExecutor` has zero role-specific code. Identity comes entirely from `role_id` → `prompt_service.get_system_prompt(role_id)`. If you instantiate it with `role_id="dev"`, it responds as Neo. With `role_id="comms"`, it responds as Joi.

**P2-RC2 (PortsBundle addition):** `messaging: MessagingPort | None = None` is added as the last optional field on `PortsBundle`. No changes to `BaseAgent.__init__()` signature — messaging is on the bundle, not a separate constructor arg.

**P2-RC3 (Entrypoint dual-service):** The entrypoint starts the A2A server as an `asyncio.create_task()` alongside the existing RabbitMQ consumer loop. Both share the same `PortsBundle`. On shutdown, both are cancelled/stopped.

**P2-RC4 (Memory is secondary):** Memory writes and retrieval are wired in this phase but are not blocking for phase completion. If memory integration is incomplete, the executor ships without it and memory is added in a follow-up.

**P2-RC5 (History comes from proxy, not A2A context):** The executor receives conversation history assembled and injected by the runtime-API proxy (Phase 3). It does not parse A2A SDK context objects for history. In Phase 2 (before the proxy exists), tests mock the injected history.

**P2-RC6 (Deferred wiring — decided):** PortsBundle construction uses `dataclasses.replace()`:
1. Build PortsBundle without messaging (`messaging=None`)
2. Create `ChatAgentExecutor` with that bundle
3. Create `A2AServerAdapter` with the executor
4. Produce final bundle: `final_ports = dataclasses.replace(ports, messaging=adapter)`
5. Assign final bundle to the system before run

This preserves the frozen dataclass invariant. The executor holds a reference to the original bundle (without messaging on it), which is fine — the executor never accesses `ports.messaging`.

### 2a. Add messaging to PortsBundle

**Modified file:** `src/squadops/agents/base.py`

Add to `PortsBundle` (after `request_renderer`):

```python
messaging: MessagingPort | None = None
```

Add to TYPE_CHECKING imports:

```python
from squadops.ports.comms.messaging import MessagingPort
```

No changes to `BaseAgent.__init__()`.

### 2b. ChatAgentExecutor

**New file:** `src/squadops/agents/executors/chat_executor.py`

Role-generic chat executor. Key behaviors:
- Receives `PortsBundle` and `role_id` at construction
- `execute()` extracts user text and injected context from the incoming message
- Assembles system prompt via `ports.prompt_service.get_system_prompt(role_id)`
- Optionally retrieves relevant memories via `ports.memory.search()` (best-effort, bounded to 5 results)
- Calls `ports.llm.chat_stream()` and enqueues text chunks to the A2A event queue
- Logs `chat_message_received` and `chat_response_complete` with role_id and session_id

The executor does NOT:
- Parse A2A context for conversation history (history is injected by the proxy)
- Access `ports.messaging` (it doesn't need its own server reference)
- Contain any role-specific logic

**Implementation note:** SDK-specific types (`AgentExecutor`, `EventQueue`, `RequestContext`, event helpers) are imported from `a2a-sdk`. Exact import paths are confirmed during Phase 1 SDK verification. The executor method signatures conform to whatever ABC the SDK provides.

### 2c. Comms role prompt fragment

**New file:** `src/squadops/prompts/fragments/roles/comms/identity.md`

Follows YAML frontmatter + markdown body format. Must include:
- Role identity (Joi, communications agent)
- Grounding rule with exact conservative answer phrasing: "I don't have that detail right now."
- Memory instructions (explicit writes only, confirm what was stored)

**New file:** `src/squadops/prompts/request_templates/request.chat_response.md`

Chat response request template.

**Modified file:** `src/squadops/prompts/fragments/manifest.yaml`

Add fragment entry for `roles/comms/identity.md` with computed SHA256 hash. Regenerate `manifest_hash`.

### 2d. Wire executor into entrypoint

**Modified file:** `src/squadops/agents/entrypoint.py`

In `_create_ports()`, conditionally create the A2A messaging adapter using the deferred wiring sequence (P2-RC6):

```python
# 1. Build PortsBundle without messaging
ports = PortsBundle(llm=llm, memory=memory, ..., messaging=None)

# 2. Conditionally wire A2A
if instance_config.get("a2a_messaging_enabled", False):
    executor = ChatAgentExecutor(ports=ports, role_id=role)
    agent_card = build_agent_card(...)
    adapter = A2AServerAdapter(agent_card=agent_card, executor=executor, port=a2a_port)
    ports = dataclasses.replace(ports, messaging=adapter)
```

In the main run loop, start A2A server as background task:

```python
async def _run(self):
    consumer_task = asyncio.create_task(self._consume_tasks())

    a2a_task = None
    if self._system.ports.messaging is not None:
        a2a_task = asyncio.create_task(self._system.ports.messaging.start())

    try:
        await asyncio.gather(consumer_task, *([a2a_task] if a2a_task else []))
    finally:
        if self._system.ports.messaging is not None:
            await self._system.ports.messaging.stop()
```

### 2e. Update instances.yaml

**Modified file:** `agents/instances/instances.yaml`

Update comms-agent entry:

```yaml
- id: comms-agent
  display_name: Joi
  role: comms
  model: llama3.1:8b
  enabled: true
  description: "Communications - Conversational interface"
  a2a_messaging_enabled: true
  a2a_port: 8080
```

### 2f. Update docker-compose.yml

**Modified file:** `docker-compose.yml`

Uncomment the comms-agent (joi) container section. Expose A2A port. Runtime-API needs network access to `joi:8080` for proxying.

### 2g. Tests

| Test file | Tests | What bug would this catch? |
|-----------|-------|---------------------------|
| `tests/unit/agents/test_chat_executor.py` | Mock LLM streams chunks correctly; works with role_id="comms" and role_id="dev" (proving genericity); handles cancel; conservative answer when grounding is empty; memory store triggered on "remember this"; memory retrieval returns bounded results | Role-specific leak, broken streaming, grounding bypass, memory wiring |
| `tests/unit/agents/test_base_agent.py` | PortsBundle with messaging=None (backward compat), PortsBundle with messaging set, dataclasses.replace produces valid bundle | Bundle construction regression |
| `tests/unit/prompts/test_comms_fragments.py` | Comms identity fragment loads, manifest hash valid after addition | Fragment registration bugs |

---

## Phase 3: Runtime-API Chat Proxy and Persistence

### Runtime Contracts

**P3-RC1 (Proxy, not processor):** The runtime-API chat routes never call LLM directly. They forward the message to the agent's A2A endpoint and relay the SSE stream back. Auth context (user identity from JWT) is forwarded.

**P3-RC2 (Postgres is authoritative):** Postgres is the source of truth for chat history. Redis is an opportunistic cache. Failed Redis writes do not fail the conversation. Failed Postgres writes fail the persistence guarantee and must be logged as errors.

**P3-RC3 (History assembly):** The runtime-API loads conversation history from Redis (or Postgres on cache miss), assembles it with grounding context (existing DTOs), and injects both into the A2A message sent to the agent. The agent receives a fully assembled context — it does not query history or grounding itself.

**P3-RC4 (Streaming method):** `POST /api/chat/{agent_id}` returns a `StreamingResponse` with `media_type="text/event-stream"`. The console consumes via `fetch()` streaming body reader. There is no separate GET SSE endpoint.

**P3-RC5 (Migration is additive only):** Migration `006_chat_tables.sql` adds new tables only. Legacy tables (e.g., `squadcomms_messages`) are NOT dropped in this migration. Cleanup is a separate housekeeping migration later.

### 3a. Chat domain models

**New file:** `src/squadops/comms/models.py`

Frozen dataclasses: `ChatSession` (session_id, agent_id, user_id, started_at, ended_at, metadata) and `ChatMessage` (message_id, session_id, role, content, created_at, metadata). Plus `AgentMessagingConfig` for instance config.

### 3b. Chat API routes

**New directory:** `src/squadops/api/routes/chat/`

Minimal v1 route surface:

| Method | Path | Purpose | Priority |
|--------|------|---------|----------|
| `POST` | `/api/chat/{agent_id}` | Send message, stream response | Required |
| `GET` | `/api/agents/messaging` | List messaging-enabled agents | Required |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Get session message history | Required |
| `GET` | `/api/chat/{agent_id}/sessions` | List sessions for agent+user | Deferrable |

The `POST` route:
1. Validates agent has `a2a_messaging_enabled` (400 if not)
2. Resolves or creates session (Postgres + Redis)
3. Persists user message (Postgres required, Redis best-effort)
4. Loads prior history from Redis (Postgres fallback on miss)
5. Assembles grounding context from existing `CycleToResponseDTO`, `RunToResponseDTO`
6. Forwards assembled A2A message to agent via `A2AClientAdapter`
7. Returns `StreamingResponse(media_type="text/event-stream")` relaying agent chunks
8. On stream completion, persists assembled agent response (Postgres required, Redis best-effort)

**New file:** `src/squadops/api/routes/chat/dtos.py`

`ChatMessageRequest`, `ChatSessionDTO`, `ChatMessageDTO`.

### 3c. Chat persistence (Postgres)

**New file:** `adapters/persistence/chat_repository.py`

`ChatRepository` with methods: `create_session`, `end_session`, `store_message`, `get_session_messages`, `list_sessions`. Takes asyncpg pool at construction.

### 3d. DDL migration

**New file:** `infra/migrations/006_chat_tables.sql`

```sql
-- SIP-0085: Chat persistence tables (additive only)

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id      TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES chat_sessions(session_id),
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session
    ON chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_agent
    ON chat_sessions(agent_id, started_at);
```

No `DROP TABLE` statements. Legacy table cleanup is a separate migration.

### 3e. Redis session cache

Uses existing Redis connection from runtime-API. Keys:
- `chat:session:{session_id}:messages` — list of recent messages (JSON)
- `chat:session:{session_id}:meta` — session metadata
- TTL: configurable, default 1 hour

Read path: Redis first → Postgres fallback → repopulate Redis.
Write path: Postgres (required) + Redis (best-effort, log on failure).

### 3f. Config schema update

**Modified file:** `src/squadops/config/schema.py`

Add to `AgentConfig`:

```python
a2a_messaging_enabled: bool = Field(default=False)
a2a_port: int = Field(default=8080, ge=1024, le=65535)
```

### 3g. Mount chat routes

**Modified file:** `src/squadops/api/runtime/main.py`

Mount chat router. Initialize `ChatRepository` and `A2AClientAdapter` in startup sequence, store in app state.

### 3h. Tests

| Test file | Tests | What bug would this catch? |
|-----------|-------|---------------------------|
| `tests/unit/api/test_chat_routes.py` | POST streams response, persists to Postgres, returns 400 for disabled agent, returns 404 for unknown agent; GET messages returns ordered history; Postgres write failure logged as error | Route logic, validation, durability semantics |
| `tests/unit/adapters/test_chat_repository.py` | CRUD operations, message ordering, session listing | Persistence bugs, SQL errors |
| `tests/unit/comms/test_models.py` | Frozen dataclass immutability, field defaults | Model construction |

---

## Phase 4: Console Chat UI

**Deferred until after Phase 3 audit.** Phase 4 will be planned in detail after Phases 1-3 are implemented and audited. The notes below capture the known constraints.

### Approach: Modal Overlay, Not a Perspective

The chat UI is a **modal overlay / drawer** triggered from the left sidebar rail — not a new console perspective. It overlays whatever perspective is currently active (cycles, runs, etc.), so the user can chat with Joi without navigating away from their work.

### Known Constraints

**P4-RC1 (Joi-only UI, generic backend):** Console presents Joi as the chat target. Backend is fully agent-generic — the UI constraint is purely a scope decision for initial release.

**P4-RC2 (fetch streaming, not EventSource):** Console uses `fetch()` with streaming body reader against `POST /api/chat/{agent_id}`. Not `EventSource` (which is GET-only).

**P4-RC3 (Overlay, not perspective):** Chat is a sidebar-triggered modal/drawer, not a routed perspective. It floats over the active view and can be opened/closed without losing context.

### Scope (to be detailed after Phase 3 audit)

- Chat icon in left sidebar rail triggers the overlay
- Message input, streaming response display
- Joi as default and initially only chat target
- Session management: create new, resume existing, clear
- Basic agent status indicator
- `fetch()` streaming consumption:

```javascript
const response = await fetch(`/api/chat/${agentId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ content: userMessage, session_id: sessionId }),
});
const reader = response.body.getReader();
const decoder = new TextDecoder();
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    // Parse SSE data: lines, append to display
    appendChunks(text);
}
```

### 4b. Tests

Component tests for chat panel rendering, streaming consumption, session state management.

---

## Phase 5: Observability and Polish

Observability is layered by priority. Do not let telemetry polish hold the feature hostage.

### Observability Priority

| Priority | What | Phase 5 status |
|----------|------|----------------|
| Required | Structured logging (session lifecycle, errors) | Already in Phase 2/3 — verify and fill gaps |
| Preferred | LangFuse generation capture for chat | Wire in this phase |
| Stretch | Metrics (counters, histograms, gauges) | Add if time permits |

### 5a. Structured logging (verify)

Verify Phase 2/3 logging is complete:
- `chat_message_received` — role_id, session_id (executor)
- `chat_response_complete` — role_id, session_id (executor)
- `chat_session_created` — agent_id, user_id, session_id (route)
- `chat_persistence_failed` — error detail (repository, on Postgres write failure)

### 5b. LangFuse recording (preferred)

Adapt the existing LangFuse generation pattern for streaming:
- Open generation span before `chat_stream()` starts
- Accumulate full response text during streaming
- Close span with full response and token counts after stream ends

Pattern reference: `_handle_chat_message()` in `entrypoint.py` lines 485-534.

### 5c. Metrics (stretch)

Via existing `MetricsPort`:
- `chat_messages_total` counter (agent_id, role)
- `chat_response_latency_seconds` histogram (agent_id)
- `chat_sessions_active` gauge (agent_id)

### 5d. Version bump

Bump to next patch in `pyproject.toml`.

### 5e. SIP promotion

```bash
SQUADOPS_MAINTAINER=1 python scripts/maintainer/update_sip_status.py \
    sips/accepted/SIP-0085-Console-Messaging-Capability-for.md implemented
```

### 5f. Tests

| Test file | Tests | What bug would this catch? |
|-----------|-------|---------------------------|
| `tests/unit/agents/test_chat_observability.py` | LangFuse span opened/closed around streaming, full response accumulated | Silent observability failures |

---

## Acceptance Criteria Mapping

| AC | Type | Phase | Verification |
|----|------|-------|-------------|
| 1. Dual-surface container (RabbitMQ + A2A) | Must prove | 2d | E2E: comms-agent starts both services |
| 2. AgentCard at `/.well-known/agent-card.json` | Must prove | 1d | Unit + E2E: card construction and curl |
| 3. Streaming response grounded in status | Must prove | 2b, 3b | Unit: executor streams; E2E: response references project state |
| 4. Console renders streamed responses | Must prove | 4a | Component test: chunks render token-by-token |
| 5. Runtime-API proxies to agent A2A endpoint | Must prove | 3b | Unit: route forwards; E2E: full proxy path |
| 6. Persistence survives Redis TTL expiry | Must prove | 3c-3e | Integration: expire Redis, reload from Postgres |
| 7. `chat_stream()` produces async iterator | Must prove | 1b, 1c | Unit: Ollama adapter yields chunks |
| 8. Discovery returns messaging-enabled agents only | Must prove | 3b | Unit: filter logic |
| 9. Any agent can enable messaging by config | Arch intent | 2d | Design property — verified by code review, not mandatory second-agent test |
| 10. LangFuse records chat generations | Preferred | 5b | Unit: generation span with chat metadata |
| 11. Memory writes stored and retrievable | Arch intent | 2b | Secondary to chat loop — can ship without if incomplete |

---

## Dependencies and Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| `a2a-sdk` API surface differs from plan | All SDK usage behind adapter boundaries. First task in Phase 1: `pip install a2a-sdk[http-server]`, verify imports, update adapter code. Pin version. |
| Deferred PortsBundle wiring | Decided: `dataclasses.replace()` (P2-RC6). No ambiguity. |
| Ollama streaming chunk format | Verify `/api/chat` with `stream: true` at start of Phase 1. |
| Redis/Postgres write coupling | Postgres is authoritative. Redis failures are logged, not propagated. (P3-RC2) |
| Console streaming method | `fetch()` body reader, not `EventSource`. (P4-RC2) |
| Feature creep from memory or observability | Memory is secondary (ship without if incomplete). Observability is layered (logs required, LangFuse preferred, metrics stretch). |
