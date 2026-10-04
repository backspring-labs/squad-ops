# 2.0.0 — pre-registration of the campaign set (plan §4, §6 step 14)

**Status: DRAFT, NOT REGISTERED.** This is the owner's stop (plan §6 step 14). Nothing in the set has
launched. Every pin marked *read at registration* is read from the final deploy when the owner approves.
None is carried from a superseded deploy. Once registered, the cut criteria do not move: only readings
are appended, and if the deploy moves, this registration is void and re-made.

**What must be true before it can be registered:**
1. **The shakeout loop's exit rule holds:** one shakeout campaign on the registered deploy with **no
   new seam finding**.
   - **Shakeouts 1–4** (2026-10-02/03) each found the next seam defect: fourteen in all, each fixed
     between cycles.
   - **Shakeout 4** found #1897, #1898, #1902 and #1905, and **it ran the release's claim end to end:**
     a calibration, increment 1 rejected and then **accepted through its repair**, and increment 2
     accepted, with every frozen criterion (T1–T3) held and T4 discriminating. That is two accepted
     increments on one tree.
   - **Shakeout 5** (rebuild 14, `cmp_9757603322b1`): success, three accepted increments. It found #1912
     (a verification-only qa task fails whatever the model writes), fixed in #1914.
   - **Shakeout 6** (rebuild 18, `cmp_58d4e3b0a5d3`, 2026-10-03): success, three accepted increments,
     with the live-lease proof at its first gate. **It found #1938:** the proposal was told frozen
     criteria by id only, so increment 3's first proposal restated increment 2's feature. Fixed in
     #1939 (SIP-0109 §24ap), which is rebuild 19.
   - **Shakeout 7** (rebuild 19, `cmp_b3a681c4f994`): **success, three accepted increments.**
     - Its gates showed #1938 working. Increment 1's promotion froze its criteria with their statements,
       and increment 2 proposed a feature not yet built.
     - **The crew's review of this draft** (2026-10-04) traced #1938 into the kill-before-promotion
       window, and that trace found **#1943**: #1938's exception-contained lookup let a promotion's
       binding vary between attempts. A replay after a restart could then be refused, leaving the
       campaign undecided. Fixed in #1944, which is rebuild 20.
     - Its first proposal was returned for a criterion the accepted app already met (T2, the default
       case of the feature). That became the first instance of #1946.
   - **Shakeout 8** (rebuild 20, `cmp_51919765933d`): **stopped at its first increment gate for #1946.**
     The calibration was accepted. Increment 1's first proposal again carried the default case (T3, "a
     run without capacity takes a tenth join"), two of three first proposals: the proposal prompt
     never stated that a new criterion must fail on the accepted tree (§8.2). Fixed in SIP-0109 §24aq,
     which is rebuild 21.
   - **Shakeout 9** (rebuild 21, `cmp_9b1025685bea`): **found #1948 at its first increment gate.** T1
     asserted that a run created without a capacity returns no capacity key. The FastAPI stack's frozen
     models return an optional field a request left out as `null` (#1125), so a correct build would
     have failed it, and the proposer is never told the convention. Returned for revision (§3a); version
     2 was approved. Fixed in SIP-0109 §24ar, which is rebuild 22. Precondition 4's live-lease proof ran
     at this gate.
   - **Shakeout 10** (rebuild 22, `cmp_36f0d3b1e98a`, 2026-10-04 08:58–11:44 UTC) **is the exit run on
     the deploy the set registers: success, three accepted increments, and no new seam finding.** The
     exit rule holds.
     - Every proposal was approved at version 1 (capacity, then the datetime sort, then the seed
       endpoint), and no ruling was returned. Neither #1946's miss (a default-case criterion) nor
       #1948's (an absent-key observable) recurred.
     - Each increment was accepted on its first cycle, with every earlier frozen criterion held
       (T1–T4 on one tree).
     - The runtime and the six agents logged no error. The two warnings were existing guards
       working: a status code the skeleton enforcement restored (SIP-0100), and the plan-prose check
       naming a path parameter (pf-31).
     - The close-time evidence package materialized (`art_e20bc6b5b99f`).
2. **Decision 1, the SIP-0107 flip: RULED (owner, 2026-10-03, "go with your recommendation on the
   flip").** #1788's re-run explained the nine empty scoped Next.js repairs. Of its 12 samples (on
   rebuild 13; SIP-0107 §46s):
   - 9 were correct dev abstentions or disputes on qa-owned defects;
   - 2 exhausted the 12,288-token completion cap;
   - 1 was an edit.

   **The flip is merged (#1909, SIP-0107 §46s):** a repair's whole re-emission of an offered file is
   refused, typed, and retried once. Proof part 1: 0 of 120 recorded repair forms were `whole_file`.
   **Proof part 2 read (2026-10-03, SIP-0107 §46s):** the checkpoint pair on rebuild 16 had both
   stacks accepted (`cyc_559e19c582d6` 21/21; `cyc_025e085a22b1` 16/16), and no repair was refused.
3. **Who supervises is not a precondition** (SIP-0109 §24al, the owner's ruling of 2026-10-03:
   "consider me or the crew as requiring the same need to supervise. it shouldn't impact squad ops
   design"). The supervisor's seat is one seat with one ruling bound. Whoever holds it rules
   through the same interface, and each ruling records its actor.
4. **The box lease is enforced and proven on the registered deploy (#1802; the crew's review of this
   draft, 2026-10-03).** The guarantee "no launch beside a crew model" in §3 needs this. Until then,
   SIP-0109 §24l built the decisions and the reads, and nothing enforces them.
   - **Completion:**
     - the lease is persisted, with its API (`/api/v1/campaigns/{id}/lease`, `campaigns:supervise`),
       and each change is audited;
     - every enforcement point is wired: the cycle-create preflight (409 plus an audit event), the
       launcher (`launch_blocked`, re-attempted at the policy's interval, escalating after its
       count), and each run start. **A run start refuses what a launch refuses** (§24an, #1928, the
       owner's ruling of 2026-10-03, found re-reading the crew's review). It waits, queued, while
       the supervisor holds the box **or** an undeclared model is resident, up to one full lease of
       its campaign. A run outside every campaign is refused at once. Before §24an a run start read
       only the lease, so a crew model left resident when the lease returned (released or expired)
       was run beside by the framing run the ruling had just approved.
     - **Built and deployed:** #1915 (§24ai) since rebuild 16; §24an (#1931) from rebuild 18. **The set
       registers on rebuild 22**, which carries both.
   - **Deployed proof, the quiet-box half (rebuild 16, 2026-10-03 10:38–10:39 ET, `cmp_969baa78fd39`):**
     with `llama3.1:8b` resident, a CLI create was refused (409 `box_not_quiet`, with an audit
     event), and the campaign's launch went `launch_blocked`, then escalated. With the model
     unloaded and a resume, the launch proceeded.
   - **Deployed proof, the live-lease half.** Run four times, each time at a shakeout's first
     increment gate, 5 of 5 every time. Each refused create was audited (`cycle.launch_refused`,
     `denied`, in the runtime's audit sink, `data/audit/runtime-api.jsonl`):
     - **rebuild 18** (`5f46d946`, shakeout 6, `cmp_58d4e3b0a5d3`, 2026-10-03 22:05–22:09 UTC); the
       framing run started 3.6 s after the unload (`waited_s=120`);
     - **rebuild 19** (`b0c25360`, shakeout 7, `cmp_b3a681c4f994`, 2026-10-04 01:10–01:13 UTC); the
       framing run started 4.4 s after the unload (`waited_s=90`). Log:
       `var/campaigns/cmp_b3a681c4f994/proofs/1802-live-lease-proof.log`.
     - **rebuild 21** (`3f6551d8`, shakeout 9, `cmp_9b1025685bea`, 2026-10-04 08:24–08:28 UTC); the
       framing run started 4.7 s after the unload (`waited_s=90`). Log:
       `var/campaigns/cmp_9b1025685bea/proofs/1802-live-lease-proof.log`.
     - **rebuild 22, the deploy the set registers** (`b09883c9`, shakeout 10, `cmp_36f0d3b1e98a`,
       2026-10-04 09:51–09:55 UTC); the framing run started 5.0 s after the unload (`waited_s=90`).
       Log: `var/campaigns/cmp_36f0d3b1e98a/proofs/1802-live-lease-proof.log`.

       Shakeout 8 on rebuild 20 was stopped at its first gate, before the proof ran.

     An acquire needs the gate open, so the expired lease comes first:
     1. a short lease: a CLI create is refused, `supervisor_holds_the_box`;
     2. the lease left to expire with a stand-in crew model resident: a CLI create is refused,
        `box_not_quiet`;
     3. the lease re-acquired and the ruling approved while held: the framing run waits, queued;
     4. the lease released with the model still resident: the framing run keeps waiting
        (`box_not_quiet`, §24an);
     5. the model unloaded: the framing run starts.
   - **Not proven live: a campaign launch under a live lease.** It cannot arise. An acquire needs the
     increment gate open and no run in flight, and a campaign launches only when a cycle ends. It is
     held in the launcher's tests.
   - **What the check sees, stated as the guarantee's limit:**
     - **Model-only (§24l).** It reads every declared engine's resident models, not the GPU's compute
       processes, until the runtime-api is granted the GPU (a `docker-compose.yml` change, the
       owner's). A crew workload outside a declared engine is not seen.
     - **Declared per model.** A crew session on a model the deploy declares (one a squad profile
       names) reads as quiet.
     - **So the guarantee is:** no launch and no run start beside an undeclared model resident in a
       declared engine, and none while the supervisor holds the box.

5. **#1803's recovery diagnostics have run on the registered deploy, or a diagnostic's read is carried
   from an earlier deploy only where the deployed-code diff and every overlap with that diagnostic's
   path are declared here, and the owner has accepted that none changes the recovery mechanism or
   invariant** (the owner-approved change below, in the crew's narrower wording). They are run as the
   validation plan's §3 (#1807) designs them, with the harness from #1924, #1927 and #1933.
   - **First live read, rebuild 17 (2026-10-03).** The blocked legs passed 4/4 (`cmp_575115942556`).
     The increment legs (`cmp_e39d5b9c24c6`) passed the restarts at `at_proposal`,
     `awaiting_ruling`, `paused` and `building`, and the repeated ruling.
   - **What that read found:** #1929. A graceful stop was handled as a run failure, and the
     re-attach dispatched the in-flight task twice. It is fixed in #1932 (§24ao), placed in 2.0 by
     the owner.
   - **Re-run on rebuild 18** (`5f46d946`, 2026-10-03): **12 of 12.**
     - The blocked legs 4/4 (`cmp_678167dcd86a`).
     - The increment legs 8/8 (`cmp_c380058c647f`), the kill before promotion exercised.
     - #1929's two halves were seen working (`run_left_for_reattach`; `task_reply_replayed` ×2).
     - #1803 was closed on it.
   - **The registered deploy is rebuild 22.** Its deployed-code diff from rebuild 18:
     - #1938: `increment_tree.py`, `progress.py`, `proposal.py`, the proposal's request template;
     - #1943: `progress.py`;
     - #1946: the proposal's request template (v4);
     - #1948: the proposal's request template (v5), a new section template, `proposal.py`, and one
       field on the stack table (`ScaffoldStack.unset_optional_response`), read only by the proposal
       handler.

     **The commit is `b09883c9`** (deploy record `dep_bb1eadeac4e7`). Read from git, the exact
     deployed-code diff from rebuild 18 (`5f46d946`) is those six files under `src/`:
     `increment_tree.py`, `progress.py`, `proposal.py`, `scaffold.py`, and the two request templates.
     Nothing changed under `adapters/`, `infra/`, `config/`, the requirements or the Dockerfiles.
   - **The increment legs re-ran on rebuild 20** (`75a4b7b8`, `cmp_c3b60dd6889d`, 2026-10-04): **8 of 8.**
     - **What they did not reach, declared.** The kill before promotion and the duplicate completion
       both landed on an increment its cycle rejected (its catch-all route lacked the not-found view).
       So no promotion ran in either: `promotes: 0` with the accepted tree unchanged, and a repair
       continuation. The #1938/#1943 lookup runs only inside a promotion, so no restart exercised
       it. Rebuild 18's kill before promotion did promote (`promotes: 1`), but that was before the
       statements were in the binding.
     - **What holds it instead:**
       - #1944's test: a promotion whose lookup fails commits nothing, and its retry commits once;
       - **a live replay, read-only on the registered deploy.** Each applied promotion has its frozen
         statements recomputed twice from the deploy's stored data, through the runtime's own lookup,
         and compared with the binding the row committed.
         - Shakeout 7's four promotions (committed on rebuild 19): 6 criteria, each recomputed twice,
           **0 mismatches** (`var/campaigns/cmp_b3a681c4f994/proofs/1943-binding-replay-rebuild22.log`).
         - Shakeout 10's four promotions (rebuild 22): 4 criteria (T1–T4), each recomputed twice,
           **0 mismatches** (`var/campaigns/cmp_36f0d3b1e98a/proofs/1943-binding-replay.log`).
   - **The proposal-path legs re-run on each deploy that changes the proposal prompt:**
     `restart-at:at_proposal`, and `abort-in-flight`, which lands in that proposal run.
     - Rebuild 21 (`3f6551d8`, `cmp_5247f81c2ea9`): 2 of 2, for #1946.
     - Rebuild 22, for #1948: *read at registration*.
   - **The other six increment legs are carried from rebuild 20:** the restarts at `awaiting_ruling`,
     `paused` and `building`, the repeated ruling, the kill before promotion and the duplicate
     completion. This is the case the owner's "go with b" ruled on: a diff that changes only how the
     proposal prompt is rendered. Each overlap with the diff from rebuild 20 (#1946, #1948), declared:
     **none of these legs renders a proposal prompt.**
     - `awaiting_ruling` and `paused` have no run in flight.
     - The repeated ruling starts a framing run.
     - `building`, the kill before promotion and the duplicate completion run an implementation or a
       repair.
     - The stack table's new field is read only by the proposal handler.
   - **The blocked legs are carried forward from rebuild 18** (4/4, `cmp_678167dcd86a`), by the
     owner-approved change to this precondition (the owner, 2026-10-03: "go with b", and the standing
     instruction of the same evening to re-run any diagnostic a fix overlaps). Each overlap, declared:
     - `restart-at:launch_blocked` and `restart-at:escalated`: none. No proposal, promotion or replay
       runs.
     - `restart-at:calibrating` and `abort-in-flight`: both land in the calibration's framing run,
       before any promotion. A calibration's promotion carries no increment evaluation, so
       `_freeze_bundles` returns before the #1938/#1943 lookup is reached.
     - #1946 and #1948 touch none of them: a calibration's framing run renders no proposal prompt.
     - None of the diff changes the restart, re-attach, kill or abort mechanism, or the recovery
       invariant on these paths.

6. **The evidence that dies with the logs is kept** (#1710, §24ak): each run's revision forms are on
   its persisted summary and in the package. `scripts/dev/campaign_log_archive.py <campaign> --follow`
   runs beside every campaign of the set.

---

## 1. What the set measures (plan §4's claims, each with where it is read)

| claim | read from | not a substitute for it |
|---|---|---|
| the app evolves: two or more increments accepted on one tree, with earlier increments still passing | the evidence package; the per-increment evaluation's frozen bundles (`increment_evaluation`, §8.1) | a cycle's own verdict |
| the strategy role's proposals hold up | the proposal ledger (`squadops campaigns ledger`): each version, its ruling and reason, its outcome | a count of proposals |
| each criterion an increment adds is guarded by a test that can fail | the evaluation's per-criterion baseline discrimination (§8.2) | a passing suite |
| the campaign ran unattended between checkpoints | the control log: every row's actor is `squadops`, the executor, the launcher, or a ruling at a checkpoint; zero manual steps | the absence of complaints |
| the supervisor loop works | each ruling's binding, its latency (the `submit` row to the `rule` row), any `ruling_overdue` rows (§24ae) | the supervisor's report alone |
| the campaign recovers and stops predictably | every limit reached in the set taking its declared action (§9.5); the recovery diagnostics (#1803), run separately | a set in which nothing went wrong |
| greenfield building did not regress | each campaign's calibration cycle against 1.9's React counted rolls | a claim about the framework as a whole |
| the brownfield mechanisms work | the reference scenario (#1804): `reference_report.py --cycle … --proposal-cycle …` (delta framing, scoped repair, accumulated acceptance, discrimination, the rated proposal) | the calibration cycle, which exercises none of them |

---

## 2. The set (decision 3)

- **Two campaigns of three increments each** (`objective.measurement: three accepted increments`,
  `objective.target_accepted_increments: 3`), each opening with its calibration cycle.
  - **Each ends in success on row 3 when its third increment is accepted** (§24ah).
  - **Without that reader, a campaign proposed past its objective until `max_cycles`.** Shakeout 4 met
    its measurement and read `exhausted`.
- **The brownfield reference scenario runs beside each:** the build half
  (`launch_reference_increment.py`) and the proposal half (`--proposal`, rated with
  `squadops cycles rate`), between the campaigns, on the same deploy.
- **The squad:** `full-38`. **The stack:** `fullstack_fastapi_react`, as every shakeout.
- **What the sample can say:** two campaigns show the mechanisms working and stopping safely. **They
  are not a reliability rate,** and the record says so.

---

## 3. The frame (plan §4, made exact)

- **Pass:**
  - **every campaign runs to its end by its own rules:** `completed`, by its objective or a limit,
    with no owner action outside the interface;
  - **no safety guarantee is violated** in any campaign. Each is read from the control log and the
    cycle records:
    - no build without an approving ruling bound to its proposal version and accepted tree;
    - no stale or conflicting ruling honoured;
    - no ruling lost;
    - no duplicate launch (one cycle per launch intent);
    - no partial promotion (every PROMOTE row carries its `tree_ref` and bundles);
    - no launch beside a crew model: no cycle launched or run started while the supervisor holds
      the box, or while an engine holds a model the deploy record does not declare (§24an; the
      limits in precondition 4: model-only, declared per model). Read from the `launch_blocked`
      rows, the lease rows, the refusal audit events, and the runtime's `run_start_waiting_for_box`
      lines;
    - an evidence package complete at close;
  - **at least one campaign advances its app through two or more accepted increments** with every
    earlier frozen criterion passing on each.
- **Fail:** any safety guarantee violated, or no campaign reaching two accepted increments.
- **Inconclusive:** a campaign ended by a cause outside the framework, such as a box halt. It is
  re-run under 1.8.2's void rule and does not spend the budget.
- **Data, not failure:** rejected proposals, repaired or abandoned increments, and an escalation that
  the owner resolves through the interface. Each is read by its signature.
- **Interventions:**
  - each ruling is through the supervision interface, and its actor is recorded. Who supervised is
    read from the rulings, not claimed in advance (§24al);
  - any owner action outside the interface (a manual repair, a manual restart) voids that campaign's
    claim of unattended operation;
  - a `resume` naming an action on an escalation is inside the interface, and is reported per
    escalation with its cause.
- **A framework fix during the set:** nothing merges while the set is open (1.9's rule). A fix voids
  the set, and it restarts on a new deploy after a shakeout.


### 3a. The supervision policy (declared before the first launch)

**Who supervises:** Claude Code, as the owner's delegate (the owner, 2026-10-03: "I don't need to
be a supervisor of the counted set; you can do that and use good judgement"). The seat is the one
seat of SIP-0109 §24al. Each ruling's actor is the identity the delegate rules with, and this
record names the delegate. Because the supervisor also built the framework, it rules by these
criteria, declared before the first launch, and each ruling's reason cites the criterion it
applied.

- **Approve,** when all of these hold:
  - the change request stays inside the objective's `allowed_scope`;
  - each criterion is concrete and checkable against a named surface, and asserts only what the
    request states (P9);
  - the footprint is no wider than the change needs;
  - `must_not_break` names the earlier criteria the change touches.
- **Request a revision,** naming exactly what to fix, when the request:
  - is internally inconsistent (shakeout 5's v1: the observable said `CAPACITY_REACHED` and the
    delta declared `capacity_reached`);
  - states a rule in a criterion that the request itself does not state;
  - has an observable a test could not check.
- **Reject,** when the request is outside the objective's scope, or reworks an accepted increment
  without a `retires` entry.
- **Plan-gate answers** come from the PRD, the accepted manifest, or an earlier answer (§24ad).
  When none of these settles a question, the answer is the narrowest one consistent with them, and
  the ruling records it as a judgement.
- **Never:**
  - edit a proposal (§9.2);
  - rule to steer a measurement or a prediction;
  - act outside the interface.
- **Classify** a returned or rejected proposal (§9.4) when the cause is one of §9.4's classes.

---

## 4. The predictions: each names a mechanism and how it is falsified

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | an increment's framing runs only the delta's plan tasks: the footprint, criteria and frozen indexes | the framing run's task ledger and plan | a plan task outside the change request's footprint |
| P2 | every new criterion's file fails on the accepted tree and passes on the candidate (§8.2) | the evaluation's `discriminations` | a criterion met without a discriminating test |
| P3 | every criterion frozen by an earlier promotion runs on each later candidate and passes | the evaluation's `frozen` rows | a frozen criterion skipped, or failing on an accepted increment |
| P4 | a failed increment leaves the accepted tree untouched | the accepted identity before and after, on the control log | a changed identity without a PROMOTE row |
| P5 | a repair continues the failed candidate under its approved plan, told what failed (#1692) | the repair cycle's `campaign_proposal.repair_of` and `prior_cycle` | a repair framing afresh, or launched without the brief |
| P6 | an answered design question is not asked again (§24ad, §24ag) | each increment's plan gate: `system:no_open_questions` when its delta adds none | a plan gate stopping on a question already answered |
| P7 | an accepted increment's tree is the whole app (§24ac) | the PROMOTE row's `tree_ref`, holding every delivered path | a later increment seeded with a stub where an accepted file was |
| P8 | each limit reached takes its declared action (§9.5) | the decision row's `row` and action, against the counters | a limit reached and not acted on, or acted on early |
| P9 | the proposals' criteria assert only what the change request states (#1884, #1886's teaching) | each criterion file against its `statement` and `observable` | an invented rule frozen as a criterion (the three earlier capacity variants) |

P9 is read by judgement, criterion by criterion, and recorded with the file and line. It is texture,
not a gate (#1884's comment of 2026-10-03).

---

## 5. The policy: immutable for the set, each value with its shakeout basis

The crew's conditions (plan §7):
- the complete policy is immutable for the counted set;
- each value is recorded with its basis;
- where the shakeout does not support a value, a conservative explicit cap is used, never an inferred
  default.

| field | value | basis (shakeouts 1–4, 2026-10-02/03) |
|---|---|---|
| `objective.target_accepted_increments` | **3** | decision 3. Row 3 stops the campaign in success at it (§24ah) |
| `max_cycles` | **9** | 1 calibration, 3 increments, one repair or retry each (3), and 2 replacement increments for abandoned ones. With row 3 reading the target, the cap guards only the failure paths. Shakeout 4's 4 left no room past its repair |
| `max_elapsed_s` | **43200** (12 h) | calibration 51–55 min; increments 56–83 min with the ruling wait; a repair 20 min. A 3-increment run with two repairs is about 5 h, so 12 h is a conservative cap |
| `budget_tokens` | **4000000** | calibration 235–265k; increments 224–484k (484k was the non-converging partial-tree cycle, #1887); a repair 138k; a proposal 9k. About 1.8M expected; 4M is the cap shakeout 4 ran under |
| `max_repair_cycles_per_increment` | **1** | shakeout 4's one repair converged in 20 min on its brief |
| `max_retry_cycles_per_increment` | **1** | no environment failure in any shakeout (0 of 156 stored failed cycles read environment; #1824). Conservative |
| `max_proposal_run_retries` | **1** | no proposal run failed in shakeouts 2–4 |
| `max_proposal_revisions` | **2** | no revision was needed in the shakeouts. The SIP's value |
| `max_rejected_proposals_in_row` | **2** | conservative |
| `max_unaccepted_increments` | **2** | the no-progress rule |
| `ruling_bound_s` | **1800** | the supervisor's bound, whoever holds the seat (§24al). Shakeout rulings took 0–30 min. It records and asks; it never rules |
| `lease_expiry_s` | **3600** | §9.3. Enforced (#1802). A waiting run start's ceiling is one full lease (§24al, §24an) |
| `launch_blocked_interval_s` / `launch_blocked_attempts` | **300 / 6** | §9.3; not reached in the shakeouts |
| `calibration_profile` / `proposal_profile` / `squad_profile` | `validated-fullstack` / `campaign-increment` / `full-38` | every shakeout |

---

## 6. Pins (read at registration)

| pin | value |
|---|---|
| deploy commit | `b09883c9` (rebuild 22; main's CI 10/10 green on it) |
| image ids (runtime-api, max, neo, nat, bob, eve, data) | runtime-api `51f0bcee6404`, max `2c941b1c066e`, neo `9bf9255f3253`, nat `1e2209567a81`, bob `ae08bb9cc501`, eve `3b432c390303`, data `fe095ed432f4` |
| deploy record | `dep_bb1eadeac4e7` (recorded 2026-10-04 08:57:49 UTC, `source_revision` `b09883c9`: 21 services, 5 models, `Qwen/Qwen3.8-27B-FP8` without a digest), referenced by every cycle of the set |
| model | `qwen3.8:27b` `22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643` (the `full-38` squad) |
| loaded checks | read in each running container, each as wanted: #1909 (the flip: a whole re-emission refused in the dev, qa and builder repair seams, 9 of 9, with its control, a new file accepted), #1912, #1802, #1920, #1918, #1943, #1938 (promotion and render), #1929 (runtime and agent halves), #1928, #1922, #1919, #1946 (the rule in the template), #1948 (template v5 and its section; the declarations `null` / none / none for FastAPI, Next.js and an unregistered stack; the handler renders it) |
| policy files | `examples/03_group_run/campaigns/2-0-0-set-1.yaml` sha256 `74cb2f031c055fc250937c8282be66c0cb25a3d0fef6752762fdf91d129d27fe`; `…/2-0-0-set-2.yaml` sha256 `c43dbb4fe216f0fca8ae2291b5527a9256282a8e8bd361f0f7da09ede2cf48dc`; both at commit `34b242a7` (#1942, #1941). Each carries shakeout 7's objective and policy exactly, and its provenance is reconciled in `examples/03_group_run/campaigns/provenance.yaml` |
| the reference scenario's pins | `examples/03_group_run/reference_scenario.yaml` (#1853), checked by the launcher |

---

## 7. Prohibited while the set is open

- **Merging to main.** A fix voids the set.
- **Rebuilding any service.**
- **Touching a campaign outside the interface.**
- **Running anything else on the box.** That includes the crew's local inference (Nostromo §36), the
  convergence replay and the recovery diagnostics.

## 8. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or
  behavioural.
- **Each escalation and its resolution.**
- **Each limit reached.**
- **Each owner action,** inside or outside the interface.

## 9. The owner's decisions at this stop

1. Register as drafted, or amend.
2. ~~Decision 1: flip or not.~~ Ruled 2026-10-03: flip (#1909). Its checkpoint pair is read before registering.
3. ~~Decision 2: who supervises.~~ Not a SquadOps decision (§24al): whoever holds the seat rules.
4. The policy values in §5.
