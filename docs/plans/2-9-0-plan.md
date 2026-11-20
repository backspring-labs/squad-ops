# 2.9 plan — stabilization: execution evidence a supervised Roblox Campaign can trust, an unattended worker that is safe, and faster plays

**Status: DRAFT, revision 2 (2026-11-20), for the owner's adoption. Not adopted.** It places nothing: SIP ledgers and
issue labels move when the owner adopts it.
- **Revision 2** takes the owner's outside review of revision 1, posted on PR #3249, whose disposition was "request
  revision before adoption". It takes the review's recommended rulings, with six changes and one deferral the Spark
  recommended and the owner accepted ("Create revision 2 as you recommend"). §7 lists each.
  - The rulings in §5 are the outside reviewer's recommendations, as changed. They become the owner's only by
    adoption.
- **Revision 1** (2026-11-20, after the v2.8.1 cut) dropped the drafted #3147 and #3218 items, both settled in 2.8.1,
  and took #3244, which the owner placed at the cut. The cut record is `verification-sets/2-8-1-cut-record.md`.
- **The draft start** (2026-11-18) came from the owner's outside review of the 2.8.1 plan. Its sequence: 2.8.1's fixes;
  stabilization before any extended supervised Campaign; 2.9 for throughput and stability; 2.10 for the missing
  game-development capabilities; a certification Campaign.

**What 2.9 is.** An odd minor: stabilization, **feature-free by rule** (CLAUDE.md, #281).
- **Unchanged:** what a squad can be asked to build.
- **No capability is added:** no scenario vocabulary, no coverage mechanism, no new authority, tool access or permission.
- **What changes:**
  - whether a recorded result is true;
  - whether an abort and a cancel govern what runs;
  - whether the worker runs safely with nobody at the Mac;
  - how long a play takes.

**The claim:**

> **A supervised Roblox Campaign's execution evidence can be trusted, its cancellation and recovery are deterministic,
> and its worker runs unattended and safely, faster. What a squad can be asked to build is unchanged:**
> - **execution truth:** a recorded result says what ran, what failed, why, and under which qualified Studio. A failure
>   the environment caused is never recorded against the candidate;
> - **operational safety:** an abort, a cancel, a pause, a lease and a recovery behave deterministically, and no
>   abandoned work changes an outcome;
> - **environment reliability:** a dedicated worker plays without a person keeping Studio in front, and a person at the
>   Mac is never overridden;
> - **measured throughput:** the median play is at least 20% faster on a matched set, or the record says why not, with
>   no loss of isolation, correctness or evidence.

**The 2.9/2.10 boundary.**
- **2.9:** stabilization, operational correctness, reliability, performance, and hardening what exists.
- **2.10** (`2-10-0-plan.md`): new game-development capabilities, scenario vocabulary, coverage mechanisms, and the
  certification Campaign.

An item that turns out to need a capability moves to 2.10, and the plan says so.

---

## 1. Stage A — operational truth

Its exit gate: the system can't accept evidence after an abort, misattribute an unavailable capability, go on without
required context, or give contradictory terminal outcomes. Stage C's unattended running isn't certified before it.

### 1. A cycle needs a QA agent that can run its remote evaluations (#3235) — the Spark lane

- **What happened:** in the 2.8.1 row-8 window's first attempt, only the runtime-api had been switched to remote execution.
  - The Campaign's own plays ran.
  - The QA agent had no remote-execution port, so its in-run evaluation read the gap as `evaluator_gap:no_remote_execution_port`.
  - The cycle was created anyway.
- **The rule:** a cycle whose verification needs remote execution is created only if every component that runs it has the capability.
  - That means the runtime-api and the QA agent. A component's capability is read from the component itself, never inferred from the runtime-api's provider setting.
  - A cycle without it is refused at creation, by name.
  - Capability lost during a run is attributed to the environment. It never triggers a candidate correction and never counts against the candidate.
- **The record:** the failing component, the capability expected and observed, its deploy identity, and when. The
  Campaign's and the cycle's evaluations name the same cause.
- **Tests:**
  - the runtime-api configured and the QA agent not;
  - the QA agent configured and the provider unavailable;
  - a provider switch without the QA agent recreated;
  - capability lost mid-run;
  - recovery after the missing capability is deployed;
  - the Campaign's and the cycle's evidence reconciled.
- **Done when:** a missing QA capability is refused at creation, or attributed to the environment during the run. In no
  test is it recorded as a candidate's defect.

### 2. An abort governs its remote operations (#3236) — the Spark lane

- **What happened:** the same window's aborted Campaign left its repair cycle's baseline play claimed.
  - The worker played it, and it settled `completed, accepted` after the abort.
  - `cancel_requested` read `false`.
- **The rule:** a Campaign's abort, or a cycle's cancel, requests cancellation of every queued and claimed operation it owns.
  - The worker sees the request at its lease renewal or heartbeat, and at result submission.
  - A result after the cancel is kept on the record, and contributes no evidence to the ended cycle.
  - Cancellation is idempotent.
  - A completion racing a cancel has one stated precedence, and the outcome records which won.
  - A restart or recovery never resumes a cancelled operation.
  - The worker's cleanup needs no person.
- **Tests:**
  - an abort before the claim;
  - an abort while claimed;
  - an abort during a play;
  - an abort racing completion;
  - a worker that disconnects during the cancel;
  - a worker restarted after it;
  - a late result after the Campaign ended;
  - a repeated abort.
- **Done when:** no operation of an aborted Campaign changes its outcome, triggers a promotion or resumes. Everything that
  actually ran stays on the record.

### 3. Every view of a cycle reads the same ending and status (#3224, #3244) — the Spark lane

- **#3244:** a one-workload cycle (a Campaign's repair or retry) ends `single_workload_ended`.
  - The route reads its status from its one run, which is right, and names no ending.
  - The route will name the recorded stop as the ending, keep the status from the run, and hide no live-run conflict. No earlier ending is rewritten.
- **#3224:** `cycles list --status` filters by the latest run alone. It will use the route's reading, `read_cycle_status`,
  with the batch read #3223 added, so a page costs no query per cycle.
- **Tests:** the reading for a one-workload cycle ended completed, failed and cancelled, with the multi-workload case
  unchanged. Then the list's filter against the route for completed, failed, cancelled, active, paused,
  between-workload and recorded-ending-conflict cycles, with a wiring test at the list route.
- **Done when:** for every Roblox cycle, the route, `cycles show`, the Campaign's ledger, the control log and the
  status-filtered list agree. That includes the two repair cycles 2.8.1 item 1 couldn't read.

### 4. A required artifact that can't be retrieved stops the task (#3128) — the MacBook lane

- **Today:** the executor's other vault reads log a warning and go on when a retrieval fails. A task can then run
  without context it needed.
- **The rule:** each executor vault read declares its input required or optional.
  - A required input whose retrieval fails fails closed, named and attributed to the environment.
  - An optional input is left out only when it's absent, or when its contract allows that.
  - A retrieval failure is never read as absence.
- **Done when:** every executor vault-read path has its declaration, and a test for each shows the failure and its
  attribution.

### 5. An accepted QA hand-off reads accepted everywhere (#3000) — the MacBook lane

- **Today:** when a product's own runner takes a QA hand-off and the router accepts its pass, three signals still read
  failed: the Prefect task run, the agent's runtime activity, and `task.failed` (counted in `tasks_failed_total`).
  The 2.8.0 package's own screenshot shows a red QA bar in a run that was accepted.
- **The rule:** the final verified hand-off result decides the terminal state those signals report. The earlier failed
  attempt stays as an event, never rewritten. A hand-off that is rejected stays failed.
  - The taxonomy is transport-owned (#506) and locked, so the change is a numbered amendment to the contract that owns
    the cycle-event taxonomy, made in the PR that changes it.
- **Done when:** an accepted hand-off has one consistent terminal state across Prefect, activity, events and metrics,
  with its attempt history whole and no false failure counted. A rejected one reads failed in all four.

### 6. The worker lease test holds under load (#3110) — the Spark lane

- **Today:** `test_a_worker_cut_off_mid_lease` (in-memory) fails under a loaded full regression run. PR #3127 is open on it.
- **The rule:** find the cause under a controlled clock and deterministic scheduling. A longer timeout doesn't count as
  a fix.
- **Done when:** the failure is reproduced or instrumented, its cause is named, and repeated loaded runs no longer fail
  on it. The record says what nondeterminism remains.

## 2. Stage B — candidate evaluation

Its exit gate: every attribution, generated test, skill stop, correction and Studio qualification is testable and
traceable.

### 7. A candidate's own setup failure is repaired in the run (#3200) — the Spark lane

- **What happened:** rehearsal 3's B-2 candidate set a property a ScreenGui doesn't have, and its client threw at start.
  - All six candidate plays read `setup_failed`, and each play's console named the error and its line. The baseline had met the same setup minutes earlier.
  - `setup_failed` is not executed, so the run made no correction. That cost about 12 minutes of plays on one named fault.
- **The rule (D2):** a numbered SIP-0117 amendment, next to R5.28. A setup failure is attributed to the candidate only
  when all six hold:
  1. the identical frozen setup was met on the baseline, in the same cycle;
  2. the baseline's and the candidate's plays share the pinned place, the qualified Studio identity and the worker;
  3. the candidate's console names an error **in a file the candidate changed, inside its approved footprint**;
  4. that error appears **before the setup's first unmet wait**;
  5. the same error is **absent from the baseline's console** in that cycle;
  6. the worker reported no environment refusal (R5.28) and no qualification mismatch (R5.29).

  The evidence for each is kept and linked from the attribution. When one fails, today's routing holds: not
  executed, never credited or failed (SIP-0096). An unexecuted assertion is never made an executed failure to enable a
  repair.
- **The repair:** one in-run correction, bounded by the run's budget, with the console's error in its evidence. Its
  attempts and spent budget are recorded.
- **Tests,** at the run's correction seam, with a wiring test from the caller the live cycle uses:
  - an attributable fault;
  - each of the six conditions failing alone;
  - evidence missing, stale or contradictory.
- **Done when:**
  - a diagnostic on the played path, with 2.8.1's fault and in-run correction on, goes from baseline to attributed failure to repair to the same frozen scenarios passing, and is accepted;
  - every negative case keeps today's routing;
  - §10 row 8 still works with in-run correction off (§6, case 11).

### 8. A product's `qa.test` is bounded, and names files its runner collects (#3182) — the MacBook lane

- **The gap:** on z_tower-ascension, a `qa.test` whose expected file is under `src/` is shown 137 files, 1.7 million characters. One whose file matches no directory is shown the whole tree, 2.9 million characters.
- **Both rules (D3):**
  - **at the plan gate:** a `qa.test`'s expected files are checked against the product runner's collection contract,
    not their extension. One no runner collects is refused by name (SIP-0112 H.4 point 3). A new test in a collected
    place is accepted.
  - **at the prompt:** a documented cap.
    - The task is shown the files its text names, their imports and the test infrastructure. It's never shown the whole tree.
    - Context that is essential and can't fit holds the task by name. Nothing is silently left out.
    - What was shown is recorded.
- **Done when:** a plan whose `qa.test` names a source file or a note is refused, and a valid new test is accepted. A
  replay of the 2.8 counted run's `qa.test` envelope shows the prompt under the cap with the files the suite needs. The
  suite it writes runs, and tells the correct build from a broken one.

### 9. A skill's declared stop outranks the task's own requirements (#3240) — the MacBook lane

- **Today:** the skills section ranks a declared stop below the task's requirements. In #3199's replay, the one miss
  the owner ruled run-to-run variance came on an input byte-identical in all four arms (3/3, 1/3, 3/3, 2/3), and the
  missed reply cites that ordering.
- **The rule:** when a skill's stop condition holds, the stop is a valid outcome of the task and outranks a conflicting
  requirement to produce artifacts. The prompt's requirements say so consistently.
- **Done when:** a skills replay, under a new experiment id, shows the conflicting case resolved for the stop, and every
  previously valid case still valid. The replay tests the cause.

### 10. A hand play's log carries `ran_with` (#3243) — the MacBook lane

- **Done when:** a test of `studio_play_scenario.py`'s actual output shows the full identity, unchanged:
  - the qualified and played identities;
  - the qualification record;
  - the place baseline, the source revision and the harness identity.

### 11. A requalification names a tool whose definition changed (#3230) — the MacBook lane

- **Today:** a qualification record names tools added and removed, but not one whose definition changed.
  - On 2026-11-19 the digest moved with nothing added or removed.
  - On 2026-11-20 two changed descriptions were found only by diffing dumps by hand. Nobody does that unattended.
- **The rule:** the record keeps each tool's definition digest beside the list's.
  - Requalification and refusal records name the tools added, removed and changed.
  - A record from before this reads "comparison unavailable", never "no change".
- **Done when:** a same-name change to a tool's description or schema is named. A Studio that changed one is never run under the stale qualification.

## 3. Stage C — unattended running, and speed

Its exit gate: a dedicated worker runs unattended and safely, keeps evidence and isolation, and meets the throughput
target or records why not.

### 12. A dedicated worker brings Studio to the front, safely (#3193) — the Spark lane

- **Today:** SIP-0117 R5.18 refuses a scenario that acts through Studio's input when another app is in front. R5.28
  retries the refusal and never repairs it. In attended windows the MacBook lane's guard procedure keeps Studio in front.
- **The rule (D1, D7):** a numbered SIP-0117 amendment to R5.18, and a runbook beside the worker's setup. The runner
  brings Studio to the front only when every condition holds:
  - the worker's settings declare it dedicated, and name the window's start and end, and the time is inside it;
  - the worker holds a valid lease on the operation;
  - the system's idle counter has reached the configured threshold;
  - human input is read again **immediately before** the activation, and none is found;
  - the Mac is unlocked and the session is available.

  Anything uncertain, including a race between that read and the activation, fails safe as a refusal. A locked screen stays a refusal; it is never unlocked or bypassed. Each activation, and each refusal, is recorded in `ran_with`.
- **Not added:** a reservation service, or any new authority. The window is declared in the worker's settings, by the
  person who owns the Mac.
- **Tests:**
  - the front lost and recovered;
  - human input found, so no activation;
  - an activation that fails reads `tool_unready`;
  - a locked screen is refused;
  - a Studio restart and a worker restart keep the qualification checks;
  - a time outside the declared window is refused.

  None ends as a failed criterion.
- **Done when:** the certification window (§6) shows each case recovered safely or refused explicitly.

### 13. Studio play throughput, measured, then cut (#3250) — the lane that owns the Studio runner

- **Revision 1's premise was wrong:** one Studio launch already serves many plays (every play of the 2.8.1 closing window, and all 32 of #3199's hand plays). Keeping Studio open saves nothing new.
- **What's known:** a play takes about 100 s from claim to completion (98.3 s, 98.2 s and 99.8 s in that window). Where
  the time goes is unmeasured.
- **The work, in order:**
  1. **Measure each stage:** sync, the place's state read, play start, the scenario's own waits, stop, reset and delivery. Use a matched scenario set pre-registered before the measurement, on the same Studio qualification and hardware.
  2. **If no stage could yield the target,** record that and build nothing.
  3. **Otherwise remove the cost.** Every play keeps its own source revision, scenario, place identity, tool
     qualification, session identity and sequence index. A failed reset refuses the next play.
- **The target (D6):** at least a 20% cut in the median claim-to-completion time on the matched set.
- **Reported:** median and p95 per play, plays per hour, each stage's time, Studio plays per accepted increment,
  retries and refusals, setup and reset failures, isolation failures, and resources where they can be read.
- **Isolation tests,** each reading leakage of:
  - module and global state;
  - GUI and player state;
  - instance attributes and workspace changes;
  - the candidate's source revision;
  - a failed play's residue, and an interrupted play's;
  - a baseline, candidate, baseline sequence;
  - state after a Studio restart and after a worker restart;
  - a competing operation.
- **Done when** all of these hold:
  - the target is met;
  - scenario outcomes are unchanged;
  - the isolation tests pass;
  - qualification and provenance are complete;
  - cancellation and restart behave as items 2 and 12 say;
  - no new false success or false failure.

  A miss is recorded as unsuccessful, even when the instrument and the change work.

## 4. Stage D — dependencies and the existing stacks

### 14. The dependency move (#3101) — the Spark lane; placed by the owner, 2026-11-15

FastAPI 0.163 with Starlette 1.10, aio-pika 10.2 and ruff 0.17. It changes two live paths, the `app.routes` readers and
the publisher's return handling, which is stabilization work (the 2.8 plan §7).
- **Covered (D9):**
  - route discovery;
  - the worker routes' wiring;
  - fill-slot integrity;
  - the runtime's access log;
  - TestClient and httpx;
  - aio-pika's publisher confirms and returned publishes;
  - ruff's version across images;
  - the evaluator image's pin and qualification.
- **Not taken with it:** #2782's live-DOM reading, a 2.10 capability.
- **Done when:**
  - the issue's failing cases pass, with the live behaviour and the existing stacks' regression;
  - the evaluator image's identity and qualification hold or are renewed;
  - the release records name the new versions and images;
  - a rollback to the previous set is shown to restore it;
  - any change to how earlier evaluations compare is recorded.

## 5. The rulings (D1–D10), for adoption

The outside reviewer's recommendations, with the Spark's changes (§7). Adoption makes them the owner's.

| | ruling |
|---|---|
| D1 | The runner brings Studio to the front on a dedicated worker, inside its declared window, after the idle threshold and a fresh human-input read, and records it. Anything uncertain is a refusal (item 12). |
| D2 | A setup failure is the candidate's only when all six of item 7's conditions hold, each with its evidence kept. |
| D3 | Both rules: collection-checked expected files at the plan gate, and a capped prompt that holds rather than drops (item 8). |
| D4 | #3240, #3243 and #3230 are in 2.9 (items 9–11). |
| D5 | #3235, #3236, #3224, #3128, #3000 and #3110 are in 2.9 (items 1–6). #3062 stays open as CI debt, and the cut record names the network dependency. #3147's remaining per-stack move stays out (§7). |
| D6 | Throughput: a 20% median cut on a matched set, measured first, with no loss of correctness, isolation or reliability (item 13). |
| D7 | The window is declared in the worker's settings, and human priority, recorded activation and fail-safe refusal hold. No reservation service, and no new authority (item 12). |
| D8 | 2.9 certifies unattended **worker execution**, not unattended supervision. An external supervisor's authority (#2760) stays a separate question for a later line. Any supervisor in a 2.9 window uses an explicitly authorized, least-privilege identity, and one that loses its authorization stops its privileged actions and holds. |
| D9 | The dependency move is checked path by path, with evaluator requalification where it's affected, versions on the record and a rollback shown (item 14). |
| D10 | The issue matrix (§8) is the placement proposal. It's applied through adoption, and no earlier owner ruling is overwritten silently. |

## 6. The certification window, pre-registered

A test suite alone doesn't show the claim. Before the window opens, an amendment states for each live case:
- the expected outcome and its pass and fail conditions;
- the evidence and the identities and revision pins it must carry;
- the operator's permitted actions and how an intervention is classed;
- the attribution rule and the recovery expected.

The shakeout's exit rule (CLAUDE.md) applies, and the cut record reports the rounds.

**Live, on the dedicated worker** (cases only Studio and the worker can show):
1. a normal Campaign, unattended;
2. the front lost and recovered;
3. human input preventing activation;
4. a locked screen refused;
5. a Studio restart and requalification;
6. a worker restart and lease recovery;
7. the QA agent's capability missing, as a deliberately misconfigured diagnostic (#3235);
8. an abort during a play (#3236);
9. an attributable setup failure, repaired in the run (#3200);
10. an ambiguous or environmental setup failure, not corrected;
11. 2.8.1's row-8 diagnostic with in-run correction off, routed row 8 as before;
12. isolation across plays (item 13);
13. the matched throughput measurement, before and after;
14. the existing stacks' shakeout pair on the final deploy, after the dependency move.

**By wiring tests, read against the window's own records,** where a live case would add nothing:
- the cycle views' agreement (item 3), re-read on every Roblox cycle, the 2.8.1 repair cycles included;
- the accepted hand-off's terminal state (item 5), read on the window's QA tasks;
- a required artifact's retrieval failure (item 4).

**Negative assertions:** across the window, none of the following happens:
- an operation is accepted after an abort;
- an environmental refusal reads as a candidate failure;
- an unqualified Studio play is credited;
- contaminated state reaches another play;
- required context goes missing silently;
- an unsupported result is promoted;
- missing evidence reads as success.

**Carried from 2.8.1:**
- #3174, read on the first escalation a person answers in the window (the owner's ruling at the 2.8.1 cut);
- #3218's threshold, re-read over the longer window: no worker request over 2 s, and none timing out.

**Reported:**
- failures attributed to the candidate against ambiguous or environmental ones;
- unattended outcomes and recoveries;
- cancellation correctness;
- worker latency and lease renewals;
- plays per hour, with the median and p95;
- plays per accepted increment;
- repair success and exhaustion;
- contradictory lifecycle readings;
- escalations and interventions;
- what was unverified or deferred.

The cut record says what one window does not show: reliability across machines, Studio versions or games.

## 7. Where revision 2 departs from the outside review, and why

1. **D2's "causally associated" error is made concrete:** a changed file inside the footprint, before the first unmet
   wait, and absent from the baseline. Left as written, it would be an acceptance criterion with no bound.
2. **D1 and D7 have no reservation service.** A declared window in the worker's settings does the job without a new
   mechanism, which would be a feature in a feature-free line.
3. **Item 13 measures before it builds,** and drops the build if no stage could reach the 20% target, rather than
   building to a known miss.
4. **The certification splits live cases from wiring tests.** The reviewer's cases 14–16 are read by wiring tests
   against the window's records. Case 17, a supervisor's session expiring, is dropped: it belongs to the supervision
   question D8 keeps out of 2.9.
5. **The plan names no external supervisor,** by the repository's rule. #2760 is cited by number.
6. **Amendments land in the PRs that build them.** The activation and attribution rules become numbered SIP-0117
   amendments there, not text in this plan (CLAUDE.md step 5a).
7. **#3147's remaining per-stack move is deferred.** It is the one item that changes the existing web stacks' QA prompts,
   in a release whose claim includes their being unchanged, and it owes its own replay. It stays open and unplaced
   (SIP-0112 H.37), a 2.10 candidate with that replay.

## 8. The open issues, each placed (proposed, D10)

The 39 issues open on 2026-11-20 are the outside review's 38, plus #3250 filed for item 13.

**In 2.9 (15):** #3235, #3236, #3224, #3244, #3128, #3000, #3110 (Stage A); #3200, #3182, #3240, #3243, #3230 (Stage B); #3193, #3250 (Stage C); #3101 (Stage D).

**2.10, already in its draft (5):** #3205, #950, #2709, #2781, #2421's remainder.
- #2709 carries an earlier 2.6 placement. Its ledger is reconciled when 2.10 adopts it, and the earlier ruling is cited, not overwritten.

**Proposed for 2.10's intake (8),** not placed by this plan: #3137, #3138, #3181, #2997, #2782, #2723, #3169, and #3147's per-stack move.

**Open outside 2.9 (11):**
| issue | disposition |
|---|---|
| #3062 | CI network dependency: a patch or a later stabilization line. The 2.9 cut record names it, and tells a registry outage from a regression |
| #2760 | an external supervisor's authority: a separate question (D8) |
| #2847 | managed Project environments: a feature line of its own |
| #2834 | console CLI parity: the console roadmap |
| #2826 | its 2.6 placement and history kept; its completion reconciled separately |
| #1469 | waits for a real frontend-build failure corpus |
| #2173 | the memory epic; its children reconciled separately |
| #557 | waits for its evidence trigger and a SIP |
| #1978 | its 2.6 placement kept; its status reconciled separately |
| #1965 | a separately governed experiment, not a release dependency |
| #1039 | the docs site's design pass, independent backlog |

## 9. The order, and the cut

**Order:** Stage A, then B, then C, then D.
- Work in a later stage may be built in parallel where its lane is free.
- Certification follows the order. Stage C's window isn't run before Stage A's exit gate holds.
- The dependency move (Stage D) lands before the final deploy, so the shakeout pair reads it.

**The cut**, when each holds:
- every 2.9 item has its done-when, read, or the owner's disposition;
- every amendment is numbered, made in its PR, and reflected in its SIP's ledger;
- every issue in §8 is where §8 puts it, or the plan was amended;
- the certification window's cases hold, with its negative assertions;
- the existing stacks' shakeout pair passes on the final deploy;
- no 2.10 capability came in;
- the cut follows CLAUDE.md's procedure (version, markers, CHANGELOG, ROADMAP, SIP sweep, tag, package with records,
  housekeeping);
- the cut record names every limitation that remains.

## 10. Not in 2.9

- **The game-development capabilities, #3205 and the certification Campaign:** all 2.10's.
- **An external supervisor's authority (#2760),** and any new permission, tool access or delegation.
- **#3147's per-stack move,** and the other issues §8 lists for 2.10's intake.
