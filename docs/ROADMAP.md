# SquadOps Development Roadmap

Living document tracking the implementation progression from initial prototype to production framework.

## Versioning Convention

Semver with an **even/odd minor** overlay (parity gates *features*, not hardening — #281): **even minors (1.2, 1.4, …) are feature releases** (led by a headline feature SIP; hardening rides along), **odd minors (1.3, 1.5, …) are feature-free stabilization releases** (the big risky refactors + debt paydown), and **patches ship urgent fixes any time, either lane.** Hardening lands wherever it's ready. See `docs/plans/1-2-0-release-plan.md` and CLAUDE.md.

## Forward Cadence (planned)

Version labels per the even/odd remap in `docs/plans/2-0-roadmap-reconciliation.md` (Findings 2 + 4):

- **v1.3 — shipped 2026-07-08** (first stabilization minor; see Release Timeline).
- **v1.4** — duty durability (SIP-0091) + verification evidence integrity (SIP-0096), the headline pair; possibly embodiment Phase 2 (SIP-0090, first live adapter). Plan: `docs/plans/1-4-evidence-arc-plan.md`.
- **v1.6** — Campaign mechanic (objective envelope + continuation policy; `sips/proposed/SIP-Campaign-Orchestration.md`), gated on SIP-0096 implemented + #288 + #316.
- **v1.8/v2.0** — the three 2.0 pillars: Capability-Backed Agents (what an agent *is*), Campaign capability-augmentation, Self-Improvement + Test Bay (the capstone).

## Release Timeline

### v1.3.0 (2026-07-08) — Current — First Stabilization Release (feature-free)
First **odd-minor stabilization release** (#281): the big structural refactors quarantined out of feature releases, plus debt paydown. Entire core scope landed from the Macbook lane (Spark offline); every structural change live-validated before merge.
- **SIP-0097 executor decomposition (#186, #295):** `DispatchedFlowExecutor` 3,358→1,805 lines across 6 sliced PRs; five injected collaborators (pure hoists, `RunLedger`+`RunCompletion` — zero per-run mutable state, the SIP-0096 §6.4 seam — `CorrectionRunner`, `PulseBoundaryRunner`, `TaskDispatcher`); slice 6 = the #295 plan-review gate check. SIP-0097 promoted → implemented.
- **#152:** `cycle_tasks.py` (3,276 lines) → `capabilities/handlers/cycle/` package behind a compat shim (after the #332 helper hoist).
- **#323:** agent comms poll→push — persistent `subscribe()` consumer, prefetch 1; kills consumer churn, up-to-1s pickup latency, and the `aio_pika` log flood (obsoleted #329).
- **#234:** dead sqlalchemy `DbRuntime` backend removed — `ports/` is vendor-type-free; asyncpg everywhere.
- **Fixed:** #327 prompt-registry drift (deploy re-sync + manifest hard-fail), #342 resume insta-fail (live pause→resume→complete verified, closed #258), #345 color-env test flakiness.
- **Docs/CI:** #335 hygiene pass (this file's stats/tables un-froze) + #336 docs-drift guards in the regression gate (version markers, SIP target parity, doc-ref existence).
- **Deferred:** #288 (Campaign 1.6 gate → pulled into the 1.4 window), #331/#333 (→ 1.5).

### v1.2.0 (2026-07-04) — First Feature Release (even/odd cadence)
First **even-minor feature release** (#281). Three feature SIPs, on a hardening base:
- **SIP-0090 Agent Embodiment Substrate — Phase 1:** the internal embodiment model — lifecycle state machine (single-active-per-agent, enforced in code + a Postgres partial unique index), resource budget primitives (non-silent exhaustion), `EmbodimentStatePort` + Postgres persistence, `EmbodimentCoordinator`. No adapter yet (#312, #317).
- **SIP-0095 Cycle Create Preflight:** create-time fail-fast (422 `PREFLIGHT_REJECTED`) on unsatisfiable roles / unpulled models; unreachable backend warns-and-allows; doctor parity; warnings on response + CLI (#298, #309, #311, #315, #321).
- **SIP-0089 runtime-arc completion:** recruitment via coordinator + FocusLease (#233); single-transaction coordinator UoW (#244).
- **#231** health signal → single source of truth (`runtime_status` always-populated); **#173** profiles → smoke/lite/full; **#158** operational hardening; **#319/#320** CLI error-message fix.
- **Deferred:** #295 (materialized-plan gate check → rides #186); SIP-0090 budget persistence/wiring (→ Phase 2).

### v1.1.1 (2026-06-28) — Runtime Lane Hardening
- **Live-validated the runtime lane (SIP-0089) end-to-end** after 1.1.0, which surfaced two regressions the unit suites couldn't catch:
  - **#270** cycle API routes 403'd every authenticated user — #150's `cycles:*` scope checks didn't account for the role-centric Keycloak realm (issues roles, not scopes); fixed with a role→scope bridge in `resolve_identity`.
  - **#272** duty windows never auto-opened under the default `missed_window_policy="skip"` — poll-cadence lag was misread as a missed window; fixed with an on-time grace of one poll interval.
- **Resume reliability:** duty-deferred runs now actually re-execute on resume (#222); mid-sequence runs resume at the correct workload index (#257).
- **Reliability:** bounded RabbitMQ publish retry/backoff (#245); `runs retry` actually executes (#133, #205); strip `<think>` before fenced parsing (#130); OTel provider test leak fixed (#239).
- **Additive (backward-compatible):** per-role Prefect task names (#94); agent `mode` + `runtime_status` on the agent list / console (#230, #231).
- **Internal:** `establish_contract` → `define_done` rename (#79); regression suite parallelized via pytest-xdist (#216); SIP-status script rewrites the body status line (#253).

### v1.1.0 (2026-06-28) — Agent Runtime State + 1.0.x Hardening
- **SIP-0089** Agent Runtime State (Phases 1–4): runtime modes (ambient/cycle/duty) with a single-writer coordinator + in-process duty scheduler, assignments & duty windows, FocusLease arbitration, RuntimeActivity observability. Migrations 1100–1130.
- **1.0.x hardening foundation** landed: CI-trust arc (declared deps, dev+CI on Python 3.12, ruff-format gate, adapters in the gate) + reliability fixes (#146 channel recovery, #155 frozen-result mutation, #77 cancel→Prefect, #209 integration config) + **#150 cycle-route scope enforcement (security)**.
- The remaining build-reliability work is re-baselined as the **1.1.x hardening plan** (`docs/plans/1-1-x-hardening-plan.md`) — it no longer gates the version. (Gate read as foundational-hardening completeness; joint Spark/Mac decision 2026-06-28.)
- **SIP-0088** (Agent Runtime Modes umbrella) stays **accepted** — its v1.2 pieces (embodiment, recruitment-driven leases) are future; promoting the umbrella would overstate it.

### v1.0.6 (2026-06-21) — Per-Agent Reply Queues
- **SIP-0094** Per-Agent Reply Queues + Long-Lived Subscription Model
  - Replaces the leaky per-run `cycle_results_{run_id}` reply queues — which lost replies in the consumer-tag churn window and leaked one orphan queue per run — with durable per-agent `{agent_id}_replies` queues
  - `ReplyRouter` holds one long-lived subscription per agent and resolves replies by `task_id`; new `QueuePort.subscribe()` primitive backed by a reconnecting RabbitMQ iterator (resubscribe surfaced in `health()`)
  - `TaskResult.from_dict` hardened to drop unknown keys (forward-compat across rolling agent deploys)
  - Substrate precondition for the 1.0.x build-reliability hardening line

### v1.0.5 (2026-04-24) — Prefect Task Log Streaming
- **SIP-0087** Prefect Task-Scoped Log Streaming
  - Per-task log forwarding to the Prefect UI with heartbeats

### v1.0.4 (2026-04-19) — Build Convergence Loop
- **SIP-0086** Build Convergence Loop
  - Dynamic task decomposition, output validation, and correction activation

### v1.0.3 (2026-04) — Post-1.0 Hardening
Post-1.0 patch line. Docs hygiene, complexity tightening (C901 threshold 15→12), streaming LLM chat path (`chat_stream_with_usage()`).

### v1.0.2 (2026-03-15) — Console Messaging
- **SIP-0085** Console Messaging Capability for Live Agents via A2A
  - Joi agent routes operator messages to the live squad via the A2A protocol
  - Modal-overlay UI approach with phase audit gates
- Continuum (console UI component) pinned to v1.0.2

### v1.0.1 (2026-03-13) — Prompt Registry
- **SIP-0084** Prompt Registry Integration
  - Versioned prompt management for handler prompts

### v1.0.0 (2026-03-10) — Architecture Complete
Release milestone, not a new SIP. 13 SIPs landed between v0.9.0 and v1.0.0 (auth → LangFuse → cycles → workload protocols → correction → wrap-up → bootstrap → multi-run). 3,032 tests passing at release. See the v1.0 Progression section below for the retrospective.

### v0.9.19 (2026-03-07) — Multi-Run Orchestration & Bootstrap
- **SIP-0083** Multi-Run Cycle Orchestration
  - `execute_cycle()` loops over `workload_sequence`, creating a Run per workload
  - `"auto"` gate sentinel for workload-to-workload handoffs without HITL
  - `_build_forwarding_overrides()` passes promoted artifacts and `impl_run_id` between workloads
  - Multi-phase cycle request profile (1 HITL gate + 1 auto gate)
- **SIP-0082** Time Budget Awareness in Planning Prompts
  - `time_budget_seconds` coerced from string at CRP load time
  - Budget awareness injected into planning prompt fragments
- **SIP-0081** Profile-Driven Bootstrap
  - Three-layer architecture: profile YAML → shell scripts → doctor validation
  - Three profiles: `dev-mac`, `dev-pc`, `local-spark`
  - `squadops bootstrap <profile>` and `squadops doctor <profile>` commands
  - State file at `.squadops/bootstrap/<profile>.json`

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
  - Correction protocol handlers (analyze_failure, correction_decision, define_done, repair handlers)
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

## v1.0 Progression (Retrospective — 1.0 shipped 2026-03-10)

1.0 was organized around one concrete objective: **the first trustworthy long-running DGX Spark cycle**. Every SIP was prioritized by how directly it contributed to that objective.

**What actually shipped in 1.0**: all five Spark-critical SIPs (SIP-0076/77/78/79/80) landed between v0.9.14 and v0.9.18, followed by multi-run orchestration and bootstrap tooling in v0.9.19. The 1.0.0 release tag on 2026-03-10 marked architecture completion.

**What did not ship in 1.0**: the two originally-scoped "1.0 Hardening" SIPs (API Contract Hardening, Cycle Evaluation Scorecard) remain in the proposed backlog. They are now post-1.0 work tracked separately. If they become blocking, they get numbered and promoted — but 1.0 did not gate on them.

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

### Post-1.0 Hardening (Originally Scoped for 1.0 — Deferred)

These SIPs were originally scoped as "1.0 Hardening" but did not land before the 1.0.0 release. They remain in the proposed backlog.

| SIP | Focus |
|-----|-------|
| API Contract Hardening | Pagination, error shapes, OpenAPI response models, status codes, gate identity, artifact validation, DB retry |
| Cycle Evaluation Scorecard | Four-dimension evaluation (outcome, quality, coordination, efficiency), failure attribution, benchmarking, Scorecard console page |

**API Contract Hardening** was kept out of 1.0 because the Spark validation path did not expose execution-safety-blocking API issues. It is sequenced whenever a consumer (console, external integrator) surfaces a specific contract pain point.

**Cycle Evaluation Scorecard** is gated on evidence-quality confidence from SIP-0077 events and SIP-0080 closeout artifacts. Scorecard sophistication improves learning *after* runs; it does not improve the success of any individual run.

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

| SIP | Title | Target |
|-----|-------|--------|
| **SIP-0088** | Agent Runtime Modes (umbrella; runtime arc shipped 1.1–1.2, remaining pieces future) | — |
| **SIP-0090** | Agent Embodiment Substrate (Phase 1 shipped 1.2.0) | Phases 2+ → v1.4+ |
| **SIP-0091** | Duty Durability via Temporal | v1.4 |
| **SIP-0092** | Implementation Plan Improvement — Typed Acceptance, Separated Authoring, and Plan Changes | — |
| **SIP-0093** | Multi-Role Plan Authoring | — |
| **SIP-0096** | Verification Evidence Integrity | v1.4 |

## Proposals (Backlog)

### Post-1.0 Hardening (Deferred from 1.0 Scope)

| SIP | Title |
|-----|-------|
| (unnumbered) | API Contract Hardening |
| (unnumbered) | Cycle Evaluation Scorecard |

### Unnumbered Drafts (filed, awaiting design review)

| SIP | Title |
|-----|-------|
| (unnumbered) | Campaign Orchestration (v1.6 candidate) |
| (unnumbered) | Campaign Self-Improvement and Test Bay Requirements (2.0 vision anchor) |
| (unnumbered) | Agent Comms Delivery Guarantees (Campaign 1.6 gate) |
| (unnumbered) | Edge Deployment Profile |
| (unnumbered) | Experiment Queue and Cycle Assessment |

### Legacy Proposals

| SIP | Title |
|-----|-------|
| SIP-0012 | Pattern-First Development Escalation Protocol |
| SIP-0013 | Extensibility & Customization Protocol |
| SIP-0016 | Human-Agent Hybrid Squad Operations |
| SIP-0018 | Enterprise Process CoE Enablement |
| SIP-0018-v2 | Squad Context Protocol |
| SIP-0023 | Domain Expert Architecture for Product Strategy |
| SIP-0028 | Hybrid Deployment Model (Multi-Environment) |

---

## Stats

*As of 2026-07-08 (v1.3.0):*

- **Framework version**: 1.3.0
- **SIPs**: 60 implemented, 6 accepted (SIP-0088, 0090–0093, 0096), 20 deprecated (registry); 14 files in `sips/proposed/` (7 registry-tracked legacy + 7 unnumbered drafts)
- **Tests**: 4,700+ passing in the regression suite
- **Python source**: ~61,000 lines (src + adapters; ~83,000 test lines, ~110,000 doc lines)
- **~6 months** from initial repo (2025-09-20) to 1.0.0 release (2026-03-10)
