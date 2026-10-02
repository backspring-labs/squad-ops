# 2.0.0 plan — Campaign: the squad evolves one app, the crew evolves the framework

**Status:** DRAFT, rev 2 (2026-10-01), for the owner's review. Rev 2 folds in an external review of rev 1 (§9). **Not adopted.** Written at the 1.9.0 cut
on the owner's word ("can you draft a plan to review and any SIP revisions"). It turns three inputs into
a release:
- the owner's direction of 2026-09-28 (`docs/plans/post-1-8-2-roadmap-reconciliation.md`);
- the owner's IDEA of 2026-10-01, Nostromo as the framework optimization crew
  (`docs/ideas/nostromo-framework-optimization-crew.md`);
- the owner's rulings on that IDEA the same day (§2 below).

The design it builds on is the Campaign SIP's revision 2 (`sips/proposed/SIP-Campaign-Orchestration.md`).
That SIP is proposed, and this plan adopts only after it is accepted (§6, step 1).

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

### 3.1 The headline: Campaign (the SIP's revision 2)

The Campaign SIP is revised to the two-loop direction: an objective envelope, a pure continuation
policy, and a campaign that evolves one app. The plan sequences its parts. The design is the SIP's.

| part | issue | required for | what it is |
|---|---|---|---|
| **the campaign object** | #1799 | first campaign | model, registry (memory and Postgres), `Cycle.campaign_id`, lifecycle, `/api/v1/campaigns` and the CLI, every control operation audited (SIP §15–§17) |
| **the continuation policy and the limits** | #1800 | first campaign | the pure decision at the completion boundary (SIP §10), reading `CycleAssessment`; each limit's action, pause or stop, and who resumes (SIP §9.5) |
| **the brownfield cycle** | #1705 | first campaign | a cycle starts from the previous accepted tree plus a change request; the manifest moves by a delta the gates check; a failed increment leaves the baseline untouched |
| **accumulated acceptance** | #1707, #1796 | first campaign | every earlier increment's acceptance still passes, **including each declared page rendering its view in a browser** (#1796); **each criterion the increment adds has a test that fails on the baseline for the intended reason**, through the app's public surface (SIP §8.1) |
| **the prior-cycle brief** | #1692 | first campaign | a repair or retry cycle is told what the cycle before it did |
| **the increment proposal, on the leash** | #1706, #1708 | first campaign | §3.2 |
| **the supervision interface** | #1801 | first campaign | the supervisor role, revision requests, rulings bound to the proposal version and the accepted tree, audit, events (§3.4) |
| **the box lease** | #1802 | first campaign | one owner of the Spark at a time, enforced at every launch (§3.2) |
| **recovery** | #1803 | first campaign | restart, duplicate completion, repeated ruling, interrupted promotion, abort. Each guarantee is verified by a fault-injected diagnostic (SIP §12a) |
| **the calibration cycle** | #1709 | first campaign | every campaign opens with group_run built from scratch: the yardstick for greenfield behaviour |
| **the brownfield reference scenario** | #1804 | shakeout | a fixed baseline and change request: the yardstick for proposal writing, scoped repair and accumulated acceptance (SIP §11a) |
| **the evidence package and the morning digest** | #1710 | shakeout | write-once campaign records, readable without the deploy that made them, with every failure under the failure-attribution registry's vocabulary (§3.7); the digest the owner reads |
| **campaign and deploy tags on Prefect runs** | #1728 | cut | with #1720's deploy records |
| **the request-profile taxonomy** | #316 | first campaign | a continuation that names the next cycle's profile needs one coherent namespace |

### 3.2 The increment proposal on the short leash (#1706, #1708)

**The proposal.** Between two cycles, the strategy role authors a **change request** within the
objective's allowed scope:
- a PRD delta, a manifest delta, and the increment's acceptance criteria;
- a statement of what the increment changes and what it must not break.

Its inputs are the objective, the accepted app (its manifest and its accumulated acceptance), the
campaign's evidence so far, the prior-cycle brief (#1692), and any backlog the owner seeded. Rails from
#1706: an out-of-scope proposal is refused, not trimmed; a proposal that would break accumulated
acceptance is not a candidate.

**The leash.**
- **Every proposal is gated in 2.0.** None builds without the supervisor's ruling on its exact version:
  approve, request revision, or reject, with a reason (#1801). There is no auto-approval tier in 2.0.
- **A ruling that does not come stops the campaign, not the leash.** If no ruling arrives within the
  checkpoint's declared bound, the campaign pauses (#1708: "no unbounded wait") and the digest says why.
  It never proceeds unapproved.
- **The owner is the fallback approver.** When the crew is not commissioned or not available, the
  owner rules through the same API.

**The checkpoint and the box (ruling 2; #1802).** SquadOps records one owner of the Spark at a time, as a
lease held by the squad or by the supervisor. The checkpoint runs in phases (SIP §9.3):
1. **Completion:** the cycle ends at `CycleCompletion`, and its participants are released.
2. **Proposing:** the strategy role writes the proposal. This is squad inference, so the squad holds the
   box.
3. **Handoff:** the lease passes to the supervisor, audited, with an expiry.
4. **Review:** the crew may run inference on the box (its operating model §36) and posts its ruling. A
   revision request returns to proposing.
5. **Return:** the supervisor releases the lease, its models unloaded.
6. **Launch.**

**Every** cycle launch on the box refuses while the supervisor holds the lease, and on a box that is not
quiet (a model resident that the squad's deploy did not load). That covers campaign, CLI and driver
launches, so no other path launches beside the crew. An expired lease reverts only if the box is quiet.
Otherwise the campaign escalates. 1.8.2's chain introduced the quiet-box check driver-side; 2.0 makes it
the framework's. SquadOps reads its own lease and the box's resident models, never the crew's files.

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
| create, start, inspect, pause, abort a campaign; post a checkpoint ruling bound to a proposal version and the accepted tree | `/api/v1/campaigns` (the route-lane standard, `docs/architecture/api-route-lanes.md`) | none: new with the campaign object (#1799) and the interface (#1801) |
| acquire and release the box lease | the same resource, enforced at every cycle launch | none: new (#1802) |
| cancel a stalled run | the existing cancel path | exists (#1683, #1700) |
| an identity for the crew, least privilege | Keycloak roles (SIP-0062) | a new service identity and role. The network path from cloud roles to the runtime API is a security design the owner reviews; its specifics stay out of the public record |
| an audit record for every control operation: actor, reason, target, idempotency key, outcome | `AuditPort` (`src/squadops/ports/audit.py`) | exists; whether its events carry a reason and an idempotency key is unverified |
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
| **Verification Yield and Test Value** (`sips/proposed/SIP-Verification-Yield.md`, new) | no. It overlaps `SIP-Test-First-Verification.md` (proposed in August, not built), which is its mechanism for the squad's own tests | **each criterion an increment adds has a test that fails on its baseline for the intended reason** (Campaign SIP §8.1); preservation tests may pass on both. Without it, accumulated acceptance is only as strong as its weakest, never-failing test | the stub-based red gate for greenfield cycles; risk-first qa instructions (an outer-loop experiment); the audit, fault corpus and deletion experiment on the framework's own suite (crew work); verification-cost reporting |
| **Cross-Cycle Memory, the v4 draft** (`docs/ideas/cross-cycle-memory-v4-draft.md`) | **yes**: it is a later draft of `SIP-Cross-Cycle-Memory.md`, folded in as revision 3 (§5a) | **one line:** the evidence package records failures under the failure-attribution registry's vocabulary, so 2.2 mines campaigns without reconstructing them | all of it. v2.2 as ruled, with the empty recall rail in v2.1. Revision 3 proposes that only owner-approved patterns inject into counted cycles |

---

## 4. The verification story

**What the release claims, and how each claim is read:**

| claim | read from | not a substitute for it |
|---|---|---|
| the app evolves: two or more increments accepted on one tree, earlier increments still passing | the evidence package; accumulated acceptance per increment | a cycle's own verdict |
| the strategy role's proposals hold up | the proposal ledger: rulings, reasons and outcomes | a count of proposals |
| each criterion an increment adds is guarded by a test that can fail | the ledger's per-criterion baseline results (Campaign SIP §8.1) | a passing suite |
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

**32 open issues on 2026-10-01, after rev 2**, each placed once. These are the 26 open after #1794 closed
(PR #1797), plus the 6 filed from the review:
- **The headline (17):** #1705, #1706, #1707, #1708, #1709, #1710, #1711, #1692, #316, #1728, #1796, and
  #1799–#1804, filed from the review: the campaign object, the continuation policy and limits, the
  supervision interface, the box lease, recovery, and the brownfield reference scenario.
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

## 6. Sequencing

1. **The Campaign SIP's revision 2: design review and acceptance** (CLAUDE.md, *SIP System*: acceptance
   is a design commitment, made before the branch). This plan adopts after it.
2. **Decision 1, the flip,** and its prerequisites: #1788 first, so the replay's Next.js empties can be
   explained; then #1755 and #1727.
3. **Before the first campaign, in parallel where files allow:**
   - the campaign object (#1799), and the continuation policy and its limits (#1800);
   - the brownfield cycle (#1705) and the prior-cycle brief (#1692);
   - accumulated acceptance (#1707), with #1796 and the baseline check;
   - the supervision interface (#1801) and the box lease (#1802);
   - #1785, #316, and the crew's commissioning work (§3.6).
4. **The increment proposal and its leash** (#1706, #1708), with the proposal ledger.
5. **Recovery (#1803),** each guarantee with its diagnostic, with #1757. Then the calibration cycle
   (#1709), the brownfield reference scenario (#1804), and the evidence package and digest (#1710).
6. **A minimum runbook (#1711), with the recovery instructions,** before any campaign runs.
7. **A shakeout campaign:** two increments, supervised by the owner if the crew is not commissioned yet.
   It is read for seam findings, on 1.9's shakeout-loop rules. #1728 lands by here.
8. **The pre-registration** (stop for the owner), with the cut's frame (§4) made exact. Then the
   campaign set.
9. The runbook, finalized from the shakeout and the set.
10. The cut.

---

## 7. Decisions for the owner at adoption

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

## 8. What this plan does not decide

- The Campaign SIP's design: that is its revision and its review.
- The crew's operating model: commissioning order, which roles run on which models, the recorder's code.
  The crew's own repository holds that.
- `fork` (concurrent sibling cycles): the SIP defers it, so #288's window is not opened in 2.0.0.
- The IDEA's Phases B–D: repeated optimization, memory and transfer, cross-domain.

## 9. Revision history

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
