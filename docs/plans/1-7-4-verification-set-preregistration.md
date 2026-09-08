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
| C | — | — | the pack; the shakeout loop to the exit rule; the pinned deploy is the last one | — |

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
