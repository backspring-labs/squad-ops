---
sip_uid: '1791574804220728'
status: accepted
title: TensorFold Provider Adapter
author: Jason Ladd
created_at: '2026-10-09T00:00:00Z'
sip_number: 111
updated_at: '2026-10-09T16:47:58.521552Z'
---
# SIP-0111: TensorFold Provider Adapter

**Status:** Accepted (2026-10-09, by the owner, at revision 2; for numbering and for implementing S, G0 and G1 in 2.3 after the 2.2 cut, see the design disposition below)
**Scope:** TensorFold **v0.6.6 on the DGX Spark's GB10, CUDA backend only.** There is no Mac installation, build,
execution or test. The `TensorFold/Qwen3.8-27B-MLX-4bit` checkpoint stays eligible because v0.6.6 serves those weights on
CUDA; its name does not mean a Mac deployment.
**The owner's rulings (2026-10-09):**
- **Q1, placement** ("2.3 is fine"): G0–G2 on the **2.3** line, dark, with SIP-0106 §4.3's even/odd waiver (#2199,
  #2200). G3 and G4 follow the evidence.
- **Q2, the bars, as recommended:**
  - G0: median wall-clock per call at most 0.75× Ollama's, at no worse a truncation rate;
  - G1: a pass rate at least Ollama's on the same envelopes.
- **Q3, the overlay, as recommended:** `docker-compose.tensorfold.yml` is OK in principle at G2. The base compose file
  stays untouched.
- **Q4, the version:** "don't plan to use the 1.0.x version. base our adapter on the faster python version that support
  the qwen 3.8 27b". **Pinned: v0.6.6** (commit `cb2ebf0540f42604e2759b2ddef497861e928248`, released 2026-10-06), the
  last Python release; its CUDA server serves Qwen3.8-27B.
- **The review of revision 1 (PR #2198):** the separate adapter, the pinned Python release, the measured gates and the
  dark rollout are sound and kept. Q5 (a Mac run) is removed.
- **Q6, the port amendments: APPROVED, with implementation safeguards** (the owner's review of revision 2, 2026-10-09).
  (a)–(d) of §5.1 and §5.2 as proposed, and:
  - unsupported controls are tested across **all** existing adapters, not only TensorFold;
  - `completion_tokens` stays inclusive of `reasoning_tokens`, with nothing double-counted;
  - **a complete, closed response that reaches the cap is kept.** A `length` finish alone never discards otherwise
    valid output (§5.2);
  - stream cancellation is verified to release the server's work before the next request (§5.4).
- **Q7, the memory floors: APPROVED as initial safety floors, subject to empirical validation in S** (§5.6):
  - before an engine loads, `MemAvailable` ≥ 90 GiB and no competing GPU inference process resident;
  - after TensorFold loads, `MemAvailable` ≥ 16 GiB;
  - **the switch fails closed** on either miss, on unknown residency, on failed authentication, or on a mismatch with
    the pinned recipe;
  - engines never overlap during rollback. Release is confirmed before Ollama is restored;
  - memory is recorded before and after load, after warm-up, and **under representative long-context generation**.
    Static idle headroom is not sufficient evidence of runtime safety;
  - if long-context tests violate the reserve or destabilize the host, `--context` is reduced or the trial parked. The
    floors are never relaxed to force a pass.

**The owner's design disposition (2026-10-09): accepted for numbering, and for implementing S, G0 and G1 in 2.3 after
the 2.2 cut.**
- **G2 stays conditional** on meeting both approved gates, G0 and G1.
- **G3 and G4 stay separate decisions.**
- **This approval does not authorize switching production inference.**
- #2199 and #2200 are synchronized with revision 2 before any work begins.
- A frozen, auditable recipe and held-out validation are preserved.
- **The decision to adopt TensorFold rests on end-to-end cycle quality, latency, stability and recoverability, never on
  vendor tokens-per-second figures.**

**Revision 2 (2026-10-09), from the owner's review of revision 1 (`866cfdac`).** These are the changes:
1. GB10 CUDA only, with the Mac workflow removed.
2. The request interface's gaps closed: seed and thinking budget become port fields, and sampling defaults become
   recorded serve settings (§5.1). Revision 1 said no seam changes; that claim is withdrawn.
3. Termination and context overflow connected to recovery (§5.2).
4. No production-name alias: distinct TensorFold model ids, with their served window verified (§5.3).
5. G1's validator table, and the G0/G1 protocol: samples, seeds, pairing, denominators, cache, a tuning/held-out split
   and a frozen recipe (§4).
6. Streaming deadlines, cancellation and terminal-state checks (§5.4).
7. Authenticated health and residency (§5.5).
8. Switching and rollback built and exercised before G0 (§5.6), and the complete CUDA recipe pinned, with adapter and
   harness parity (§5.7).

**Authors:** Jason Ladd (the direction, 2026-10-09: plug in TensorFold "as soon as I can to benefit from the tps for
running cycles and campaigns"; the review of revision 1); Claude Code (this draft).
**Extends:** SIP-0106 (Atlas Provider Adapter, implemented). TensorFold is a third candidate engine behind `LLMPort`, under
SIP-0106's design:
- provider selection as required configuration (§3.1);
- declared capabilities (§3.2);
- provider-scoped model identity (§3.4);
- one adapter per provider (§3.5a);
- the conformance suite as the gate (§3.6);
- the dark-ship rule (§4);
- the A/B protocol (§6.1a).

**It changes the port in four backward-compatible places** (§5.1, §5.2): two optional request fields, two capability
constants, a normalized termination field, and one exception. They are recorded here as SIP-0106 amendments.

## Intake check

Checked against `sips/PORTFOLIO.md` on 2026-10-09, and again for revision 2 (CLAUDE.md, "SIP System").
- **Overlaps:**
  - **SIP-0106, all of it, by design.** Its seam, gates and protocol are reused. Its two outcomes are this draft's
    evidence (§3): Atlas was not adopted (§1.2a) and the vLLM arm is parked (§1.2e).
    - **Revision 2:** this draft also amends its port (§5.1, §5.2). The changes are backward-compatible, and every
      existing provider keeps its behaviour. SIP-0106 keeps the seam's rules.
  - **SIP-0110, Cross-Cycle Memory.**
    - The 2.2 window pins the engine, so nothing runs on the Spark until it closes.
    - Its captured authoring envelopes are the trial's corpus (§4).
    - An engine change is a listed-input change for every later measurement, and the approved lesson's tested
      applicability names the `qwen3.8` configuration in the window's manifest (G4).
    - **Revision 2:** the replay needs a seed per generation on this engine, which §5.1 provides.
  - **SIP-0073, the model registry.** The TensorFold model ids get entries of their own, with family `qwen3.8` and
    TensorFold's served window. Ollama's `qwen3.8:27b` entry is untouched (§5.3).
  - **SIP-0109's box lease and quiet-box launch rule (§24ai, §24an).** Residency is read only from authenticated
    sources, and an unknown state is never quiet (§5.5). Switching engines holds the box (§5.6).
  - **The executor's failure taxonomy (D5) and the correction loop (#568).** A context overflow is a typed error. It is
    never retried unchanged, and never blamed on the work product (§5.2).
  - **#2149 and #431, the cap-truncation path.** It reads a normalized termination where a provider reports one, and
    the token count otherwise (§5.2).
  - **#1177 (retired unbuilt, 2026-09-29) and #1178: arm exclusivity and OOM containment.** The guard #1177 named is
    built here, as a prerequisite of G0 (§5.6).
- **Conflicts:** one, **resolved by the owner on 2026-10-09** (Q1). 2.3 is feature-free by rule, and G0–G2 are placed
  there, dark, under SIP-0106 §4.3's waiver.

## Delivery ledger (current as of 2026-10-09)

Placed by the owner's Q1 ruling (2026-10-09). The rows are ordered as the work runs.

| part | status | where |
|---|---|---|
| S: engine switching and rollback, with the exclusivity guard, built and exercised before the first TensorFold load (§5.6) | **placed** | 2.3.0, #2199 |
| G0: throughput on held-out captured envelopes, against production Ollama, on a frozen recipe (§4) | **placed** | 2.3.0, #2199 |
| G1: emission quality, the same calls through each task type's production validator (§4) | **placed** | 2.3.0, #2199 |
| G2: the adapter, dark, with the port amendments, registry entries, the overlay and parity tests (§5) | **placed** | 2.3.0, #2200 (merged only if G0 and G1 pass) |
| G3: an uncounted cycle A/B on both stacks, judged on cycle wall-clock | **unplaced** | after G2 |
| G4: cutover | **unplaced** | the owner's decision on G3's evidence |

**What closes this SIP:** G4 decided (adopted, or parked with its record), with each earlier row shipped or its negative
recorded.

## 1. Summary

The squads' throughput is bounded by single-stream decode, because SquadOps dispatches one task at a time. On the Spark,
production Ollama decodes `qwen3.8:27b` (Q4_K_M) at about 22–37 tok/s on real work:
- 22.4–22.7 tok/s in 2026-10-09's diagnostic handler lines;
- 23.6–36.8 tok/s on framing (SIP-0106 §1.2e);
- 23.9–27.4 tok/s in the box's reference measurement.

TensorFold v0.6.6 reports 50.0–57.8 tok/s for the same model on GB10, using exact speculative decoding (§2).

TensorFold's API is **OpenAI-shaped, not Ollama's** (§2), so it gets its own adapter (SIP-0106 §3.5a).

**This engine class has failed here twice, both times on measurement** (§3), so the plan is a ladder of gates. Each is
cheap, and runs before the next one's cost is spent:
1. **S:** switching and rollback, proven.
2. **G0:** throughput on our own captured prompts.
3. **G1:** those responses through our own validators.
4. **G2:** the adapter, dark.
5. **G3:** a cycle A/B.
6. **G4:** cutover, the owner's decision.

## 2. TensorFold v0.6.6 on GB10 (read at the tag, 2026-10-09)

Sources at `v0.6.6`: [docs/api.md](https://github.com/ashhart/TensorFold/blob/v0.6.6/docs/api.md), the README,
`docs/recipes/cuda.md` and `docs/recipes/qwen3.8-27b.md`, in [ashhart/TensorFold](https://github.com/ashhart/TensorFold).
Every performance figure is the vendor's. None is measured here.

- **The API:** OpenAI chat completions, completions and Responses, plus Anthropic Messages, by default at `127.0.0.1:8080`.
  There are **no Ollama endpoints.** Models are pulled and served by the CLI, not over HTTP.
- **Our model on CUDA:** Qwen3.8-27B is served on CUDA in three forms, each with the `z-lab/Qwen3.8-27B-DFlash2` drafter.
  CUDA requires the drafter unless `--no-drafts` is set.
  - `TensorFold/Qwen3.8-27B-MLX-4bit`, MLX-format weights served on CUDA;
  - `nvidia/Qwen3.8-27B-NVFP4`, on one GPU;
  - `turboderp/Qwen3.8-27B-exl3`, experimental.
- **The vendor's GB10 decode, 64-token replies, sampled:**
  - MLX 4-bit: 57.8 tok/s on code and 50.0 on chat;
  - NVFP4: 47.1 and 38.2;
  - EXL3 3.00bpw: 83.4 and 44.2.

  Our replies run to thousands of tokens on 30–50k-token prompts, where 0.5.0 reported 38.9–45.9 tok/s at 96–128k.
- **The install:** NVIDIA's `pytorch:26.07-py3` container, then `pip install` from the pinned commit (the RUNBOOK's DGX
  Spark setup).
- **The request surface:**
  - `reasoning_effort` is per request. For Qwen3.8 the server maps an unnamed level to the template's nearest, so `high`
    is heard as `xhigh`.
  - `thinking_budget` is per request (`--thinking-budget` is the server default).
  - `seed` is per request. Without one, the seed is derived from the prompt, so a repeated request repeats its sample.
  - Sampling defaults (temperature, `top_p`, `top_k`, `min_p`) are server flags that request fields override.
  - Its stated precedence: an explicit `chat_template_kwargs.enable_thinking` wins over `reasoning_effort`.
- **The response:**
  - The answer is in `content`, and reasoning is in `reasoning_content` (`delta.reasoning_content` when streaming).
  - Usage carries prompt, completion and total tokens, `cached_tokens`, and `reasoning_tokens` (through the closing
    think marker).
  - Streamed usage arrives in its own final event with `include_usage`. `finish_reason` is `length` at the cap.
- **Errors:**
  - A prompt and reply that overflow the window are refused with HTTP 400 and `context_length_exceeded`, before a
    stream opens.
  - A generation error is HTTP 500, or, once a stream is open, a `server_error` event followed by `[DONE]`.
  - A client disconnect cancels the work (0.3.5).
  - **No server-side request timeout is documented.**
- **Auth and health:**
  - API keys come from `--api-key-file` (mode 0600) and are sent as Bearer.
  - **With keys configured, `/health` returns only `{"status":"ok"}`,** and `/metrics` and every `/v1/*` route need the
    key. The `busy` and `context_length` counters on `/health` exist only without keys.
  - `/v1/models` lists the served id **and its aliases**.
- **Memory on GB10:**
  - CUDA allocations come out of host RAM and are **not charged to a container's memory limit**.
  - The window is sized from `MemAvailable`, less a reserve (`TENSORFOLD_MEMORY_RESERVE_GIB`).
  - Exhausting unified memory can freeze the host.
- **Exactness:** a drafted reply equals the same engine's serial (`"draft": false`) reply, on the same checkpoint,
  template, runtime, seed and sampling. It is **not** equal to Ollama's reply: the weights and the runtime differ.

## 3. What Atlas and vLLM taught, which this plan carries

1. **A vendor's speed claim predicted the wrong direction.**
   - Atlas was predicted at ≥2× Ollama and measured 0.4× (SIP-0106 §1.2a).
   - vLLM measured 7.8–10.8 tok/s against 23.6–36.8 (§1.2e).
2. **Emission quality was the blocking measurement.**
   - vLLM authored 0 of 3 plans, where Ollama authored 5 of 5. Two of the three spent the whole budget thinking.
   - Atlas authored 0 of 44, its loop guard corrupting correct YAML.
3. **Two engines resident at once took the box down** (§1.2c). The guard meant to stop it, #1177, was never built.
4. **Compare deploy against deploy** (the owner's ruling on the Atlas A/B, 2026-08-28):
   - production Ollama as it runs, never re-tuned;
   - the candidate at its best tuned recipe, chosen by a stated matrix;
   - the same model size on both arms.

   Quantization is a stated property of each arm, recorded verbatim.
5. **Parked is not deleted.** A negative is recorded, and anything merged stays inert (§4 of SIP-0106).

## 4. The gates and the protocol

**S: switching and rollback** (§5.6). Built and exercised, on the Spark and after the 2.2 cut, before TensorFold is
loaded for any measurement.

**The pre-registration** (in #2199, before any measured call): the sample, the split, the seeds, the recipe matrix, the
memory thresholds (§5.6) and the analysis below. It is written before the first TensorFold load.

**The corpus.** SIP-0110's captured authoring envelopes from real cycles on both stacks. As of 2026-10-09 it holds:

| seam | task type | captured |
|---|---|---:|
| plan writing | `development.design_plan` | 22 |
| plan writing | `development.author_manifest` | 18 |
| plan writing | `governance.prepare_plan_authoring_brief` | 22 |
| plan writing | `development.propose_plan_tasks`, `qa.propose_plan_tasks`, `strategy.propose_plan_guidance` | 4 each |
| build authoring | `development.develop` | 72 |
| build authoring | `builder.assemble` | 23 |
| build authoring | `qa.test` | 48 |
| proposal writing | `strategy.propose_increment` | 5 |
| repair | `development.correction_repair` | 5 |
| repair | `qa.test_repair` | 6 |

`governance.merge_plan` is deterministic now (SIP-0093; `planning/merge.py`). Only its sole-author fallback calls the
model, and it is not a captured seam. The vLLM failure on its old prompt is history, not part of this corpus.

**The split, fixed before any call:**
- Each envelope gets a split by a seeded hash of its id, stratified by task type and stack, recorded in the
  pre-registration.
- **Tuning:** up to 2 envelopes per task type and stack. They are used only to choose the recipe.
- **Held-out:** the rest, up to 8 per task type and stack, all when fewer.
- G0 and G1 read only held-out envelopes.

**Each envelope's own settings.** Every call sends exactly the captured `chat_kwargs`: its model, its `max_tokens` (12,288
on most, and absent on the 23 `none`-reasoning envelopes) and its reasoning level. In the corpus, `medium` is 116,
`high` 79, `none` 23 and `low` 15. Nothing is assumed uniform.

**Tuning, then freezing.**
- On the tuning set only, the matrix is run:
  - the checkpoint (MLX 4-bit, NVFP4, EXL3 3.00bpw);
  - the drafter settings;
  - the serve flags;
  - the thinking budget (none, or a stated value).
- One recipe is chosen by its tuning-set wall-clock and validity.
- **It is then frozen:** the checkpoint and drafter revisions, every flag, the thinking budget and the sampling defaults
  (§5.1). G0 and G1 run once on the held-out set, on that recipe.
- Any later change to the recipe re-runs both G0 and G1 on the held-out set.

**Seeds and repetitions.**
- Each held-out envelope runs **3 generations per arm,** with seeds 1001, 1002 and 1003, recorded.
- Each generation sends its seed through the port (§5.1), so TensorFold's repeats are independent draws. The Ollama arm
  receives the same seeds through its `options.seed`.
- Independence is claimed only where an arm's capability declares the seed is honoured.

**Order and cache.**
- The arms run in alternating blocks: all Ollama, then all TensorFold, then a second Ollama block of one generation per
  envelope, to detect drift. Only one engine is ever resident (S).
- Within a block, the order is a seeded shuffle, so no envelope follows itself.
- Each call records `cached_tokens` (TensorFold) or its prompt-eval count (Ollama). **The primary timing reads calls
  with no prefix cache hit.** Calls with a hit are reported apart.

**G0, throughput.**
- For each held-out (envelope, generation) pair, the paired ratio is TensorFold's wall-clock over Ollama's.
- **The bar (Q2):** the median paired ratio is at most 0.75, with a truncation rate (§5.2) no worse than Ollama's.
- **The denominator is every planned call.** A timeout or failed call enters at its deadline (§5.4), never dropped.
- **Reported by seam, task type and stack,** each with its median ratio and its failures, so an aggregate gain cannot
  hide one seam's regression. A seam whose median ratio is above 1.0 is named in the readout.

**G1, emission quality.**
- Every response is scored by **its task type's production validator.** The harness calls each handler's own
  `parse_and_validate` callback, or its emission path, with the response as the handler would see it:

  | task type | validator |
  |---|---|
  | `governance.prepare_plan_authoring_brief` | the handler's callback: `PlanAuthoringBrief.from_yaml` and its checks |
  | `development.design_plan` | the handler's `parse_and_validate` |
  | `development.author_manifest` | the handler's `parse_and_validate`: `InterfaceManifest.from_yaml`, the authoring checks |
  | `*.propose_plan_tasks`, `strategy.propose_plan_guidance` | the handlers' callbacks (`PlanGuidance.from_yaml` for guidance) |
  | `strategy.propose_increment` | the proposal handler's change-request parse and the rails |
  | `development.develop`, `builder.assemble`, `qa.test` | the build emission path: fenced extraction, slot integrity, the #2149 cap check |
  | `development.correction_repair`, `qa.test_repair` | the repair handlers' emission paths |

- **A task type with no wired validator fails the harness** before any call. A sample is never skipped silently.
- **The bar (Q2):** TensorFold's pass rate is at least Ollama's, overall **and per seam**. The denominator is every
  planned call, with timeouts, errors and truncations counted as failures.
- Recorded per failure:
  - its class (parse, semantic, truncation, runaway reasoning, error);
  - runaway reasoning means `reasoning_tokens` equals `completion_tokens` at the cap;
  - any corrupted content.

**The drafted-against-serial check, before any speed is relied on.**
- On the frozen recipe: 5 held-out envelopes, greedy and seeded, with `draft` true and then `"draft": false`.
- The decoded replies must be byte-identical, as the vendor claims.
- A mismatch stops the trial, and its record goes to the owner.

**What is kept.**
- Raw request payloads, raw responses and every stream event, beside the normalized results.
- The recipe's pins (§5.7).
- All of it goes under `var/` and is attached to #2199.

**A negative** is recorded in this SIP as Atlas's and vLLM's were. It parks the trial; it does not delete it.

**G2, the adapter (§5),** only if G0 and G1 pass. **G3, cycles:** uncounted regression pairs on both stacks, interleaved
A, B, A, B, one engine resident at a time, judged on cycle wall-clock, with a short pre-registration. **G4, cutover:**
the owner's decision.
- Every later counted set and memory measurement restarts on the new engine.
- The approved lesson's replay check is re-run on it first.
- Rollback is S's restoration path (§5.6).

## 5. The adapter and its contracts (G2)

`adapters/llm/tensorfold.py`, in its own file (SIP-0106 §3.5a). It is selected by `provider == "tensorfold"`, required,
never defaulted (#1157).

### 5.1 The request interface

Today `LLMRequest` and `LLMPort`'s `generate`, `chat`, `chat_stream` and `chat_stream_with_usage` carry no `seed`, no
`top_k` and no thinking budget, and `LLMCapability` has no budget or seed constant (`squadops/llm/models.py`,
`squadops/ports/llm/provider.py`).

**Per-call controls become optional port fields.**
- `seed: int | None` and `thinking_budget: int | None` are added to `LLMRequest` and to all four generation methods, with
  default `None`. The new capability constants are `LLMCapability.SEED` and `LLMCapability.THINKING_BUDGET`.
- **The route:**
  - the replay tool and the G0/G1 harness set `seed` per generation;
  - the deploy's model configuration sets `thinking_budget` (the frozen recipe's value), and the handlers pass it through
    `chat_kwargs` with the other call settings;
  - the adapter writes both into the wire payload.
- **The behaviour where unsupported.** A provider that does not declare the capability **refuses a non-`None` value**
  with a `ValueError` naming the control, before any call. A control that changes the generation is never dropped
  silently.
- **Existing providers keep their behaviour.** Both fields default to `None` and are sent only when set.
  - The Ollama adapter declares `SEED` and sends `options.seed`, which Ollama honours.
  - vLLM declares `SEED`. Atlas declares neither.
  - No existing caller sets either field.

**Sampling defaults become recorded provider-level settings, not port fields.**
- The window manifest recorded the production model's defaults, which no call sends: temperature 1, `top_p` 0.95,
  `top_k` 20, `min_p` 0.
- The TensorFold arm is served with the same values as serve flags, recorded in the recipe, so both arms sample alike
  without a per-call `top_k`.
- A future per-call need adds a field by the same rule.

**Reasoning:**
- `reasoning_effort` carries the port's level, `none|low|medium|high`, and TensorFold maps `high` to Qwen3.8's `xhigh`
  itself.
- The adapter never sends `chat_template_kwargs.enable_thinking`, which would override the effort (§2).

**The acceptance tests:**
- distinct replay seeds reach the server;
- the thinking budget reaches every generation method;
- an unsupported control raises;
- the Ollama, vLLM and Atlas suites pass unchanged.

### 5.2 Termination, truncation and context overflow

Today `LLMResponse` and `ChatMessage` carry no stop reason. The cap check reads `completion_tokens` against the requested
`max_tokens` (`cycles/emission_integrity.py:109`, `reached_cap`), and with usage missing the cap "cannot be asserted". The
exception vocabulary has no context-overflow error, and an unclassified failure is retried, then sent to correction (the
D5 fallback, `dispatched_flow_executor.py`).

**A normalized termination field.**
- `termination: str | None` is added to `LLMResponse` and `ChatMessage`, with the vocabulary `stop | length`. `None`
  means the provider reported none.
- The TensorFold adapter maps `finish_reason`: `stop` → `stop`, and `length` → `length`. The vLLM and Atlas adapters
  map theirs the same way. Ollama's adapter is unchanged and leaves it `None`.
- `reached_cap` reads `termination == "length"` where it is set, and today's token rule where it is `None`. So
  existing providers keep today's path.

**Tokens.** `completion_tokens` stays **inclusive of reasoning**, with `reasoning_tokens` a subset of it. Nothing
subtracts reasoning or counts it twice (Q6).

**A `length` finish marks the cap. It never discards output by itself** (Q6).
- `termination == "length"` says only that the budget was reached: it stands in for today's token comparison.
- What happens next is decided by the content, exactly as #2149 decides it today:
  - a final block left **unclosed** is the cut, and is dropped;
  - **every block closed** means the response is returned as is;
  - an **empty answer** with the budget spent is the exhausted path.

**Missing usage.**
- On TensorFold a successful stream must carry its terminal finish frame and, with `include_usage`, its usage event
  (§5.4). A stream without them is an error, not a success.
- A non-streamed response without usage is accepted only with its `finish_reason`. The termination then decides the
  cap, and the tokens are recorded as unknown.

**Context overflow.**
- A new `LLMContextOverflowError(LLMError)` carries the served window and the prompt's tokens from the server's
  `context_length_exceeded`.
- The executor classifies it as **infrastructure**, not as the work product's failure. It is never `RETRYABLE` with the
  same prompt, and never routed to a correction round. The task is **held**, as a `BLOCKED` outcome, with the evidence,
  and the run escalates as any held task does.
- The prompt-size guard prevents it in the first place by reading the served window (§5.3). An overflow therefore
  means the registry and the server disagree, which is a deploy defect.

**The acceptance cases, each taking its path:**
- **reasoning-only exhaustion** (`length`, empty `content`, `reasoning_tokens == completion_tokens`): the exhausted
  path, then one retry with the fact;
- **a cut final code fence at the cap:** #2149's path, which drops the cut block;
- **a complete answer that ends exactly at the cap,** every block closed: returned as is;
- **missing usage:** as above;
- **context overflow:** `LLMContextOverflowError`, held, with no retry and no repair.

### 5.3 Model identity, with no production-name alias

The registry is keyed by model name only, and `qwen3.8:27b` already means a 262,144-token window and the TOGGLE dial
(`llm/model_registry.py`). Aliasing TensorFold to that name would claim a window and dial TensorFold does not serve.
- **Distinct TensorFold model ids** get their own `ModelSpec` entries, one per checkpoint in the matrix, for example
  `tensorfold/Qwen3.8-27B-MLX-4bit`. The served id is the server's `--name`.
- **Each entry records:**
  - the effective **served window** (the recipe's `--context`, or what the server sized);
  - the completion allowance;
  - `reasoning_control = EFFORT`, the graded levels that TensorFold maps;
  - `family = "qwen3.8"`, so the approved lesson's applicability resolves.

  Ollama's `qwen3.8:27b` entry is not touched.
- **Validation before work starts:** at the adapter's startup check and at the switch's verification step (§5.6), the
  served window is read from an authenticated source (§5.5). A registry window larger than the served one refuses to
  start.
- **The tests:**
  - prompt budgeting uses TensorFold's served window;
  - each port level reaches the server as the effort that maps correctly;
  - switching back to Ollama leaves `qwen3.8:27b`'s budgeting and dial exactly as before.

### 5.4 Streaming, deadlines and cancellation

- **Two timeouts, distinct.** A read-inactivity timeout catches a silent server. An **overall request deadline** bounds
  the whole call, stream included, so a stream that keeps emitting cannot outlive it. Either one raises
  `LLMTimeoutError`.
- **Cancellation closes the stream.** On a deadline, or on the caller's cancellation (including during reasoning), the
  adapter closes the HTTP stream, which TensorFold treats as a disconnect and cancels.
  - The adapter then confirms on authenticated metrics that the request is gone before the next request is sent.
  - A retry waits for that confirmation, bounded. If it cannot be confirmed, the state is unknown, never quiet (§5.5).
- **The terminal-state check.** A streamed call succeeds only when all of these arrived:
  - a finish frame with a `finish_reason`;
  - the usage event, which is consumed **after** the finish frame when `include_usage` is set;
  - `[DONE]`.
- **Errors are never partial successes.**
  - A `server_error` event, a malformed essential frame (a `data:` line that is not JSON), or a disconnect before the
    terminal frames each **raise**. The partial output is attached to the exception as evidence only.
  - This adapter does **not** copy vLLM's skip of malformed frames (`adapters/llm/vllm.py`).
- **The tests:**
  - content followed by `server_error`;
  - a missing terminal completion;
  - a usage-only final event;
  - continuous output past the deadline;
  - cancellation during reasoning;
  - a healthy request after each of these.

  Each test verifies that the cancellation released the server's work before the next request.

### 5.5 Authenticated health and residency

- **`/health` is not used for state:** with keys, it says only `ok`.
- **The state comes from authenticated sources:** `/metrics` (running requests, cache occupancy), `/v1/models` (the
  served id) and the served window. The window's authenticated source is identified in S and recorded. If none reports
  it, the recipe's `--context` is the record, verified by a probe at the boundary.
- **Aliases.** `/v1/models` lists the served id and its aliases, and the adapter maps them all to **one resident model**.
  The drafter is part of the recipe, not a second model. Neither raises a foreign-model alarm.
- **The states:**
  - `idle`: authenticated, the expected model, nothing running;
  - `busy`: authenticated, a request running;
  - `unauthorized`: a 401, an error that names the key setting;
  - `unreachable`;
  - `unknown`.

  **Only `idle` is safe to launch** under §24an. `unauthorized`, `unreachable` and `unknown` never are.
- **The tests:** the checks work with keys enabled, bad credentials fail visibly, aliases cause no false alarm, and an
  unknown state blocks a launch.

### 5.6 Switching and rollback (S, a prerequisite of G0)

Client selection (an env change and an agent restart, SIP-0106 §6.1a) is not engine residency. The overlay switches
clients. `scripts/dev/ops/engine_switch.py` (new, tracked) switches engines. #1177's arm script lived outside the repo,
and its guard was retired unbuilt.

**The switch, in order:**
1. **Hold the box:** the box lease where a campaign is open; otherwise, verify that no run is running or queued, and
   refuse new launches for the switch's duration.
2. **Stop new dispatch,** and drain running work or cancel it, recorded.
3. **Stop the old engine.** Ollama unloads its models and stops serving; TensorFold's container stops.
4. **Verify the memory is released:**
   - no GPU process resident;
   - `MemAvailable` at or above the pre-registered floor, proposed as at least 90 GiB of the box's 121 GiB.
5. **Start the selected engine** with its pinned recipe, `TENSORFOLD_MEMORY_RESERVE_GIB` and `--context` set.
6. **Authenticate, and verify** the served model, its window, its drafter and its flags against the recipe. The host
   headroom must stay at or above the pre-registered floor, proposed as 16 GiB `MemAvailable` after load.
7. **Resume clients,** with endpoint, model, credentials and provider switched together. Verify one healthy generation.

- **The floors (Q7, approved as initial safety floors, subject to validation in S):**
  - before a load, `MemAvailable` ≥ 90 GiB and no competing GPU inference process resident;
  - after TensorFold loads, ≥ 16 GiB.
- **The switch fails closed.** These abort it to restoration:
  - a missed floor;
  - unknown residency;
  - failed authentication;
  - a mismatch with the pinned recipe;
  - a startup failure;
  - a failed verification generation.
- **Memory is recorded:**
  - before the load and after it;
  - after warm-up;
  - **under representative long-context generation**, the longest captured prompts at their own `max_tokens`.

  S's evidence is the long-context record. Static idle headroom is not sufficient. If long-context generation violates
  the reserve or destabilizes the host, `--context` is reduced and S re-run, or the trial is parked. The floors are never
  relaxed to force a pass.
- **Restoration:** engines never overlap.
  - TensorFold is stopped **before** Ollama loads, and its release confirmed as in step 4;
  - Ollama is started;
  - Ollama's endpoint, model, credentials and provider are restored together;
  - one healthy generation is verified.
- **Exercised in S, before G0:** a full switch in each direction, a failed TensorFold startup (a bad flag) that restores
  Ollama, and a restoration from a verified-busy TensorFold.

### 5.7 The pinned recipe, and adapter and harness parity

- **Everything pinned and recorded:**
  - the TensorFold commit (`cb2ebf05…`);
  - the CUDA container image by digest;
  - the environment's frozen dependency list;
  - the target checkpoint revision, and the drafter revision;
  - the tokenizer and chat-template revision;
  - every serve flag, the thinking budget and the sampling defaults.

  A model tag and a server version alone do not reproduce a speculative-decoding deployment.
- **Live fixtures** come from the pinned GB10 deployment in G0, raw.
- **Parity.** G2 reproduces G0's effective wire payload and its response interpretation **through the real `LLMPort`
  entry points:**
  - the adapter's built request is compared, as JSON, with the raw requests G0 sent;
  - its normalized results on the recorded responses equal the harness's.
- **Any implementation change to sampling, reasoning, parsing or budget behaviour re-runs the affected gates.**
- **The other G2 parts:**
  - the overlay `docker-compose.tensorfold.yml`, whose exact contents come for review in its PR;
  - an API key from the deploy's `.env`, by #2006's rule;
  - inert on merge (SIP-0106 §4.1);
  - the `local-spark` bootstrap installs nothing until a cutover;
  - the unit conformance tier on G0's fixtures, and the live tier on the Spark.

## 6. Sequencing

- **While the 2.2 window is open: nothing on the Spark.** The manifest pins the engine. A second resident engine is the
  §1.2c trap. A benchmark would perturb the live campaigns.
- **After the 2.2 cut, on the Spark:**
  1. S;
  2. the pre-registration;
  3. tuning;
  4. the drafted-against-serial check;
  5. G0 and G1 on the held-out set.
- **G2's PR follows if both pass.** G3 and G4 follow on the owner's word.

## 7. What this does not do

- It does not add per-cycle engine routing (deleted, SIP-0106 §1.2d), and it does not touch 2.2's window.
- It does not swap the dense 27B for a MoE model on decode speed alone. TensorFold's strongest numbers are for Flash Next.
- It makes no claim from vendor figures. G0 replaces them with ours.
- It installs nothing by default. The `local-spark` profile stays Ollama-only until a cutover.
- It does not use a Mac at any step.

## 8. Questions for the owner

**All ruled (2026-10-09):** Q1–Q4 on revision 1, and Q6 and Q7 on revision 2 (the header records each). Q5 is removed.
Kept below as they were asked.

- **Q6: the port amendments** (§5.1, §5.2).
  - `seed` and `thinking_budget` as optional port fields, refused where unsupported;
  - the sampling defaults as recorded serve settings;
  - a normalized `termination`;
  - `LLMContextOverflowError`, held as infrastructure.

  Recommended as written. The alternative is to make the thinking budget a serve flag only, leaving the port alone for
  it. That works for G0 and G1, but no task could ever set its own budget.
- **Q7: the memory floors** (§5.6). Recommended: at least 90 GiB `MemAvailable` before a load, and at least 16 GiB after
  it. Both are written into #2199's pre-registration, and an abort below either.
