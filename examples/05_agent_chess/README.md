# Agent Chess: Squad Consensus Benchmark

A multi-round chess experiment where the agent squad plays against
Stockfish, inventing its own consensus method for move selection.

## Prerequisites

- Stockfish installed and on PATH (or set `STOCKFISH_PATH`)
- `python-chess` (`pip install python-chess`)

## Quick Start

```bash
# Authenticate
squadops login -u squadops-admin

# Create a cycle
squadops cycles create agent_chess \
  --request-profile examples/05_agent_chess/pcr.yaml

# Monitor via Prefect UI at http://localhost:4200
```

## What to Observe

This is a coordination benchmark, not a chess strength test. Watch for:

- **Planning phase** — does the squad declare a concrete consensus
  method, or stay vague?
- **Move selection** — are moves chosen through a visible process, or
  does one agent dominate?
- **Time management** — does the squad spend time proportional to
  position complexity?
- **Adaptation** — does Round 2's method differ from Round 1 based on
  evidence?

## Success Tiers

| Tier | What it means |
|------|---------------|
| 1 | Completes legal games within the time budget |
| 2 | Shows coherent strategy (not random moves) |
| 3 | Repeatable performance across both rounds |
| 4 | Adapts consensus method between rounds |

## Files

| File | Purpose |
|------|---------|
| `prd.md` | What the squad builds + experiment protocol |
| `pcr.yaml` | Cycle request profile (2-round workload sequence) |
