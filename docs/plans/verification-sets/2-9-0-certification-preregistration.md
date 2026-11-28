# 2.9 certification window: pre-registration

**Status: REGISTERED when this file merges, before any run it names** (the 2.9 plan §6, adopted 2026-11-26; D13,
D14). Nothing below is created or launched before the merge. The owner's outside review reads this file once, with
item 12's activation rule (SIP-0117 R5.33), before the window opens (D14). Neither holds the build.

**Written by the Spark lane.** The MacBook lane reads it before it merges, and supplies the facts only its host
holds. Its read of 2026-11-26 (PR #3283) supplied the matched set, the owner's part in cases 3 and 4, and how each
case on the Mac is made to happen with nobody there. What is not built yet, the per-stage instrument's field names
and the bar for comparable host readings, is frozen here by an amendment (§13) before the first measured play.

## 1. What it counts

The 2.9 claim (the plan's opening):

> A supervised Roblox Campaign's execution evidence can be trusted, its cancellation and recovery are deterministic,
> and its worker runs unattended and safely, faster. What a squad can be asked to build is unchanged.

**The claim is read on the certification window alone** (§7), on one final deploy (§4). The rehearsals before it
(§6) are uncounted, and their outcomes are reported beside the window's. A test suite alone doesn't show the claim,
and neither does a rehearsal.

**What the claim is not.** It is not a claim about what a squad can build: the Campaigns here build the two
increments the 2.8 demonstration already built. An accepted increment in this window is evidence that the path
ran, and no new evidence about the models.

**The four parts, and the cases that read each:**

| Part of the claim | Read by |
|---|---|
| Execution truth: a recorded result says what ran, what failed, why, and under which qualified Studio | cases 1, 5, 7, 9, 10, 11, and the readings of §8 |
| Operational safety: an abort, a cancel, a pause, a lease and a recovery behave deterministically | cases 6, 8, and §8's views and hand-off readings |
| Environment reliability: a dedicated worker plays without a person keeping Studio in front, and a person is never overridden | cases 2, 3, 4 |
| Measured throughput: the median play at least 20% faster on a matched set, or the record says why not | cases 12, 13 |
| Unchanged: what a squad can be asked to build | case 14 |

## 2. The order

1. **The final deploy** (§4), once every 2.9 item's code is on main.
2. **The opening checks** (§3), each recorded.
3. **The rehearsals** (§6), uncounted, until one passes whole with no new seam finding.
4. **The window's cases** (§7). Cases 1, 2 and 5 to 14 need nobody at the Mac. Cases 3 and 4 need the owner there,
   for about fifteen minutes, and case 4 is the last of that sitting.

**The measured sets (case 13) are the exception to "one final deploy", by the plan's own order** (item 13: measure,
then decide, then build). The before set is taken ahead of the window, as soon as the per-stage instrument is on
main and on the worker and §13's amendment is in, with none of the throughput change on the worker. The after set
runs in the window. Each runs with nothing else on the Mac, never between two other cases. What makes them a
matched pair, and what happens when they aren't, is case 13's.

**A deploy that a rehearsal's finding changes is superseded** (the verification sets' README). The fix merges, the
deploy is rebuilt from main, the opening checks are read again, and the rehearsal runs again. No counted case runs on
a superseded deploy.

## 3. The window

**The window is the owner's to declare** (D12). The owner writes the dedicated window's four values in the worker's
settings on the Mac (`docs/ops/STUDIO_WORKER_RUNBOOK.md`), inside the takeover hours the owner named to the MacBook
lane. No lane writes them. The window opens at the declared start, on a deploy whose opening checks all read, and
it closes at the declared end.

**Checks before anything plays, each recorded with its time (ET):**

1. **Remote execution is bound.** The Spark's `SQUADOPS__REMOTE_EXECUTION__PROVIDER` is `runtime_api`, for the
   window and its rehearsals, and is set back to `none` when the window closes (D11).
2. **What loaded.** `verify_loaded.py` reads every row ok on the final deploy, and the deploy record's id is written
   into the window's record with its commit.
3. **The worker is serving.** `squadops workers list` shows the MacBook's worker online, serving `roblox-studio`
   `play_scenario`.
4. **The Studio the worker is proved on is the one running.** The pin, as the MacBook lane requalified it on
   2026-11-26 at 22:15 ET, on main at `3e4cc511`:
   - Studio `0.748.0.7481526`, channel `production`;
   - tools `41:8f661f40cfd0081134c8ad488a48058f7a56fa5afe05d35c2804a10dc2502899`;
   - the qualification record `edcbf9c10a7257c318099fac246866de1950ebaf21ec1dfaa0d560d9f515953d`, schema
     `squadops.studio-qualification/3`;
   - the qualification scenario `qualify-screen-visible.json`, kept on the Mac beside the place. Its frozen
     digest, the canonical text under `roblox-studio/1` that the qualification record carries, is
     `sha256:4c660da5…88bf93`. The file's own bytes hash to `sha256:0d554807…cd9df`, so a hash of the file is not
     expected to match the frozen one. Its content is the product's and is not reproduced here.

   **The tool list is read again after a fresh launch of Studio, before the first play.** It moved at three launches
   in a row at one Studio version (2026-11-20 to 2026-11-26), with nothing installed. If the digest differs from the
   pin, the MacBook lane requalifies before anything plays, the new record's digest is written here as an amendment
   (§13), and R5.31's reading of which tools changed is recorded with it. A play on a Studio that differs from its
   proof is refused by the worker (R2.4, R5.29), so this check saves a refusal; it is not what prevents the play.
5. **The Mac is quiet** (item 13). The MacBook lane records the host's readings at the window's start and end, and
   at each measured set's start and end, with `scripts/dev/host_quiet_reading.py` (to be built, §4). Through the
   window the Mac runs no tests, no containers and no model:
   - the Mac's own SquadOps stack is stopped by the MacBook lane before the window (`docker compose stop`, from
     its main checkout, the compose file untouched) and started again after the close;
   - `ollama ps` reads empty.

   Two things keep running there: the MacBook lane's session, and the worker, as its installed service. The
   worker's checkout isn't pulled or switched until the window closes, but for the one switch case 13 allows.
6. **The front guard is not running.** With it running, case 2 would show the guard and not the runner, and case 3
   couldn't pass.
7. **The dedicated settings are written, by the owner.** The MacBook lane confirms that the four settings are
   present in the worker's settings and that the owner wrote them. The values themselves are not recorded here or
   in any result: a result records only whether an activation happened and why not (R5.33).

**The owner's own apps.** For the measured sets (cases 12 and 13) the owner's apps are closed, and the readings of
check 5 show it. For the other cases they are recorded and need not be closed: case 2 needs an app other than
Studio in front.

**When the window closes:** at its declared end, or at the first thing that needs the owner outside cases 3 and 4.
The provider goes back to `none`. A Campaign still running at the close is aborted by the Spark lane, which is an
intervention (§9), and its case is reported as not completed.

## 4. What it runs on

**One final deploy.** Built from main at a commit that holds every 2.9 item, the dependency move (item 14) among
them. Its commit, its deploy record id and its `verify_loaded` row count are written into the window's record when
it is built. Main may move after it only by documents, and any such move is named in the record.

**The product:** `prj-z-tower-ascension`, a private copy, at baseline commit `0beaac09`, Development Configuration
revision 3. The Campaigns here start from that baseline: nothing the 2.8 demonstration accepted was contributed
to it.

**The goal set:** revision 1, the owner's approved set of 2026-11-17. Its backlog in order: B-1, the lobby hint;
B-2, the session clock. No goal, item or constraint is added for this window.

**The rest:**
- **The squad:** `game-dev-roblox`, under the development profile `game_dev_roblox`.
- **The worker:** the MacBook's, serving `roblox-studio/1`, on the pin of §3.
- **Who rules the gates** (D13): the Spark lane, signed in as `squadops-supervisor`, the least-privilege identity
  D8 asks for. It rules an increment's gate and starts, pauses and aborts a Campaign. It can't resume an escalation
  or a limit's pause: those are the owner's (D16), and a Campaign that reaches one waits.
- **Held-out separation:** none is pinned. The scenarios are public QA verification, and no role gains held-out
  access.

**What must be on the final deploy, beyond the plan's items,** each built before the window and named here so a
missing one stops the window at check 2:
- a request profile for case 9: the 2.8.1 row-8 diagnostic's (`campaign-increment-source-client-stops`, the fault
  `luau_client_throws_at_start`) with `max_correction_attempts` at the standard profile's 3 in place of 0;
- a fault and a request profile for case 10: a client script that waits in a loop where the engine loads it, and
  raises and logs nothing, so the setup is never met and no script error is named;
- the Studio provider's half of R5.32 (it names script errors and its environment), without which no Studio play
  can be attributed and case 9 can't pass;
- item 13's per-stage instrument and its isolation tests (#3250), and `scripts/dev/host_quiet_reading.py`, without
  which cases 12 and 13 can't be read.

The first two are built under #3284. The last two are the MacBook lane's.

## 5. The bar for a ruling

The Spark lane rules each proposal at the increment gate by the bar of the 2.8 demonstration's amendment 12e, the
same for every ruling:
- **It approves** a proposal whose named assertions fail on the baseline and can pass only when the increment
  works.
- **It returns** one whose check would pass on broken work, naming the defect, mapped to its §24bi class in the
  ruling's notes.
- **A rejection stays the owner's.**
- **Before it rules, it reads** each scenario for the three shapes that end an increment at its baseline read (a
  named assertion using `not_equals` on the element the change adds; a setup action that needs that element; a
  precondition on that element), and each literal path in the footprint and the criteria against the baseline tree.
  The MacBook lane reads each change request first when it is free to, and its reading is recorded with the ruling.
- **Each ruling's notes stand alone:** they cite what was read, and say the Spark lane ruled under D13.

A ruling is a permitted action, not an intervention. The window's record says, beside each, who ruled.

## 6. The rehearsals (uncounted)

A rehearsal runs cases 1, 2, 5, 6, 8, 9, 10 and 11 on the final deploy, with nobody at the Mac. It doesn't run
cases 3 and 4, which need the owner, or cases 12 and 13, whose plays are measured once.

**The exit rule,** stated before the first launch: one rehearsal in which every case it runs meets its pass
condition (§7), on one deploy, with no new seam finding. A finding is a defect in a seam a 2.9 item touched, or a
reading that couldn't have seen its own miss. A defect in the increment a cycle built is the cycle's and doesn't
reset the loop.

**The budget:** two rehearsals. The cut record reports how many it took, each superseded deploy's commit, and what
each rehearsal found.

**Nothing carries from a rehearsal into the window.** Each case in the window is a new Campaign from the baseline,
and the place is reset between Campaigns by the worker, as it is between plays.

## 7. The window's cases

Each case names what is done, what is expected, what passes, what fails, the evidence it must leave and the pins
that evidence carries, how a failure is attributed, and the recovery expected. Every result named below carries the
Studio's identity as played and as qualified, the place's baseline digest, the harness digests, the source revision,
the play session, the environment and who served it (`ran_with`; R5.29, R5.32, R5.34).

**Case 1. A normal Campaign, unattended.**
- **Done:** a Campaign on goal set revision 1, B-1 then B-2, started by the Spark lane with nobody at the Mac.
- **Expected:** both increments are accepted, each on a frozen scenario that executed and failed on the accepted
  baseline and passed on the candidate, with B-1's scenario replayed and passing on B-2's candidate.
- **Passes when** the 2.8 demonstration's readings C1 to C7 hold for both increments, and no play needed a person.
- **Fails when** any reading doesn't hold, or a person acted on the Mac for a play.
- **Evidence:** the Campaign's control log and ledger, each cycle's baseline and candidate readings, and each
  `criterion_head_check`.
- **Attribution:** a candidate that fails its scenario is the candidate's, and its repair is the design. A play
  refused for the worker's own state (`tool_unready`, `unavailable`) is the environment's, retried by rows 10 and
  11, and never read against the candidate.
- **Recovery:** the Campaign's own retries and repairs. A limit's pause waits for the owner.

**Case 2. The front lost and recovered.**
- **Done:** during case 1's Campaign, or one like it, the MacBook lane puts another app in front
  (`open -a Finder`) while no operation is claimed, records the time, and touches nothing else. A fresh launch of
  Studio brings it to the front, so after any reset the case doesn't happen by itself. The command moves no
  keyboard or pointer input, so the idle reading is still a true one. The next play that uses Studio's input is
  then claimed with that app in front.
- **Expected:** the worker reads the six conditions, brings Studio forward once, and the play runs.
- **Passes when** the play's result reads `front.activated` `true` and `front.was` `other`, with `front.idle_s` at
  or over the threshold, and its assertions executed.
- **Fails when** the play is refused with the conditions holding, when Studio is brought forward more than once for
  one operation, or when the result names an app.
- **Evidence:** the result's `front.*` keys and the play log.
- **Attribution:** a refusal here is the worker's, by its `front.refused` reason.

**Case 3. Human input prevents an activation** (the owner present).
- **Done:** the owner can't know the moment a play is claimed, so the input covers a span. What the owner is
  asked: "With another app in front, sit at the Mac and keep using it, typing or moving the pointer every few
  seconds, from when the MacBook lane says a play is queued until it says the play was refused, then stop."
- **Expected:** no activation. The play is refused, and the increment is retried later.
- **Passes when** the result reads `not_executed`, `tool_unready`, `front.activated` `false`, and `front.refused`
  one of `idle_below_threshold`, `input_before_activation` or `input_during_activation`; Studio was not brought
  forward, or, for `input_during_activation`, nothing was played and no input was sent. The third reason can't be
  produced on purpose; it passes if it is what happened.
- **Fails when** Studio takes the front while the owner is using the Mac and a play proceeds.
- **Evidence:** the result, and the owner's own account of what they saw, recorded in their words.

**Case 4. A locked screen is refused** (the owner present; the last of the sitting).
- **Done:** a play that uses input is claimed with the screen locked. What the owner is asked: "With another app
  in front, lock the screen (Control-Command-Q) and step away. When the MacBook lane says the play was refused,
  come back, check that the screen is still locked, and unlock it yourself."
- **Expected:** a refusal. Nothing unlocks, dismisses or works around the lock.
- **Passes when** the result reads `not_executed`, `tool_unready`, `front.refused` `locked`, and the screen is still
  locked when the owner returns.
- **Fails when** anything is played, or the lock state changed without the owner. Which app a locked screen reads
  as in front hasn't been seen on this Mac. If Studio reads as in front, the play could proceed on a locked screen,
  and this line is what catches it.
- **Evidence:** the result, its `front.was`, the play log, and the owner's account of the screen on their return.
- **Recovery:** the owner unlocks; the increment is retried by the Campaign.

**Case 5. A Studio restart and requalification.**
- **Done:** between plays of a Campaign, while no operation is claimed, the MacBook lane stops the worker's
  service and starts it. The worker's own start-up reset quits Studio, restores the place and reopens it, and its
  first claim holds the running Studio to its proof. A reset run by hand beside a serving worker would race the
  worker's claims, and is not what is done.
- **Expected:** the tool list is read after the launch. If it is the pin's, plays resume. If it moved, every play is
  refused as not proved until a requalification passes, and then plays resume on the new record.
- **Passes when** no play is credited on a Studio that differs from its proof, each refusal reads `tool_unready`
  naming how the Studio differs, and the first play after the requalification names the new record in
  `qualified_by`.
- **Fails when** a play completes with `played.*` differing from `qualified.*`.
- **Evidence:** the qualification records, R5.31's `tools_changed`, and the results either side of the restart.

**Case 6. A worker restart and lease recovery.**
- **Done:** the worker's service is stopped while it holds an operation's lease, and started again. This is what
  sets it apart from case 5, where nothing is claimed.
- **Expected:** the lease runs out and the operation is requeued or reads `interrupted` on its last attempt. The
  restarted worker reconciles before it claims, and the operation runs once.
- **Passes when** exactly one accepted result exists for the operation, and the increment's outcome is the one a
  run without the restart gives. A stopped service sends no late result; if one arrives, it is refused by its
  fence.
- **Fails when** two results are accepted, or the abandoned attempt changes an outcome.
- **Evidence:** the operation's attempts and refusals, the worker's sessions, and the restarted worker's log line
  for its start-up reset, which is where "reconciles before it claims" is read.

**Case 7. The QA agent's capability missing** (a deliberately misconfigured diagnostic, #3235).
- **Done:** the QA agent's container is recreated by compose's own `up` for that one service, with the provider
  set to `none` in that command's shell, which is the shape #3235 was found in. The runtime's stays bound, and the
  compose file and `.env` are unchanged. A Campaign is started. After, the container is recreated the same way
  without the variable, and the agent's report is read to bind `runtime_api` again before any other case runs.
  A squad profile can't show this: every agent container takes the provider from the one `.env`, so no agent on
  the box reports a different one until a container is recreated apart.
- **Expected:** the cycle is refused at creation, naming the agent that can't ask for a play.
- **Passes when** nothing is queued or played, the refusal names the QA agent and what it binds, no cycle is
  created, and the Campaign's control log records the refused launch as its own handling of a launch it can't
  make.
- **Fails when** a cycle is created and reaches a play it can't ask for.
- **Labelled apart:** a diagnostic, never counted as a Campaign outcome.

**Case 8. An abort during a play** (#3236).
- **Done:** the Spark lane aborts a Campaign while one of its plays is running in Studio.
- **Expected:** the worker stops the play, resets Studio, and answers `interrupted`, naming what it had run on.
  Nothing new is queued for the Campaign, and a result that arrives after the abort is kept as the late result and
  is no evidence.
- **Passes when** every operation the Campaign owned is settled, none is accepted after the abort, the abort's
  answer counts the operations it reached, and the next Campaign's first play starts from the pinned baseline.
- **Fails when** an operation is accepted after the abort, or the next play sees the aborted play's state.
- **Evidence:** the abort's answer, the operations' states and late results, and the next play's
  `place_baseline`.

**Case 9. An attributable setup failure, repaired in the run** (#3200; a diagnostic).
- **Done:** a Campaign under case 9's profile: the first development emission carries a client script that raises
  where Roblox loads it, with in-run correction on.
- **Expected:** the candidate's play reads `setup_failed`; the attribution reads all six conditions holding, with
  the script error named in a file the candidate changed; one correction is dispatched; the repaired candidate's
  play executes the same frozen scenario and passes; the increment is accepted.
- **Passes when** `setup_attribution.json` reads `attributed` `true` and `repair` `dispatched`, the check rows of
  the first play stay not executed, exactly one such correction was spent on the task, and the scenario digest is
  the same before and after.
- **Fails when** an unexecuted assertion is recorded as an executed failure, when a second correction is spent on
  the same task for the same cause, or when the repair is accepted on a different scenario.
- **Labelled apart:** the fault is injected, so the outcome is no evidence about the models.

**Case 10. An ambiguous or environmental setup failure, not corrected** (a diagnostic).
- **Done:** a Campaign under case 10's profile: the candidate's client waits in a loop where the engine loads
  it, and raises and logs nothing. A stall inside `WaitForChild` was not chosen: Roblox logs an infinite-yield
  warning for it, with a stack. The Studio half of R5.32 reads a warning as no script error, and its amendment says
  so; the fault doesn't lean on that.
- **Expected:** the candidate's play reads `setup_failed`; the attribution is kept and reads condition 3 not
  holding (no script error named); no correction is dispatched; the cycle ends `blocked_unverified`.
- **Passes when** `setup_attribution.json` reads `attributed` `false`, `repair` `not_dispatched`, and the run made
  no development repair.
- **Fails when** the run repairs a candidate nothing faulted, or the play reads as a failed criterion.

**Case 11. The 2.8.1 row-8 diagnostic, with in-run correction off.**
- **Done:** the 2.8.1 diagnostic's Campaign as it ran then (`2-8-1-row8-diagnostic-campaign.yaml`:
  `max_correction_attempts` 0).
- **Expected:** the candidate's plays read `setup_failed`; the attribution may hold, and reads `not_dispatched`
  because the run has no correction; the cycle ends `blocked_unverified`; the Campaign routes §10 row 8; the repair
  cycle is accepted.
- **Passes when** the control log reads rows 5, 8 and 3 as it did on 2026-11-19, and the repair cycle's route names
  its ending (`single_workload_ended`, item 3).
- **Fails when** the run fails on an exhausted correction budget, or row 8 isn't reached.

**Case 12. Isolation across plays** (item 13). **Case 13. The matched throughput measurement, before and after.**
- **The matched set:** one scenario, `qualify-screen-visible.json`, at the frozen digest of §3's check 4, played
  on the pinned baseline, **20 plays in each set**. With 20, the p95 is the 19th value; with fewer it is the
  maximum. It uses an input action and reads two client assertions, and took 98 to 100 s a play on 2026-11-26.
  - **Why one scenario:** it is the only frozen scenario whose tree is the baseline itself. Every other is an
    increment's, frozen against a candidate tree that the baseline isn't.
  - **Beside it, uncompared:** each stage's time for every play of case 1, which are plays of real increments.
- **The before set** is taken ahead of the window (§2): the instrument on the worker, none of the throughput change.
  It is also the plan's first step, the measurement that decides whether anything is built.
- **The after set** runs in the window, on the final deploy.
- **A matched pair** is two sets on one qualification record, by its digest, with comparable host readings, shown
  side by side. If either differs when the after set is due, the before set is taken again in the window's
  sitting, on the worker's checkout at the first before set's commit. That is the one switch of the worker's
  checkout the window allows, made by the MacBook lane and recorded with both commits. If the worker at that commit
  can't serve the final deploy, the pair is unmatched, and case 13 is recorded as unsuccessful, with why.
- **Read where:** claim-to-completion and delivery on the Spark's runtime, with the provider on. Each stage's
  time from the worker's own evidence item for the play, never from `ran_with`.
- **The host readings,** one JSON document from `scripts/dev/host_quiet_reading.py` at each set's start and end:
  the load average; free, active, wired and compressed memory and the free percentage; the models loaded; whether
  Docker answers and how many containers run; the memory and CPU of Studio and of the worker; and every other
  process as a count and a total, never by name, since the record goes on a public Release.
- **Frozen by amendment (§13) before the first measured play,** because they don't exist yet: the instrument's
  field names, once #3250 is built; the bar for "comparable", once a first host reading exists to set it from;
  and each isolation test with what it reads.
- **Case 13 passes when** the median claim-to-completion time on the matched set is at least 20% lower after than
  before, scenario outcomes are unchanged play for play, the isolation tests pass, and no play is a new false
  success or false failure.
- **A miss is recorded as unsuccessful,** even when the instrument and the change work (D6). The claim allows it
  on the record: "or the record says why not". If the measurement shows no stage could yield the target, nothing
  is built, and the record says so with each stage's time.
- **Case 12 passes when** each isolation test reads no leakage: module and global state; GUI and player state;
  instance attributes and workspace changes; the candidate's source revision; a failed play's residue and an
  interrupted play's; a baseline, candidate, baseline sequence; state after a Studio restart and after a worker
  restart; a competing operation.

**Case 14. The existing stacks' shakeout pair, on the final deploy.**
- **Done:** one cycle on each existing stack (FastAPI with React, and Next.js), as each release's cut shakeout
  runs them.
- **Expected:** each completes as the 2.8.1 cut's pair did.
- **Passes when** each pair member's verdict and check set match what the 2.8.1 pair read, with any difference
  named and attributed. Three things are read in particular: the dependency move (item 14) changed no outcome; no
  prompt of these stacks changed (items 8 and 9 hold them byte-identical by tests, and this is the live read);
  and the lint reading is taken on evaluator image `…ruff0.17-eslint10.12-9`, a new series that is compared with
  no reading on `-8` or earlier.
- **Fails when** a verdict differs for a cause in a 2.9 item.

## 8. Read against the window's own records

Where a live case would add nothing, a wiring test holds the behaviour, and the window's records are read for it:
- **The cycle views agree (item 3):** `scripts/dev/read_cycle_views.py prj-z-tower-ascension` exits 0 over every
  Roblox cycle, the 2.8.1 repair cycles among them and every cycle of this window.
- **An accepted hand-off's terminal state (item 5):** on every QA task of the window that was handed off, the
  Prefect task run, the activity, the task's events and the failure count agree with the verdict.
- **A required artifact's retrieval failure (item 4):** no run of the window reads a recorded artifact as absent and
  goes on; any `gate_input_unavailable` or `infrastructure_failed` ending names its artifact.

**Negative assertions.** Across the window, none of these happens. Each is read from the records, and one
occurrence fails the window:
- an operation is accepted after an abort;
- an environmental refusal reads as a candidate failure;
- an unqualified Studio play is credited;
- contaminated state reaches another play;
- required context goes missing silently;
- an unsupported result is promoted;
- missing evidence reads as success.

**Carried from 2.8.1:** #3174, read on the first escalation a person answers in the window; and #3218's
threshold over the longer window: no worker request over 2 s, and none timing out.

## 9. Operator actions

**Permitted, and part of the design** (each recorded):
- the Spark lane's rulings at the increment gate, by §5's bar;
- starting, pausing and aborting a Campaign as `squadops-supervisor`. Case 8's abort is the case itself;
- the MacBook lane's reads of the host before any takeover run: the idle counter and the lock;
- the owner's part in cases 3 and 4.

**Permitted, and each is an intervention,** recorded with its time (ET), who, what, why and which cycle:
- the owner's answer to an escalation or a limit's pause;
- restarting Studio or the worker outside cases 5 and 6, or doing anything in Studio by hand;
- taking the box's operator lease;
- an abort outside case 8, which ends that case as not completed.

**Not permitted.** Any of these voids the case it touches, and it is reported as void:
- editing a proposal, criterion, scenario, emission or candidate by hand;
- accepting or promoting by hand;
- relaunching a cycle outside the Campaign's own retry and launch-blocked handling;
- changing the goal set, the product's configuration, the product, the deploy, `.env` or the worker's checkout
  while a case runs, except case 7's one override;
- publishing anything from Studio, opening any place but the local test place, or writing to the real product.

**A lane's pause.** A session stopped by its usage limit leaves a Campaign waiting at its gate, which is safe. The
gap is recorded as the operator's delay, with its start and end. It is never read as the candidate's failure or
the worker's. A ruling bound that runs out during such a pause is the supervisor's lateness, and the Campaign's own
handling of it is reported.

## 10. What is reported

For the window and, beside it, for each rehearsal:
- each case's outcome against its pass condition, with every attempt;
- failures attributed to the candidate, against ambiguous or environmental ones, each with its attribution;
- unattended outcomes and recoveries, and every intervention;
- cancellation correctness: operations reached, settled, and late results kept;
- worker latency and lease renewals;
- plays per hour, with the median and p95; plays per accepted increment;
- repair success and exhaustion;
- contradictory lifecycle readings, which §8 expects to be none;
- escalations, and the operator's delays;
- what was unverified or deferred, including every play not executed, by reason.

Non-execution is counted beside failure in every readout.

## 11. What the evidence doesn't cover

- **One Mac, one Studio version on one channel, one game.** Nothing here shows reliability across machines, Studio
  versions or games.
- **A person at the Mac in ways case 3 doesn't act out:** input the idle counter doesn't count, a person reading
  the screen without touching it, a second user session.
- **The models.** The increments are ones already built once, and two cases inject their fault.
- **A reboot that renumbers the Spark's GPU card** with the bootstrap's refresh installed (#3251): not in the window.
- **Unattended supervision.** The window certifies unattended worker execution. The gates are ruled by a lane's
  session under D13, and an external supervisor's authority is a later line's question (D8).

## 12. If it misses

- **A case fails for a defect in a 2.9 item:** the fix merges, the deploy is superseded, and the rehearsal loop
  starts again from §2. The cut record reports it.
- **Case 13 misses its target:** recorded as unsuccessful. The claim's fourth part then reads "the record says why
  not", and the cut is not held for it (D16).
- **Any other miss of a done-when** is the owner's to dispose (D16).

## 13. Amendments

Each is added here before the run it changes, with its date, what changed, the evidence and who ruled.
Still expected: if check 4 finds the tool list moved, the new pin.

### 13a. The measured sets: the instrument, the host's bar, and how a set is played and read (2026-11-27)

**What changed.** Case 13 left three things to an amendment before the first measured play. This freezes two of
them, and fixes how a set is played and read. Nothing measured has been played.

**Who ruled.** The Spark lane, which the plan's item 13 has freeze the matched set. The MacBook lane built the
instrument and took the readings the bar is set from.

**The evidence.**
- The instrument is on main (PR #3286, `229c25fa`). One live play with it took 97.2 s, and its fifteen stages
  summed to 97.17 s, so the stages cover a play.
- In that play the place's non-script state was read three times, 67.7 s of the 97.2 s. A stage could yield the
  target, which is the plan's second step. It is one play and not the measurement.
- A quiet reading of the Mac (2026-11-27, 01:21 ET, its stack stopped for six minutes, no model loaded, Studio
  and the worker not running): load 1.17, 2.07 and 2.68 over 1, 5 and 15 minutes; free memory 80%; no container;
  every other process together at 65.5% CPU. A reading one minute after the stack stopped still read 3.75 and
  157.5%.

**1. The instrument's fields, frozen as merged.** Each completed play carries an evidence item `stages.json`,
schema `squadops.play-stages/1`:
- `stages`: seconds for each stage that ran, among `session_open_s`, `proof_s`, `front_s`, `identity_s`,
  `place_state_s`, `sync_s`, `marks_s`, `baseline_before_s`, `play_start_s`, `scenario_s`, `player_s`,
  `console_s`, `stop_s`, `baseline_after_s`, `read_back_s` and `reset_s`. A stage that didn't run is absent.
  A stage timed more than once in a play is the sum: `console_s` is one console read at #3286, and three once
  R5.32's Studio half (PR #3288) is on the worker;
- `waits`: each of the scenario's own waits, in seconds;
- `transactions`: how many times the transaction ran. It is 2 when the place had drifted and the play began
  again after a reset, and each stage is then the sum over both.

**2. How a set is played.** By `scripts/dev/measured_play_set.py play`, on the Spark, inside its runtime's
container:
- **20 plays, one at a time, back to back,** each queued when the one before it has its result. One attempt
  each: an interrupted play is recorded as it ended and is not retried.
- **Each play is queued on the runtime's worker registry** with the request a cycle's own verification builds:
  every text file of the pinned commit `0beaac09`, and the frozen scenario of §3's check 4. The tool refuses a
  scenario file that doesn't freeze to that digest.
- **The set owns its plays under its own name.** A measured set is no cycle, so nothing but the tool can cancel
  them, and it does on any exit for every play it queued that has no result.
- **A set is whole or it is taken again.** A set that stopped early, or in which any play didn't complete, is
  not a measured set. It is recorded with what happened, and the whole set is played again from a start reading
  that meets the bar. No play is patched in.
- **A play that began again after a drift is counted as it ran,** and the set's record says how many did.

**3. What is read, and from where.**
- **Claim to completion,** the time the 20% target is read on: the runtime's own record of each operation, from
  its attempt's claim to its settlement. The tool's own polling times nothing.
- **Each stage:** the play's `stages.json`.
- **Outside the stages:** claim to completion less the stages' sum. This narrows §7's "claim-to-completion and
  delivery": no record times delivery apart, so what is read is the worker staging the tree, the result's
  delivery and the runtime's acceptance, together.
- **The median and the p95** of claim to completion (the p95 is the 19th of 20 by nearest rank), plays per hour
  over the set's own span, and each stage's median.
- **The pair** is read by `measured_play_set.py compare`. It is unmatched, and says why, when the two sets
  differ in scenario, commit, staged revision or number of plays, when either names no single qualification
  record or they name different ones, or when either stopped early or holds a play that didn't complete. It
  names every play whose outcomes differ between the sets.

**4. The host's bar, which makes two sets' readings comparable.** Read by `measured_play_set.py host-bar` from
a `host_quiet_reading.py` document (schema `squadops.host-quiet-reading/1`). A reading that wasn't taken misses
the bar. Docker answering that it isn't running meets "no container running". A Docker that didn't answer in
time misses it, since a hung daemon can still have containers at work.
- **At a set's start** (the 1-minute figure is amended to 2.5 by 13d): the 1-minute load under 2.0 and the
  15-minute load under 3.0; free memory at 70% or
  more; no container running; no model loaded; every process that isn't Studio, the worker, Docker or Ollama
  together under 100% CPU.
- **At a set's end:** no container running and no model loaded. A set of plays raises the load and Studio's
  memory by itself, so those are recorded and not held to a bar.
- **A set whose start reading misses the bar waits** until one meets it. It is not played and explained after.
- **Two sets are comparable** when both start readings and both end readings meet their bars. All four are
  shown side by side in the record.

**5. When the before set is taken.** After this amendment is on main, with the worker's checkout on main at
or after the merge of R5.32's Studio half (PR #3288), the Spark's deploy rebuilt from main so that each result
names who served it, and the Spark's provider set to `runtime_api` for the set. The worker's commit, the
deploy's record id and the four host readings are written into the set's record beside the tool's own.

**The two sets differ by the throughput change and nothing else on the worker.** That is why the before set
waits for #3288: it adds two console reads to every play, and a before set without them would credit their
cost to the change. Any other change to the worker's play path that merges between the sets is named in the
record with its measured cost, or the before set is taken again after it.

**Not built, said deliberately:** a separate timing of delivery. **Still to come, by a later amendment:** each
isolation test of case 12 with what it reads. They read the throughput change, which isn't designed until the
before set is in.

### 13b. Case 12's isolation tests, the change they read, and how the worker runs for both sets (2026-11-27)

**What changed.** 13a left case 12's tests to a later amendment. This names them, before any play they read.
It also records the before set, the change it led to, and one condition on the pair that 13a didn't state.

**Who ruled.** The Spark lane wrote the tests and the condition. The change is the MacBook lane's design, agreed
between the two lanes under the owner's grant of 2026-11-26, and recorded as SIP-0117 R5.36 in the PR that
builds it.

**The evidence.**
- **The before set** (2026-11-27, 02:56 to 03:30 ET; issue #3250): 20 of 20 plays completed, every assertion
  passed, one qualification. The median claim-to-completion time was 98.339 s and the p95 99.230 s. The place's
  non-script state was read three times a play, 22.6 s each, 67.8 s of the 98.3 s. The scenario itself took
  1.8 s, and 0.447 s fell outside the stages.
- **The change:** the read after the sync and before play is removed, and the read after play is held to the
  pin check's own reading. It projects a median near 75.7 s, a 23% cut. Only the after set can say.
- **A dry run of the sequence** against the Spark's runtime built its three trees from the pinned commit as three
  revisions and froze its four scenarios under the reader's vocabulary.

**1. The pair's worker runs the same way for both sets.** The before set's worker was a plain process started
from the main checkout, with no launchd service. The after set's worker is started by the same command, from the
same checkout at the later commit, with the same environment. If the after set has to run under a service, the
before set is taken again in that sitting under the service. §3's check 5 says "as its installed service" of the
window's worker; for the measured sets this condition governs.

**2. What the change must still do** (the MacBook lane's tests, and the after set):
- a change to the place made while the sync runs is refused, naming the window;
- a change through play is still refused;
- a place that isn't its pin before the sync is still caught before anything is written, and the play begins
  again after the reset;
- a place that lacks a folder the sync would create is refused before anything is written, by the folder's name,
  as the Mac's state and not the work's;
- every completed play names the pin's place baseline, in the unit tests and across the after set's 20 plays;
- the after set's 20 plays read the same outcomes as the before set's, play for play.

**What the change gives up, said deliberately:** a change to the place made during the sync and undone before
play ends was refused, and now passes. It takes something acting on the place twice inside one play. In the
other direction, a change made during the sync and left in place went unseen, and is now refused.

**3. The isolation sequence,** played by `scripts/dev/play_isolation_sequence.py play` on the Spark, through the
runtime, as the measured sets are. Ten plays of three trees, each built from the pinned commit:
- **the baseline,** untouched;
- **the marked tree:** the baseline plus marks its first server script and first client script leave when they
  start (a workspace attribute, a value instance, a `_G` key on each side, a key in a module's table, a screen
  under the player) and one module no other tree holds;
- **the reading tree:** the baseline plus a reader that reports, for each mark, `present` or `absent`. The marked
  tree carries the reader too, after its marks.

The marks and the reader are the tool's own lines, named `squadops_*`. They exist only in a play's staged tree
and are never written to the product.

| # | Test | Passes when |
|---|---|---|
| 1 | The marks are made, and the reader sees them | A play of the marked tree reads all seven marks `present`. Without this, `absent` anywhere proves nothing |
| 2 | Nothing is left after a completed play | The reading tree, played next, reads all seven `absent` |
| 3 | The failed play's setup did fail | A marked play whose setup can't be met reads `setup_failed` on every assertion |
| 4 | Nothing is left after a failed play | The reading tree, played next, reads all seven `absent` |
| 5 | The cancelled play was interrupted | A marked play cancelled 30 s after its claim reads `interrupted` |
| 6 | Nothing is left after an interrupted play | The reading tree, played next, reads all seven `absent` |
| 7 | The baseline reads the same before and after the candidates | The registered scenario passes on the baseline first and again eighth, with the same outcomes and the same staged revision |
| 8 | Two plays queued together run one after the other, each on its own tree | A marked play and a reading play are queued before either is claimed. The marked one is claimed first, the reading one is claimed only after it settles, and it reads all seven `absent` |
| 9 | Every completed play read one place baseline | Each completed play's `place_baseline` is named, and all are the same |
| 10 | Every play ran the revision asked, and each tree is its own | Each completed play's `ran_with` names the revision its request staged; each tree staged as one revision; no two trees as the same |

**How the plan's list is read by it:** module and global state by the `_G` and module-table marks; GUI and
player state by the screen; instance attributes and workspace changes by the attribute and the value instance;
the candidate's source revision by test 10 and by the module only the marked tree holds; a failed play's residue
and an interrupted play's by tests 4 and 6; the baseline, candidate, baseline sequence by test 7; a competing
operation by test 8. **State after a Studio restart and after a worker restart** is read by the window's cases 5
and 6, and by the play after test 5's cancel, which follows the worker's own reset of Studio.

**Case 12 passes when** all ten tests hold on one whole sequence, with section 2's readings. A sequence that
stopped early is not a pass whatever its tests read, and a test whose plays weren't played is not read.

**When it is played.** In the window, after the after set, with the throughput change on the worker. Its
cancelled play makes the worker reset Studio, so it never runs between the two sets or inside one. An uncounted
play of it before the window, on whatever worker is serving, is a rehearsal: it shakes out the tool and proves
nothing counted.

**What it doesn't show:** state held outside Studio's datamodel and Lua state, such as a file the worker writes;
isolation between plays on two workers; and anything about marks a real candidate might leave that these seven
don't resemble.

### 13c. The definitions of cases 1, 9, 10, 11 and 14 (2026-11-27)

**What changed.** §7 named each case's Campaign by what it does. This names the files, before any of them is
created, and the one limit that differs from the run each is copied from. Nothing about a case's pass or fail
condition changes.

**Who ruled.** The Spark lane, which creates and starts the Campaigns as the supervisor (D13).

| Case | Definition | What it is |
|---|---|---|
| 1, and the Campaign cases 2, 5, 6 and 8 are acted out on | `2-9-0-certification-campaign.yaml` | The 2.8 counted run's definition, limit for limit, but `max_elapsed_s` 14,400 where that had 7,200 |
| 9 | `2-9-0-case-9-attributed-setup-failure-campaign.yaml` | The 2.8.1 row-8 diagnostic's definition with its proposal profile changed to `campaign-increment-source-client-stops-corrected`, and nothing else |
| 10 | `2-9-0-case-10-unattributed-setup-failure-campaign.yaml` | The same definition with its proposal profile changed to `campaign-increment-source-client-stalls`, and nothing else |
| 11 | `2-8-1-row8-diagnostic-campaign.yaml` | The 2.8.1 diagnostic as it ran on 2026-11-19, unchanged |
| 14 | `2-9-0-cut-shakeout-fastapi-react.yaml` and `2-9-0-cut-shakeout-nextjs.yaml` | The 2.8.1 cut pair's set configs: the same squad, request profile, gate policy and loaded-check scripts. Their names, records directories and notes changed, and all 321 loaded-check rows at registration are tracked |

**Why case 1's elapsed limit is doubled.** The elapsed-time guard paused both 2.8 rehearsals that reached a
repair, and a limit's pause is the owner's to resume (D16). A Campaign paused by a guard set for an attended run
would end an unattended case for a reason that isn't the case's. The 2.8.1 diagnostic used the same value for
the same reason.

**Case 14's exit rule,** stated in each config before its first launch: one shakeout per stack on one deploy,
and the pair passes when each cycle is functional (a verdict, a passing boot audit, no intervention, a seeded
tree matching its manifest) with no new seam finding. It runs on the final deploy and needs nothing of the Mac,
so it may run before the Campaign cases' rehearsal.

**The same file serves a rehearsal and the window.** A rehearsal's Campaign is uncounted by when it runs (§6),
not by its definition, so no second file can drift from the first.

**What case 10's Campaign does after the cycle the case reads.** The faulted increment's cycle ends
`blocked_unverified` with no correction, which is what case 10 reads. The Campaign then routes §10 row 8, as it
does for any unread candidate, and its repair cycle is built without the fault. That repair is the Campaign's
own design and is reported, and it is not part of case 10's pass condition.

### 13d. The quiet bar's 1-minute load is 2.5, read with Studio idling (2026-11-27)

**What changed.** 13a's point 4 held a measured set's start to a 1-minute load under 2.0. It is now under 2.5.
Every other line of the bar stands: the 15-minute load under 3.0, free memory at 70% or more, no container
running, no model loaded, the other processes together under 100% CPU, and the end bar as it was. A start
reading that misses still waits, and a reading that wasn't taken still misses.

**Who ruled.** The owner, on 2026-11-27, on the Spark lane's recommendation: "Yes - one hour of waiting is
pointless."

**The evidence.**
- **The bar was set from the wrong reading.** 13a took 2.0 from a reading with Studio and the worker not
  running (load 1.17 at 01:21 ET; PR #3286, comment 7211459597). A set can only start with Studio open, and
  Studio idling used between 43 and 56% of a core in each of the seventeen host readings kept on 2026-11-27,
  and between 44 and 51% in all but two.
- **With Studio idling the Mac sits between 2.0 and 2.5.** Before the after set's rehearsal, eleven readings
  three minutes apart read 2.41, 2.46, 2.14, 2.29, 2.16, 2.05, 2.06, 2.46, 2.78, 2.36 and 1.92. The set waited
  31 minutes for the last one. Ten of the eleven are under 2.5, so under the new bar it would have started on
  the first.
- **The start's load doesn't move the plays.** Both sets ended above 2.0 by their own doing (2.26 and 2.52).
  The plays of one set spread over about 2.5 s, and the change measured is 22 s. The rehearsal's set started at
  1.92, ended at 2.52, and every play ran between 74.9 and 77.3 s by the runtime's record of the set.
- **Both sets are held to one bar.** The before set's start reading was 1.87, which meets 2.0 and 2.5 alike.

**Why it is an amendment and not a quiet edit.** The bar was loosened after a set had been played under it and
after a rehearsal had shown the result. That is the order in which a test gets bent, so the change is the
owner's, it is written before the counted after set, and the reason is that the bar was miscalibrated, not that
a set missed it. No set has missed it.

**What it gives up.** A counted after set may now start on a Mac up to 0.6 of a load point busier than the
before set's start (1.87). The record shows all four readings side by side, so a reader can see how far apart they
were.

### 13e. Rehearsal 1's reading, and how cases 2 to 6, 8 and 14 are run in the window (2026-11-27)

**What changed.** Seven things, each written before the window opens. No case's pass or fail condition changes.

1. **The exit rule is read as met by rehearsal 1 for the seven cases it ran, and case 2 is rehearsed at the
   window's opening.** §6 lists eight cases for a rehearsal. Rehearsal 1 ran seven of them (1, 5, 6, 8, 9, 10 and
   11). It could not run case 2: the worker brings Studio forward only inside the dedicated window, whose four
   values are the owner's to write (D12), and they were not written while the rehearsal ran. So:
   - case 2 gets one uncounted rehearsal inside the window, before case 2 is counted and before the owner's
     sitting for cases 3 and 4;
   - a seam finding in it is handled as §2 handles any rehearsal's: the fix merges, the deploy or the worker's
     checkout is superseded, and any case already counted on the superseded one is counted again;
   - the budget of two rehearsals stands. The cut record reports one rehearsal of seven cases and case 2's own.
2. **Cases 2, 5, 6 and 8 are acted out on a second Campaign of case 1's definition,** in that order, and case 1's
   own Campaign is left untouched from start to finish. §7 allowed either ("during case 1's Campaign, or one like
   it"). Case 8's abort ends the second Campaign, so it can't be case 1's.
3. **Cases 3 and 4 are single queued plays, not plays of a Campaign.** Each is one play of the registered
   qualification scenario on the baseline, queued by the Spark lane with `measured_play_set.py play --plays 1`
   when the MacBook lane says the owner is ready. A Campaign's next play arrives when its build ends, which
   nobody can time to a person sitting down. The result's keys are read exactly as §7 says. The lines "the
   increment is retried later" and "the increment is retried by the Campaign" don't apply: no increment waits on
   these plays.
4. **Case 8's "next play" is one queued play, read at once.** After the abort the Spark lane queues one play of
   the registered scenario on the baseline, the same way, and reads its `place_baseline`. §7 named "the next
   Campaign's first play", which may be an hour later and behind a worker restart; a play queued at once reads
   the place the aborted play left.
5. **The worker runs as a plain process through the window,** started from the main checkout by one command, as
   it ran for the before set and for the rehearsal. §3's check 5 said "as its installed service", and 13b had
   changed that for the measured sets only. For cases 5 and 6, "stops the worker's service" is the stop a service
   manager gives: SIGTERM to the worker's process, then SIGKILL if it hasn't exited in ten seconds. The restart
   is the same command, straight after the stop.
6. **The shakeout pair played on 2026-11-27 stands as case 14.** 13c let it run before the Campaign cases'
   rehearsal, on the final deploy. It did, and the deploy has not been superseded since. If the deploy is
   superseded before the cut, the pair is played again.

7. **A proposal whose scenario uses `move_to` is returned at the gate** as `criteria_not_checkable`, by §5's
   bar. The action can't arrive as the reader stands (#3298): `play.py` waits for arrival on
   `@player.Character.HumanoidRootPart`, and the reader's `resolve` walks a path by child lookup, where a
   player's character is a property and not a child. So the step reads `setup_failed` on the baseline and on
   any candidate, and an assertion behind it never executes. The MacBook lane read this by hand on the pin
   after the rehearsal, with the worker stopped and nothing claimed: one play that read the path as `absent`
   with the character spawned, and one that failed its `move_to` after 25 s. No rehearsed scenario uses the
   action, and no ruling already made changes. The reader is not changed before the cut: a fix moves
   `harness.observe`'s digest, and with it the environment every certified play names. It goes to the first
   patch after the cut, with its own requalification, and §11 carries it until then.

**Who ruled.**
- Points 1 to 4, 6 and 7: the Spark lane, which wrote this registration and supervises the Campaigns (D13), under
  the owner's grant of 2026-11-26. Case 2's ordering was put to the owner on 2026-11-27 in the Spark lane's plan
  for the window. The owner questioned that plan's hours and did not speak to the ordering, so it is the
  Spark lane's reading of the exit rule and not the owner's ruling. The plan asks for "a full pass", and a
  missed done-when's disposition is the owner's (D16), so the owner may overrule it before the window opens.
- Point 5: the owner, on 2026-11-27. The Spark lane recommended the plain process when it laid out how the
  worker runs in the window, and the owner answered: "Im good with your recommendations on all other
  decisions."
- The MacBook lane acted out cases 5 and 6 in the rehearsal and read each ruling at its gate.

**Rehearsal 1, uncounted,** on the final deploy `dep_8ce04da70a65` (main at `f35c714b`), 2026-11-27, with nobody
at the Mac. The worker ran from main at `4ceba696`. Every case it ran met its pass condition, and no seam finding
was made.

| Step | Case | Campaign | From, to (ET) | What it read |
|---|---|---|---|---|
| A | 9 | `cmp_eac9d55c48f9` | 06:57, 07:24 | `setup_failed`, attributed, one correction dispatched and spent, the same scenario digests before and after, the increment accepted |
| B | 10 | `cmp_37dbef8e83a7` | 07:25, 08:07 | `setup_failed`, not attributed, no correction dispatched, the cycle `blocked_unverified`; then the Campaign's own row 8 and an accepted repair cycle |
| C | 11 | `cmp_ee48e5bc3785` | 08:07, 08:48 | the injected error attributed, no correction left to dispatch; rows 5, 8 and 3; the cycle's views agree on 33 of 33 readings |
| D | 1 | `cmp_fec2f4dd5981` | 08:48, 09:58 | both increments accepted, C1 to C7 holding for each; fourteen plays, none needing a person; B-1's scenarios replayed and passing on B-2's candidate |
| E | 5 | `cmp_c7e6a25c3182` | 10:17 | the worker stopped with nothing claimed and started; the new session's tool list is the pin's; nothing was queued while it was down |
| E | 6 | the same | 10:20, 10:23 | the worker stopped 11 s into a claim; attempt 1 `expired`, attempt 2 accepted with the outcome an undisturbed run gave; one accepted result, no late result |
| E | 8 | the same | 10:23, 10:26 | the abort's answer counts one operation cancelled; the worker answers `interrupted`, naming what it ran on; nothing queued after; the next play reads the pin's place baseline |

- **Plays:** 50 operations over the five steps, 51 attempts, no refusal. 49 completed and one was interrupted
  (case 8's). Every result names the pin's place baseline. Five results carry a script error, all in steps
  A and C, whose profiles inject a script that raises. Step B's fault waits and raises nothing.
- **Rulings at the increment gate:** six proposals and eight rulings. Four proposals were approved as first
  proposed. Two were returned first, both `criteria_not_checkable` by §5's bar (step B's, and step D's second
  item), and each was approved on its revision.
- **Interventions:** none outside the cases themselves.
- **Two readings of how the cases behave,** neither a finding:
  - *Case 6.* The registry ends an earlier session's attempt when the same worker registers again. With the
    restart straight after the stop, attempt 1 ended at the new registration, 53 s after its claim and before
    its 60 s lease ran out, with outcome `expired`. §7's "the lease runs out" reads either way: the attempt is
    ended by the runtime, never by a result from the stopped worker.
  - *Case 8.* The worker hears a cancellation on its lease watch's next turn. The abort came 49 s into the
    claim, the worker stopped the play 12 s later, and its answer followed the tool's reset 34 s after that.
- **Studio's memory at a Campaign's pace:** over step D's fourteen plays and 70 minutes, Studio's resident
  memory went from 3.1 GB down to 1.6 GB and back to 3.0 GB, rising with plays and falling while Studio idled.
  The measured sets' growth of 1.6 GB over twenty plays was play after play with no idle between.

**What rehearsal 1 doesn't show,** added to §11 for the window as well where it says so:
- **Case 2,** for the reason in point 1. Cases 3, 4, 7, 12 and 13 are not a rehearsal's (§6); 12 and 13 had
  their own uncounted rehearsals (13a, 13b).
- **Case 5's second branch.** The tool list was the pin's after every launch of Studio in the rehearsal, so the
  refusal of a moved list and the requalification after it were not exercised. They are exercised in the window
  only if the list moves.
- **A quiet Mac.** The Mac's own stack was running through the rehearsal, where the plan asks for none through a
  rehearsal's plays. The rehearsal was not held to the quiet bar and its play times are not compared with the
  measured sets'. For the window the stack is stopped (§3, check 5).
- **Where the proposals came from, in the rehearsal and in the window.** On every proposal run the proposer is
  supplied the project's one approved lesson. That lesson was drafted from the 2.8 run's two items: it names
  the defect each proposal first had, and it carries the form of the check that passes the second item (#3297).
  So a proposal that meets §5's bar at its first reading is no evidence that the squad worked the bar out, and
  the counts of returned proposals are read with that said beside them. The owner ruled on 2026-11-27 that the
  lesson stays through 2.9 and is corrected in 2.10. What the cases certify, the worker's unattended execution
  and the runtime's handling of it, doesn't rest on who shaped the proposal.
- **`move_to`, in the window and in the release.** No scenario that walks the character to a point is
  certified, because none can pass (point 7, #3298). The held key (`hold_key`) is the only movement the
  window's plays use.
- **The deploy against main.** Four merges followed the final deploy: two reading scripts and their tests
  (`host_quiet_reading.py`, `measured_play_set.py`), and documents. None is loaded by the runtime or an agent,
  so the deploy is not superseded. The worker's checkout carries the first of them and the Spark's tool the
  second.

### 13f. The outside review: rehearsal 2 runs whole, the worker's checks guard every input play, and the claims are narrowed (2026-11-27)

**What changed.** The outside review (D14) read the activation rule (#3269) and this registration (#3283) with
§13a to §13e, and asked for corrections before any counted run. This amendment takes them. Points 1 to 3 change what
runs. Points 4 to 9 change what the record must show. Nothing counted has run, so no result is re-judged.

**Who ruled.** The owner, on 2026-11-27, on the review and the Spark lane's assessment of it: "Yes, go ahead with
the fixes and 13f." The review's findings are the reviewer's. This text is the Spark lane's, and the MacBook lane read
it before it was registered. Where the Spark lane departed from the review, it says so below, with the reason.

1. **Rehearsal 1 is a partial rehearsal, and 13e's point 1 is withdrawn.** §6 asks for one rehearsal of cases 1, 2,
   5, 6, 8, 9, 10 and 11 that passes whole. Rehearsal 1 ran seven of them on a Mac that wasn't quiet, and 13e read
   that as the exit rule met. That reading was the Spark lane's, and the review holds §6 to its text. So:
   - rehearsal 1 stays on the record as partial and uncounted, with what each of its seven cases read;
   - **rehearsal 2** runs all eight cases, one after another, on one deploy and one worker checkout. The four
     dedicated values must be written by the owner, the Mac quiet by §3's check 5 for its whole length, and the
     worker the corrected one from point 2;
   - rehearsal 2 is the last the budget allows. A third is the owner's to allow (D16);
   - a case that fails in rehearsal 2 for a defect in a 2.9 item supersedes the deploy or the worker's checkout, as §2
     says. No case of the window runs until a rehearsal has passed whole.
2. **The worker's checks guard every input play (SIP-0117 R5.37, #3300).** The review found that R5.33's
   conditions are read only when Studio is behind, so a locked screen or a person at the keyboard didn't stop a play
   with Studio already in front, and that nothing is read during a play. R5.37 moves the checks from the activation
   to the input. Its tests are at the runner and through `Worker.serve()`. The window and rehearsal 2 run on a
   worker checkout that carries it. No result's `ran_with` names the worker's commit (its `source_revision` is the
   candidate tree's), so the record names the checkout's commit for every play, from the MacBook lane's run log,
   and every result's `harness.*` digests must match that checkout's.
3. **Two new owner-present variants,** in the same sitting as cases 3 and 4, each one queued play, as 13e's point 3:
   - **Case 3b, input during a play.** The guard reads the counter before each input action after the first, and
     as soon as a held key ends, so the play needs a second input. The scenario is the qualification scenario with
     one 10 s `hold_key` added after its setup, kept beside it on the Mac and frozen by digest before the sitting.
     The MacBook lane measured the idle counter on that shape (R5.37's as-built table). Studio is in front and the
     Mac idle. The MacBook lane tells the owner when the hold has begun, and the owner then moves the pointer. *Passes when* no
     input action is sent after the owner's input is read, the result reads `not_executed`, `tool_unready` and
     `front.refused` `input_during_play`, and no assertion reads as failed. If R5.37's measurement shows the idle
     counter can't tell the play's own input from a person's, case 3b is not run, and the record says that input
     during a play is not detected.
   - **Case 4b, a lock with Studio already in front.** Studio is in front when the owner locks the screen and steps
     away. The play is queued only once the MacBook lane reads the screen locked and the idle counter past the
     threshold, since a dedicated worker reads the counter before the lock and a counter under the threshold would
     refuse first, as `idle_below_threshold`, without testing the lock. *Passes when* nothing is sent, the result reads `not_executed`, `tool_unready` and `front.refused` `locked`, and the
     screen is still locked when the owner returns. This is the path the review found unguarded. Case 4 keeps its own
     variant, with another app in front.

   §7's case 4 is queued the same way, after the lock and the counter both read, for the same reason. Its other lines,
   and case 3's, stand.
4. **Cases 3, 4, 3b and 4b prove the worker's refusal, not a Campaign's retry.** Their plays are queued alone, so
   no increment waits on them. The record cites the wiring tests that hold `tool_unready` to rows 10 and 11's retry,
   never a repair, by name, and doesn't present the single plays as evidence of it.
5. **A negative assertion cites the test that proves its enforcement.** A clean window shows only that nothing
   forbidden happened, not that it would have been refused. The record names, beside each of §8's negative
   assertions and cases 6 and 8's, the tests that submit the forbidden thing and see it refused:
   - a late result after another session reclaimed the operation (`tests/unit/remote_execution/remote_path.py`);
   - a late result never satisfying a newer attempt, and the same result submitted twice being answered once
     (`tests/unit/remote_execution/registry_contract.py`);
   - a result after a cancel being kept and being no evidence (the same file);
   - a cancel racing a completion, in both orders: a result that settled before the cancel stands, and one that
     arrives after it is kept and is no evidence (the same file).

   **Case 5's moved tool list** is cited the same way, from `tests/unit/remote_execution/test_roblox_studio_requalification.py`.
   A live Studio version change is not forced to make it happen. The record keeps the live restart and the tested
   refusal apart, and presents neither as the other.
6. **The supervisor's bar is shown to refuse.** The Spark lane writes this registration and rules the gates, so the
   review asked for evidence that the gate refuses a plausible but non-discriminating proposal. Rehearsal 1 holds
   two such refusals, both of the squad's own proposals and both by §5's bar: step B's first proposal and step D's
   second. They are cited. And before the window, a **blind control** runs outside any Campaign:
   - the MacBook lane writes six change requests in the shape the proposer emits, for the window's two backlog
     items. Some are sound, some carry one of §5's three shapes, and some carry a subtler fault, a check that a
     broken build passes;
   - it keeps them, and which is which, out of the repository, since they name the product;
   - the Spark lane rules each by §5's bar without being told the mix;
   - the MacBook lane then scores the rulings, and the record gives the counts: sound approved, faulted returned,
     and every miss named by its shape.

   *The departure from the review:* the review asked for the control to be submitted at the gate. A change request
   placed in a Campaign by hand is §9's edit of a proposal, which voids the case it touches. So the control is ruled
   on paper, by the same bar and the same ruler, and the record says so. A miss in it doesn't stop the window. It is
   reported beside the window's rulings, so a reader can weigh them.
7. **The throughput claim is the registered scenario's.** Case 13's 20% is a reduction in the matched scenario's
   median, on the conditions 13a and 13d fix, and the record claims nothing wider. Beside the median and p95 it gives:
   - all twenty plays of each set, with each stage's time;
   - the spread;
   - a bootstrap interval for the reduction in the median (10,000 resamples of each set, the seed recorded);
   - the four host readings, each against both the 2.0 bar and 13d's 2.5;
   - the worker's checkout and the deploy for each set;
   - the window's Campaign plays' times, described and not compared.
8. **Isolation names what was reused.** Case 12's record names, for each step of its sequence:
   - the Studio process and the session, so a reader can see that the steps meant to share a session shared one;
   - each reset, and when it ran.

   A step that passed on a fresh process where it claims a reused one doesn't pass. R5.36's lost corner, a change
   made during the sync and undone before play ends, is a limit of what the runner detects. The record names it, and
   no test is built to show it, since it is the design's stated give and not a defect.
9. **Every Campaign reports its time.** Beside case 1's outcome:
   - the elapsed time, the time spent building and playing, and the time waiting on a ruling or an operator;
   - each pause and retry;
   - how much fell past the 2.8 limit of 7,200 s.

   A Campaign that finished only because 13c doubled the limit is reported as such.

**Added to §11 (what the evidence doesn't cover):**
- the lesson, by point C1 of the review. Each accepted increment's record names the lesson supplied to its proposer.
  The record doesn't describe these increments as evidence of the squad's ability to build, only of the worker's and
  the runtime's handling of them;
- `move_to`, as 13e's point 7;
- input during a play, if point 3's measurement means case 3b isn't run;
- R5.36's lost corner, as point 8;
- the blind control's misses, if there are any.

**The record keeps the evidence apart.** The cut record sorts each claim by what shows it:
- a live Campaign;
- a fault injected on purpose;
- a wiring or regression test;
- not shown at all;
- shaped by a supplied lesson;
- limited to the registered scenario.

It lists every departure from this registration with who ruled it. No claim is shown in a class it wasn't shown in.

### 13g. Rehearsal 2's reading, a parse error the provider didn't name, and a third rehearsal (2026-11-27)

**What changed.** Rehearsal 2 didn't pass whole: case 1 failed, on a seam finding in a 2.9 item. The fix merged,
the worker's checkout moved to it, and the owner allowed a third rehearsal. No case's pass or fail condition
changes, and nothing counted has run.

**Who ruled.**
- **The third rehearsal: the owner** (D16). To the MacBook lane in its own session, at about 21:54 ET: "Yes, run
  rehearsal 3 (Recommended)", in answer to a question naming rehearsal 3's eight cases, the counted window after
  it with the owner at the Mac for cases 3, 3b, 4 and 4b, and the release PR's merge and the tag staying the
  owner's. And to the Spark lane at 21:52 ET: "Do everything you can to cut 2.9 tonight."
- **The finding and its fix: the Spark lane** read the finding by §6. The MacBook lane read it the same way,
  built the fix (#3306, closing #3304) and the Spark lane reviewed it.

**Rehearsal 2, uncounted,** on the final deploy `dep_d5820ce5efc8` (main at `41de5f25`), 2026-11-27, with the
owner's four dedicated values written and the Mac's own stack stopped. The worker ran from main at `41de5f25`.

| Step | Case | Campaign | From, to (ET) | What it read |
|---|---|---|---|---|
| A | 2 | `cmp_0081a91970b5` | 18:49, 19:01 | Finder in front; the play claimed with it there; `front.was` `other`, `front.activated` `true`, `front.idle_s` 1647; the play ran, every assertion executed |
| A | 5 | the same | 19:02, 19:03 | the worker stopped with nothing claimed and started; the new session's tool list the pin's |
| A | 6 | the same | 19:08, 19:10 | the worker stopped 10 s into a claim; attempt 1 `expired` at the re-registration, attempt 2 accepted; one accepted result, no late result |
| A | 8 | the same | 19:10, 19:13 | the abort 48 s into a claim cancelled one operation; the worker answered `interrupted`; nothing queued after; the next play read the pin's place baseline |
| B | 1 | `cmp_76f9ecb61c0e` | 19:13, 20:41 | B-1 accepted. **B-2 not accepted**: its candidate's client module didn't parse, every candidate play read `setup_failed`, the provider named no error, no correction was dispatched, and the repair cycle repeated the fault. The Campaign escalated (§10 row 9). **Case 1 fails** |
| C | 9 | `cmp_4efa26ceb3b1` | 20:43, 21:07 | `setup_failed`, attributed (the injected throw named, file and line), one correction dispatched and spent, the same scenario digests before and after, the increment accepted |
| D | 10 | `cmp_3805f605374d` | 21:08, 21:46 | `setup_failed`, not attributed, no correction dispatched; then the Campaign's own row 8 and an accepted repair cycle |
| E | 11 | `cmp_bd47b518c87d` | 21:46, 22:19 | the injected error attributed on every candidate play, no correction left to dispatch; rows 5, 8 and 3, the repair cycle accepted |

- **Rulings at the increment gate:** six proposals and nine rulings. Three were approved as first proposed (cases
  9, 10 and 11), and three were returned first, each `criteria_not_checkable` by §5's bar, then approved on
  revision: step A's B-1, step B's B-1 and step B's B-2. The MacBook lane read every proposal before its ruling. Two
  of the returns rest on a defect the Spark lane's first read missed:
  - step A's B-1 read only an added element's text, so a hidden element passed, and its `prd_delta` was empty.
    The Spark lane's first read approved it, and the MacBook lane found both;
  - step B's B-1's headless criterion keyed its rule on values of a type the product never passes it. The Spark
    lane raised the keys as a question, and the MacBook lane traced the type.

  The cut record reports these beside the window's rulings, as misses of the ruler's first read.
- **Interventions:** none outside the cases themselves. Case 1's escalation was left as it stood for the owner.

**The seam finding: a staged script that doesn't parse was never named** (#3304). R5.32's Studio half (#3288)
reported only an error block with its own stack, and skipped the follow-on "Requested module experienced an
error while loading". Studio writes a parse error as one stackless line naming the script and its line, and the
only stacks after it are the follow-ons'. So the candidate's `script_errors` read `[]` while its console named a
file the candidate changed. R5.32's condition 3 failed, no correction was dispatched, and the repair cycle was
built without the error. It is a reading that couldn't see its own miss (§6). Case 1's failure is its
consequence and not a second finding: with the error named, the run's one correction would have had the line.
Nothing was credited wrongly.

**The fix and what it supersedes.** #3306 (main at `4972be1b`) names a stackless `<script>:<line>: <message>` line
whose script is staged, in console order with the stacked blocks. It changes the worker's provider only:
- the runtime never loads the module, so the deploy `dep_d5820ce5efc8` is not superseded, and case 14's pair
  stands (13e point 6);
- no `harness.*` digest moves, and `environment` doesn't either. It doesn't name the console reader, so the record
  names the worker's commit for every play (13f point 2), and §11 says so;
- the worker's checkout moves to `4972be1b`, after case 11 ends with nothing claimed. The MacBook lane plays a
  client module that doesn't parse by hand on it first, and the record gives what the result names.

**Rehearsal 3** runs all eight cases on that checkout and the same deploy, with the opening checks 3 and 4 read
again for the new session: case 1 first, since it is the case that failed; then cases 2, 5, 6 and 8 on a second
Campaign of case 1's definition (13e point 2); then cases 9, 10 and 11. Its exit rule and pass conditions are §6's
and §7's. A new seam finding in it ends the window's attempt for this cut. A fourth rehearsal is the owner's (D16).

**The counted window after it, and the owner-present cases run without the owner.** The owner, to the MacBook lane
in its own session at about 22:00 ET, asked "Can you do it without me?", and answered "Yes" to the MacBook lane's
plan below. It changes cases 3, 3b, 4 and 4b, so it is registered here before any of them runs. Each case's record
names its stand-in, and none is reported as a person's.

- **The order.** Cases 1, 2 and 5 to 14 unattended, then 3, then 3b, then 4b last, since nothing can play after it.
  The window's end is the owner's to move (D12).
- **Cases 3 and 3b: a declared user activity stands in for a person's input.** The MacBook lane declares it with
  `caffeinate -u -t 1`, which needs no permission or setting changed.
  - **Its condition, read before either case runs:** with the worker stopped, the idle counter the worker reads
    (`HIDIdleTime`) is read before and after one declaration. If the declaration doesn't reset it, cases 3 and 3b
    are not run without the owner, and the record says so.
  - **Case 3:** one play of the qualification scenario on the baseline is queued straight after a declaration,
    with another app in front. It passes by §7's condition, read as `idle_below_threshold`.
  - **Case 3b:** one play of the frozen hold scenario (`sha256:80403cee…14f5ae`), with the declaration made during
    its 10 s hold. It passes by 13f point 3's condition, read as `input_during_play`.
  - **What they show:** the worker refuses on an idle counter that a declared activity reset. They don't show that a
    person's own typing or pointer resets that counter. That is §11's, beside the R5.37 measurement of the counter
    on the play's own input.
- **Case 4b: the display put to sleep stands in for the owner's lock.** With Studio in front, the MacBook lane runs
  `pmset displaysleepnow`, after which the Mac locks at once. It reads the screen locked and the idle counter past
  the threshold, and only then does the Spark lane queue the one play. It passes by 13f point 3's condition, read
  as `locked`. "The screen is still locked when the owner returns" is read by the MacBook lane, which never
  unlocks: the lock state is read again after the result, and the Mac stays locked until the owner returns.
- **Case 4 is not run, and is reported as shown by tests only.** One lock can't serve both 4 and 4b faithfully, and
  4b is the path the review found unguarded. A lock with another app in front is held by R5.37's tests and by
  R5.33's condition tests with Studio behind, named in the record. §11 says it wasn't played.
- **What stays the owner's:** the release PR's merge and the tag.

**Added to §11:**
- cases 3, 3b and 4b ran with stand-ins (a declared user activity; the display put to sleep), not with a person;
  case 4 wasn't played;
- `environment` doesn't name the worker's console reader. Two checkouts with different readers name one
  `environment`, so a reading compared across checkouts names the commit;
- a headless criterion loads only the module it tests, so nothing headless parsed the candidate's client module. A
  build check that compiles every changed `.luau` file in the footprint is a follow-on for 2.10 (#3304).
