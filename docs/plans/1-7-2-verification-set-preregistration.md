# 1.7.2 — Verification Sets: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Merging it is the owner's act and does not change what it pre-registers; the
branch commit is the record. Revised while the shakeout loop runs — each round's finding
becomes a merged fix and, where the fix is in deployed code, a new deploy (§2) — and frozen
before the first counted launch.

This is the 1.7.2 plan's §4 (`docs/plans/1-7-2-plan.md`) as data: **six counting rolls on
FastAPI+React** and **three on Next.js+TS** (up from 1.7.1's two — both its Next.js rolls
went through the contentless-emission path, so this arm reads L1 directly and L2/L4 fire
here first). Everything not restated here is inherited **verbatim** from the 1.7.1
pre-registration and, through it, 1.6.6/1.6.5/1.6.4/1.6.3: §5 (scoring), §5.1 (roll validity
— void / reset / counted), §6 and §6.1 (the gate constant and the two approval paths), §7
(prohibited while open).

**What is different this time, and why.** The 1.7.1 record §7 named two failures of the
instrument, not of the squad: predictions that no roll happened to exercise were reported as
silence, and three readouts counted rows whose reason was not the one the prediction names.
Both are answered here rather than noted:

- **§3 states an exercise plan for every prediction before roll 1.** Where a roll is
  unlikely to reach one, a fault-injected diagnostic (#1251) runs the roll's own path with
  the fault. "Unexercised" on a counted roll then reads as "exercised by injection,
  held/falsified", not as silence.
- **Every readout is read by its reason** (#1276), and the record counts contentless
  emissions and non-execution beside failure.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **6 counted** on FastAPI+React (§4) and **3 counted** on Next.js+TS (§5). 1.6.6 §1.3 on what these sizes can and cannot say holds unchanged: exercise, not a rate. |
| Bar | **one, and only one: L1** (§4). Every other prediction is pass/fail on its own terms with no rate bar, as in 1.7.1. |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6, 1.7.0 and 1.7.1, so the pack is the only variable |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React `c4d6a2165acf`, Next.js+TS `d4d4f66217d8` — **both unchanged from 1.6.6/1.7.1** (the pack changed code, not configuration); observed on the round-1 shakeouts of each arm; asserted on every counting roll; a roll on any other hash is void |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` — unchanged from 1.6.6, 1.7.0 and 1.7.1; a roll on any other snapshot is void |
| Deploy — commit | **filled from the last shakeout** (§2). A pin here is a value an operator types and nothing can check — `SOURCE_HASH` is a build arg, not an `ENV` or `LABEL`, so the commit an image was built from is unreadable at runtime (#1296). **The image ids below are the assertion**; this line is a label. |
| Deploy — 7 image ids | **filled from the last shakeout** (§2); asserted at every counting launch by the driver, which refuses a roll on any mismatch. |
| Loaded, not built | Verified per container as a **live call with its paired control**, never a symbol import: a symbol can be present and unreachable, which is the shape #1289 had for the whole of 1.7.1. The calls are in each set config's `loaded_checks` and their output is recorded in every record (#1297). |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-7-2-<arm>.yaml --roll N` — one roll per invocation |
| Order | FastAPI+React rolls 1–6 first (the measurement), then Next.js+TS rolls 1–3 |

---

## 2. Preconditions and the shakeout log

- **Counted launches run from `main`** (the owner's 2026-08-27 ruling), which requires this
  document and the two set configs to be merged before roll 1.
- **The shakeout loop with its exit rule**, stated before the first launch as
  `docs/plans/verification-sets/README.md` requires: **exit on a pair on one deploy with no
  new seam finding**; **budget three pairs**; the cut record reports how many it took,
  because that number is evidence about the pack. A finding is a defect in a seam the pack
  touched, or a prediction's readout that cannot see its own miss; a defect in the
  application a cycle built is the cycle's, not the deploy's, and does not reset the loop.
- **A fix to the instrument does not supersede the deploy.** The rule's remedy — rebuild and
  run both stacks again — presumes a fix to *deployed* code, because that is what changes
  what a cycle does. A driver-only fix changes how a cycle is reported; re-running one to
  change its rendering would produce the same measurement and cost a round. Such a round is
  **kept**, its records re-rendered from the stored identity, and the fix is named here.

### Deploys and what each pair found

| deploy | built | pair | result and findings |
|---|---|---|---|
| (`d6165d2a`) | 2026-09-04 15:31Z | **round 1 — both arms green** · React `cyc_0ac33bb2230b` accepted/PASS/functional, 61 min · Next.js `cyc_380505d906cc` accepted/PASS/functional, 52 min | **#1296** (PR #1297) — a record could not name the deploy it observed; instrument-only. **#1298** (PR #1299) — a fault declaration could not survive the set config: a list override was stringified so the chained diagnostic could not launch at all, and a single fault was reported letter by letter. **Superseded**, because #1298's fix is in `fault_injection.py`, which runs in the agent containers. |

**Why round 1 does not exit the loop.** Both arms were green and neither cycle exposed a
seam defect. But #1298's fix is deployed code, and the rule is that a deploy on which a
shakeout produced a fix is superseded. The available counter-argument — that the change is
inert for a cycle declaring no fault, since `declared_faults` returns `()` identically in
both versions — is exactly the reasoning the rule exists to refuse, and the rebuild is
required regardless: the diagnostics cannot run until the new parsing is in the containers.
Round 1's readings are kept as evidence (below) and its deploy is not the pinned one.

**What round 1 measured, carried forward as texture rather than as a pin:**

| reading | React | Next.js |
|---|---|---|
| verdict · boot audit · functional | accepted · PASS · yes | accepted · PASS · yes |
| contentless emissions (L1) | 0 of 20 | 0 of 19 |
| criteria verified / total | 21 / 21 | 17 / 17 |
| correction rounds | 1 | 0 |
| non-execution by skip reason | 0 | 0 |
| gate decider | `system:no_open_questions` | `agent:005159fd…` |
| packaging (reporting-only, #598) | 0 | 1 — `npm_ci_without_lockfile` |

L1 held on 39 of 39 first attempts across both arms. The 1.7.1 comparison is 3 of 5 on
React and **0 of 2** on Next.js; a green Next.js pair member is the first in this line.

The `npm_ci_without_lockfile` row is a defect in the application the cycle built, which the
exit rule places with the cycle rather than the deploy; it is reporting-only by design
(#598) and does not reset the loop.

**Round 2 folds the diagnostics into the pair.** A diagnostic is a non-counting cycle on the
same deploy, and it exercises the recovery path where this pack lives — so running the three
alongside the pair means a defect they expose resets the loop at the same cost as any other
round, instead of surfacing after the pins are set.

*(Superseded deploys stay in this table, parenthesised, with what their shakeouts found.
The pinned deploy is the last one.)*

**Not shaken out and not counted:** `cyc_cea47fc7a429`, a React cycle launched at 15:16Z on
the previous deploy (`c1b37193`, before #1292 merged) and cancelled at ~4 minutes with no
measurement. It is recorded here so the round count is not read off the cycle list.

---

## 3. The exercise plan — stated before roll 1

The 1.7.1 record's first finding: R2, R4 and R7 were unexercised on three of five React
rolls, and a diagnostic that hands a seam its input is a replay of the function, not an
exercise of the path. So every prediction below names how it gets exercised, and the ones a
roll is unlikely to reach get a **fault-injected diagnostic** (#1251) that runs the roll's
own path with a real shape a real roll produced.

**A diagnostic is never a roll.** The driver refuses to count a cycle whose config declares
a fault, and the record names the fault beside every readout it produces, so an injected red
can never be read as a real one.

| prediction | reached by an ordinary roll? | exercise plan |
|---|---|---|
| **L1** (#1268) | **yes** — every roll has a qa first attempt | read directly from the emission-shape readout on each counted roll |
| **L2** (#1269) | unlikely — needs a repair of an *absent* suite | diagnostic: `fault_injection: [qa_suite_absent]` — the emission carries no fence, the repair supplies the suite, and the prediction is whether that repair is retested |
| **L3** (#1271) | yes when any qa task is re-attempted | read from the summary's failed rows against the last stored evaluation |
| **L4** (#1273) | unlikely — needs a prose-only repair | diagnostic: chained, below |
| **L5** (#1260) | unlikely — needs a re-dispatch after a failure that named cases | **rides the chained diagnostic**, and needs no fault of its own: `prior_failing_cases` is threaded at the top of `_handle_task_outcome` (`dispatched_flow_executor.py:2889`) from *any* outcome carrying case evidence, before the retry/re-dispatch/repair decision |
| **L6** (#788) | unlikely — needs a runtime error in the delivered app | read from the stored repair brief whenever a roll produces one; no fault reproduces an app traceback honestly, so if no roll produces one the record says **unexercised** |
| **L7** (#1270) | unlikely — needs an own-frame failure in a qa-owned file | diagnostic: `fault_injection: [qa_suite_vitest_own_frame_type_error]` — roll 4's own one-line import edit |
| **L8** (#1272) | unlikely — the fence template was fixed | diagnostic: `fault_injection: [qa_suite_at_path_prefix]` |

**The chained diagnostic — one cycle, three predictions.** Declaring
`fault_injection: [qa_suite_vitest_own_frame_type_error, repair_prose_only]` fires each fault
on its own task in a single cycle: the first makes the qa suite fail in its own frame (L7),
the repair that follows is prose-only and must be refunded rather than verified (L4), and the
re-take after the refund must carry the original row's cases (L5). Verified as expressible:
`validate_declaration` accepts the pair, and `inject` applies the first to `qa.test` and the
second to `repair-…-qa.test_repair`.

If the refund takes another repair round instead of a re-dispatch, **L5 is unexercised and
the record says so.** Unexercised is not passed.

**Plan §3 says three predictions cannot be exercised without injection and §4 lists four.
Neither count is used here** — the table above is the statement, and it is four diagnostics
covering L2, L4, L7, L8 with L5 riding the chain.

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — the measurement, six rolls

| # | prediction | falsified by | read from |
|---|---|---|---|
| **L1** | (#1268) no qa first attempt is contentless | one contentless emission in a counted roll | emission-shape readout (chars, fences, finish reason) |
| **L2** | (#1269) a repair of an absent suite is retested; the run carries executed `tests_pass` | one such repair accepted with `tests_pass` never executed | patch/retest log lines; the summary's `unverified` |
| **L3** | (#1271) a run whose last attempt passed is never rejected on an earlier attempt's rows | one such rejection | the summary's failed rows against the last stored evaluation |
| **L4** | (#1273) every re-taken brief carries the original row's cases; no prose-only repair is verified | one 0-case re-take brief while the row carried cases; one prose-only repair verified | `repair_brief_case_counts` as (brief, row) pairs; refund lines |
| **L5** | (#1260) a re-dispatched suite carries every case the failed report named | one dropped case | the two stored suites, by case title |
| **L6** | (#788) a runtime-error repair is briefed with the traceback | one such brief without it | the stored repair brief |
| **L7** | (#1270, = 1.7.1 R2) an own-frame failure in a qa-owned file — including `is not a function` on vitest — is routed to `qa.test_repair` targeting that file | one such failure whose repair targets an app file | `qa_owned_routed`; `correction_repair_locus` lines |
| **L8** | (#1272) no emission lands under a literal `path/` prefix | one such artifact | stored artifact names |
| **R1, R3, R5; S0–S3, Q0, Q3, Q5, P0** | carried from 1.7.1 and 1.6.6 unchanged — unexercised is not passed | as there | as there |

**One bar, and only one: L1.** #1268 is the condition every other prediction is measured
*through*: a set in which a first attempt is still contentless has not measured the pack, it
has measured the loop's recovery from the same fault again. **A falsified L1 blocks the cut**
— the fix is revised from the new evidence and the set re-rolled — where 1.7.1's R2 did not.

**Texture, no prediction attached:** verdict rate against 1.7.1's 3 of 5 (no bar); correction
rounds; greens by repair versus re-dispatch; refused versus applied versus refunded;
contentless emissions per roll; qa primary tokens; `checks_by_environment`.

**What this arm cannot read:** a repair never attempted (L2, L4, L7 need a correction round —
hence the diagnostics); an app runtime error (L6); a manifest with no view anchors (R3).

**Early stop, one direction.** A falsified prediction stops the set. A good result is never
grounds to stop early. A stop in one set does not stop the other.

---

## 5. Next.js+TS (`nextjs_ts`) — three rolls

Three rather than two: both 1.7.1 Next.js rolls went through the contentless-emission path,
so this arm reads **L1** directly and **L2/L4** fire here first. #1292 also changes what a
Next.js roll does — the stack's qa namespace no longer claims the application, so the
scaffold-emission guard and every ownership decision keyed on that namespace answer
differently here and only here.

| # | prediction | falsified by | read from |
|---|---|---|---|
| **L1–L5, L7, L8** | as §4 | as §4 | as §4 |
| **L6** | as §4; vacuous unless a roll produces an app runtime error | as §4 | as §4 |
| **R6** | (#939) no `.ts`/`.tsx` emission with an unresolved name reaches test execution | one `ReferenceError: … is not defined` in a stored per-round `test_report.md` | `typed_checks.undefined_name_rejections`; per-round reports |
| **R7** | (#1229) no repair returns `unverifiable / no_executed_blocking_checks` because its toolchain was absent where verification ran | one such verdict | `unverifiable_by_reason`; `decided_by_agent` |
| **Q0, Q5, P0** | carried from 1.6.6 §4 unchanged | as there | as there |

**Vacuous here, declared rather than discovered:** R3/R4's anchor half binds only where a
manifest declares view anchors and a suite renders; Next.js suites call route handlers.

**Early stop, one direction, per set** — as §4.

---

## 6. Delegation

Executed by the assistant under the owner's delegation — FastAPI+React rolls 1–6, then
Next.js+TS rolls 1–3: launch, gate approval with the §7 constant, collection, and the
per-roll record. **The counted/void/reset reading and the prediction check are made at each
roll boundary before the next launch**; a reset or a falsified prediction stops that set for
the owner.

## 7. Gate constant

Inherited verbatim (1.6.3 §6, §6.1); the text is in each set config's `gate_notes`.

## 8. Prohibited while open

Inherited verbatim (1.6.3 §7): **no merges to main while the set is open.** The driver pins
HEAD at roll 1 and refuses a later roll on a different HEAD.
