# 1.8.0 verification set — pre-registration (plan §7 step 8)

**Status:** DRAFT for the owner's approval — committed on the frozen deploy before any diagnostic
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
| Deploy — commit | **`2356c079`** — main after the shakeout loop's last fix (#1584). A label, not an assertion (#1296): the image ids are the assertion |
| Deploy — image ids | `runtime-api` **`4b950e964602`**, `max` **`ffa77a2cc779`**, `neo` **`013f0ef28813`**, `nat` **`d8f4a648f63a`**, `bob` **`db271648015e`**, `eve` **`713312f65991`**, `data` **`ec9700321fda`** — deploy E, live 2026-09-15 18:07 ET, backup `squadops-20260915T220605Z.dump` |
| Loaded, not built | Verified per container as a live call with its paired control at each deploy (`verify_C/D/E_loaded`): SIP-0107 §46k–§46p (the revision form, the scoped output contract, the shown files with the fence-aware renderer, fragment anchors, the replaced span, fill-mode anchorable files), #1581's unanimity rule, and the prelude's surfaces the set configs carry |
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

**Rounds taken: four. Budget: four (plan rev 8; three before it).** Rounds attributable to the
headlines: pairs 1 and 3 (the scoped-repair contract and its instrument); pair 2's routing defect
predates them and was made legible by them. Records: `var/verification_sets/1-8-0-fastapi-react/`
and `1-8-0-nextjs/`, `shakeout-2026091{5,6}T*.md`.

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

## 9. Drift the record must declare

**Intended zero** — the tag is the measured deploy plus this pre-registration, the diagnostic
configs, the records, the baseline and the package.

**One difference exists already and is named here.** The images were built from `2356c079`, and
that is what `frozen_deploy_commit` carries. The driver runs from a checkout at main, which is
ahead of `2356c079` by this document, the eight diagnostic configs, the pinned set configs and plan
rev 9 — `git diff 2356c079..HEAD -- src/ adapters/` is **empty**, the condition the driver's own
framework-drift check enforces on every counting roll. Docs-only, therefore additive.

## 10. Diagnostic readings — appended as they land

_(none yet)_
