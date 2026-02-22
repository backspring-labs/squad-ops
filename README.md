# SquadOps – Agent Squad Framework

## Overview
**SquadOps** is an AI agent collaboration framework for software development. The system implements a role-based agent architecture where specialized agents handle different aspects of development tasks, from requirements analysis to application deployment.

**Current Status**: Production-ready framework (v0.9.10) with hexagonal architecture, distributed cycle execution pipeline, agent build capabilities, Postgres-backed persistence, LangFuse observability, Keycloak authentication, CLI tooling, and 1,830+ passing tests.

---

## Mission
- **Learn**
- **Build**
- **Experiment**

*repeat.*

---

## Core Components

### Architecture
- **Hexagonal Architecture** – Ports & adapters pattern with clean domain/infrastructure separation
- **Dependency Injection** – Constructor-injected dependencies for testability
- **Unified Agent Build** – Single multi-stage Dockerfile for all agent roles
- **Distributed Execution** – RabbitMQ-based task dispatch across 5 agent containers

### Agent Framework
- **Agent Squad** – 5 agents: Max (Lead), Neo (Dev), Nat (Strategy), Eve (QA), Data (Analytics)
- **BaseAgent** – DI-enabled base class with SecretManager, DbRuntime, and port injection
- **Capability Contracts** – Declarative delivery expectations with acceptance checks (SIP-0058)

### Cycle Execution Pipeline (SIP-0064/0066/0068)
- **Cycle API** – Create, monitor, and manage execution cycles via REST API
- **Task Planning** – Automatic task plan generation from PRD references
- **Distributed Flow Executor** – Sequential task dispatch to agent containers via RabbitMQ
- **Gate Decisions** – Human-in-the-loop approval gates between pipeline stages
- **Artifact Management** – Typed artifact ingestion and retrieval per run
- **Build Capabilities** – Agents produce executable source code, tests, and config from plans (SIP-0068)
- **Pulse Verification** – Cadence-bounded checks at pipeline boundaries with bounded repair loops (SIP-0070)
- **Assembly** – CLI command to assemble build artifacts into a runnable project directory

### Infrastructure Adapters
- **Secrets** – Pluggable providers (env, file, docker_secret) with `secret://` URI resolution
- **Persistence** – PostgresRuntime with connection pooling, SSL, and health checks
- **Cycle Registry** – Postgres-backed durable cycle/run/gate storage (SIP-0067)
- **Comms** – RabbitMQ adapter for inter-agent messaging
- **Telemetry** – OpenTelemetry + LangFuse LLM observability (SIP-0061)
- **Auth** – Keycloak OIDC with JWT validation and audit logging (SIP-0062)

### Services
- **Runtime API** – FastAPI service with cycle execution, auth middleware, and Postgres migrations (SIP-0048)
- **CLI** – Typer-based CLI for cycle management (`squadops cycles create/show/list/gate`) (SIP-0065)
- **PostgreSQL** – Cycle registry, task logging, and state persistence
- **Redis** – Caching and performance optimization
- **RabbitMQ** – Inter-agent message queue
- **Keycloak** – OIDC identity provider with realm auto-provisioning
- **LangFuse** – LLM observability with cross-process trace linking
- **Prefect** – Workflow orchestration and DAG visibility
- **Ollama** – Local LLM inference (runs natively)
- **Console** – Control-plane UI with Continuum plugin shell (SIP-0069)
- **Caddy** – Reverse proxy for console and API
- **Docker Compose** – 17-service development environment

---

## Documentation
Comprehensive documentation and protocols are available in `/docs/`:

- **SIPs (SquadOps Improvement Proposals)** – 68 protocol specifications in `sips/` directory (44 implemented, 9 proposals, 15 deprecated)
- **IDEA Documents** – 25+ strategic ideas including Reasoning Telemetry Sharing, Squad Memory Pool, Observer Governance
- **Architecture Documents** – Design guides for agent implementations and handoff templates
- **Book Chapters** – 9 chapters covering methodology, implementation, and operations
- **Plans** – Implementation plans for major SIPs in `docs/plans/`
- **Retrospectives** – WarmBoot run analyses and lessons learned
- **Protocols** – Testing, data governance, communication patterns

**Total Documentation**: ~61,665 lines across 215+ markdown files

---

## Repo Structure
```
/src/squadops/        # Core framework (hexagonal architecture)
├── ports/            # Abstract interfaces (secrets, db, comms, cycles, auth, telemetry)
├── agents/           # BaseAgent with DI, entrypoint, role definitions
├── capabilities/     # Capability contracts & workload runner (SIP-0058)
│   └── handlers/     # Cycle task handlers (strategy, dev, QA, data, governance, build)
├── orchestration/    # AgentOrchestrator, HandlerExecutor
├── cycles/           # Cycle models, lifecycle state machine, task planning
├── auth/             # Auth models, JWT validation, middleware
├── cli/              # Typer CLI commands and CRP contract packs
├── api/              # FastAPI runtime API service (SIP-0048)
│   └── runtime/      # Routes, DTOs, DI wiring, migrations
├── telemetry/        # LLM observability models and NoOp adapter
├── memory/           # LanceDB semantic memory
├── llm/              # LLM router abstraction with dynamic provider registry
├── config/           # Configuration loading (SQUADOPS__* env vars)
├── tasks/            # TaskEnvelope, TaskResult models (A2A message format)
└── core/             # Core utilities (SecretManager)
/adapters/            # Concrete implementations
├── secrets/          # env, file, docker_secret providers
├── comms/            # RabbitMQ adapter
├── persistence/      # PostgreSQL runtime
├── cycles/           # DistributedFlowExecutor, MemoryCycleRegistry, PostgresCycleRegistry
├── telemetry/        # LangFuse adapter with buffering, flush, redaction
├── auth/             # Keycloak adapter, JWT middleware
├── capabilities/     # Filesystem repository, ACI executor
└── llm/              # Ollama adapter
/agents/              # Agent definitions and Dockerfile
├── Dockerfile        # Unified multi-stage agent build
└── instances/        # Agent instance configurations
/sips/                # SquadOps Improvement Proposals
├── proposals/        # Unnumbered drafts
├── accepted/         # Numbered, approved
├── implemented/      # Matched to code
└── registry.yaml     # Canonical index
/tests/               # Test suite (1,830+ tests)
├── unit/             # Unit tests (mocked deps)
├── integration/      # Integration tests (real services)
└── conftest.py       # Global fixtures
/docs/                # Documentation and protocols
/scripts/             # Development and maintainer scripts
/infra/               # Database migrations and DDL
docker-compose.yml    # 17-service development environment
```

---

## Reference Applications
- **play_game** – Tic-Tac-Toe game built end-to-end by the agent squad (plan + build + test)
- **hello_squad** – Minimal CLI greeting script (simplest build-capable example)
- **group_run** – Multi-module running activity logger (multi-file build example)

Each ships with a PRD (`examples/<project>/prd.md`) and a cycle request profile.

```bash
# Run a full plan-then-build cycle
squadops cycles create play_game --squad-profile full-squad --profile build
squadops cycles show play_game <cycle-id>
squadops runs gate play_game <cycle-id> <run-id> plan-review --approve
squadops runs assemble play_game <cycle-id> <run-id> --out ./output
```

---

## Getting Started

### Prerequisites

- **Python 3.11+** (required for local development and testing)
  - Recommended: Use [pyenv](https://github.com/pyenv/pyenv) for version management
- **Docker** and **Docker Compose** (required for running agents and services)
- **Ollama** (for local LLMs) - Required for agent task execution

### Quick Start

1. **Set up Python environment**:
   ```bash
   brew install pyenv
   pyenv install 3.11.14
   pyenv local 3.11.14
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   pip install -r tests/requirements.txt
   ```

2. **Start Infrastructure**: `docker-compose up -d`

3. **Login** (Keycloak auth required):
   ```bash
   squadops login
   ```

4. **Run a cycle**:
   ```bash
   squadops cycles create play_game --squad-profile full-squad --profile selftest
   squadops cycles show <cycle-id>
   ```

5. **Monitor**: Check LangFuse UI at `http://localhost:3001` and Prefect UI at `http://localhost:4200`

---

## Development Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full release timeline.

**Current**: v0.9.10 — Codebase audit cleanup, artifact updates

---

## Current Status
**Framework Version**: 0.9.10
**Development Status**: Production-ready multi-agent orchestration with console UI, distributed cycle execution, agent build capabilities, durable persistence, authentication, CLI tooling, and full observability stack. Recent 5-phase codebase audit removed legacy endpoints, dead tables, stale config, and orphaned wiring.

### Project Statistics
- **~38,000 lines** of Python source code
- **~31,000 lines** of test code
- **~62,000 lines** of documentation
- **1,830+ tests** passing in regression suite
- **68 SIPs** (44 implemented, 9 proposals, 15 deprecated)

### Functional Components
- 5 Agents: Max (Lead), Neo (Dev), Nat (Strategy), Eve (QA), Data (Analytics)
- Cycle Execution API with runs, gates, and artifact management (SIP-0064)
- Distributed flow execution via RabbitMQ (SIP-0066)
- Postgres-backed cycle registry with migrations (SIP-0067)
- LangFuse LLM observability with cross-process trace linking (SIP-0061)
- Keycloak OIDC authentication with JWT middleware and audit logging (SIP-0062)
- CLI for cycle management with CRP contract packs (SIP-0065)
- Capability contracts with declarative acceptance checks (SIP-0058)
- Task planning with automatic task flow generation (plan + build modes)
- Agent build capabilities: source code, tests, and config generation (SIP-0068)
- Pulse verification at pipeline boundaries with bounded repair loops (SIP-0070)
- Assembly CLI command for extracting build artifacts into runnable projects
- LLM router abstraction with Ollama adapter
- LanceDB semantic memory (SIP-042)
- OpenTelemetry with trace correlation
- Console Control-Plane UI with Continuum plugin shell and auth BFF (SIP-0069)
- Docker build system with deterministic multi-stage builds
- 17-service Docker Compose development environment

---

## Docker Build Process

SquadOps uses a **build-time assembly approach** for creating agent containers:

### Build Script
The `scripts/dev/build_agent.py` script:
- Reads agent `config.yaml` to resolve dependencies automatically
- Assembles only required files into `dist/agents/{role}/`
- Generates build artifacts (`manifest.json`, `agent_info.json`)
- Creates deterministic builds with SHA256 build hash

### Usage
```bash
# Build agent package locally (required before Docker build)
python scripts/dev/build_agent.py <role>

# Rebuild and deploy all agents
./scripts/dev/ops/rebuild_and_deploy.sh agents

# Rebuild runtime-api only
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api

# Rebuild everything
./scripts/dev/ops/rebuild_and_deploy.sh all
```

---

> **Note:** This project is part of the broader **SquadOps Field Guide** initiative – documenting how AI squads can operate as autonomous product-building teams with traceability, governance, and continuous optimization.
