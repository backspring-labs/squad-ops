# SquadOps Examples

Examples are ordered by progressive complexity.

| # | Example | What it tests |
|---|---------|---------------|
| 01 | `hello_squad` | Single-agent greeting — simplest possible cycle |
| 02 | `play_game` | Terminal Tic-Tac-Toe — full 5-agent sequential build with quality gate |
| 03 | `group_run` | Parallel execution — full squad runs concurrently |
| 04 | `run_crysis` | Browser game (FastAPI + React) — complex multi-stack build |
| 05 | `agent_chess` | Consensus benchmark — squad plays chess against Stockfish |

## How to Run an Example

```bash
# 1. Start services
docker-compose up -d

# 2. Authenticate
squadops login -u squadops-admin

# 3. Create a cycle (replace <name> and <number>)
squadops cycles create <project_name> \
  --request-profile examples/<number>_<name>/pcr.yaml

# 4. Monitor progress in Prefect UI
open http://localhost:4200
```

Each example directory contains:

- **`prd.md`** — product requirements the agents build against
- **`pcr.yaml`** — cycle request profile defining the execution plan
- **`README.md`** (where present) — example-specific instructions
