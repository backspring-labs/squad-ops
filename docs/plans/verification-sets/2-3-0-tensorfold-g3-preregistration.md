# 2.3.0 — pre-registration of the 27B on TensorFold in cycles, against production Ollama (SIP-0111 G3, #2229)

**Status: DRAFT, written 2026-10-13 for the owner's review, before any G3 cycle.** It is registered when the owner
approves it. The registration commit and the four set configs are posted on #2229 before the first shakeout.

**What had to be true before it was written, all met:**
1. **G0 and G1 passed** for the 27B on the frozen NVFP4 recipe, G1 by the owner's ruling (SIP-0111 §9e).
2. **G2 shipped and ran live** (SIP-0111 §9f–§9h): the adapter, and the switch that moves the engine and every model
   client together. It was exercised on 2026-10-13 09:17–09:19 ET (#2200, issuecomment-6146480456).
3. **The deploy carries both arms' paths:** `dep_268949794186` at `cd1fca1d`, with 73 of 73 loaded checks passing.
4. **The deploy serves both squad profiles:** `full-38` (snapshot `2d8d4feb3519a7ec`) and `full-38-tf`
   (`a1280ff8ed4398b3`).

---

## 1. What it measures

G4's question: **does the squad run its regression cycles on TensorFold at least as well as on Ollama, and faster?**
G0 measured single calls, and G1 measured whether each emission was valid. Cycles are the first measure of what a
user of the squad sees: whole runs, their corrections, their verdicts and the apps they deliver. The 2.3 plan's §2.1
fixes what is read for each arm:
- cycle wall-clock, and task completion time by task type;
- emission retries, correction rounds, and the final verdict with its criteria and the boot audit;
- the decode and prefill rates the deploy's instruments log.

**What it does not measure:**
- **Application quality beyond the verdict, its criteria and the boot audit.** The rolls are the regression pair's
  own PRD, judged by its own checks.
- **Cross-Cycle Memory.** Every launch declares memory disabled (the 2.3 plan's D12), on both arms.
- **A counted result.** These rolls count for G3 only, not for the release. The 2.3 cut set, on whichever engine G4
  chooses, is the release's evidence.
- **It does not switch production.** That is G4, the owner's decision on this record.

## 2. The fixed parts

| | A: Ollama (production) | B: TensorFold |
|---|---|---|
| squad profile | `full-38` (snapshot `2d8d4feb3519a7ec`) | `full-38-tf` (`a1280ff8ed4398b3`): `full-38`'s roster and overrides on the served id, which a test holds equal (#2270) |
| model and engine | `qwen3.8:27b` (Q4_K_M), Ollama 0.32.14 in its container (#2249), settings all default | the frozen recipe `infra/tensorfold/recipes/qwen27b-nvfp4.yaml`: `nvidia/Qwen3.8-27B-NVFP4` at `482ca0f3`, the DFlash2 drafter at `50307d4c`, TensorFold 0.6.6 (`cb2ebf05`, image `sha256:b62567b8…`), context 65,536, `parity_effort: medium`, sampling 1.0 / 0.95 / 20 / 0 |
| adapter | `OllamaAdapter` | `TensorFoldAdapter` (#2269), on G0's wire |
| how the box is pointed at it | `scripts/dev/ops/engine_switch.py to-ollama` | `engine_switch.py to-tensorfold infra/tensorfold/recipes/qwen27b-nvfp4.yaml`: the engine, then the nine model clients through `docker-compose.tensorfold.yml` (§9h) |
| project and request profile | `group_run` / `validated-fullstack` | the same |
| stacks | FastAPI+React (no overrides); Next.js+TS (`build_profile` and `development_profile`: `nextjs_ts`) | the same |
| the gate | `progress_plan_review`, approved by the driver with the set's fixed text, identical on every roll | the same |
| memory | declared disabled on every launch | the same |
| the deploy | `dep_268949794186`, framework `cd1fca1d`; image ids in each set config, asserted by the driver on every measured roll. A rebuild before the last roll voids the rolls it would have touched | the same deploy, images and ids |
| set configs | `2-3-0-g3-regression-ollama-fastapi-react.yaml`, `2-3-0-g3-regression-ollama-nextjs.yaml` | `2-3-0-g3-regression-tensorfold-fastapi-react.yaml`, `2-3-0-g3-regression-tensorfold-nextjs.yaml` |

**Each set config prints its arm in the loaded checks:** the runtime API and an agent print the provider, model and
URL their containers run with, so each roll's record says which arm it was. The configs carry no config-hash pin,
as R1-prime's don't: every launch declares memory disabled, an execution override, so the roll records the hash it
launched with.

## 3. The order

1. **Two shakeouts on B, React then Next.js.** No full cycle has run on TensorFold, and they are the warm-up. They
   are recorded and flagged, and they are not G3's rolls.
   - **The exit rule** (`docs/plans/verification-sets/README.md`): a pair on one deploy with no new seam finding.
   - **A shakeout that produces a fix supersedes the deploy.** The fix merges, the deploy is rebuilt from main, and
     both shakeouts run again on the new deploy. No measured roll has run, so nothing is voided.
2. **The measured rolls, by stack: A1, B1, A2, B2 on React, then A1, B1, A2, B2 on Next.js.** That is eight rolls,
   two per arm per stack, interleaved as SIP-0111 §4 and §9a item 6 fix it.
3. **Every roll starts right after the switch to its arm,** so each arm starts on a freshly started engine: Ollama
   loads its model on the first call, and TensorFold is warm once started. The switch's record is kept beside the
   roll's.
4. **Before each roll:** the box free (the driver and the switch both check), and the arm's loaded checks answering.
5. **After the last roll:** the switch back to Ollama.

**The budget:**

| part | estimate |
|---|---|
| the shakeouts | 2 × ~30–35 min |
| A's rolls | 4 × ~55 min |
| B's rolls | 4 × ~30–35 min |
| switches | 10 × ~1 min |
| **total** | **~7.3 h** (the plan's ~8 h) |

A's estimate is the 2.0–2.3 regression rolls' median. B's applies G0's 0.44 wall-clock ratio to the ~90% of a roll that
is model time and keeps the rest unchanged, which gives about 27 minutes; the budget allows more.

## 4. The readings, fixed now

**Read for each roll:**

| reading | source |
|---|---|
| verdict; criteria verified of total; boot audit | the driver's record |
| correction rounds | the driver's `correction_rounds` |
| emission retries | the driver's `failed_emissions_banked`: each one an emission refused and asked again |
| cycle wall-clock | the driver's `wall_clock_seconds` |
| task completion time, by task type | Prefect's task runs in the cycle's flow runs (`group_run/<cycle>/…`), end minus start; the task type is the run's name. A type that runs twice counts twice |
| per model call: decode rate, prefill seconds, prompt, completion and reasoning tokens | each agent's `LLM chat_stream_with_usage completed` lines in the roll's window. Prometheus's `squadops_llm_*` histograms, labelled by engine (#2263), read over the window by exact counting, are the cross-check |

**Summarized per arm,** for each stack and for both together: the median cycle wall-clock; per task type, the median
completion time, completion tokens and decode rate; the correction rounds and emission retries; the verdicts.

**The baseline range for correction rounds** is every regression roll on Ollama from 2.0.0 to 2.3's R1-prime (the
records under `var/verification_sets/2-*-regression/`):

| stack | rolls | correction rounds | wall-clock |
|---|---:|---|---|
| FastAPI+React | 21, all accepted | 0–1 | 46.6–58.3 min |
| Next.js+TS | 16, 15 accepted (one rejection, at 2 rounds) | 0–2 | 48.8–80.5 min |

**The guide** (the 2.3 plan's §2.1). The owner reads it at G4. It is a guide, not a threshold:
1. every B roll accepted, with its boot audit passing;
2. B's correction rounds within the stack's baseline range;
3. B's median cycle wall-clock below A's, on each stack;
4. no task type's median completion time on B worse than A's by more than 10%.

**The reading order** is the Atlas A/B's: tokens first (P4), then the paired wall-clock, then the rates, then the
quality half.

## 5. The predictions, one per mechanism

| | prediction | read from |
|---|---|---|
| P1 | **Decode:** B's median decode rate is at least 1.8× A's, on every task type with two or more calls on each arm. G0 measured 0.44 of Ollama's wall-clock, and the live tier decoded at 54.3 tok/s against Ollama's ~27 | the per-call log lines |
| P2 | **Paired wall-clock:** B is faster than A in each of the four pairs | the driver's `wall_clock_seconds` |
| P3 | **Size:** B's median cycle wall-clock is at most 0.70× A's on each stack. Decode is 88–92% of a roll on Ollama (the plan's §1), so twice the decode rate would give about 0.55. Prefill, tests and dispatch, which do not speed up, set the floor | the driver's records |
| P4 | **Volume:** for each task type, B's median completion tokens are within ±20% of A's. It is the same model at the same prompt (§9c), but with different weights (NVFP4 against Q4_K_M). If this fails, speed is compared per token before any claim | the per-call log lines |
| P5 | **No engine-attributable failure:** no B roll's per-round evidence names the TensorFold path, whether a stream error, an infrastructure hold, a 401, an unconfirmed release or a deadline | per-round evidence and handler logs, never the roll-up |
| P6 | **The window holds:** no B task is held for a context overflow. The registry's window (65,536) is the served one, and the prompt guard keeps every prompt inside it | the task outcomes |
| P7 | **Quality parity:** in each pair, B's verdict, criteria and boot audit are no worse than A's | the driver's records |

**A falsified prediction stops the set for a read, not a fix**, as the 1.6.x rule has it. The owner decides whether
the set goes on.

## 6. What stops it

- **A failed switch.** It restores Ollama itself. The set stops for a read.
- **A B task held as infrastructure** (`BLOCKED`, §5.2). The set stops before the next roll: by §5.2 it is a deploy
  defect.
- **The memory floors** (S's: 16 GiB `MemAvailable` with TensorFold loaded), or any swap.
- **A seam finding in a measured roll** takes the loop rule: the fix merges, the deploy is rebuilt, and every measured
  roll starts again, since the deploy they shared has changed.
- **An unexplained red on main** (the standing rule).

## 7. The record

`docs/plans/verification-sets/2-3-0-tensorfold-g3-record.md`, beside this file, posted on #2229. It holds:
- one row per roll: arm, order, stack, cycle id, verdict, criteria, boot audit, correction rounds, emission retries and
  wall-clock;
- per task type, for each arm: the medians of completion time, completion tokens, decode rate and prefill;
- each prediction, read;
- the guide's four lines, read;
- the shakeouts, flagged.

The records go under `var/verification_sets/2-3-0-g3/` and travel with the 2.3 Release's records (#2267). **There is
no threshold.** The record reports, and the owner decides G4.

## 8. What the result decides

**G4, the owner's decision, before the 2.3 cut set** (the plan's D4):
- **On adoption:**
  - cutover by `engine_switch.py to-tensorfold`;
  - every later counted set and memory measurement restarts on TensorFold, and the 2.3 cut set is the engine's first
    counted baseline;
  - the launch gate starts reading TensorFold's residency (§9g item 7), which lands with the cutover.
- **On parking:** the record goes into SIP-0111, and 2.3 continues on Ollama.

## 9. Prohibited while open

- No rebuild, and no merge that would need one.
- No change to the recipe, the profiles, Ollama or TensorFold. A recipe change re-runs G0 and G1.
- No other cycle or campaign on the box.
- The record is written from per-round evidence before any conclusion.

## 10. Choices this draft makes, for the owner's review

1. **TensorFold shakeouts only, none on Ollama.** This deploy's changes since R1-prime are inert on Ollama's path:
   - the termination field is unset on Ollama, so its cap reads the token count as before;
   - Ollama raises no overflow;
   - no call sets a seed;
   - the API's error bodies change only on errors;
   - the metrics gain a label.

   An Ollama shakeout would cost about 55 minutes. A seam finding in an A roll still takes §6's loop rule.
2. **A, B, A, B, as ruled.** Each pair puts Ollama first. Each roll starts on a freshly switched engine, which levels
   most of what order could carry. The Atlas A/B's A, B, B, A balanced order is the alternative.
3. **Two rolls per arm per stack.** That is the plan's budget. A third pair per stack would add about 3 h.
