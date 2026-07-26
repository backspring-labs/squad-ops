---
title: Ephemeral Application Sandbox
status: proposed
author: jladd
created_at: '2026-07-08T00:00:00Z'
updated_at: '2026-07-26T00:00:00Z'
---
# SIP: Ephemeral Application Sandbox

*(Evolved from "Externalized Build Sandbox," same SIP — scope expanded from
build-job execution to the full application sandbox after the 2026-07-14
live-validation campaign and two second-opinion review rounds; see
`docs/ideas/IDEA-Functional-App-Obstacles-and-Roadmap.md` v3.)*

## Status
Proposed

**Targets:** **v1.4 headline component** (re-targeted from the 2.0 vision arc on
2026-07-14 — see Motivating case). Together with SIP-0099
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
workspace is an ordinary host directory, and `qa_handoff.md` still documents
how to run it directly.

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
