---
sip_uid: "01KB6432E7MBYVZVXYYQT916W6"
sip_number: null
title: "SquadOps Console (SOC) - Web-OS Interface, Observation Gateway, Theme Engine, and Auth Integration"
status: "proposed"
author: "Jason Ladd"
approver: null
created_at: "2025-11-28T20:57:28Z"
updated_at: "2025-11-28T20:57:28Z"
original_filename: "SIP-SOC-WebOS.md"
---

# SIP-SOC-WebOS: SquadOps Console (SOC)
### Web-OS Interface • Observation Gateway • Theme Engine • Hidden "Enterprise" Theme • Auth Integration

**Status:** Proposed (Unnumbered)  
**Owner:** Jason / SquadOps Maintainers  
**Version:** Draft v1.4 (Export Ready, revised)  
**Target Release Window:** 1.0 → 1.3  
**Scope:** SquadOps Framework, SOC Frontend, SOC Backend, Observation Gateway, Auth, Theming

---

## Revision History

- **v1.4** – Corrected Theme catalog to list only `core` and `enterprise` themes and clarified that Dawn/Day/Dusk/Dark/Auto are **display modes**, not themes.
- **v1.3** – Clarified Theme Engine vs Display Modes semantics, tightened Enterprise theme behavior, and refined left-hand navigation rail into workspace switchers vs action icons.
- **v1.2** – Introduced formal Theme Engine and time-of-day Display Modes, Enterprise hidden theme activation via `make it so`, and initial navigation layout.
- **v1.1** – Clarified required tech stack (Next.js, shadcn/ui, Zustand, TanStack Query, Recharts, oidc-client-ts) and removed references to specific implementation tools.
- **v1.0** – Initial draft of SOC Web-OS specification.

---

## 1. Purpose

This SIP defines the **design and phased implementation** of the **SquadOps Operations Console (SOC)** — a web-OS style operator interface that acts as the primary "glass cockpit" for observing and steering SquadOps multi-agent activity.

The SOC will provide:

- A **window-manager UI** (desktop-style) with floating and dockable windows  
- A centralized **Observation Gateway (OGW)** for cached, aggregated operational telemetry  
- A formal **Theme Engine** (themes = visual skins, separate from time-of-day modes)  
- A **Display Mode** system (Dawn, Day, Dusk, Dark, Auto) applied on top of the active theme  
- A hidden **"enterprise" theme**, activated via the console command `make it so`  
- A Keycloak-ready **Authentication & Authorization** model  
- A clean **API surface suitable for both web and mobile SOC clients**  

The design is intentionally **modular** and **incremental**, so we can deliver value in phases without blocking on the full vision.

---

## 2. Goals & Non-Goals

### 2.1 Goals

1. Provide a **first-class operator interface** for SquadOps:
   - Monitor agents, tasks, execution cycles, alerts, health, and telemetry
   - Inspect CycleDataStore artifacts and summaries
   - Surface Prefect and Langfuse summaries for orchestration and tracing

2. Establish a **clean architecture**:
   - SOC frontend talks to SOC backend APIs only
   - SOC backend relies on Observation Gateway (OGW) for hot telemetry
   - Avoids direct DB queries or tight polling from the UI

3. Implement a **flexible theming system**:
   - Token-based theme engine
   - Time-of-day display modes (Dawn / Day / Dusk / Dark / Auto)
   - Hidden "enterprise" theme triggered by `make it so` in the command console

4. Support **future mobile clients**:
   - SOC backend APIs must be client-agnostic and documented
   - Mobile can reuse all key views (health, agents, cycles, alerts)

5. Integrate with **AuthN/AuthZ**:
   - Keycloak as reference OIDC provider
   - Role-based access control (viewer/operator/maintainer/admin/mobile_ops)

### 2.2 Non-Goals

- Building a full **Prefect UI** or replacement for Prefect Cloud  
- Building a full **Langfuse UI**  
- Creating a generic dashboard-builder or low-code UI framework  
- Implementing multi-tenant SaaS, billing, or complex customer management  
- Replacing the IDE (Cursor) as the primary development UI  

---

## 3. High-Level Architecture

The SOC consists of five main layers:

1. **SOC Frontend (Web OS UI)**  
   - React/Next.js-based SPA or app shell  
   - Implements window manager, docking, theme switching, and user interactions

2. **SOC Backend API (FastAPI)**  
   - Exposes a stable REST + WebSocket API for SOC and mobile  
   - Houses presentation-level view models and role-based validations

3. **Observation Gateway (OGW)**  
   - Intermediate service that **samples, aggregates, and caches** operational data:
     - System metrics
     - Agent states
     - Execution cycle summaries
     - Queue depth and other health metrics  
   - Provides a single hot-data source to SOC Backend

4. **Auth Layer**  
   - Keycloak reference OIDC provider (integrated via Auth SIP)  
   - SOC and OGW enforce roles/permissions

5. **Back-End Integrations**  
   - CycleDataStore (new CycleData design)  
   - Task Adapter (SQL/prefect)  
   - Prefect adapter (for run/flow states, summary only)  
   - Langfuse (for trace summaries)  
   - RabbitMQ/SquadComms metrics  

SOC Frontend → SOC Backend → OGW → downstream systems.

---

## 4. Web-OS UX Specification

### 4.1 Window Manager Model

The SOC behaves like a lightweight window manager in the browser:

- **Left-hand navigation rail** lists "apps":
  - Console
  - System Health
  - Agents
  - Cycles
  - Logs
  - Alerts
  - Settings

- Selecting an app opens a **window** which can be:
  - **Floating**: draggable around the desktop area
  - **Docked**: snapped to specific edges (bottom, right, etc.)
  - **Resizable**: vertical and/or horizontal resizing
  - **Minimized/closed**: window can be hidden and restored

The window manager is responsible for:
- Z-ordering (bring to front)
- Window state (open/closed/docked)
- Persistent layout (optional later phase)

### 4.2 Core Windows & Overlays

1. **Command Console (bottom dock-capable)**  
   - Primary textual interaction surface  
   - Command entry (incl. special commands like `make it so`)  
   - Output history with scrollback  
   - Dockable bottom panel or floating window

2. **System Health HUD (top overlay)**  
   - Displays critical high-level metrics:
     - CPU/RAM utilization (local / key hosts)  
     - Queue depth summaries  
     - Agent online/offline counts  
     - Execution cycles in progress / failing  
   - Typically anchored at top as a slim bar or overlay

3. **Agent Inspector**  
   - List of agents with status (online/offline, last heartbeat)  
   - Per-agent detail view:
     - Role, capabilities, skills, build_hash, version
     - Agent info and manifest metadata
     - Recent events or faults

4. **Cycle Explorer**  
   - List of execution cycles (ECIDs) with key metadata  
   - Per-cycle detail:
     - Status (active, completed, failed)  
     - Associated PIDs  
     - Links to artifacts in CycleDataStore  
     - Timeline markers (phases, pulses when added to the model)

5. **Streaming Logs Viewer**  
   - Right-docked panel for streaming logs and events  
   - Filters (agent, ECID, level)  
   - Pause/resume and search

6. **Alerts & Notifications Center**  
   - Aggregated alerts with de-duplication and debouncing  
   - Severity filtering
   - Drill-down to relevant agent/cycle

7. **Settings & Preferences**  
   - Display Mode selection (Dawn/Day/Dusk/Dark/Auto)  
   - Theme preview  
   - Auth/identity information  
   - Environment summary (local vs cloud)  

---

## 5. Observation Gateway (OGW)

The OGW is a new service whose job is to **protect core systems** from aggressive polling while providing **near real-time** telemetry to the SOC.

### 5.1 Responsibilities

- Periodically sample metrics and states from:
  - Local host (CPU, RAM, disk, network)
  - Cloud provider metrics (where configured)
  - RabbitMQ queue depth and stats
  - Agent heartbeats / status messages
  - Execution cycle summary tables
  - Prefect (flow runs / task run summaries)
  - Langfuse (trace/segment summaries)

- Aggregate data into:
  - **System health summary** (single JSON document)  
  - **Agent status list**  
  - **Cycle summaries**  
  - **Alert/event timeline**

- Cache aggregated data with short TTLs.

### 5.2 Caching Requirements

- **Hot metrics** (CPU/RAM, queue depth, active agent count):  
  - TTL: **1–2 seconds**

- **System summary** (overall health, top-level statuses):  
  - TTL: **5–10 seconds**

- **Heavier rollups** (top failing cycles, aggregated histories):  
  - TTL: **30–60 seconds**

### 5.3 OGW API Surface

OGW exposes **only aggregated, safe-to-display** views:

- `GET /api/v1/system/health`  
  - Returns overall health summary (status, metrics, derived indicators)

- `GET /api/v1/system/summary`  
  - High-level summary: agents online, cycles in progress, error counts, etc.

- `GET /api/v1/agents/status`  
  - Detailed agent status list

- `GET /api/v1/cycles/summary`  
  - High-level view of recent cycles, statuses, timestamps

- `WS /ws/metrics`  
  - WebSocket for streaming deltas / periodic snapshots

SOC Backend uses these endpoints to serve UI-friendly representations.

SOC **must not** query DBs, Prefect, or Langfuse directly on a tight loop.

---

## 6. Theme Engine & Display Modes

### 6.1 Conceptual Separation: Themes vs Display Modes

We explicitly separate:

- **Themes** – Visual skins (design tokens)
- **Display Modes** – State machine that selects which theme to use

#### Themes

Themes are sets of tokens (colors, radii, shadows, typography tweaks). Initial catalog:

- `core` — default SquadOps theme (baseline from SOC style guide), supports all display modes  
- `enterprise` — hidden retro starship-bridge theme (see §7), also supports all display modes  

Each theme is defined in terms of design tokens, *not* hard-coded values in components.


Display Modes are *user-facing options* that determine which **display variant of the currently active theme** is used:

- `Dawn`
- `Day`
- `Dusk`
- `Dark`
- `Auto` (default)

**Default Display Mode:** `Auto`

Auto mode maps local browser time to modes:

- 05:00–09:59 → Dawn  
- 10:00–16:59 → Day  
- 17:00–20:59 → Dusk  
- 21:00–04:59 → Dark  

When the user explicitly selects a mode (Dawn/Day/Dusk/Dark), that selection **overrides** Auto until the user chooses Auto again.

### 6.2 Theme Selector Behavior

- A **Theme/Display Mode selector** must be available in Settings and/or a quick-access menu.
- It lists only:
  - Dawn  
  - Day  
  - Dusk  
  - Dark  
  - Auto (recommended)  

The **enterprise theme is not shown in this selector**.

### 6.3 Persistence

- Phase 1–2: store the display mode preference client-side (e.g., `localStorage`) keyed per browser profile or user ID.  
- Future: optional server-side preference storage aligned with user identity from Keycloak.

### 6.4 Runtime Requirements

- Theme changes must apply at runtime, without full page reloads.  
- All windows and chrome must respond cleanly to theme changes.  
- Adding a new theme should require minimal changes outside token definitions.

---

## 7. Hidden "Enterprise" Theme

### 7.1 Purpose & Concept

The **enterprise** theme is a retro, starship-bridge-inspired appearance (TNG era vibe) implemented in a way that **does not infringe** on copyrighted designs or trademarks.

Design language guidelines:

- Rounded panel shapes with segmented bars  
- Warm accent colors (muted amber, soft orange, dusty pinks, warm reds) on a dark backdrop  
- Subtle gradients in surfaces instead of flat colors  
- Slightly asymmetric panel divisions reminiscent of LCARS-like layouts (but not copied)  
- Existing typography remains; no proprietary fonts required  

### 7.2 Activation Mechanism

The enterprise theme is **hidden from the UI selector** and can only be activated via a console command in the **Command Console window**:

```text
make it so
```

- Exact string: `make it so`  
- Case-insensitive; no punctuation required  
- No extra spaces; internal whitespace is a single space between words

### 7.3 Behavior

When the SOC receives the `make it so` command:

1. The console logs an acknowledgment, e.g.:  
   > "Aye, Captain. Reconfiguring the bridge…"

2. The active theme is set to `enterprise`, irrespective of current Display Mode.

3. The enterprise theme **persists** as long as the user does not explicitly change display modes.

4. If the user later selects **any** mode from the Theme Selector (Dawn/Day/Dusk/Dark/Auto):
   - The enterprise theme is deactivated
   - The newly selected mode drives the new theme decision

The enterprise theme:

- **Is documented in the theme catalog (for developers)**
- **Is not listed in the Theme/Display Mode selector**

### 7.4 Mode Handling for Enterprise

For simplicity, the `enterprise` theme is treated as a **regular theme** in the Theme Engine:

- Display Modes (Dawn/Day/Dusk/Dark/Auto) still apply while `enterprise` is active.
- The visual treatment for each mode under `enterprise` can differ from the `core` theme, but the semantics of the modes (time-of-day / brightness) remain the same.
- The Theme Engine always combines **(active theme)** + **(active display mode)**; `enterprise` does not redefine what a mode is, it only changes how that mode looks.

Special behavior:

- `enterprise` **cannot** be selected from the Theme/Display Mode selector.
- It can **only** be activated via the `make it so` command in the SOC Command Console.
- Once activated, `enterprise` remains the active theme until the user explicitly picks a different theme via the selector or another override is applied.

Implementation detail:

- The theme catalog contains a `core` token set and an `enterprise` token set.
- The Display Mode state machine remains the same regardless of theme; it simply maps to different token variants when `enterprise` is active.

---

## 8. Authentication & Authorization

### 8.1 Identity Provider

- Use Keycloak as the **reference OIDC/OAuth2 IdP**.  
- SOC and OGW must be able to validate tokens issued by Keycloak.  
- Exact Keycloak configuration will be covered in a dedicated Auth SIP; this SIP assumes a working OIDC setup.

### 8.2 Roles

Initial roles:

- `viewer` — can view system summaries, health, high-level information  
- `operator` — viewer plus agent/cycle detailed info, logs, alerts  
- `maintainer` — operator plus certain framework configuration views  
- `admin` — full access, including SOC configuration and environment-level settings  
- `mobile_ops` — restricted role for mobile clients focusing on health/alerts

### 8.3 Role-Based Access

High-level mapping:

- System Health HUD & summary: **viewer+**  
- Agent Inspector: **operator+**  
- Cycle Explorer: **operator+**  
- Logs & Alerts: **operator+** (with possible further granularity later)  
- Settings: **maintainer/admin**  

SOC must handle authorization failures gracefully and present clear messages rather than generic errors.

---

## 9. API Requirements (SOC & Mobile)

The SOC Backend must expose APIs that:

- Are **client-agnostic** (suitable for web and mobile)  
- Use stable, versionable schemas  
- Avoid leaking internal DB schemas directly

Key endpoint categories (high level):

1. **System health & summary**  
2. **Agents list & detail**  
3. **Cycles list & detail**  
4. **Alerts list & detail**  
5. **Log streaming endpoints**  

SOC Backend uses OGW as its primary source for hot state. For heavier data such as artifacts, it can coordinate with CycleDataStore or other services in a controlled, explicit way.

---

## 10. CycleDataStore Integration

- SOC uses CycleDataStore as the source of truth for cycle and artifact data.  
- OGW may provide summarised views (counts, statuses, last updated) but does not replace CycleDataStore.

Rules:

- SOC displays:
  - Execution cycle summaries (status, timestamps, PIDs)  
  - Links/identifiers to artifacts (e.g., design docs, test results, build outputs)  

- Large artifacts:
  - Are **not fetched by default** into the SOC front-end  
  - Are retrieved explicitly when the user drills into a specific artifact  

This keeps the UI responsive and avoids excessive bandwidth usage.

---

## 11. Phased Implementation Plan

The SOC is intentionally split into phases to align with your incremental implementation philosophy and to avoid overwhelming Cursor with a huge change set.

### Phase 0 – Foundations

- Create SOC frontend shell (React/Next.js or equivalent)
- Create SOC backend service skeleton (FastAPI)
- Create OGW skeleton (service + wiring)
- Implement baseline theme engine with **Dark** theme only
- Basic Auth bootstrapping (integration with Keycloak in minimal form)

**Exit criteria:**  
- You can navigate to a basic SOC shell and log in via OIDC.  
- Dark theme is applied globally.

---

### Phase 1 – Window Manager & Console

- Implement window manager:
  - Open/close windows via left nav
  - Floating windows
  - Dock bottom (Console) and right (future Logs)
- Implement Command Console window:
  - Command input + scrollback output
  - Wire up minimal internal commands (e.g., help, version)
- Implement basic theme switching between **Dark** and one additional theme (e.g., Day) via Settings

**Exit criteria:**  
- You can open/close/dock the Console window and at least one other window stub.  
- Theme switching between Dark and Day works reliably.

---

### Phase 2 – OGW System Health & Auto Mode

- Implement OGW metrics sampling for:
  - Local CPU, RAM, disk
  - RabbitMQ queue depth
  - Agent heartbeats (if available)
- Implement short-TTL caches per §5.2
- Expose OGW `/system/health` and `/system/summary`
- Implement System Health HUD in SOC
- Implement Display Mode **Auto** as default
  - Time-of-day mapping to Dawn/Day/Dusk/Dark

**Exit criteria:**  
- Health HUD reflects real metrics via OGW.  
- Auto mode selects appropriate theme by local time.  

---

### Phase 3 – Agent Inspector

- OGW aggregates agent status (from agent_info, heartbeats, etc.)
- OGW exposes `/agents/status` endpoint
- SOC implements **Agent Inspector** window:
  - List with online/offline status
  - Detail view showing role, capabilities, skills, build_hash, etc.

**Exit criteria:**  
- You can see all agents and their key metadata in the SOC Agent Inspector.  

---

### Phase 4 – Cycle Explorer

- OGW aggregates cycle summaries (from CycleDataStore)
- OGW exposes `/cycles/summary`
- SOC implements **Cycle Explorer** window:
  - List cycles with status
  - Detail view per cycle with summary info and artifact references

**Exit criteria:**  
- You can browse recent execution cycles and their basic details through SOC.  

---

### Phase 5 – Logs & Alerts

- Implement log aggregation and/or streaming adapter (through OGW or a direct Logs service)
- Implement alert debouncing and TTL to avoid flooding the UI
- Expose relevant endpoints and `WS /ws/metrics` extensions for logs/alerts
- SOC implements:
  - Logs window (right dock)
  - Alerts center overlay or docked panel

**Exit criteria:**  
- Operators can monitor streaming logs and alerts, filter them, and drill down to details.  

---

### Phase 6 – Auth Hardening & RBAC

- Fully integrate Keycloak-based OIDC into SOC and OGW
- Enforce role-based access per §8.3 at the backend level
- SOC surfaces authorization failures gracefully (e.g., read-only views for viewer role)

**Exit criteria:**  
- Roles meaningfully restrict which data/actions are visible within SOC.  

---

### Phase 7 – Mobile Compatibility

- Ensure SOC Backend API contracts are stable and documented
- Confirm that all mobile-useful flows (health, agents, cycles, alerts) are exposed via:
  - Token-authenticated JSON APIs
  - Optional simplified endpoints for mobile usage

**Exit criteria:**  
- A mobile client could be implemented without needing to change SOC backend APIs.  

---

### Phase 8 – Theming Polish & Enterprise Theme

- Refine Dawn, Day, Dusk, and Dark themes using style guide tokens  
- Ensure accessibility and legibility in each mode  
- Implement `enterprise` theme:
  - Add theme token set
  - Wire up command handling in the Command Console for `make it so`
  - Implement the override logic described in §7

**Exit criteria:**  
- Theme engine supports all planned modes.  
- Typing `make it so` in the console activates the enterprise theme and logs the appropriate response.  

---

## 12. Risks & Considerations

- **Window Manager Complexity** – Over-engineering tiling behaviors could slow delivery. Keep V1 simple and pragmatic.
- **OGW Load** – Misconfigured sampling intervals or missing caches could overload backends.
- **Theme Engine Sprawl** – Too many theme-specific hacks could make maintenance difficult; keep themes mostly token-driven.
- **Auth Configuration Drift** – Multiple services using Keycloak must be consistently configured.

Mitigation: keep phases small, with clear acceptance criteria, and document assumptions alongside implementation.

---

## 13. Acceptance Criteria Summary

This SIP is considered successfully implemented when:

- SOC provides a **usable web-OS interface** with window manager behavior.  
- OGW supplies **cached system health, agent status, and cycle summaries** and prevents direct heavy polling of core systems.  
- SOC supports **multiple themes** with Display Modes and defaults to **Auto**.  
- The **enterprise** theme is implemented and can be activated only by entering `make it so` in the Console.  
- Auth is integrated, and roles (`viewer`, `operator`, `maintainer`, `admin`, `mobile_ops`) are meaningfully enforced.  
- APIs are stable and documented enough for a **future mobile SOC client**.  

---

**End of SIP-SOC-WebOS**

