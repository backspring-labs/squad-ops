# SquadOps – Agent Squad Framework

## Overview
**SquadOps** is an AI agent collaboration framework for software development. The system implements a role-based agent architecture where specialized agents handle different aspects of development tasks, from requirements analysis to application deployment.

**Current Status**: Production-ready framework (v0.9.6) with hexagonal architecture, distributed cycle execution pipeline, Postgres-backed persistence, LangFuse observability, Keycloak authentication, CLI tooling, and 1,328+ passing tests.

---

## Mission
- **Learn**
- **Build**
- **Benchmark**

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

### Cycle Execution Pipeline (SIP-0064/0066)
- **Cycle API** – Create, monitor, and manage execution cycles via REST API
- **Task Planning** – Automatic task plan generation from PRD references
- **Distributed Flow Executor** – Sequential task dispatch to agent containers via RabbitMQ
- **Gate Decisions** – Human-in-the-loop approval gates between pipeline stages
- **Artifact Management** – Typed artifact ingestion and retrieval per run

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
- **Health Check** – FastAPI monitoring service
- **PostgreSQL** – Cycle registry, task logging, and state persistence
- **Redis** – Caching and performance optimization
- **RabbitMQ** – Inter-agent message queue
- **Keycloak** – OIDC identity provider with realm auto-provisioning
- **LangFuse** – LLM observability with cross-process trace linking
- **Prefect** – Workflow orchestration and DAG visibility
- **Ollama** – Local LLM inference
- **Docker Compose** – 14-service development environment

---

## Documentation
Comprehensive documentation and protocols are available in `/docs/`:

- **SIPs (SquadOps Improvement Proposals)** – 63 protocol specifications in `sips/` directory (40 implemented, 1 accepted, 7 proposals, 15 deprecated)
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
│   └── handlers/     # Cycle task handlers (strategy, dev, QA, data, governance)
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
/tests/               # Test suite (1,328+ tests)
├── unit/             # Unit tests (mocked deps)
├── integration/      # Integration tests (real services)
└── conftest.py       # Global fixtures
/docs/                # Documentation and protocols
/scripts/             # Development and maintainer scripts
/infra/               # Database migrations and DDL
docker-compose.yml    # 14-service development environment
```

---

## Reference Application: play_game
- **play_game** is a sample project that demonstrates the full cycle execution pipeline
- Ships with a PRD (`examples/play_game/prd.md`) and PCR (Project Cycle Request)
- Exercises all 5 agents: strategy analysis, implementation, QA, data reporting, governance review
- Run via CLI: `squadops cycles create play_game --squad-profile full-squad --profile selftest`

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
   squadops auth login
   ```

4. **Run a cycle**:
   ```bash
   squadops cycles create play_game --squad-profile full-squad --profile selftest
   squadops cycles show <cycle-id>
   ```

5. **Monitor**: Check LangFuse UI at `http://localhost:3001` and Prefect UI at `http://localhost:4201`

---

## Development Roadmap

**Current Phase**: Distributed Cycle Execution Pipeline Complete

### Implemented (v0.9.x)
- **SIP-0061** – LangFuse LLM Observability Foundation (buffered trace/span/generation recording)
- **SIP-0062** – Auth Boundary (Keycloak OIDC, JWT middleware, service identities, audit logging)
- **SIP-0064** – Project Cycle Request API (cycles, runs, gates, artifacts via REST)
- **SIP-0065** – CLI for Cycle Execution (Typer CLI with CRP contract packs)
- **SIP-0066** – Distributed Cycle Execution Pipeline (RabbitMQ dispatch, Prefect DAG, LangFuse traces)
- **SIP-0067** – Postgres Cycle Registry (durable cycle/run/gate persistence with migrations)

### Implemented (v0.8.x)
- **SIP-0048** – Runtime API with FastAPI
- **SIP-0055** – DB Deployment Profile
- **SIP-0058** – Capability Contracts

### Next Phase
- Multi-cycle orchestration and pipeline chaining
- Enhanced gate decision workflows
- Production deployment hardening

---

## Current Status
**Framework Version**: 0.9.6
**Development Status**: Production-ready distributed cycle execution with durable persistence, authentication, CLI tooling, and full observability stack.

### Project Statistics
- **~34,578 lines** of Python source code (271 files)
- **~28,133 lines** of test code (160 files)
- **~61,665 lines** of documentation (215 markdown files)
- **1,328+ tests** passing in regression suite
- **63 SIPs** (40 implemented, 1 accepted, 7 proposals, 15 deprecated)

### Functional Components
- 5 Agents: Max (Lead), Neo (Dev), Nat (Strategy), Eve (QA), Data (Analytics)
- Cycle Execution API with runs, gates, and artifact management (SIP-0064)
- Distributed flow execution via RabbitMQ (SIP-0066)
- Postgres-backed cycle registry with migrations (SIP-0067)
- LangFuse LLM observability with cross-process trace linking (SIP-0061)
- Keycloak OIDC authentication with JWT middleware and audit logging (SIP-0062)
- CLI for cycle management with CRP contract packs (SIP-0065)
- Capability contracts with declarative acceptance checks (SIP-0058)
- Task planning with automatic task flow generation
- LLM router abstraction with Ollama adapter
- LanceDB semantic memory (SIP-042)
- OpenTelemetry with trace correlation
- Docker build system with deterministic multi-stage builds
- 14-service Docker Compose development environment

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
