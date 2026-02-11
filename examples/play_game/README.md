# Play Game: SquadOps Sample Project

> "Shall we play a game?"

Terminal Tic-Tac-Toe built by the SquadOps agent squad. This is the
canonical sample application and platform selftest.

## Quick Start

```bash
# Authenticate
squadops login -u squadops-admin

# Submit the PRD as an artifact
squadops artifacts ingest examples/play_game/prd.md \
  --project play_game \
  --type documentation \
  --media-type text/markdown

# Create a cycle using the sample PCR profile
squadops cycles create play_game \
  --profile examples/play_game/pcr.yaml

# Watch it run
squadops runs status play_game <cycle_id> --follow

# Review and approve the quality gate
squadops cycles gate <cycle_id> quality-review --approve

# Download the built game
squadops artifacts download <artifact_id> -o ./play_game_output/

# Play!
python ./play_game_output/play_game/main.py
```

## Files

| File | Purpose |
|------|---------|
| `prd.md` | Product requirements — what the agents build against |
| `pcr.yaml` | Cycle request profile — how the cycle executes |

## What This Tests

- Full authentication flow (login + token caching)
- Project and cycle creation via CLI
- Artifact ingestion (PRD as input)
- 5-agent sequential execution (Nat → Neo → Eve → Data → Max)
- Quality gate decision (approve/reject)
- Artifact retrieval (built code output)
- End-to-end: PRD in, playable game out
