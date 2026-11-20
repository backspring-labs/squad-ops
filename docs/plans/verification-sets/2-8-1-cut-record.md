# 2.8.1 cut record: each item's done-when, read, and what the evidence doesn't cover

The 2.8.1 plan (`docs/plans/2-8-1-plan.md`, adopted 2026-11-18), a patch on the 2.8 line. This record reads every
item's **done when** (the plan's §3) and re-reads its §4 dispositions. The owner disposed of two remainders on
2026-11-20, in the Spark session, and each is named below where it applies.

## 1. The deploys, and what the tag adds

| what | deploy | built from | loaded |
|---|---|---|---|
| the row-8 diagnostic, attempt 2 (`2-8-1-row8-diagnostic-record.md`) | `dep_bd729a20fc2e` | `70b91c8d` | as the record says |
| the skills replay, revision 3 (`roblox-skills-v4-revised-3`) | the Spark's agents | `5a7cc8d3` | 301 / 0 |
| the shakeout pair (§3) | the Spark | `5c43fb4b` | as its driver logs record |
| the closing window (`2-8-1-closing-window-record.md`) | `dep_06ab48234612` | `a67dace4` | 302 / 0 |

**What the tag adds beyond the closing window's deploy:** documents only. Those are amendment 12j (#3241), the
window's record (#3242), this record and the release commit. The closing window ran every line of code the tag
carries.

**What the tag adds beyond the shakeout pair's deploy:** #3228, the Roblox scenario-writing skill (`a67dace4`).
- **What it touches:** one skill's text and assets, plus its loaded check. Only the strategy agent loads it, and only on a
  cycle whose development profile requires `roblox-increment-design` (`game_dev_roblox`).
- **Why the pair still stands:** neither web stack's cycle loads it. The change is additive for the stacks the pair
  read, so the pair wasn't rerun.

## 2. Each item's done-when, read

| item | done when | read | where |
|---|---|---|---|
| 1. #3201 | every view names the same ending; `cyc_929c449744f1` reads its end row and names the cancel | **met, as the owner ruled** (below) | §2.1 |
| 2. #3174 | an answered escalation reads `resolved`, once | **accepted on the route tests, as the owner ruled**: no escalation opened in a 2.8.1 window | §2.2 |
| 3. #3206 | the proof records the channel; no result runs off its qualification | **met** | §2.3 |
| 4. #3199 | the replay's predictions hold, both arms recorded | **met under the owner's readings** of predictions 4 and 5 (2026-11-19); #3228 merged `a67dace4` | the plan's item 4 *As run*; SIP-0118 R5.8 |
| 5. row 8 | readings 1–5 on one run, or a finding filed | **met**: D1–D4 hold on attempt 2. The row was 3, not 7, a pre-registration error the record names | `2-8-1-row8-diagnostic-record.md` |
| 6. #3218 | the threshold holds, or the owner's disposition | **met**: 32 entries, no worker request over 2 s, none timed out | `2-8-1-closing-window-record.md` §3 |
| 7. #3147 | both render tests, or the move recorded | **met**: #3229's render tests in CI; `qa-capture` 3 of 3 on a fresh capture | `2-8-1-closing-window-record.md` §4 |
| existing stacks unchanged | a shakeout pair with no seam finding | **met in round 1** | §3 |

### 2.1 Item 1: four views of every Roblox cycle

The Roblox project's 21 Campaigns (2026-11-16 to 2026-11-20) launched 28 cycles. Each was read four ways:
- the cycle route;
- `squadops cycles show`;
- the Campaign's ledger;
- the control log's ending row.

The end record (`cycle_ends`) was mapped onto the Campaign's ending by `campaigns/progress.py`'s `cycle_ending`.
`squadops campaigns show` carries the Campaign's outcome and no cycle's ending, so the Campaign's per-cycle view
read is `campaigns ledger`.

- **26 of 28 name the same ending in every view.** That includes `cyc_929c449744f1`: `failed`, `recorded_ending:
  revision_unavailable`, `status_conflict: cancelled_after_ending`, and control log row 6, `rejected_at_gate`.
- **The other two are the two Campaign repair cycles,** `cyc_aeb6c8e22b64` and `cyc_bd5078b22c8e`.
  - Each has a single workload and ended `single_workload_ended`.
  - `STATUS_OF_ENDING` maps that stop to `None`, so their statuses (`completed`, `cancelled`) come from their one run. Those
    statuses agree with the control log (`assessed`, row 3) and with the abort, which left them alone.
  - But the route names no ending for them. That is **#3244**.
- **The owner's disposition** (2026-11-20): item 1 is met, and #3244 goes to 2.9.

### 2.2 Item 2: no live reading

No escalation opened on the Spark after #3227 merged (`454f98e6`, 2026-11-19). The control log's only
`escalation_closed` row since 2026-11-17 is `cmp_1afaeaaacd46`'s, which predates the fix. So the done-when's live
read has nothing to read. What covers it:
- #3227's route tests, entered at the cycle's gate route, which the CLI takes;
- the sweep's cases;
- the loaded check `3174-escalation-ends-at-the-decision`.

**The owner's disposition** (2026-11-20): item 2 is accepted on those tests. The first escalation a person answers in a 2.9
window is read against the done-when.

### 2.3 Item 3: every 2.8.1 result against its qualification

- **The Spark's 18 remote results since 2026-11-19:** `ran_with` read equal on every one, in version, channel and tool list.
  - 15 in the row-8 window, on `zluauordereddensehashmapcontrol` / `38:3d29f729…`;
  - 3 in the closing window, on `production` / `39:b7cd2a22…`.
- **The MacBook lane's 32 hand plays for #3199:** played equals qualified in every one, established by the runner's
  refusal rule and a single Studio launch, with the two identities not printed.
  - `studio_play_scenario.py` builds the worker's runner, which reads `completed` only after its identity check, and all
    32 read `completed`.
  - One launch (13:10:40Z, `production`) served every play. Its tool list is byte-identical to the requalified one and to
    the closing window's.
  - The script doesn't print `ran_with`: #3243, unplaced.

## 3. The shakeout pair: one round, no seam finding

Built from `5c43fb4b`: `group_run`, `full-38-tf` on TensorFold, `validated-fullstack`. The set configs are
`2-8-1-cut-shakeout-{fastapi-react,nextjs}.yaml` (#3239), with the exit rule stated before the first launch. The records are under
`var/verification_sets/2-8-1-cut-shakeout/`.

| stack | cycle | verdict | criteria | correction rounds | wall clock | config hash (= 2.8.0's) |
|---|---|---|---|---|---|---|
| FastAPI + React | `cyc_db442fe686f3` | **accepted** | 22 / 22 | 0 | 21 min | `4d26be92e4bd` |
| Next.js | `cyc_731a0a691ee4` | **accepted** | 21 / 21 | 1, refunded | 36 min | `947655d3112f` |

**Next.js's one round** was a qa repair after `qa.test` m008 failed one row. The repair's emission held only reasoning,
a known class (#1658's exemption, as in 2.3.1), and the re-take passed. Two disputed checks named no failing row,
as also seen in 2.3.1. Neither is a seam finding. One round, so the exit rule took one pair.

## 4. §4's dispositions, re-read

| issue | at the cut |
|---|---|
| #3200 | unchanged; **2.9** (attribution on evidence). Row 8 is proved on a played product (item 5), and the repair wasn't shown the console's error, which is recorded on #3200 |
| #3193 | unchanged; **2.9**. The front guard ran in every 2.8.1 window and made no re-activation in the closing window |
| #3182 | unchanged; **2.9** |
| #3174 | **in**: shipped (#3227); item 2 as ruled |
| #3147 | **its condition held**: the split shipped (#3229) and was read (item 7). The per-stack move stays open, unplaced (SIP-0112 H.37) |
| #3205 | unchanged; **2.10** |
| #3218 | **in**: fixed (#3238), and the threshold holds |

**New since the plan:**
- #3243, the hand-play script printing `ran_with`: unplaced;
- #3244, a single-workload cycle's ending on the route: **2.9**, by the owner's ruling;
- #3240, the skills section ranking a declared stop below the task: unplaced;
- strategy-unobservable's example sentence: a text note for the skill's next pass.

## 5. What the evidence doesn't cover

- **2.8.1 adds no counted increment.**
  - The closing window's Campaigns were uncounted. B was the first live Campaign under the revised skill. It reached the
    skill's route after one return, not before, and one Campaign isn't a rate.
  - It isn't readiness for a supervised Campaign of useful game improvements. That is 2.10's, after 2.9 (`2-10-0-plan.md` §3).
- **The revised skill's gap:** a headless rule doesn't prove the screen uses it. Each proposal declares this, and no check fails on it.
- **Studio versions:** only `0.748.0.7481526`, on `production` (the closing window and #3199's plays) and on
  `zluauordereddensehashmapcontrol` (the row-8 window).
- **#3218:** one window, two Campaigns, three plays. A longer Campaign, with more promotions per gate, is untested.
  One non-worker request took 2.06 s (a Campaign's start).
- **Unchanged from the 2.8.0 cut record's §5:** feel and visuals; multiplayer; parts, models or UI built in Studio; effects outside the scenario vocabulary.
