# 2.4.0: the measurement window's close

The readout of the window that [the pre-registration](2-4-0-window-preregistration.md) registered. The manifest it
specified is [`2-4-0-window-manifest.json`](2-4-0-window-manifest.json), copied here as §5 requires. The full record
(the window log, every ruling and change request, every reading's raw output) is the supervisor's, under
`var/window/2-4-0/` on the Spark.

- **Window:** registered 2026-10-20 18:38Z; last campaign ended 2026-10-21 10:24:38Z; readings taken 10:24Z–11:00Z.
- **Deploy:** `dep_19dfa94c0a0a`, framework commit `92e26330`, unchanged throughout (no rebuild or redeploy, G7).
- **Suite:** revision 3, digest `db69fd37…`, 25 scenarios, pinned on every campaign.
- **Rulings:** the supervisor's, by §2's rule, unchanged throughout. 16 proposals ruled: 12 approved, 4 rejected
  (all four campaign 4's, on priority order).

---

## 1. The campaigns

| campaign | stack | outcome | accepted increments | cycles |
|---|---|---|---|---|
| 1, `cmp_83d63c2ebb50` | FastAPI + React | **success** | 3: capacity, sorting (re-proposed after its first try and that try's repair failed on #2572), seed | 6 |
| 2, `cmp_ae20bfd95bc3` | Next.js | **failure**, row 4 `unaccepted_increments` | 2: capacity, sorting. Seed failed twice, each try and repair on `only_setup_failures` (#2577), as predicted | 7 |
| 3, `cmp_e717aefe1143` | FastAPI + React | **success** | 3: capacity, sorting (through the window's first accepted repair), seed | 5 |
| 4, `cmp_263d1e49aca8` | Next.js | **aborted** | 1: capacity status in the run detail view | 6 |

**Campaign 4** proposed PRD Expansion Tier 2 item 6 (a per-participant leave button) in four of its five proposals,
with Tier 1 incomplete and no reason given. Each was rejected on §2's condition 2. `max_rejected_proposals_in_row`
paused it twice; the owner delegated the decision (2026-10-21, "you may resume or stop campaign 4 on your own
judgement"), and the supervisor resumed it once and aborted it at the second pause. A fresh proposal after a
rejection is never shown the rejection (#2593), which is consistent with the repetition. The pre-registered c4
prediction (two accepted, then a stop on seed) is **not met as written**: the campaign never reached sorting or seed.

## 2. The predictions

| | reading | verdict |
|---|---|---|
| **P1** discrimination | Capacity's two scenarios fail on each of campaigns 1–3's calibration trees and pass on the tree that added capacity (6 scenario pairs). Sorting fails on each calibration and passes on every tree that added it (6 pairs). No scenario passed on a tree known to lack its outcome. Normalization passes every tree it takes part in, on both stacks, and no increment added it: **withdrawn as evidence**. Campaign 4's capacity scenarios are `surface_absent` on both its trees | **holds, on the window's pairs.** The reference-pair arm was **not run** on this deploy (§3) |
| **P2** no step reaches the squad | The sweep searched every place §4 lists, with nothing unsearched, and found 10 of its 35 markers outside the suite's store. **Nine don't discriminate:** each value was already in deliveries the squad wrote before any suite existed, or in the repository before the suite was written. **One is a real exposure:** a held-out step value, introduced by the supervisor after the suite was drafted, is in what every agent image carries. It reached no authoring envelope, task envelope, LLM generation, workspace or delivered tree. None of the 25 markers without prior public presence was found anywhere | **falsified as written.** The nine are a flaw of §4's marker rule, read post hoc and declared as such. The remedy for the one is the owner's (D2) |
| **P3** contribution isn't acceptance | Six accepted increments are counted (capacity and sorting in campaigns 1–3). **All six read `contributed`.** Every `neutral` came from an increment the rule doesn't count: seed (no scenario covers it), campaign 4's capacity display (`surface_absent`), and unaccepted tries | **falsified as written.** Contribution and acceptance didn't separate on any counted increment |
| **P4** quality measures are stable | 12 re-measures, 3 per calibration tree: every measure spread **0** on every page (axe by impact, lint by rule, Lighthouse accessibility, best practices and performance). Across sessions, 23 of the 24 calibration Lighthouse readings at evaluation equal the close's; campaign 4's `/runs` performance moved 0.96 → 0.93 on the unchanged tree | **holds.** Within-session spread 0; between sessions at most 0.03, inside the 0.05 bound |
| **P5** the ledger matches the control log | All four ledgers read `matches_the_control_log: true`, 0 unclassified, 0 orphaned | **holds, after the supervisor classified 7 rows at the close** (§3) |
| **P6** an evaluation leaves no trace | 20 evaluation records, each naming the tree its vault files still make; all 13 accepted cycles' records equal their promoted identity; no promoted cycle lacks a record | **holds** |
| **M1** memory observes and supplies nothing | No lesson approval in force. 209 exposures across the 24 window cycles, all `none_eligible`, each seam in exactly the cycles that ran it. 9 correction rounds in 8 cycles, and 9 observations in exactly those 8 | **holds** |

## 3. What the evidence does not cover

- **P1's reference pair** (`cyc_7a4b7a6fbf0e`, `cyc_20246018f2b8`) was not evaluated on the window's deploy. No record
  exists and no on-demand evaluation route does; its last reading was live on 2026-10-18, on an earlier suite
  revision (SIP-0113 §7). P1 is read on the window's own pairs only.
- **Campaign 3's evidence package was never stored** (#2595): its accepted repair froze a criterion without its
  statement, and the digest's `KeyError` stopped the package before either part was written. Its readings come from
  a read-only rebuild with the deploy's own `materialize_package` (writes captured, nothing stored). The same rebuild
  of campaign 1 reproduced its stored package's identity exactly.
- **P2's marker rule doesn't exclude values the squad already writes.** Nine of the ten hits are that. The sweep's
  verdict stands as falsified; the reading that separates them is post hoc.
- **The intervention rows were classified at the close, not as the campaigns ran.** Seven rows waited until
  10:54Z; the classifications are the supervisor's labelled opinions.
- **Lighthouse reports two decimals,** so a performance movement under 0.005 doesn't show. Campaign 4's increment's
  −0.03 performance on `/runs` equals the drift on its unchanged calibration and is **not attributable** to it.
- **The re-measure ran from a one-line fix** (#2594): the script as registered failed at start-up before measuring
  anything. The bytes that ran are recorded (sha256 `27e0079f…`).

## 4. Also read

- **The seven safety guarantees:** all held, in all four campaigns.
- **AOR** (work class tier-1, unattended, 3 increments; four campaigns): campaign 1 is unread by design (its "every
  quality baseline held" input waits on P4's tolerance, SIP-0113 §10f); campaign 2 ended `failure`; campaign 3 has an
  intervention above advisory (its plan-gate question, an `unblock`); campaign 4 was aborted. **The rate is not yet
  read** while campaign 1 is unread. P4's result gives phase 2 the tolerance to read it.
- **Quality deltas:** Lighthouse and axe did not move on any accepted increment beyond campaign 4's drift. **Lint grew
  with every increment:** against calibration, campaign 1 19 → 67, campaign 2 27 → 53, campaign 3 23 → 78, mostly
  `PLR2004` on FastAPI and `@typescript-eslint/no-explicit-any` on Next.js.
- **The per-increment scorecard:** 12 to 23 LLM calls and 190k to 490k tokens per accepted increment; waiting (the
  ruling, the plan gate, the box and dispatch) 2 to 4 minutes of each.

## 5. Found and filed

| | what | state |
|---|---|---|
| #2572 | the authored entry-module import contradiction (campaign 1's sorting) | fixed in the window, #2573 (not deployed) |
| #2577 | Next.js new-route criteria can't discriminate (campaign 2's seed) | after the window |
| #2593 | a fresh proposal is never shown why the last one was rejected (campaign 4) | after the window |
| #2595 | a campaign with an accepted repair loses its evidence package (campaign 3) | after the window; needs a deploy |
| #2594 | the re-measure script read a config attribute that doesn't exist | fixed at the close |
| #2592 | Outcome Evaluation reads a source-backed cycle's vault tree | after the window |

## 6. Drift (§8)

Thirteen merges to main while the window was open, none deployed: #2571, #2573, #2570, #2574, #2579, #2581, #2585,
#2589, #2590, #2484, #2565, #2584 and #2594. Each is declared, additive or behavioural, in the window log. The
window's deploy ran none of them.
