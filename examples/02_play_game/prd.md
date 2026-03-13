# Play Game: Terminal Tic-Tac-Toe

**Project:** play_game
**Version:** 0.1.0
**Status:** Draft

---

## Overview

A terminal-based Tic-Tac-Toe game where a human player faces an AI opponent. The game runs entirely in the terminal with no external dependencies beyond the Python standard library.

This project serves as the canonical SquadOps sample application and platform selftest. If the agents can build a working game from this PRD, the platform is healthy.

---

## Game Requirements

### Board

- Standard 3x3 grid
- Numbered positions 1-9 for player input (top-left = 1, bottom-right = 9)
- Clear terminal rendering after each move showing current board state
- Display column/row reference for orientation

### Players

- **Human** plays as X (always moves first)
- **AI** plays as O
- Player selects position by entering a number 1-9

### AI Opponent

Three difficulty levels selectable at game start:

| Level | Behavior |
|-------|----------|
| Easy | Random valid moves |
| Medium | Blocks opponent wins, otherwise random |
| Hard | Minimax algorithm (unbeatable) |

### Win Detection

- Three in a row horizontally, vertically, or diagonally
- Detect draw when all 9 positions are filled with no winner
- Announce result clearly: "X wins!", "O wins!", or "Draw!"

### Game Loop

1. Display welcome message and difficulty selection
2. Show empty board
3. Alternate turns: human input -> AI move -> render board
4. Detect win/draw after each move
5. On game end, offer to play again

### Input Handling

- Accept numeric input 1-9 only
- Reject already-occupied positions with a clear message
- Handle non-numeric input gracefully (re-prompt, don't crash)

---

## Technical Constraints

- **Language:** Python 3.11+
- **Dependencies:** Standard library only (no pip packages)
- **Entry point:** `python -m play_game` or `python play_game/main.py`
- **Structure:** Separate modules for board, AI logic, game loop, and entry point
- **No global mutable state** — pass game state explicitly

---

## File Structure

```
play_game/
    __init__.py
    __main__.py       # Entry point
    board.py          # Board representation, rendering, win detection
    ai.py             # AI opponent (easy/medium/hard)
    game.py           # Game loop, input handling, turn management
```

---

## Acceptance Criteria

1. Game launches and displays difficulty selection prompt
2. Human can play a full game against each difficulty level
3. Easy AI makes only valid (but random) moves
4. Medium AI blocks an immediate opponent win when possible
5. Hard AI never loses (minimax is optimal for Tic-Tac-Toe)
6. Invalid input (non-numeric, out of range, occupied cell) is handled without crashing
7. Game correctly detects all 8 win conditions (3 rows, 3 columns, 2 diagonals)
8. Game correctly detects a draw
9. Play-again prompt works (y/n)
10. All modules have corresponding unit tests with >= 90% coverage

---

## Cycle 2 Scope (Future Iteration)

After the baseline is established from Cycle 1:

- Add a `--difficulty` CLI flag to skip the interactive prompt
- Add move history display (move log)
- Add game statistics tracking across sessions (wins/losses/draws per difficulty)

This scope is intentionally deferred to validate the platform's iteration-against-baseline capability.
