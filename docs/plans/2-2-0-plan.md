# 2.2.0 plan — Cross-Cycle Memory Phase 1: reviewed lessons from earlier cycles, measured before the cut

**Status: DRAFT (2026-10-06), revised 2026-10-06 and 2026-10-07, for the owner's review.**

**The first draft** was written while the 2.1 cut was being prepared: the final deploy built, its
diagnostics running, its set waiting for registration (#2090).

**The 2026-10-06 revision adopts two things:**
- **An external design review** of SIP-0110 revision 4 and of the first draft. It is now SIP-0110 revision 5:
  §0 is the normative Phase-1 contract, and §5c records the change.
- **The owner's choice of release shape B** ("go with B"): 2.2.0's cut waits for the bounded measurement
  window's finding (§3).

**The 2.1 cut's two open sections were read on 2026-10-07:**
- **the cut's findings** (§2.4) were all fixed within 2.1, and none is placed here;
- **#1964's cut readings** are in SIP-0110 §5b. The whole 2.1 line returned no proposal.

**The 2026-10-07 revision re-scopes the plan for SIP-0110 revision 6** (the owner: "this is cross cycle memory; not
cross campaign memory"). Revision 5 had narrowed Phase 1 to campaigns. Revision 6 restores the cycle as its unit:
- every eligible cycle is observed, inside a campaign or not;
- memory is supplied at plan writing, build authoring, repair and proposal writing;
- the snapshot is pinned per standalone cycle or per campaign;
- counted regression rolls declare memory disabled.

The proposal behavior stays the first measured target. Re-scoped: §2.1's slices, §2.2's interaction with the auto tier,
§2.5, §3's steps, the cut's criteria, and §4's D1, D7 and D8. New: §4's D11 and D12.

**Added the same day, at the owner's request** ("yes, add those three"), after the owner asked what cross-cycle memory
produces in the quality of the application the squad builds:
- build authoring (`development.develop`, `qa.test`, `builder.assemble`) as a fourth seam, inert until approved;
- the app-build indicators recorded beside each exposure, observed and never gating;
- "What 2.2 does not claim", below.

**Added later the same day, at the owner's request** ("yes, add the Postgres decision to 2111 and file the volume
issue"), after the owner asked how agent memory and the squad's project memory work:
- **D13:** Phase 1's records are stored in Postgres beside the cycle registry, not in SIP-042's per-agent LanceDB store;
- **#2112**, placed in §2.3: three agents have no volume for their own store;
- corrections from the owner's review request: the repair seam is composed at runtime by the correction runner, not by
  the plan composer (§2.1), and four places in SIP-0110 §0 still written for one seam or one unit (its §5d).

**And at the owner's request on the review** ("yes, make both changes in 2111"), after the owner asked "who better to
determine the lesson than the AI auditing everything":
- **D14:** a failure-shape sorter for each test runner and a repeat report, in slice 3, so that a build mistake
  repeated across cycles can be seen;
- **D15:** a frontier-model auditor drafts each lesson from the recorded evidence. Each draft is frozen, replay-checked
  and approved by the owner before any task is given it.

**And nine changes from review feedback the owner supplied before adoption** ("yes, add all nine to 2111"), recorded in
SIP-0110 §5d:
1. the cut names the next build-side experiment, or records that no build-side target recurred and when that is read
   again, and keeps three results apart (below, §3);
2. the application-quality dependency is corrected: Outcome Evaluation's scenarios, not #557, #949 and #950 (below);
3. slice 2 reads temporal validity by evidence time, with a test for two units running at once (§2.1);
4. every activated lesson gets a disposition at the cut (§3);
5. lessons are checked together with those supplied beside them, and the task's requirements win over any lesson
   (§2.1);
6. a failure shape is an observed signature, and the auditor substantiates the mistake (§2.1, D14);
7. when a lesson takes effect is stated exactly: never within the campaign that learned it, in 2.2 (below, D7, §2.5);
8. the window's freeze is an experiment manifest, not a rule about directories (§3, D8);
9. acceptance checks for future compatibility and for the indicators' states (§2.1).

**This revision changes prose only.**

**What 2.2 is.** An even minor, a feature release (CLAUDE.md, #281), led by one headline: **SIP-0110 Phase 1**,
the line's one change to what the squad generates (`sips/PORTFOLIO.md` Q2).

**Beside it: #1708's auto tier and escalation queue.** They change who decides a gate, not what the squad
generates. Decisions shape later application state, prompts and failures, though, so the tier's activation is
held outside the measurement window (D3). Hardening rides along.

**The question it answers:**

> **When an authoring step is supplied reviewed lessons from earlier cycles, does a named defect recur less in later
> authoring, measured by replay against today's prompt, without degrading the output? The first measured target is a
> proposal behavior. And can plan reviews be decided under a declared policy while the owner is away, escalating
> everything the policy does not cover?**

**What Phase 1 is, precisely** (SIP-0110 §0.1):
- **cross-cycle learning: a frontier-model auditor drafts each lesson from the recorded evidence, and the owner approves
  it after a replay check (D15);**
- observations are recorded from every eligible cycle, whether it stands alone or runs inside a campaign;
- new guidance never activates within the unit that is running: a standalone cycle, or a campaign with its cycles;
- the owner approves a lesson, and it reaches cycles and campaigns admitted afterwards;
- **within a campaign, a lesson learned in one of its cycles cannot reach a later cycle of the same campaign:** the
  campaign's snapshot is fixed at admission (D7). Within it, a retry's prior-cycle brief (#1692) and a returned
  proposal's note still carry what they carry. Activation within a running campaign is deferred (§2.5);
- a campaign is provenance and one consumer, not memory's scope;
- correcting the same output stays with the rungs that already exist: a re-roll's rejection context (#669), a
  repair's failure evidence, and a proposal revision's note (SIP-0109 §9.2).

**Why the first measured target is a proposal behavior.** The memory SIP was written for the plan gate. 2.1's re-read
(SIP-0110 §5b) found that gate dormant: no framing re-rolls in 36 framings, and every plan review approved. The correction
rounds failed, but each for a different reason. The only seam that showed a recurring mistake was the campaign's proposal
gate:
- **6 of 22 increment rulings were returned,** all on the 2.0 set's deploys.
- **One behavior recurred in three campaigns:** a new criterion already satisfied by the accepted application.
- **It recurred after a prompt rule (#1947),** and again after the proposer was shown the return.

**That is where Phase 1 is measured first, not what Phase 1 is** (SIP-0110 §5d). Every eligible cycle is observed, and
the plan-writing, build-authoring and repair seams are wired inert. The repeat report (D14) shows whether a target
recurs there. If one does, its lesson is drafted, approved, supplied and measured. The headline is a measurement, not an
expected win.

**The corpus is small.** The proposal behavior has about three independent historical cases, none captured before
authoring, and the 2.1 line added none. The test corpus is built by the 2.2 line's own cycles and campaigns, and
**"inconclusive" is a likely and legitimate finding** (SIP-0110 §0.13).

**What 2.2 does not claim: an improvement in the application the squad builds.** Its finding is about one authoring
behavior's recurrence, measured by replay. The proposal behavior decides what is built next, not how well it is built.
- **The app-build indicators recorded during the window are observation:** correction rounds, rounds to green and
  acceptance beside each exposure (SIP-0110 §0.10). They never gate Phase 1 (§9).
- **The counted regression rolls run with memory disabled** (D12), so the release's yardstick of the built application
  is unchanged by design.
- **The builds leave little to learn from today.** The 2.1 counted set passed 4 of 4 with one correction round across
  the set, and the cut's four failed rounds were four different defects (SIP-0110 §5b). The repeat report (D14) is
  what tells whether that still holds over the 2.2 line.

**Three results, kept apart** (SIP-0110 §0.13):
- **authoring improvement:** a mistake's absence in authored output at a seam. 2.2 measures this, for one target;
- **delivery reliability:** correction rounds, rounds to green and acceptance. 2.2 observes this;
- **application quality:** what the built application does. 2.2 does not read this.

**What each claim needs:**
- **a delivery-reliability claim** (fewer repeated build failures, less repair effort, lower delivery cost) needs a
  build-side target that recurs, an approved lesson, and a comparison with memory on and off at the build seams, read
  from the replay and the app-build indicators. It waits for no later feature;
- **an application-quality claim** needs Outcome Evaluation's independent outcome scenarios: its instruments are placed
  in 2.3 (reporting only) and its feature half in 2.4 (`SIP-Outcome-Evaluation`);
- #557, #949 and #950 are later judgment and decision-record features (the post-retest review, feedback-scoped framing
  revision, the plan-gate review packet). They follow Outcome Evaluation, and no build-side experiment depends on them.

**The next step toward better builds is named at the cut.** The cut record names the next build-side experiment: its
owner, the evidence that triggers it (the repeat report), its comparison, its quality checks and its release placement.
If no build-side target recurred, the record says so and names when the question is read again (§3, step 9).

---

## 1. The open issues, every one placed

26 issues are open on 2026-10-07, counting the four Phase-1 slices (#2096, #2105–#2107) and #2112. #1964 closed with
#2097.

| where | count | issues |
|---|---|---|
| **2.2: the headline** | 4 | #2105 (slice 1: capture and the source-case inspection), #2106 (slice 2: the replay), #2096 (slice 3: the mechanism), #2107 (slice 4: the first lesson and the measurement window) |
| **2.2: beside it** | 1 | #1708's remainder: the auto tier and the escalation queue (placed 2026-10-03, 2.0 plan rev 9 §5a.5; kept 2026-10-04, Q2) |
| **2.2: hardening, placed by the owner during the 2.1 line** | 3 | #2079 (the realm's admin password), #2082 (two console test files depend on their order), #2083 (the realm sync never applies a service account's roles) |
| **2.2: hardening, filed at the owner's request on 2026-10-07** | 1 | #2112 (three agents have no volume for their own store). Its fix is a compose change, built only on the owner's OK (§2.3) |
| **2.1's, read at its cut** | 2 | #1964 closed with #2097 (the cut's readings are SIP-0110 §5b's last part). #1911 and #1469 carry, each waiting on its evidence: #1911 on its replay of #1788's bundles, and #1469 on a failing build of a second module shape (the cut window had none) |
| **2.3** | 6 | #316 (the owner, 2026-10-06: "2.3 is fine just let's not forget about it"), #1976, #1977, #1992, #1993, #1994 |
| **2.3, recommended here** (§4, D6) | 1 | #2062 (hoisting #1985's deferred imports: 606 import sites, a structural change for the stabilization line, next to #1992's move) |
| **2.4 or later** | 4 | #1966, #557, #949, #950 (they follow Outcome Evaluation, Q2) |
| **2.6** | 1 | #1978 |
| **the crew's** | 2 | #1756, #1965 |
| **rides any release** | 1 | #1039 |

---

## 2. The work

### 2.1 The headline: SIP-0110 Phase 1, in four slices

**Built to SIP-0110 §0, revision 6.** Every part ships inert until the owner approves a pattern. Only an approved
revision in the running unit's pinned snapshot is supplied (§0.6–§0.7), and counted regression rolls declare memory
disabled. So building the parts does not move the regression baseline.

| slice | what | the seam that owns it | size | deploy |
|---|---|---|---|---|
| 1, #2105 | the source-case inspection, then an `AuthoringReplayEnvelope` captured immediately before each consuming seam's authoring, complete beyond #1756's 10,000-character cut (§0.11): proposal writing first, then plan writing, build authoring and repair | the proposal handler's input assembly (`capabilities/handlers/planning/proposal.py`); the plan-authoring and build-authoring inputs' assembly (`cycles/task_plan.py`) and the build handlers (`capabilities/handlers/cycle/develop.py`, `qa_test.py`, `builder.py`); the repair inputs' assembly, at runtime, by the correction runner (`adapters/cycles/correction_repair.py`); the vault for storage | **L** (M in revision 5: one seam, now four) | yes |
| 2, #2106 | the authoring replay: three arms over captured envelopes at any seam, validated first on proposals; temporal validity read by evidence time, not admission time, with a test for two units running at once; counterfactual replays reported apart from prospective claims; isolation from production memory; one fixed rubric per target; the combined replay of lessons supplied together (§0.6, §0.11–§0.12) | `scripts/dev/`, beside the increment replay (#1959) | M | no |
| 3, #2096 | the mechanism (§0.2–§0.10), observing every eligible cycle and supplying four seams, with the failure-shape sorter and the repeat report (D14). Its parts are listed below | see the parts | L, larger than revision 5's | yes |
| 4, #2107 | the lesson for the one supported target behavior, drafted by the auditor on development cases and replay-checked, with any lessons supplied beside it, before the owner approves it (D15); the pre-registration, which fixes the primary target; the window; the finding (§0.4, §0.6, §0.12–§0.13) | the store (D13) for the drafted revision; `docs/plans/` for the pre-registration | M, plus the window's box time | yes |

**Slice 3's parts, each with the seam that owns it:**
- observations, pattern revisions, approvals and exposures, in `src/squadops/memory/models.py`;
- drafted revisions, each with its drafter's model and version and the observations it cites, and on each approval the
  replay check it was given (D15);
- **three idempotent projections,** each from its authoritative record (SIP-0110 §0.3):
  - rejected plans, from the cycle's gate decisions and their `rejection_record` (the cycle registry);
  - failed correction rounds, from `run_loop_summaries` (the correction loop);
  - returned proposals, from the campaign control log (the campaign domain);
- **the failure-shape sorter (D14):** each runner's table of its own failure messages and the failure shape each
  identifies: an observed signature, never a cause. It extends the per-runner tables the test runner already keeps
  (`capabilities/handlers/test_runner.py`: `_VITEST_SUITE_BROKEN_MARKERS`, `_OWN_FRAME_SHAPES`), and never maps a shape
  to an attribution class (SIP-0108 §4.2). The correction-round projection applies it to each `failed_detail` entry. A
  message no row matches is `unclassified`;
- **the repeat report (D14):** repeated shapes and recurring target behaviors, kept apart and counted by independent
  cycles (a retry and the cycle it retries count once). A target behavior counts only where the auditor substantiated
  it from the round's artifacts; a case they do not settle stays `unclassified`. The auditor drafts from it, and it is
  read at slice 3's deploy, at the pre-registration and at the cut;
- **the eligibility rule:** fault-injected diagnostics, environment-attributed failures and replays produce no
  observation. The projections run beside execution, so a failure never changes a cycle;
- the classification-disposition rail on proposal returns (D2), with its SIP-0109 amendment. Rejected plans and failed
  rounds take their source's class or `unclassified`, with no new rail;
- **the snapshot pinned per unit:** at a standalone cycle's creation, and at a campaign's admission;
- **the memory-disabled declaration** on the cycle, with the verification-set driver writing it on every counted roll
  (`scripts/dev/verification_set_driver.py`, D12);
- **the store, in Postgres beside the cycle registry (D13):** a port for the four records, an in-memory adapter for
  tests and a Postgres adapter in a deploy, selected as the cycle registry is (`adapters/cycles/factory.py`), with its
  migration in `infra/migrations/`. It is not SIP-042's per-agent LanceDB store;
- the recall policy behind `FailurePatternRecallPort` (`src/squadops/ports/memory/recall.py`, #2058). `RecallQuery`
  carries only the project and the task type today (`src/squadops/memory/recall.py`), and gains the snapshot and the
  applicability inputs;
- **injection at four seams,** each declared on the task type's context-assembly contract
  (`capabilities/context_assembly.py`) and each in its own slot:
  - the six plan-authoring types, through #2058's call site;
  - the three build-authoring types (`development.develop`, `qa.test`, `builder.assemble`), through the same
    plan-time composer (`cycles/task_plan.py`), in a slot apart from a retry's prior-cycle brief (#1692);
  - the four repair types. Their envelopes are composed at runtime by the correction runner
    (`adapters/cycles/correction_repair.py`), not by the plan composer, so the run's pinned snapshot is carried to it.
    Today the recall is asked once, when the run is provisioned (`adapters/cycles/run_provisioning.py`);
  - `strategy.propose_increment`, through the plan composer;
- per-exposure assessment;
- **the app-build indicators beside each exposure,** `disabled` ones included: the implementation run's correction
  rounds, rounds to green and acceptance, read from `run_loop_summaries` and the run's verdict or the increment's
  ruling (SIP-0110 §0.10). Observed only. **Counted once per distinct build run,** with each exposure's build state:
  built, no downstream build, pending, or evidence missing, none of the last three read as a failure;
- approval and revocation, **with the overlap and conflict check** against the approved lessons that would be supplied
  together, and the slot's statement that the task's requirements and the manifest take precedence over any lesson;
- **acceptance checks for future compatibility** (SIP-0110 §0.15): `agent_id` stays apart from the role, a record with
  no cycle needs no fabricated cycle id, and the recall policy works outside the cycle executor. They build no duty,
  ambient or organization memory.

**Renamed when touched:** three docstrings and a comment name the draft (`SIP-Cross-Cycle-Memory §5`):
- `src/squadops/memory/recall.py`;
- `src/squadops/ports/memory/recall.py`;
- `src/squadops/cycles/task_plan.py`;
- `adapters/cycles/run_provisioning.py`.

They are left until a slice touches them, so that the plan's PRs stay prose only.

**Slice 1 comes first,** for two reasons:
- **The inspection may show the information was on screen.** Version 2's return said "the manifest above already
  declares capacity", so the failure may be reasoning, not access. That changes what the lesson should say. An
  evidence-access gap, if found, is fixed as a separate change, held identical across the arms.
- **Every campaign after the capture ships adds faithful cases** to the corpus the window needs.

**Within slice 1, the proposal seam's capture lands first,** because the first measured target is there. Plan writing,
build authoring and repair follow in the same slice. Every cycle after they ship adds faithful cases at those seams too.
A build-authoring prompt carries the accepted tree, so its envelope references files by hash rather than copying them
(SIP-0110 §0.11: "contains, or immutably references").

### 2.2 Beside it: #1708's auto tier and escalation queue

**The authority comes from a declared policy,** settled in a SIP-0109 amendment. Thirty-six approvals in thirty-six
plan reviews do not show that review can be removed: the same evidence shows those reviews answering design
questions. Historical approval rates inform the policy; they never grant authority. An automatic decision needs:
- the gate kind and action the policy permits;
- the objective's and resources' bounds;
- the evidence it requires;
- no unresolved owner or product decision, unless an authoritative decision already resolves it;
- explicit escalation conditions.

The decider is recorded on the gate decision.

**2.2's tier covers plan reviews only (D3, D4).** #1995's typed link from each PRD-delta item to what carries it is
necessary for proposal auto-approval and not sufficient. Proposal auto-approval would also need checks for:
- unsupported added scope;
- omitted obligations;
- already-satisfied criteria;
- exact accepted-state references;
- evidence that the stated behavior is carried by the artifacts;
- an explicit "cannot establish" that escalates.

Those checks do not exist, so proposal rulings stay with the supervisor in 2.2. After any automation, an assessed
sample or holdout stays independent, and auto-approved, unassessed work is never memory feedback.

**The tier also decides what memory observes** (SIP-0110 revision 6). Rejected plans are one of memory's three
sources, and a plan the tier approves is never observed as a rejection. So an active tier changes the plan-review
corpus. This is a second reason its activation follows the window (D3).

**The escalation queue's contract,** designed in the same amendment:
- an escalation's identity is tied to the objective, campaign, gate, proposal revision and accepted baseline;
- its states are pending, resolved, expired, cancelled and superseded;
- creation and resolution are idempotent, and the digest's delivery survives a restart;
- a stale approval never authorizes a changed proposal;
- the campaign continues only with independently eligible work, and work that depends on a parked increment waits;
- repeated escalation, reproposal, retries and resources are bounded;
- a campaign whose every available increment needs the owner ends with completed and unresolved work kept distinct;
- the answer to an owner's late response, after the campaign closed, is defined;
- silence is never approval, and a parked problem is never regenerated in a loop.

**The purity boundary** (SIP-0110 §7, §0.8): the continuation decision never queries mutable memory. It may consume
ordinary evidence from memory-informed proposals.

### 2.3 Hardening placed by the owner

| issue | the defect | the fix | size | deploy |
|---|---|---|---|---|
| #2079 | the realm's `squadops-admin` signs in with the password every realm file commits; #2006 left the realm's human users out | generate it per deploy, as #2006 does for service credentials, and rotate it with the same runbook (`docs/ops/credential_rotation.md`) | S | yes |
| #2082 | `test_cycle_command_handlers.py` stubs `auth_bff` in `sys.modules`, and `test_auth_bff.py` imports the real one, so the pair fails 5 tests in one order | one fixture that owns the module for both files and restores its prior state | S | no |
| #2083 | the realm sync's `partialImport` leaves out `users`, so a service account added after a realm was created never gets its realm roles | apply each service account's roles from the export, repeatably, without importing human users | S | yes |
| #2112 | nat, eve and han mount no volume at `/app/data/memory_db`, so their own store (console chat today) is lost when the container is recreated | a named volume on each, as the other five agents have. **A compose change: built only on the owner's OK** | S | yes |

Each issue carries its acceptance criteria (posted 2026-10-06).

**`docker-compose.yml`:** the owner's exception was for the 2.1 line (2.1 plan §5 ruling 13). A 2.2 item that needs a
compose change asks first.

### 2.4 From the 2.1 cut (open)

The cut found four defects, and each was fixed within 2.1, so none is placed here:
- #2094: a refused run could not leave `queued`;
- #2099: the rotation's `.env` copy was not ignored by git;
- #2101: the retry rows were asked after the blocked rows (SIP-0109 §24bh);
- #2103: LangFuse's health check.

The counted set passed 4 of 4 (the 2.1 pre-registration §10).

### 2.5 Not in 2.2 (ruled)

- **#557, #949 and #950** follow Outcome Evaluation's scenarios, in 2.4 or later (Q2).
- **The recurring design questions** (7 of 8 unresolved questions asked how the runs list is ordered or paged) are
  decision records. They are the Design Decision Register's payload, and arrive with its home, #950 (SIP-0110 §5b,
  Q12).
- **Phase 2**, semantic ranking, autonomous promotion and the other deferrals of SIP-0110 §0.14 stay unplaced. Phase 2
  begins only on the owner's ruling after the window's finding.
- **A built-in auditor** that drafts lessons inside the product after each cycle. In 2.2 the outer loop's model drafts
  them (D15).
- **Phase 1.5 is not a separate part any more.** SIP-0110 revision 6 folds the correction lane into Phase 1: its rounds
  are observed, and its repair seam is wired inert, in 2.2. **A lesson for a plan-review or correction-round target**
  is drafted in 2.2 only if the repeat report shows one recurring across independent cycles. That is read at the
  pre-registration and again at the cut (SIP-0110 §0.4, D11, D14).
- **Activation within a running campaign.** A lesson learned in a campaign reaches later units only. Activating one
  mid-campaign would need an approval during an unattended run and would break the comparison of whole campaigns
  (SIP-0110 §0.1, §0.14).
- **Proposal auto-approval** (§2.2).
- **#316** is 2.3's (2.1 plan §5 ruling 14).

---

## 3. Sequencing (shape B: the cut waits for the window)

1. **Inherit the 2.1 cut's findings** (§2.4). They are live evidence.
2. **Rule before building:**
   - this plan, with SIP-0110 revisions 5 and 6 (D5, D11–D15);
   - the SIP-0109 amendments for D2's rail and for #1708's policy and queue.
3. **Slice 1 (#2105):**
   - the source-case inspection, posted;
   - capture at the proposal seam, proven live by a byte-exact reconstruction of a real proposal's prompt;
   - capture at plan writing, build authoring and repair, each proven the same way on a live cycle. A repair needs a
     failed round, so a fault-injected diagnostic may prove its capture: capture is not observation, and the
     diagnostic's failure is never observed (SIP-0110 §0.3).
4. **Hardening:**
   - #2082 (tooling, no deploy);
   - then #2079 and #2083 together, since both are the realm's, with a rebuild and the regression pair;
   - #2112 rides that rebuild if the owner has OK'd its compose change.
5. **Slice 3 (#2096),** inert, with the acceptance matrix (SIP-0110 §0.15) held on a controlled corpus. A rebuild
   and the regression pair follow. Nothing is supplied, because nothing is approved.
   - **The regression pair is the first live proof that a standalone cycle is observed.** It declares memory disabled,
     its prompts are byte-identical at every seam, and its rejected plans and failed rounds, if any, are recorded.
   - **A campaign proves the campaign's sources,** with the same inertness.
   - **From this deploy on, every eligible cycle the line runs adds observations:** regression pairs, diagnostics,
     shakeouts and campaigns.
   - **The repeat report is read first here,** over every round recorded with `failed_detail` since #2028 and #2086
     began recording it.
6. **Slice 2 (#2106):** the replay, proven end to end on the historical cases, which are exploratory and diagnostic
   only.
7. **#1708** is built, and its activation is held until the window closes (D3).
8. **Slice 4 (#2107):** the auditor drafts the first lesson on development cases and it is replay-checked (D15), then
   the pre-registration with its budget cap and stopping rule (D8), which reads the repeat report (D14). Then **the
   window opens**:
   - the deploy is frozen;
   - campaigns build the proposal corpus, and every cycle adds to the plan-review and correction-round corpus;
   - the owner approves the lesson, with its replay check, at a campaign boundary;
   - the replay compares the arms;
   - every exposure records its build's indicators (correction rounds, rounds to green, acceptance), observed only;
   - **an experiment manifest is recorded as the window opens** (SIP-0110 §0.12), each input by version or hash: the
     deployed artifact, the prompts and fragments, the configuration (`config/`, the request profiles, the squad
     profile as stored in Postgres), the deploy's model settings, the policies, the evaluator (the replay tool and its
     rubric in `scripts/dev/`), the PRDs (`examples/`), the referenced evidence, and the store's lessons and
     approvals. The framework-drift check (`verification_set_driver.py`, `src/` and `adapters/` only) covers part of
     it;
   - **no rebuild during the window.** A merge that changes an input the manifest lists waits for the window to close,
     so that the cut tags the tree the window measured. Any other merge, prose or code, is free. A change that must
     land inside it (an instrument fix, a revocation) restarts the window under a new manifest, or is recorded as an
     intervention that sets the affected measurements apart;
   - 2.3's work waits on branches: its refactors need rebuild pairs, and the box is held.
9. **The finding** is recorded in SIP-0110: instrument validity first, then benefit, no benefit, harm or
   inconclusive. With it:
   - whether a plan-review or correction-round target recurred: the repeat report's repeated shapes and substantiated
     target behaviors (D11, D14);
   - the app-build indicators, as observation, with no claim about the built application;
   - **each activated lesson's disposition:** retained within its tested applicability, disabled, revised for
     retesting, or continued in an explicitly bounded experiment. Harm invokes the revocation procedure (D9).
     Inconclusive may ship the mechanism, but never makes an activation permanent by default;
   - **the next build-side experiment:** its owner, its triggering evidence, its comparison, its quality checks and its
     release placement, or the finding that no build-side target recurred and when that is read again;
   - the owner's disposition for Phase 2.

   "Inconclusive" at the budget cap is a valid finding, and the cut goes ahead on it.
10. **#1708's plan-review tier is activated** under its declared policy, and validated by the cut's shakeout.
11. **The cut:**
    - a regression set on both stacks, with memory disabled (D12);
    - one campaign shakeout;
    - the release cut procedure (CLAUDE.md);
    - a record that states separately the mechanism's correctness, the experiment's validity and result, the
      activated patterns with their applicability and dispositions, the app-build indicators, the repeat report, the
      next build-side experiment, the auto-gate scope enabled, and the owner's disposition for the next phase.

### The cut's criteria

- **The mechanism:** SIP-0110 §0.15's acceptance matrix holds. At every consuming seam, an empty, unapproved or
  disabled snapshot leaves the rendered prompt byte-identical. Standalone cycles and a campaign's cycles have both
  recorded observations live.
- **The instrument:** valid, by #2106's validity check, and the experiment manifest held, or each change to it
  recorded.
- **The finding:** recorded, whichever of the four. **A benefit is not a cut criterion.** The app-build indicators are
  reported beside it, as observation.
- **Every activated lesson has a disposition,** and the next build-side experiment is named, or its absence recorded
  with the next review point.
- **#1708:** its tier escalates every case its policy does not cover, read in the shakeout.
- **The regression set:** passes, under its own pre-registration, with memory disabled.

---

## 4. Decisions for the owner

Each has a recommendation. None is built before it is ruled.

| # | decision | recommendation | why |
|---|---|---|---|
| — | **the release shape** | **decided: B** (the owner, 2026-10-06: "go with B") | the cut waits for the bounded window's finding |
| — | **memory's unit** | **the cycle, not the campaign** (the owner, 2026-10-07: "this is cross cycle memory; not cross campaign memory") | SIP-0110 revision 6 (§5d). D11 and D12 are its shape, for ruling |
| D1 | **the instrument** | **authoring replay, conditional on slice 1's verified pre-authoring fidelity at each seam, validated first on proposals** | replay runs identical inputs under each arm. The boundary is immediately before authoring, never "at the ruling": later rulings and notes reveal what the author did not have |
| D2 | **a return's classification disposition** | **a `ProposalClassification` class or an explicit `unclassified` with rationale; a return with neither is refused** (a SIP-0109 rail and amendment) | 3 of the 6 historical returns carry their class only in prose. A novel defect must stay returnable without being forced into a wrong class |
| D3 | **memory and the auto tier, in order** | **proposal rulings stay supervised through the window. #1708's tier covers plan reviews, under its declared policy, activated after the window** | the window's evidence comes from the supervisor's classified rulings. A tier active during it would change the cases it measures |
| D4 | **#1995's typed link** | **a prerequisite for proposal auto-approval, never its authorization. No proposal auto-approval in 2.2** | §2.2's further checks do not exist |
| D5 | **this plan** | adopt as revised, or amend | — |
| D6 | **#2062** | **2.3,** with the structure batch | 606 import sites move for no behaviour, and #1992's move rewrites many of the same imports |
| D7 | **snapshot and activation semantics** | **as SIP-0110 §0.7:** pinned at the unit's admission, which is a standalone cycle's creation or a campaign's admission; a campaign's cycles use its snapshot; changes reach units admitted later; concurrent units keep their own. **So a lesson learned in a campaign never reaches a later cycle of that campaign;** activation within a running campaign is deferred (SIP-0110 §0.1) | otherwise a confidence or status update changes the next prompt mid-cycle or mid-campaign, and the comparison moves under itself |
| D8 | **the experiment's arms and the window's bound** | **as SIP-0110 §0.12–§0.13,** with the budget cap set in the pre-registration. The primary target is fixed there, from the seam with the most independent cases of one target behavior: the proposal behavior, on today's evidence. A proposed default: about five campaigns, with "inconclusive" at the cap. The window is held by an experiment manifest of every input, not by which directories may change | a bounded window cannot hold the release open indefinitely. Standalone cycles add plan-review and correction-round observations at no cost to the cap |
| D9 | **emergency revocation** | **as SIP-0110 §0.7:** halt or restart the affected work under a new snapshot, and invalidate or set apart the affected measurements | harmful guidance must be removable without silently changing a counted intervention |
| D10 | **the escalation queue's resumption** | **designed in #1708's SIP-0109 amendment against §2.2's contract** | it is SIP-0109's surface (SIP-0110 §0.14) |
| D11 | **what is observed, and where memory is supplied** | **every eligible cycle, standalone or in a campaign, from three sources (rejected plans, failed correction rounds, returned proposals); supplied at plan writing, build authoring, repair and proposal writing, each inert until a lesson is approved. A plan-review or correction-round lesson is drafted in 2.2 only if the repeat report (D14) shows one target recurring across independent cycles, read at the pre-registration and at the cut. Every exposure records its build's indicators, observed only** | memory's unit is the cycle. Observing every cycle costs a projection beside execution. Supplying only where a lesson is approved keeps the measurement clean. Build authoring is where a correction-round lesson reaches a later cycle before its check fails, not only after (SIP-0110 §0.9, §2) |
| D12 | **counted regression rolls and memory** | **declare memory disabled until a finding of supported benefit and the owner's ruling. Their observations are still recorded** | the regression set is the framework's yardstick. A lesson approved for plan writing would otherwise reach it and move it unannounced |
| D13 | **where Phase 1's records are stored** | **Postgres, beside the cycle registry, behind their own port** (SIP-0110 §0.8). Not SIP-042's LanceDB store | that store is created inside each agent's container and used only by console chat. Recall runs in the runtime API, which has none. Phase 1's recall is exact filtering, so it needs no embedding. The projections must be idempotent against records already in Postgres. Postgres is addressable as a service (the Embodiment Runtime's invariant 2) and is the only store in the nightly verified backup. Phase 2 chooses a similarity index when it adds ranking |
| D14 | **seeing a repeated build mistake** | **a failure-shape sorter for each test runner and a repeat report, in slice 3** (SIP-0110 §0.4). The sorter is a table of each runner's own failure messages, extending the test runner's existing per-runner tables (`capabilities/handlers/test_runner.py`), applied to every failed round's `failed_detail`, with no model in it. A shape is an observed signature, never a cause: it sits beneath the attribution and never maps to an attribution class (SIP-0108 §4.2). The auditor substantiates a target behavior from the round's artifacts, and the report keeps repeated shapes apart from recurring target behaviors, counted by independent cycles. It is read at slice 3's deploy, at the pre-registration and at the cut | a correction round is labelled only by its attribution and its failed check, and every failed round in the 2.0 and 2.1 windows failed `tests_pass`. What went wrong is only in `failed_detail`'s text, so a repeated build mistake could only be found by hand, and the build-authoring and repair seams would stay empty by design. The four rounds recorded so far each carry one message that names its defect. Added at the owner's request ("yes, make both changes in 2111") |
| D15 | **who drafts a lesson** | **a frontier-model auditor, from the recorded evidence:** the outer loop's model (the supervisor in 2.2, the crew once commissioned), never the squad's own model. It drafts between units and cites its cases. Each draft is frozen, replay-checked on development cases together with any lessons supplied beside it, and approved by the owner before any task is given it (SIP-0110 §0.4, §0.6). A built-in auditor is later | an AI auditing every failure is better placed than a person reading a sample (the owner: "who better to determine the lesson than the AI auditing everything"). The owner's direction of 2026-09-28 has frontier models improve the framework from evidence. A lesson can be wrong whoever writes it: #1947's rule was followed by the same mistake twice, so the replay check stays. Added at the owner's request ("yes, make both changes in 2111") |

---

## 5. What this plan does not decide

- **The 2.1 cut's findings** (§2.4) and **#1964's cut readings** (SIP-0110 §5b).
- **The cut's numbers:** the regression set's size, and the window's N, budget cap and minimum worthwhile effect.
  They are written as pre-registrations when their batches are built.
- **The standing authority for 2.2.** The owner's grant of 2026-10-04 covered the 2.1 line and ended at its cut. 2.2's
  authority is the owner's to give when this plan is adopted.
- **Any compose change** (§2.3).
