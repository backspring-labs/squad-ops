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
| model | `qwen3.8:27b`, **Q4_K_M** (Ollama's tag), 262K native window | `Qwen/Qwen3.8-27B-FP8`, **FP8 dequantized to BF16 in memory**, served window 32K |
| engine | Ollama 0.32.14 as deployed; no tuning — every 1.6.x record sits on it | `avarok/atlas-gb10:latest` (built 2026-08-15), `serve Qwen/Qwen3.8-27B-FP8 --speculative --num-drafts 3 --enable-prefix-caching --scheduling-policy slai --kv-cache-dtype fp8 --max-seq-len 32768 --gpu-memory-utilization 0.75 --bind 0.0.0.0 --require-auth --auth-tokens-file … --no-auto-swap --no-tui` |
| why that serve line | — | the tuning matrix (#1160): FP8 12.5 t/s → MTP speculative K=3 29.5 → **K=4 33.8** → K=5 23.0 (over-drafting); NVFP4 12.8 and also dequantized (no memory or speed gain). Token counts identical across rows on the fill brief |
| how the deploy is pointed at B | — | `docker compose -f docker-compose.yml -f docker-compose.atlas.yml up -d` (`ATLAS_MODEL=Qwen/Qwen3.8-27B-FP8`, secret `atlas_api_key`); back to A with plain `docker compose up -d`. Recreating the containers is also Appendix C.3's "restart the agent containers between arms" |
| project / request profile | `group_run` / `validated-fullstack` | same |
| stacks | **Next.js+TS** (`nextjs_ts` overrides) for the paired wall-clock — the 1.6.6 arm that ran 6/6, so verdict noise does not swamp the pair; then **one FastAPI+React pair** for correction texture (Appendix C.3's sleeper metric needs a stack where corrections happen — 1.6.6 ran 4/6 there) | same |
| order | **A1, B1, B2, A2** (Next.js), then **A3, B3** (FastAPI+React) — the first pair A-first, the second B-first, so an ordering effect shows instead of being credited to one side | |
| shakeout | one non-counting Atlas cycle before B1 (no cycle has ever run on Atlas: the model preflight over `/v1/models`, the 32K guard, the fenced parser on Atlas output, timeouts at 2.8× decode). It is also the warm-up Appendix C.2 requires, recorded and flagged | |
| frozen deploy | agent images from `43721563` (`max=22429f8898cb neo=af175877d8b5 eve=fde6d6b0fb26 bob=5d2e2f19e9be nat=864419a35f7f data=feaa005116b7 joi=7e6173048297`); runtime-api rebuilt once on the commit that carries `full-38-atlas` (its image id pinned in the set files after that rebuild) and identical for both arms | |
| engine isolation (C.2) | before every B cycle: `ollama ps` empty (keep-alive has paged the models out); before every A cycle: the `atlas` container stopped. Neither checkpoint coexists with Ollama-27B in the Spark's unified memory at usable KV | |

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
