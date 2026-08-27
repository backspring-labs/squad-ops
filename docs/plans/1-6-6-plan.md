# 1.6.6 — plan

**Revision 1, 2026-08-27.** Written the morning the 1.6.5 verification sets closed, from those
sets' banked per-roll records and nothing else: twelve counted rolls on frozen deploy `7ebdb00e`,
Next.js+TS 6 of 6 with zero correction rounds, FastAPI+React (`fullstack_fastapi_react`) 2 of 6.
The pre-registration is `docs/plans/1-6-5-verification-set-preregistration.md`; every prediction
on both sets held, so nothing here reverses a 1.6.5 item. **This plan is about one thing: the
FastAPI+React roll success rate**, and it is derived the way the 1.6.4 and 1.6.5 plans were — from
the per-round test reports and emission timelines of the rolls that went red, not from the
roll-up, not from the audit, and not from a sweep.

**The owner's rulings that shape it (2026-08-27):** file every finding (done — #1125 #1126 #1127
#1128 #1129 #1130 #1131, and #1111 re-evidenced); the structural refactor that separates stack #1
from the "generic" scaffold is **#1131 and belongs to 1.7**, not here; 1.6.6 carries the fixes
that most raise the React arm's success rate, patched in place.

---

## 1. What the FastAPI+React set actually found

Six rolls, four rejected. The rejections are not four stories; they are two mechanisms and a
long tail, and **one scaffold defect sits under five of the six rolls.**

| roll | cycle | verdict | audit | rounds | how it ended | what was under it |
|---|---|---|---|---|---|---|
| 1 | `cyc_b9296c255dfc` | rejected | PASS | 3 | attempts exhausted | #1125 round 0 (repaired); then #1127 → #1126 discarded the green → #1111 misdirected round 1 |
| 2 | `cyc_f84649c68646` | accepted | PASS | 1 | green **by repair** | #1125 round 0, one-line dev repair landed |
| 3 | `cyc_184b3a1d194e` | rejected | FAIL | 2 | plan_defect (correct) | #1128 unsatisfiable contract; #1130 qa-owned TypeError never routed |
| 4 | `cyc_5ef83cc6fc2b` | accepted | PASS | 1 | green **by repair** | #1125 round 0, one-line dev repair landed |
| 5 | `cyc_0e7bc622169a` | rejected | FAIL | 2 | plan_defect after **zero applied repairs** | #1125 round 0; #1129 refused patch counted as a round |
| 6 | `cyc_d43c644e52d0` | rejected | FAIL | 2 | plan_defect after **zero applied repairs** | #1125 round 0; #1129 — the refused patch carried the correct fix |

**#1125 is the round-0 tax.** When the manifest author writes an optional field as
`required: false, default: null`, `src/squadops/capabilities/scaffold.py:1332-1340` freezes
`distance: str = None` — a non-nullable annotation with a `None` default — because `default: null`
sets `has_default` (`:486`) and the nullable branch only fires when no default key exists. The
request shape is correctly `str | None`, so the route forwards `None` into `Run(...)` and pydantic
returns 500 on POST /runs; every dependent probe then fails on an unresolved `{run_id}`. Five of
five manifests with the key hit it; zero of three without (roll 3 and both shakeouts). Rolls 2 and
4 recovered it with the one-line repair `payload.distance or ""`; rolls 5 and 6 did not, and the
reason they did not is the second mechanism.

**#1129 is why a repairable defect ended two rolls.** Both repairs on rolls 5 and 6 were whole-file
rewrites of `backend/routes.py`. Roll 5's dropped the router and every decorator and was refused
by the structural gate (`unresolved_imports`); roll 6's carried the **correct** fix inside a
rewrite that switched to a prefixed router, and the literal `endpoint_defined` check refused it.
In both, no retest ran, `qa.test` was re-dispatched against the unrepaired tree, the failure
signature was unchanged by construction, and `correction_terminated_plan_defect` fired on
"signature repeated from round 0". The terminal cannot tell "the repair did not help" from "the
repair was never applied".

**Roll 1 is the long tail, and it is the shape of the React arm's qa problem.** The first
frontend suite failed "Found multiple elements" because the frozen `test-setup.js` registers no
`afterEach(cleanup)` and vitest runs `globals:false` (#1127). After a failed retest the executor
re-dispatched `qa.test`; the new suite rendered the real `App` with `fetch` stubbed and passed
3/3 — and `detect_self_mocking_tests` failed the handler, because its "imports a real route"
discriminator is literally an `app/api/` import, the Next.js in-process model (#1126). Between
those, the round-1 analysis re-diagnosed the already-repaired backend defect because the qa
task's failed report and typed-check evaluation had been re-stored over the passing retest in the
same second (#1111, now a loop defect rather than a record nit).

**Roll 3 is the loop being right.** The manifest wrote `request: Participant` — an entity, not a
declared request shape — which validation accepts (`scaffold.py:438-440`) and the contract
generator cannot resolve (`src/squadops/capabilities/scaffold_contract.py:439`, `:537-541`), so
both participants probes shipped `json: {}` expecting 201 then 409 against a route that requires
`name`. Unsatisfiable by construction; `plan_defect` was the correct verdict (#1128). The same
roll's backend suite called `client.delete(url, json=…)` in every round and nobody was ever
dispatched to fix it (#1130).

**What held.** #1120's fix — never an empty dev-role target — held 6 of 6, as did the typed-models
floor, the qa completion cap (max 7,697 of 12,288) and the post-self-eval suite ordering. Both
greens were by repair; **none by re-dispatch**, the distinction the 1.6.5 pre-registration asked
the release notes to keep.

---

## 2. The pack

### 2.1 Six items, ordered by rolls flipped per line changed

Each item is one row of §1's last column. A and B change frozen scaffold output and share one
GENERATOR_VERSION bump; C, D and F change loop and check code that Next.js never exercised in its
set (zero corrections) and are therefore measured on the React arm only; E changes the shared
contract generator on a path no Next.js manifest took.

**A. Nullable frozen fields for `default: null` (#1125).** In `_model_source`, a field whose
declared default is `None` — or that is not required — is emitted as `{ann} | None = None`, the
branch that already exists for the no-default case. A generator test with
`required: false, default: null`; `tests/unit/capabilities/test_scaffold.py:68` covers
`has_default` only for the list case today. This is the largest single item in the pack: it
removes the round-0 defect from the five rolls where it fired. Whether a roll then accepts is
what §3 measures; the 1.6.5 evidence is that two of the four repairs of this defect landed and the
other two were refused for reasons D addresses.

**B. `afterEach(cleanup)` in the frozen React test harness (#1127).** One line in the scaffold's
`test-setup.js` source (`scaffold.py:1622`): import `cleanup` and register it, so RTL unmounts
between tests under vitest's `globals:false`. Every "Found multiple elements" failure in the set
traces to a suite with `render()` in more than one test and no cleanup; the one suite that added
it was green. Rides A's GENERATOR_VERSION bump.

**C. The self-mocking predicate becomes stack-aware through the seam that exists (#1126).**
`detect_self_mocking_tests` takes the stack (or is consulted through `check_stack_for`,
`scaffold.py:2092`): on `nextjs_ts` "invokes the application" stays an `app/api/` import; on
`fullstack_fastapi_react` a real component or `App` import invokes it, and `vi.mock` of the app's
own `api.js` is the self-mock. **Not** a third regex in the shared file, and **not** the module move —
that is #1131 in 1.7. Test: the stored roll-1 suite (`art_477b87f85956`) passes on the React
stack and a `vi.mock('../api.js')`-only suite is the one flagged. Replay is the proof: the exact
file that was discarded.

**D. A refused patch is not a round (#1129).** When `patch_verification` refuses a repair, the
runner retries the repair once with the refusal reason as evidence before any retest or
re-dispatch; and the repeated-signature terminal keys on `(signature, patch_applied)` so a repeat
after a refusal can never satisfy it. Two sub-points ride along: the repair brief says *edit
minimally, keep decorator paths literal* (roll 6's patch was correct and was thrown away on a
convention), and `endpoint_defined` resolves an `APIRouter(prefix=…)` when it reads the decorator.
`adapters/cycles/correction_runner.py:1203` and
`adapters/cycles/dispatched_flow_executor.py:3087` are the two sites. Replay proof: rolls 5 and
6's stored refusals through the runner produce a retry, not a termination.

**E. One resolver for an endpoint's request body (#1128).** The contract generator and the route
emitter agree on what `request: X` means: a declared shape's `required` fields, else the entity's
required, non-generated fields. `entity_field_names` is already computed in
`scaffold_contract.py` and unused for this. Test: an endpoint whose `request:` names an entity
yields a probe body with that entity's required fields, on both stacks' fixtures. Roll 3's
manifest through the generator is the replay.

**F. The passing retest is what the qa task stores (#1111).** After a passing retest, the qa
task's run-end re-store must not overwrite `test_report.md` and the typed-check evaluation with
the failed forms. Filed on 2026-08-26 as a record inconsistency; roll 1 showed the analyzer
reading the re-stored failure and sending round 1 at a fixed file. Small, and it protects every
item above from being misread by the next analysis.

### 2.2 What is deliberately not built

- **#1131 — extracting stack #1 into its own module and the structural guard against
  stack-shaped literals outside `stack_*`.** Owner's ruling: 1.7. The fixes above are patched in
  place so the 1.6.5 record describes the tree that was measured; the move follows with
  byte-identical fixtures as its proof. C is written so that the predicate it adds is the one the
  seam will own after the move.
- **#1130 — routing a qa-owned defect in a free-authored suite to `qa.test_repair`.** One roll,
  and it is the same design question as #1123 (targeted qa repair on this stack) and #1122
  (SIP-0104 for stack #1). A narrow routing hack here would be a second path to the same place;
  it goes with those in 1.7.
- **A Next.js set.** A, B and E do not change Next.js output (A is the Python emitter, B the
  React harness, E a manifest shape no Next.js roll used — the fixtures must stay byte-identical
  and that is asserted); C, D and F change code the Next.js set never executed. One Next.js
  shakeout is the regression, not six rolls (§3).

### 2.3 Instrumentation, because the set will need it

- The driver's `loop_texture` gains `refused_patches` (count and reason) and
  `plan_defect_after_zero_applied` so D is readable from the record, not the executor log.
- The P0 static check on `fullstack_fastapi_react` asserts every optional entity field in the
  frozen `models.py` is nullable when the manifest says `default: null` — A's prediction as a
  per-roll fact.

---

## 3. The verification set — test the mechanism, not the rate

A FastAPI+React counting set, **N = 6**, same driver
(`scripts/dev/verification_set_driver.py`), a new set config beside the 1.6.5 ones in
`docs/plans/verification-sets/`, one frozen deploy after every item is merged and rebuilt, one
Next.js shakeout on the same deploy before roll 1. Pre-registered before the first counted
launch, in a document of its own, with these predictions read only from the evidence named:

| # | prediction | falsified by | read from |
|---|---|---|---|
| **R1** | (A) no frozen entity field is emitted non-nullable with a `None` default | one `string_type … input_value=None` on a frozen field, or the P0 assertion in §2.3 | frozen `backend/models.py`; per-round `test_report.md` |
| **R2** | (B) no frontend report fails "Found multiple elements" | one such line | per-round `test_report.md` |
| **R3** | (C) no suite that imports `App` or a view component is failed by `no_self_mocking_tests` | one `handler_failed` on a suite whose own report passed | eve log + stored suite |
| **R4** | (D) no run terminates `plan_defect` with zero applied patches | one `plan_defect_after_zero_applied` in the record | driver `loop_texture` |
| **R5** | (E) no POST probe on an endpoint with a `request:` carries `json: {}` | one such probe | `verification_contract.yaml` |
| **R6** | (F) after a passing retest, the qa task's stored report is the passing one | one failed re-store over a passing retest | artifact vault timestamps |
| **S0–S3, Q3** | carried from 1.6.5 unchanged | as there | as there |

**Texture, no prediction attached:** the verdict rate against 2 of 6 (reported with its Wilson
interval, no significance claimed at N=6 — the 1.6.5 interval was [10%, 70%]); correction rounds;
greens by repair versus by re-dispatch, counted separately; the `stores_beyond_roots` edges.

**Early stop, one direction, as before.** A falsified R1–R6 stops the set: the fix did not work
and the remaining rolls teach nothing about it. A good result is never grounds to stop early.

---

## 4. Sequencing

1. **A + B on one PR** (one GENERATOR_VERSION bump, fixture regeneration with the owner's OK —
   pins are proposals). Replay: the five 1.6.5 manifests with `default: null` through the emitter
   produce nullable fields.
2. **F**, small and independent.
3. **C**, with the roll-1 replay as its test.
4. **D**, with rolls 5 and 6's refusals as its replay.
5. **E**, with roll 3's manifest as its replay.
6. Rebuild agents and runtime-api, verify the loaded modules in-container, one shakeout per
   stack, pre-register (§3), roll. No merges to main while the set is open.
7. Cut 1.6.6 from the closed set's record; then 1.7 opens with #1131 first.

Items 1–5 are independent branches off main; they merge in this order because 1 and 2 are the
ones the set cannot read without, and 3–5 each carry a replay from a specific 1.6.5 roll.

---

## 5. What this plan does not decide

- **The 1.6.5 cut.** Its record (docs/plans/1-6-5-verification-set-record.md, to be written from
  the banked roll records) and its release notes are a separate deliverable; this plan is what
  comes after them.
- **Whether 1.6.6 is the last 1.6.x.** If §3 closes with no falsified prediction, 1.7 opens with
  #1131; if it falsifies one, the answer is a 1.6.7 with that item and nothing else.
- **The `lite` fault-injection arm** the 1.6.5 plan left to the owner — still the owner's.

---

## 6. Revision history

- **Rev 1 (2026-08-27)** — written from the 1.6.5 set records the morning both sets closed;
  issues filed the same morning on the owner's go.
