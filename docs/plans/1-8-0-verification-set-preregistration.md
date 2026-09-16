# 1.8.0 verification set — pre-registration (plan §7 step 8)

**Status:** rev 10 (2026-09-16) — re-pinned on **deploy F** after the deploy-E set re-opened the shakeout loop (§2, §6, §10). Committed on the frozen deploy before any diagnostic
launches. Once merged, the cut criteria do not move (plan §7 step 8); only diagnostic readings are
appended. If the deploy moves after this commit, the commit is void and re-made, and no
transaction from the superseded deploy counts toward N.

**What this set measures.** The 1.8.0 headlines on one frozen deploy: **Scoped Code Revision**
(SIP-0107, steps 1–6 built; step 7, the flip, is 1.8.1's by §46a) and the **Cycle Evaluation
Scorecard slice** (SIP-0108 (a)–(c); (d) is 1.8.1's by plan rev 7). The bar is L1. The
experimental gate is SIP-0107 §39.8's two readings — all-attempt integrity and N successful
scoped transactions — read per cell, plus the #598 prediction and every registered diagnostic
reaching its seam (plan §3.9).

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| Counted rolls | **6** on FastAPI+React (§4) and **3** on Next.js+TS (§5) — the fifth consecutive set at that size (1.7.2 → 1.8.0) on one PRD and two stacks |
| Bar | **one: L1** (#1268) — blocking on a counted roll whose contentless emission is *not recovered*; the count tracked and never quoted as zero |
| **N** (SIP-0107 §39.8) | **6 successful scoped revision transactions across the counted rolls and the diagnostics together, with at least one in each required cell** — qa × React, qa × Next.js, dev × React, dev × Next.js (§3c). Fixed here, before any transaction that could count is observed |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 → 1.7.5 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React **`3921c5a62106`**, Next.js+TS **`33cadf53688e`** — observed on every shakeout of every deploy of this line (A through E), unchanged from 1.7.5 |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` — the Postgres-seeded `full-38` (#1568), observed on both arms of pair 4 and identical to the 1.7.5 pin; the driver refuses a counting roll on any other (#1571) |
| Deploy — commit | **`969cd44e`** — main after the six fixes the deploy-E set found (#1590, #1591, #1592, #1593, #1595, #1597; rev 10). Deploy E, `2356c079`, ran the set recorded in §10a–§10b. A label, not an assertion (#1296): the image ids are the assertion |
| Deploy — image ids | `runtime-api` **`b3278c26dd25`**, `max` **`36cc6eb9a923`**, `neo` **`07498c2a4a94`**, `nat` **`1ddf151647c0`**, `bob` **`b59711b8f653`**, `eve` **`14d15dc8e3f7`**, `data` **`9a41965b25ad`** (deploy F, 18:53 ET 2026-09-16; deploy E's were `4b950e964602`, `ffa77a2cc779`, `013f0ef28813`, `d8f4a648f63a`, `db271648015e`, `713312f65991`, `ec9700321fda`) — deploy E, live 2026-09-15 18:07 ET, backup `squadops-20260915T220605Z.dump` |
| Loaded, not built | Verified per container as a live call with its paired control at each deploy (`verify_C/D/E/F_loaded`; F reads the six fixes from the loaded modules of `runtime-api`, `eve`, `neo` and `bob` — the verifier's escape, the refund branch, the namespace validator and the basename reader, the suite-side token, and a caret-anchored `regex_match` evaluated live on a heading below the first line): SIP-0107 §46k–§46p (the revision form, the scoped output contract, the shown files with the fence-aware renderer, fragment anchors, the replaced span, fill-mode anchorable files), #1581's unanimity rule, and the prelude's surfaces the set configs carry |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-8-0-<arm>.yaml --roll N` — one roll per invocation; diagnostics via `shakeout --set …-diagnostic-*.yaml` |
| Order | **The eight diagnostics first** (plan §7 step 9, two-run budget each), then FastAPI+React rolls 1–6, then Next.js+TS rolls 1–3 |

---

## 2. Preconditions and the shakeout log

Six deploys and five pairs brought the line here. Every pair's finding became a fix the next
deploy carried, and the last pair found nothing new.

| deploy | commit | pair | React | Next.js | finding → fix |
|---|---|---|---|---|---|
| A (prelude) | `f9a5344e` | checkpoint | `cyc_830f4b5698c2` accepted | `cyc_79f70a0bbac1` **rejected** on an unchanged suite | #1532 #1533 #1534 #1535 #1540 → five fixes (deploy A′) |
| A′ | `1b27a32c` | checkpoint | `cyc_f04993da75dd` accepted, 0 rounds | `cyc_b0e4cdecc36d` accepted, 0 rounds | clean — the fixes not exercised |
| B (headlines) | `9547e310` | 1 | `cyc_b2cca1138e15` accepted, 0 rounds | `cyc_e62d74598211` accepted, 1 round: a one-line dev repair came back as a **whole file** | the repair prompt contradicted the edit form and never showed the file (#1576) → #1574 #1575 #1577 #1578 #1579 |
| C | `de4f6861` | 2 | `cyc_24746bb1091e` accepted, 1 round: a qa-attributed test defect **routed to the dev**, whose correct refusal read as an empty emission | `cyc_95323272a17e` accepted, 0 rounds | #1581 → #1582 (routing); the dispute half is SIP-0096 §17a, 1.8.1's |
| D | `0d0e8f41` | 3 | `cyc_c815dbbd832b` accepted, 1 round: #1582 routed to qa; an anchored edit applied and was verified, the retest refused a wrong router API, the patch was discarded | `cyc_95c0e2dbb25c` accepted, 1 round: #1582 routed to qa; the fill repair **re-emitted the free-authored suite whole**, unread as whole-file | #1583 → #1584 (fill-mode anchorable files; unoffered whole re-emission read) |
| **E** | **`2356c079`** | **4** | `cyc_930df0dbb13c` accepted, 1 round: **the first successful scoped transaction in a live cycle** — one anchored edit, 3% of the file, verified, retest passed, identity held | `cyc_2b8da9f82ed7` accepted, 0 rounds | **none — exit** |

| **E (the set)** | `2356c079` | the counted set | diagnostics 8/8 seams, two on run 2 (#1586, #1587); rolls 1–4 accepted and functional; **5 and 6 rejected — both false rejections of the framework's own making** (#1594; #1596 over #1598) | 3/3 accepted, 0 rounds | seven findings → six fixes (#1590, #1591, #1592, #1593, #1595, #1597) → **deploy F** (rev 10) |

**Rounds taken: four. Budget: four (plan rev 8; three before it).** Rounds attributable to the
headlines: pairs 1 and 3 (the scoped-repair contract and its instrument); pair 2's routing defect
predates them and was made legible by them. Records: `var/verification_sets/1-8-0-fastapi-react/`
and `1-8-0-nextjs/`, `shakeout-2026091{5,6}T*.md`.

**Rev 10 (2026-09-16).** The exit rule was met at pair 4, and the counted set on deploy E re-opened
the loop: seven latent seams, every one surfaced by plan-author variance the framework accepted at
one seam and disowned at another — no typed row on the qa task (#1586), a suite at a directory the
stack's namespace does not own (#1587), an empty repair verified and retested (#1589), a seam read
without asking whether its fault applied (#1588), a caret-anchored regex the evaluator could never
match (#1594), a `verification` label the token list did not read (#1596), and a harness that seeds
no store isolation while the plan hint says it does (#1598, the owner's ruling, not fixed here). Under
the cut rule that the shakeout is a loop with an exit rule, **the set restarts on deploy F**, which
carries the six fixes; the E set stands in §10a–§10b as evidence and is not the cut's set. The E
arm's two rejections are attributed to the framework, not the squad, each by replay (§10b).

**The readiness probe that preceded deploy C** (`var/probes/2026-09-15-scoped-repair-readiness-v2/`,
gitignored; SIP-0107 §46m): the real repair handler in the dev agent's image against the live
model, three real failed repairs, 24 trials with the typed checks executing. With the file shown,
the React repair was a 5% edit in 25 seconds; with it hidden, a 93% blind structural rewrite in
two minutes — both legal, both passing the signature check, both "successful scoped transactions"
to §39.8 until #1579 put the replaced span on the record. That reading is why §3c carries a
ceiling.

---

## 3. The exercise plan — stated before the first diagnostic

### 3a. The bar

| id | claim | blocking on | typed field |
|---|---|---|---|
| **L1** (#1268) | the loop remains able to produce a valid running result — a counted roll whose contentless emission is **not recovered** breaches it | every counted roll | `loop_texture.contentless_emissions`, the count beside the recovered flag |

### 3b. The live predictions

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **All-attempt integrity** (SIP-0107 §39.8, first reading) — across every attempted transaction, counted rolls and diagnostics together, successful or refused: zero outside-grant changes, post-verification drops, verified/persisted identity mismatches, preservation violations (by reconstruction), partial acceptances, over-ceiling regrants, and zero restorations on a successful scoped transaction; **unauthorized whole-file responses reported as a count per cell, not a violation** (§46a) — offered and unoffered alike (§46p) | the per-repair `repair_revision_form` line and the `anchored_edit_transaction` line in the repairing role's container; `patch_candidate_identity` at acceptance; the driver's `loop_texture.repair_revision_forms` and `candidate_identities` | one of the defect classes on any transaction | that the contract holds where it was exercised — on this deploy, these stacks, these lanes — and nothing about repairs no roll or diagnostic produced |
| **Success-path readiness** (§39.8, second reading) — at least **N = 6** successful scoped transactions, at least one per required cell (§3c) | the sum of §3c's counting rule over counted rolls and diagnostics | fewer than 6, or a required cell at zero | that a scoped repair can be produced on demand in every lane the flip will govern |
| **The rendered packaging** (#598): zero `container_packaging` findings on the accepted emission of every counted roll; the builder emits only `assembly_notes.md` | the check's rows per roll; the builder's emission log | one finding on an accepted emission, or a builder-authored Dockerfile | that the rendering is what the boot audit builds |

**An unmet N blocks the cut** (plan §3.9): in the SIP it holds back the flip; here it also fails
the experimental gate. A falsified prediction or an unreached seam stops the set and the plan is
revised in the open, not amended after.

### 3c. N — the definition, the cells, the supply, and three counting rules

**A successful transaction** (§39.8): resolved inside its grant, composed, passed its preservation
proof (§17), **verified, and persisted under the identity it was verified with** (§20). A
transaction refused, failed closed, or whose repair failed patch verification or the retest adds
nothing. Pair 3's React anchored edit — applied, verified, retest failed — is the shape that does
not count; pair 4's React edit — applied, verified, retest passed, identity held — is the shape
that does.

**Required cells and their supply.** Seven of nine 1.7.5 counted rolls took zero correction
rounds; this line's five pairs took four rounds in ten cycles, all on the qa suite's failure. So
counted rolls supply little, and the diagnostics supply the rest, by design (plan §4.1).

| cell | forcing fault (diagnostic) | what the repair revises | expected successful transactions | counted-roll expectation |
|---|---|---|---|---|
| **dev × React** | `dev_join_response_omits_declared_fields` (`dev-lane-fastapi-react`) | the join handler in `backend/routes.py` — a structural `function:` entity or an anchored edit | 1–2 (two-run budget) | ~1 across six rolls (pair 4: one in four shakeouts) |
| **dev × Next.js** | `dev_join_response_omits_declared_fields` (`dev-lane-nextjs`) | the join handler in `app/api/runs/[run_id]/join/route.ts` — `function:POST#try` or an anchored edit | 1–2 | ~0 across three rolls (no dev round in six Next.js shakeouts) |
| **qa × React** | `qa_suite_own_frame_failure` + `repair_prose_only` (`own-frame-then-prose-repair`) | the qa suite the fault broke — an anchored edit on the existing file | 1–2 (the second repair, after the prose one is refunded) | ~1–2 across six rolls (pairs 2, 3, 4 each had a qa-suite round; #1582 now routes them to qa) |
| **qa × Next.js** | the same diagnostic in fill mode; and every counted roll's qa round | the scaffold shells by **fill** (§9.3 region) and, since #1584, the free-authored suite by anchored edit | 1–2 | ~1 across three rolls (pair 3's fill repair was accepted and persisted) |
| builder × React | `builder_emission_contentless_all_attempts` (F1) | `assembly_notes.md` by `builder.assemble_repair` — a Markdown file, anchored edits only | 0–1 — **declared, not required** | none (the builder emits only notes, #598) |
| builder × Next.js | — | — | **unaskable**: no forcing fault is registered on this stack's builder, and #598 leaves it nothing to revise but `assembly_notes.md` | none |

Expected total 5–10 against **N = 6**. The number is chosen so that a clean run of the eight
diagnostics meets it with the counted rolls as margin, and a required cell at zero — the most
likely miss is dev × Next.js — fails it regardless of the total, which is the coverage §39.8
demands.

**Three counting rules, fixed here.**

1. **A qa repair in fill mode counts as a §9.3 region transaction** when the merged shells are
   accepted and persisted under the identity they were verified with. It does not run through
   `RevisionTransaction`, so its integrity evidence is the fill-merge record (`fill_merge_evidence`:
   `dropped_shell_rewrites` zero, `misaddressed` zero, `additive_containment` held) in place of the
   transaction record. Without this rule the qa × Next.js cell cannot be met by construction: every
   scaffold-bound qa repair fills. The record reports fill transactions in their own column.
2. **A successful transaction that replaced more than half of its file's characters is a scoped
   rewrite and does not count toward N.** It is reported per cell in its own column. The
   readiness probe produced 93% structural rewrites that passed every check; the flip's
   precondition is evidence that repairs are repairs. The threshold is the `replaced.pct` the
   revision form carries (§46o); a whole-file response is 100 by definition.
3. **Every transaction is read against the round that produced it**, not in isolation: the
   `repair_revision_form` line names the form offered, the form taken, the modes, the replaced
   span per file and the fragment-anchor count; the record's per-cell table carries every one of
   those columns, so the sum against N and the texture behind it come from the same rows.

### 3d. The seam invariants — proven on the pinned deploy, two-run budget each

Eight diagnostics (plan §4.1 said seven; the dev-lane fault runs on **both** stacks because dev ×
Next.js is a required cell with no other supply — plan rev 9). Each runs the roll's own path with
the fault injected in the producing role's container (#1251); the driver refuses to count one.

| diagnostic | fault(s) | invariant | readout | N cell |
|---|---|---|---|---|
| `absent-suite` | `qa_suite_absent` | **L2** (#1269) — a repair that supplies the suite an emission failure lacked is retested; the #1406 untouched-file rule rides it | "repair-retest seam reached" | none — the suite is new, not revised |
| `own-frame-then-prose-repair` | `qa_suite_own_frame_failure`, `repair_prose_only` | **L7** (#1270) routes to `qa.test_repair`; **L4** (#1273) a prose-only repair is refunded, not verified; **L5** the re-take is briefed | the locus line, the refund line, the second repair's revision form | qa × React |
| `path-prefix` | `qa_suite_at_path_prefix` | **L8b** (#1311) — no emission lands under a literal `path/` prefix | the extractor's strip count and the stored names | none |
| `absent-suite-then-false-claim` | `qa_suite_absent`, `analyzer_false_source_claim` | **A1** (#968) — the decision does not inherit an analyzer claim the workspace refutes | `decision_inherited_claims` beside `analyzer_claims` | none |
| `contentless-builder` | `builder_emission_contentless` | **R1** (#1372) — retried with its fact, not blind | `retried_with_fact` | none |
| `contentless-builder-all-attempts` | `builder_emission_contentless_all_attempts` | **F1** (#1374) — no false corrected result composed; `builder.assemble_repair` reached | the re-derived required_files line; the repair's revision form | builder × React (declared) |
| `dev-lane-fastapi-react` | `dev_join_response_omits_declared_fields` | **the dev lane** (SIP-0107 step 3, the dev grant) — a probe failure on a developer-owned route is repaired by a development repair aimed at the probe-owned slot, inside its grant | the locus and target lines; the dev repair's revision form; the retest | **dev × React** |
| `dev-lane-nextjs` | `dev_join_response_omits_declared_fields` | the same, on the App Router stack — `function:POST#try` keeps the signature and the catch envelope by construction (§46j) | as above | **dev × Next.js** |

**A seam not reached after two runs stops the set.** Each config's `loaded_checks` asserts the
seam's presence on the deployed image before the run, with a control.

### 3d′. Deploy F — one mechanism prediction per fix (rev 10)

Each fix is read where its mechanism shows, never as a rate. Two are exercised by a diagnostic on
every run of this set; the others by the counted rolls only when plan-author variance produces the
shape again, and the record says which it was.

| fix | mechanism predicted | read from |
|---|---|---|
| #1590 (#1586) | a qa suite repair for an emission failure is retested whether or not the plan attached a typed row to the qa task; `no_typed_criteria` never terminates a qa-suite round | `absent-suite`: `patch_retest` follows the qa repair on every run; `correction_terminated_unverifiable` absent |
| #1591 (#1589) | a refunded round shows no `patch_verification` and no retest; the next attempt is told the repair emitted no content | `own-frame-then-prose-repair`: round 0 after the prose-only fault |
| #1592 (#1587) | a plan declaring a qa suite outside the stack's qa namespace is re-rolled once with the reason; on React the backend suite lands under `backend/tests/` | every React plan; `framing_rerolls` names `validate_qa_suite_namespace` when it fires — **watch the first roll's re-roll count** |
| #1593 (#1588) | every diagnostic record carries `faults_applied`; a seam whose fault never applied reads UNASKABLE, never YES or NO; L4 reads the refund of the faulted round only | every diagnostic record (reporting-only) |
| #1595 (#1594) | a caret-anchored heading regex on a document passes when the heading is below the first line | **replay-verified** on roll 5's own notes (the check's regression test) and live in `verify_F_loaded`; exercised by a counted roll only if a plan author anchors a pattern again — named as a replay, not a live reading |
| #1597 (#1596) | a round whose analyzer names only the suite and whose lead labels it `test` / `verification` routes to the qa repair | any counted round of that shape; not forced by a diagnostic |

### 3e. CI invariants, read live as texture

The rewind invariant (W1), the locus invariant (D1, now with #1581's unanimity rule beside
#1054's dispute rule), the derived-rows invariant (F1), the untouched-file rule (#1406), the #1501
carried-signature rule.

### 3f. Texture — observed, never blocking, every field with its unaskable state declared

Per repair, from the revision form (§46k–§46p): the files offered with their entity counts; the
form taken; the modes; the replaced span per file; fragment anchors; whole-file responses offered
and unoffered; refusals and retries. Per round: the locus line and which rule chose it; the
termination reason; the carried, cleared and added signature counts. Per roll: emitted bytes and
tokens per repair against the 1.7.5 whole-file figures; correction rounds; framing-run verdicts;
fill-mode completion tokens; `container_packaging` rows; the three #80 lineage fields; a
`run_loop_summaries` row per run; the `CycleAssessment` on every record with its attribution id
(SIP-0108 §4.1–4.2) — texture here, the evidence gate's subject in plan §3.9. **Unauthorized
whole-file responses per cell** are the count 1.8.1's flip replays from.

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — the measurement, six rolls

Config `docs/plans/verification-sets/1-8-0-fastapi-react.yaml`, pinned to deploy E. The driver
records `launch_notes` "COUNTED roll N of 6" on each; the benchmark registry (#1563) reads it.

## 5. Next.js+TS (`nextjs_ts`) — three rolls

Config `docs/plans/verification-sets/1-8-0-nextjs.yaml`, pinned to deploy E, the stack overrides
carried in the config. Three rolls, as in 1.7.2 → 1.7.5.

## 6. The shakeout loop and its exit

Deploy A got one checkpoint pair and a second on A′. Deploy B entered the loop — exit on a pair
with no new seam finding — and it took **four rounds** against a budget of three, raised to four
by plan rev 8 when pair 3's finding arrived with the budget spent (§2). Pair 4 on deploy E
produced no new seam finding in either arm. A fourth finding would have stopped the loop for a
plan revision, not a fifth pair; none came.

**Round five (rev 10): the counted set on E.** The pairs found nothing; the set found seven latent
seams (§2). The loop restarts on deploy F with the same eight diagnostics first — they exercise the
seams the fixes change (§3d′) and are this deploy's shakeout; no separate pair precedes them. The
exit is unchanged: a diagnostic that misses its seam twice stops the set; a rejected roll is a result.

**Early stop, one direction.** A falsified prediction or an unreached seam stops the set; a good
result never stops it early; a stop in one arm does not stop the other.

## 7. Gate constant

Inherited verbatim (1.6.3 §6); carried in each set config's `gate_notes` and applied identically
to every roll and every diagnostic.

## 8. Prohibited while open

Inherited verbatim. **Nothing merges to main between the first diagnostic launch and the last
counted roll** — the launch checkout's HEAD is pinned at the first launch, and a commit on that
branch voids the pin. Diagnostic readings are appended to this document's §10 as they land; the
cut criteria above do not move.

The E set closed at 16:24 ET on 2026-09-16; the six fix PRs and this revision merged after it and
before the F launch, which is where the prohibition re-opens.

## 9. Drift the record must declare

**Intended zero** — the tag is the measured deploy plus this pre-registration, the diagnostic
configs, the records, the baseline and the package.

**One difference exists already and is named here.** The images were built from `969cd44e`, and
that is what `frozen_deploy_commit` carries. The driver runs from a checkout at main, which is
ahead of `969cd44e` by this revision and the re-pinned set configs — `git diff 969cd44e..HEAD --
src/ adapters/` is **empty**, the condition the driver's own framework-drift check enforces on every
counting roll. Docs-only, therefore additive. (Rev 9's statement of the same shape for `2356c079`
held through the E set.)

## 10. Diagnostic readings — appended as they land

### 10a. Deploy E — the eight diagnostics (2026-09-15 23:28 → 2026-09-16 08:32 ET)

| diagnostic | run | cycle | verdict | rounds | seam |
|---|---|---|---|---|---|
| `absent-suite` | 1 | `cyc_53d6ff52c989` | blocked_unverified | 1 | L2 **NO** — the plan attached no typed row to the qa task; the repair that supplied the suite was refused `no_typed_criteria` and the round terminated (#1586) |
| `absent-suite` | 2 | `cyc_547a34c8c037` | accepted | 1 | L2 **YES** — one typed row on the plan; retest ran |
| `own-frame-then-prose-repair` | 1 | `cyc_eee9b62e6a4f` | accepted | 1 | L7 **NO** — the fault bit a pytest suite at the root `tests/`, outside the stack's qa namespace; routed to the dev (#1587). L4 read YES by the driver **and is corrected here to UNASKABLE**: the prose-only fault never applied because no qa repair ran; the refund it read was the dev's (#1588) |
| `own-frame-then-prose-repair` | 2 | `cyc_44535c62fbe0` | accepted | 2 | L7 **YES**, L4 **YES** — suites under `backend/tests/` and `frontend/src/__tests__/`; both faults applied; both qa repairs refunded |
| `path-prefix` | 1 | `cyc_a466aa7690bb` | accepted | 0 | L8b **YES** |
| `absent-suite-then-false-claim` | 1 | `cyc_0d319c3f68f3` | accepted | 1 | L2 **YES**, A1 **YES** |
| `contentless-builder` | 1 | `cyc_1417b1f9cfaf` | accepted | 0 | R1 **YES** |
| `contentless-builder-all-attempts` | 1 | `cyc_1189dc498ac5` | accepted | 2 | F1 **YES** — the first deploy on which F1 was reachable |
| `dev-lane-fastapi-react` | 1 | `cyc_717f0bb0efcf` | accepted | 1 | **YES** — dev anchored edit on `backend/routes.py`, 122 of 3,826 chars (3%), verified 8 checks, retest passed, identity held |
| `dev-lane-nextjs` | 1 | `cyc_b6a4ba977d5e` | accepted | 2 | **YES** — dev anchored edits on `app/api/runs/[run_id]/join/route.ts`, 203 of 1,355 chars (15%), first retest failed, second passed, identity held |

Eight of eight seams reached inside the two-run budget; the two run-1 misses are #1586 and #1587,
each with its run-2 control on the same deploy. During the own-frame run 1, the refund fell through
to a verification and a retest of the empty patch (#1589).

### 10b. Deploy E — the counted arm (recorded; not the cut's set)

| arm | roll | cycle | verdict | rounds | reading |
|---|---|---|---|---|---|
| React | 1 | `cyc_9fd0990f1912` | accepted, functional | 0 | clean |
| React | 2 | `cyc_0b545fbf8997` | accepted, functional | 0 | clean |
| React | 3 | `cyc_83934970bdba` | accepted, functional | 1 | **qa × React cell**: anchored edit on `frontend/src/__tests__/runs.test.jsx`, 533 of 7,823 chars (7%), verified 10 checks, retest passed, identity held; routed by #1582's unanimity branch |
| React | 4 | `cyc_7599ed9ef73b` | accepted, functional | 0 | clean |
| React | 5 | `cyc_7998e63be37f` | **rejected** (blocked_unverified) | 3 | **framework**: two plan-authored `^`-anchored `regex_match` rows on `assembly_notes.md` could never match below the title line — the notes carried both headings in every version (replayed on the three stored copies) (#1594) |
| React | 6 | `cyc_767ad2dc59d2` | **rejected** | 2 | **framework over a qa suite defect**: the suite assumed a harness reset the seeded conftest does not provide (#1598); the analyzer named only the suite, the lead labelled it `test`, `verification`, and the router abstained on the second label and sent it to the dev (#1596), who refused in prose |
| Next.js | 1 | `cyc_7529a4eb8f1f` | accepted, functional | 0 | clean |
| Next.js | 2 | `cyc_11a72c6842dc` | accepted, functional | 0 | clean |
| Next.js | 3 | `cyc_c2cae2841022` | accepted, functional | 0 | clean |

React 4 of 6, Next.js 3 of 3. One counted cell filled (qa × React); every other accepted roll
needed no repair, so the dev cells rest on the two dev-lane diagnostics — a clean squad gives the
scoped-revision instrument nothing to measure, which is why the diagnostics carry the dev lane by
design (§3c supply table). L1 held: no counted roll blocked on an unrecovered contentless emission.

### 10c. Deploy F — appended as they land

_(none yet)_
