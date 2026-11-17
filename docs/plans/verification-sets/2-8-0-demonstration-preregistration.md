# 2.8 demonstration: pre-registration

**Status: REGISTERED when this file merges, before any of the runs it names** (#3043, SIP-0118 phase 3; the
2.8 plan §0 and §2, revision 4). Nothing below is created or launched before the merge.

## 1. What it counts

The 2.8 headline claim (the plan §0, the game-dev-roblox plan §1, D1):

> A squad running on the Spark takes two consecutive small increments of an existing Roblox game from design to
> accepted source, each proved in a real play session in Roblox Studio, on a private copy of Tower Ascension.

**The claim is read on the counted run alone** (§7). The full-path gate (§5) and the rehearsal (§6) are uncounted, and
their outcomes are reported beside the counted run's. The repair diagnostic (§8) is labelled apart. It proves the
correction route and is no evidence about the models.

## 2. The order, as the owner ruled it

The plan (§4 step 8) and #3043 put the steps in this order: the full-path gate, the rehearsal, the repair
diagnostic, then the counted run. **The owner changed that order on 2026-11-17** ("Counted run first"). The order is
now:
1. the full-path gate;
2. the rehearsal;
3. the counted run, only if the rehearsal reads clean (§6.1);
4. the repair diagnostic, once its fault is merged and deployed: today if the window allows, otherwise in a later
   window.

**Why.** While this file was drafted, the injectable faults (`fault_injection.FAULTS`, 13 shapes) turned out to hold
no behavioural defect for a Luau development emission. The diagnostic couldn't run without one. The MacBook lane
built it as `luau_player_text_drops_a_word` (#3170, PR #3171). Steps 1 to 3 all run on one deploy, so the rehearsal reads the same machinery the counted run uses.
The fault arrives with a later rebuild.

**The counted claim doesn't depend on the diagnostic** (the plan §0; SIP-0118 R3.5).

## 3. The window

**The window:** one attended window on 2026-11-17, ruled by the owner that day. It opens when this file merges. The
owner is at the MacBook with Roblox Studio open on the z_tower place, for about three hours. **Nothing plays outside
it.**

**Checks before anything plays, each recorded:**
1. **Remote execution is bound.** The Spark's `SQUADOPS__REMOTE_EXECUTION__PROVIDER` is set to `runtime_api`, and
   the Spark is rebuilt from this file's merge commit. This holds for this window only, on the owner's go.
2. **What loaded.** `verify_loaded.py` reports every row ok, and the deploy's record id is written into the run
   record.
3. **The worker is serving.** `squadops workers list` shows `macbook` online, serving `roblox-studio`
   `play_scenario`.
4. **The MacBook side is ready.** The MacBook lane confirms:
   - Studio is open on the place, unpublished, with Studio writes going to the local copy only (the owner's standing
     rule);
   - the Studio version is the one the worker was qualified on (#3048). Any other version stops the window;
   - **the Mac is unlocked and awake, and Studio is the app in front** (amended 2026-11-17, §12a). The MacBook lane
     reads this at each launch that plays, and keeps it so until the plays that launch asks for have settled.

**When the window closes:** at its end, or at the first thing that needs the owner or the MacBook lane, the provider
goes back to `none` and the Spark is rebuilt. It isn't left bound outside the window.

**The time rule.** The counted Campaign is created only if what remains of the owner's window is at least the
rehearsal's own wall time plus 30 minutes. Otherwise the window stops before it, and the counted run waits for
another attended window. An overnight counted run needs an unattended rehearsal first (the plan §8, decision 7).

**If the window ends while the counted Campaign is running,** the owner decides on the spot whether to stay.
- If the owner leaves, the Spark aborts the Campaign. The abort is an intervention (§7.4), and that attempt doesn't
  meet the claim.
- A later counted run is attempt 2, on the same items in the same order.

## 4. What it runs on

**The deploy:**
- built from this file's merge commit;
- one deploy for steps 1 to 3. Main moves before the counted run only by documents, and any such move is named in
  the record;
- verify_loaded is expected to read 285 rows, the count at `fed77db3`.

**The product:**
- `prj-z-tower-ascension` (`backspring-labs/z_tower-ascension`, a private copy), at baseline commit `0beaac09`;
- Development Configuration revision 3;
- baseline captured at revision 3 on 2026-11-17 (`luau_tests` PASS);
- its derived profile discloses two gaps:
  - `no_start_declaration`, which is Outcome Evaluation's. No scenario suite is pinned here, so Outcome Evaluation
    reads nothing in this run;
  - `stack_unmatched`, which SIP-0116 §17v reads as no defect.

**The goal set:** revision 1, the owner's approved draft on #3042, registered 2026-11-17 08:14 ET. Its two results
are observed on a `scenario` surface, "the HUD in a play session". Its backlog, in order:
- B-1, the lobby hint, serving ER-lobby-hint;
- B-2, the session clock, serving ER-session-clock.

**The rest:**
- **The squad:** `game-dev-roblox` under the development profile `game_dev_roblox`, named in each Campaign's policy
  (SIP-0109 §24ed).
- **The worker:** the MacBook's, serving `roblox-studio/1`.
- **Held-out separation (SIP-0118 R3.5):** none is pinned. The scenarios are public QA verification, and no role
  gains held-out access.

**What changed on the deploy since the plan was written, and how it bears on this run:**
- **SIP-0109 §24ee** (#3167, `b0c0c28f`):
  - **What it does:** the plan-review tier has a fourth condition, `no_escalated_conflict`. When the merge escalated
    a brief conflict, blocking or unread, the plan gate goes to a person. It does the same when merge decisions are
    absent or can't be read.
  - **For this run:** in the counted run, a person's ruling on such a gate is an intervention (§7.4).
- **SIP-0093 §15d** (#3165, `6200f1ea`):
  - **What it does:** both task proposers are shown a brief conflict's shape. A conflict that can't be read is
    escalated with what was written.
  - **For this run:** the proposers' prompts changed. Envelopes captured before `6200f1ea` won't reconstruct exactly
    on this deploy.
- **SIP-0112 H.35** (#3168, `fed77db3`; z_tower's configuration revision 3):
  - **What it does:** z_tower reserves three paths. A proposal, plan or run that reaches one is refused by path:
    - `src/Server/Util/ProfileSchema.luau`
    - `src/Shared/Config/SaveConfig.luau`
    - `src/Server/Services/PersistenceService.luau`
  - **For this run:** B-1 and B-2 touch no saved data, by the goal set's constraints.
- **SIP-0116 §17w** (#3162, `4fd813b8`):
  - **What it does:** a `game_dev_roblox` cycle is refused at creation unless remote execution is bound, and a
    cancelled run asks no scenario to be played.
  - **For this run:** this is why §3's first check comes first.
- **SIP-0115 §10h** (#3166, `c96bd104`):
  - **What it does:** the `scenario` surface kind. A proposal is shown each result as "scenario `the HUD in a play
    session`".

## 5. Step 1: the full-path gate (uncounted)

**What it is:** one increment on z_tower, from `2-8-0-full-path-gate-campaign.yaml`.
- **Its objective:** the part 5 Campaign's (`cmp_d1463eb2d31b`), the replay's `strategy-hud-text` case word for
  word: the HUD's lives label. It is neither B-1 nor B-2.
- **It plays:** its scenario criterion makes the framework append `qa.run_remote_operation`, so the reader's leg is
  in it.
- **Its acceptance isn't read.** Its scenario depends on the lives count the developer's save holds, which is one
  more reason the gate reads machinery and not acceptance.

**Who rules its proposal:** the Spark, under the owner's 2026-11-16 grant for uncounted runs. It is approved as it
stands when it is a change request for the objective, and when every literal path it names (footprint and criterion
`paths`) is a file the product holds at its baseline commit, or one the change says it adds (amended 2026-11-17,
§12b). A return is reported.

**Read per task family:**
- the strategy proposal;
- the plan's task proposers and their merge;
- `governance.define_done`;
- `development.develop`;
- `qa.test`;
- `qa.run_remote_operation`, the play.

**Each family is read from its authoring envelope and its memory exposure:**
- **G1. Budget.** The prompt fits the real budget, and no section is cut or left out for budget. Read from the
  context assembly's record.
- **G2. Skills.** The skills loaded are the skillset record's assignment for the role. `game_dev_roblox` requires
  `roblox-increment-design`, `roblox-luau-dev` and `roblox-studio-qa`.
- **G3. Context selection, measured.** For `development.develop` and `qa.test`, three lists, read from the envelope:
  - the product files the task was handed;
  - the change's footprint;
  - the modules those footprint files require (their `require` targets, resolved).

  Reported as handed, needed and missing. It is measured and doesn't gate.
- **G4. The reader.** Each part is read without any degraded, unread or malformed section:
  - every emission is parsed, including §15d's unread brief conflicts;
  - the play's assertion records are read by the harness reader, with every assertion executed, or named with why
    not.
- **G5. Endings.** Every task reaches an ending.

**The rule:** the gate passes when G1, G2, G4 and G5 hold for every family. If it fails, the window stops before the
rehearsal, with the failing family and its reading reported.

## 6. Step 2: the rehearsal (uncounted)

**What it is:** `2-8-0-rehearsal-campaign.yaml`, the counted Campaign's definition limit for limit. Only the
objective's statement differs. It runs goal set revision 1, B-1 then B-2.
- **The same items as the counted run, on purpose.** Only a goal-set Campaign on this goal set exercises the counted
  path: the proposal naming the next eligible item, the scenario surface, and B-2's replay of B-1's frozen scenario.
- **The owner rules its proposals,** as in the counted run, with the MacBook lane's reading of each scenario first
  (§7.4). So the rehearsal includes the ruling path.

### 6.1 Clean

"Clean" reads the machinery, not acceptance. The rehearsal is clean when all of these hold:
1. **Endings:** every cycle reaches a named ending at a SIP-0109 §10 row.
2. **No framework defect:** no stop or refusal is attributed to the framework rather than to the squad's work, and
   no undesigned refusal is met.
3. **No unplanned action:** nobody acts beyond the permitted actions of §7.4.
4. **Plays did only the scenario's steps:** every play did in Studio only what its scenario's steps say. The MacBook
   lane reads this.
5. **The worker held:** it stayed online, or each wait resolved through the Campaign's own launch-blocked handling
   (#3045).

**A rejection for model reasons doesn't make it unclean.** If the rehearsal's increments end rejected because of the
squad's own work, the counted run still runs. That is disclosed as a second attempt at the same items.

**If it isn't clean:**
- the window stops before the counted run, and the finding is reported and fixed;
- a further rehearsal is reported as rehearsal 2;
- the counted run follows only a clean rehearsal, on the deploy that rehearsal ran on.

### 6.2 Nothing carries into the counted run

Each item below says what it rests on, and how it is checked after the counted run.

| what | what it rests on | checked after the counted run by |
|---|---|---|
| **the product** | The integrated commit moves only when a review request is merged and the product is synced. Neither Campaign's work is pushed (`campaigns push-review` isn't run), and nothing is merged into z_tower. | `projects show`: the integrated commit is still `0beaac09`. The counted Campaign's calibration record names the tree at `0beaac09` |
| **the goal set** | Nobody edits it between the Campaigns. Neither Campaign promotes or drops a candidate. | `goals history`: revision 1 is still the active one when the counted Campaign is created |
| **backlog status** | Each Campaign derives its backlog from its own control log (`campaigns/backlog.py`). An item accepted in another Campaign isn't carried, since `accepted (carried)` isn't built (SIP-0115 §10b). | `campaigns backlog` on the counted Campaign at its create: B-1 `pending`, the next item |
| **its branch** | Each Campaign has its own campaign branch from the calibrated tree. | the counted Campaign's calibration record and accepted tree |
| **memory: lessons** | Recall answers only approved lesson revisions, pinned when a unit is admitted (`memory/lessons.py`). Approvals are the owner's. The store holds one, for `group_run`, revoked 2026-10-10. None is approved between the Campaigns. | the counted run's `memory_exposures`: every row `none_eligible`, or memory disabled, with no approval in its snapshot. `memory_approvals` unchanged |
| **memory: failure recall** | A repair's lessons come through the same snapshot recall (`correction_repair.py`), so the same pin applies. | the same `memory_exposures` rows, at the repair seam |
| **proposal evidence** | It shows a Campaign's own pinned suite's results on its own accepted tree (SIP-0113 §4.5). Neither Campaign pins a suite. | the counted proposals' envelopes carry no `proposal_evidence` input |
| **any other path** | none known | Every counted envelope's inputs are listed by key, and none names the rehearsal's campaign, cycle or proposal ids. B-2 is shown B-1's accepted tree from the counted Campaign itself, by design |

z_tower's 37 memory exposures to date are all `none_eligible`. **If any path is found that could carry the
rehearsal's work into a counted prompt unapproved, it is stated before the counted Campaign is created,** and the run
waits for the owner.

### 6.3 The place between the Campaigns

**The worker keeps the place to the baseline itself** (SIP-0117 R5.15–R5.19 and the reset in §R5.17):
- each play syncs the candidate's whole script set into the place and reads it back, removing scripts the candidate
  doesn't hold;
- each claim holds the place to its pinned non-script baseline. A drifted place is reset once from
  `ta-copy.pristine.rbxl`, with Studio reopened and no person involved;
- the tool is reset after any ending but a returned result.

**Nothing is done by hand in Studio between the Campaigns.** Before the counted Campaign is created, the MacBook lane
reads the worker's log for two things:
- the place left unpublished at its pinned non-script baseline after the rehearsal's last play;
- no save prompt pending.

**If the MacBook lane judges a reload needed,** it is done before the counted Campaign's create row (reload without
saving; Play stopped). It is recorded with its time and reason. It comes before counting starts, so it is no
intervention in the counted run.

## 7. Step 3: the counted run

**What it is:** `2-8-0-counted-campaign.yaml`, created only after a clean rehearsal (§6.1) and under the time rule
(§3). It runs on the same deploy.

### 7.1 How the two increments are selected

**The selection:** goal set revision 1's backlog order, B-1 then B-2. It was fixed before any run, and the
rehearsal's outcome doesn't change it.
- **One item per increment:** each increment's proposal must name the next eligible item (SIP-0115 §5.3). A proposal
  naming any other item is returned at the gate.
- **A failed increment ends the Campaign:** `max_unaccepted_increments: 1` ends it at the first abandoned increment
  (continuation's row 4, `no_progress`). So B-2 never runs after a failed B-1, and **a failed increment is never
  replaced by another**.

**Each result is observable through `roblox-studio/1`'s scenario vocabulary.** The MacBook lane reads this against
the vocabulary before merge.

| item | what is played | what isn't played, and where it is proved instead |
|---|---|---|
| **B-1** | the lobby half: the hint line's text, read in the lobby, where the session starts | the floor half (the line hidden on a floor): no vocabulary action takes a player through the portal by name, so it is proved by the rule module's headless test |
| **B-2** | the clock: a `wait_until` in the scenario's steps, where a timeout lets the scenario go on, for the clock to read a later time; then the named assertion on that reading, with `contains` or `equals`. A missing clock and one stuck at its start value both fail it. The vocabulary compares a reading with a value, never two readings, and has no action that only waits | how a duration is written (65 s is `1:05`): the rule module's headless test |

### 7.2 When counting starts and stops

**Counting starts** at the counted Campaign's `create` row. **It stops** at the Campaign's terminal state:
- **success:** `objective_met`, both items accepted;
- **failure or exhaustion:** row 4, by `no_progress` or a bound;
- **an abort:** an intervention (§7.4).

**The claim is read live** against §7.3 as the Campaign runs, and at its end.

### 7.3 The readings, each with what falsifies it

Each holds for each increment unless it says otherwise.
- **C1. The item.** The increment's accepted proposal names B-1 for the first increment and B-2 for the second, at
  revision 1. Falsified by an increment built from any other item.
- **C2. Frozen before development.** The change request carries a scenario criterion. Its scenario is frozen (by
  digest) before `development.develop` is first dispatched. Falsified by a scenario frozen after development starts,
  or by no scenario criterion.
- **C3. It fails on the accepted baseline.** The scenario baseline step plays the frozen scenario on the accepted
  baseline: `0beaac09` for B-1, and B-1's accepted tree for B-2. The named assertion executes and fails. Falsified
  by:
  - a pass;
  - an assertion that didn't execute: blocked, `not_executed` or unread. Anything unread blocks (the plan §11's reconciliation
    row for the criterion failing on the baseline; #3044).
- **C4. Dev writes the Luau change.** `development.develop`'s accepted emission changes Luau source under `src/`,
  within the footprint, and reaches no reserved path. Falsified by a candidate with no source change.
- **C5. It passes on the candidate.**
  - **The play:** `qa.run_remote_operation` (`game.scenario_verification`, play mode) syncs the candidate into
    Studio and plays the same frozen scenario, by digest. The named assertion executes and passes.
  - **The headless suite:** the product's `luau_tests` pass on the candidate.

  Falsified by a different digest, a failed assertion, or an assertion that didn't execute.
- **C6. Accepted.** The Campaign's `promote` row accepts the source onto the campaign branch, on revision-bound
  Studio evidence (#3053). Falsified by no `promote` row for the increment.
- **C7. B-2 replays B-1.** B-2 is accepted only with B-1's frozen scenario, by its digest, re-run and passing on
  B-2's candidate. Falsified by a B-2 acceptance without that replay, or with it failing.

**The claim holds** when C1 to C7 hold for both increments in the counted Campaign, and every attempt is reported
(§9). A repair or a retry inside an increment is allowed, and each is reported. A correct first candidate is
acceptable (SIP-0118 R3.5).

### 7.4 Operator actions

**Permitted, and part of the design** (each recorded):
- **The owner rules each proposal at the increment gate:** approve it as it stands, return it with a reason, or
  reject it with a reason. The owner rules through the MacBook session, and the Spark enters the ruling with the
  owner's words.
- **The MacBook lane reads each proposal's scenario before its ruling.** It reads the scenario against the strategy
  skill's baseline rules and tells the owner what it reads. That reading is recorded with the ruling.
  - **It reads for three shapes,** each of which ends the increment at its baseline read:
    - a named assertion using `not_equals` on the element the change adds;
    - a setup action that needs that element;
    - a precondition on that element.
  - **A return on that ground** is a permitted ruling by the owner, and is reported like any other return.
- **The Spark reads each proposal's literal paths against the baseline tree before it sends the change request**
  (amended 2026-11-17, §12b).
  - It names any path in the footprint or a criterion's `paths` that the product doesn't hold and the change doesn't
    say it adds, and that reading goes to the MacBook lane and the owner with the change request.
  - A return on that ground is a permitted ruling by the owner.
  - Globs are read as globs: a glob that matches no held file is named too.
  - **How it flows:** the Spark sends the MacBook lane each change request whole, with its scenario, when the gate
    opens.

**Permitted, and each is an intervention, recorded with its time (ET), who, what, why and which cycle:**
- a person's ruling on an escalated plan gate (§24ee) or on a held cycle's escalation;
- restarting Studio or the worker, or doing anything in Studio by hand;
- taking the box's operator lease (#2287);
- aborting or cancelling the Campaign. This ends counting, and the attempt doesn't meet the claim.

**Not permitted.** Any of these voids the run, and it is reported as void:
- editing a proposal, criterion, scenario, emission or candidate by hand;
- accepting or promoting by hand;
- relaunching a cycle outside the Campaign's own retry and launch-blocked handling;
- changing the goal set, the product's configuration, the product, the deploy or `.env` while the Campaign runs;
- swapping out B-1 or B-2.

**The Spark reads during the counted run.** Its only writes are entering the owner's rulings and, if an intervention
is ruled, carrying it out.

## 8. Step 4: the repair diagnostic, labelled apart

**Its pre-registration stands as the plan and SIP-0118 R3.5 write it:**
- **D1:** a pre-registered, seeded behavioural defect fires on the first `development.develop` attempt, and its
  record names the fault;
- **D2:** the unchanged verifier, the frozen scenario by digest, fails as an executed behavioural failure;
- **D3:** the repair is routed;
- **D4:** the same verifier, by the same digest, passes on the repaired candidate.

It is non-counting by construction (README, "What a diagnostic is").

**The fault: `luau_player_text_drops_a_word`** (#3170, PR #3171, SIP-0118 R5.6; the MacBook lane's):
- **What it does:** a `development.develop` transform, applied to the first attempt only, so the repair's emission
  runs clean. It cuts the last word of the first player-facing text in the emission's first client script, meaning
  a string literal of two or more words on a code line, in a file under a `Client` folder or a `.client.luau` or
  `.local.luau` file.
- **Where it cuts instead:** with no such text in a client script, it cuts the first other Luau source. Specs,
  comments and one-word names are left alone.
- **Where it can be declared:** only on cycles under a profile that names a platform (today `game_dev_roblox`). On
  any other cycle it is refused at create.
- **Its provenance:** no roll produced it, and its `found_in` says so. It is modelled on the skills replay v2's HUD
  case.

**The Campaign:** `2-8-0-repair-diagnostic-campaign.yaml`. One increment, declared through
`policy.proposal_profile: campaign-increment-source-wrong-text`, which is `campaign-increment-source` plus the one
fault declaration. Everything else is the counted run's: the development profile, the squad and no stack.
- **Its objective puts the text in a client script:** a static line of several words on the HUD in the lobby. It
  reads no saved value. It is neither B-1 nor B-2, and the diagnostic runs only after the counted run.
- **Its proposal** is ruled by the Spark under the owner's 2026-11-16 grant for uncounted runs.

**What the diagnostic counts as its pass, stated before it runs:**
- **Pass (D1–D4):** the frozen scenario fails as an executed assertion on the first candidate, a development repair
  is routed, and the same scenario by digest passes on the repaired candidate.
- **The spec-first outcome:** if the developer puts the text in a shared module, a headless spec may meet the cut
  before the scenario does. That is still an executed failure and a routed repair. The record names which verifier
  failed, and it is reported as **a diagnostic that didn't exercise the scenario**, not as the pass.
- **Did not bite:** if the emission holds nothing to cut, the fault's log says `DID NOT BITE`, and the diagnostic
  proves nothing. It is run again, not read, and every run is reported.

**Where and when it runs:**
- on a deploy that carries the fault: the MacBook lane's PR merged, the Spark rebuilt, and verify_loaded's
  `3170-wrong-text-fault` row (read in the development agent's container) ok;
- **after the counted run,** today if the window allows and otherwise in a later window.

Before it runs, an amendment to this file records the merge commit and the deploy.

## 9. What is reported

**Every attempt, for each step:**
- every proposal version, and its ruling and words;
- every cycle and run;
- every task attempt and retry;
- every repair and retry cycle;
- every launch-blocked wait and relaunch (#3045);
- every time the worker was unavailable;
- every escalation;
- every intervention.

**The record** is `docs/plans/verification-sets/2-8-0-demonstration-record.md`. It names, for each reading, the
record it was read from (control log row, artifact, envelope, exposure or worker log), and, by its reason, everything
that didn't execute beside everything that failed (README, "Readouts").
- **The rehearsal's outcome on each item** is reported beside the counted run's, as an earlier attempt at the same
  items, whatever it is.

## 10. What the evidence doesn't cover

The cut record repeats this:
- how the game feels or looks;
- more than one player;
- parts, models or UI built in Studio;
- any effect outside the scenario vocabulary, which here includes B-1's floor half and B-2's duration format, both
  proved headless;
- any Studio version the worker wasn't qualified on;
- that the counted run is the squad's second attempt at these items, the rehearsal's being the first;
- a rate: two increments are one run, not a rate.

## 11. If it misses

The counted Campaign's result stands as read. Whether a second counted attempt runs, on the same items in the same
order and never on easier ones, or the cut narrows under the plan §5 and §6, is the owner's ruling.

## 12. Amendments

### 12a. The full-path gate's first two attempts, and the fixed deploy (2026-11-17, before any rehearsal or counted run)

**Neither attempt counts toward step 1.** Both ran on the window's first deploy (`c31f720a`). Step 1 is the gate
run on the fixed deploy named below. Every attempt is reported (§9).

**Attempt 1:** `cmp_c22ad50e1de0`, cycle `cyc_0c4a22cbc932`, deploy `dep_800a593a0cf2`, 09:09–09:33 ET. Aborted under
the owner's grant for uncounted runs.
- **The plan gate escalated under §24ee.** Both task proposers raised a blocking `must_cover_requirements`
  conflict. The brief lists the footprint's scenario declarations (`.squadops/scenarios/criterion_T1.json`,
  `criterion_T2.json`) among the files modified. The increment's writable list names only
  `src/Client/UI/HUD.luau`.
  - **The Spark's answer**, approving under the grant: the framework places those files
    (`change_request.scenario_criterion_path`, #3044).
  - **The escalation stayed `pending`** after that decision (#3174).
- **Both baseline plays were `not_executed`.** "the scenario acts through Studio's input, which acts only on a Studio
  in front". The Mac was locked (`loginwindow` in front), and the worker ran nothing in Studio.
- **The retry launch was refused at creation preflight.** roblox-studio's rule `footprint_scripts_only` refused the
  framework's own `.squadops/scenarios/criterion_T1.json`. Any retry or repair cycle of a scenario increment would be
  refused the same way.

**Attempt 2:** `cmp_1afaeaaacd46`, cycle `cyc_c75cdc9d6d4c`, deploy `dep_9702e88f5c73` (the same commit), 09:37–10:13
ET. The Mac was unlocked, and Studio was in front, confirmed by the MacBook lane. Aborted under the owner's grant
for uncounted runs, with the owner's "Ok to proceed".
- **Plan validation rejected the first plan,** which named two `qa.test` specs under `tests/` outside the footprint.
  It re-rolled the framing, as designed.
  - **The re-rolled plan escalated on `framed_once` alone.** No brief conflict was raised that time.
- **The play leg worked end to end.** Both baseline plays ran in Studio, 77 s each by the worker's log: claim, sync,
  play, the setup actions, the reader's records and the evidence.
- **Both stopped at setup.** The squad's scenario waits on `gui_state` `visible` of `@player.PlayerGui.TA_HUD`. The
  reader refused it: "TA_HUD is a ScreenGui, not a GUI object". So the named assertions didn't execute, and the
  run failed before development.
  - The model wrote this shape in all three proposals so far (part 5, attempts 1 and 2), although the strategy
    skill's own example observes `Enabled`.
- **The retry launch was refused** by `footprint_scripts_only`, as in attempt 1.

**What the attempts settle:**
- **Studio runs with DataStore off,** so every play starts from the default profile. The game's console says
  "Saving is OFF for this Studio test". §5's lives-count dependence doesn't arise in this place, and B-1 and B-2
  read the same on any save by construction.
- **The worker missed several heartbeat and claim answers.** Seven claim or heartbeat `ReadTimeout`s on the worker,
  each within about 15 s of a run starting on the Spark. The worker recovered each time. One play's claim was
  delayed about 5 s. Recorded as a finding about the runtime's answer time.

**The fix: PR #3175** (the MacBook lane's; it closes #3173 and #3176), merged as `5d374fa5` (2026-11-17 10:31 ET):
1. **The footprint a provider's authority is asked about** is the squad's footprint, without the framework's
   scenario declarations (`execution/product_view.squad_footprint`).
2. **What plan authors are told:** the stages shown the change request, and every plan author's scenario-criteria
   appendix, say that the framework writes each criterion's declaration, that no task is planned for it, and that
   it is no conflict with the brief. `validate_increment_footprint`'s refusal names the files a task may plan
   without them.
3. **The reader** (SIP-0117 R5.25): `gui_state` `visible` on a screen (a ScreenGui, any LayerCollector) reads its
   `Enabled`. `text` on a screen stays unsupported, by name. This is additive: no scenario that ran before reads
   differently.
   - **The provider's version goes to 2.**
   - **The worker was requalified on Studio 0.747.0.7471481** under version 2, on the MacBook, 10:11–10:14:46 ET, by
     `studio_requalify.py`. The scenario's third setup action waits on `gui_state` `visible` of
     `@player.PlayerGui.TA_HUD`, the shape both attempts wrote.
     - Play 1 passed.
     - Then a reset: Studio quit, the place restored from the pristine file, and Studio reopened.
     - Play 2 passed.
   - **The record:** `20261117T151446.571002Z-passed.json`, the first under version 2.
   - **The worker** runs the merge commit's harness from its own checkout, restarted under launchd.

The skills' text is unchanged, so no replay is owed.

**The deploy for steps 1 to 3** is built from `5d374fa5` with `runtime_api` bound, once main's CI on it is green. Its
record id and verify_loaded count (288 expected) go into the run record before gate attempt 3 (§3, check 2). What it runs on (§4)
now includes the worker's side: the provider `roblox-studio` at version 2, the harness at the merge commit, and the
version-2 qualification record above. A change to any of them is a change of deploy. #3171 (the
diagnostic's fault) stays out of it.

**The order and the time rule are unchanged** (§2, §3). The owner's window ends around 12:04 ET. If the counted run
can't start under the time rule, it waits for another attended window, on the deploy that window's clean rehearsal
ran on.

### 12b. The full-path gate's third attempt, and the second fixed deploy (2026-11-17, before any rehearsal or counted run)

**Attempt 3 doesn't count toward step 1.** It ran on the first fixed deploy (`5d374fa5`). Step 1 is the gate run on
the deploy named below. Every attempt is reported (§9).

**Attempt 3:** `cmp_35659d2394a3`, cycle `cyc_9528027ea865`, deploy `dep_ecf661722547` (`c7dfdb9a`, 288 loaded),
worker session `wks-3d5c20973c194d88885613b03c02a3a1` at provider version 2, 10:53–11:12 ET. Aborted under the owner's
grant for uncounted runs.

**What #3175's fixes did on the live path:**
- **The plan gate was approved by the tier unescalated:** no brief conflict over the scenario declarations, and no
  re-roll.
- **Both baseline plays executed their named assertions and failed them,** observed `<absent>`. Both preconditions
  passed (the v2 reader read `TA_HUD`'s visibility). This is §7.3 C3's mechanism working on the real place.

**Finding 1: the framework's `qa.test` overflowed** (#3179).
- The plan held one `development.develop` task and no `qa.test`. So the task plan re-appended the workload's static
  `qa.test` (#439), which has no focus and takes the monolithic prompt: every non-test source and support file.
- On the game's tree that's 181 files, about 2.25 M chars. The task failed before any model call:
  `PROMPT_EXCEEDS_CONTEXT_WINDOW`, an estimated 570,726 tokens against 53,248 available.
- Correction ended the run (`model_limitation`), and the cycle escalated (§10 row 9).
- Every earlier repository-backed Campaign had a criterion test file, so its plan carried a `qa.test`. A
  scenario-only increment is the first with none.

**Finding 2: the path named didn't exist** (#3178).
- The approved footprint named `src/Client/UI/HUD.luau`, as attempt 1's had. The product holds
  `src/Client/UI/Screens/HUD.luau` (26,586 bytes at `0beaac09`) and no `src/Client/UI/HUD.luau`.
- The repository map shown to every author was top-level only (`src/ (137 files)`). The developer's
  `existing_files` was empty, and its prompt never showed the real HUD.
- It wrote a new 42-line module at the named path, inventing its own `TA_HUD`. Nothing requires that module, so the
  candidate play couldn't have passed.
- The Spark approved attempts 1 and 3 under the grant without reading their paths against the tree. The check added
  to §5 and §7.4 above is that reading.

**The fix: PR #3180** (the MacBook lane's; it closes #3178 and #3179), merged as `<COMMIT>`:
1. **The repository map** (SIP-0112 H.36): past 400 paths, binary and generated files fold first, by directory, and
   every other path stays listed with its size. On this game at `0beaac09`: all 234 text files listed, including
   `src/Client/UI/Screens/HUD.luau (26586 bytes)`.
2. **New files are named:** `source_repository.new_files`. A task is told which of the files it names the product
   doesn't hold.
3. **An increment whose plan authors no `qa.test` dispatches none** (SIP-0109 §24eg). A scenario-only increment
   runs `governance.define_done`, `development.develop`, then the plays. A cycle that is no increment keeps the
   workload's `qa.test`.

The worker's side is unchanged: provider version 2, the same harness and qualification record, and no restart.

**Split out, not in #3180, after the demonstration:**
- #3181: a proposal's footprint shown to its approver, with new paths marked.
- #3182: a plan's own `qa.test` on a product can be shown a whole top-level directory.

**The deploy for steps 1 to 3** is built from `<COMMIT>` with `runtime_api` bound, once main's CI on it is green. Its
record id and verify_loaded count go into the run record before gate attempt 4 (§3, check 2). #3171 stays out of it.

**What is expected of attempt 4, read as G3 (context selection) for the first time:**
- the proposal's literal paths are held files, or declared additions;
- the developer's `existing_files` holds the files it edits;
- the composed task plan has no `qa.test`.

These are readings, not gates. G1, G2, G4 and G5 still decide the gate (§5).

**The window:** today's window closed at the gate. The counted run waits for the next attended window the owner names.
