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

## Delivery ledger (current as of 2026-10-23)

Placed by the owner's Q1 ruling (2026-10-09). The rows are ordered as the work runs.

| part | status | where |
|---|---|---|
| S: engine switching and rollback, with the exclusivity guard, built and exercised before the first TensorFold load (§5.6) | **shipped** | 2.3.0, #2252: the switch and the four exercises, passed (their records are on #2199) |
| G0: throughput on held-out captured envelopes, against production Ollama, on a frozen recipe (§4) | **shipped** | 2.3.0, #2256 and #2262 (the harness and its reader), #2199: the 27B on NVFP4 passed, a median of 0.438 of Ollama's wall-clock (§9e) |
| G1: emission quality, the same calls through each task type's production validator (§4) | **shipped** | 2.3.0, #2256 and #2262, #2199: passed by the owner's ruling of 2026-10-13, with plan writing one answer under Ollama's (§9e) |
| G2: the adapter, dark, with the port amendments, registry entries, the overlay and parity tests (§5) | **shipped** | 2.3.0, #2268 (the port's controls, §9f), #2269 (the adapter, §9g) and #2270 (the clients' switch, overlay and key, §9h), closing #2200: the live tier passed on the Spark on 2026-10-13, the switch to TensorFold and back with the clients and an in-agent generation each way (#2200 issuecomment-6146480456) |
| G3: the selected candidate's uncounted cycle A/B on both stacks, compared on wall-clock, task times, retries, correction rounds and verdicts (§9a item 6) | **shipped** | 2.3.0, #2282 (the record, `docs/plans/verification-sets/2-3-0-tensorfold-g3-record.md`): every roll accepted on both arms; TensorFold's median cycle 0.45 of Ollama's on FastAPI+React and 0.61 on Next.js; two predictions falsified as registered (decode on every task type, and volume), the rest held; its arm held one planning draw per stack, not two (§9j) |
| a seed on every TensorFold call, G3's finding (§9j) | **shipped** | 2.3.0, #2283, closing #2281 |
| G4: cutover | **shipped** | 2.3.0, #2285, closing #2229 and #2284 (the switch records the deploy, §9k): adopted by the owner on G3's evidence on 2026-10-13 (§9j). The Spark serves on TensorFold from 2026-10-13 20:01 ET (dep_1724f586cc3a), and its cutover pair passed (§9k) |
| the memory watchdog as a host service that restores Ollama after a kill (§9l) | **shipped** | 2.3.0, #2289, closing #2288 |
| the upgrade to TensorFold 1.x, measured two ways: the engine, 1.x against 0.6.6 on the 27B; and the model, the 27B against Flash-Next on 1.x. S, G0 and G1 per checkpoint, then G2 to G4 for what is selected (§9m, which replaces §9a item 5's second candidate) | **unplaced** | deliberately, #2230: the owner on 2026-10-18, "I will want to tackle this move to 1.1.0 - but not just yet", and on its sequencing, "I think this model change will come after 2.4 and the outcome evaluation work". The second candidate it replaces was unplaced by the owner on 2026-10-15 ("no second tensorfold candidate at this time") and kept so by the 2.4 plan's D9 (ruled 2026-10-17). 2.3 ran only an exploratory measure of Flash-Next, and not measuring it is not a negative |

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
- **Amended by §9c (ruled 2026-10-12):** the level is not sent. TensorFold gets thinking on or off through
  `enable_thinking`, and with thinking on the recipe's `parity_effort`, so its prompt is Ollama's to the token.

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

## 9. Post-acceptance amendments

### 9a. The 2.3 plan's protocol amendments (RULED 2026-10-11, with the 2.3 plan)

**Status: ruled, 2026-10-11.** The owner approved the 2.3 plan's D1–D11 as recommended, and D10 is this amendment: "approve
D1-D11 as recommended". It was drafted in the same PR as the plan (#2228, revision 2), from the owner's review of the
plan's first draft ("apply all nine and the SIP amendment"). From here, §4's protocol is read with these changes.

**The owner's guidance on its numbers** (2026-10-11): "I'm ok with the numbers. Let's just be flexible as we see
performance in making a decision without such hard lines drawn early." So:
- **They are guides,** reported against, never automatic triggers: the selection margin, the drift threshold, and G3's
  comparison line.
- **Each decision is the owner's,** with its reason recorded where it departs from a guide.
- **The measurement protocol stays fixed:** the held-out set, frozen recipes, pairing, drift panels, clustered intervals
  and the reporting.
- **Q2's bars stand as ruled.**

**What changes:**
1. **A self-contained harness for S, G0 and G1** (amends §4's "sends its seed through the port (§5.1)").
   - **It calls each engine's own API:** Ollama's `/api/chat` with `options.seed` and the envelope's options, and
     TensorFold's `/v1/chat/completions` with `seed`, `reasoning_effort` and `thinking_budget`.
   - **It normalizes how each call ended** itself, and records every raw request, response, stream event, and prompt and
     decode duration.
   - **The port's four amendments (§5.1, §5.2) land with G2, not before.** The harness's recorded payloads and normalized
     outcomes become G2's parity fixtures.
2. **Repetitions, uncertainty and drift** (amends §4's seeds and order).
   - **Repetitions:** the generations per arm are the plan's D2.
   - **Uncertainty:** paired intervals clustered by envelope, reported beside the point estimates.
   - **What is reported:** unique envelopes, source cycles, repetitions and denominators, by seam and stack. An observed
     pass is reported apart from evidence of general non-regression.
   - **Drift** is read on a fixed panel of identical envelope-and-seed calls, at the start and end of each arm. The
     guide: at least 15 of 16 identical, and a median wall-clock change within 10%. Exceeding it flags the arm. The
     owner decides on a re-run.
   - **The bars of Q2 are unchanged.**
3. **Reusing the Ollama arm across candidates,** only if nothing it depends on changed:
   - the deploy, model digest, prompts, seeds, sampling and deadlines;
   - its cache treatment and each validator's revision.

   Its drift panel must also pass again at reuse time.
4. **The held-out set is protected:**
   - each recipe is frozen on tuning data before any held-out result is read;
   - screening prompts never come from the held-out set;
   - the selection rule (item 6) is fixed before either candidate's held-out run;
   - a recipe adjusted after a held-out look is exploratory, and needs fresh cases captured after the freeze.
5. **A second candidate: Qwen3.8-Flash-Next on TensorFold** (amends §7's "does not swap the dense 27B for a MoE model").
   - **Its own gate path:**
     - S's floors with its checkpoint;
     - a plan-authoring screening replay (#1408's gate);
     - its own frozen recipe and matrix on tuning data: checkpoint and revision, tokenizer and template, the
       `qwen4_exp` reasoning mapping, output allowance, drafting settings and context window;
     - G0 and G1 at the same bars.
   - **Its own registry identity, and a model family of its own,** never `qwen3.8`.
   - **Its forecasts are per checkpoint.** The EXL3 pack's prefill is under half the MLX checkpoint's in TensorFold's
     recipe.
6. **Candidate-specific outcomes, selection, and G3** (amends §4's G2 and G3 lines).
   - A failed gate parks that candidate only.
   - When both pass G0 and G1, **the owner selects.** The written guide prefers the 27B unless Flash-Next's median
     paired ratio is at least 0.15 lower, its G1 pass rate at least the 27B's on every seam, and its truncation and
     runaway rates no higher.
   - **G2 and G3 run on the selected candidate.** A replacement selected after a G2 or G3 failure needs its own G2 and
     G3.
   - **G3 is pre-registered.** It compares, against Ollama on both stacks:
     - cycle wall-clock, and task completion time by task type;
     - emission retries, correction rounds, and the final verdict with criteria and the boot audit.

     It is no longer judged on cycle wall-clock alone.
   - G1 is recorded as emission validity, never as reasoning or application quality.

**The evidence.**
- **The review of the 2.3 plan's first draft,** which the owner supplied (PR #2228). It found:
  - the G2 sequencing contradiction;
  - the gap between port-dependent seeds and a pre-G2 harness;
  - the missing drift isolation;
  - the overstatement that G1 decides adoption;
  - the need for a separate Flash-Next recipe.
- **TensorFold v0.6.6's [Flash-Next recipe](https://github.com/ashhart/TensorFold/blob/v0.6.6/docs/recipes/qwen3.8-flash-next.md):** the checkpoints, their memory, and
  the EXL3 pack's prefill.

**Who ruled it.** The owner, 2026-10-11, with the 2.3 plan's D9 and D10. The supervisor drafted it.

### 9b. S switches both containers (2026-10-11, with #2249)

**What changed.** §5.6 was written while Ollama was a host system service, so its steps 3 and 7 stop and start "Ollama"
without saying how, and the switch could not do it without sudo. #2249 moved the Spark's Ollama into a container
(`docker-compose.ollama.yml`), so `engine_switch.py` now stops and starts both engines itself:
- **To TensorFold:** `docker compose stop ollama`, then remove any `squadops-tensorfold` container, then step 4's release
  check, then `docker run` from the recipe.
- **To Ollama:** remove `squadops-tensorfold`, step 4's release check, then `docker compose up -d --wait ollama` and one
  healthy generation.

Nothing else in §5.6 changes: the order, the floors and failing closed are as written.

**The evidence.** The overnight S exercises of 2026-10-11/12 (records in `var/engine_switch/`, summarized on #2199):
- a switch to TensorFold with the box idle (87 s, the first start compiling the kernels; 23 s once cached);
- the long-context record, with `MemAvailable` never under 82 GiB and no swap;
- a restoration with a TensorFold request in flight (28 s);
- a failed start on an unknown flag, which exited 2 and restored Ollama.

**Who ruled it.** The owner approved moving Ollama into Docker ("go ahead with moving Ollama into docker on that scope",
2026-10-11). The switch's use of it follows from that, and #2199 was told (issuecomment-6115685094).

### 9c. Reasoning is sent at parity with Ollama's prompt (RULED 2026-10-12)

**What changed.** §5.1's "Reasoning" and §9a item 1 sent TensorFold the port's level as `reasoning_effort`, with
`high` heard as `xhigh`. From this ruling the harness, and G2's adapter, send what Ollama's prompt says:
- thinking on or off (`chat_template_kwargs.enable_thinking`);
- with thinking on, the recipe's `parity_effort`: the level whose rendered prompt is Ollama's to the token;
- never the port's level.

Level-aware thinking, which Ollama cannot express, would be a separate experiment, measured on G1 and G3 rather than
G0.

**Why.** The checkpoints' chat template (one template, md5 `519239a4`, in all four checkpoints the 2026-10-11 run loaded) writes an effort line into
every thinking prompt. By default, and for `high`, it is "Reasoning effort is set to xhigh. Please think carefully
through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency,
and clarity in the final answer." It writes a shorter "low" line for `low`, and none for `medium`. Ollama's template
for the same model writes none. So sending the level gives TensorFold a different prompt from Ollama's, and G0 would
measure the instruction as well as the engine.

**The evidence** (#2199, the overnight exploratory run, tuning data only):
- `/tokenize` at `medium` matched Ollama's `prompt_tokens` on all 18 thinking-on round-1 prompts; the default rendered
  38 tokens more on each;
- on `development.author_manifest` (reasoning high), the same engine and checkpoint wrote:
  - 12,288 tokens and hit the cap with the xhigh line (280 s);
  - 8,244 tokens and finished, at parity (145 s);
  - against Ollama's 5,455 (210 s).
- sent at parity, all 156 of the run's pairs (39 prompts on each of four checkpoints) had the same prompt token count on
  both engines (the results, 2026-10-12, are on #2199);
- §2's note that an explicit `enable_thinking` "wins over `reasoning_effort`" concerns `false`. With `true`, v0.6.6
  hears both: thinking on, at the effort sent (`cuda/server.py`, `heard_effort`).

**Who ruled it.** The owner approved it on 2026-10-12 ("1, yes", answering whether TensorFold should get exactly the
same prompt as Ollama). No counted gate had run. From here, §5.1's "Reasoning" and §9a item 1 are read with this
change.

### 9d. The 27B's gates run on TensorFold's Python 0.6.6 line (RULED 2026-10-12)

**What changed.**
- **This SIP assumed one TensorFold that would carry its recipe forward.** It doesn't. TensorFold 1.0 (2026-10-07) is
  a native rewrite, and its CUDA build serves only Nemotron. The 27B on the Spark runs only on the Python 0.6.6
  engine, in every checkpoint the tuning run loaded. §5.7's pinned recipe therefore pins the Python line, with no
  newer TensorFold to move it to.
- **The 27B's held-out run uses one generation per arm,** the 2.3 plan's D2 at its leanest, in place of §4's three and
  §9a's two.

**The evidence.**
- **TensorFold's own `docs/recipes/cuda.md` at v1.0.8:**
  - "The native binary registers only Nemotron on CUDA";
  - "EXL3 loading and DFlash2 drafting remain Python-engine features, not native upgrade paths."
- **Its release notes:**
  - v1.0.0 kept the 27B out: it was slower than Python 0.6.6;
  - v1.0.3 brought the 27B to the native engine on Apple silicon only.
- **The `python-0.6` branch** is 12 commits past `v0.6.6`, with none since 2026-10-07.
- **A community proposal** to port the 27B to native CUDA (ashhart/TensorFold#603) targets Ampere sm_86, not GB10.
- **On the one-generation choice:** in the tuning run every 27B checkpoint's median was 0.40–0.51 of Ollama's
  wall-clock, against G0's 0.75 (#2199). The interval G1 needs is the one the second generation would have narrowed.

**What it means.**
- If the gates and G3 pass, production would run an engine line that gets no further fixes for this model on this
  hardware.
- S's switch back to Ollama is the fallback. It took at most 28.2 s in S's exercises.
- A future native port is a recipe change, and re-runs G0 and G1.

**Who ruled it.** The owner, on 2026-10-12. Told the finding, the owner answered "once per prompt, run on 0.6.6,
NVFP4". The same answer chose the checkpoint. The pre-registration
(`docs/plans/verification-sets/2-3-0-tensorfold-27b-preregistration.md`) records it.

### 9e. The 27B's G0 and G1, read, and the owner's ruling on plan writing (RULED 2026-10-13)

**What changed.** Q2's validity bar is TensorFold's pass rate at least Ollama's, overall and per seam. On the 27B's
held-out run, plan writing came in one answer under Ollama's. The owner ruled that this does not fail G1, and that the
27B goes on to G2 on the frozen recipe without a re-run. Every other reading met its bar. So G2 (#2200) starts on
`infra/tensorfold/recipes/qwen27b-nvfp4.yaml`. No production switch follows from it; that is still G4.

**The evidence** (the held-out run of 2026-10-12, read by `engine_gates.py` as the pre-registration fixes it;
`docs/plans/verification-sets/2-3-0-tensorfold-27b-preregistration.md` §9, and #2199):
- **G0 passed.** The median paired ratio was 0.438 (interval 0.401–0.476) against the bar of 0.75. By seam: build
  authoring 0.356, plan writing 0.472, proposal writing 0.676 and repair 0.436. TensorFold hit its cap on 1 call and
  Ollama on 2. The truncation interval's unfavourable bound is +1.5 points, so the speed pass is observed on this
  corpus, not bounded. The arms took 3.5 h on TensorFold and 7.4 h on Ollama.
- **G1, by seam:**

  | | TensorFold | Ollama | difference (interval) |
  |---|---|---|---|
  | overall | 109 of 132 | 107 of 132 | +1.5 points (−4.5 to +7.6) |
  | build authoring | 41 of 46 | 38 of 46 | +6.5 points (−4.3 to +17.4) |
  | **plan writing** | **55 of 68** | **56 of 68** | **−1.5 points (−10.3 to +7.4)** |
  | proposal writing | 3 of 8 | 3 of 8 | 0 |
  | repair | 10 of 10 | 10 of 10 | 0 |

- **The one answer:** a Next.js `governance.prepare_plan_authoring_brief`, whose YAML failed to parse at line 98 on a
  mis-indented key. The model finished on its own (`stop`) at 7,809 tokens; it was not cut off.
- **Drift:** each arm's 14-envelope panel was identical before and after, 14 of 14, with median wall-clock changes of
  −0.3% (Ollama) and −0.2% (TensorFold).
- **The draft check:** all 5 drafted replies matched the plain ones byte for byte.
- **One change to the reader** after registration, before any validity verdict was read: an all-cache-hit group read
  as untimed rather than raising (#2262; the pre-registration's §5).

**Who ruled it.** The owner, on 2026-10-13, told the readings above and asked whether one answer under the bar fails
validity or the 27B goes on to the adapter, and whether to re-run plan writing first (about 8 h, or about 3 h for Next.js
plan writing only). The supervisor had recommended the full plan-writing re-run. The owner answered "1, does not fail
vailidity, let's go with TensorFold. 2, no re-run". The plan-writing reading stands as an observed miss of one answer,
and it is recorded here as the owner's departure from Q2's per-seam bar.

### 9f. G2's port amendments, as built (2026-10-13, with #2200's first PR)

**What was built** is §5.1 (a) and §5.2 (c) and (d), for every existing adapter. Two parts differ from the text.

- **`thinking_budget` is a port field with no deploy route.** §5.1 has the deploy's model configuration set it and the
  handlers pass it through `chat_kwargs`. The frozen recipe sets no budget (§9d; the pre-registration's §3), so that
  route would carry only `None`. The field, its capability and the refusal are built. The route is not, until a
  recipe sets a budget, and a recipe change re-runs G0 and G1 anyway.
- **The overflow is held by the agent, which the cycle executor already reads.** §5.2 has "the executor" classify
  `LLMContextOverflowError` as infrastructure. Every handler catches `LLMError` its own way, and some name their own
  outcome. So the one call every generation goes through (`_llm_call`) records the overflow on the task's context, and
  the handler executor gives any failed task with one `TaskOutcome.BLOCKED` and the evidence (`infrastructure_block`),
  whatever the handler named. The cycle executor pauses a run on a blocked result, as it does today. There is no
  retry and no correction round.

**What did not change:** Ollama leaves `termination` unset, and its cap is still read from the token count. vLLM
declares `SEED`; Atlas declares neither control. A provider refuses an undeclared control with `ValueError` before
any call, on all four generation methods.

**The evidence:** the conformance suite runs each control on all four methods of every adapter. A termination-decides-
the-cap test and the overflow test each enter where a live cycle enters (`handle`, and the handler executor).

**Who ruled it.** The owner, on 2026-10-13, approving #2268's merge ("1, merge"), in which the supervisor proposed
both. Neither changes a behaviour Q6 approved. The first leaves a route unbuilt because nothing would travel it. The
second places §5.2's classification at the one seam that sees every handler's failure.

### 9g. G2's adapter, as built (2026-10-13, with #2200's second PR)

**What was built:** `adapters/llm/tensorfold.py`, its `ModelSpec`, the factory's `tensorfold` and the config value, held
to the conformance suite and to G0's own calls. Nothing selects it until a deploy names it, so it is inert. The wire is
read from TensorFold's source at `cb2ebf05` (`server/http.py`, `errors.py`, `metrics.py`, `auth_http.py`). Seven parts
differ from §5's text.

1. **The registry's dial is `TOGGLE`, not `EFFORT`** (§5.3). From §9c the adapter sends thinking on or off with the
   recipe's `parity_effort`, never the port's level. A `MEDIUM` call thinks as a `HIGH` one does and is budgeted the
   same, which is what `TOGGLE` means to `thinking_headroom`.
2. **The sampling is sent with every call, from the frozen recipe** (§5.1 had it as serve flags). G0's requests
   carried it on each call, and §5.7 holds the adapter to G0's requests. The adapter's `RECIPES` table carries each
   frozen recipe's `parity_effort` and sampling, and a test holds it to the recipe YAML. A served id with no frozen
   recipe is refused: sent bare, it would think at the template's `xhigh` and sample at the server's defaults, which no
   gate measured. A call's own temperature or `top_p` still wins, as on Ollama.
3. **A call that names no reasoning level sends the effort alone.** TensorFold hears `reasoning_effort` without
   `enable_thinking` as thinking on at that effort. That is the model's own default posture, at Ollama's prompt, and
   no switch is sent the call did not ask for.
4. **Every call streams, `chat` and `generate` included.** One wire path and one terminal-state check (§5.4), so
   §5.2's case of a non-streamed reply without usage does not arise.
5. **A cancelled request's release is read from the request gauges** (§5.4). The CUDA server counts no client
   disconnections, only `tensorfold:requests_running` and `requests_waiting`. So the adapter reads them before each
   request, and after one is abandoned (a deadline, a cancellation, a broken stream), the next call waits until the
   count is back to that reading. It waits 30 s at most; past that the state is unknown, and the call raises before
   sending anything. It waits on the next call because a cancelled task cannot wait.
6. **The served window is checked before the first generation, not at startup** (§5.3). No composition root has a
   startup hook for an LLM port. `/tokenize`'s `max_model_len` is read once per model, and a registry window larger
   than it refuses every generation.
7. **Residency is `health()["state"]`, and the launch gate does not read it yet** (§5.5). `list_loaded_models` names
   the served id once, whatever its aliases, so the quiet-box check sees one model. The launch gate (§24an) still reads
   loaded models, not `busy`. Wiring `idle` into it belongs with the cutover. Until then, the box lease is what keeps a
   G3 launch off a busy engine.

**The evidence:**
- The conformance suite passes on TensorFold. It declares three things on its case: a stream must end with its usage
  (§5.4), the recipe's `top_p` is sent (§5.7), and its window and gauge reads are not generations.
- Every one of the run's 160 TensorFold calls, read through `chat_stream_with_usage` from its raw record, sent G0's
  request and read G0's text, tokens and termination: 132 held-out and 28 panel calls, 0 differences. Three of them
  are committed as fixtures.
- §5.4's cases each raise, and the request after each is healthy and waits for the release first. Writing them found
  a frame that raised in the caller leaving its stream open until garbage collection, which the adapter now closes.

**Who ruled it.** The owner, on 2026-10-13, approving #2269's merge ("1, merge"), in which the supervisor proposed
all seven. The deploy overlay and the switch's network attachment come in their own PR, for review as §5.7 asks.

### 9h. The switch moves the clients, and the key is the deploy's own (RULED 2026-10-13)

**What changed.** §5.6 step 7 had the clients resume "with endpoint, model, credentials and provider switched
together", and §5.7 an API key "from the deploy's `.env`". Neither said how. S, as built for G0 (§9b), moved only the
engines. From this ruling:
- **`engine_switch.py to-tensorfold` moves the model clients after it verifies the engine.** It recreates every
  running service that calls a model with `docker-compose.tensorfold.yml` appended to the deploy's `COMPOSE_FILE`.
  That overlay sets the provider, the URL (`http://tensorfold:8080` on squadnet, which the switch now attaches
  TensorFold to), the key and the served id together. The switch then runs one generation through the deployed
  adapter from inside an agent.
- **`to-ollama` moves them back**, and so does a restoration after a failed switch, whatever step it reached. An
  asked-for switch back refuses a box with work on it, since recreating the runtime API ends any cycle it runs.
- **The overlay replaces each client's `depends_on`, never merges it:** the Ollama overlay makes every client wait for
  Ollama, and compose would start Ollama beside TensorFold for any client it recreated. The engines never run
  together. Each list restates the base file's, and a test holds them equal.
- **`rebuild_and_deploy.sh` refuses while TensorFold serves.** Its first step starts Ollama's container, and its
  restarts would put the clients back on Ollama.
- **The key's home is `.env`** (`SQUADOPS_TENSORFOLD_API_KEY`, in `infra/deploy_credentials.json`). `deploy_credentials.py`
  generates it and writes the server's key file from it (`secrets/tensorfold_api_key.txt`, as `squadops: <key>`). There
  is one home, so a rotation reaches the server and every client. The key file outside the checkout
  (`~/tensorfold/secrets/api_key`) is retired.
- **A cycle on TensorFold names `full-38-tf`:** the `full-38` roster on the served id, since an agent takes its squad
  profile's model first. A test holds the two profiles equal in every other field.

**Who ruled it.** The owner, on 2026-10-13. Asked where the agents should get the key and whether the switch should
also move the clients, the owner answered "2 and 3, as recommended": the key from `.env`, registered for rotation, and
the switch moving the clients through an overlay that drops their dependency on Ollama.

### 9i. The cutover's machinery, built before G4 (2026-10-13, with #2229's readiness PR)

**What changed.** §4 has G4's cutover "by S's switching path", and §9h has the switch move the clients. Neither
covered what a deploy does after the cutover, so a TensorFold deploy could not be rebuilt. Since §9h, the rebuild
script refused while TensorFold served, its first step starts Ollama's container, and a re-bootstrap rewrote
`COMPOSE_FILE` back to Ollama's. A fresh box had no way to install TensorFold at all. So, ahead of G4:
- **The deploy records its engine.** Every switch writes it to `.env`'s `COMPOSE_FILE` (the TensorFold overlay
  named, or not), and `engine_switch.py deploy-engine` reads it.
  - `rebuild_and_deploy.sh` keeps it: on TensorFold it starts no Ollama and the clients come back on TensorFold.
  - A rebuild refuses a half-done switch, which is TensorFold serving a deploy whose `.env` says Ollama, or the
    reverse.
  - Bootstrap's Ollama setup keeps the overlay. A rollback (`to-ollama`) records Ollama again.
- **The launch gate reads a busy TensorFold as not quiet** (§5.5, which closes §9g item 7). A port reading,
  `requests_in_flight`, is declared as `loaded_models` is: TensorFold declares it from its authenticated request
  gauges, and the other adapters don't. `box_quietness` names any request in flight before a launch. Unread is an
  unread engine, never quiet.
- **A fresh box installs exactly what the frozen recipe pins.** `tensorfold_install.py` builds the image at the
  recipe's TensorFold commit (checked against the image's revision label) and fetches the checkpoint and drafter
  at their revisions, through the image itself. It is idempotent.
  - A bootstrap profile declares `inference_engine: {engine: tensorfold, recipe: …}`. The recipe must be a frozen
    one in the repository.
  - Bootstrap installs the recipe before the services start and switches at the end. Ollama stays installed as
    the rollback.
- **The runbook** is `docs/ops/inference_engine.md`.

**What it leaves for G4's own PR**, on the owner's decision:
- `local-spark` declaring `inference_engine: tensorfold`;
- the switch that makes TensorFold production on this box;
- the cut set on `full-38-tf`;
- this SIP's G4 row.

**The evidence:** each part is tested where it runs.
- The rebuild guard's own lines run against a fake `docker`, in five cases.
- Bootstrap's own function runs on a scratch `.env`, keeping the overlay.
- The switch writes the deploy's `.env`, a scratch one in the tests: its other lines and owner-only mode are kept,
  and a rollback clears the overlay.
- The quiet-box check runs through the real TensorFold adapter: idle is quiet; busy and a refused key are not.
- The installer runs against a fake `docker`: it builds and fetches at the pins, leaves a complete box alone, and
  refuses an image from another commit.
- The installer's dry run on the Spark reports the image, checkpoint and drafter present.

**Who ruled it.** The owner, directing the work on 2026-10-13: "I just want to implement tensorfold and complete the
2.3 plan!". The design of each part is proposed in its PR, and the owner rules it with the merge. It merges after
G3's last roll, because G3's switches run the main checkout's `engine_switch.py`.

### 9j. A seed on every call, before the cutover (RULED 2026-10-13)

**What changed.** §5.1 sent both new controls "only when set", and no production call sets a seed. §2 records the
engine's rule: "Without one, the seed is derived from the prompt, so a repeated request repeats its sample." Together
they keyed every production call on TensorFold to its prompt, so the same prompt drew the same answer. G3 found it (#2281):
TensorFold's two rolls on each stack planned identically, token for token, up to the merge. So its arm held one planning
draw per stack, where two were registered. From this ruling:
- **The TensorFold adapter sends a seed on every call:**
  - the call's own where it sets one, so the replay tool and the G0/G1 harness keep theirs;
  - otherwise a fresh one, drawn from the OS in the server's 63-bit domain.
- **The call's line names the seed** (`LLM chat_stream_with_usage completed: … seed=N`, and a line of its own for
  `chat_stream`). So any call can still be replayed with its own seed.
- **Ollama, vLLM and Atlas are unchanged.** Ollama samples afresh without a seed, and §5.1's "sent only when set" still
  holds for them.
- **Production's calls become the kind G0 and G1 measured.** Every gate call carried its seed (§4, §9a item 1). G3's
  calls were the first unseeded ones.
- **A path that re-sends an unchanged prompt now draws afresh,** on TensorFold as on Ollama: a framing reroll, a
  re-taken round, a blind retry. No inventory of those paths is needed for this.
- **The server's `TENSORFOLD_SEED_SALT` is not the fix.** It is one value per process, so it re-keys the derived seed,
  and a repeated prompt still repeats its answer.

**G4.** The owner adopted TensorFold for production on G3's evidence (the record's §8), with this change landing
first, so the 2.3 cut set's rolls are independent draws. The cutover has its own PR: the deploy's engine, the
production switch, and the cut set on `full-38-tf`.

**The evidence:**
- The G3 record's §6.1 (`docs/plans/verification-sets/2-3-0-tensorfold-g3-record.md`): each call's prompt and
  completion tokens in TensorFold's four rolls. Ollama's pairs differ on every row.
- The rule, read in TensorFold's source at `cb2ebf05`:
  - `server/request_options.py`'s `_resolve_sampling` takes `options.get("seed", seed_for(prompt_ids))`;
  - `engine/exact_sampling.py`'s `seed_for` is a SHA-256 of the prompt's token ids and the salt, cut to 63 bits.

**Who ruled it.** The owner, on 2026-10-13. Asked whether to switch production to TensorFold, with the supervisor
recommending this fix land first, the owner answered "1, yes". Asked to approve the fix's shape, as written above, the
owner answered "2, yes".

### 9k. G4: the cutover, as run (2026-10-13, with #2229's cutover PR)

**What changed.** The owner adopted TensorFold at G4 (§9j). §9i left four parts to this PR: `local-spark` on
TensorFold, the production switch, the cut set on `full-38-tf`, and the G4 row. The switch found a fifth.
- **The production switch ran on 2026-10-13 at 20:01 ET.** The deploy had been rebuilt from `e899a6c4` (the seed
  fix included) as dep_18acaffab259, with 73 of 73 loaded checks answering. `to-tensorfold` took 26.9 s, with the
  nine model clients moved and a generation through the deployed adapter. The deploy's `.env` records TensorFold.
- **The switch now records the deploy it leaves** (#2284, found by this switch):
  - **The defect:** the rebuild's record went on saying Ollama served, and `verify_loaded.py` read Ollama as
    recorded but not running. So every cycle launched afterwards would have carried a record naming the engine it
    did not run on.
  - **`deploy_facts.py`** reads TensorFold's container, which runs outside compose, as the service `tensorfold`.
  - **Each completed switch and each restoration records the deploy,** with the deploy's own revision from the
    runtime image's label. A switch that completed but could not record exits 4.
  - **On this deploy,** the record was written by hand with the fixed facts: dep_1724f586cc3a, which names
    `tensorfold` (its image at TensorFold's commit `cb2ebf05`) and no `ollama`. The deploy check reads it as
    describing what runs.
- **`local-spark` serves on TensorFold:** the frozen NVFP4 recipe and the squad `full-38-tf`. A fresh box installs the
  recipe and switches last (§9i).
- **`doctor` checks the squad against the engine's models.** The engine block carries the recipe's `served_id`, and
  on TensorFold the squad check reads it, since the adapter serves no other model (§5.3).
- **The cut set runs on `full-38-tf`.** Its configurations come with its pre-registration, in the 2.3 plan's phase 9.
- **Two loaded checks**, which the old code fails: `2229-quiet` (§9i's launch-gate reading) and `2281` (§9j's seed).

**The evidence: the cutover pair** (`2-3-0-cutover-regression-tensorfold-fastapi-react.yaml`). It is two uncounted
shakeouts of one FastAPI+React request on `full-38-tf`, with what they must show stated before the first launch.
- **Both cycles completed accepted, and the boot check passed on both,** each app declaring three routes:
  - `cyc_af79e6520ae6`: 27.6 min, 20 of 20 criteria, one correction round. A QA test was itself wrong
    (`test_leave_run_empty_name_rejected`), classified a work-product defect, and patched.
  - `cyc_a21e10ff8fde`: 25.1 min, 21 of 21 criteria, no rounds.
- **The seed is live:**
  - each of the pair's 37 calls named its seed, and none repeated;
  - the first call, the data agent's research context, sent the same 4,247-token prompt in both cycles and answered
    with 4,447 and 4,885 completion tokens;
  - G3's two TensorFold React rolls had both answered that prompt with 6,129;
  - the cycles diverge from that first call on.
- **Every call ended `stop`,** each launch found the engine idle, and both cycles carry dep_1724f586cc3a.
- **The box:**
  - `MemAvailable` stayed at 70.3 GiB or more, with no swap;
  - the memory watchdog ran throughout, started by hand as for G3, and never acted;
  - the board peaked at 90.4 °C while the branch's test suite ran on the box during the first cycle, and at
    84.1 °C outside that window (G3's TensorFold range was 81.2–85.0).

**Who ruled it.** The owner, on 2026-10-13: G4 adopted ("1, yes", §9j). The design of each part is proposed in this
PR, and the owner rules it with the merge, as §9i's were.

### 9l. The memory watchdog: a host service that restores Ollama (RULED 2026-10-13)

**What changed.** §5.6 has the memory watchdog kill TensorFold when `MemAvailable` stays under its floor or swap
climbs, and "let restoration start Ollama". Two things were missing once TensorFold became production (§9k, #2288):
- **Nothing started the watchdog.** G0, G1 and G3 had it because their chains started it. At the cutover it was
  started by hand, so it would have stopped at the next reboot or session kill.
- **A kill left the box with no engine.** Nothing ran the restoration, so the clients stayed on a dead TensorFold
  until someone ran the switch back.

From this ruling:
- **The watchdog is a host service,** `squadops-memory-watchdog` (`infra/systemd/`). It is wanted at boot, restarted
  whenever it stops, and the last process the OOM killer takes. It is installed once per machine with sudo, as the
  backup timer is (`scripts/dev/ops/install_host_unit.sh`, which now installs a long-running unit as well as a
  timer). It acts only while TensorFold runs, so it stays on whichever engine serves.
- **After a kill, it runs `engine_switch.py restore`:**
  - Ollama started and the clients moved back, as a failed switch restores, and the deploy recorded (§9k);
  - no refusal for work on the box, since that work's engine is gone;
  - nothing done when Ollama already serves a deploy that records it.
- **One engine switch runs at a time on the host.** Every command that moves an engine takes one lock, and waits
  for a switch in progress. So the watchdog's restoration never runs beside a switch's own, and a switch that
  fails restores Ollama itself.

**The evidence:**
- The watch's step is tested where the service's loop enters it. It acts on two low readings or a swap climb while
  TensorFold runs, and on nothing else.
- The kill is followed by the restoration, whose failure or hang is logged as one.
- `restore` is tested at `main`, as the watchdog runs it, in four states. A switch holding the lock makes every
  engine command wait, touching nothing.
- The unit guard requires a unit with no timer to be wanted at boot and restarted always. `systemd-analyze verify`
  passes on the rendered unit.

**Who ruled it.** The owner, on 2026-10-13. Asked how the watchdog should run in production, the owner chose "a": a
host service installed once with the owner's sudo, which after a kill switches the box back to Ollama.

### 9m. The second candidate becomes the upgrade to TensorFold 1.x (RULED 2026-10-18)

**What changed.**
- **#2230 no longer measures Flash-Next as a second candidate on the Python 0.6.6 engine** (§9a item 5). It is now
  the eventual upgrade to TensorFold 1.x, measured two ways:
  1. **the engine:** 1.x against 0.6.6, on the 27B. This answers whether to upgrade.
  2. **the model:** the 27B against Flash-Next, on 1.x. Flash-Next keeps §9a item 5's terms: its own frozen recipe,
     registry identity and model family, never `qwen3.8`, with nothing carried over from the 27B.
- **This departs from Q4** ("don't plan to use the 1.0.x version") **and from this SIP's v0.6.6 scope.** Production
  stays on 0.6.6 (§9d, §9k) until this row's own G4.
- **Flash-Next has two checkpoints to test on 1.x.** The owner agreed the same day to add the second ("sure add"):
  - the MLX affine 4-bit with the MTP head, which 1.1.0 serves natively on one GPU;
  - NVIDIA's quantization-aware-distilled (QAD) checkpoint, `nvidia/Qwen3.8-Flash-Next-FP4-Local` (revision
    `b9ce18a6`, 102.3 GB). It becomes eligible when a TensorFold release serves it on one GPU without the
    experimental label.

  Both are probed on the same tuning prompts, one at a time, since the two together are 215.5 GB. One goes on to
  the held-out run.
- **It comes after 2.4 and the Outcome Evaluation work.** The owner, the same day: "I think this model change will come after 2.4 and the outcome evaluation work". So it isn't placed in
  2.4, and it doesn't run during 2.4's measurement.
- **The row stays unplaced.** Before it runs, the owner rules on:
  - its placement;
  - the 1.x release pinned at the start;
  - the disk for the Flash-Next checkpoint;
  - the bars for the engine question, fixed before any held-out run (§9a item 4).
- **The path is the supervisor's draft, in #2230's body, for the owner's review at placement:**
  1. an exploratory probe of each candidate, on tuning prompts only, with its predictions written down first. For
     the QAD checkpoint, the predictions are fewer output-cap hits and thinking runaways than the MLX 4-bit, and
     decode about a quarter slower;
  2. a native image pinned by sha256, and the switch's serve command for each engine line;
  3. the adapter and the harness, checked against the native wire;
  4. S, G0 and G1 for each checkpoint, on the 132-envelope held-out plan, with every arm's stored answers scored on
     one framework SHA;
  5. G2, G3 and G4 for what is selected.

  A recipe change re-runs G0 and G1 (§9d).

**The evidence (read 2026-10-18).**
- **TensorFold 1.1.0, released 2026-10-18,** serves both models on CUDA through the native server: Qwen3.8-27B with
  DFlash2, and Qwen3.8 Flash Next with its MTP head
  ([release notes](https://github.com/ashhart/TensorFold/releases/tag/v1.1.0)). §9d's finding was that the native
  CUDA build served only Nemotron, and its release notes now say otherwise.
- **Native Flash-Next reads one checkpoint on one GPU:** MLX affine 4-bit, group 32, with the MTP head
  (`TensorFold/Qwen3.8-Flash-Next-MLX-4bit-MTP`, revision `2b170fa6`, 113.2 GB). The EXL3 pack 2.3 measured is
  served only by the Python engine
  ([`flash-next-cuda.md`](https://github.com/ashhart/TensorFold/blob/v1.1.0/docs/recipes/flash-next-cuda.md)).
- **NVIDIA's QAD checkpoint** ([its card](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-FP4-Local)):
  - **What it is:** its routed experts are NVFP4, trained by distillation against the BF16 model. The training adds
    separate losses for ending the thinking and ending the answer, and 2.3's Flash-Next misses were of that kind.
    On the EXL3 pack it hit the 12,288-token cap twice and ran away thinking once.
  - **NVIDIA's figures:** 91.5% on GPQA Diamond against BF16's 92.2%, and 88.7% on ToolEvalBench against 89.4%.
    The card gives no comparison with the MLX 4-bit or the EXL3 pack.
  - **On TensorFold:** 1.1.0's notes call a ModelOpt NVFP4 Flash-Next experimental, on two ranks. Its one-GB10
    measurements are in TensorFold's pull request 952, still open:
    - drafted decode: 64.1–64.6 tok/s on code and 40.7–41.1 on chat, against the MLX 4-bit's 84.2 and 62.6;
    - a cold 8,192-token prompt: 7.11 s, about the MLX 4-bit's rate;
    - the prompt cache: not qualified with drafting on that path.
  - **Its terms:** the NVIDIA Open Model Agreement, over the Qwen Community License.
- **Not yet read: which 27B checkpoints native CUDA reads.**
  - 1.1.0's notes name MLX checkpoints for the Qwen CUDA family. They don't name NVIDIA's NVFP4 export.
  - If native CUDA doesn't read NVFP4, the engine question holds `TensorFold/Qwen3.8-27B-MLX-4bit` fixed on both
    engines. Production's NVFP4 on 0.6.6 stays the reference.
- **The native server keeps the Python server's wire names:**
  - the request gauges;
  - `max_model_len`, `invalid_api_key` and `context_length_exceeded`;
  - the thinking controls;
  - `--api-key-file`.

  Their behaviour is read from the native source at the pinned tag before any harness call, as §5.7 read the
  Python source.
- **The vendor's Flash-Next numbers on one GB10:**
  - 84.2 tok/s drafted on code, and 62.6 on chat;
  - a cold 12,001-token prompt in 10.4 s, against 6.7 s on the Python engine.
- **A forecast, which the probe tests.** 2.3's exploratory run measured Flash-Next at 0.37 of Ollama's wall-clock
  (#2199), and the 27B's held-out reading was 0.438 (§9e). Against those, Flash-Next on 1.1.0 is forecast near
  0.33–0.37. §9a item 6's guide asks it for about 0.29.

**What it means.**
- **This section replaces §9a item 5.** Its rules for Flash-Next carry over. §9a items 1–4 and 6 apply to every
  candidate here.
- **SIP-0111 stays accepted while this row is open,** as it did while the second candidate was unplaced.
- **An overlap with SIP-0113, Outcome Evaluation,** recorded in the portfolio's intake log:
  - switching the engine or the model while it measures changes an input that its comparisons across units read;
  - its §4.6 names only the project-instruction set as a listed input;
  - SIP-0111 owns the switch and its gates.

  The owner's sequencing settles when this row runs: after 2.4 and the Outcome Evaluation work. One question stays
  open, to be ruled before the row is placed. Should SIP-0113 add the engine and the model to its listed inputs? A
  comparison made after the switch, against baselines measured before it, spans the change.

**Who ruled it.** The owner, on 2026-10-18. After the supervisor assessed the effort of #2230 on 1.1.0, the owner
said "I will want to tackle this move to 1.1.0 - but not just yet". The owner then directed that #2230 focus on
eventually upgrading to TensorFold 1.x, and on evaluating its performance against 0.6 and the 27B against Flash-Next.
On the PR that records this section (#2423), the owner set its sequencing: "I think this model change will come after 2.4 and the outcome evaluation work".
The supervisor rewrote #2230 (its comment `issuecomment-6250014247` records the redirection) and drafted this section.
Asked whether to add NVIDIA's QAD checkpoint as a second Flash-Next checkpoint, the owner answered "sure add".
