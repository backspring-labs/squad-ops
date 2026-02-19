# SquadOps Development Roadmap

Living document tracking the implementation progression from initial prototype to production framework.

## Release Timeline

### v0.9.8 (2026-02-16) — Console Control-Plane UI
- **SIP-0069** Console Control-Plane UI via Continuum Plugins
  - SvelteKit shell with 7 plugins (home, agents, cycles, projects, artifacts, observability, system)
  - Auth BFF with PKCE flow, session store (Redis/memory), token refresh
  - Same-origin API proxy for runtime-api (eliminates cross-origin issues)
  - Cycle command handlers (create, cancel, gate approve/reject)
  - API-backed dashboard widgets: run activity, build artifacts, gate decisions, cycle stats

### v0.9.7 (2026-02-14) — Agent Build Capabilities
- **SIP-0068** Enhanced Agent Build Capabilities
  - Fenced code parser, build handlers (development, QA)
  - Task plan generator with BUILD_TASK_STEPS
  - Assembly CLI command (`runs assemble`) for extracting build artifacts
  - Reference apps: hello_squad, group_run

### v0.9.6 (2026-02-12) — Durable Persistence + Observability
- **SIP-0067** Postgres Cycle Registry (durable cycle/run/gate persistence with migrations)
- **SIP-0066** Distributed Cycle Execution Pipeline (RabbitMQ dispatch, Prefect DAG, LangFuse cross-process traces)
- **SIP-0065** CLI for Cycle Execution (Typer CLI with CRP contract packs)

### v0.9.3 (2026-02-08) — Cycle Execution API
- **SIP-0064** Project Cycle Request API (cycles, runs, gates, artifacts via REST)

### v0.9.2 (2026-02-08) — Keycloak Hardening
- **SIP-0063** Keycloak Production Hardening (config, realms, console auth)

### v0.9.1 (2026-02-07) — Auth Boundary
- **SIP-0062** Auth Boundary (Keycloak OIDC, JWT middleware, service identities, audit logging)

### v0.9.0 (2026-02-06) — LLM Observability
- **SIP-0061** LangFuse LLM Observability Foundation (buffered trace/span/generation recording)

### v0.8.9 (2026-02-01) — Legacy Retirement
- **SIP-0060** Agent Migration to Hexagonal Application Layer
- **SIP-0059** Infrastructure Ports Migration
- Removal of `_v0_legacy/` directory

### v0.8.8 (2026-02-01) — Hexagonal Completion
- **SIP-0058** Capability Contracts + Reference Workloads

### v0.8.5 (2026-01-29) — Hexagonal Middleware
- **SIP-0057** Hexagonal Layered Prompt System
- **SIP-0056** Hexagonal Queue Transport Layer

### v0.8.3 (2026-01-24) — Hexagonal Foundation
- **SIP-0055** DB Deployment Profile (Postgres portability)

### v0.8.2 (2026-01-10) — Secrets Management
- **SIP-0052** Secrets Management (env, file, docker_secret providers)

### v0.8.0 (2025-12-13) — ACI v0.8
- **SIP-0050** Agent Container Interface (ACI)
- **SIP-0048** CDS Baseline + Runtime API with FastAPI
- **SIP-0049** Agent Lifecycle & Health Check Integration

### v0.6.x (2025-11) — Skills + Memory
- **SIP-0040** Capability System & Loader (v0.6.0)
- **SIP-042** LanceDB Semantic Memory (v0.5.0)

### v0.4.0 (2025-11-03) — Orchestration
- **SIP-0041** Naming & Correlation (cycle/pulse/channel)
- **SIP-0031** Internal A2A Envelope Standard

### v0.2.0 (2025-10-11) — Test Coverage Milestone
- **SIP-0026** Testing Framework and Philosophy

### v0.1.x (2025-10) — Genesis
- First end-to-end AI agent collaboration (2025-10-07)
- WarmBoot runs 001–006 proving real agent work
- Initial 5-agent squad (Max, Neo, Nat, Eve, Data)
- Initial repo structure (2025-09-20)

---

## Accepted (Next Up)

| SIP | Title | Notes |
|-----|-------|-------|
| SIP-0070 | Pulse Checks and Verification Framework | Accepted, plan in progress |

## Proposals (Backlog)

| SIP | Title |
|-----|-------|
| SIP-0012 | Pattern-First Development Escalation Protocol |
| SIP-0013 | Extensibility & Customization Protocol |
| SIP-0016 | Human-Agent Hybrid Squad Operations |
| SIP-0018 | Enterprise Process CoE Enablement |
| SIP-0023 | Domain Expert Architecture for Product Strategy |
| SIP-0028 | Hybrid Deployment Model (Multi-Environment) |
| (unnumbered) | Intelligent Delegation Protocols |
| (unnumbered) | Cycle Event System |

---

## Stats

- **Framework version**: 0.9.8
- **SIPs**: 42 implemented, 1 accepted, 8 proposals, 15 deprecated
- **Tests**: 1,447+ passing
- **Python source**: ~38,000 lines
- **5 months** from initial repo to production-grade console UI
