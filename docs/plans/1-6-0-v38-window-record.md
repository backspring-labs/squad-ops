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
| Cycle | _pending launch_ |

## Arm B rolls

Pending shakedown #2 outcome.
