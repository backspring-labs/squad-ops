# 2.8.1 plan — the 2.8 demonstration's follow-ups, fixed small

**Status: ADOPTED (2026-11-18), revision 2.** The owner: "Approve the 2.8.1 plan, merge it." Revision 2 followed the owner's outside review:
- **Revision 1:** after the 2.8.0 cut the Spark proposed five items. The owner answered "I agree with the 2.8.1 items proposed", then held this PR's merge for an outside review.
- **The review:** keep the small-patch scope. Give each item an unambiguous verification result and a definition of done. Dispose of every open risk explicitly. Don't read 2.8.1 shipped as a supervised Campaign ready for unattended game development.
- **The owner's ask:** "Can you update the 2.8.1 plan and draft the start of 2.9 and 2.10 plan accordingly".

**What revision 2 changes:**
- each item gains the cases it's tested on and a **done when** line that the cut record reads;
- the repair diagnostic is held to §10 row 8, and a row-12 result doesn't count (§1 item 5);
- #3174 joins (item 2), and #3147 joins only on a condition (item 7);
- §4 disposes of every open risk the review named, and §5 says what 2.8.1 doesn't claim.

The review's observations beyond 2.8.1 open two draft plans: `2-9-0-plan.md` (stabilization) and `2-10-0-plan.md` (the next feature line).

**What 2.8.1 is.** A patch on the 2.8 line (CLAUDE.md, #281: urgent or small fixes, either lane). Each item is something the 2.8.0 windows met:
- a defect in what 2.8 shipped;
- a gap in what its evidence covers;
- the squad's most frequent return.

None changes a design beyond a numbered SIP amendment it names.

**The claim it makes:**

> **What the Roblox line reports is what happened, and the squad's scenarios are written to the rules the gate
> applies:**
> - a cycle's ending is read from its durable end record, the same in every view, and an abort cancels each cycle
>   still running exactly once;
> - an escalation a person answered reads answered;
> - no play runs on a Studio whose channel, version or tools differ from its qualification;
> - the scenario-writing skill's rules remove the window's return shapes in a replay, without losing a case today's
>   skill meets;
> - the Campaign-level repair of a candidate the verifier couldn't read (§10 row 8) runs end to end on a played product;
> - the API's stall after a gate entry is fixed, or bounded and disposed of by the owner.

---

## 1. The items

### 1. A cycle's ending is read from its end record (#3201) — the Spark lane

- **The defect:** `cycle_status_of` (`api/routes/cycles/mapping.py:204`) reads runs and workload progress, never `cycle_ends`.
  - A cycle ended `rejected_at_gate` has a completed proposal workload and pending later workloads, so `resolve_cycle_status`'s rule 3 (`cycles/lifecycle.py`) reads it `ACTIVE`.
  - Rehearsal 3's abort then cancelled `cyc_929c449744f1`, which had ended 40 minutes earlier. It left the cycle that was actually paused alone.
- **The fix:**
  - **The end record is authoritative.** A cycle with a `cycle_ends` row reads as ended. A stated table maps each of the nine endings (`CycleEnding`, `campaigns/continuation.py:38`) onto the public status, and the read carries the ending's name beside it, so no client infers the ending from the status.
  - **Precedence, stated and tested:**
    1. an end row with a run still queued, running or paused is a conflict. It reads active, with the conflict named on the read, so an end row never hides a run that is really going, and an abort cancels that run;
    2. an end row and a cancellation: the first one recorded is the ending, and the second is named as a conflict, never dropped;
    3. an end row with only pending workloads reads ended (the defect's case);
    4. no end row: today's rules, unchanged.
  - **The abort** cancels each cycle that reads active, paused or created exactly once. It skips one that has ended or is already cancelled. A second abort cancels nothing more and says so. The cancel and a cycle's own ending can't both be written: whichever lands first is the ending.
- **Verified by:**
  - the reading, parametrized over every ending and over the two conflicts;
  - a wiring test entering at the abort route, the caller a Campaign's abort uses, with three cycles:
    - one ended `rejected_at_gate`: not in `cancelled_cycles`;
    - one paused at a gate: cancelled;
    - one between workloads (#2214's case): cancelled;
  - a second abort on the same Campaign: it cancels nothing;
  - an abort racing a cycle's own ending: one ending is stored.
- **Done when:** for every cycle of the 2.8 windows' Campaigns still stored on the Spark, these name the same ending:
  - `squadops cycles show`;
  - the cycle route;
  - `squadops campaigns show`;
  - the control log's ending row.

  `cyc_929c449744f1`, which holds both an end row and the abort's cancel, reads its end row's ending and names the cancel as the conflict.

### 2. An escalation a person answered reads answered (#3174) — the MacBook lane

- **The defect:** on 2026-11-17 a person approved an escalated plan gate through `squadops runs gate`.
  - Ten minutes later `squadops campaigns escalations` still read the escalation `pending`, and the control log held no `escalation_closed` row.
  - `campaigns/escalation.py` says a person deciding the gate before the bound resolves it, as one `escalation_closed` row. The route the decision took never reached that.
  - A supervisor reading the queue would take an answered question for open work.
- **The fix:** a gate decision closes its open escalation `resolved` on whichever route records the decision. It's written once, from the stored decision, and carries who decided and when. The cause, meaning which route skipped the close, is read first and named in the PR.
- **Verified by:** tests entering at the cycle's gate route, the path the CLI takes:
  - an approval closes the escalation `resolved` once;
  - the same when the run then fails;
  - the close is written after a runtime restart between the decision and the read;
  - the same decision posted twice writes one close;
  - a decision after the bound reads `expired`, never `resolved`.
- **Done when:** for a gate a person decided before the bound:
  - `squadops campaigns escalations` reads `resolved`, with `closed_by` and `closed_at`;
  - the control log holds one `escalation_closed` row.

### 3. Studio's qualification identity includes its channel (#3206) — the MacBook lane

- **The gap:** on 2026-11-18 Roblox's updater moved the MacBook's Studio from `production` to `zluauordereddensehashmapcontrol` at the same version.
  - The qualification proof holds the version and the tool list, so a claim's version check (R5.21) passed.
  - Amendment 12f made the channel a window-opening check, by hand.
- **The fix:**
  - **The identity:** Studio's qualification identity is its version, its channel and its tool list. The channel is read from Studio's startup log.
  - **When it's compared:** against the proof at every claim, and again after every reset or relaunch.
  - **A mismatch:** a claim on a Studio whose identity differs from the proof's is refused by name. The refusal is a `tool_unready` not-executed (R5.28), so it's retried and never repaired.
  - **Missing evidence:** a channel the worker can't read is unqualified. The worker refuses, and never falls back to an older proof.
  - **The record:** each result's `ran_with` holds both the qualification's identity and the identity the play ran on.
  - **The amendment:** a numbered SIP-0117 amendment.
- **Verified by:** tests at the runner, each on a Studio with the same version:
  - the channel has changed: refused by name;
  - the channel can't be read: refused;
  - the channel changes across a Studio restart: refused after the relaunch;
  - a failed requalification leaves the pin where it was and the worker refusing;
  - a passed requalification moves the pin, and the plays run.

  And a requalification run on the Mac that records the channel.
- **Done when:** the Mac's proof records the channel, and on every result of the 2.8.1 windows the two identities in `ran_with` are equal. No result reads executed under an identity its qualification doesn't name.

### 4. The scenario-writing skill carries the gate's rules (#3199) — the MacBook lane writes it, the Spark replays it

- **The evidence:** 7 of 11 proposal versions were returned across rehearsal 3 and the counted run (the record's §3 and §4).
  - **Checks that passed on broken work:** a format-only clock, a counter attribute standing in for the text, a lobby half with no floor half.
  - **Checks that failed on working work:** a wait on a value nothing sets, and an exact match on a value that changes each second.
- **The skill's rules:** `play-scenario-authoring/SKILL.md` gains these, each with a worked example taken from the issue and its comments, and invented example values:
  - **coverage:** every acceptance sentence of the item is read by some criterion;
  - **reachability:** every setup action, wait and observation reads something the baseline game sets, or something the footprint adds;
  - **the broken build:** each named check fails on the obvious broken version and on a partial one, and passes on any correct one;
  - **timing:** a band measured from a start the criterion states, with margin on both edges;
  - **preservation:** a check that something still works reads it independently of unrelated navigation or game state;
  - **the kind of evidence:** each criterion says whether it's played or headless. An effect the vocabulary can't reach is declared as a coverage gap in the proposal, with its headless proof. A weaker played check never stands in for it.
- **The self-review:** the skill ends with a check the author runs on each criterion before submitting. The proposal answers it per criterion, in the text the supervisor reads: the broken build the check fails on, and where its band starts.
  - **No schema change in 2.8.1.** A deterministic reachability check at the proposal seam needs a map of the place, which is 2.10's (`2-10-0-plan.md` §2).
- **Verified by:** a skills replay under a new cases version (`roblox-skills-v4`), run before the profile requires the changed skill (SIP-0116 §7, §17p).
  - **The cases:** the window's returned shapes as authoring cases, plus every `v3` case unchanged:
    - B-2's clock, which needs the stuck timer and a working timer told apart;
    - B-1's floor state, which no play can reach: the right answer declares the gap and proves the floor half headless;
    - B-1's lobby half alone, a partial build;
    - a wait on a value nothing sets.
  - **The arms:** today's skill and the revised skill, on the same cases, generations and seed. §17p's no-skill baseline is kept for contrast.
  - **Judged two ways, each fixed before the run:**
    - **by rule (§17p):** coverage; a stated band start; waits only on what the baseline sets or the footprint adds, read against the baseline tree and the footprint; a valid `roblox-studio/1` criterion;
    - **by play:** each authored named check is played with `scripts/dev/studio_play_scenario.py` on the case's fixed candidates. The broken ones (the stuck timer, the lobby half alone) must fail it, and the correct one must pass it.
      - **The candidates:** the counted run's accepted trees are the correct ones. Each broken one is a stated mechanical transform of an accepted tree, applied by a script and recorded with its diff. Nobody hand-writes game code for it.
  - **The predictions, stated before it runs** (mechanisms, not rates, at this sample size):
    - under the revised skill, no generation writes a format-only or exact-match check on a value that changes;
    - none waits on a value the baseline doesn't set and the footprint doesn't add;
    - none leaves an acceptance sentence unread;
    - every named check fails on the case's broken candidates and passes on its correct one;
    - and no `v3` case the current skill meets goes unmet.

    Today's skill's answers are recorded beside them.
  - The held working-work lesson (`pat_0e0dfc199afe0bed@2`) is withdrawn once this ships, since the skill supersedes it.
- **Done when:** the replay's record shows the predictions holding, with both arms' answers kept. A prediction that fails is reported as failed, and the skill doesn't ship on that version.

### 5. The Campaign-level repair of a blocked candidate, played (§10 row 8) — both lanes

- **The gap:** the 2.8.0 cut record §5.
  - Both rehearsals that reached §10 row 8 were paused by `max_elapsed_s` before the repair launched.
  - The diagnostic's repair was the run's in-run correction, not the Campaign's.
- **Row 8 only.** Rows 8 and 12 both launch a repair cycle, but they're different routes (`campaigns/continuation.py:393` and `:400`):
  - row 8 repairs a candidate the verifier couldn't read (`blocked_unverified`);
  - row 12 repairs one it read and refused (`rejected`).

  The cut record's gap is row 8. A row-12 result doesn't count.
- **The failure, pre-registered:** a candidate whose client throws at start where the baseline doesn't. That's rehearsal 3's B-2 shape (#3200).
  - **The expected classification:** every candidate play reads `setup_failed`, which is not executed. So the cycle ends `assessed`, with the verdict `blocked_unverified` and an attribution that isn't the environment's (so not rows 10 or 11), and the Campaign routes row 8.
  - **Making it deterministic:** a new opt-in fault, beside #3171's, adds the error to a footprint file of the candidate. It applies only to the increment's first cycle, and the repair cycle builds without it.
  - **Scoping it is part of this item:** today a fault applies to a task's first attempt in any cycle (`capabilities/handlers/fault_injection.py:20`), so a repair cycle under the same profile would get it again. A wiring test covers the scoping.
- **In-run correction is off, and the Campaign's repair is kept:**
  - a not-executed play gives the run nothing to correct (by design, until #3200);
  - the diagnostic's request profile also sets `max_correction_attempts` to 0, so no in-run correction can stand in;
  - `max_repair_cycles_per_increment` stays at least 1;
  - `max_elapsed_s` is set so the elapsed-time guard can't pause the Campaign before the repair.
- **What's read, in order** (the pre-registration amendment restates D1–D4 for the repair cycle):
  1. **The conditions before any repair:**
     - the baseline's setup was met and the candidate's wasn't, on the same place and worker;
     - the fault's APPLIED line names the file and the line it changed.
  2. **The routing:** the cycle's ending and verdict as above, and the control log's continuation reads row 8, `repair`.
  3. **The repair cycle:**
     - its launch intent and its cycle (`kind repair`) are in the control log;
     - it has the original's proposal id and content hash, baseline tree, footprint and frozen scenario hashes.
  4. **The candidate:** the repair cycle's candidate meets setup, and the same frozen scenarios pass, with the same hashes.
  5. **The outcome:** the increment is accepted (row 7).
  6. **The record:** every attempt, repair action, elapsed time and intervention.
- **The outcomes, stated before it runs:**
  - **a pass:** readings 1–5 hold;
  - **a finding, not a pass:** a repair cycle that launches but whose candidate still fails, say because it wasn't shown the console's error. That's filed. Whether the repair cycle is shown the error is read, not assumed;
  - **a failure at reading 2:** the Campaign doesn't route row 8.
- **Exhaustion and escalation, tested apart** (wiring tests at the Campaign's continuation, with no Studio):
  - `blocked_unverified` with no repairs left routes row 9, `escalate`;
  - a repair cycle that ends blocked again, with the budget spent, routes row 9;
  - a cycle blocked only for want of a worker routes rows 10 and 11, never row 8 (#3045, R5.28).
- **Needs:** about an hour of the Mac, in an attended window the owner names. It's an uncounted Campaign, so the Spark rules its gates under the owner's grant of 2026-11-16.
- **Done when:** readings 1–5 hold on one run, and the record carries reading 6. Or the run's finding is filed, and the cut record says row 8 is still unproven.

### 6. The API's stall after a gate entry (#3218) — the Spark lane

- **The finding:** 17 worker requests went unanswered, about 13–16 s after a gate entry or a Campaign transition, and each was answered at the next poll. None cost a play.
- **The work:**
  1. **Instrument:**
     - the runtime-api's latency on `/api/v1/workers/*`, with timestamps;
     - the event loop's delay, from a loop-lag probe;
     - waits on the DB pool;
     - the worker's own request timeouts and lease renewals.

     Each is read around gate entries and Campaign transitions.
  2. **Reproduce:** gate entries on an uncounted Campaign with a worker polling. It reproduces when a poll stalls for 10 s or more within 20 s of an entry.
  3. **Find** the operation that holds the loop or a connection, and fix it in 2.8.1 if the fix is small and safe.
- **The threshold, fixed before the final shakeout:** across at least 20 gate entries and Campaign transitions with a worker polling, every worker request is answered within 2 s, and none times out.
- **If the fix can't be made safely in 2.8.1:**
  - the owner rules where it goes;
  - the cut record names the risk that remains: a stall long enough reads as an absent worker, on #3045's launch-blocked path;
  - the cut record also names the safeguard in place: the claim and lease rules held through all 17 stalls, and the worker retries at its next poll.
- **Done when:** the threshold holds on the final deploy, or the owner's disposition is on the record. Measurement alone doesn't close it.

### 7. The QA prompt names only the product's runner (#3147) — the MacBook lane, on a condition

- **The finding:** the shared `qa.test` system fragment gives a Luau product's QA author pytest, vitest, FastAPI and JSX rules and examples.
- **In 2.8.1 only if it's small and replay-safe.** Here that means a split under which every existing stack's rendered `qa.test` system prompt is byte-identical before and after.
  - A test renders the prompt for a FastAPI + React product and a Next.js product and asserts the bytes are unchanged.
  - It renders the prompt for a Luau product and asserts that none of those idioms is in it.
  - Since the existing stacks see the same bytes, their behaviour can't move.
  - The Luau prompt's change is read by the `roblox-skills-v4` replay's QA cases, under its new experiment id.
- **Otherwise** it moves to 2.9 with a replay of its own (`2-9-0-plan.md`).
- **Done when:** both render tests pass and the replay's QA cases meet their expectations, or the move is recorded.

---

## 2. Order

Sequencing, not dates.
1. **Fixes and the first measurement:**
   - the Spark: #3201, and #3218's instrument and reproduction;
   - the MacBook: #3206 and #3174, and #3147's split if it meets its condition.
2. **The skill:** #3199's skill text (the MacBook), then its replay (the Spark), with the plays on the Mac.
3. **The repair diagnostic:** the pre-registration amendment, then the diagnostic itself, on a deploy carrying items 1–4 and the fault's scoping, in an owner-named window. The replay's plays can share the window.
4. **The latency threshold:** #3218's threshold read on the final deploy.
5. **The cut:**
   - one shakeout pair on the final deploy, with the exit rule stated before the first launch;
   - the cut record reads each item's **done when** and re-reads §4's dispositions.

The release PR merges only when each item has its result, met or disposed of by the owner.

## 3. The cut's evidence

| item | done when | the evidence |
|---|---|---|
| 1. #3201 | every view names the same ending; the abort's tests pass | a read across the 2.8 windows' stored Campaigns; the wiring tests |
| 2. #3174 | an answered escalation reads `resolved`, once | the route tests; a decision on the diagnostic's Campaign, read |
| 3. #3206 | the proof records the channel; no result runs off its qualification | the runner tests; the requalification record; every 2.8.1 result's `ran_with` |
| 4. #3199 | the replay's predictions hold, both arms recorded | `roblox-skills-v4`'s record and its plays |
| 5. row 8 | readings 1–5 on one run, or a finding filed | the diagnostic's record and Campaign |
| 6. #3218 | the threshold holds, or the owner's disposition | the instrument's readings on the final deploy |
| 7. #3147 | both render tests, or the move recorded | CI; the replay's QA cases |
| existing stacks unchanged | a shakeout pair with no seam finding | the pair's records |

## 4. Open risks, each disposed of

The review named open issues that bear on a supervised Campaign. Each one's place, and what holds until then:

| issue | the risk | in 2.8.1 | until it's fixed | where it goes |
|---|---|---|---|---|
| #3200 | a candidate's own setup failure, which the console names, gets no in-run repair | it's the repair diagnostic's failure shape, so the Campaign-level path is proved end to end on it (item 5) | §10 row 8 repairs it at the Campaign level, once item 5 proves that | **2.9**: attribution on evidence, as a SIP-0117 amendment |
| #3193 | a play is refused when another app is in front of Studio | unchanged | R5.18 refuses it by name, and R5.28 (shipped in 2.8, #3195) retries it and never repairs, so a refusal is never evidence against the game's code. In attended windows the MacBook lane's front-guard procedure runs | **2.9**: a dedicated-worker policy, and an activation only if the owner authorizes it |
| #3182 | a `qa.test` on a product can be shown 1.7 million characters, or the whole 2.9-million-character tree | unchanged; no run has planned one | the prompt guard refuses it by name (`PROMPT_EXCEEDS_CONTEXT_WINDOW`), so it fails loudly, at the cost of a run | **2.9**: refused at the plan gate, and the prompt bounded |
| #3174 | an answered escalation reads open | **in** (item 2) | — | — |
| #3147 | the QA prompt names runners a Luau product doesn't have | **on a condition** (item 7) | the specs written so far used Lune's globals, and the increment was accepted | 2.9 if its condition fails |
| #3205 | a supervisor can't replay a lesson without shell access to the Spark | unchanged | lesson replays run on the Spark lane, and a lesson's approval stays the owner's (`memory:approve`) | **2.10**: a governed replay route; an auth-boundary change, so the owner rules |
| #3218 | a worker's poll stalls about 15 s after a gate entry | **in** (item 6) | the claim and lease rules held through all 17 stalls | the owner rules, if it moves |

## 5. What 2.8.1 doesn't claim

- **It isn't readiness for a supervised Campaign of useful game improvements.** That needs:
  - 2.9's stabilization;
  - 2.10's capabilities: play actions that reach a named place, readings compared across steps, a map of the place, screenshots and a client-script harness;
  - and a certification Campaign of its own: `2-10-0-plan.md` §3.

  One accepted run isn't a rate, and 2.8.1 adds no counted increment.
- **Unchanged from the 2.8.0 cut record's §5:**
  - feel and visuals;
  - multiplayer;
  - parts, models or UI built in Studio;
  - effects outside the scenario vocabulary;
  - Studio versions other than the qualified one.

## 6. Left out, and where it goes

- **2.9, stabilization** (`docs/plans/2-9-0-plan.md`, a draft):
  - #3200, #3193 and #3182;
  - #3147 if its condition fails;
  - #3218 if the owner moves it;
  - reusing a Studio session across plays, with play throughput measured;
  - #3101, the dependency move the owner placed on 2026-11-15.
- **2.10, the next feature line** (`docs/plans/2-10-0-plan.md`, a draft):
  - **the Roblox capabilities:** play actions that reach a named place, readings compared across steps, a map of the place for the proposer, screenshots tied to their revision, a headless harness for client scripts, declared coverage gaps, and multiplayer marked unverified;
  - #3205's governed replay route;
  - the supervised-Campaign certification;
  - the items 2.8's decision 9 already moved there: #2709, #950 and #2781.
