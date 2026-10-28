---
title: Ephemeral Application Sandbox
status: accepted
author: jladd
created_at: '2026-07-08T00:00:00Z'
updated_at: '2026-07-31T09:32:07.081680Z'
sip_number: 102
---
# SIP: Ephemeral Application Sandbox

*(Evolved from "Externalized Build Sandbox," same SIP — scope expanded from
build-job execution to the full application sandbox after the 2026-07-14
live-validation campaign and two second-opinion review rounds; see
`docs/ideas/IDEA-Functional-App-Obstacles-and-Roadmap.md` v3.)*

## Status
Accepted — **1.4 floor SHIPPED in v1.4.0 (2026-07-31, S-lane headline)**, SIP-0090-Phase-1 precedent: migration steps 1–2 complete (execution service + workspace provisioning + Docker adapter on `ContainerPort`; pinned canonical environment image) plus the clean-room capability as the post-hoc delivered-app audit (`scripts/dev/audit_delivered_app.py` — install/build/boot/HTTP contract probes; the FAY measurement pre-registered audit-not-in-cycle) and the doctor preflight category from step 4. **Open (the SIP stays accepted until these land)**: step 3 (route in-process exec sites — `test_runner`, `CommandExitZeroCheck`, probe runner — through typed sandbox ops), step 5 (clean-room verification at run finalization; `verified_executable`/`verified_functional` into SIP-0096 outcome derivation), step 6 (**retire the #306 qa-Node branch — "the payoff and the regression guard"**; note 1.4 moved further from this by adding Node to the dev image for #648), step 7 (golden-path live validation incl. #419 builder-seam). Target: integration steps → 1.5/1.6 per owner sequencing.

**Targets:** **v1.4 headline component, shipped in v1.4.0** (re-targeted from the vision arc on
2026-07-14 — see Motivating case). The remaining steps are unplaced, deliberately: see the delivery ledger. Together with SIP-0099
(Contract-First Build Scaffolding, accepted 2026-07-16) it forms the "Verified
Canonical App Build" vertical slice: *one canonical stack can be
deterministically composed, executed, and honestly verified without manual
intervention.*
**Acceptance gate (arc rev 2, Mac-lane review):** acceptance of this SIP is gated on
the **Phase-0.5 walking-skeleton spike** succeeding (see the 1.4 arc plan) — empirical
proof of the golden-path thesis before this service is committed to a minor. Noted
residual (rev 2 final): a green spike validates this service's *demand*, not its
*implementation feasibility* — the arc's **alternative-ready checkpoint** covers that
residual risk (when the evidence release is otherwise cut-ready, this floor must have
executed the golden path end-to-end at least once, or the fallback fires by default).
**Gate status (2026-07-26): satisfied.** The Phase-0.5 spike concluded (attempts
3.5–3.14) and both sibling SIPs (SIP-0098/0099) were accepted 2026-07-16 on its
evidence; this SIP is promotable. The alternative-ready checkpoint remains live
as the residual-risk control.
**v1.4 floor (arc rev 2):** build runner + `start_application` + HTTP health probe,
with environment contract + preflight and clean-room verification. Browser probe,
probe-as-peer implementation, and operator-access CLI/caddy defer to 1.5+; if the
browser probe descopes, the 1.4 verdict is honestly named `verified_executable`.
**Builds on:** `ContainerPort` (`src/squadops/ports/tools/container.py`,
`ContainerSpec`/`ContainerResult`) and the `CapabilityExecutor` port. Extends
the build lineage: SIP-0068, SIP-0071 (Builder Role), SIP-0086 (Build
Convergence Loop), SIP-0096 (Verification Evidence Integrity).
**Motivating case:** originally #306 (Node bundled into the qa image so the
frontend build check could run at all). Escalated 2026-07-14: the #419/#420
typed-acceptance seam made every task evaluate its own criteria in its own
agent container, and #425's vocabulary teaches plan authors that `node --check`
is valid for any task — demand for the toolchain went squad-wide while supply
stayed qa-only. Live consequence: `cyc_b9be8be77b31` (full 27b squad,
lint-clean plan, largely-correct code) died at dev subtask 3 on
`command_spawn_failed`; the builder was never dispatched — third consecutive
cycle stalled pre-builder on environment, not intelligence. The stopgap
(spread Node to more agent images) was **considered and rejected**: this SIP
is the chosen path, and the #419 builder-seam live validation deliberately
waits for its minimal version.
**Coordinates with:** SIP-0099 Contract-First Build Scaffolding (*what* is
deterministic vs generated — orthogonal and sibling in the 1.4 slice),
SIP-Stack-Blueprint-Contract (generalized blueprint schema, deliberately
deferred until a second stack exists — see the §4.2 status note),
SIP-Edge-Deployment-Profile (remote sandbox adapter target),
SIP-Capability-Backed-Agents (toolchain-as-capability, 2.0 arc).

## Delivery ledger (current as of 2026-10-28)

Kept by the rule in CLAUDE.md ("SIP System"): one row per part, updated in the PR that ships or re-places it, read at each release cut. Built from the read-only SIP-portfolio audit of 2026-10-04; `sips/PORTFOLIO.md` indexes it.

| part | status | where |
|---|---|---|
| step 1: execution service, workspace provisioning, Docker adapter | **shipped** | v1.4.0 |
| step 2: pinned canonical environment image | **shipped** | v1.4.0 |
| step 4: preflight (doctor category) | **shipped** | v1.4.0 |
| post-hoc clean-room audit | **shipped** | v1.4.0 (`scripts/dev/audit_delivered_app.py`) |
| §11a stack #2 in the sandbox; §11b packaging rendered | **shipped, amended** | 2026-08-15; v1.8.0 |
| step 3: route in-process exec sites through typed ops | **unplaced, deliberately** (§11c) | none |
| step 5: clean-room verdicts at finalization | **unplaced, deliberately** (§11c); SIP-0108's clean-room indicators wait on it (`cycle_assessment.py:324-325`) | none |
| step 6: retire the qa-Node branch | **unplaced, deliberately** (§11c) | none |
| step 7: golden-path live validation (incl. #419) | **unplaced, deliberately** (§11c) | none |
| §5 deferrals: browser probe, probe-as-peer, `expose_application` | **unplaced, deliberately** (§11c); `SIP-Outcome-Evaluation` may need `expose_application`-like hosting | none |
| campaign evaluation through this sandbox | **dropped** by §11c: SIP-0109 evaluates and renders routes in the qa container (runtime-api cannot reach the sandbox), the accepted path | SIP-0109 §24n, §24p |
| X-1: a `git_checkout` revision origin (§11d; SIP-0112 §8.2.2) | **shipped** | 2.4.0, PR #2441, issue #2419 |
| X-2: a checkout's tracked tree round-trips: bytes, line endings, tracked derived names, the executable bit (§11d) | **shipped** | 2.4.0, PR #2442, issue #2420 |
| X-3a: a product's declared command, run against a pinned revision in a disposable copy (§11d) | **shipped** | 2.4.0, PR #2447 |
| X-3b: starting a product from its declaration, with `http` and `tcp` readiness, the secrets' redaction and its declared entry points (§11d, §11e) | **shipped** | 2.4.0, PRs #2450 and #2474 |
| X-3b's remainder: resolving an owner-approved evaluation secret into the copy's environment at start (§11e; SIP-0112 Q40) | **placed**, re-placed from 2.4 on 2026-10-21, and from 2.5 on 2026-10-28 (the owner took the supervisor's recommendation to leave it unbuilt in 2.5: "Go with your recommendations"). 2.6's plan re-reads it; its consumer is the evaluation of a repository-backed Project's Campaign that needs a secret | 2.6.0, #2421 |
| the runtime API as the service's caller: its own client selector, the service's URL and token, the service's provider split from the preflight's (§11f; #2451 parts 1–3) | **shipped** | 2.4.0, PR #2456 |
| the apps the service starts, on the internal `sandbox-apps` network by container name, with no host port (§11h; #2451 part 4) | **shipped** | 2.4.0, PR #2460 |
| a pinned revision's content, read through the port from the live tree only while it matches its pin (§11i; SIP-0112's E.4.3 capture) | **shipped** | 2.4.0, PR #2461 |
| a seeded workspace released through the port, the operation journal kept by every removal (§11j) | **shipped** | 2.4.0, PR #2527, issue #2473 |
| a started tree's client routes read by the scenario runner, with the evaluator image's own Chromium as its entrypoint, for a repository-backed product's acceptance (§11k; SIP-0109 §24co) | **shipped** | 2.5.0, PR #2777 |

**What closes this SIP:** Steps 3, 5, 6, 7 shipped or dropped. Until a clean-room requirement returns, they are unplaced by ruling (§11c, 2026-10-04).

## 1. Abstract

Build, test, and verification execution currently runs **in-process, inside
agent containers** — `test_runner.py` and the typed-acceptance
`CommandExitZeroCheck` both `create_subprocess_exec` in the agent's own
process space. The agent image must therefore carry every toolchain any check
might invoke, untrusted generated code executes inside the agent trust
boundary, and "the app works" can only ever be claimed about an agent venv —
not about anything app-shaped.

This SIP proposes the **Ephemeral Application Sandbox**. The core boundary in
one sentence: **the execution service is the authoritative execution boundary
for all application code — agents never execute application code directly.**
The sandbox is cycle-scoped, managed by that dedicated **execution service**,
and contains a **persistent cycle workspace** and disposable **build**,
**runtime**, and **probe** execution units. Agents never touch a container
runtime; they request **typed operations** (`build_frontend`,
`start_application`, `probe_http_endpoint`, …) that return structured
semantic results. Authoritative verification is governed by the **clean-room
invariant** (§4.5): verdicts come from a freshly provisioned environment
against a pinned workspace revision (§4.6), never from the dirty convergence
container.

Agent images become lean and stack-agnostic; untrusted execution is isolated;
the environment becomes a pinned, preflight-validated contract; and
executable + functional verification finally happens where the application
contract says the app must run.

### 1.1 Terminology

| Term | Meaning |
|---|---|
| **Sandbox** | the whole cycle-scoped construct: one workspace plus the execution units operating on it |
| **Execution service** | the privileged service owning the container runtime and managing sandboxes — the only socket holder ("workspace/execution service" in earlier drafts) |
| **Workspace** | the persistent, revisioned application state for one cycle; outlives every execution unit (§4.6) |
| **Execution unit** | a disposable container provisioned for one concern: build runner, application runtime, or probe runner |
| **Application runtime** | the execution unit that starts the assembled app — never the agent runtime, which runs no application code |

## 2. Problem Statement

**P1 — Toolchain bundling couples agent images to build breadth.** Every
buildable stack forces dependencies into agent images (#306 weighed "bloat
all six images" vs "qa-only" and chose the least-bad *bundling* option).
Post-#419/#420/#425, bundling would have to go squad-wide per stack.

**P2 — In-process execution of generated code is a security boundary
violation.** The agent container holds credentials, queue identity, and (post
#326) a service identity. `npm install` on a generated `package.json` runs
arbitrary install scripts inside that boundary.

**P3 — No reproducibility or pinning of the build environment.** The
toolchain is whatever the agent base image happened to install; there is no
single pinned answer to "what environment did this build run in."

**P4 — Per-role image divergence is accreting** (`requirements.txt` + the
#306 apt branch = role-conditional Dockerfile logic in two dimensions).

**P5 — The verification locus is wrong for the claim being made** *(new)*.
The question the system currently answers is "does this source pass a command
inside the dev agent's container?" The claim the north star requires is "does
this application install, build, start, and operate inside its declared
environment?" No amount of agent-side tooling closes that gap — and nothing
today reconciles what the check vocabulary *advertises* against what any
execution locus *provides* (the roll-4 failure class).

## 3. Goals / Non-Goals

**Goals**
- A cycle-scoped application sandbox: persistent workspace + disposable
  build/runtime/probe execution units, owned by a dedicated execution
  service.
- Agents and runtime-api never hold a container-runtime socket; the execution
  service is the only privileged component, exposing typed operations only.
- Agent images carry **no** build toolchain; retire the #306 qa-Node branch
  once the sandbox path is live (the exit #306's text promised).
- A **Build Environment Contract**: pinned images + required tools/versions,
  validated at **preflight** — advertised-vs-provided mismatches fail before
  dispatch, never at task time.
- Typed operations with structured semantic outputs (never raw console text
  as the contract).
- The **clean-room invariant** (§4.5): warm reuse is confined to bounded
  builder attempts; authoritative final verification always runs in a freshly
  provisioned environment against a pinned workspace revision.
- Executable and functional verification levels (per the roadmap doc's
  three-level model), including a deliberately narrow browser probe; the
  probe runner executes as a **peer** of the application runtime, not inside
  it.

**Non-Goals**
- Not a general remote-code-execution service or user-facing build API.
- Not Kubernetes / a deployment platform — a small container-compose
  abstraction owned by the execution service suffices for v1.4.
- Not committing a sandbox runtime (Docker/rootless/gVisor/microVM) — the
  contracts abstract it; adapters choose. Rootless is preferred where
  compatible but is not a v1.4 blocker.
- Not dependency-supply-chain trust (malicious packages) beyond isolation.
- Not multi-stack generalization (that is v1.6; v1.4 ships the canonical
  fastapi+react blueprint only).

## 4. Design

### 4.1 Four separable concerns, one sandbox

```
Cycle Workspace  (persistent, cycle-scoped, content-versioned)
      |
      +-- Build Runner            install / build / unit test   (disposable)
      +-- Application Runtime     backend / frontend processes  (short-lived)
      +-- Probe Runner            HTTP / browser / functional   (peer of runtime)
```

- **Workspace** — the durable unit of application state for the cycle:
  scaffold output, agent changes, patches, manifests, build reports,
  evidence references. Outlives every execution unit.
- **Build environment** — compilers and dev dependencies; may differ from
  runtime (built assets need a static server, not Node).
- **Runtime environment** — starts and exercises the assembled app.
- **Probe environment** — where health/functional probes execute. A probe
  inside the app container hides port-exposure, host-binding, and origin
  failures; probes run as network peers.

For v1.4 these may be implemented as one execution service and one container
composition (a single combined build+runtime container is acceptable); the
**contracts remain separate** so the composition can change without changing
the agent-facing model.

### 4.2 Environment definition is the contract; Dockerfiles are an adapter rendering

The stack's blueprint declares a deterministic environment definition: base
environment identity, required tools/versions, build/runtime operations,
exposed endpoints, mounts, env inputs, network policy. The container adapter
renders that into Dockerfiles/compose for the canonical stack (checked in,
deterministic, never LLM-authored). The Dockerfile is one representation, not
the contract.

**Status note (2026-07-26):** the generalized `StackBlueprint` schema is
deliberately deferred — SIP-Stack-Blueprint-Contract gates it on a second real
stack existing. For v1.4 the environment definition is a checked-in canonical
definition for `fullstack_fastapi_react`, owned alongside SIP-0099's expander
surface, and migrates into the blueprint when that SIP is accepted. Whether
the blueprint ultimately owns the packaging set is that SIP's open question;
this SIP requires only that the definition be deterministic, checked in, and
pinned.

### 4.3 The execution service

A **dedicated service beside runtime-api** (same Spark host initially):

| | runtime-api | execution service |
|---|---|---|
| owns | cycle lifecycle, authz, execution *requests*, status, outcome integration | workspace provisioning, image resolution, container lifecycle, typed op execution, resource limits, network policy, evidence capture, cleanup |
| socket | never | the only holder |

Runtime-api calls it over a narrow authenticated port. Rationale: a
container-runtime socket is host-equivalent authority; compromise of
runtime-api must not imply host-container control; execution jobs are
long-lived and stream logs; later remote execution must not restructure
runtime-api.

### 4.4 Typed operations with semantic results

`install_dependencies`, `build_frontend`, `run_backend_tests`,
`start_application`, `probe_http_endpoint`, `run_browser_smoke`,
`read_build_diagnostics`, `apply_workspace_patch`.

Each returns structured data — e.g. `build_frontend` → status, exit
classification, duration, diagnostics, artifact refs, warning count,
failure-ownership hints, raw-log evidence reference; `start_application` →
process identity, endpoint handles, readiness state, startup diagnostics,
cleanup handle. The adapter may run shell commands underneath; the domain
surface stays typed so correction and outcome logic reason over stable
contracts, not reparsed console text. These are policy-bearing operations,
not renamed shell commands — there is no generic shell and no safelist
expansion.

The original `BuildSandboxPort` (`run_build(job) → BuildResult`, v1 of this
SIP) survives as the build-runner layer's internal shape; `ran=False`
semantics (environment unavailable ≠ deliverable failure) carry forward and
now roll up through SIP-0096 as explicit environment-contract failures.

### 4.5 Lifecycle: warm convergence, clean-room verdicts

**Clean-room invariant** — *authoritative verification evidence is only ever
produced by a freshly provisioned execution environment against a pinned
workspace revision (§4.6); no verdict may depend on state accumulated in a
convergence container.* Later sections and §7 reference this invariant by
name rather than restating it.

- **Persistent workspace per cycle** — required for iterative builder
  patches, attempt comparison, outer-loop correction, evidence lineage.
- **Warm execution unit within one bounded builder convergence attempt** —
  build → inspect → patch → rebuild without re-provisioning. Destroyed when
  the attempt ends.
- **Fresh environment for authoritative verification** — the invariant
  applied: it prevents false success from lingering processes, undeclared
  files, mutated state, or previously installed undeclared packages.
  `verified_functional` and `verified_executable` are only ever rendered
  under it.

### 4.6 Workspace revision lifecycle

The workspace is the durable unit of state; **revisions are its unit of
truth**:

- **Every typed operation executes against, and records, an explicit
  workspace revision.** No operation runs against "whatever is in the
  directory."
- **Revision boundaries:** a new revision is cut when content enters the
  workspace from outside an execution unit — scaffold seeding, an applied
  agent patch (`apply_workspace_patch`), and build outputs explicitly
  promoted as artifacts.
- **Mutability window:** within a warm builder attempt the working tree may
  mutate freely between operations; the attempt's end (success or budget
  exhaustion) cuts a revision. Intermediate dirty state is never
  referenceable by later operations.
- **Verification pinning:** clean-room verification provisions against a
  named revision and fails if the workspace content does not match it — so
  the revision recorded in evidence (§7 item 15) is the one that was
  verified, by construction.
- The storage backend (bind-mounted dir vs volume vs content-addressed
  store — open question 2) may change how revisions are captured, never
  these semantics.

### 4.7 Dependency caching

Shared **read-through download caches** only (npm/wheel caches, browser
binaries, base layers). No shared installed-dependency directories
(`node_modules`, venvs); dependencies install into the cycle sandbox;
lockfile/manifest captured as evidence; the clean-room build must succeed
without undeclared workspace state. Cache hits are recorded but never change
the semantic result.

### 4.8 Verification levels and check locus

- **Structural** checks need no application runtime. They may run near
  agents for fast feedback, but **authoritative structural verification runs
  deterministically against the assembled cycle workspace via the execution
  service** (model-independent, centralizes evidence, validates what was
  actually assembled).
- **Executable** (install/build/start/health) and **functional** (probe the
  PRD's critical path) run in the sandbox. The first browser probe is
  deliberately narrow: open declared URL, await readiness, assert one
  required element, perform one critical interaction, assert the result,
  capture console errors + screenshot. **If the browser probe is descoped,
  the outcome name honestly downgrades to `verified_executable`.**
- Typed acceptance `command_exit_zero` evaluation moves from agent-side
  `create_subprocess_exec` (`acceptance_checks.py`) to sandbox execution,
  alongside `test_runner.py`'s exec sites and the 98.4 probe runner's
  in-process boot+probe path (`probe_runner.py` — its `ExecutionProfile` was
  designed as runner-owned mechanics precisely so it re-homes here with no
  contract change).

### 4.9 Correction-policy integration: locus × mode

Failure classification gains two dimensions — **locus** (which layer owns the
failure) and **mode** (syntax / build / startup / runtime / timeout /
unsupported / unavailable):

| Locus | Owns the failure | Examples | Routing |
|---|---|---|---|
| **infrastructure** | the execution environment | binary missing from the declared env; image unresolvable; unit won't start; service unavailable | retry infra, continue after environment correction, or block as infrastructure-unverified — **never `patch`, never application correction budget** (roll-4 defect: an `execution`-classified missing-binary failure took `patch` and burned the budget) |
| **application** | the generated application | build reveals a code defect; app crashes; health never ready; probe hits an app exception | builder patch, outer correction, or replan — patchable and budgeted |
| **orchestration** | the cycle machinery around execution | dispatch/envelope failure surrounding an operation | orchestration recovery, outside the correction budget |
| **verification** | the probe/check apparatus itself | the probe runner fails, as distinct from a probe failing | recorded as a verification-infrastructure failure — never a pass, never an application defect |

Environment-contract violations (advertised-vs-provided mismatches) are the
distinguished infrastructure sub-class preflight exists to eliminate; one that
surfaces at task time anyway is an explicit contract failure (§7 item 7),
never a generic execution error.

**Vocabulary note (2026-07-26):** main now carries `FailureLocus`
(`cycles/failure_evidence.py`, #568) — an *artifact-ownership* axis
(own_artifact / subject) that routes which role repairs. The two compose
rather than collide: this SIP's locus decides whether a failure is patchable
at all; #568's ownership axis then routes *application-locus* failures to the
right role. Reconciling the shared name is part of the correction-policy
follow-up (open question 3).

### 4.10 Operator access / manual inspection

The runtime unit is short-lived by design — started, probed, torn down. But
the operator's boot-it-yourself verification habit (the #376 lesson) deserves
a first-class affordance, and the persistent workspace makes it cheap:

- **`squadops sandbox up <cycle-id>`** — the execution service re-provisions
  the application runtime *on demand*, clean-room, from the exact persisted
  workspace revision the verdict was rendered on (fresh containers, cached
  installs, same pinned images), then publishes endpoints to the operator:
  routed through the existing caddy reverse proxy
  (`/sandbox/<cycle-id>/` → frontend, `/sandbox/<cycle-id>/api/` → backend)
  or, minimally, ephemeral host ports printed back. On the `local` profile
  the tailnet is the reach boundary; `lab`/`cloud` profiles must put the
  route behind the existing auth before enabling this.
- **`squadops sandbox down <cycle-id>`** tears it down; every exposure
  carries a **TTL lease** (auto-teardown unless renewed) and idempotent
  cleanup on service restart — no stranded runtimes (the FocusLease lesson
  applied to sandboxes).
- A `--hold` variant on cycle create covers the watching-it-live case:
  after final verification, re-expose instead of tear down, same TTL.
- Exposure is an explicit typed operation (`expose_application`) that punches
  through the sandbox's deny-by-default network — never a default — and the
  published endpoints are recorded in run evidence.

On-demand re-provisioning is deliberately preferred over keeping runtimes
alive: a fresh boot from the persisted revision re-proves reproducibility on
every inspection, whereas a lingering container is stale evidence and a
resource leak. The bare-metal escape hatch remains free — the assembled
workspace is an ordinary host directory, and the stack's environment contract
declares how to run it directly (this said `qa_handoff.md` until #1312 retired
that document; the run commands were always the contract's, and are now
threaded to the test author from it).

## 5. v1.4 scope split

| Designed correctly in 1.4 (contract level) | May be minimal in 1.4 (implementation level) |
|---|---|
| All four concerns as separate contracts | One composition; combined build+runtime container |
| Execution service owns the only socket | Same-host service, Docker adapter only |
| Typed ops with semantic results | Minimal op set for the canonical stack |
| Clean-room final verification | Warm reuse only inside builder attempts |
| Environment contract + preflight validation | One canonical environment image |
| Probe-as-peer | HTTP probes + one narrow browser happy-path |
| Locus × mode failure classification | Wired for sandbox-originated failures first |
| `expose_application` as explicit, TTL-leased, evidenced operation | **deferred to 1.5+** (arc rev 2), as are the browser probe and probe-as-peer implementation; the 1.4 floor is build runner + app start + HTTP health |

## 6. Migration

1. Land the execution-service skeleton + workspace provisioning + Docker
   adapter (on `ContainerPort`), behind config with a NoOp default (parity
   with today).
2. Publish the pinned canonical environment image(s) for fastapi+react.
3. Route the in-process execution sites through typed operations —
   `test_runner.py`'s exec sites, `CommandExitZeroCheck`, and the probe
   runner's boot+probe path (`probe_runner.py`); unit tests assert parity.
4. Wire preflight validation of the environment contract (doctor category +
   cycle-create check).
5. Builder convergence loop adopts the warm-unit ops; add clean-room final
   verification to run finalization; roll `verified_executable` /
   `verified_functional` into SIP-0096 outcome derivation.
6. **Retire the #306 qa-Node branch and qa runtime test deps** — agent
   images return to runtime-only. This is the payoff and the regression
   guard.
7. Live-validate: one canonical `full` cycle walking the entire golden path
   — including the deferred #419 builder-seam validation.

## 7. Security requirements (acceptance-grade)

1. Agents cannot access the container runtime directly.
2. The execution service accepts typed operations only.
3. Every execution runs against a declared workspace revision.
4. Every operation records image identity + environment-contract identity.
5. Interactive convergence runs are distinguished from authoritative final
   verification.
6. Final verification begins from a clean execution environment.
7. Undeclared tools/services produce explicit environment-contract failures.
8. Host paths outside the cycle workspace cannot be mounted; agents cannot
   supply host paths.
9. Resource limits and timeouts are mandatory; privileged containers and
   host networking are forbidden by default; capabilities dropped.
10. Network access denied or explicitly declared (deps-only egress for
    installs); permitted images/registries policy-controlled.
11. Execution logs and terminal failures persist even when orchestration
    crashes (#427 alignment).
12. Cleanup is idempotent and recoverable after service restart.
13. Cached dependencies cannot substitute for undeclared dependencies.
14. Functional probes execute from outside the application process boundary.
15. Verification evidence identifies the exact workspace revision,
    blueprint, environment contract, image, and operation versions used.
16. Application exposure for manual inspection is an explicit operation,
    TTL-leased, recorded in evidence, and auth-gated on any profile whose
    reach boundary is not a private network.

## 8. Open Questions

1. Execution-service transport: HTTP on localhost vs unix socket vs queue —
   and its auth story against the #326 service-identity pattern.
2. Workspace storage backend: bind-mounted host dir per cycle vs volume vs
   content-addressed store. (The v1 "files inline in BuildJob" is resolved —
   workspace revisions, not inline bytes; §4.6 fixes the revision
   *semantics*, only the capture mechanism is open.)
3. How much of the locus × mode taxonomy lands in this SIP vs the
   correction-policy follow-up (#413 lineage) — including reconciling the
   `FailureLocus` name collision (§4.9 vocabulary note)?

*(Pruned 2026-07-26: the browser-probe runtime question was already resolved
by arc rev 2 — HTTP-only floor, `verified_executable` naming, browser probe a
1.5+ decision; environment-image ownership/publish pipeline is an
implementation-planning choice and moves to the implementation plan.)*

## 9. Alternatives Considered

- **Bundle toolchains per-role in agent images** (status quo + extension).
  Rejected 2026-07-14 (user decision): conflates agent runtime with
  deliverable runtime; N stacks × M roles accretion; verifies the wrong
  claim. #306's qa-only bundling remains the correct *interim*; this SIP is
  its exit.
- **One fat agent image with every toolchain.** Worst of P1/P2. Rejected.
- **Run builds via `CapabilityExecutor`.** Dispatches task envelopes to
  agents; a build command has no agent on the far side. Distinct service.
- **Embed execution in runtime-api.** Rejected: socket authority, long-lived
  jobs, log streaming, and future remote execution all argue for a dedicated
  service (§4.3).

## 10. References

- `docs/ideas/IDEA-Functional-App-Obstacles-and-Roadmap.md` (v3) — strategy
  context, three contracts, verification levels, Functional App Yield.
- #306, #290/#296/#303 — toolchain lineage; #419/#420/#421, #425 —
  typed-acceptance seam + safelist vocabulary/lint; #422/#423/#424/#426/#427
  — 2026-07-14 findings; #114 — evaluator outcome surfacing.
- `cyc_b9be8be77b31` — the roll-4 motivating run (full squad, stalled
  pre-builder on environment).
- SIP-0068, SIP-0071, SIP-0086, SIP-0096; SIP-0099 Contract-First Build
  Scaffolding (sibling); SIP-Stack-Blueprint-Contract (deferred blueprint
  schema); SIP-Edge-Deployment-Profile; SIP-Capability-Backed-Agents.
- `ContainerPort` — `src/squadops/ports/tools/container.py`;
  `test_runner.py`; `acceptance_checks.py` (`CommandExitZeroCheck`);
  `probe_runner.py` (`ExecutionProfile` — the in-process boot+probe path
  this SIP re-homes).

## 11. Post-acceptance amendments

### 11a. Stack #2 entered the sandbox without the generalization this SIP deferred (2026-08-15)

**What changed.** §3 non-goals state *"Not multi-stack generalization (that is v1.6; v1.4
ships the canonical fastapi+react blueprint only)"*, and §4.2's status note defers the
`StackBlueprint` schema until a second real stack exists. #822 subsequently added a
`nextjs_ts` `EnvironmentContract` to the sandbox registry — extending the subsystem to a
second stack — while the generalization stayed deferred and nothing recorded the gap. The
environment *contract* seam took a second entry cleanly; every surface around it stayed
shaped by the canonical stack's behavior.

**Evidence.** Four defects, all one class, measured in a single audit of SIP-0104 window
roll 1 (`cyc_04d36309d793`, 2026-08-15):

1. `NEXTJS_TS` declared `npm ci`, which EUSAGE-refuses without a `package-lock.json` the
   scaffold cannot deterministically produce — **the stack-#2 sandbox path was
   unreachable-green by construction.** The identical correction already existed in
   `probe_runner`'s `nextjs_next_start` profile (roll 10, `cyc_43a216d43e1e`) and in this
   SIP's own canonical contract ("no lockfile → npm install"); neither propagated.
2. `scripts/dev/audit_delivered_app.py` hardcoded the canonical environment and a
   `backend/routes.py` assembly sentinel, so auditing stack #2 would stand a Next.js tree
   up with uvicorn and report the auditor's defect as the app's.
3. `WorkspaceStore._EXCLUDED_SEGMENTS` (§4.6 derived state) listed `dist` — Vite's build
   output — but not `.next`. Pin verification therefore walked into webpack caches and
   read binary bytes as UTF-8, raising `UnicodeDecodeError`: not over-pinning, a crash.
4. **The §4.6 revision-lifecycle model itself.** `next build` GENERATES `next-env.d.ts`
   and REWRITES the scaffold's frozen `tsconfig.json` (injecting `allowJs`,
   `skipLibCheck`) — documented Next behavior. No tree on this stack can match its pin
   once a build has run, so verification before `start_application` asserted an invariant
   that was never true for this stack.

**The ruling (owner, 2026-08-15).** Finding 4 is a design fork, not a missing list entry,
and was decided as: **pin verification is enforced before the tree is built, not after.**
`EnvironmentContract` now declares `build_mutates_source` — a fact about the toolchain,
declared per stack — and where it is true, only the operation preceding any build
(`install_dependencies`) verifies. The guarantee kept is the one that carries meaning:
*the source we declared is the source we built.* Where it is false (the canonical stack)
behavior is unchanged, and a post-build drift still refuses. Alternatives weighed and
rejected: excluding `tsconfig.json` from verification (silently drops tamper detection on
a frozen scaffold file); re-pinning post-build (faithful but larger, and unneeded until
something consumes a post-build revision); changing the scaffold to emit a tsconfig Next
will not rewrite (fixes the root cause but moves generator bytes, which would reset
SIP-0104's measurement window — deferred until that window closes).

**What remains ungeneralized, stated so the next stack meets a boundary rather than
rediscovering it.** `_EXCLUDED_SEGMENTS` is still one global set, not a per-stack
declaration: a third stack whose build output is named something else repeats finding 3.
The honest scope of this amendment is "stack #2 works and the lifecycle claim is now
true", NOT "the sandbox is stack-general". `SIP-Stack-Blueprint-Contract` still owns that
generalization — and its own gating condition (*"deferred until a second real stack
exists"*) is now satisfied, so it is unblocked by its own criterion.

**Consequence to note.** `contract_id()` covers the full declaration by design (§7 items
4/15), so adding `build_mutates_source` changes every contract id and invalidates
workspace caches keyed to them — a cache miss, not a correctness risk.

### 11b. §4.2's open question is answered: the scaffold renders the packaging (2026-09-13)

**What changed.** §4.2 left open whether the blueprint owns the packaging set and required only
that the environment definition be deterministic, checked in and pinned. SIP-0105 A1 answers it:
both registered stacks now render their Dockerfile (and, for `fullstack_fastapi_react`, the nginx
config and start script) from this SIP's `EnvironmentContract`, frozen and never LLM-authored.
That is §4.2's "adapter rendering" as written. The sandbox's own operations are unchanged. They
still run the application directly in the sandbox image, and no sandbox operation builds the
rendered image. `package_builds` stays declared unbuilt.

**Evidence and ruling.** Recorded in SIP-0105 A1, where the rule lives.

### 11c. In-agent execution is the accepted path for campaign evaluation; steps 3, 5, 6 and 7 wait for a clean-room requirement (2026-10-04)

**What changed.**
- **SIP-0109 built its in-cycle evaluation and route rendering in the qa agent container,** not in this sandbox: the runtime-api cannot reach the sandbox (provider `noop`, no client wired; SIP-0109 §24n, §24p). That diverges from §1's boundary, "agents never execute application code directly". It is ruled the accepted path for campaign evaluation, and recorded here so this SIP no longer reads as describing main.
- **Steps 3, 5, 6 and 7, and the §5 deferrals, are unplaced, deliberately,** until a requirement for clean-room execution returns. The header's "Target: integration steps → 1.5/1.6" is superseded. SIP-0108's clean-room indicators stay unaskable until step 5 (`cycle_assessment.py:324-325`). `SIP-Outcome-Evaluation` (proposed) is the likeliest such requirement: its scenarios run against a stood-up app.

**Evidence.** The read-only SIP-portfolio audit of 2026-10-04; SIP-0109 §24n and §24p.

**Who ruled it.** the owner's rulings of 2026-10-04 on the SIP-portfolio audit (`sips/PORTFOLIO.md`): "yes, move them to 3.x including capability-backed agents. I accept all your other recommendations to keep SIPs current, reflecting what gets delivered, and where the work is targeted".

### 11d. A product's Git checkout as the live tree, and the product's declared commands (2026-10-18, §4.6, §4.7, §7 items 2 and 3; SIP-0112 §8.2.2, X-1 to X-3; implementer's record, for the owner)

SIP-0112 (accepted 2026-10-17) brings products SquadOps didn't build into the sandbox. Its §8.2.2 names
three sandbox changes, and the 2.4 plan's D12 has the Spark lane build them. They change this SIP's
§4.6 and §7 for those products, so they are recorded here.

**What changed.**
- **X-1 (#2441): a `git_checkout` revision origin.** The commit isn't on the revision: the sandbox never
  runs Git, and SIP-0112's revision-to-commit mapping holds it.
- **X-2 (#2442): a checkout's tracked tree comes back exactly as it went in.**
  - **Content is text or bytes.** A revision ID hashes each file's bytes, and text hashes as its UTF-8
    encoding, so every existing ID is unchanged.
  - **The tree is read as the bytes on disk.** Universal-newline reading had made a seeded `\r\n` file
    fail its own pin.
  - **§4.6's derived-state exclusion now keeps out only what no revision names.** A `git_checkout` seed's
    files are all content, whatever their name, so a product's tracked `package-lock.json` or `dist/` file
    is pinned. A patch may change one its base names, but may never add one. `.git` is never content.
    Untracked installs and builds stay out of the pin, as §4.7 has it.
  - **The executable bit is content in a checkout's lineage.** It enters the revision ID only when a file
    has it. A scaffold lineage ignores modes, as it always did.
- **X-3a (this PR, #2421): `run_declared_command`, widening §7 item 2.** "Typed operations only" now has
  one operation whose argv the caller supplies.
  - **Whose argv:** a product's own declaration, from the Development Configuration revision SIP-0112's
    E.4.2 confirms. It is never an agent's output, and agents still can't reach the runtime (§7 item 1).
  - **Where it runs:** in a disposable copy of exactly the pinned revision, taken from the live tree only
    while the tree matches its pin (§7 item 3), and discarded afterwards. Nothing a command does reaches
    the live tree or a revision.
  - **Posture:** setup argvs get the install network and the command gets none (§7 item 10). Caps are
    dropped, with no new privileges, as the workspace owner. X-3a carries no secrets.
  - **How it ended is typed:** `exited` with its status, `setup_failed`, `timeout`, `command_not_found`
    (127) and `command_not_executable` (126). The last two are not-run, never a failed check (§4.4).
  - **A limit:** the command runs offline, so a check that needs the network fails. A product declares
    such a check as needing its environment, and SIP-0112's E.4.2 records it UNVERIFIED.
- **Still X-3b (#2421, with SIP-0113's runner #2414):** starting a product from its declaration, with
  readiness and the owner-approved evaluation secrets (SIP-0112 Q40).

**A step 5a gap, closed here.** X-1 and X-2 shipped in #2441 and #2442 without this amendment. X-2's
tracked-name rule changes §4.6, so this, the first sandbox PR after them, records both.

**§11c, for these products.** *(The selector named here is superseded by §11f.)* The runtime API reaches
this sandbox only where the deploy sets `SQUADOPS__SANDBOX__PROVIDER=http` and runs the sandbox service
(`rebuild_and_deploy.sh sandbox`). SIP-0112's E.4.2 uses it that way. §11c's ruling for campaign
evaluation stands.

**Evidence.** SIP-0112 §8.2.2, accepted by the owner. The MacBook lane's G4 reviews of #2441 and #2442
raised the tracked names, the executable bit, and the bit's scope to a checkout's lineage. The X-3 split
was agreed on #2407: E.4.2's inherited baseline runs a product's checks, which waited on X-3.

**Who ruled it.** The owner accepted SIP-0112 with X-1 to X-3 in its §8.2.2 (2026-10-17), and D12
assigns them. The tracked-name and executable-bit rules and the X-3 split are the implementer's, reviewed
by the MacBook lane as consumer (G4), for the owner's review.

### 11e. The sandbox runs SIP-0113's scenario runner, and X-3b starts a product from its declaration (2026-10-18, §4.6, §7 items 2, 3 and 10; SIP-0113 §4.1 A3; #2414, #2421; implementer's record, for the owner)

- **A second surface, `POST /api/v1/evaluations`,** beside the cycle's operations. It takes an evaluated
  tree by its `FileTree.identity`, not a workspace revision, as SIP-0112's contract 3 asks of Outcome
  Evaluation. The tree's files are refused unless they hash to that identity, which is §7 item 3 for a
  tree that never had a workspace.
- **X-3b, the start:**
  - **from a product's declaration:** setup argvs, the start argv and its port, with an `http`
    readiness (a 2xx from the target) or a `tcp` one (a connection to the port). The argvs and the
    working directory are checked again here with X-3a's own `declared_argv` and `working_directory`;
  - **or from its stack's environment contract,** as today.

  Either way it runs in a disposable copy that is removed afterwards. The live tree is never mounted, so
  nothing a scenario does reaches a revision. This widens §7 item 2 the way §11d did: the argv is the
  product's own declaration, never an agent's output.
- **The evaluation secrets** (SIP-0112 Q40) reach only the app container's environment. They are never
  written or journaled, and every value is replaced with `[redacted]` in the free text the runner
  returns. An app may log its environment or answer with a token, and the start's detail, its last lines
  and each step's detail are returned as written. Results, identities and ids are left alone.
- **An evaluated tree's keys are checked before anything is written** (`workspace.tree_path`): a key that
  is absolute, climbs out with `..` or isn't in its normal form is refused, and nothing runs. The tree is
  a squad's files from the vault, and a key like `../<cycle>/workspace/x` would otherwise write into a
  cycle's live tree.
- **`declared_argv` refuses a string.** A string is a sequence of strings too, so `"ls -l"` had passed
  as one-letter arguments.
- **What X-3b doesn't ship yet, still on #2421:**
  - **The declared entry points: built in the PR stacked on #2453.** Scenarios reach the `http_base`
    entry point's port and path, and a blueprint reaches its stack's `api_prefix`. A `ui_base` waits on
    page scenarios (SIP-0113 A2).
  - **The approved secrets' resolution.** The runner takes the resolved values. Resolving only the
    `secret://` references a Project declares and the owner approves, and refusing anything else as
    `blocked_unverified`, `secret not available` (contract 7), needs the approval record. That record
    is SIP-0112's E.4.2, so it lands after E.4.2(b), in the evaluation service.
  - **Contract 7's three reasons:** `no start declaration` and `start failed` are mapped by the
    evaluation service (#2453). `secret not available` lands with the resolution above.
  - **The network:** the app still gets the bridge. #2451's fourth part puts it on the internal
    `sandbox-apps` network.
- **Posture:** setup gets the install network. The app gets the bridge to publish its one port to
  loopback, with caps dropped, no new privileges and the copy owner's uid.

### 11f. The runtime API calls the sandbox service: its own client selector, and the service's URL and token (2026-10-18, §4.1, §11c, §11d; #2451; the owner's ruling)

SIP-0112's E.4.2 seeds a product's checkout into this sandbox from the runtime API, and SIP-0113's
evaluation service runs its scenarios here (§11e). Neither could. The runtime API had no client of the
service, compose gave it neither the service's URL nor its token, and one variable,
`SQUADOPS__SANDBOX__PROVIDER`, was read both by the runtime's cycle-create preflight and by the
service for its own backend.

**What changed.**
- **The runtime API binds one client of the service,** `adapters.sandbox.factory.create_sandbox_client`,
  called once by `_init_cycle_subsystem` and read through `deps.get_sandbox_client`. E.4.2's seeding and
  SIP-0113's runner share it.
- **It has its own selector,** `sandbox_client.provider` (`SQUADOPS__SANDBOX_CLIENT__PROVIDER`:
  `http` | `none`). It is required: the runtime API refuses to start without it (#1568).
  - `http` calls the service. Compose gives the runtime API `http://squadops-sandbox-service:8002` and
    the service's token, and a client missing either is refused at config load.
  - `none` binds no client, and each caller reads the sandbox as unavailable.
- **The section belongs to the runtime API alone.** It carries the service's token, so the seven agents
  never load it. `AppConfig` holds it as optional, and the root's factory refuses it absent.
  `test_composition_roots.py` asserts that the runtime API's compose service names it and that no other
  service does.
- **The service's own provider has its own variable,** `SQUADOPS_SANDBOX_SERVICE_PROVIDER` (`docker` |
  `noop`). Compose writes it into the service's `SQUADOPS__SANDBOX__PROVIDER`. **The runtime's
  preflight is unchanged:** it still reads `SQUADOPS__SANDBOX__PROVIDER`.
- **The service runs on the deploys where E.4.2 or the 2.4 window runs,** the MacBook and the Spark
  (`rebuild_and_deploy.sh sandbox`).
- **Superseded:** §11c's "no client wired", and §11d's selector. The runtime API reaches the sandbox where
  `SQUADOPS__SANDBOX_CLIENT__PROVIDER=http` and the service runs. §11c's ruling for campaign evaluation
  stands.

**Not covered here, ruled for the next PR: inside a deploy, the service can't reach an app it starts**
(#2451's fourth part). `DockerAdapter.run_detached` publishes an app's port on the host's loopback, and the
service is a container on `squadnet`, whose `127.0.0.1` is its own. So readiness, `probe_http_endpoint`
and every scenario step fail to connect there. The flaw predates SIP-0113: `start_application` has always
had it, unseen because the service has always been `noop`. The live runs for #2447, #2450 and #2453
worked because they ran on the host. The owner ruled the fix on #2451 the same day: an internal,
no-egress `sandbox-apps` network that the service joins, with apps on it by container name and no host
port, its name reaching the service through a required `SQUADOPS__SANDBOX__APP_NETWORK`. The PR that
builds it records it and adds its ledger row. Until then, a live evaluation runs from the host.

**Evidence.** #2451's three parts, read against `docker-compose.yml`, `deps.py` and the preflight. The
wiring test enters at `load_config` with the env compose writes and asserts the seeded tree at a
sandbox service app (`tests/unit/sandbox/test_sandbox_client_factory.py`).

**Who ruled it.** The owner, 2026-10-18, on #2451 (recorded by the MacBook session): "approved as
proposed (D11's compose ruling …): 1. The runtime API gets the sandbox service's URL and token. 2. The
runtime API's sandbox selector is split from the service's own, and its cycle-create preflight is
unchanged. 3. The opt-in sandbox service runs on the deploys where E.4.2 or the window runs: the MacBook
and the Spark." The section's scope to the runtime API is the implementer's, for the MacBook lane's
review (G4).

### 11g. Seeding joins the port (2026-10-18, §4.4, §4.6; §11f; contract 3; implementer's record, for the owner)

**What changed.** `seed_workspace` is an operation of `ExecutionSandboxPort`, with X-2's signature: the
files as text or bytes, the origin, the executable bit and the creation time. Before, it was a
service-level method of `SandboxService` and `HttpExecutionSandbox`, outside the port. §11f's
`create_sandbox_client` returns the port, so a caller typed against it couldn't seed: SIP-0112's E.4.2
seeds a product's checkout through that client.
- `SandboxService.seed_workspace` is now async, like every port operation, and the service's seed
  route awaits it.
- The noop cuts the content's own revision and stores nothing, as its patch returns the untouched base.
  It never raises, and every operation on that revision is not-run.
- All three implementations cut the same revision for the same checkout, binary file and executable bit
  included (`tests/unit/sandbox/test_seed_on_the_port.py`).

**Who ruled it.** The MacBook lane asked for it in its G4 review of #2456, as contract 3's consumer. It is
the implementer's change, for that lane's review and the owner's.

### 11h. The service's apps run on an internal network, by name, with no host port (2026-10-18, §4.3, §7 items 9 and 10; §11f; #2451 part 4; the owner's ruling)

**Why.** Inside a deploy the sandbox service is a container on `squadnet`. `DockerAdapter.run_detached`
published each app on the host's loopback (`-p 127.0.0.1:0:<port>`), and the service's own `127.0.0.1`
is its own, so readiness, `probe_http_endpoint` and every scenario step would fail to connect. The flaw
predates SIP-0113: the service had always been `noop`, and every live run so far ran on the host.

**What changed.**
- **Compose declares `sandbox-apps`,** named `squadops-sandbox-apps` (fixed, not project-prefixed) and
  `internal: true`: no route out. The service joins it beside `squadnet`, and no other service does.
  The service reads its name from `SQUADOPS__SANDBOX__APP_NETWORK`.
- **The service's root requires it when its provider is `docker`** (`squadops.sandbox.main.build_app`),
  never defaulted (#1568). `SandboxConfig.app_network` is optional, because the runtime's preflight and
  the doctor read the same section and start no apps.
- **On the network, an app runs under a name of its own** (`squadops-app-<cycle>-<suffix>`), publishes
  nothing, and is reached at `http://<name>:<port>`. `ContainerBackend` takes `app_network` as a
  required argument. `None` keeps loopback publishing for a host run, which the audit scripts and the
  sandbox floor smoke name explicitly.
- **Every detached container is named,** and a `docker run -d` that times out, or exits non-zero (125 to
  127 can leave a container created and never started), is removed by that name before the error is
  raised. Before, it left an unnamed container nobody could find (the MacBook
  lane's note on #2450).
- **Setup steps keep the install network,** with egress for dependencies and no secrets. The app, which
  holds the evaluation secrets (SIP-0112 Q40), has no route out.
- **SIP-0113's scenario runner joins the same network** (the PR after #2450 and this one, at the MacBook
  lane's review of this PR). The app it starts holds the evaluation secrets, so on the network it has no route
  out and no host port, and its setup steps keep the install network with no secrets. The factory hands it
  `app_network`, and the runner and the backend share one placement (`adapters/sandbox/placement.py`).

**Evidence.**
- **Read live on the Spark's Docker** with a throwaway internal network and the sandbox image:
  - an app answered 200 by name from a peer on the network;
  - the app's own connection out failed, "Network is unreachable";
  - it published no host port.
- **The wiring test** enters at `build_app` with the env compose writes, and asserts the app's container
  spec on the network with nothing published (`tests/unit/sandbox/test_app_network.py`).
- **A compose guard** asserts the network is internal, its name is the one the service reads, and only
  the service joins it.

**Who ruled it.** The owner, 2026-10-18, on #2451: "An internal, no-egress `sandbox-apps` network that
the sandbox service joins. Apps run on it by container name with no host port, and the network's name
reaches the service through a required `SQUADOPS__SANDBOX__APP_NETWORK`. The Spark lane builds it; the
MacBook lane reviews."

### 11i. A pinned revision's content is read through the port (2026-10-18, §4.6, §7 item 3; §11g; contract 3; SIP-0112 E.4.3; implementer's record, for the owner)

**Why.** SIP-0112's E.4.3 captures a change back from the sandbox into a product's repository. It needs
the content of the revision a cycle accepted: its files, binary ones included, and their executable
bits. Nothing exposed it. The store keeps hashes, not contents, so the live tree is the only copy.

**What changed.**
- **`read_workspace_revision(revision)` on `ExecutionSandboxPort`,** beside §11g's seed. It returns a
  `RevisionContent`: the revision, its files as text or bytes, and its executable bits.
- **It reads the way a disposable copy does** (`WorkspaceStore.read_pinned`, which X-3a's
  `disposable_copy` now uses too). It reads only while the live tree matches the pin, and holds what
  was read to the revision's ID, so a patch landing mid-read returns nothing rather than a mix of two
  revisions. A tree that moved is refused.
- **The service answers at `GET /api/v1/workspaces/{cycle_id}/revisions/{revision_id}`,** in the
  seed's wire form: text under `files`, base64 under `binary_files`, and `executable`. A revision the
  cycle never held is 404, and a tree that moved is 409. The two directions of the wire's encoding are
  one pair in `squadops.sandbox.models` (`wire_files`, `decode_binary`), used by the client and the
  service alike.
- **The noop refuses:** its seed stored nothing, so it has nothing to read.

**Evidence.** `tests/unit/sandbox/test_read_revision.py` seeds one checkout, with a `\r\n` file, a
binary file and an executable bit, and reads it back exactly, over HTTP and in process. It refuses a
tree edited or patched after its pin. Three mutations are each caught: the client dropping binaries,
the pin check removed, and the executable bits dropped.

**Who ruled it.** The MacBook lane asked for it in its review of #2456, as contract 3's consumer, for
E.4.3 (#2410). It is the implementer's change, for that lane's review and the owner's.

### 11j. A seeded workspace is released through the port, and the release keeps the operation journal (2026-10-19, §4.6, §7 items 11 and 12; §11g; #2473; implementer's record, for the owner)

**Why.** Nothing released a workspace seeded through the port (§11g). SIP-0112's inherited baseline
(E.4.2, #2468) seeds `baseline-<project>-<commit12>` for each capture, and a source-backed run (E.4.3)
seeds one live tree per Cycle, so the sandbox root only grew. The store had leases
(`touch_lease`, `cleanup_expired`), but nothing called them.

**What changed.**
- **`release_workspace(cycle_id)` on `ExecutionSandboxPort`,** beside §11g's seed and §11i's read. The
  consumer calls it once it has recorded what it needs: the inherited baseline after
  `record_inherited_baseline`, a source-backed run at its teardown. An application started from the
  workspace is stopped first, since the release takes the tree away beneath it.
  - The service removes the cycle's workspace.
  - The client calls `DELETE /api/v1/workspaces/{cycle_id}`, which answers 204. An ID outside the
    store's pattern is 400 `INVALID_WORKSPACE`. A `..` is resolved in the URL before any route
    matches, so it answers 404 and deletes nothing.
  - The noop stored nothing, so it releases nothing.
  - Releasing an absent workspace is no error (§7 item 12).
- **A release, a cleanup and a lease sweep keep the operation journal.** The journal (§7 item 11) lives
  in the cycle's directory (`<root>/<cycle_id>/evidence/`), and the store removed that whole directory.
  The store now removes only its own entries (`workspace/`, `copies/`, `revisions/` and the lease),
  and removes the directory once nothing is left in it. The lease goes last, so a removal that a crash
  interrupts is still leased and the next sweep finishes it.
- **Not built: the lease at seeding.** #2473 offered either a lease taken at seeding with a sweep, or an
  explicit release. The consumer knows when it has recorded what it needs, so the explicit release is
  the one built. A consumer that dies before releasing leaves its workspace, as before. The store's
  lease and sweep remain for a caller that wants a time bound.

**Evidence.** `tests/unit/sandbox/test_seed_on_the_port.py` seeds a workspace through the service and
through the HTTP client, runs a journalled operation on it, and releases it twice. The cycle's
directory then holds only `evidence/`, no revision is left, and the journal reads every operation. An ID
outside the pattern is refused with nothing deleted. `tests/unit/sandbox/test_workspace_store.py`
sweeps a cleaned and an expired cycle, with and without a journal. On the store's previous whole-
directory removal, the journalled cases of both tests fail.

**Who ruled it.** The Spark lane raised it in its G4 review of #2468. The sandbox's port and service are
that lane's files by ownership (CLAUDE.md's lanes; this SIP was its 1.4 headline), so the explicit
release is the implementer's choice, for the MacBook lane's review as its caller and the owner's.

### 11k. The scenario runner reads a started tree's client routes, with the evaluator image's own Chromium (2026-10-28, §4.6, §7 items 2, 9 and 10; §11e, §11h; SIP-0109 §24co; #2619; implementer's record, for the owner)

**Why.** SIP-0109 §24co renders a repository-backed product's client routes at its increment's acceptance. The product
can only be started here, from its declaration (§11e). §11c's dropped row, campaign evaluation through this sandbox,
stands for a sample application, whose routes are still read in the qa container. For a repository-backed product,
its acceptance (SIP-0109 §24cl) and its routes run here.

**What changed.**
- **`POST /api/v1/evaluations` takes `routes`:** each one a client route and, for a parameterized one, its seed
  (`RouteRequest`). The answer carries each route's reading (`TreeEvaluation.routes`: the path it was read at, the
  test ids its page's elements carried, or why it wasn't read). It defaults to none, so every existing caller's request
  and answer are as they were.
- **When:** after the quality reading and the scenarios, so a route's seed reaches neither. The app is the one started
  from the declaration in the disposable copy, and it's torn down after.
- **How:** Chromium runs as the evaluator image's entrypoint (`ContainerSpec.entrypoint`, rendered as `docker run
  --entrypoint`, an inert default for every other spec). It dumps each page's DOM with the flags the qa role reads a
  sample application's pages with.
  - It runs on the app network, at the app's IP (a UI server may refuse a name it doesn't know), with caps dropped,
    no new privileges, nothing mounted and nothing of the app's environment, as the evaluator's other runs are (§11h).
  - The image's driver isn't run, so the image and its tag are unchanged.
- **A seed** is sent to the app's own address, with the path as the manifest writes it (SIP-0113 §10n ruling 8).
- **What reads unread, with why:** no `ui_base`, no app network, the image absent, the browser's container not run, a
  non-zero exit, nothing dumped, no seed, or a seed refused. A reading's detail is scrubbed of the evaluation's
  secrets, as every free text is (§11e).

**Evidence.** `tests/unit/sandbox/test_scenario_runner_routes.py` and `test_http_surface.py`, and the live read
SIP-0109 §24co records: the `-7` image's Chromium as its entrypoint, on a throwaway network, with nothing left running.

**Who ruled it.** The implementer, building SIP-0109 §24co, for the owner's review. The sandbox's service is the Spark
lane's by ownership.
