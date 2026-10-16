# 2.3.0 plan — a faster engine first, then the structure: TensorFold to a decision, and stabilization on the engine that ships

**Status: ADOPTED (2026-10-11); STARTED the same day, about 15:30 ET, after 2.2.1's cut** (the owner: "go ahead with 2.3, place #2234 in 2.3"). The owner ruled §6 at about 12:45 ET: "approve D1-D11 as recommended". SIP-0111 §9a is
ruled with it (D10). The 2.3 line starts after 2.2.1's cut, on D8's terms. Revision 2's history:
- **Drafted** while 2.2.1's diagnostic ran, at the owner's request: "I want to prioritize the TensorFold adapter to get
  shorter cycle times".
- **Revision 2** applies the nine changes from the owner's review of PR #2228 ("apply all nine and the SIP amendment").
  It proposes them to SIP-0111 as one amendment in the same PR (§9a). The amendment is ruled with this plan, before any
  measurement.
- **The owner's guidance on revision 2** (2026-10-11): "I'm ok with the numbers. Let's just be flexible as we see
  performance in making a decision without such hard lines drawn early."
  - So the numbers this plan proposes are **guides,** reported against, never automatic triggers. They are:
    - the selection margin;
    - the drift threshold;
    - G3's pass rule;
    - the box budget and its checkpoints.
  - **Each decision is the owner's,** on the evidence: which candidate, whether to re-run, whether to go on, whether to
    adopt.
  - **What stays fixed is the measurement:** the held-out set and its protection, frozen recipes, pairing, drift panels,
    clustered intervals, and reporting by seam and stack. That keeps the evidence honest whatever is decided.
  - SIP-0111's Q2 bars stand as the owner ruled them, and a reading near one goes to the owner.
- **It assumes 2.2.1 cuts as its plan says.** Nothing here starts before that cut.

**What 2.3 is.** An odd minor: a stabilization release, feature-free by rule (CLAUDE.md, #281). One track rides it under
a waiver the owner already granted: **SIP-0111's TensorFold trial**, dark, under SIP-0106 §4.3 (the owner's Q1,
2026-10-09). This plan puts that track first, and carries it to a cutover decision rather than stopping at the adapter.

**The question it answers:**

> **Can the squad run on a faster engine with no loss in the cycles it completes, and does the framework's structure
> hold through its largest refactors, measured on the engine 2.3 ships with?**

**Why the engine goes first, beyond speed.** An engine change is a listed-input change for every measurement after it
(SIP-0111 §1, its SIP-0110 overlap). So anything measured before the engine decision would be measured again after it:
- regression baselines;
- Outcome Evaluation's baselines;
- the next build-side memory experiment.

Deciding the engine first means 2.3 measures once. **The cut's regression set on the chosen engine is in scope** (§3,
phase 9). It is the new baseline if TensorFold is adopted.

---

## 1. What a faster engine could buy: projections, measured by G3

Squad work dispatches one task at a time, so a cycle's length is mostly single-stream decode (SIP-0111 §1). This table
reads every model call each agent logged in the 2.2 cut set's four counted rolls.

| roll | wall clock (min) | model calls | prompt tokens | generated tokens | decode (min) | share |
|---|---:|---:|---:|---:|---:|---:|
| React 1 `cyc_0009e2942a6c` | 50.5 | 16 | 162,028 | 75,858 | 46.1 | 91% |
| Next.js 1 `cyc_e2a1ad13af47` | 54.3 | 16 | 187,307 | 78,444 | 48.5 | 89% |
| React 2 `cyc_5fb4b1537245` | 52.0 | 16 | 163,140 | 76,704 | 47.6 | 92% |
| Next.js 2 `cyc_e7e0670e2681` | 62.1 | 19 | 230,260 | 91,055 | 54.7 | 88% |

**How it was read.**
- **The source:** each agent container's `LLM ... completed:` lines inside the roll's window in
  `var/verification_sets/2-2-0-cut-chain/chain.log`.
- **Decode** is `completion_tokens / t/s`. The adapter computes `t/s` as Ollama's `eval_count / eval_duration`
  (`adapters/llm/ollama.py:31-39`), so it is **decode alone**.
- **Each call** is listed with its container, timestamp and token counts in `docs/plans/2-3-0-roll-model-calls.tsv`
  (67 calls). A call's container and log timestamp are its identifier: the log line carries no call id.

**Decode is 88–92% of a roll.** Two parts of a call aren't in that figure:
- **The full request time:** prompt evaluation, load, and the handler around the call. Ollama's `prompt_eval_duration`
  isn't logged, so prefill is not measured here; the harness records it (§2.1).
- **What's left of the wall clock,** about 4–8 minutes a roll: prefill, tests, typed checks, assembly, dispatch and the
  gates. React roll 1's two `qa.test` tasks ran 3.0 and 6.1 minutes, of which the suites and checks took about 10
  seconds.

Reasoning is 54% of the generated text in React roll 1, and the emitted answers are the rest.

*Corrected in revision 1's second commit:* the first draft read only the captured authoring envelopes and put model
calls at 61–66%. Those envelopes miss five framing calls, so that figure was a floor.

**Fixed-output-volume projections.** These assume each candidate generates the same tokens per roll that the 27B on
Ollama does today:

| candidate | decode time vs today's (27.4 tok/s average) | saved per roll | roll |
|---|---|---|---|
| TensorFold, 27B, at G0's bar | 0.75× | ~12–14 min (~23%) | ~39–48 min |
| TensorFold, 27B, at the vendor's figures (50–58 tok/s) | ~0.47–0.55× | ~21–29 min (~45%) | ~27–35 min |
| TensorFold, Flash-Next MLX 4-bit, at the vendor's figures (63–77 tok/s) | ~0.36–0.43× | ~26–35 min (~55%) | ~23–30 min |
| TensorFold, Flash-Next EXL3 3.05 bpw | decode similar (59–81 tok/s); **prefill 930–970 tok/s**, under half the MLX checkpoint's 2,300–2,500 | **no forecast:** its slower prefill needs its own measurement | — |
| infinitely fast calls (the ceiling) | 0 | ~46–55 min | ~4–8 min |

**What these do not say:**
- **A model change can change the volume.** Its reasoning length, retries and correction rounds can rise or fall, so
  Flash-Next's row is the least reliable.
- **The vendor's figures are 64-token replies.** Ours average about 4,700 tokens, and this engine class has missed its
  vendor claims here twice (SIP-0111 §3).
- **Only G3 measures cycle savings** (§2.1).

**The gain arrives only at cutover, G4.** Until then SIP-0111 runs TensorFold dark. Adoption rests on end-to-end cycle
quality, latency, stability and recoverability, never on vendor tokens per second.

**Beyond the engine, the other levers are model time too.** Build and test speed is not among them: those take minutes,
not tens of minutes. The model-time levers are:
- **fewer reasoning tokens:** each task type's reasoning level;
- **fewer framing calls:** eight calls, about 31 minutes, before any code;
- **concurrent dispatch of independent tasks:** about 2–3 minutes a roll on TensorFold, and nothing on Ollama.

None is in this plan. Each changes what the squad emits.

---

## 2. The work

### 2.1 Track A, first: SIP-0111, one gate path per candidate

**Step 0, before any measurement: SIP-0111 §9a, ruled with this plan.** It holds every change below that the accepted
SIP doesn't already say:
- the self-contained harness;
- the repetitions, drift and uncertainty rules;
- the reuse and held-out rules;
- the second candidate;
- candidate-specific outcomes and the selection rule;
- G3's comparison.

**Two candidates, each on its own gate path.** A candidate that fails a gate is parked, with its record in SIP-0111.
That parks it alone, never every TensorFold candidate.

| gate | the 27B (`TensorFold/Qwen3.8-27B-MLX-4bit` and the other §2 checkpoints) | Flash-Next (D9) |
|---|---|---|
| S: switching, rollback and the exclusivity guard (#2199) | exercised once, on the benchmark deploy (§3) | its checkpoint inside S's floors (§2.2) |
| screening | none | #1408's plan-authoring replay, on prompts outside the held-out set (§5) |
| recipe | frozen on tuning data, SIP-0111 §4 | **its own matrix and frozen recipe** (§2.2), on tuning data |
| G0, throughput | the held-out set, the owner's bar (≤ 0.75× Ollama's median paired wall-clock, no worse truncation) | the same set and bar |
| G1, emission validity | the held-out set, each task type's production validator, ≥ Ollama overall and per seam | the same |
| selection | the pre-declared rule, below | |
| G2, the adapter, dark | **only the selected candidate,** built only after its G0 and G1 pass. Its parity and conformance are read against the harness's recorded fixtures, and every adapter's unsupported-control tests | |
| G3, cycles | **the selected candidate, on both stacks** | |
| G4 | the owner's decision, on G3's evidence (D4) | |

**What G1 shows, and what it doesn't.** G1 shows that each emission parses and passes its task type's own validator.
That is emission validity. It says nothing of reasoning quality, or of whether the delivered app is correct. **Adoption
rests on G3** (completed cycles) and the owner's G4, never on G1 alone.

**The selection guide, written before either candidate's held-out run.** When both candidates pass G0 and G1, the
evidence is reported against it, and **the owner selects:**
- **The guide prefers the 27B,** unless Flash-Next is better on all three counts:
  - its median paired ratio is at least **0.15 lower** than the 27B's;
  - its G1 pass rate is **at least the 27B's on every seam**;
  - its truncation and runaway-reasoning rates are **no higher**.
- **The reason:** a model change resets every baseline, and carries risks G1 can't see. It has to buy clearly more speed.
- **When only one passes,** that one is selected. **When neither passes,** the trial is parked, and 2.3 continues on
  Ollama.

**If the selected candidate fails G2 or G3,** it is parked. If the other candidate passed G0 and G1, the owner may
select it at that check-in (§4). It then needs **its own G2 and its own G3**: no evidence transfers between candidates
after G3.

**G3's comparison.** It is pre-registered before its first roll, and amends SIP-0111 §4's "judged on cycle wall-clock".
It runs the selected candidate against Ollama, as uncounted regression pairs on both stacks, interleaved A, B, A, B, one
engine resident at a time. It reads, for each arm:
- **cycle wall-clock** and **task completion time** by task type;
- **emission retries,** **correction rounds,** and the **final verdict** with criteria verified and the boot audit;
- the decode and prefill rates the instrumented deploy logs.

**Its guide** (written in G3's pre-registration, and read by the owner at G4):
- every candidate roll accepted, with its boot audit passing;
- correction rounds within the stack's baseline range;
- the candidate's median cycle wall-clock below Ollama's;
- no task type's median completion time worse than Ollama's by more than 10%.

**The harness, before G2, without the port's amendments** (§9a).
- **It is self-contained.** It calls each engine's own API:
  - Ollama's `/api/chat`, with `options.seed`, the envelope's captured options and `think`;
  - TensorFold's `/v1/chat/completions`, with `seed`, `reasoning_effort` and `thinking_budget` as its own documented
    request fields, and `stream_options.include_usage`.
- **It normalizes how each call ended** itself: `finish_reason` or `done_reason`, the cap, a context overflow (HTTP 400
  `context_length_exceeded`), and the deadline.
- **It records everything:**
  - each raw request and response;
  - every stream event;
  - prompt and decode durations: Ollama's `prompt_eval_duration` and `eval_duration`, and TensorFold's timings and
    `cached_tokens`.
- **No `LLMPort` change lands before G2.** The recorded payloads and normalized outcomes become **G2's parity fixtures:**
  the adapter, given the same envelope and seed, must send the same request and normalize the same response the same
  way.

### 2.2 Flash-Next: its own recipe, matrix and identity (D9)

Flash-Next is a model change, not only an engine change. SIP-0111 §7 excludes it until §9a amends it. **Nothing about the
27B carries over:** not its three-checkpoint matrix, not its reasoning mapping, not its registry identity.

**What TensorFold's v0.6.6 recipe states** ([its Flash-Next recipe](https://github.com/ashhart/TensorFold/blob/v0.6.6/docs/recipes/qwen3.8-flash-next.md), read 2026-10-11):
- The model is the `qwen4_exp` family: Gated DeltaNet, sparse attention, a mixture of experts, hyper-connections and
  hashed n-gram embeddings, with an MTP head used for drafting.
- **Sizes are by checkpoint.** The MLX 4-bit checkpoint is 105.4 GiB, of which:
  - about 29.8 GiB is n-gram tables, kept as host file mappings;
  - 70.3 GiB is routed experts.

  On a Spark its weights take 81 GB of GPU memory, with a default window of about 74,000 tokens.
- **The EXL3 3.05 bpw pack:** 52 GB of weights and the full 262,144-token window, with a 32.6 GB n-gram table in the page
  cache.
- **Parameter counts:** the recipe gives none. The pre-registration cites the model card for the core model, the n-gram
  tables and the MTP head separately. The earlier "about 93B total parameters" came secondhand from #1408's community
  NVFP4 recipe, and is withdrawn.

**Eligible checkpoints,** each pinned by revision in the pre-registration:

| checkpoint | revision | weights | prefill (2k–64k, vendor) | decode (64-token, vendor) | memory on a Spark |
|---|---|---|---|---|---|
| `TensorFold/Qwen3.8-Flash-Next-MLX-4bit-MTP` | pinned at pre-registration | MLX affine 4-bit, groups of 32 | 2,300–2,500 tok/s | 62.7–76.5 tok/s sampled | 81 GB weights, ~74k window, plus the 29.8 GiB tables |
| `turboderp/Qwen3.8-Flash-Next-exl3` | branch `3.05bpw_h5_ng5`, pinned | EXL3 3.05 bpw | 930–970 tok/s | 59.4–80.8 tok/s sampled | 52 GB weights, full window, plus the 32.6 GB table |
| `local-inference-lab/Qwen3.8-Flash-Next-NVFP4` | `7c4f1bc1` | NVFP4 experts, MXFP8 elsewhere | 0.94–1.03× of its FP8 prompt path; not separately timed | 59.2 code / 36.6 chat, greedy | not stated in the recipe; read in S |

**Each checkpoint's speed and memory forecast belongs to that checkpoint.** The EXL3 pack's slower prefill means it
inherits nothing from the MLX row.

**The recipe's fixed parts, recorded and frozen with the recipe:**
- **The tokenizer and chat template:** the checkpoint's own, by revision and hash.
- **Reasoning controls:** `qwen4_exp`'s template mapping of `reasoning_effort` and `enable_thinking`, read from the
  template. It is never assumed to be the 27B's mapping. The pre-registration records which level each corpus setting
  (`none`, `low`, `medium`, `high`) is heard as.
- **The output allowance:** each envelope's own `max_tokens` (12,288 on most), unchanged. A thinking budget is a matrix
  dimension.
- **Drafting:**
  - the MTP draft cap (CUDA default 6) and `--mtp-confidence` (default 0.70);
  - the drafted-against-serial check (`"draft": false`) before any speed result counts.
- **The context window:** set explicitly. It must be at least the corpus's largest prompt plus its `max_tokens`, about
  25k plus 12,288; inside the MLX checkpoint's ~74k. The KV dtype stays bf16 (int8 and int4 change outputs).
- **Registry identity:** a TensorFold model id of its own, with a **model family of its own**, never `qwen3.8`. No
  lesson's tested applicability carries over to it.

**Its matrix, on its tuning envelopes only:**
- the checkpoints S admits;
- drafting at the default and at a lower cap;
- each reasoning mapping in use;
- with and without a thinking budget.

The pre-registration states the matrix, and one recipe is frozen before its held-out run.

### 2.3 Track B: stabilization, on the engine Track A leaves

Each item is a framework fix, an output-quality change, an instrument or an evaluator change. Every item has a slot in
§3.

| item | what | kind | size | slot (§3) |
|---|---|---|---|---|
| **#2204a** | host and GPU exporters, `GET /health/host`, the agent inference metrics (decode rate, TTFT, prefill, tokens per increment) | instrument | M | phase 1: the benchmark deploy |
| **#2204b** | the console's Host panel and the Grafana dashboard | instrument (presentation) | M | phase 8, any slot: no engine dependency |
| #2201 | CI's Docker Hub rate limit | framework | S | phase 1 |
| #2206 | a cross-role repair's file labelled as the failed task's | framework (evidence) | M | phase 8, R3 |
| #2210 | a revocation names finished units as holding the lesson | framework (display) | S | phase 8, R3 |
| **#2231** (placed by the owner, 2026-10-11) | `max_proposal_run_retries` is never read: failed proposal runs are retried by new cycles until `max_cycles`, and SIP-0109 §9.5's in-cycle retry isn't built | framework (campaign) | S–M | phase 8, R3. **Its two questions are ruled first:** build §9.5's retry or retire the field, and whether consecutive failed proposal runs pause the campaign |
| #2174, #2175, #2176 | SIP-0110's entry-point prerequisites | framework | M each | phase 8, R3 |
| **#2202** | a manifest decision the build doesn't honour passes acceptance | **output quality** | M | phase 8, its own slot: a targeted pre-registration and before/after evidence on the chosen engine |
| **#2205** | a manifest delta's undefined key dropped, so a footprint omits the file the criteria need | **output quality** | S–M | phase 8, its own slot, as #2202 |
| **#2208** | the `criterion_already_satisfied` rubric @3 | **evaluator change** | S | phase 8. Its new version is pinned in every later measurement, and @2 is kept for the historical results scored with it |
| the tier's timeout half, live | a diagnostic-only fault that makes an increment's plan ask a question, then two campaigns (the owner approved #2296's pre-registration, 2026-10-14) | framework | S code, ~3 h box | phase 8, R3's deploy |
| #1976, #1977 | API contract residue; comms hardening | framework | M, M–L | phase 8, R4 |
| **#2062** | hoist the 606 deferred imports #1985 left | framework (refactor) | M | phase 8, **R5, before or alongside #1993** (the 2.2 plan's D6). **It stays in 2.3 when #1992 and #1994 are deferred** |
| #1993 | a `stacks` package | framework (refactor) | M | phase 8, R5 |
| #1992 | orchestration out of `adapters/cycles` (~12,000 lines) | framework (refactor) | L | phase 8, R6; deferrable (§4) |
| #1994 | the largest units split | framework (refactor) | L | phase 8, R7; deferrable (§4) |
| #316 | the request-profile taxonomy | framework | L | phase 8, R8. **Its SIP is accepted first** (Q13: pinned definitions keep resolving old names) |
| Outcome Evaluation's reporting-only instruments | the yardstick for output-quality work after 2.3 | instrument | M–L | phase 8, R9. **Its SIP is accepted first** (PR #1963) |
| **#2234** (placed by the owner, 2026-10-11) | the release capture: the delivered-app capture can't seed an app with an empty API base path, and the Prefect capture hangs on a failed flow run | framework (release tooling) | S | phase 8, any slot; before the 2.3 cut captures its package |
| **#2315** (placed by the owner, 2026-10-14) | a rejected increment whose only unmet criteria the accepted application already meets was sent to a repair that cannot change them, and the next proposal wasn't told which (found by #2205's comparison) | framework (campaign) | S | phase 8, with R4. SIP-0109 §24bq |

### 2.4 Not in 2.3

Only later experiments are deferred. The new baseline the 2.3 cut needs on the chosen engine is in scope (§3, phase 9).
- **The next build-side memory experiment** (SIP-0110 §5h): broad multi-increment campaigns with memory on, on the final
  engine. Recommended for 2.4, beside Outcome Evaluation's scenarios (D6).
- **The other model-time levers** (§1): reasoning levels, fewer framing calls, concurrent dispatch.
- **#2177–#2183** (the entry points' feature half, 2.4) and **#2184** (2.5), as SIP-0110's ledger places them.

---

## 3. Sequencing: the box is the constraint

One box runs everything: measurements, rebuilds, regression pairs and campaigns. Code proceeds on branches while it's
held. **No adapter code is written for either candidate before that candidate's G0 and G1 pass.**

| phase | what | box |
|---|---|---|
| 0 | 2.2.1 cuts. The owner rules this plan and SIP-0111 §9a | — |
| 1 | **The benchmark deploy:** #2204a and #2201 merged, a rebuild (R1), a regression pair, every loaded check answering. **This instrumented deploy is frozen** for both candidates' benchmark arms, and its deploy id is recorded in each pre-registration. A rebuild before the last benchmark call voids the affected arms (§5) | rebuild and pair, ~2 h |
| 2 | **S,** built and exercised on the benchmark deploy (#2199's acceptance list) | ~1–2 h |
| 3 | **The harness and the pre-registrations:** the 27B's, and Flash-Next's screening and recipe matrix. The selection rule is in both | — |
| 4 | **The 27B:** tuning, the frozen recipe, the drift panel, the held-out run, the drift panel again, and drafted-against-serial. **Checkpoint A** (§4). **Done:** the held-out run took 13.7 h (2026-10-12 10:19 to 10-13 00:01 ET). G0 passed at 0.438 of Ollama's wall-clock; G1 passed by the owner's ruling at checkpoint A, with plan writing one answer under Ollama's (SIP-0111 §9e) | §4 |
| 5 | **Flash-Next: moved to 2.4** by the owner on 2026-10-12 ("skip to next release"), before checkpoint A. It is recorded as not measured in 2.3. Its exploratory tuning results are on #2199: 0.37 of Ollama's wall-clock against the best 27B's 0.40, short of the 0.15 selection margin. Its gate path, when it runs, is unchanged: S's floors with its checkpoint, the screening replay, tuning, its frozen recipe, then its held-out arm (reusing Ollama's arm only under §5's rules) | — |
| 6 | **Selection** (§2.1), then **G2** for the selected candidate: the adapter, the port's four amendments, registry entries, the overlay, the conformance suite across every adapter, and parity against the harness fixtures. Then a rebuild. **Checkpoint B** **Done 2026-10-13:** the 27B is the only candidate; G2 merged as #2268, #2269 and #2270, deployed (`dep_268949794186`), and its live tier passed: the switch to TensorFold and back in 27 s and 48 s, with the clients | rebuild |
| 7 | **G3** on both stacks, then **G4,** the owner's decision. On adoption, cutover by S; from here every measurement is on TensorFold. **Done 2026-10-13:** G3's record (#2282); the owner adopted TensorFold at G4, with the seed fix first (#2283, SIP-0111 §9j); the Spark serves on TensorFold from 20:01 ET, and the cutover pair passed (#2285, §9k) | ~8 h |
| 8 | **Track B's merges on the chosen engine,** each rebuild with a regression pair (listed below) | ~2 h each |
| 9 | **The cut:** a pre-registered regression set on both stacks on the chosen engine (the new baseline if TensorFold was adopted), a campaign shakeout, the release procedure | as 2.2's |

Phase 8's rebuilds, in order:
- **R3:** #2206, #2210, #2231 (once its questions are ruled), #2174–#2176, with a regression pair. Then the timeout-half diagnostic on R3's deploy: the fault
  is a diagnostic-only code path merged in R3, and two campaigns follow: the late answer can only be read by a later
  campaign (#2296, approved by the owner 2026-10-14). **The rebuild and its pair: done 2026-10-14.**
  #2243, #2242, #2245, #2246, #2247 and #2257 merged (closing #2206, #2210, #2231, #2174, #2175, #2176) and deployed as
  `dep_8f91bad18697` from `e30ec9cb`; both cycles of the pair were accepted on TensorFold with no new seam finding. The
  diagnostic's pre-registration is #2296. **The diagnostic: done 2026-10-14.** Every reading held on `dep_c627c2873c3c`,
  after three defects it found were fixed (#2293, #2302, #2304); the readings are on #2279.
- **#2202, then #2205:** each with its own pre-registered before/after comparison on the chosen engine (a targeted set,
  or one campaign), before it is batched with anything else. **#2202's comparison: done 2026-10-14.** #2276 merged
  between its arms, and #2309 before the after arm's re-run (its pre-registration's §9). Every reading reached held,
  and the proposer's wasn't exercised; the readings are on #2202. It found #2308 (fixed by #2309) and #2310.
  **#2205's comparison: done 2026-10-14.** #2275 merged between its arms. The before arm's proposer asked for no
  exact wording, so the defect wasn't exercised there. In the after arm both proposals declared the wording on the
  error codes, and every reading held: the footprint held the frozen error module, the contract asserted the wording,
  and the build returned it word for word. The readings are on #2205. It found #2315.
- **#2208,** its rubric version pinned. **Done 2026-10-14.** @3 merged as #2274 on 2026-10-13. #2313 pins each
  version by its text: an authoring replay's manifest records the named version's hash, a version the repository
  doesn't hold is refused, and @2's text is kept verbatim (`criterion_already_satisfied@2.md`) for the results
  scored with it.
- **R4:** #1976 and #1977, with #2315 (placed by the owner, 2026-10-14). **The rebuild and its pair: done
  2026-10-15.** #2317, #2319, #2320, #2321, #2323 and #2324 merged (closing #1976, #1977 and #2315) and deployed
  as `dep_fd13cc434ac7` from `8f98c070`. Both cycles of the pair were accepted on TensorFold, with the boot audit
  passing and no intervention (`cyc_6178d14156b8`, `cyc_18f12f4be0e3`), and every tracked loaded check answered,
  R4's seven among them. No new seam finding.
- **R5:** #2062 with #1993. **The rebuild and its pairs: done 2026-10-15.** #2325 and #2326 merged (closing #1993
  and #2062) and deployed as `dep_2c758b8ae9a1` from `c255017a`, with every tracked loaded check answering, R5's four
  among them.
  - **The first pair found a defect in R4's code** (#2333). The agent's delivery record (#2324) was keyed by the
    task id alone. So when the runtime sent a task again under its own id, for a retry or for the re-run after a
    failed patch retest, the agent took the send for a duplicate and never ran or answered it. The React cycle
    (`cyc_8bf1b636acf9`) waited out its per-task wait three times and was rejected, 20 of 21. The Next.js cycle
    (`cyc_682692645b2a`) was accepted.
  - **#2334 fixed it:** the record is kept per send (SIP-Agent-Comms-Delivery-Guarantees §5.3c, ruled by the
    owner). It was deployed as `dep_5fedb4ac415c` from `7cc1990d`.
  - **The second pair, on that deploy:** every tracked loaded check answered, R5's four and #2334's two among them.
    - **React** (`cyc_df5860e79d36`) was accepted 21/21 on TensorFold, with the boot audit passing and no
      intervention.
    - **Next.js** (`cyc_8174805a98ca`) was rejected, 11/16. The developer's route stored a run without an `id`.
      The repair added it and cleared six of seven failures, but #1522's rule discarded it: the probe it half-fixed
      now failed for a different reason, the list's order, and the rule read that as a failure the repair added
      (#2340). The re-send #2334 fixed ran live here and was answered in about two minutes. #2341 is the retest's
      log line, which hid the failed probe.
  - **The owner counted the second pair as R5's exit (2026-10-15):** neither finding is in R5's changes. #2340
    (option (a): a probe still failing for a new reason, with nothing new failing, is progress) and #2341 ship in
    their own rebuild after R6's pair.
- **R6:** #1992 (deferrable). **The rebuild and its pair: done 2026-10-15.** #2327 merged (closing #1992): the
  cycle orchestration moves to the top-level `squadops.execution` (the owner's ruling, SIP-0097 §14). It was deployed
  as `dep_59af9bbbc3dd` from `8cc3f8b3`. Both cycles of the pair were accepted on TensorFold, with the boot audit
  passing and no intervention (`cyc_73198e1cc055` 20/20, `cyc_90af2aa1c71c` 16/16). Every tracked loaded check
  answered, R6's own among them. No new seam finding.
- **R6's fixes:** #2343, closing #2340 and #2341 (found by R5's second pair; placed by the owner in their own
  rebuild after R6's pair). **The rebuild and its pair: done 2026-10-15.** It was deployed as `dep_d3dced7c5c9e`
  from `de811cf2`. Both cycles of the pair were accepted on TensorFold, with the boot audit passing and no
  intervention (`cyc_e8b065df3e58` 17/17; `cyc_9b99b2cd1e53` 17/17 after one correction round, whose repair passed
  its retest). Every tracked loaded check answered, #2343's two among them. No retest failed, so the probe rule
  (#2340) wasn't exercised live; its tests enter at the executor's acceptance entry. No new seam finding.
- **R7:** #1994 (deferrable). Its map, `docs/plans/2-3-0-r7-extraction-map.md`: the owner approved
  unit 1's step table on 2026-10-15, and reviews each later unit's before its first extraction PR.
  - **The qa handler breakup (unit 1): its rebuild and pair, done 2026-10-15.** #2330 and #2331 merged: the qa
    handler's 481-line `handle` runs as eight named steps, moved and not changed. It was deployed as
    `dep_c8161efff2a5` from `125c9db6`. Both cycles of the pair were accepted on TensorFold, with the boot audit
    passing and no intervention (`cyc_213693497a97` 22/22 after three correction rounds, `cyc_1e3c7dfac55b` 18/18
    after one). Every tracked loaded check answered, its own (`1994-qa-agent`, "True 8 True") among them. No new
    seam finding.
  - **The handler base class split (unit 2): its rebuild and pair, done 2026-10-15.** #2336–#2339 merged (#2339
    closing #2335): the base class every agent's task code inherits keeps its acceptance decisions beside the
    evaluator, its envelope capture and contentless marker are their own steps, and its generic `handle` uses the
    shared helpers, moved and not changed. It was deployed as `dep_391013504581` from `012208ee`. Both cycles of
    the pair were accepted on TensorFold, with the boot audit passing and no intervention (`cyc_98dd068cbb18`
    21/21 with no correction round, `cyc_a65a98824c7f` 20/20 after one). All 106 tracked loaded checks answered
    as expected, its own (`1994-handler-base`, "True True True") among them. No new seam finding.
- **R8:** #316, once its SIP is accepted.
- **R9:** Outcome Evaluation's instruments, once their SIP is accepted.
- **#2204b** at any of them.

On branches during phases 4–7: Track B's code, and the two SIP design reviews (#316's, Outcome Evaluation's).

**The cut's criteria:**
- **Track A:** G4 decided (adopted, or parked with its record), with each candidate's gate evidence in SIP-0111.
- **Track B:** each item merged with its evidence, deferred under §4's rule, or re-placed by the owner. Substance gates
  the cut, not the clock.
- **The regression set** passes under its own pre-registration.

---

## 4. Box-time budget, checkpoints and the deferral rule

**Track A's planning budget: about 80 box-hours,** from S's first exercise to the G4 decision. It is a guide for
planning the box, not a cut-off. It counts:
- engine switches, at about 10 minutes each, warm-up included;
- the drafted-against-serial checks;
- the drift panels;
- every failed call, at its deadline (an allowance of 10% on each arm).

| block | estimate |
|---|---|
| S's exercise | ~1–2 h |
| **The 27B** (lean protocol, D2): tuning (3 checkpoints at production's thinking settings) ~5 h; Ollama arm, 2 generations ~14.6 h; TensorFold arm ~7–11 h; two drift panels on each arm ~3 h; drafted-against-serial ~0.5 h; ~6 switches ~1 h; failed-call allowance ~2.5 h | **~34–38 h** |
| **Flash-Next** (if checkpoint A allows): S's floors and screening ~2 h; tuning ~4 h; its arm ~5–7 h; drift panels ~1.5 h; switches ~1 h; allowance ~1 h | **~14–17 h,** plus **~17 h** if Ollama's arm can't be reused |
| G3, the selected candidate | **~8 h** |
| A repeated gate (a recipe change re-runs G0 and G1) | ~20–25 h each |

**Checkpoint A,** after the 27B's G0 and G1 are read: the owner's check-in. The supervisor reports the time used, the
27B's readings, and the estimate for Flash-Next and G3. **The owner decides** whether Flash-Next runs now, waits for
2.4 (as "not measured," never as a negative), or the trial changes course.
- **Held 2026-10-13.** Flash-Next had already moved to 2.4, so the 27B is the only candidate and selection (phase 6)
  is the 27B. Told the readings, the owner ruled the one-answer plan-writing miss does not fail G1, with no re-run
  ("1, does not fail vailidity, let's go with TensorFold. 2, no re-run"). G2 starts on the 27B's frozen recipe
  (#2200).

**Checkpoint B,** after selection: the same check-in before G3.

**Track B's deferral guide,** read at checkpoint B. If phase 8's remaining rebuilds look longer than about a calendar
week of box time, **#1992 and #1994 are the ones to move to 2.5.** The owner decides. **#2062 and #1993 stay in
2.3.**

---

## 5. G0 / G1's statistics, drift, reuse and the held-out set

**What is reported:**
- unique held-out envelopes, and the **source cycles** they came from;
- repetitions per envelope, and the denominator of every rate;
- everything **by seam and by stack.**

The corpus on 2026-10-11 has 129 held-out envelopes: 87 React and 42 Next.js. Some strata are small: Next.js repair
has 2, and React's `qa.test_repair` 0.

**The thresholds are unchanged** (the owner's Q2):
- G0: the median paired ratio is at most 0.75, at no worse a truncation rate;
- G1: the pass rate is at least Ollama's, overall and per seam.

**What the reports add:**
- **Paired uncertainty, clustered by envelope.** Repetitions of one envelope are not independent evidence, so intervals
  are bootstrapped over envelopes (resampling envelopes, each with all its repetitions). That is reported beside the
  point estimate.
- **An observed pass is not evidence of general non-regression.** A threshold met by the point estimate is reported as an
  **observed pass on this corpus.** It is evidence of non-regression only where the clustered interval's unfavourable
  bound also meets the threshold. A seam or stratum too small to bound is named as unbounded, not passed.

**Drift: a fixed panel of identical calls.**
- **The panel:** about 16 envelope-and-seed pairs, two per seam and stack where the stratum allows, drawn from the
  held-out set before any call.
- **When it runs:** on each arm, at the start and at the end of that arm's held-out run. The calls are identical:
  prompt, settings, seed and deadline.
- **What shows drift:**
  - **identity:** a seeded call repeats its output, so the token-id hashes should match;
  - **speed:** the median wall-clock change across the panel, start against end.
- **The guide:** at least 15 of 16 identical, and a median wall-clock change within 10%.
- **If it's exceeded,** the arm's results are flagged, the cause is read, and the owner decides whether the run is
  re-run or read as it stands.
- **Different-seed blocks alone can't separate engine drift from generation variability,** so they are not used for
  drift.

**Reusing Ollama's arm across candidates.** It is reused only if all of these are unchanged since it ran:
- the deploy (by deploy id);
- the model digest;
- prompts, seeds and sampling;
- deadlines;
- cache treatment (each call's prefix-cache state recorded, primary timing on calls without a hit);
- each validator's revision.

It also needs the drift panel to pass on Ollama again at reuse time. Otherwise the Ollama arm is re-run beside the new
candidate.

**Protecting the held-out set:**
- **Each recipe is frozen on tuning data** before any of its held-out calls is read.
- **Flash-Next's screening prompts** come from tuning envelopes, or from envelopes captured after the split. They are
  never held-out ones.
- **The selection guide** (§2.1) is written in both pre-registrations, before either candidate's held-out run, so the
  evidence is read against a line drawn before it was seen. The owner's choice may depart from it, with the reason
  recorded.
- **Exploratory after a look.** A recipe adjusted after a held-out failure is read becomes exploratory. Confirming it
  needs **fresh cases:** envelopes captured from cycles run after the freeze, which every new cycle adds. They are run as
  a new held-out set under the same rules. Small strata grow slowly, so that can take more than one release.

---

## 6. Decisions for the owner

**Ruled 2026-10-11: D1–D11 as recommended** (the owner: "approve D1-D11 as recommended").

| # | decision | recommendation |
|---|---|---|
| D1 | **the order** | **Track A first** (§3), Track B on branches meanwhile, and Track B's merges after G4, so 2.3 measures on one engine |
| D2 | **G0 / G1's size** | **lean:** 2 generations per arm, the drift panel (§5), and the 3 checkpoints at production's thinking settings. About 34–38 h for the 27B. *As accepted:* about 55–60 h. *Leanest* (1 generation): about 22–25 h, with wider intervals. **Ruled 2026-10-12: leanest, 1 generation** (the owner: "once per prompt"; SIP-0111 §9d) |
| D3 | **G3, placed** | **in 2.3,** for the selected candidate, with its pre-registered comparison (§2.1). Tracked as #2229 |
| D4 | **G4, the cutover decision** | **in 2.3, the owner's, on G3's evidence, before the cut set**, so the cut measures the engine 2.3 ships with. Cutover in an odd minor extends Q1's waiver from "dark" to "adopted", and that extension is the owner's to grant. If it isn't granted, G4 moves to 2.4's start, and 2.3's cut runs on Ollama |
| D5 | **the structure batch** | **#2062 with #1993 in 2.3** (R5). **#1992 and #1994 in 2.3 unless §4's deferral rule moves them to 2.5** |
| D6 | **the next build-side memory experiment** | **2.4,** beside Outcome Evaluation's scenarios, on the final engine |
| D7 | **#2201's fix** | registry credentials in CI (a repository secret), or a pull-through mirror. Recommended: **credentials**. **Changed by the owner on 2026-10-11 to the mirror** ("do 2"): Google's `mirror.gcr.io`, needing no account or secret |
| D8 | **who runs the line** | **the supervisor, on the 2.2 line's terms:** build in §3's order, merge on green with main's run read, run rebuilds and uncounted runs. **The owner's:** compose changes beyond #2204a's services and SIP-0111's overlay; G4; any lesson approval; the tag and Release unless delegated at the cut |
| D9 | **Qwen3.8-Flash-Next on TensorFold, a second candidate** (the owner's request, 2026-10-11; tracked as #2230) | **on its own gate path** (§2.1, §2.2), behind S's floors and a screening replay, with its own frozen recipe and registry family. The owner selects between candidates on the evidence, against the written guide, and decides at checkpoint A when it runs. **Ruled 2026-10-12, before checkpoint A:** moved to 2.4 (§3 item 5) |
| D10 | **SIP-0111 §9a** | **ruled with this plan, before any measurement:** the self-contained harness, the statistics and drift rules, the reuse and held-out rules, the second candidate, candidate-specific outcomes, the selection rule, and G3's comparison |
| D11 | **Track A's budget** | **about 80 box-hours as a planning guide,** with checkpoints A and B as the owner's check-ins (§4). **The numbers are accepted as guides** (the owner, 2026-10-11) |

---

## 7. What this plan does not decide

- **G4 itself.** D4 places the decision; it doesn't make it.
- **The cut's numbers:** the regression set's size and the shakeout's exit rule, written as a pre-registration when the
  last batch is built. G3's pass rule is fixed in G3's own pre-registration.
- **#316's and Outcome Evaluation's designs.** Each needs its SIP accepted, at its own design review.
- **Anything compose beyond #2204a's services and SIP-0111's overlay.**
