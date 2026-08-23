# Getting started

## Requirements

- **Python 3.11+** — production runs 3.11; develop on 3.12 to match CI
- **Docker** and **Docker Compose**
- **[Ollama](https://ollama.com)** for local inference

## Install

```bash
git clone https://github.com/backspring-labs/squad-ops.git
cd squad-ops

python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Bootstrap

One command provisions the environment for a named profile — packages, models,
services, and configuration:

```bash
./scripts/bootstrap/bootstrap.sh dev-mac      # or dev-pc, local-spark
docker-compose up -d
```

Then validate the environment against the profile's contract:

```bash
squadops doctor dev-mac
```

`doctor` reports what is missing rather than failing later and further away. Run
it with `--json` for machine-readable output.

## Run a cycle

```bash
squadops login

squadops cycles create play_game --squad-profile lite --request-profile selftest
squadops cycles show play_game <cycle-id>
```

Approve a gate when one is waiting, then assemble the result into a runnable
project:

```bash
squadops runs gate play_game <cycle-id> <run-id> progress_plan_review --approve
squadops runs assemble play_game <cycle-id> <run-id> --out ./output
```

!!! tip "Which profile?"

    Use `lite` for a real end-to-end run on a laptop. `smoke` only checks that
    the plumbing is alive. `full` pins a 27B model and expects a Spark-class
    machine.

## Watch it work

| Surface | URL |
|---|---|
| Prefect — task orchestration | `http://localhost:4200` |
| LangFuse — LLM traces | `http://localhost:3001` |
| Runtime API | `http://localhost:8001` |
| Grafana | `http://localhost:3000` |

## Worked examples

Each ships with a requirement document and a request profile:

`hello_squad` · `play_game` · `group_run` · `run_crysis` · `agent_chess`
