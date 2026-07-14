# IDEA: Getting to a Functional App — Current Obstacles and Resolution Roadmap

**Version:** 2 (revised after second-opinion review; v1 2026-07-14, same day)
**Status:** Idea / working strategy draft — graduates to a `sips/proposed/` draft if it survives review
**Evidence base:** six live cycles run 2026-07-14 on the Spark deploy
(`cyc_bc325a67417d`, `cyc_dafd6b5fe58c`, `cyc_7d2f505e5e8f` — group_run/lite;
`cyc_23c6d9a7363a` — play_game/lite; `cyc_b9be8be77b31` — group_run/full;
plus the `hello_squad` deploy smoke), the #374/#376 post-mortem, and the
second-opinion review of v1.

## North star and current state

The goal is a cycle that ends with a **functional app** — one that assembles,
boots, and does what the PRD says — not a cycle that ends `completed`. The
#376 lesson stands: those are different claims. No cycle to date has produced
an app that ran without manual intervention.

The day's headline finding: **almost nothing failed because an LLM wrote bad
application code.** Even 7b devs produced acceptable components; 27b devs
produced correct Vite/Router structure first try. What failed was everything
around the code. The roll-4 full-squad cycle sharpened this to a point: with
models removed as the weak link, a lint-clean plan and largely-correct code
*still* could not reach the builder — the remaining failures were environment
and correction policy, not intelligence.

> The system should not optimize for better code generation. It should
> construct a controlled software-delivery system around code generation.
> (Second-opinion review — adopted as the doc's thesis.)

## Obstacles, ranked by what actually blocks "app runs"

### O1 — The verification environment cannot execute what the contract advertises (blocking)

- **Toolchain locus mismatch.** #306's per-role `system-packages.txt`
  mechanism exists and works — but only the qa role declares Node/npm (added
  for #407 `frontend_build`). Meanwhile the #419/#420 seam hoist made every
  task evaluate its own typed criteria in its *own* container, and the #425
  vocabulary teaches plan authors that `node --check` is valid for *any*
  task. Demand went squad-wide; supply stayed qa-only. Live consequence
  (roll 4): every frontend dev task carried an unexecutable-but-blocking
  criterion (`command_spawn_failed`), and the run died at subtask 3 of 8 —
  bob never dispatched, third consecutive cycle stalled pre-builder.
  **Nothing reconciles what the safelist/vocabulary advertises against what
  each execution locus provides.**
- **Skip-as-pass** (#423): checks on unsupported syntax/extensions count as
  `passed: true` — 7 of 14 evaluations in `cyc_bc325a67417d` were free passes.
- **Failed runs are black boxes** (#427): terminal exceptions persisted
  nowhere; runtime-api application logging never reaches stdout. Failing
  typed-check evaluations persist no artifact (#114), so the C1
  evaluator-error metric misses exactly the events it exists to count.
- The `command_check_safelist` CRP key is declared but consumed nowhere
  (dead; superseded by the typed-tools direction below — delete it).

### O2 — Apps fail to assemble, not to compile (the #376 class)

Components are fine; the *app* doesn't build — missing entrypoints, files
that disagree about imports/paths, absent index.html, LLM-dreamed
Dockerfiles. One-shot generation has no mechanism guaranteeing cross-file
agreement, and the correction loop repairs code defects, not assembly gaps.

### O3 — Contract authoring: largely mitigated (evidence-backed)

Three of the day's cycles died or degraded on plan-authoring defects.
Mitigations landed in #421 + #425 and verified live: typed criteria survive
dispatch and evaluate at every seam; the safelist is single-sourced; the
vocabulary teaches allowed command forms; the authoring lint rejects
violations with corrective feedback. Post-fix: the 7b merger went 0/3 → 1
retry to converge; the 27b merger authored 6/6 safelisted commands, picking
the correct form per stack. Remaining tail: semantic check quality, and
schema-constrained decoding (Phase 5).

### O4 — Config coherence traps

- Planner offers `builder.assemble` off *squad composition*;
  `generate_task_plan` gates off *resolved config* `build_profile` (#426) —
  plans that pass the gate and are dead at implementation start (8ms failure,
  found live).
- Plan-merge exhaustion silently downgrades `typed_acceptance: true` cycles
  to untyped static steps (#424).

### O5 — Repair policy and outcome honesty (mostly landed, tail remains)

SIP-0096's `blocked_unverified` verdict worked honestly in every failed cycle
today. New tail found in roll 4: the correction analyzer classified a failure
as `execution` (environmental) and still chose the `patch` path — burning
budget on a failure patches cannot fix, inconsistent with its own `continue`
decision on the identical class earlier in the same run. **Classification
should constrain path**; environmental failures should arguably not consume
correction budget at all (couples to #423's polarity redesign).

## Architecture: three contracts, not one bundle

v1 proposed "build profile = skill pack." The review correctly split this
into three independently-declared contracts (shippable together, reasoned
about separately):

1. **Build Environment Contract** — what the runtime must provide: required
   executables/versions, package managers, env vars, network policy,
   sandbox permissions, supported verification commands. Validated at
   **preflight**: Node absence becomes a preflight failure, never a
   task-time discovery.
2. **Stack Blueprint** — the deterministic shape of the application: scaffold
   expander, file topology, entrypoints, package manifests and scripts,
   import/path conventions, build/test commands, health endpoint, smoke
   hooks, a curated dependency catalog, stack-specific prompt guidance.
   Ownership rule: *the blueprint owns everything required for structural
   validity; agents own application-specific behavior and content.*
3. **Build Capability Pack** — agent-facing capability to implement and
   repair the blueprint: scaffold-population guidance, typed tool bindings,
   diagnostics interpretation, patch application, evidence collection.

### Decision (2026-07-14): the Environment Provider is an ephemeral app container

Rather than spreading app toolchains across agent images (rejected — it
conflates agent runtime with deliverable runtime, fattens every agent image
per stack, and couples agent rebuilds to app-stack drift), the environment
contract is satisfied by a **per-cycle, disposable app container**:

- The blueprint declares the app base image (and owns the Dockerfile —
  deterministic, never LLM-authored).
- A **workspace/execution service** owns container lifecycle: assemble
  workspace → instantiate app container → execute typed operations in it →
  capture evidence → destroy. Agents never touch a container runtime
  (no Docker socket in agent containers — root-equivalent, wrong shape).
- **Checks split by locus**: structural checks (regex/AST/file topology)
  stay agent-side — they read files. Executable and functional checks run in
  the app container: install, build, start, health probe, smoke path.
- Security posture improves: agent-side subprocess execution (today's
  `command_exit_zero`) shrinks; execution moves into a disposable,
  resource-limited sandbox.
- Accepted consequence: the #419 builder-seam live validation stays blocked
  until a minimal version exists. The stopgap (Node in dev/builder images)
  was considered and rejected — it would produce evidence about the wrong
  claim ("builds in an agent venv" ≠ "builds in an app-shaped environment").

## Three verification levels

`verified_functional` requires all levels; internal failure states stay
fine-grained (failed / unsupported / not-executed / timed-out /
infrastructure-error / invalid-check), even where several map to one
cycle-outcome bucket:

1. **Structural validity** — required files exist, imports/paths agree,
   manifests valid, dependencies declared. (Agent-side, deterministic.)
2. **Executable validity** — dependencies install, app builds, services
   start, health checks pass. (App container.)
3. **Functional validity** — required PRD behaviors exercised: route
   responds, expected element renders, critical user path succeeds. First
   browser probe deliberately narrow: start app, open root, assert no fatal
   console error, one required element, one critical path. (App container.)

## Roadmap

Ordering principle: speed is explicitly not the concern — each phase is
ranked by how directly it closes "cycle says done" vs "app runs." Phases
1A/2A interleave; the governing dependency is **"do not claim scaffold
success until verification truth exists"** — not "do not begin the scaffold
until verification is complete."

### Phase 0 — Freeze the golden benchmark

One frozen canonical challenge: one PRD (group_run), one expected app shape,
one stack blueprint, one environment image, one verification suite, one
model policy. Captures per-run: plan validity, scaffold completeness, typed
check execution, install/build/startup/health/smoke results, repair count,
elapsed time, manual-intervention count.

**Primary metric: Functional App Yield** — % of canonical builds reaching
verified-functional with zero manual intervention. Replaces cycle completion
rate as the number that matters.

### Phase 1A — Minimum verification truth

- #423 skip-as-pass polarity (unsupported → `unverified`, never `passed`)
- #427 terminal failure persistence + runtime-api logging
- Persist failing typed-check evaluation artifacts (#114)
- Build Environment Contract + preflight validation (advertised-vs-provided
  reconciliation; the roll-4 Node mismatch is the motivating case)
- Correction policy: classification constrains path (`execution` ⇒ never
  `patch`; environmental failures don't consume correction budget)
- #426 config coherence; delete dead `command_check_safelist`

### Phase 2A — Canonical stack blueprint (parallel with 1A)

One FastAPI + React blueprint owning deterministic topology, manifests,
entrypoints, integration seam, build scripts, test harness, health endpoint,
smoke hooks, dependency catalog. Scaffold publishes **ownership classes**
(framework-owned / extension-owned / shared / generated) so later agents
cannot erase its guarantees; a deterministic **assembly validator** checks
cross-file invariants (files exist, imports resolve, deps cover imports,
paths/ports agree) *before* any expensive build or repair loop.

### Phase 1B — Executable + functional verification against the scaffold

The ephemeral app container lands here: workspace/execution service,
frontend build, backend startup, health probe, first narrow browser smoke.
Expanded *against the canonical scaffold* rather than in the abstract.

### Phase 3 — Builder interactive convergence (bounded)

Typed, policy-controlled tools — `install_dependencies`, `build_frontend`,
`run_backend_tests`, `start_application`, `probe_http_endpoint`,
`read_build_diagnostics`, `apply_workspace_patch` — executing in the app
container via the workspace service. Not a shell, not a longer safelist: the
agent requests an operation; the platform decides how it is performed. Hard
limits: max repair attempts, max elapsed time, max patch size/file count,
workspace-scoped, no undeclared network, no mutation of scaffold-owned
files, complete tool-call evidence. Inner loop = "make this assembled app
build and run"; outer #413 loop = "change the plan when the approach is
structurally wrong." MCP is a candidate transport, not the capability
boundary. Known risk this pilot measures: local-model multi-turn tool-use
reliability.

### Phase 5 — Schema-constrained control artifacts

Plans, briefs, proposals, tool requests, correction decisions emitted as
schema-valid JSON (YAML rendered only where the repo contract wants it).
Not merely a YAML-quality fix: makes orchestration artifacts
machine-authoritative rather than prose interpreted by convention.

### Phase 6 — Model topology optimization (explicitly last)

Mixed-tier squads, role-specific budgets, routing by failure classification —
only after Functional App Yield is repeatably nonzero. Evidence to date:
tier delta concentrates in judgment (merge, correction analysis), not
generation; untested link is whether 7b devs consume the corrector's budget.

## Capability responsibilities (tempered from the review)

The review proposed six new capabilities. Adopt the responsibilities; resist
role proliferation on a single-GPU box — map onto existing structures:

| Responsibility | Home |
|---|---|
| Environment Steward | Preflight/doctor lane (environment contract validation), not a dispatched role |
| Integration Architect | **Elevated**: a framing-time *integration contract* artifact (API base path, route ownership, shared schemas, file-per-task ownership) — attacks cross-file disagreement even before the scaffold covers every case; authored under the lead role |
| Dependency Curator | The blueprint's curated dependency catalog (deterministic, not generative) |
| Build Diagnostician | Embodied in the builder initially; modeled separately so it can be benchmarked/rebound later |
| Functional Probe | Typed tools in the app container (Phase 1B/3) |
| Artifact Ownership Guard | Scaffold ownership classes + assembly validator (Phase 2A) |
| Evidence Curator | Existing evidence arc (SIP-0096 / #114); completeness, not judgment |

## Model policy (temporary experimental control, not settled architecture)

Until the canonical stack achieves repeatable functional completion,
benchmark runs use uniform `full` to remove model topology as a confounding
variable. `lite` remains the deliberate fault-injection profile for
control-plane and recovery testing; `smoke` for deploy-alive checks. PR
smokes exercise the changed surface. Larger models appear most valuable for
judgment, integration, and diagnosis; smaller models may suffice for bounded
implementation — Phase 6 tests this, not before.

## Release framing (aligns with the even/odd convention, #281)

- **v1.4 — Verified Canonical App Build** (feature): *one canonical
  application stack can be deterministically composed, executed, and
  honestly verified, without manual intervention.* Includes: Phase 1A truth
  fixes, environment contract + preflight, canonical blueprint + ownership +
  assembly validator, ephemeral app container + workspace service, bounded
  builder convergence, minimal executable + functional smoke, #426/#424
  coherence. Excludes: multi-stack generalization, broad browser automation,
  mixed-tier optimization, generic shell access, comprehensive
  schema-constrained generation.
  Acceptance: *given the canonical group_run brief and a supported `full`
  profile, SquadOps produces an assembled application that installs, builds,
  starts, passes declared health checks, and receives a verified functional
  outcome with zero manual file modification.*
- **v1.5 — Stabilization** (odd minor): repeated Spark campaigns against the
  benchmark, builder-loop reliability, failure-taxonomy refinement, evidence
  completeness, security boundary hardening, flaky-check elimination.
- **v1.6 — Generalized Build Capability** (feature): pluginized stack
  blueprints, reusable capability pack, a second canonical stack,
  schema-constrained control artifacts, stronger functional probes.

## Changes from v1 (for reviewers)

1. Three-contract separation replaces "build profile = skill pack."
2. **Ephemeral app container adopted as the Environment Provider** (user
   decision); per-role toolchain spread rejected; workspace/execution
   service owns container lifecycle.
3. Phases interleave (1A ∥ 2A → 1B) instead of strict serial.
4. Phase 0 golden benchmark + Functional App Yield added as primary metric.
5. Three verification levels defined; functional validity made first-class.
6. Typed build tools replace safelist expansion; RC-10a refined to "declared,
   bounded capabilities in an isolated workspace under explicit policy."
7. Assembly validator + scaffold ownership classes added.
8. Integration contract elevated to a framing artifact; other proposed
   capabilities mapped onto existing structures.
9. Roll-4 evidence added: full-squad cycle stalled pre-builder on
   environment + correction policy — the motivating case for 1A ordering.
10. New defect candidate: correction path must be constrained by failure
    classification (`execution` ⇒ never `patch`).

## Open questions

1. Where does the workspace/execution service live — inside runtime-api, or
   a dedicated container with the container-runtime socket (and what is the
   security story for that socket on the Spark box)?
2. Does the ephemeral app container run per-cycle (persistent workspace,
   faster) or per-verification (cleaner, slower)? Dependency caching policy?
3. Is the integration-contract artifact authored by the lead during framing
   (new artifact type) or folded into the implementation plan schema?
4. First browser probe: is a headless browser in the app container
   acceptable 1.4 scope, or does functional validity stop at HTTP probes
   until 1.6?
