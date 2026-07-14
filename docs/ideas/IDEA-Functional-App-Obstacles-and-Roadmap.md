# IDEA: Getting to a Functional App — Current Obstacles and Resolution Roadmap

**Version:** 3 (v1 + two second-opinion review rounds, all 2026-07-14)
**Status:** Working strategy — the sandbox design has graduated to
`sips/proposed/SIP-Externalized-Build-Sandbox.md` (now titled **Ephemeral
Application Sandbox**, evolved in place from the 2026-07-08 draft and
re-targeted from the 2.0 vision arc to v1.4); the scaffold was already
drafted as `sips/proposed/SIP-Contract-First-Build-Scaffolding.md`. This doc
remains the strategy umbrella over both.
**Evidence base:** six live cycles run 2026-07-14 on the Spark deploy
(`cyc_bc325a67417d`, `cyc_dafd6b5fe58c`, `cyc_7d2f505e5e8f` — group_run/lite;
`cyc_23c6d9a7363a` — play_game/lite; `cyc_b9be8be77b31` — group_run/full;
plus the `hello_squad` deploy smoke), the #374/#376 post-mortem, and two
review rounds.

## North star and current state

The goal is a cycle that ends with a **functional app** — one that assembles,
boots, and does what the PRD says — not a cycle that ends `completed`. No
cycle to date has produced an app that ran without manual intervention.

The day's headline finding: **almost nothing failed because an LLM wrote bad
application code.** What failed was everything around the code. Roll 4
sharpened this to a point: with models removed as the weak link (full 27b
squad, lint-clean plan, largely-correct code), the run still could not reach
the builder — the remaining failures were environment and correction policy,
not intelligence.

> The system should not optimize for better code generation. It should
> construct a controlled software-delivery system around code generation.

## Obstacles, ranked by what actually blocks "app runs"

### O1 — The verification environment cannot execute what the contract advertises (blocking)

- **Toolchain locus mismatch.** #306's per-role `system-packages.txt`
  mechanism works but only qa declares Node/npm. The #419/#420 seam hoist
  made every task evaluate its own typed criteria in its *own* container, and
  the #425 vocabulary teaches plan authors `node --check` is valid for *any*
  task — demand went squad-wide, supply stayed qa-only. Roll 4: every
  frontend dev task carried an unexecutable-but-blocking criterion
  (`command_spawn_failed`); the run died at subtask 3 of 8; bob never
  dispatched (third consecutive pre-builder stall). **Nothing reconciles what
  the safelist/vocabulary advertises against what each execution locus
  provides.**
- **Skip-as-pass** (#423): unsupported-syntax/extension checks count
  `passed: true` — 7 of 14 evaluations in `cyc_bc325a67417d` were free passes.
- **Failed runs are black boxes** (#427): terminal exceptions persisted
  nowhere; runtime-api app logging swallowed; failing typed-check
  evaluations persist no artifact (#114).
- Dead `command_check_safelist` CRP key — delete; superseded by typed
  operations (below).

### O2 — Apps fail to assemble, not to compile (the #376 class)

Components are fine; the *app* doesn't build — missing entrypoints, files
that disagree, LLM-dreamed Dockerfiles. One-shot generation has no mechanism
guaranteeing cross-file agreement; the correction loop repairs code defects,
not assembly gaps. Owned by **SIP-Contract-First-Build-Scaffolding**
(interface manifest → deterministic expander → walking skeleton → fill
fixed slots).

### O3 — Contract authoring: largely mitigated (evidence-backed)

Fixed by #421 + #425 and verified live: typed criteria survive dispatch and
evaluate at every seam; safelist single-sourced; vocabulary teaches allowed
forms; lint rejects with corrective feedback. Post-fix: 7b merger 0/3 → one
retry to converge; 27b merger 6/6 safelisted, correct form per stack.
Remaining tail: semantic check quality; schema-constrained decoding
(Phase 5).

### O4 — Config coherence traps

Planner offers `builder.assemble` off squad composition while
`generate_task_plan` gates off `build_profile` config (#426); plan-merge
exhaustion silently downgrades typed cycles to static steps (#424).

### O5 — Repair policy and outcome honesty (mostly landed; policy tail)

`blocked_unverified` reported honestly in every failed cycle. New tail from
roll 4, refined by review round 2: failure classification needs **two
dimensions** — **locus** (infrastructure / application / orchestration /
verification) × **mode** (syntax / build / startup / runtime / timeout /
unsupported / unavailable). *Infrastructure*-locus execution failures
(missing binary, container won't start) must never take the `patch` path and
must not consume application correction budget; *application*-locus execution
failures (app crashes, startup import error) are patchable and budgeted.
Roll 4's corrector took `patch` on an infrastructure failure it had itself
classified as environmental, burning the budget. (The earlier
"`execution` ⇒ never `patch`" rule was too absolute — locus is what gates
the path, not the word "execution.")

## Architecture: three contracts + the sandbox

Three independently-declared contracts (shippable together, reasoned about
separately):

1. **Build Environment Contract** — what the runtime must provide (tools,
   versions, network policy, sandbox permissions). **Preflight-validated**:
   advertised-vs-provided mismatches fail before dispatch (kills the O1
   class). The environment *definition* is the contract; Dockerfiles are one
   adapter rendering of it (deterministic, checked in, never LLM-authored).
2. **Stack Blueprint** — the deterministic application shape: scaffold
   expander, topology, entrypoints, manifests, build/test commands, health
   endpoint, smoke hooks, curated dependency catalog, ownership classes
   (framework-owned / extension-owned / shared / generated), plus a
   deterministic **assembly validator** (files exist, imports resolve, deps
   cover imports, paths/ports agree) that runs before any expensive build.
   *The blueprint owns everything required for structural validity; agents
   own application-specific behavior and content.*
3. **Build Capability Pack** — agent-facing: scaffold-population guidance,
   typed tool bindings, diagnostics interpretation, patch application,
   evidence collection.

### The Environment Provider: Ephemeral Application Sandbox (decided; SIP updated)

The Build Environment Contract is satisfied through an **ephemeral
application sandbox managed by a dedicated workspace/execution service** —
a cycle-scoped sandbox containing disposable **build**, **runtime**, and
**probe** execution units operating against a **persistent cycle workspace**.
(Refined from v2's "per-cycle app container": four separable concerns, one
sandbox; a single composed implementation is fine for 1.4, the contracts stay
separate.) Key rules:

- The execution service is the **only** holder of container-runtime
  authority; agents and runtime-api never get the socket. It exposes **typed
  operations with structured semantic results** (`build_frontend` →
  diagnostics/artifacts/ownership-hints, `start_application` → endpoint
  handles/readiness, …) — policy-bearing operations, not renamed shell.
- **Lifecycle hybrid:** persistent workspace per cycle; a **warm** execution
  unit may be reused within one bounded builder convergence attempt; **final
  executable/functional verification always runs clean-room** — a freshly
  provisioned environment against the persisted workspace. The verdict never
  depends on the dirty convergence container.
- **Probes run as peers** of the application runtime, never inside it
  (in-container probes hide port/binding/origin failures).
- **Dependency caching:** shared read-through download caches only; no
  shared installed deps; the clean-room build must succeed without
  undeclared workspace state; cache hits recorded, never semantic.
- Rejected alternative (user decision): spreading toolchains across agent
  images. Accepted consequence: the #419 builder-seam live validation waits
  for the sandbox's minimal version.

Full design, v1.4 scope split (contract-level-right vs
implementation-level-minimal), 15 acceptance-grade security requirements,
and migration: **`sips/proposed/SIP-Externalized-Build-Sandbox.md`**.

## Three verification levels

`verified_functional` requires all three; internal failure states stay
fine-grained (failed / unsupported / not-executed / timed-out /
infrastructure-error / invalid-check):

1. **Structural** — needs no application runtime. May run near agents for
   fast feedback, but **authoritative structural verification runs
   deterministically against the assembled cycle workspace via the
   verification service** (the trust boundary is the deterministic lane, not
   the agent).
2. **Executable** — dependencies install, app builds, services start, health
   passes. (Sandbox.)
3. **Functional** — the PRD's critical path exercised. First browser probe
   deliberately narrow: open declared URL, await readiness, assert one
   required element, one critical interaction, assert result, capture
   console + screenshot. **If the browser probe is descoped from 1.4, the
   outcome name honestly downgrades to `verified_executable`.**

## Roadmap

Ordering principle: speed is explicitly not the concern — rank by how
directly each phase closes "cycle says done" vs "app runs." Phases 1A/2A
interleave; the governing dependency is **"do not claim scaffold success
until verification truth exists"**, not "do not begin the scaffold until
verification is complete."

### Phase 0 — Freeze the golden benchmark

One frozen canonical challenge (group_run PRD, one blueprint, one environment
image, one verification suite, one model policy). **Primary metric:
Functional App Yield** — % of canonical builds reaching verified-functional
with zero manual intervention. Captures per-run: plan validity, scaffold
completeness, typed-check execution, install/build/startup/health/smoke,
repair count, elapsed time, manual interventions.

### Phase 1A — Minimum verification truth

#423 polarity; #427 failure persistence + logging; failing typed-check
artifacts (#114); Build Environment Contract + preflight (the roll-4
mismatch is the motivating case); locus × mode correction classification;
#426/#424 coherence; delete dead `command_check_safelist`.

### Phase 2A — Canonical stack blueprint (∥ 1A)

`SIP-Contract-First-Build-Scaffolding`: fastapi+react walking skeleton,
ownership classes, assembly validator, dependency catalog.

### Phase 1B — Sandbox executable + functional verification

The Ephemeral Application Sandbox lands here (execution service, canonical
environment image, typed ops, clean-room rule, HTTP + narrow browser probe)
— expanded against the canonical scaffold, not in the abstract. Includes the
deferred #419 builder-seam live validation as its closing evidence.

### Phase 3 — Builder interactive convergence (bounded)

Typed ops via the sandbox; warm unit within one bounded attempt; hard limits
(max attempts / elapsed time / patch size / changed files; workspace-scoped;
no scaffold-owned mutation; full evidence). Inner loop = "make this
assembled app build and run"; outer #413 loop = replanning. MCP is candidate
transport, not the capability boundary. The pilot measures local-model
multi-turn tool-use reliability before any wider commitment.

### Phase 5 — Schema-constrained control artifacts

Plans, briefs, proposals, tool requests, correction decisions as
schema-valid JSON (YAML rendered where repo contracts want it). Control-plane
integrity, not merely YAML hygiene.

### Phase 6 — Model topology optimization (explicitly last)

Mixed-tier squads etc., only after Functional App Yield is repeatably
nonzero.

## Capability responsibilities (tempered)

| Responsibility | Home |
|---|---|
| Environment Steward | Preflight/doctor lane (environment-contract validation), not a dispatched role |
| Integration Architect | A **first-class integration contract artifact** — own schema, identifier, validation, and revision semantics; authored under the lead during framing; consumed by the assembly validator, scaffold, builder diagnostics, and probes. For 1.4 it may physically ride the plan envelope as a schema-separated section |
| Dependency Curator | The blueprint's curated dependency catalog (deterministic) |
| Build Diagnostician | Embodied in the builder initially; modeled separately for later rebinding |
| Functional Probe | Typed ops in the sandbox's probe runner (peer of the app) |
| Artifact Ownership Guard | Scaffold ownership classes + assembly validator |
| Evidence Curator | Existing evidence arc (SIP-0096 / #114); completeness, not judgment |

## Model policy (temporary experimental control, not settled architecture)

Until the canonical stack achieves repeatable functional completion,
benchmark runs use uniform `full` to remove model topology as a confounding
variable. `lite` remains the deliberate fault-injection profile; `smoke` for
deploy-alive; PR smokes exercise the changed surface. Phase 6 tests whether
smaller implementation models suffice — not before.

## Release framing (even/odd convention, #281)

- **v1.4 — Verified Canonical App Build** (feature): headline = the sandbox
  SIP + scaffold SIP vertical slice. Acceptance: *given the canonical
  group_run brief and a supported `full` profile, SquadOps produces an
  assembled application that installs, builds, starts, passes declared
  health checks, and receives a verified functional outcome with zero manual
  file modification.* Includes Phase 1A truth fixes and #426/#424 coherence.
  Excludes: multi-stack generalization, broad browser automation, mixed-tier
  optimization, shell access, comprehensive schema-constrained generation.
- **v1.5 — Stabilization**: repeated benchmark campaigns, builder-loop
  reliability, evidence completeness, security hardening (rootless/socket
  proxy candidates), flaky-check elimination.
- **v1.6 — Campaign + Generalized Build Capability** (reconciled with the 1.4
  evidence arc, 2026-07-14): Campaign Orchestration (Lane M) alongside
  pluginized blueprints, reusable capability pack, second canonical stack,
  schema-constrained control artifacts, stronger functional probes (Lane S);
  SIP-0091 + SIP-0090 P2 ride here. Campaign gains the gate *Functional App
  Yield repeatably > 0*. See `docs/plans/1-4-evidence-arc-plan.md` (revised)
  for the governing arc.

## Changes from v2 (for reviewers)

1. "Per-cycle app container" → **ephemeral application sandbox**: four
   separable concerns (workspace / build / runtime / probe) under one
   cycle-scoped sandbox; probes as peers.
2. **Clean-room rule** added (the most important missing lifecycle rule):
   warm units only within a bounded convergence attempt; authoritative
   verdicts from freshly provisioned environments.
3. Environment *definition* is the contract; Dockerfile demoted to adapter
   rendering.
4. Execution service placed **beside** runtime-api (sole socket holder).
5. Typed operations must return structured semantic results.
6. Structural-check trust boundary corrected: agent-side = fast feedback;
   authoritative structural verification = deterministic service lane.
7. Correction rule refined from "`execution` ⇒ never `patch`" to **locus ×
   mode** classification (infrastructure failures never patch / never burn
   app budget; application execution failures are patchable).
8. Browser probe pulled into 1.4 — or the verdict honestly renames to
   `verified_executable`.
9. Integration contract elevated to a first-class artifact (may ride the
   plan envelope in 1.4).
10. Dependency caching policy added (read-through caches; never semantic).
11. **Discovered and reconciled with existing drafts:** the sandbox design
    evolved `sips/proposed/SIP-Externalized-Build-Sandbox.md` in place
    (re-targeted 2.0-vision → v1.4) rather than duplicating it; Phase 2A is
    owned by the already-drafted `SIP-Contract-First-Build-Scaffolding`.

## Open questions (carried by the sandbox SIP)

1. Execution-service transport + auth (vs the #326 service-identity pattern).
2. Workspace storage backend (bind-mount vs volume vs content-addressed).
3. Headless-browser image weight acceptable for 1.4, or HTTP-only +
   `verified_executable`?
4. Environment-image ownership and publish pipeline.
5. How much locus × mode taxonomy lands in the sandbox SIP vs a
   correction-policy follow-up.
