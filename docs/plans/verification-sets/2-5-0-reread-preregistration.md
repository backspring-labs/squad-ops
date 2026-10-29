# 2.5.0 — pre-registration of Track B's re-read: the 2.4 cut's eleven trees on revisions 5 and 6, on `-7`

**Status: REGISTERED 2026-10-29, before any tree is read.** Uncounted: it measures the yardstick, not a build, and its
output is the cut's baselines (the always-pass sets the cut's no-loss reading reads).

## 1. Why it runs

The 2.5 plan's §2.2 ("the re-read") and §3 phase 2.
- **The yardstick moved twice since 2.4's baselines.**
  - The evaluator went `-5` → `-6` (#2706, #2659's driver change, #2712 and #2469's lock bumps; SIP-0113 §10x) → `-7`
    (#2637's finer quality reading; §10y, §10z).
  - The suite went revision 5 → revision 6 (#2659's two-form page scenario and the eight public step values replaced,
    §10w; approved 2026-10-24, its validation held: `var/verification_sets/2-5-0-recut/validation-readout.md`).
- **Every 2.4 reading the cut compares against was taken on `-5` and revision 5.**
- **#2637's S1 and S2 series,** the plan's third re-read item, were read on 2026-10-28 (§10z) and aren't repeated here.

## 2. What is read

- **The trees:** the 2.4 cut's seven baseline trees and its four counted rolls, eleven in all (`docs/plans/2-4-0-cut-preregistration.md`
  §4.1 and §13).

  | stack | baseline cycles | counted rolls |
  |---|---|---|
  | FastAPI + React | `cyc_4145fa7e4b4a`, `cyc_413e75801797`, `cyc_f34b2bc781ee`, `cyc_00f7cec8da9b` | `cyc_de4b598fb1d2`, `cyc_1aa7a36f28b1` |
  | Next.js | `cyc_23232c9e72da`, `cyc_42ad92a3290d`, `cyc_17dcac259f6f` | `cyc_0b6cbf9ab49c`, `cyc_007ec7f73c86` |

- **The suites,** both approved in the store:
  - revision 5: `92a26ad00f26a822458e18f4864853adb431aecd5706ed4e4146232ad9eb67fd`;
  - revision 6: `89bffc198c99b6fd347ef51d6263f6e2360a680a42bb4f01138750e44809854a`.
- **The tool:** `scripts/dev/read_scenarios.py`, each tree once (`--times 1`), through the evaluation service's own path,
  run in the runtime image as its docstring says. Revision 5 is read first, then revision 6.
- **The deploy:** `dep_0a4f31cd9c10` (from `10a35adb`), evaluator `…eslint10.12-7`. Nothing rebuilds or runs beside it
  while it reads; a merge changes no deploy and may land.
- **The comparison:**
  - each tree's revision-5 reading on `-5`: `var/verification_sets/2-4-0-cut/baseline-heldout.json`,
    `baseline-heldout-reread.json` and `readings/q1-heldout.json`;
  - its revision-5 reading here (R1);
  - its revision-6 reading here (R2).
- **The records:** `var/verification_sets/2-5-0-recut/reread-rev5.json` and `reread-rev6.json`, each with its stderr, plus
  the derived sets in `always-pass-rev6.json`. Counts and ids only reach any document.

## 3. The predictions: each names a mechanism and how it is falsified

**R1. Nothing since 2.4 changes what an HTTP scenario reads.** On revision 5, every HTTP scenario's result on each tree
here equals its result on `-5` (25 HTTP scenarios a tree).
- **Why:** HTTP steps and checks run in the sandbox's runner, not in the evaluator image.
- **The runner's known change since 2.4 that could move a result** is #2785 (SIP-0113 §10ab): a check that names a saved
  value now reads it. It moves nothing here: counted on 2026-10-29, no check in revision 5 or revision 6 names a saved
  value.
- **Falsified by:** any HTTP scenario whose result differs.

**R1b. The browser's moves are explained, one by one.** A page scenario's result on revision 5 (6 a tree) may differ
between `-5` and `-7` only through:
- #2706 (a label ending with a colon is now read);
- `-6`'s lock bumps (the browser's version).

Each difference names which. Falsified by a page scenario that differs with neither.

**R2. The suite's change moves only its changed scenario.** On `-7`, revision 6's results equal revision 5's on every
tree, except #2659's two-form page scenario. The eight replaced step values change the data sent, never the behaviour
read, so their scenarios read as before. Falsified by any other scenario whose result differs between the revisions on
the same tree.

**A tree that doesn't start** (`start_failed` or `no_runner`) is reported and re-read once. A second failure stops the
reading and is filed, since it says nothing about the yardstick.

## 4. What the reading derives

- **The always-pass sets on revision 6,** as 2.4 defined them (`docs/plans/2-4-0-cut-preregistration.md` §4.1): per
  stack, every revision-6 scenario that reads `passed` on every one of that stack's baseline trees. These are four on
  FastAPI + React and three on Next.js; the counted rolls are read, never used to derive a set.
  - Their counts and ids go to `always-pass-rev6.json`.
  - The cut's pre-registration reads them for its no-loss reading (2.5 plan §4).
- **Reported, not predicted:**
  - each tree's passed count on both revisions, beside 2.4's;
  - each scenario that moved, with its mechanism;
  - the set's change against 2.4's (5 and 4).

## 5. What it doesn't cover

- **Quality's new measures** (§10y). They are reporting-only after §10z, and this reading records them without
  reading them.
- **Revision 7** (#2723). It moves to 2.6 under the plan's deferral rule, since it wasn't ready when `-7` was.
- **Any new build.** Every tree here is 2.4's.

## 6. Records, filled as read

| what | value |
|---|---|
| revision-5 reading | |
| revision-6 reading | |
| R1, R1b, R2 | |
| always-pass sets on revision 6 | |
