# 2.8.0 early-read shakeout pair: record

**This is an early read, not the cut's shakeout pair.** One shakeout per stack ran on the deploy of main `7b79d956`, on 2026-11-16 (ET), to check one merge. That merge was #3121 (SIP-0112 H.32, SIP-0117 R5.22), which changes the runtime path and merged with no live cycle on a deployed stack. The pair is also an early read on the cut's "existing stacks' cycles unchanged". The cut's own pre-registration, pair and record come later, under the plan's §6.

## 1. The deploy

| | |
|---|---|
| main | `7b79d956` (#3121), after main CI 43875212338 passed every job |
| deploy record | `dep_b1f476ea0944`, from `rebuild_and_deploy.sh all` |
| loaded checks | `verify_loaded.py`: 266 loaded, 0 not |
| #3121's constants, read in the running containers (runtime-api, neo, eve, bob) | `ARTIFACT_CONTENTS_LIMIT_BYTES` 4,194,304, `MAX_WORKSPACE_BYTES` 3,145,728, and `ContentsOverLimit` present |
| set configs | `2-8-0-early-shakeout-fastapi-react.yaml` and `2-8-0-early-shakeout-nextjs.yaml` |

**The set configs** are the 2.7.0 shakeout pair's, with the same loaded checks. They differ in:
- their names, records directory and notes;
- tracking every row of `scripts/dev/loaded_checks.yaml`;
- leaving out the counted rolls' pins.

**The squad** is `full-38-tf` on TensorFold, as the 2.7.0 pair ran. Each cycle's config hash equals its 2.7.0 counterpart's: `4d26be92e4bd` and `947655d3112f`.

## 2. The pair, against the 2.7.0 pair

| stack | cycle | verdict | boot audit | criteria | correction rounds | wall clock | 2.7.0's shakeout |
|---|---|---|---|---|---|---|---|
| FastAPI + React | `cyc_4abb0534180f` | **accepted** | PASS (5 probes, 3 routes) | 21 / 21 | none | 22 min | accepted, PASS, 21 / 21, none, 21 min |
| Next.js | `cyc_5470423621fe` | **accepted** | PASS (5 probes, 3 routes) | 20 / 20 | none | 28 min | rejected on `tests_pass`, PASS, 20 / 21, 3 rounds, 38 min |

- **Both cycles were functional:** the verdict, the audit and zero intervention all held. Both seeded trees matched their manifests (P0 held).
- **Next.js did better than in 2.7.0.** One cycle per stack can't separate that from the variance between rolls, so it is recorded as observed, not as a change.
- **The records** are in `var/verification_sets/2-8-0-early-shakeout/<stack>/` (gitignored), to be attached to the line's release records.

## 3. #3121's live checks

- **No run ended `contents_over_limit`.** All four runs completed. Not one of the eight service containers (runtime-api, the six agents, the sandbox service) logged `ContentsOverLimit` or `contents_over_limit` from the first launch through the second cycle's end.
- **The old line is gone.** `Artifact content limit exceeded` (the pre-#3121 executor's log of a resolution cut short) appears in no container's log since the deploy.
- **Each acceptance workspace was the whole tree it should have been.**
  - **What the evaluations record:** each typed-check evaluation records the `workspace_revision_id` of its acceptance workspace. That id is a content hash, cut from the exact mapping the executor handed the task.
  - **The replay:** the deployed executor's own `_resolve_artifact_contents`, with the acceptance filter, ran over every prefix of the cycle's stored artifacts in their stored order (the framing run's, then the implementation run's).
  - **What a match means:** this is a replay of the resolution, named as one. But a matched hash means the live workspace held exactly that file set.

  **The result:** every recorded id matched.

  | stack | `development.develop` workspaces (files, in task order) | `qa.test` workspaces | the run's accepted tree |
  |---|---|---|---|
  | FastAPI + React | 25, 26, 27, 28 | 30, 30 | 30 |
  | Next.js | 33, 34, 35, 36, 37, 38, 39 | 41, 41 | 41 |

  Each development task's workspace held one file more than the one before it, as each previous task's output was accepted. Each `qa.test` was handed the whole accepted tree.

**The exit rule** (`README.md`: a pair on one deploy with no new seam finding) **holds for this deploy.** This pair found no seam defect.

## 4. On the same deploy: z_tower-ascension's checkout

The deployed `source_checkout.checkout_of` was run in runtime-api, composed as the runtime composes it. It used `prj-z-tower-ascension` at its baseline commit `0beaac09`, and started nothing.
- **Accepted:** 619 files in the tree and the manifest, 385 binary held back, and 234 files seeded, 2,880,052 bytes.
- **The margin under the 3 MiB cap** (3,145,728 bytes) is 265,676 bytes, 8.4%. A few hundred kilobytes of new source would take the product past the cap. #3041 and #3043 should plan for that.
- **The size preflight was not run,** because it runs only when a Campaign starts, and that needs #3041's profile.

## 5. What this does not cover

- **No source-backed product ran.** Both cycles are the sample application, whose trees are small: 30 and 41 files. A limit refusal (`ContentsOverLimit`) was neither reached nor injected.
- **The 4 MiB limit and the 3 MiB cap are read here only as loaded constants, and through one product's checkout.**
- **#3049's payload limits weren't exercised.** No remote operation ran, since no worker is registered with the Spark yet (#3046).
- **The deploy carries the MacBook lane's #3115, #3116, #3117 and #3119 too.** Their remote-execution paths run on no cycle of this pair.
