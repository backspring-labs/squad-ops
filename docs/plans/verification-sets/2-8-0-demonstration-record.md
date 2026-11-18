# 2.8 demonstration record (#3043, SIP-0118 phase 3)

The record that `2-8-0-demonstration-preregistration.md` §9 names. Each reading below names the record it was read from.

## 1. The result

**The claim holds on the counted run's first attempt.** The counted Campaign `cmp_7ec826c9ec22` ended `completed`, `success`, at 11:37:34 ET on 2026-11-18. Its control log reads §10 row 3, objective met. B-1 and B-2 were both accepted, in order, each proved in a real play session in Roblox Studio on the private copy of Tower Ascension. C1 to C7 (§7.3) hold for both increments (§4 below).

> A squad running on the Spark takes two consecutive small increments of an existing Roblox game from design to
> accepted source, each proved in a real play session in Roblox Studio, on a private copy of Tower Ascension.

**What this is, and isn't** (§10):
- It is one run, not a rate.
- The counted run was the squad's fourth attempt at these items: after rehearsals 1, 2 and 3.
- The counted run's proposals were ruled by the MacBook lane, a Claude session, under the owner's delegation (amendment 12e), not by the owner in person.

## 2. The window

**When and where:**
- **Opened:** at about 08:01 ET on 2026-11-18, when the owner said "Ok go" in the Spark session.
- **Extended:** to 13:30 ET, when the owner said "Extend to 13:30" in the MacBook session at about 10:20.
- **Closed:** at about 11:43 ET, when the Spark closed it after the counted run, on the owner's "Cmon what's the best next step. You can make good judgments to keep things moving". The provider went back to `none` and the Spark was rebuilt as `dep_bf1c78883b45` (294 loaded, 0 not).
- **Deploy:** `dep_29fb79dcf37e`, built from `6ef904ad` (12d's "e191b89f, or main above it by documents and tests only"), with `SQUADOPS__REMOTE_EXECUTION__PROVIDER=runtime_api`. `verify_loaded.py`: 294 loaded, 0 not, including `3192-tool-unready-retries`.
- **Worker:** `macbook`, session `wks-0f6ae91341734967b91fa85877afb76a`, on `6ef904ad`, Studio `0.748.0.7481526`, the pinned version (qualification record `20261117T194035.352679Z-passed.json`).

**§3's checks, before anything played:**

| check | reading | read from |
|---|---|---|
| 1. Remote execution is bound | provider `runtime_api`, rebuilt from `6ef904ad` at 08:01–08:05 | `.env`; the rebuild log |
| 2. What loaded | 294 loaded, 0 not; record `dep_29fb79dcf37e` | `verify_loaded.py` |
| 3. The worker is serving | `macbook` online, serving `roblox-studio/play_scenario`, registered 08:06:58 | `squadops workers show macbook` |
| 4. The MacBook side is ready; the guard | Studio relaunched by the adapter's reset (08:03:13) and again by the worker's start reset (08:06:30), at the pinned version, with no update waiting. The guard ran from 08:04:19 to 11:43:15 | the MacBook lane's report; Studio's log |
| 5. One commit | the worker's checkout and the deploy were both `6ef904ad` | the MacBook lane; `git rev-parse` |

**Amendments in force:** 12a to 12e. 12d (the guard and one commit) and 12e (the delegation) were approved by the owner on 2026-11-18, in the words "approve 12d" and "Approve 12e". 12e was approved at 08:10 and merged at 08:20:21 as `77467843`. Rehearsal 3's first ruling, a return entered at 08:14:08, came between the approval and the merge. 12e touches only the document, so the deploy stayed `6ef904ad`.

**The guard's whole log** (check 4): "guard started 08:04:19 ET" and "guard stopped 11:43:15 ET (window closed)". Nothing but Studio took the front between the first launch and the last play.

## 3. Rehearsal 3 (uncounted, §6)

`cmp_83836022543d`, from `2-8-0-rehearsal-campaign.yaml` (sha256 `c7b3c017…`), ran 08:07:10 to 10:11:26 ET, so 2 h 04 m.

**B-1, accepted at 09:09:31** (§10 row 7, capture `22feffd7d5fd`), on the third version of `prop_4d88071a38e1`:

| version | at the gate | ruling (MacBook lane, 12e) | the lane's reason |
|---|---|---|---|
| v1 | 08:11:31 | return, entered 08:14:08 | "the criteria read only the lobby half; nothing reads that the hint is hidden on a floor, so a hint that never hides would pass" |
| v2 | 08:39:55 | return, entered 08:41:26 | "S3 can't be met by correct work: it waits for a player attribute named Floor, which nothing in the game sets, and walking into the portal opens the floor menu with the player still in the lobby. …" |
| v3 | 08:44:21 | approve, entered 08:45:13 | "S1 and S2 read the lobby half in play and fail on the baseline; S3 reads the floor half headless on the rule module, as §7.1's B-1 row names. …" |

B-1's six plays came out as intended:
- the baselines failed `<absent>` (08:57:23, 08:59:04);
- the run's candidates passed (09:04:04, 09:05:48);
- the Campaign's candidates passed (09:07:39, 09:09:21).

**B-2, not accepted.** Its two proposal cycles:

| proposal | version | at the gate | ruling | the lane's reason |
|---|---|---|---|---|
| `prop_4547793c7d7e` | v1 | 09:12:02 | return, 09:13:46 | "S5 would pass on a clock that shows one time and never moves: …" |
| | v2 | 09:19:47 | return, 09:21:04 | "S5 can fail on a working clock: it needs the text to be exactly 0:04 at the instant it is read, a one-second window, …" |
| | v3 | 09:24:58 | return, 09:25:36 | "S5 passes on a clock that never moves, including one stuck at 0:00: …" |
| (budget spent: `rejected_at_gate`, §10 row 6, 09:25:37) | | | | |
| `prop_265ac84a01fc` | v1 | 09:29:55 | return, 09:30:52 | "no assertion reads the clock's text, which is what the player sees: …" |
| | v2 | 09:39:10 | approve, 09:40:48 | "S5 reads the clock's text after a 15 s hold and needs it between 0:10 and 0:19: …" |

- Every return was entered with the class `criteria_not_checkable`. That class is the Spark's mapping of the lane's reason, and each ruling's notes say so.
- B-2's baselines failed `<absent>` (09:53:16, 09:54:58).
- **The squad's build threw at the client's start.** The candidate's `HUD.luau` line 311 set `.Visible` on the `TA_HUD` ScreenGui, which has `Enabled`, not `Visible`. Every play's console read `Visible is not a valid member of ScreenGui "TA_HUD"`.
- **So all six candidate plays read `setup_failed`.** Setup 1 (the title's Play button within 20 s) wasn't met. Those were the run's S5 and S6, the Campaign's S5 and S6, and the replays of frozen S1 and S2. All six staged the same `HUD.luau` (hash `dbc64001…`).
- `setup_failed` is "not executed" by design, so there was no in-run correction.
- The cycle ended at 10:10:56, `blocked_unverified`, at §10 row 8 (repair). The elapsed-time guard, past `max_elapsed_s` 7200, paused it before the repair.
- The Spark aborted the paused Campaign at 10:11:26 under the owner's grant for uncounted runs, as it had rehearsal 2.

**§6.1, clean,** read by the Spark and by the MacBook lane:

| item | reading |
|---|---|
| 1. Endings | every cycle ended at a named row: B-1 at row 7; B-2's first cycle at row 6 (`rejected_at_gate`); its second at row 8, paused |
| 2. No framework defect | none. The `setup_failed` routing is the designed one, and is filed as a question in #3200 |
| 3. No unplanned action | every ruling was the lane's under 12e, entered by the Spark; the guard never acted; nothing was done by hand in Studio |
| 4. Plays did only their scenario's steps | fourteen operations, fourteen Studio play sessions, one inside each claim. Every play_log is its scenario's declared actions or a prefix of them |
| 5. The worker held | one session, every claim on attempt 1, no reset, no refusal, no `not_executed` |

**§6.3 after the rehearsal:** at 10:12, `ta-copy.rbxl`'s sha256 equalled `ta-copy.pristine.rbxl`'s and the pin (`49157df1…`). No reload was needed, and nothing was done by hand.

**Its outcome on each item,** as the attempt before the counted run's: B-1 accepted; B-2 not accepted (the squad's build).

## 4. The counted run (§7)

`cmp_7ec826c9ec22`, from `2-8-0-counted-campaign.yaml` (sha256 `00502b64…`, the rehearsal's file except for its header comment and the objective's statement).
- **Created** at 10:30:23 ET, and **started** at 10:30:30.
- **Ended** `completed`/`success` at 11:37:34. So 1 h 07 m.

**The time rule (§3):** at the create, 3 h 00 m remained to 13:30, against rehearsal 3's 2 h 04 m plus 30 m.

**§6.2 at the create, and again after the run:**

| what | at the create | after the run | read from |
|---|---|---|---|
| the product | integrated `0beaac09` | integrated `0beaac09` | `projects show` |
| the goal set | revision 1, the only one | unchanged | `goals history` |
| backlog | B-1 `pending` (next), B-2 `pending` | B-1 `accepted` (`prop_ac54aa388c8b` v1, r1), B-2 `accepted` (`prop_ab56c66c5075` v2, r1) | `campaigns backlog` |
| memory: approvals | 1 row, 2026-10-09 | unchanged | `memory_approvals` |
| memory: exposures | — | 19, all `none_eligible`: proposal writing 3, plan writing 10, build authoring 6 | `memory_exposures` for the counted cycles |

No path carrying the rehearsal's work into a counted prompt was found.

### 4.1 B-1, the lobby hint

**Its cycle:** `cyc_e26c45c7747c`, accepted at 10:58:17, §10 row 7, capture `042d5a12b9ac`. Its runs were proposal `run_359dfce4477b`, framing `run_593127320233` and implementation `run_9fb673e9ba6e`.

**Its proposal:** `prop_ac54aa388c8b` v1 was at the gate at 10:33:28. The MacBook lane approved it under 12e, entered at 10:34:22: "S1 and S2 read the lobby half in play and fail on the baseline; P1 reads the floor half headless on the rule module, as §7.1's B-1 row names: the rule's text and visibility for the lobby and for a floor." It had no returns. Its criteria:
- **S1, scenario:** `LobbyHintLabel` text equals "Step into the portal to climb";
- **S2, scenario:** `LobbyHintLabel` visible;
- **P1, package:** `LobbyHintRules` text and visibility for the lobby and for a floor.

| reading | holds | read from |
|---|---|---|
| C1 the item | B-1 at revision 1 | the change request's `backlog_item`, `goals_revision` |
| C2 frozen before development | frozen at the approval (10:34:22). Its baselines played at 10:44–10:47, before development | control log row `rule`; the baseline operations |
| C3 fails on the baseline | `hint-text` failed `<absent>` (`rop-cb88ca26`, 10:45:48); `hint-visible` failed `<absent>` (`rop-92b8506b`, 10:47:30). The preconditions passed | the operations' records |
| C4 dev writes the Luau | `src/Client/UI/Screens/HUD.luau`, `src/Shared/Modules/LobbyHintRules.luau`, `tests/criterion_P1.spec.luau`, all within the footprint | the implementation run's artifacts |
| C5 passes on the candidate | the run's plays `rop-0d3c88b1` ("Step into the portal to climb") and `rop-0b18be68` (true); the Campaign's `rop-68eb190c` and `rop-56f62ae5`, the same. The headless suite `tests_pass` passed | records; the cycle outcome |
| C6 accepted | `promote` row 9, 10:58:17 | control log |
| C7 | n/a for B-1 | — |

**The cycle outcome:** `accepted`. Verified: the build checks, `tests_pass` and the four scenario assertions. Failed, unverified, inert and waived: none.

### 4.2 B-2, the session clock

**Its cycle:** `cyc_de850f1b65a6`, accepted at 11:37:34, which ended the Campaign at §10 row 3. Capture `791a118bfe07`. Its runs were proposal `run_65e01603a1fe` (cancelled by the return) and `run_a02a8a5faffd`, framing `run_9a82573b63ad` and implementation `run_083f055fcb00`.

**Its proposal:** `prop_ab56c66c5075`.

| version | at the gate | ruling (MacBook lane, 12e) | the lane's reason |
|---|---|---|---|
| v1 | 11:01:18 | return, entered 11:02:19, class `criteria_not_checkable` (the Spark's mapping) | "S4 passes on a clock that never moves, including one stuck at 0:00: its named check reads only that the text has a colon, and nothing reads a time that depends on how long the play waited" |
| v2 | 11:06:06 | approve, entered 11:07:42 | "S4 reads the clock's text after a 20 s hold and needs it between 0:20 and 0:29: a missing, blank or stuck clock fails, and a working one passes. P2 reads the format headless and S3 the label's visibility. The shape approved in rehearsal 3, one band higher." |

v2's criteria:
- **P2, package:** `SessionClockRules.format` for 0, 59, 65 and 125 s.
- **S3, scenario:** `SessionClockLabel` visible.
- **S4, scenario:** `SessionClockLabel` text contains "0:2" after a 20 s hold.

| reading | holds | read from |
|---|---|---|
| C1 the item | B-2 at revision 1 | the change request |
| C2 frozen before development | frozen at the approval (11:07:42). Its baselines played at 11:19–11:22 | control log; operations |
| C3 fails on the baseline (B-1's accepted tree, `7ed031b2…`) | `clock-visible` failed `<absent>` (`rop-7b531831`, 11:20:35); `clock-advanced` failed `<absent>` (`rop-a066b73d`, 11:22:37). The preconditions passed, `lobby-hint-visible` included, after the 20 s walk | records |
| C4 dev writes the Luau | `HUD.luau`, `src/Shared/Modules/SessionClockRules.luau`, `tests/criterion_P2.spec.luau`, within the footprint | artifacts |
| C5 passes on the candidate | the run's `rop-dd8e5c79` (visible true) and `rop-d419a1d0` ("0:23"); the Campaign's `rop-caf2a7d7` (true) and `rop-4a866d7c` ("0:23"). `tests_pass` passed | records; the cycle outcome |
| C6 accepted | `promote` row 17, 11:37:34 | control log |
| C7 B-2 replays B-1 | frozen S1 `rop-cedad67f` (11:35:50, "Step into the portal to climb") and frozen S2 `rop-c9fd0c37` (11:37:31, true) on B-2's candidate | records |

**The cycle outcome:** `accepted`. Verified: the build checks, `tests_pass` and the six scenario assertions. Failed, unverified, inert and waived: none.

**S4's margin, measured.** Each S4 play ran 25.1 to 25.2 s from Studio's play start to its stop. The candidate's clock read "0:23" in both plays, the reading the MacBook lane predicted from that timing for a clock started at the client's start. That leaves about 3 s below the band and 6 s above it.

### 4.3 Every attempt in the counted run (§9)

- **Proposal versions:** three. B-1 v1 approved; B-2 v1 returned, v2 approved. All rulings are above.
- **Cycles:** two. **Runs:** seven, one of them cancelled by a return.
- **Repair and retry cycles:** none. **Launch-blocked waits:** none. **Escalations:** none. **Interventions:** none.
- **Plays:** twelve operations, all claimed on attempt 1, all `completed`. Each had one Studio play session inside its claim, and each play_log is its scenario's declared actions with `stopped` "".
- **Worker unavailability:** none. Seven of the worker's requests to the runtime got no answer during the counted run, and each was answered at the next poll, none during a play: claims at 10:30:44, 10:34:35, 10:58:30, 11:02:31, 11:07:55 and 11:18:50, and a heartbeat at 11:06:37. Six were ReadTimeouts. The heartbeat was the window's one server disconnect. Most came about 13 to 16 s after a gate entry by the Spark. The MacBook lane counted seventeen across the whole window.
- **What didn't execute:** nothing, in the counted run.

## 5. The whole window's plays

28 operations, 28 Studio play sessions, one inside each claim. One worker session from 08:06:58 to its stop at 11:43:00, every claim on attempt 1, no reset after its start, no refusal, no `not_executed`. The six `setup_failed` plays are rehearsal 3's B-2 (§3), caused by the candidate. Studio stayed `0.748.0.7481526` throughout. After the last play, the place file's sha256 equalled the baseline file's and the pin.

## 6. What the evidence doesn't cover (§10)

- How the game feels or looks; more than one player; parts, models or UI built in Studio.
- **B-1's floor half and B-2's duration format.** Both are proved headless (P1, P2), not in play. Nothing proves `HUD.luau` applies the hint rule on a floor.
- **B-2's "counts up each second"** is read as "a reading in 0:20–0:29 after a 20 s hold". The vocabulary compares a reading with a value, never two readings.
- Any Studio version other than `0.748.0.7481526`.
- **Not a first attempt.** The counted run is the squad's fourth attempt at these items: rehearsal 1 (unclean, #3185/#3184), rehearsal 2 (unclean, #3192 and a click), and rehearsal 3 (clean; B-2 not accepted).
- **A rate:** two increments are one run.
- **Who ruled.** The counted proposals were ruled by a Claude session on the MacBook under 12e, at the bar the owner applied in rehearsal 2.

## 7. Not run in this window

**The repair diagnostic (§8)** waits for a later attended window. Its fault, #3171, was held unmerged until the counted run ended. It then needed its conflicts with main resolved and its checks re-run, which put its start near 12:30 against a 13:30 end. So the Spark closed the window on the counted result. The counted claim doesn't depend on it (§2).

**Also not exercised:**
- **The Campaign-level repair (§10 row 8) on a played product.** Both rehearsals that reached it (2 and 3) were paused by the elapsed-time guard before the repair launched. The diagnostic is the step meant to prove that route.
- **Interventions:** none in the counted run.

## 8. Findings from the window

- **#3199** (filed by the MacBook lane): the scenario-writing skill. Across the window, eight of B-2's proposals moved between checks that pass on broken work and checks that fail on working work. The issue carries worked examples and three rules, after #3043.
- **#3200:** a candidate's setup failure, where the baseline's identical setup was met, is routed as "not executed". So it goes unrepaired in the run, although the console names the candidate's line (rehearsal 3, B-2).
- **#3201:** a cycle a Campaign ended at the gate (`rejected_at_gate`) reads `active` on the cycle route, and rehearsal 3's abort later cancelled it.
- **Lessons, for the owner:** the rehearsals' returns are to be filed as observations for SIP-0110 lessons (the clock that must move; the floor half proved headless). Agreed with the owner on 2026-11-18, after the counted run, so as not to carry anything into it (§6.2).

## 9. Who did what

- **The owner:**
  - opened the window ("Ok go");
  - delegated the proposal rulings ("Can you just approve or return these gates. Use good judgement");
  - approved 12d and 12e;
  - ruled #3193 ("agree");
  - extended the window ("Extend to 13:30").
- **The MacBook lane:**
  - ruled every proposal in rehearsal 3 and the counted run under 12e;
  - read §3's check 4 and §6.1 item 4;
  - ran the guard and the worker.
- **The Spark:**
  - entered every ruling;
  - read §6.2 and the counted readings;
  - aborted rehearsal 3 under the owner's grant for uncounted runs;
  - created and started the counted Campaign;
  - closed the window.
- **On the counted run:** the Spark recommended deferring it after rehearsal 3, since B-2 hadn't been accepted in any rehearsal. The owner extended the window and it ran.
