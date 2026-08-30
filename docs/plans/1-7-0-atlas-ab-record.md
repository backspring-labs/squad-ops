# 1.7.0 — the Atlas A/B, record (#1160, SIP-0106 P5)

The artifact §4 of `1-7-0-atlas-ab-preregistration.md` commits to. It is not the shape that
section describes, and the reason is the result: **the set never opened to counting rolls.**
Arm B could not complete a shakeout, so there are no cycle rows to tabulate. What follows is
what the shakeout phase established, scored through the production validator, and the owner's
disposition.

**Outcome: Atlas is not adopted.** Ruled by the owner on 2026-08-29 on the evidence below.
Recorded as an amendment in SIP-0106 §1.2a, which is the permanent home; this file is the
measurement record behind it.

## 1. What was run

Three shakeout cycles and a 14-configuration replay matrix. No counted roll on either arm.

| # | Cycle | Date | Outcome |
|---|---|---|---|
| Shakeout 1 | `cyc_6e068cdd7de0` | 2026-08-28 | failed — Atlas `--request-timeout` default of 300 s cut generations, returned as a 200 with `finish_reason=timeout` |
| Shakeout 2 | `cyc_6db3a5d8d1ca` | 2026-08-28 | failed — content-loop guard severing YAML plans |
| Shakeout 3 | `cyc_cc5c58ff2cde` | 2026-08-29 | failed at `governance.merge_plan` after 8 manifest attempts across two rounds; recorded `blocked_unverified` |

Each failure produced a serve-line fix and the next shakeout. The third exhausted the
available controls, which is what turned the question from "tune it" into "can it do this at
all" and produced the replay matrix.

## 2. The replay matrix — the substantive result

One stored `merge_plan` prompt (9,244 prompt tokens), replayed byte-identically, each response
scored through `ImplementationPlan.from_yaml` — the handler's own gate, not a bare YAML parse.

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

**14 configurations · 44 plan emissions · 41 guard-stopped · 0 accepted.** All 41 stopped
*below* the completion cap — the budget was never the binding constraint on this arm.

**The mechanism.** The guard fires on legitimately repetitive YAML (consecutive
`- check: / file: / severity:` blocks, of which a 15-task plan carries fifty). The damage is not
the stop but the rollback-and-re-steer, capped at 2 per sequence, rewinding mid-token:
`depends_on: []` emerges as `depend0]`, `frontend_compiles` as `frontend_compil`. Those
corruptions *are* the validator's "while scanning a simple key" and "mapping values are not
allowed here".

**It cannot be disarmed.** Four documented controls are inert: the `--content-loop-watchdog
false` CLI flag (correct syntax per `--help`, startup line unchanged); the
`ATLAS_CONTENT_LOOP_WATCHDOG` env var (confirmed set on the container, behaviour unchanged); the
per-request `repetition_detection` object the help says "still outranks this", at `min_count:
64` against a default of 3; and `--content-loop-min-repeats 64`, the vendor's own documented
remedy for output that is "short-period repetitive (code, tables)". A second detector,
`simhash_semantic_loop`, has no CLI flag and no env var in `--help` at all.

Two rows carry their own caveat. **R10** used the vendor recipe verbatim including
`--max-batch-size 1` and `--gpu-memory-utilization 0.85`, which yields a 12,976-token KV pool on
this box; one 9,244-token prompt exhausts it, so two of three replays died on `KV cache
exhausted`. The recipe says of itself that 32K "is a gate value, not a recommendation" — it is a
qualification config, not a serving one. **R12/R14** forced the SSM decode-rollback ring back on,
the only knob that visibly changed engine state; it shifted the failure from corruption toward
clean truncation without changing the verdict.

## 3. Predictions

| # | Prediction | Result |
|---|---|---|
| P1 | arm B decode rate ≥ 2× arm A on `none` generations | **FALSIFIED, in reverse.** Arm A 28.8–29.2 tok/s on the framing prompt; arm B 12–14 tok/s. Both decode-only, from each engine's own reporting. The tuning matrix's 33.8 tok/s came from a short fill brief; #1160 had already recorded framing decode at 12–18 tok/s |
| P2 | paired cycle wall-clock B < A on every Next.js pair | **unanswerable** — no counted cycle on either arm |
| P3 | verdict parity, no arm-B rejection naming the runner | **unanswerable** — same |
| P4 | completion tokens per task type within ±20% between arms | **unanswerable** — same |
| P5 | every arm-B qa-fill generation carries `reasoning_tokens = 0` | **unanswerable** — same |
| P6 | FastAPI+React corrections consumed B ≤ A | **unanswerable** — same |

P2–P6 read from counted cycles. Arm B cannot clear `governance.merge_plan`, so it never reaches
build, so those cycles do not exist. This is a property of the result, not a gap in the
instrument.

## 4. The arm-A control

Run because a 0/44 on arm B means nothing without knowing what arm A does on the same prompt,
through the same validator.

**R0 — production budget as it stood (`num_predict: 8192`):**

| replay | thinking | plan | finish | verdict |
|---|---:|---:|---|---|
| 1 | 16,716 ch | 12,573 ch | `stop` | **ACCEPTED (5 tasks)** |
| 2 | 27,920 ch | 1,774 ch | `length` | rejected: missing `summary` |
| 3 | 22,474 ch | 7,406 ch | `length` | rejected: missing `summary` |

**1 of 3.** Both failures are budget exhaustion with no guard involved — the opposite of arm B's
failure, which is the guard, below the budget. That difference is why retries rescue arm A and
cannot rescue arm B: each arm-A attempt is an independent chance, so 8 attempts land a plan with
high probability, which is why 11 of 11 recorded Next.js cycles show `framing_rerolls: 0`. Arm
B's shakeout spent 8 attempts without one landing.

**R15 — the same control at the budget #1173 now computes (`num_predict: 14336`):**

| replay | eval tokens | plan | finish | verdict |
|---|---:|---:|---|---|
| 1 | 11,732 | 15,449 ch | `stop` | **ACCEPTED (7 tasks)** |
| 2 | 8,285 | 11,909 ch | `stop` | **ACCEPTED (7 tasks)** |
| 3 | 9,586 | 10,074 ch | `stop` | **ACCEPTED (4 tasks)** |
| 4 | 8,204 | 10,975 ch | `stop` | **ACCEPTED (6 tasks)** |
| 5 | 7,350 | 12,806 ch | `stop` | **ACCEPTED (8 tasks)** |

**5 of 5**, against 1 of 3 at the old flat clamp. The mechanism is the one #1173 names: the 8,192
cap truncated the document before `summary` could be emitted, and both R0 failures said exactly
that. One replay (11,732 tokens) genuinely needed room past the old cap; the rest finish well
below the new one, which is why the fix is nearly free.

**Cost per attempt barely moved.** Mean 305 s at 14,336 against 289 s at 8,192 — +5.5% — because
a *failed* attempt at 8,192 burned the full cap by definition, while a successful attempt at
14,336 averages 9,031 tokens. The budget is not buying longer generations; it is buying an end to
wasted ones.

**Wall-clock consequence, derived rather than measured.** At a 1-in-3 accept rate the handler's
retry loop expects 3 attempts to land a plan (3 × 289 s ≈ 14.5 min); at the observed rate it
expects 1 (≈ 5.1 min). Against framing runs that historically took 28.4–37.8 min against
implementation's 14.8–21.9, a ~9 min saving is a material share of cycle wall clock. This is
arithmetic from replay timings, **not** a measured cycle: `agent_task_log` holds zero rows and
#1172 meant `merge_plan` emitted no generation record, so the rest of framing's ~34 min cannot
currently be attributed. The fix-validation shakeout `cyc_74a6ad13d309` is the direct
measurement; n here is 8 replays, and it is the mechanism rather than the rate that carries the
claim.

## 5. Model support

`Qwen/Qwen3.8-27B-FP8` is not in the supported-model table of the shipped image's README, of the
GitHub README, or of the GB10 Deployment Guide. Support exists only as a recipe in
`atlas-recipes`, annotated "tested on binary main 680b3a568". The kernel audit cited in §2
precondition 3 (236 lookups / 0 unresolved) was run against the **NVFP4** checkpoint, not the FP8
one the A/B served. R11 closes that gap: on the NVFP4 weights, with the audited kernel set, the
outcome is identical. Unsupported-model status is therefore not an available explanation for the
result.

## 6. What the A/B produced anyway

Three engine-independent defects, all found because the A/B forced instrumentation that did not
previously exist, and all fixed in #1174:

- **#1171** — framing generations reached LangFuse costed at zero tokens
- **#1172** — `governance.merge_plan` emitted no generation record at all
- **#1173** — the completion budget ignored the reasoning level a capability declares, which is
  the whole of arm A's failure rate above

`--dump` (added by §1.3) is the only reason the guard behaviour was knowable at all, given #1171
and #1172. An A/B that returns a negative on its headline question and three production fixes on
the way is not a wasted set.

## 7. Incident

On 2026-08-29 the arm-A control was run directly against Ollama while the Atlas container still
held `--gpu-memory-utilization 0.90`. The Spark's 121 GiB is unified; both engines went resident;
the box entered swap thrash at 17:50:44 and was unreachable until a power cycle at ~19:25. Ollama
recorded the decision: `free="7.8 GiB"` against `need to reduce device memory by 28802 MiB`, and
it loaded anyway.

This is Appendix C.5 trap 1 of SIP-0106, realised. Filed as **#1177** (`arm.sh` enforces arm
exclusivity but the replay scripts bypass it; `atlas_serve_nvfp4.sh` raised utilization to 0.90
and dropped the reserve `atlas_serve.sh` warns about) and **#1178** (the box has no OOM
containment — no `systemd-oomd`, no earlyoom, no `MemoryMax=`). A preflight guard is now in
`replay_ollama.py`. No measurement in this record is affected: the incident followed the last
completed Atlas request at 16:55:59, and the only run it interrupted was R15, whose two timed-out
replays are discarded rather than reported.

## 8. Disposition

- **Atlas is not adopted.** SIP-0106 §1.2a records the amendment; the merged `AtlasAdapter`
  stays inert in the tree under the §4 dark-ship rule, so no revert is required.
- **vLLM becomes the second arm** (SIP-0106 §1.2b), activating P6 — written in §3.5a as the
  hedge for exactly this outcome. It needs its own pre-registration; this one does not transfer,
  because its fixed parameters and predictions are engine-specific.
- **The gating unknown for that work** is the one §3.5a already stated: vLLM on GB10 / ARM64 is
  unverified, and the SIP's instruction is to verify before scheduling. A feasibility probe
  precedes the new pre-registration.
- **A vendor report on `simhash_semantic_loop`** is worth filing regardless of adoption: a guard
  with no flag and no env var, firing on correct output, whose rollback corrupts the stream
  mid-token.
- **Everything else SIP-0106 built stands and is shipped** — provider selection as required
  configuration, declared capabilities, on-port model availability, provider-scoped model
  identity, and the conformance suite. The seam is what made rejecting the engine cheap.
