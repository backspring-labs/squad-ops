---
title: Console Messaging Capability for Live Agents via A2A
status: implemented
author: jladd
created_at: '2026-03-15T00:00:00Z'
sip_number: 85
updated_at: '2026-03-16T18:55:31.342348Z'
---
# SIP: Console Messaging Capability for Live Agents via A2A

## Status
Draft

## Summary
Add a real-time messaging surface to SquadOps. Agent containers that opt into messaging run a lightweight A2A-compliant HTTP/SSE server alongside their existing RabbitMQ task consumer, sharing the same `PortsBundle`. The runtime-API acts as an A2A client proxy, forwarding console chat requests to the targeted agent and streaming responses back via SSE. Chat history is persisted in Postgres with a Redis hot cache.

Joi (comms role) is the first agent to enable messaging by default. Her identity, prompt fragments, and contextual grounding follow the same prompt registry and assembly patterns established in SIP-0084. The architecture is role-generic — any agent can enable messaging by configuration.

Discord and other external channel adapters are deferred to a subsequent SIP.

## SIP Relationships
- **Extends SIP-0084** (Prompt Registry): System prompts assembled from prompt fragments via `PromptService`.
- **Extends SIP-0061** (LangFuse): Chat LLM generations recorded through `LLMObservabilityPort`.
- **Builds on SIP-0073** (LLM Budget/Timeout): Chat responses respect token budget and timeout controls.
- **Future SIP**: Discord adapter, broadcast channels, workflow delegation from chat.

## Problem
SquadOps has no conversational interface for human-to-agent interaction. The only way to interact with agents is through cycle/run task dispatch via RabbitMQ. There is no direct chat experience in the console, no way to ask an agent a question about project status, and no real-time conversational surface.

RabbitMQ is designed for asynchronous work dispatch (fire-and-forget with ack), not for request-response conversations with streaming.

## Goals
1. Adopt A2A protocol as the initial messaging foundation for human-to-agent conversations, wrapped behind port/adapter boundaries.
2. Enable agent containers to run a dual interaction surface: RabbitMQ (task dispatch) + A2A HTTP/SSE (messaging).
3. Introduce Joi as the first messaging-enabled agent with console chat by default.
4. Add a console chat UI panel that streams responses in real time.
5. Ground chat responses in project/cycle status summaries (status-level only — not raw evidence traversal).
6. Keep the messaging capability role-generic so other agents can opt in by configuration.

## Non-Goals
1. **Discord or external channel adapters** — deferred to a subsequent SIP.
2. **Multi-agent group chat or broadcast channels** — out of scope. This SIP covers one-to-one human-to-agent conversations.
3. **Workflow delegation from chat** — Joi cannot trigger cycle creation or task dispatch from chat in v1.
4. **Deep evidence retrieval** — chat agents answer from injected status summaries, not arbitrary database or artifact queries. Answers are conservative when coverage is incomplete.
5. **Agent-to-agent messaging** — the infrastructure supports it, but only human-to-agent is wired in v1.
6. **Automatic memory extraction** — v1 uses explicit writes only. LLM-driven post-conversation extraction is future work.

---

## Design

### 1. A2A Protocol Adoption

The Google A2A Python SDK (`a2a-sdk`) provides the messaging protocol, server framework, client library, and SSE streaming infrastructure. SquadOps wraps all SDK usage behind port/adapter boundaries — if the SDK API changes or a different protocol is adopted later, only the adapter layer changes.

Key A2A concepts mapped to SquadOps:

| A2A Concept | SquadOps Mapping |
|-------------|-----------------|
| `AgentCard` | Agent capability advertisement (skills, streaming support, identity) |
| `Message` | Conversational exchange (human ↔ agent) — no task lifecycle |
| `AgentExecutor` | Agent-side message handler — one generic executor for all roles |
| `A2AStarletteApplication` | HTTP/SSE server running inside agent container |
| `EventQueue` | Streaming response buffer — agent pushes text parts, client consumes via SSE |
| `/.well-known/agent-card.json` | Discovery endpoint served by each messaging-enabled container |

Chat exchanges use A2A `Message` objects, not `Task` objects. No task lifecycle is created for a conversation — chat stays lightweight and outside the cycle/run pipeline.

The SDK requires Python 3.10+ and depends on `httpx`, `pydantic`, and `sse-starlette` (for the HTTP server extra). These are compatible with the existing dependency set.

### 2. MessagingPort on PortsBundle

Messaging is a port like any other — `None` when the agent doesn't have it, injected when it does:

```python
@dataclass(frozen=True)
class PortsBundle:
    llm: LLMPort
    memory: MemoryPort
    prompt_service: PromptService
    queue: QueuePort
    metrics: MetricsPort
    events: EventPort
    filesystem: FileSystemPort
    llm_observability: LLMObservabilityPort | None = None
    request_renderer: RequestTemplateRenderer | None = None
    messaging: MessagingPort | None = None          # New — A2A messaging surface
```

The entrypoint creates the A2A server adapter only if `a2a_messaging_enabled` is true in the instance config, otherwise `messaging` stays `None`. The agent container then runs two concurrent services sharing the same runtime:

```
┌─────────────────────────────────────┐
│          Agent Container            │
│                                     │
│  ┌─────────────┐  ┌──────────────┐  │
│  │  RabbitMQ    │  │  A2A Server  │  │
│  │  Consumer    │  │  (HTTP/SSE)  │  │
│  │  (port 5672) │  │  (port 8080) │  │
│  └──────┬───────┘  └──────┬───────┘  │
│         │                 │          │
│         ▼                 ▼          │
│  ┌─────────────────────────────────┐ │
│  │         PortsBundle             │ │
│  │  (LLM, PromptService, Memory,  │ │
│  │   Messaging, Observability)     │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

Because `messaging` lives on `PortsBundle`, task handlers could technically access `ports.messaging` mid-task. This is **enabled by port shape but not exercised in v1** — no task handler references `ports.messaging`. The capability exists so that future agent-to-agent communication has a natural path without separate wiring.

### 3. Joi Agent Profile

Joi uses the existing `comms-agent` entry in `instances.yaml` (id: `comms-agent`, role: `comms`, display name updated to `Joi`).

- `a2a_messaging_enabled: true`

This is agent profile configuration, not a new agent type. Other agents may enable `a2a_messaging_enabled` later. The comms role does not participate in cycle/run task dispatch because no task type in `PLANNING_TASK_STEPS`, `CYCLE_TASK_STEPS`, `BUILD_TASK_STEPS`, or `WRAPUP_TASK_STEPS` routes to it — exclusion is by omission, not by policy flag.

### 4. ChatAgentExecutor (Role-Generic)

Any agent with `a2a_messaging_enabled: true` uses the same `ChatAgentExecutor`. There is no role-specific subclass. The executor resolves identity and behavior from prompt fragments based on the agent's configured `role_id` — the same assembly mechanism used by task handlers.

```python
class ChatAgentExecutor(AgentExecutor):
    """Generic chat executor — any messaging-enabled agent uses this.

    Identity and behavior come from the agent's prompt fragments and
    PortsBundle, not from the executor class.
    """

    def __init__(self, ports: PortsBundle, role_id: str):
        self.ports = ports
        self.role_id = role_id

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()

        # Build conversation history from context
        history = self._build_chat_history(context)

        # Inject grounding context (project/cycle state)
        grounding = await self._fetch_grounding_context()

        # Assemble system prompt from this agent's role fragments
        system_prompt = self.ports.prompt_service.get_system_prompt(self.role_id)

        # Call LLM with streaming via the same LLMPort used for tasks
        async for chunk in self.ports.llm.chat_stream(system_prompt, history):
            await event_queue.enqueue_event(
                new_agent_text_message(chunk)
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            new_agent_text_message("Conversation cancelled.")
        )
```

This is illustrative — the key points are:
- The executor receives the **same `PortsBundle`** used for task handling.
- Identity is resolved from `role_id` → `prompt_service.get_system_prompt(role)`.
- The LLM call goes through the same `LLMPort` (same model, same adapter) as task work.
- Enable chat on Neo, he responds as dev. Enable it on Max, he responds as lead. The executor code is identical across all roles.

### 5. Runtime-API as A2A Client Proxy

The runtime-API does not process chat messages itself. It acts as a thin proxy:

1. Console sends chat message to `POST /api/chat/{agent_id}` on runtime-API
2. Runtime-API resolves the agent's A2A endpoint from configuration
3. Runtime-API uses the A2A SDK `ClientFactory` to forward the message
4. Agent streams response events back via SSE
5. Runtime-API relays the SSE stream to the console client

```
Console  ──HTTP POST──▶  Runtime-API  ──A2A message──▶  Agent Container
Console  ◀──SSE stream──  Runtime-API  ◀──SSE stream───  Agent Container
```

The runtime-API also handles:
- Agent discovery: which agents have `a2a_messaging_enabled`
- Agent card aggregation: `GET /api/agents/{agent_id}/card`
- Auth context: user identity from JWT forwarded to the agent
- Session management: `context_id` maps to Redis-stored conversation session

### 6. Agent Card and Discovery

Each messaging-enabled agent serves an `AgentCard` at `/.well-known/agent-card.json`:

```json
{
  "name": "Joi",
  "description": "Communications agent for SquadOps project status and team interaction",
  "version": "1.0.1",
  "url": "http://comms-agent:8080",
  "capabilities": {
    "streaming": true
  },
  "skills": [
    {
      "id": "project_status",
      "name": "Project Status",
      "description": "Answer questions about project and cycle status"
    }
  ],
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"]
}
```

The runtime-API collects agent cards at startup (or on demand) to know which agents support messaging and what skills they advertise.

### 7. Console Chat UI

The shipped v1 console UI is a Joi chat panel. The backend is fully agent-generic (any messaging-enabled agent is reachable), but the console initially presents Joi as the primary chat surface.

- Chat panel accessible from the console navigation
- Agent selector (messaging-enabled agents from discovery endpoint; Joi is the default)
- Message input with send button
- Streaming response display (SSE consumption via `EventSource`)
- Session-scoped conversation history (loaded from Redis via API)
- Agent online/offline indicator (based on A2A endpoint health)

The console connects to `GET /api/chat/{agent_id}/stream?session_id=...` for SSE and `POST /api/chat/{agent_id}` to send messages.

### 8. Context Grounding

Chat responses are grounded in injected status summaries, not raw evidence traversal.

Context sources for v1:
- **Project state**: active projects, recent cycles (from existing API DTOs)
- **Cycle/run state**: current status, workload progress, gate decisions (from existing registry)
- **Agent status**: which agents are online, what roles are active (from health endpoints)

This context is assembled by the runtime-API proxy before forwarding the chat message, injected as a `DataPart` in the A2A message. The agent's system prompt instructs it to answer from this context and to respond conservatively ("I don't have that detail right now") when coverage is incomplete. No deep artifact queries, no evidence traversal.

No new summary generation pipeline is required. The existing `CycleToResponseDTO` and `RunToResponseDTO` provide sufficient structured state.

### 9. Chat Persistence

Chat transcripts are persisted in Postgres for durability and queryability. Redis is the hot cache for active session state.

The legacy `squadcomms_messages` table (pre-hex era, empty) is dropped and replaced:

```sql
DROP TABLE IF EXISTS squadcomms_messages;

CREATE TABLE chat_sessions (
    session_id      TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE TABLE chat_messages (
    message_id      TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES chat_sessions(session_id),
    role            TEXT NOT NULL,  -- 'user' or 'agent'
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id, created_at);
CREATE INDEX idx_chat_sessions_agent ON chat_sessions(agent_id, started_at);
```

Redis holds recent messages for low-latency reads during conversation. On session resume after Redis TTL expiry, history is reloaded from Postgres. The console can display past conversations via `GET /api/chat/{agent_id}/sessions` and `GET /api/chat/sessions/{session_id}/messages`.

### 10. Semantic Memory

Chat-enabled agents access `ports.memory` (`MemoryPort` / LanceDB) for cross-session continuity. v1 uses **explicit memory writes only**: the user says "remember that the auth migration is blocked on legal review", the agent writes an embedding via `ports.memory.store()` and confirms the write. On new session start, the agent queries `ports.memory.search()` with the user's first message and injects relevant prior context alongside grounding state.

Automatic LLM-driven extraction is not in v1.

### 11. LLM Chat Streaming

The existing `LLMPort` has a `chat()` method (SIP-0073) but no streaming variant. This SIP adds:

```python
class LLMPort(ABC):
    # Existing
    async def chat(self, messages: list[ChatMessage], ...) -> str: ...

    # New — streaming variant
    async def chat_stream(
        self, messages: list[ChatMessage], ...
    ) -> AsyncIterator[str]: ...
```

The Ollama adapter implements `chat_stream()` using `httpx` streaming response against the Ollama `/api/chat` endpoint with `stream=true`.

### 12. Configuration Model

```yaml
# In agent profile / instances.yaml
instances:
  - id: joi
    display_name: Joi
    role: comms
    model: llama3.1:8b
    enabled: true
    description: "Communications - Conversational interface"
    a2a_messaging_enabled: true
    a2a_port: 8080
```

```yaml
# In SQUADOPS config (environment)
SQUADOPS__AGENTS__COMMS__A2A_MESSAGING_ENABLED: "true"
SQUADOPS__AGENTS__COMMS__A2A_PORT: "8080"
```

### 13. Observability

- **LangFuse**: Chat LLM generations recorded via `LLMObservabilityPort`
- **Metrics**: Message count, response latency, session duration via `MetricsPort`
- **Structured logging**: Chat session lifecycle (start, message, end) logged with session ID and agent ID

Chat does **not** emit through `CycleEventBus` — chat sessions have no cycle context.

---

## Key Design Decisions

### D1: A2A Protocol with Port Isolation
Adopt Google's A2A protocol as the initial messaging foundation rather than a custom layer. A2A provides agent cards (discovery), message/task separation, SSE streaming, and a well-defined client/server contract. All SDK usage is wrapped behind `MessagingPort` / adapter boundaries — if A2A changes or is replaced, only the adapter changes. Chat uses A2A `Message` objects (not `Task`), keeping conversations outside the cycle pipeline.

### D2: Dual Surface Architecture
Agent containers run two independent interaction surfaces sharing the same `PortsBundle`. RabbitMQ handles async task dispatch; A2A handles synchronous/streaming conversations. SSE (Server-Sent Events) is used for console streaming — simpler than WebSocket (no upgrade handshake, works through proxies, FastAPI native) and sufficient for one-directional server-to-client streaming.

### D3: Runtime-API as Proxy, Not Processor
The runtime-API relays chat messages to agent A2A endpoints. It does not call LLM directly. This preserves the principle that agent identity and conversation behavior live in the agent container with its full `PortsBundle`, not in infrastructure.

### D4: Context Grounding from Status Summaries
Grounding uses existing `CycleToResponseDTO` and `RunToResponseDTO` — no new summary pipeline. The agent answers from injected state and responds conservatively when data is incomplete.

### D5: Dual-Layer Persistence (Redis + Postgres)
Redis alone loses history on TTL expiry. Postgres alone adds latency during active conversation. Redis is the hot cache; Postgres is the durable record.

### D6: Discord Deferred
Discord introduces external API credentials, webhook management, rate limiting, and channel routing — all orthogonal to the core chat capability. A subsequent SIP keeps this SIP focused and shippable.

---

## File-Level Design

### New Files

| File | Purpose |
|------|---------|
| `src/squadops/ports/comms/messaging.py` | `MessagingPort` — abstract interface for A2A agent executor |
| `src/squadops/comms/models.py` | Chat domain models: `ChatSession`, `ChatMessage`, `AgentMessagingConfig` |
| `adapters/comms/a2a_server.py` | A2A server adapter — wraps `A2AStarletteApplication`, wires `AgentExecutor` |
| `adapters/comms/a2a_client.py` | A2A client adapter — used by runtime-API to proxy messages to agents |
| `src/squadops/agents/executors/chat_executor.py` | `ChatAgentExecutor(AgentExecutor)` — role-generic, used by any messaging-enabled agent |
| `src/squadops/api/routes/chat/routes.py` | Chat API routes: `POST /chat/{agent_id}`, `GET /chat/{agent_id}/stream`, session/history endpoints |
| `src/squadops/api/routes/chat/dtos.py` | Chat DTOs: `ChatMessageRequest`, `ChatStreamEvent`, `ChatSessionDTO` |
| `adapters/persistence/chat_repository.py` | Postgres chat persistence — `chat_sessions` and `chat_messages` tables |
| `infra/migrations/006_chat_tables.sql` | DDL for `chat_sessions`, `chat_messages` tables and indexes |
| `src/squadops/prompts/fragments/roles/comms/identity.md` | Comms role identity prompt fragment |
| `src/squadops/prompts/request_templates/request.chat_response.md` | Chat response request template |

### Modified Files

| File | Change |
|------|--------|
| `src/squadops/agents/base.py` | Add `messaging: MessagingPort | None = None` to `PortsBundle` |
| `src/squadops/agents/entrypoint.py` | Conditionally start A2A server alongside RabbitMQ consumer |
| `src/squadops/ports/llm/provider.py` | Add `chat_stream()` async iterator method to `LLMPort` |
| `adapters/llm/ollama.py` | Implement `chat_stream()` using httpx streaming |
| `agents/instances/instances.yaml` | Update `comms-agent` entry: rename to `joi`, add A2A config fields |
| `docker-compose.yml` | Uncomment and update comms-agent container, expose A2A port |
| `src/squadops/config/schema.py` | Add `A2AMessagingConfig` to `AgentConfig` |
| `src/squadops/prompts/fragments/manifest.yaml` | Add comms role identity fragment entry |
| `src/squadops/api/main.py` | Mount chat routes |

### Files NOT Modified

| File | Reason |
|------|--------|
| `adapters/comms/rabbitmq.py` | Task dispatch unchanged — chat uses a separate transport |
| `src/squadops/cycles/` | No cycle model changes — chat is outside the cycle pipeline |
| `src/squadops/capabilities/handlers/` | No handler changes — no task handler references `ports.messaging` in v1 |

---

## Implementation Phases

### Phase 1: A2A Foundation
- Add `a2a-sdk[http-server]` to requirements
- Implement `MessagingPort` interface
- Implement `a2a_server.py` adapter wrapping `A2AStarletteApplication`
- Implement `a2a_client.py` adapter wrapping A2A SDK `ClientFactory`
- Add `AgentCard` construction from agent profile config
- Add `chat_stream()` to `LLMPort` and Ollama adapter
- Tests: port contract, adapter construction, agent card serialization, streaming mock

### Phase 2: Chat Executor and Agent Wiring
- Add comms role identity prompt fragment (`roles/comms/identity.md`)
- Add chat response request template (includes memory recognition instructions)
- Implement `ChatAgentExecutor` — role-generic, resolves identity from `role_id`
- Wire explicit memory writes via `ports.memory.store()` and retrieval via `ports.memory.search()`
- Wire executor into agent entrypoint (conditional A2A server startup)
- Update `instances.yaml` and `docker-compose.yml` for comms-agent
- Tests: executor unit tests with mock LLM across multiple roles, conversation history, memory write/retrieve, context injection

### Phase 3: Runtime-API Chat Proxy and Persistence
- Add chat API routes, DTOs, A2A client proxy logic
- Add agent discovery endpoint with messaging capability filter
- Add `chat_sessions` and `chat_messages` DDL migration
- Implement `chat_repository.py` for Postgres persistence
- Add Redis session cache with Postgres fallback on TTL expiry
- Tests: route tests, proxy integration, session lifecycle, persistence round-trip

### Phase 4: Console Chat UI
- Svelte chat panel component in `continuum-plugins`
- Agent selector (Joi default, other messaging-enabled agents available)
- Message input, streaming response display (SSE via `EventSource`)
- Session management (create/resume/clear), agent online/offline indicator
- Tests: component tests, SSE consumption

### Phase 5: Observability and Polish
- LangFuse generation recording for chat LLM calls
- Structured logging for chat session lifecycle
- Metrics collection (message count, latency, session duration)
- Version bump, SIP promotion
- Tests: observability assertions

---

## Acceptance Criteria

1. Agent container with `a2a_messaging_enabled: true` starts with both RabbitMQ consumer and A2A HTTP/SSE server running concurrently.
2. `GET /.well-known/agent-card.json` on a messaging-enabled container returns a valid A2A `AgentCard`.
3. Sending an A2A `Message` to an agent endpoint returns a streaming text response grounded in project/cycle status.
4. Console chat panel renders streamed responses token-by-token.
5. Runtime-API proxies chat messages to the targeted agent's A2A endpoint and relays SSE back.
6. Conversation history persists to Postgres and caches in Redis; history survives Redis TTL expiry.
7. Any agent can enable messaging by setting `a2a_messaging_enabled: true` — no code changes required.
8. Chat LLM generations appear in LangFuse with chat-specific metadata.
9. `chat_stream()` on `LLMPort` produces an async iterator of text chunks.
10. Agent discovery endpoint returns only agents with messaging enabled.
11. Explicit memory writes from chat are stored via `MemoryPort` and retrievable in subsequent sessions.

---

## Risks

### A2A SDK Maturity
The `a2a-sdk` is at v0.3.x. API surface may change. **Mitigation**: All SDK usage is behind port/adapter boundaries — changes are isolated to the adapter layer.

### Agent Container Complexity
Running two services (RabbitMQ consumer + HTTP server) increases container complexity. **Mitigation**: A2A server is opt-in per agent profile. The Starlette app is lightweight.

### LLM Streaming Quality
Streaming from small local models may produce choppy output. **Mitigation**: Token budget controls from SIP-0073 apply. Model selection is independently tunable.

---

## Broadcast Evolution Path

This SIP delivers point-to-point messaging. The intended evolution is toward squad-wide broadcast channels — shared conversation surfaces where multiple agents and humans subscribe and contribute. The design protects this path: `MessagingPort` is agent-generic (not role-specific), `context_id` can scope multi-participant conversations, executors are stateless per-request (no embedded session state), and agent cards declare messaging capability for future channel routing. RabbitMQ topic exchanges (already in infrastructure) are the natural broadcast transport. A dedicated `CommsEventBus` may be introduced in a broadcast SIP for channel-level event propagation.

---

## Future Extensions (Subsequent SIPs)
- Discord and Slack channel adapters
- Squad broadcast channels (RabbitMQ topic exchanges + multi-agent subscription)
- Workflow delegation from chat ("start a planning cycle for project X")
- Agent-to-agent messaging without human intermediary
- Automatic memory extraction from conversations
- Push notifications for async updates
