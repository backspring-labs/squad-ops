# 2.7 scripted soak: pre-registration

**Status: DRAFT, prepared 2026-11-08, before any of its scripts is recorded and before its Campaign is created.** It
is registered by the commit hash of this document on its branch once every placeholder in §9 is filled, and that
commit comes before the soak's Campaign is created. It fills the 2.7 plan's §4.4 contract for #2892, amended by R6
(`z_shelfnote`, not battle-trainer). The soak is a release gate (plan §1). If it's deferred, the cut record narrows the
claim's fifth line explicitly.

## 1. What it reads

Whether the control loop lasts hours with no model in it. Every call is answered from a recorded script (#2495), so
a failure is the framework's, never a model's. The soak runs at least eight accepted increments and at least nine
hours, whichever comes later. It takes a controlled restart, token expiries up to the session's maximum lifetime, an
upstream push and a pause. Each injected event is recovered from or named, and the Campaign completes or stops only
for named reasons.

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
  added for the soak, so a recording that loses an item to abandonment still has eight to accept. They're outcomes,
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

| launch | kind | recorded from (cycle) | soak script | dry-run script |
|---|---|---|---|---|
| 1 … N | §9 | §9 | `shelfnote-soak-c01@<version>` … | `shelfnote-soak-dry-c01@<version>` … |

Each script records how its latency was made (`recorded_from.latency`: the scale, the cap, how many answers were
held at it, and the total). The set's library digest is the deploy record's `scripted` model digest
(`ScriptLibrary.digest`).

## 4. The soak's Campaign

The definition is committed beside this document as `2-7-0-soak-campaign.yaml` once §9's values are known. It holds
these values:
- **The project and goals:** `project_id: prj-shelfnote`, and `objective.goals` naming §2's revision.
- **Scope and target:** `allowed_scope: ["backend/**", "tests/**"]`, and `target_accepted_increments` set to the
  recording's count of accepted increments, at least 8.
- **The squad:** `squad_profile: machinery`, `calibration_profile` and `proposal_profile` both
  `campaign-increment-source`, `plan_gate` the recording's.
- **The scripts:** `llm_scripts`, the soak set in launch order (SIP-0109 §24dt). The first launch takes the first
  script, a repair or a retry the next one, as the recording did.
- **The limits:**
  - `max_cycles` is the recording's count of launched cycles plus 2;
  - `max_elapsed_s: 54000` (15 h);
  - `ruling_bound_s: 7200`, so the reconciliation at the push's gate (§6.2) writes no `ruling_overdue` row;
  - `unattended_resume: []`: every escalation waits for the owner.
- **No `scenario_suite`.**

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
  scripts of the first eight accepted increments, is at least 32,400 s. That ignores the orchestration and the
  product's own checks, which run for real on top. So the eighth acceptance falls after nine hours.
- **The cap.** It's 1,500 s per answer, and each task's summed latency over its calls stays at most 1,500 s. The
  deploy's per-task wait is `SQUADOPS__DISPATCH__TASK_TIMEOUT=1800`.
- **The run budget.** Each run's summed latency stays at most 9,000 s, against the profile's `time_budget_seconds:
  10800` (`campaign-increment-source.yaml:61`).

If no `k` meets all three, the soak doesn't launch, and the shortfall is reported to the owner. A scaled latency
isn't the recording's own time. The soak's records give `k` with every duration they report.

**The end:** the later of the eighth accepted increment and nine hours from the Campaign's start. The Campaign may
continue to its target after that. The session's maximum lifetime (§6.4) is read whenever it falls, and "not
exercised" if the Campaign closes first.

## 6. The injections

Increments are numbered in the soak's own order, from 1. Each landing is checked in the control log before the
injection is made. An injection that can't land where it's registered isn't moved: it's recorded *not exercised*,
with why.

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

### 6.4 Token expiries (throughout)

- **The access token, 600 s:** a silent refresh whenever a call finds it expired
  (`src/squadops/cli/config.py:110-117`). The supervisor makes an authenticated call at least every 900 s outside the
  pause, which keeps the session alive. **Falsified by** a `401` outside §6.1 and the maximum lifetime below.
- **The session's maximum lifetime, 28,800 s:** counted from the supervisor's last login, which is §6.1's re-login.
  At that point plus 28,800 s, a refresh is refused even within the idle limit. The next call fails `401`, the
  non-interactive login succeeds, and the next ruling succeeds. With §6.1 at increment 1, this falls about nine hours
  into the soak. **Falsified by** a refresh accepted past it, or a ruling that fails after the re-login.

All three expiries are read for the intended supervision identity, `squadops-supervisor` (role
`campaign-supervisor`), and posted on #2760. That issue's four questions stay the operator's.

## 7. The readings

1. **The run.** The soak reaches its end (§5), or stops only at a row of SIP-0109 §10 that names why. **Falsified
   by** a stop no row names, or an increment with no ending.
2. **The replay.** The soak's launch order, kinds and acceptances are the recording's. Where they differ, the first
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
- **The goal set:** its id and the revision holding §2's backlog. **PLACEHOLDER**
- **The recording:**
  - its Campaign id, squad profile and deploy;
  - its launched cycles in order, each with its kind;
  - its accepted count, which must be at least 8.

  **PLACEHOLDER**
- **The scripts:**
  - the scale `k`, and §5's three sums for it;
  - each soak and dry-run script's name and version, and the library digest;
  - the hand-written answers.

  **PLACEHOLDER**
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
