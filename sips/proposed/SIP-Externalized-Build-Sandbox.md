---
title: Ephemeral Application Sandbox
status: proposed
author: jladd
created_at: '2026-07-08T00:00:00Z'
updated_at: '2026-07-14T00:00:00Z'
---
# SIP: Ephemeral Application Sandbox

*(Evolved from "Externalized Build Sandbox," same SIP — scope expanded from
build-job execution to the full application sandbox after the 2026-07-14
live-validation campaign and two second-opinion review rounds; see
`docs/ideas/IDEA-Functional-App-Obstacles-and-Roadmap.md` v3.)*

## Status
Proposed

**Targets:** **v1.4 headline component** (re-targeted from the 2.0 vision arc on
2026-07-14 — see Motivating case). Together with
SIP-Contract-First-Build-Scaffolding it forms the "Verified Canonical App
Build" vertical slice: *one canonical stack can be deterministically composed,
executed, and honestly verified without manual intervention.*
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
**Coordinates with:** SIP-Contract-First-Build-Scaffolding (*what* is
deterministic vs generated — orthogonal and sibling in the 1.4 slice),
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

This SIP proposes the **Ephemeral Application Sandbox**: a cycle-scoped
execution sandbox, managed by a dedicated **workspace/execution service**,
containing a **persistent cycle workspace** and disposable **build**,
**runtime**, and **probe** execution units. Agents never touch a container
runtime; they request **typed operations** (`build_frontend`,
`start_application`, `probe_http_endpoint`, …) that return structured
semantic results. Authoritative verification runs **clean-room** — a freshly
provisioned environment against the persisted workspace — never from the
dirty convergence container.

Agent images become lean and stack-agnostic; untrusted execution is isolated;
the environment becomes a pinned, preflight-validated contract; and
executable + functional verification finally happens where the application
contract says the app must run.

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
  build/runtime/probe execution units, owned by a dedicated
  workspace/execution service.
- Agents and runtime-api never hold a container-runtime socket; the execution
  service is the only privileged component, exposing typed operations only.
- Agent images carry **no** build toolchain; retire the #306 qa-Node branch
  once the sandbox path is live (the exit #306's text promised).
- A **Build Environment Contract**: pinned images + required tools/versions,
  validated at **preflight** — advertised-vs-provided mismatches fail before
  dispatch, never at task time.
- Typed operations with structured semantic outputs (never raw console text
  as the contract).
- **Clean-room rule:** interactive builder convergence may reuse a warm unit
  within one bounded attempt; authoritative final verification always runs in
  a freshly provisioned environment against the persisted workspace.
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

The Stack Blueprint (SIP-Contract-First-Build-Scaffolding) declares a
deterministic environment definition: base environment identity, required
tools/versions, build/runtime operations, exposed endpoints, mounts, env
inputs, network policy. The container adapter renders that into
Dockerfiles/compose for the canonical stack (checked in, deterministic,
never LLM-authored). The Dockerfile is one representation, not the contract.

### 4.3 The workspace/execution service

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

- **Persistent workspace per cycle** — required for iterative builder
  patches, attempt comparison, outer-loop correction, evidence lineage.
- **Warm execution unit within one bounded builder convergence attempt** —
  build → inspect → patch → rebuild without re-provisioning. Destroyed when
  the attempt ends.
- **Fresh environment for authoritative verification** — final
  executable/functional evidence always comes from a newly provisioned
  environment against the persisted workspace. Prevents false success from
  lingering processes, undeclared files, mutated state, or previously
  installed undeclared packages. **`verified_functional` never depends on
  the dirty convergence container.**

### 4.6 Dependency caching

Shared **read-through download caches** only (npm/wheel caches, browser
binaries, base layers). No shared installed-dependency directories
(`node_modules`, venvs); dependencies install into the cycle sandbox;
lockfile/manifest captured as evidence; the clean-room build must succeed
without undeclared workspace state. Cache hits are recorded but never change
the semantic result.

### 4.7 Verification levels and check locus

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
  alongside `test_runner.py`'s three sites.

### 4.8 Correction-policy integration: locus × mode

Failure classification gains two dimensions — **locus** (infrastructure /
application / orchestration / verification) and **mode** (syntax / build /
startup / runtime / timeout / unsupported / unavailable):

- **Infrastructure execution failure** (binary missing from declared env,
  container won't start, image unresolvable, service unavailable): retry
  infra, continue after environment correction, or block as
  infrastructure-unverified. **Never consumes application correction
  budget, never takes the `patch` path.** (Roll-4 defect: an
  `execution`-classified missing-binary failure took `patch` and burned the
  budget.)
- **Application execution failure** (app crashes, build reveals a code
  defect, health never ready, browser hits an app exception): local builder
  patch, outer correction, or replan — these are patchable and budgeted.

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

## 6. Migration

1. Land the execution-service skeleton + workspace provisioning + Docker
   adapter (on `ContainerPort`), behind config with a NoOp default (parity
   with today).
2. Publish the pinned canonical environment image(s) for fastapi+react.
3. Route `test_runner.py`'s three exec sites and `CommandExitZeroCheck`
   through typed operations; unit tests assert parity.
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

## 8. Open Questions

1. Execution-service transport: HTTP on localhost vs unix socket vs queue —
   and its auth story against the #326 service-identity pattern.
2. Workspace representation: bind-mounted host dir per cycle vs volume vs
   content-addressed store (the v1 "files inline in BuildJob" is resolved —
   workspace revisions, not inline bytes; the storage backend is open).
3. Browser probe runtime: headless chromium in the probe image — acceptable
   image weight for v1.4, or HTTP-only with the `verified_executable` name?
4. Toolchain/environment image ownership and publish pipeline (this repo vs
   deployment-profile repo).
5. How much of the locus × mode taxonomy lands in this SIP vs the
   correction-policy follow-up (#413 lineage)?

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
- SIP-0068, SIP-0071, SIP-0086, SIP-0096; SIP-Contract-First-Build-Scaffolding
  (sibling); SIP-Edge-Deployment-Profile; SIP-Capability-Backed-Agents.
- `ContainerPort` — `src/squadops/ports/tools/container.py`;
  `test_runner.py`; `acceptance_checks.py` (`CommandExitZeroCheck`).
