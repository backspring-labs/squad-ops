# Dependencies

What each library is responsible for. Most sit behind a port, so replacing one
is a factory change.

## Runtime

| Responsibility | Library | Notes |
|---|---|---|
| HTTP API | **FastAPI** + **uvicorn** | The runtime API — cycles, runs, gates, artifacts |
| Data modelling | **Pydantic** | API DTOs and config schema. Validation runs at the boundary; the domain uses frozen dataclasses |
| Database | **asyncpg** | Direct async Postgres. No ORM: the cycle registry writes a small, hand-controlled set of queries and an ORM would add a translation layer over a schema that is already explicit |
| Message queue | **aio-pika** | RabbitMQ client for task dispatch, behind `QueuePort` |
| Cache | **redis** | Caching and coordination |
| Config | **pydantic-settings** + **python-dotenv** + **PyYAML** | `SQUADOPS__*` env vars, profile YAML |
| Workflow visibility | **Prefect** | Flow runs and task graphs. Orchestration decisions stay in the executor — Prefect is the view |
| Identity | **Keycloak** (service) + **PyJWT** | OIDC, JWT validation, scopes |
| Semantic memory | **LanceDB** + **sentence-transformers** | Embedded vector store; local embeddings, no hosted API |
| Inference | **Ollama** / **vLLM** | Both behind `LLMPort`, selected by configuration |
| LLM observability | **LangFuse** | Behind `LLMObservabilityPort`, alongside OpenTelemetry and a NoOp |
| Tracing / metrics | **OpenTelemetry** | Collector transport for traces and metrics |
| CLI | **Typer** + **Rich** + **httpx** | Command surface and API client |
| Validation | **jsonschema** | Contract and manifest gates |
| State machines | **transitions** | Agent lifecycle |

## Development

| Responsibility | Library |
|---|---|
| Lint and format | **ruff** — one tool, replacing flake8/isort/black |
| Tests | **pytest** with `pytest-asyncio`, `pytest-xdist`, `pytest-cov` |
| Integration fixtures | **testcontainers** — runs the tests against real Postgres and RabbitMQ |
| Types | **mypy** |
| Docs site | **mkdocs-material** — build-time only, installed from `site/requirements.txt` |

## Where dependencies are declared

`pyproject.toml` declares optional extras only. The install sets live in
`requirements/`, one pair per deployment surface:

| Pair | Installed by |
|---|---|
| `requirements/base.{txt,lock}` | shared foundation |
| `requirements/api.{txt,lock}` | the runtime-API and sandbox images |
| `requirements/agent.{txt,lock}` | agent images |
| `tests/requirements.txt` + `ci-constraints.txt` | CI and local development |
| `site/requirements.txt` | this documentation site |

Each surface has a `.txt` of ranges and a `.lock` of exact pins; Dockerfiles
install from the `.lock`. CI installs `tests/requirements.txt` *constrained by*
`ci-constraints.txt`, so an upstream release cannot silently change what CI
tested.

Agent images install per surface, so a role that does not need the memory stack
does not carry LanceDB, PyArrow and pandas — the difference between a small
agent image and a very large one.

!!! warning "Known gap: CI does not test the deployed version set"

    The lock files and `ci-constraints.txt` are resolved independently, and they
    have diverged: **28 of 46 shared packages differ between `api.lock` and CI,
    36 of 53 for `agent.lock`, and 9 of 19 for `base.lock`** — including
    `cryptography` 46 vs 49 and `aio-pika` 9.3.1 vs 9.6.2.

    The same framework code runs in both, so a green regression suite does not
    establish that the deployed images work. Nothing has broken because of it
    yet, which is precisely why it is worth writing down.

## Excluded by design

- **ORM.** The cycle registry owns an explicit schema; migrations are plain SQL.
- **Agent frameworks** (LangChain, LlamaIndex, CrewAI). Orchestration is the subject of the project, so it is implemented directly.
- **Hosted inference SDKs.** Inference is local.
