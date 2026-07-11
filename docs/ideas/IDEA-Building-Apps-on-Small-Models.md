# IDEA: Building Apps on Small Models — a Falsifiable Thesis

## Target Release
Vision item / running experiment log — validated incrementally as the build-reliability
levers land, with the payoff retrospective due once `sips/proposed/SIP-Contract-First-Build-Scaffolding.md` (intervention R3) ships.

### Status
Thesis draft — predictions recorded *before* the interventions, to be scored *after*.

### Owner
Build / Architecture

### Origin
Distilled 2026-07-11 from the SIP-0096 Phase-2 field evidence: the Mac `lite` squad
(all `qwen2.5:7b`) cannot reach `qa.test` positively — it aborts upstream at
`builder.assemble` / `development.develop` — while the Spark `full` squad (`qwen3.6:27b`)
completes the build→test chain. The question that produced this doc: *what will it take
for a small, Mac-runnable model to build an app — honestly — and what did each step cost?*
Companion to `docs/ideas/IDEA-Scaffold-Interface-vs-Implementation.md` and #375/#376.

---

## The thesis (stated so it can be proven wrong)

> **A small, commodity-hardware model can build a working application — not by being
> made bigger, but by being asked the right way.** The dominant blocker to small-model
> app-building is *unscaffolded generative burden* (rote, cross-file-consistent assembly
> held in working memory), not raw reasoning capacity. Removing that burden
> architecturally moves the build frontier further than scaling the model does.

The strong form — the one worth validating — is the second sentence: **scaffolding beats
scale.** If, after R3, a **7B** model honestly builds an app that a **14B** model could
*not* build unscaffolded, the thesis holds. If only bigger models ever cross the line,
it is falsified and the real answer was capacity all along.

## Why this is measurable now (SIP-0096 is the truth instrument)

This thesis is only testable because we can no longer be lied to. Before SIP-0096, "the
small model built an app" was unfalsifiable — a run that printed `completed` over a
frontend that never builds (the #376 case, `cyc_769db63c9d2b`) *looked* like success.

SIP-0096 (Verification Evidence Integrity) makes the claim honest: only
executed-and-passed evidence credits, not-executed silence never credits, and a required
check with no real result blocks as `blocked_unverified`. **So the unit of proof for this
thesis is an honest `accepted` verdict** — build→`qa.test`→passing test evidence→verdict
`accepted`, with `no_stub_fallback` clean. A small model that earns `accepted` genuinely
built the thing; one that can't earns an honest `rejected`/`blocked` we can act on. The
verdict is the scoreboard, and it cannot be gamed — which is the whole point.

## Where small models hit the wall (grounded, not guessed)

The build path to a positive `qa.test`, and where each model tier fails today:

```
governance.define_done → planning → builder.assemble → [gate] → development.develop → qa.test
        (JSON quality, D9)              (scaffold a buildable pkg)   (code + real tests)   (run them; must pass)
```

| Tier | Model | Fails at | Honest verdict |
|------|-------|----------|----------------|
| smoke | qwen2.5:3b | `governance.define_done` (D9 JSON quality) | never reaches build |
| lite | qwen2.5:7b | `builder.assemble` / `development.develop` (incomplete/unbuildable output) | run FAILs before `qa.test` |
| full | qwen3.6:27b (Spark) | — reaches `qa.test` positively | `accepted` (the reference) |

Two facts this pins down:
- **It is not the harness or toolchain.** For a Python objective, `pytest` + the
  generated-test runner are already present (#306 added Node for frontend). The variable
  is *generation quality* at assemble+develop, nothing downstream.
- **The wall is specifically cross-file, rote assembly** — the exact weakness named in
  the scaffolding idea doc. Governance stages already clear at 7B; the build stages don't.

Hardware context (the constraint that makes "small" concrete): the Mac has **24 GB RAM**
and swaps models per task (≈1 resident at a time). Locally available today:
`qwen2.5:7b` (4.7 GB), `qwen2.5:14b` (9 GB), `qwen2.5:3b`. `qwen3.6:27b` is Spark-only.
So the Mac frontier is anything ≤ ~14 GB resident.

## The intervention ladder (each rung is a prediction to score)

Ordered by cost. Each rung is a hypothesis with a prediction recorded *now*; the
validation table below is scored *after* running it. The anti-lever is called out because
it is the tempting wrong turn.

- **R0 — baseline (observed).** `lite`, all `qwen2.5:7b`. **Result: FAILs at
  assemble/develop, no positive `qa.test`.** This is the documented starting frontier.
- **R1 — scale, general (zero new pulls).** A `lite-14b` profile, all `qwen2.5:14b`
  (already local). *Prediction:* reaches `qa.test` positively on a **trivial**
  single-function objective; likely still stalls on multi-file objectives.
- **R2 — code-tuning (one pull).** `qwen2.5-coder:14b` on the build-critical roles
  (Bob/Neo/Eve), governance stays 7B. *Prediction:* reaches `qa.test` positively on
  **small-to-moderate** objectives — code-tuning is a bigger jump for buildable code than
  raw size.
- **R3 — scaffolding (lever 3 / SIP-Contract-First-Build-Scaffolding).** Deterministic
  interface→skeleton expander; the model fills bodies into scaffold-owned slots it cannot
  rewire. *Prediction:* reaches `qa.test` positively on **real multi-file** objectives
  **even at 7B**, because the generative burden collapses from "assemble the whole app" to
  "fill a body." **This is the rung the thesis lives or dies on.**

**The anti-lever — do not.** Relaxing the acceptance bars (D9, `no_stub_fallback`,
assemble-completeness) to force a green is manufacturing the exact false-green SIP-0096
exists to kill. A "positive" `qa.test` earned by lowering the bar validates nothing — it
validates the harness against a lie. Every rung must clear the *same* bars; only then is
frontier movement real.

## The frontier is two-dimensional

"Small models can build apps" is really *"a model of size M can honestly build an
objective of complexity C."* Track both axes; the cell value is the honest SIP-0096
verdict.

```
objective complexity →
              single-fn   single-module CLI   multi-file backend   full-stack app
qwen2.5:3b       ?              —                    —                   —
qwen2.5:7b       ?              R0: FAIL             —                   —
qwen2.5:14b     R1?            R1?                  R1?                  —
coder:14b       R2?            R2?                  R2?                 R2?
+ scaffold(R3)  ✓ expect      ✓ expect             ✓ expect(7B!)       ✓ expect
27b (Spark)      ✓             ✓                    ✓                  ✓ (ref)
```

The interventions push the "honestly `accepted`" region toward the **small-model /
complex-objective** corner. R3's claim is that scaffolding moves the *whole 7B row* right,
not just the big-model rows.

## Validation scorecard (fill in as each rung runs)

Fixed objective ladder, run identically at each rung; record the **most complex objective
that yields an honest `accepted`** and *what broke* below it. This is the "what it took" log.

| Rung | Model roster | Highest honest `accepted` | Where it broke above that | Remediation applied | Date |
|------|--------------|---------------------------|---------------------------|---------------------|------|
| R0 | lite / 7b | *(none — fails at assemble)* | `builder.assemble`: incomplete package | — (baseline) | 2026-07-11 |
| R1 | lite-14b / 14b | _tbd_ | _tbd_ | _tbd_ | |
| R2 | coder:14b (build roles) | _tbd_ | _tbd_ | _tbd_ | |
| R3 | 7b + contract-first scaffold | _tbd_ | _tbd_ | _tbd_ | |

**Limitations & how addressed (the running log the goal asks for):**

| # | Limitation observed | Stage | How addressed | Rung that fixed it |
|---|---------------------|-------|---------------|--------------------|
| L1 | 7B ships an unbuildable package skeleton (missing entry files, unwired imports) | assemble/develop | _tbd_ | _tbd_ |
| L2 | 3B can't produce valid define_done JSON | define_done | (governance stays ≥7B) | R0 |
| … | | | | |

## How the thesis gets scored (the retrospective, due after R3)

When SIP-Contract-First-Build-Scaffolding (lever 3) lands, answer these — this is the payoff:

1. **Did R3 let a 7B honestly `accept` an objective that R1/R2 could not?**
   - Yes → **thesis validated**: the unlock is architecture, not scale. Record the
     objective and the frontier delta.
   - No, but a bigger model could → **thesis falsified (strong form)**: capacity was the
     real constraint; document at what size the frontier actually opens.
2. **Attribution:** decompose the frontier movement across R1 (scale) vs R2 (code-tuning)
   vs R3 (scaffolding). Which moved it most per unit cost (GB resident, $, latency)?
3. **What did it *cost*?** The honest "what it took": pulls, config, the scaffolding SIP's
   implementation effort, and any objective-complexity ceiling still standing.
4. **What's the new frontier?** The smallest model × most complex objective cell now
   honestly `accepted`, and the next wall beyond it.

## Relationship to the rest of the arc

- **SIP-0096** — the instrument. Makes every result on this ladder honest; without it the
  scorecard is unfalsifiable.
- **SIP-Contract-First-Build-Scaffolding** — intervention R3, the thesis's decisive test.
  This doc is its empirical companion: the SIP proposes the mechanism, this scores whether
  it delivered small-model app-building.
- **Two-lane model** — the Spark `full` (27B) squad stays the *quality reference*; this
  thesis is about pushing the *Mac (small-model) frontier* toward it, cheaply and honestly.
  A validated thesis means fast, local, trustworthy build validation without a Spark
  round-trip per slice.
