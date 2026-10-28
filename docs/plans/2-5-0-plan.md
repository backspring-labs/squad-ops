# 2.5.0 plan — stabilization: a Campaign on a product SquadOps doesn't own, the yardstick re-cut once, and the hardening the 2.4 line found

**Status: ADOPTED (2026-10-24).** The owner ruled §7 and the lanes on 2026-10-24:
- **D1–D10 as recommended,** D5 deferred to 2.6 as recommended. The owner's words: "with all your recommendations and
  defer tensor fold upgrade", then "I agree with your recommendations" on the outside review's changes, then "agree"
  to the summary that named the ten as ruled;
- **D11: approval of the two demonstration suites delegated** on revision 5's terms ("agree");
- **the MacBook lane kept, narrowed** ("keep it narrowed"): it builds Track A's Project Lifecycle Management pieces
  on its own code and does two design reviews, and everything else is the Spark lane's (§5).

**Drafted 2026-10-23, for the owner's review,** and revised three times on 2026-10-24:
- **on the MacBook lane's review:** its rows confirmed, one split, one added, and §24bv's three proposals made D10;
- **on an outside reviewer's review, which the owner brought and accepted** ("I agree with your recommendations"):
  D10's exemption narrowed to the one limit §24bv names; two demonstration Campaigns with a table of what each
  cross-lane scenario reads (§2.1a); Track D moved before the demonstration, with an invalidation rule and the
  scenarios required to pass (§3); the changed browser scenario validated before baselines freeze (§2.2); #2253 built
  on its completed read; a fresh plan-gate check for D3; and, found while checking, each demonstration Project's start
  declaration and held-out suite (D11);
- **and on the MacBook lane's second review:** `z_continuum` tests with pytest only, so the main demonstration's
  features are backend ones or the `web/` gap is named first; and run-path fixes land before Track D's read.

The Spark lane drafted it after the 2.4.0 cut (the owner: "let's draft
2.5"). Every item in it was already placed in 2.5 by a ruling or a ledger row, or was found by the 2.4 line and is
placed here for the first time. §1 says which is which.

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

The first half is Track A (§2.1), read by two demonstration Campaigns and the cross-lane scenarios IR-3 to IR-9
(§2.1a), which must pass for the release to claim it (§3). The second is Tracks B and C (§2.2, §2.3), each read
against its own pre-registered evidence.

---

## 1. Where each item comes from

| item | placed by | when |
|---|---|---|
| #2619: a Campaign on a repository-backed Project (SIP-0112 H.4, SIP-0109 §24bv, SIP-0113 §10l) | the owner: "go with 2.5, write up the amendment" | 2026-10-21 |
| #2414's remainder (the declared start at the cycle-end hook) and #2421's (an owner-approved evaluation secret resolved at start) | SIP-0113's and SIP-0102's ledgers, re-placed with #2619 | 2026-10-21 |
| #2421's remainder (an owner-approved evaluation secret resolved at start) | **left unbuilt in 2.5** (the owner, 2026-10-28, taking the supervisor's recommendation): SIP-0102's ledger re-places it at 2.6.0 | 2026-10-28 |
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
| **#2757** | a vitest test-id reader, so a criterion that runs only under vitest can be read as discriminating (SIP-0109 §24ci (a)). With it, §24bv point 3's pytest reader carries each failure's exception class. It lands before `z_shelfnote`'s demonstration, whose frontend tests with vitest. Placed 2026-10-28 | Spark | S–M |
| **#2592** | Outcome Evaluation reads the tree a source-backed cycle contributes (the managed clone's captured commit), not its vault artifacts | Spark | S–M |

**Read by two demonstration Campaigns,** carried from the 2.4 plan's shared demonstration (its D13), on private copies
owned by the owner's account. Never the real `backspring-labs/continuum`.
- **The main one, on `z_continuum`:** across two features, with an outside contribution between them, as D13 shaped
  it. It is an imported product SquadOps didn't build, with no SquadOps interface manifest (IR-6 needs one without)
  and an inherited failing check, its `lint` (IR-9 needs one). IR-3's 2.4 run bound a project instruction to its
  `CLAUDE.md` (`repo:file:CLAUDE.md@current`), and that record is withdrawn now. So a project instruction bound to the
  same file is written before the Campaign starts, and the outside contribution changes that file: IR-3 completes
  here. **It tests with pytest only:** its `web/` app's scripts are `dev`, `build`, `preview` and `check`, with no
  test runner, and its plugin UIs only build. So H.4's profile names a disclosed gap for changes under `web/`, and
  the main demonstration's pre-registration picks two features with backend observables, or names that gap before
  it launches (the MacBook lane's review).
- **A short one, on `z_shelfnote`:** the greenfield product from E.4.6's proof, for its first Campaign (IR-7), with
  H.4's blueprint path. One increment is enough. On its own, `z_shelfnote` can't read IR-6 or IR-9: it was created
  from an approved manifest, and its recorded failing check passes once its first contribution is reconciled (the
  Mac's baseline at `433f6c51` reads all PASS).

**Each needs, before it launches** (and the main one, the instruction above):
- **a start declaration,** recorded as a Development Configuration revision (contract 7). Neither Project records one
  today, and without it every scenario reads `blocked_unverified` (SIP-0113 §10l);
- **its own held-out suite,** since revision 6 is written for `group_run`: drafted by the supervisor, approved as D11
  rules, and pinned by its Campaign;
- **its own pre-registration,** written before it launches.

**The order inside the track:** H.4's contract first, since both lanes build against it; then the profile and its
gaps, since a blocking gap refuses a Campaign before dispatch; then the recipe, the proposal's input, the increment's
pin and §24bv's points 1–4 together; then §10l and #2592, which only an evaluated increment exercises. D10's three
proposals are ruled before the calibration record or the proposal's input is built.

### 2.1a What each cross-lane scenario reads

Each row is SIP-0112 §8.4's scenario, the Campaign that runs it, and the evidence its pass reads. Each must pass for
the release to claim Track A (§3).

| scenario | passes when (SIP-0112 §8.4) | runs on | the evidence read |
|---|---|---|---|
| **IR-3**, completed | an outside commit changes a repository instruction source under an admitted Campaign. **As H.3 restates it:** new launches wait for the Project's reconciliation, then each later cycle binds the new content at its own commit; a standalone cycle created afterwards binds the new content; a re-binding changes the Campaign only as a recorded intervention | `z_continuum`: a project instruction bound to `CLAUDE.md` is written before the Campaign starts, and the outside contribution between the two features changes that file | the launch held for reconciliation; each later cycle's binding, at its own commit; a standalone cycle's binding after the change; any re-binding in the control log. It closes the one gap 2.4's integration record names ("one Campaign's two cycles at different commits") |
| **IR-4** | no scenario step reaches a prompt, a stored envelope, a squad container, the Project Context, the handoff, an instruction, the managed clone, a workspace or the product repository | both | `heldout_sweep.py` and `--goals` over each Campaign, against baselines taken before it, as the 2.4 cut's Q5 read them, including the product repository and the managed clone. **The proposal's §4.5 evidence** (phase 2's first half, shipped in 2.4) reaches the proposal task's own inputs only, the excused place, and nowhere else |
| **IR-5** | an accepted increment's sandbox revision, Git commit, Campaign accepted tree and evaluation result resolve to one another, and none is stored in another's field | both | each accepted increment's four identities read back and resolved through their mappings, the campaign branch's commit among them |
| **IR-6** | a Project with its own layout and **no SquadOps interface manifest** runs through Outcome Evaluation, started by contract 7's commands: scenarios run on their declared surfaces or read `blocked_unverified`; a surface kind the product lacks is recorded not applicable; nothing falls back to a sample application | `z_continuum` | the evaluation records, with the start declaration's command and the surfaces each scenario ran on; no read of any manifest; each not-applicable surface named |
| **IR-7** | a greenfield Project's first Campaign is read by Outcome Evaluation as any other Project is | `z_shelfnote` | its calibration record and its increment's evaluation record, read through the same path as `z_continuum`'s |
| **IR-8**, the evaluation's half | a Project registered after the cutover is seen by Outcome Evaluation's reads at once, with no YAML shadow | `z_continuum`, registered after the Spark's cutover | the evaluation records name the registry's Project, and `config/projects.yaml` names none of it |
| **IR-9** | an inherited failing native check stays FAIL, attributed `inherited`, and Outcome Evaluation's reading of the same increment is its own: neither derives from or rewrites the other | `z_continuum` (`lint`) | each increment's native verification beside its evaluation record: `lint` reads `inherited`, or `introduced/regressed` only where its findings grew (H.5's reader), while the evaluation reads its own scenarios |

IR-1, IR-2 and IR-10 run on the final deploy beside the cut's set, as at 2.4.0 (§4).

### 2.2 Track B: the yardstick, re-cut once

Everything here moves the evaluator's tag, the suite's revision or a measure's version. Each of those re-reads every
baseline it touches, so the track lands as **one batch**, with one deploy and one re-read (§3, phase 2).

| item | what | kind | size |
|---|---|---|---|
| **#2706** | a correctly labelled field isn't read as absent when its label ends with a colon: the driver's name match drops the trailing colon, or the scenario's names accept it. **Evidence before merge:** round 1's three trees read the field, and no tree that passes today stops passing | evaluator change | S |
| **#2659** | a page scenario reads an outcome built in either of two forms, one disabling the control (an `if_enabled` click), so neither correct build reads failed. **Validated before any baseline freezes** (below): no historical tree builds the disabled form, so re-reading them can't show it works | evaluator change, suite change | S–M |
| **#2712 and #2469** | the evaluator lock's fixes: `fast-uri` 3.1.9 or later, and the peer `puppeteer` whose `chromium-bidi` takes `zod` 4; then the three older accepted advisories retired if Puppeteer's chain allows, and the accepted-advisory list emptied of whatever the bump fixes | evaluator change | S |
| **suite revision 6** | drafted by the supervisor and approved on the owner's delegation, on revision 5's terms: a fresh agent reviews it independently, the approval is recorded with counts only, and it passes `heldout_public_check.py`. **Its contents:** #2659's two-form scenario; the eight step values already public, replaced (SIP-0113 §10w); and nothing else, so the re-read separates the evaluator's change from the suite's | suite change | M |
| **#2637** | the finer quality reading: axe by element, the failing audits by id, and the HTTPS audits recorded as the environment's. **Its design review comes first** (D7). Each is a new measure version, so no delta compares it with the old one, and it carries no weight until its own S1 and S2 series hold, read by re-measuring the window's 20 trees | instrument | M |
| **#2557, if D3 rules it in** | the workhorse PRD's core list names its order: the order runs were created, with sorting left in Expansion Tier 1. That is the answer the supervisor gave at every escalation of this question, and the 2.4.0 cut's `#2183` campaign parked on it once. The PRD is every cycle's input, so it lands with this batch and is re-read once | PRD revision | S |
| **#2723** (deferrable) | held-out suite revision 7: the two limits revision 6's review recorded for the two-form page reading, a disabled input and a skipped click. **It lands only inside this batch,** drafted, reviewed and validated as revision 6 was, before the re-read. If it isn't ready when `-7` is, it moves to 2.6, since a second revision after the re-read would re-cut the yardstick twice. Placed 2026-10-27 | suite | S |

**The changed scenario's validation,** before the re-read derives anything from revision 6. It uses
`read_scenarios.py`'s fault-injected diagnostic, which runs the reading's own path, as SIP-0113 §10r's page scenarios
were validated:
- **known-good builds pass:** one in each correct form, the control left enabled with the limit enforced, and the
  control disabled at the limit;
- **broken builds fail:** a submission accepted beyond the limit, in either form;
- **the check below the limit is kept:** a submission below it still succeeds and reads back;
- **on both stacks, three rounds each,** every round matching on result, blocked reason and first failing step.

A validation that doesn't hold stops the batch, and revision 6 isn't approved until it does.

**The re-read,** on the new evaluator tag, before anything else in 2.5 is measured:
- the 2.4 cut's eleven baseline and counted trees (`docs/plans/2-4-0-cut-preregistration.md` §4.1 and §13), on
  revision 5 and then revision 6, so the evaluator's change and the suite's are read apart;
- the always-pass sets re-derived on revision 6, after the validation above, for the 2.5 cut's no-loss reading;
- #2637's S1 and S2 series on the window's 20 trees.

**If D3 rules #2557 in,** a fresh calibration on each stack goes through its plan gate on the revised PRD, and its
plan's open questions are read: the order question should be gone. Re-reading old trees can't show that, since the
behaviour is the plan's. One calibration per stack is a check, not a rate, because the escalation was intermittent, so
the cut's rolls and the shakeout's calibrations are read for it too, at no extra cost.

### 2.3 Track C: the checks and the correction loop

| item | what | lane | size |
|---|---|---|---|
| **#2297** | `contract_assertions_match` also flags a suite request that matches a declared route only with a required path segment left empty. **Evidence before merge:** it flags both stored failing suites and passes every accepted suite in the vault since 2026-09-15 | Spark | S |
| **#2664** | a repair of a failing slot assertion keeps an assertion on the same field and surface unless the declarations show the field absent there, or it's refused as `slot_subject_dropped`. **The MacBook lane reviews the design first** (G4), since the correction loop's acceptance is its ground. **Evidence before merge:** read against the 9 recorded cases, it refuses `cyc_bb493eb4725b`'s weakening and passes the strengthening and both correct reductions | Spark, after the MacBook lane's G4 | M |
| **#2253** | QA's output budget, **built on the headroom read already done** (#2253, 2026-10-18): `qa.test` and `qa.test_repair` are the only task types whose p95 is the cap, and on TensorFold 7.9% of `qa.test` calls and 20.8% of `qa.test_repair` calls were cut; most cut calls ran out thinking, not writing. The 2.4.0 cut's Next.js roll 2 had one more. **Before any change:** compare, for both task types, the suites' outcomes and the time spent under the two remedies the read names, a higher cap (a replay of the cut envelopes at it) and a lower reasoning level for test authoring (the finished re-asks against first calls that finished). **"No change" is a valid outcome** if the evidence doesn't favour either | Spark | S–M read, S change |
| **#2602** | a Next.js page criterion for a page or route the change adds can discriminate: its test's imports and fetch stub resolve on the accepted tree, as #2599 did for endpoints | Spark | M |
| **#2743** | a proposal's derived footprint no longer forces every QA test namespace the stack declares into the owner's scope, so a backend-only change scoped to one route and one test file can validate. The fix's shape is read from `campaigns/change_request.py` first. **Evidence before merge:** the issue's deterministic reproduction (`validate_proposal` over campaign `cmp_b79783b2…`'s accepted manifest, no model call) passes, and a request naming a test outside the owner's scope is still refused `out_of_scope`. Placed 2026-10-27 | Spark | S–M |
| **#2521** | a repair whose files the write authorization drops is told why and counted, not refunded and re-taken unchanged | Spark | S–M |
| **#2553's remainder** | an input refusal's failure record names its class (`input_contract_failure`). It bumps `ATTRIBUTION_REGISTRY_VERSION` from 1, so failure records written before and after it read differently: the Spark lane builds it, since it reads those records, and it lands before the cut's pre-registration, so no counted reading straddles it | Spark | S |

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
| **#2493** | an agent's service-token expiry is read on the wall clock, so a host sleep doesn't leave every agent sending an expired token | Spark (reproduced by moving the clock, since it shows only on a host that sleeps) | S |
| **#2561** | the deploy record carries a model digest under TensorFold, read from TensorFold's own model listing | Spark | S |
| **#2560** | CI's integration job survives `mirror.gcr.io`'s request quota | Spark | S |
| **#2286** | TensorFold's key file holds labelled operator keys beside the deploy key, so an operator key survives a rotation. **Partly delivered by the owner's #2742 (2026-10-24):** readers take the `squadops` line by its label, and `ensure` keeps every other label. **What remains:** the `.env` operator-key spec, whether `rotate` keeps the other labels (unverified), the restart on adding a key, and `credential_rotation.md` | Spark | S |
| **#2672** | a managed clone's missing directory is named as that, not as "git is not installed here" | Spark | S |
| **#2402** | `run_prose_lane.sh` runs under macOS's bash 3.2 (no `mapfile`) | Spark (tested under bash 3.2 in a container, since it shows only on macOS) | S |
| **#2710** | `update_sip_status.py` stamps UTC | Spark | S |
| **#2713** | the release capture names the browser's own load error, and the Spark's capture browser is fixed or replaced (its snap Chromium refuses every local page since 2026-10-22) | Spark | S |
| **#1469** | `frontend_build`'s per-failure signature (#878's treatment, which #1468 left out) | Spark | S |
| **#2744** | `engine_replay.py` records a transport exception's type, never its text. A header error's text carries the bearer key, and replay rows are `var/` records that the line's Release tarball carries. Placed 2026-10-27 | Spark | S |
| **#2287** (deferrable) | the box lease of SIP-0109 §9.3, outside campaigns: built as that section is written, not extended | Spark | M |
| **#2495** (if D6 rules it in; deferrable) | a scripted squad for machinery cycles: every task answered from a recorded script, with no model. The owner asked for it on 2026-10-19 ("we don't need to test model quality just execution machinery"). It is a test tool, not a squad capability | Spark | L |

### 2.6 Not in 2.5

- **Features, by parity,** each waiting for 2.6's plan: the judgement steps (#557, #949, #950) and Test-First's
  greenfield gate (#1978), as re-read at the 2.4.0 cut (the 2.4 plan's D10); SIP-0112's lifecycle completeness
  (E.4.5, #2709, placed in 2.6 with the SIP's close, the owner 2026-10-23) and E.4.7's ship-or-drop decision; a
  source-backed change's file deletion (#2612) and its end-of-plan regression repair (#2613); Outcome Evaluation's
  outcome target and quality gates (SIP-0113 §4.7, held until a reading shows contribution separating from
  acceptance).
- **The TensorFold 1.x upgrade** (#2230), unless D5 places it.
- **#1965,** the Verification Yield crew's suite audit, and **#1039,** the docs site's design pass: unplaced, as
  before.
- **#2405,** the Game Development Platform proposal, waiting for 2.6's planning.

---

## 3. Sequencing: the box is the constraint

The Spark is one GPU and one deploy. Everything that measures runs one thing at a time.

1. **Designs and reviews, no box time.** H.4's contract, the MacBook lane's first 2.5 PR, reviewed by both lanes;
   D10's three proposals ruled; #2664's G4 and #2578 part 2's G4 by the MacBook lane; #2637's design review (D7);
   suite revision 6 drafted and reviewed. Small fixes from Tracks C and E merge on green. **Each fix that changes a
   path a run executes lands in phases 1–2,** before Track D's uncounted Campaign, so the invalidation rule below voids
   neither that read nor the demonstrations: #2521, #2553's remainder, #2672 and #2493 among them.
   **Track C's are among them too** (2026-10-27): #2253's outcome, #2664, #2602, #1469 and #2743 land before phase 3's
   Campaign. Track A's builds go on beside them wherever they're unblocked.
   A fix to a script no run executes, such as #2402, can land at any time.
2. **Track B's batch, one deploy.** #2706, #2659, #2712 and #2469 in one evaluator tag; #2557 if ruled; #2637's
   measure versions. Then, in order: **the changed scenario's validation** (§2.2), about 2 box-hours as a guide;
   revision 6 approved; **the re-read**, about 2; and D3's fresh calibrations, if ruled, about 1. Nothing after this
   measures on the old yardstick.
3. **Track D, before the demonstration.** #2578's migration changes the campaign cycle records the demonstration
   exercises, so it lands first, on its own deploy, read by one uncounted sample-application Campaign before anything
   counts on it. **Run and read 2026-10-28** (`cmp_9c9df268084a`, uncounted, on `dep_fbeecffcc625` and, after #2754's
   fix, `dep_31949f050a30`): #2578's records hold on every cycle kind (R1–R4), and the campaign ended `success`
   (`verification-sets/2-5-0-track-d-campaign-preregistration.md` §7).
4. **Track A's builds, then its two demonstrations.** H.4's contract and profile, then the recipe, the proposal's
   input, the increment's pin and §24bv, then §10l and #2592. **§24bv's regression baseline, its acceptance on the
   product's runner and the rebase wait for contract 1's increment pin** (the MacBook lane's
   `ProjectSourceContext.pinned_commit` and `pinned_from`, SIP-0109 §24cd point 1). Until it lands, every increment is
   pinned at the Project's baseline and there is nothing for them to wire into. Both Projects' start declarations are
   recorded and their suites approved first. The Campaigns run on a deploy carrying all of it: about 6–9 box-hours as a guide, the main
   one 4–6 and the short one about 3.
5. **The cut** (§4): its pre-registration, the shakeout loop, the counted set, and the integration scenarios beside
   it. About 6 box-hours as a guide, as at 2.4.0.

**What invalidates earlier evidence.** A run's evidence holds for the release only while what it exercised is
unchanged. A later merge that changes a path an earlier run's cycles executed (the agents' code, the runtime's, the
evaluator's image, a request profile, a suite or the PRD) voids that run for the release claim. That run is repeated,
or the owner rules on it, and the cut record names each case. Documents, records and changes to paths the run didn't
execute leave it standing. The cut's pre-registration lists the paths each run exercised.

**The release claim needs the cross-lane scenarios to pass.** 2.5's first half claims a Campaign on a
repository-backed Project works end to end, so IR-3 to IR-9 must pass (§2.1a). One reported *not run*, or failed,
needs **the owner's explicit ruling narrowing the release claim**, named in the cut record. 2.4's G5, which let a
scenario report *not run* with its four fields, doesn't carry for these.

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
- **The cross-lane scenarios:** IR-3 to IR-9 read on the two demonstration Campaigns (§2.1a) and must pass; IR-1, IR-2
  and IR-10 run on the final deploy beside the set. Any demonstration evidence a later merge voided (§3) is repeated
  on the final deploy before the set registers, or the owner rules on it.
- **What the record says it doesn't cover:** every difference between the tagged tree and the validated deploy, as at
  every cut.

---

## 5. The lanes

**The MacBook lane is kept, narrowed** (the owner, 2026-10-24: "keep it narrowed"). Its reason to exist in 2.5 is Track
A's Project Lifecycle Management pieces, which build on code it wrote in 2.4, and its reviews as that code's owner.
- **The MacBook lane builds:** H.4's contract (its first 2.5 PR), the derived profile and gaps, the recipe, §24bv point
  5's proposal input and contract 1's pin for an increment. **It reviews:** #2664's design and #2578 part 2's cycle
  field (G4), before the Spark lane builds either.
- **The Spark lane does everything else:** Tracks B, C, D and E, #2521, #2553's remainder, #2672, #2493 and #2402
  among them; §24bv points 1–4 with SIP-0109 §24ci's readers and push, #2757, §10l, #2414's remainder and #2592; the deploys, the re-read, the
  demonstrations' runs and the cut.
- **The lanes meet at three points only:** H.4's contract, reviewed by both before either builds against it; the two
  G4 reviews; and merge holds while a counted set or a demonstration runs. Nothing else needs the MacBook lane, so a
  lane that's asleep holds nothing up.

---

## 6. Box-time budget and checkpoints

About **20–27 box-hours** in total, as a guide: phase 2's scenario validation about 2 and its re-read about 2; D3's
fresh calibrations about 1; Track D's uncounted Campaign about 2; the two demonstrations 6–9; and the cut about 6. The
supervisor's estimates have run high on earlier lines, so these are ceilings to report against, not targets.
**Checkpoints:** after phase 2's re-read, the supervisor reports what it moved; after the demonstrations, the table in
§2.1a, filled in, before the cut's pre-registration is drafted.

---

## 7. Decisions for the owner (ruled 2026-10-24, as recommended; D11 delegated)

| # | decision | recommendation |
|---|---|---|
| D1 | **2.5's scope** | **§2 as drafted:** Tracks A to E, with Track E's two deferrable items deferrable |
| D2 | **the order** | **the yardstick's re-cut first** (§3 phase 2), so everything 2.5 measures, the demonstration and the cut included, is read once on one evaluator and one suite revision |
| D3 | **the workhorse PRD's list order** (#2557) | **name it in §5.2 as the order runs were created,** with sorting left in Expansion Tier 1, landing with the re-cut so the baselines are re-read once. It matches the answer every escalation got. **The alternative:** leave the PRD as it is, and answer the escalation each time it's raised |
| D4 | **retire the legacy LanceDB store** (#2184) | **yes, in 2.5:** its prerequisites are met (#2180 shipped, #2183 passed). The re-inventory runs first, and the volumes are kept as a backup until the cut. **It's a compose change, so it needs your OK** |
| D5 | **the TensorFold 1.x upgrade** (#2230) | **not in 2.5. 2.6's first track,** as TensorFold itself was 2.3's: 2.5's regression then reads against 2.4's baselines with no engine change beside the evaluator's, and 2.6's features measure once on the engine they ship with |
| D6 | **the scripted squad** (#2495) | **in 2.5, deferrable:** it makes the machinery cycles both lanes run independent of a model's mistakes, and it changes no squad behaviour |
| D7 | **#2637's design review** | **the supervisor drafts it as a SIP-0113 amendment, a fresh agent reviews it, and you approve it:** it changes what the yardstick reads |
| D8 | **the cut's shape** (§4) | **2.4's,** with the two demonstrations as the cross-lane scenarios' vehicle, those scenarios required to pass (§3), pre-registered when the last batch is built |
| D9 | **who runs the line, and the tag** | **2.4's terms carry:** the supervisor builds the Spark lane in §3's order, merges on green with main's run read, and runs the rebuilds, the re-read and the uncounted runs. **Yours:** compose changes, gate changes beyond #2664 (already placed), lesson approvals, security, and the Release. **The tag:** the supervisor pushes it at the cut once you say go, as at 2.4.0 |
| D10 | **three proposals of SIP-0109 §24bv**, which gate the calibration record and the proposal's input and are the supervisor's, left for your review | **take them as §24bv proposes** (the MacBook lane's G4 on #2626 found each well argued): **(1)** a Campaign's start is refused, naming why, when no calibration record can be written (the Project isn't ready, its drift isn't reconciled, no baseline is captured, or a blocking gap stands); **(2)** an increment abandoned because upstream moved under it doesn't count toward `max_unaccepted_increments`, the one limit §24bv names, since the squad's work didn't fail. **Every other limit stands:** the cycles it spent count toward `max_cycles`, its tokens toward `budget_tokens`, and its time toward `max_elapsed_s`. Tests show repeated upstream movement still exhausts those limits, or pauses the Campaign at them; **(3)** a repository-backed Campaign's objective names its requirements source at creation, a file in the product or a stored artifact, since such a Project has no PRD of its own |
| D11 | **the demonstration Projects' held-out suites** (§2.1), one each for `z_continuum` and `z_shelfnote`, since revision 6 is written for `group_run` | **the supervisor drafts each, on revision 5's terms:** a fresh agent reviews it independently, the approval is recorded with counts only, and it passes `heldout_public_check.py`. **Recommended: you delegate the approval on those terms,** as you did for revisions 4 to 6. **The alternative:** you approve each suite yourself, from its counts and its review. The 2.4 plan put a new product's suite with you (its D13, under D2), so this needs your word either way |

---

## 8. What this plan does not decide

- **The cut's numbers:** the set's size, the predictions' thresholds and the shakeout's budget, fixed in the cut's
  pre-registration.
- **Revision 6's text.** The supervisor drafts and approves it on the owner's delegation, and nothing of its content
  is written here.
- **#2637's design,** which its review settles (D7). **Approved by the owner 2026-10-28** (SIP-0113 §10y).
- **§24bv's other three open questions:** whether the review request stays a draft until the Campaign ends, a
  per-increment review request beside the Campaign's, and how a frozen bundle snapshots fixtures for runners other
  than pytest and vitest. They wait until after the demonstrations, whose products test with pytest, and vitest on
  `z_shelfnote`.
- **Anything compose** beyond #2184's volumes, and that only with D4.
