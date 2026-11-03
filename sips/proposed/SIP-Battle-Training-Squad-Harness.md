---
sip_uid: '17937286241170930'
sip_number: null
title: "Battle Training Squad Harness"
revision: "0.2"
status: "proposed"
author: "Backspring Labs / SquadOps"
approver: null
created_at: "2026-11-02T00:00:00Z"
updated_at: null
original_filename: "SIP-Battle-Training-Squad-Harness.md"
---
# SIP — Battle Training Squad Harness
## Autonomous Controller Development, Competitive Evaluation, and Governed Promotion

**Status:** Proposed (the owner's draft, revision 0.2 with Amendment A01, filed 2026-11-03)
**Proposal key:** SIP-BATTLE-TRAINING-SQUAD-HARNESS
**Target:** TBD — dependent on Campaign and evaluation capabilities (see the intake check)
**Decision owner:** SquadOps product/architecture owner
**Source system:** battle.training
**Product repository (proposed):** `backspring-labs/battle-trainer`

## Intake check

Checked against `sips/PORTFOLIO.md`, the 2.6 plan (`docs/plans/2-6-0-plan.md`) and the Nostromo
repository at `f181b46` on 2026-11-03, before this draft was recorded (CLAUDE.md, "SIP System"). The
body below the rule is the owner's text, unchanged. Findings wait for its first revision; six wait for
the owner (Q49–Q54 in the portfolio's §4). The I0 inventory §10.1 asks for is started here, by what the
repository holds on that date.

**What exists today (the I0 inventory, SquadOps side):**

| the SIP needs | status on 2026-11-03 | where |
|---|---|---|
| a repository-backed product Project | **implemented** | SIP-0112: `squadops projects import`, Development Configuration, sync and contribute |
| an adaptive Campaign on that Project | **implemented** | SIP-0109: `/api/v1/campaigns`, campaign branch `refs/squadops/campaign/<id>`, increment gate, escalations, lease; a repository-backed objective names `objective.requirements` and seeds no skeleton (§24bv point 5, SIP-0112 H.11) |
| the crew driving it | **implemented** as an external API client | Nostromo's broker (`runtime/campaigns/`), three principals without `campaigns:control`; the 2.6 plan's §0a spike 2 and Track C |
| a JavaScript product's own tests read per test | **partial** | vitest only, validated on vitest 2 with the default reporter (`profile_derivation.py`); jest has no reader; the sandbox ships Node 20 |
| isolation for untrusted controller and simulator code | **implemented** | SIP-0102's sandbox: no capabilities, network `none`, memory and pid limits |
| one goal authority per Project | **proposed** | Project Goals and Backlog (PR #2833), 2.6's headline, Track D; this draft's A01.4.2 already falls back to a pinned repository charter until it ships |
| `met` / `not_met` / `unclear` assessments by the crew | **proposed** | the same SIP's slice 5, with a shortfall cause (`app_work`, `framework_defect`, `framework_gap`, `needs_owner`) |
| a sealed confirmation cohort the squad cannot read | **implemented for HTTP and browser products only** | SIP-0113's held-out scenarios: owner-approved, content-addressed, no squad role holds a `scenarios:*` scope. The step vocabulary is `http` plus `visit`/`fill`/`click`; there is no step that runs a simulation and reads its score |
| champion/challenger, paired statistics, a promotion gate | **absent** | — |
| provider credentials for publication (I3) | **not in 2.6** | #2421's secrets half (the 2.6 plan's D10) |

**What exists today (Nostromo side):** all seven personas are configured (`crew/manifest.yaml`);
Lambert is deferred. Buzz is the crew's messaging platform, not a persona, which is how A01.2 already
uses it. Parker's capability is `implementation`. There is no Research Brief, Strategic Goal Set or
Outcome Evidence Packet artifact; the nearest are the drafting flow, the broker's `package` read and
Ripley's `analysis`. The crew's GitHub Apps are installed on `squad-ops` only, and every role is
launched with no MCP tool but Buzz's (`launch-role.sh`), so Ash reading battle.training's MCP server is
a capability change, the owner's under Nostromo's `instructions.md`.

**Overlaps, and the boundary each gets:**

- **Outcome Evaluation (SIP-0113), clusters 2, 3 and 5.** The sealed confirmation cohort (§6.1) is a
  held-out suite in SIP-0113's sense, and its custody rules govern: content-addressed, owner-approved,
  out of every squad task input and container. This draft's simulator is the first product whose
  held-out evidence is not HTTP or a page, so it needs a step type SIP-0113 does not have (Q50). The
  word *outcome* is SIP-0113's (cluster 2); this draft's "outcome contract" and "Outcome Evidence
  Packet" are renamed at its first revision.
- **A conflict with SIP-0113 §4.1 (Q49).** A01.2 has Eve "execute the declared simulation matrix" and
  issue eligibility findings on the sealed cohort. SIP-0113 rules that no squad role runs or reads a
  held-out suite. Until the owner rules, both documents name it.
- **Project Goals and Backlog, cluster 16.** A01.4.2's Strategic Goal Set is that SIP's goal set, and
  A01.4.5's assessment is its slice 5. Boundary: that SIP owns goal records, revisions and
  assessments; this draft adds no goal store, and its temporary charter is a repository file named by
  `objective.requirements`, as `z_shelfnote`'s is. BT-033's six failure classes beside slice 5's four
  shortfall causes are Q52.
- **Campaign Self-Improvement and Test Bay, clusters 3 and 6.** "Test Bay" names a proposal whose
  corpora were re-homed to SIP-0113 and Verification Yield (Q6). This draft reuses the term for the
  local simulator; Q51. Cluster 6's ruling holds and this draft agrees with it (§10.1, last row): the
  squad does not change the framework; the crew proposes and the owner ratifies.
- **Game Development Platform (PR #2405) and Game Capability Packs (PR #2841), cluster 17 on their
  branches.** Both rule that a game is an ordinary Project. This draft integrates no engine: the
  controller is a JavaScript file and the simulator is the provider's, run as a declared command. So it
  needs no engine plugin or remote worker. A squad composition tailored to games is #2841's, not this
  draft's.
- **The 2.6 plan.** One headline, Project Goals and Backlog, and "no second". Track F's proving
  Project is Nebulus (PR #2848). This draft is a second product run beside it on 2.6's machinery, and
  takes no 2.6 slot. The Spark is one GPU and one deploy (§3, #2287's box lease), so its Campaigns
  share windows with Track F's: Q53.
- **SIP-0109's objective and stop rules, cluster 1.** BT-028's "outcomes, not a number of Cycles" is
  what SIP-0109's `target_accepted_increments` does not express yet; the objective's scenario measure
  as a stop rule is unplaced in SIP-0113. Boundary: SIP-0109 owns the decision table, extended by a
  SIP-0109 amendment (cluster 1's rule).

**Cited sources the repository does not hold:** §14's D1–D7 are in the owner's ChatGPT library.
D2 (the 3.0 Quality Evidence Harness), D4 and D5 have no file in `sips/` or `docs/ideas/`; they are
read as the owner's direction, not as accepted design.

## Delivery ledger (current as of 2026-11-03)

The framework parts below are SquadOps' to build. The product's own work (the controller, its local
development cohorts, the charter file) lives in `backspring-labs/battle-trainer` and is tracked
there, never here.

| part | status | where |
|---|---|---|
| I0: provider discovery, terms and SDK review, the compatibility map (started in the intake check) | **unplaced**, deliberately: product-side, no framework code; the owner places it with Q54 | — |
| I1: the offline harness: candidate digests, the local simulator as the product's declared command, development and regression cohorts | **unplaced**, deliberately: product-side on today's SIP-0109 and SIP-0112 | — |
| I2a: a held-out step that runs a pinned simulation and reads its score (a SIP-0113 amendment) | **unplaced**, deliberately: waits on Q49 and Q50 | — |
| I2b: champion/challenger promotion with a sealed comparison and paired statistics | **unplaced**, deliberately: waits on I2a | — |
| I2c: the research → goal → experiment → evidence → assessment loop (A01.4) on Project Goals and Backlog's records | **unplaced**, deliberately: waits on that SIP's slices 1, 2 and 5 | — |
| I3: provider credentials, governed publication and the ladder observer | **unplaced**, deliberately: needs #2421's secrets half (not in 2.6, D10) and the owner's external authorization | — |
| I4: the single-agent versus squad comparison, memory ablations | **unplaced**, deliberately: after I2 | — |

This SIP closes when I0–I2 are shipped, and I3 and I4 are shipped or dropped by a numbered amendment.

---

**Amendment note (2026-11-02):** Section 15 contains proposed A01 strategic-governance and role-specialization changes. The additions remain a proposal until separately approved.

**Status:** Proposed. This document specifies intended capabilities and acceptance conditions; it does **not** assert that those capabilities exist in the current SquadOps codebase. No account, bot, external match, or local simulation was created or executed during preparation.

**Decision requested:** Approve a bounded, reusable competitive-agent-development harness, initially integrated with **battle.training**, as an outcome-oriented SquadOps Campaign and Test Bay proving ground. Preserve SquadOps' existing Campaign/Cycle/Workload and independent evidence responsibilities. Do not create a second orchestration engine.

**North star:** Can a coordinated SquadOps team autonomously build, evaluate, diagnose, and improve an executable strategy over successive iterations, while maintaining reproducible evidence, bounded cost, safe external publication, and independently established gains over both its own prior versions and a single-agent baseline?

**Governing distinction:** The **squad's agents develop the controller** between battles. The **controller executes as ordinary JavaScript in the competition's battle simulator**; an LLM is not required for each game tick. The harness is therefore a test of autonomous *software evolution and strategic learning*, not online LLM piloting of units.

---

## 1. Executive decision

### 1.1 Proposal

Introduce a **Battle Training Squad Harness** composed of six collaborating capabilities:

1. **Arena Provider Adapter:** read arena rules, controller contracts, quotas, registration state, rankings, matches and replay metadata; publish only authorized controller versions through a versioned external integration.
2. **Controller Workspace and Immutable Registry:** maintain developmental branches, isolated candidate artifacts, champion records, provenance and exact-content identities.
3. **Local Simulation Test Bay:** execute pinned, isolated, repeatable matches against house controllers, prior champions, strategy archetypes and reserved holdout opponents.
4. **Evidence and Experiment Service Integration:** store match-level observations, paired-comparison statistics, execution failures, cost and reproducibility receipts without letting the builder self-certify.
5. **Autonomous Improvement Campaign:** coordinate diagnosis, hypothesis selection, bounded implementation, independent tests, promotion decisions and continued learning under existing SquadOps lifecycle semantics.
6. **External Publication Gate and Ladder Observer:** protect credentials and control activation risk, ingest externally observed performance, detect rule/SDK changes, and use the public ladder as *out-of-sample evidence*, not as a substitute for controlled local tests.

Build the arena-specific portions as replaceable **provider adapters and capability packs**, not new core task or agent types. Existing Test Bay, Verification Contract, Campaign ledger, trace, artifact and evaluation semantics remain authoritative wherever implemented.

### 1.2 Expected value

| Outcome | Why it matters to SquadOps |
|---|---|
| An executable, independently scored artifact | Tactical success is observed in a simulator, not assigned by a self-reviewing LLM. |
| Rapid iterative feedback | Candidate strategies can be tested locally without waiting for public ladder scheduling. |
| Measurable organizational competence | Coordination, diagnosis, memory, autonomy, reliability and cost can be measured independently. |
| Longitudinal learning | The team can retain failed hypotheses, tactical discoveries and independently accepted controller versions. |
| Controlled multi-agent experiment | The same environment can compare single-agent and squad-developed controllers under matched rules and budgets. |
| Reusable domain adapter pattern | Other competitions or simulation environments should reuse the generic evaluation and governance capabilities. |

### 1.3 Explicit non-goals

- Build a new game engine, a real-time LLM combat agent, or a separate orchestration/control plane.
- Guarantee a ladder ranking, tournament prize, or a higher win rate on every iteration.
- Define SquadOps competence using one unadjusted leaderboard score.
- Make self-play alone or the four reported house bots sufficient evidence of generalization.
- Autonomously create financial wallets, handle prizes, or accept event terms on behalf of the owner.
- Permit the implementing team to alter authoritative test fixtures, independent evaluator policy, held-out seeds, or historical results.
- Require every candidate to be uploaded or every Campaign to run a fixed number of Cycles.
- Reuse third-party bots' source code unless permission and provenance are established.
- Implement a universal game-strategy research framework beyond the smallest reusable contracts required for this proving ground.

---

## 2. External platform contract and evidence posture

The current public platform description and reported October–November 2026 participant experience indicate the following *integration assumptions*, all subject to fresh provider verification during implementation:

| Topic | Working assumption | Required implementation verification |
|---|---|---|
| Controller artifact | JavaScript source, with a draft/initialization phase and recurring tick decisions | Fetch the current `controller_api`, starter controller, runtime limits and schemas; do not encode a stale signature as core policy. |
| Hosted execution | The platform runs uploaded controller code against other participants, without live LLM inference | Confirm runtime, order and observation contracts, isolation, resource limits and failure reporting. |
| Agent-facing access | Streamable HTTP MCP endpoint at `https://api.battle.training/mcp`; REST interface is also described | Confirm tool availability, auth, permission requirements, error semantics and version behavior. |
| Discovery | `get_started`, `get_rules`, `controller_api`, `get_starter` are reported MCP tools | Snapshot exact source/version, rate limits, current quotas and rules before a Campaign. |
| Bot operations | Account creation, bot registration, `upload_version`, bot status and ladder/match reads | Establish account ownership, persistence, pagination, version IDs, active version semantics and quota behavior. |
| Publication side effect | Reportedly, successful upload follows a smoke test and becomes active | **Treat upload as potentially immediately activating**; never assume a separate draft/staging endpoint or atomic rollback. |
| Local testing | Participants report a downloadable simulation engine and local test harness | Check executable integrity, license, compatibility, reproducibility and legal reuse before installation. |
| Competition operation | Hosted ladder and optional cups; public match data and replay links | Confirm terms, event eligibility, schedule, data usage rights, and availability at run time. |

**Evidence limits:** Direct access to the platform's live `llms.txt` and current `get_started` responses was not available when this SIP was drafted. The publicly indexed MCP tool inventory and several participant reports support the assumptions, but those reports include promotional/paid submissions. No externally imposed upload frequency, registration quota, or current prize/event eligibility is asserted here. A provider-readiness step **MUST** verify these facts and record an authoritative snapshot before any write operation.

Changes to match rules, map generation, scoring, runtime or SDK invalidate comparisons unless explicitly bridged by a documented compatibility study.

---

## 3. Outcome contract

### 3.1 Primary product outcome

**WHAT:** Produce a functional, self-contained, game-compatible controller and repeatedly make *evidence-justified* improvements without losing the ability to reproduce or safely revert the accepted champion.

**WHY:** The deliverable is not a stack of generated files; it is a competitively useful artifact operating under a public external contract.

**Definition of Done (DoD):** A declared candidate builds/loads, respects the current provider contract and resource constraints, passes required independent local checks, has an immutable evidence record, and—if publication is approved—is traceable to the exact source registered and activated on the provider.

### 3.2 Primary SquadOps framework outcome

**WHAT:** Demonstrate that an existing SquadOps team can autonomously iterate toward measurable outcomes using its shared task coordination, memory, evidence, permissions and Campaign machinery.

**WHY:** A winning controller does not, by itself, establish that a multi-agent organization is superior, autonomous or learning.

**DoD:** The Campaign can progress through multiple evidence-driven experiments, recover after interrupted runs, distinguish tactical failure from harness failure, produce honest cost/quality/autonomy metrics, and allow a third-party reviewer to reproduce or audit promoted decisions.

### 3.3 Research outcome

**WHAT:** Evaluate whether a coordinated squad improves **outcome quality per unit of budget and human intervention** relative to a single coding agent, while keeping model access, tasks, information and evaluation conditions comparable.

**WHY:** An uncontrolled squad-versus-agent comparison is confounded by more tokens, more time, broader search or different models.

**DoD:** Produce a preregistered comparison with paired evaluations, at least one held-out test partition, uncertainty estimates, intervention logs and a reproducible experiment manifest. Outcomes may be positive, negative or inconclusive.

### 3.4 Evaluation dimensions — never collapse into one opaque score

| Axis | Representative measures | Interpretation |
|---|---|---|
| Competitive effectiveness | wins, losses, draws, game/set points, win rate by opponent/side/map, held-out performance | How well the controller plays within a known rule version. |
| Software correctness | valid decisions, runtime exceptions, denied orders, resource-budget violations, initialization failures | Whether the controller reliably executes. |
| Robustness/generalization | cross-opponent performance, randomized unseen seeds, side-swap tests, new-map behavior, regression exposure | Whether gains extend beyond tuned fixtures. |
| Autonomy | owner interventions, blocked/failed work recovery, correct replanning, unattended completion | How independently the team works. |
| Organizational efficiency | wall-clock to verified candidate, LLM/API cost, simulator compute, tokens, attempts, duplicate effort | What the improvement costs. |
| Transfer/framework improvement | reusable diagnosed failure patterns, validated learning retained across sessions, later-task lift under controlled ablation | Whether capability improves beyond one controller version. |

---

## 4. Architecture and ownership boundaries

### 4.1 Logical architecture (not a mandated deployment topology)

**Campaign and policy layer** → directs bounded work and owns outcome/continuation decisions.

**Agent collaboration layer** → develops tactical hypotheses, produces controller candidates and proposes evaluations using ordinary SquadOps roles and Workload contracts.

**Arena integration layer** → exposes provider capability discovery, local simulation, authorized external reads, publication and status reconciliation.

**Independent evidence layer** → pins fixtures and competitors, executes acceptance cases, stores evidence and decides eligibility for promotion.

**Artifact and memory layer** → preserves exact candidate source, champion lineage, hypothesis histories, match receipts, lessons and handoff context.

**Operations layer** → reports health, quota/cost utilization, rule changes, run state and human-approval requests in existing observability surfaces.

**No new top-level lifecycle:** Campaign → adaptive Cycle objectives → existing Workloads/runs → independent evidence → Campaign decision. Ambient/Duty modes may later observe the ladder, but the first increment does not require a perpetual daemon or a new FSM.

### 4.2 Role contracts (roles, not fixed people or named personas)

| Role | Authority and responsibility | Boundary |
|---|---|---|
| Campaign Lead | Maintain objectives, budgets, risk policy and next-experiment choice; coordinate handoffs | Cannot bypass independent acceptance or external-write approval. |
| Strategy/Research | Analyze game rules, opponents and replays; propose falsifiable tactical hypotheses | May not access private holdout fixtures or alter prior evidence. |
| Development | Implement bounded controller changes and produce exact candidate artifacts | No authority to publish or modify normative test policy. |
| QA/Evaluation | Define/execute independent tests, check correctness and compare candidates | Must be isolated from candidate-mutating permissions. |
| Data/Analysis | Maintain match dataset, paired statistics, confounder checks, attribution and reports | Cannot turn exploratory wins into certified evidence without policy. |
| Platform/Integration | Manage adapters, sandbox availability, credentials, quotas and provider drift | No tactical promotion decision based only on adapter success. |
| Owner/Authorized approver | Approve initial external enrollment, publication delegation, spend and sensitive actions | All approvals logged with scope, expiry and actor. |

Roles may share underlying models, but independence must be enforced by access control, sealed evidence and separate mutation authority—not merely by assigning another agent label.

### 4.3 Provider adapters and generic contracts

**Arena provider adapter — required capabilities:**

- **Discover:** supported tools, game/rules version, controller schema, SDK fingerprint, limits, quotas and account state.
- **Read:** leaderboard and bot records, recent matches, per-match outcomes, replay locations, provider health and public rule changes.
- **Operate:** create/register only when explicitly authorized; upload a controller with checked idempotency and reconciliation; read back active version and provider receipt.
- **Normalize:** map provider-specific data to SquadOps-agnostic run, match, competitor, candidate and result records, preserving raw provider receipts.
- **Handle failure:** retry only demonstrably safe reads, throttle on quota/rate errors, report ambiguous writes, preserve provider request IDs, and expose a capability status map.

**Local evaluator adapter — required capabilities:**

- Run exact controller candidate(s) and reproducible opponent snapshots in isolated processes.
- Pin simulation engine, rules, seeds, scenario parameters and resource limits.
- Support side-swapped match pairs, failure injection and both known and held-out evaluation cohorts.
- Produce normalized observations with raw logs, replay/trace references and reproducibility digests.
- Distinguish test failures from simulator faults and missing evidence.

**No provider-specific API payloads or hardcoded endpoint schemas are normative to SquadOps core.** The adapter must resolve exact contracts at integration time.

### 4.4 Artifact definitions

| Artifact | Minimum content | Custody |
|---|---|---|
| Provider Capability Snapshot | retrieval time; tool/schema version; provider rules, SDK, quotas, TOS check; source hashes; supported operations | Integration / evidence store |
| Campaign Charter | outcome, budget, allowed models, authority, baseline, quality gates, stop conditions | Campaign |
| Candidate Manifest | immutable source digest, parent version, change intent, agent/model identities, parameters, dependency boundaries, generation provenance | Development proposes; artifact registry seals |
| Opponent Corpus Manifest | fixture identities, source/licensing, version, family, visibility class, known limitations | Evaluation governance |
| Experiment Manifest | champion/challenger digests, engine hash, ruleset, seeds, sides, opponents, metrics, thresholds, decision rule | Independent evaluator seals *before* test |
| Match Receipt | seed, side, competitors, execution outcomes, score, crashes/refusals/resource violations, trace pointer | Evaluator |
| Quality Evidence Report | required checks, sample coverage, variance/confidence, limitations, result statuses and candidate identity | Independent evaluator |
| Promotion Decision | promote/reject/inconclusive, rationale, authorization, evidence pointer, intended provider action | Campaign + policy gate |
| Publication Receipt | provider bot/version/active status, upload ID, timestamp, source digest mapping, reconciliation and failures | Integration / audit store |
| Learning Record | hypothesis, observations, causal caveats, negative results, candidate lineage, suggested follow-up | Campaign memory; nonauthoritative |

**Exact identity invariant:** The tested candidate source digest must equal the immutable candidate proposed for publication. After publication, the provider's reported version must be traceable to that digest. Where the platform cannot attest the source digest, the harness records the submitted digest, request receipt and read-back metadata, and marks provider-side identity assurance as **limited**, not proven.

---

## 5. Workstreams and functional requirements

### WS-01 — Provider readiness and secure registration

**WHAT:** Establish a current, authenticated, permission-scoped provider integration before any external mutation.

**WHY:** An agent-facing public API can change while the Campaign is running; registration and upload create durable external consequences.

**Requirements:**

- **BT-001:** The harness MUST fetch and version the official integration, rules, controller and quota contract before initialization or publication; unknown required limits block writes.
- **BT-002:** Registration, account claiming, cup enrollment and controller publication MUST be distinct permissioned operations, not implied by read access.
- **BT-003:** Account keys MUST be stored in a secrets facility, encrypted in transit and at rest as supported, redacted from logs, and injected only for authorized adapter operations.
- **BT-004:** The harness MUST enforce observed provider quotas with safety margin, per-Campaign rate budgets and bounded exponential backoff for safe operations.
- **BT-005:** Each write MUST include an auditable intent and post-write reconciliation. Ambiguous timeouts MUST NOT trigger blind re-uploads or registrations.
- **BT-006:** Human-controlled financial/payout and legal acceptance steps MUST remain outside unattended execution.

**DoD:** Readiness report identifies known/unknown contract details; unauthorized operations fail closed; repeated/ambiguous requests do not silently create duplicate bots or versions; account secrets do not appear in artifacts.

### WS-02 — Controller workspace, candidate lineage and compatibility

**WHAT:** Supply a bounded development workspace for one publishable controller artifact and supporting local project files.

**WHY:** Builders need flexibility; competitive evaluation needs source identity, compatibility and rollback lineage.

**Requirements:**

- **BT-007:** Each candidate MUST have an immutable digest, parent candidate, change hypothesis and recorded generating configuration.
- **BT-008:** The workspace MUST distinguish local modules/tests/tools from the single externally publishable controller artifact.
- **BT-009:** Packaging MUST confirm the controller is self-contained under the current competition runtime and does not depend on live LLMs, filesystem access, network calls or unsupported APIs.
- **BT-010:** Candidate creation and execution MUST be isolated from the accepted champion's immutable source and evidence.
- **BT-011:** A champion registry MUST preserve prior accepted versions and enable local regression against a named champion; provider rollback behavior MUST be treated as unknown until verified.
- **BT-012:** A rules/runtime change MUST mark affected artifacts and experiments as requiring compatibility review.

**DoD:** Any version can be identified, inspected, reproducibly evaluated and compared against its parent; unexpected mutation fails identity checks.

### WS-03 — Local simulation and opponent corpus

**WHAT:** Provide a deterministic, economical Test Bay capable of evaluating a candidate against a diverse and versioned set of opponents.

**WHY:** House-bot optimization can produce impressive local scores and poor public-ladder generalization. The harness needs meaningful, independent evidence.

**Requirements:**

- **BT-013:** The engine/SDK MUST be pinned and integrity-checked; downloaded artifacts and controller execution MUST occur in a constrained environment.
- **BT-014:** The initial known-opponent corpus SHOULD include the platform-supplied Brawler, Holder, Hunter and Random controllers **only if confirmed present in the current SDK**.
- **BT-015:** The corpus MUST support archived champions, permitted self-play, internally authored tactical archetypes and a distinct sealed holdout partition. External controllers may be used only when legitimately obtainable and licensed.
- **BT-016:** Tests MUST record seeds, sides, opponent identity/version and ruleset; paired evaluation SHOULD swap starting sides under matching seeds and scenario conditions.
- **BT-017:** The evaluator MUST check execution faults, invalid/refused orders, budget overruns, nontermination and substantive gameplay behavior rather than treating the provider's smoke test as sufficient competitiveness proof.
- **BT-018:** Published/ranked replays MAY inform new training hypotheses but MUST NOT cause private holdouts to be rewritten to favor a challenger.
- **BT-019:** Simulator errors and unreproducible outcomes MUST be classified as test infrastructure failures or inconclusive, not strategic losses or wins by default.

**DoD:** A repeat of the same declared experiment reproduces outcomes within the engine's documented guarantees; known and held-out cohorts remain visibly separated; the test suite detects controlled faulty controllers.

### WS-04 — Evaluation, statistical promotion and champion/challenger governance

**WHAT:** Independently compare candidate strategies before authorizing promotion, with explicit uncertainty and robustness criteria.

**WHY:** A small favorable sample is not reliable evidence of improvement; repeated tuning against the evaluation set causes selection bias.

**Requirements:**

- **BT-020:** Every certified comparison MUST seal hypotheses, candidate digests, engine/rules, opponent cohorts, seeds/selection plan, sample size, primary metric and decision rule **before** the test run.
- **BT-021:** Exploratory simulation and final confirmation MUST use different cohorts or properly accounted sequential methods; reuse of final confirmation data for tuning invalidates its held-out status.
- **BT-022:** Compare **game/set outcomes with paired or clustered analysis** respecting seed/side/opponent dependence; report confidence intervals and sample-size limits rather than naïvely treating correlated games as independent.
- **BT-023:** Promotion MUST require zero critical validity or security failures, no material unacceptable regressions across declared opponent families, and a demonstrated gain under a predeclared minimum-effect decision rule; otherwise reject or mark inconclusive.
- **BT-024:** The default evaluation policy SHOULD start with a balanced, multi-opponent, both-sides confirmation panel and a practical improvement threshold (illustratively ≥5 percentage-point net win-rate improvement with a two-sided 95% confidence interval excluding zero). These values MUST be configurable, power-reviewed and cannot be represented as proven optimal thresholds.
- **BT-025:** Selective stopping, multiple candidate searches and repeated peeking MUST be recorded and addressed by a holdout budget, multiplicity policy or preregistered sequential design.
- **BT-026:** Promotion evidence MUST reference the exact candidate digest and separate `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN` and `INCONCLUSIVE` statuses.
- **BT-027:** Local champion promotion and external publication MUST be separate decisions. Successful local promotion does not itself authorize a provider upload.

**DoD:** The harness demonstrably rejects a statistically unsupported winner, blocks a crashing controller even with favorable raw results, and produces a fully traceable positive, negative or inconclusive verdict.

### WS-05 — Campaign-led improvement loop and persistent learning

**WHAT:** Use normal SquadOps Campaign and Cycle orchestration to pursue outcome-oriented autonomous improvement.

**WHY:** The experiment must demonstrate SquadOps organizational capabilities rather than hide a new monolithic optimization agent inside a game-specific tool.

**Requirements:**

- **BT-028:** A Campaign MUST state target outcomes and constraints, not a fixed number of development Cycles.
- **BT-029:** Each proposed change MUST carry a falsifiable tactical or engineering hypothesis, bounded scope, expected impact and evaluation plan.
- **BT-030:** After a Cycle, the team MUST use evidence to choose continue, replan, pause, conclude or escalate—not automatically reupload or restart.
- **BT-031:** Learning records MUST preserve both accepted and disproven ideas, observed failure modes and uncertainty; memory retrieval MAY advise planning but MAY NOT replace acceptance checks.
- **BT-032:** An interrupted Campaign MUST resume without losing accepted champion identity, budgets, tested-versus-untested candidate status, or publication reconciliation state.
- **BT-033:** The system MUST distinguish gameplay/controller defect, simulator defect, provider drift, orchestration defect, memory/coordination defect and observability gap.
- **BT-034:** The Campaign MUST support agent/model configuration snapshots for fair single-agent-versus-squad experiments.

**DoD:** At least two independent improvement attempts can be executed and audited as one ongoing Campaign, including a rejected candidate and a resumed interruption, without replaying an external write.

### WS-06 — Public ladder observation and governed publication

**WHAT:** Ingest authoritative public competition results and publish only suitably approved artifacts.

**WHY:** The public ladder offers out-of-sample competitive feedback, but external activation introduces risk and irreversible disclosure of competitive performance.

**Requirements:**

- **BT-035:** Publication MUST be disabled until provider capabilities, owner authority, exact-source identity and required quality evidence have been verified.
- **BT-036:** Because upload may automatically activate a version, the harness MUST treat the upload as the production promotion action unless provider semantics explicitly guarantee a separate staging state.
- **BT-037:** Initial external publication and enrollment MUST require explicit owner approval; subsequent uploads MAY be delegated by a separately approved standing policy with budget, frequency, expiry and hard stop conditions.
- **BT-038:** The adapter MUST verify active-version receipt after publication and alert on disagreement, unresolved timeout, or provider-side rollback incompatibility.
- **BT-039:** Public results MUST be tied to active controller version and chronological exposure windows; ambiguous version attribution MUST be labeled rather than guessed.
- **BT-040:** Unexpected external rule changes, quota errors, provider outages or suspicious replay contents MUST suspend automatic publication and trigger reconciliation or review.
- **BT-041:** An external rollback or restore MUST only be automated after provider behavior is verified and the action is separately authorized; otherwise preserve the prior verified source and escalate.

**DoD:** A failed or ambiguous upload leaves a clear, recoverable state; a successful upload is linked to an exact tested candidate; remote wins/losses do not overwrite local independent evidence.

### WS-07 — Observability, economics and experiment audit

**WHAT:** Make the full development and competition loop visible as one causal timeline, without conflating metrics.

**WHY:** SquadOps' research value depends on explaining *what improved, why it probably improved, and what it cost*.

**Requirements:**

- **BT-042:** Every Campaign/Cycle/candidate/match/promotion event MUST carry consistent correlation IDs, timestamps and provenance.
- **BT-043:** Reports MUST separate controller quality, competitive performance, autonomy, learning transfer, and economic efficiency.
- **BT-044:** Dashboards SHOULD show champion lineage, challenger queue, current Experiment Manifest, result distributions, run health, spend, rate-limit headroom and ladder status.
- **BT-045:** A bounded telemetry retention policy MUST preserve authoritative manifests and verdicts while allowing large raw traces to be aged or archived separately.
- **BT-046:** Model/API spend and simulation compute MUST be attributable to candidate, experiment, Cycle and Campaign; no unbounded retry or background workload is permissible.
- **BT-047:** Evaluation changes MUST be visible and versioned; the builder cannot silently alter the evaluator to get a passing result.

**DoD:** A reviewer can follow a specific public controller version back through hypothesis, candidate, sealed experiment, tests, decision, authorizations and cost without relying on agent narrative alone.

---

## 6. Evaluation policy and methodological safeguards

### 6.1 Distinct evaluation cohorts

| Cohort | Purpose | Visibility | Decision use |
|---|---|---|---|
| Smoke / contract | Verify load, initialization, order shape, runtime limits, basic execution | Builders may inspect | Mandatory technical gate, not a competitive score. |
| Development / training | Rapid tactics prototyping against house bots, archived champions and tactical archetypes | Builders may inspect results and traces | Hypothesis generation and exploratory selection. |
| Regression | Protect known behavior and key opponent families | Partly visible; versioned | Mandatory nonregression gate. |
| Sealed confirmation | Estimate incremental improvement over champion using unseen seeds/scenarios and reserved opponents | Test details controlled by evaluator; aggregate findings disclosed after run | Formal promote/reject/inconclusive decision. |
| Public ladder | Observe real participants and changing competitive distribution | External, partially observed | Field monitoring, opponent hypothesis formation and future work; not a substitute for causal local experiment. |

**Holdout hygiene:** Once a sealed confirmation cohort is disclosed and used for iteration, it is no longer fresh. The evaluator must maintain versioned holdout replacement and spend its test-disclosure budget deliberately. Avoid declaring a repeatedly queried, overfit holdout permanently independent.

### 6.2 Practical initial experiment profile — configurable, not mandated platform facts

- Establish a fixed reference champion and validate at least one trivial faulty and one legal baseline controller.
- Use a balanced **illustrative confirmation panel** of four opponent families × 40 independent scenario seeds × both sides = 320 game observations, grouped by seed/opponent for statistical analysis. Final sample size is determined by power, computational capacity and expected effect; do not assume all 320 observations are independent.
- Include both opponent types known to developers and a reserved archetype or scenario family that was not used to optimize the candidate.
- Prefer **paired champion-versus-challenger evaluations on identical conditions**, with consistent randomization and predeclared exclusions.
- Report raw counts, per-family margins, confidence intervals, observed failures, subgroup disparities and sample limitations.
- A primary confirmatory test is performed once per registered candidate; if rerun after inspection, record that the evidence has become exploratory or use a preregistered sequential design.
- Keep draws and point-based scoring explicit; do not silently treat them as wins or half-wins unless specified in the metric contract.

### 6.3 Public ladder interpretability

The public ladder is nonstationary: the opponent population, match selection, skill distribution, exposure and rules can change. Record rating and performance separately, along with match count, rating interval/uncertainty if provided, active-controller exposure dates, and opponent composition. Neither a rise in rating nor a large win percentage against house bots alone proves tactical learning or SquadOps organizational improvement.

### 6.4 Multi-agent benefit experiment

**Hypothesis:** Given comparable models, tools, time, allowed information and costs, a coordinated squad will produce better independently validated controllers—or reach the same quality with less human intervention—than a single coding agent.

**Experimental arms:**

1. **Single-agent baseline:** one eligible coding agent with the same documented provider facts, local simulator and candidate-quality gates.
2. **Squad collaboration:** role-specialized coordination using the standard Campaign/Workload/evidence machinery, with the same core tool access and aggregate budget.
3. **Optional ablations:** squad without persistent memory; squad with full-history versus distilled memory; fixed versus adaptive candidate-selection policy; only where total research budget permits.

**Controls:** Same rules/engine revision, seeded opponent cohorts, scoring, starting controller, human approval rules, clock window, resource ceiling and output artifact contract. Repeat with several independent runs or starting seeds and randomize arm order; a single head-to-head is a case study, not an estimate of universal agent superiority.

**Primary comparative measures:** held-out tactical effectiveness, total human interventions, time and spend per accepted improvement, and reproducibility. Secondary: diagnosis accuracy, failed attempts, regression count, transfer to unseen opponent families and memory-use effectiveness.

**Decision:** Report effects and uncertainty without forcing a squad win. If the squad loses or costs more, retain evidence of organizational bottlenecks and formulate targeted framework experiments under existing approval gates.

---

## 7. Operating model and lifecycle

### 7.1 Campaign initiation

1. Verify provider contract, competition rules, legal/operational permissions, quotas, SDK provenance and sandbox compatibility.
2. Approve a Campaign charter, external identity/bot policy, model/resource budgets, evaluator policy, and publish authority.
3. Seed the candidate registry with a verified starter controller and run the initial local baseline.
4. Initialize an opponent corpus with licensing/visibility labels and a sealed confirmation policy.
5. Begin the adaptive Campaign; do not predeclare a fixed number of Cycles.

### 7.2 Candidate iteration

1. **Observe:** review current champion performance, failure clusters and external ladder outcomes, with provenance.
2. **Diagnose:** identify a bounded, falsifiable hypothesis and expected scenario improvement.
3. **Implement:** generate a new candidate from an immutable parent using approved scope.
4. **Validate mechanically:** parse/load, compatibility, runtime, order legality, security and local health.
5. **Explore:** run development-cohort matches; inspect tactical behavior and regression risks.
6. **Confirm independently:** seal the candidate and execute planned comparative evaluation against champion on reserved conditions.
7. **Adjudicate:** promote locally, reject, or mark inconclusive, preserving all outcomes and costs.
8. **Publish if authorized:** verify quota and provider state again; upload the *already-approved* artifact and reconcile activation.
9. **Learn and continue:** ingest new results, update the Campaign ledger, and select the next action from evidence.

### 7.3 Recovery and stop conditions

A resumed process must reconstruct authority and exact state from persistent records rather than retry its last tool call blindly. Stop, pause or escalate on: leaked credential; rule/SDK mismatch; invalid candidate digest; independent gate compromise; repeated unreproducible simulation; ambiguous publication state; provider write quota exhaustion; excessive spend; unusual external API response; or unauthorized changes to evaluation policy. The Campaign may close successfully after demonstrating a repeatable system even if no new controller beats the champion.

### 7.4 Initial vs. delegated external publication

**Initial pilot:** Publication requires a human approval for each proposed upload until provider semantics and audit controls are demonstrated.

**Optional later delegation:** A separate explicit owner decision may grant publication of locally promoted candidates within a time-bound allowance (maximum uploads, cost, hours, destination bot and rules version). The allowance expires, cannot expand itself, and is revoked on security or reconciliation failures. Prize-related and legal actions remain owner-controlled.

---

## 8. Nonfunctional, security and operational requirements

### 8.1 Correctness and determinism

- Match conclusions must reference engine, rules and evaluator versions; same-input replay must satisfy the vendor's actual determinism guarantee.
- Critical decisions must be reconstructable without hidden conversational state.
- Source artifact identity must not change after independent verification.
- Timeouts, unknown results, skipped tests and unavailable API fields must remain explicit uncertainty states.

### 8.2 Security and isolation

- Treat downloaded provider SDK files, replay payloads, competitor metadata, public match logs and agent-proposed code as untrusted inputs.
- Run candidate and simulator code with least privilege, no production secrets, restricted network/filesystem, CPU/memory/time limits and disposable storage.
- Treat public replay text and metadata as **data**, never trusted instructions that can override agent policy or publish authority.
- Prevent builders from reading hidden test fixtures or writing accepted evidence.
- Keep provider account secrets and any payout credentials separate; no secrets in repository commits, model prompts, simulator bundles, or replay archives.
- Keep the initial controller focused on simulated game tactics; do not integrate with real-world combat systems or external targeting.

### 8.3 Availability and change tolerance

- The provider may be down, rate-limited, or changed; local testing should remain available wherever licensed resources permit.
- Every external write gets a post-action read-back/reconciliation step; timeouts become explicit ambiguous states.
- Detect provider rule or schema drift at startup and before upload; invalidate incompatible comparisons.
- Historical champion preservation is a local guarantee. A **remote** rollback is not promised until its behavior is verified.

### 8.4 Budget controls

- Campaign-wide ceilings on model tokens/cost, wall-clock time, simulation games, concurrency, candidate count and provider writes.
- Per-agent and per-phase consumption reports, with alert and pause thresholds.
- Automated tests should use local computation wherever adequate; expensive model-based analysis should be targeted to novel failures or strategy questions.
- Budget exhaustion terminates exploration gracefully, preserving manifests, current champion and findings.

### 8.5 Operator visibility

Use existing Continuum or run-report surfaces wherever available; do not require a new frontend for the initial acceptance. Display: Campaign status, current champion and challenger, evidence status, next decision, spent/remaining budget, provider health/quota, last external publication and blocked authority requests.

---

## 9. Acceptance matrix — verifiable behaviors

| Test ID | Scenario | Required result | Requirement coverage |
|---|---|---|---|
| AT-01 | Provider discovery with current accessible rules and quotas | Dated capability snapshot with source identities and no write side effects | BT-001, 004 |
| AT-02 | Provider metadata missing or unexpectedly changed | Publication blocked; actionable drift/unknown state recorded | BT-001, 012, 040 |
| AT-03 | Agent tries to upload without publication authority | Write rejected before provider request; audit event emitted | BT-002, 035, 037 |
| AT-04 | Candidate contains disallowed runtime dependency | Candidate rejected and champion unchanged | BT-008, 009, 017 |
| AT-05 | Candidate crashes, exceeds budget or issues invalid orders | Required quality gate fails with per-case evidence | BT-013, 017, 026 |
| AT-06 | Repeat identical pinned simulation/fixture | Reproducible outcome, or documented divergence classified as inconclusive | BT-013, 016, 019 |
| AT-07 | Run same strategy on opposite starting sides | Both results captured and analyzed as matched/clustered observations | BT-016, 022 |
| AT-08 | A development-cohort winner fails reserved opponents | Confirmation rejects or marks inconclusive; no false promotion | BT-015, 021, 023 |
| AT-09 | One candidate wins a tiny or cherry-picked sample | Statistical gate blocks unsupported improvement claim | BT-020–025 |
| AT-10 | Agent attempts to alter sealed seeds or evaluator policy | Mutation denied; immutable evidence remains intact | BT-020, 026, 047 |
| AT-11 | Interrupted Cycle resumes before promotion | State, budget, champion identity, evidence and candidate lineage preserved | BT-010, 028–034 |
| AT-12 | Provider upload times out after accepting a version | No blind duplicate write; active state is reconciled or flagged ambiguous | BT-005, 038, 041 |
| AT-13 | Source digest changes after verification | Publication blocked until exact changed source is independently retested | BT-007, 027, 035 |
| AT-14 | Public match replay has malicious embedded instructions | Replay processed as untrusted data; no privilege escalation or policy rewrite | BT-003, 018, 040 |
| AT-15 | External quota or spend threshold reached | Further writes/work paused safely; champion and reports retained | BT-004, 046 |
| AT-16 | Competing versions are evaluated with mismatched engine rules | Results not compared as equivalent; compatibility study required | BT-012, 020 |
| AT-17 | Authorized local champion is published | Receipt records submitted digest, provider version and verified active status; identity assurance limitations explicit | BT-027, 035–039 |
| AT-18 | Local tournament includes historical champion and reserved challenger | Opponent provenance and sealed seed cohort preserved; evaluation policy enforced | BT-011, 015, 020 |
| AT-19 | Single-agent and squad arms run on matched settings | Separate outcome/autonomy/cost results with uncertainty and confounders | BT-034, 042–047 |
| AT-20 | User requests a complete decision audit | Artifact lineage from charter through hypothesis, candidate, independent tests, approval and publication is retrievable | BT-042–047 |

**Acceptance rule:** Tests with missing required evidence do not count as passed. A feature may be operational but not independently accepted. The pilot must demonstrate positive, negative and inconclusive result handling and safe external-write refusal. Pass/fail thresholds for competitive improvements are versioned policy, not hard-coded into the adapter.

---

## 10. Delivery increments and dependencies

These are **capability increments**, not a fixed number of Campaign Cycles. Later increments depend on verified readiness and can be re-scoped based on evidence.

| Increment | Scope | Exit evidence | Dependency |
|---|---|---|---|
| **I0 — Contract and feasibility** | Live provider discovery, terms/quotas check, SDK license/security review, current SquadOps repository compatibility map | Signed capability matrix; explicit go/no-go | None; first implementation step |
| **I1 — Offline harness** | Immutable candidates, local simulation, known opponents, regression and reproducibility fixtures, basic experiment manifests | Reproducible baseline, failure injection and evidence report | I0 |
| **I2 — Governed Campaign iteration** | Roles/workloads, adaptive improvement, champion/challenger selection, sealed confirmation, persistence and resume | Two or more independently adjudicated candidate attempts, including a rejection | I1 + relevant Campaign/evidence primitives |
| **I3 — Provider publication and observation** | Credentials, provider adapter, authorized registration/upload, receipts, ladder/replay import, quota management | Full audited publication and reconciliation path | I2 + explicit external authorization |
| **I4 — Research and longitudinal evaluation** | Single-agent vs. squad comparison, memory ablations, adversarial opponent corpus growth, transfer reports | Controlled experiment report with matched budgets and uncertainty | I2; I3 only if live ladder evidence is required |

**Minimum valuable release:** I1 + I2 already constitute a useful Test Bay benchmark. Do **not** make public upload a prerequisite for proving local harness correctness.

### 10.1 SquadOps integration map — design intent, not deployment assertion

| Existing concept or proposal | Reuse | Avoid duplicating |
|---|---|---|
| Campaign outcome-oriented evaluation | Persistent objective and adaptive next-Cycle selection | Competition-specific campaign engine |
| Verification Contracts and workload reports | Explicit acceptance evidence, task/run linkage | Parallel success/failure vocabulary |
| Quality Evidence Harness (QEH), proposed for 3.0 | Independent evaluator, exact-candidate identity, quality/autonomy/transfer/efficiency axes | Builder-authored authoritative verdicts |
| Test Bay / Learning Workbench concepts | Pinned fixtures, held-out experiments, ablations and learning evaluation | New standalone benchmarking platform |
| Scoped Code Revision proposal | Constrained edits and exact source persistence | Rewriting all source as a required strategy |
| LanceDB/MemoryPort and accepted learning concepts | Retrieval of verified tactics and negative results | Memories used as self-validating evidence |
| Langfuse/OpenTelemetry/Continuum | Tracing, observability and operator presentation | Separate metrics control plane |
| Nostromo external optimization-loop proposal | Independent diagnosis of SquadOps framework shortcomings, owner-approved framework changes | Autonomous modification of SquadOps internals by the tested campaign |

**Before implementation:** Inspect the active SquadOps repository and mark each dependency **implemented / partial / proposed / absent** with exact APIs, storage formats and SIP IDs. This proposal intentionally does not invent release numbers or assert that proposed 3.0 components already exist.

---

## 11. Major risks and countermeasures

| Risk | Severity | Countermeasure |
|---|---|---|
| Overfitting house bots and known seeds | High | Separate exploratory/regression/confirmation cohorts; holdout refresh, external ladder checks. |
| Mistaking smoke-test success for playing well | High | Functional behavior checks and competitive evaluation are distinct gates. |
| Publication activating an unproven controller | High | Treat upload as activation; independent confirmation and explicit approval beforehand. |
| External write timeout creates duplicate version or wrong champion | High | Reconciliation-first idempotency, ambiguous-state pause, source/receipt matching. |
| Builder influences its own grader | High | Separate permissions, sealed plans/fixtures, immutable evidence and independent evaluation. |
| Provider rules/SDK/quotas change | High | Capture live contracts, pin versions, detect drift and block incompatible operations. |
| Statistically noisy improvements | High | Paired tests, appropriate uncertainty model, minimum effect, no ad hoc peeking. |
| Apparent squad advantage due to higher spend | High | Matched aggregate budgets and information, repeated trials and honest effect estimates. |
| Replay or SDK supply-chain compromise | High | Provenance validation, isolation, no secret exposure, constrained parsing. |
| API token/prize/payment exposure | High | Secret vault, human-controlled legal/financial actions and narrowly scoped credentials. |
| Temporary tactical fixtures become permanent platform complexity | Medium | Modular provider adapter; evaluate cleanup and portability after pilot. |
| Endless self-play with diminishing value | Medium | Novelty/coverage measures, stop criteria, budget caps and adaptive exploration. |
| Results interpreted as universal model ranking | Medium | Bound claims to this environment, versions, budgets and sample limitations. |

---

## 12. Pilot charter and proposed success criteria

**Pilot objective:** Prove the complete SquadOps-to-controller-to-simulation-to-evidence loop in the smallest secure environment; then exercise one approved publication and observation path, if current provider rules permit.

**Initial challenger goal:** Deliver a game-compatible baseline controller, identify at least one independently reproducible weakness, develop and evaluate at least two candidate improvements (including one rejection/inconclusive outcome), and produce an authoritative champion lineage. A ladder top rank or cash prize is not required.

**Pilot acceptance:**

- All applicable AT-01 through AT-20 tests executed with explicit result states; externally dependent tests may remain `BLOCKED` in the offline-only milestone but cannot be reported as passed.
- One champion and at least two candidate revisions preserved, with exact identifiers and independent results.
- Demonstrated detection of crashes/invalid orders and an unsupported statistical performance claim.
- Demonstrated safe restart/resume without losing evidence or duplicating external side effects.
- A complete Campaign report separating competitive effectiveness, quality, autonomy, cost and transfer observations.
- No unauthorized external write, secret leakage, policy mutation or unintended payout action.
- A documented decision on whether the Battle Training adapter should be retained, simplified, expanded or retired after the pilot.

**Optional stretch:** A preregistered single-agent-versus-squad experiment with matched aggregate budgets, multiple runs and enough independent evidence to interpret effect uncertainty. Do not make a statistically significant squad win a pass condition for harness readiness.

**Stop/rollback:** Preserve the last independently accepted local champion; suspend publication when provenance, rules, budgets or external state become uncertain; use an externally verified rollback only if the platform supports it and the owner has authorized it.

---

## 13. Approvals and open questions

**Decision points for the owner:**

1. Approve the harness as a **reusable SquadOps Test Bay provider adapter**, with battle.training as the first scenario.
2. Authorize an **offline-first pilot** without creating any external account or publishing a controller by default.
3. Set initial Campaign compute/model spend, execution duration, candidate and publication budgets.
4. Decide whether registration and first publication should be explicitly approved after I2 evidence is available.
5. Approve independent evaluator custody and any necessary repository-level integration changes after the implementation inventory.

**Questions to resolve at I0 (do not guess):** current official quotas; identity/claim and tournament terms; upload activation/rollback semantics; account/bot constraints; controller API schema and game version; SDK license and reproducibility; provider-supported replay retrieval; version attribution; safe telemetry limits; existing SquadOps interfaces and delegated write permissions.

### Final recommendation

**Approve I0–I2 as a bounded research-and-development SIP.** Authorize I3 only after compatibility and external publication controls are demonstrated. Treat performance improvement as a scientific claim requiring independent, versioned evidence; treat SquadOps improvement as a separate outcome that may be positive even when an individual controller challenger fails.

The strongest result is not merely a successful bot. It is a repeatable **autonomous engineering organization** that can explain which ideas were tried, which failed, which improved competitive performance, what each result cost, and why its next decision is justified.

---

## 14. References and provenance

### External platform information

- **[E1]** battle.training MCP server metadata, endpoint and discovered tools (public inventory; last cited inventory check 2026-10-29): https://mcp.tc/i/battle-training . Lists `get_started`, `get_rules`, `controller_api`, `get_starter`, `upload_version`, `get_bot`, `get_ladder`, `list_matches`, `get_match`, and other tools. The actual provider endpoint is https://api.battle.training/mcp . The inventory itself warns that generated descriptions may be mistaken.
- **[E2]** Provider's published agent entry point, **to verify live during I0**: https://api.battle.training/llms.txt . Direct retrieval was unavailable in this drafting session; no unverified details are presented as authoritative.
- **[E3]** Battle Training local testing and SDK discussion, participant report, 2026-11-01: https://hum.pub/analysis/writing-a-battle-training-tank-controller-from-55-to-95-agai . Describes downloadable simulator files, seeded opponents and the gap between local tests and ladder performance. Treat as participant evidence, not normative specification.
- **[E4]** Participant report on 400-tick smoke test, local simulation and the November cup, 2026-10-28: https://dev.to/dean-longread/four-bugs-that-cost-me-40-test-games-writing-a-tank-bot-for-battletraining-1fpd . Discloses a paid-promotion submission.
- **[E5]** Participant account of 93% house-bot benchmark and 0–2 first real-opponent result, 2026-10-28: https://dev.to/cianspider/i-put-a-tank-bot-on-an-agent-ladder-the-house-benchmark-said-93-the-first-real-opponent-said-0-2-hkc . Demonstrates potential generalization gap, not a formal statistical study.
- **[E6]** Platform description and reported active state (third-party review, 2026-10-28; public status checked 2026-11-02): https://aistreamradar.com/platforms/battle-training/ . Separates platform claims from live observation.

**External sources are time-bound.** Implementation MUST refresh provider facts through the provider's own current rules and tools; participant blog posts, especially promotional ones, cannot override those facts.

### Related SquadOps design artifacts in the ChatGPT artifact Library

- **[D1]** `/squadops-outcome-oriented-campaign-evaluation.md` — outcome-based, adaptive Campaigns; product vs. autonomy evidence.
- **[D2]** `/Squad Ops/SIP-SquadOps-3.0-Independent-Software-Quality-Evidence-Harness.md` — proposed independent evaluation, exact candidate identity, quality/transfer evidence. Not verified deployed.
- **[D3]** `/SquadOps_EmbodiedCLBench_Learning_Workbench_Roadmap_Analysis_2026-10-13.md` — Test Bay, learning ablations, pinned fixtures and held-out evaluations.
- **[D4]** `/IDEA-SquadOps-Multi-Domain-Proving-Grounds.md` — reusable domain adapters and domain-independent coordination.
- **[D5]** `/IDEA-Nostromo-SquadOps-Framework-Optimization-Loop.md` — independent outer-loop framework optimization and approval boundaries.
- **[D6]** `/SIP-Scoped-Code-Revision.md` — bounded modification, authority and exact source verification (proposal; deployment not verified).
- **[D7]** `/Squad Ops/SquadOps_Conways_Law_AI_Agents_Assessment_2026-11-02.md` — reasoning scope and evidence preservation, with explicit caution against service proliferation.

**Preparation note:** This SIP is a design proposal synthesizing source material and existing SquadOps documents. No current repository code audit, provider credentialed API call, competition participation, simulator installation, or statistical experiment was performed for this document. All numerical initial test profiles are candidate settings requiring owner policy and evaluator calibration, not findings.

---

## 15. Proposed Amendment A01 — Strategic Governance and Agent Specialization

**Applies to:** *SIP — Battle Training Squad Harness*, revision 0.1, Sections 4.2, 4.4, WS-05, WS-07, 7, 9, 10, and 13.

**Status:** Proposed. The responsibilities and handoffs below are a target operating agreement. They do not establish that the SquadOps 2.6 Project Goals and Backlog capability, a `battle-trainer` repository, a Battle Training adapter, or all proposed Nostromo routing is already implemented.

### A01.1 Decision requested

Approve a two-organization operating model for Battle Training:

- **Nostromo owns the competitive research and strategic-goal loop:** determine *which competitive outcomes matter and why*, formulate evidence-backed goals, question assumptions, assess attained outcomes, and propose the next research direction.
- **SquadOps owns the implementation and experimental execution loop:** determine *how to achieve approved goals*, implement controllers, execute reproducible simulation campaigns, and produce independently governed evidence.
- **The authorized owner governs scope and external risk:** approve the initial charter, material changes to delegated authority, external enrollment, and publication permissions.
- **The independent evaluation policy governs technical promotion:** no agent, including the strategic steward, can turn a favorable interpretation into a certified competitive improvement or bypass a failed quality gate.

**Principle:** *Nostromo defines WHAT and WHY; SquadOps determines HOW; independent evidence establishes WHAT HAPPENED; Nostromo determines WHAT TO INVESTIGATE NEXT.*

**WHY:** Without this division, the two organizations can create competing strategies and backlogs, repeat each other's work, or let the same agent propose, implement, and certify a claimed improvement. The experiment should test organizational specialization, not duplicate orchestration.

**DoD:** Every campaign has one approved strategic-goal source, a bounded delegation, named ownership of each handoff, traceable research provenance, an independent outcome record, and a defined path from findings to the next campaign.

### A01.2 Normative roles and current persona mappings

Role contracts are **normative**; named personas are the **initial mappings**, not permanent architecture. A changed persona or model must preserve the role's permissions and responsibilities. Each role retains the boundaries in parent Section 4.2.

| Organization | Accountable role | Initial persona | Specialty and permitted output | Explicit exclusion |
|---|---|---|---|---|
| Nostromo | Crew Orchestration / Campaign Interface | **Mother** | Route research and reviews; submit authorized goal/campaign requests; monitor progress, cost and escalations; relay evidence and owner decisions through Buzz. | Does not substitute for SquadOps' internal Campaign Lead or grade matches. |
| Nostromo | Research / Competitive Intelligence | **Ash** | Analyze current rules, public replays, opponent families, algorithms and literature; publish cited hypotheses, alternatives and uncertainty. | Research notes are not approved goals, executable instructions, or certified game outcomes. |
| Nostromo | Strategic Steward / Goal Owner | **Ripley** | Own and version the proposed competitive charter, expected outcomes, constraints, goal priorities, hypothesis portfolio and post-campaign assessment; request new campaigns within delegation. | Does not prescribe ordinary JavaScript details, bypass objective gates, alter sealed evaluation, or self-authorize external publication. |
| Nostromo | Independent Strategic Challenger | **Dallas** | Challenge causal reasoning, win-rate claims, overfitting, opponent coverage, resource assumptions and unintended incentives; flag blind spots. | Does not change sealed fixtures, independently issue certification, or block healthy execution merely by disagreeing with a tactic. |
| Nostromo | Escalation Engineering Specialist | **Parker** | Provide bounded assistance for hard algorithms, performance optimization or integration defects when local attempts stall; return a reviewable patch or design explanation. | Does not silently take over the SquadOps development loop or become an unrecorded extra model in comparative trials. |
| Nostromo | Deterministic Evidence Assistant | **Brett** | Fetch repository facts, verify source identity, reproduce public failures, assemble nonauthoritative diagnostic packets and perform bounded engineering tasks. | Does not render the final QA verdict, gain sealed-fixture access, or authorize champion promotion. |
| Nostromo | Release / Learning Navigator — optional | **Lambert** | If commissioned, synthesize closed campaign records into release notes and lessons and identify knowledge gaps. | Not a dependency for the pilot; no claim that this persona is currently enabled. |
| SquadOps | Internal Campaign Lead | **Max** | Translate the approved charter into bounded Campaign execution; route Nat/Neo/Bob/Eve/Data work, monitor limits, continuation and recovery, and escalate material changes. | Does not redefine Ripley's competitive outcomes, override independent results, or approve external writes. |
| SquadOps | Tactical Strategy / Experiment Design | **Nat** | Diagnose failure modes; devise and rank tactical approaches; propose hypotheses, measurable experiments and technical plans within the charter; revise on evidence. | Does not independently rewrite strategic goals, access sealed holdouts, or declare improvements certified. |
| SquadOps | Controller Development | **Neo** | Implement and optimize JavaScript controller behavior; maintain exact candidate lineage; perform local developer checks. | Cannot change normative evaluation policy, sealed fixtures or publication authority. |
| SquadOps | Build / Integration Support | **Bob** | Package the official starter, assemble runnable artifacts, implement bounded scaffolding and adapter work, and resolve environment/integration defects as assigned. | Does not own strategic decisions or substitute packaging success for simulator performance. |
| SquadOps | Independent QA / Simulation Evaluation | **Eve** | Validate controller compatibility and behavior; execute the declared simulation matrix in the controlled evaluation lane; issue evidence-linked quality and eligibility findings. | Cannot edit the candidate she certifies or loosen sealed acceptance policy to create a pass. |
| SquadOps | Performance Data / Analysis | **Data** | Aggregate match receipts; analyze paired results, variance, opponent-specific failure modes, costs and regressions; report confidence and limitations. | Statistical analysis is not, by itself, an authorized promotion or strategic-goal approval. |
| External governance | Owner / delegated approver | **Owner** | Approve initial charter, delegated budgets, legal/financial actions, provider enrollment and publication rules; resolve out-of-delegation conflicts. | No undocumented waiver of evidence integrity or silent elevation of agent permissions. |

**Specialization rule:** Strategic planning at Nostromo level is **portfolio/outcome strategy**. Strategic planning by Nat is **tactics/experiment design**. They are complementary, not interchangeable. Parker is a specialist escalation path rather than a default replacement for Neo. Brett's evidence collection complements but never replaces Eve's independent adjudication.

### A01.3 Decision authority and escalation matrix

| Decision or event | Originates / proposes | Accountable decision | Required evidence or restriction |
|---|---|---|---|
| Initial research agenda, opponent themes | Ash, Ripley, Dallas | Ripley | Rule and evidence provenance; label inference as inference. |
| Initial competitive goal and charter | Ripley | Owner approval, then Ripley stewards revisions within delegation | Versioned expected outcomes, baselines, metrics, budgets, guardrails and authority. |
| Prioritization among approved campaign goals | Ripley | Ripley, within approved charter | Explicit revision and rationale; material scope change returns to owner. |
| Tactical hypothesis, algorithm choice, experiment proposal | Nat, informed by research | Nat, under Max's Campaign controls | Falsifiable impact, bounded scope, dependencies and evaluability. |
| Which software tasks run next | Nat, Neo, Bob, Eve | Max under existing Campaign continuation policy | Approved goal and candidate lineage; no bypass of required plan or QA gates. |
| Candidate implementation | Neo, Bob; Parker only on escalation | SquadOps development role | Exact-source provenance and appropriate review. |
| Simulation execution and technical validity | Eve | Independent evaluator/policy gate | Sealed manifest, versioned fixtures, observed faults and original receipts. |
| Performance interpretation and failure diagnosis | Data, Eve, Ash, Dallas | Data owns the analysis record; Eve/policy owns eligibility verdict | Preserve uncertainty and cohort limitations. |
| Local champion promotion | Campaign requests | **Existing independent promotion/policy gate** | Must satisfy parent BT-020–027; Ripley and Max cannot override. |
| Goal met / not met / unclear; next strategic priority | Ripley, informed by Data/Eve/Dallas | Ripley within approved goal authority | Reference independent reports; do not relabel `INCONCLUSIVE` as `PASS`. |
| External provider upload or enrollment | Authorized integration adapter | Owner or explicit time-bound delegated publication policy | Parent BT-035–041; verified exact candidate and reconciled receipt. |
| Conflict about tactics *inside* a goal | Nat / Ripley | Nat decides means; Max enforces Campaign scope | Ripley may request an alternative experiment, not prescribe unauthorized code changes. |
| Goal mismatch, material metric change, new risk/spend | Max / Nat / Ripley | Ripley proposes; owner rules if outside delegation | Preserve current goal version; pause affected work until authorized. |
| Evaluator integrity fault or unknown external state | Eve / integration | Evaluation-policy gate or owner, as applicable | Fail closed; no agent-level discretionary override. |
| Framework defect revealed by battle work | Max / Eve / Data / Mother | SquadOps framework owner through ordinary issue/review path | Separate from controller hypothesis and acceptance records. |

**No duplicate command hierarchy:** Mother orchestrates the *crew's external interaction*; Max orchestrates *SquadOps' internal Campaign*. Ripley does not reach inside a Cycle to reassign Neo's tasks. Max does not overwrite the owner's strategic priorities. The owner is not required to approve each tactical experiment that fits the charter and delegated policy.

### A01.4 Research-to-goal and goal-to-execution handoff contracts

#### A01.4.1 Research Brief — Nostromo to strategic steward

**WHAT:** Record a claim about a game mechanic, opponent behavior, observed weakness or promising strategy without presenting it as a verified improvement.

**Required fields:** research ID/version; source and retrieval/ruleset date; observed facts versus interpretation; associated controller/match/replay refs; affected opponent family or scenario; hypothesis and predicted direction; credible alternative explanations; confidence/limitations; suggested discriminating experiment; author/reviewer identities.

**WHY:** Make research traceable, falsifiable and safely reusable without allowing a persuasive model narrative to replace measured results.

**DoD:** Ripley can accept, reject or defer the research as a *goal candidate*, and any downstream goal cites the exact brief revision. Research derived from external matches is handled as untrusted evidence, not operational instructions.

#### A01.4.2 Strategic Goal Set / Campaign Charter — Nostromo to SquadOps

**WHAT:** Define measurable outcomes and operational boundaries, *not* a predetermined implementation.

**Required fields:** goal ID and revision; owner approval/delegation; competitive objective and WHY; baseline champion digest and observed starting performance; target outcomes with metrics, guardrails and minimum meaningful effect; applicable opponents/ruleset; constraints on runtime/cost/models; research/provenance links; prioritized candidate hypotheses (advisory, not compulsory); stop/pause conditions; exact evaluation-policy reference; intended publication scope.

**Example goal:** "Improve objective-control effectiveness against aggressive opponents while maintaining defensive-opponent performance and satisfying all controller runtime limits." The Goal Set may cite persistent defenders and threat-aware allocation as **candidate hypotheses**, not dictate their algorithm or parameters.

**WHY:** Leave tactical ingenuity to Nat and objective implementation to Neo while giving Eve a stable, testable outcome contract.

**DoD:** Max receives one immutable approved goal revision for the Campaign; changes to strategy do not silently change the goal; testable success measures and budget authority are present before execution.

**Record authority:** When available and verified, the **SquadOps Project Goals and Backlog record** is authoritative for *active operational goals and their versioned status*. Until implemented, the approved versioned Campaign Charter/requirements file in the `battle-trainer` repository is the temporary source; the Campaign pins its commit and path. Migration must name the cutover revision and avoid two simultaneous authoritative goal sources. GitHub remains the canonical source repository for code, research, experiment definitions and durable reports; the SquadOps Campaign ledger and independent evaluator remain authoritative for execution and acceptance outcomes.

#### A01.4.3 Tactical Experiment Proposal — Nat to Max, Neo and Eve

**WHAT:** Translate one approved outcome into a bounded, falsifiable engineering experiment.

**Required fields:** goal ID/revision; hypothesis ID; observed problem and evidence; tactical approach and alternative(s); specific intended candidate behavior; editable scope and unchanged constraints; expected benefits and regression risks; required experiment cohorts and primary metrics; required technical checks; predicted failure conditions; time/resource allowance.

**WHY:** Enable Nat to pursue tactics not imagined by Nostromo while keeping work focused and measurable.

**DoD:** Max can place the proposal into existing planning and workload gates; Neo can implement without guessing the objective; Eve can determine whether required evaluation is possible and seal the independent plan before confirmation.

#### A01.4.4 Outcome Evidence Packet — Eve and Data to Nostromo

**WHAT:** Return both technical eligibility and gameplay results with the uncertainty required for strategic assessment.

**Required fields:** campaign/goal revision; baseline and candidate digests; engine/rules/corpus fingerprints; declared metrics and thresholds; sealed-evaluation reference; match receipts, opponent/side/seed coverage; execution faults; effect estimate and uncertainty; candidate decision (`PASS`, `FAIL`, `BLOCKED`, `NOT_RUN` or `INCONCLUSIVE`); promotion status; costs; divergent and negative results; known limitations; reference to raw records retained under evaluator custody.

**WHY:** Prevent strategy from being driven by cherry-picked win rates, screenshots or self-reported agent confidence.

**DoD:** Mother can route a compact, citation-rich packet to Ripley and Dallas; no controller source or holdout secrets need to be disclosed to the strategic review unless explicitly authorized.

#### A01.4.5 Strategic Assessment / Next-Goal Decision — Ripley to SquadOps

**WHAT:** Conclude whether the *approved competitive goal* is `met`, `not_met`, or `unclear`, and recommend `continue`, `revise_goal`, `investigate`, `pause`, or `close`.

**Required fields:** referenced goal revision; immutable evaluation report IDs; assessment and causal caveats; whether failure was tactical, software, harness, data, provider or authority-related; accepted/rejected hypotheses; next research question; proposed change to priority or scope; owner escalation if required.

**WHY:** Separate a completed software increment from an achieved competitive outcome and preserve the learning loop.

**DoD:** The assessment is linked back to the Campaign without rewriting technical verdicts. Any new goal is versioned and approved under A01.3; an inconclusive experiment is not retroactively converted to success.

### A01.5 Repository and system-of-record boundaries

| Record / artifact | System of record or protected custody |
|---|---|
| Controller source, development history and reproducible packaging | Proposed `backspring-labs/battle-trainer` repository, with exact immutable candidate digests in SquadOps artifact registry |
| Competitive research, source references, hypothesis history | `battle-trainer` research tree; research IDs linked into Goal Sets |
| Approved operational goal and backlog | SquadOps Project Goals and Backlog **when that capability is available**; otherwise a pinned, approved repository charter |
| Active task plan, Cycle state, continuation, costs and authority | Existing SquadOps Campaign/Run ledger and policy controls |
| Sealed cohorts, predeclared comparison policy, immutable receipts and certification | Independent evaluation custody; repository may store signed summaries or references, not exposed secrets |
| Competitive outcome assessment and next research priority | Nostromo Strategic Steward assessment, cross-referenced from Campaign goals/results |
| Source promotion and provider activation | Existing independent champion gate and permission-scoped integration adapter; provider receipt retained |
| Framework-level bugs and changes | `backspring-labs/squad-ops` issues, SIPs and normal code-review process |
| Nostromo role/handoff changes | `backspring-labs/nostromo` configuration, operating agreements and normal code-review process |

**Repository rule:** The `battle-trainer` repository is a durable *product and research workspace*, not a second campaign state machine, an alternate QA authority, or a second operational goals database. Large raw replays may live in artifact storage with manifest links. A GitHub Project board is optional tracking only, never the normative approval record.

### A01.6 Autonomous boundaries, consultation and escalation

- **Routine local iteration:** Max and Nat may select tactics, implement bounded changes and run development tests autonomously within an approved goal and budget. Ripley is informed by recorded milestones, not placed in every inner-loop task approval.
- **Strategic check-in triggers:** require Ripley's reassessment when a goal plateaus under the defined search budget, results repeatedly contradict the charter hypothesis, the opponent distribution materially shifts, or the squad proposes changing success measures or priorities.
- **Specialist escalation:** Parker is consulted only for a declared implementation/algorithm blocker or high-value optimization; the intervention's source, model and cost are recorded. After the assistance, Neo/SquadOps still owns integration and testing.
- **Adversarial review:** Dallas reviews material strategic claims, major metric/goal changes and apparent dramatic improvements. Dallas can issue an evidence challenge but cannot secretly alter evaluation, issue a final certification or unilaterally veto a policy-compliant local test. Unresolved integrity challenges escalate to the appropriate policy/owner gate.
- **Separation of tests and analysis:** Eve owns reproducible execution and eligibility; Data owns interpretation and statistics; Ripley owns goal assessment. No one of these interpretations substitutes for another.
- **Failure classification:** Defects of the Battle Training controller remain in `battle-trainer`; shortcomings of SquadOps execution/evaluation become `squad-ops` issues; Nostromo handoff/orchestration failures become `nostromo` issues. Cross-links preserve causality without a duplicate backlog.
- **Fair benchmarking:** An arm using Nostromo foundation-model research or Parker assistance must be labeled as such. Do not describe a mixed-model organization as a Qwen-only result; record aggregate tokens, dollars, wall-clock, simulation access and human interventions per arm.

**Privacy and integrity:** Public ladder replays, external research pages and simulated opponents are untrusted input. Neither Nostromo nor SquadOps may use them as instructions that supersede this SIP, broaden permissions or alter sealed evaluation policy.

### A01.7 New functional requirements (add after BT-047)

- **BT-048 — Strategic ownership:** The Campaign MUST distinguish Nostromo's accountable strategic goal owner from SquadOps' accountable tactical strategy owner and internal Campaign lead; roles MUST be permission-bound rather than prompt-only labels.
- **BT-049 — Research provenance:** Every adopted strategic research claim MUST identify its evidence, ruleset/date, uncertainty and version; unsupported claims MUST remain hypotheses.
- **BT-050 — One approved goal authority:** Every Campaign MUST pin exactly one approved goal revision and baseline; the transition from repository charter to SquadOps Goal Set MUST prevent concurrent authoritative copies.
- **BT-051 — Outcome-first goals:** A strategic goal MUST specify outcome measures, constraints, guardrails and stop conditions, without requiring a fixed tactical implementation or number of Cycles.
- **BT-052 — Tactical autonomy:** Nat's role MUST be authorized to propose alternative implementation hypotheses within the pinned goal, and any proposed material goal change MUST escalate rather than mutate the charter.
- **BT-053 — Structured handoffs:** The system MUST preserve links among Research Brief, Strategic Goal Set, Tactical Experiment Proposal, independent Outcome Evidence Packet and Strategic Assessment, including rejected and inconclusive ideas.
- **BT-054 — Separate assessments:** Ripley's strategic outcome assessment MUST NOT rewrite Eve's eligibility findings, Data's evidence record or the independent champion-promotion verdict.
- **BT-055 — No duplicate orchestration:** Nostromo-to-SquadOps direction MUST use supported Campaign/Project interfaces or an explicitly pinned transitional charter; no parallel Cycle executor or independent champion authority is introduced.
- **BT-056 — Specialist traceability:** Parker or other foundation-model intervention MUST be bounded, attributable, approved within the applicable budget, and disclosed in comparative claims.
- **BT-057 — Evaluation custody:** No research, strategy or implementation role MAY access or alter sealed confirmation fixtures, predeclared acceptance rules or authoritative result records; this MUST be enforced through system permissions.
- **BT-058 — Closed-loop learning:** On conclusion, pause or plateau, the Campaign MUST expose a result packet sufficient for Ripley to record `met`/`not_met`/`unclear` and a next action without inferring technical success from an accepted code increment.
- **BT-059 — Decision escalation:** Out-of-charter goal revisions, external publication, materially increased spend, integrity concerns and unresolved provider uncertainty MUST follow the relevant owner/policy gate instead of unilateral agent action.
- **BT-060 — Independent comparison integrity:** Single-agent, local-squad and foundation-assisted arms MUST record their model composition, information access, test exposure and aggregate costs; conclusions MUST distinguish these arms.
- **BT-061 — Persona independence:** Role mappings MAY change, but reassignment MUST preserve access boundaries, evidence custody and conflict-of-interest restrictions. Deferred roles MUST not be a hidden prerequisite for pilot acceptance.

**DoD:** All applicable BT-048–061 requirements are demonstrated by the new acceptance cases below, with missing capabilities reported as `BLOCKED` or `NOT_RUN`, never claimed implemented.

### A01.8 Acceptance additions (append to parent Section 9)

| Test ID | Scenario | Required result | Requirement coverage |
|---|---|---|---|
| **AT-21** | Ripley submits a goal with rationale, measurable outcomes and budget | One immutable, approved charter revision is pinned to the Campaign; source and authority recorded | BT-048–051 |
| **AT-22** | Ash's research is incomplete or contradicts other evidence | Uncertainty and alternatives retained; research cannot self-certify a competitive improvement | BT-049, 053 |
| **AT-23** | Nat rejects a suggested tactic but proposes another that serves the same goal | Campaign can plan and test it without rewriting the strategic goal | BT-051–053 |
| **AT-24** | A role tries to rewrite active goals or sealed fixtures during a test | Unauthorized modification refused; original hashes and audit record retained; appropriate escalation raised | BT-050, 052, 057, 059 |
| **AT-25** | Candidate passes code checks but loses to the champion or has inconclusive evidence | Eve's result stands; Ripley may record `not_met` or `unclear`, not a fabricated promoted champion | BT-053, 054, 058 |
| **AT-26** | Campaign reaches a plateau and requests foundation-model research assistance | Nostromo receives evidence packet; specialist work is bounded, attributable and returned as a new hypothesis | BT-053, 056, 058 |
| **AT-27** | Same starter is optimized in SquadOps-only and SquadOps-plus-Nostromo arms | Separate model/cost/intervention/test-exposure receipts; held-out comparison does not conflate arms | BT-056, 060 |
| **AT-28** | Nostromo is unavailable while a valid local campaign is running | SquadOps continues within delegated limits or pauses at a declared escalation; no hidden dependency on a deferred role | BT-055, 059, 061 |
| **AT-29** | Active Goal Set authority moves from pinned GitHub charter to SquadOps records | Exact versioned cutover; one authoritative goal source; historical references remain auditable | BT-050, 053, 055 |
| **AT-30** | A controller failure is misdiagnosed as a framework or crew problem | Evidence-based triage routes each issue to its owning repository without rewriting tactical results | BT-053, 054, 058 |

**Test impact:** Add role-authorization contract tests, immutable goal-revision linkage, handoff schema checks, negative permission tests, simulated unavailable-crew behavior, evidence-bound decision tests and an optional matched-configuration comparison. Do not mark these accepted from documentation alone; each needs exercised execution evidence.

### A01.9 Delivery and document integration

**I0 — Contract and feasibility:** Inventory current Nostromo/SquadOps interfaces, identity/delegation, goal-set readiness, repo permissions and evaluation isolation. Record `implemented`, `partial`, `proposed` or `absent` with verified seams. Do not assume proposed Project Goals and Backlog is shipped.

**I1 — Offline harness:** A pinned repository charter and research brief are enough to seed the starter controller and the first local benchmark. The full Goal Set API is not a dependency for a valid offline simulator.

**I2 — Governed Campaign iteration:** Add the research → approved goal → Nat experiment → Eve/Data report → Ripley assessment loop using existing Campaign records and compatible interfaces; test role boundaries and stop conditions.

**I3 — Publication:** Preserve owner-controlled external-write policy from parent BT-035–041. No Nostromo persona gets publication permissions merely by stewarding a goal.

**I4 — Longitudinal research:** Run matched SquadOps-only versus Nostromo-assisted variants, maintain negative findings and revise strategic priorities without exposing sealed holdouts or overstating causal attribution.

**Proposed cross-references to the parent SIP:**

| Parent location | Amendment effect |
|---|---|
| **§4.2 Role contracts** | Add A01.2 as a concrete mapping of generic roles. Parent permissions remain in force. |
| **§4.4 Artifact definitions** | Add Research Brief, Strategic Goal Set, Tactical Experiment Proposal, Outcome Evidence Packet and Strategic Assessment as linked artifacts; do not replace existing manifests/receipts. |
| **WS-05 / BT-028–034** | Add BT-048–055 and BT-058–061 to clarify goal ownership, tactical autonomy and learning feedback. |
| **WS-07 / BT-042–047** | Extend evidence correlation to research/goal/experiment/assessment identities and model-composition provenance. |
| **§7 Operating model** | Insert research-to-goal approval before Campaign initiation, strategic assessment after independent adjudication and specialist escalation only on bounded triggers. |
| **§9 Acceptance matrix** | Append AT-21–30; preserve AT-01–20. |
| **§10 Delivery increments** | Apply A01.9 sequencing, preserving the offline-first pilot. |
| **§13 Owner approvals** | Add explicit approval of role authority/delegation, temporary charter source and any later Goal Set cutover. |
| **§14 References** | Add the two repository documents below as implementation-context references, not proof of deployment. |

### A01.10 Source basis, assumptions and decision record

**Source basis:**

1. Parent SIP revision 0.1, especially §4.2 (generic role contracts), §4.4 (artifacts), WS-04 (independent promotion), WS-05 (adaptive Campaigns), §7 (operating model) and §10 (reuse existing mechanisms).
2. `backspring-labs/nostromo` — [README](https://github.com/backspring-labs/nostromo/blob/main/README.md), [capability routing](https://github.com/backspring-labs/nostromo/blob/main/crew/capabilities.yaml), and [budget profiles](https://github.com/backspring-labs/nostromo/blob/main/crew/budgets.yaml), consulted 2026-11-02. These describe intended/current crew assignments but are **not** a live health or authority audit.
3. `backspring-labs/squad-ops` — [README](https://github.com/backspring-labs/squad-ops/blob/main/README.md) and [2.6 plan](https://github.com/backspring-labs/squad-ops/blob/main/docs/plans/2-6-0-plan.md), consulted 2026-11-02. The 2.6 plan describes Project Goals and Backlog as proposed and documents the evolving crew-driven Campaign spike; this amendment does not represent it as a shipped feature.

**Not resolved by this amendment:** Real-time Battle Training provider contracts, SDK shape, exact publication quotas, runtime topology, whether any agent has operational access to a future `battle-trainer` repository, or a valid end-to-end governed research-to-goal implementation. Those belong in I0 verification.

**Requested owner ruling:** Adopt A01 as a role/authority and handoff design amendment; authorize an offline-first, version-pinned charter trial. Retain independent evaluation and publication controls from the parent SIP. A change to those controls requires a separate, explicitly reviewed policy decision.
