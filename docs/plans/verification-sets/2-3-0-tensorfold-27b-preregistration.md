# 2.3.0 — pre-registration of the 27B's held-out run on TensorFold (SIP-0111's speed and validity gates, #2199)

**Status: REGISTERED 2026-10-12, before any held-out call.** The owner's rulings, asked and answered that morning:
- **TensorFold's prompt matches Ollama's** (SIP-0111 §9c): "1, yes".
- **The tuning answers were scored before the checkpoint was chosen:** "2, check last night first".
- **Flash-Next moves to 2.4** (#2230): "3, skip to next release".
- **After §8's finding**, the owner chose "once per prompt, run on 0.6.6, NVFP4":
  - one generation per arm, the 2.3 plan's D2 at its leanest;
  - TensorFold's Python 0.6.6 engine;
  - the NVFP4 checkpoint.

The registration commit and the plan's sha256 are posted on #2199 before the run starts.

**What had to be true before it was registered, all met:**
1. **The owner chose the checkpoint and ruled on the engine line:** NVFP4 on 0.6.6 (§3, §8).
2. **The deploy is the benchmark deploy:** framework `7001c035` in every agent container, with no rebuild since R1-prime (§2).
3. **The plan file is committed** with the sha256 in §2.
4. **The frozen recipe is committed:** `infra/tensorfold/recipes/qwen27b-nvfp4.yaml`, whose `status` says frozen.

---

## 1. What the run measures

It measures whether the 27B on TensorFold beats production's Ollama on the gates SIP-0111 §4 sets. The bars are the
owner's Q2, unchanged by §9a:
- **The speed gate (G0):** the median paired wall-clock ratio, TensorFold over Ollama, is at most **0.75**, at a
  truncation rate no worse than Ollama's.
- **The validity gate (G1):** TensorFold's first-answer pass rate is at least Ollama's, **overall and per seam.**

Both are read on the held-out set only. None of its 132 envelopes has been sent to any engine. The tuning run of
2026-10-11/12 (#2199) is exploratory. It chose nothing on its own; it informs the owner's choice of checkpoint.

**What it does not measure:**
- **Application quality.** The validity gate records emission validity, never reasoning or application quality (§9a
  item 6). Cycles are the cycle comparison's to measure (G3, #2229).
- **A second candidate.** Flash-Next was moved to 2.4 by the owner on 2026-10-12 (#2230). §6 records the selection guide
  for when it runs.

## 2. The fixed parts

| what | value |
|---|---|
| the split | `docs/plans/verification-sets/2-3-0-tensorfold-split-2199.json`, sha256 `27ee298ec39e…`, posted on #2199 before the first TensorFold load |
| the plan | `docs/plans/verification-sets/2-3-0-tensorfold-held-out-plan-2199.json`, sha256 `6586370ac58c9fed…`, from `engine_replay.py plan` with seed 2199 |
| the held-out set | 132 envelopes: React 88, Next.js 44; by seam, plan writing 68, build authoring 46, repair 10, proposal writing 8 |
| generations | one per envelope per arm, seed 1001 (the owner's ruling, the 2.3 plan's D2 at its leanest), so 132 calls an arm |
| the order | the plan's: one seeded shuffle, the same for both arms, with no envelope following itself |
| the drift panel | the plan's 14 envelopes, two per seam and stack (Next.js has no proposal writing), seed 1001 |
| the draft check | the panel's first 5 envelopes, greedy, capped at 512 tokens, drafting on and then off |
| the deploy | `dep_c6cbc5110943`, framework `7001c035`: the R1-prime benchmark deploy. A rebuild before the last call voids the arms it touches |
| production's model | Ollama `qwen3.8:27b`, id `22130167c4c2`, in the `ollama` container (#2250) |
| each call's settings | the envelope's own: messages, `max_tokens` (8,192 where the capture has none) and reasoning on or off. Production's sampling (temperature 1, top_p 0.95, top_k 20, min_p 0) |
| reasoning | at parity with Ollama's prompt (§9c, ruled 2026-10-12): thinking on or off, plus the recipe's `parity_effort` |
| a call's deadline | 1,800 s; a timeout enters at its deadline and counts as a failure |
| the validators | each task type's own handler on the deploy, through `engine_replay.py score` (#2254); their revision is the container's framework SHA |

## 3. The frozen recipe

**`infra/tensorfold/recipes/qwen27b-nvfp4.yaml`, the owner's choice.** It holds:
- TensorFold 0.6.6 (`cb2ebf05`), image `squadops-tensorfold:0.6.6-cb2ebf05` (`sha256:b62567b8d89f…`);
- `nvidia/Qwen3.8-27B-NVFP4` at `482ca0f3`, served as `qwen3.8-27b-tf-nvfp4`;
- the DFlash2 drafter `z-lab/Qwen3.8-27B-DFlash2` at `50307d4c`;
- context 65,536, no thinking budget, and `parity_effort: medium`.

The recipe is unchanged from the tuning run except its `status`. Any change to it after this registration re-runs both
gates (SIP-0111 §4).

**The tuning evidence the choice was read against** (exploratory, 39 prompts per arm; #2199, #2254):

| | NVFP4 | EXL3 3.0 bpw |
|---|---|---|
| median wall-clock vs Ollama | 0.47 | 0.40 |
| first answers that passed (Ollama: 33 of 39) | 35 | 36 |
| prompt reading | 2,704 tok/s | 955 tok/s |
| hit the 12,288 cap | 0 | 1 (the prompt that cut Ollama off too) |
| TensorFold's label | none | "experimental" |

## 4. The run

Each step's records go under `var/engine_replay/<date>-held-out/` in the main checkout:
1. **Ollama's arm:**
   - `--part panel-start`;
   - `--part held-out` (132 calls);
   - `--part panel-end`.
2. **The switch to TensorFold,** by S (`engine_switch.py`), on the frozen recipe.
3. **TensorFold's arm:** the same three parts, in the same order.
4. **The draft check:** `--part draft-check --greedy --max-tokens-cap 512`, once with `--draft on` and once with
   `--draft off`.
5. **The switch back to Ollama,** and its healthy generation.
6. **Scoring and reading:** `engine_replay.py score` on both arms, then `engine_gates.py` (§5).

**What stops it:**
- the memory watchdog (S's floors: 16 GiB after load, swap);
- three failed TensorFold calls in a part (`THREE_FAILURES`), which stops that part and is reported;
- a draft-check mismatch, which stops the trial and goes to the owner (SIP-0111 §4).

**The estimate:** Ollama's arm about 8–9 h, TensorFold's about 4–5 h, the panels about 3 h, and switches and the draft
check under 1 h: about 15–17 h.

## 5. The readings, fixed now

`scripts/dev/engine_gates.py` computes every reading below from the arms' folders and the scores. It is committed
with this pre-registration, and a change to it after registration is recorded here with its reason.

**The denominator is every planned call:** 132 an arm. A failed or timed-out call is never dropped.

**The speed gate:**
- For each (envelope, generation), the paired ratio is TensorFold's wall-clock over Ollama's.
- **The bar:** the median ratio is at most 0.75. A failed TensorFold call enters at its 1,800 s deadline.
- **The truncation rate** is the share of calls that ended at their cap (`finish: length`), runaways and cut-offs
  together. TensorFold's must be no higher than Ollama's.
- **Cache treatment:**
  - TensorFold reports `cached_tokens`.
  - On Ollama, a prompt evaluation shorter than TensorFold's prompt count for the same call is a cache hit. The
    tuning run's 156 pairs matched exactly.
  - The primary timing reads pairs where neither call had a hit. Pairs with a hit are reported apart.
- **Reported** by seam, task type and stack, each with its median ratio and failures. A seam whose median is above 1.0
  is named.

**The validity gate:**
- Each answer is scored by `engine_replay.py score`: `pass` is a first answer the handler accepted without calling
  the model again. Anything else fails: `asked_again`, `failed`, `raised` or `error`.
- **The bar:** TensorFold's pass rate is at least Ollama's, overall and in each of the four seams.
- **Recorded per failure:** its class (parse, semantic, truncation, runaway reasoning, error, or the handler's own
  reason) and the handler's text.

**Uncertainty (the 2.3 plan's §5):**
- Each reading carries a 95% interval from a bootstrap that resamples envelopes (each with all its generations, here
  one): 10,000 resamples, seed 2199.
- A bar met by the point estimate is an **observed pass on this corpus.** It is evidence of non-regression only where
  the interval's unfavourable bound also meets the bar.
- A seam too small to bound is named as unbounded, not passed. Next.js repair has 2 envelopes, and proposal writing
  has 8, all React.

**Drift (the panel):**
- Each arm's panel runs before and after its held-out calls, identically.
- **The guide,** scaled from the plan's 15 of 16:
  - at least 13 of 14 identical, by the hash of thinking and text;
  - the median wall-clock change within 10%.
- Exceeding it flags the arm. The cause is read, and the owner decides whether it is re-run or read as it stands.

**The draft check:** the 5 drafted replies must be byte-identical to the plain ones (`text_sha`). A mismatch stops the
trial.

**Changed after registration (2026-10-12, before any validity verdict was read):**
- **What:** `engine_gates.py` raised on a group in which every pair had a cache hit. It now reads that group's speed
  as having no primary timing (median `None`, neither observed nor bounded) and reads its validity as any other
  group's.
- **Why:** all 8 React repair pairs reported a cached prefix on TensorFold: the same 355 tokens of the repair prompt's
  opening, on prompts of 5,381–13,206 tokens. That cell's interval had no median to bound, so the reading raised
  before writing anything. No rule changes: the primary timing still reads only pairs where neither call had a hit, and the
  overall and per-seam readings are computed as before.

## 6. The selection guide, written before either candidate's held-out run

From SIP-0111 §9a item 6, for when Flash-Next's own run is read (2.4, #2230):
- When both candidates pass both gates, **the owner selects.**
- The written guide prefers the 27B unless all three hold for Flash-Next:
  - its median paired ratio is at least 0.15 lower;
  - its validity pass rate is at least the 27B's on every seam;
  - its truncation and runaway rates are no higher.
- A choice that departs from the guide is recorded with its reason.

## 7. What the result decides

- **Both gates pass:** the adapter work (G2, #2200) starts on this recipe, then the cycle comparison (G3, #2229).
  Production does not switch on this result. That is G4, the owner's decision on G3's evidence.
- **Either gate fails:** the 27B on TensorFold is parked with its record (SIP-0111 §4, "a negative is recorded").
  Adjusting the recipe after this look makes the trial exploratory. Confirming it needs envelopes captured after the
  freeze (the 2.3 plan's §5).

## 8. The engine line, read 2026-10-12

- **TensorFold 1.0 is a native rewrite.** Its CUDA build registers only Nemotron, qualified on GB10 and Ampere
  (`docs/recipes/cuda.md` at v1.0.8). "EXL3 loading and DFlash2 drafting remain Python-engine features, not native
  upgrade paths."
- **The 27B runs only on the Python 0.6.6 engine** on the Spark, in every checkpoint this run could use. That engine is
  maintained on the `python-0.6` branch: 12 commits past the tag, the last on 2026-10-07.
- **A port is only proposed.** A community proposal to port the 27B to the native CUDA engine (ashhart/TensorFold#603)
  targets Ampere sm_86, not GB10.

So a pass here would put production on an engine line its maker has moved past, for this model on this hardware. The
switch back to Ollama took at most 28.2 s overnight. **The owner ruled to run on it** (2026-10-12, "run on 0.6.6"),
after being told that no fixes are coming for the 27B on NVIDIA and that the switch back to Ollama is the fallback.
SIP-0111 §9d records it.

## 9. The reading (2026-10-13)

The run finished at 00:01 ET on 2026-10-13, with every planned call made: 132 an arm, the panels and the draft check.
`engine_gates.py` read it as §5 fixes it, after the one change §5 records. The full reading is
`var/engine_replay/2026-10-12-held-out/reading.json`, posted on #2199 (issuecomment-6137968954).

| reading | result |
|---|---|
| G0, median paired ratio | **0.438** (interval 0.401–0.476), every seam under 1.0: an observed pass |
| G0, truncation | TensorFold 1 call, Ollama 2 |
| G1, overall | 109 of 132 against 107 of 132: an observed pass |
| G1, per seam | build authoring 41 against 38, **plan writing 55 against 56**, proposal writing 3 against 3, repair 10 against 10 |
| drift | 14 of 14 identical on each arm, median wall-clock change −0.3% and −0.2% |
| the draft check | 5 of 5 byte-identical |

**Plan writing missed §1's per-seam bar by one answer:** a Next.js `governance.prepare_plan_authoring_brief` whose YAML
did not parse (line 98, a mis-indented key), finished `stop` at 7,809 tokens. No interval in G1 is bounded, so each
validity reading, the miss included, is observed on this corpus only.

**What the owner decided** (§7, checkpoint A): "1, does not fail vailidity, let's go with TensorFold. 2, no re-run".
G1 is read as passed, the 27B goes on to G2 (#2200) on this recipe, and nothing is re-run. SIP-0111 §9e records it as
the owner's departure from the per-seam bar, with the evidence above.

**The records** are under `var/engine_replay/2026-10-12-held-out/` and travel with the 2.3 Release's records
(`attach_release_records.py`, which carries the line's engine records from this release on).
