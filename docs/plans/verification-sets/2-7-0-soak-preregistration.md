# 2.7 scripted soak: pre-registration

**Status: DRAFT, prepared 2026-11-08. Its scripts were recorded on 2026-11-09 (§3a), before its Campaign is created.** It
is registered by the commit hash of this document on its branch once every placeholder in §9 is filled, and that
commit comes before the soak's Campaign is created. It fills the 2.7 plan's §4.4 contract for #2892, amended by R6
(`z_shelfnote`, not battle-trainer). The soak is a release gate (plan §1). If it's deferred, the cut record narrows the
claim's fifth line explicitly.

## 1. What it reads

Whether the control loop lasts hours with no model in it. Every call is answered from a recorded script (#2495), so
a failure is the framework's, never a model's. The soak runs at least eight increments, of any verdict, and at least
nine hours, whichever comes later. It takes a controlled restart, token expiries up to the session's maximum lifetime, an
upstream push and a pause. Each injected event is recovered from or named, and the Campaign completes or stops only
for named reasons.

**Eight increments of any verdict, not eight accepted** (the call recorded on #2892 on 2026-11-09, under the 2.7
grant). On `z_shelfnote` the production squad has had about one increment in three accepted (`cmp_5947cfb57197`: 1 of
3), so eight accepted would need a recording of 15 hours or more, which would hit its own limits first. The plan's
claim already reads "at least eight increments". Rejections, repairs and abandonments exercise the control loop as much
as acceptances do, and the soak still runs at least nine hours.

It reads the machinery only. How good the scripted changes are says nothing about any model or prompt, and the
records say the run was scripted (`llm_script_declared`; the engine `scripted` on every call's metrics).

## 2. The fixture

- **The repository:** `backspring-labs/z_shelfnote`, private, owned by the owner's account. The owner ruled on
  2026-11-08 that its code may be public, so the recorded scripts are committed to this public repository.
- **The base commit:** `177323bed8f6bea36eac4e8aefc8901bca13b8f4`, `main`'s head since 2026-11-03 (the merge of
  z_shelfnote PR #4). It holds the backlog's items 1 to 5 (search, reading status, tags, ratings and sorting),
  accepted by earlier Campaigns and merged by the owner.
  - **Why this commit and no earlier one.** A repository-backed Project is pinned at its upstream's head when it's
    validated, and nothing pins an older commit. Starting from before item 1 would need `main` rewritten, which the
    soak won't do.
  - **Nothing merges to `main` between the recording (§3) and the soak** but the soak's own upstream push (§6.2). The
    recording Campaign's review request isn't opened, so its accepted work stays on its own campaign branch.
- **The Project:** `prj-shelfnote`, READY, validated, configured and baselined at the base commit before the recording.
  Its Development Configuration revision and inherited baseline are §9's placeholders.
- **No held-out suite is pinned.** The soak and its recording name no `scenario_suite`, so no sealed value is read,
  run or carried anywhere. Outcome Evaluation isn't part of this reading.
- **The backlog:** a goal-set revision on `prj-shelfnote` whose backlog holds only items the base doesn't meet, in
  this order. Items 6 to 10 are `docs/goals.md`'s own, as its author wrote them at the base commit. Items 11 to 15 are
  added for the soak, so a recording that loses items to abandonment still has eight increments to end. They're outcomes,
  with the design left to the squad. The goal, expected results E1 to E5, and out-of-scope stay as `docs/goals.md`
  states them, with "every change keeps what already works working" as a constraint.

  | id | title | serves | outcome |
  |---|---|---|---|
  | 6 | Stats | E5 | see how many books there are by status, and the average rating |
  | 7 | Pagination | E1 | page through a long shelf |
  | 8 | Related books | E3 | from a book, find others like it by their tags |
  | 9 | Authors | E5 | see each author on the shelf and how many of their books are there |
  | 10 | Export | E5 | take the shelf away as a spreadsheet file |
  | 11 | Recently added | E2 | see the shelf in the order its books were added, newest first |
  | 12 | Notes | E4 | keep a short note on a book, and see it with the book |
  | 13 | Reading dates | E2 | record when a book was started and finished, and see how long it took |
  | 14 | Duplicates | E3 | find the books that are on the shelf more than once |
  | 15 | Status and tag together | E1 | list the shelf by a status and a tag at once |

## 3. The scripts: how they're made, and their versions

The scripts are package data, `src/squadops/llm/llm_scripts/<name>.yaml` (`squadops.llm.script.PACKAGED_SCRIPTS_DIR`,
`src/squadops/llm/script.py:79`). That is the seam #2495 built for them: `pyproject.toml:90` ships `**/*.yaml` under
`squadops`, and both images copy `src/` and install it (`agents/Dockerfile:112,116`;
`src/squadops/api/runtime/Dockerfile:58,66`). The runtime checks each script at creation and the agents answer from
the same files. Nothing reads a script from the checkout or the host.

**So a script reaches the soak only through a deploy.** A file under `src/` is code to `classify_ci_diff.sh`, so a
script merged after the final shakeout pair passes supersedes the pinned deploy (plan §4.3). The scripts therefore
merge before the final deploy is built, and the dry run in step 3 is repeated on the final deploy (§9).

1. **Record.** A recording Campaign runs on `prj-shelfnote` at the base commit with the backlog above, on the
   production squad the pinned deploy serves, with the soak's definition (§4) except the squad and the scripts. Its
   supervisor approves each proposal as it stands. It's a real model run, uncounted, and its readings decide nothing.
2. **Make one script per cycle it launched, in launch order:**
   `record_llm_script.py --replay-latency --latency-scale <k> --latency-cap 1500` names each one
   `shelfnote-soak-cNN`. The scale `k` is §5's. A cycle the recording launched because of a fault outside the
   squad's answers (a timeout, an engine outage) can't be replayed by answers. If there is one, the recording is run
   again: a script set with a hole in its order would replay another launch's answers.
3. **Dry run.** The same cycles are recorded again without `--replay-latency`, as `shelfnote-soak-dry-cNN`, and a
   scripted Campaign runs on them, in minutes. The recorder can't recover a task's extra calls (self-evaluation
   passes, re-asks), so each key the dry run names as missing is written into both sets by hand. Every hand-written
   answer is listed in the record. The dry run repeats until its launch order, its rows and its acceptances are the
   recording's.
4. **Merge** both sets with the last code change of the line, before the final deploy.

Each script records how its latency was made (`recorded_from.latency`: the scale, the cap, how many answers were
held at it, and the total). The set's library digest is the deploy record's `scripted` model digest
(`ScriptLibrary.digest`).

### 3a. What was recorded (2026-11-09)

**The recording** is Campaign `cmp_f14bab82c35f` on `prj-shelfnote`, deploy `dep_16a1cb4f54c8` (main `40e81a4e`),
squad `full-38-tf`, unattended, with goal-set revision 3. Its definition is the soak's but for the squad, the scripts and
the limits (`var/campaigns/2-7-0-soak-recording.yaml`). It ended ten increments with six accepted (SN-6, 7, 8, 10, 12,
13) and four abandoned (SN-9, 11, 14, 15), and closed when no backlog item was left pending (control log seq 77-78).

**It launched 15 cycles, and no calibration cycle.** A repository-backed Project's calibration is a record, not a cycle
(`src/squadops/campaigns/calibration_record.py:1-19`): the start wrote `calrec_db8de50b7545` at `177323bed8f6` (seq
3-4), and the first launch was increment 1's. A scripted Campaign binds a script to every launch that has a cycle, in
order (`scripted_launch`, `src/squadops/campaigns/launch_requests.py:299`), so the soak's first script is increment 1's.
No cycle was launched for a fault outside the squad's answers, so §3 step 2's re-recording rule didn't apply.

| launch | kind | item | recorded from | its verdict (row, action) | soak script | dry-run script |
|---|---|---|---|---|---|---|
| 1 | increment 1 | SN-6 | `cyc_dbb56e0feb6f` | accepted (7, propose) | `shelfnote-soak-c01@bcba108b2107` | `shelfnote-soak-dry-c01@9920157c798f` |
| 2 | increment 2 | SN-7 | `cyc_39f69c62f20b` | accepted (7, propose) | `shelfnote-soak-c02@ff20fa02fe48` | `shelfnote-soak-dry-c02@d9634201d879` |
| 3 | increment 3 | SN-8 | `cyc_1e784bf38f3c` | accepted (7, propose) | `shelfnote-soak-c03@9ceeab42ae13` | `shelfnote-soak-dry-c03@a175ed39d38d` |
| 4 | increment 4 | SN-9 | `cyc_4875f91fd6d4` | rejected (12, repair) | `shelfnote-soak-c04@162dfa9c1cbe` | `shelfnote-soak-dry-c04@80f938625f7d` |
| 5 | repair of 4 | SN-9 | `cyc_d5ce68001c7a` | blocked_unverified (9, escalate); abandoned at the owner's seat | `shelfnote-soak-c05@5286d0d096f9` | `shelfnote-soak-dry-c05@ea1f50684e8d` |
| 6 | increment 5 | SN-10 | `cyc_b40a358f4eba` | accepted (7, propose) | `shelfnote-soak-c06@93aca6b9fa88` | `shelfnote-soak-dry-c06@dd173c6fa31c` |
| 7 | increment 6 | SN-11 | `cyc_5c03ac78e402` | rejected (12, repair) | `shelfnote-soak-c07@9622d0aba086` | `shelfnote-soak-dry-c07@cb6ca6f7c1c8` |
| 8 | repair of 6 | SN-11 | `cyc_eda5f15c88c9` | rejected (13, abandon_and_propose) | `shelfnote-soak-c08@cc3bfbe7ebab` | `shelfnote-soak-dry-c08@e5a178bcbf5d` |
| 9 | increment 7 | SN-12 | `cyc_e8cc2ffc74c0` | accepted (7, propose) | `shelfnote-soak-c09@d2712c4f6b1e` | `shelfnote-soak-dry-c09@1b18e115673a` |
| 10 | increment 8 | SN-13 | `cyc_e29f148cda8b` | rejected (12, repair) | `shelfnote-soak-c10@8c03cff56f52` | `shelfnote-soak-dry-c10@63fe0ae9e02a` |
| 11 | repair of 8 | SN-13 | `cyc_80565095ab2b` | accepted (7, propose) | `shelfnote-soak-c11@48baf5563971` | `shelfnote-soak-dry-c11@a3d42ad667f8` |
| 12 | increment 9 | SN-14 | `cyc_64b1209d4b8b` | rejected (12, repair) | `shelfnote-soak-c12@9f1cfa9a863a` | `shelfnote-soak-dry-c12@9267e38308ef` |
| 13 | repair of 9 | SN-14 | `cyc_ed47b5ec78e5` | rejected (13, abandon_and_propose) | `shelfnote-soak-c13@1f90a3cd6cf1` | `shelfnote-soak-dry-c13@d3008877f281` |
| 14 | increment 10 | SN-15 | `cyc_c4c02cd03e4f` | blocked_unverified (8, repair) | `shelfnote-soak-c14@c136e3824e4b` | `shelfnote-soak-dry-c14@f90108885eef` |
| 15 | repair of 10 | SN-15 | `cyc_b0e5258168a7` | rejected (13, abandon_and_propose); nothing pending, escalated | `shelfnote-soak-c15@2cd0d8c2dd72` | `shelfnote-soak-dry-c15@c7ca8ff5ba5d` |

The soak's Campaign completes at launch 11 (§4), so launches 12 to 15 are recorded for completeness and are named in
its `llm_scripts`, but aren't expected to run.

**The scripts were checked against the recording's own calls before the dry run.** The agents' logs for the recording
window hold one `LLM ... completed` line per model call, each followed by its handler's name. There were 218. Each was
matched to the recorded attempt its files came from (same task type, stored within 180 s after the call), and the key
the scripted provider would give it was computed the way `adapters/llm/scripted.py:105-109` counts. All 217 calls the
replay will make have an answer at their key, holding the files that call yielded. The 218th is the cut-off first call
described below.

**The recorder was fixed first** (`scripts/dev/record_llm_script.py`, this PR). Made as it stood, the scripts would
not have replayed the recording:
- **A retest took an occurrence.** A retest re-runs a repaired suite with no model call, but its stored report counted
  as a `qa.test` task. In launches 3 and 11 the next `qa.test` task would have been answered with the retest's report,
  and its own criterion never written. A retest's files are now left out (`is_retest_task_id`,
  `src/squadops/execution/correction_ids.py`).
- **A handler's records were fenced into answers.** `typed_check_evaluation` and `test_report` are what a handler
  stores about an answer, never part of it. The logs agree: each `qa.test` answer had one fenced file.
- **Every repair was recorded whole.** The vault keeps a repair's revised file, not its edits, and the repair handlers
  refuse an offered file re-emitted whole (SIP-0107 §9.4). Every replayed correction would have been refused at its
  first repair. A repair's revision is now rebuilt as one anchored edit from the file's last earlier stored version,
  and checked by applying it with the handler's own parse and apply. The 15 cycles hold 16 repair answers. Fifteen
  revise files, by 16 edits in all, and each edit was rebuilt and checked. The sixteenth, launch 11's correction
  repair, was prose with no file, and it is kept as recorded.

**The hand-written fills.** No answer was written by hand: every call has its recorded answer. One latency was:
- `shelfnote-soak-c04`, `strategy.propose_increment` occurrence 1 call 1: `latency_seconds: 108.6`. A cycle's first
  answer has no earlier stored file to measure a gap from, so the recorder gives it no latency, and the proposal would
  return in about a second. §6.3's restart lands while this task is running, so it needs one to run. The value is the
  recorded call's own 36.2 s (the strategy agent's log, 13:53:49.5 to 13:54:25.7 UTC) times `k`. The script records
  the fill under `recorded_from.hand_filled`, and its `total_seconds` includes it. The dry-run copy replays no
  latency, so it has no fill.

The dry run (§3 step 3) may still name a missing key, a call the logs show but the recorder couldn't place, or a
divergence. Any answer written by hand then is added to this list, in both sets.

**What the replay will do differently, known before the dry run:**
- **A cut-off first call isn't replayed.** In launch 10, `development.develop`'s first call ran out of tokens
  (`termination=length`, 16:08:24) and the handler asked again. The vault holds only the second answer, so the replay
  answers the first call with it, and the task makes one call instead of two.
- **Some keys are never reached.** `governance.merge_plan` calls no model, but the files it stores carry its task type,
  so each increment's script holds an answer for it (10 in all). Nine `qa.test` answers are a task's accepted outputs
  stored again after its last call. These answers are never asked for. Their latency, about 49 s over the fifteen scripts at
  `k = 3`, is never slept, and §5's sums leave it out.

## 4. The soak's Campaign

The definition is committed beside this document as `2-7-0-soak-campaign.yaml` once §9's values are known. It holds
these values:
- **The project and goals:** `project_id: prj-shelfnote`, and `objective.goals` naming §2's revision.
- **Scope and target:** `allowed_scope: ["backend/**", "tests/**"]`, and `target_accepted_increments: 6`. That's
  the recording's count of accepted increments among its first eight, and the sixth acceptance is increment 8's
  (launch 11). So the Campaign completes at increment 8's end, after eight increments of any verdict (§1; #2892,
  2026-11-09). The recording's target was 10, because its count wasn't known when it was made, and it ran on to ten
  increments. `stop_when: backlog_done` is the recording's. It doesn't fire here, because an abandoned item is never
  accepted (`_objective_met`, `src/squadops/campaigns/progress.py:2306`).
- **The squad:** `squad_profile: machinery`, `calibration_profile` and `proposal_profile` both
  `campaign-increment-source`, and `plan_gate: tier`, the recording's.
- **The scripts:** `llm_scripts`, the soak set in launch order (SIP-0109 §24dt). The first launch takes the first
  script, a repair or a retry the next one, as the recording did.
- **The limits:**
  - `max_cycles: 17`, the recording's 15 launched cycles plus 2;
  - `max_elapsed_s: 54000` (15 h);
  - `ruling_bound_s: 7200`, so the reconciliation at the push's gate (§6.2) writes no `ruling_overdue` row;
  - `unattended_resume: []`: every escalation waits for the owner;
  - the rest as the recording ran them: one repair and one retry per increment, one proposal-run retry, two proposal
    revisions, four rejected proposals in a row, ten unaccepted increments, and the recording's lease and launch-blocked
    bounds.
- **No `scenario_suite`.**

The dry run's definition, `2-7-0-soak-dry-run-campaign.yaml`, is the same but for `llm_scripts`, which names the
dry-run set.

## 5. The duration

**Replay works as built.** A scripted answer waits out its `latency_seconds` before it's returned, when its script
sets `replay_latency` (`adapters/llm/scripted.py:112-113`). It's an `asyncio.sleep` in the agent, so the task takes
real time and its heartbeats continue.

**This fixture's recorded latency alone doesn't reach nine hours.** In the vault, the five accepted `z_shelfnote`
increment cycles span 0.44, 0.25, 0.38, 1.12 and 0.28 h from their first stored file to their last: 2.5 h for five,
0.49 h on average. The cycles are `cyc_f447552e9107`, `cyc_d2e4e3e107a7`, `cyc_e1c252b75274`, `cyc_d652fe24cfc2` and
`cyc_31b493d704f6`, read from their metadata in this preparation. Eight increments replayed at their recorded gaps
give roughly 4 h of answer latency, and the backlog has 10 items, not the 18 or so that would cover nine hours at that
rate. A recorded gap also includes any gate wait between two stored files, which can outlast one task's allowance.

**So the replayed latency is the recorded gap times a declared scale `k`, held at a cap**
(`record_llm_script.py`'s `--latency-scale` and `--latency-cap`, written into each script):
- **The scale.** `k` is the smallest of 1, 1.5, 2, 2.5 and 3 for which the soak set's summed latency, over the
  scripts of the first eight increments of any verdict (§1), is at least 32,400 s. That ignores the orchestration and
  the product's own checks, which run for real on top. So the eighth increment ends after nine hours. (Drafted as "the
  first eight accepted increments"; re-read on 2026-11-09 for the call recorded on #2892 that day.)
- **The cap.** It's 1,500 s per answer, and each task's summed latency over its calls stays at most 1,500 s. The
  deploy's per-task wait is `SQUADOPS__DISPATCH__TASK_TIMEOUT=1800`.
- **The run budget.** Each run's summed latency stays at most 9,000 s, against the profile's `time_budget_seconds:
  10800` (`campaign-increment-source.yaml:61`).

If no `k` meets all three, the soak doesn't launch, and the shortfall is reported to the owner.

**`k = 3`, from the recording (2026-11-09).** The first eight increments are launches 1 to 11. The sums are over the
answers the replay asks for (§3a), and before the one hand-filled latency:

| `k` | first eight increments | longest answer | longest dispatch | longest run |
|---|---|---|---|---|
| 1 | 11,848 s | 692 s | 692 s | 1,333 s |
| 1.5 | 17,773 s | 1,038 s | 1,038 s | 2,000 s |
| 2 | 23,697 s | 1,385 s | 1,385 s | 2,667 s |
| 2.5 | 29,390 s, short | 1,500 s (1 held) | 1,500 s | 3,333 s |
| **3** | **34,968 s** | **1,500 s (1 held)** | **1,500 s** | **4,000 s** |

- **The duration:** at `k = 3` the first eight increments sum to 34,968 s, and 35,077 s with the hand-filled 108.6 s,
  against 32,400 s. At 2.5 they fall short. All fifteen scripts sum to 46,549 s.
- **The cap:** one answer is held at 1,500 s, the first framing answer of launch 1. Its recorded gap of 692 s holds
  increment 1's ten-minute gate wait.
- **The per-task wait, read per dispatch.** No dispatch waits more than 1,500 s, so the constraint holds with 300 s
  to spare. "Each task's summed latency over its calls" is read as one dispatch's, because the wait it guards is per
  dispatch: the runtime waits `TASK_TIMEOUT` for each dispatched task (`src/squadops/execution/task_dispatcher.py:459,
  567`). A failed task sent again is a fresh dispatch with a fresh wait. Every model call in the recording ran in its
  own dispatch (the agents' logs: one `executing_task` per call). Read per task id instead, two tasks exceed 1,500 s
  at `k = 3`, each over three dispatches: launch 8's `qa.test` `m003` (518, 481 and 583 s; 1,582 s) and launch 15's
  `qa.test` `m002` (540, 649 and 730 s; 1,919 s). At that reading no `k` would meet all three constraints. This
  reading is recorded here so the owner can overrule it before the launch.
- **The run budget:** the longest run sums to 4,000 s (launch 8's implementation run), against 9,000 s.
- **The expected length:** about 11 hours to the Campaign's completion at increment 8, that is, 35,077 s of latency
  plus the orchestration the gaps don't hold (about 1,200 s in the recording), §6.1's pause of at least 2,100 s, the
  gates, §6.2's reconcile and §6.5's escalation. The nine-hour mark falls during increment 8. `max_elapsed_s: 54000`
  leaves about four hours. A scaled latency
isn't the recording's own time. The soak's records give `k` with every duration they report.

**The end:** the later of the eighth increment's end, any verdict, and nine hours from the Campaign's start. The
eighth increment's end is the Campaign's completion (§4). The session's maximum lifetime (§6.4) is read whenever it falls, and "not
exercised" if the Campaign closes first.

## 6. The injections

Increments are numbered in the soak's own order, from 1. Each landing is checked in the control log before the
injection is made. An injection that can't land where it's registered isn't moved: it's recorded *not exercised*,
with why.

**Re-checked against the recording (2026-11-09).** Each landing was drafted before the recording said which
increments are accepted. The soak replays the recording's order (§3a): increments 1 to 3 accepted (SN-6, 7, 8),
increment 4 abandoned (SN-9), increment 5 accepted (SN-10), increment 6 abandoned (SN-11), increments 7 and 8 accepted
(SN-12, 13). Each injection's check is at its own section. None is moved.

### 6.1 Pause, held past the refresh token's idle limit (increment 1's gate)

- **Lands:** at increment 1's open increment gate, `awaiting_ruling`.
- **Procedure:** the supervisor pauses the Campaign and makes no authenticated call for at least 2,100 s. That's
  over Keycloak's `ssoSessionIdleTimeout` of 1,800 s in every SquadOps realm (`infra/auth/squadops-realm*.json`).
  It then resumes its own pause and rules.
- **Expected:**
  1. While paused, nothing launches and nothing is ruled.
  2. The supervisor's first call after the pause fails `401`. The cached access token has expired, and the refresh
     is refused because the session went idle, so `resolve_token` returns no token
     (`src/squadops/cli/config.py:113-118`). The CLI never re-logs in by itself.
  3. The supervisor's non-interactive login (§9) succeeds, and so do the resume and the ruling.
  4. The Campaign resumes into the gate it paused at, and increment 1 proceeds on the same proposal version.
- **Falsified by:** a launch or a ruling while paused; a resume into any other state; a second proposal; or a `401`
  after the re-login.
- **Re-checked:** increment 1 is SN-6, accepted in one cycle, so its gate is an ordinary increment gate, as assumed.

### 6.2 Upstream push, outside the allowed scope (increment 2's gate)

- **Lands:** at increment 2's open increment gate, never at increment 1's. Increment 1 is pinned at the calibration
  record's commit, and its delivery compares with the Project's inherited baseline at that commit
  (`src/squadops/execution/source_delivery.py:500-508`). A baseline re-captured during increment 1 would refuse its
  delivery. From increment 2 on, delivery compares with the previous increment's verification (`:509-525`), which
  the reconciliation doesn't touch.
- **The commit:** one new file, `docs/notes/upstream-change.md`, pushed to `main` as a fast-forward by the
  supervisor's GitHub identity (§9). Its content, exactly:

  ```markdown
  # An upstream change

  Added to `main` outside the running Campaign's scope, to move upstream under it.
  ```

  The path is outside `allowed_scope`. Its drift category is `source`, which `relevant` excludes
  (`src/squadops/projects/drift.py:124-127`). So the push alone holds no launch (`unreconciled`,
  `src/squadops/projects/sync.py:121`; `require_reconciled_upstream`, `src/squadops/api/routes/cycles/cycles.py:618`).
- **The reconciliation is made as the admin.** These routes need `admin:write`, which the supervisor doesn't hold
  (`src/squadops/api/routes/cycles/projects.py`: sync `:484`, validate `:116`, configure `:158`, baseline `:213`).
  The integration check syncs only where a contribution is pending (`src/squadops/projects/integration_check.py`,
  step 1), and none is. While increment 2's gate is open, the session driving the soak logs in as `squadops-admin`
  for these four acts only (the owner's ruling, 2026-11-08) and runs `projects sync`, `projects validate`,
  `projects configure` (the same technical block, a new revision) and `projects baseline --capture`, in that order.
  The supervisor rules on increment 2 only after all four.
- **Predicted: reconciles.** At increment 3's launch, `BranchRebase.before_launch` finds the branch's base behind the
  Project's reconciled commit and revision (`src/squadops/campaigns/branch_rebase.py:225-238, 365`). The steps:
  1. The pin is checked as reconciled (`:367`).
  2. The branch's commits are replayed onto the pushed commit with `merge-tree`, one at a time
     (`adapters/tools/git_source.py:374-440`). The branch is linear (`:409`), and its base is in its head's history
     (`:390`). Each commit touches only `backend/` and `tests/`, which the push doesn't, so none conflicts (`:426`)
     and none is dropped (`:439`).
  3. The rebased head passes the product's checks against the new inherited baseline (`branch_rebase.py:551`).
  4. Every frozen criterion's bundle holds on the product's runner (`:502-548`).
  5. One `BRANCH_REBASED` row is written (`rebase_transition`, `:241`), and increment 3 launches on the rebased head.

  The row names:
  - `base_before` the base commit, and `base` the pushed commit;
  - `replayed` with increments 1 and 2's captures, and `dropped` empty;
  - `verification: rebase_verification`, with every frozen criterion in `frozen_criteria_held`.
- **Falsified by:**
  - any of `CAMPAIGN_BRANCH_CONFLICT`, `CAMPAIGN_BRANCH_UNREBASEABLE`, `REBASED_HEAD_REGRESSED`,
    `REBASED_HEAD_UNVERIFIABLE` or `STALE_SOURCE_PRECONDITION`;
  - increment 3 launching on the old base;
  - a second rebase row.

  If the four acts can't be made while the gate is open, the push is never read. The Campaign then runs on
  its old base to the end, and the reconcile is recorded *not exercised*.
- **Re-checked:** the reconcile needs accepted increments on the branch before it, and has them. Increments 1 and 2
  (SN-6, SN-7) are both accepted, so the rebase at increment 3's launch replays their two captures. Increment 3
  (SN-8) is accepted in the recording, so a rebased head that broke it would show as a difference from the recording.
  The rebase only moves the base, and the scripts' anchors are in `backend/` and `tests/`, which the push doesn't
  touch.

### 6.3 Controlled restart of the runtime API and the agents (increment 4's proposal, in flight)

- **Lands:** while increment 4's `strategy.propose_increment` task is running. That's read from the cycle's runtime
  activities, as the verification-set driver's `crash` fault waits for its task.
- **Procedure:** `docker restart` of `runtime-api` and the six agents, in one command, on the pinned images, which
  change nothing. The image ids and the deploy record are read before and after.
- **Why there.** The scripted provider counts its keys in the agent's process (`adapters/llm/scripted.py:17-19,
  105-109`), so a restarted agent counts the cycle's remaining tasks from the first again. The proposal is its
  cycle's first task, so no task type has a task before the restart and another after it, and the fresh count gives
  every remaining task the key it had. A restart anywhere a type straddles would give a later task an earlier
  task's answer. That's the provider's limitation, not the framework's, so it isn't injected.
- **Expected:**
  1. The interrupted run is left for re-attach, not recorded failed
     (`src/squadops/execution/dispatched_flow_executor.py:1169-1174`). The startup re-attach dispatches the proposal
     task again under its task id (`src/squadops/api/runtime/main.py:1086`).
  2. The killed agent's unacknowledged delivery is redelivered, and the agent answers the task once, from its
     script's first key.
  3. The reply to the earlier send is dropped as stale (`src/squadops/execution/reply_router.py:159`, #2932).
     There is one such drop, or none if the broker didn't redeliver.
  4. The current send is answered from the agent's finished tasks, with that send's dispatch id
     (`src/squadops/agents/entrypoint.py:1138-1150`, #1929), and no second scripted call is made.
  5. The run resumes from its checkpoint, and increment 4 ends as the recording's increment 4 did.
- **Falsified by:**
  - a run failed or left `running` with no owner;
  - a second launch of increment 4;
  - a `ScriptEntryMissingError` naming a second call to the proposal;
  - increment 4 ending differently from the recording's.
- **Re-checked:** increment 4 is SN-9. In the recording, launch 4 was rejected (row 12) and repaired by launch 5. The
  repair ended `blocked_unverified` (row 9) and escalated, and the item was abandoned at the owner's seat (§6.5).
  "Ends as the recording's" therefore means exactly that sequence. The shape the restart assumes still holds: the
  proposal is its cycle's first task, and the only cycle running. Two things follow from the recording:
  1. **The proposal needs a running task to land in.** As recorded, a cycle's first answer has no latency and would
     return in about a second. Its latency is therefore hand-filled to 108.6 s (§3a).
  2. **The landing isn't moved to increment 5** (SN-10, accepted in one cycle), although the shape is the same there.
     Moving it would gain only a simpler ending to compare. The escalation that follows increment 4 comes two launches
     after the restart, and is read in §6.5 on its own terms.

### 6.4 Token expiries (throughout)

- **The access token, 600 s:** a silent refresh whenever a call finds it expired
  (`src/squadops/cli/config.py:110-117`). The supervisor makes an authenticated call at least every 900 s outside the
  pause, which keeps the session alive. **Falsified by** a `401` outside §6.1 and the maximum lifetime below.
- **The session's maximum lifetime, 28,800 s:** counted from the supervisor's last login, which is §6.1's re-login.
  At that point plus 28,800 s, a refresh is refused even within the idle limit. The next call fails `401`, the
  non-interactive login succeeds, and the next ruling succeeds. With §6.1 at increment 1, this falls about nine hours
  into the soak. **Falsified by** a refresh accepted past it, or a ruling that fails after the re-login.

- **Re-checked:** the maximum lifetime falls about 8.6 hours into the soak (§6.1's re-login at about 0.6 hours, plus
  8 hours). That's during increment 7 or 8, before the Campaign completes at about 11 hours (§5), so it's expected to
  be exercised.

### 6.5 The replay's own escalation (increment 4's repair), not an injection

- **Lands:** at launch 5, when increment 4's repair ends `blocked_unverified`, §10 row 9: escalate. This is the
  recording's control-log seq 30.
- **Procedure:** as the recording did. The supervisor's resume is refused `resume_not_delegated`, because
  `unattended_resume: []` delegates no `in_cycle_failure` (seq 31). The owner's seat resumes with
  `abandon_and_propose` (seq 32). The session driving the soak makes that resume as `squadops-admin`, on the owner's
  OK of 2026-11-09 for the recording's and the soak's rulings and resumes, recorded on that row.
- **Expected:** the same escalation row and the same refusal, then the resume to `at_proposal`, and increment 5
  proposed for SN-10.
- **Falsified by:** a different row or action at launch 5, or a resume that does anything but propose the next item.

All three expiries are read for the intended supervision identity, `squadops-supervisor` (role
`campaign-supervisor`), and posted on #2760. That issue's four questions stay the operator's.

## 7. The readings

1. **The run.** The soak reaches its end (§5), or stops only at a row of SIP-0109 §10 that names why. **Falsified
   by** a stop no row names, or an increment with no ending.
2. **The replay.** The soak's launch order, kinds and acceptances are the recording's first eight increments'
   (launches 1 to 11 of §3a: SN-6, 7, 8, 10, 12 and 13 accepted, SN-9 and 11 abandoned). Where they differ, the first
   difference is attributed to an injection or named as a finding.
3. **Scripted throughout.** Every cycle's create warns `llm_script_declared`, naming its own script. No call reaches
   the deploy's engine during the soak: the engine's own call metrics are read for the window, and every squad call
   is charted under the engine `scripted`.
4. **Each injection** lands where §6 registers it and ends as predicted, or is recorded *not exercised*, with why.

## 8. What's recorded

Records go in `var/verification_sets/2-7-0-soak/` under the main checkout:
- every control-log row, each escalation, each ruling and its time, and each cycle's runs and their endings;
- the deploy record and the image ids before and after §6.3;
- each `401` and each login, with its time, for §6.1 and §6.4;
- the `BRANCH_REBASED` row in full;
- the reply router's stale drops and each agent's `task_reply_replayed` lines around §6.3;
- the elapsed time at each acceptance.

**Every failure is recorded, and so is every injection that didn't land where it was registered.** A behavioural fix
the soak finds supersedes the deploy (plan §4.3), and the soak runs again on the new pin, under a revision of this
document.

## 9. Filled at launch

Each value is written here, in a commit, before the Campaign is created.

- **The deploy pin:** `dep_<…>`, its commit, and its seven image ids, from the passing shakeout pair (plan §4.3).
  **PLACEHOLDER**
- **The Project at the base:** `prj-shelfnote`'s development baseline commit, which must equal §2's; its Development
  Configuration revision; and its inherited baseline, ids and verdict. **PLACEHOLDER**
- **The goal set:** `prj-shelfnote`'s goal set, revision 3 (2026-11-09 12:50 UTC), holding §2's backlog SN-6 to SN-15.
  It was made as `squadops-admin` with the owner's OK (#2892, 2026-11-09).
- **The recording:**
  - Campaign `cmp_f14bab82c35f`, squad profile `full-38-tf`, deploy `dep_16a1cb4f54c8` (main `40e81a4e`), goal-set
    revision 3;
  - its 15 launched cycles in order, each with its kind, in §3a's table. No calibration cycle: the calibration is
    record `calrec_db8de50b7545`;
  - its increments: ten ended, six accepted (SN-6, 7, 8, 10, 12, 13) and four abandoned (SN-9, 11, 14, 15). That is
    at least eight increments of any verdict, the count §1 now reads (#2892, 2026-11-09). Its first eight increments,
    the soak's, hold all six acceptances.
- **The scripts:**
  - `k = 3`. Over launches 1 to 11, the summed latency is 34,968 s, or 35,077 s with the hand fill. The longest
    dispatch waits 1,500 s (one answer held at the cap), and the longest run 4,000 s (§5);
  - the soak and dry-run scripts' names and versions are in §3a's table, 30 scripts in all. The library digest, over
    those 30 and nothing else, is `b4f843e2e640`. The deploy record's `scripted` model digest must read that, or name
    the scripts added since;
  - the hand-written answers: none. One latency was hand-filled, `shelfnote-soak-c04`'s proposal at 108.6 s (§3a).
- **The dry run on the final deploy:** its Campaign id, and that it reproduced the recording's order. **PLACEHOLDER**
- **The supervisor's login,** ruled by the owner on 2026-11-08. The session driving the soak logs the CLI in as
  `squadops-supervisor` with no prompt, and logs in again the same way after §6.1's and §6.4's expiries. It reads
  `SQUADOPS_SUPERVISOR_PASSWORD` from the deploy's `.env`, where it is already held, and never prints it. This
  document adds no credential, host script or schedule.
- **The supervisor's GitHub identity** for §6.2: the owner's account, `jasonLadd`, the only one with write access to
  `z_shelfnote` (the owner's ruling, 2026-11-08).
- **§6.2's four acts** are made as `squadops-admin`, logged in the same way from `SQUADOPS_ADMIN_PASSWORD`, for those
  acts only, while increment 2's gate is open (the owner's ruling, 2026-11-08). They don't wait on the owner's hours.

## 10. What it doesn't cover

- **No model's quality.** The scripted changes are the recording's, and the soak is never read as a model run.
- **The provider's in-process count.** A restart where a task type straddles the restart isn't injected (§6.3).
- **Outcome Evaluation and sealed suites:** none is pinned.
- **A rebase that conflicts.** The push is disjoint by construction, so `CAMPAIGN_BRANCH_CONFLICT`'s path isn't read
  here.
- **The duration is partly declared.** The scale `k` stretches the recorded gaps. The soak's hours read that the
  control loop, its tokens and its sessions hold for that long, not that a recording took that long.
- **What the recorder rebuilt, not what a model wrote.** A repair's answer is the edit the recorder rebuilt from the
  stored before and after, not the model's own edit, and a cut-off first call isn't replayed (§3a). The control loop
  sees the same outcomes either way. A model's way of getting there isn't replayed.
- **Increments 9 and 10.** Their scripts are recorded, but the soak completes at increment 8 (§4), so the
  recording's end, a goal set with nothing left pending, isn't replayed.
