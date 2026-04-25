---
title: Agent Embodiment Substrate
status: accepted
author: Jason Ladd
created_at: '2026-04-25T00:00:00Z'
sip_number: 90
updated_at: '2026-04-25T17:57:13.839284Z'
---
# SIP-0090: Agent Embodiment Substrate

**Status:** Accepted
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 2 (incorporated review feedback on 2026-04-25)
**Targets:** v1.2
**Depends on:** `sips/accepted/SIP-0089-Agent-Runtime-State.md` (v1.1) — must land first
**Parent vision:** `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (umbrella index)
**Sibling:** `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3)
**Future follow-on:** `SIP-Minecraft-Embodiment-Adapter.md` (not in this package)

---

## 1. Summary

This SIP introduces an **embodiment abstraction** that lets a SquadOps agent act through a runtime surface in a world or system — without making any specific world part of the core domain.

The first proof point is intentionally **not** Minecraft. It is a lighter surface (Discord presence) chosen because it is easier to test than world-simulation surfaces, has well-established adapter patterns, and exercises the embodiment model without dragging in physics, blocks, mob AI, or pathfinding.

The agent identity remains durable. The embodiment is the runtime surface through which it acts. They are separable: the same agent can detach from one embodiment and reattach to another.

Minecraft is a **named future follow-on** (`SIP-Minecraft-Embodiment-Adapter.md`), addressed after this substrate proves stable.

---

## 2. Problem Statement

Once an agent can be persistent (per `SIP-0089-Agent-Runtime-State.md`), the next architectural question is:

> How does an agent act in environments that are not its own process?

Without a substrate:

- Discord, browser, Minecraft, and any future surface get bolted directly onto agents
- Agent state and embodiment state get conflated in prompt context
- Embodiment health (connection, disconnection, desync) becomes invisible
- Location, when it matters, has nowhere clean to live
- Each new world brings ad-hoc state machines

The challenge:

> How can SquadOps represent embodied presence in any external surface, with observable attachment state and health, without contaminating the core domain with surface-specific knowledge?

---

## 3. Design Intent

1. Separate **agent identity** from **embodiment** — the agent is durable, the embodiment is a runtime surface.
2. Make embodiment **observable**: attachment state, health, capability set, location reference.
3. Keep **location generic** in the core; world-specific detail lives in adapters.
4. Prove the abstraction with a **lightweight first surface** (Discord), not Minecraft.
5. Establish the adapter pattern so future surfaces (Minecraft, browser, Decentraland, etc.) plug in cleanly.
6. Introduce **resource budgets** as a first-cut guard against irresponsible scheduling, with explicit decrement and exhaustion rules.
7. **Preserve the package invariant:** embodiment never decides intent.

---

## 4. Non-Goals

This SIP does **not** propose:

- Minecraft, Mineflayer, or any virtual-world game logic — see `SIP-Minecraft-Embodiment-Adapter.md` (future)
- Spatial reasoning, pathfinding, or world simulation
- Replacing existing agent communication (RabbitMQ, message envelopes) with embodiment events
- Temporal or durable workflow integration — see `SIP-0091-Duty-Durability-via-Temporal.md`
- Ambient autonomy beyond what the runtime-state SIP already permits
- A full EmbodiedAction ledger as a first-class table — explicitly deferred (see §5.6)
- Multiple simultaneously-attached embodiments per agent — explicitly deferred (see §5.5)

---

## 5. Proposed Embodiment Model

### 5.1 The agent / embodiment split

```
Agent (durable)            Embodiment (runtime surface)
  identity                   discord_session / browser_ctx / minecraft_avatar (future)
  mode/focus/activity        attachment_state / health / location / capabilities
```

An agent without an embodiment is still a fully valid agent — it just can't act in external surfaces. An embodiment without an agent is meaningless and should never exist.

### 5.2 Embodiment lifecycle

```
unattached → attaching → attached → desynced → reconnecting → attached
                                  ↘ detached
```

- **unattached** — embodiment record exists, no live connection
- **attaching** — adapter is connecting; transient
- **attached** — live, healthy, capable of action
- **desynced** — connection live but state divergence detected (e.g., Discord rate limit, browser context lost)
- **reconnecting** — adapter recovering
- **detached** — explicitly released or terminally failed

Each transition is evented from the canonical `embodiment.*` event set in the umbrella SIP.

### 5.3 Embodiment fields

```yaml
Embodiment:
  embodiment_id: string
  agent_id: string                    # owning agent
  embodiment_type: discord | browser | minecraft | cli | other
  platform: string                    # e.g., "discord:guild_id", "browser:chromium"
  attachment_state: unattached | attaching | attached | desynced | reconnecting | detached
  health: healthy | degraded | failed
  capability_set: [string]            # what this embodiment can do
  location_ref: string | null         # opaque to core; see 5.4
  last_health_check_at: timestamp
  credentials_ref: string             # secret:// reference; never the credential itself
```

### 5.4 Location (generic in core, opaque to core)

Core knows that location exists and matters. Adapter-specific shape lives in adapters.

```yaml
Location:
  location_type: string               # opaque; e.g., "discord_channel", "url", "minecraft_xyz"
  location_system: string             # e.g., "discord", "browser", "minecraft"
  location_ref: string                # opaque; the adapter understands its content
  updated_at: timestamp
```

**Location opacity rules** (binding):

- Core MAY compare whether `location_ref` changed (equality only).
- Core MAY route `location_ref` back to the owning adapter for interpretation.
- Core MAY NOT parse or interpret `location_ref` content.
- Core MAY NOT branch scheduling logic on the internal contents of `location_ref`.

This keeps Minecraft coordinates, Discord channel IDs, and browser URLs from leaking into core scheduling.

### 5.5 Single-active-embodiment rule (decided for v1.2)

**v1.2 supports at most one *active* (attached) embodiment per agent.** Multiple Embodiment records may be configured, but only one may be in `attached` or `desynced` or `reconnecting` state at a time.

Multi-embodiment presence is **explicitly deferred** to a future SIP. This keeps the v1.2 implementation tractable and avoids resolving complex cross-surface coordination prematurely.

### 5.6 EmbodiedAction (deferred, with light hooks)

A full EmbodiedAction event ledger is **not introduced in v1.2**. Adapter calls may be logged as lightweight events linked to the active RuntimeActivity, sufficient for observability but not a new first-class table.

If Minecraft or browser automation later requires stronger replayability or evidence chains, a follow-on SIP will promote embodied actions to first-class records. The v1.2 substrate accommodates this without requiring core changes.

### 5.7 Capability set

Embodiment capabilities are declared by the adapter at attach time. Examples:

- Discord embodiment: `send_message`, `read_channel`, `add_reaction`, `manage_threads`
- Browser embodiment: `navigate`, `click`, `type`, `screenshot`, `extract_text`

The runtime-state RuntimeActivity model can require an embodiment with a specific capability before scheduling. This is the seam where embodiment integrates with the v1.1 substrate.

---

## 6. Embodiment Authority Boundary

**Invariant:** Embodiment adapters do not decide agent intent, mode, or priority. They:

- expose capabilities,
- report surface events,
- execute already-authorized action requests,
- report health and location.

Core runtime policy decides whether an embodied action may proceed. This prevents Discord, Minecraft, or browser adapters from becoming mini-agent brains.

### 6.1 What adapters DO translate

Adapters translate **already-authorized, surface-specific action requests** into platform calls:

- "send a message to channel X" → Discord API call
- "click selector Y" → browser DOM operation
- "navigate to URL Z" → browser navigation
- "capture a screenshot" → browser screenshot
- "place a block at (x,y,z)" → Minecraft protocol call (future)

### 6.2 What adapters DO NOT do

Adapters do not decompose broad goals or decide whether an action should be taken. The following are **never** adapter-level responsibilities:

- "Handle a customer support conversation" — must be planned by SquadOps and decomposed into individual authorized actions
- "Build a Minecraft base" — same
- "Complete a browser research assignment" — same

If a goal needs decomposition, the decomposition happens in SquadOps (handlers, planners, RuntimeActivities). The adapter sees only the resulting concrete actions.

---

## 7. Resource Budgets (with explicit decrement and enforcement)

The goal is not to simulate a human body. The goal is to prevent irresponsible scheduling — especially for ambient agents that may otherwise burn tokens or take unbounded action.

### 7.1 Budget dimensions and decrement rules

| Budget | Decremented by |
|--------|----------------|
| **attention_budget** | Time the agent holds a primary FocusLease |
| **compute_budget** | LLM token / cost usage attributed to the agent |
| **action_budget** | Embodied actions executed |
| **concurrency_allowance** | Simultaneously-open RuntimeActivities or held leases |

Budgets attach to the **agent**, not the embodiment, so cross-embodiment usage sums correctly.

### 7.2 Exhaustion behavior (must not be silent)

Budget exhaustion must produce a `budget_exhausted` event (canonical reason code) and force one of:

- **reject_new_activity** — new RuntimeActivities denied
- **pause_current_activity** — current RuntimeActivity paused if `can_pause`
- **detach_embodiment** — release the active Embodiment
- **transition_to_ambient** — force mode back to `ambient`
- **require_operator_override** — block until `operator_override` reason code is supplied

Silent degradation is forbidden. Every exhaustion produces a visible policy event.

---

## 8. Adapter Pattern

Embodiments follow the existing SquadOps hexagonal pattern.

- **Port:** `EmbodimentPort` in `src/squadops/ports/`
- **Adapters:** `adapters/embodiment/discord/`, `adapters/embodiment/browser/`, etc.
- **Factory:** `EmbodimentFactory` selects adapter by `embodiment_type` and platform config

The adapter owns:

- Connection lifecycle (attach, reconnect, detach)
- Health checks
- Capability declaration
- Translating already-authorized action requests into platform calls (per §6.1)
- Updating `location_ref` when the adapter detects location change

The core owns:

- Embodiment record (attachment_state, health, capability_set, location_ref)
- Resource budget enforcement
- Event emission on state transitions
- Integration with RuntimeActivity and FocusLease from the v1.1 substrate
- Authorization decisions (what the adapter is permitted to execute)

---

## 9. Credentials

Embodiment credentials are **never** stored in Embodiment records.

- The Embodiment record carries `credentials_ref` — a `secret://` reference resolved by the existing `SecretManager`.
- Adapters receive resolved credentials at `attach` time only.
- Adapters must not log, persist, or echo credentials.

This avoids accidental token persistence in Postgres and reuses the existing secret-management seam.

---

## 10. First Proof Point: Discord Presence

Recommended first surface: **Discord**.

Why Discord:

- Stable, well-documented SDK
- No physics or world simulation
- Clean message-event model maps naturally to RuntimeActivity
- Real Backspring use case: agents that monitor channels, respond to mentions, post status

### 10.1 Minimum capability set

- Connect to a Discord guild
- Listen on a configured channel
- Send messages
- React to mentions
- Cleanly detach

### 10.2 Staged test strategy (realistic)

Discord integration is not as easy to CI as the original draft implied. Use a layered approach:

| Tier | What | When |
|------|------|------|
| Adapter unit tests | Mocked gateway/events; pure logic | Always run in CI |
| Local integration | Real Discord client against a private guild | Run on-demand by developers |
| CI integration (optional) | Real Discord against a CI-only guild | Only when bot credentials are configured in CI secrets |

### 10.3 Phase-1 acceptance for the proof point

- An ambient agent can attach a Discord embodiment, listen on a channel, respond to a mention, and detach cleanly on shutdown
- Embodiment state transitions are observable via the canonical `embodiment.*` events
- A FocusLease prevents two RuntimeActivities from claiming the embodiment simultaneously
- An ambient agent **cannot** send a Discord message without first acquiring a FocusLease and starting a RuntimeActivity (per the v1.1 ambient irreversibility rule)

---

## 11. Substrate Generality Proof: Browser (narrow)

A second adapter validates that the substrate is general. Recommended: a **narrow browser embodiment**.

**v1.2 browser scope is deterministic navigation and observation only:**

- Navigate to a configured URL
- Read text content
- Capture screenshot
- Cleanly detach

**Not in v1.2 browser scope:**

- Autonomous browsing
- Form filling against arbitrary sites
- Multi-tab orchestration
- Persistent session state

This proves the substrate without committing to a full browser-automation rabbit hole. Full browser autonomy can be a future SIP if needed.

---

## 12. Future Surfaces (Out of Scope for v1.2)

Documented for trajectory clarity, but **not** part of this SIP:

- **Minecraft via Mineflayer** — `SIP-Minecraft-Embodiment-Adapter.md`. Scope will include adapter, pathfinding, block placement, spatial action plans, world-state observation, acceptance checks for built structures, embodied safety constraints.
- **Decentraland / The Sandbox** — far future; depends on platform stability
- **Multi-tab / multi-session browser** — follow-on if v1.2 browser proof point reveals demand
- **Multi-active-embodiment per agent** — follow-on after v1.2 single-embodiment model is proven

---

## 13. Implementation Phases

### Phase 1 — Core embodiment model

- `EmbodimentPort` interface
- Embodiment record + Postgres table
- Lifecycle state machine
- Canonical event emission
- Resource budget primitives with decrement rules and exhaustion behaviors per §7
- SecretManager integration via `credentials_ref`

**Acceptance:** Embodiment records exist and transition states cleanly. No adapter required yet.

### Phase 2 — Discord adapter

- `adapters/embodiment/discord/` with full lifecycle support
- Connect, listen, send, react, detach
- Capability declaration
- Health checks via Discord gateway
- Staged test strategy per §10.2

**Acceptance:** an ambient agent can hold a Discord presence end-to-end with the §10.3 acceptance criteria.

### Phase 3 — RuntimeActivity integration

- RuntimeActivities can declare `requires_embodiment: <type>` and `required_capabilities: [...]`
- Scheduler refuses to start a RuntimeActivity without a matching attached embodiment
- Pause/resume semantics handle embodiment desync via `embodiment_desynced` event

**Acceptance:** a duty agent can hold a Discord embodiment, take a moderation RuntimeActivity, pause it on disconnect, and resume it on reconnect.

### Phase 4 — Narrow browser adapter (substrate generality proof)

- Headless browser embodiment with navigate/read/screenshot only (per §11)
- Validates the abstraction by exercising a second surface
- Demonstrates that adding a new surface requires zero core embodiment changes

**Acceptance:** the browser adapter ships without changing any core embodiment code.

---

## 14. Acceptance Criteria

The SIP is successful when:

1. **Identity / embodiment separation** is clean — agents survive embodiment loss; embodiments cannot exist without agents
2. **Single-active-embodiment rule** is enforced (one attached embodiment per agent in v1.2)
3. **Adapter authority boundary** holds — no adapter decides intent, mode, or priority
4. **Observable lifecycle** — every embodiment state transition is evented from the canonical set
5. **Generic location** — core never interprets `location_ref`; adapters do
6. **Capability-aware scheduling** — RuntimeActivities cannot start without a matching embodiment capability
7. **Budget enforcement** — exhaustion produces a `budget_exhausted` event and forces one of the §7.2 outcomes; never silent
8. **Credentials safety** — no embodiment record contains credentials; all access via `secret://` refs
9. **First proof point lives** — Discord adapter passes the §10.3 acceptance with the staged test strategy
10. **Substrate generality** — adding the narrow browser adapter requires zero core changes
11. **Ambient irreversibility upheld** — ambient agents cannot perform irreversible embodied actions without a FocusLease and RuntimeActivity
12. **No regressions** — `run_regression_tests.sh` continues to pass; v1.1 runtime-state primitives unaffected

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Surface-specific concerns leak into core | Location opacity rules in §5.4; review every PR for adapter-specific imports in core |
| Adapter authority creep (decomposing goals) | §6 invariant; reject any adapter PR that branches on goal text |
| Discord adapter complexity bleeds in | Keep adapter behind clean port; minimal capability set |
| Budgets become a new policy quagmire | Start with 4 dimensions in §7.1; resist additions until proven need |
| Embodiment desync silently degrades agents | Mandatory health checks; `embodiment_desynced` event triggers explicit RuntimeActivity pause |
| Multiple embodiments contend | Single-active rule in §5.5; deferred to future SIP |
| Browser adapter scope creep | §11 explicitly limits v1.2 browser to deterministic navigation |
| Credentials leak into DB or logs | §9 rule: credentials never persisted; adapter must not log |

---

## 16. Open Questions

1. How does embodiment attachment interact with the v1.1 FocusLease? Same lease type, or a distinct EmbodimentLease? **Recommend deferring to implementation; default to reusing primary FocusLease.**
2. Should resource budgets be configurable per agent role (`max`, `bob`, `eve`, etc.) or only global defaults?
3. Does the Discord adapter belong in the main `adapters/` tree, or as an optional install (extras dependency `squadops[discord]`)?
4. Should `embodiment.attached` events include the full capability set in the payload, or just a capability hash with capabilities queried separately?
5. For the browser adapter, do we use Playwright, Puppeteer, or an existing SquadOps browser harness if one exists?

---

## 17. References

- Depends on: `sips/accepted/SIP-0089-Agent-Runtime-State.md` (v1.1)
- Parent vision: `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (canonical reason codes, event names, terminology, package invariant)
- Future follow-on: `SIP-Minecraft-Embodiment-Adapter.md`
- Original full proposal: commit `76a1f90` on main
- Related: SIP-0061 (LangFuse Observability — telemetry pattern reused for embodiment events), SIP-0042 (memory adapter — pattern for optional integrations), `SecretManager` in `src/squadops/core/`
- Hexagonal pattern: existing `src/squadops/ports/` and `adapters/` structure
