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
overrides, same gate policy, same §5 scoring (corrected instrument) — with exactly one
change: squad profile **`full-38`**, which is the `full` roster verbatim on `qwen3.8:27b`.

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
| 2.2 | Ollama upgraded to a version that serves `qwen3.8:27b`; **`qwen3.6:27b` verified still generating on the GB10 after the upgrade** (the incumbent must not break) | pending |
| 2.3 | `qwen3.8:27b` pulled; raw throughput measured and recorded in §3 (t/s on the standard prompt shape) | pending |
| 2.4 | `full-38` profile merged; **`full` untouched** (it is the meaning of every historical record) | this PR |
| 2.5 | Deploy frozen and recorded in §3. The comparison deploy differs from V7's (`61a12e38`) by **only**: the #1005 instrument fix (`efad69a7`, post-cycle audit only — ruled into the V7 measurement standard) and the inert `full-38` profile entry (never referenced by any V7 roll). Any other delta voids comparability and must instead trigger re-registration | pending — rebuild at merge |
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
| Model | `qwen3.8:27b`, Ollama version + model digest recorded here at freeze: `_____` |
| Measured t/s (2.3) | `_____` |
| Deploy — commit + 7 image ids | `_____` at freeze |
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
