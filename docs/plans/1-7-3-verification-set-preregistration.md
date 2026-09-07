# 1.7.3 — Verification Sets: Pre-registration (DRAFT — pins blank until the last shakeout)

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Merging it is the owner's act and does not change what it pre-registers; the
branch commit is the record. Revised while the shakeout loop runs — each round's finding
becomes a merged fix and, where the fix is in deployed code, a new deploy (§2) — and frozen
before the first counted launch.

This is the 1.7.3 plan's §4 (`docs/plans/1-7-3-plan.md`) as data: **the 1.7.2 set
re-registered verbatim** — six counting rolls on FastAPI+React, three on Next.js+TS — with
**no new pack**. The line's content is the thirteen CI-verified Boundaries items (plan §3.2);
its verification claim holds in one direction only: **a red on this set is the refactor's**,
a green is not evidence about the list, twelve of whose thirteen items have no roll-level
readout. Everything not restated here is inherited **verbatim** from the 1.7.2
pre-registration and, through it, 1.7.1/1.6.6/1.6.5/1.6.4/1.6.3: §5 (scoring), §5.1 (roll
validity — void / reset / counted), §6 and §6.1 (the gate constant and the two approval
paths), §7 (prohibited while open).

**What is different this time, and why.** The 1.7.2 record §7 and §8 named three failures of
the instrument: two predictions (L2, L8) entered the set unexercisable as registered, a
readout (L3) reported HELD on the roll that falsified it, and a declared texture field ("qa
primary tokens") had no producer. All three are answered here rather than noted:

- **L8 is two claims** (#1311): L8a, the model does not emit under the placeholder, read from
  the extractor's own `fence path placeholder` strips on every counted roll; L8b, an
  emission that does is repaired rather than spent, read from stored names and exercised by
  the path-prefix diagnostic. The old single readout could not see its own miss.
- **The absent-suite fault reaches L2's seam** (#1310): the fault applies to every emission
  attempt of the qa task, so the task exhausts its emission retries and fails into
  correction, where the repair that supplies the suite is retested. The diagnostic is read
  by the seam reached (`seam_reached` in its record), never by "the fault fired".
- **Every texture field named in §4 has a producer, checked against a real 1.7.2 record**
  (plan §4, the #1285 lesson) — see §4's texture list, each with the record field it reads.
- **One new readout, B1** (#1087/#1112), on the one list item that shapes an emission.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **6 counted** on FastAPI+React (§4) and **3 counted** on Next.js+TS (§5) — the 1.7.2 sizes held (plan §4 at rev 2: this line expects the rounds-attributable-to-the-list number to be non-zero for the first time, so fewer rolls is the wrong direction). 1.6.6 §1.3 on what these sizes can and cannot say holds unchanged: exercise, not a rate. |
| Bar | **one, and only one: L1** (§4), as in 1.7.2. |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 → 1.7.2 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` — **the key is `development_profile` since #922**; `dev_capability` is refused at cycle create, so a launch on the old key cannot silently run the wrong stack |
| `resolved_config_hash` | FastAPI+React `TBD`, Next.js+TS `TBD` — observed on the round-1 shakeouts of each arm on the frozen deploy; asserted on every counting roll; a roll on any other hash is void. **The Next.js hash is expected to move from 1.7.2's `d4d4f66217d8`** because the override key is part of the resolved configuration (#922); the React hash is expected to hold at `c4d6a2165acf`. Either expectation failing is recorded, not explained away. |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` expected unchanged from 1.6.6 → 1.7.2; a roll on any other snapshot is void |
| Deploy — commit | `TBD` — main after the shakeout loop's last fix; carries the thirteen list items and every instrument fix (#1316 #1311 #1330 #1310 #1323 #1347 …). A label, not an assertion (#1296): **the image ids below are the assertion**. |
| Deploy — 7 image ids | `TBD` — filled from the last shakeout's `shakeout-deploy.json`; asserted at every counting launch by the driver, which refuses a roll on any mismatch. |
| Loaded, not built | Verified per container as a **live call with its paired control**, never a symbol import. Beside the 1.7.2 calls, each set config's `loaded_checks` now carries the list's own: the Prefect state for `QUEUED` (#377, the pair `.upper()` got wrong), the failed-emission stage (#1323), the `TaskType` member and its wire string (#559), the retired module absent (#922), the reference store's roots only (#1087). Output recorded in every record (#1297). |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-7-3-<arm>.yaml --roll N` — one roll per invocation |
| Order | FastAPI+React rolls 1–6 first, then Next.js+TS rolls 1–3 |

---

## 2. Preconditions and the shakeout log

- **Counted launches run from `main`** (the owner's 2026-08-27 ruling), which requires this
  document and the five set configs to be merged before roll 1.
- **The shakeout loop with its exit rule**, stated before the first launch
  (`docs/plans/verification-sets/README.md`): **exit on a pair on one deploy with no new seam
  finding**; **budget three pairs** for the post-list loop; the cut record reports **two
  numbers — rounds taken, and rounds attributable to the list** (the 1.7.2 record §7 rule).
  A finding is a defect in a seam the list touched, or a prediction's readout that cannot
  see its own miss; a defect in the application a cycle built is the cycle's and does not
  reset the loop.
- **Instrument rounds are counted apart from shakeout rounds.** Phase 1 proved the
  instrument on its own deploy (deploy A, built from the last precondition commit
  `2b75c3e5`, before any list item entered a deploy), so a shakeout round on this line's
  deploys is about the list. The instrument rounds are logged below with what each found.
- **One checkpoint pair between the structural block and the behavioural block** (deploy B),
  added at the line's opening for attribution: a red on the final pair then belongs to the
  five behavioural items, and a red on the checkpoint to the eight structural ones, whose
  own guards do the bisecting.
- **A fix to the instrument does not supersede the deploy** (1.7.2 §2 rule): a driver-only
  fix re-renders a kept round from its stored identity and is named here.

### Deploys and what each found

| deploy | built from | images | purpose | found |
|---|---|---|---|---|
| A | `2b75c3e5` (main at #1334: the 1.7.2 tree + #1316 #1311 #1330 #1310 #1323 #1285-producer) | runtime-api `c83438b1dab7` · agents `718166749b69 fc69ea857fe0 d3a427c45a04 4ab1f69cbd02 670caad84a10 dd960db7372d` | instrument round 1 — the three diagnostics on a pre-list deploy | **#1347**: the absent-suite fault applied to all three correction re-dispatches (`cyc_1b3b225e593e`) — the emission-retry marker (#566) was never cleared, so the fault scope and the handler both read a correction re-take as an emission retry; L2's seam was reached each round; the run's red was manufactured |
| A″ | `2b75c3e5` + `7eb930ba` (the #1347 fix, runtime-api only) | runtime-api `2c46f709e2d9` · agents as A | instrument round 2 — the three diagnostics re-run | **absent-suite `cyc_075b459f6aef`: the fault applied to the first attempt and the emission retry only; the correction re-take ran clean ("outside its scope — not applied"); L2's seam reached (repair retested, retest failed, re-take recovered); accepted, boot PASS, functional** — the instrument holds. **Own-frame chain `cyc_375bdea6e140`: rejected, boot FAIL, `seam_reached` false for both faults — three defects, none of them the list's.** (1) **#1352**, instrument: the Python own-frame fault was a `NameError`, which the emission seam's `undefined_names` check refused and the handler's self-eval removed before the suite ran — L7 on a pytest suite had never been exercised (1.7.2's chain held L7 on its vitest task). (2) **#1350**, the #1323 instrument change: the suite then failed at the app, the repair routed to dev correctly, and `_try_accept_patch` judged the dev's `backend/routes.py` under the **failed qa task's** grants — dropped as a QA write to a dev slot, patch refused, re-take on the unrepaired tree, `plan_defect` at round 1. (3) **#1351**, pre-existing (1.4.0): the dev emitted `APIRouter(prefix="/runs")` + `@router.post("")`; `fill_slot_integrity` restored the router line alone, and FastAPI refuses an empty prefix with an empty path at `include_router` — the app could not import, on the first emission and on the repair. Path-prefix skipped on A″ (it runs on the pinned deploy). |
| B | `4a2cf724` (main after #1342 — the structural block: #922 #559 #377 #381 #1241 #154 #218 #219) **+ the #1347, #1350 and #1352 instrument fixes cherry-picked** (as A″ carried #1347 onto A), so the checkpoint still isolates the structural block from the behavioural one | `TBD` | the checkpoint pair | *pending* |
| C… | main after the behavioural block (#305 #225 #999 #1087/#1112) | `TBD` | the shakeout loop to the exit rule; the pinned deploy is the last one | *pending* |

*(The path-prefix diagnostic also ran once on the 1.7.2 images with the repaired readout,
`cyc_fa3b503d9d60`: L8a read two strips, L8b none — the readout that was blind now sees.)*

---

## 3. The exercise plan — stated before roll 1

The 1.7.2 rule, kept: every prediction names how it gets exercised, and the ones a roll is
unlikely to reach get a fault-injected diagnostic that runs the roll's own path. **A
diagnostic is never a roll**, and since #1310 **a diagnostic is read by the seam it reached**
(`seam_reached` in its record) — never by "the fault fired" (#1300).

| prediction | reached by an ordinary roll? | exercise plan | result |
|---|---|---|---|
| **L1** (#1268) | yes — every roll has a qa first attempt | read from the emission-shape readout on each counted roll | — |
| **L2** (#1269) | unlikely | `1-7-3-diagnostic-absent-suite` — the fault now applies to every emission attempt (#1310), so the task fails into correction and the repair is retested; read from `seam_reached.qa_suite_absent` (correction ≥ 1 **and** a `patch_retest` for the qa task) | **EXERCISED, HELD** on A″ (`cyc_075b459f6aef`): `seam_reached: true`, one `patch_retest` keyed on the qa task, the run recovered by re-take and was accepted. (A's run reached the seam three times under #1347's manufactured re-dispatches.) |
| **L3** (#1271) | yes when any qa task is re-attempted | read from the summary's failed rows against the last stored evaluation, and from `stale_evaluations` (the 1.7.2 field that made the readout see its miss) | — |
| **L4** (#1273) | unlikely | the chained diagnostic; read from `refused_rounds_not_counted` | — |
| **L5** (#1260) | unlikely | rides the chain; read from the two stored suites by case title | — |
| **L6** (#788) | unlikely | no honest fault; read from a stored repair brief if a roll produces one, else recorded unexercised | — |
| **L7** (#1270) | unlikely | the chained diagnostic; read from `qa_owned_routed` | — |
| **L8a** (#1272, the model) | yes — every counted roll | `placeholder_strips` on every roll: the model emitted under the placeholder if the count is non-zero | — |
| **L8b** (#1272, the extractor) | unlikely | `1-7-3-diagnostic-path-prefix`; read from `stored_under_placeholder` (must be empty) beside `placeholder_strips` (must be non-zero — the fault bit) | — |
| **B1** (#1087/#1112) | yes — every counted roll with a qa fill | read from the stored qa suites against the manifest's root-persisted entities: no fixture table for a non-root entity | — |

**The chained diagnostic — one cycle, three predictions** (L7 → L4 → L5), as in 1.7.2 §3,
declared `fault_injection: [qa_suite_own_frame_failure, repair_prose_only]`. If the refund
takes another repair round instead of a re-dispatch, L5 is unexercised and the record says so.

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — the measurement, six rolls

The 1.7.2 §4 table, verbatim, with L8 split and B1 added:

| # | prediction | falsified by | read from |
|---|---|---|---|
| **L1** | (#1268) no qa first attempt is contentless | one contentless emission in a counted roll | emission-shape readout (chars, fences, finish reason) |
| **L2** | (#1269) a repair of an absent suite is retested; the run carries executed `tests_pass` | one such repair accepted with `tests_pass` never executed | patch/retest log lines; the summary's `unverified` |
| **L3** | (#1271) a run whose last attempt passed is never rejected on an earlier attempt's rows | one such rejection | the summary's failed rows against the last stored evaluation; `stale_evaluations` |
| **L4** | (#1273) every re-taken brief carries the original row's cases; no prose-only repair is verified | one 0-case re-take brief while the row carried cases; one prose-only repair verified | `repair_brief_case_counts` as (brief, row) pairs; refund lines |
| **L5** | (#1260) a re-dispatched suite carries every case the failed report named | one dropped case | the two stored suites, by case title |
| **L6** | (#788) a runtime-error repair is briefed with the traceback | one such brief without it | the stored repair brief |
| **L7** | (#1270) an own-frame failure in a qa-owned file is routed to `qa.test_repair` targeting that file | one such failure whose repair targets an app file | `qa_owned_routed`; `correction_repair_locus` lines |
| **L8a** | (#1272) the model does not emit under a literal `path/` prefix | one `fence path placeholder` strip on a counted roll | `placeholder_strips` |
| **L8b** | (#1272) an emission under the placeholder is repaired, never spent | one stored artifact under `path/`, or a round spent on one | `stored_under_placeholder`; the round count of the path-prefix diagnostic |
| **B1** | (#1087/#1112) no stored qa suite declares a fixture table for an entity that is not root-persisted | one such table in a stored suite | the stored suites against the manifest's `root_persisted_entities` |
| **R1, R3, R5; S0–S3, Q0, Q3, Q5, P0** | carried unchanged — unexercised is not passed | as there | as there |

**One bar, and only one: L1.** A falsified L1 blocks the cut.

**A known non-pack rejection cause, declared before roll 1 (#1312):** the builder omits
`qa_handoff.md` in roughly 9% of builder tasks; the signature is as 1.7.2 §4 states it, and a
roll rejected on it is not evidence about any prediction. #1312 with #1254 is 1.7.4's (plan
§6, §8 — a reversal of the 1.7.2 §4 placement, recorded there).

**Texture, no prediction attached — each with the record field that produces it** (plan §4:
every field checked against a real 1.7.2 record before the set opens):

| texture | record field | producer checked |
|---|---|---|
| verdict rate (no bar) | `verdict` per roll | 1.7.2 records |
| correction rounds | `correction_rounds` | 1.7.2 records |
| greens by repair vs re-dispatch | `loop_texture.applied_patches` / `retests` / `narrowed_targets` | 1.7.2 records + #1310's `retests` |
| refused vs applied vs refunded | `refused_patches` (whole lines since #1330) / `applied_patches` / `refused_rounds_not_counted` | 1.7.2 Next.js roll 2 replayed |
| contentless emissions per roll | `contentless_by_handler` of `emissions_logged` | 1.7.2 records |
| qa emission spend | `emission_tokens_by_handler` — **completion tokens and reasoning *chars***; reasoning *tokens* are unreported by the adapter's shape line on every qa emission (the #1285 finding), so the record reads chars and says so | 1.7.2 Next.js roll 2 replayed |
| fill-merge assertion strength | `fill_merge_evidence` per qa task (#999) | none before this line — first read on deploy C's shakeouts |
| `checks_by_environment` | `typed_checks.checks_by_environment` | 1.7.2 records |
| L8a strips | `placeholder_strips` | `cyc_fa3b503d9d60` |

**Early stop, one direction.** A falsified prediction stops the set. A good result is never
grounds to stop early. A stop in one set does not stop the other.

---

## 5. Next.js+TS (`nextjs_ts`) — three rolls

| # | prediction | falsified by | read from |
|---|---|---|---|
| **L1–L5, L7, L8a, L8b, B1** | as §4 | as §4 | as §4 |
| **L6** | as §4; vacuous unless a roll produces an app runtime error | as §4 | as §4 |
| **R6, R7, Q0, Q5, P0** | carried from 1.7.2 §5 unchanged | as there | as there |

**Vacuous here, declared rather than discovered:** R3/R4's anchor half, as 1.7.2 §5.

**Early stop, one direction, per set** — as §4.

---

## 6. Delegation

Executed by the assistant under the owner's delegation for the whole line (2026-09-06):
FastAPI+React rolls 1–6, then Next.js+TS rolls 1–3 — launch, gate approval with the §7
constant, collection, the per-roll record. **The counted/void/reset reading and the
prediction check are made at each roll boundary before the next launch**; a reset or a
falsified prediction stops that set and is reported to the owner.

## 7. Gate constant

Inherited verbatim (1.6.3 §6, §6.1); the text is in each set config's `gate_notes`.

## 8. Prohibited while open

Inherited verbatim (1.6.3 §7): **no merges to main while the set is open.** The driver pins
HEAD at roll 1 and refuses a later roll on a different HEAD.
