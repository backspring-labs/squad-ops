# 2.5.0 plan — stabilization: a Campaign on a product SquadOps doesn't own, the yardstick re-cut once, and the hardening the 2.4 line found

**Status: DRAFT (2026-10-23), for the owner's review; revised 2026-10-24 on the MacBook lane's review** (its rows
confirmed, one split, one added, and §24bv's three proposals made D10). Nothing in it starts before the owner rules §7. The Spark lane
drafted it after the 2.4.0 cut (the owner: "let's draft 2.5"). Every item in it was already placed in 2.5 by a ruling
or a ledger row, or was found by the 2.4 line and is placed here for the first time. §1 says which is which.

**What 2.5 is.** An odd minor: a stabilization release, feature-free by rule (CLAUDE.md, #281). It carries no headline
feature. It carries the three things the 2.4 line left unfinished or found weak:
- **A Campaign on a repository-backed Project can't launch an increment** (#2619). 2.4 shipped Project Lifecycle
  Management and Campaigns separately, and their combination fails at three points. So the 2.4 plan's shared
  demonstration (its D13: one Campaign on an external Project across two features) and four of its cross-lane
  scenarios didn't run. The owner placed the fix here on 2026-10-21 ("go with 2.5"). It is labelled a defect: it
  completes two shipped features, and adds none.
- **The yardstick needs one re-cut.** The browser driver misreads two kinds of correct build (#2706, #2659), the
  evaluator's lock carries five advisories accepted only for 2.4.0 (#2712), eight of the held-out suite's step values
  are already public (SIP-0113 §10w), and the quality baselines are too coarse to see an increment (#2637). Each one
  changes the evaluator's tag or the suite's revision, and either change means re-reading every baseline. So they land
  together, once.
- **The checks, the correction loop and the operations** the 2.4 line found weak: two check changes the owner placed
  here (#2297, #2664), the increment's own identity (#2578), the QA output budget the cut's Next.js roll hit (#2253),
  and a list of small operational defects.

**The question it answers:**

> **Does what 2.4 shipped hold together, a Campaign evolving a product SquadOps doesn't own and read by the yardstick,
> and do the instruments and checks the 2.4 line found weak now read what they claim?**

The first half is Track A (§2.1), read by the shared demonstration and IR-4 to IR-7. The second is Tracks B and C
(§2.2, §2.3), each read against its own pre-registered evidence.

---

## 1. Where each item comes from

| item | placed by | when |
|---|---|---|
| #2619: a Campaign on a repository-backed Project (SIP-0112 H.4, SIP-0109 §24bv, SIP-0113 §10l) | the owner: "go with 2.5, write up the amendment" | 2026-10-21 |
| #2414's remainder (the declared start at the cycle-end hook) and #2421's (an owner-approved evaluation secret resolved at start) | SIP-0113's and SIP-0102's ledgers, re-placed with #2619 | 2026-10-21 |
| #2297: widen `contract_assertions_match` | the owner ("3–5 yes") | 2026-10-23 |
| #2664: refuse a QA repair that weakens a failing slot assertion, after the MacBook lane's review | the owner ("3–5 yes") | 2026-10-23 |
| #2578, parts 2–4: an increment's own identity | the owner ("3–5 yes") | 2026-10-23 |
| held-out suite revision 6, approval delegated to the supervisor on revision 5's terms | the owner ("6 delegate") | 2026-10-23 |
| #2706 and #2659, the browser driver's two misreads, with revision 6 | the cut's pre-registration (§12), on the delegation above | 2026-10-23 |
| #2637: a finer quality reading, its design review first | SIP-0113 §10o and its ledger | 2026-10-22 |
| #2184: retire the legacy per-agent LanceDB store | SIP-0110's ledger; its compose change waits for the owner's OK | 2026-10-09 |
| #2433: the Spark thermal rule's no-data alert on other boxes | the owner: "we can pickup 2433 in 2.5 if it's not a blocker" | 2026-10-18 |
| #2712: the evaluator lock's five advisories, accepted for 2.4.0 only | the owner, at the cut | 2026-10-23 |
| everything else in §2 | **this plan, proposed:** each was filed on the 2.4 line and is unplaced | — |

---

## 2. The work

Each item is a framework fix, an instrument fix, a structural change or operations. **Nothing in it is a feature.**
Sizes are S (a day or less), M (a few days) and L (a week or more), as guides.

### 2.1 Track A: a Campaign on a repository-backed Project (#2619)

The design is ruled: SIP-0112 H.4, with its counterparts in SIP-0109 §24bv and SIP-0113 §10l (all 2026-10-21). This
plan only orders and verifies it.

| item | what | lane | size |
|---|---|---|---|
| **H.4's derived profile and gaps** | when a Development Configuration revision is recorded, read what the squad's roles depend on from the pinned tree (languages, test runners, lint and its findings reader, the start declaration, the blueprint if any, the toolchains), and name each gap as **blocking** or **disclosed**. A blocking gap refuses a Cycle before dispatch, and `projects configure` and `projects show` report the gaps. **Its record is the lanes' contract and the MacBook lane's first 2.5 PR,** reviewed by both. Beside H.4 point 1's list, it carries what §24bv point 3 reads: where the product's runner discovers tests, which files are test files, whether the runner can be scoped to one file, the test-support files a frozen bundle takes, and the client routes where a blueprint names them | MacBook | L |
| **H.4's recipe** | the request profiles carry no stack, the source-backed increment profile that §24bv point 1's `proposal_profile` names included, with a resolution-parity test over every `examples/03_group_run/campaigns/*.yaml`, `policy.stack` set and unset. E.4.3's guard narrows from "a stack is named" to "a skeleton would be seeded". A repository-backed cycle takes the derived profile: the configuration's checks, QA writing for the product's runner, and a blueprint's conventions without its template | MacBook | M |
| **SIP-0109 §24bv point 5, the proposal's input** | what the strategy role is handed for a repository-backed Project in place of the accepted tree's manifest, `objective.requirements` at creation (D10), and the change request's rules there, built against §24bv's text | MacBook | M |
| **contract 1's pin for an increment** | `prepare_cycle` pins a repository-backed increment at the campaign branch's head, and its inherited-baseline check reads the previous accepted verification there; H.2's gate keeps reading the Project's baseline. It meets §24bv's branch at the head commit and the previous verification, both in the contract above | MacBook | S |
| **SIP-0109 §24bv points 1–4** | point 1, the calibration is a record of the inherited baseline, not a built cycle, and the start is refused when none can be written (D10); point 2, the accepted tree is one campaign branch, increments promoted onto it in order, with one review request per Campaign; point 3, what an increment pins and is compared against, its acceptance read on the product's own runner; point 4, when upstream moves, a rebase that conflicts escalates and an increment built on the old head is abandoned as `upstream_moved` (D10) | Spark | M–L |
| **SIP-0113 §10l, and #2414's remainder** | the Campaign's baseline reading is an evaluation of the calibration record's commit; the product starts from its own declaration at the cycle-end hook | Spark | M |
| **#2421's remainder** | an owner-approved evaluation secret resolved into the disposable copy's environment at start (SIP-0102 §11e) | Spark | S |
| **#2592** | Outcome Evaluation reads the tree a source-backed cycle contributes (the managed clone's captured commit), not its vault artifacts | Spark | S–M |

**Read by:** the shared demonstration, carried from the 2.4 plan (its D13). One Campaign on an external Project, across
two features, with an outside contribution between them. It is the vehicle for IR-4, IR-5, IR-6 and IR-7, and for
IR-8's and IR-9's evaluation halves, the scenarios the 2.4 integration record reports *not run*. **The Project:**
`z_shelfnote`, the greenfield product from E.4.6's proof, owned by the owner's account. IR-7 needs a greenfield
Project's first Campaign, so on `z_shelfnote` IR-4 to IR-7 read on one Campaign, and H.4's blueprint path runs too. On
`z_continuum`, an imported product, IR-7 would need a Campaign of its own (the MacBook lane's review). Never the real
`backspring-labs/continuum`.

**The order inside the track:** H.4's contract first, since both lanes build against it; then the profile and its
gaps, since a blocking gap refuses a Campaign before dispatch; then the recipe, the proposal's input, the increment's
pin and §24bv's points 1–4 together; then §10l and #2592, which only an evaluated increment exercises. D10's three
proposals are ruled before the calibration record or the proposal's input is built.

### 2.2 Track B: the yardstick, re-cut once

Everything here moves the evaluator's tag, the suite's revision or a measure's version. Each of those re-reads every
baseline it touches, so the track lands as **one batch**, with one deploy and one re-read (§3, phase 2).

| item | what | kind | size |
|---|---|---|---|
| **#2706** | a correctly labelled field isn't read as absent when its label ends with a colon: the driver's name match drops the trailing colon, or the scenario's names accept it. **Evidence before merge:** round 1's three trees read the field, and no tree that passes today stops passing | evaluator change | S |
| **#2659** | a page scenario reads an outcome built in either of two forms, one disabling the control (an `if_enabled` click), so neither correct build reads failed | evaluator change, suite change | S–M |
| **#2712 and #2469** | the evaluator lock's fixes: `fast-uri` 3.1.9 or later, and the peer `puppeteer` whose `chromium-bidi` takes `zod` 4; then the three older accepted advisories retired if Puppeteer's chain allows, and the accepted-advisory list emptied of whatever the bump fixes | evaluator change | S |
| **suite revision 6** | drafted by the supervisor and approved on the owner's delegation, on revision 5's terms: a fresh agent reviews it independently, the approval is recorded with counts only, and it passes `heldout_public_check.py`. **Its contents:** #2659's two-form scenario; the eight step values already public, replaced (SIP-0113 §10w); and nothing else, so the re-read separates the evaluator's change from the suite's | suite change | M |
| **#2637** | the finer quality reading: axe by element, the failing audits by id, and the HTTPS audits recorded as the environment's. **Its design review comes first** (D7). Each is a new measure version, so no delta compares it with the old one, and it carries no weight until its own S1 and S2 series hold, read by re-measuring the window's 20 trees | instrument | M |
| **#2557, if D3 rules it in** | the workhorse PRD's core list names its order: the order runs were created, with sorting left in Expansion Tier 1. That is the answer the supervisor gave at every escalation of this question, and the 2.4.0 cut's `#2183` campaign parked on it once. The PRD is every cycle's input, so it lands with this batch and is re-read once | PRD revision | S |

**The re-read,** on the new evaluator tag, before anything else in 2.5 is measured:
- the 2.4 cut's eleven baseline and counted trees (`docs/plans/2-4-0-cut-preregistration.md` §4.1 and §13), on revision
  5 and then revision 6, so the evaluator's change and the suite's are read apart;
- the always-pass sets re-derived on revision 6, for the 2.5 cut's no-loss reading;
- #2637's S1 and S2 series on the window's 20 trees.

### 2.3 Track C: the checks and the correction loop

| item | what | lane | size |
|---|---|---|---|
| **#2297** | `contract_assertions_match` also flags a suite request that matches a declared route only with a required path segment left empty. **Evidence before merge:** it flags both stored failing suites and passes every accepted suite in the vault since 2026-09-15 | Spark | S |
| **#2664** | a repair of a failing slot assertion keeps an assertion on the same field and surface unless the declarations show the field absent there, or it's refused as `slot_subject_dropped`. **The MacBook lane reviews the design first** (G4), since the correction loop's acceptance is its ground. **Evidence before merge:** read against the 9 recorded cases, it refuses `cyc_bb493eb4725b`'s weakening and passes the strengthening and both correct reductions | after G4: the MacBook lane names the builder | M |
| **#2253** | QA's output budget. The 2.4.0 cut's Next.js roll 2 had a `qa.test` emission cut at its 12,288-token cap, 8,403 of them reasoning. A read first: every `cap_truncated` QA emission since the TensorFold cutover, against the budget. Then the budget, or the reasoning level, set on that evidence | Spark | S read, S change |
| **#2602** | a Next.js page criterion for a page or route the change adds can discriminate: its test's imports and fetch stub resolve on the accepted tree, as #2599 did for endpoints | Spark | M |
| **#2521** | a repair whose files the write authorization drops is told why and counted, not refunded and re-taken unchanged | MacBook | S–M |
| **#2553's remainder** | an input refusal's failure record names its class (`input_contract_failure`). It bumps `ATTRIBUTION_REGISTRY_VERSION` from 1, so failure records written before and after it read differently: the Spark lane, which reads those records, rules the bump at its G4, and it lands before the cut's pre-registration, so no counted reading straddles it | MacBook | S |

### 2.4 Track D: structure

| item | what | lane | size |
|---|---|---|---|
| **#2578, part 2** | `increment_id` on each cycle and an indexed `cycles` column, set to the proposal id at launch; a repair or retry reuses it, a re-proposal gets a new one, a calibration or standalone cycle leaves it empty. A migration, and a shared contract, so **the MacBook lane reviews it** (G4). A SIP-0109 amendment records it in the PR that builds it | Spark | M |
| **#2578, part 3** | Prefect tags `increment:<id>` and `kind:<calibration|increment|repair|retry>`, for operators only. Nothing reads them to decide | Spark | S |
| **#2578, part 4** | no writable increments table: a per-increment view derived from the control log and the cycles, and `campaigns ledger` lists each increment's cycles | Spark | S–M |

### 2.5 Track E: operations and hardening

| item | what | lane | size |
|---|---|---|---|
| **#2184** | retire the legacy per-agent LanceDB store, after a re-inventory. **Its volumes are a compose change, the owner's** (D4) | Spark | M |
| **#2433** | the Spark-only thermal rule raises no alert on a box without that board, and the deploy starts node-exporter wherever its rules expect it | Spark | S |
| **#2493** | an agent's service-token expiry is read on the wall clock, so a host sleep doesn't leave every agent sending an expired token | MacBook (it shows only on a host that sleeps) | S |
| **#2561** | the deploy record carries a model digest under TensorFold, read from TensorFold's own model listing | Spark | S |
| **#2560** | CI's integration job survives `mirror.gcr.io`'s request quota | Spark | S |
| **#2286** | TensorFold's key file holds labelled operator keys beside the deploy key, so an operator key survives a rotation | Spark | S |
| **#2672** | a managed clone's missing directory is named as that, not as "git is not installed here" | MacBook | S |
| **#2402** | `run_prose_lane.sh` runs under macOS's bash 3.2 (no `mapfile`) | MacBook (it shows only there) | S |
| **#2710** | `update_sip_status.py` stamps UTC | Spark | S |
| **#2713** | the release capture names the browser's own load error, and the Spark's capture browser is fixed or replaced (its snap Chromium refuses every local page since 2026-10-22) | Spark | S |
| **#1469** | `frontend_build`'s per-failure signature (#878's treatment, which #1468 left out) | Spark | S |
| **#2287** (deferrable) | the box lease of SIP-0109 §9.3, outside campaigns: built as that section is written, not extended | Spark | M |
| **#2495** (if D6 rules it in; deferrable) | a scripted squad for machinery cycles: every task answered from a recorded script, with no model. The owner asked for it on 2026-10-19 ("we don't need to test model quality just execution machinery"). It is a test tool, not a squad capability | Spark | L |

### 2.6 Not in 2.5

- **Features, by parity,** each waiting for 2.6's plan: the judgement steps (#557, #949, #950) and Test-First's
  greenfield gate (#1978), as re-read at the 2.4.0 cut (D10); SIP-0112's lifecycle completeness (E.4.5, #2709, placed
  in 2.6 with the SIP's close, the owner 2026-10-23) and E.4.7's ship-or-drop decision; a source-backed change's file
  deletion (#2612) and its end-of-plan regression repair (#2613); Outcome Evaluation's outcome target and quality gates
  (SIP-0113 §4.7, held until a reading shows contribution separating from acceptance).
- **The TensorFold 1.x upgrade** (#2230), unless D5 places it.
- **#1965,** the Verification Yield crew's suite audit, and **#1039,** the docs site's design pass: unplaced, as before.
- **#2405,** the Game Development Platform proposal, waiting for 2.6's planning.

---

## 3. Sequencing: the box is the constraint

The Spark is one GPU and one deploy. Everything that measures runs one thing at a time.

1. **Designs and reviews, no box time.** H.4's contract, the MacBook lane's first 2.5 PR, reviewed by both lanes;
   D10's three proposals ruled; #2664's G4 and #2578 part 2's G4 by the MacBook lane; #2637's design
   review (D7); suite revision 6 drafted and reviewed. Small fixes from Tracks C and E merge on green throughout.
2. **Track B's batch, one deploy.** #2706, #2659, #2712 and #2469 in one evaluator tag; revision 6 approved; #2557 if
   ruled; #2637's measure versions. Then **the re-read** (§2.2): about 2 box-hours as a guide. Nothing after this
   measures on the old yardstick.
3. **Track A's builds, then its demonstration.** H.4's profile, then the proposal input and §24bv, then §10l and #2592.
   The demonstration Campaign runs on a deploy carrying all of them: about 4–6 box-hours as a guide, with its own
   pre-registration written before it launches.
4. **Track D,** whose migration lands on its own deploy, read by one uncounted Campaign before anything counts on it.
5. **The cut** (§4): its pre-registration, the shakeout loop, the counted set, and the integration scenarios beside
   it. About 6 box-hours as a guide, as at 2.4.0.

**A deferral rule, as 2.3's:** an item marked deferrable that isn't merged when phase 5's pre-registration is drafted
moves to 2.6, named in the cut record. Tracks A to D aren't deferrable without the owner's ruling.

---

## 4. The cut

Written as a pre-registration when the last batch is built, as at 2.4.0. This plan proposes its shape (D8):
- **The counted set: two regression rolls per stack,** 2.4's number, with every tracked loaded check, memory disabled,
  and 2.4's predictions carried: every model call TensorFold's, memory inert, the cadence, pulse and correction paths
  the baseline's.
- **The no-loss reading,** carried from 2.4's for #1966: no always-pass held-out scenario lost against the re-read
  baselines, now on revision 6.
- **The shakeout, a loop with an exit rule:** one Campaign on the final deploy with no new seam finding, budgeted at
  three rounds.
- **The cross-lane scenarios beside it:** IR-1 to IR-10 each run or reported *not run* with SIP-0112 §8.5's four
  fields. IR-4 to IR-7 run on the demonstration's records, if they can't run on the final deploy itself.
- **What the record says it doesn't cover:** every difference between the tagged tree and the validated deploy, as at
  every cut.

---

## 5. The lanes

As 2.4's D11 and D12, by file ownership:
- **The MacBook lane:** H.4's contract, derived profile and recipe, §24bv point 5's proposal input and contract 1's
  pin for an increment (Project Lifecycle Management's surfaces); #2521, #2553's remainder, #2672, #2402 and #2493;
  the G4 reviews of #2664 and #2578 part 2. It names #2664's builder at its review. Confirmed in its review of this PR
  (2026-10-24).
- **The Spark lane:** Tracks B and D; Track E but for #2672, #2402 and #2493; §24bv points 1–4, §10l, #2414's and
  #2421's remainders, #2592, #2297, #2253 and #2602; the G4 of #2553's registry bump; the deploys, the re-read, the
  demonstration's runs and the cut.
- **The lanes meet** at H.4's contract (the derived profile's record, which §24bv and §10l read): it's written down
  first, and reviewed by both, as 2.4's shared fixture was.


---

## 6. Box-time budget and checkpoints

About **15–20 box-hours** in total, as a guide: phase 2's re-read about 2, the demonstration 4–6, Track D's
uncounted Campaign about 2, and the cut about 6. The supervisor's estimates have run high on earlier lines, so these
are ceilings to report against, not targets. **Checkpoint:** after phase 2's re-read, the supervisor reports what it
moved, before Track A's demonstration launches.

---

## 7. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| D1 | **2.5's scope** | **§2 as drafted:** Tracks A to E, with Track E's two deferrable items deferrable |
| D2 | **the order** | **the yardstick's re-cut first** (§3 phase 2), so everything 2.5 measures, the demonstration and the cut included, is read once on one evaluator and one suite revision |
| D3 | **the workhorse PRD's list order** (#2557) | **name it in §5.2 as the order runs were created,** with sorting left in Expansion Tier 1, landing with the re-cut so the baselines are re-read once. It matches the answer every escalation got. **The alternative:** leave the PRD as it is, and answer the escalation each time it's raised |
| D4 | **retire the legacy LanceDB store** (#2184) | **yes, in 2.5:** its prerequisites are met (#2180 shipped, #2183 passed). The re-inventory runs first, and the volumes are kept as a backup until the cut. **It's a compose change, so it needs your OK** |
| D5 | **the TensorFold 1.x upgrade** (#2230) | **not in 2.5. 2.6's first track,** as TensorFold itself was 2.3's: 2.5's regression then reads against 2.4's baselines with no engine change beside the evaluator's, and 2.6's features measure once on the engine they ship with |
| D6 | **the scripted squad** (#2495) | **in 2.5, deferrable:** it makes the machinery cycles both lanes run independent of a model's mistakes, and it changes no squad behaviour |
| D7 | **#2637's design review** | **the supervisor drafts it as a SIP-0113 amendment, a fresh agent reviews it, and you approve it:** it changes what the yardstick reads |
| D8 | **the cut's shape** (§4) | **2.4's,** with the demonstration as the cross-lane scenarios' vehicle, pre-registered when the last batch is built |
| D9 | **who runs the line, and the tag** | **2.4's terms carry:** the supervisor builds the Spark lane in §3's order, merges on green with main's run read, and runs the rebuilds, the re-read and the uncounted runs. **Yours:** compose changes, gate changes beyond #2664 (already placed), lesson approvals, security, and the Release. **The tag:** the supervisor pushes it at the cut once you say go, as at 2.4.0 |
| D10 | **three proposals of SIP-0109 §24bv**, which gate the calibration record and the proposal's input and are the supervisor's, left for your review | **take them as §24bv proposes** (the MacBook lane's G4 on #2626 found each well argued): **(1)** a Campaign's start is refused, naming why, when no calibration record can be written (the Project isn't ready, its drift isn't reconciled, no baseline is captured, or a blocking gap stands); **(2)** an increment abandoned because upstream moved under it is counted toward no limit, since the squad's work didn't fail; **(3)** a repository-backed Campaign's objective names its requirements source at creation, a file in the product or a stored artifact, since such a Project has no PRD of its own |

---

## 8. What this plan does not decide

- **The cut's numbers:** the set's size, the predictions' thresholds and the shakeout's budget, fixed in the cut's
  pre-registration.
- **Revision 6's text.** The supervisor drafts and approves it on the owner's delegation, and nothing of its content is
  written here.
- **#2637's design,** which its review settles (D7).
- **#2664's builder,** which the MacBook lane names at its review.
- **§24bv's other three open questions:** whether the review request stays a draft until the Campaign ends, a
  per-increment review request beside the Campaign's, and how a frozen bundle snapshots fixtures for runners other than
  pytest and vitest. They wait until after the demonstration, since `z_shelfnote` runs on pytest and vitest.
- **Anything compose** beyond #2184's volumes, and that only with D4.
