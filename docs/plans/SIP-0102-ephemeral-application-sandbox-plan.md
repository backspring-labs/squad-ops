# SIP-0102 Ephemeral Application Sandbox — Implementation Plan

**SIP:** `sips/accepted/SIP-0102-Ephemeral-Application-Sandbox.md` (accepted 2026-07-26, PR #617)
**Release:** v1.4 headline, Lane S surfaces — the golden path's execution half (sibling: SIP-0099)
**1.4 floor (arc rev 2):** build runner + `start_application` + HTTP health probe, with
environment contract + preflight and clean-room verification. Browser probe, probe-as-peer
implementation, and operator CLI/caddy → 1.5+; the honest 1.4 verdict name is
`verified_executable`.
**Arc checkpoints this plan serves:** engine-turns-over (arc fallback clause 2 — the floor
must execute the golden path end-to-end at least once before the evidence release is
otherwise cut-ready) and the cut gate (≥3 consecutive Phase-0 benchmark runs).

## Status & handoff (updated 2026-07-26)

The single in-repo source of truth for where SIP-0102 stands — read this first.

| Phase | Milestone unlocked | State |
|---|---|---|
| 102.1 Execution boundary (service skeleton + workspace + Docker adapter) | the execution boundary exists | ⬜ not started |
| 102.2 Environment contract + canonical image + preflight | environment is a pinned, validated contract | ⬜ |
| 102.3 Typed-op relocation of in-process exec sites | execution leaves the agent trust boundary | ⬜ |
| 102.4 Clean-room verification + outcome integration | verdicts are clean-room and honestly named | ⬜ |
| 102.5 Builder warm-unit convergence | convergence iterates inside the sandbox | ⬜ |
| 102.6 Retirement + golden-path live validation | lean agent images; engine-turns-over proven | ⬜ |

**Lane note (recorded deviation):** SIP-0102 is the Lane-S headline (test-runner /
build-check / agent-image / deploy-infra file ownership), but implementation is being
driven from the **Mac lane** (decided 2026-07-26 — Spark is saturated running the 98.5
measurement lineage). Collision rules stand: the executor god-file stays M-owned;
integration goes through the SIP-0097 `RunCompletion`/`RunLedger` boundaries; changes to
`test_runner.py` / build-check surfaces / agent images (102.3, 102.6) coordinate with the
Spark lane explicitly before merge, and Spark remains the integration validator for the
assembled release. The execution service *deploys* on the Spark host regardless of where
it is authored.

## Standing constraints

- **Data-driven, no flag** (the 98/99 doctrine): sandbox presence is config
  (`SQUADOPS__EXECUTION__*`) with a NoOp default; unconfigured ⇒ byte-identical behavior.
- **Zero contract revisions on probe re-home** — SIP-0098 §98.6's reserved constraint:
  `ExecutionProfile` is runner-owned mechanics precisely so 102.3 moves execution without
  touching verification contracts.
- **`ran=False` semantics carry forward** (SIP §4.4): environment unavailable ≠
  deliverable failure; rolls up through SIP-0096 as an explicit environment-contract
  failure, never a false red.
- **Prompt content in managed assets** (#448), **new capabilities designed from
  SquadOps patterns** (ports + factory + always-inject NoOp), **API routes conform to
  the lane standard** (#218) — the execution service's own API is a *new* surface: its
  conventions get proposed at 102.1 review, not invented ad hoc.
- Runtime-affecting PRs get a live smoke/lite cycle on the deployed stack before merge.

## Phase ladder

### 102.1 — Execution boundary: service skeleton, workspace provisioning, Docker adapter
*(SIP migration step 1; unlocks: the execution boundary exists)*

- **Port + domain models** (`src/squadops/ports/`): `ExecutionSandboxPort` exposing the
  floor's typed operations (`install_dependencies`, `build_frontend`, `run_backend_tests`,
  `start_application`, `probe_http_endpoint`, `apply_workspace_patch`,
  `read_build_diagnostics`) returning frozen semantic-result dataclasses; the v1
  `BuildSandboxPort` shape (`run_build(job) → BuildResult`) survives as the build-runner
  layer's internal contract. `WorkspaceRevision` model implementing §4.6 semantics
  (every op records a revision; boundaries: seeding / applied patch / promoted outputs;
  warm-attempt dirty state never referenceable; verification pins by content match).
- **Execution service skeleton** (`src/squadops/execution/` proposed — confirm home at
  review): narrow authenticated API, workspace provisioning (cycle-scoped, revision
  capture), typed-op dispatch, TTL'd idempotent cleanup recoverable after restart
  (§7 items 11–12), evidence capture that persists through orchestration crashes (#427).
- **Docker adapter** (`adapters/execution/`) on `ContainerPort`
  (`src/squadops/ports/tools/container.py`): resource limits + timeouts mandatory,
  privileged/host-networking forbidden, capabilities dropped, no host paths mountable
  outside the cycle workspace, network deny-by-default (§7 items 8–10).
- **NoOp adapter is the factory default** — parity with today; always-inject pattern.
- Tests: §4.6 revision semantics enforced by unit tests; NoOp parity regression guard;
  adapter contract tests (no Docker in unit tier — the adapter integration tests ride
  `tests/integration/adapters/`).
- **Decisions resolved at this phase's review:** transport + auth (open decision 1),
  storage backend (2), compose service addition (3).

### 102.2 — Environment contract, canonical image, preflight
*(SIP migration steps 2+4; unlocks: environment is a pinned, preflight-validated contract)*

- **Environment-contract schema**: checked-in canonical definition for
  `fullstack_fastapi_react` (§4.2 status note — the generalized `StackBlueprint` is
  deferred to SIP-Stack-Blueprint-Contract; this definition migrates there when stack #2
  arrives). Deterministic, pinned image digests, required tools/versions; the Dockerfile
  is an adapter rendering, never the contract.
- **Pinned canonical environment image(s)** for build + runtime (one combined
  build+runtime container is acceptable for 1.4; contracts stay separate).
- **Preflight**: advertised-vs-provided reconciliation (the roll-4 failure class) as a
  `squadops doctor` category + cycle-create check on the SIP-0095 preflight seam —
  mismatches fail before dispatch, never at task time (§7 item 7's preflight half).
- **Read-through dependency caches** (npm/wheel/base layers) — cache hits recorded,
  never semantic; cached deps cannot substitute for undeclared ones (§7 item 13).
- Every operation records image identity + environment-contract identity (§7 item 4).
- **Decision resolved here:** image ownership + publish pipeline (open decision 4 —
  moved out of the SIP).

### 102.3 — Typed-op relocation of in-process execution
*(SIP migration step 3; unlocks: execution leaves the agent trust boundary)*

- Route through `ExecutionSandboxPort` when configured (NoOp ⇒ today's in-process path,
  byte-identical): `test_runner.py`'s exec sites; `CommandExitZeroCheck`
  (`acceptance_checks.py`); the 98.4/98.5 probe path (`probe_runner.py` boot+probe —
  its `ExecutionProfile` re-homes with zero contract edits, per the 0098 §98.6 reserve).
- Wire shapes unchanged through the #420/#421 seams; parity unit tests assert identical
  check rows from both paths.
- **Coordination flag:** `test_runner.py`/build-check are Spark-owned files and
  `acceptance_checks.py` is the explicitly-coordinated shared surface (#421/#425
  precedent) — Spark reviews before merge.

### 102.4 — Clean-room verification + outcome integration + failure classification
*(SIP migration step 5, second half; unlocks: verdicts are clean-room and honestly named)*

- **Clean-room final verification** at run finalization: fresh provision against the
  pinned workspace revision (§4.5 invariant; §7 items 5–6), integrated through the
  SIP-0097 `RunCompletion`/`RunLedger` boundaries (executor stays M-owned).
- Roll `verified_executable` (and the `verified_functional` name, dormant until the
  browser probe exists) into SIP-0096 `CycleOutcome` derivation; evidence identifies
  workspace revision, environment contract, image, and operation versions (§7 item 15).
- **Locus × mode wiring for sandbox-originated failures** (§4.9): infrastructure
  failures never take `patch`, never burn application correction budget; task-time
  environment-contract violations surface as explicit contract failures (§7 item 7).
  Resolve the `FailureLocus` (#568 artifact-ownership axis) name reconciliation here
  (open decision 5) — the two compose (locus gates patchability; ownership routes the
  repairing role) but must not share a name ambiguously.

### 102.5 — Builder warm-unit convergence
*(SIP migration step 5, first half; unlocks: convergence iterates inside the sandbox)*

- SIP-0086 builder convergence loop adopts the warm execution unit within one bounded
  attempt: build → inspect (`read_build_diagnostics`) → patch (`apply_workspace_patch`,
  cutting revisions per §4.6) → rebuild without re-provisioning; unit destroyed at
  attempt end. Warm state never feeds a verdict (§7 item 5).

### 102.6 — Retirement + golden-path live validation
*(SIP migration steps 6+7; unlocks: lean agent images + engine-turns-over)*

- **Retire the #306 qa-Node branch and qa runtime test deps** — agent images return to
  runtime-only. This is the payoff and the regression guard; agent-image/deploy surfaces
  are Spark-owned, so this lands coordinated or handed off.
- **Live validation:** one canonical `full` cycle walking the entire golden path on the
  Spark deploy — scaffold → fill → build → start → HTTP health → clean-room
  `verified_executable` — including the deliberately-deferred **#419 builder-seam live
  proof** (three cycles stalled pre-builder on environment; this is the revision's
  motivating evidence closing out).
- This satisfies the arc's **engine-turns-over** checkpoint and opens Phase-0 benchmark
  runs (cut gate: ≥3 consecutive, squad-authored-manifest mode only).

## Acceptance mapping (SIP §7 → phases)

| §7 item | Proven by |
|---|---|
| 1 agents can't reach the container runtime; 2 typed ops only; 8 no host paths; 9 limits/no-privilege; 10 network deny-by-default; 11 crash-surviving logs; 12 idempotent cleanup | 102.1 |
| 3 every execution against a declared revision | 102.1 (§4.6 tests), exercised end-to-end 102.3–102.4 |
| 4 image + contract identity recorded; 7 undeclared tools → explicit contract failure (preflight half); 13 caches never substitute | 102.2 |
| 7 (task-time half) | 102.4 |
| 5 convergence vs authoritative distinguished | 102.4 + 102.5 |
| 6 clean-room final verification; 15 evidence pins revision/contract/image/op versions | 102.4 |
| 14 probes outside the app process boundary | partial in 1.4 — probes execute service-side, outside the app process, but full probe-as-peer network isolation is 1.5+ (honest note rides the evidence) |
| 16 exposure explicit/TTL-leased | deferred 1.5+ with `expose_application` |

## Open decisions (resolve at the flagged phase, not before)

1. **Transport + auth** (102.1): HTTP-on-localhost vs unix socket vs queue for
   runtime-api → execution service, against the #326 service-identity pattern. Lean:
   HTTP on localhost with service identity — matches existing patterns and survives the
   later remote-host split; confirm at review.
2. **Workspace storage backend** (102.1): bind-mounted host dir per cycle vs volume vs
   content-addressed store. §4.6 fixes the semantics; only capture mechanics are open.
   Lean: bind-mounted dir + content-hash manifest per revision — cheapest thing that
   honestly implements pinning.
3. **Compose service addition** (102.1): repo rule requires explicit approval for
   docker-compose changes — the service entry (name, port) gets proposed alongside the
   102.1 PR, not silently added.
4. **Environment-image ownership + publish pipeline** (102.2): this repo vs
   deployment-profile repo (moved out of the SIP at acceptance).
5. **Locus × mode scope + `FailureLocus` naming** (102.4): how much taxonomy lands here
   vs the correction-policy follow-up (#413 lineage), and the #568 name reconciliation.

## Out of scope (1.5+ per the SIP's scope split)

- Browser probe (`run_browser_smoke`) and probe-as-peer *implementation* (peer isolation).
- Operator access: `squadops sandbox up/down`, `--hold`, caddy routing,
  `expose_application`.
- Multi-stack generalization (v1.6; the canonical fastapi+react blueprint only).
- Sandbox runtime hardening (rootless/socket-proxy/gVisor — 1.5 stabilization, SIP §7
  candidates).
- Remote execution adapter (SIP-Edge-Deployment-Profile target).
