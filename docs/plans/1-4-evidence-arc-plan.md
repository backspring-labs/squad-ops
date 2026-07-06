# 1.4 Evidence Arc — Execution Plan (1.3 riders → 1.4 → 1.6 gates)

**Established:** 2026-07-06 · companion to `1-3-x-two-lane-plan.md` (which governs the
current release and is **not disturbed** by this plan) and `2-0-roadmap-reconciliation.md`
(whose Finding-5 feature-lane line this supersedes: 1.4 is now **duty durability +
verification evidence integrity**, not duty durability alone).

## The thesis (one sentence per release)

- **1.3 (current)** stabilizes the *structure* (god-object decomposition, port de-leak, comms push consumer).
- **1.4** makes the *evidence* trustworthy (Verification Evidence Integrity SIP + SIP-0091 duty durability).
- **1.6** automates decisions *over* trusted evidence (Campaign Orchestration).
- **2.0** compounds on top (Capability-Backed Agents, Self-Improvement, Test Bay, Scorecard).

The ordering is load-bearing: Campaign's continuation policy reads the `CycleOutcome`
roll-up the evidence SIP defines, and its recruitment safety depends on lease hardening
(#288). Every gate below exists to keep "automate over evidence" strictly behind
"evidence is honest."

## SIP map

| SIP | Status | Release | Role in the arc |
|---|---|---|---|
| Verification Evidence Integrity | proposed (`sips/proposed/`) | **1.4 headline** | integrity invariant, provenance, inert-check detection, `CycleOutcome` contract |
| SIP-0091 Duty Durability via Temporal | accepted (fix stale `Targets: v1.3` → 1.4, #335) | **1.4 headline** | durable responsibility |
| SIP-0090 Embodiment Phase 2 (Discord) | accepted (phased) | 1.4 **or** 1.6 — open decision | first live embodiment consumer |
| Campaign Orchestration | proposed (revised 2026-07-06 per #334) | **1.6 headline** | objective envelope + continuation policy |
| Self-Improvement + Test Bay; Capability-Backed Agents; Cycle Evaluation Scorecard | proposed (vision/backlog) | 2.0 / post-1.6 | consumers of the trusted-evidence substrate |

## Phase-by-release execution

### Now / patch lane (no release gate — ship when ready)

| Item | Lane | Notes |
|---|---|---|
| ~~#276 stub-fallback + frontend-build checks~~ | S | **already shipped** (PRs #289/#290); #296 **closed** (`5cb22ce`). What remains of #276 is #291 (executor `required_files`, Lane M → rides the 1.4 evidence arc). **#152's #276-gate is therefore satisfied.** |
| #306 Node.js in agent image | S (Mac-doable) | bug; makes the shipped #290 frontend check actually executable |
| #329 aio_pika log demotion | S (Mac-doable) | restores fleet observability this week |
| #326 `/health` write-lane fix | S (Mac-doable) | untracked security hole → 1.3-hardening-shaped |
| #335 docs hygiene (ROADMAP stats, SIP-0091 tag, untracked refs) | M | direct-push OK (simple docs) |

The remaining bug fixes ship as ordinary patches; the evidence SIP locks the *class*
(its Phase 2 covers the shipped #289/#290 checks with classification + provenance
conformance, no behavior change).

### During 1.3 (riders — additive to the two-lane plan, not amendments)

| Item | Lane | Why it rides here |
|---|---|---|
| **Evidence SIP Phase 0** — verification audit (confirm the SIP's §6.1 classification mapping + §8 conformance table against code and the accepted SIP-0092/0070 texts; semantics are decided in the SIP, not here) | M | docs-only, feature-free, keeps 1.4 unblocked |
| **#288 lease-arbitration fix** | M | lease-semantics *hardening* (1.3-legal); runtime surface is Lane-M-owned; hard gate for 1.6 Phase 2 — do not let it slip past 1.5 |
| Evidence SIP proposal PR → design review → **accept** | M (maintainer) | acceptance is a design commitment on main; the 1.4 feature branch starts from it |
| #336 docs-drift lint | S | CI/test-infra is Lane-S-owned |

Note: #295 stays exactly where the 1.3 plan put it (rides #186). The evidence SIP's
choke point attaches to the **post-#186 completion boundary**, so #186 landing in 1.3
is itself an arc prerequisite — a reason to protect the 1.3 batch, not change it.

### 1.4 (feature minor — the evidence release)

- **Evidence SIP Phase 1** — aggregation function + `blocked_unverified` verdict +
  provenance fields + `required_checks` profile schema. (Lane M: cycles/executor seam.)
- **Evidence SIP Phase 2** — conformance of the real gaps (rev-2 §8): the two named
  SIP-0070 amendments (SKIP-only→PASS pulse fix; D13 required-frontend blocking),
  #306 image fix + preflight tooling-parity, #291 required-files as a checked contract,
  and classification/provenance retrofit of the shipped #289/#290 checks. Each lands
  with a live `lite` cycle per the live-validation rule. (Split M/S along the usual
  file ownership: executor/handlers = M; test-runner/build-check/agent-image = S.)
- **Evidence SIP Phase 3** — `CycleOutcome` roll-up persisted + consumed by wrap-up,
  gate waiver flow, doctor verification category (non-executable + inert reporting;
  console badging and a dedicated event are deferred until demand).
  #114 (typed-check evaluation surfacing) rides this phase.
- **SIP-0091 duty durability** per its own spec (Lane M).
- **Open decision (make at 1.4 planning, not now):** does SIP-0090 Phase 2 (Discord)
  ride 1.4 or wait for 1.6? Leaning 1.4 if capacity allows — it is the first *live*
  embodiment test and independent of the evidence work.
- **Cut gate:** standard checklist (bump → CHANGELOG/markers → regression → tag +
  Release → rebuild+deploy+verify → E2E smoke → SIP promotion sweep). Promotion sweep
  expects: Verification Evidence Integrity → implemented (all phases), SIP-0091 →
  implemented; SIP-0090 stays accepted unless Phase 2 shipped *and* its arc is complete.

### 1.5 (stabilization — feature-free by rule)

Home for: #288 if it slipped 1.3; evidence-arc hardening spillover (provenance-storage
tuning, roll-up persistence cleanup); the next god-module batch (#331 planning_tasks.py
if it didn't ride #152's arc); accumulated debt (#154 residue, #301, #234 follow-through).

### 1.6 (feature minor — Campaign)

Campaign Orchestration accepts and implements **only when its named gates are green**:

| Gate | Where it lands |
|---|---|
| Verification Evidence Integrity implemented (the `CycleOutcome` contract §7.2 reads) | 1.4 |
| #288 lease arbitration fixed | 1.3 (target) / 1.5 (backstop) |
| #316 request-profile naming taxonomy (for policy-derived `next_request_profile`) | 1.3–1.5, Lane S (`SIP-Cycle-Request-Profile-Naming-Taxonomy.md` exists in proposed) |
| Campaign SIP open questions 1 (fork) and 5 (defer mechanism) resolved | pre-acceptance |

## Issue → arc map (everything filed 2026-07-04/05)

| Issue | Arc slot |
|---|---|
| #326 /health write lane | patch/1.3 hardening (S) |
| #327 prompt manifest | patch (S); Phase-2-adjacent (deploy-time verification = same honesty principle) |
| #328 broker hygiene + doctor queue check | patch/1.3 (S) |
| #329 log demotion | patch now (S) |
| #330 Prefect loop starvation | investigate before any long Spark cycle; no release gate |
| #331 planning_tasks.py | 1.3 if #152's layout extends cheaply, else 1.5 (M) |
| #332 hoist copy-pasted helpers | 1.3, step 0 of #152 (M) |
| #333 entrypoint fallbacks/env drift | 1.3–1.5 hardening (M) |
| #334 Campaign SIP fixes | **done 2026-07-06** (SIP revised; close via the proposal PR) |
| #335 docs hygiene | now (M, direct-push) |
| #336 docs-drift lint | 1.3 rider (S) |

## What must be true before each "go"

1. **Evidence SIP acceptance** ← Phase 0 audit complete (no vocabulary collision with 0092/0070/0079).
2. **1.4 cut** ← evidence Phases 1–3 live-validated (one `lite` cycle blocking honestly on a required unrunnable check; one completing with disclosure); SIP-0091 arc complete.
3. **Campaign SIP acceptance** ← the four 1.6 gates above.
4. **Any 2.0 measurement work (scorecard, self-improvement)** ← consumes `CycleOutcome` only; never raw check results.

## Ratification note

This plan does not edit `docs/ROADMAP.md`. When ROADMAP is next touched (#335), apply:
the Finding-4 remap from `2-0-roadmap-reconciliation.md`, the stats-block fix, **and**
the 1.4 line from this plan (duty durability + verification evidence integrity as the
even-minor headliners, embodiment Phase 2 as the open rider).
