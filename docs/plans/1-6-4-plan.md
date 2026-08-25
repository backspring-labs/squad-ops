# 1.6.4 — plan

**Derived from measured loss modes, not from a sweep.** Every item below is something the
1.6.3 repeatability set observed on a frozen deploy
(`docs/plans/1-6-3-repeatability-set-record.md`), and the verification set is designed to
test whether fixing it worked.

That method is deliberate. The August sweep aged badly twice inside a single evening —
#795 and #913 closed out from under its 1.6.4 pack, #939 was mis-sized, and 11 of 17
census classes turned out already fixed with the largest one *misnamed*, because it was
classified from analyzer prose that had itself misread a parse rejection as an authoring
failure. **Date each class against its fixing commit and read the fix.**

---

## 1. What the set actually found

| finding | evidence | disposition |
|---|---|---|
| **#1087** — the frozen store exports a table handle for every declared entity, including embedded shapes and response projections no correct app writes | 2 of 3 rejections. Perfect separation: every roll asserting only `TABLES.Run` accepted, both reaching elsewhere rejected. Dev side verified correct in both | **fix — headline** |
| **#1079 producer half** — `json_has` has no producer, so contract probes never check response bodies | Roll 5: real missing field, suite caught it, **audit passed**. The oracle is blind to shape | **fix — pairs with the above** |
| **correction non-convergence** — nothing recovered past round one in eight rolls; ~2 of 9 hours spent on rounds that never worked | 0–1 rounds → all 5 accepted; 3–4 rounds → all 3 rejected, no overlap | **fix (#414/#1015)** |
| **#1021** — `criteria_unevidenced` never settled: 1–5 `vc-compiles-*` dropped per roll on one frozen deploy | eight same-configuration samples now banked | **investigate** |

Already fixed at the cut: **#1089** (stale version metadata).

---

## 2. The pack

### 2.1 The two hash-movers ship together

**#1087** moves the *generator* hash. **#1079's producer** moves the *contract* hash.

Landing them in one release means the hashes move **once**, and a 1.6.4 regression stays
attributable to the pair rather than to an unlucky sequence. Landing them separately
doubles the re-baselining and gives two windows in which the reference fixtures disagree
with the shells.

**#1087 — remove the ambiguity, do not document it.** The scaffold already knows which
entities are root-persisted: `Run` has endpoints, `Participant` appears only as
`list[Participant]` inside `Run`, `RunSummary` only as a `response:` type. Stop emitting
`TABLES.X` for the rest. A fill that reaches for a non-existent table then fails at
*compile* time with a clear message rather than at runtime with an empty array. Naming the
root-persisted tables in the brief is the weaker option — it leaves the handle present and
relies on the author reading, which is the losing half of the #911/#912 lesson.

**#1079's producer — derive, do not author.** The response floor #1029 already renders into
the shells is the same derivation a probe needs. One derivation, two renderings, so the
audit and the suite answer the same question about the same app.

### 2.2 Stop paying for corrections that are not converging

**#414 / #1015.** Not "make round three smarter" — round three has never worked. Detect at
round two that the diagnosis has not landed and terminate. The honest caveat from the set:
this is an association, not a cause. "Corrections make it worse" and "hard rolls need
corrections and are also likelier to fail" are indistinguishable in eight rolls. What the
data does support is that **continuing past round one bought nothing in eight attempts**,
which is enough to justify not paying for it.

### 2.3 Investigate, not fix

**#1021.** Code-read first — the standing instrument-before-fixing rule, and this loop has
produced wrong guessed diagnoses before. The set banked eight same-configuration samples;
that is the largest body of evidence the question has had.

---

## 3. The verification set — test the mechanism, not the rate

**Chasing the rate is a trap at this N.** Even if #1087 lifts 62.5% to ~87%, an eight-roll
set cannot distinguish those: the intervals overlap heavily. A set designed around the rate
would spend nine hours and conclude "consistent with improvement, consistent with noise."

**But each fix makes a falsifiable prediction about the texture fields**, and those are
testable at N=8 — some at N=1.

| # | prediction | falsified by |
|---|---|---|
| **P1** | No roll asserts on a non-`Run` table, because the handle does not exist | any roll that does, or any rejection traceable to a phantom table |
| **P2** | Every contract probe carries a shape check, and a roll-5-class defect is caught by the audit as well as the suite | a roll rejected on the response floor whose audit passes |
| **P3** | No roll spends more than two correction rounds | a roll reaching three |

The rate is reported as a **secondary** against 5/8, with the same interval discipline §1.3
pre-registered last time and the same refusal to read significance into a small delta.

**Pre-registered early stop, and only in one direction.** If P1 or P2 is falsified, the fix
did not work and the remaining rolls teach nothing about it — stop, record, re-register.
**A good result is never grounds to stop early**; that is cherry-picking, and V7's "no
re-rolls to improve the figure" rule carries over unchanged.

**N = 8**, for comparability with the 1.6.3 baseline. Same frozen-deploy discipline, same
§5.1 validity rules, same gate policy including §6.1's two-path handling, same freeze.

---

## 4. Sequencing

1. **#1087 + #1079 producer**, together, with the reference fixtures regenerated once.
   Regenerating a pinned fixture is an owner decision — propose the regen with the diff,
   do not fold it into the fix.
2. **#414 / #1015.**
3. **#1021 read** — no code until the mechanism is named.
4. **Re-register the set** against the predictions above; rebuild, verify LOADED in-container
   rather than built, freeze, record image ids.
5. **Two shakeouts are not automatic.** One is required because #1087 and #1079 both change
   squad-facing behaviour. A second only if the first finds something, per V7 §2.f's
   reasoning rather than as ritual.
6. **Cut 1.6.4 promptly off the set**, preserving the zero-drift property 1.6.3 achieved:
   the freeze means the tagged tree is the validated deploy, and that dies on the next merge.

---

## 5. What this plan does not decide

**Whether 1.6.4 is the last patch before 1.7.** That should be gated on the set's result,
not on this document. A run that satisfies P1–P3 with a rate at or above the baseline makes
the 1.6 line's claim — the squad authors the interface design and the release proves it was
won — and 1.7 opens for hardening. A run that falsifies a prediction means 1.6.5 re-measures.

The 1.7 slate itself should be **re-derived before it opens**, using the dating method in
the preamble. It currently carries 39 open issues inherited from a sweep that has already
been shown stale twice.
