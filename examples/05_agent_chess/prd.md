# Agent Chess: Squad Consensus Benchmark

## Overview

Build a chess harness that lets the agent squad play chess against
Stockfish, then use it to run a multi-round consensus benchmark.

The goal is not to beat Stockfish. The goal is to observe whether the
squad can invent a workable consensus method for move selection, execute
it under time pressure, and improve it between rounds.

---

## Part 1: Chess Harness Requirements

### What the Squad Builds

A Python package that provides:

1. **Engine wrapper** — interface to Stockfish via the `python-chess`
   library. Must support:
   - Starting a new game (squad plays White)
   - Getting the top N candidate moves from Stockfish (without scores)
   - Submitting a move and getting Stockfish's response
   - Detecting game-over conditions (checkmate, stalemate, draw)

2. **Board management** — track game state using `python-chess.Board`.
   Print the board after each move pair.

3. **Evidence capture** — after each game, write a structured evidence
   file (JSON or YAML) containing:
   - Declared consensus method (from planning phase)
   - Each move: candidates considered, final selection, short rationale
   - Timeout or fallback events
   - Override and disagreement counts
   - Per-move decision time
   - Game outcome (win/loss/draw, reason, move count)

4. **File structure**:
   ```
   agent_chess/
   ├── engine.py          # Stockfish wrapper
   ├── board.py           # Board state management
   ├── evidence.py        # Evidence capture and serialization
   ├── main.py            # Entry point — runs one game
   └── tests/
       ├── test_engine.py
       ├── test_board.py
       └── test_evidence.py
   ```

### Technical Constraints

- Python 3.11+
- Dependencies: `python-chess` (required), `stockfish` path from
  environment variable `STOCKFISH_PATH` (default: `stockfish`)
- No web framework needed — this is a CLI tool
- Tests must pass without Stockfish installed (mock the engine interface)

---

## Part 2: Experiment Protocol

### Round Structure

Each round consists of:

1. **Planning** — the squad declares its consensus method before play.
   This includes: how candidates are evaluated, how disagreements are
   resolved, who has authority, and how deliberation is bounded.
   The method is declared by the squad, not prescribed by this PRD.

2. **Play** — the squad plays one complete game against Stockfish at the
   configured skill level. The squad receives the top N candidate moves
   (without engine scores) and must select one per turn.

3. **Wrapup** — the squad reviews the game evidence and answers
   reflection questions.

### What the Squad Decides

The following are explicitly NOT prescribed. The squad must invent its
own approach:

- **Consensus method** — voting, lead-agent override, rotating
  authority, critic/champion, confidence-weighted selection, or
  something else entirely
- **Reasoning styles** — each agent differentiates organically; do not
  assign reasoning personas
- **Time allocation** — the squad manages its own per-move timing
  within the overall budget
- **Candidate evaluation** — how deeply to analyze each candidate move

### What the System Provides

- Game rules (via python-chess)
- Win/loss/draw conditions
- Top N candidate moves per turn (without scores)
- Overall time budget
- Evidence capture requirements (see Part 1)

### Success Tiers

| Tier | Criterion |
|------|-----------|
| 1 | Squad completes legal games within the time budget |
| 2 | Squad shows coherent strategic behavior (not random move selection) |
| 3 | Squad produces repeatable performance across both rounds |
| 4 | Squad adapts its consensus method between rounds based on evidence |

### Wrapup Reflection Questions

After each round, the squad should address:

1. Where did the consensus method work well?
2. Where did it stall or waste time?
3. Were there moves where the squad disagreed significantly? What
   happened?
4. Was authority too centralized or too diffuse?
5. What specific changes would improve the method in the next round?

These are Socratic prompts — the squad answers in its own terms, not
with a prescribed template.

---

## Out of Scope

- Playing as Black (squad always plays White)
- ELO calculation or rating estimation
- Head-to-head squad-vs-squad play (future experiment)
- Real-time UI or web interface
- Opening book or endgame tablebase integration
