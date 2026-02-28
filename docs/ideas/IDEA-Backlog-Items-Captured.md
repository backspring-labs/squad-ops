# IDEA: Backlog Items (Captured from Conversation)

## Purpose
Capture backlog items before they are lost, separating **fixes** from **enhancements**, and refine them into implementation-ready ideas later.

## Status
Draft (captured + organized from conversation)

## How to use this doc
- Use as a backlog staging area before SIP/PRD creation
- Split items into execution plans, SIPs, or PRDs as they mature
- Revisit priorities/effort after current milestones

---

## Structured Backlog Items

### [IDEA-BLG-001] Fix agent role display and redesign deployed-agent listing status model
- **Type:** Fix (with follow-on Enhancement implications)
- **Area / Component:** Continuum / Svelte plugin (agent listing UI), squad runtime agent metadata display
- **Problem / Opportunity:** A newly added agent (Bob) displays as `N/A` for role in the console. This exposed hardcoded assumptions in the Svelte plugin agent listing logic and highlights a broader design gap in how deployed agents are presented for squad runs.
- **Current Behavior:** Agent list UI can show `N/A` for role when a new/unknown agent is present or when role mapping is hardcoded/incomplete. Online status and deployable availability semantics may also be unclear or not modeled consistently.
- **Desired Behavior / Outcome:** Console reliably shows deployed agents available for a squad run with accurate role labels and current online status using runtime/registry metadata rather than hardcoded UI assumptions. Unknown/missing metadata should degrade gracefully with clear fallback behavior.
- **Why this matters:** User-facing correctness issue and signal of brittle UI/data contracts. Accurate agent role/status visibility is important for trust, debugging, and pre-run readiness.
- **Scope (V1):**
  - Fix `N/A` role display bug for Bob
  - Remove/replace hardcoded role mapping in Svelte plugin agent listing (or centralize mapping contract)
  - Define display contract for deployed agents shown as available for squad runs (minimum fields: agent name/id, role, online status)
  - Add graceful fallback for unknown/missing role metadata
- **Out of Scope:**
  - Full agent lifecycle management redesign
  - Advanced presence/heartbeat visualization/history
  - Multi-cluster deployment topology views
- **Risks / Dependencies:** Runtime metadata contract may need tightening; plugin and runtime API shape may both require changes. Need clarity on authoritative source for role and online status.
- **Rough Priority:** High
- **Rough Effort:** M
- **Notes / Open Questions:**
  - What is the canonical source of truth for agent role (squad definition, deployment profile, runtime registration, agent self-report)?
  - How should “available for squad run” differ from “online”?
  - Do we need separate states (deployed, registered, healthy, idle, assigned, offline)?

---

### [IDEA-BLG-002] Improve console artifact listing scalability with grouping/folders
- **Type:** Enhancement
- **Area / Component:** Continuum console artifact panel / cycle artifact display UX
- **Problem / Opportunity:** Console currently lists all files as artifacts, including every generated code file. This will become noisy and hard to navigate on larger app builds.
- **Current Behavior:** Artifact view is effectively a flat list of files/outputs for a cycle, which can overwhelm operator workflows as output volume grows.
- **Desired Behavior / Outcome:** Console presents cycle outputs in a clearer structure (e.g., folders/groups/taxonomy) so operators can quickly inspect meaningful artifacts while still having access to all files when needed.
- **Why this matters:** Preserves artifact panel usefulness as cycle output scales; improves operator UX and reduces noise during run review.
- **Scope (V1):**
  - Introduce UI grouping/foldering for artifact display (without requiring immediate storage-model rewrite)
  - Distinguish at least curated/higher-value outputs vs raw generated files (or provide grouping/filtering)
  - Preserve access to “show all” file list
- **Out of Scope:**
  - Full artifact storage architecture redesign
  - Full provenance graph for every file
- **Risks / Dependencies:** May expose need for artifact taxonomy metadata; should avoid coupling a UI fix to a storage-layer rewrite.
- **Rough Priority:** Medium-High
- **Rough Effort:** M
- **Notes / Open Questions:** UI grouping only vs true artifact taxonomy? Group by path, type, or producing task/phase?

---

### [IDEA-BLG-003] Add console footer platform version and stale install/update-required indicator
- **Type:** Enhancement
- **Area / Component:** Continuum console footer / platform status UX
- **Problem / Opportunity:** Operators need quick visibility into platform version and whether the running install is stale after local code updates.
- **Current Behavior:** Footer status indicator does not clearly surface platform version or update/rebuild/reinstall requirement state.
- **Desired Behavior / Outcome:** Lower-right footer shows platform version inline with status indicator and can indicate when platform update has been detected and rebuild/re-install is required.
- **Why this matters:** Reduces confusion from version mismatch/stale builds; improves local testing confidence and troubleshooting speed.
- **Scope (V1):**
  - Display platform version in footer
  - Add non-blocking status badge/indicator for stale install or update-required state
  - Define version/build metadata contract source for footer display (at least one authoritative source)
- **Out of Scope:**
  - Full compatibility matrix or auto-update workflow
  - Blocking enforcement on version mismatch
- **Risks / Dependencies:** Requires clear version source-of-truth (UI build vs runtime version vs commit SHA); mismatch detection contract may require backend support.
- **Rough Priority:** Medium
- **Rough Effort:** S-M
- **Notes / Open Questions:** Show UI version, backend/runtime version, or both? Compare build hash, semver, timestamp, or commit SHA?

---

### [IDEA-BLG-004] Add CLI-driven platform rebuild/redeploy workflow for local device cycle testing
- **Type:** Enhancement
- **Area / Component:** CLI / local deployment workflow / platform ops DX
- **Problem / Opportunity:** Updating platform capabilities for local device testing currently depends on an AI assistant (Claude) to run rebuild/container redeploy steps. This adds friction and reduces repeatability.
- **Current Behavior:** Rebuild/redeploy is operationally possible but not streamlined for direct operator-triggered execution.
- **Desired Behavior / Outcome:** Operator can trigger platform rebuild/redeploy (and basic health validation) from terminal/CLI without needing an AI assistant.
- **Why this matters:** Improves iteration speed, determinism, and operational independence for laptop → Spark local testing workflow.
- **Scope (V1):**
  - Provide CLI command/workflow to rebuild and redeploy platform on local target device/profile
  - Run basic health/status checks post-deploy
  - Emit clear CLI output summary of success/failure
- **Out of Scope:**
  - Fully autonomous self-mutating platform updates
  - HA/production deployment automation
  - Advanced rollback orchestration (may be later phase)
- **Risks / Dependencies:** Depends on deployment target model (Compose/K8s/custom), version/build source-of-truth, service restart ordering, and health-check definitions.
- **Rough Priority:** High
- **Rough Effort:** M-L
- **Notes / Open Questions:** Build on laptop vs build on Spark? Push image vs pull source? Remote trigger from laptop to Spark?

---

### [IDEA-BLG-005] Design console slide-out terminal panel and unified operator interaction model
- **Type:** Enhancement (UX/DX + platform interaction design)
- **Area / Component:** Continuum console lower-left actions / terminal/chat/command UX
- **Problem / Opportunity:** Need a better way to run quick actions, invoke CLI methods, and chat with agents from the console without fragmenting the operator experience.
- **Current Behavior:** Action triggers, CLI methods, and chat capabilities are not yet unified in a carefully designed control surface; prior health-check dashboard had useful terminal/chat behavior.
- **Desired Behavior / Outcome:** Add a lower-left “Terminal” action that opens a slide-out panel and supports a deliberate interaction model balancing:
  - quick key-bound actions
  - CLI command execution
  - agent chat (any/all agents)
- **Why this matters:** Defines the operator control surface philosophy for speed, power, and flexibility while preserving safety and usability.
- **Scope (V1):**
  - Add slide-out terminal panel entry point in console actions
  - Define interaction modes (actions vs CLI vs chat) and initial UX boundaries
  - Support at least one useful execution path (e.g., CLI commands or curated actions) in-panel
- **Out of Scope:**
  - Full “god mode” shell with unrestricted platform mutation
  - Finalized multi-agent conversational orchestration UX across all use cases
- **Risks / Dependencies:** Requires clear command execution security model, transcript model, and distinction between safe actions vs privileged operations.
- **Rough Priority:** Medium-High
- **Rough Effort:** L
- **Notes / Open Questions:** Single transcript vs tabs/modes? Can chat invoke actions/CLI? What gets hotkeys vs command palette vs chat?

---

### [IDEA-BLG-006] Minimal Infra Bootstrap Mode with embedded adapters + Ollama for real Hello Squad runs
- **Type:** Enhancement (Architecture / platform profile strategy)
- **Area / Component:** Runtime profiles, ports/adapters, local bootstrap deployment, console infra tiles
- **Problem / Opportunity:** Full platform setup requires substantial infrastructure (Postgres, RabbitMQ, Prefect, Prometheus, Grafana, Redis, Keycloak, etc.), creating friction for onboarding and local iteration. Need the simplest truthful setup that can still run real agents and grow incrementally.
- **Current Behavior:** Platform assumes/benefits from full infra stack for a complete squad environment, making lightweight bootstrap runs harder.
- **Desired Behavior / Outcome:** Provide a minimal bootstrap mode that can run **Hello Squad with one real agent** using **Ollama** and embedded/local adapters while preserving platform shape (ports, tiles, contracts) and enabling incremental replacement with real providers.
- **Why this matters:** Dramatically improves onboarding, smoke testing, laptop/Spark iteration speed, and contributor accessibility without abandoning architecture discipline.
- **Scope (V1):**
  - Minimal runtime profile / deployment mode for Hello Squad (single agent supported)
  - Real LLM runtime via Ollama (required)
  - Embedded DB (e.g., SQLite) for core persisted data (tasks, comms, run/cycle metadata, basic metrics/events, artifacts)
  - Lightweight local orchestration loop (Prefect substitute)
  - Local comms transport substitute (in-memory or DB-backed queue semantics preserving comms contract shape)
  - Basic runtime API for console/CLI (health, run state, agent list/role/status, artifacts/events, limited actions)
  - Console tiles remain visible and indicate provider mode honestly (embedded/external/disabled/placeholder)
  - At least one real agent runtime process/container using Ollama + squad comms + task execution path
  - Simple local/dev auth mode (explicitly local-only or bypass mode)
  - Basic logs + event visibility for debugging bootstrap mode
  - Prefer one-command bootstrap CLI profile for startup and readiness validation
- **Out of Scope:**
  - Full replacement of production infra capabilities
  - HA/distributed scheduling
  - Full RBAC / Keycloak parity
  - Prometheus/Grafana parity in V1
  - Multi-agent production scaling guarantees
- **Risks / Dependencies:** Requires strong port contracts and provider capability status exposure; risk of bootstrap mode becoming a fake/demo shell if real agent execution and persistence semantics are not preserved.
- **Rough Priority:** High
- **Rough Effort:** L
- **Notes / Open Questions:** What is the minimum viable infra set for true SquadOps semantics? Which components are embedded vs placeholder vs disabled? What is the progressive provider replacement order?

---

### [IDEA-BLG-007] Explore hierarchical repo-like cycle data store representation (future architecture)
- **Type:** Enhancement (Deferred Architecture Exploration)
- **Area / Component:** Cycle data store / artifact storage model / artifact navigation APIs
- **Problem / Opportunity:** Flat artifact value storage may not scale well for larger builds and richer artifact navigation needs. A structured hierarchical representation (repo/tree-like) may better support console navigation, grouping, and provenance.
- **Current Behavior:** Cycle data/artifacts are represented as a flat store, which is simple but may become limiting as file volume and artifact complexity grow.
- **Desired Behavior / Outcome:** Evaluate a future move to a more structured hierarchical cycle data model while preserving upgrade path and compatibility where possible.
- **Why this matters:** Architectural pressure is already visible from artifact UI scaling concerns; capturing this now prevents losing the design signal while intentionally deferring the larger rewrite.
- **Scope (V1):**
  - Capture the architectural question and defer implementation
  - Optionally document evaluation criteria / triggers for when to revisit
- **Out of Scope:**
  - Immediate storage rewrite
  - Breaking artifact API changes in current cycle
- **Risks / Dependencies:** Large cross-cutting change touching storage APIs, console UX, provenance semantics, and migration strategy.
- **Rough Priority:** Low (now) / Strategic later
- **Rough Effort:** L-XL (future)
- **Notes / Open Questions:** UI grouping may solve near-term needs without storage rewrite; define triggers that justify moving to a repo-like model.

---

## Candidate Buckets

### Fixes
- [IDEA-BLG-001] Agent role display / deployed-agent role + online status contract redesign

### Enhancements
- [IDEA-BLG-002] Artifact list scalability (grouping/folders)
- [IDEA-BLG-003] Footer version + stale install indicator
- [IDEA-BLG-004] CLI rebuild/redeploy workflow
- [IDEA-BLG-005] Terminal panel + Actions/CLI/Chat interaction model
- [IDEA-BLG-006] Minimal Infra Bootstrap Mode (embedded adapters + Ollama)

### Tech Debt / Refactors
- [IDEA-BLG-007] Future hierarchical cycle data store exploration

---

## Triage Queue

### Ready to Spec Next
- [IDEA-BLG-001] Fix agent role display and redesign deployed-agent listing status model
- [IDEA-BLG-006] Minimal Infra Bootstrap Mode (embedded adapters + Ollama) for Hello Squad
- [IDEA-BLG-004] CLI-driven platform rebuild/redeploy workflow for local device testing

### Needs More Definition
- [IDEA-BLG-005] Console terminal panel + Actions vs CLI vs Chat interaction model
- [IDEA-BLG-002] Artifact grouping/folders in console (UI grouping vs artifact taxonomy)
- [IDEA-BLG-003] Version footer + stale install detection/version contract

### Parked / Future
- [IDEA-BLG-007] Hierarchical repo-like cycle data store representation

---

## Export Notes
This backlog IDEA can be split into:
- bugfix execution plans
- enhancement IDEA docs
- SIP candidates
- PRD candidates
