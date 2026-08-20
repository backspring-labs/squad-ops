# V38 — Model-Comparison Window (qwen3.6 vs qwen3.8): Pre-Registration

**Status: DRAFT — not in force until every §2 precondition holds.** Once in force, nothing
in this document changes until the window closes.

**Owner:** maintainer · **Question:** does swapping the squad's model from `qwen3.6:27b` to
`qwen3.8:27b`, with **everything else identical**, change authored-mode FAY and its texture?
· **Comparison arm A:** the closed V7 window (amended 4/6, `1-6-0-v7-fay-window-record.md`)
· **Arm B:** six fresh rolls under this document.

---

## 1. Design: one variable, and the honest limits of N=6

Arm B runs the **identical recipe** to V7 attempt 2 — same PRD, same request profile, same
overrides, same gate policy, same §5 scoring (corrected instrument) — with the squad profile
changed to **`full-38`**, the `full` roster verbatim on `qwen3.8:27b`.

**This is a STACK comparison, not a pure model isolate** *(owner-ruled 2026-08-20)*. Running
qwen3.8 required upgrading Ollama 0.21.2 → 0.32.14, so two things differ between arms and
both are named: the model, and the inference server. The server change is behaviorally real:
under 0.21 the model's reasoning arrived inline in `content` (V7's emission logs show
thinking prose inside emissions); under 0.32 reasoning routes to a separate `thinking` field
and `content` arrives clean — same completion-token budget semantics (the #998 class is
unchanged), different emission shape. The deltas are inseparable in practice — nobody would
run 3.8 on the old server — so the window measures the decision actually on the table:
**the incumbent stack (3.6 on 0.21) vs the 3.8 stack (3.8 on 0.32)**, and the closing claim
words it exactly that way. A pure model isolate would require re-baselining 3.6 on 0.32
(six more rolls); the owner declined that cost knowingly.

**What this window can claim:** gross differences in the headline (e.g. 2/6 vs 6/6) and
differences in **texture** — zero-correction rate, first-attempt fill rate, store-assertion
rate, repair convergence, additive-suite failure rate, thinking-cap events, emission sizes,
cycle durations, tokens per roll. **What it cannot claim:** significance for small headline
deltas. 4/6 vs 5/6 is noise and the closing claim must say so if it lands there. The texture
fields are the real instrument; the per-roll record captures them identically to V7's.

Cost note (three-pools): both arms draw exclusively from local capacity — the comparison's
marginal cost is electricity. Cost-per-verified-outcome is recorded per arm.

## 2. Preconditions

| # | Precondition | State |
|---|---|---|
| 2.1 | V7 closed and banked (the A arm exists) | **MET** — amended 4/6, record on `docs/v7-window-record` |
| 2.2 | Ollama upgraded to a version that serves `qwen3.8:27b`; **`qwen3.6:27b` verified still generating on the GB10 after the upgrade** (the incumbent must not break) | **MET** — 0.32.14; incumbent verified through the deployed adapter (clean content, 12.3 t/s warm) |
| 2.3 | `qwen3.8:27b` pulled; raw throughput measured and recorded in §3 (t/s on the standard prompt shape) | **MET** — see §3 |
| 2.4 | `full-38` profile merged; **`full` untouched** (it is the meaning of every historical record) | **MET** — #1006 merged; profile live in the baked config |
| 2.5 | **MET at `5d66f80f`** — deploy frozen and recorded in §3. The comparison deploy differs from V7's (`61a12e38`) by **only**: the #1005 instrument fix (`efad69a7`, post-cycle audit only — ruled into the V7 measurement standard), the inert `full-38` profile entry (never referenced by any V7 roll), and — named per the §1 stack-comparison ruling — the host inference server (Ollama 0.21.2 → 0.32.14, incumbent verified through the deployed adapter post-upgrade). Any other delta voids comparability and must instead trigger re-registration | pending — rebuild at merge |
| 2.6 | **One declared shakedown** on `full-38`, NON-COUNTING, before roll 1: a new model is a new failure surface (structured-output compliance, fence discipline, thinking behavior — the #998 cap-exhaustion class is exactly what a model swap moves). Bar: the cycle reaches a verdict without a *new* harness-attributable mechanical failure. Findings are fixed or declared before the window opens | pending |
| 2.7 | Zero unreleased focus leases; nothing in flight at each launch | check at launch |

## 3. Fixed parameters — complete before roll 1, unchanged thereafter

| Parameter | Value |
|---|---|
| N (rolls) | 6 counted; §5.1 void/reset/counted rules inherited from V7 verbatim |
| Bar | none — **this window has no pass/fail bar.** It measures a delta; V7's ≥4/6 bar belonged to the viability question, already answered |
| PRD | `examples/03_group_run/prd.md`, sha `f744843d…` — re-verify at roll 1 |
| Squad profile | **`full-38`** (sole intended delta) |
| Request profile / overrides | `validated-fullstack`; `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | expect `d4d4f662…` unchanged (profile is not an input); re-verify at roll 1 |
| Model | `qwen3.8:27b`, digest `22130167c4c2`, Q4_K_M, 27.3B params, 262k context, thinking-capable; **Ollama 0.32.14** |
| Measured t/s (2.3) | **24.0 t/s** warm generation / 104.8 t/s prompt eval (incumbent same-box warm: 12.3) — 2x at equal parameter count and quantization on a bandwidth-bound chip suggests sparser per-token activation; recorded as an open architecture question, answered by the rolls' quality texture rather than guessed |
| Deploy — commit + 7 image ids | **RE-FROZEN at `f7a5e0a2`** after shakedown #1's findings (both fixed per the owner's fix-refreeze-shakedown-open ruling: #1008 = qwen3.8 registry clamp parity + bounded JSON re-ask; loaded-module verified in data). Prior freeze `5d66f80f` recorded for the audit trail; shakedown #1 ran on it and is non-counting by declaration. runtime-api `34126b76ff90`; max `865aa7fa2677`; neo `17c4c315cb98`; nat `8f21700fb42b`; bob `30004c6c1aaf`; eve `7a3852e0e66b`; data `f7833405d0d4`. Delta vs V7's `61a12e38` = #1005 + `full-38` profile + #1008 + docs |
| Gate policy | V7 §7.3(c) verbatim — the same pinned text, unchanged |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the frozen deploy commit (carries #1005) |

## 4. Per-roll record

Identical fields to V7's §4 (verdict, counts, criteria, corrections, fills/slots,
store-assertion evidence with method noted while #999 stands, boot audit as a separate
fact, gate disposition, §5.1 validity) **plus** per-roll: total completion tokens by role,
cycle wall-clock, and any #998-class cap-exhaustion events.

## 5. Scoring and the closing claim

A roll is functional iff verdict `accepted` AND the audit passes AND zero manual
intervention — V7's §5 verbatim, corrected instrument. The closing claim reports: both
arms' headlines side by side, the texture table, and an explicit statement of what N=6
does and does not support. **No re-rolls to improve either figure; six rolls, done**
(V7 §7.4 rule 2 inherited).

## 6. Prohibited during the window

V7 §6 verbatim: no merges to main, no rebuilds, no prompt/plan-asset edits, no gate-policy
changes, no edits to this document. Detections recorded as issues, left unfixed. The
machinery fix queue (additive-suite containment, #1002, #994, #995/#998/#999) lands
**after** this window — fixing between arms would destroy the comparison.

## 7. Provenance

Derived from the owner's 2026-08-19 proposal ("upgrade the model… thorough compare of the
rolls on a whole new run of 6") and the ≥4/6 gate ruling; V7 closed at an amended 4/6 on
2026-08-20, opening this window's precondition 2.1.
