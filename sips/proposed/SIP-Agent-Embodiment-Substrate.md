# SIP: Agent Embodiment Substrate

**Status:** Proposed (draft)
**Authors:** Jason Ladd
**Created:** 2026-04-25
**Revision:** 1
**Targets:** v1.2
**Depends on:** `SIP-Agent-Runtime-State.md` (v1.1) — must land first
**Parent vision:** `sips/proposed/SIP-Agent-Runtime-Modes.md` (umbrella index)
**Sibling:** `SIP-Duty-Durability-Temporal.md` (v1.3)

---

## 1. Summary

This SIP introduces an **embodiment abstraction** that lets a SquadOps agent act through a runtime surface in a world or system — without making any specific world part of the core domain.

The first proof point is intentionally **not** Minecraft. It is a lighter surface (Discord presence or browser session) chosen because it is easier to test in CI, has well-established adapter patterns, and exercises the embodiment model without dragging in physics, blocks, mob AI, or pathfinding.

The agent identity remains durable. The embodiment is the runtime surface through which it acts. They are separable: the same agent can detach from one embodiment and reattach to another.

Minecraft remains a future proof point, addressed in a follow-on SIP after this substrate proves stable.

---

## 2. Problem Statement

Once an agent can be persistent (per `SIP-Agent-Runtime-State.md`), the next architectural question is:

> How does an agent act in environments that are not its own process?

Without a substrate:

- Discord, browser, Minecraft, and any future surface get bolted directly onto agents
- Agent state and embodiment state get conflated in prompt context
- Embodiment health (connection, disconnection, desync) becomes invisible
- Location, when it matters, has nowhere clean to live
- Each new world brings ad-hoc state machines

The problem is not "how do we play Minecraft." It is:

> How can SquadOps represent embodied presence in any external surface, with observable attachment state and health, without contaminating the core domain with surface-specific knowledge?

---

## 3. Design Intent

1. Separate **agent identity** from **embodiment** — the agent is durable, the embodiment is a runtime surface.
2. Make embodiment **observable**: attachment state, health, capability set, location reference.
3. Keep **location generic** in the core; world-specific detail lives in adapters.
4. Prove the abstraction with a **lightweight first surface** (Discord or browser), not Minecraft.
5. Establish the adapter pattern so future surfaces (Minecraft, Decentraland, etc.) plug in cleanly.
6. Introduce **resource budgets** as a first-cut guard against irresponsible scheduling.

---

## 4. Non-Goals

This SIP does **not** propose:

- Minecraft, Mineflayer, or any virtual-world game logic — that's a follow-on SIP after this substrate stabilizes
- Spatial reasoning, pathfinding, or world simulation
- Replacing existing agent communication (RabbitMQ, message envelopes) with embodiment events
- Temporal or durable workflow integration — see `SIP-Duty-Durability-Temporal.md`
- Ambient autonomy beyond what the runtime-state SIP already permits

---

## 5. Proposed Embodiment Model

### 5.1 The agent / embodiment split

```
Agent (durable)            Embodiment (runtime surface)
  identity                   discord_session / browser_ctx / minecraft_avatar
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

Each transition is evented and auditable, mirroring the runtime-state SIP's approach to mode transitions.

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
  location_ref: string | null         # see Location below
  last_health_check_at: timestamp
```

### 5.4 Location (generic in core)

Core knows that location exists and matters. Adapter-specific shape lives in adapters.

```yaml
Location:
  location_type: string               # opaque to core; e.g., "discord_channel", "url", "minecraft_xyz"
  location_system: string             # e.g., "discord", "browser", "minecraft"
  location_ref: string                # opaque ref the adapter understands
  updated_at: timestamp
```

Core never inspects `location_ref`. Adapters interpret it.

### 5.5 Capability set

Embodiment capabilities are declared by the adapter at attach time. Examples:

- Discord embodiment: `send_message`, `read_channel`, `add_reaction`, `manage_threads`
- Browser embodiment: `navigate`, `click`, `type`, `screenshot`, `extract_text`

The runtime-state Activity model can require an embodiment with a specific capability before scheduling. This is the seam where embodiment integrates with the SIP-1.1 substrate.

---

## 6. Resource Budgets

The goal is not to simulate a human body. The goal is to prevent irresponsible scheduling — especially for ambient agents that may otherwise burn tokens or take unbounded action.

First-cut budget dimensions (coarse, intentionally simple):

- **attention_budget** — how much focused time the agent can hold per window
- **compute_budget** — token / inference cost ceiling
- **action_budget** — count of embodied actions per window
- **concurrency_allowance** — how many activities can be open at once

Budget exhaustion forces a transition (e.g., back to ambient, or detach embodiment) rather than silent overrun.

Budgets attach to the agent, not the embodiment, so cross-embodiment usage is summed.

---

## 7. Adapter Pattern

Embodiments follow the existing SquadOps hexagonal pattern.

- **Port:** `EmbodimentPort` in `src/squadops/ports/`
- **Adapters:** `adapters/embodiment/discord/`, `adapters/embodiment/browser/`, etc.
- **Factory:** `EmbodimentFactory` selects adapter by `embodiment_type` and platform config

The adapter owns:

- Connection lifecycle (attach, reconnect, detach)
- Health checks
- Capability declaration
- Translating Activity goals into surface-specific actions
- Updating location_ref when the adapter knows location changed

The core owns:

- Embodiment record (attachment_state, health, capability_set, location_ref)
- Resource budget enforcement
- Event emission on state transitions
- Integration with Activity and FocusLease from the v1.1 substrate

---

## 8. First Proof Point: Discord Presence

Recommended first surface: **Discord**.

Why Discord:

- Stable, well-documented SDK (discord.py / discord.js)
- No physics or world simulation
- Clean message-event model maps naturally to Activity
- Easy to test in CI with a private guild
- Real Backspring use case: agents that monitor channels, respond to mentions, post status

Minimum capability set:

- Connect to a Discord guild
- Listen on a configured channel
- Send messages
- React to mentions
- Cleanly detach

Acceptance for Phase 1 of this SIP:

- An ambient agent can attach a Discord embodiment, listen on a channel, respond to a mention, and detach cleanly on shutdown
- Embodiment state transitions are observable via the existing telemetry seam
- A focus lease prevents two activities from claiming the embodiment simultaneously

---

## 9. Future Surfaces (Out of Scope for v1.2)

Documented here so reviewers see the trajectory, but **not** part of this SIP:

- **Browser** — natural second surface; reuses existing browser automation patterns
- **Minecraft via Mineflayer** — requires its own SIP; pulls in pathfinding, block placement, world acceptance checks
- **Decentraland / The Sandbox** — far future; depends on platform stability

The substrate proposed here should accommodate all of them without core changes.

---

## 10. Implementation Phases

### Phase 1 — Core embodiment model

- `EmbodimentPort` interface
- Embodiment record + Postgres table
- Lifecycle state machine
- Event emission
- Resource budget primitives (attention, compute, action, concurrency)

**Acceptance:** Embodiment records exist and transition states cleanly. No adapter required yet.

### Phase 2 — Discord adapter

- `adapters/embodiment/discord/` with full lifecycle support
- Connect, listen, send, react, detach
- Capability declaration
- Health checks via Discord gateway

**Acceptance:** an ambient agent can hold a Discord presence end-to-end.

### Phase 3 — Activity integration

- Activities can declare `requires_embodiment: <type>` and `required_capabilities: [...]`
- Scheduler refuses to start an Activity without a matching attached embodiment
- Pause/resume semantics handle embodiment desync

**Acceptance:** a duty agent can hold a Discord embodiment, take a moderation Activity, pause it on disconnect, and resume it on reconnect.

### Phase 4 — Browser adapter (optional, demonstrates substrate generality)

- Headless browser embodiment with navigate/click/type/screenshot
- Validates the abstraction by exercising a second surface

**Acceptance:** the browser adapter ships without changing any core embodiment code.

---

## 11. Acceptance Criteria

The SIP is successful when:

1. **Identity / embodiment separation** is clean — agents survive embodiment loss; embodiments cannot exist without agents
2. **Observable lifecycle** — every embodiment state transition is evented and queryable
3. **Generic location** — core never interprets `location_ref`; adapters do
4. **Capability-aware scheduling** — Activities cannot start without a matching embodiment capability
5. **Budget enforcement** — exhaustion causes explicit transitions, never silent overrun
6. **First proof point lives** — Discord adapter passes integration tests in CI
7. **Substrate generality** — adding the browser adapter requires zero core changes
8. **No regressions** — `run_regression_tests.sh` continues to pass; v1.1 runtime-state primitives unaffected

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Surface-specific concerns leak into core | Keep `location_ref` opaque; review every PR for adapter-specific imports in core |
| Discord adapter complexity bleeds in | Keep adapter behind clean port; use a minimal capability set |
| Budgets become a new policy quagmire | Start coarse (4 dimensions); resist adding more until needed |
| Embodiment desync silently degrades agents | Mandatory health checks; desync transitions trigger explicit Activity pause |
| Multiple embodiments per agent contention | Defer multi-embodiment to a follow-on; v1.2 is one embodiment per agent |

---

## 13. Open Questions

1. Should one agent be allowed to hold multiple embodiments simultaneously in v1.2, or is it strictly one-at-a-time?
2. How does embodiment attachment interact with the focus lease from v1.1? Same lease type, or a distinct embodiment lease?
3. Where do embodiment credentials (Discord bot tokens, browser cookies) live? `SecretManager` already exists — likely reuse via `secret://` refs.
4. Should resource budgets be configurable per agent role, or global defaults?
5. Does the Discord adapter belong in the main `adapters/` tree, or does it warrant a separate optional install (extras dependency)?

---

## 14. References

- Depends on: `sips/proposed/SIP-Agent-Runtime-State.md` (v1.1)
- Parent vision: `sips/proposed/SIP-Agent-Runtime-Modes.md`
- Original full proposal: commit `76a1f90` on main
- Related: SIP-0061 (LangFuse Observability — telemetry pattern reused for embodiment events), SIP-0042 (memory adapter — pattern for optional integrations)
- Hexagonal pattern: existing `src/squadops/ports/` and `adapters/` structure
