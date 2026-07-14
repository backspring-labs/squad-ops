# 1.4 Evidence Arc — Execution Plan (1.3 riders → 1.4 → 1.6 gates)

**Established:** 2026-07-06 · companion to `1-3-x-two-lane-plan.md` (which governs the
current release and is **not disturbed** by this plan) and `2-0-roadmap-reconciliation.md`
(whose Finding-5 feature-lane line this supersedes: 1.4 is now **duty durability +
verification evidence integrity**, not duty durability alone).

## North Star — why this arc exists

Two outside-in capabilities are the payoff the whole arc builds toward; every release
below is a rung under them, not an end in itself:

- **A — Experimentation over squads.** Run bounded experiments on squads building apps /
  performing tasks, measure outcomes, and surface either a **config efficiency** (tune
  what we have) or a **capability gap** (we need something we don't). This is the 2.0
  *Test Bay / Self-Improvement* pillar: the 1.8 scorecard generalized from grading *one*
  cycle to comparing *many* (baseline vs challenger, with isolation/replay so the
  comparison is fair).
- **B — Capability-pack authorship.** The squad itself authors new agent capability packs
  from industry/domain knowledge via the extension mechanism (SKILL.md-format bundles +
  references) — continually finding new ways to build better. This is the 2.0
  *Capability-Backed Agents* pillar; here a Campaign's *deliverable* is a reusable pack,
  not an app.

**They are one flywheel:** A detects the gap → B authors the pack that fills it → A
re-measures the delta. It closes only if the evidence underneath is honest — the entire
reason for the ladder: honest evidence (1.4) → automate over it (1.6) → grade it (1.8) →
**experiment over grades (A)** → **author from gaps (B)**. The dependency is strict —
**A before B**: never adopt a capability you cannot yet measure, or you are back to
intuition-over-evidence, the risk this arc exists to kill.

**Invocation engine (working hypothesis, not yet committed):** probably *not* a new
engine — **Campaign parameterized by objective type** (`build-app` | `run-experiment` |
`author-capability-pack`), one orchestrator with a typed objective/deliverable. Hold this
hypothesis until it demonstrably breaks before minting a separate engine (the same
"don't name a subsystem before you need it" discipline that de-personified the scorecard).

**What this demands of 1.4 now:** both visions are *experiments over configuration*, and
you can only compare configs you recorded. So `CycleOutcome` (1.4) and `CycleAssessment`
(1.8) must carry **config + squad + capability-pack provenance** (which model / profile /
packs / memory were active) so the Test Bay can later attribute an outcome delta to a
config change. Design it in now; it is expensive to retrofit.

## The thesis (one sentence per release)

- **1.3 (current)** stabilizes the *structure* (god-object decomposition, port de-leak, comms push consumer).
- **1.4** makes the *evidence* trustworthy (Verification Evidence Integrity SIP + SIP-0091 duty durability).
- **1.6** automates decisions *over* trusted evidence (Campaign Orchestration).
- **1.8** makes the evidence *graded* (a thin cycle-evaluation scorecard: `CycleAssessment` over the `CycleOutcome` seam) — the release where the SquadOps thesis ("a governed squad beats a single strong model on long-horizon work") becomes falsifiable.
- **2.0** compounds on top (Capability-Backed Agents, Self-Improvement, Test Bay) over a *trusted, shipped* scorecard — not one it invents in the same release.

The ordering is load-bearing, and it extends one rung at a time: Campaign's continuation
policy (1.6) reads the `CycleOutcome` roll-up the evidence SIP (1.4) defines, and its
recruitment safety depends on lease hardening (#288); the grading layer (1.8) is a new
*reader* of that same `CycleOutcome` seam; and 2.0's self-improvement acts only on grades
the 1.8 scorecard has already shipped and live-proven. Every boundary keeps the consumer
of a trust layer strictly behind the release that earns it: "automate over evidence"
behind "evidence is honest," and "compound over grades" behind "grades are trustworthy."

## SIP map

| SIP | Status | Release | Role in the arc |
|---|---|---|---|
| **SIP-0096** Verification Evidence Integrity | **accepted 2026-07-06** (PR #337, rev 2) | **1.4 headline** | integrity invariant, provenance, inert-check detection, `CycleOutcome` contract |
| SIP-0091 Duty Durability via Temporal | accepted (fix stale `Targets: v1.3` → 1.4, #335) | **1.4 headline** | durable responsibility |
| **SIP-0097** Executor Decomposition Boundaries | **accepted 2026-07-06** (PR #340, rev 2) | **1.3** (structural) | produces the `RunCompletion`+`RunLedger` seam SIP-0096 §6.4 wires into (slice 2 scheduled early for exactly this) |
| SIP-0090 Embodiment Phase 2 (Discord) | accepted (phased) | 1.4 **or** 1.6 — open decision | first live embodiment consumer |
| Campaign Orchestration | proposed (revised 2026-07-06 per #334) | **1.6 headline** | objective envelope + continuation policy |
| **Cycle Evaluation Scorecard** | proposed — slice thin from the over-scoped `SIP-Plutarch-Experimentation-and-Cycle-Assessment-Framework` vision doc (retarget off stale `v1.1`) | **1.8 headline** | grades honest evidence: `CycleAssessment` over the `CycleOutcome` seam + benchmark registry + first-wave internal eval packs + model-comparison harness — makes the thesis falsifiable |
| Self-Improvement + Test Bay; Capability-Backed Agents | proposed (vision/backlog) | 2.0 | compound over the *shipped* 1.8 scorecard, never raw check results |

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
| ~~Evidence SIP proposal PR → design review → **accept**~~ | M (maintainer) | **done 2026-07-06** — PR #337 merged; promoted to **SIP-0096** (`sips/accepted/`); the 1.4 feature branch starts from it |
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
- **#419/#420 typed-acceptance seam integrity** (Phase-2-shaped, found via the
  post-#413 validation cycle): builder.assemble evaluates the plan's typed contract
  (SIP-0092 M1.3) through a seam hoisted to the cycle-handler base, and criteria now
  survive distributed dispatch — `asdict()` was flattening `TypedCheck` to dicts the
  handlers misfiled as prose, so M1.3 was silently inert in the field (#420). With
  #413 in, a builder path-contract violation becomes a one-round self-heal instead
  of an unfixable qa.test stall.
- **Evidence SIP Phase 3** — `CycleOutcome` roll-up persisted + consumed by wrap-up,
  gate waiver flow, doctor verification category (non-executable + inert reporting;
  console badging and a dedicated event are deferred until demand).
  #114 (typed-check evaluation surfacing) rides this phase. **Design `CycleOutcome` for
  its two downstream readers now** — Campaign's continuation policy (1.6) and the
  `CycleAssessment` scorecard (1.8) — so 1.8 is a new reader of a stable seam, not a
  re-cut (carry the scorecard's outcome/quality/efficiency/stability fields from the start).
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

### 1.7 (stabilization — feature-free by rule)

Home for: Campaign hardening spillover (continuation-policy edge cases, defer/fork
mechanics from 1.6); `CycleOutcome` persistence/schema tuning ahead of its 1.8 grading
consumer; accumulated debt. Standard odd-minor: substance gates the cut, not the clock.

### 1.8 (feature minor — the grading release)

The release where honest evidence becomes **graded** evidence, and the SquadOps thesis
becomes falsifiable. Headline: a **thin cycle-evaluation scorecard** — not the full
7-subsystem experimentation framework the vision doc describes (its own risk section warns
against "overbuilding the experiment system before the app-building loop is stable").
Ship, in dependency order:

- **`CycleAssessment` scorecard** consuming the `CycleOutcome` roll-up (a new *reader* of
  the 1.4 seam, never a re-cut) — outcome / quality / efficiency / stability at minimum.
- **Benchmark registry** + **first-wave internal eval packs** (Dev, QA, Research, Tool
  Executor — the roles with the clearest starting eval paths).
- **Model-comparison harness**: one squad configuration vs one strong single-model
  baseline under the same pack — the direct test of the thesis (can a governed squad outperform one strong model?).
- Recommendation-*producing*, **not** self-authorizing (governance boundary held; active
  policy mutation stays a 2.0 concern).

**Cut gate:** the scorecard live-produces a `CycleAssessment` for a real `lite`/`full`
cycle, and at least one squad-vs-single-model comparison runs end-to-end. Retarget the
vision SIP (`SIP-Plutarch-…`) off its stale `v1.1` tag and slice this scorecard out of it
before acceptance.

**Why 1.8 and not folded into 2.0:** a major version must *compound on* a proven
measurement substrate, not invent it in the same cut. Splitting grading (1.8) from
self-improvement (2.0) keeps "compound over grades" strictly behind "grades are
trustworthy" — the same producer-before-consumer discipline that separates 1.4 from 1.6.

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
4. **1.8 grading (cycle-evaluation scorecard) acceptance** ← the vision SIP (`SIP-Plutarch-…`) retargeted off `v1.1` and the scorecard sliced thin; `CycleAssessment` consumes `CycleOutcome` only, never raw check results; the fields it reads already exist in the 1.4 `CycleOutcome` contract (no re-cut).
5. **Any 2.0 compounding work (self-improvement, capability-backed agents)** ← the 1.8 scorecard is shipped and live-proven; it acts on `CycleAssessment` grades, never on raw checks.

## Ratification note

The forward cadence here is mirrored in `docs/ROADMAP.md` → "Forward Cadence (planned)":
the even-minor trust ladder **1.4** (honest evidence) → **1.6** (Campaign) → **1.8**
(grading / cycle-evaluation scorecard) → **2.0** (compounding), each behind an odd-minor
stabilization tail, per the #281 even/odd convention. The legacy "Cycle Evaluation
Scorecard" backlog entry in that file is reconciled to the 1.8 slot in the same edit.
