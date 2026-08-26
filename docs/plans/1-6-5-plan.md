# 1.6.5 — plan

**Revision 2, 2026-08-26.** Adds a qa-only completion budget (§2.1 E) on the strength of the
emission distribution the cut question surfaced: four of ten qa primary emissions in the 1.6.4 set
sat at the 8,192 cap or within 3% of it, with the content roughly constant and the reasoning the
variance. Revision 1 deferred the raise until fills-first was measured; the distribution says the
budget is tight for this task shape, not merely unlucky, so the raise ships alongside the ordering
fix — each with its own prediction — rather than after it. The registry clamp is untouched.

**Revision 1, 2026-08-26.** Written at the 1.6.4 cut, from the 1.6.4 verification set record
(`docs/plans/1-6-4-verification-set-record.md`, §1.1, §3, §5) and nothing else. Every item below
is something that set observed on frozen deploy `5a697dfa`; the sweep leftovers the 1.6.4 plan
(§5) sent to 1.7's re-derivation stay there. **This is the narrow patch the 1.6.4 record said the
next one must be**, and it is the last patch before 1.7 opens unless its set falsifies a
prediction.

**Derived from measured loss modes, not from a sweep** — the 1.6.4 plan's method, unchanged, with
its second half: read the gate's own per-round output, not the roll-up. The 1.6.4 set was 8 of 8,
and the record is explicit that half of that is luck: the two rolls that entered the correction
loop were recovered by fallbacks, not by repair, and the cause behind both fired on three of
eight rolls.

---

## 1. What the set actually found

**One mechanism, three faces.** The qa author's primary emission — a ~17k-token prompt asking for
eight fill slots *and* an additive suite file — hit the 8,192-token completion cap on three of
eight rolls (roll 6 primary, roll 8 primary, roll 8 repair). The cap is deliberate:
`src/squadops/llm/model_registry.py:64-68` clamps `qwen3.8:27b` to 8,192 for comparability with
`qwen3.6:27b`, and the registry's own comment argues that longer completions drift. Roll 6's
second attempt authored the same eight fills in 5,498 tokens, so the work fits under the cap — but
not with much room. **All ten `qa.test` primary emissions in the set** (eve's `emission shape` log:
eight rolls plus shakeout 2 and roll 6's re-dispatch), completion tokens ascending:

```
4418  4947  5045  5498  5743  6292  7947  7963  8192  8192      cap = 8192
```

Four of ten at the cap or within 3% of it. The content is roughly constant — 7–15k characters,
~3.5–5k tokens of fills plus suite — and the variance is reasoning on top of it: the near-cap
emissions run ~1.4 characters per token against ~2.2 for the cheap ones. Both cap hits would have
closed under ~12k: roll 8 had every fill out and lost only the additive file's tail; roll 6 had
7,136 characters of additive file written when the cap took the fills. The dev side is a different
shape — 79 `develop` emissions in the same window, two at the cap, thirteen between 7.2k and 7.8k —
and its 8,192 clamp is *designed* to force per-file decomposition (`model_registry.py:47-55`);
nothing here touches it.

What happened after each cap hit is the finding:

| roll | where the cap fell | what recovered it | what should have |
|---|---|---|---|
| 6 | additive file written **first**, cap hit with **zero fills**; every shell rendered "no fill received" | the executor re-dispatched the whole `qa.test` task; the fresh attempt fit | the self-eval pass, which re-emitted eight valid fills — and that path discards them (#947, observed live) |
| 6 (repair) | — | — | the own-artifact `qa.test_repair`, which re-produced only `__tests__/runs.test.ts` because a repair cannot reach fills (#969/#970, observed live); its retest failed |
| 8 | all eight fills extracted; the additive `__tests__/api.test.ts` truncated (#1082 caught it) | the self-eval had already re-emitted a complete file; a correction round ran, its repair emitted nothing (`cap_exhausted`, refunded), and the retest ran the stored suite unchanged and passed | the suite, which ran against the **truncated** file the self-eval had just replaced |

Roll 8's third face is deterministic and is in the handler, not the model.
`qa_test.py:1255` merges the self-eval's re-emission into `artifacts`; `qa_test.py:1265` then
runs the suite on `extracted`, the pre-self-eval file set, which the loop never updates. The
stored artifact is the fixed file (hash `ef53ca9d…`); the report that failed the task was
produced from the broken one; the retest, on the same hash, passed. **A correction round was paid
to rediscover a fix the task already held.**

**Nothing else.** Rolls 1–5 and 7 never entered the loop. The develop-side emission failures (roll
2 `cap_exhausted`, roll 7 `unextractable`) were recovered by the aimed retry in-task, and #998's
signatures named both. P1, P3 and P5 — the 1.6.4 loop-side fixes — were never exercised and are
not this plan's problem to prove; §3 says how they are carried.

---

## 2. The pack

### 2.1 The headline: a truncated qa emission must be rarer, must cost the least important content, and what survives must be used

Five items, each one face of §1, ordered by yield per line changed. Together they convert roll 6's
shape into a green with no correction round and roll 8's into a green with none either. E makes the
cap hit rarer; A–D make it cheap when it happens. They address different halves and are measured
separately (§3).

**A. Fills first (#998 ask 2, the ordering half).** The qa fill-mode brief tells the author the
slots and the fence format; it does not say what to write first. On roll 6 the additive file came
first and the cap took every fill. The brief says: **emit every fill slot before any additive
file.** Prompt content, so it lives in the fill-mode appendix asset
(`request.qa_test_fill_mode_appendix.md`, v4) through `PromptService`, never in a handler string
literal. When the cap then falls, it falls on the additive file — the shape #1082 already catches
and the self-eval already repairs.

Measurable without a model: the fence order in every qa primary emission, read from the banked
artifact order. Roll 6 is the falsifier at N=1.

**B. The suite runs on what the task will store (the roll-8 ordering gap; to be filed, §5).**
`qa_test.py` recomputes the suite-execution set from `artifacts` after the self-eval loop, so a
self-eval re-emission that fixed a blocking typed check is the file the suite runs against. One
call-site change plus the `extracted` bookkeeping it currently bypasses. Replay proof: roll 8's
stored primary and self-eval emissions through the handler must produce a passing report on the
first run.

**C. The self-eval merges fills (#947, option 2).** Roll 6's self-eval re-emitted eight valid fills
and the drop filter at `qa_test.py:1253` discarded them because it only knows how to drop shell
paths. The self-eval's emission goes through the same `merge_fills` gate as the primary — the
phantom-table and element-kind rules (#1087, #1094) included — so a second pass can actually
repair a slot. Its prompt renders the slot list and the fill fence format, from the same appendix
as A (option 2's "own deploy boundary" concern is met: this line has one). Replay proof: roll 6's
stored primary and self-eval emissions through the handler must merge eight fills.

**D. An own-artifact qa repair can reach fills (#970, with #969's brief).** Under fill mode the
shells are merge products, never in `expected_artifacts`, so `correction_runner.py`'s own-artifact
branch aims the repair at the plan's declared file and a failing fill is structurally unreachable.
The fix is the one 1.6.4 already built for probes: when the failed task is a fill-mode `qa.test`,
the own-artifact target is the failing slot's shell, resolved through the same `_probe_owned_slots`
/ `_narrowed_or_scoped` chain (#1015-A) rather than a second resolver. The repair brief is composed
through the seam `qa.test` uses (#969's question — a fourth appendix or one composition seam — is
answered: the seam), so the repair knows the fill protocol and the in-process execution model.

**E. A qa-only completion budget (#998 ask 2, the budget half).** The `full-38` profile's `eve`
entry gains `config_overrides: {max_completion_tokens: 12288}` — the seam already exists and is
allowlisted (`src/squadops/cycles/models.py:184`), rides the plan as `agent_config_overrides`
(`task_plan.py:899`), and wins over the registry clamp at `base.py:351`. Config, not code: the
registry's 8,192 for `qwen3.8:27b` (`model_registry.py:64-68`) is the V38 comparability pin and
applies to every role; it stays. Cost when used: ≤ ~3 minutes per emission at 3.8's measured
~24 t/s, and only on the emissions that need it — the six under 6.3k pay nothing. The registry's
"coherence drifts past 8k" note is from qwen3.6 at ~10 t/s and is unmeasured on 3.8; Q5 and the
texture below are where it gets measured. **This changes `resolved_config_hash`**, so the 1.6.5
set is a new configuration line and its pre-registration records the new hash; no comparison to
`d4d4f66217d8` is claimed beyond the texture fields.

What E does not fix, stated so the set is not misread: the zero-character exhaustion class (roll
8's repair, roll 2's develop — 8,192 tokens of reasoning that never closed). A larger budget makes
those longer, not fewer; A–C and #998's signatures are what handle them.

D is the largest item and the only one that changes the repair path. It is in the pack because
the record names it (§1.1) and because without it the third net stays a net the set has watched
fail. It ships last (§4) and, if the set opens before it is ready, the set opens without it and
says so.

### 2.2 What is deliberately not built

**Raising the registry clamp, or the dev budget.** E is scoped to the qa role on one profile. The
registry's per-model clamp stays at 8,192 — it is the pin that made the V38 comparison honest and
the number every 1.6 record was measured under — and the dev budget stays where its own comment
puts it: an 8k ceiling that forces decomposition into per-file tasks. If the set's texture shows
dev emissions crowding the cap the way qa's did, that is a separate revision with its own number.

**#947 option 1 (skip the pass).** Superseded by C: a fill-aware self-eval is the pass that helps.

**#933** (the plan-authored competing qa deliverable that arms #970). D makes the mis-aim harmless
by targeting the slot rather than the declared file; #933's plan-side half stays a 1.7 item with
that fact recorded.

### 2.3 Instrumentation, in the pack because it is cheap and the set needs it

- The executor's aimed-retry log line echoes the #998 signature it re-dispatches with, so whether
  the retry prompt *rendered* the remedy is readable from logs (record §4; the 10,000-character
  LangFuse cap makes it unreadable there).
- The qa task's `test_report.md` is not re-stored in its failed form at run end after a passing
  retest (record §4, last-writer-wins). Cosmetic in outcome, but it is the exact artifact the
  next triage reads first.
- `scripts/dev/run_regression_tests.sh` exits 0 when `ruff` is not on the path and runs no tests.
  Found at this cut; it must fail loudly.

---

## 3. The verification set — test the mechanism, not the rate

Same discipline as 1.6.4 §3, inherited verbatim: N=8, frozen deploy with image ids asserted at
every launch, §5.1 validity, the §6 gate constant, no early stop on a good result, pre-registration
merged before roll 1. The rate is reported as texture against 8/8 and 5/8 with no significance
claim.

| # | prediction | falsified by |
|---|---|---|
| **Q0** | every qa primary emission places all fill fences before any additive file (A) — checked from the banked artifact order, no model in the loop | one emission with an additive file ahead of a fill |
| **Q1** | a qa primary emission that hits the cap loses only additive content: every fill slot merges (A) | a cap hit with any shell rendering "no fill received" |
| **Q2** | a self-eval re-emission of fills is merged through the gate (C) | a self-eval emission with `fill: N>0` followed by a shell with no fill |
| **Q3** | the suite runs on the post-self-eval file set (B) | a failing `test_report.md` whose error names content the stored artifact of the same task does not contain |
| **Q4** | an own-artifact qa repair whose failing test is a shell targets that shell (D) | a `correction_repair_locus: own_artifact — qa.test re-produces __tests__/…` line when the failed test was a scaffold file |
| **Q5** | no `qa.test` primary emission reaches its completion cap (E) — read from eve's `emission shape` log, `completion_tokens < 12288` on every primary | one primary at 12,288 |
| **P1, P3, P5** | carried from 1.6.4 unchanged — unexercised is not passed, and they are on this deploy too | as pre-registered in 1.6.4 |

**Texture, no prediction attached:** the full qa primary completion-token distribution against the
ten in §1 (whether the headroom was consumed, and by how much — the number the next cap decision
is made with), the cap-hit count against 3/8, and qa wall-clock per emission against the 1.6.4
set's; correction rounds against 1.6.4's 2 and 1.6.3's 0/1/3/4 split; wall clock.

**A fault-injection arm is the honest way to exercise Q4 and P1/P3/P5.** Eight `full-38` rolls
produced no dev-side failure and two qa-side ones; the loop-side predictions cannot be read from a
set that never enters the loop. A **non-counting** arm on the `lite` squad (7b), same project and
overrides, pre-registered separately with its own image ids, exists to *produce* correction rounds
so the targeting and gate predictions get exercised. It reports predictions only — its rate means
nothing and is not written down as one. Whether to run it is the owner's call at set time; the
plan recommends it, because the alternative is shipping D unexercised a second time.

---

## 4. Sequencing

1. **File the roll-8 ordering gap and the three §2.3 items** (owner's OK first); give B its number.
2. **A + B + C + E together** — one deploy boundary: three in the qa handler and its appendix, E
   in `config/squad-profiles.yaml`. Attribution survives the bundling: Q0 is a static check on
   fence order, Q5 and the token texture read from counts, Q2/Q3 from the handler's own records.
   Replay proof before any rebuild: roll 6's and roll 8's stored emissions through the handler
   paths (`feedback: replay-first`). Regression green.
3. **D** — the runner change through the 1.6.4 resolver chain, the brief through the qa seam.
   Its unit proof is roll 6's stored `failure_evidence` resolving to the failing shell.
4. **Pre-register**, rebuild, verify **loaded** in-container (not built), freeze, record image ids.
   One shakeout; a second only if the first finds something.
5. **Run the counting set**, and the fault-injection arm if the owner takes it.
6. **Cut 1.6.5 promptly off the set** with zero drift, as 1.6.3 and 1.6.4 did.

---

## 5. What this plan does not decide

**Whether 1.7 opens after 1.6.5.** Gated on the set, as 1.6.4 §5 said: a set that holds Q0–Q4
closes the 1.6 line's known loss modes and 1.7 opens for hardening; a falsified prediction means
1.6.6 re-measures. The 1.7 slate re-derivation (39 inherited issues, plus #1099 and #242, #372,
#1041) happens **before** 1.7 opens and is not this plan's work.

**The unfiled findings.** Filing is the owner's act. To file, with the record as evidence: the
roll-8 ordering gap (B); the executor retry log not echoing the #998 marker; the qa `test_report`
last-writer-wins re-store; the regression script's silent exit; and the root-table rule's
single-object-response edge (shakeout 1 and roll 8 declared `RunWithParticipants` / `RunDetail`
and the store gave each a table — nothing asserted on it, so it is recorded here and not planned).

**Issue hygiene from the 1.6.4 cut.** #1096, #1087 (nextjs_ts half), #1079, #1021, #1015-A and
#1094 shipped in 1.6.4 without `Closes` lines and are open at this writing; they close at the cut
with the PR named. #998 stays open, narrowed to ask 2's budget half. #1087 stays open, narrowed
to stack #1.

---

## 6. Revision history

| rev | date | what changed | evidence |
|---|---|---|---|
| 2 | 2026-08-26 | E added: eve-only `max_completion_tokens: 12288` on `full-38`, with Q5 and the distribution texture; §2.2 rescoped from "no raise" to "no registry or dev raise"; §1 carries the ten-emission distribution and the dev-side contrast | eve `emission shape` lines for the set window (ten `qa_test_handler` primaries); neo's 79 `develop` emissions; `models.py:184`, `task_plan.py:899`, `base.py:351`, `model_registry.py:47-68` |
| 1 | 2026-08-26 | Initial, at the 1.6.4 cut | `1-6-4-verification-set-record.md` §1.1, §3, §4, §5; `qa_test.py:1253-1265`; `model_registry.py:64-68`; #947, #969, #970, #998 as filed |
