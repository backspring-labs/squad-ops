# IDEA — WebSocket Realtime Channel Framework for SquadOps (Operator, Debrief, Presence, Live Control)

## Status
Proposed

## Summary
Define a **shared realtime channel framework** for SquadOps using a WebSocket-based protocol (or equivalent bidirectional realtime transport), so multiple interactive experiences can use a common foundation instead of each inventing its own transport pattern.

This IDEA expands beyond live chat to support other realtime, interactive channels discussed for SquadOps, including:

- **Operator console live updates** (cycle/pulse/task monitoring)
- **Comms debrief channel** (interactive post-run review / mission debrief)
- **Agent presence & control interactions** (cancel, pause, resume, acknowledge, intervene)
- **Live tool/progress streams** (build/test/log/tail-like updates)
- **Human-in-the-loop decision prompts** (approvals, clarifications, escalation actions)

The key architectural concept is:

- **WebSocket / realtime channels for interactivity**
- **Durable events/comms for system record and orchestration**

This preserves platform reliability while unlocking responsive operator experiences.

---

## Problem / Motivation
SquadOps is evolving toward long-running, observable, interactive execution. Several user/operator-facing experiences need **realtime interactivity**, not just durable async processing:

- monitoring cycles as they execute
- interacting with a debrief stream after a run
- interrupting or steering an agent during a live session
- watching tool progress and logs in near real time
- approving/rejecting proposed workload changes quickly

If each capability builds its own custom protocol path, the system risks:
- fragmented message formats
- inconsistent auth/session handling
- duplicate reconnect logic
- poor correlation across streams
- hard-to-maintain UI adapters

A shared realtime channel framework can provide a common pattern for all interactive channels.

---

## Core Idea
Create a **Realtime Channel Layer** (gateway + protocol envelopes + channel semantics) that supports multiple interactive channel types over a persistent connection.

### Conceptual split
1. **Realtime Channel Layer (interactive transport)**
   - multiplexed channels / subscriptions
   - low-latency push + control messages
   - session presence and interactive commands

2. **Durable Comms/Event Layer (system record)**
   - cycle execution orchestration
   - task dispatch / retries / idempotency
   - auditable state transitions
   - replayable event history

3. **Bridge / Mirror**
   - selected realtime events mirrored durably
   - durable events projected into realtime feeds
   - correlation IDs across both layers

This makes websocket/realtime support a platform capability, not a one-off chat feature.

---

## Why a Shared Realtime Framework
### 1) Consistency across interactive features
Common:
- auth/session model
- message envelope
- reconnect/resume behavior
- channel subscription semantics
- command/ack/error handling

### 2) Better platform ergonomics
UI and agents can use one protocol for:
- status feeds
- debrief conversations
- live intervention
- streaming outputs

### 3) Cleaner extensibility
New channel types (voice, multimodal, remote presence, shared collaboration rooms) can reuse the same foundation.

---

## Candidate Realtime Channel Types
Below are the channel classes this framework should support (initially or over time).

## A) Operator Channel (Live Console)
**Purpose:** operator monitoring + control during cycle execution

### Typical content
- cycle state changes
- pulse check progress
- workload/task status summaries
- warnings/errors
- telemetry summaries / health indicators
- action prompts (approve / cancel / retry / inspect)

### Interactive actions
- pause / resume cycle
- cancel task / workload
- request detail for a task
- trigger manual pulse check
- acknowledge alert

### Why realtime matters
Polling makes this feel laggy and reduces operator trust in the console as a live control surface.

---

## B) Debrief Channel (Comms Debrief / Mission Review)
**Purpose:** interactive debrief after or during a cycle, with structured context and live follow-up

### Typical content
- run summary stream
- root-cause analysis discussion
- artifact review pointers
- “what happened / why” Q&A
- proposed corrective actions
- post-run decisions and next steps

### Interactive actions
- ask follow-up questions
- request drill-down on a pulse/task/tool call
- ask for replay summary
- approve remediation workload proposal
- convert debrief findings into backlog items / IDEA / SIP drafts

### Why realtime matters
Debriefs are conversational and iterative; responsiveness improves reasoning flow and operator engagement.

---

## C) Live Chat / Agent Presence Channel
**Purpose:** direct human ↔ agent conversational interaction (already discussed)

### Typical content
- token streaming
- tool progress
- clarifying questions
- structured handoff proposals

### Interactive actions
- interrupt/cancel
- respond/follow up
- escalate to cycle execution

---

## D) Live Execution Feed Channel (Logs / Progress / Tool Streams)
**Purpose:** realtime visibility into long-running steps without opening multiple subsystems

### Typical content
- build/test progress
- streaming structured logs
- command status updates
- artifact generation milestones
- tool subprocess summaries

### Interactive actions
- subscribe/unsubscribe to a task stream
- filter level/category
- request tail window / checkpoint summary
- collapse noisy stream to summary mode

### Why realtime matters
This gives the “live operations room” experience without requiring direct shell access.

---

## E) Human-in-the-Loop Decision Channel
**Purpose:** deliver time-sensitive questions/prompts requiring operator decision

### Typical content
- approval requests
- ambiguity prompts
- policy boundary confirmations
- exception handling choices

### Interactive actions
- approve/reject
- choose option
- add instruction
- defer / snooze / route to another operator

### Why realtime matters
Fast decisions keep long runs moving and reduce idle time or drift.

---

## F) Multi-Agent Debrief / Collaboration Room (Future)
**Purpose:** shared interactive channel where multiple agents and the operator can participate in a coordinated debrief or planning discussion

### Typical content
- role-tagged agent responses (Lead, QA, Dev, Data, Joi, etc.)
- structured turns
- shared artifacts/references
- summary snapshots

### Interactive actions
- @mention agent
- grant speaking turn / focus
- freeze topic / summarize
- spawn execution proposal from discussion

### Note
This can be a later-stage feature, but a shared realtime framework should avoid blocking it.

---

## Architectural Components (Conceptual)
## 1) Realtime Gateway
Entry point for websocket/realtime sessions.

### Responsibilities
- connection lifecycle
- authentication/authorization
- protocol negotiation (version/capabilities)
- channel subscription management
- rate limits / quotas
- keepalive / heartbeat
- connection metadata (operator, agent, console instance)

---

## 2) Channel Router / Multiplexer
Routes messages to channel handlers and supports multiple active channel subscriptions per connection.

### Example behavior
A single operator session could subscribe simultaneously to:
- `operator.cycle.<cycle_id>`
- `debrief.session.<session_id>`
- `alerts.personal.<operator_id>`

This avoids opening separate sockets for every view/panel.

---

## 3) Channel Handlers
Per-channel logic modules that:
- project durable events into realtime messages
- accept interactive commands
- enforce permissions
- publish mirror/control events when needed

This aligns well with your plugin mindset and Continuum/Switchboard direction.

---

## 4) Realtime ↔ Durable Bridge
Bidirectional bridge between realtime channels and SquadComms/cycle events.

### Directions
- **Durable → Realtime:** project state changes/events into live channel updates
- **Realtime → Durable:** mirror key commands/actions/events as system record

### Examples
- operator clicks “pause cycle” → realtime command → durable `cycle.pause.requested`
- task failure event emitted durably → projected into operator and debrief channels live

---

## 5) Presence Registry (Optional / Later)
Tracks live presence for operators and possibly agent-facing sessions.

### Use cases
- show active operator viewing a cycle
- indicate agent session currently connected
- support debrief participant list
- route prompts to active consoles first

Presence should be ephemeral and not confused with durable execution state.

---

## Protocol Design Principles
### 1) Channel-first semantics
Protocol should model named channels with:
- subscribe
- unsubscribe
- publish/command (where allowed)
- ack/error
- heartbeat
- resume

### 2) Shared envelope, channel-specific payloads
Use one common message envelope, with payload schemas per channel type.

### 3) Correlation IDs everywhere
Include identifiers like:
- `session_id`
- `connection_id`
- `channel_id`
- `cycle_id` / `workload_id` / `task_id`
- `trace_id`
- `message_id`
- `causation_id` / `correlation_id` (if adopted)

### 4) Interactivity without losing auditability
Realtime commands can be transient in transport, but meaningful actions should emit durable events.

### 5) Degrade gracefully
If realtime disconnects:
- execution continues
- operator can reconnect
- channel resumes from checkpoint/sequence where practical

---

## Suggested Common Message Envelope (Conceptual)
The exact schema can be designed later, but a shared envelope should support:

- `protocol_version`
- `connection_id`
- `session_id`
- `channel`
- `message_type` (event, command, ack, error, heartbeat, snapshot, delta)
- `message_id`
- `sequence` (per channel or per stream)
- `timestamp`
- `trace_id`
- `payload`

Optional:
- `resume_token`
- `capabilities`
- `compression`
- `sampling_hint`

---

## Suggested Core Protocol Operations (Conceptual)
### Connection/session
- `hello`
- `hello.ack`
- `heartbeat`
- `resume`
- `disconnect.notice`

### Channel management
- `channel.subscribe`
- `channel.subscribed`
- `channel.unsubscribe`
- `channel.snapshot` (initial state on join)
- `channel.event` (incremental updates)

### Interactivity/control
- `channel.command`
- `channel.command.ack`
- `channel.command.rejected`
- `channel.prompt` (request operator input)
- `channel.prompt.response`

### Errors
- `error`
- `warning`
- `rate_limit.notice`

---

## Projection Pattern: Durable Events to Realtime Channels
A major value of this framework is **projection**.

### Example projections
- `cycle.state.changed` → operator channel state badge update
- `pulse.check.completed` → operator timeline + debrief summary feed
- `task.failed` → operator alert + debrief “investigate failure?” prompt
- `rca.generated` → debrief channel artifact summary card

This means the realtime layer becomes the **live surface** for the durable system, not a separate truth source.

---

## Command Pattern: Realtime to Durable System
Commands issued from realtime channels should typically become durable control events.

### Example commands
- pause cycle
- retry task
- approve remediation
- escalate chat to workload
- mark debrief action item accepted

### Why this matters
It preserves:
- audit trail
- replay/debug
- policy enforcement
- deterministic system behavior (as much as possible)

---

## Security / Governance Considerations
### Authentication
- authenticated websocket session (operator / service identity)
- short-lived tokens preferred
- explicit session scope

### Authorization
Channel-level permissions, e.g.:
- view-only operator feed
- debrief participation
- control commands allowed/not allowed
- sensitive artifact access restrictions

### Rate limiting / abuse controls
Especially important if agent presence expands to external surfaces in the future.

### Privacy / retention
Define what is:
- stream-only transient
- mirrored durably
- summarized/persisted
- redacted

---

## Risks / Tradeoffs
### 1) Added platform surface area
A robust realtime layer is non-trivial.

**Mitigation:** start with a narrow MVP (Operator + Debrief + Live Chat), reuse shared envelope/handlers.

### 2) Message explosion / noise
Too many low-level updates can overwhelm UI and infrastructure.

**Mitigation:** projection/sampling/aggregation policies; snapshots + deltas.

### 3) Ordering and resume complexity
Realtime streams and durable events may arrive at different times.

**Mitigation:** sequence numbers, snapshots, checkpointed resume, explicit eventual consistency behavior.

### 4) Scope creep into “another comms system”
Realtime layer could accidentally duplicate SquadComms.

**Mitigation:** treat realtime as interaction/projection layer; durable layer remains orchestration/system record.

---

## Implementation Sketch (High Level)
### Phase 1 — Realtime Gateway + Operator Channel MVP
- Stand up websocket gateway
- Define common envelope v1
- Implement operator cycle channel projection (read-mostly)
- Add heartbeat and reconnect basics

### Phase 2 — Debrief Channel + Live Commands
- Add interactive debrief channel
- Add command path for drill-down requests / action proposals
- Mirror significant debrief actions to durable events

### Phase 3 — Unified Realtime Channel Framework
- Multiplex subscriptions
- Shared channel handler plugin model
- Permissions framework per channel/action
- Snapshot + delta patterns

### Phase 4 — Advanced Channels
- HITL prompts
- multi-agent debrief room
- richer presence
- voice/multimodal adapters (if desired later)

---

## Relationship to Existing Ideas
This IDEA complements (not replaces) the separate IDEA for **Realtime Chat Protocol (Fast Lane + Comms Mirror)**.

That IDEA focuses on the **chat interaction path**.

This IDEA generalizes the concept into a **platform-wide realtime channel framework** that can support:
- chat
- operator console
- debrief
- live progress feeds
- interactive control prompts

The chat protocol can be implemented as one channel type within this broader framework.

---

## Recommendation
Adopt a **shared realtime channel framework** as a SquadOps design direction, using WebSocket (or equivalent) for interactivity while keeping durable comms/events as the authoritative orchestration and audit layer.

This gives SquadOps a coherent foundation for:
- live operator UX
- debrief interactivity
- agent presence
- real-time control
- future collaborative channel experiences
