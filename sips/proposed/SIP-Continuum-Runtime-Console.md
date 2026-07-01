---
title: Continuum Runtime Console
status: proposed
author: Jason Ladd
created_at: '2026-06-30'
---

# SIP-XXXX: Continuum Runtime Console

**Status:** Proposed
**Authors:** Jason Ladd (Backspring Labs / SquadOps)
**Created:** 2026-06-30
**Targets:** Continuum Console (v1.2 candidate)
**Depends on:**
- `sips/implemented/SIP-0069-SquadOps-Console-Control-Plane.md` — Continuum plugin / perspective model, CLI-parity discipline
- `sips/implemented/SIP-0089-Agent-Runtime-State.md` — `mode`, `runtime_status`, FocusLease, RuntimeActivity, DutyWindow
- `docs/agent-runtime-status-model.md` — the canonical **Health = `runtime_status`, Posture = `mode`** rule
**Related issues:** #230 (null `mode`/`runtime_status` back-compat), #231 (`network_status` → `runtime_status` consolidation), #218 (API lane conformance)

---

## 1. Summary

Continuum should evolve from a primarily cycle-oriented operator console into a broader **agent runtime console**.

SquadOps agents (SIP-0089) are no longer only participants in cycles. At any moment an agent may be idle, executing a bounded task, participating in a squad cycle, holding a persistent duty, or maintaining ambient presence in an external channel. The console should reflect that.

This SIP proposes three changes:

1. **Promote the Agent Roster to the default (Home) anchor** — surface *all* known agents with their health and posture at a glance, not only agents currently in a cycle.
2. **Add a Duty perspective** to the left-side navigation, with a clipboard icon, representing persistent operational responsibilities (duties, watches, ambient presence).
3. **Conform the console's status vocabulary to the canonical runtime model** (`docs/agent-runtime-status-model.md`) so the console, CLI, and API all say the same thing.

This is an **enhancement of existing console surfaces**, not a greenfield build (see §5).

## 2. Motivation

The current console mental model is too cycle-centered. That was right when the operational question was *"what cycle is running?"* The runtime model has matured; the more important operator question is now:

> **What are my agents doing, and who needs help?**

An agent may be online but idle, executing a bounded task, in a cycle, on a persistent duty, ambiently watching a channel, blocked, degraded, or offline while still holding an assignment. Without this change, Duty and Ambient work is either hidden, misrepresented as cycles, or scattered into ad-hoc panels — which weakens the operator model and makes Continuum less useful as the primary control plane.

## 3. Background — the canonical runtime vocabulary (grounded in code)

This SIP does **not** define new status vocabulary. It adopts the vocabulary SIP-0089 already shipped and that `docs/agent-runtime-status-model.md` designates as canonical. The console MUST conform to it.

The rule: **Health = `runtime_status`. Posture = `mode`.** These are two orthogonal axes, not one badge, and not three.

| Signal | Field / source | Allowed values | Console role |
|--------|----------------|----------------|--------------|
| **Health** | `agent_runtime_state.runtime_status` (`runtime/models.py:25`) | `online` · `degraded` · `recovering` · `offline` | The health pill. Canonical; coordinator-owned. |
| **Posture (Mode)** | `agent_runtime_state.mode` (`runtime/models.py:24`) | `ambient` · `cycle` · `duty` | The mode chip. Coordinator is the single writer (D16). |
| Lifecycle state | `agent_status.lifecycle_state` | `STARTING` · `READY` · `WORKING` · `BLOCKED` · `CRASHED` · `STOPPING` (+ `UNKNOWN`) | **Feeds** health via a locked map (`lifecycle_status.py`: `BLOCKED→degraded`, `CRASHED→offline`, …). Detail/tooltip only — *not* a co-equal display axis. |
| `network_status` (legacy) | derived from heartbeat age | `online` · `offline` | **Deprecated** (#231). Fallback for the health pill *only* when an agent has no runtime-state row yet. Do not build new dependencies on it. |
| Interruptibility | `FocusLease.interruptibility` (`runtime/models.py:26`) | `none` · `low` · `medium` · `high` | "Safe to interrupt" / attention hints. |
| Current activity | `RuntimeActivity` (`runtime/models.py:300`) | `state ∈ {pending, running, paused, completed, aborted, failed}`; `source_kind ∈ {cycle_task, workload, duty_handler, ambient_observation, embodied_action}` | "What is it doing right now" + current-assignment line. |
| Assignment | `Assignment` (`runtime/models.py:83`) | `type ∈ {duty, reserve, cycle_eligibility}`; `strictness ∈ {hard, soft}` | Duty perspective; persists independent of health. |
| Duty window (computed) | `WindowState` (`runtime/models.py:57`) | `before_window` · `in_reserve_before` · `active` · `in_reserve_after` · `closed` · `missed` | Duty perspective timeline + escalation. |

**Two things that are NOT modes:** `idle` and `task`. "Idle" is *derived* — no active FocusLease and no non-terminal RuntimeActivity (the activity endpoint 404s; the CLI already treats 404 as idle). "On a task" is *derived* — a RuntimeActivity whose `source_kind` is `cycle_task` or `workload`. The console must present these as derived facts, never as values of the `mode` enum.

## 4. Non-Goals

This SIP does **not**:

- redesign the full Continuum shell or replace the perspective model;
- make Continuum the owner of SquadOps runtime logic, scheduling, or a Duty orchestration engine;
- add a complete observability platform, or runtime-state history in v1;
- add destructive agent controls (start/stop/kill) from the console;
- add a separate **Ambient** perspective (ambient is surfaced within Duty for now — §9, Decision 4);
- introduce a new status vocabulary — it consumes SIP-0089's canonical fields verbatim;
- force Duty or Ambient work to be represented as cycles.

## 5. Current console state (what already exists)

The console lives in-repo at `console/continuum-plugins/` (Continuum plugin architecture, SIP-0069). Relevant existing assets this SIP builds on rather than replaces:

- **Perspectives today:** `signal` (Home), `discovery` (Projects), `systems`, `cycles`, `squad`. Registered via `PerspectiveSpec` in `console/app/main.py` and nav contributions in each plugin's `__init__.py`.
- **`squadops.agents` plugin** already renders `AgentsStatus.svelte` (custom element `squadops-agents-status`) — an "Agent Squad" card showing name / role / status / mode / current task, polling `GET /api/health/agents` every 10s. It currently lives in the **signal right-rail**.
- **`squadops.squad` perspective** already has an "Agent Health" tab (`AgentHealthTab.svelte`).
- **Backing endpoints (runtime-api, `api/routes/platform_health.py`):**
  - `GET /health/agents` — roster list (backs the card above; proxied by the console as `/api/health/agents`).
  - `GET /health/agents/{id}/runtime-state` — `AgentRuntimeState` (`mode`, `runtime_status`, `focus`, `interruptibility`, `current_assignment_ref`, `current_runtime_activity_id`). Backs `squadops agent state`.
  - `GET /health/agents/{id}/activity` — current `RuntimeActivity`. Backs `squadops agent activity`.
- **Icon library:** Lucide, referenced by name in nav contributions (`icon: "refresh-cw"`, `"users"`, `"folder"`, `"settings"`).

**Known gap this SIP exposes:** the existing card's status logic collapses health and mode (`healthy|idle|online|ready → healthy`, `busy → busy`). That conflates the two canonical axes and must be fixed as part of §6.1.

**Known gap for Duty:** there is **no list endpoint** for assignments, duty windows, or focus leases — only per-agent runtime-state/activity. The Duty perspective therefore requires a new read endpoint (§8).

## 6. Proposed changes

### 6.1 Promote the Agent Roster to the default (Home) anchor

Raise the existing `squadops-agents-status` roster from the Signal right-rail to the **main slot of the default Home perspective** (whose current internal perspective id is `signal`; Home is the operator-facing label), and increase its fidelity so it answers "who is alive, what are they doing, who needs help?" at a glance.

Each agent row shows, per the **normative field mapping in §7**:

- agent name and role;
- **health pill** ← `runtime_status` (not the collapsed status class it uses today);
- **mode chip** ← `mode` (`ambient` / `cycle` / `duty`), rendered separately from health;
- **current activity** ← RuntimeActivity `activity_type` + `goal` + `state` (empty = "idle");
- **current assignment** when applicable;
- **interruptibility** hint;
- an **attention indicator** computed by the derivation rule in §7.1.

The roster lists **all known agents** — meaning every agent returned by the canonical roster endpoint (`GET /health/agents`), including agents with idle/inactive posture and agents not participating in any cycle, but excluding archived/retired agents unless the endpoint explicitly marks them visible. Idle is represented intentionally, never omitted.

### 6.2 Add a Duty perspective (clipboard icon)

Add a new first-class **Duty** perspective to the left nav, as a **top-level peer of Cycles** (not a tab under `squad`):

- Register a `duty` `PerspectiveSpec` in `console/app/main.py` and a `squadops.duty` plugin contributing a `nav` entry with **`icon: "clipboard"`** (valid Lucide name; omit `icon_path` as the `systems` plugin does — the clipboard glyph is not a single `d` path). Place it adjacent to Cycles — suggested nav `priority: 750` (between `cycles`=800 and `squad`=700) so Duty and Cycles read as sibling operator perspectives.
- The Duty perspective is **assignment-centric**: it assembles, per assignment, the assignment itself, its duty-window schedule/state, and the **agent activity executed against it** (RuntimeActivity). It represents persistent/standing responsibilities — scheduled duties, repeating check-ins, watch assignments, ambient monitoring, and escalation-oriented responsibilities.
- It is **not** a cycle list and must not reuse cycle-specific labels. It reads from the duty data model in §8.

### 6.3 Conform console vocabulary to the canonical model

The console consistently distinguishes **Health** (`runtime_status`), **Mode** (`mode`), and — only as tooltip/detail — **Lifecycle** (`lifecycle_state`). It must not collapse Health and Mode into a single badge (Decision 3), must render `null` `mode`/`runtime_status` explicitly as "unknown" (#230), and must not introduce new dependencies on `network_status` (#231).

## 7. Roster field → data-source mapping (Normative)

| Column | Source field | Endpoint | Notes |
|--------|--------------|----------|-------|
| Name / Role | agent name, role | `GET /health/agents` | — |
| Health pill | `runtime_status` | `GET /health/agents` (or per-agent runtime-state) | `online/degraded/recovering/offline`; `null` → **"unknown"** (#230); fall back to `network_status` **only** when no runtime-state row exists. |
| Mode chip | `mode` | `GET /health/agents` / `.../runtime-state` | `ambient/cycle/duty`; `null` → **"unknown"** (agent has no runtime-state row yet, #230). Idle is *not* a null mode — it is derived from activity/focus. |
| Current activity | `RuntimeActivity.activity_type` + `.goal` + `.state` | `GET /health/agents/{id}/activity` | `state ∈ {pending,running,paused,…}`; **404 → idle** (match the CLI). |
| Current assignment | `current_assignment_ref` → `Assignment` | §8 endpoint | `type ∈ {duty,reserve,cycle_eligibility}`. When multiple ownership signals exist, the primary line follows the **active FocusLease owner** — the runtime already arbitrates this via lease precedence (a SIP-0089 concern, not a console display choice); standing assignments render as secondary. If a fixed fallback ordering is ever needed, use `duty > cycle > ambient` and revisit after live usage. |
| Interruptibility | `FocusLease.interruptibility` | `.../runtime-state` (`focus`) | `none/low/medium/high`. |
| Attention | derived | — | rule in §7.1. |

### 7.1 "Needs attention" derivation rule

Attention is **derived**, not a stored field, and has two severity tiers.

**Attention** (operator action likely needed) when **any** of:

1. `runtime_status ∈ {degraded, offline}`; or
2. `lifecycle_state ∈ {BLOCKED, CRASHED}` (surface the reason); or
3. the active `RuntimeActivity.state ∈ {failed, aborted}`; or
4. a duty `WindowState == missed` under `MissedWindowPolicy == require_operator_review`.

**Watch** (caution, lower severity — no action required yet) when `runtime_status == recovering` — a transient boot/shutdown state per the lifecycle map (`STARTING`/`STOPPING → recovering`). `online` is normal.

`lifecycle_state` may *contribute* to derived attention and tooltip detail, but it must not become a third primary status badge alongside health and mode.

**Recommendation:** compute this server-side (a derived field on the roster endpoint) so the console and any future CLI agree on one definition rather than each surface re-deriving it.

## 8. Duty perspective data model & required API

The Duty perspective is **organized around assignments**: each entry assembles an assignment, its window schedule/state, and the agent activity executed against it (RuntimeActivity), so the operator sees not just *what is assigned* but *how it is being served*. It reads from SIP-0089 primitives:

- **Assignments** — `type ∈ {duty, reserve, cycle_eligibility}`, `strictness ∈ {hard, soft}`, `recall_policy`, `missed_window_policy`. Persist independently of health, so an **offline** agent can still show an assigned duty.
- **Duty windows** — computed `WindowState` (`before_window/in_reserve_before/active/in_reserve_after/closed/missed`) for the timeline and escalation surfacing.
- **Focus leases** — `owner_type` (`duty/cycle/ambient`), `interruptibility`, `expires_at`, `renewal_policy`.
- **Ambient** — surfaced here for now as `mode == ambient` and/or `RuntimeActivity.source_kind == ambient_observation` / lease `owner_type == ambient`.
- **Scheduler cadence** — `SchedulerConfig.poll_interval_seconds` (default 30). Note `SchedulerConfig.enabled` **defaults to `False`**; when disabled, the perspective must render an explicit **"duty scheduler disabled"** state, not an empty board that implies "no duties."

**Required new API (read-only):** no list endpoint exists today. This SIP requires one — e.g. `GET /api/v1/duties` (a duty board of active/upcoming windows across agents) and/or `GET /api/v1/agents/{id}/assignments`. Per the runtime-api lane rules (CLAUDE.md → API Conventions, #218):

- Duty listing is an **authenticated, managed resource** → it belongs on **`/api/v1/*`**, **not** `/health/*` (which is reserved for no-auth operational probes).
- The existing per-agent `runtime-state`/`activity` endpoints living under `/health/*` are a **known deviation** — do **not** extend that pattern for the new duty resource.
- Surface the exact shape/prefix to #218 before building, and add a read scope (e.g. an `agents:read`/`cycles:read`-analogous scope) enforced via the OIDC BFF.

## 9. Product decisions

- **Decision 1 — Duty is a first-class perspective, peer to Cycles.** Duty is a distinct operational mode (persistent, responsibility-oriented, often time-based); it sits at the **same left-nav level as Cycles**, not as a tab under `squad`. Treating it as a subtype of Cycle would blur the runtime model. Cycles answers *what goal-directed effort is running*; Duty answers *what standing responsibilities agents hold, and how they are being served*.
- **Decision 2 — the Agent Roster is the default console anchor.** The operator's first need is runtime awareness. Concretely: promote the existing `squadops-agents-status` roster into the Home/`signal` main slot (§6.1).
- **Decision 3 — Mode and Health stay separate.** "On duty" and "degraded" are different kinds of fact — one is posture (`mode`), the other is health (`runtime_status`). Never collapse them into one badge.
- **Decision 4 — Ambient is visible through Duty for now.** Ambient attention is close enough to Duty to share a perspective initially; a dedicated Ambient perspective can be introduced later. Do not hard-code that assumption.

## 10. Design intent / UX

The updated console should feel like a **mission-control surface for an agent runtime**. Opening Continuum, the operator immediately sees which agents exist, which are available, which are working, which hold long-running duties, which are ambiently watching, which are blocked/degraded, and which need intervention.

The Duty perspective should feel like a standing operations board, not a project page. The roster should feel like the default operational heartbeat of the system. Design review ensures the experience is legible, well-ordered, and polished — it must not read as a raw status table, and its empty / loading / degraded / unavailable states are intentionally designed.

## 11. CLI parity

SIP-0069 makes console↔CLI parity normative. Two backing CLI commands already exist and should share the console's vocabulary verbatim:

- `squadops agent state <id>` → `GET /health/agents/{id}/runtime-state`
- `squadops agent activity <id>` → `GET /health/agents/{id}/activity`

When §8's duty read endpoint lands, add a parity command (e.g. `squadops duties list` / `squadops agent duties <id>`) so the Duty board is reachable from the CLI. This parity is required before the Duty perspective is considered complete, but it does **not** block Phase 1 roster fidelity (which reuses endpoints that already have CLI coverage).

## 12. Phased delivery

- **Phase 1 — Roster fidelity (no backend changes).** Promote `squadops-agents-status` to the Home main slot; split health vs mode per §7; add current-activity, interruptibility, and the §7.1 attention indicator; render `null` and "idle" explicitly. Consumes existing endpoints only.
- **Phase 2 — Duty perspective (read-only).** Lead with a **cross-agent Duty board endpoint** on `/api/v1` (§8) as the primary backing source, so the perspective avoids N+1 per-agent calls; per-agent assignment endpoints are optional drill-down. Add the `squadops.duty` plugin (clipboard nav) rendering assignments, windows, and ambient, with explicit *scheduler-disabled* / *no-duties* / *unavailable* / *unauthorized* states.
- **Phase 3 — Parity & polish (deferred).** CLI parity command, filters/grouping, and (optionally) runtime-state history.

## 13. Acceptance Criteria

**Roster (default anchor)**
- The default (Home) screen lists **all** known agents, including idle agents and agents not in any cycle.
- Each agent shows a **health pill** sourced from `runtime_status` (with the §7 null/`network_status` fallback rule), a **mode chip** sourced from `mode`, a **current activity** line, and an **attention indicator** per §7.1.
- Health and mode are rendered as **separate** signals (Decision 3); the existing collapsed status class is removed.
- `null` `mode`/`runtime_status` renders as an explicit "unknown" state (#230); no new dependency on `network_status` is introduced (#231).
- Idle (activity 404) is represented intentionally.

**Duty perspective**
- A **Duty** perspective appears in the left nav as a **top-level peer of Cycles**, with a **clipboard** (Lucide) icon, and is selectable as a distinct perspective.
- Duty is **not** presented as a cycle list and uses duty vocabulary (assignment, check-in, watch, cadence, escalation).
- Duty is assignment-centric: each assignment assembles its window schedule/state and the agent activity executed against it, including ambient watch-style assignments, and assignments render for offline agents.
- The Duty board distinguishes and renders differently: **scheduler disabled** (`SchedulerConfig.enabled == False`), **no active/upcoming duties**, **duty data unavailable** (API/runtime error), and **authorization denied** — never a single ambiguous empty board.

**Runtime semantics**
- `ambient`, `cycle`, `duty` are the only mode values shown; `idle`/`task` are presented as derived facts, never as modes.
- Health (`runtime_status`) is never conflated with mode; `lifecycle_state` appears only as tooltip/detail, never as a third primary badge.
- The console introduces **no new persisted or API-visible status vocabulary** for health, mode, lifecycle, activity, or assignment. Derived display facts (idle, the attention/watch tiers) are computed — preferably server-side — from the canonical fields, not stored as new enums.

**API / conformance**
- The new duty read endpoint lives on `/api/v1/*`, is authenticated with a read scope, and was reviewed against #218 before merge; no new URL prefix/variant was added, and the `/health/*` per-agent pattern was not extended.

**UX quality**
- The roster is readable and modern with clear visual hierarchy; empty, loading, degraded, and unavailable states are intentionally designed and pass design review for legibility and polish.

## 14. Risks and Mitigations

- **R1 — Default screen becomes noisy.** All agents × several signals is a lot. *Mitigation:* attention-first ordering, grouping (by role or attention state), filters, strong hierarchy.
- **R2 — Duty implemented as "just another cycle view."** *Mitigation:* distinct data model (§8) and vocabulary; no cycle labels unless a duty actually launches a cycle.
- **R3 — Status vocabulary drift** across agents, API, and UI. *Mitigation:* this SIP forbids new vocabulary — the console consumes SIP-0089's canonical fields, and the `docs/agent-runtime-status-model.md` rule is the single source. This is the risk the original draft most needed to close.
- **R4 — Ambient outgrows Duty.** *Mitigation:* keep Ambient inside Duty for now (Decision 4) without hard-coding the assumption; a future SIP can split it out.
- **R5 — New endpoint drifts the API surface** (#218). *Mitigation:* `/api/v1` lane, review before build, add a read scope; do not extend the `/health/*` deviation.

## 15. Open Questions

1. The Duty board leads with a **cross-agent** endpoint (`/api/v1/duties`) with per-agent assignment endpoints as optional drill-down (resolved, §12); the remaining open detail is the exact response **field schema** for the board.
2. Should "needs attention" be computed **server-side** (recommended, §7.1) or client-side?
3. Should the roster group agents by **role**, **mode**, or **attention state** by default?
4. Should Duty support operator-authored checklists, or only agent-owned responsibilities? (Leaning: agent-owned only for v1.)
5. Should runtime-state history be in v1 or deferred to Phase 3? (Leaning: deferred.)

## 16. References

- `sips/implemented/SIP-0069-SquadOps-Console-Control-Plane.md` — Continuum plugin/perspective model, CLI-parity matrix.
- `sips/implemented/SIP-0089-Agent-Runtime-State.md` — modes, duty windows, focus leases, RuntimeActivity.
- `docs/agent-runtime-status-model.md` — canonical Health/Posture rule (#231).
- `src/squadops/runtime/models.py` — `RuntimeMode`, `RuntimeStatus`, `Interruptibility`, `Assignment`, `FocusLease`, `RuntimeActivity`, `WindowState`.
- `src/squadops/api/routes/platform_health.py` — `/health/agents*` endpoints.
- `console/continuum-plugins/squadops.agents/` — existing roster card (`AgentsStatus.svelte`).
- Issues: #230 (null back-compat), #231 (`network_status` consolidation), #218 (API lane conformance).
