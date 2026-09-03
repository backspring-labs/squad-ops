# SquadOps – Agent Squad Framework

## Overview
**SquadOps** is an AI agent collaboration framework for software development. The system implements a role-based agent architecture where specialized agents handle different aspects of development tasks, from requirements analysis to application deployment.

**Current Status**: v1.7.1 — Experiment-ready framework with hexagonal architecture. The 1.6 Authorship release climbs the rung above 1.4: **the squad authors the interface design from the PRD** — a dedicated authoring stage writes the interface manifest under in-cycle schema and winnability gates, a question-gated human review stops only when the design declares an unresolved decision, a revision loop answers review notes instead of re-rolling the framing, and authoring provenance records how the design was written without moving the hash its contract binds (SIP-0103, implemented). Lane S generalizes the build machinery: the five per-stack surfaces collapse into a single `ScaffoldStack` registration and a second real stack (`nextjs_ts`) is live, with the Stack Blueprint Contract accepted with its unbuilt parts named (SIP-0105). The release claim is measured, not asserted: authored-mode Functional App Yield banked at **4/6 functional (amended; dual record 3/6 pre-registered instrument / 4/6 corrected, both always reported)** on a pre-registered window against a frozen deploy with zero manual interventions — and a follow-on model-comparison window (qwen3.8:27b) re-exercised the full authored path at 4/6, equal yield at roughly half the wall-clock. v1.6.3 adds the first **measured repeatability rate**: eight pre-registered rolls on a frozen deploy, no voids and no resets, **5/8 functional (95% CI 30.6–86.3%)** with zero manual interventions — and, corrected after the cut (record §6), all three failures were the same defect: the join endpoint's response shape versus the declared element kind, diagnosed at round 0 and never landed by the repair rounds. v1.6.4 fixes what that set found — the frozen model, the store's table handles, the audit's blindness to response bodies, the ledger's per-file identity, the fill gate and the repair target all stop contradicting the manifest — and re-measures on the same protocol: **8/8 functional (95% CI 63.1–100%), 14/14 criteria on every roll**, with the record explicit that the two rolls which entered the correction loop were recovered by fallback, not by repair. v1.6.5 takes the qa completion cap (fills first, a qa-only budget, the self-eval merging fills, a qa repair that reaches a fill) and measures on **two stacks**: Next.js+TS **6/6 functional (95% CI 61.0–100%) with zero correction rounds and zero cap hits**, and FastAPI+React's first authored-mode baseline, **2/6 (95% CI 9.7–70.0%)**, with one scaffold defect under five of its six rolls and the fixes filed as the 1.6.6 plan. v1.6.6 ships those six fixes and re-measures on the same protocol: **FastAPI+React 4/6 (95% CI 30–90%), Next.js+TS 2/2** — every fix held wherever a roll exercised it, and the two remaining rejections are one class the 1.7 plan names. The v1.4 **Verified Canonical App Build** claim stands beneath it: given a PRD and a fully specified interface manifest, 6/6 functional yield under the same protocol. Built on the stabilized 1.5 line (SIP-0096 verification integrity end-to-end, typed-acceptance seam, progress-aware correction termination), with distributed cycle execution, correction protocol with checkpoint/resume, maintainer-only cycle replay, Postgres persistence, LangFuse observability, Keycloak authentication, CLI tooling, test quality enforcement, and 7,900+ passing tests.

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
- **Distributed Execution** – RabbitMQ-based task dispatch across 6 agent containers

### Agent Framework
- **Agent Squad** – 6 agents: Max (Lead), Neo (Dev), Nat (Strategy), Bob (Builder), Eve (QA), Data (Analytics)
- **BaseAgent** – DI-enabled base class with full port injection (LLM, memory, queue, telemetry, filesystem)
- **Capability Contracts** – Declarative delivery expectations with acceptance checks (SIP-0058)

### Cycle Execution Pipeline (SIP-0064/0066/0068/0076–0080/0083)
- **Cycle API** – Create, monitor, and manage execution cycles via REST API
- **Task Planning** – Automatic task plan generation from PRD references
- **Dispatched Flow Executor** – Sequential task dispatch to agent containers via RabbitMQ
- **Gate Decisions** – Human-in-the-loop approval gates between pipeline stages
- **Artifact Management** – Typed artifact ingestion and retrieval per run with promotion model
- **Build Capabilities** – Agents produce executable source code, tests, and config from plans (SIP-0068)
- **Pulse Verification** – Cadence-bounded checks at pipeline boundaries with bounded repair loops (SIP-0070)
- **Assembly** – CLI command to assemble build artifacts into a runnable project directory
- **Workload Protocols** – Planning, implementation, and wrapup lifecycle with structured handoffs (SIP-0078/0079/0080)
- **Event System** – 25-event taxonomy with lifecycle bus and bridge subscribers (SIP-0077)
- **Correction Protocol** – Detect → RCA → decide → repair with durable checkpoint/resume (SIP-0079)

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

- **SIPs (SquadOps Improvement Proposals)** – ~98 protocol specifications in `sips/` directory (63 implemented, 8 accepted, 20 deprecated; drafts in `sips/proposed/`)
- **IDEA Documents** – 79 strategic ideas including Reasoning Telemetry Sharing, Squad Memory Pool, Observer Governance
- **Architecture Documents** – Design guides for agent implementations and handoff templates
- **Book Chapters** – 9 chapters covering methodology, implementation, and operations
- **Plans** – Implementation plans for major SIPs in `docs/plans/`
- **Retrospectives** – Run analyses and lessons learned (2025 WarmBoot era → cycle era; distilled in `docs/book/WARMBOOT_ERA_LESSONS.md`)
- **Protocols** – Testing, data governance, communication patterns

**Total Documentation**: ~84,000 lines across 260+ markdown files

---

## Repo Structure
```
/src/squadops/        # Core framework (hexagonal architecture)
├── ports/            # Abstract interfaces (secrets, db, comms, cycles, auth, telemetry)
├── agents/           # BaseAgent with DI, entrypoint, role definitions
├── capabilities/     # Capability contracts & workload runner (SIP-0058)
│   └── handlers/     # Cycle task handlers (strategy, dev, QA, data, governance, build, wrapup)
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
├── events/           # Cycle event bus, event types, bridge subscribers (SIP-0077)
└── core/             # Core utilities (SecretManager)
/adapters/            # Concrete implementations
├── secrets/          # env, file, docker_secret providers
├── comms/            # RabbitMQ adapter
├── persistence/      # PostgreSQL runtime
├── cycles/           # DispatchedFlowExecutor, MemoryCycleRegistry, PostgresCycleRegistry
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
/tests/               # Test suite (5,500+ tests)
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
squadops cycles create play_game --squad-profile full --request-profile build
squadops cycles show play_game <cycle-id>
squadops runs gate play_game <cycle-id> <run-id> plan-review --approve
squadops runs assemble play_game <cycle-id> <run-id> --out ./output
```

---

## Getting Started

Bootstrap a fresh machine with one command using a [bootstrap profile](docs/GETTING_STARTED.md):

```bash
./scripts/bootstrap/bootstrap.sh dev-mac      # macOS
./scripts/bootstrap/bootstrap.sh dev-pc       # WSL2 / Ubuntu
./scripts/bootstrap/bootstrap.sh local-spark  # DGX Spark (GPU)
```

Then verify and start working:

```bash
squadops doctor dev-mac                       # Validate environment
squadops login                                # Authenticate via Keycloak
squadops cycles create play_game --squad-profile full --request-profile selftest
```

See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for full setup instructions, profile details, and troubleshooting

---

## Development Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full release timeline.

**Current**: v1.7.1 — **Stack Seams**, the first patch line of 1.7 above **the Reasoning line** (v1.7.0), opening the odd-minor stabilization above **the Authorship release** (v1.6.6), the even minor above 1.4's Verified Canonical App Build (v1.5.0: stabilization — promises finished, structure extracted, feature-free verified). Dual-lane headlines: **SIP-0103 Squad-Authored Manifest** (Lane M, implemented at the cut) — the manifest-authoring framing stage with schema and winnability gates in-cycle, the question-gated manifest review (#807), the revision loop that answers a review note by restoring the unaffected prefix and re-running from the technical design (#811), gate decisions that name who decided (#812), and system-owned authoring provenance excluded from the canonical projection (M5/#803) — and **Generalized Build Capability** (Lane S): the per-stack surfaces consolidated into `ScaffoldStack` (S1), the second stack `nextjs_ts` landed, and **SIP-0105 Stack Blueprint Contract** accepted 2026-08-17 with its unbuilt parts named. Exit evidence, pre-registered and unfiltered on frozen deploys: the **V7 authored-mode FAY window — amended 4/6 functional, bar ≥4/6 MET** (dual record: 3/6 under the pre-registered audit instrument, 4/6 after the owner-ruled instrument correction #1004/#1005 — both numbers always reported), zero manual interventions across all launches; and the **V38 model-comparison window** (qwen3.8:27b): 4/6, equal yield at roughly half wall-clock, failure classes shifted toward framing-rooted contract violations — the gates that catch them are the 1.6.1+ queue (#1013, #1014, #1015, #1012). Records: `docs/plans/1-6-0-v7-fay-window-record.md`, `docs/plans/1-6-0-v38-window-record.md`. **v1.6.3 — the measurement patch line**: failed-task emissions persist for triage (#971), a truncated emission is caught at the task that wrote it (#1082), and the boot-audit oracle judges a contract with the same code as the in-cycle runner (#1079). Its evidence is a pre-registered 8-roll set on a frozen deploy — **5/8 functional**, 8/8 booting, **zero framing re-rolls** across ten consecutive cycles (the 1.6.2 success-status work, measured). Record: `docs/plans/1-6-3-repeatability-set-record.md`. **v1.6.4 — the self-consistency patch line**: every fix is the framework deriving one declared fact two ways and the renderings disagreeing — the frozen model typed entity fields as `string` (#1096), the store exported tables no correct app writes (#1087), contract probes never checked a response body (#1079 producer), per-file compile criteria superseded each other in the ledger (#1021), a fill could contradict the element kind the floor pins (#1094), and the repair target was the whole application in 18 of 18 rounds (#1015-A). Evidence: a pre-registered 8-roll set on frozen deploy `5a697dfa` — **8/8 functional, 14/14 criteria every roll, zero framing re-rolls** (eighteen consecutive), every exercised prediction held, P1/P3/P5 unexercised; the correction loop recovered 2 of 2 **by fallback, not by repair**, and three of eight qa emissions hit the completion cap. Record: `docs/plans/1-6-4-verification-set-record.md`. **v1.6.5 — the qa-emission patch line**: fills first, a qa-only completion budget, the self-eval merges fills, a qa repair reaches a fill, one home for the success-status default (#772), a qa-side failure never empties the dev repair target (#1120), the verification-set driver promoted. Evidence: the first two-stack pre-registered set on frozen deploy `7ebdb00e` — **Next.js+TS 6/6, zero correction rounds, zero cap hits; FastAPI+React 2/6 as a first baseline**, every prediction held on both. Record: `docs/plans/1-6-5-verification-set-record.md`. **v1.6.6 — the React-arm patch line**: the nullable-field emission (#1125), the harness cleanup (#1127), the passing retest stored (#1111), a stack-aware self-mocking check (#1126), a refused patch not counted as a round (#1129), one request-body resolver (#1128). Evidence: a second two-stack pre-registered set on frozen deploy `e14a6ad4` — **FastAPI+React 4/6 (two by repair, none by re-dispatch), Next.js+TS 2/2**, every prediction held where exercised; both rejections are the free-authored-assertion class (#1153 #1130 #1123). Record: `docs/plans/1-6-6-verification-set-record.md`. **v1.7.0 — the Reasoning line opens**, the odd-minor stabilization above 1.6's Authorship release. The measured pack is Reasoning: the model's thinking channel becomes a declared, observable, controllable thing rather than a paid-for side effect — a per-capability reasoning level on the port with a cycle-level override (#927), the thinking text captured and emitted to LangFuse on every adapter and, after #1194, on the streaming path every handler actually calls (#410), the emission log reporting the reasoning split (#924), an unregistered model failing loudly on all three paths (#1145), and a boot log that names a fallback as a fallback (#930). The CI-truth rider closes the gap beneath it: the deployed images and CI stop testing different dependency sets — 42 divergences down to 2, both documented with reasons — and every container moves to Python 3.12 (#1041, #237). Evidence is a two-stack shakeout pair on frozen deploy `bbf42f8d` with zero code drift between the deploy and the tag: **Next.js+TS 15/15 and FastAPI+React 15/15, both accepted, zero correction rounds, both boot audits PASS**. The line's honest record is that it took six rolls to get there — five rejections across four distinct causes, every one a real defect the shakeouts surfaced and all but one now fixed. What this cut does *not* cover is stated in `docs/plans/1-7-0-cut-record.md` §2, not implied: `.ts` emissions have no unresolved-name guard (#939, declared in the typed-check menu), dev repairs on nextjs_ts still cannot be verified where their toolchain is absent (#1221), and LangFuse holds roughly three-quarters of generations (#1206). Atlas is **not adopted** — the A/B returned a negative and SIP-0106 stays accepted with its open phases named.  **v1.7.1 — Stack Seams**: typed checks execute in the producing role's container at emission and at repair (rule B, #1229), each image provisioning its toolchain as data; `undefined_names` reads `.ts`/`.tsx`/`.js`/`.jsx` (#939); the assertion-kind gate (#1153), DOM-anchor enforcement (#668), additive-suite containment (#1022) and the case-scoped qa repair (#1123) close the free-authored-assertion class the 1.6.6 record named; the qa-owned defect routes to the qa role (#1130); packaging findings are reported (#598); stack #1 moves behind the stack seam (#1131). Evidence: a pre-registered two-set run on frozen deploy `f85de47a` with zero code drift to the tag — **FastAPI+React 3/5 (the sixth withheld by the early-stop rule: R2 falsified on the JavaScript own-frame shape, #1270), Next.js+TS 0/2**, the delivered app passing the boot audit on all seven rolls; rule B live on every one of eleven repairs, the kind gate refusing three contradicting repairs. The non-greens are one new thing and four old ones: the qa role's first-attempt emission became a sentence of intent and nothing else on the 1.7.0 tree (first seen 2026-08-31, zero in 1.6.6; #1268, the top of 1.7.2), and it reached four pre-existing recovery-path seams for the first time (#1269, #1271, #1273, plus #1272). Record: `docs/plans/1-7-1-verification-set-record.md`. Next: 1.7.2 — Loop Honesty, opening with #1268.

---

## Current Status
**Framework Version**: 1.7.1
**Development Status**: Verified canonical app build (SIP-0098/0099/0100/0102 golden-path arc: contract-owned acceptance, deterministic scaffolding, frozen-file enforcement, sandbox audit) with complete verification-evidence integrity (SIP-0096: earned verdicts, disclosed waivers, inert detection) on stabilized multi-agent orchestration (post-SIP-0097 decomposition, extended by the 1.5 extraction of context assembly, planning, and typed-check governance into declared registries) with the Agent Runtime State platform (SIP-0089: runtime modes, duty scheduler, FocusLease, RuntimeActivity), console UI, distributed cycle execution, multi-run cycle orchestration, workload protocols (planning → implementation → wrapup), cycle event system, correction protocol with checkpoint/resume, maintainer-only cycle replay (SIP-0101 minimum slice), agent build capabilities, Prefect task-scoped log streaming, durable persistence, authentication, CLI tooling, profile-driven bootstrap, test quality enforcement, and full observability stack.

### Project Statistics
*As of 2026-09-01 (v1.7.0):*
- **~61,000 lines** of Python source code (src + adapters)
- **~88,000 lines** of test code
- **~119,000 lines** of documentation
- **7,900+ tests** passing in regression suite
- **~98 SIPs** (64 implemented, 7 accepted, 20 deprecated; proposals/drafts in `sips/proposed/`)

### Functional Components
- 6 Agents: Max (Lead), Neo (Dev), Nat (Strategy), Bob (Builder), Eve (QA), Data (Analytics)
- Cycle Execution API with runs, gates, and artifact management (SIP-0064)
- Distributed flow execution via RabbitMQ (SIP-0066)
- Postgres-backed cycle registry with migrations (SIP-0067)
- Workload protocols: planning, implementation, and wrapup lifecycle (SIP-0078/0079/0080)
- Cycle event system with 25-event taxonomy and bridge subscribers (SIP-0077)
- Correction protocol: detect → RCA → decide → repair with checkpoint/resume (SIP-0079)
- Multi-run cycle orchestration with auto-gate and workload forwarding (SIP-0083)
- Workload & gate canon with artifact promotion model (SIP-0076)
- LangFuse LLM observability with cross-process trace linking (SIP-0061)
- Keycloak OIDC authentication with JWT middleware and audit logging (SIP-0062)
- CLI for cycle management with cycle request profile contract packs (SIP-0065)
- Capability contracts with declarative acceptance checks (SIP-0058)
- Task planning with automatic task flow generation (plan + build modes)
- Agent build capabilities: source code, tests, and config generation (SIP-0068)
- Builder role: dedicated product builder agent (SIP-0071)
- Stack-aware development capabilities with file classification (SIP-0072)
- LLM budget and timeout controls with prompt guard (SIP-0073)
- Pulse verification at pipeline boundaries with bounded repair loops (SIP-0070)
- Assembly CLI command for extracting build artifacts into runnable projects
- LLM router abstraction with Ollama adapter
- LanceDB semantic memory (SIP-042)
- OpenTelemetry with trace correlation
- Console Control-Plane UI with Continuum plugin shell and auth BFF (SIP-0069)
- Profile-driven bootstrap with doctor validation (SIP-0081)
- Time budget awareness across cycle execution (SIP-0082)
- Prompt registry integration for versioned prompt management (SIP-0084)
- Console messaging capability for operator ↔ squad communication (SIP-0085)
- Test quality enforcement: AST linter blocking in regression suite
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
