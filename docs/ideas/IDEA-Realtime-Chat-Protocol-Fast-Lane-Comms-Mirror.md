# IDEA — Realtime Chat Protocol for SquadOps (Fast Lane + Comms Mirror)

## Status
Proposed

## Summary
Introduce a **realtime chat interaction protocol** (e.g., WebSocket-based streaming) for low-latency live agent conversations, while **preserving SquadComms events as the system record** through mirrored event emission.

This creates a dual-lane model:

- **Conversation Mode (fast lane):** direct realtime stream to agent/LLM runtime for interactive chat UX
- **Control/Record Mode (control lane):** mirrored SquadComms events for traceability, governance, observability, and handoff into structured cycle execution

This avoids forcing token streaming through a durability-first queue, while still keeping the platform architecture coherent.

---

## Problem / Motivation
SquadOps durable comms and eventing are a strong fit for:

- task dispatch
- cycle / pulse / task orchestration
- retries / idempotency
- auditability
- replay / recovery

But they are not the ideal transport for **live conversational interaction**, which needs:

- low latency
- token streaming
- interrupt/cancel
- conversational turn continuity
- “agent presence” feel in the console

If live chat is forced through a durability-first message path, UX may feel delayed or unnatural. If live chat bypasses comms entirely, the platform loses observability, governance, and handoff consistency.

This IDEA proposes a split that preserves both goals.

---

## Core Idea
Use a **direct realtime channel** for the live chat path, but **emit mirrored comms/events as side effects**.

### Architectural Concept
1. **Fast lane (realtime chat protocol)**
   - User ↔ Console/UI ↔ Chat Session Gateway ↔ Agent/LLM runtime
   - Optimized for streaming and responsiveness

2. **Control lane (SquadComms mirror events)**
   - Emit key chat/session/tool events into SquadComms (or cycle event bus)
   - Provides audit trail, telemetry correlation, and structured escalation to workloads/cycles

This creates a “best of both worlds” model:
- chat feels live
- platform remains observable and governable

---

## Design Principles
### 1) Do not bypass the platform
Live chat may use a different transport, but must still produce platform-visible events.

### 2) Separate interaction mode from execution mode
- **Conversation Mode** ≠ **Execution Mode**
- Both can coexist and hand off cleanly

### 3) Preserve correlation across lanes
Use a shared identity envelope (e.g., `session_id`, `trace_id`, `agent_id`, `user_id`) across:
- stream messages
- comms events
- telemetry spans
- tool execution events

### 4) Escalate from conversation to structured work
A live chat session should be able to promote work into:
- workload proposal
- cycle creation
- pulse/task planning
- approval flow (optional)

---

## Proposed Modes
## A) Conversation Mode (Realtime)
**Purpose:** direct human ↔ agent interaction

### Characteristics
- low-latency bidirectional messaging
- token streaming responses
- tool progress/status streaming
- cancel/interrupt support
- session continuity

### Candidate transports
- WebSocket (most likely)
- SSE + POST (fallback pattern)
- provider-specific realtime APIs (wrapped by gateway)

---

## B) Execution Mode (Durable / Orchestrated)
**Purpose:** formal work execution under SquadOps controls

### Characteristics
- durable events/messages
- retries and backoff
- idempotent handlers
- scheduling and orchestration
- checkpoints / pulse checks
- auditable state transitions

---

## C) Bridge Mode (Mirror + Handoff)
**Purpose:** connect conversation to execution without losing system integrity

### Responsibilities
- emit mirrored session/turn/tool events
- attach correlation IDs
- persist transcript summary / metadata (where appropriate)
- support “chat → workload/cycle” escalation

---

## Suggested Event Mirror (examples)
These are examples of **control-lane events** that mirror fast-lane behavior.

### Session lifecycle
- `chat.session.started`
- `chat.session.resumed`
- `chat.session.ended`

### Turn lifecycle
- `chat.turn.received`
- `chat.turn.routed`
- `chat.turn.cancelled`

### Agent response lifecycle
- `agent.response.started`
- `agent.response.delta` *(optional mirror; likely sampled/aggregated rather than every token)*
- `agent.response.completed`
- `agent.response.failed`

### Tool execution (during chat)
- `tool.call.started`
- `tool.call.progress`
- `tool.call.completed`
- `tool.call.failed`

### Escalation / handoff
- `chat.session.propose_workload`
- `chat.session.escalated_to_cycle`
- `chat.session.escalation_rejected`

> Note: token-by-token events probably should **not** all be mirrored durably. Mirror summaries/checkpoints, not every stream fragment, unless explicitly needed for debugging.

---

## Suggested Realtime Message Envelope (conceptual)
The fast-lane protocol should use a lightweight message envelope with consistent identifiers.

### Common fields (conceptual)
- `session_id`
- `trace_id`
- `message_id`
- `agent_id`
- `role` (user/agent/system/tool)
- `type` (turn, delta, tool_status, error, control)
- `timestamp`
- `payload`

### Control messages (fast lane)
- cancel current response
- interrupt/replace active generation
- keepalive/ping
- reconnect/resume token
- client ack (optional)

This keeps the stream protocol purpose-built for realtime interaction without overloading SquadComms semantics.

---

## Handoff Flow: Chat → Cycle Execution (Key UX Win)
This is likely the most valuable pattern.

### Example flow
1. User chats with Joi in realtime
2. Joi clarifies intent and scope
3. Joi detects actionable work request
4. Joi emits `chat.session.propose_workload`
5. Operator approves (or policy auto-approves)
6. SquadOps creates workload/cycle
7. Execution transitions to durable orchestration
8. Live chat remains available for updates / clarifications

### Why this matters
- keeps conversational UX natural
- preserves operational structure for real work
- supports governance and approval boundaries
- aligns with the “conversation becomes execution” experience

---

## Benefits
### UX / Operator Experience
- responsive “agent presence”
- live debrief and troubleshooting feel
- better console interactivity than polling

### Architecture / Platform Integrity
- comms/event trail remains intact
- easier debugging and replay correlation
- clear separation of concerns (chat vs orchestration)

### Future Extensibility
- multiple realtime adapters (OpenAI, Anthropic, local models, etc.)
- role-specific live chat surfaces (e.g., Joi debrief, Lead planning)
- voice/chat/multimodal session pathways using same bridge pattern

---

## Risks / Tradeoffs
### 1) Dual-lane complexity
Two paths (fast + control) add implementation complexity.

**Mitigation:** define a clear contract for what must be mirrored and what remains stream-only.

### 2) Connection drops / reconnect behavior
Realtime channels can disconnect.

**Mitigation:** session resume semantics, reconnect tokens, and mirrored state checkpoints.

### 3) Event duplication / noise
Mirroring too much (especially token deltas) can flood the event system.

**Mitigation:** aggregate/summarize stream events before durable emission.

### 4) Drift between lanes
If mirror events fail, chat may continue without record fidelity.

**Mitigation:** treat mirror emission as first-class, with retry/buffer strategy and telemetry alarms.

---

## Implementation Sketch (High Level)
### Phase 1 — Realtime Chat Session Gateway
- Introduce `Chat Session Gateway` service/module
- Support basic realtime session + streaming response path
- Attach shared `session_id` / `trace_id`

### Phase 2 — Comms Mirror Events
- Emit minimal lifecycle events into SquadComms / cycle event bus
- Add correlation to telemetry spans
- Define mirror event schema and sampling policy

### Phase 3 — Handoff to Execution
- Implement `propose_workload` → approval → cycle creation flow
- Preserve transcript summary/context package for handoff

### Phase 4 — Hardening
- reconnect/resume semantics
- backpressure handling
- authN/authZ for live sessions
- operator controls (cancel, pause, escalate, transfer)

---

## Open Questions (for later design)
- Should mirror events go into SquadComms proper or a dedicated cycle/event stream that is adjacent to SquadComms?
- What level of transcript persistence is required for compliance/debug vs privacy/minimal retention?
- How should tool outputs be streamed vs persisted (full payload vs summarized metadata)?
- What is the minimum viable resume behavior for dropped connections?
- Should live chat sessions support multiple participating agents, or remain single-agent first?

---

## Recommendation
Adopt this as a **design direction / IDEA** for SquadOps:
- **Realtime protocol for live chat**
- **Mirrored comms events for system record**
- **Structured handoff from conversation into durable cycle execution**

This preserves the strengths of SquadOps orchestration while unlocking a much better live interaction model.
