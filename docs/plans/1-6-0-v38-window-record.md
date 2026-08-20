# V38 Model-Comparison Window — Record

**Pre-registration:** `1-6-0-v38-model-comparison-preregistration.md` (in force at the §3
freeze, `5d66f80f`). **Arm A:** V7 (amended 4/6, `1-6-0-v7-fay-window-record.md`). **Arm B:**
six counted rolls on `full-38` (qwen3.8:27b, Ollama 0.32.14) recorded here. No pass/fail
bar; texture is the instrument. This file lives on a branch until the window closes (§6).

## Shakedown — NON-COUNTING (declared per §2.6 before launch)

Bar: the cycle reaches a verdict without a NEW harness-attributable mechanical failure.
Watching for the model-swap failure surface: structured-output compliance, fence discipline,
thinking behavior (#998 class), emission shape under the 0.32 thinking routing.

| Field | Value |
|---|---|
| Cycle | `cyc_cc83a907f09e` (run `run_0a037698a5c5`), launched 2026-08-20, config hash matches pin |

### Shakedown #1 outcome (cyc_cc83a907f09e, deploy 5d66f80f) — findings, both fixed

Framing 34 min (vs 54–73 on 3.6); implementation failed in 17 min. Findings: (1) squad-output
texture — dev named-imported next/link's default export, repeated across 3 self-eval rounds;
(2) **harness×model**: analyze_failure emitted a mid-object-truncated JSON once (703 tokens,
uncapped, 0-for-3 reproducible), parser rejected loudly, correction ran decisionless, run
collapsed; (3) **harness**: qwen3.8:27b had no model-registry entry → completion clamp never
fired → arm B ran at capability ceilings (12,000) arm A never had, an undeclared inter-arm
delta. Owner ruled fix-refreeze-shakedown-open; #1008 merged (registry clamp parity 8,192 +
one bounded JSON re-ask across the three JSON impl handlers); §3 re-frozen at `f7a5e0a2`.
In-cycle throughput on 3.8: 22.6–34.4 t/s (vs 10.5–10.9 on 3.6).

## Shakedown #2 — NON-COUNTING (declared per §2.6 before launch)

Same bar: reach a verdict with no NEW harness-attributable mechanical failure. Additionally
watching: recurrence of the truncation (now survivable via re-ask — a fired re-ask is a
logged observation, not a failure) and the clamp taking effect.

| Field | Value |
|---|---|
| Cycle | `cyc_bc85a4b81808` (run `run_59b59cf49f05`), launched 2026-08-20, hash matches pin |

### Shakedown #2 outcome — BAR MET; declaration; WINDOW OPENS

Framing 32 min (gate: one question → §7.3(c) verbatim, agent decision); implementation
failed 19:02 UTC, "Max correction attempts (3) exhausted," `rejected`.

**The bar was "reach a verdict with no NEW harness-attributable mechanical failure" — MET:**

- No truncation recurrence; the #1008 re-ask never needed to fire; every analyzer/decision
  parse succeeded.
- The clamp held on capability tasks (eve capped at exactly 8,192).
- The machinery cycled correctly through a builder failure → builder repair, and qa failures
  → dev-routed corrections (locus correct: the probes said the APP was wrong).
- Every failure was **app-semantic, squad output**: duplicate join accepted (200 ≠ 409),
  leave broken (404 ≠ 200) — which is the quantity the window MEASURES, not a precondition.

**Declared under §2.6 (not fixed):** repair handlers bypass the per-model completion clamp
(a dev repair emitted 12,314 tokens) — pre-existing and **symmetric across both arms** (V7's
repairs ran the same uncapped path and self-limited), so it does not bias the comparison.
Filed #1011 for the post-window queue.

**Texture preview, recorded:** shakedown #2's delivered app **fails its own probes at boot**
(duplicate-join and leave) — the first non-working delivered application of the entire arc,
after 9/9 working under 3.6. Non-counting, but the first observed instance of a failure
class arm A never produced.

## WINDOW OPEN (2026-08-20, deploy `f7a5e0a2`)

All §2 preconditions hold. Six counted arm-B rolls follow, §5.1 rules inherited, no bar,
texture as instrument, §6 freeze in force from here.

## Arm B rolls

| Launch | Cycle | §5.1 | Score |
|---|---|---|---|
| 1 | cyc_02e9af402c82 | COUNTED | not functional |

### Roll 1 — cyc_02e9af402c82 — COUNTED, not functional

| Field | Value |
|---|---|
| Framing | 38 min; gate auto-approved |
| Implementation | `run_9733f845dedd` — failed 20:47 UTC (63 min), max corrections (3) exhausted |
| Verdict | `rejected` — 32 executed / 27 passed; failed: create probe (**200 ≠ declared 201**) + 3 downstream probes (cascade: `{run_id}` never captured) + `tests_pass` |
| Correction rounds | 3 — locus-correct dev-chain repairs (suite executed and failed → subject implicated); patch verification passed each round, retests stayed red |
| Boot audit (separate fact) | **FAIL — identical cascade. The delivered app genuinely violates its contract** (create returns 200, not 201) |
| Manual interventions | none |
| Tokens (impl, completion, by role) | neo 119.9k · eve 58.1k · max 14.8k · data 10.7k · bob 8.4k — total ~212k |
| Wall-clock | 1h41m total (fastest full roll of either arm) |

Texture, corrected twice as triage deepened — final attribution (#1012, #1013):

1. **The initial red is FRAMING-rooted, not implementation-rooted.** The manifest declares
   `success_status: 201`; the implementation plan's own dev criterion says *"returns 200"*.
   Neo built his brief faithfully; the contract judged him by the manifest. A framing-
   internal contradiction — authored by 3.8 in one session — with no gate that checks
   manifest↔plan consistency (#1013). A V7 green framing, checked as contrast, said 201 in
   both places. The status-discipline model claim now rests only on shakedown #2's 409
   (taught correctly, missed anyway — genuine slip).
2. **Recovery was then prevented by the machinery**: rounds 1–2 emitted the 201 fix
   (stored, patch-verified) and it vanished by round 3 (#1012 — re-dispatch blind to the
   accepted repair, or round-3 regression; unadjudicable from banked evidence, fourth
   instance of the evidence-dropped family). The final additive suite was contract-correct
   (201 on create), so the suite was satisfiable — the app the suite saw was not the
   repaired one.

So roll 1's counted red = 3.8 authoring self-contradiction (measured stack, model side)
× correction-loop state loss (harness, symmetric). Both named, per the standing rule.

**Arm B tally: 0 functional / 1 counted.**
