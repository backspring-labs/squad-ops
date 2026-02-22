# PRD: Build Crysis (Tabletop Tactics) — Browser Benchmark App

**Document Type:** Embedded PRD (for Benchmark Cycle)  
**Status:** Draft  
**Owner:** SquadOps  
**Primary Goal:** Provide a small, deterministic, browser-playable, single‑page app to benchmark agent planning/build/test quality and measure model tradeoffs via the Agent Scoring Protocol.

---

## 1. Problem Statement

We need a lightweight application that is:
- **Actually playable** (not a mock UI)
- **Deterministic and testable** (seeded runs, replayable)
- **Simple enough to build in a single cycle**
- **Rich enough to exercise** planning, development, QA, and scoring instrumentation

The application must run as a **Single Page Application (SPA)** in a browser, backed by a Python server that enforces game rules.

---

## 2. Target Users

- **Primary:** SquadOps maintainers and contributors running benchmark cycles locally
- **Secondary:** Anyone evaluating model sizes (e.g., 3B vs 70B) using repeatable runs

---

## 3. Success Criteria

### 3.1 Functional Success
- A user can start a new game, take turns, and win/lose in the browser
- Game rules are enforced server-side (no client authority)
- Enemy behavior is automated and consistent

### 3.2 Benchmark Success
- Deterministic runs via **seed**
- Exportable run summary (turns, win/loss, energy curve)
- Hooks for Agent Scoring Protocol artifacts

---

## 4. Scope

### 4.1 In Scope (MVP)
- 6×6 grid board
- Solo player vs computer-controlled enemies
- Nanosuit modes (Cloak/Armor/Strength/Speed)
- Energy + health systems
- Turn-based loop with clear phases
- One scenario: **Reach Extraction**
- SPA UI with controls and visual grid
- Server APIs for game actions
- Unit tests for rules engine and key invariants
- Seeded RNG + replay payload export

### 4.2 Explicitly Out of Scope (MVP)
- Graphics/animation beyond simple token rendering
- Real-time combat
- Weapon variety, inventory, crafting, physics
- Multi-player
- Persistent accounts / auth
- Full telemetry dashboards (basic JSON export only)

---

## 5. Gameplay Requirements (MVP)

### 5.1 Board
- Canonical board size: **6×6**
- Start: player at (0,0)
- Extraction: at (5,5)
- Enemies: default 3, placed by seed; cannot spawn adjacent to player

### 5.2 Turn Structure (Deterministic)
Each turn MUST execute in this order:
1. **Mode Selection**
2. **Player Action** (exactly one)
3. **Enemy Phase**
4. **Regen/Cleanup** (energy regen, status resets)

### 5.3 Player Resources
- **Energy:** integer, range 0–10, starts at 10
- **Health:** integer, range 0–5, starts at 5

Energy regen:
- +1 energy at end of turn (max 10)

Energy depletion behavior:
- If energy == 0: Cloak forced OFF; Strength and Speed actions disabled until energy > 0

### 5.4 Nanosuit Modes (Exclusive)
Player must have exactly one active mode per turn.

**Cloak**
- Passive: player is not targetable unless adjacent (distance 1)
- Cost: -1 energy per turn while active
- Attacking while cloaked breaks cloak immediately before resolution

**Armor**
- Passive: incoming damage reduced by 1 (min 0)
- Constraint: max move distance = 1

**Strength**
- Effect: +2 damage on attack OR a special “burst” action (configurable)
- Cost: -2 energy per Strength attack/burst

**Speed**
- Effect: max move distance = 3
- Cost: -1 energy per extra tile beyond 1 moved that turn (e.g., moving 3 costs 2)

### 5.5 Player Actions (one per turn)
- **Move** (orthogonal only; distance depends on mode)
- **Attack** (adjacent enemy only)
- **Wait** (no movement; +1 energy immediate, still capped by 10, then end-of-turn regen applies)
- **Extract** (only at extraction tile; completes win condition after full turn)

### 5.6 Combat
- Player attack hit chance: d6 roll 4–6 hits (or deterministic mode via config)
- Base player damage: 1
- Strength adds +2 damage (total 3)
- Enemy health: 2 (default)

Enemy attack:
- If adjacent and alerted: deal 1 damage (Armor reduces by 1)

### 5.7 Enemy Behavior
Enemies have states:
- **Patrol** (default)
- **Alerted**

Detection:
- If player is visible (not cloaked) and within Manhattan distance ≤ 2 → enemy becomes Alerted

Enemy phase per enemy:
- If Alerted:
  - Move 1 toward player (reduce Manhattan distance)
  - If adjacent after move → attack
- If not Alerted:
  - Roll d6 (seeded):
    - 1–3: move randomly 1 tile (valid orthogonal)
    - 4–5: hold
    - 6: raise alert (global): all enemies gain +1 move next turn (one-turn buff)

### 5.8 Win/Loss
Win:
- Player uses **Extract** at extraction tile and survives enemy phase that turn

Loss:
- Health <= 0
- Turn count exceeds limit (default 15)

---

## 6. SPA Requirements

### 6.1 UI Screens
- **Game Screen (single route):**
  - Grid view (6×6) with player/enemy/extraction markers
  - Current turn number
  - Current mode and mode selector
  - Energy + health meters
  - Action controls: Move (click tile), Attack, Wait, Extract
  - Event log panel (last N events)
  - Win/Loss banner + “New Game”

### 6.2 Interaction Rules
- Client MUST NOT modify authoritative state
- Client sends intent (mode/action) to server and re-renders server state
- All illegal actions must return user-friendly error messages

### 6.3 Accessibility & UX
- Playable with mouse and keyboard
- Clear highlighting for:
  - reachable move tiles
  - adjacent attack targets
  - extraction tile

---

## 7. Telemetry & Benchmark Outputs (MVP)

### 7.1 Run Summary Export
Server must provide a JSON export for a completed run:
- seed, board size, enemy count
- turns taken
- win/loss + reason
- per-turn energy, health, mode, action
- enemy alerts triggered count

### 7.2 Scorecard Hook Points
Emit artifacts compatible with Agent Scoring Protocol (paths configurable):
- `artifacts/game/run_summary.json`
- `artifacts/game/replay.json` (optional: full state per turn)

---

## 8. Non-Functional Requirements

- **Determinism:** Given the same seed, outcomes must match
- **Performance:** Turns resolve < 150ms locally (typical laptop)
- **Testability:** Rules engine must be unit-testable without web server
- **Portability:** `make run` / `docker compose up` runs locally

---

## 9. Technical Architecture

### 9.1 Backend (Authoritative Rules Engine)
- Python service enforces:
  - legal moves
  - mode effects
  - enemy AI
  - RNG seeding
- Stores per-game state in memory (MVP) keyed by `game_id`
- Optional: SQLite for persisted replays (future)

### 9.2 Frontend (SPA)
- SPA renders state, sends commands to backend
- No business logic beyond UI affordances (tile highlights)

---

## 10. Proposed Tech Stack

### Backend
- **Python 3.11+**
- **FastAPI** (REST APIs)
- **Pydantic** models for state/commands
- **Uvicorn** for local dev
- **Pytest** for tests

### Frontend
- **React + Vite** (SPA)
- **TypeScript** (preferred) or JS (acceptable for MVP)
- Minimal UI framework (optional): none / lightweight CSS only

### DevOps (Local)
- `Makefile` targets: `install`, `run`, `test`, `lint`
- Optional Docker:
  - `Dockerfile` (backend)
  - `docker-compose.yml` (backend + nginx static hosting) — optional for MVP

---

## 11. Integration Interface Requirements (PRD-Level)

The application MUST expose a backend interface that supports the SPA gameplay loop. 
This PRD intentionally avoids prescribing endpoint shapes or payload schemas; those are defined by the Build Agent in the implementation spec.

Required interface capabilities:
- Start a new game with optional **seed**, **board size**, and **enemy count** inputs
- Fetch the current authoritative game state for rendering
- Submit **mode selection** and exactly one **player action** per turn
- Receive the updated authoritative state after each submission (including enemy phase + regen outcomes)
- Export a completed-run JSON summary suitable for scoring and replay analysis

Constraints:
- The backend MUST remain authoritative; the client MUST NOT be able to mutate state outside allowed actions
- The interface MUST return clear, user-friendly errors for illegal actions (e.g., invalid move, insufficient energy)
- Determinism: given identical seed and action sequence, the resulting state trajectory MUST match
## 12. Acceptance Criteria (MVP)

- SPA loads and displays a new game within 2 seconds locally
- Player can complete a full run to win and to lose
- All rules are enforced server-side (client cannot cheat)
- Unit tests cover:
  - energy/mode interactions
  - enemy detection/alert transitions
  - deterministic RNG with seed
  - win/loss conditions
- Export endpoint returns a valid JSON run summary

---

## 13. Milestones (Single Cycle Friendly)

1. **Rules engine + tests**
2. **FastAPI endpoints**
3. **SPA UI + wiring**
4. **Run export + scoring hook artifacts**
5. **Polish + docs** (readme + how to run)

