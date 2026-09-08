# 1.7.4 — Verification Sets: Pre-registration (DRAFT — pins blank until the last shakeout)

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Merging it is the owner's act and does not change what it pre-registers; the
branch commit is the record. Revised while the instrument rounds, the checkpoint pair and the
shakeout loop run — each finding becomes a merged fix and, where the fix is in deployed
code, a new deploy (§2) — and frozen before the first counted launch.

This is the 1.7.4 plan's §4 (`docs/plans/1-7-4-plan.md`, rev 3) as data: **two bars, L1 and
H1; three live hypotheses, F1, B1 and Q1; the seam invariants R1, H2, W1, A1 and D1 and the
1.7.3 diagnostics' L2/L4/L7/L8, proven on the pinned deploy and reported as texture on the
counted rolls; the 1.7.3 set's own claims re-registered under a `1.7.3/` prefix.** Six
counting rolls on FastAPI+React, three on Next.js+TS, on one frozen deploy. Everything not
restated here is inherited **verbatim** from the 1.7.3 pre-registration and, through it,
1.7.2/1.7.1/1.6.6/1.6.5/1.6.4/1.6.3: §5 (scoring), §5.1 (roll validity — void / reset /
counted), §6 and §6.1 (the gate constant and the two approval paths), §7 (prohibited while
open).

**The rules this document carries from the plan's preamble, applied before roll 1:**

- **Every registered readout maps to a typed evidence field before the set opens, checked
  against a real record.** §3 names the field beside every claim. Two of them did not exist
  when the line opened and were built on it: B1's (`static_checks.non_root_fixture_tables`,
  #1378 — 43 suites, 0 mentions on the 1.7.3 records) and R1's (`retried_with_fact` beside
  `emission_retries`, #1378). One was found missing by the first diagnostic and built after
  it: F1's (`framework_rows_rederived`, #1398 — the executor composes the re-derived row into
  the corrected result and stores no evaluation artifact, so `typed_checks.by_check` was
  blind to it).
- **No fault, no prediction.** W1's honest fault does not exist (§3): #994's mechanism is the
  "continue" fallback after an applied-but-unverified repair, not the correction path's
  `rewind`, and rule B (#1229) and #1221 have since changed what that fallback does. **W1 is
  CI-only on this line**, declared here before roll 1, unless pack row 4's design finds a
  fault.
- **Rolls measure emergent behaviour; faults prove reachable seams; CI proves deterministic
  mappings.** A diagnostic is read by the seam it reached (`seam_reached`), never by "the
  fault fired" (#1310, #1300), with the **two-run budget** of plan §3.1 for a seam that sits
  behind a live emission or repair.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **6 counted** on FastAPI+React (§4) and **3 counted** on Next.js+TS (§5) — the 1.7.3 sizes held, for comparability and observation across one frozen deploy (plan §4); faults provide the guaranteed seam exercise. |
| Bars | **two: L1 and H1** (§3). L1 — the loop remains able to produce a valid running result; H1 — this line's rejection class is gone. |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 → 1.7.3 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React **`<blank>`**, Next.js+TS **`<blank>`** — observed on the last shakeout pair of each arm on the frozen deploy; asserted on every counting roll. Expected to hold at 1.7.3's `3921c5a62106` / `33cadf53688e` unless a pack row changes the resolved configuration; a move is recorded, not explained away. |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` expected unchanged from 1.6.6 → 1.7.3 |
| Deploy — commit | **`<blank>`** — main after the shakeout loop's last fix. A label, not an assertion (#1296): the image ids are the assertion. |
| Deploy — 7 image ids | **`<blank>`** — from the frozen deploy's identity; asserted at every counting launch. |
| Loaded, not built | Verified per container as a live call with its paired control. Each set config's `loaded_checks` carries the 1.7.3 calls and the 1.7.4 surfaces: the builder and analyzer faults wired at their seams, the correction envelopes' `resolved_config`, the pool's JSON codecs, `DispatchConfig`, the domain-error handlers, the migration lock (`docs/plans/verification-sets/1-7-4-<arm>.yaml`, #1399). |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit — since #1384 a failed probe's line carries the status and a bounded excerpt of the response it judged, and the record keeps every FAIL line |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-7-4-<arm>.yaml --roll N` — one roll per invocation |
| Order | FastAPI+React rolls 1–6 first, then Next.js+TS rolls 1–3 |

---

## 2. Preconditions and the shakeout log

- **Counted launches run from `main`**, which requires this document and the set configs to
  be merged before roll 1.
- **The control-plane precondition is met**: `integration` is a required status check on
  `main` since 2026-09-08 (branch protection lists it beside `closing reference present`,
  `lint + regression` and `scaffold skeleton gate`); the controlled negative check (PR
  #1376, one deliberately failing integration test) was observed **BLOCKED** and closed
  unmerged; PR #1377 records both.
- **The instrument was proven on its own deploy (A) before the pack's first PR**: the driver
  fields (#1378), the two faults with their readouts (#1379), F1's field (#1398).
- **The shakeout loop with its exit rule**: exit on a pair on one deploy with no new seam
  finding; budget three pairs; the record reports rounds taken and rounds attributable to
  the pack. A finding is a defect in a seam the pack touched, or a readout that cannot see
  its own miss; a defect in the application a cycle built is the cycle's.
- **The rider landed before the pack behind a checkpoint pair** (plan rev 3): every
  subsequent roll exercises it; the tag matches the frozen deploy. **#560 landed last** and
  every driver field is re-checked on the checkpoint pair's records.
- **A fix to the instrument does not supersede the deploy** (1.7.2 §2 rule).

### Deploys and what each found

| deploy | built from | images | purpose | found |
|---|---|---|---|---|
| A | main at `4ce18165` (the 1.7.3 tree + #1377 #1378 #1379 #1380) | runtime-api `6b57d5a7b85a` · max `99f2944fc87b` · neo `b90268bfaf21` · nat `b059cfafb84b` · bob `19ba155dd9c3` · eve `0a0587a8d6f0` · data `6f8f9c9239c6` | instrument round — the diagnostics on a pre-rider, pre-pack deploy | **contentless-builder `cyc_ceef5581bfd1`: seam reached — the fault applied to the builder's first attempt (48 chars, 2,281 completion tokens, no fence), the attempt failed as a semantic failure with no retry marker (the #1372 gap), correction round 0 entered, the builder's own repair verified `passed`, the executor re-derived `required_files` on the patched set (`passed=True`, #1364's rule); accepted, boot PASS, functional, one correction round, 3,307 s.** Instrument finding: the record's `required_files_rows` read `{}` — the re-derivation is composed into the result, not stored as an evaluation artifact — so F1's field now reads the executor's line (#1398). **absent-suite-then-false-claim `cyc_1063c4dca548` (06:27–07:39Z): both seams reached; A1 falsified in substance, as expected before #968, and the readout was blind to it.** The absent-suite fault took every qa emission attempt (two qa tasks, two correction rounds, both repairs retested and passed — L2 twice); the analyzer fault applied to round 0's analysis (1,361 chars in, the claim leading the summary and `implicated_files`). The lead's round-0 decision then said *"the root cause is also an injected backend fault preventing endpoint verification … address the missing router registration"* and put `backend` in `affected_task_types` — the refuted claim absorbed in full — **without the marker string**, so the marker-keyed readout wrote `A1: YES` into the live record. Fixed before pre-registration: the reading now carries the marker, the claim's substance (`echoes`) and non-task-type entries (#1401), and the record re-rendered from its stored identity reads **A1: NO** on `art_bd2bec36ef94` (echoes `injected`, `router registration`; foreign `backend`) and clean on round 1's decision (`art_02495ecbb4bf`, the analysis unfaulted). The qa own-artifact routing was right (`qa.test re-produces backend/tests/test_runs.py`) and consults no source check — `_verified_implicated_files` is the dev repair-target path's alone — which is #968's row. Accepted, boot PASS, functional. Second instrument finding from the re-renders: the log window had no end, so a record re-rendered after a later cycle carried that cycle's lines (the builder record showed the analyzer diagnostic's qa retries as its own); the window now ends at the cycle's last run plus a grace and the record states it (#1402). Both records are re-rendered (`shakeout-rerender-*`) with #1398, #1401 and #1402. **Texture from A**: qa emission retries DO carry the fact today (`retried_with_fact` two of two, `appendix_chars` 888/909, `expected_files=1`) — #1372's gap is the builder's missing retry path, not the qa side; the lead writes non-task-type names into `affected_task_types` on an unfaulted decision too (`builder`, `assembler`, `data`, `qa_handoff` on the builder diagnostic) — D1's live field. **The 1.7.3 three on A** — absent-suite `cyc_1b54b29e2a99` (07:40–08:44Z): L2 reached across two rounds (the round-1 retest FAILED, round 2 recovered), accepted, boot PASS, functional; the dev repair-target check dropped an unfaulted analyzer claim (`backend/store.py`, "the workspace has no such file") — the structured half of #968 firing on a real analysis. own-frame-then-prose-repair `cyc_a26c6828482c` (08:44–09:37Z): L7 reached (the own-frame `TypeError` at `test_create_run_returns_id_and_submitted_fields:51` routed to `qa.test_repair`), L4 reached (round 0 refunded), L5 reached (the re-take briefed with the one failing case), accepted, boot PASS, one round; its decision said "injected" of the fault call it could see in the suite, which narrowed A1's echo list to the claim's own phrases (#1403). path-prefix `cyc_b80f0ea3ca64` (09:37–10:26Z): **L8 held** — the fault bit once (`path/backend/tests/test_runs.py` → `backend/tests/test_runs.py`), `stored_under_placeholder` empty; boot PASS, the app answering all five probes — and **rejected on #1312's shape**: the builder omitted `qa_handoff.md` (`required_files`, `sections_present: file_not_found`), its repair was unverifiable (`no_executed_blocking_checks`, `file_not_in_patch:2`), the loop terminated honestly and the run failed "Build deliverable incomplete". The pack's first row, on a pre-pack deploy, as on 1.7.3's deploy D; the cycle's, not a seam finding. **Every diagnostic on A reached its seam: L2 (twice, plus the analyzer chain), L4, L5, L7, L8, the contentless-builder sequence's steps 1, 2, 5 and 6, and A1 falsified in substance as expected.** All five records re-rendered with the driver at main `0fe8aa9b`. |
| B | main at `d571da60` — deploy A **plus the whole rider** (#1373 #1205 #575 #1324 #574 #300 #1147 #581 #578 #1204 #577 #576 #352 #372 #330 #560), the F1 field, the A1 readout and the bounded window; the refreshed pins | runtime-api `3e013f437c98` · max `8b3773184dec` · neo `4fcc71b6a902` · nat `c88844430183` · bob `11d0d1e5628d` · eve `42dd35d53374` · data `d9b2abb29a33` | the rider's rebuild; the checkpoint pair; every driver field re-checked | **The rebuild itself is the rider's first live reading**: `up -d --wait` returned on every service, 251 s end to end against the old fixed sleeps (#581); `cryptography 50.0.1` / `pyasn1 0.6.4` loaded (#1204); the pool codec, `DispatchConfig` (unset → follows `llm.timeout`), the domain-error handlers and the migration lock loaded (#577 #1147 #576 #300); **#560 live**: zero `squadops.audit` and zero `httpx` lines on the runtime-api's stdout since the deploy, 53 records in `data/audit/runtime-api.jsonl` after the first minute; **#372 live**: the realm sync reported `squadops-dev` **added 2, skipped 9** — two resources the export carried and the running realm lacked, the issue's claim in numbers — and `squadops-local` added 0, skipped 11; **#352**: this deploy's asset provider is `filesystem`, so the registry boot check is loaded but not exercised here (the negative case is not run). **Checkpoint pair — CLEAN, and the rider is confirmed.** React `cyc_dd3068d22f2c` (10:32–11:33Z, config hash `3921c5a62106`, 1.7.3's as expected): accepted, boot PASS, 60 min, 1 correction round, 0 contentless emissions of 20. Next.js `cyc_bd6d424ba2fb` (11:47–12:43Z, config `33cadf53688e`): accepted, boot PASS, 55 min, **0 correction rounds**, 19/19 criteria, 0 contentless of 17. Neither half is attributable to any rider item. **The React half found one thing, and it is not the rider's:** its qa repair's patch verification returned `status=passed` carrying `skips=missing_tooling:3`, and those three skips DEMOTED three `vc-view-compiles-*` criteria that had already passed at emission — 21 of 24 on an accepted roll, the first non-N-of-N accepted roll in 30 records. npm exists only in the dev and qa images, so a criterion re-asked at the runtime-api can only skip; no rider commit touches `acceptance_checks`, `verification_integrity` or `verification_normalize`. Filed as **#1406**. The instrument was blind to both halves of it and was fixed before the pack opened (**PR #1407**): skips are counted on every patch verification, not only unverifiable ones, and the criteria shortfall is named and split by whether a row was produced — replayed on the real record, which now reads `3 missing_tooling` on a PASSED verification and names all three lost criteria. |
| C | main at `bbe0df8e` — deploy B **plus the whole pack** (#1312+#1254, #1374, #1372, #994, #995, #968, #1054, #1070, #936/#933, #1285) and the probes that read it. Also carries another lane's docs merged during the pack (SIP-0106 §1.2e/§1.2f, plan §6a) — documents only, no behavioural drift, named so the deploy is not read as the pack alone | runtime-api `9dbecefbe6db` · max `9c393544c60e` · neo `516a26fce184` · nat `7c106d404c51` · bob `95373605543d` · eve `558d26db1c63` · data `3d79c1ca2607` | the pack; the shakeout loop to the exit rule; the pinned deploy is the last one | Rebuilt rc=0 in **91 s**. **The pack is LOADED, verified in-container with each row's paired control** — runtime-api: `('required_files',) ()` (#1374 a builder owes, a dev task owes nothing), `{'fill':0,'path':0,'plain':0}` (#1372's shape), `patch` / `rewind` (#994 with and without an accepted repair), `True` / `False` (#1054 a decision that disputes and one that abstains), `emission_failure` (#1054's non-disputable signal), `['backend/ghost.py']` / `[]` (#968 a refuted path and a sound claim refuting nothing), `none` / `medium` (#1285's two levels); bob: the handoff is **not required**, the notes are optional, seven exclusion lines derived from the stack, and the legacy profile renders `()`; eve: `none` / `medium`. **Shakeout round 1 — both halves accepted, functional, and behaviourally clean.** React `cyc_00872b888f80` (13:55–14:49Z, 52 min): 0 correction rounds, 17/17 criteria, L1 **0 contentless of 16**, 0 skips on any patch verification — #1406's shape did not recur. Next.js `cyc_cb132e22956c` (14:54–15:52Z, 57 min, driver at `80e01882`): 0 correction rounds, 16/16 criteria, L1 **0 contentless of 20**, 0 skips; the #999 fill-merge field carries real content (8 filled slots, 8 store slots, `TABLES`/`all` used). **Three findings, none of them a pack seam defect in the cycles themselves.** **#1425** (mine, the instrument): three of seven loaded checks had never run — see the correction below. **#1427**: the pack retired `qa_handoff.md` from every checking surface and from the prompt assets, but `examples/03_group_run/prd.md` still asks for it in seven places (and `prd-scaffold.md` in two more), so the framing role writes it into the definition of done as `required_artifacts[0]` and the builder spends its emission on it. Reproduced on both arms. Owner decision, raised not taken: `compute_config_hash` does not cover the PRD text, so editing it leaves `resolved_config_hash` unchanged and breaks comparability with 1.7.1–1.7.3 silently. **#1428**: every framing run reports `blocked_unverified` with `frontend_build`, `required_files` and `tests_pass` as `subject_missing [required]` — its tasks emit no source, suite or required files, so those checks have no subject by construction. Pre-existing (deploy B's pair has it), verdicts unaffected. |
| D | main at `dfe9a6f2` — deploy C plus **#1430** (the request stops naming the retired handoff, finishing SIP-0098 §6.7) and #1429's record. Rebuilt rc=0 in 88 s; the runtime-api's **baked** PRD verified at 0 `qa_handoff` occurrences in both files — `Dockerfile:50 COPY examples/` puts the request inside the image, which is also why `frozen_image_ids` pins it | runtime-api `afa3d44bf0d7` · max `79f4cd50888e` · neo `f0a8763936ab` · nat `1463d82507ca` · bob `3538b8cd506a` · eve `b366dfdc9a22` · data `612264db115f` | shakeout round 2; the pre-registered prediction | **Round 2 — both halves accepted, boot PASS, functional, zero intervention.** React `cyc_69d34bc41c20` (60 min): **1 correction round**, 20/20 criteria, L1 0 of 21, 0 skips — and #1406's own path ran here (a qa repair's patch verification) carrying **no skips**, criteria whole. Next.js `cyc_c45d60c9eb16` (60 min): 1 correction round, 17/17, 0 skips — and **L1 did not hold: 2 contentless `qa_test_handler` of 24**, the first non-zero in six rolls, recovered by retry-with-fact then repair. Ruled non-blocking and split, above; mechanism filed as **#1434**. **The pre-registered prediction is confirmed** (registered `98f4e9b4`, 16:50:18Z, before the 16:50:34Z launch): the retired name appears **0 times in 0 artifact files** against a 51–72 baseline across deploys B and C, and `retired_artifact_criterion_stripped` fired **0 times** — the planner's prior was entirely request-fed. `task_plan.py`'s compensation is now **unexercised on this corpus**: not removable (a caller's own PRD may still name the file, which is its scoping argument) but a regression in that path would no longer be visible to the verification sets, and the record says so. Instrument finding **#1431**: the record's "failed emissions banked" counted artifacts, not emissions — one failed qa.test banking three artifacts read as 3; fixed to report both (#1432). |

### Correction — three loaded checks that never ran (#1425)

`loaded_checks` was keyed on the container name, so a second probe for one service needed a
distinct key; the suffix invented for that (`bob-1-7-4`) was docker-exec'd as
`squadops-bob-1-7-4`. **Three of the seven probes therefore errored at every 1.7.4 launch,
including deploy B's checkpoint pair, which was read as clean.** A probe that could not run
is an unasked question, not a failed one, and in the recorded identity the two are
indistinguishable — which is why four answering probes read as a clean deploy.

What this does and does not cost, stated exactly:

- **The pair's behavioural evidence stands.** It is cycle outcomes, not probe readings, and a
  checkpoint pair injects no faults, so nothing it concluded rested on the three.
- **Deploy B's row above is not wrong.** Its runtime-api claims (pool codec, domain-error
  handlers, migration lock, `cryptography`/`pyasn1`) came from `deploy_B.sh`'s own readout,
  not from the driver probe.
- **One half of that row was weaker than it read.** Both the manual readout and the probe took
  `DispatchConfig().task_timeout` off a freshly constructed model — the schema default whatever
  the deploy carried, a row that can only pass. Read from the loaded config on deploy C, the
  deploy leaves `dispatch.task_timeout` unset and the orchestrator's hung-agent wait is joined
  to `llm.timeout` at **1800 s**; the control confirms a set value moves the two apart. #1147's
  documented default, now measured rather than assumed.
- **The two fault seams were never probed on B by any path.** They were proven behaviourally on
  deploy A instead, where every diagnostic reached its seam.

All three answer on deploy C — `builder-fault-seam` `True True True`, `analyzer-fault-seam`
`True True`, `rider-surfaces` `True 1800.0 None 1800.0 True True` — and preflight now refuses
to launch on any probe that could not run, so this cannot recur silently on the pinned deploy.
### H1's live readout, and why an empty field is not evidence

H1 holds by construction — the rejection class is gone — and the owner's ruling is that it be
reported that way, with the required-files readout as its live content. That readout has two
sources, and **both are structurally empty on a roll with no correction round**, so an empty
H1 field must not be read as "measured, nothing found".

- **The typed-row source cannot see the framework's row at all.**
  `_build_typed_check_evaluation_artifact` (`src/squadops/capabilities/handlers/cycle/validation.py:252`)
  keeps only rows whose `check` starts with `acceptance:` — deliberate, per #114, so the gate
  evaluator can tell "no typed checks ran" from "all passed". `required_files_row()` emits
  `check="required_files"` with no prefix, so the framework row is filtered out at **both** seams
  that emit it: the builder's own emission (`builder.py:523`) and the accepted-patch re-derivation
  (`patch_verification.py:648`). The driver's `required_files_rows` field therefore reports typed
  *acceptance criteria* named `required_files`, never the framework's evidence. Deploy A recorded
  the same fact for the patch path and moved F1 onto the executor's log line (#1398); the builder
  path has it too.
- **The log-line source only fires on a patch.** `required_files_declared` is derived from
  runtime-api lines containing `re-derived required_files`, which the executor writes on the
  accepted-patch path alone. A roll with zero correction rounds produces none.

Round 1's React half is the demonstration, and the run report settles what the driver's fields
cannot show. The implementation run records **57 checks executed, 57 passed, zero unverified**,
against the 34 rows the driver's `by_check` can see — the difference is the framework rows, which
execute and are counted but are not `acceptance:`-prefixed. So `required_files` ran and passed on
a builder whose required set is `['Dockerfile']`, with the handoff absent from it: exactly the
row-1 change H1 exists to protect. Both H1 fields were empty on that same roll. **The bar held and
the readout could not show it** — which is why the record states the bar as holding by
construction and cites the run report, not the H1 fields.

**The Next.js half supplies what the readout cannot: a counterfactual, measured.** That roll's
builder emitted **`QA_HANDOFF.md`** — uppercase — while the definition of done asked for
`qa_handoff.md`. `required_files_row` matches basenames exactly and case-sensitively
(`item not in have`), so replaying this roll's own emission through both contracts gives:

| contract | `passed` | `missing` |
|---|---|---|
| retired (`qa_handoff.md`, `Dockerfile`) | `False` | `['qa_handoff.md']` |
| current (`Dockerfile`) | `True` | `[]` |

**This shakeout roll would have been rejected under the retired contract, on filename casing
alone, and was accepted under the pack's.** That is H1's bar with live content — not an empty
field, and not an assertion that a bar survived a test it cannot fail. It also sharpens #1427:
the request still names a document whose exact casing decided acceptance, which is the fragility
row 1 removed.
### Round 2's prediction, registered before the round is launched

Deploy D is deploy C plus #1430 — the request no longer names the retired handoff — and
nothing else behavioural. `task_plan.py` still carries the compensation that strips a
retired-artifact criterion from tasks that do not declare the file, and its comment records
the prior it was built against: *213 of 213 builder criteria in the last 40 stored plans
named it*, the planner being "a language model with a strong prior about this filename".

**The claim.** That prior was fed by the request. If it was, removing the name from the PRD
removes it from the plans; if the prior is the model's own, it will persist and the
compensation is load-bearing for reasons the request never controlled.

**The baseline, counted from stored artifacts** (which survive a rebuild; the runtime-api
logs do not) — occurrences of the retired name per cycle, across deploys B and C:

| cycle | deploy | files mentioning it | occurrences |
|---|---|---|---|
| `cyc_dd3068d22f2c` | B, React | 10 | 65 |
| `cyc_bd6d424ba2fb` | B, Next.js | 10 | 62 |
| `cyc_00872b888f80` | C, React | 10 | 72 |
| `cyc_cb132e22956c` | C, Next.js | 7 | 51 |

**Expected on round 2:** a sharp fall in both columns. A residue is not a falsification —
the planner may still reach for the name unprompted — but a count in the 50–70 band would
say the request was never the source, and that is worth knowing before the counted set,
because it changes what #1430 bought.

Read, not a gate. Registered here before launch; the result lands in deploy D's row.
### A sixth ruling, recorded before the counted set opens (#1434)

Round 2's Next.js half breached **L1** — 2 contentless `qa_test_handler` emissions of 24 logged,
the first non-zero in six 1.7.4 rolls — and the roll was still **accepted, functional, 17/17,
with zero intervention**: the emission was retried with its fact (R1 read 1 aimed / 1 with fact /
0 blind), then repaired in one correction round, patch-verified on 8 checks with no skips, and
retested green.

**Owner's ruling: a recovered roll does not block the cut.** 1.7.4 is the recovery-half line and
this is the machinery doing what it was built to do — the failure was detected, retried, banked,
escalated, repaired and reported, with nothing hidden from the instrument.

**L1 is therefore split rather than downgraded**, so the regression signal is not lost with the
blocking half:

- **Blocking:** a counted roll whose contentless emission is **not recovered** — it costs the
  roll its verdict or its functional reading.
- **Tracked, never blocking:** the **occurrence count** on every counted roll, reported beside
  the emissions logged. #1268 measured this class at zero in 1.6.6 and fourteen across the 1.7.1
  counted rolls; 1.7.2 recorded 0 of 172. The 1.7.4 shakeouts stand at 2 of 118.

At n=2 that is not distinguishable from noise, which is the reason to track it across the counted
set rather than rule it a regression now.

**Why this ruling is legitimate here and would not be later.** Changing a bar's semantics after it
fires is the goalpost-moving pattern this line has been strict about. It is admissible only
because **the counted set has not opened** — this is pre-registration, which is when semantics are
settled. Recorded here, with its rationale, rather than applied silently at the reading.

**The candidate mechanism is named and is not yet decided (#1434).** #1268 was closed by
`446ebae4`, which gave `qa.test` its reasoning channel back after measuring `think:false` at 1
usable emission in 6 against 6 in 6 for both `think:true` and no `think` key. #1285 — pack row 10
— re-declared `NONE` for the **fill** shape, wired at `qa_test.py:1300`, so a fill-mode `qa.test`
sends `think:false` again. Every `think:false` roll in this line is a Next.js fill-mode roll and
the only breach is one of the two; both `medium` React rolls are clean. #924's fill measurement
(413 vs 5,727 completion tokens) measured **token cost**, not **usability at rate** — that is the
gap row 10 landed in. Whether to revert the declaration or let the counted set read it is Q1's
question, which this set was registered to answer.

**Owner's decision, before round 3: leave the declaration in place and let the counted set read
it.** Reverting now would pre-empt the measurement the set was registered to make, and would make
Q1 read null *by construction* rather than by measurement; n=2 is too thin to discard a pack row.
The accepted cost is wall-clock — each occurrence buys a retry and a correction round — not
validity, since the ruling above makes occurrences non-blocking and the roll's verdict is
unaffected. Q1's reading therefore answers a real question: whether the fill shape's token saving
(#924: 413 vs 5,727 completion tokens) is worth its emission-usability cost (#1268: `think:false`
at 1 usable in 6, measured on the authoring shape). A third wire neither option covers — omitting
the `think` key, which #1268 measured at 6 in 6 — stays available if the set reads against the
declaration.
---

## 3. The exercise plan — stated before roll 1

| claim | category | reached by an ordinary roll? | exercise plan and field | result |
|---|---|---|---|---|
| **L1** (#1268) | bar | yes — every roll | `contentless_emissions`, qa first attempts | — |
| **H1** (#1312) | bar | yes — every roll | the roll-up's `required_unmet` and the typed rows by check: no `qa_handoff.md` required, no `sections_present` row for it; the readout lists every required file, not the handoff's | — |
| **F1** (#1374) | live hypothesis | on every roll whose accepted patch supplies a framework row's subject | `framework_rows_rederived` (#1398) for the concrete case; the per-row comparison against a re-derivation over the stored accepted tree lands with #1374; the contentless-builder diagnostic is the deterministic exercise (steps 2 and 6) | diagnostic on A: **the seam reached** (`cyc_ceef5581bfd1`) |
| **B1** (#1087/#1112) | live hypothesis | yes — every roll with a qa fill | `static_checks.non_root_fixture_tables` (#1378) | — |
| **Q1** (#1285) | live hypothesis | yes — every Next.js roll | `emission_tokens_by_handler` by shape, under the second reasoning declaration | — |
| **R1** (#1372) | seam invariant | no — L1 keeps qa at zero, the builder's contentless emission is rare | the contentless-builder diagnostic (steps 3 and 4 after #1372); `retried_with_fact` / `retried_blind` beside `emission_retries` (#1378); live contentless retries are texture | pre-#1372 on A: **0 retries aimed** — the builder's contentless attempt is a semantic failure with no marker, as the wiring test asserts |
| **H2** (#1312) | seam invariant | CI | the appendix renderer under present / absent / superseded notes; live: appendix presence per task with the producing artifact id | — |
| **W1** (#994) | seam invariant, **CI-only on this line** | no | no honest fault exists (preamble); CI on the repair-then-continue path; live: rewind occurrences against `applied_patches` | declared before roll 1 |
| **A1** (#968) | seam invariant | no | `1-7-4-diagnostic-absent-suite-then-false-claim` (the analyzer runs only behind a failure, #1298's chain); read from `decision_inherited_claims` — the marker, the claim's substance, and non-task-type entries (#1401) — beside `analyzer_claims_dropped`. **Pre-#968 the expected reading is NO with the decision named** | `cyc_1063c4dca548` on A: **NO, as expected** — round 0's decision carried the claim in substance; the live readout had said YES (fixed, #1401) |
| **D1** (#1054) | seam invariant | CI | the locus classifier under decisions naming each task-type family; live: `affected_task_types → correction_repair_locus` pairs | — |
| **L2, L4, L7, L8** (1.7.3) | seam invariants | unlikely | the three 1.7.3 diagnostics re-run on A and on the pinned deploy | **All reached on A** — L2 (`cyc_1b54b29e2a99`, two rounds; twice more in the analyzer chain), L7 → L4 → L5 (`cyc_a26c6828482c`), L8 (`cyc_b80f0ea3ca64`: one strip, nothing stored under the placeholder) |
| **T1** (#995) and the texture | texture | when it occurs | the fields in plan §4's texture table, plus `prefect_loop_overruns` (#330, #1396) | — |

**Diagnostics on A, all done:** contentless-builder, absent-suite-then-false-claim,
absent-suite, own-frame-then-prose-repair, path-prefix — every seam reached; A1 falsified in
substance as expected before #968. All are re-run on the
pinned deploy before roll 1 with the two-run budget.

### 3a. Five rulings recorded BEFORE the diagnostics run (2026-09-08, owner-approved)

The pack merged between deploy A and deploy C, and three of §3's expected readings were
written against a tree that no longer exists. A reading corrected after the run is not a
prediction. These are recorded before the pinned deploy's diagnostics, and before roll 1.

**1. A1's expected reading FLIPS to *holds*.** §3's row says *"pre-#968 the expected reading
is NO with the decision named"*, and deploy A confirmed it — round 0's decision carried the
refuted claim in substance. #968 landed (PR #1418): the analyzer's prose is now checked for
paths the workspace lacks, and the decision is handed the refutation beside the unedited
analysis. **On the pinned deploy the expected reading is YES** — the decision reaches its
verdict carrying neither the marker nor the claim's substance — read from
`decision_inherited_claims` beside `analyzer_claims_dropped`. A NO now falsifies the
invariant rather than confirming the gap.

**2. R1's expected reading FLIPS to *retried with its fact*.** §3's row says *"pre-#1372 on
A: 0 retries aimed — the builder's contentless attempt is a semantic failure with no
marker"*. #1372 landed (PR #1414): the builder banks the marker and lets D5 classify, so its
first contentless attempt is retryable, and the retry carries fence counts and the model's
own opening words. **On the pinned deploy the contentless-builder diagnostic is expected to
show one retry in `retried_with_fact`, none in `retried_blind`.**

**3. H1 holds by construction, and the record says so rather than claiming a test.** No
counted roll can be rejected on a handoff no build profile requires — #1312 removed the
requirement, the criterion and the document. The bar is not evidence that survived a trial;
it is a rejection class that no longer exists. Its live content is the readout naming **every
required file the roll's own rows declared**, which is what would catch H1's own blind spot:
a NEW required file the profile derives, failing identically under a different name.

**4. #1406 does not gate this set; a roll it touches is disclosed by name.** The defect
under-reports criteria on ACCEPTED rolls — a criterion re-asked where its toolchain is absent
skips, and the skip erases an earlier executed-and-passed row. It can only ever REMOVE
credit, so it can make a good roll look worse and can never make a bad roll look better, and
neither bar is exposed to it: L1 counts contentless emissions, H1 counts handoff rejections.
Pulling the framework fix into this line would mean editing the verifier immediately before
the measurement it produces, forcing a new deploy and a fresh shakeout loop — the riskiest
available change, for accuracy in the one direction that cannot flatter the result. It stays
in 1.7.5 (plan §6a). **The condition, registered here:** any counted roll accepted with
demoted criteria is named in the record with the criteria it lost, and its criteria-coverage
figure is never quoted as whole. PR #1407's readout prints exactly that — the adverse
criteria by name, and the skips that caused them, including on a verification that passed.

**5. Q1 is read, never a gate.** The second reasoning declaration (#1285, PR #1422) landed
hours before this deploy and this set is its first measurement. If the fill-mode saving does
not show at roll level, that is a finding for the record, not a reason to hold the cut.

**And the attribution rule for deploy C's shakeout pair:** a red here is **the pack's**, as a
red on deploy B's pair was the rider's. Nothing in the pack has been exercised by a live
cycle; this pair is the first thing that does.

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — the measurement, six rolls

The 1.7.3 §4 held verbatim — scoring, validity, the texture list — with §3's table as the
claims. **Known non-pack rejection cause, declared before roll 1: none** — #1312 was that
cause and is the pack; it showed once more on deploy A (the path-prefix diagnostic, a booting
app rejected on the omitted handoff), which is H1's reason. Packaging findings stay reporting-only.

## 5. Next.js+TS (`nextjs_ts`) — three rolls

The 1.7.3 §5 held verbatim; Q1 is exercised on every roll of this arm.

## 6. Delegation

As 1.7.3 §6: the owner delegated the line; the driver approves the gate with §7's constant;
every decision the plan author made is in plan §8 for the owner to overrule.

## 7. Gate constant

The 1.6.3 §6 text, verbatim in each set config's `gate_notes`.

## 8. Prohibited while open

As 1.7.3 §8: no merge to `main`, no rebuild, no config or profile change while a set is open;
a driver-only fix re-renders from stored identity and is named in §2.

---

## 9. Plan revisions recorded on this line

- **#353 is not landed on this line** (plan §3.5's rule: a row that does not land revises
  the plan in the open with the reason). It is a SIP-0084 governance change — the fragment
  manifest's hashes stamped at build rather than hand-maintained — that warrants its own
  small SIP or amendment; the #351 CI guard contains the debt (a stale hash cannot merge).
  Carried to 1.7.5 by name.
- **W1 is CI-only** (above).
- **R1 is a seam invariant** (plan rev 3), not a live hypothesis.
