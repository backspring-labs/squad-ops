# Build Crysis: Tabletop Tactics — Browser Benchmark App

**Project:** run_crysis
**Version:** 0.1.0
**Status:** Draft

---

## Overview

A browser-playable, turn-based tactical game inspired by Crysis Nanosuit mechanics. A solo player navigates a 6x6 grid, switching between Cloak/Armor/Strength/Speed modes to evade or engage enemies and reach an extraction point. The game runs as a single-page application backed by a Python rules engine that enforces all game logic server-side.

This project serves as the SquadOps benchmark application for measuring agent planning, build, and test quality across different model configurations.

---

## Game Requirements

### Board

- 6x6 grid
- Player starts at (0,0), extraction at (5,5)
- 3 enemies placed by seed (cannot spawn adjacent to player)

### Turn Structure

Each turn executes in order:
1. Mode Selection
2. Player Action (exactly one)
3. Enemy Phase
4. Regen/Cleanup (energy regen, status resets)

### Player Resources

- **Energy:** integer, 0-10, starts at 10, +1 regen per turn (cap 10)
- **Health:** integer, 0-5, starts at 5

Energy depletion: Cloak forced OFF, Strength/Speed disabled until energy > 0.

### Nanosuit Modes (Exclusive)

| Mode | Effect | Cost |
|------|--------|------|
| Cloak | Not targetable unless adjacent | -1 energy/turn; attacking breaks cloak |
| Armor | Incoming damage -1 (min 0); max move = 1 | None |
| Strength | +2 damage on attack | -2 energy per attack |
| Speed | Max move distance = 3 | -1 energy per extra tile beyond 1 |

### Player Actions (one per turn)

- **Move** — orthogonal only, distance depends on mode
- **Attack** — adjacent enemy only; d6 roll 4-6 hits, base 1 damage (+2 Strength)
- **Wait** — no movement, +1 energy immediate (then end-of-turn regen)
- **Extract** — only at extraction tile, completes win condition after full turn

### Enemy Behavior

States: Patrol (default), Alerted.

Detection: player visible (not cloaked) within Manhattan distance 2 triggers Alert.

- **Alerted:** move 1 toward player, attack if adjacent
- **Patrol:** d6 roll (1-3: random move, 4-5: hold, 6: global alert buff)

Enemy health: 2. Enemy attack damage: 1 (Armor reduces by 1).

### Win/Loss

- **Win:** Extract at extraction tile and survive that turn's enemy phase
- **Loss:** Health <= 0 or turn count exceeds 15

---

## Technical Constraints

- **Backend:** Python 3.11+, FastAPI, Pydantic models, seeded RNG
- **Frontend:** React + Vite SPA (TypeScript preferred)
- **Dependencies:** FastAPI, uvicorn, pytest (backend); React, Vite (frontend)
- **Determinism:** Same seed + same actions = same outcome
- **Authority:** Server-side only; client renders state and sends intents

---

## File Structure

```
run_crysis/
    backend/
        __init__.py
        main.py           # FastAPI app, game endpoints
        models.py          # Pydantic game state, commands
        engine.py          # Rules engine, mode effects, combat
        enemy_ai.py        # Enemy detection, patrol, alert behavior
        export.py          # Run summary / replay JSON export
    frontend/
        src/
            App.tsx        # Main game screen
            Grid.tsx       # 6x6 board rendering
            Controls.tsx   # Mode selector, action buttons
            EventLog.tsx   # Turn event log panel
    tests/
        test_engine.py     # Rules engine unit tests
        test_enemy_ai.py   # Enemy behavior tests
        test_determinism.py # Seeded replay tests
```

---

## Telemetry and Benchmark Outputs

Server provides JSON export for completed runs:
- Seed, board size, enemy count
- Turns taken, win/loss + reason
- Per-turn energy, health, mode, action
- Enemy alerts triggered count

Artifact paths: `artifacts/game/run_summary.json`, `artifacts/game/replay.json`

---

## Acceptance Criteria

1. SPA loads and displays a new game within 2 seconds locally
2. Player can complete a full run to win and to lose
3. All rules are enforced server-side (client cannot cheat)
4. Nanosuit modes work correctly (energy costs, movement limits, damage modifiers)
5. Enemy detection, alert transitions, and patrol behavior are correct
6. Deterministic replay: same seed + actions = identical outcome
7. Unit tests cover energy/mode interactions, enemy AI, win/loss conditions, and seeded RNG
8. Export endpoint returns valid JSON run summary
