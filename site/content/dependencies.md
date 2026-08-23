# Dependencies

What each library is responsible for, and why it was chosen. Squad Ops keeps its
dependency surface deliberately small — the hexagonal structure means most
libraries sit behind a port and are replaceable without touching the domain.

## Runtime

| Responsibility | Library | Notes |
|---|---|---|
| HTTP API | **FastAPI** + **uvicorn** | The runtime API — cycles, runs, gates, artifacts |
| Data modelling | **Pydantic** | API DTOs and config schema. The *domain* uses frozen dataclasses, not Pydantic — validation belongs at the boundary |
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
| Integration fixtures | **testcontainers** — real Postgres and RabbitMQ, not mocks |
| Types | **mypy** |
| Docs site | **mkdocs-material** (build-time only, not a runtime dependency) |

## Where dependencies are declared

This is worth knowing, because it is not where you would expect.

`pyproject.toml` declares almost nothing — only optional extras. The install
sets live in `requirements/`, one pair per deployment surface:

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

## What is deliberately absent

- **No ORM.** The cycle registry owns a small explicit schema; migrations are plain SQL.
- **No agent framework.** No LangChain, LlamaIndex, or CrewAI. The orchestration *is* the product, so wrapping someone else's abstraction over it would put the interesting decisions inside a dependency.
- **No hosted inference SDK.** Local models are a requirement, not a default.
