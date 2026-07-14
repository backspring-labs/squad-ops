# 1.4 Evidence Arc — Execution Plan (1.3 riders → 1.4 → 1.6 gates)

**Established:** 2026-07-06 · **Revised 2026-07-14** (golden-path rung added after the
six-cycle live-validation campaign; see `docs/ideas/IDEA-Functional-App-Obstacles-and-Roadmap.md` v3).
Companion to `1-3-x-two-lane-plan.md` and `2-0-roadmap-reconciliation.md`
(whose Finding-5 feature-lane line this supersedes).

**Revision summary (2026-07-14):** 1.4 is now **verification evidence integrity + the
Verified Canonical App Build** (Ephemeral Application Sandbox SIP, Lane S + Contract-First
Build Scaffolding SIP, Lane M). SIP-0091 duty durability and the SIP-0090 P2 decision move
to 1.6 (they serve long-running Campaign-era automation, not the golden path). Rationale:
the 2026-07-14 campaign proved honest evidence alone converges on `blocked_unverified`
forever — the evidence layer can only report that nothing is verifiable until the golden
path exists. The ladder gains a rung: evidence must be honest **and obtainable** before
1.6 automates over it or 1.8 grades it fairly.

**Revision 2 (2026-07-14, Mac-lane review):** the golden-path commitment is restructured
from an unconditional bet into a **staged, exit-able one**: (1) a cheap
**walking-skeleton spike (Phase 0.5)** gates *acceptance* of both golden-path SIPs —
empirical proof before design commitment; (2) an explicit **fallback clause** — if the
spike fails or the slice stalls at checkpoint, 1.4 reverts to the evidence-release shape
(SIP-0096 + SIP-0091 returns) and the golden path moves out, so the ladder never blocks;
(3) the 1.4 sandbox floor is **de-scoped** to build-runner + app-start + HTTP health
(browser probe / probe-as-peer / operator CLI → 1.5+, verdict honestly named);
(4) the scaffold's own acceptance surface is a **Mac-owned CI gate** (skeleton builds +
boots on plain runners), decoupled from Spark; (5) the cut bar rises to **≥3 consecutive**
benchmark runs, explicitly claiming *capability demonstrated* — reliability is 1.5's
campaigns and 1.6's FAY gate.

**Lane-pinning amendment (2026-07-14):** headline feature SIPs are pinned by **file
ownership**, not lane identity (previously: features come from the Macbook lane). The
existing ownership split already encodes this — executor/handlers/framing = M;
test-runner/build-check/agent-image/deploy-infra = S. 1.4 is the first dual-lane-headline
release: Scaffold (M-owned surfaces) + Sandbox (S-owned surfaces, and the execution
service holding the container socket lives on the Spark host). Collision rules: the
executor god-file stays M-owned — M provides the sandbox's integration seams via the
SIP-0097 `RunCompletion`/`RunLedger` boundaries; the shared acceptance-evaluation surface
coordinates explicitly (precedent: #421/#425). Spark remains the integration validator
for the assembled release (the 1.2.0 §6 lesson).

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
reason for the ladder: honest **and obtainable** evidence (1.4: SIP-0096 + the golden
path) → automate over it (1.6) → grade it (1.8) →
**experiment over grades (A)** → **author from gaps (B)**. The 2026-07-14 revision makes
both North-Star pillars concrete earlier: **A** is seeded by the Phase-0 golden benchmark
and its **Functional App Yield** metric (1.4) → 1.8 benchmark registry → Test Bay; **B**
is seeded by the Build Capability Pack contract (1.4 hand-authored → 1.6 pluginized →
2.0 squad-authored). The dependency is strict —
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

- **1.3 (shipped 2026-07-08)** stabilizes the *structure* (god-object decomposition, port de-leak, comms push consumer).
- **1.4** makes the evidence *trustworthy and obtainable* (SIP-0096 + the Verified Canonical App Build: Ephemeral Application Sandbox + Contract-First Build Scaffolding — one canonical app deterministically composed, executed, and honestly verified).
- **1.6** automates decisions *over* trusted evidence (Campaign Orchestration, Lane M) and *generalizes the build* (pluginized blueprints + second stack, Lane S); SIP-0091 + SIP-0090 P2 ride here.
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
| **SIP-0096** Verification Evidence Integrity | **accepted 2026-07-06** (PR #337, rev 2); P1–P3 landing through 1.3.x/1.4 (P3 slice 2b merged #418) | **1.4 headline** | integrity invariant, provenance, inert-check detection, `CycleOutcome` contract |
| **Ephemeral Application Sandbox** (`SIP-Externalized-Build-Sandbox.md`, evolved 2026-07-14) | proposed — **acceptance gated on the Phase-0.5 spike** | **1.4 headline (Lane S)** | the golden path's execution half; 1.4 floor: build runner + app start + HTTP health (rest → 1.5+) |
| **Contract-First Build Scaffolding** | proposed (2026-07-10) — **acceptance gated on the Phase-0.5 spike** | **1.4 headline (Lane M)** | the golden path's composition half; own acceptance surface = the Mac-owned CI skeleton-builds+boots gate |
| SIP-0091 Duty Durability via Temporal | accepted | **1.6** (moved from 1.4, 2026-07-14 — serves Campaign-era long-running automation, not the golden path) | durable responsibility |
| **SIP-0097** Executor Decomposition Boundaries | **accepted 2026-07-06** (PR #340, rev 2) | **1.3** (structural) | produces the `RunCompletion`+`RunLedger` seam SIP-0096 §6.4 wires into (slice 2 scheduled early for exactly this) |
| SIP-0090 Embodiment Phase 2 (Discord) | accepted (phased) | **1.6** (decision resolved 2026-07-14) | first live embodiment consumer |
| Campaign Orchestration | proposed (revised 2026-07-06 per #334) | **1.6 headline (Lane M)** | objective envelope + continuation policy |
| Generalized Build Capability (pluginized blueprints, 2nd stack, schema-constrained control artifacts) | direction set in the roadmap idea doc; SIP to be sliced at 1.6 planning | **1.6 headline (Lane S)** | generalizes the 1.4 golden path; first pluginized Build Capability Pack (North-Star B seed) |
| **Cycle Evaluation Scorecard** | proposed — slice thin from the over-scoped `SIP-Plutarch-Experimentation-and-Cycle-Assessment-Framework` vision doc (retarget off stale `v1.1`) | **1.8 headline** | grades honest evidence: `CycleAssessment` over the `CycleOutcome` seam + benchmark registry + first-wave internal eval packs + model-comparison harness — makes the thesis falsifiable |
| Self-Improvement + Test Bay; Capability-Backed Agents | proposed (vision/backlog) | 2.0 | compound over the *shipped* 1.8 scorecard, never raw check results |

## Phase-by-release execution

### Now / patch lane (HISTORICAL — retained for provenance; all rows shipped/closed by 1.3.x–2026-07-14, and #306's image-fix row is superseded by the sandbox SIP)

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

### During 1.3 (HISTORICAL — 1.3 shipped 2026-07-08; riders landed)

| Item | Lane | Why it rides here |
|---|---|---|
| **Evidence SIP Phase 0** — verification audit (confirm the SIP's §6.1 classification mapping + §8 conformance table against code and the accepted SIP-0092/0070 texts; semantics are decided in the SIP, not here) | M | docs-only, feature-free, keeps 1.4 unblocked |
| **#288 lease-arbitration fix** | M | lease-semantics *hardening* (1.3-legal); runtime surface is Lane-M-owned; hard gate for 1.6 Phase 2 — do not let it slip past 1.5 |
| ~~Evidence SIP proposal PR → design review → **accept**~~ | M (maintainer) | **done 2026-07-06** — PR #337 merged; promoted to **SIP-0096** (`sips/accepted/`); the 1.4 feature branch starts from it |
| #336 docs-drift lint | S | CI/test-infra is Lane-S-owned |

Note: #295 stays exactly where the 1.3 plan put it (rides #186). The evidence SIP's
choke point attaches to the **post-#186 completion boundary**, so #186 landing in 1.3
is itself an arc prerequisite — a reason to protect the 1.3 batch, not change it.

### 1.4 (feature minor — honest + obtainable evidence: the Verified Canonical App Build)

*(Revised 2026-07-14. Strategy umbrella:
`docs/ideas/IDEA-Functional-App-Obstacles-and-Roadmap.md` v3. Its phases map onto lanes:
S runs 1A verification-truth + 1B sandbox; M runs 2A scaffold + evidence P3 closure; the
1A ∥ 2A interleave is literally the two lanes. Governing dependency: don't* claim
*scaffold success until verification truth exists.)*

- **Phase 0.5 — walking-skeleton spike (runs FIRST; gates both golden-path SIP
  acceptances):** hand-write the group_run interface manifest; build the
  `fullstack_fastapi_react` expander only; confirm the *empty* skeleton builds + boots
  (local/CI — no sandbox, no Spark); then one fill-only cycle on Spark with dev scoped
  to filling slots, boot-building the output manually (spike-grade verification). If a
  27b produces a working app once freed of the plumbing, both headlines' thesis is
  validated for the price of one experiment; if not, the arc redirects **before** a new
  privileged service is committed to a minor. Mostly Mac-ownable; the two theses are
  validated *decoupled* before they ever compose.
- **Fallback clause (the exit — pinned, rev 2 final):** 1.4 reverts to the
  evidence-release shape (SIP-0096 completion + SIP-0091 returns from 1.6) and the
  golden path moves to 1.6 when **any** of these fires. Each is a **default that
  requires an explicit, recorded maintainer decision to override** — stalling is never
  a judgment call:
  1. **Spike verdict due 2026-07-25.** No verdict by then = fallback fires (a spike that
     can't be run in ten days is itself the signal).
  2. **Mid-release checkpoint 2026-08-15.** Fallback fires unless, by this date, (a) the
     scaffold's CI skeleton gate is green **and** (b) the sandbox floor has executed the
     golden path end-to-end at least once — engine-turns-over, regardless of FAY.
  3. **Post-integration: FAY still 0 after 10 benchmark attempts** = fallback fires
     (the capability isn't demonstrating; stop paying for it in release time).

  SIP-0096 P3 consumers keep landing as ordinary PRs on main regardless of this gate —
  deployed value never waits on the bet.
- **What the spike does and doesn't prove (rev 2 final, Mac-lane note):** a green spike
  validates the **scaffold thesis** (a 27b fills the skeleton into a working app) and
  the **sandbox's demand** (a clean execution locus is needed) — it does **not** test
  the sandbox's implementation feasibility. Post-spike, the new privileged execution
  service is the residual concentration risk; checkpoint 2 above exists precisely
  because the spike cannot cover it. Note also the spike's decisive half (the fill-only
  cycle) is Spark-bound — 27b is Spark-only — so the go/no-go is mostly, not entirely,
  Mac-ownable.
- **Phase 0 — golden benchmark (joint, after the spike):** freeze the canonical challenge
  (group_run PRD, one blueprint, one environment image, one verification suite, uniform
  `full` model policy as experimental control). Primary metric: **Functional App Yield**
  — % of canonical builds reaching verified-functional with zero manual intervention.
- **Evidence SIP completion** — P1 shipped; P3 in flight (slice 2b merged #418,
  derive-on-read `CycleOutcome` verified live 2026-07-14). Remaining: persistence +
  wrap-up/gate-waiver/doctor consumers; #114 rides (incl. persisting *failing*
  typed-check evaluation artifacts — the C1 gap). **Design `CycleOutcome` for its two
  downstream readers now** — Campaign continuation (1.6) and `CycleAssessment` (1.8) —
  carrying config/squad/pack provenance from the start. New outcome vocabulary from the
  golden path: `verified_executable` / `verified_functional` (three verification levels).
- **Ephemeral Application Sandbox** (Lane S headline; `SIP-Externalized-Build-Sandbox.md`)
  — **1.4 floor (rev 2): build runner + `start_application` + HTTP health probe.**
  Browser probe, probe-as-peer implementation, operator-access CLI/caddy → 1.5+; if the
  browser probe descopes, the 1.4 verdict is honestly named `verified_executable`.
  Environment contract + preflight and clean-room verification stay in the floor.
  **Supersedes** the old Phase-2 items "#306 image fix + preflight tooling-parity"
  (image-fix approach rejected 2026-07-14) and absorbs command-check execution
  relocation.
- **Contract-First Build Scaffolding** (Lane M headline) — interface manifest →
  deterministic walking skeleton → fill-only dev tasks; ownership classes; assembly
  validator. **Absorbs** old Phase-2 item "#291 required-files as a checked contract."
  **Own acceptance surface = the CI skeleton gate** (expander runs, `vite build` passes,
  backend imports — plain runners, Mac-owned, Spark-independent); FAY is the
  *integration* gate, not the scaffold's gate.
- **Integration order (rev 2):** scaffold lands first behind its CI gate; the sandbox
  consumes the blueprint contract second; the M/S executor seam goes through the
  SIP-0097 boundaries. No parallel-blind development toward a first-try integration.
- **Evidence-adjacent conformance tail (post-P2 — SIP-0096 P2 itself is done)** —
  SIP-0070 amendments (SKIP-only→PASS pulse fix;
  D13 required-frontend blocking) now generalized as **#423** (skip-as-pass polarity,
  typed-check variant included); classification/provenance retrofit of #289/#290;
  **#427** failure observability; **#426/#424** config coherence; correction-policy
  **locus × mode** classification (infrastructure failures never patch / never burn
  application correction budget — the roll-4 lesson).
- ~~#419/#420 typed-acceptance seam integrity~~ — **shipped 2026-07-14** (#421 + #425:
  seam hoist, wire-shape coercion, safelist single-sourcing + vocabulary + authoring
  lint). #420 live-validated; **#419's builder-seam live proof deliberately waits for
  the sandbox** (its migration step 7) — three cycles stalled pre-builder on
  environment, which is the revision's motivating evidence.
- **Cut gate:** standard checklist, plus: **≥3 consecutive Phase-0 benchmark runs
  achieving the acceptance statement** — *an assembled application that installs,
  builds, starts, passes declared health checks, and receives a verified outcome with
  zero manual file modification* (`verified_functional`, or honestly
  `verified_executable` if the browser probe descoped — then the release says so).
  **This bar claims capability *demonstrated*, not capability *reliable*** —
  repeatability and anti-overfit are the 1.5 campaigns' job, enforced by 1.6's
  FAY gate before anything automates over it. Promotion sweep expects: SIP-0096 →
  implemented; both golden-path SIPs → implemented (or the fallback clause exercised
  and the sweep re-scoped accordingly).

### 1.5 (stabilization — feature-free by rule)

Home for: **benchmark campaigns** (repeated Phase-0 runs, Functional App Yield
measurement, flaky-check elimination); **builder-loop reliability**; **sandbox security
hardening** (rootless/socket-proxy candidates, per the SIP's §7); locus × mode
correction-policy follow-through; #288 if it slipped 1.3; evidence-arc hardening
spillover (provenance-storage tuning, roll-up persistence cleanup); the next god-module
batch (#331 planning_tasks.py if it didn't ride #152's arc); accumulated debt (#154
residue, #301, #234 follow-through).

### 1.6 (feature minor — Campaign + Generalized Build)

Dual-lane headline pair (per the 2026-07-14 lane-pinning amendment): **Campaign
Orchestration** (Lane M) and **Generalized Build Capability** (Lane S — pluginized stack
blueprints, a second canonical stack, schema-constrained control artifacts, stronger
functional probes; SIP sliced at 1.6 planning from the roadmap idea doc). Riders:
**SIP-0091 duty durability** and **SIP-0090 Phase 2 (Discord)** — both serve
long-running Campaign-era automation (decision resolved 2026-07-14).

Campaign Orchestration accepts and implements **only when its named gates are green**:

| Gate | Where it lands |
|---|---|
| Verification Evidence Integrity implemented (the `CycleOutcome` contract §7.2 reads) | 1.4 |
| **Functional App Yield repeatably > 0 on the canonical benchmark** — continuation policy must have reachable verified outcomes to decide over, or it automates over noise | 1.4 cut gate + 1.5 campaigns |
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
  the 1.4 seam, never a re-cut) — outcome / quality / efficiency / stability at minimum,
  with **Functional App Yield as a first-class dimension**.
- **Benchmark registry** — **seeded by the 1.4 Phase-0 golden benchmark** (its records
  already carry config/squad/pack provenance by 1.4 design) — + **first-wave internal
  eval packs** (Dev, QA, Research, Tool Executor).
- **Model-comparison harness**: one squad configuration vs one strong single-model
  baseline under the same pack — the direct test of the thesis. **Fair only post-golden-path**:
  both sides must be able to build, or the comparison grades the environment, not the
  squad. (Model-topology experiments — mixed-tier squads — also unlock here, after FAY
  is repeatable.)
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

1. **Evidence SIP acceptance** ← Phase 0 audit complete (no vocabulary collision with 0092/0070/0079). *(Done — accepted 2026-07-06.)*
2. **Golden-path SIP acceptance (both)** ← the **Phase-0.5 walking-skeleton spike
   succeeds** (skeleton builds+boots deterministically; one fill-only Spark cycle yields
   a manually-verified working app), **verdict due 2026-07-25**. Spike failure or
   no-verdict exercises the fallback clause; the mid-release checkpoint (2026-08-15,
   engine-turns-over) and the 10-attempt FAY trigger gate the middle of the bet.
3. **1.4 cut** ← evidence phases live-validated (the honest-blocking half is **already
   proven** — every failed 2026-07-14 cycle reported `blocked_unverified` with explicit
   `required_unmet`) **and** the golden path proven: ≥3 consecutive Phase-0 benchmark
   runs achieving the acceptance statement, including the deferred #419 builder-seam
   live validation (sandbox migration step 7) — **or** the fallback clause exercised and
   1.4 cut in the evidence-release shape.
4. **Campaign SIP acceptance** ← the five 1.6 gates above (incl. FAY repeatably > 0).
5. **1.8 grading (cycle-evaluation scorecard) acceptance** ← the vision SIP (`SIP-Plutarch-…`) retargeted off `v1.1` and the scorecard sliced thin; `CycleAssessment` consumes `CycleOutcome` only, never raw check results; the fields it reads already exist in the 1.4 `CycleOutcome` contract (no re-cut).
6. **Any 2.0 compounding work (self-improvement, capability-backed agents)** ← the 1.8 scorecard is shipped and live-proven; it acts on `CycleAssessment` grades, never on raw checks.

## Ratification note

The forward cadence here is mirrored in `docs/ROADMAP.md` → "Forward Cadence (planned)":
the even-minor trust ladder **1.4** (honest + obtainable evidence — the Verified
Canonical App Build) → **1.6** (Campaign + Generalized Build) → **1.8** (grading /
cycle-evaluation scorecard) → **2.0** (compounding), each behind an odd-minor
stabilization tail, per the #281 even/odd convention. The 2026-07-14 revision also
amends the lane convention (features pinned by file ownership, not lane identity — see
header) — mirror that in `CLAUDE.md` §Versioning. The legacy "Cycle Evaluation
Scorecard" backlog entry in that file is reconciled to the 1.8 slot in the same edit.
