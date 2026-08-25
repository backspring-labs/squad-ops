# 1.6.4 — plan

**Revision 4, 2026-08-25.** The two reads §2.1 required are done (`1-6-4-reads.md`), and the
second found the root cause of the set's dominant loss mode: the `nextjs_ts` expander types
every entity-typed field as `string`, so the frozen `lib/models.ts` — labelled authoritative
in the developer's brief — contradicts the response floor on every roll (**#1096**). It is the
headline now. Read 1 withdrew rev 3's targeting guess: the repair target was the whole
application every round, the named file present but never distinguished.

**Revision 3, 2026-08-25.** Revision 1 took the set record's attribution of the three
rejections at face value; revision 2 corrected it from the stored per-round test reports
(record §6) but named #1015 as the headline without dating it — parts B and C were already
on the set's deploy (`4f631df7`, v1.6.2) — and said #435's termination lever stayed silent
in roll 5, which the run report contradicts. Revision 3 is derived from the per-round
*repair emission* timelines, which name the mechanism. Revision history is in §6.

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
| **#1096** — the frozen `lib/models.ts` declares `Run.participants: string[]` where the manifest declares `list[Participant]`; the floor, from the same manifest, demands objects | Every `nextjs_ts` roll, greens included (reads §2). Roll 4's developer returned exactly what the frozen file declared and failed the floor at every round; rolls 1 and 5 the same; the greens passed by ignoring the frozen type. `_ts_type` (`stack_nextjs_ts.py:59`) maps every entity reference to `string` | **fix — headline** (§2.1); moves the generator hash, ships with §2.2's pair |
| **The repair never distinguishes the file it was told about.** The decision names the join handler; the repair emits the create route | Roll 1 round 2, roll 4 rounds 2–3. The target list was the **entire application** every round — package scoping never matches on `nextjs_ts` (18 of 18 rounds hit the #688 fallback, reads §1) — so the named file was in the list and never singled out. #1015 B/C were on the deploy and did not prevent it | **fix** (§2.1): #1015 A as a *narrowing* + #968's slice |
| **A repair round emits nothing.** `development.correction_repair` returns 0 characters | 3 of the 11 repair rounds in the reds (roll 1 r3; roll 5 r1, r2). `a93240dc` refunds the attempt — measured working, roll 5 reached a fourth decision — but each cost ~15 minutes and its signature (cap-exhausted vs empty) is not recorded | **fix** (§2.1): #998 detection |
| **#1094** — a correct repair is discarded because the qa fills contradict the contract | Roll 5 round 3: the dev re-emit passed the frozen floor; the qa fills (`expect(body.participants).toContain('sample')` on a `list[Participant]` field) failed; the candidate was rejected, Fix E excluded it from the next workspace, and #435 terminated the run as `plan_defect` at the next decision. The application was correct for one round and the loop threw it away | **fix** (§2.1): fills must agree with the declared element kind, from the same derivation as the floor |
| **#1087** — the frozen store exports a table handle for every declared entity, including embedded shapes and response projections no correct app writes | A **second** failing probe in rolls 1 and 4 (`join-duplicate`), never the only one. Misdirected roll 1's round-1 repair into `insert(TABLES.Participant, …)`. Yield on this set if fixed alone: **zero rolls** | **fix — with #1079's producer** (§2.2) |
| **#1079 producer half** — `json_has` has no producer, so contract probes never check response bodies | 3 of 3 rejected apps failed the response floor in the suite; **3 of 3 passed the boot audit**. The record's own misattribution is what that blindness costs | **fix — pairs with the above** (§2.2) |
| **#1021** — `criteria_unevidenced` never settled: 1–5 `vc-compiles-*` dropped per roll on one frozen deploy | eight same-configuration samples now banked | **investigate** (§2.4) |

Found at the cut, not yet merged: **#1089** (stale version metadata) — fix in PR #1092.

**What this table does not say.** The dominant loss mode is not "fills reach for phantom
tables" and it is not "the loop needs a terminator": #435 fired in roll 5, and rolls 1 and
4 never produced an exact repeat because each repair failed somewhere new. It is that
**the scaffold told the developer the wrong shape with the word "authoritative" attached,
and then the repair loop spent three or four rounds not acting on a diagnosis that was
right from round 0** — emitting the wrong file, or nothing, or the right thing that a wrong
fill then rejected. Three of eight developers obeyed the frozen file; five ignored it and
were accepted. That is the whole rate.

**Stop-early is demoted, not dropped.** Revision 1's "detect at round two and terminate"
would have made rolls 1, 4 and 5 fail forty minutes sooner. It does not touch the reason
they failed. #414 stays where the sweep put it, in 1.7's design queue.

---

## 2. The pack

### 2.1 The headline: the scaffold must not contradict itself — then the repair must act

**The two reads are done** — `docs/plans/1-6-4-reads.md`. In one line each: the repair
target on `nextjs_ts` is always the whole application (the named file is present, never
distinguished); and the frozen `lib/models.ts` the developer is told never to rewrite
declares the collection field as `string[]` while the floor demands objects.

**#1096 first.** `_ts_type` passes entity and shape names through, case-preserved, so
`list[Participant]` renders `Participant[]`; unknown primitives keep the `string` rule. Pin
it twice: a unit test on the function, and a completeness-style test that the generated
`models.ts` element kind for every `list[X]` field agrees with `derive_response_shape` for
the same manifest — the two derivations disagreed for the stack's whole life and nothing
noticed. It moves the generator hash, so it ships inside §2.2's pair.

Then three fixes on the loop, each with its own prediction in §3:

- **#1015 part A, as a narrowing.** The analyzer emits a structured `implicated_files` list
  beside its prose; #968's slice checks each entry against the source before it is trusted
  (the file exists; the failing test references it); the repair target is *narrowed* to the
  verified list ahead of package scoping and the #688 fallback — which, on this stack, is
  the only path that ever runs. A target derived from prose is the anti-pattern
  `correction_signature` bans, which is why part A was not built as filed.
- **#998 — name the empty round.** `completion_tokens == cap AND response_chars == 0` is
  a distinct signature from an empty response and has the opposite remedy. Record it on
  the emission evidence and on the `CORRECTION_COMPLETED` disclosure `a93240dc` already
  carries, so "converged in 3 after two empty emissions" also says *why* they were empty.
- **#1094 — fills must agree with the declared element kind.** The scaffold gate
  (`verification_scaffold_gate.py`) validates placement, imports, handler references and
  status assertions. It does not check that a fill's assertion on a `list[X]` field agrees
  with what the floor already pins for `X`. Roll 5's fill asserted strings on a field the
  manifest declares as objects; the floor and the fill contradicted each other inside one
  test, and the fill won because it ran second. Derive the finding from
  `derive_response_shape` — one derivation, now three renderings — and reject the fill at
  the gate, where #936/#967-class findings are already rejected.

**One instrumentation gap, recorded rather than fixed here.** LangFuse observation text is
capped at 10,000 characters (`telemetry/models.py:134`), and every develop prompt on this
stack is longer, so "what did the developer actually see" is unanswerable from stored state.
The reads got their answer from the 1,845 characters that survived. Raise the cap, or store
the render hash somewhere the artifact can point to, before the next set — or accept that
the next such question is unanswerable too.

### 2.2 The hash-movers ship together

**#1096** and **#1087** move the *generator* hash. **#1079's producer** moves the *contract* hash.

Landing them in one release means the hashes move **once**, and a 1.6.4 regression stays
attributable to the set rather than to an unlucky sequence. Landing them separately
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

### 2.3 The terminator is not the problem

**#435 fired in roll 5** — run report: `plan_defect: correction terminated at round 1 —
failure signature repeated from round 0, structural plan-change candidates on both
decisions`. "Round 1" after four decisions is the empty-emission refund doing its job. In
rolls 1 and 4 no exact repeat ever occurred, because each repair landed somewhere new and
moved the signature. A round-two terminator would have shortened all three rolls and
rescued none.

The set's association stands — 0–1 rounds → all accepted, 3–4 → all rejected — and the
honest caveat with it: "corrections make it worse" and "hard rolls need corrections and
are also likelier to fail" are indistinguishable in eight rolls. What §2.1 adds is that the
two hours spent in rounds that never worked were spent on rounds that never touched the
file, so the time is recovered by fixing targeting, not by giving up sooner. **#414 stays
in 1.7's design queue** where the sweep placed it.

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
| **P0** | The seeded frozen tree agrees with the floor: for every `list[X]` field in the authored manifest, the seeded `lib/models.ts` types it `X[]` — checked before the roll starts, no model in the loop (#1096) | a seeded `models.ts` that disagrees with the manifest, at N=1 |
| **P1** | No roll asserts on a non-`Run` table, because the handle does not exist (#1087) | any roll that does, or any rejection traceable to a phantom table |
| **P2** | Every contract probe carries a shape check, and a response-floor defect is caught by the audit as well as the suite (#1079) | a roll rejected on the response floor whose audit passes — the shape all three 1.6.3 reds took |
| **P3** | No repair candidate is rejected on fill assertions the floor contradicts — a fill disagreeing with the declared element kind is rejected at the gate before it can gate a repair (#1094) | a rejected candidate whose retest failed only on such a fill |
| **P4** | Every zero-character repair emission carries a named signature (cap-exhausted or empty), and the count is disclosed on the correction event (#998) | a zero-character emission recorded without one |
| **P5** | Every repair round's emission includes the file the correction decision named, or the round is recorded as failing to (#1015-A) | a red roll whose repair emissions never touched the file its decisions named |

Correction-round counts are **reported as texture**, against 1.6.3's 0/1/3/4 split, with
no prediction attached: §2.3 says why.

The rate is reported as a **secondary** against 5/8, with the same interval discipline §1.3
pre-registered last time and the same refusal to read significance into a small delta.

**The record for each rejection names the failing assertion's origin — spine or fill — and
the round it first appeared.** That is the field revision 1 lacked and the one that would
have caught its error before it was written down.

**Pre-registered early stop, and only in one direction.** If any of P0–P5 is falsified, the
fix did not work and the remaining rolls teach nothing about it — stop, record,
re-register. **A good result is never grounds to stop early**; that is cherry-picking, and
V7's "no re-rolls to improve the figure" rule carries over unchanged.

**N = 8**, for comparability with the 1.6.3 baseline. Same frozen-deploy discipline, same
§5.1 validity rules, same gate policy including §6.1's two-path handling, same freeze.

---

## 4. Sequencing

1. **The two reads** — done, `1-6-4-reads.md`.
2. **#1096 + #1087 + #1079 producer**, together, with the reference fixtures regenerated
   once. Regenerating a pinned fixture is an owner decision — propose the regen with the
   diff, do not fold it into the fix.
3. **#1015 part A with #968's slice**, **#998** detection, the **#1094** gate. All three
   are prompt-, evidence- or gate-side changes to a measured surface and are tested by the
   set.
4. **#1021 read** — no code until the mechanism is named.
5. **Re-register the set** against P0–P5; P0 is checked on the seeded tree before roll 1
   and again on every roll. Rebuild, verify LOADED in-container rather than built, freeze,
   record image ids.
6. **Two shakeouts are not automatic.** One is required because every item above changes
   squad-facing behaviour. A second only if the first finds something, per V7 §2.f's
   reasoning rather than as ritual.
7. **Cut 1.6.4 promptly off the set**, preserving the zero-drift property 1.6.3 achieved:
   the freeze means the tagged tree is the validated deploy, and that dies on the next
   merge.

---

## 5. What this plan does not decide

**Whether 1.6.4 is the last patch before 1.7.** That should be gated on the set's result,
not on this document. A run that satisfies P0–P5 with a rate at or above the baseline makes
the 1.6 line's claim — the squad authors the interface design and the release proves it was
won — and 1.7 opens for hardening. A run that falsifies a prediction means 1.6.5 re-measures.

**The August sweep's 1.6.x packs are not silently dropped.** Still open from its 1.6.4
pack: #772, #939, #668, #930, #901, #936; from its 1.6.2/1.6.3 packs: #933, #1022, #788,
#924, #927, #947, #969, #970, #994, #995, #999. None appeared as a loss mode in eight
rolls (roll 4's round-3 rewind discarded nothing correct, so it is not #994 evidence; the
qa emissions after each repair are retests, not #1054 misroutes). They go to the 1.7
re-derivation below with that fact recorded, not into a gap between a superseded sweep
and this plan. Three of them (#936, #933, #822) look closed-by-commit and should be
verified and closed rather than re-planned.

The 1.7 slate itself should be **re-derived before it opens**, using the dating method in
the preamble. It currently carries 39 open issues inherited from a sweep that has already
been shown stale twice.

---

## 6. Revision history

| rev | date | what changed | evidence |
|---|---|---|---|
| 1 | 2026-08-25 | Initial. Headline #1087 on the record's "2 of 3 rejections were false" | record §2–§3 as merged in PR #1088 |
| 4 | 2026-08-25 | Both reads done (`1-6-4-reads.md`). Read 2 found #1096 — `_ts_type` renders every entity reference as `string`, so the frozen `models.ts` contradicts the floor on every `nextjs_ts` roll; it is the headline and joins the hash-mover set. Read 1 withdrew rev 3's targeting guess: the target was the whole application every round (18/18 #688 fallbacks); #1015-A restated as a narrowing. P0 restated for #1096 (N=1, no model); the old P0 becomes P5. LangFuse 10k-char cap recorded as an instrumentation gap | runtime-api `correction_repair_target` log lines; LangFuse generation input for `task-run_6d6b25fe-m001-development.develop`; seeded `lib/models.ts` in rolls 1, 2, 4, 5; `stack_nextjs_ts.py:59` |
| 3 | 2026-08-25 | #1015 dated: B/C on the set's deploy (`4f631df7`), only A open and blocked on structured analyzer output. #435 shown to have fired in roll 5. Headline re-stated from the repair emission timelines: wrong file (rolls 1, 4), empty emission (rolls 1, 5), correct repair discarded by a contract-violating fill (roll 5) — the last filed as #1094. Stop-early demoted; #414 returns to 1.7. P0/P3/P4 restated; round counts become texture. Sweep leftovers extended to the 1.6.2/1.6.3 packs with what the rolls did and did not show | per-round emission timelines (artifact `created_at` + `role`), `repair_output.md` sizes, `run_report.md` failure reason, `correction_decision.md` rationales for the same three cycles |
| 2 | 2026-08-25 | Rolls 1 and 4 re-attributed: both failed the frozen response floor at every round; #1087 was a second failure, yield zero rolls. Headline moved to repair convergence on a correctly-diagnosed shape defect (§2.1). P0 added; the #435 lever's silence in roll 5 made a precondition of §2.3; harness `entities[0]` detail added to #1087; sweep leftovers dispositioned; #1089 corrected from "fixed" to "PR #1092 open" | per-round `test_report.md` and `failure_analysis.md` under `data/artifacts/group_run/` for `cyc_a24e4619844e`, `cyc_a38814afc16d`, `cyc_421d29473f86`; record §6 |
