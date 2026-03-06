# SquadOps Development Roadmap

Living document tracking the implementation progression from initial prototype to production framework.

## Release Timeline

### v0.9.18 (2026-03-06) — Wrap-Up Workload Protocol & Test Quality Enforcement
- **SIP-0080** Wrap-Up Workload Protocol
  - Domain models: ConfidenceClassification, CloseoutRecommendation, UnresolvedIssueType/Severity, NextCycleRecommendation
  - 5 wrap-up handlers (gather_evidence, assess_outcomes, classify_unresolved, closeout_decision, publish_handoff)
  - YAML frontmatter validation for structured closeout/handoff decisions
  - wrapup.yaml cycle request profile with 3 milestone pulse check suites
  - WRAPUP_TASK_STEPS and REQUIRED_WRAPUP_ROLES validation
- **Test Quality Enforcement**
  - AST linter made blocking in regression script (was non-blocking)
  - 235 tautological tests removed across 77 files (attribute-only, sole isinstance, issubclass-only)
  - Linter false-positive fix: gate isinstance/is-not-None on has_calls
  - Codebase fully ruff-clean (4 pre-existing violations fixed)

### v0.9.17 (2026-03-05) — Implementation Run Contract & Correction Protocol
- **SIP-0079** Implementation Run Contract & Correction Protocol
  - Domain models: RunContract, RunCheckpoint, PlanDelta, TaskOutcome, FailureClassification
  - Checkpoint persistence in both registry adapters, FAILED→RUNNING FSM transition
  - Implementation/correction/repair task steps with deterministic IDs
  - 6 bounded execution CRP schema keys (`max_task_retries`, `max_task_seconds`, `max_consecutive_failures`, `max_correction_attempts`, `time_budget_seconds`, `implementation_pulse_checks`)
  - Executor checkpoint/resume, time budget enforcement, `_PausedError`
  - Correction protocol handlers (analyze_failure, correction_decision, establish_contract, repair handlers)
  - Outcome routing with `outcome_class` on TaskResult
  - Resume and checkpoints API routes (`POST /{run_id}/resume`, `GET /{run_id}/checkpoints`)
  - Resume and checkpoints CLI commands (`squadops runs resume`, `squadops runs checkpoints`)
  - Implementation cycle request profile with milestone + cadence pulse check suites
  - MetricsBridge correction counters, PrefectBridge RUN_RESUMED state mapping
  - AST-based test quality linter with Claude Code PostToolUse hook

### v0.9.16 (2026-03-03) — Planning Workload Protocol
- **SIP-0078** Planning Workload Protocol
  - `PLANNING_TASK_STEPS` (5 steps) and `REFINEMENT_TASK_STEPS` (2 steps) with workload-type branching
  - `UnknownClassification` constants (5 classification levels)
  - 7 planning/refinement handlers with `_PlanningTaskHandler` base (task_type prompt assembly)
  - `GovernanceAssessReadinessHandler` structural validation (YAML frontmatter, readiness, sufficiency_score)
  - `GovernanceIncorporateFeedbackHandler` D17 fail-fast and differentiated companion artifact
  - 7 task_type prompt fragments with manifest integrity
  - Planning cycle request profile with `progress_plan_review` gate, 2 pulse check suites, cadence policy
  - `REQUIRED_REFINEMENT_ROLES` validation for refinement runs

### v0.9.15 (2026-03-01) — Cycle Event System
- **SIP-0077** Cycle Event System
  - `CycleEventBusPort` with 20-event taxonomy across 6 entity types
  - `InProcessCycleEventBus` adapter with per-run monotonic sequences
  - Bridge subscribers: LangFuseBridge, PrefectBridge, MetricsBridge
  - 25 emission points (19 executor + 6 API routes)
  - Dual-emit alongside existing telemetry (v0 scope)
  - Drift detection tests for registry/event parity

### v0.9.14 (2026-02-28) — Workload & Gate Canon
- **SIP-0076** Workload & Gate Canon
  - `WorkloadType` and `PromotionStatus` constants, DDL migration
  - Artifact promotion (one-way, idempotent, route-level baseline check)
  - `workload_type` filter on list_runs, gate name prefix validation
  - CRP `workload_sequence` key, CLI gate flags with mutual exclusion

### v0.9.13 (2026-02-26) — LLM Budget & Timeout Controls
- **SIP-0073** LLM Budget & Timeout Controls
  - `chat()` budget/timeout params, model registry, prompt guard
  - Capability-level `max_completion_tokens` and `test_timeout_seconds`
  - Handler wiring for Dev, QA, and test runner budgets

### v0.9.12 (2026-02-24) — Stack-Aware Development Capabilities
- **SIP-0072** Stack-Aware Development Capabilities
  - `DevelopmentCapability` registry with file classification
  - Handler stack awareness (dev, QA, builder)
  - Node test runner, fullstack build profile

### v0.9.11 (2026-02-22) — Builder Role
- **SIP-0071** Builder Role (Dedicated Product Builder Agent)

### v0.9.10 (2026-02-20) — Squad Configuration Perspective
- **SIP-0075** Squad Configuration Perspective (console plugin, icon distribution)

### v0.9.9 (2026-02-18) — Pulse Checks and Verification
- **SIP-0070** Pulse Checks and Verification Framework
  - Milestone and cadence-based pulse checks in the cycle execution pipeline
  - Repair loops with acceptance engine integration
  - Verification record persistence (memory + Postgres)
  - Pulse check cycle request profiles (pulse-check, pulse-check-build)
- CLI `--prd` accepts file paths (auto-ingest) in addition to artifact IDs
- Fix: PRD content resolution in executor (artifact ID → full text)
- BuildKit cache mounts for all Dockerfiles

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
- **SIP-0065** CLI for Cycle Execution (Typer CLI with cycle request profile contract packs)

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

## v1.0 Progression

The path to 1.0 is organized around one concrete objective: **the first trustworthy long-running DGX Spark cycle**. Every SIP is prioritized by how directly it contributes to that objective.

The SIP set is divided into Spark-critical execution readiness (must land before the first long run) and 1.0 hardening (must land before the 1.0 release, but does not gate the first Spark run).

### Cross-Cutting Dependency: Canonical Artifact Flow

Multiple SIPs depend on a shared artifact contract. The following artifact types must have a consistent identity, storage, and promotion model across the platform:

- **Planning artifact** — durable handoff from planning to implementation
- **Plan refinement artifact** — structured deltas from human review
- **Implementation outputs** — code, tests, build results
- **QA findings** — defect reports, verification evidence
- **Plan deltas** — correction records during implementation
- **Closeout artifact** — wrap-up adjudication and evidence
- **Next-cycle handoff artifact** — carry-forward for the next planning phase

The Workload & Gate Canon SIP defines the artifact promotion model (working vs promoted). All pipeline SIPs produce or consume these artifacts. This dependency should be treated as a first-order integration concern, not an afterthought.

### Spark-Critical — Execution Readiness

These SIPs must land before the first DGX Spark validation run. They are sequenced by dependency.

| Order | SIP | Focus | Status |
|-------|-----|-------|--------|
| 1 | **SIP-0076** Workload & Gate Canon | `workload_type` on Run, gate outcome expansion, artifact promotion, Pulse vs Gate semantics | **Implemented (v0.9.14)** |
| 2 | **SIP-0077** Cycle Event System (v0) | Canonical lifecycle event bus, 20-event taxonomy, bridge adapters. v0 scope only — emit + bridge. Full rewire (v1) and event-first (v2) follow later. | **Implemented (v0.9.15)** |
| 3 | **SIP-0078** Planning Workload Protocol | Planning contract, durable planning artifact, QA-first test strategy, proto validation, unknown classification, readiness decision | **Implemented (v0.9.16)** |
| 4 | **SIP-0079** Implementation Run Contract | Run contract, correction protocol (detect → RCA → decide → plan delta → resume), **durable checkpoint/resume**, bounded retry/timebox | **Implemented (v0.9.17)** |
| 5 | **SIP-0080** Wrap-Up Workload Protocol | Closeout artifact, planned-vs-actual comparison, confidence classification, structured unresolved issues, next-cycle handoff | **Implemented (v0.9.18)** |

**Why this order**: Workload Canon defines the execution vocabulary. Event System provides lifecycle facts. The three pipeline protocols (Planning → Implementation → Wrap-Up) build on both. Implementation Run Contract is the single most important Spark-readiness SIP — without durable checkpoint/resume, a long run is fragile regardless of how clean the architecture is. Wrap-up is execution safety, not reporting polish — it is what makes memory, evaluation, and next-cycle readiness trustworthy.

### Milestone Stage 1: Local Validation (MacBook)

All Spark-critical SIPs are developed, tested, and validated locally on MacBook before the DGX Spark is available. The protocols are duration-agnostic — if they don't work reliably on a 1-hour MacBook cycle, they won't work on an 8-hour Spark cycle. Duration amplifies problems; it doesn't create them.

**Target**: One bounded Cycle on MacBook (1–2 hours) using the existing Docker Compose stack and Ollama with:
- 1 approved planning workload (15–30 min, timeboxed to local model speed)
- 1–2 bounded implementation workloads
- Pulse Checks active throughout execution
- At least one correction path exercised (simulated failure or real)
- Mandatory wrap-up artifact generation
- Checkpoint/resume tested (interrupt and resume a short cycle cleanly)

**Preflight Checklist** (required before local validation):
- [ ] Deployed platform version includes all Spark-critical SIPs
- [ ] Reference workload/app selected and cycle request profile defined
- [ ] Role capability readiness verified (Lead, Dev, QA, Data, Builder)
- [ ] Model budgets and timeouts configured for local Ollama models
- [ ] Checkpoint/resume tested on a trivial cycle (e.g., selftest profile)
- [ ] Event emission visible in LangFuse / Prefect
- [ ] Artifact persistence verified (create, retrieve, promote)
- [ ] Wrap-up path verified (closeout artifact emitted on both success and failure)
- [ ] Restart/redeploy confidence confirmed (services recover cleanly)
- [ ] Operator can monitor cycle health via console or Prefect UI

**Success Criteria** (same for both stages):
- Cycle completes or terminates cleanly (no orphaned state)
- Closeout artifact is produced with confidence classification
- Planned-vs-actual comparison is present and accurate
- Next-cycle handoff artifact is usable
- Operator can reconstruct what happened without reading raw logs

**Acceptable Failure Classes** (not a milestone failure):
- Partial completion with honest confidence classification
- Correction protocol triggered and executed cleanly
- Model limitations identified and attributed correctly (expected on smaller local models)

**Milestone Failure** (requires investigation before retry):
- Orphaned or inconsistent run state
- Missing or corrupted artifacts
- Checkpoint/resume fails silently
- Wrap-up does not execute or produces false confidence
- Events missing or out of order

### Milestone Stage 2: DGX Spark Validation Run

Once local validation passes, the same protocols are exercised at longer duration on DGX Spark. The Spark run proves the protocols hold under sustained execution with stronger models — it should not be the first time they are tested.

**Target**: One bounded Cycle on DGX Spark (4–8 hours) with:
- 1 approved planning workload (60–90 min)
- 2–4 bounded implementation workloads
- Pulse Checks active throughout execution
- At least one supported correction path exercised or verified
- Mandatory wrap-up artifact generation
- Checkpoint/resume tested (at minimum: verified that a resumed run recovers cleanly)

**Additional Spark-specific checks**:
- [ ] Model budgets and timeouts reconfigured for Spark-class models
- [ ] Longer execution does not introduce state drift, memory pressure, or artifact corruption
- [ ] Wrap-up quality does not degrade with larger evidence volume
- [ ] Correction protocol handles real (not simulated) mid-run issues

### 1.0 Hardening

These SIPs are required for the 1.0 release but do not gate the first Spark validation run. If schedule pressure emerges, they trail the Spark-critical work — they do not displace it.

| SIP | Focus |
|-----|-------|
| API Contract Hardening | Pagination, error shapes, OpenAPI response models, status codes, gate identity, artifact validation, DB retry |
| Cycle Evaluation Scorecard | Four-dimension evaluation (outcome, quality, coordination, efficiency), failure attribution, benchmarking, Scorecard console page |

**API Contract Hardening** lands as a single SIP (the P0 items are tightly coupled), sequenced after the pipeline SIPs. If the Spark run exposes specific API contract issues that affect execution safety, those items get pulled forward.

**Cycle Evaluation Scorecard** depends on evidence quality from the event system and closeout artifacts. It should not outrun the fidelity of the evidence it consumes. Scorecard sophistication improves learning after runs — it does not improve the success of the first run itself.

### Critical Path

```
Workload & Gate Canon ─── Planning Workload Protocol ──────────────┐
          │                                                         │
          │            Implementation Run Contract ─────────────────┤
          │                                                         │
          │            Wrap-Up Workload Protocol ───────────────────┤
          │                                                         │
Cycle Event System (v0) ───────────────────────────────────────────┤
                                                                    │
                    ┌── LOCAL VALIDATION (MacBook) ──┐              │
                    │   1-2 hour bounded cycle       │              │
                    └────────────────────────────────┘              │
                                  │                                 │
                    ┌── SPARK VALIDATION ────────────┐              │
                    │   4-8 hour long run            │              │
                    └────────────────────────────────┘              │
                                                                    │
          API Contract Hardening ───────────────────────────────────┼── v1.0
                                                                    │
          Cycle Evaluation Scorecard ──────────────────────────────┘
```

### Post-1.0 Horizon

The following areas are identified for future work but do not block 1.0 readiness:

- **WebSocket / Realtime Channels** — live event streaming to the console, real-time chat protocol between operators and agents. Depends on the Cycle Event System. See `docs/ideas/IDEA-WebSocket-*` and `docs/ideas/IDEA-Realtime-Chat-*`.
- **Cycle Event System v1/v2** — rewire call sites (v1), event-first architecture (v2).
- **Retrieval-enriched planning memory** — LanceDB integration for planning phases.
- **Cross-cycle learning** — historical comparison, scored memory, trend analysis.
- **Autonomous improvement proposals** — agent-driven suggestions based on repeated failure patterns.
- **Advanced benchmarking** — rule-based recommendations on top of the scorecard framework.

---

## Accepted (Next Up)

(none — all accepted SIPs are implemented)

## Proposals (Backlog)

### 1.0 Track — Spark-Critical

| SIP | Title | Status |
|-----|-------|--------|
| **SIP-0076** | Workload & Gate Canon | **Implemented** |
| **SIP-0077** | Cycle Event System | **Implemented** |
| **SIP-0078** | Planning Workload Protocol | **Implemented** |
| **SIP-0079** | Implementation Run Contract & Correction Protocol | **Implemented (v0.9.17)** |
| **SIP-0080** | Wrap-Up Workload Protocol | **Implemented (v0.9.18)** |

### 1.0 Track — Hardening

| SIP | Title |
|-----|-------|
| (unnumbered) | API Contract Hardening |
| (unnumbered) | Cycle Evaluation Scorecard |

### Other Proposals

| SIP | Title |
|-----|-------|
| SIP-0012 | Pattern-First Development Escalation Protocol |
| SIP-0013 | Extensibility & Customization Protocol |
| SIP-0016 | Human-Agent Hybrid Squad Operations |
| SIP-0018 | Enterprise Process CoE Enablement |
| SIP-0023 | Domain Expert Architecture for Product Strategy |
| SIP-0028 | Hybrid Deployment Model (Multi-Environment) |
| (unnumbered) | Intelligent Delegation Protocols |

---

## Stats

- **Framework version**: 0.9.18
- **SIPs**: 54 implemented, 0 accepted, 11 proposals (2 on 1.0 track), 15 deprecated
- **Tests**: 2,890+ passing
- **Python source**: ~39,000 lines (~51,000 test lines, ~84,000 doc lines)
- **5 months** from initial repo to production-grade console UI
