---
sip_uid: '1791574804220728'
status: proposed
title: TensorFold Provider Adapter
author: Jason Ladd
created_at: '2026-10-09T00:00:00Z'
---
# SIP: TensorFold Provider Adapter

**Status:** Proposed (draft, 2026-10-09, for the owner's review)
**The owner's ruling on the version (2026-10-09):** "don't plan to use the 1.0.x version. base our adapter on the faster
python version that support the qwen 3.8 27b". **Pinned: TensorFold v0.6.6** (tag `v0.6.6`, commit `cb2ebf05`, released
2026-10-06). It is the last Python release, and its CUDA server serves Qwen3.8-27B. The 1.0.x Zig line is not used.
**Target:** unplaced until the owner rules (§8). Recommended: gates G0–G2 on the 2.3 line, dark (§6); cutover by
evidence, not by date.
**Authors:** Jason Ladd (the direction, 2026-10-09: plug in TensorFold "as soon as I can to benefit from the tps for
running cycles and campaigns"); Claude Code (this draft).
**Extends:** SIP-0106 (Atlas Provider Adapter, implemented). TensorFold is a third candidate engine behind the same
`LLMPort`, under SIP-0106's design: provider selection as required configuration (§3.1), declared capabilities (§3.2),
provider-scoped model identity (§3.4), one adapter per provider (§3.5a), the conformance suite as the gate (§3.6), the
dark-ship rule (§4) and the A/B protocol (§6.1a). Nothing here redesigns the seam.

## Intake check

Checked against `sips/PORTFOLIO.md` on 2026-10-09 (CLAUDE.md, "SIP System").
- **Overlaps:**
  - **SIP-0106, all of it, by design.** Its seam, gates and protocol are reused. Its two outcomes are this draft's
    evidence (§3): Atlas was not adopted (§1.2a) and the vLLM arm is parked (§1.2e). Boundary: SIP-0106 keeps the seam
    and its rules; this draft adds one adapter and one measured trial.
  - **SIP-0110, Cross-Cycle Memory.** The 2.2 measurement window pins the engine in its manifest, so nothing here runs
    on the Spark until the window closes (§6). Its captured authoring envelopes are this trial's corpus (§4, G0–G1).
    An engine change is a change to a listed input for every later measurement, and the approved lesson's tested
    applicability names the `qwen3.8` configuration in the window's manifest (§4, G4).
  - **SIP-0073, the model registry.** A TensorFold model id needs a registry entry with family `qwen3.8`. Without one,
    `model_family_of` returns `""` and the approved lesson silently stops applying (§5).
  - **SIP-0109's box lease and quiet-box launch rule (§24ai, §24an).** A launch waits while a model the deploy does not
    declare is resident, so the adapter's model listing must answer that check truthfully (§5).
  - **#1177 and #1178 (closed): arm exclusivity and OOM containment.** Both engines resident at once on the Spark's
    unified memory made the box unreachable once (SIP-0106 §1.2c). Every step here carries the exclusivity guard.
- **Conflicts:** one, for the owner's ruling. **2.3 is a stabilization release, feature-free by rule.** A dark adapter
  changes no squad behaviour, and SIP-0106 §4.3 waived the even/odd rule for exactly that reason. Placing G0–G2 in 2.3
  needs the same waiver (§8 Q1).

## Delivery ledger (current as of 2026-10-09)

Nothing is placed until the owner rules (§8).

| part | status | where |
|---|---|---|
| G0: feasibility and throughput on captured envelopes, Ollama against TensorFold, one engine resident at a time | **unplaced** | recommended: 2.3, after the 2.2 cut |
| G1: emission quality, the same envelopes through each handler's own gate | **unplaced** | recommended: 2.3, with G0 |
| G2: `adapters/llm/tensorfold.py`, dark, with conformance, registry entries and the deploy overlay | **unplaced** | recommended: 2.3, only if G0 and G1 pass |
| G3: uncounted cycle A/B on both stacks, judged on cycle wall-clock | **unplaced** | after G2 |
| G4: cutover | **unplaced** | the owner's decision on G3's evidence |

**What closes this SIP:** G4 decided (adopted, or parked with its record), with each earlier gate shipped or its
negative recorded.

## 1. Summary

The squads' throughput is bounded by single-stream decode. SquadOps dispatches one task at a time, and on the Spark
production Ollama decodes `qwen3.8:27b` (Q4_K_M) at about 22–37 tok/s on real work: 22.4–22.7 tok/s in today's
diagnostic cycle's handler lines, 23.6–36.8 tok/s on framing in SIP-0106 §1.2e, and 23.9–27.4 tok/s in the box's
reference measurement. TensorFold claims up to 2× on the same model through exact speculative decoding.

**The premise needs one correction.** TensorFold's API is **OpenAI-shaped, not Ollama's** (§2). The Ollama adapter
cannot be pointed at it by changing a URL. It needs its own adapter, as Atlas and vLLM did, and SIP-0106 built the seam
that makes that cheap.

**This engine class has failed here twice, and both failures were measured, not argued** (§3). So the plan is a ladder
of gates. Each gate is cheap and runs before the next one's cost is spent:
1. **G0, throughput on our own prompts:** the SIP-0110 capture corpus, sent to each engine in turn.
2. **G1, emission quality:** the same prompts, through each handler's own gate.
3. **G2, the adapter, dark:** built only after G0 and G1 pass, from responses recorded in G0.
4. **G3, a cycle A/B:** uncounted, on both stacks, judged on cycle wall-clock.
5. **G4, cutover:** the owner's decision on G3's evidence.

## 2. What TensorFold is (read 2026-10-09, from its own README and CHANGELOG)

Sources: [ashhart/TensorFold](https://github.com/ashhart/TensorFold) (upstream),
[its CHANGELOG](https://github.com/ashhart/TensorFold/blob/main/CHANGELOG.md), and a fork's README
([BobClawblaw/TensorFold](https://github.com/BobClawblaw/TensorFold)). Every performance figure below is the vendor's.
None has been measured here.

- **The API:** OpenAI chat completions, completions and Responses, plus Anthropic Messages, at
  `http://127.0.0.1:8080/v1`. Also `/v1/models`, `/metrics`, `/stats` and `/memory`. **No Ollama endpoints** (`/api/chat`,
  `/api/tags`, `/api/show`). Models are managed by the CLI (`pull`, `serve`), not over HTTP, as with Atlas.
- **Versions:** 0.3.0 (2026-09-26) was the first CUDA release. **v0.6.6** (2026-10-06) is the last Python release, and
  the one pinned here (the owner's ruling, above). 1.0.0 is a native Zig rewrite, and 1.0.2 is current. That is two weeks
  of CUDA history, with releases most days.
- **Our model on our box.** **1.0.0 qualifies CUDA on GB10 for Nemotron only, greedy decoding only.** Its changelog says
  Qwen3.8-27B's "served speed is still below Python 0.6.6". The Python line (0.3.5–0.6.6) served Qwen3.8-27B on CUDA:
  - **0.5.0, one Spark, MLX 4-bit with DFlash2 drafts:** 18.4 → 38.9 tok/s at 128k context, and 23.6 → 45.9 at 96k;
  - **0.6.1, NVFP4:** first token on a Spark from 1.6 s to 0.15 s;
  - **0.3.6.2, `--parallel 16`:** 161.7 tok/s aggregate on one Spark. That is not our workload: we dispatch one task at
    a time, as vLLM's idle 24× concurrency showed (SIP-0106 §1.2e).
- **v0.6.6 on our model and box** (its `docs/recipes/qwen3.8-27b.md` at the tag; vendor's figures):
  - It serves Qwen3.8-27B on CUDA in three forms:
    - `TensorFold/Qwen3.8-27B-MLX-4bit`;
    - `nvidia/Qwen3.8-27B-NVFP4`, on one GPU;
    - `turboderp/Qwen3.8-27B-exl3`, experimental.

    Each runs with the `z-lab/Qwen3.8-27B-DFlash2` drafter, which CUDA requires unless `--no-drafts` is set.
  - **Decode on one GB10, 64-token replies, sampled:**
    - MLX 4-bit: 57.8 tok/s on code and 50.0 on chat;
    - NVFP4: 47.1 and 38.2;
    - EXL3 3.00bpw: 83.4 and 44.2;
    - vLLM MTP=3, for comparison: 23.4 and 25.4.

    These are short replies. Ours run to thousands of tokens of reasoning on 30–50k-token prompts, where 0.5.0 reported
    38.9–45.9 tok/s at 96–128k.
  - **Install:** NVIDIA's `pytorch:26.07-py3` container, then `pip install git+https://github.com/ashhart/TensorFold.git@v0.6.6`
    (its RUNBOOK's DGX Spark setup).
- **Exact speculative decoding:** a drafted token is accepted only when it equals the token the same engine would
  produce serially. That holds against the same engine, weights and settings. **It does not make TensorFold's output
  equal Ollama's.** The weights differ (MLX 4-bit, NVFP4 or FP8, against Ollama's GGUF Q4_K_M), so quality is measured,
  never assumed (G1).
- **The API at v0.6.6** (its `docs/api.md` at the tag):
  - **Reasoning arrives separately,** in `reasoning_content` (`delta.reasoning_content` when streaming), never inline.
  - **`reasoning_effort` is accepted per request.** For Qwen3.8 the server maps an unnamed level to the template's
    nearest (`high` and `max` are heard as `xhigh`), so unlike Atlas the adapter needs no mapping.
  - **`thinking_budget` is accepted per request,** a cap on tokens inside reasoning. It is the documented control for
    vLLM's blocking failure shape (§3).
  - **Usage:** prompt, completion and total tokens, `cached_tokens`, and `completion_tokens_details.reasoning_tokens`.
    Streamed usage arrives in its own final event with `stream_options.include_usage`.
  - **Errors:** a prompt and reply that overflow the window are refused with HTTP 400 and `context_length_exceeded`
    before generation. A generation error is HTTP 500, or a `server_error` event then `[DONE]` once a stream is open.
  - **No server-side request timeout is documented,** so the client's timeout is the only one.
  - **Sampling is seeded from the prompt by default.** The same request repeats the same sample unless it sends a
    `seed`, so a replay's repeated generations must send a seed each.
  - **`GET /health` carries counters,** including `busy`, `requests_running` and `context_length`.
- **Memory on GB10:** the CUDA server's allocations come out of host RAM and are not charged to a container's memory
  limit. It sizes its window from `MemAvailable` less a reserve (`TENSORFOLD_MEMORY_RESERVE_GIB`), and the docs warn that
  exhausting unified memory can freeze the host. That is §1.2c's trap in the vendor's own words.
- **Auth:** API keys (`--api-key-file`, a Bearer token). The default bind is localhost.
- **Licence:** Apache-2.0 from 0.6.0 (MIT before).

## 3. What Atlas and vLLM taught, which this plan carries

1. **A vendor's speed claim predicted the wrong direction.** Atlas was predicted at ≥2× Ollama's decode rate and measured
   0.4× on framing (SIP-0106 §1.2a). vLLM measured 7.8–10.8 tok/s against Ollama's 23.6–36.8 (§1.2e). **G0 measures on
   our prompts before anything is built.**
2. **Throughput was the smaller half. The blocking measurement was emission quality.** vLLM authored 0 of 3 plans on the
   stored `merge_plan` prompt, where Ollama authored 5 of 5. Two of the three spent the whole budget thinking. Atlas
   authored 0 of 44, its loop guard corrupting correct YAML. **G1 runs every seam's gate before any adapter merges.**
3. **Two engines resident at once on unified memory took the box down** (§1.2c, #1177). **Exactly one engine serves at
   a time,** behind the arm-exclusivity guard.
4. **Compare deploy against deploy** (the owner's ruling on the Atlas A/B, 2026-08-28):
   - production Ollama as it runs, never re-tuned, because it is the baseline every record sits on;
   - the candidate at its best tuned recipe, chosen by a stated matrix of checkpoint × drafts × flags;
   - the same model size on both arms (Qwen3.8-27B).

   Quantization is a stated property of each arm, not a confound to equalize, so each arm's weights and flags are
   recorded verbatim.
5. **Parked is not deleted.** A negative is recorded, and the adapter, if one was merged, stays in the tree, inert (§4).

## 4. The gates

**G0: feasibility and throughput (Level 1 of SIP-0106 §6.1a; no cycle runs).**
- TensorFold **v0.6.6** (the owner's ruling), with the DFlash2 drafter. The checkpoint is chosen by a stated matrix,
  as the owner's Atlas ruling asks of a candidate's best tuned line:
  - `TensorFold/Qwen3.8-27B-MLX-4bit`, the vendor's fastest dense-27B form on GB10;
  - `nvidia/Qwen3.8-27B-NVFP4`;
  - `turboderp/Qwen3.8-27B-exl3` at 3.00bpw (experimental, lower precision; it is in the matrix only if G1 holds for it).

  Each is recorded by revision, with every serve flag. `--context` and `TENSORFOLD_MEMORY_RESERVE_GIB` are set so its
  memory leaves headroom on the unified GB10.
- **The corpus is SIP-0110's capture:** byte-exact authoring envelopes at every consuming seam, from real cycles, on both
  stacks: plan writing (including `governance.prepare_plan_authoring_brief` and `merge_plan`), build authoring,
  proposal writing and repair. Take a fixed sample, chosen before any is sent, and send each to Ollama, then to TensorFold,
  with Ollama unloaded in between.
- Each envelope carries the call settings it was captured with: the model, `max_tokens` 12,288 and reasoning `high`.
  The model's defaults it did not send are recorded too: temperature 1, `top_p` 0.95, `top_k` 20. Both arms use those.
- Record per call: wall-clock, time to first token, decode rate (the engine's own and from wall-clock), completion and
  reasoning tokens, `finish_reason`, and `load_ms ≈ 0` (warm-up discarded).
- **Recommended pass criterion (§8 Q2):** TensorFold's median wall-clock per call is at most 0.75× Ollama's (at least
  1.33× faster) on the sample, at no worse a truncation rate. Below that, park with the record.

**G1: emission quality (the half that failed before).**
- The same responses, each scored by its handler's own gate:
  - `ImplementationPlan.from_yaml` for plans;
  - the build emission parser and its slot checks for builds;
  - the change-request rails for proposals.
- **Pass criterion:** TensorFold's pass rate is at least Ollama's on the same envelopes.
- There must be **no runaway reasoning** (a budget spent inside the think block) and **no corrupted content**.
- If reasoning runs away, `--thinking-budget` is the documented control, and its value is recorded as part of the arm's
  recipe.

**G2: the adapter, dark (only if G0 and G1 pass).**
- What is built is listed in §5.
- Fixtures are recorded from G0's live responses, not written from the vendor's description.
- **Gate:** the unit conformance tier, and then the live tier, which vLLM passed 14 of 14.
- **Inert on merge (SIP-0106 §4.1):** no deploy selects it, and the `local-spark` bootstrap does not install it until it
  is adopted (§1.2f's precedent).

**G3: cycles (Levels 2 and 3).**
- Uncounted regression pairs on both stacks, interleaved A, B, A, B, one engine resident at a time.
- Judged on **cycle wall-clock** (the owner's ruling of 2026-08-08: decode rate is diagnostic), with acceptance verdicts,
  correction rounds and envelope reconstruction observed.
- A short pre-registration is written before the first pair runs.

**G4: cutover (the owner's decision).**
- **What a switch costs:** every later counted set and memory measurement restarts on the new engine, because the engine
  is a listed input.
- The approved lesson was tested on the `qwen3.8` configuration under Ollama, so its replay check is re-run on the new
  engine before anything relies on it.
- **Rollback** is SIP-0106 §4.2a's: an env change and an agent restart.

## 5. The adapter (G2), within SIP-0106's design

- **`adapters/llm/tensorfold.py`, its own file** (§3.5a). It is OpenAI-shaped like `vllm.py` and `atlas.py`, but its
  dialect differs where it matters, so a shared base would need provider conditionals (#559).
- **Factory and config:** `provider == "tensorfold"` in `create_llm_provider`, and the value in the config schema.
  The provider stays required, never defaulted (#1157).
- **Capabilities, declared (§3.2), against v0.6.6's documented API and confirmed by G0's recorded responses:**
  - **reasoning:** read from `reasoning_content` and `delta.reasoning_content`, never spliced into the text, as the
    Atlas adapter does;
  - **reasoning effort:** passed through. The server maps Qwen3.8's levels itself;
  - **thinking budget:** `thinking_budget` per request, declared as a capability. It is the lever for runaway reasoning,
    and any default is recorded in the arm's recipe;
  - **usage:** `reasoning_tokens` give the thinking-token accounting, and streamed usage comes from the final
    `include_usage` event;
  - **truncation:** `finish_reason: "length"` surfaces as the truncation the cap-truncation path already handles (#2149).
    An empty `content` after an unclosed think block is a truncation, never an answer;
  - **context overflow:** HTTP 400 `context_length_exceeded` becomes a typed error naming the window, not a generic
    failure;
  - **generation errors:** HTTP 500, or a streamed `server_error` event, raise an error;
  - **timeouts:** the client's own timeout raises `LLMTimeoutError`, the locus the correction loop classifies (#568);
  - **seed:** sent when the caller supplies one. The replay's repeated generations need it, since TensorFold seeds from
    the prompt by default.
- **Model identity (§3.4, SIP-0073):**
  - Registry entries for the served model ids, or an `--alias` to the production name, with family `qwen3.8` and
    TensorFold's context window. Without the family, `model_family_of` returns `""`, and the approved lesson matches
    nothing.
  - The deploy record names the checkpoint by its revision where Ollama names a digest. The Atlas FP8 entry's
    `digest: null` today is the gap this closes.
- **The box's quiet-launch rule:** `list_loaded_models` reports the resident model truthfully, so §24an's check reads
  the TensorFold arm as it reads Ollama.
- **Auth:** an API key from the deploy's `.env`, by #2006's rule, with no literal in compose.
- **Deploy:**
  - `docker-compose.tensorfold.yml`, an overlay on the pattern of the vLLM and Atlas ones. The base compose file is
    untouched. A compose change needs the owner's OK (§8 Q3).
  - Arm switching goes through the existing arm script, with the exclusivity guard (#1177).

## 6. Sequencing

- **While the 2.2 window is open: nothing on the Spark.**
  - The window's manifest pins the engine and its deploy.
  - A second engine resident beside the campaigns' Ollama is §1.2c's trap.
  - Benchmarking would perturb the live campaigns' timing.
- **What can happen now, off the box:**
  - this draft;
  - the G0 harness, as a branch;
  - optionally, the owner runs TensorFold on the Mac (MLX), which records the API's shape but makes no speed claim
    (§8 Q5).
- **After the window closes and 2.2 is cut:** G0 and G1 together, in one box session, then G2 if both pass. Running
  them between the window's close and the cut would delay the cut. The cut's regression set and shakeout need the box on
  Ollama.
- **G3 and G4** follow G2, on the owner's word.

## 7. What this does not do

- It does not change the seam, add per-cycle engine routing (deleted, SIP-0106 §1.2d), or touch 2.2's window.
- It does not swap the dense 27B for a MoE model on decode speed alone. TensorFold's strongest numbers are for Flash
  Next. A model change is a separate decision with its own quality gate.
- It makes no claim from vendor figures. Every figure in §2 is the vendor's, and G0 replaces them with ours.
- It does not install anything by default. The `local-spark` profile stays Ollama-only until a cutover.

## 8. Questions for the owner

- **Q1: placement.** Recommended: G0–G2 on the 2.3 line, dark, with the even/odd waiver SIP-0106 §4.3 used. G3 and G4
  wait for evidence. The alternative is 2.4.
- **Q2: G0's bar.** Recommended: median wall-clock per call at most 0.75× Ollama's on our captured envelopes, at no
  worse a truncation rate. G1's bar is a pass rate at least Ollama's on the same envelopes.
- **Q3: the overlay.** Recommended: OK in principle to add `docker-compose.tensorfold.yml` at G2, as a new overlay.
  The base compose file stays untouched. Its exact contents come for review in that PR.
- **Q4: version policy. Ruled 2026-10-09:** TensorFold v0.6.6, the Python line that serves Qwen3.8-27B; no 1.0.x. Any
  later version change re-runs G0 and G1.
- **Q5: the Mac (optional).** If you want the API's shape recorded before the Spark is free, run TensorFold on the Mac
  with a Qwen3.8 MLX checkpoint, and I will turn its responses into the G2 fixtures. It answers nothing about speed on the
  Spark.
