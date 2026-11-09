# 2.6.0 cut record

The cut rests on the machinery, on the owner's ruling of 2026-11-07: goals propose the work, Campaigns and cycles execute
it, learning returns to the goal definition, and the events are recorded. How well the tanks play, and how many increments
are accepted, are the operator's work on the released line. The measures were registered before the run, in
`2-6-0-three-increment-preregistration.md`.

## The run

`cmp_6963834274e0` on `prj-battle-trainer`, deploy `dep_2b6c8b9da0ca` (`faed0f6f`), unattended, goal set revision 9 then 11.
It ended `completed`, outcome failure, at §10 row 4 (`unaccepted_increments`), with no escalation and no person at a gate
beyond the ruler that approved each proposal as it stood.

| # | Item | Cycle | Ending | Decided |
|---|---|---|---|---|
| 1 | BT-15 Tanks get to the objectives | `cyc_0e295bfa12ce`, repair `cyc_10461009286b` | rejected, then `criteria_not_checkable` | row 12, then row 19 |
| 2 | BT-13 Tanks keep making ground | `cyc_d93eae2ab96b` | `criteria_not_checkable` | row 19 |
| 3 | BT-10 Every gun fights | `cyc_8e691eb2bccf`, repair `cyc_89192b4e02fd` | rejected, rejected | row 12, then row 13 |
| 4 | BT-11 Field a squad that wins | `cyc_2efc17faf3e5` | accepted | row 7 |
| 5 | BT-16 Tanks stay clear of each other | `cyc_fd7b58f28055`, repair `cyc_9f849319f6c9` | rejected, rejected | row 12, then row 4 |

## The measures

- **M1, goals drive the work: holds.** Each proposal named the next eligible item: BT-15, 13, 10, 11, 16.
- **M2, every increment reaches a named ending: holds.** All five did, and the stop is row 4.
- **M3, learning returns to the goal definition: holds.** Assessment 1's finding became candidate BT-16 at revision 10 and
  was promoted at revision 11. The running Campaign read 11 uninterrupted: every proposal after the promotion read it, and
  BT-16 was proposed and worked. BT-11's product reading reached BT-16's proposal (§24dk).
- **M4, events are recorded: holds, with three gaps.** The control log, ledger, digest and goal-set history show the run.
  - An assessment isn't in the digest (#2954). It is on the goal set, and its finding shows in the revisions' reasons.
  - Each ruling's note says "goal set revision 9". That was stale text in the operator's ruler script. The proposals read
    revision 11, as the control log's bindings show. The notes are as written and stay wrong.
  - The digest says repair `cyc_10461009286b`'s own failed checks were not recorded, and several cycles read `unattributed`.
- **R2, an accepted increment reaches a review request: holds.** battle-trainer PR #11, contribution `9de088f165e4`.
  **It is not merged,** and merging it is the owner's.
- **R3 is M2.**

**Reported, deciding nothing:**
- **R1:** one increment accepted of the three the Campaign aimed at.
- **R4:** BT-11 rewrote the whole controller, not only its draft. The sealed watch set of ten games read 4 wins and 16 of 30
  tanks never reaching an objective, against 3 wins and 21 of 30 at `3c5e123`. Mean path rose about 8%. That is ten games,
  and the replays have not been watched. The claim set is unopened.

## After the run

BT-10's failure read a defect. Its test summed a field `play()` doesn't return, so a real 21 shots read 0, and the squad
never saw the true shortfall against 40. A focused qa task and its repair were never shown code outside the suite's package.
#2953 fixed that after the run, and a correct test on that cycle's controller still reads 21, since its change altered
no shot. The cause of the other rejections was not traced.

## The diagnostic after the fix

`cmp_790e5aa6c641`, one increment on deploy `dep_efb3a3ae83d6` (`58e2213f`, so with #2953): not the registered run, and it counts
for no measure. It read #2953 in a live cycle. It ended `completed`, outcome success, at §10 row 3: BT-15 was accepted on its
repair `cyc_17da06e75b68`, commit `8cd435ca3f95`, after the first cycle read `blocked_unverified` at row 8.

qa's test read `play()`'s real fields, which fits the fix working. No record confirms what the prompt held, since the trace is
cut short. The test also defines `OPPONENTS = [0, 1, 2, 3]` for itself instead of importing the real names, so its games aren't
the ones the goal specifies, and its pass is weak evidence.

The sealed watch set read 3 wins and 9 of 30 tanks never reaching an objective. That is ten games, the replays have not been
watched, and the blocked share read 56.3%. The increment was built from `3c5e123` and is **not contributed**: it isn't in the
product's main, and it replaces the same controller BT-11 does.

## What this evidence does not cover

- **The tagged tree differs from the validated run's deploy.** `dep_2b6c8b9da0ca` is `faed0f6f`. The tag adds two changes:
  - #2953 is behavioural: what qa and a qa repair are shown, and what `test_report.md` says. The diagnostic ran on it.
  - #2955 changes prose and error text, the safety guarantee's label, and how a pre-§24al stored policy is read. All 118 stored
    policies read correctly through it, six of them on the old key. No Campaign has run on the tagged deploy
    `dep_bd2a684d602a`.
- **No Campaign has accepted three items.** SIP-0115 stays accepted, and its close is the operator's reading (#2954 beside it).
- **No unattended overnight run.** The soak moved to 2.7, with the sealed play claim, which the operator's work now owns.
- **The operator's own path isn't proven:** a promotion by the operator through `campaigns delegate`, and D14's check.
- **The console's Campaigns view** answered its seven data calls directly and through the proxy. No one has yet seen it
  render in a browser.
- **Open defects carried:** #2909, #2921, #2933, #2935, #2938's remainder, #2944's remainder, #2949's remainder.
