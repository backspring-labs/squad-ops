# 2.0.0 plan — Campaign: the squad evolves one app, the crew evolves the framework

**Status:** **adopted, rev 8 (2026-10-01).** On 2026-10-01 the owner accepted the Campaign SIP as
**SIP-0109**, after the crew approved its revision 6, and ruled this plan's seven decisions (§7): "good
to accept Campaign SIP. good with seven decisions". Rev 2 folded in an external review of rev 1. Rev 3 folded in the crew's design review of rev 2 (Ripley, on #1798), with the owner's rulings on it. Rev 4 folded in the crew's re-review, rev 5 its third review, and rev 6 its fourth (§9). Written at the 1.9.0 cut
on the owner's word ("can you draft a plan to review and any SIP revisions"). It turns three inputs into
a release:
- the owner's direction of 2026-09-28 (`docs/plans/post-1-8-2-roadmap-reconciliation.md`);
- the owner's IDEA of 2026-10-01, Nostromo as the framework optimization crew
  (`docs/ideas/nostromo-framework-optimization-crew.md`);
- the owner's rulings on that IDEA the same day (§2 below).

The design it builds on is the Campaign SIP's revision 6 (`sips/accepted/SIP-0109-Campaign-Orchestration.md`).
That SIP was accepted as **SIP-0109** on 2026-10-01, after the crew approved revision 6, and this plan adopted with it (§6, step 1).

**What 2.0 is.** An even minor, a feature release, led by one headline: **Campaign**. 1.9 extracted the
completion boundary (`CycleCompletion`, `adapters/cycles/cycle_completion.py:20`) that a campaign observes
and continues through. The roadmap's ladder puts this rung here: 1.6 taught the squad to design, 1.7
made the seams hold, 1.8 taught it to judge. **2.0 lets it run on its own, with a supervisor watching.**

**The exit claim, stated before any of it is built.** The release answers one question:

> **Can a campaign propose, obtain approval, execute, verify, recover and stop predictably, while
> preserving one accepted app and a complete evidence trail?**

It is demonstrated by a group_run campaign that:
- opens with a calibration cycle;
- advances the **same** app through at least two increments;
- has each increment proposed by the strategy role, approved at its checkpoint by the supervisor, and
  accepted with every earlier increment still passing;
- runs its cycles unattended;
- closes with an evidence package and a morning report that a reader who was not there can act on.

§4 sets the cut's pass, fail and inconclusive frame.

---

## 1. What the 1.9 line says this release has to be

| what 1.9 showed | evidence | what it says about 2.0 |
|---|---|---|
| **The completion boundary exists and is exercised:** every way a cycle ends reaches `CycleCompletion`, and the unattended chain read YES on every row | 1.9 pre-registration §10, §13 | Campaign lands **at** the boundary. It does not open the executor again |
| **Functional yield 4 of 6 on the set, cut on the owner's ruling.** Both rejections had one root cause: a React view threw under jsdom, and nothing read the error | §11e; #1784 (fixed); #1785 | **#1785, the prevention, lands before the first campaign.** A campaign multiplies every per-cycle failure rate by its length |
| **Two rejected React rolls also carried a detail route no browser could reach,** and the boot audit passed them | #1794 (fixed, PR #1797 merged); #1796 | accumulated acceptance (#1707) must check what a browser can reach, or a campaign builds increments on a broken page. **#1796 lands with #1707** |
| **N read a fourth time:** on the set both dev cells are zero; after the set, both are supplied. The convergence replay favoured scoped repair on both stacks | SIP-0107 §46r; #1764 | **the flip (step 7) is decided before the first campaign**, because a brownfield increment edits an existing app, and that edit runs through SIP-0107 (#1705). Decision 1 |
| **The instruments have gaps a frontier reader feels:** the stored generation text is cut at 10,000 characters, the replay keeps no raw response, and the release capture misreads a dead browser | #1756, #1788, #1793 | the outer loop's throughput is how fast a reader gets from evidence to a finding. These are its instruments, and the crew's first work (§3.6) |
| **Records survive only where a step keeps them:** worktree hygiene, records on the Release, deploy lineage on every cycle | 1.9 cut steps 7–8; #1720 | a campaign's evidence is write-once from the start (#1710), never reconstructed |

---

## 2. The two loops, the crew, and the owner's rulings

**The direction (2026-09-28).**

| loop | what evolves | who evolves it |
|---|---|---|
| **inner**: Campaign, a SquadOps feature | the app's scope | the squad. The strategy role proposes each increment, and the squad builds it |
| **outer**: a process | the SquadOps framework | frontier models: the owner with Claude Code sessions, and the Nostromo crew |

**The IDEA (2026-10-01)** gives the crew two jobs. It **supervises** each campaign at its checkpoints
(the IDEA's Loop 2), and it **optimizes the framework** from what campaigns show (Loop 3). It keeps
three things apart throughout: an observation, a causal hypothesis, and a validated effect.

**The owner's rulings on it, 2026-10-01:**
1. **The strategy role proposes the next increment, on a short leash.** In the owner's words: "I would
   like to get to the Squad strategy agent Nat recommending next scope, but can we put that on a short
   leash? Meaning have the Nostromo crew watch closely how features are proposed and implemented … and
   the crew needs to recommend improvements to the feature writing cycle over cycle."
   - Every proposal waits for the crew's ruling at the checkpoint: approve, request revision, or reject,
     with a reason.
   - The crew reviews how each approved increment was then implemented.
   - Its recommendations for the feature-writing step are the outer loop's first standing subject (§3.3).
2. **Crew inference on the Spark.** "Nostromo crew can run inference on the Spark in between squad
   cycles and campaigns, just not while the squad is running cycles."
   - This is the crew operating model's §36 as written (`backspring-labs/nostromo`,
     its spec `crew-operating-model.md`): the crew's development mode and counted SquadOps mode,
     never concurrent, switched by a mode file and a guard.
   - 2.0 adds the SquadOps half of that handshake (§3.2).
3. **"Good with the rest":**
   - the continuation policy stays in SquadOps, pure and testable, and the crew holds the escalation
     queue and an abort;
   - the ship's recorder is deterministic code that reads SquadOps's API, so it may run during a cycle;
   - the crew is commissioned on 2.0's pre-campaign work (§3.6);
   - every crew proposal predicts a mechanism, not only a rate;
   - the calibration cycle is the outer loop's baseline.

**What the ruling on the leash means for the design.**
- **The squad authors scope; the crew rules on it.** The crew never writes the increment.
  - It approves, **requests a revision**, or rejects. A revision request sends the proposal back to the
    strategy role, which writes the next version. The crew never edits one.
  - Every ruling binds to the exact proposal version and the accepted tree, so a stale approval cannot
    authorize changed scope.

  That keeps 2.0 the rung where the squad runs on its own, and gives the crew authority without
  authorship.
- **Within a campaign, the crew rules cycle over cycle.** Its ruling on a proposal takes effect at the
  next cycle.
- **Across campaigns, its recommendations become framework changes, with the owner's approval.** A
  change to how the strategy role writes increments is a change to the framework. It lands between
  campaigns, so that the calibration cycle can say whether it helped. Changing the strategy role's prompt
  inside a running campaign would make that campaign's own comparison meaningless.

---

## 3. The content

### 3.1 The headline: Campaign (the SIP's revision 6)

The Campaign SIP is revised to the two-loop direction: an objective envelope, a pure continuation
policy, and a campaign that evolves one app. The plan sequences its parts. The design is the SIP's.

| part | issue | required for | what it is |
|---|---|---|---|
| **the campaign object and the control log** | #1799 | first campaign | model, registry (memory and Postgres), `Cycle.campaign_id` and `kind`, lifecycle, `/api/v1/campaigns` and the CLI; **a transactional control log as the authority** for every control operation, with security audit and events as projections; **a launch-intent outbox with idempotent cycle creation**, so each decision launches exactly once (SIP §12b, §13, §15–§17) |
| **the continuation decision and the limits** | #1800 | first campaign | **an ordered, three-step decision** at the completion boundary (SIP §10): terminal outcomes, then a pending action, then a pausing guard. A pause holds the pending action, and the owner's resume executes it without recomputation. Reads `CycleAssessment`; each limit's action, and who resumes (SIP §9.5) |
| **the increment cycle** | #1705 | first campaign | workloads `proposal` → gate `increment_ruling` → delta-scoped `framing` → gate `progress_plan_review` → `implementation`, starting from the accepted tree; **a typed change request** whose manifest delta the gates check, with a derived footprint the plan validator enforces (SIP §7) |
| **the evaluator trees** | #1806 | first campaign | accepted (immutable), candidate, **the baseline-evaluator overlay** (the accepted tree's product code plus the candidate's tests, never its product code), and **the candidate-verifier overlay** (the candidate's product code under one frozen criterion's bundle, never its own test files); test identity; **content-addressed verifier bundles**, one per criterion (SIP §7.4, §8) |
| **accumulated acceptance** | #1707, #1796 | first campaign | every earlier increment's acceptance still passes, **including each declared page rendering its view in a browser** (#1796); **each criterion the increment adds has a test that fails on the baseline for the intended reason**, through the app's public surface (SIP §8.2) |
| **the prior-cycle brief** | #1692 | first campaign | a repair or retry cycle is told what the cycle before it did |
| **the proposal run and the increment gate, on the leash** | #1706, #1708, #1801 | first campaign | §3.2 |
| **the box lease** | #1802 | first campaign | one owner of the Spark at a time, enforced at every launch (§3.2) |
| **recovery** | #1803 | first campaign | restart, duplicate completion, repeated ruling, interrupted promotion, abort. Each guarantee is verified by a fault-injected diagnostic (SIP §12a) |
| **the calibration cycle** | #1709 | first campaign | every campaign opens with group_run built from scratch: the yardstick for greenfield behaviour |
| **the brownfield reference scenario** | #1804 | shakeout | a fixed baseline and change request: the yardstick for proposal writing, scoped repair and accumulated acceptance (SIP §11a) |
| **the evidence package and the morning digest** | #1710 | shakeout (its failure producer: first campaign) | write-once campaign records, readable without the deploy that made them, with every failure under the failure-attribution registry's vocabulary (§3.7). The digest the owner reads **opens with the squad's first pass** at what went wrong: each claim cites its run, cycle and artifact ids and the log excerpt it rests on, a lead rather than a finding (#1719) |
| **campaign and deploy tags on Prefect runs** | #1728 | cut | with #1720's deploy records |
| **the request-profile taxonomy** | #316 | first campaign | a continuation that names the next cycle's profile needs one coherent namespace |

### 3.2 The increment proposal on the short leash (#1706, #1708)

**The proposal is the increment cycle's first run** (SIP §9.1). It is a run like any other: one task
(`strategy.propose_increment`), recruited by the coordinator and released at its end, with its own
request profile, budget, persisted inputs and output, retry and restart. Its output is a **typed change
request**:
- a PRD delta;
- a typed manifest delta;
- acceptance criteria, each tied to a public surface;
- what it must not break, and what it retires;
- a footprint derived from the delta, never authored.

Rails from #1706: an out-of-scope proposal is refused, not trimmed, and no other role proposes.

**The leash is a gate after the proposal run** (SIP §9.2), using the gate decisions that already exist:

| ruling | gate decision | what follows |
|---|---|---|
| approve | `approved` | delta-scoped framing, then the build |
| request revision | `returned_for_revision` | a new proposal run in the same cycle, carrying the supervisor's note |
| reject | `rejected` | the cycle ends with no build |
| (refine) | `approved_with_refinements` | **not legal here.** Refining would make the supervisor an author |

- **Every ruling binds** to the proposal's version and hash and to the accepted tree. A stale ruling is
  refused. A reused idempotency key with a different payload is refused.
- **A ruling that does not come pauses the campaign** after its bound: 30 minutes for the crew, 12 hours
  for the owner, each declared in policy. It never proceeds unapproved.
- **There is no auto-approval tier in 2.0, and the owner is the fallback approver,** ruling through the
  same gate path.

**The box (ruling 2; #1802).** SquadOps records one owner of the Spark at a time.
- **The supervisor holds the lease while the gate is open.** The proposal run has ended, and no run is
  in flight.
- **Every launch and every run start on the box** refuses while the supervisor holds it. Every launch
  also requires a quiet box: every loaded model must be in the active deploy record (#1720), and every
  GPU process must belong to a declared engine. An unreadable engine counts as not quiet.
- **A refused launch** waits as launch-blocked, retries within a count, then escalates.
- SquadOps reads its own lease and the box, never the crew's files.

**The proposal ledger: the data the leash produces.** One record per increment:
- each proposal version, and the crew's ruling, its reason and its binding;
- what the cycle then did: verdict, correction rounds and their causes, framing re-rolls, the criteria the
  increment added with each one's discriminating test, and any earlier increment it broke;
- the crew's classification of what went wrong, if anything. The candidates are scope too large,
  acceptance criteria not checkable, a conflict with an earlier increment, an ambiguous manifest delta,
  and a correct proposal implemented badly. That last one is not a feature-writing defect.

This ledger is how the crew sees "where the weakness is" in feature writing. It is the evidence any
later loosening of the leash would need. **2.0 does not decide to loosen it.** It records what the
decision would read (decision 4).

### 3.3 The outer loop (#1711)

The runbook, written close to the first campaign, carries the IDEA's §7–§9 with the rulings applied.
- **Two speeds of verification.** A fast lane between campaigns: the unit suite, the calibration cycle,
  and a small fixed regression pack. The next campaign is the soak. **Full pre-registered sets** are
  kept for release cuts and headline claims.
- **The proposal schema** is the IDEA's eight fields, with one change: the prediction names a
  **mechanism**, meaning the logged fact or record field that changes, beside any rate. At a campaign's
  N, a rate alone cannot separate an effect from noise. The verification sets learned that repeatedly.
- **Frontier models are spent on judgement, not on reading** (#1719). The frontier reader starts from
  the squad's first pass in the digest, and decides what the squad cannot: whether the diagnosis is
  right, and whether the cause is the app, the framework, or model variance. The squad and the
  evidence package do the reading.
- **The baseline for "it improved" is the calibration cycle**, run on the deploy before and after the
  change. The increments are not the baseline: they change from campaign to campaign.
- **The first standing subject is feature writing**, the strategy role's proposals, from the ledger
  (§3.2).
- **The approval boundary:** the crew triages during a campaign. It lands framework changes only between
  campaigns, only with the owner's approval, and through the repository's normal review. It never merges
  silently, never extends budget or scope, and never promotes an architectural change on its own.

### 3.4 The supervision interface: what SquadOps gives the crew

One control surface, on the existing lanes. No shadow control plane.

| need | the seam | state today |
|---|---|---|
| create, start, inspect, pause, abort a campaign; read the ledger and the control log | `/api/v1/campaigns` (the route-lane standard, `docs/architecture/api-route-lanes.md`) | none: new with the campaign object (#1799) |
| rule at the increment gate, bound to the proposal version and the accepted tree | the existing gate decision path (`GateDecisionValue`, `src/squadops/cycles/models.py:57-63`) | exists; the binding and the idempotency key are new (#1801) |
| acquire and release the box lease | the same resource, enforced at every cycle launch | none: new (#1802) |
| cancel a stalled run | the existing cancel path | exists (#1683, #1700) |
| an identity for the crew, least privilege | Keycloak roles (SIP-0062) | **two roles, each enforced by the API:** a supervisor role (campaign controls and reads), and a read-only triage role (`cycles:read`). **Crew accounts reach SquadOps through the CLI and API only, with no docker access** (#1719). The network path from cloud roles is a security design the owner reviews; its specifics stay out of the public record |
| an authoritative record of every control operation: actor, role, reason, target, idempotency key, binding, outcome | **the campaign control log**, transactional with each state change; security audit is a projection | new (#1799). `AuditPort` is fail-open by contract (`src/squadops/ports/audit.py:16-17`), and `AuditEvent` has no role, reason or idempotency key (`src/squadops/auth/models.py:139-153`), so it cannot be the authority |
| events, and authoritative snapshots after a missed event | the cycle event bus (`src/squadops/ports/events/cycle_event_bus.py`) and the API's reads | the bus exists; no endpoint streams cycle events (only chat streams). Snapshots by polling suffice for the first campaign |
| tree identity per cycle and per accepted increment | workspace revision ids (#734); SIP-0107 §20's verified identity | exists per cycle; the accepted-tree identity per increment is #1705/#1707's |
| cost: tokens by role, task and model | the usage ledger and LangFuse | exists per cycle; per campaign is the evidence package's |
| which framework ran | deploy records (#1720) on every cycle | exists |
| isolated replay with a fresh run identity | SIP-0101 | the minimum slice is maintainer-only. Exposing it to the crew is **not in 2.0.0** (the IDEA's Phase B) |

### 3.5 Carried in: the placements 1.9 made

Each item is classified: **first campaign** (required before it), **cut** (required for the release), or
**deferrable** (it may move to 2.1 without changing the claim).

| issue | what | required for | placement |
|---|---|---|---|
| #1785 | the two jsdom pitfalls, shown in the develop and qa prompts | **first campaign** | before the shakeout |
| #1796 | the boot audit renders each declared route | **first campaign** | with accumulated acceptance (#1707) |
| #1757 | what rewind means for an unattended run | **first campaign** | with recovery (#1803) |
| #1755, #1727, #1788 | the qa re-take's dropped files; §20 on the re-take path; the replay's raw response | **first campaign, if decision 1 flips** | the flip's prerequisites, #1788 first. Deferrable if it does not flip |
| #949, #950, #557 | the framing revision boundary; the plan gate's review packet; the post-retest acceptance review | decided with the gate policy (#1708) | each absorbed by #1708 (then first campaign) or deferrable, ruled at adoption |
| #1793 | the release capture | **cut** | the cut's screenshots depend on it; the crew's commissioning work (§3.6) |
| #414 | the sequencing rule: an unrepaired non-required failure does not stop the run reaching its required checks | deferrable | if built, it lands before the shakeout, and its counted evidence is a **dedicated diagnostic** placing a non-required failure ahead of a required check. A campaign set will not reliably produce that case, so its cycles carry it only as texture |
| #1031 | the manifest-authoring design primer | deferrable | it pays at the brownfield manifest delta (#1705) |
| #1756 | stored generation text cut at 10,000 characters | deferrable | crew commissioning work (§3.6); unblocks #567 |
| #567 | the fenced parser's CommonMark engine | deferrable | blocked on #1756's corpus |
| #1469 | the per-module build signature | deferrable | blocked on its corpus; re-read at the cut |
| #1039 | the docs site's remainder | deferrable | idle-box time |

### 3.6 Commissioning the crew on 2.0's own work

The crew is not commissioned yet. Its §43.1 requirements are its own to meet, and its one squad-ops PR
is the probe #1512. Commissioning it on the pre-campaign work means the first campaign is not also its
first job. 2.0's list has items that fit the operating model's §44.1 "safe first" archetypes:

| item | archetype (§44.1) | why it is bounded |
|---|---|---|
| #1793, the release capture: the vault path, the browser's error page, a browser setting | 9 (guard authoring) and 10 (evidence instrument fields) | the refusal's attribution has a real fixture: the 2026-10-01 error page |
| #1788, the replay keeps its raw response | 10 | the field's producer is named and its three states are specified |
| #1756, the stored generation text is not cut | 10 | the producer is named; the corpus it unblocks is #567's |
| the ship's recorder (§3.4), deterministic | the crew's own repository | nothing in squad-ops changes |

The order and the gate are the crew's operating model to settle (the 09-28 note: "Nostromo's
commissioning order … is the crew's operating model to settle").

### 3.7 The other proposals reviewed at drafting (2026-10-01)

The owner brought two more proposals to this plan's review. Each was checked against what exists, and
placed:

| proposal | exists? | before the first campaign | after |
|---|---|---|---|
| **Verification Yield and Test Value** (`sips/proposed/SIP-Verification-Yield.md`, new) | no. It overlaps `SIP-Test-First-Verification.md` (proposed in August, not built), which is its mechanism for the squad's own tests | **each criterion an increment adds has a test that fails on its baseline for the intended reason** (Campaign SIP §8.2); preservation tests may pass on both. Without it, accumulated acceptance is only as strong as its weakest, never-failing test | the stub-based red gate for greenfield cycles; risk-first qa instructions (an outer-loop experiment); the audit, fault corpus and deletion experiment on the framework's own suite (crew work); verification-cost reporting |
| **Cross-Cycle Memory, the v4 draft** | **yes**: it is a later draft of `SIP-Cross-Cycle-Memory.md`, folded in as revision 3 in **its own PR, #1805**, reconciled with its Phase 1 rules after the crew's review | **one line:** the evidence package records failures under the failure-attribution registry's vocabulary, so 2.2 mines campaigns without reconstructing them | all of it. v2.2 as ruled, with the empty recall rail in v2.1. Revision 3 proposes that only owner-approved patterns inject into counted cycles |

---

## 4. The verification story

**What the release claims, and how each claim is read:**

| claim | read from | not a substitute for it |
|---|---|---|
| the app evolves: two or more increments accepted on one tree, earlier increments still passing | the evidence package; accumulated acceptance per increment | a cycle's own verdict |
| the strategy role's proposals hold up | the proposal ledger: rulings, reasons and outcomes | a count of proposals |
| each criterion an increment adds is guarded by a test that can fail | the ledger's per-criterion baseline results (Campaign SIP §8.2) | a passing suite |
| the campaign ran unattended between checkpoints | the chain's four properties per cycle (1.8.2's claim), and zero manual steps in the record | the absence of complaints |
| the supervisor loop works | each checkpoint's ruling and its binding, its latency, the lease handoff, and the audit trail | the crew's report alone |
| the campaign recovers and stops predictably | each recovery diagnostic (#1803), and every limit reached in the set taking its declared action (#1800) | a set in which nothing went wrong |
| greenfield building on group_run React did not regress | the calibration cycles against 1.9's set's React counted rolls | a claim about the framework as a whole |
| the brownfield mechanisms work | the brownfield reference scenario (#1804): delta framing, scoped repair, accumulated acceptance, and the rated proposal | the calibration cycle, which exercises none of them |

**The cut's evidence: a pre-registered campaign set,** in 1.9's discipline: predictions before the first
launch, readings per cycle, drift declared. Its size is decision 3. The fast lane between campaigns is not
the cut's evidence.

**The cut's frame, which the pre-registration makes exact before the first launch:**
- **Pass:**
  - every campaign runs to its end by its own rules;
  - no safety guarantee is violated in any campaign: no unruled build, no stale ruling honoured, no lost
    ruling, no duplicate launch, no partial promotion, no launch beside a crew model, and an evidence
    package complete at close;
  - at least one campaign advances its app through two or more accepted increments with accumulated
    acceptance held.
- **Fail:** any safety guarantee violated, or no campaign reaching two accepted increments.
- **Inconclusive:** a campaign ended by a cause outside the framework, such as a box halt. It is re-run
  under 1.8.2's void rule: a run lost to a box halt does not spend the budget.
- **Rejected proposals and failed increments are data, not failures.** The leash and the limits working
  is part of the claim. Each is read by its signature.
- **Owner interventions:**
  - the owner ruling as fallback supervisor is reported separately from crew supervision;
  - any owner action outside the interface (a manual repair, a manual restart) is an intervention, and
    voids that campaign's claim of unattended operation.
- **Crew supervision is claimed only for a campaign whose every checkpoint the crew ruled.**
- **A framework fix during the set:** nothing merges while the set is open (1.9's rule). A fix voids the
  set, and it restarts on a new deploy after the shakeout loop.
- **What the sample can say:** two campaigns show that the mechanisms work and stop safely. They are not a
  reliability rate, and the record says so.

**The predictions name mechanisms.** For example:
- "the brownfield cycle's framing runs only the delta tasks" is read from the task ledger;
- "a failed increment leaves the baseline untouched" is read from the accepted-tree identity before and
  after.

---

## 5. Re-placements by name: every open issue placed

**33 open issues on 2026-10-01, after rev 3**, each placed once. These are the 26 open after #1794 closed
(PR #1797), the 6 filed from the external review, and #1806 from the crew's review:
- **The headline (18):** #1705, #1706, #1707, #1708, #1709, #1710, #1711, #1692, #316, #1728, #1796,
  #1799–#1804 (the campaign object and control log, the continuation decision and limits, the
  supervision interface, the box lease, recovery, and the brownfield reference scenario), and #1806
  (the evaluator trees).
- **Carried in (14):** #1785, #414, #1755, #1727, #567, #1031, #1469, #949, #950, #557, #1757, #1039,
  #1756, #1788. Each is classified in §3.5.
- **Instruments, the crew's first work (1):** #1793. With #1756 and #1788 above, these are §3.6.

**Not an issue, named so it is not lost:**
- SIP-0107 §38 step 7, the flip (decision 1);
- the SIPs placed in §3.7: Verification Yield (new), Test-First Verification, and Cross-Cycle
  Memory revision 3;
- the crew's §36 handoff, which is the crew's to build and SquadOps's to meet (§3.2);
- the Capability-Backed Agents SIP and Cross-Cycle Memory (decision 5).

---

## 5a. Status at the end of the shakeout loop (rev 9, 2026-10-03)

§5 placed every open issue at adoption. This section records where each stands after the build and
five shakeout campaigns, and adds the issues filed since. **Built** means merged, deployed and, where
named, seen working live. The re-placements below, and the closures, were **ruled by the owner on
2026-10-03** (§5a.5). Each placement names its release.

### 5a.1 The Campaign (2.0) issues

Fifteen issues carry the title. Three are closed: #1728, #1802 and #1804.

| issue | built (evidence) | what is left | placement |
|---|---|---|---|
| #1799 the campaign object and control log | model, registries, `/api/v1/campaigns`, CLI, outbox, projections (#1808, #1809, #1815, #1816, #1838; SIP-0109 §24e). Restart from Postgres held by integration tests; audit per row | nothing in its acceptance | **closed, 2026-10-03** |
| #1800 the continuation decision and limits | §10's fourteen rows, pure (#1825); the owner's word (#1835); the completion hook (#1834). Live: row 3 success (shakeout 5), row 4 exhausted (shakeout 4), row 8 repair and row 9 escalate on `blocked_unverified` (shakeout 5) | the retry rows' reachability is #1824's | **closed, 2026-10-03** |
| #1801 the supervision interface | the increment gate and its binding (#1828), revision in a new run (#1830), ruling from the reviewed change request (#1836), the ledger and classification (#1841), the ruling bound (#1895). Live: a revision returned and re-ruled (shakeout 5) | the lease's return at the crew's bound (§24ae, not built); the crew's network path is decision 6, not this issue | **closed, 2026-10-03** |
| #1705 the brownfield increment cycle | steps a–e (#1840, #1842, #1843, #1844, #1848, #1850–#1852, #1854; §24j–§24p). Live: two increments accepted on one tree (shakeouts 4 and 5) | nothing in its scope | **closed, 2026-10-03** |
| #1706 the proposal run | the change request and its rails (#1818), the run (#1820, #1821). Live in every increment | nothing | **closed, 2026-10-03** |
| #1707 accumulated acceptance | discrimination and frozen criteria (#1823, #1839, #1863). Live: T1–T3 held, T4 discriminating (shakeout 4) | nothing | **closed, 2026-10-03** |
| #1806 the evaluator trees | trees, verifier bundles, test identity (#1822) | nothing | **closed, 2026-10-03** |
| #1709 the calibration cycle | every campaign opens with it (#1831, #1834). Accepted in all five shakeouts | its yardstick reading against 1.9 is the set's (§4) | **closed, 2026-10-03** |
| #1708 the gate policy for unattended cycles | the increment gate is supervised and bounded (#1801, #1895); an increment's plan gate decides itself when no question is open (#1905), and an answered question carries forward (#1885). **A plan gate waiting on a question is bounded and recorded: #1918** (§24aj). **One supervisor's bound, whoever holds the seat: #1920** (§24al, the owner's ruling) | auto-decision within scope and an escalation queue: **not 2.0** (decision 4) | **the 2.0 part built**; the auto tier and the queue **2.2.0** |
| #1710 the evidence package and digest | the failure producer and records (#1811, #1813); the package and digest at close (#1837, §24h). **What died with the logs is kept: #1919** (§24ak): the runs' revision forms persisted and carried in the package; each cycle's log window archived on the Spark | the size bound; the app's evolution with screenshots (the owner's 2026-09-28 input); the squad's first pass (#1719; who writes it is the owner's open question) | **the capture built**; the renderings **after the set, before the cut** (re-materialized from records) |
| #1711 the outer-loop runbook | the minimum runbook (#1904, step 12), grown through the shakeouts | the loop's second half: fix, redeploy, next campaign, the approval boundary, the calibration as baseline | **after the set** (step 15) |
| #1803 recovery semantics | a cycle that ended undecided is re-heard at startup (#1860, §24v); the live launch-blocked diagnostic ran in #1802's proof (refused, escalated, resumed) | **the remaining fault-injected diagnostics (§12a, §19 item 1)**, designed in the validation plan's §3 (#1807): a restart at each state, a duplicate completion, a repeated and a conflicting ruling, an interrupted promotion, an abort. The pre-registration reads them as the set's recovery evidence. Not built: a re-hear between restarts; escalating a launch the preflight refuses (§24e) | the harness in `scripts/dev` (it does not move the deploy), run **after the exit shakeout, before registration**, on the registered deploy |
| #1824 the retry rows are unreachable | evidence: none of 156 stored failed cycles reads `environment_or_infrastructure_failure`, and `INFRASTRUCTURE_FAILURE` has no producer | the gap is in attribution (SIP-0108), not in §10. Escalating is the safe direction: every failure outside the work goes to the owner | **2.1.0**, with the attribution work; rows 10–11 named in the record as unreachable |

### 5a.2 The rest of §5's headline and carried-in issues

| issue | status | placement |
|---|---|---|
| #1692 the prior-cycle brief | built for repair and retry (§24u) and for the proposal after an abandoned increment (§24w). Not built: the correction chain's own record, the recurrence measure | **the remainder 2.1.0** |
| #1796 route rendering | the campaign side is built: an increment's evaluation renders every declared route (§24p). The boot audit itself still checks only the API calls | **the boot-audit half 2.1.0** |
| #316 the request-profile taxonomy | not built. A campaign names its profiles in its policy, so it did not need one namespace | **2.1.0** (a structural refactor) |
| #1757 rewind for an unattended run | not built. A cycle whose correction rewinds ends its run, and the campaign decides from the ending | **2.1.0**, unless the set shows rewind ending an increment the campaign could have kept |
| #1727 §20 on the re-take path | not built. Its stake was N's count, and N became texture (decision 1's ruling) | **2.1.0** |
| #1788 the replay's raw response | built (#1892); the re-run read; the flip merged (#1909); **the checkpoint pair read on the flipped deploy:** both stacks accepted, and no repair refused (SIP-0107 §46s) | **closed** by this revision's PR |
| #949, #950, #557 | not built. Decision 4 keeps every increment gated, so none is needed in 2.0 | **2.2.0**, with the gate loosening, decided from the ledger |
| #1785, #1755 | closed | — |
| #1793 the release capture | open | the cut, as placed |
| #414, #567, #1031, #1469, #1756 | open | **2.1.0** |
| #1039 the docs site's design pass | open | deferrable, as placed |

### 5a.3 Filed since adoption

- **Found during the build and the shakeouts, each fixed and closed:** #1817, #1832, #1845, #1857, #1864, #1866, #1868,
  #1870, #1872, #1874, #1876, #1877, #1880, #1885, #1887, #1891, #1897, #1898, #1902, #1905, #1912.
- **Open:**
  - **#1884** (criterion files asserting behaviour the change request never stated): the teaching
    shipped (#1886) and held on its first live read. It is read as texture (P9 in the
    pre-registration draft). **Kept open as texture**, closed when the set has read P9.
  - **#1911** (a repair's completion spent on reasoning): measure before changing any budget.
    **2.1.0.**
  - **#1913** (the qa agent's checks read a file the runtime drops): its live trigger is removed by
    #1912. **2.1.0.**

### 5a.4 The path to registration

1. **Before the exit shakeout,** because each changes what the set runs: #1708's plan-gate bound
   (#1918, merged), #1710's capture (#1919, merged), and the one supervision bound (#1920).
2. **The exit shakeout:** shakeout 6, on the deploy that carries them, with the log archive beside
   it. It also reads #1802's live-lease proof (the quiet-box half ran on 2026-10-03).
3. **On the registered deploy, before registration:** #1803's recovery diagnostics, as the
   validation plan's §3 (#1807) designs them. **#1922** (found 2026-10-03 by reading the code
   ahead of the restart diagnostic): a restart mid-cycle left a campaign's gate decision unacted
   on and its run stuck `running`. The fix (#1923, SIP-0109 §24am) re-attaches campaign cycles at
   startup. It lands before rebuild 17, so the exit shakeout and the diagnostics run on a deploy
   that carries it.
4. **The owner's stop:** registration (#1908), after the crew's re-review. **Who supervises is not a
   SquadOps decision** (§24al): decision 2 resolves to whoever rules, recorded as each ruling's
   actor, and decision 6 belongs to the crew's access, not to the set.
5. **After the set, before the cut:** #1710's renderings, #1711's runbook, #1793's capture.

**#1807, the validation plan** (verification matrix, recovery diagnostics, reference scenario
inputs) sat unmerged from 2026-10-02, outside this section. The 2.0 regression configs cite it as
their pre-registration. It is brought to rev 3 and merged before the diagnostics are built.

**Where §5's placements did not hold:** §5 placed #316, #1727, #1757 and #1796's boot-audit half as
"first campaign", and five shakeout campaigns ran without them. Each is re-placed above, with its
reason. That a placement had passed unmet was surfaced only on the owner's question. The working rule
since: an issue is closed the moment it is met, and each new finding is placed in this plan when it
is filed.

### 5a.5 Ruled by the owner, 2026-10-03

- **The re-placements:**
  - **2.1.0** (the feature-free stabilization release): #316, #1824, #1727, #1757, #1796's boot-audit
    half, #1692's remainder, #1911, #1913, #414, #567, #1031, #1469 and #1756;
  - **2.2.0** (the next feature release): #1708's auto-decision tier and escalation queue, and #949,
    #950 and #557, decided from the 2.0 campaigns' proposal ledger;
  - **2.0.1:** nothing now. It stays free for anything urgent the set or the cut turns up.
- **The eight built Campaign (2.0) issues are closed:** #1799, #1800, #1801, #1705, #1706, #1707,
  #1806, #1709.
- **The order to registration (§5a.4):**
  1. #1708's plan-gate bound and #1710's capture of what dies with the logs;
  2. then the exit shakeout;
  3. then #1803's diagnostics on that deploy;
  4. then the pre-registration.

---

## 6. Sequencing

Merge order follows the dependencies (the Campaign SIP's §18). Each step's PR proves its
intermediate acceptance before the next starts.
1. **Done, 2026-10-01: the Campaign SIP accepted as SIP-0109** at revision 6, after the crew's approval,
   and this plan adopted.
2. **Decision 1, the flip,** and its prerequisites: #1788 first, then #1755 and #1727.
3. **The domain model, the transactional control log, and the launch outbox (#1799).** Proves atomic
   commit with state, conflicts refused, restart read from the log, and exactly one cycle per launch
   intent under a crash on either side of creation.
   - **Then the one failure producer (#1710's first part):** `failure_events(outcome, evidence)`
     extracted. In one completion transaction, the events are persisted and then the attribution is
     computed from them. It is behaviour-neutral, and proves it by backfilling every stored cycle and
     recomputing its attribution unchanged.
4. **The proposal run and the typed change request (#1706).** Proves recruitment like any run,
   out-of-scope refusal, and the delta through the manifest gates.
5. **The evaluator trees and the verifier bundles (#1806).** Proves the accepted tree immutable, no
   candidate product code in the baseline overlay, no candidate test files in the candidate-verifier
   overlay, and that adding a criterion changes no other criterion's bundle.
6. **Accumulated acceptance and baseline discrimination (#1707, #1796),** with the prior-cycle brief
   (#1692). Proves frozen criteria executing, and import errors not counted.
7. **The increment gate, the binding, the box lease, the continuation decision, and repair and retry
   cycles (#1801, #1802, #1800, #1705, #1708, #316).** Proves stale and conflicting rulings refused,
   every launch path honouring the lease, each row reachable, a paused action resumed exactly once, and
   repair and retry reusing exactly the bound request.
8. **The audit and event projections.**
9. **The calibration cycle, the reference scenario, the evidence package and digest (#1709, #1804,
   #1710).** Proves the package materializing from records alone.
10. **The recovery diagnostics (#1803),** with #1757.
11. **Alongside, where files allow:** #1785, the crew's commissioning work (§3.6), #1728.
12. **A minimum runbook (#1711), with the recovery instructions,** before any campaign runs.
13. **A shakeout campaign:** two increments, supervised by the owner if the crew is not commissioned
    yet. It is read for seam findings, on 1.9's shakeout-loop rules.
14. **The pre-registration** (stop for the owner), with the cut's frame (§4) made exact. Then the
    campaign set.
15. The runbook, finalized from the shakeout and the set.
16. The cut.

---

## 7. Decisions at adoption: ruled by the owner, 2026-10-01

**Ruled: all seven, as recommended, with the crew's refinements below adopted** ("good with seven
decisions").

1. **SIP-0107's flip: decide it before the first campaign.**
   - **Recommendation: flip to scoped revision first,** once #1788 has explained the nine empty
     scoped Next.js repairs.
   - The replay (#1764) found scoped never converged worse and regressed in no sample.
   - A brownfield increment is an edit of an existing app, which is what scoped revision is for (#1705).
   - The alternative is a fifth count of N on 2.0's set, which the campaign's edits would supply as
     texture.
2. **Who supervises the first campaign.** **Recommendation: the crew if commissioned by step 6, the
   owner otherwise,** through the same API. The leash is the same either way.
3. **The size of the cut's campaign set.** **Recommendation: two campaigns of three increments each,**
   each opening with its calibration cycle and run beside the brownfield reference scenario. Two, so one
   campaign's bad night does not decide the release; three, so accumulated acceptance is tested against
   more than one earlier increment. It demonstrates the mechanism, not a rate (§4).
4. **Loosening the leash: not in 2.0.** **Recommendation: record what loosening would read,** and decide
   it in 2.x from the ledger. For example: a run of proposals approved at their first version, accepted
   without breaking earlier increments, under a narrower scope.
5. **Capability-Backed Agents.** The roadmap row leaves it to this plan. **Recommendation: not in
   2.0.0.** Campaign is the release's one headline. Cross-Cycle Memory is already ruled to 2.2.
6. **The crew's access path to the runtime API**, from cloud roles. **A security design for the owner's
   review before the first supervised campaign.** Its specifics stay out of both public repositories.
7. **What 2.0.0 means.**
   - **Recommendation: state the project's convention in the CHANGELOG.** The major marks a capability
     rung, not a compatibility break. The roadmap ruled on 2026-09-12 that 2.0 is the boundary between
     the major versions.
   - 2.0's planned surface changes are additive: a new `/api/v1/campaigns` resource, a nullable
     `Cycle.campaign_id`, and a launch gate that refuses only while a supervisor holds the box lease.
   - Any break found during the line is named in the CHANGELOG under its own heading.

**The crew's review answered all seven (Ripley, on #1798, at the SIP's revision 3).** It concurred
with each recommendation, and its refinements are part of the owner's ruling:
- **Decision 1:** the flip stays conditional on #1788 explaining the nine empty Next.js repairs. **If
  the raw responses show a framework or tooling defect, rather than scoped revision's own inability, it
  is fixed and the replay re-run before flipping.**
- **Decision 2:** the crew supervises campaign 1 **only if its commissioning evidence is complete**.
  Otherwise the owner supervises the shakeout, through the same interface.
- **Decision 3:** two campaigns of three increments, **claiming only the mechanism and safe stop**,
  never a rate.
- **Decisions 4–7, as recommended:** every increment stays gated in 2.0, with the ledger designing any
  later loosening; Capability-Backed Agents are deferred beyond 2.0; the runtime access path stays a
  private, least-privilege security design for the owner; and 2.0 is a capability rung, with any actual
  break named separately in the CHANGELOG.

**The limits' values.** They are set from the shakeout at the pre-registration, as proposed, under the
crew's conditions:
- **the complete policy is immutable for the counted set;**
- the evidence records each value **and its shakeout basis;**
- **where the shakeout does not support a value, a conservative explicit cap is used,** never an
  inferred default.

## 8. What this plan does not decide

- The Campaign SIP's design: that is its revision and its review.
- The crew's operating model: commissioning order, which roles run on which models, the recorder's code.
  The crew's own repository holds that.
- `fork` (concurrent sibling cycles): the SIP defers it, so #288's window is not opened in 2.0.0.
- The IDEA's Phases B–D: repeated optimization, memory and transfer, cross-domain.

## 9. Revision history

- **Rev 10 (2026-10-03, afternoon):** §5a brought current the same day:
  - #1708's plan-gate bound (#1918) and #1710's capture (#1919) built;
  - the flip's checkpoint pair read (SIP-0107 §46s), closing #1788;
  - the owner's ruling that supervising is one need, whoever holds the seat (§24al, #1920), which
    takes decisions 2 and 6 off SquadOps's path;
  - #1807 placed.
- **Rev 9 (2026-10-03):** §5a records each 2.0 issue's status after the build and five shakeout
  campaigns. It covers the Campaign (2.0) issues, the rest of §5's issues, and the issues filed
  since. It names what remains before the exit shakeout, before registration and before the cut. The
  owner ruled the re-placements the same day (§5a.5):
  - the deferrals go to 2.1.0;
  - the gate loosening goes to 2.2.0;
  - 2.0.1 is kept for anything urgent;
  - the eight built Campaign (2.0) issues are closed;
  - the order to registration stands.
- **Rev 8 (2026-10-01, late evening):** #1719's ideas, revised to match SIP-0109, are folded in:
  - the digest opens with the squad's first pass;
  - frontier models are spent on judgement, not on reading;
  - the crew has two roles, and reaches SquadOps through the CLI and API only.
- **Rev 7 (2026-10-01, late evening): adopted.** The crew approved the SIP's revision 6 for
  implementation, and the owner:
  - accepted it as **SIP-0109**;
  - ruled all seven decisions as recommended, with the crew's refinements;
  - merged Cross-Cycle Memory revision 3 (#1805).
- **Rev 6 (2026-10-01, late evening):** folds in the crew's fourth review. It confirmed rev 5's
  corrections, and named one final contradiction (escalation and the pausing guard), resolved in the
  SIP's revision 6.
- **Rev 5 (2026-10-01, late evening):** folds in the crew's third review. The SIP's revision 5 makes
  its bounded corrections: verifier bundles executed through a candidate-verifier overlay, launch
  actions separated from control transitions, the outcome-aware failure producer, and deterministic
  repair exhaustion. This plan's step 3 now uses that producer's signature.
- **Rev 4 (2026-10-01, late evening):** folds in the crew's re-review of rev 3. It confirmed rev 3 closed
  its seven blockers, and named five seams, closed in the SIP's revision 4:
  - the held pending action and its resume;
  - the repair and retry contract;
  - the launch outbox with idempotent cycle creation;
  - one failure producer and its write point;
  - criterion-owned verifier bundles.

  The crew's answers to the seven decisions and its rule for the limits' values are recorded in §7.
- **Rev 3 (2026-10-01, evening):** folds in the crew's design review of rev 2 (Ripley, on #1798), with
  the owner's rulings on it:
  - the proposal as the increment cycle's first run, with the ruling as a gate using the existing gate
    decisions;
  - the transactional control log as the authority;
  - the typed change request and the three trees (#1806);
  - the ordered continuation table;
  - merge order by dependency, with each step's intermediate acceptance;
  - Cross-Cycle Memory revision 3 split into its own PR (#1805).
- **Rev 2 (2026-10-01):** folds in an external review of rev 1. Its nine points were each accepted:
  - the box handoff as one recorded owner, enforced at every launch, with a proposing phase (#1802);
  - revision requests instead of edits, and rulings bound to the proposal version and the accepted tree
    (#1801);
  - recovery guarantees verified before the first unattended campaign (#1803);
  - the limits, and who resumes them (#1800);
  - the baseline rule narrowed to one discriminating test per criterion;
  - the brownfield reference scenario, with the regression claim narrowed (#1804);
  - the cut's frame;
  - the minimum runbook before the shakeout;
  - tracked deliverables (#1799), a uniform classification of carried-in work, #414's evidence placed,
    and what 2.0.0 means (decision 7).

  The exit claim now leads with the review's question.
- **Rev 1 (2026-10-01):** the draft, written at the 1.9.0 cut from the 09-28 direction, the owner's IDEA,
  and the owner's rulings on it. For review. Amended the same day with §3.7: the owner's two further
  proposals, Verification Yield and Cross-Cycle Memory v4, each checked against what exists and placed.
