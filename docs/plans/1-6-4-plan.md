# 1.6.4 — plan

**Revision 2, 2026-08-25.** Revision 1 took the set record's attribution of the three
rejections at face value. A re-read of the stored per-round test reports (record §6) showed
that attribution was wrong for two of them, and §1–§4 below are re-derived from the corrected
reading. Revision history is in §6.

**Derived from measured loss modes, not from a sweep.** Every item below is something the
1.6.3 repeatability set observed on a frozen deploy
(`docs/plans/1-6-3-repeatability-set-record.md`), and the verification set is designed to
test whether fixing it worked.

That method is deliberate. The August sweep aged badly twice inside a single evening —
#795 and #913 closed out from under its 1.6.4 pack, #939 was mis-sized, and 11 of 17
census classes turned out already fixed with the largest one *misnamed*, because it was
classified from analyzer prose that had itself misread a parse rejection as an authoring
failure. **Date each class against its fixing commit and read the fix.**

And the method has a second half, learned between revisions of this document: **read the
gate's own per-round output, not the roll-up.** Revision 1 inherited "two of three
rejections were false" from a record that had inferred application correctness from a boot
audit that its own §2 says cannot see response bodies. The stored `test_report.md` files —
seven per rejected roll — said otherwise at every round.

---

## 1. What the set actually found

| finding | evidence | disposition |
|---|---|---|
| **Join-response shape** — the join endpoint's response violates the declared `list[Participant]` element kind (or a required `Run` field), and 3–4 repair rounds never land a fix the analyzer named correctly at round 0 | **All three rejections** end on the frozen #1029 response floor of `vc-probe-api-runs-join` (`expectShape`, which runs before the qa fill). Roll 4's final route returns bare strings for `participants`; the manifest declares `Participant{name}`. Rounds: 4, 3, 4. 3 of 8 devs wrong on this at round 0 | **fix — headline** (§2.1) |
| **#1087** — the frozen store exports a table handle for every declared entity, including embedded shapes and response projections no correct app writes | A **second** failing probe in rolls 1 and 4 (`join-duplicate`: `expected [] to have a length of 1`), never the only one. Misdirected roll 1's repair into `insert(TABLES.Participant, …)`. Yield on this set if fixed alone: **zero rolls** | **fix — with #1079's producer** (§2.2) |
| **#1079 producer half** — `json_has` has no producer, so contract probes never check response bodies | 3 of 3 rejected apps failed the response floor in the suite; **3 of 3 passed the boot audit**. The oracle is blind to shape, and the record's own misattribution is what that blindness costs | **fix — pairs with the above** (§2.2) |
| **correction non-convergence** — nothing recovered past round one in eight rolls; ~2 of 9 hours spent on rounds that never worked | 0–1 rounds → all 5 accepted; 3–4 rounds → all 3 rejected. Roll 5 repeated one identical failure across rounds 1–3 with a non-`none` structural candidate each time and #435's termination lever did **not** fire | **read, then fix** (§2.3) |
| **#1021** — `criteria_unevidenced` never settled: 1–5 `vc-compiles-*` dropped per roll on one frozen deploy | eight same-configuration samples now banked | **investigate** (§2.4) |

Found at the cut, not yet merged: **#1089** (stale version metadata) — fix in PR #1092.

**What this table does not say.** The dominant loss mode is not "fills reach for phantom
tables"; it is "the dev gets the join response shape wrong, the analyzer says so at round
zero, and the repair loop does not land a one-field fix in three or four tries." #1087 is
real and it sharpens the loop's failure (a phantom table gives the repair a wrong target to
chase), but it did not by itself reject anything.

---

## 2. The pack

### 2.1 The headline: land the fix the analyzer already named

Three rolls, one shape: the analyzer's round-0 `failure_analysis.md` correctly identifies
`vc-probe-api-runs-join` line 36 (`app_contract`, owner dev) in all three; three or four
repair rounds follow; the final test report shows the same line failing. This is #864's
"diagnoses accurately, then re-emits it" and #1015's causal chain — broad re-emission
mandated by the template, no minimality instruction, no attempt counter, and on rounds ≥ 1
no view of what the prior repair changed.

**Two reads before any code**, in the instrument-before-fixing discipline this loop has
earned twice over:

1. **Which dev-brief path rendered the response surface.** `response_shape.
   response_surface_instructions` is wired into `context_assembly.py` and
   `repair_handlers.py`; three of eight devs still returned the wrong element kind at
   round 0. Confirm the rendering actually reached the develop task on the roll's real
   code path (the shared-surface-with-a-private-drifted-duplicate pattern) before assuming
   the brief is right and the model ignored it.
2. **Why #435 did not fire in roll 5.** `should_terminate_plan_defect`
   (`src/squadops/cycles/correction_signature.py:192`) terminates on an exact adjacent
   signature repeat with non-`none` candidates on both sides. Roll 5's rounds 1–3 carried
   the same single failure and `tighten_acceptance` each time. Either the signature at the
   round boundary was not what the reports suggest, or the lever has a gap. Name which.

Then **#1015 A/B/C**: target from the failure analysis before the language-wide fallback,
a minimality block in the repair template, and the loop state ("attempt N of M", the prior
repair's changed files) threaded into the prompt. These are prompt-side and targeting-side
changes to a measured surface, so they ship inside the pack and are tested by the set.

### 2.2 The two hash-movers ship together

**#1087** moves the *generator* hash. **#1079's producer** moves the *contract* hash.

Landing them in one release means the hashes move **once**, and a 1.6.4 regression stays
attributable to the pair rather than to an unlucky sequence. Landing them separately
doubles the re-baselining and gives two windows in which the reference fixtures disagree
with the shells.

**#1087 — remove the ambiguity, do not document it.** The scaffold already knows which
entities are root-persisted: `Run` has endpoints, `Participant` appears only as
`list[Participant]` inside `Run`, `RunSummary` only as a `response:` type
(`scaffold.py:112`, `Endpoint.response`; `ManifestField.type`). Stop emitting `TABLES.X`
for the rest (`stack_nextjs_ts.py:386`). A fill that reaches for a non-existent table then
fails at *compile* time with a clear message rather than at runtime with an empty array.
Naming the root-persisted tables in the brief is the weaker option — it leaves the handle
present and relies on the author reading, which is the losing half of the #911/#912 lesson.

One detail the fix must carry: the frozen harness (`_harness_test_source`,
`stack_nextjs_ts.py:282`) addresses `entities[0]`, which on `group_run` is `Participant`.
Every roll's harness therefore *demonstrated* inserting into the phantom table. The harness
has to pick a root-persisted table or it stops compiling.

**#1079's producer — derive, do not author.** The response floor #1029 already renders into
the shells (`stack_nextjs_ts_tests.py:188`) is the same derivation a probe needs;
`_probes` in `scaffold_contract.py` currently emits `status`/`error_code` only. One
derivation, two renderings, so the audit and the suite answer the same question about the
same app. Had this existed, the record could not have called rolls 1 and 4 working
applications.

### 2.3 Stop paying for corrections that are not converging — after the #435 read

**#414 / #1015 are cited here for adjacency, not because either proposes this.** #414 is
the correction-budget allocation design; #1015 is targeting and prompt minimality. What
the set supports is narrower: **continuing past round one bought nothing in eight
attempts.** Detecting at round two that the diagnosis has not landed, and terminating, is
an *amendment to #435's rule*, and it is designed only after §2.1's second read says why
the existing rule stayed silent.

The honest caveat from the set stands: this is an association, not a cause. "Corrections
make it worse" and "hard rolls need corrections and are also likelier to fail" are
indistinguishable in eight rolls. And the corrected attribution makes one more thing
explicit: **stopping early is a time lever, not a rate lever.** Rolls 1, 4 and 5 would have
failed faster, not passed. The rate lever is §2.1.

### 2.4 Investigate, not fix

**#1021.** Code-read first. The set banked eight same-configuration samples; that is the
largest body of evidence the question has had.

---

## 3. The verification set — test the mechanism, not the rate

**Chasing the rate is a trap at this N.** An eight-roll set cannot distinguish 62.5% from
87%: the intervals overlap heavily. A set designed around the rate would spend nine hours
and conclude "consistent with improvement, consistent with noise."

**But each fix makes a falsifiable prediction about the texture fields**, and those are
testable at N=8 — some at N=1.

| # | prediction | falsified by |
|---|---|---|
| **P0** | No roll ends on the join-probe response floor after its round-0 analyzer names that floor — a correctly-diagnosed shape defect is landed by round two or the roll terminates | a roll whose final `test_report.md` fails `expectShape` on a line the round-0 analysis named |
| **P1** | No roll asserts on a non-`Run` table, because the handle does not exist | any roll that does, or any rejection traceable to a phantom table |
| **P2** | Every contract probe carries a shape check, and a response-floor defect is caught by the audit as well as the suite | a roll rejected on the response floor whose audit passes — the shape all three 1.6.3 reds took |
| **P3** | No roll spends more than two correction rounds | a roll reaching three |

The rate is reported as a **secondary** against 5/8, with the same interval discipline §1.3
pre-registered last time and the same refusal to read significance into a small delta.

**The record for each rejection names the failing assertion's origin — spine or fill — and
the round it first appeared.** That is the field revision 1 lacked and the one that would
have caught its error before it was written down.

**Pre-registered early stop, and only in one direction.** If P0, P1 or P2 is falsified, the
fix did not work and the remaining rolls teach nothing about it — stop, record,
re-register. **A good result is never grounds to stop early**; that is cherry-picking, and
V7's "no re-rolls to improve the figure" rule carries over unchanged.

**N = 8**, for comparability with the 1.6.3 baseline. Same frozen-deploy discipline, same
§5.1 validity rules, same gate policy including §6.1's two-path handling, same freeze.

---

## 4. Sequencing

1. **The two reads** (§2.1): dev-brief rendering path; why #435 stayed silent in roll 5.
   No code until both are written down.
2. **#1015 A/B/C**, shaped by read 1.
3. **#1087 + #1079 producer**, together, with the reference fixtures regenerated once.
   Regenerating a pinned fixture is an owner decision — propose the regen with the diff,
   do not fold it into the fix.
4. **The #435 amendment** (§2.3), shaped by read 2.
5. **#1021 read** — no code until the mechanism is named.
6. **Re-register the set** against P0–P3; rebuild, verify LOADED in-container rather than
   built, freeze, record image ids.
7. **Two shakeouts are not automatic.** One is required because every item above changes
   squad-facing behaviour. A second only if the first finds something, per V7 §2.f's
   reasoning rather than as ritual.
8. **Cut 1.6.4 promptly off the set**, preserving the zero-drift property 1.6.3 achieved:
   the freeze means the tagged tree is the validated deploy, and that dies on the next
   merge.

---

## 5. What this plan does not decide

**Whether 1.6.4 is the last patch before 1.7.** That should be gated on the set's result,
not on this document. A run that satisfies P0–P3 with a rate at or above the baseline makes
the 1.6 line's claim — the squad authors the interface design and the release proves it was
won — and 1.7 opens for hardening. A run that falsifies a prediction means 1.6.5 re-measures.

**The August sweep's 1.6.4 pack is not silently dropped.** #772, #939, #668, #930, #901 and
#936 are still open and none is in this pack, because none appeared in eight rolls. They go
to the 1.7 re-derivation below with that fact recorded, not into a gap between a superseded
sweep and this plan.

The 1.7 slate itself should be **re-derived before it opens**, using the dating method in
the preamble. It currently carries 39 open issues inherited from a sweep that has already
been shown stale twice.

---

## 6. Revision history

| rev | date | what changed | evidence |
|---|---|---|---|
| 1 | 2026-08-25 | Initial. Headline #1087 on the record's "2 of 3 rejections were false" | record §2–§3 as merged in PR #1088 |
| 2 | 2026-08-25 | Rolls 1 and 4 re-attributed: both failed the frozen response floor at every round; #1087 was a second failure, yield zero rolls. Headline moved to repair convergence on a correctly-diagnosed shape defect (§2.1). P0 added; the #435 lever's silence in roll 5 made a precondition of §2.3; harness `entities[0]` detail added to #1087; sweep leftovers dispositioned; #1089 corrected from "fixed" to "PR #1092 open" | per-round `test_report.md` and `failure_analysis.md` under `data/artifacts/group_run/` for `cyc_a24e4619844e`, `cyc_a38814afc16d`, `cyc_421d29473f86`; record §6 |
