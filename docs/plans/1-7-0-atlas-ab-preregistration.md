# 1.7.0 — the Atlas A/B, pre-registration (#1160, SIP-0106 P5)

**Written 2026-08-28, before any counting cycle.** The artifact the switch decision reads
(SIP-0106 §3.6.1, §4.2). Two deploys, not two engines: the owner's ruling of 2026-08-28 —
*"keep Ollama fixed at what we have been running basically out of the box, but put the
effort to determine a better tuned config on the Atlas side"* — replaces Appendix C's
"same weights at the same quantization" precondition with **each arm is its production
configuration, stated in full**. The tuning pass that chose arm B is on #1160.

## 1. Fixed parameters

| | Arm A — Ollama (production, untouched) | Arm B — Atlas (tuned) |
|---|---|---|
| squad profile | `full-38` | `full-38-atlas` — the same roster and eve override, model named as Atlas serves it |
| model | `qwen3.8:27b`, **Q4_K_M** (Ollama's tag), 262K native window | `Qwen/Qwen3.8-27B-FP8`, **FP8 dequantized to BF16 in memory**, served window 64K (§1.4) |
| engine | Ollama 0.32.14 as deployed; no tuning — every 1.6.x record sits on it | `avarok/atlas-gb10:latest` (built 2026-08-15), `serve Qwen/Qwen3.8-27B-FP8 --speculative --num-drafts 3 --enable-prefix-caching --scheduling-policy slai --max-seq-len 65536 --gpu-memory-utilization 0.75 --request-timeout 1800 --content-loop-watchdog false --lm-head-dtype bf16 --kv-cache-dtype bf16 --dump /dumps/atlas-requests.jsonl --bind 0.0.0.0 --require-auth --auth-tokens-file … --no-auto-swap --no-tui` (`--request-timeout` added by §1.1; `--content-loop-watchdog false --lm-head-dtype bf16` by §1.2; `--kv-cache-dtype bf16` replacing `fp8` and `--dump` by §1.3; `--max-seq-len` raised from `32768` by §1.4) |
| why that serve line | — | the tuning matrix (#1160): FP8 12.5 t/s → MTP speculative K=3 29.5 → **K=4 33.8** → K=5 23.0 (over-drafting); NVFP4 12.8 and also dequantized (no memory or speed gain). Token counts identical across rows on the fill brief |
| how the deploy is pointed at B | — | `docker compose -f docker-compose.yml -f docker-compose.atlas.yml up -d` (`ATLAS_MODEL=Qwen/Qwen3.8-27B-FP8`, secret `atlas_api_key`); back to A with plain `docker compose up -d`. Recreating the containers is also Appendix C.3's "restart the agent containers between arms" |
| project / request profile | `group_run` / `validated-fullstack` | same |
| stacks | **Next.js+TS** (`nextjs_ts` overrides) for the paired wall-clock — the 1.6.6 arm that ran 6/6, so verdict noise does not swamp the pair; then **one FastAPI+React pair** for correction texture (Appendix C.3's sleeper metric needs a stack where corrections happen — 1.6.6 ran 4/6 there) | same |
| order | **A1, B1, B2, A2** (Next.js), then **A3, B3** (FastAPI+React) — the first pair A-first, the second B-first, so an ordering effect shows instead of being credited to one side | |
| shakeout | one non-counting Atlas cycle before B1 (no cycle has ever run on Atlas: the model preflight over `/v1/models`, the 32K guard, the fenced parser on Atlas output, timeouts at 2.8× decode). It is also the warm-up Appendix C.2 requires, recorded and flagged | |
| frozen deploy | the ids are **not listed here** — they have been superseded three times (§1.1's rebuild, §1.4's, and the #1171/#1172/#1173 rebuild), and a table that names one deploy while the box runs another is worse than a pointer. The operative record is `frozen_deploy_commit` + `frozen_image_ids` in the four set files, committed before the first counting roll and asserted by the driver on every counting roll (`verification_set_driver.py`); identical for both arms | |
| engine isolation (C.2) | before every B cycle: `ollama ps` empty (keep-alive has paged the models out); before every A cycle: the `atlas` container stopped. Neither checkpoint coexists with Ollama-27B in the Spark's unified memory at usable KV | |

### 1.1 Revision after the first shakeout (2026-08-28, `cyc_6e068cdd7de0`, failed)

The first Atlas cycle failed at `governance.prepare_plan_authoring_brief`: its `high`
framing generations ended at exactly 300 s with `finish_reason: "timeout"` and half a
YAML. **The cause is Atlas's server-side `--request-timeout` (default 300 s)**, which cuts
a request and returns the partial output as a 200 — not the reasoning tier: the checkpoint's
own chat template defaults to `xhigh` when no effort is given, so Ollama's `think: true`
renders the same instruction, and the 1.6.6 Next.js rolls show Ollama's framing generations
running **183–316 s** (`frame_objective`, `design_plan`, `research_context`, LangFuse) under
the deploy's 1800 s LLM timeout. The two arms were at parity on reasoning; Atlas was cut
where Ollama was not. **Revision:** the serve line gains `--request-timeout 1800` (the
deploy's `SQUADOPS__LLM__TIMEOUT`), and the Atlas adapter raises `LLMTimeoutError` on a
server-side cut instead of handing a truncated message to the parser; the agent and
runtime-api images are rebuilt on that commit, which becomes the frozen deploy; **a second
shakeout on arm B precedes B1**, recorded and flagged like the first. The `high → xhigh`
mapping stands. Nothing else in §1 changes. The failed shakeout's per-request evidence is
on #1160 and stays in the record as the warm-up that found this.

### 1.2 Revision after the second shakeout (2026-08-28, `cyc_6db3a5d8d1ca`, failed)

The second Atlas cycle, on the rebuilt deploy with `--request-timeout 1800`, got through the
brief (no generation was cut) and failed at `governance.merge_plan`: eight attempts, every
one an `implementation_plan.yaml` that failed validation, 3–5k-token emissions all reporting
`stop`. The vendor's own long-generation gate (a ~3k-token YAML plan at `xhigh`, parsed)
found the cause in Atlas's log: **the content-loop watchdog** — "period-2…64 repetition
detector", which its `--help` says can false-positive on code and tables — fired on the
legitimate repetition of a YAML task list and ended the emission mid-document (2,727 tokens,
`finish_reason: length`, no fence). With `--content-loop-watchdog false` the same gate parsed
4 of 4 plans clean (4.2–7.9k tokens) on both the default (NVFP4) and BF16 lm-head, at the same
decode rate. **Revision:** the serve line adds `--content-loop-watchdog false` and
`--lm-head-dtype bf16` (the vendor's stated safe choice for long structured generation; no
measured cost). Both are server-side flags — the frozen deploy of §1.1 stands unchanged — and
Ollama has no equivalent of either, so this is a serve-line difference between the arms, not
a model one. **A third shakeout on arm B precedes B1.** The per-request evidence of both
failed shakeouts and both gate runs is on #1160.

### 1.3 Reading the rest of the serve defaults before the third shakeout (2026-08-29)

Two failures from unread defaults prompted a full pass over the server's startup log,
`--help`, the checkpoint's `generation_config.json` and Ollama's Modelfile:

- **KV cache**: Atlas warned at every start that the checkpoint ships no `k_scale`/`v_scale`
  tensors, so the FP8 KV cache used scale 1.0 — "silently clips BF16 into E4M3 range and
  destroys dynamic range" — precisely where the ~17k-token qa briefs live. The model has 16
  full-attention layers × 4 KV heads × 256 dims: BF16 KV is ~64 KB/token, ~2 GB per 32K
  sequence, trivial under the 0.75 cap. **`--kv-cache-dtype bf16`** replaces `fp8`; no
  calibration to get wrong.
- **Sampling parity**: with no override the handlers send no sampling parameters, so each
  engine's defaults apply. Both default to temperature 1, top-k 20, top-p 0.95, min-p 0 — the
  1.6.x record ran at temperature 1 — and Atlas adds `top_n_sigma=1`, a logit filter it
  recommends for agent workloads. Kept, as part of "best from Atlas"; stated here as an arm
  difference.
- **Behaviour defaults now known and set**: `thinking_default=true`, `max_thinking_budget=2048`
  (`xhigh` = 4×), watchdog off (§1.2), MTP 3 drafts/step, prefix caching on, chunked prefill
  8,192, `max_batch=8`.
- **`--dump /dumps/atlas-requests.jsonl`**: every request and response on arm B, verbatim, to
  a host-mounted file — the full-prompt store the record otherwise lacks (LangFuse caps
  `input` at 10k chars). Arm A has no equivalent; the record says so.

### 1.4 The served window, read against the arm's own prompts (2026-08-29)

The third revision from an unread serve default, and the first that would not have failed
loudly. `--max-seq-len 32768` was the first-serve recipe's number (#1158), carried into the
registry entry the prompt guard reads. The guard spends `context_window −
max_completion_tokens` on the prompt: **24,576 usable prompt tokens on arm B** against
**253,952 on arm A** (`qwen3.8:27b`, 262,144 − 8,192). Over budget it does not fail — it
deletes the `## Prior Analysis from Upstream Roles` section and sends the rest
(`src/squadops/capabilities/handlers/prompt_guard.py`), raising
`PROMPT_EXCEEDS_CONTEXT_WINDOW` only if the remainder still will not fit. Framing prompts
never reach the guard at all (its only callers are the dev and qa handlers) and would have
met the server's limit directly, as in §1.1.

What this arm's prompts actually are — Ollama's own `new prompt` lines for the 27B,
n = 1,145 since 2026-08-22, `n_ctx_slot = 262144`:

| median | p90 | p99 | max | > 24,576 | > 32,768 |
|---|---|---|---|---|---|
| 9,895 | 20,212 | 31,137 | 38,210 | ~5.9% | 0.87% |

Roughly **one generation in seventeen** would have run on arm B with its upstream analysis
deleted and on arm A intact — a difference in what the model was asked, invisible in the
verdict, that the record would have credited to the engine. **Revision:** `--max-seq-len
65536` on the serve line and `context_window=65_536` on the registry entry; 38,210 plus the
8,192 completion clamp fits with headroom. The KV pool is paged and sized independently of
the cap (16.2 GB ≈ 265K tokens at ~64 KB/token BF16), so one 64K sequence costs ~4 GB of it
and nothing at the observed median. Arm A is untouched — and its 262,144 is the *served*
window, not just the checkpoint's claim: every 27B load in the Ollama server log reports
`n_ctx = 262144`. The registry entry ships in the images, so **the agent and runtime-api
images are rebuilt on this commit and that rebuild is the frozen deploy** (superseding
§1.1's, whose ids the §1 table still named); the ids are pinned in the set files before the
first counting roll. The third shakeout runs on this line.

**Probed on this serve line, 2026-08-29, before the shakeout.** Atlas *rejects* past its
window, it does not truncate — the registry comment's assertion is now a measurement: a
69,668-token prompt returns `400 invalid_request_error`, *"Prompt too long: 69668 tokens
exceeds max_seq_len 65536 (leave room for output tokens)"*, in 0.1 s. Below the cap it
serves what the old line would have cut: 7,642 tokens → 200 in 13.2 s; **37,836 tokens →
200 in 55.3 s** — over the old 32,768 cap and half again the old guard's 24,576 budget. The
server's arithmetic is the guard's: prompt plus output must fit `max_seq_len`, which is what
reserving `default_max_completion` inside `context_window` produces. Two readings for the
record: prefill runs ~600–700 tok/s, so a 38K prompt costs ~55 s before the first token on
arm B — that belongs to P2's wall-clock, not to a failure; and at 65,536 the KV pool reports
16.8 GB → 274,656 tokens (17,166 blocks × 16 tok/block), so one full-length sequence is ~24%
of it and the only cap-scaled cost is a 355 MB chunked-prefill reserve.

### 1.5 The third shakeout, the replay matrix, and what arm B cannot do (2026-08-29)

`cyc_cc5c58ff2cde`, on the frozen deploy at `55ad5995`, failed at
`governance.merge_plan` after 8 manifest attempts across two rounds; the run recorded
`blocked_unverified`. **§1.2's conclusion is falsified.** The startup line "content-loop
watchdog ENABLED" is not a vendor log quirk and `--content-loop-watchdog false` is not in
force. The `--dump` added by §1.3 is the only reason this is knowable: LangFuse records
nothing for this capability (#1172) and no token usage for any framing generation (#1171).

**The guard is armed, and four documented controls do not disarm it.** 11 of 25 responses
in the shakeout carried `loop_watchdog_triggered: true`, `guard_stop` naming one of two
detectors — `token_loop_watchdog` (what the flag targets) and `simhash_semantic_loop` (no
CLI flag, no env var in `--help`). Tried and inert: the CLI flag; the env var
(`ATLAS_CONTENT_LOOP_WATCHDOG=false`, confirmed set on the container, startup line
unchanged, behaviour unchanged); the per-request `repetition_detection` object the help
says "still outranks this", at `min_count: 64` against a default of 3; and
`--content-loop-min-repeats 64`, the vendor's own documented remedy for output that is
"short-period repetitive (code, tables)".

**What it fires on, and what its rollback does.** The severed content is legitimately
repetitive YAML — consecutive `- check: … / file: … / severity: error` blocks, one per
file, which a 15-task plan can carry fifty of. That is the false-positive class the
vendor's help names. The damage is not the stop but the rollback+re-steer (cap 2 per
sequence) rewinding mid-token: `depends_on: []` emerges as `depend0]`,
`frontend_compiles` as `frontend_compil`. Those corruptions *are* the validator's
"while scanning a simple key" and "mapping values are not allowed here".

**Replay matrix.** One stored merge_plan prompt (9,244 prompt tokens), replayed
byte-identically, scored through `ImplementationPlan.from_yaml` — the handler's own gate,
not a bare YAML parse:

| row | change | accepted | guard-stopped |
|---|---|---:|---:|
| R1 | baseline (the §1.1–§1.4 serve line, FP8) | 0/3 | 1/3 |
| R4 | per-request `repetition_detection`, `min_count: 64` | 0/3 | 2/3 |
| R7 | `max_tokens: 16384` | 0/3 | 3/3 |
| R6 | `reasoning_effort: high` | — | 400: no such tier |
| R6′ | `reasoning_effort: medium` | 0/3 | 3/3 |
| R8 | `xhigh` + `chat_template_kwargs.thinking_budget: 2048` | 0/3 | 3/3 |
| R2 | `ATLAS_CONTENT_LOOP_WATCHDOG=false` (env) | 0/3 | 3/3 |
| R3 | `--content-loop-min-repeats 64` | 0/3 | 3/3 |
| R5 | `--kv-cache-dtype fp8` | 0/3 | 3/3 |
| R10 | the vendor's own recipe, verbatim, NVFP4 checkpoint | 0/1 | 1/1 |
| R11 | NVFP4 + recipe flags at serving size | 0/3 | 3/3 |
| R12 | R11 + `ATLAS_SSM_DECODE_RING=1` | 0/3 | 3/3 |
| R13 | R11 + `temperature: 0.2` | 0/3 | 3/3 |
| R14 | R12 + `temperature: 0.2` | 0/3 | 3/3 |

**14 configurations · 44 plan emissions · 41 guard-stopped · 0 accepted.** Of the 41, all
were stopped *below* the completion cap — the budget was never the binding constraint on
this arm.

Two rows deserve their own note. **R10** used the vendor recipe
(`atlas-recipes/recipes/qwen3.8/qwen3.8-27b-nvfp4-unsloth.yaml`) verbatim, including its
`--max-batch-size 1` and `--gpu-memory-utilization 0.85`; that produces a 12,976-token KV
pool on this box, which one 9,244-token prompt exhausts, so two of its three replays died
on `KV cache exhausted`. The recipe says of itself that 32K "is a gate value, not a
recommendation" — it is a qualification config, not a serving one. **R12/R14** forced the
SSM decode-rollback ring back on, the only knob all day that visibly changed engine state
(the "SKIPPED" line disappears, a 1.2 GB pool is allocated, and Phase-C
rollback-to-boundary activates). It shifted the failure from corruption toward clean
truncation — 2 of 3 parsed cleanly against a 27% base rate — without changing the verdict.

**Arm-A control (R0).** The same prompt, in arm A's production request shape (`think:
true`, `num_predict: 8192`), scored by the same validator:

| replay | thinking | plan | finish | verdict |
|---|---:|---:|---|---|
| 1 | 16,716 ch | 12,573 ch | `stop` | **ACCEPTED (5 tasks)** |
| 2 | 27,920 ch | 1,774 ch | `length` | rejected: missing `summary` |
| 3 | 22,474 ch | 7,406 ch | `length` | rejected: missing `summary` |

**1 of 3 on arm A against 0 of 44 on arm B** — and the two arms fail for different reasons.
Arm A's failures are budget exhaustion with no guard involved; arm B's are the guard,
below the budget. That difference is why retries rescue arm A and cannot rescue arm B:
each arm-A attempt is an independent ~⅓ chance, so 8 attempts land a plan ~96% of the
time, which is exactly why 11 of 11 recorded Next.js cycles show `framing_rerolls: 0`.
Arm B's shakeout spent 8 attempts without one landing.

**P1 is falsified on this workload.** Arm A decoded at 28.8–29.2 tok/s on this prompt
against arm B's 12–14 tok/s, both decode-only figures from each engine's own reporting.
The prediction was arm B ≥ 2× arm A; the observed direction is the reverse. The tuning
matrix's 33.8 tok/s came from a short fill brief, and #1160 had already recorded framing
decode at 12–18 tok/s — the throughput case does not survive contact with the framing
workload, independently of the correctness failure.

**Model support.** `Qwen/Qwen3.8-27B-FP8` is not in the supported-model table of the
shipped image's README, of the GitHub README, or of the GB10 Deployment Guide; support
for this model exists only as a recipe in `atlas-recipes`, annotated "tested on binary
main 680b3a568". The kernel audit cited in §2 precondition 3 (236 lookups / 0 unresolved)
was run against the **NVFP4** checkpoint, not the FP8 one the A/B has been serving. R11
closes that gap: on the NVFP4 weights, with the audited kernel set, the outcome is
identical.

**Three defects this surfaced, all engine-independent** — #1171 (framing generations
record zero token usage), #1172 (`merge_plan` emits no generation record at all), #1173
(the completion budget ignores the reasoning level a capability declares, which is the
whole of arm A's ⅓ failure rate). Fixed in one PR; the rebuild on its merge becomes the
frozen deploy, superseding §1.4's.

**How §1.2 went wrong, recorded so it is not repeated.** Its "4 of 4 clean plans" gate
counted tasks in parsed YAML. The handler requires `version`, `project_id`, `cycle_id`,
`prd_hash`, `tasks` and `summary`. A check weaker than the one in production cleared a
remedy production then rejected — and the remedy had never taken effect at all. Every row
above is scored through the production validator for that reason.

**Standing.** No counting roll on arm B until a shakeout completes. The arms, order and
predictions of §1 are otherwise unchanged; this section records what the shakeout phase
found, not a change to the design.

## 2. Preconditions — all, or the numbers lie

1. #927, #1157, #1159 merged and deployed; `provider` and the adapter verified in-container (done 2026-08-28).
2. The `full-38-atlas` profile on main and seeded (squad-profile provider is `config`: a runtime-api rebuild); `docker compose … config` renders the override on all eight services.
3. Atlas: ufw allow on `:8888` (owner, 2026-08-28), token secret at `secrets/atlas_api_key.txt`, kernel audit `236/0` on this checkpoint, the serve line above answering `/v1/models` with the token.
4. Per-arm `loaded_checks`: runtime-api and an agent print `config.llm.provider` and the served model — the arm is what the record says it is.
5. No other cycle, set, or deploy change while open.

## 3. Predictions — falsifiable from the record, one per mechanism

| # | Prediction | Read from |
|---|---|---|
| P1 | On `none` generations (qa fill, repairs, verdicts) arm B's decode rate is ≥ 2× arm A's | LangFuse `tokens_per_second` per generation (B: the engine's own `response_token/s`; A: Ollama `eval_count/eval_duration` — both decode rates) |
| P2 | Paired cycle wall-clock B < A on every Next.js pair | the driver's `wall_clock_seconds` |
| P3 | Verdict parity: no arm-B rejection whose per-round evidence names the runner (extraction failure, parse, timeout, 401/400 from Atlas) | per-round `test_report.md` / handler logs, never the roll-up (the per-round-evidence rule) |
| P4 | Completion tokens per task type within ±20% between arms — if not, the difference is thinking posture, and speed is normalized per token before any claim (C.4 reading order, item 1) | LangFuse `completion_tokens` by capability |
| P5 | Every qa-fill generation on arm B carries `reasoning_tokens = 0` — the policy's `none` reaches Atlas's wire | LangFuse (`GenerationRecord.reasoning`) and Atlas usage |
| P6 | The FastAPI+React pair: corrections consumed on B ≤ A (the sleeper metric; one pair is texture, not a bar) | the driver's `correction_rounds` |

A falsified prediction stops the set for a read, not a fix — the 1.6.x rule.

## 4. The artifact

The record, written beside this file at the close (`1-7-0-atlas-ab-record`): one row per cycle — arm, order, cycle id, verdict,
checks executed/passed, correction rounds, extraction health, `wall_clock_seconds`; then
per-generation medians by capability (completion tokens, reasoning tokens where reported,
decode t/s) from LangFuse; the shakeout and warm-up rows present and flagged. Read in
Appendix C.4's order: tokens first, then paired wall-clock, then rate, then the quality
half. **No threshold** (Ruling 2): the artifact reports; the owner decides.

## 5. Appendix C amendments this artifact records

- C.1-1 superseded: each arm is its production configuration, stated (Ruling of 2026-08-28).
- `load_ms` is not emitted by Atlas: the shakeout/warm-up is recorded and flagged, and
  TTFT stability is the warm guard; `prefill_ms`/`total_ms` → TTFT and client wall-clock.
- Corpus = real cycles, not a frozen prompt set (no full-prompt store exists; LangFuse caps
  `input` at 10k chars).

## 6. Prohibited while open

No Ollama tuning; no profile edits; no deploy change other than the arm switch; no other
cycles on the box; the record written from per-round evidence before any conclusion.
