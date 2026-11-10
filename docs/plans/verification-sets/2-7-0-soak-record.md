# 2.7 scripted soak: the record

**What it records:** the soak Campaign `cmp_056721e622e2` (#2892), read against its pre-registration,
`2-7-0-soak-preregistration.md`, which was registered at `b9790bb0` on `docs/2-7-0-shakeout` before the Campaign was created.
Each section below answers the pre-registration's section of the same number.

**The sources:**
- the Campaign's control log (`campaign_control_log`, rows 1–64), `campaigns` and `cycle_runs`, read in Postgres;
- the runtime API's and the agents' container logs;
- Prometheus's `squadops_llm_call_seconds_count`;
- the driver's event log, which is the supervisor's tooling and not a record of the framework.

The CLI's `campaigns digest/log/ledger` weren't used: they read through the supervisor's token cache, which the restart
diagnostic (§6.3a) was using for §6.4's reading at the time. Times are UTC.

**About the driver.** The soak was driven by a shell script that the supervisor wrote for this run. It isn't in the
repository. Every **driver defect** below is a defect in that script, the supervisor's tooling, and none is the
framework's. Each one is named where it changed what was read.

## The result

- **It completed** with outcome `success`, at §10 row 3 (`objective_met`, row 64), at the sixth acceptance, as §4 registers.
- **It ran 10 h 52 min:** created 05:06:44 (row 1) and completed 15:59:29 (row 64).
- **8 increments ended, 6 accepted.** It ran 11 cycles: 8 increments and 3 repairs.
- **Every cycle was scripted.** Each ran on `dep_d2b4ca823f07` at `ae684458`, squad `machinery`, and named its own
  soak script (`cycle_registry`).

| # | Item | Cycle | Script | Ending | Rows |
|---|---|---|---|---|---|
| 1 | SN-6 | `cyc_bcb06d3ab73b` | `shelfnote-soak-c01@e9a159c699e6` | accepted | 10, 12 (row 7) |
| 2 | SN-7 | `cyc_eef3f9a9914c` | `c02@5ed2831c5082` | accepted | 16, 18 (row 7) |
| 3 | SN-8 | `cyc_d5dbb450d5a3` | `c03@4ab10a2e2d50` | accepted, on the rebased branch | 19 (rebase), 23, 25 (row 7) |
| 4 | SN-9 | `cyc_128b97aee98a`, repair `cyc_1db4390bbb8b` | `c04@2d35a9154c75`, `c05@e516bb753704` | rejected (row 12); repair `blocked_unverified` (row 9); abandoned at the owner's seat | 30, 33, 34, 35 |
| 5 | SN-10 | `cyc_e54fdc7b4629` | `c06@9331e1c72e11` | accepted | 39, 41 (row 7) |
| 6 | SN-11 | `cyc_5e55b41f7c6a`, repair `cyc_dd01ef6a3c80` | `c07@1589a3f59980`, `c08@4362a231ae21` | rejected (row 12); repair rejected (row 13, `abandon_and_propose`) | 46, 49 |
| 7 | SN-12 | `cyc_c4c5a781dabe` | `c09@88fad7abeb9b` | accepted | 53, 55 (row 7) |
| 8 | SN-13 | `cyc_ed24b65af2bf`, repair `cyc_9b03ed54aceb` | `c10@26e2c5213ac5`, `c11@63abed2ed581` | rejected (row 12); repair accepted, and the Campaign completed (row 3) | 60, 62, 64 |

**The decision sequence** (A an acceptance, rN a §10 row, R a resume, B the rebase):
`R A r7 A r7 B A r7 r12 r9 R R A r7 r12 r13 A r7 r12 A r3`.
- The first R is §6.1's resume (row 8), and B is §6.2's rebase (row 19).
- The R R pair is §6.5: the supervisor's resume, refused (row 34), and then the owner's seat (row 35).

**The elapsed time at each acceptance**, from row 1, with `k = 3`:

| Acceptance | Row | Time | Elapsed |
|---|---|---|---|
| 1 | 10 | 06:46:53 | 1 h 40 min |
| 2 | 16 | 07:38:56 | 2 h 32 min |
| 3 | 23 | 08:30:43 | 3 h 24 min |
| 5 | 39 | 10:28:02 | 5 h 21 min |
| 7 | 53 | 13:51:43 | 8 h 45 min |
| 8 | 62 | 15:59:29 | 10 h 53 min |

**Against §5:**
- §5 expected about 11 hours, and the run took 10 h 52 min.
- The nine-hour mark, 14:06:44, fell during increment 8 (launched at row 56, 13:51:43), as §5 predicted.
- Increment 4's proposal ran 111 s (`cycle_runs`, 08:30:44 to 08:32:35). That is the hand-filled 108.6 s (§3a) landing.

## 6.1 Pause, held past the refresh token's idle limit: exercised, as predicted

- **Landed** at increment 1's open gate. The proposal `prop_7a6f1eb719a9` v1 was submitted at row 6, 05:06:58, and the
  supervisor's pause is row 7, 05:07:23 (`awaiting_ruling` → `paused`; the API answered `POST …/pause` 200).
- **Expected 1, nothing launched or ruled while paused: held.** Rows 7 and 8 are adjacent. No `mark_launched`,
  `rule` or `submit` row falls between 05:07:23 and the resume at 05:43:14.
- **Expected 2, the first call after the pause fails `401`: held.**
  - The call came at 05:43:13, 2,150 s after the pause. It was `GET /api/v1/campaigns/cmp_056721e622e2`, and the API
    answered `401 Unauthorized`.
  - The CLI printed `Error: authentication failed — Missing or invalid Authorization header`. It sent no token, which
    is what `resolve_token` returning none gives, and it didn't log in by itself.
  - The API log holds no request from the supervisor between the pause and that call.
- **Expected 3, the non-interactive login succeeds, and so do the resume and the ruling: held.** The login came at
  05:43:14. The resume is row 8 (`paused` → `awaiting_ruling`, 05:43:14), and the ruling is row 9 (05:43:51).
- **Expected 4, increment 1 proceeds on the same proposal version: held.**
  - Row 9 rules `run_9e6d44c8c389`, row 6's run, on `prop_7a6f1eb719a9` v1.
  - Increment 1 has one `submit` row, and no second proposal was made.
- **Falsifiers:** none observed.
- **A driver defect, with no effect on the reading.** The pause was applied (row 7), but the driver's check of the
  CLI's output didn't match, so it stopped with `pause_failed`. It was restarted at about 05:08:11, with the hold
  counted from row 7's time (05:07:23). It made no authenticated call while it was down.

## 6.2 Upstream push, outside the allowed scope: the prediction held; the reconcile was late

**The push landed where it was registered.**
- z_shelfnote `main` moved to `aa7fe4595d8023a72e1690d7a3a4d08a88ecaf92`, whose parent is the base `177323bed8f6`. The
  message is `docs: an upstream change outside the 2.7 soak's scope (#2892 §6.2)`, at 06:47:20, by the owner's GitHub
  account.
- That was during increment 2's open gate: the submit is row 14 (06:46:56), and the ruling row 15 (06:47:52).

**The reconcile didn't complete at that gate: a deviation, caused by two driver defects.**

| When | Act | Result | Record |
|---|---|---|---|
| 06:47:22 | `projects sync`, `projects validate` | **Failed.** Git asked for credentials (`terminal prompts disabled`). The driver omitted `--token-from-gh`, which the private repository needs | driver defect 1 |
| 06:47:23 | `projects configure` | Revision 12, at `177323bed8f6` | `project_development_configurations` |
| 06:47:51 | `projects baseline --capture` | Baseline 12, at `177323bed8f6` | `project_inherited_baselines` |
| 06:47:52 | The ruling on increment 2 | Approved (row 15), though the reconcile hadn't happened. §6.2 says the ruling comes only after all four acts succeed | |
| 07:08:46 | `sync` and `validate`, with `--token-from-gh` | **Failed:** `gh auth token` gave no token. The driver ran the admin's CLI under its own `XDG_CONFIG_HOME`, which hid gh's login | driver defect 2 |
| 07:08:47 | `configure` | Revision 13, at `177323bed8f6` | |
| 07:09:23 | `baseline --capture` | Baseline 13, at `177323bed8f6` | |
| 07:09:34 | `sync`, with gh's own configuration | Sync 12: `177323bed8f6` → `aa7fe4595d80` | `project_source_syncs` |
| 07:09:35 | `validate` | READY at `aa7fe4595d80` | |
| 07:09:36 | `configure` | Revision 14, at `aa7fe4595d80` | |
| 07:10:04 | `baseline --capture` | Baseline 14, at `aa7fe4595d80` | |

- **When the reconcile completed.** It completed at 07:10:04, during increment 2's framing run (`cycle_runs`, 06:47:54 to
  07:25:59), not at its open gate.
- **What this changes.** Increment 2's delivery compares with increment 1's verification, not with a baseline (§6.2,
  "Lands"), and it was accepted (row 16, 07:38:56). The orphan revisions and baselines 12 and 13, both at the old
  commit, are read by no row: the rebase row names revision 11 → 14.
- **What wasn't read.** "The push alone holds no launch" wasn't read: the reconcile completed before increment 3 launched.

**The prediction held: the branch reconciled.** There is one `branch_rebased` row, row 19, at 07:39:52. It shares
`lnc_68f45ecc62ca` with increment 3's launch (row 20). Its reason: "upstream moved: the campaign branch rebased from
177323bed8f6 onto aa7fe4595d80 (revision 14), head e31427929c". Its binding:

| Field | Registered | Read |
|---|---|---|
| `base_before` | the base commit | `177323bed8f6bea36eac4e8aefc8901bca13b8f4` |
| `base` | the pushed commit | `aa7fe4595d8023a72e1690d7a3a4d08a88ecaf92` |
| `replayed` | increments 1 and 2's captures | `1c452771fba8` → `4df969aafb85`, and `738561bc76ad` → `e31427929c2b`. These are increment 1's and 2's captures, rows 10 and 16 |
| `dropped` | empty | `[]` |
| `verification` | `rebase_verification` | `rebase_verification`, `art_d3aa78c076f3`: "accepted: boots, backend_tests, frontend_tests passed" |
| `frozen_criteria_held` | every frozen criterion | `T1`, `T2`, `T3`. That's every criterion frozen by then: SN-6's T1 and T2, and SN-7's T3 (the proposals `prop_7a6f1eb719a9` and `prop_8efdaa45b5da`) |
| configuration revision | | 11 → 14 |

- **Increment 3 ran on the rebased head and was accepted:** row 23, capture `c33dcdc48cc1`.
- **Falsifiers:** none. No conflict, unrebaseable, regressed, unverifiable or stale-precondition row appears; increment
  3 didn't launch on the old base; and there is no second rebase row.

## 6.3 Controlled restart: NOT EXERCISED in the soak

- **Why: a driver defect.** The restart step looked up increment 4's cycle id from the launch row's `target`, which is
  the launch id (`lnc_127c0c1e1eb9`), instead of its `binding` (`{"cycle_id": "cyc_128b97aee98a"}`, row 26). It never saw
  the proposal running.
- **The landing passed unrestarted.** Increment 4's proposal ran 08:30:44 to 08:32:35. The driver recorded the miss at
  09:11:17. As §6 requires, the landing wasn't moved.
- **Nothing was restarted during the soak.** The runtime API and the six agents had been up since 03:00–03:02
  (`docker inspect` `StartedAt`), and no deploy record follows `dep_d2b4ca823f07`. So the reply router's stale drops and the agents'
  `task_reply_replayed` lines (§8) have nothing to show: the soak's window holds none.

### 6.3a The restart diagnostic, `cmp_e27a006adea1`: exercised, every prediction held

A separate diagnostic, defined at `7813c29b` (`2-7-0-restart-diagnostic-campaign.yaml`), replays the soak's launches
1–5 and injects the restart at increment 4's proposal, as §6.3 registers it. It isn't the soak. Its readings are §6.3's
predictions, and it was running when this record was written.

Read by the supervisor, 2026-11-10. Driver records: `var/verification_sets/2-7-0-restart-diagnostic/`.
- **The landing:** increment 4's proposal run `run_b267b136d682` (`cyc_23f875e9b788`) was `running` when
  `docker restart` of the runtime API and the six agents was issued at 16:09:59Z (11:09:59 ET). The seven image ids
  were read before and after and are unchanged. The deploy record wasn't re-read.
- **Expected 1, held:** `run_left_for_reattach run=run_b267b136d682 … left as it was, for the startup re-attach`
  (16:09:48), then `campaign_cycle_reattached cycle=cyc_23f875e9b788 run=run_b267b136d682` (16:09:49).
- **Expected 2, held:** the strategy agent answered the proposal once. One emission, and `produced valid output on
  attempt 1` (16:11:43). No `ScriptEntryMissingError`.
- **Expected 3, held:** exactly one stale drop, `reply_router_stale_reply_dropped
  task=task-run_b267b136-000-strategy.propose_increment` (16:11:43,583).
- **Expected 4, held:** `task_reply_replayed: … finished here for an earlier runtime boot; a restarted runtime asked
  again, so it is answered` (16:11:43,586). No second scripted call.
- **Expected 5, held:** the proposal run completed, and increment 4 ended as the recording's did. Its decision
  sequence is `A r7 A r7 A r7 r12 r9`: increment 4 was rejected (row 12) and repaired, and the repair escalated
  (row 9) at 17:11:33Z. That's the recording's sequence through the same point.
- **Falsifiers:** none met. No run failed or was left running with no owner, increment 4 launched once, and there was
  no missing-entry error on the proposal. The diagnostic was then closed at the owner's seat, since it ends at the
  escalation.

## 6.4 Token expiries

**The access token, 600 s: exercised, and silent refresh held.**
- **How it was exercised.** The driver made an authenticated supervisor call at least every 780 s outside the pause.
  That is past the access token's 600 s lifetime, so every call after the first needed a refresh.
- **No 401 outside §6.1.** The API logged one `401` in the whole soak window (05:06–16:00), and that was §6.1's at
  05:43:13. So no call outside §6.1 found the token refused, and the falsifier ("a 401 outside §6.1") wasn't met.
- **Before 07:53:14:** the refreshes from 05:43:14 to 07:53:14 were genuine, with no login in between.

**A driver defect forced three false re-logins.**
- The driver's 401 check matched the string `401` inside a hash in the output of `campaigns show`, not an
  authentication failure. It recorded "SUPERVISOR 401" and logged in again at 07:53:15, 08:06:17 and 08:19:19.
- The API logged no `401` at any of the three times, which confirms they were false. The check was corrected at 09:11:17.
- Each login started a new session. So the session's clock runs from 08:19:19, not from §6.1's re-login.
- Refreshes from 08:19:19 to the end (15:59:29) were genuine again, with no `401` at the API.

**The session's maximum lifetime, 28,800 s: NOT EXERCISED in the soak.** Counted from 08:19:19, it falls due at about
16:19:19, after the soak completed at 15:59:29. §5 allows this ("not exercised if the Campaign closes first"). The
false re-logins are why it fell after the end: from §6.1's re-login it would have fallen due at 13:43:14, during
increment 7.

### 6.4a The maximum lifetime, read on the restart diagnostic's calls: exercised, as predicted

- **The first supervisor call past the limit,** at 16:25:03Z (11:25:03 ET), 29,144 s after the 08:19:19 login, got
  `Error: authentication failed — Missing or invalid Authorization header`. The API logged one `401` after 16:19.
  No refresh was accepted past 28,800 s: every call before it, the last at 16:12, refreshed silently.
- **The non-interactive login** succeeded at 16:25:04, and the supervisor's later calls succeeded.
- **The next ruling:** none followed. The diagnostic's next decision was the escalation, read without a ruling. So
  "the next ruling succeeds" is read as "the next authenticated calls succeed".

**Each 401 and each login** (§8):

| Time | Event | Real |
|---|---|---|
| 05:43:13 | `401` (§6.1) | yes, logged by the API |
| 05:43:14 | supervisor login | yes |
| 06:47:21 | admin login, for §6.2, under its own token cache | yes |
| 07:53:14, 08:06:16, 08:19:18 | "401" recorded by the driver | **no**: the API logged no 401 |
| 07:53:15, 08:06:17, 08:19:19 | supervisor login, forced by those false 401s | yes, and each reset the session |
| 09:44:22 | admin login, for §6.5 | yes |

## 6.5 The replay's own escalation: as predicted

- **Landed:** at launch 5. Increment 4's repair `cyc_1db4390bbb8b` ended `blocked_unverified` at row 9, and the
  Campaign escalated (row 33, 09:44:12). The failure reason was "source delivery: the product's own checks: regressed:
  backend_tests failed where the baseline did not; the repair round decided 'abort'", word for word the recording's
  `cyc_d5ce68001c7a`.
- **The supervisor's resume was refused,** at row 34, 09:44:21, with `resume_not_delegated`. The API answered `403`.
  Its binding: `class: in_cycle_failure`, `delegated: false`, `escalation: seq 33`, and "the campaign's
  unattended_resume [] does not declare in_cycle_failure".
- **The owner's seat resumed,** at row 35, 09:44:22: `abandon_and_propose`, `escalated` → `at_proposal`. It was made as
  `squadops-admin` on the owner's OK of 2026-11-09, which its reason records.
- **Increment 5 was proposed for SN-10:** the launch is row 36 (`cyc_e54fdc7b4629`), and the proposal
  `prop_185663a793c4` is row 37.
- **Falsifiers:** none. The row, the action and the refusal are the recording's (rows 30–32 there).

## 7. The readings

### 7.1 The run: holds

- The soak reached its end at §10 row 3 (row 64), after nine hours, at its sixth acceptance.
- Every increment has an ending. Every cycle's runs ended: 22 completed and 5 failed (`cycle_runs`), and none was left
  `running`.

### 7.2 The replay: holds at the Campaign's rows, with one divergence inside a run

**Against the recording, row by row.** The recording's first eight increments (`cmp_f14bab82c35f`, launches 1–11)
read `A r7 A r7 A r7 r12 r9 R R A r7 r12 r13 A r7 r12 A r7`. The soak's sequence is the same but for three
differences:
- §6.1's R, an injection;
- §6.2's B, an injection;
- the last row: r3 here, where the recording read r7. The soak completes at its target (§4).

Every launch, kind, item and acceptance is the recording's.

**Run by run, one divergence, now #3020.** Each soak run's ending was compared with the recording's run (`cycle_runs`).
Five of the six failed or repaired cycles match the recording word for word. Launch 8 (`cyc_dd01ef6a3c80`, the repair
of increment 6) doesn't:
- **What happened.** Its second `development.correction_repair`'s recorded edit was refused by the handler, which
  asked again (`repair_handlers.py:457` → `_retry_refused_anchored_edits`, `:765`). The script holds no second call. So
  the task failed with `ScriptEntryMissingError: script shelfnote-soak-c08@4362a231ae21 has no answer for
  development.correction_repair occurrence 2 call 2` (the dev agent, 12:48:53).
- **No model answered,** as the scripted contract requires.
- **How the runtime read it.** It read the failure as "repair emitted no content" and refunded the round (12:48:53). The
  correction terminated `plan_defect` (13:01:13). The run stored `Rewinding to checkpoint after qa.test failure`, where
  the recording's run reads `plan_defect: correction terminated at round 2 …`.
- **The Campaign's row is still the recording's:** row 13, `abandon_and_propose`.
- **The dry run shows the same,** at 03:26:26 on `shelfnote-soak-dry-c08@ada038395860`, with its run `cyc_41ac51f77ab5`
  failing the same way. So the dry run's "matched" (pre-registration §9) holds at the rows only.
- **The cause isn't traced.** The recording's agent logs were lost when the agents were recreated for this deploy. Whether
  the stored failure reason is right is #3020's third question.
- **What this changes.** The replay isn't faithful inside launch 8, and §7.2 reads the rows, which matched.

### 7.3 Scripted throughout: holds

- **The scripts.** Every one of the 11 cycles names its soak script in the order of §3a (`cycle_registry`). The deploy
  record's `scripted` digest reads `4721341de0a2`, §9's library digest (`deploy_records`, `dep_d2b4ca823f07`).
- **The preflight warnings.** The runtime logged 11 `cycle_create_preflight_warning` lines in the window, one per cycle.
  The log line doesn't carry the warning's code: that it is `llm_script_declared` is inferred from the script each
  cycle names.
- **The engine.** Prometheus's `squadops_llm_call_seconds_count` read as follows:
  - `engine="scripted"`: 156 at the soak's start and 312 at its end, so 156 scripted calls;
  - `engine="tensorfold"`: 56 at both times, so no call reached the engine.

  The agents had run since about 03:01, so neither counter was reset in the window. Every emission the agents logged in
  the window reads `completion_tokens=None`: 156 in all, from max (42), neo (41), nat (16), eve (42) and data (15).

### 7.4 Each injection

| Injection | Reading |
|---|---|
| §6.1 the pause | **exercised, as predicted** |
| §6.2 the upstream push | **the push landed as registered, and the prediction (reconcile) held.** The reconcile was made during increment 2's build rather than at its gate (driver defects 1 and 2) |
| §6.3 the controlled restart | **not exercised in the soak** (driver defect). Read on the diagnostic, §6.3a |
| §6.4 the access token | **exercised, silent refresh held** |
| §6.4 the refresh idle expiry | **exercised, in §6.1** |
| §6.4 the maximum lifetime | **not exercised in the soak** (it falls due after the end, because of the driver's false re-logins). Read on the diagnostic, §6.4a |
| §6.5 the escalation | **as predicted** |

## What this record doesn't cover

- **The restart and the session's maximum lifetime** are read on the diagnostic, not the soak: §6.3a and §6.4a.
- **Launch 8's replay** diverged inside its run (§7.2, #3020).
- **The upstream push's gate.** The reconcile was made during a build, not at a gate. Whether the push alone holds a
  launch wasn't read.
- **What the pre-registration's §10 names:** no model's quality, no Outcome Evaluation, no conflicting rebase, and the
  duration partly declared (`k = 3`).
- **Where the records are.** §8's records are under `var/verification_sets/2-7-0-soak/` in the main checkout, copied
  there at 16:11 UTC:
  - the control log's 64 rows with their bindings (`control-log.psv`);
  - the 27 runs (`cycle-runs.psv`);
  - the driver, its event log and its state (`driver.sh`, `driver-events.log`, `driver-state`);
  - the eight change requests ruled (`rulings/`).

  The container logs this record cites aren't copied. They last only until each container is recreated.
