# 2.8.1 row-8 diagnostic record (#3222, the 2.8.1 plan's item 5)

The Campaign-level repair of a candidate the verifier couldn't read (SIP-0109 §10 row 8), played on the
Roblox product. Uncounted: the Spark ruled its gates under the owner's grant of 2026-11-16. Pre-registered by
amendments 12h and 12i of `2-8-0-demonstration-preregistration.md`; the Campaign file is
`2-8-1-row8-diagnostic-campaign.yaml`.

## 1. The result

**D1–D4 hold, on the second attempt (`cmp_2c451478218f`).** The first candidate's plays read `setup_failed` where
the baseline's identical setup was met. The Campaign routed row 8, launched a repair cycle without the fault, and
the repair's candidate passed the same frozen scenarios, by the same digests. The increment was accepted.

Two corrections to what was pre-registered, and one finding:
- **The final row is 3, not 7.** Amendment 12h's D4 and the plan's reading 5 say "the increment is accepted
  (row 7)". The Campaign ended on row 3, `stop_success`: the increment was accepted *and* the objective's
  measurement was met. Rows are read in order, and in a one-increment Campaign the accepted increment meets the
  objective, so row 3 fires before row 7 can. The predicted verdict, accepted, is what happened; the row number in
  both documents was wrong.
- **The first attempt was aborted in error, by the Spark** (§3).
- **The repair cycle wasn't shown the console's error** (§5). The diagnostic proves the routing and the
  re-check by digest. It doesn't prove that a repair can fix a real client-start error from the evidence it's
  given. Recorded on #3200.

## 2. The window

- **Named by the owner** on 2026-11-19 ("Go"), for the row-8 diagnostic, #3218's reading and #3199's plays.
- **The deploy:** framework `70b91c8d` throughout; `dep_176379613a3b` for attempt 1, then `dep_bd729a20fc2e`
  for attempt 2, once the QA agent was recreated (§3).
- **The provider:** `SQUADOPS__REMOTE_EXECUTION__PROVIDER` was switched from `none` to `runtime_api` for the
  window.
- **The worker:** `wks-484ee427` on the MacBook, with Studio on the pinned channel (amendment 12i). Studio stayed
  in front all window, and the focus guard never had to act. Every play settled `completed` on its first
  attempt. Two runtime read timeouts on claims fell outside every play.

## 3. Attempt 1, `cmp_ab3a75290809` (partly read; aborted in error)

- **The proposal:** `prop_76510cb350d7` v1, submitted 12:11:36 ET and approved by the Spark at 12:12:32.
- **D1:** the fault applied to the increment cycle's first `development.develop` attempt (neo, 12:30:14 ET,
  `scope=first_attempt`). The candidate play's own `console.txt` holds the throw from the HUD script, with its
  stack.
- **D2:** the S1 baseline (`rop-0549aee3`, 12:25–12:26) met setup, and its named check read `<absent>`. The S1
  candidate (`rop-53bc32da`, 12:31–12:33) read `setup_failed`. The Campaign decided "§10 row 8" at 12:33:05.
- **D3 started:** repair cycle `cyc_bd5078b22c8e` launched at 12:33:06, and its baseline play ran.
- **The abort, 12:34:18, by the Spark, in error.** The cycle's own outcome read
  `evaluator_gap:no_remote_execution_port`. Only `runtime-api` had been recreated at the provider switch, so the
  QA agent's in-run check had no port. The Spark read that alone as "no play reached Studio" and aborted. In
  fact the Campaign's own plays (`remote_operations`, requester `runtime-api`) had run, and row 8 had come from
  them. The MacBook lane caught it from the worker's log.
- **Filed from it:**
  - #3235: a QA agent with no port reads the gap as the candidate's, while the Campaign's plays run;
  - #3236: an abort leaves claimed operations running, and their results are accepted (the repair baseline
    settled after the abort).

## 4. Attempt 2, `cmp_2c451478218f` (read)

The QA agent was recreated with the provider (`dep_bd729a20fc2e`), and the Campaign was relaunched at 12:37:09 ET.

| Reading | Evidence | Holds |
|---|---|---|
| **D1** | neo, 12:58:23 ET: `APPLIED luau_client_throws_at_start to task=task-run_883ccd63-m000-development.develop … scope=first_attempt`. The line changed is the HUD client script's first code line. | yes |
| **D2** | Baselines met setup: `rop-aa6b3362` (S1, 12:52–12:53) and `rop-85e96b76` (S2, 12:53–12:55), their named checks `<absent>`. Every candidate play read `setup_failed`: in-run `rop-cc63574e` (S1) and `rop-a0170cf6` (S2), and the Campaign's `rop-c6031d48` (S1) and `rop-4690f5f3` (S2). Same place, same worker. Control log seq 10, 13:07:00: "cycle `cyc_e8260793f781` ended (assessed); §10 row 8". | yes |
| **D3** | Seq 11, 13:07:01: repair cycle `cyc_aeb6c8e22b64` (`kind repair`) launched, with `execution_overrides.fault_injection: []`. The profile's fault still shows in its `applied_defaults`, and the override wins. neo logged no `APPLIED` for it. | yes |
| **D4** | The repair's candidate passed both assertions in every play: in-run `rop-a8eb7d76` (S1) and `rop-4b18581d` (S2), and the Campaign's `rop-87554d90` (S1, 13:16–13:18) and `rop-22e311b6` (S2, 13:18–13:20). The scenario digests are the same in every attempt-2 and repair play: S1 `sha256:011bdb53…`, S2 `sha256:0e01cd82…`. Seq 12, 13:20:07: promote, "cycle `cyc_aeb6c8e22b64` accepted". Seq 14: completed, "§10 row 3" (§1). | yes |

**Where the fault fired, from Studio's own log** (MacBook lane, launch `20261119T170705Z`): five throws, at
12:32:09, 12:59:40, 13:01:54, 13:04:04 and 13:06:05 ET. That's once in each candidate play of both attempts, in
none of the six baseline plays, and in none of the repair cycle's six plays. Each throw was followed by the module
failing to load in the client's UI controller, which is why setup never completed.

**Elapsed:** launch to row 8, 30 minutes; row 8 to completion, 13 minutes. **Interventions:** the gate ruling on
the proposal (the Spark, under the grant). Nothing else touched attempt 2.

## 5. What the repair was shown

The plan says whether the repair cycle is shown the error is to be read, not assumed. The repair's
`development.develop` prompt (envelope `5e174138…`) carried:
- the first cycle's verdict, `blocked_unverified`;
- each blocked check, with `evaluator_gap:setup_failed`;
- each criterion as `not_run`.

**It didn't carry the console's error.** Neither the throw nor its line appears in the prompt. The repair passed
because the fault is held out of repair cycles, not because it knew what broke. A real client-start error would
reach a row-8 repair the same way rehearsal 3's did: named in every play's console, and absent from the repair's
evidence. This is recorded on #3200, whose ruling should cover both the run's correction and the evidence given
to a row-8 repair.

## 6. What this doesn't cover

- **Rows 9, 10 and 11** are covered by the wiring tests at the Campaign's continuation (item 5), not by this run.
- **Row 12** (a rejected candidate's repair) is a different route, and wasn't exercised.
- **A repair's ability to fix a client-start error** isn't shown (§5).

## 7. Who did what

- **The owner:** named the window.
- **The Spark:** launched both attempts, ruled the proposal gates under the 2026-11-16 grant, aborted attempt 1 in
  error, and read D1–D4 and the repair's evidence.
- **The MacBook lane:** ran the worker and Studio, caught the abort's error from the worker's log, and read
  Studio's log for each throw.
