# Changelog

All notable changes to SquadOps are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [Unreleased]

## [1.3.1] — 2026-07-08

Hardening patch on the 1.3.0 stabilization line — the post-1.3.0 batch surfaced by
the 2026-07-04 independent health assessment, reassigned to the Macbook lane while
Spark was offline. All fixes; no feature SIPs (patches land on either lane anytime,
independent of the even/odd feature parity — #281). Every runtime-affecting change
was live-validated on the deployed stack before merge.

### Security
- **Agent-status writes moved off the unauthenticated `/health` lane (#326).**
  `POST/PUT /health/agents/status` were writable by any anonymous network client
  (the auth middleware allowlists the whole `/health` prefix). They now live at
  `POST/PUT /api/v1/agents/status` behind the `agents:write` scope; `/health/*`
  keeps only GET probes. The middleware allowlist is now **method-scoped**
  (GET/HEAD), so a future write route under `/health` fails closed instead of
  riding the no-auth lane. Agents authenticate their heartbeats via a new
  `squadops-agent` service identity (client credentials, `agent` realm role ⇒
  `agents:write` only); a half-configured identity raises at startup rather than
  silently sending anonymous heartbeats.

### Fixed
- **Concurrent same-agent cycles no longer bypass FocusLease arbitration (#288).**
  `RuntimeCoordinator.request_transition` short-circuited every same-mode request
  to `idempotent_skip` before arbitration, so a second cycle recruiting an
  already-recruited agent free-rode the first run's lease and lost the agent when
  the first finalized. A same-mode request from a *different* lease owner now
  rejects with `focus_lease_conflict` (admission defers the run); a same-owner
  replay still skips.
- **QA agent image now has Node.js so the frontend build check runs (#306).** The
  `qa.test` frontend build check (#290) and vitest shelled out to `npm`/`npx` in an
  image with no Node — every frontend check silently skipped, so a non-building
  frontend shipped green. Node ships in the qa image only (the sole Node consumer),
  declared via a config-driven per-role `system-packages.txt` (the apt analog of the
  existing per-role `requirements.txt` — no role name hardcoded in the Dockerfile).

### Added
- **Broker-hygiene check in `squadops doctor` (#328).** A new `broker` category
  flags queues on the retired pre-SIP-0094 `cycle_results_*` naming scheme and any
  queue holding messages with no consumer (an undrained backlog). Reads queue stats
  via `rabbitmqctl` inside the container (resolved from the compose service name, no
  credentials); an unqueryable broker warns rather than fails. The orphaned
  `cycle_results_*` queues left by the SIP-0094 migration (one with 48 undrained
  messages) were swept.

### Docs & SIP lifecycle
- Filed the **Externalized Build Sandbox** proposal (`sips/proposed/`) — the
  principled long-term home for build/test execution (a `BuildSandboxPort` so agents
  carry no toolchain), with #306 as its interim. Stays `proposed`.

## [1.3.0] — 2026-07-08

First **stabilization release** on the even/odd minor cadence (#281): odd minors are
feature-free by rule, and the big risky structural refactors quarantined out of the
feature releases are the *product*. Spark was offline for this cycle, so the entire
core scope landed from the Macbook lane. Every structural change below was
live-validated on the deployed stack before merge.

### Changed
- **SIP-0097 Dispatched Flow Executor decomposition (#186, #295).** The 3,358-line /
  53-method executor god-object decomposed to 1,805 lines across six sliced PRs
  (#341, #344, #347–#350), extracting five plain injected collaborators: pure hoists,
  **`RunLedger` + `RunCompletion`** (append-only run evidence + terminal-outcome
  mapping — the executor now carries **zero per-run mutable state**, and
  `RunCompletion.finalize(ledger, …)` is the seam SIP-0096 §6.4 wires into),
  **`CorrectionRunner`**, **`PulseBoundaryRunner`**, and **`TaskDispatcher`** (the
  interim dispatch callables were replaced by the real collaborator per AC#9). Slice
  6 carried the arc's one behavior addition (#295): the plan-review gate validates
  the run's materialized implementation plan against the squad profile *before*
  pausing — completing SIP-0095's materialized-plan half. SIP-0097 accepted (PR #340)
  and **promoted to implemented** within this release.
- **`cycle_tasks.py` split into the `capabilities/handlers/cycle/` package (#152).**
  The 3,276-line handler monolith is now per-handler modules behind a compat shim
  (PR #339), preceded by hoisting its copy-pasted helpers into `_CycleTaskHandler`
  (#332, PR #338). Shim retirement rides the importer migration filed in #339.
- **Agent comms migrated from queue polling to a persistent push consumer (#323,
  PR #354).** The entrypoint's 1s open/close `consume()` poll is gone; agents hold
  one long-lived `subscribe()` consumer (delivery-time pickup, `prefetch_count=1`,
  ack semantics unchanged). Removes the consumer-count flapping, up-to-1s dispatch
  latency, and the `aio_pika` "closing" INFO flood that was 99.7% of retained agent
  logs — which also closed #329 (the interim log-demotion mitigation) as obsolete.
- **Dead sqlalchemy `DbRuntime` backend removed (#234, PR #356).** Audit found zero
  production callers (its factory was only ever constructed by its own tests, and
  the one production breadcrumb referenced a method that never existed).
  `src/squadops/ports/` now contains no vendor types in any contract; the `postgres`
  extra and sqlalchemy test pin are dropped. Every active persistence path is asyncpg.

### Fixed
- **Prompt-pack drift broke `merge_plan` fleet-wide (#327, PR #351).** Agents resolve
  prompts from the LangFuse registry, which was seeded once and never re-synced —
  SIP-0093's templates were missing at runtime though the files shipped in the image.
  Deploys now re-sync prompts to LangFuse (production label) as a pipeline step; the
  manifest loader hard-fails on hash mismatch (was warn-and-continue); the regen tool
  maintains the whole-manifest hash; CI guards manifest integrity. Design-debt
  follow-ups filed: #352 (registry runtime guard), #353 (build-time fingerprint).
- **`runs resume` insta-failed since 1.1.1 (#342, PR #343).** The resume route
  pre-flipped the run to RUNNING and the executor then re-issued an illegal
  RUNNING→RUNNING transition — every resume died in ~2s. Found by SIP-0097 slice-2
  live validation; pause→resume→complete now verified live end-to-end (closed #258).
- **Test suite is color-env-proof (#345, PR #346).** Shells exporting `FORCE_COLOR`
  broke CLI output assertions (rich token-splits digits under forced color); all
  assertions now ANSI-strip first.

### Added
- **CI docs-drift guards (#336, PR #357).** Version markers across
  CLAUDE.md/README/ROADMAP must equal `pyproject.toml` (this release's bump is the
  first it enforces), accepted-SIP `Targets:` lines must respect even/odd parity,
  and planning-doc references must resolve — lifecycle-aware, with the historical
  residue frozen in an explicit allowlist.

### Docs & SIP lifecycle
- **SIP-0096 Verification Evidence Integrity accepted** (PR #337, rev 2) — the 1.4
  headline alongside SIP-0091; execution plan in `docs/plans/1-4-evidence-arc-plan.md`.
- **SIP-0095 promoted to implemented** (PR #324); SIP-0091's stale `Targets: v1.3`
  remapped to v1.4 per the parity rule (#335).
- **Docs hygiene pass (#335, PR #357):** ROADMAP stats/tables reconciled (they were
  frozen at 1.0.6), Forward Cadence section added (1.3 → 1.4 → 1.6 → 2.0 pillar map),
  referenced-but-untracked drafts committed (Edge Deployment Profile, Experiment
  Queue), and a registry entry pointing at a never-committed file removed.
- **Drafts filed** (proposed, not accepted): Agent Comms Delivery Guarantees
  (PR #355 — Campaign 1.6 gate candidate), Campaign SIP revision + two-lane/evidence
  plans (PR #325).

### Deferred / follow-ups
- **#288** (same-mode lease bypass — a named Campaign 1.6 gate) slipped this release;
  pulled forward into the 1.4 window as hardening.
- **#331** (`planning_tasks.py` split) and **#333** (entrypoint config-masking
  fallbacks) → 1.5 stabilization backlog.
- SIP-0097 post-arc open questions (residual-method review / optional seventh
  collaborator; `RunOrchestrator` rename + #168 sweep) are standalone follow-ups.

## [1.2.0] — 2026-07-04

First **feature release** on the even/odd minor cadence (#281): even minors carry
features, gated by headline feature SIPs. 1.2.0 is led by three — the SIP-0089
runtime-arc completion, the SIP-0090 Agent Embodiment Substrate (Phase 1), and the
SIP-0095 Cycle Create Preflight — riding a hardening base (#158, #231). Two lanes
fed it: features from the Macbook lane, hardening + supporting decisions from Spark.

### Added
- **SIP-0090 Agent Embodiment Substrate — Phase 1 (core model).** The internal
  substrate for embodied agents: an `Embodiment` lifecycle state machine
  (`unattached→attaching→attached→desynced→reconnecting→detached`) with an explicit
  transition allow-list and a single-active-embodiment-per-agent invariant (enforced
  both in code and by a Postgres partial unique index); resource budget primitives
  (attention/compute/action consumables + a concurrency capacity gauge, with
  non-silent exhaustion made type-unrepresentable); an `EmbodimentStatePort` with a
  Postgres adapter; and an `EmbodimentCoordinator` that validates transitions and
  emits canonical events. No adapter yet — Discord/browser embodiments are later
  phases (#312, #317).
- **SIP-0095 Cycle Create Preflight.** A create-time fail-fast gate: a cycle is
  rejected (HTTP 422 `PREFLIGHT_REJECTED`) when the squad can't satisfy the requested
  workloads' required roles, or names a model definitively not pulled (exact
  canonical-tag match, no family inference). An unreachable LLM backend
  warns-and-allows rather than blocking on missing evidence; warnings surface on the
  create response and in the CLI. `squadops doctor` gained model-availability parity
  via the same shared decision (#298, #309, #311, #315, #321).
- **SIP-0089 runtime-arc completion.** Cycle recruitment now routes through the
  RuntimeCoordinator with FocusLease arbitration (a lease conflict is a deferral, not
  a failure) (#233), and coordinator transitions commit lease + activity + mode in a
  single `RuntimeTransaction` unit of work with live-validated rollback (#244).
- **Validated-fullstack request-profile** — instrumentation + builder + stack for
  end-to-end framework validation (#279).

### Changed
- **Health signal consolidated to a single source of truth (#231).** `runtime_status`
  is now the canonical health signal across every read surface (API single + list
  routes, CLI, both console plugins); it is always-populated (the heartbeat ensures
  the runtime row and reconciliation backfills legacy agents), and the
  `runtime_status || network_status` fallback is gone. `network_status` is demoted to
  a deprecated back-compat field (column drop tracked separately) (#302).
- **Squad profiles consolidated to `smoke` / `lite` / `full`** (#173).

### Fixed
- **CLI now renders cycle-route error messages (#319).** They were nested under
  FastAPI's `detail` and silently dropped — the operator saw `validation failed —`
  with no reason (e.g. the preflight's actionable "pull model X"). Found via live
  cycle validation (#320).
- **Operational hardening (#158)** — configurable adapter timeouts + a DDL↔model
  drift guard; the `_schema_migrations` applier remains idempotent.
- Local-spark bootstrap models reconciled with the squad profiles (#285); QA-harness
  robustness + portable-frontend build fixes (#303, #296, #280).

### Deferred / follow-ups
- SIP-0095's materialized-plan capability check at the plan-review gate (#295) —
  deferred to land with the #186 executor decomposition; the dispatch-time check
  remains the net.
- SIP-0090 Phase 1 budget persistence + composition-root wiring — no live consumer
  until Phase 2 (Discord).

## [1.1.1] — 2026-06-29

Hardening patch on the 1.1.0 runtime line. The runtime lane (SIP-0089) was
live-validated end-to-end after 1.1.0, surfacing two regressions the unit
suites couldn't catch (#270, #272); both are fixed here alongside the resume
and reliability work from the 1.1.x hardening plan. No new SIPs — the additive
items are backward-compatible and the one rename (#79) is internal.

### Added
- Per-role Prefect task names: tasks render as `{role} [{n}/{total}]: {title}`
  so a role appearing multiple times in a plan is distinguishable in the
  Prefect UI (#94).
- Agent **`mode`** and **`runtime_status`** are now surfaced on the agent-list
  API and the console agent view, alongside the heartbeat fields — health is
  `runtime_status`, posture is `mode` (see
  `docs/agent-runtime-status-model.md`) (#230, #231).

### Fixed
- **Auth:** cycle API routes returned 403 for every authenticated user — #150
  applied `cycles:read`/`cycles:write` scope checks, but the role-centric
  Keycloak realm issues *roles*, not those scopes. Bridge realm roles to their
  implied scopes in `resolve_identity` so role-bearing tokens authorize as
  intended (#270).
- **Duty scheduler:** duty windows never auto-opened under the default
  `missed_window_policy="skip"` — the poll-cadence lag before the first
  observing tick was misread as a missed window. A just-active window is now
  treated as on-time within one poll interval (plus jitter margin) (#272).
- **Resume:** a duty-deferred run is now re-attempted *and* actually
  re-executed on resume — the resume route never re-invoked the executor
  before (#222).
- **Resume:** mid-sequence runs resume at the correct workload index instead of
  re-running from workload 0 (#257).
- **Comms:** `publish()` now retries with bounded backoff across the RabbitMQ
  reconnect window instead of failing the first send after a drop (#245).
- **Capabilities:** strip `<think>` blocks before fenced-code parsing, and log
  the raw output on zero extraction so empty parses are diagnosable (#130).
- **CLI/API:** `runs retry` now actually executes the run (it previously
  no-op'd); corrected stale docstrings (#133, #205).
- **Telemetry:** the `BrokenExporter` test no longer leaks a global OTel
  provider into sibling tests (#239).

### Changed
- Renamed the `governance.establish_contract` capability → **`governance.define_done`**
  and its `run_contract.json` artifact → **`definition_of_done.json`** (the fields
  are a standard Definition of Done, not a "contract"). Internal rename, no
  behaviour change; historical artifacts on disk are left as-is (#79).

### Internal / tooling
- Regression suite runs in parallel via `pytest-xdist -n auto` (#216).
- `update_sip_status.py` now rewrites the body `**Status:**` line on promotion,
  not just the frontmatter (#253).
- Deduplicated three copies of the JSONB-parsing helper into one (#156); routed
  the dispatched-flow factory through `create_workflow_tracker` (#250); corrected
  stale flow-executor references in the control-plane context doc (#168).

## [1.1.0] — 2026-06-28

The v1.1 line ships the **Agent Runtime State** platform (SIP-0089) on top of a
hardened 1.0.x foundation. Per the release decision, "1.0.x hardening
completeness" was read as the foundational CI-trust + reliability arc (complete);
the remaining build-reliability work continues as the **1.1.x hardening plan**
(`docs/plans/1-1-x-hardening-plan.md`).

### Added — Agent Runtime State (SIP-0089, Phases 1–4)
- **Runtime modes** (`ambient` / `cycle` / `duty`) with a single-writer
  RuntimeCoordinator (D16) and an in-process duty scheduler that drives
  `ambient↔duty` transitions on a poll — the live central mode-writer.
- **Assignments & duty windows** (hard/soft strictness, pre/post reserve
  buffers) plus a cycle-recruitment reserve-buffer guard that defers a run
  rather than pull an agent into a hard-duty window.
- **FocusLease** arbitration — `granted`/`rejected`/`preempting`, the hard gate
  for an agent's primary attention. lease ≠ mode; a failed mode write rolls the
  lease back (no stranded leases).
- **RuntimeActivity** — an agent's current cycle task is observable
  (`running` → `completed`/`failed`), instrumented at the executor dispatch
  boundary; surfaced via `squadops agent activity <id>` and
  `GET /health/agents/{id}/activity`.
- Postgres migrations `1100`–`1130` (agent_runtime_state, agent_assignments,
  focus_leases, runtime_activities), each with single-active-row invariants.
- CLI: `squadops agent state`, `squadops agent activity`,
  `squadops assignment list|show|create`.

### Security
- Enforce `cycles:read` / `cycles:write` scopes on all cycle API routes
  (`require_scopes` was wired in SIP-0062 but never applied — any authenticated
  user could perform any cycle operation). No-op when auth is disabled (#150).

### Changed — 1.0.x hardening (CI-trust foundation)
- Dev and CI standardized on **Python 3.12** (production stays 3.11; build a
  3.12 venv to reproduce the gate) (#217).
- Regression gate now enforces `ruff format --check` and runs the adapter unit
  tests (#196, #207).
- Declared previously-transitive deps as optional extras: `sqlalchemy`
  (`postgres`) and `python-jose` (`auth`), and decoupled the core `DbRuntime`
  port so the `postgres` extra is truly optional (#206, #191).

### Fixed
- Cancelling a cycle/run now propagates to Prefect — the orphaned flow run is
  transitioned to CANCELLED instead of running on (#77).
- Stop in-place mutation of the frozen `HandlerResult` in the planning retry
  path (#155).
- RabbitMQ consume-loop channel recovery locked with regression tests (the
  spin-forever path was already fixed by SIP-0094; #146).
- Integration test config no longer drifts from the stack: env vars now override
  `test_config.env`, and creds match the deployed broker (#209).
- `test_pulse_check_e2e` repaired (event-loop seeding + stale-API drift) (#211).

### Known limitations (1.1.0)
- Cycle **recruitment does not yet acquire FocusLeases through the coordinator**
  — the lease gate is enforced at the coordinator, not at recruitment (#233);
  the coordinator's lease+activity+mode writes use best-effort compensation, not
  a single Postgres transaction (#244).
- A cycle **deferred by a hard-duty reserve window cannot be resumed** — the
  deferral is correct, but no checkpoint exists to resume from (#222).
- RuntimeActivity is emitted for **cycle tasks only** (executor-side);
  ambient/duty-handler activities are not yet instrumented.
