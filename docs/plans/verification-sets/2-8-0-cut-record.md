# 2.8.0 cut record: what the evidence ran on, and what it doesn't cover

**The line:** `docs/plans/2-8-0-plan.md`, adopted 2026-11-11, a feature release. Its headline (§0, SIP-0118):

> A squad running on the Spark takes two consecutive small increments of an existing Roblox game from design to
> accepted source, each proved in a real play session in Roblox Studio, on a private copy of Tower Ascension.

**The outcome is "go"** (§5, §6): every row of §6's "go" column holds (§2 below). Times are ET, 2026-11-18, unless a
row says otherwise.

## 1. The deploys, and what the tag adds

| what | deploy | built from | loaded |
|---|---|---|---|
| rehearsal 3 and the counted run (`2-8-0-demonstration-record.md` §2–§4) | `dep_29fb79dcf37e` | `6ef904ad` | 294 / 0 |
| the repair diagnostic, attempt 2 (the record's §7; amendment 12g) | `dep_d8ae923c079c` | `1083c158` | 296 / 0 |
| the shakeout pair (§3) | `dep_5eb206d5f646` | `1a135f01` | 296 / 0 |

**Between the counted run's deploy and the tag** (`git log 6ef904ad..`):
- **Code, behavioural, on the played path:**
  - **#3171 and #3210:** the wrong-text fault and its fix. Opt-in through one request profile, which only the diagnostic declares.
  - **#3212** (#3152): the `no_start_declaration` gap's sentence, which a proposal on a product without a start declaration is shown. It adds a clause saying the gap stops only the scenarios that start the application. It still ends with the words the strategy skill quotes, so the skill is unchanged.
  - **What ran on the newest code:** the counted run ran on the older sentence. The shakeout pair ran on the newest code. The played path didn't run on #3212.
- **A CI input:** #3204, the evaluator's audit-ignore entry for a withdrawn advisory. No image holds it.
- **A dev script:** #3203, a replay rubric.
- **Documents:** the pre-registration's amendments 12e–12g, the demonstration record and its updates, the shakeout set configs, this record and the release commit (the version, markers, CHANGELOG, ROADMAP, SIP sweep).

The deploys report framework `2.7.0` until the post-tag rebuild, which changes only that.

## 2. §6's evidence, read

| §6 evidence ("go") | read | where |
|---|---|---|
| the machinery Campaign (#3050) green in CI on the tagged commit | to be read on the tag's CI run, every job | the release PR's merge run |
| the Luau runner's headless checks (#2906) | green in CI on main; the counted run's `tests_pass` verified on both increments | CI; the record §4 |
| Studio operations qualified unattended, including after a restart | #3117 (R5.19, R5.20): `play_scenario` on the worker's loop, including after a Studio restart with no person. #3130: the worker back after a restart and the owner's login. Requalified 2026-11-18 on Studio's channel move (12f) | SIP-0117 ledger |
| Studio sync, read-back and reset on the worker | every play of the window. The reset ran at each worker start and after a cancel, the place restored to its pin (`49157df1…`) each time | the record §2, §5, §7 |
| **the counted two-increment run, read live** | **success on attempt 1:** `cmp_7ec826c9ec22`, B-1 and B-2 accepted, C1–C7 hold for both | the record §4 |
| **the repair diagnostic, labelled apart** | **attempt 2 passes, D1–D4.** Attempt 1 didn't exercise the scenario (#3208, fixed by #3210) | the record §7 |
| a shakeout pair on the existing stacks shows them unchanged | both accepted on the final deploy, no seam finding | §3 |

## 3. The shakeout pair: one round, no seam finding

On `dep_5eb206d5f646` (`1a135f01`), `group_run`, `full-38-tf` on TensorFold, `validated-fullstack`. The set configs are `2-8-0-cut-shakeout-{fastapi-react,nextjs}.yaml`, and their exit rule was stated before the first launch. The records are under `var/verification_sets/2-8-0-cut-shakeout/` in the main checkout.

| stack | cycle | verdict | boot audit | criteria | correction rounds | wall clock | config hash (= 2.7.0's) |
|---|---|---|---|---|---|---|---|
| FastAPI + React | `cyc_63eea7a53944` | **accepted** | PASS | 21 / 21 | 0 | 21 min | `4d26be92e4bd` |
| Next.js | `cyc_0fdf27d09922` | **accepted** | PASS | 20 / 20 | 0 | 26 min | `947655d3112f` |

**One round,** so the pack's exit rule took one pair. SIP-0116 closes "with every existing stack's cycles unchanged", and these two are that evidence.

## 4. Counted outcome

- **The claim (§0) holds on the counted run's first attempt.**
- **What came before it:** the counted run was the squad's fourth attempt at B-1 and B-2. Rehearsals 1 and 2 weren't clean (framework findings #3185, #3184, #3192 and a click). Rehearsal 3 was clean, with B-1 accepted and B-2 not.
- **The proposals were ruled by the MacBook lane** under the owner's delegation (12e), and the record says so beside each ruling.
- **Every return, and the window's findings:**
  - **Every return:** 7 of 11 proposal versions were returned across rehearsal 3 and the counted run, each named in the record.
  - **The findings:** #3199 (the scenario-writing skill), #3200 (setup failure routing), #3201 (a gate-ended cycle reads active), #3205 (a replay route an API client can run), #3206 (Studio's channel invisible to the pin) and #3208 (fixed).

## 5. What the evidence doesn't cover

The plan's §6 list and the pre-registration's §10:
- **Not covered at all:** feel and visuals; multiplayer; parts, models or UI built in Studio.
- **Effects outside the scenario vocabulary:** here, B-1's floor half and B-2's duration format, both proved headless only. Nothing proves `HUD.luau` hides the hint on a floor.
- **Studio versions:** none other than `0.748.0.7481526`, which is qualified on the `production` channel (counted run) and on `zluauordereddensehashmapcontrol` (diagnostic and requalification).
- **A rate:** two increments are one run, not a rate.
- **The Campaign-level repair (§10 row 8) on a played product:** never exercised. The elapsed-time guard paused both rehearsals that reached it, and the diagnostic's repair was the run's in-run correction.
- **Lessons:** one lesson was approved after the counted run (`pat_6d8e5eb97e1bcb13@2`, `apr_68fa097635c0b7b7`). No counted cycle received it.

## 6. SIP sweep

`scripts/maintainer/sip_sweep.py 2.8.0`:
- **SIP-0116** is promotable: all six phases shipped, and the shakeout pair reads every existing stack unchanged. It is promoted in this release.
- **SIP-0118's rows close here:** phase 2g (#3042, done when "a Campaign on it passes creation preflight") and phase 3 (#3043) are shipped by this release. SIP-0118 stays accepted, since its Unity row remains.
- **SIP-0117** stays accepted, since Godot and Unity remain.
