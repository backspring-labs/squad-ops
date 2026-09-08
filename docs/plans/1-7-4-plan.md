# 1.7.4 — plan

**Revision 1, 2026-09-07.** Written the evening the 1.7.3 line closed, from the 1.7.3 plan (rev 4
§6, §8, §9), the 1.7.3 record (`docs/plans/1-7-3-verification-set-record.md` §0, §5, §8), the
1.7.2 plan §8/§8a and record §8, the 1.7.0 plan §3.1 (as amended by the 1.7.3 plan) and §6.2,
the ROADMAP's 1.7 identity, and the issues the 1.7.3 line filed and placed here (#1369, #1372,
#1373, #1374). **This plan is about one thing: the loop's second half — what a cycle does after
a failure, made true at the three seams the last two lines caught lying** — with the
infrastructure rider at the quota beside it, kept out of the measurement's way. It is the last
behavioural line of 1.7; 1.7.5 closes the line with Composition Root and the deferrals.

Two rules carried from 1.7.3 without discount: **a measured pack and a rider do not land on one
deploy without a checkpoint between them**, and **every readout must have a producer before
the set opens, checked against a real record**.

---

## 1. What the 1.7.3 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| the builder's short first emission is the loop's live rejection cause: two of six counted React rolls began with a Dockerfile-only emission of 373 and 642 tokens (normal 1,391–2,382); one recovered, one did not; with the two shakeouts and the void roll, four of the last nine React builder first emissions on the line were short, at the same prompt size | 1.7.3 record §1.1, §5 | **#1312 with #1254 leads, as the 1.7.3 plan §6 placed it**, and the record's rate is its baseline: 1.7.2 saw one in seven, 1.7.3 two in six counted. The builder's repair also emitted ten unaddressed fences on roll 1 — the same emission-shape class from the repair side |
| two void counted rolls in two lines on one mechanism: the accepted-patch path composes a corrected result from whatever rows an earlier stage happened to write, and #1318 then #1364 each patched one gate | 1.7.2 record §0; 1.7.3 record §0, §4.1 | **#1374**: every framework row a task's contract declares is derived from the patched set by contract. Design first, then the fix, then a fault that exercises it — a contentless builder attempt has no fault today and was reached only by chance |
| the one contentless emission of the line was the builder's, and the builder has no emission-retry path; the qa retry re-rolls blind | 1.7.3 record §0, §2 | **#1372**, the retry-with-fact backstop 1.7.2 §8a named and did not build: one mechanism for every producer, read as a new texture field |
| the shakeout loop reported as two numbers: three pairs, zero attributable to the sixteen items; every supersede came from the instrument or the loop's own accounting; two readouts had been wrong for a whole line (the kind gate, the pytest own-frame fault) | 1.7.3 record §0 | the instrument is proven on its own deploy before the pack's first PR (§7), and **a readout that cannot see its own miss is a finding** (1.7.2 §7) — §4 asks that question of every new prediction before roll 1 |
| main's integration job was red for six merges before it was read — not a required check | 1.7.3 record §4.6 | **`integration` becomes a required check** (§3.1) — the one workflow line that turns a process rule into a mechanism |
| #1285's producer exists (#1334); the reading: qa emissions cost ~10.2k completion tokens each in fill mode (Next.js) against ~5.8k on React, reasoning characters in the same ratio, `reasoning_tokens` unreported on every one | 1.7.3 record §5, §8 | the fill-mode cost is visible and roughly double; whether it is *material* is §8's decision — built here if so |
| B1 was read by hand: a grep over 43 stored suites, because the driver produced no field for it | 1.7.3 record §2 | a declared readout with no producer is the #1285 shape again; **B1 gets a driver field** before this set opens (§3.1) |
| the release package's cycle count was the number of `--cycle` flags typed; the script labels in-place SIP amendments as moves and lists a PR twice | #1369; 1.7.3 cut | the rider carries #1369; the cut procedure in CLAUDE.md names the full cycle list as step 7's input |

---

## 2. Why this line, on the roadmap

- **The 1.7 identity has a loop half.** "Every port is actually a port" is 1.7.3's and 1.7.5's;
  the 1.7.0 plan §3.1 split Loop Honesty across 1.7.2 and this line because the recovery path
  is the part of the framework the 1.8 scorecard grades most directly — a grade over
  `CycleOutcome` is a grade over what the loop reported, and two lines have now shown the loop
  reporting a booting app as a failure.
- **The handoff is the design fault the last eight issues were symptoms of.** #1312's ruling
  (2026-09-05) names it: a required file with no consumer generates assertors, the assertors
  disagree, and every fix moves the disagreement. Removing the requirement removes the class.
- **1.8 needs the emission shape settled.** The Slot-Scoped Emission draft (PR #1325) subsumes
  the file-as-unit problems this line and the last one patched (#1323, #1350, #1351, the
  unaddressed repair fences); its design review is scheduled to start during this line (§7) so
  1.8.0 opens with an accepted design rather than a draft.

**What it does not do, stated here rather than implied.** It does not touch the boundaries
(1.7.3 shipped them; 1.7.5 closes them). It does not build Composition Root (#301, 1.7.5). It
does not adopt Atlas (SIP-0106 stays accepted and not adopted until #301). It does not change
the reasoning budget (1.7.0's), the stack seams (1.7.1's) or the recovery-path seams 1.7.2
shipped, except where §3.2 says a seam lied.

---

## 3. The content

### 3.1 Preconditions — before the pack's first PR

| item | what | verified by |
|---|---|---|
| **`integration` required** | `.github` branch protection lists the integration job beside the three required checks; a red integration job blocks a merge | the next PR with a red integration job cannot merge; recorded in CLAUDE.md's merge rule |
| **B1 producer** | the driver reads the stored qa suites against the manifest's root-persisted entities into a `non_root_fixture_tables` texture field, so B1 is a record field rather than a grep | driver test on the 1.7.3 roll records (43 suites, zero mentions) |
| **a contentless-builder fault** | `builder_emission_contentless` in `FAULTS` (scope `first_attempt`, target `builder.assemble`), with a `seam_readouts` entry that reads the corrected result's framework rows — the #1364 shape becomes exercisable rather than a chance event | fault tests; the guard that every fault has a readout |
| **`retried_with_fact` producer** | the driver reads the emission-retry feedback lines for the fact (#1372's readout), so the prediction has a field before the fix exists | driver test on a synthetic line |
| **#1369** | the package script reads a SIP's status transition, not its path in the diff; the PR table de-duplicated | script tests; the v1.7.3 package re-rendered as a check, not re-committed |

The fault and the two producers are instrument; they ship first and are proven on a deploy built
before the pack's first PR (§7), as 1.7.3 did with deploy A — the instrument rounds are counted
apart from the shakeout rounds.

### 3.2 The pack, in merge order — measured, roll-verified

| # | item | what | prediction (§4) |
|---|---|---|---|
| 1 | **#1312 with #1254** | `qa_handoff.md` stops being required. The builder's deliverable is an optional `assembly_notes.md` defined by exclusion from the stack's declared surfaces — the "already supplied, do not restate" list rendered from `EnvironmentContract.operation_commands`, `app_invocation_for`, `qa_test_namespace` and the manifest, one asset, derived content; both check surfaces go (`required_files` on the handoff, the planner's `regex_match`/`sections_present` family, #1254's doubled `harness_boundary`); `qa_test.py` gains a seventh, presence-keyed appendix that carries the notes when they exist; a derived guard over `_STACKS` asserts the rendered exclusion list equals each stack's declarations. **The mirror rule on removal:** the 1.7.3 record says what consumed the handoff — nothing — and the PR's Evidence names every check row that disappears and who read it | **H1**, **H2** |
| 2 | **#1374** | the accepted-patch path derives every framework row the task's contract declares from the patched set (`required_files`, `tests_pass` via the retest, `frontend_build`, the two suite-integrity rows) and supersedes the failed attempt's; the seam table in the PR names which stage's rule derives each row and on which tree | **F1** |
| 3 | **#1372** | a contentless emission's retry carries its own emission-shape fact and the task's expected artifacts, at the shared emission seam, for every producer | **R1** |
| 4 | **#994** | a rewind after a successful correction repair does not re-dispatch the task and discard the repaired state | **W1** |
| 5 | **#995** | a task timeout mid self-eval banks the attempt's real history, not "zero response chars" | **T1** (texture until exercised) |
| 6 | **#968** | the failure analyzer's factual claims about source are checked against the source before the correction decision inherits them | **A1** |
| 7 | **#1054** | a correction decision naming dev task types dispatches a dev repair — the locus classifier's conservative default is read against the decision's own `affected_task_types` | **D1** |
| 8 | **#1070** | the plan's restatement of `success_status` collapsed; the manifest's field is the one copy | CI (goldens); no prediction |
| 9 | **#936 / #933** | verify-then-close against the tree — both were fill-mode window blockers whose fixes may already have landed with SIP-0104's later phases | CI; no prediction |
| 10 | **#1285** | *if §8 rules the fill-mode cost material*: the qa task's two output shapes get two reasoning declarations | **Q1** |

Items 1–3 are the line's subject: the emission shape the builder produces, the rows the loop
composes from it, and what the loop does when the emission is empty. Items 4–7 are the
remaining 1.7.2 §7 step-8 loop items. The order is the dependency order: #1312 changes what the
builder is asked for, #1374 what the loop composes, #1372 what happens when it produces nothing.

### 3.3 The rider, at the quota — CI- or live-verified, never roll-verified

| group | items | verified by |
|---|---|---|
| **timeouts and lineage** | #1147 (one setting bounds two things), #575 (placeholder trace/span ids) | CI |
| **persistence and API shape** | #577 (shared asyncpg pool + JSONB codec), #576 (domain-error handlers, the per-route envelope blocks deleted), #578 (graphlib for the plan DAG; decide `depends_on`) | CI |
| **ops** | #581 (compose healthchecks, `up --wait`), #560 (log hygiene), #574 (AMQP URL parsing), #300 (migration advisory lock), #330 (Prefect loop starvation) | #581/#560/#574 CI + one rebuild; #300 and #330 **live** on the dev deploy, after the set closes (§7) |
| **prompt registry** | #352 (runtime staleness guard), #353 (manifest hashes stamped at build) | CI + one rebuild |
| **realm and deps** | #372 (Keycloak realm export reaches existing realms), #1204 (refresh `ci-constraints.txt`), #1205 (dependency vulnerability scanning) | #372 live; #1204/#1205 CI |
| **evidence and tooling** | #1324 (the boot audit keeps the response it judged), #1369 (§3.1), #1373 (identity-permutation test) | CI |

Eighteen items. The 1.7.3 plan §5 kept all of them out of that line so a shakeout regression
would be attributable; the same rule here puts the CI-verified rider items **before** the pack
with a checkpoint pair between (§7), and the live-verified ops items **after** the set closes.
None of them has a roll-level readout and none gets one.

### 3.4 The count this line owes the record

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #1147, #330, #300 | 1.7.0 (rider), 1.7.2 (rider), 1.7.3 (rider, deferred), 1.7.4 | **4** each |
| #575–#578, #581, #560, #372, #352, #353, #574 | 1.7.0, 1.7.2, 1.7.3, 1.7.4 | **4** each |
| #994, #995, #968 | 1.7.0 (1.7.2's half), 1.7.2 (step 8), 1.7.3 §6, 1.7.4 | **4** each |
| #1312 | 1.7.2 (pre-registration §4 as 1.7.3's), 1.7.3 (reversed to here), 1.7.4 | **3** |
| #1254, #1054, #1070, #936, #933 | 1.7.0 (1.7.3's half), 1.7.3 §6, 1.7.4 | **3** each |
| #1285, #1324, #1204, #1205 | 1.7.3 §6, 1.7.4 | **2** each |
| #1369, #1372, #1373, #1374 | 1.7.4 | **1** each — filed on the 1.7.3 line |

Every rider item is on its fourth plan. That is the number this section exists to print.

### 3.5 The cut criterion

The pack's ten rows landed (item 10 conditional on §8), the rider at the quota, both sets closed
with no falsified prediction and **two bars held: L1 and H1**. A row that does not land revises
this plan in the open with the reason, never a re-place-by-name at the cut.

### 3.6 Merge discipline

One PR per row; the seam table in every PR that binds or removes a check (CLAUDE.md, typed
checks); the mirror rule on every removal; `--head` on every PR; every job of main's run read
after every merge; no merge to main while a set is open. The plan's own PR carries the 1.7.0
plan §3.1 amendment pointing here.

---

## 4. The verification set — a new pack, so new predictions

Two counting sets on one frozen deploy. The 1.7.3 predictions **re-registered verbatim** (L1–L8
as two claims, B1 now a field, R1/R3/R5/R6/R7, S0–S3, Q0, Q3, Q5, P0), plus the pack's own.
Every new prediction below names its falsification and its readout field, and — the 1.7.2 §7
question — what the readout would say if the prediction were false for a reason not yet thought
of.

| prediction | claim | falsified by | read from |
|---|---|---|---|
| **H1** (#1312) | no counted roll is rejected or blocked on the handoff: `required_files` names no `qa_handoff.md`, no `sections_present` row exists for it | one such row on a counted roll | the roll-up's `required_unmet` and the typed rows by check; **its own miss**: a *new* required file the profile derives would fail the same way with a different name — the readout lists every required file, not the handoff's |
| **H2** (#1312) | when the builder emits `assembly_notes.md`, the qa prompt carries it; when it does not, the qa prompt carries nothing in its place | notes stored and the appendix absent, or an appendix rendered from nothing | the stored qa prompt evidence (LangFuse) and the appendix presence per task; **its own miss**: a rendered appendix that carries a *stale* notes file from an earlier attempt — the readout pairs the appendix with the producing artifact's id |
| **F1** (#1374) | no counted roll whose accepted patch supplies a framework row's subject is rejected or blocked on that row | one such verdict | the corrected result's rows against the roll-up; the contentless-builder diagnostic is its exercise |
| **R1** (#1372) | every contentless emission on a counted roll is retried with its fact | one retry whose feedback carries no fact | `retried_with_fact` beside `contentless_emissions`; L1 stays the bar for the qa side, so R1's live exercise is the builder's short emission — expected on the order of two rolls in six by the 1.7.3 rate |
| **W1** (#994) | a rewind after an accepted repair never re-dispatches the repaired task | one re-dispatch after an accepted repair | the rewind lines against `applied_patches`; unexercised if no rewind occurs, and the record says so |
| **A1** (#968) | no correction decision inherits an analyzer claim the source refutes | one refuted claim in a decision | the analyzer's claims table against the checked-source rows the fix adds |
| **D1** (#1054) | a decision naming dev task types dispatches a dev repair | one qa repair dispatched under a dev-typed decision | `correction_repair_locus` against the decision's `affected_task_types` |
| **T1** (#995) | texture: a timed-out attempt banks its real history | — (no bar; read when it occurs) | the banked failure analysis against the emission-shape lines |
| **Q1** (#1285, conditional) | each qa output shape is measured under its own declaration | one fill-mode emission reported under the free-authored declaration | `emission_tokens_by_handler` by shape |

**Bars: L1 and H1.** L1 because it is the condition every other prediction is measured through
(1.7.2 §4). H1 because it is this line's subject: a counted roll rejected on the handoff after
#1312 lands means the design fault survived the fix, and that blocks the cut.

**Diagnostics before roll 1**, on the pinned deploy, each read by the seam it reached: the
1.7.3 three (absent-suite, own-frame chain, path-prefix) re-run; **plus the contentless-builder
diagnostic** (F1, R1's builder side); **plus a rewind diagnostic** if §3.1 can name an honest
fault for it — if not, W1 is declared unexercised before roll 1 rather than discovered so after.

**Size — 6 + 3, the 1.7.3 sizes held**, for the 1.7.3 plan §4's reason turned around: this line
changes what a cycle does, so a red is *expected* to be the pack's, and the counted set is the
one place that can attribute it. Fewer rolls would leave H1 read on fewer than the builder's
short-emission rate can show.

**Known non-pack rejection cause, declared before roll 1:** none is carried from 1.7.3 — #1312
was that cause and is the pack. Packaging findings (`npm_ci_without_lockfile`, 4 of 9 rolls on
1.7.3) stay reporting-only.

**Texture, no prediction attached — each with the field that produces it:** the builder's first
emission size (`emission_tokens_by_handler`); packaging findings; correction rounds; the fill
assertion strength per run (`fill_merge_evidence`); B1's denominator (`non_root_fixture_tables`);
`checks_by_environment`; the qa tokens by shape (Q1's producer whether or not Q1 is registered).

---

## 5. Hardening — the rider is here, not pulled forward

§3.3 is the infrastructure rider the 1.7.2 and 1.7.3 plans deferred, in full, at the quota. The
1.7.0 plan §3.1 named it 1.7.3's; the 1.7.3 plan §5 gave the reason it moved — no roll reaches
any of it, and landing it beside a measured pack makes a red unattributable — and §7 here keeps
that reason: CI-verified rider items land before the pack behind a checkpoint pair, live-verified
ops items after the set closes.

---

## 6. Re-placements by name — nothing silently carried

**1.7.5 — Composition Root and the close of 1.7.** Unchanged from the 1.7.3 plan §6: #820, #376;
#301, #286, #1152 with #1149 first; #567, #579; #198, #157, #176, #580, #1180/#1182; #1197;
#929 with #1206. Plus, from this line: whatever §3.3's live-verified ops items leave unverified
at the cut, named in the record.

**The 1.8 lane.** The Slot-Scoped Emission draft (PR #1325) with #1213 and #1176 — its design
review starts during this line (§7 step 2) with the 1.7.3 findings as evidence (#1323, #1350,
#1351, roll 1's unaddressed repair fences), so 1.8.0 opens against an accepted design. #906
(the Next.js baseline stylesheet) stays post-window. #1122 stays with SIP-0104.

**Still at design review, unchanged:** #414, #557, #316; #80, #950, #949, #194, #1039, #1031.

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.7.0 plan §3.1 amendment. Opened now; merges on the
   owner's review.
2. **The Slot-Scoped Emission design review opens** (PR #1325) — a review, not a build; it
   runs beside this line and gates nothing here.
3. **§3.1's preconditions**: `integration` required first (a workflow change, one PR); then
   the instrument — the contentless-builder fault, the two producers, #1369 — with a rebuild
   (deploy A) and the instrument rounds: the four diagnostics on A, read by the seam reached.
4. **The rider's CI-verified items**, one PR each, in §3.3's order; rebuild (deploy B); **one
   checkpoint pair** — a red here is the rider's.
5. **The pack, in §3.2's order**, one PR each; item 10 only if §8 rules it in. Rebuild (deploy
   C); shakeouts to the exit rule — a pair on one deploy with no new seam finding; budget three
   pairs; the record reports rounds taken and rounds attributable to the pack.
6. **Pre-register** (`1-7-4-<arm>.yaml`, pins from the last shakeout); the diagnostics on the
   pinned deploy; **roll 6 + 3** — no merges to main while a set is open; the counted/void/
   reset reading at each boundary.
7. **The rider's live-verified ops items** (#330, #300, #372) after the set closes, each verified
   on the dev deploy and named in the record as verified live, not by a roll.
8. **Record from the per-round evidence; cut 1.7.4 by the seven steps**, step 7's capture named
   with every cycle the record cites and its role. Then 1.7.5.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

- **#1312 with #1254 leads, as one change** (the 2026-09-05 ruling): the handoff becomes
  optional assembly notes defined by exclusion; both check surfaces go; the qa appendix is
  presence-keyed; a derived guard over the registered stacks.
- **#1374 and #1372 are the pack's second and third rows**, ahead of the 1.7.2 step-8 items:
  two void counted rolls in two lines is the loop's most expensive habit, and a retry that
  carries its fact is the smallest change that makes the builder's short emission recoverable
  in place.
- **Two bars: L1 and H1.** One bar was right when the line's subject was not the loop; this
  line's subject is a rejection cause, and the cut should not survive its recurrence.
- **`integration` becomes a required check.** The alternative — the process rule alone — held
  for one line only because the owner read the run.
- **The rider lands before the pack behind a checkpoint pair**, its live-verified ops items after
  the set. The alternative — rider after everything — leaves eighteen items on their fourth plan
  to a fifth.
- **#1285: decided here from the 1.7.3 record §5.** The fill-mode qa emission costs roughly
  double the free-authored one in completion tokens and reasoning characters (10.2k vs 5.8k;
  69k vs 136k characters over 3 vs 10 emissions). **Recommendation: material — build Q1's
  half in this line**, because the reasoning declaration is 1.7.0's whole subject and it
  currently speaks for the cheaper shape only. If the owner rules it not material, #1285 closes
  with the reading and the producer stays.
- **A rewind diagnostic only if an honest fault exists**; otherwise W1 is declared unexercised
  before roll 1. The 1.7.2 lesson: a prediction no roll is likely to reach gets a fault or gets
  named, never a green by absence.
- **N = 6 + 3.**
- **The Slot-Scoped Emission review starts now, beside the line**, so that 1.8.0's headline is
  not designed in 1.8.0.

---

## 9. Revision history

- **Rev 1 (2026-09-07)** — written the evening the 1.7.3 line closed, on the owner's ask,
  from the 1.7.3 plan and record, the 1.7.2 plan §8/§8a, the 1.7.0 plan §3.1 and §6.2, and the
  issues filed on the 1.7.3 line (#1369, #1372, #1373, #1374 — the last three filed with this
  plan so nothing is carried as plan text). Placement against the 1.7.3 plan §6's re-placements
  by name, with the pack reordered to put the two void-roll mechanisms second and third. Owed
  at the review: the owner's ruling on #1285 (§8), on the two bars, and on the rider's
  position.
