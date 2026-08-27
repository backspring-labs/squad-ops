# 1.6.5 — Verification Sets: Record

**Closed 2026-08-27, 04:31 ET.** Two counting sets, twelve counted rolls, no voids, no resets.
Pre-registration: `docs/plans/1-6-5-verification-set-preregistration.md` (PR #1124, merged as
`fea4b5d6` before roll 1), in force from roll 1 and unchanged throughout. Deploy frozen at
`7ebdb00e` (the seven image ids in the pre-registration §1, asserted by the driver at every
launch) from both shakeout pairs through FastAPI+React roll 6; HEAD pinned at `fea4b5d6`, which
is the pre-registration merge and nothing else — **zero code drift between the measured deploy
and main.** Executed overnight under the owner's delegation (pre-registration §5): every roll
launched only after the previous record was read and its predictions checked; the
counted/void/reset reading and the early-stop check were made at every boundary before the next
launch. Driver: `scripts/dev/verification_set_driver.py`, its two set configs under
`docs/plans/verification-sets/`.

This record follows the rule the 1.6.3 record's §6 set for its successor: **every rejection is
attributed from that roll's stored per-round `test_report.md` files and emission timeline** —
the origin of the failing assertion and the round it first appeared — never from the roll-up and
never from the boot audit.

---

## 1. Headline

**Next.js+TS (`nextjs_ts`): 6 of 6 functional — 100%, 95% CI [61.0%, 100%].** Every roll:
verdict `accepted`, boot audit PASS, zero manual intervention, every criterion credited, **zero
correction rounds**, zero framing re-rolls, zero failed emissions.

**FastAPI+React (`fullstack_fastapi_react`): 2 of 6 functional — 33%, 95% CI [9.7%, 70.0%]** —
the stack's **first authored-mode baseline**, pre-registered with no bar and no comparison.
Both greens were **by repair** (a retest passed after a dev repair); **none by re-dispatch**.

Wilson intervals, the 1.6.3 record's method. The Next.js set is the 1.6.5 pack measured against
the 1.6.4 baseline (8 of 8) on the same project, squad, request profile, overrides and config
hash (`d4d4f66217d8`, squad snapshot `575707c58536cf3b` — E moved the snapshot, not the hash);
the intervals overlap and, per the pre-registration §1, no significance is claimed on the rate.
What it claims is in §2.

### 1.1 Next.js+TS

| roll | cycle | framing | gate decider | verdict | audit | corrections | criteria | qa primary tokens | wall (ET) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_a306b4e858d9` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 4,499 | 16:56→17:44 (48m) |
| 2 | `cyc_9b17553ce9d5` | 1 | agent, §6 constant | accepted | PASS | 0 | 12/12 | 8,099 | 17:46→18:41 (55m) |
| 3 | `cyc_0d85a682881a` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 4,093 / 3,263 | 18:43→19:41 (58m) |
| 4 | `cyc_face9e37d93a` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 7,286 | 19:43→20:30 (47m) |
| 5 | `cyc_345268417e31` | 1 | agent, §6 constant | accepted | PASS | 0 | 12/12 | 9,148 | 20:31→21:30 (59m) |
| 6 | `cyc_47cd83559c4a` | 1 | agent, §6 constant | accepted | PASS | 0 | 14/14 | 5,227 | 21:31→22:22 (51m) |

Gate split (§6.1): 3 auto-approved by `system:no_open_questions`, 3 by the §6 constant — a count,
used for nothing. Rolls 2 and 5 framed the 12-criterion manifest shape (two fewer `vc-compiles-*`
criteria declared, all credited); the others the 14. Roll 3's qa work was split across two
`qa.test` tasks by the manifest, hence two emissions.

### 1.2 FastAPI+React

| roll | cycle | framing | gate decider | verdict | audit | corrections | how it ended | criteria | failed emissions banked | wall (ET) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_b9296c255dfc` | 1 | agent, §6 constant | **rejected** | PASS | 3 | attempts exhausted | 11/16 | 12 | 22:24→23:38 (73m) |
| 2 | `cyc_f84649c68646` | 1 | agent, §6 constant | accepted | PASS | 1 | green **by repair** | 14/14 | 3 | 23:41→00:38 (56m) |
| 3 | `cyc_184b3a1d194e` | 1 | `system:no_open_questions` | **rejected** | **FAIL** | 2 | `plan_defect` at round 1 | 13/16 | 6 | 00:39→01:36 (56m) |
| 4 | `cyc_5ef83cc6fc2b` | 1 | `system:no_open_questions` | accepted | PASS | 1 | green **by repair** | 17/17 | 3 | 01:37→02:31 (54m) |
| 5 | `cyc_0e7bc622169a` | 1 | agent, §6 constant | **rejected** | **FAIL** | 2 | `plan_defect` at round 1, **zero applied repairs** | 10/15 | 6 | 02:32→03:33 (60m) |
| 6 | `cyc_d43c644e52d0` | 1 | `system:no_open_questions` | **rejected** | **FAIL** | 2 | `plan_defect` at round 1, **zero applied repairs** | 12/17 | 6 | 03:34→04:30 (56m) |

Gate split: 3 and 3. Zero framing re-rolls on this stack too — **twenty-four consecutive cycles**
(both sets, both shakeout pairs) have now framed on the first attempt. Config hash
`c4d6a2165acf`, same squad snapshot.

---

## 2. The predictions — what the sets were built to answer

Pass/fail as pre-registered, read only from the evidence each names. **Every prediction held on
every roll that exercised it, on both sets; the early stop never fired.**

### 2.1 Next.js+TS (§3 of the pre-registration)

| # | prediction | result | read from |
|---|---|---|---|
| **Q0** | every `qa.test` primary emission places all fill fences before any additive file (A) | **held 7/7 emissions** — first fill fence at index 0–342, first path fence at 1,389–2,456 | LangFuse generation output per emission (`scratchpad` texture files, banked in the roll records' notes) |
| **Q1** | a cap hit loses only additive content | **unexercised** — no emission reached the cap | — |
| **Q2** | a self-eval re-emission of fills is merged (C) | **unexercised** — no self-eval fill re-emission occurred | — |
| **Q3** | the suite runs on the post-self-eval file set (B) | **held 6/6** — no failing report named content absent from the task's stored suite (trivially: no failing report) | per-task reports vs stored artifacts |
| **Q4** | an own-artifact qa repair whose failing test is a shell targets that shell (D) | **unexercised** — no qa repair ran | — |
| **Q5** | no `qa.test` primary emission reaches the 12,288 cap (E) | **held 7/7** — max 9,148 | eve `emission shape … completion_tokens=` |
| **P0** | the seeded frozen tree agrees with the floor | **held 6/6** — `TABLES = ['Run']` = roots, models entity-typed | driver `static_checks.p0` |
| **Coverage** | a green roll credits every criterion (#1021) | **held 6/6** | `run_verification_summaries` |
| P1, P3, P5 | carried from 1.6.4 | **unexercised** — as there | — |

**Unexercised is not passed.** Three of the five pack items (Q1, Q2, Q4 — i.e. C and D's live
behaviour) were not asked a question by this set because nothing went wrong on this stack. The
replay proofs in their PRs (#1115, #1116) are the only evidence those paths work.

### 2.2 FastAPI+React (§4 of the pre-registration)

| # | prediction | result | read from |
|---|---|---|---|
| **S0** | the seeded `backend/models.py` types every collection field with its declared element type | **held 6/6** | driver `static_checks.p0` (`p0_models_entity_typed`) |
| **S1** | an accepted roll credits every criterion | **held 2/2** (14/14, 17/17) | `run_verification_summaries` |
| **S2** | a qa-side failure routed to the dev chain always yields a non-empty dev-role target (#1120) | **held 6/6** — zero `ownership veto emptied` lines; every narrowing landed on `backend/routes.py` | runtime-api log, driver `loop_texture` |
| **S3** | no `qa.test` primary emission reaches the 12,288 cap | **held 11/11** — max 7,697 | eve `emission shape` |
| **Q3** | carried | **held 6/6** | as in §2.1 |

**#1120's fix — the thing this arm was built to test — held on every roll**, including four
rolls that ran the correction loop it was built for. S0 held while `stores_beyond_roots` was
recorded on rolls 3 and 4 (`participant`, `run_list_item` / `run_summary`) — the #1087 stack-#1
half and #1112's edge, harmless here.

---

## 3. What the loop did when it ran

It never ran on Next.js: six rolls, zero correction rounds, so this set says nothing about C, D,
or the correction loop on that stack. It ran on every FastAPI+React roll. Attributed per round:

| roll | round 0 — origin of the failing assertion | what the loop did | where it ended |
|---|---|---|---|
| 1 | **frozen model** (scaffold): `Run(distance=None, …)` → pydantic `string_type` → 500 on POST /runs | dev repair landed (`or ""`), retest-00 green 03:15Z — then the qa task re-stored its **failed** report over it (#1111); frontend suite red "Found multiple elements" (`render()` ×3, no cleanup — #1127); round-1 analysis re-diagnosed the fixed backend defect and narrowed to `backend/routes.py`; retest-01 red; executor re-dispatched `qa.test` → new suite (real `App`, stubbed `fetch`, `afterEach(cleanup)`) **passed 3/3** and was failed by `no_self_mocking_tests` (#1126); round 2 `qa.test_repair` re-emitted without cleanup | attempts exhausted, rejected — the green at 03:26Z was discarded by the check |
| 2 | frozen model, same line | dev repair landed; retest-00 green | accepted **by repair** |
| 3 | **contract** (framing): `vc-probe-runs-participants` / `-duplicate` sent `json: {}` — the manifest's `request: Participant` names an entity, which validation accepts and the contract generator cannot resolve (#1128); **and qa's own** `test_runs.py` called `client.delete(url, json=…)` → TypeError at collection (#1130) | dev repair on `backend/routes.py` could not change either; retest red on both; round 1 repeated the signature | `plan_defect` (`tighten_acceptance`) — **the correct verdict**: the contract was unsatisfiable by construction |
| 4 | frozen model, same line | dev repair landed; retest-00 green | accepted **by repair** |
| 5 | frozen model (+ `capacity: int = None`) | repair emitted `routes.py` as an 84→61-line rewrite with the router and every decorator dropped → **refused** by `patch_verification` (`unresolved_imports`); no retest; `qa.test` re-dispatched on the unrepaired tree; signature "repeated" | `plan_defect` after **zero applied repairs** (#1129) |
| 6 | frozen model, same line | repair carried the **correct** fix inside a rewrite that switched to `APIRouter(prefix="/runs")` → **refused** (`file_owned_criteria: endpoint_defined`, a literal-path check); no retest; re-dispatch; signature "repeated" | `plan_defect` after **zero applied repairs** (#1129) |

**So the four rejections are two mechanisms and a long tail.** One scaffold defect (§4, #1125)
opened five of six rolls with a round-0 500; the dev repair landed it twice (rolls 2, 4) and was
refused twice (rolls 5, 6 — whole-file rewrites both times, where both accepted repairs kept
the file's shape). Roll 1's tail is the shape of this stack's qa problem: a harness gap, a
Next.js-shaped check, and a re-stored failure misdirecting the analysis. Roll 3 is the one
rejection where the loop's verdict named the right culprit.

**Greens by repair versus by re-dispatch, counted separately as the pre-registration asked:**
2 by repair, 0 by re-dispatch. The two re-dispatches that did occur (rolls 1 and 5) produced a
green suite that a check discarded, and a re-run against an unrepaired tree, respectively.

---

## 4. Findings — filed on the owner's go, 2026-08-27

Each was cited to file:line from the stored artifacts before filing; the issue bodies carry the
evidence. The morning's question — *were these all React-stack findings?* — has a precise answer:
three are about that stack, four are shared loop code that only a red roll can expose, and the
Next.js set gave none.

| # | finding | where it lives | rolls |
|---|---|---|---|
| **#1125** | manifest `required: false, default: null` freezes as `distance: str = None` — non-nullable annotation, None default — because `default: null` sets `has_default` (`scaffold.py:486`) and the nullable branch only fires with no default key (`:1332-1340`); the request shape is correctly nullable, so the route forwards None into `Run(...)` | Python model emitter (stack #1 only; the TS emitter renders `distance?: string`) | 1, 2, 4, 5, 6 |
| **#1126** | `detect_self_mocking_tests` defines "invokes the application" as an `app/api/` import — the Next.js in-process model — and rejects a React suite that renders the real `App` with `fetch` stubbed, while passing `vi.mock('../api.js')` (the more self-mocking shape; both accepted shakeouts got past it that way) | shared check (`handlers/stub_detection.py:120-185`), no stack parameter | 1 |
| **#1127** | frozen `test-setup.js` registers no `afterEach(cleanup)`; vitest runs `globals:false`, so RTL never unmounts between tests | React harness (`scaffold.py:1622`) | 1 |
| **#1128** | an endpoint whose `request:` names an entity gets `json: {}` — validation accepts "shape or entity" (`scaffold.py:438-440`), the contract generator resolves only shapes (`scaffold_contract.py:439`, `:537-541`) | shared contract generator | 3 |
| **#1129** | a patch refused by `patch_verification` still counts as a round: no retest, `qa.test` re-dispatched on the unrepaired tree, "signature repeated" → `plan_defect` after zero applied repairs | shared correction loop (`correction_runner.py:1203`, `dispatched_flow_executor.py:3087`) | 5, 6 |
| **#1130** | a qa-owned defect in a free-authored suite is named by every analysis and decision and never dispatched to qa; the only repair target is the dev slot | shared owner routing (with #1123, #1122) | 3 |
| **#1111** (re-evidenced) | the qa task's failed report and typed-check evaluation are re-stored over the passing retest in the same second; the next analysis reads the failure and sends the repair at a fixed file | shared run-end store | 1 |
| **#1131** | the structural cause: `stack_nextjs_ts.py` exists and no stack-#1 module does — the "generic" `scaffold.py` *is* stack #1 (its expander inline at lines ~1284–1890), so shared checks written while working on one stack are tested only against it. Extract the module; guard stack-shaped literals outside `stack_*` with a #772-style structural test | 1.7 | — |

**#1125 has perfect separation on one frozen deploy.** Every manifest that wrote `default: null`
(rolls 1, 2, 4, 5, 6) froze the non-nullable field and paid the round-0 500; every manifest that
omitted the key (roll 3, both shakeouts) was clean. Manifest-author wording selects a generator
branch no test covers.

**What is deliberately not concluded from roll 1.** The round-0 backend defect was repaired; what
ended the roll was three framework behaviours in sequence (#1127 → #1126 → the round-2 repair),
none of which is the model's work. It is recorded as one rejection, not as evidence about the
squad.

---

## 5. Texture

**qa primary completion tokens.** Next.js: `3263 4093 4499 5227 7286 8099 9148` (max 9,148 of
the 12,288 cap, 25% headroom) against the 1.6.4 set's ten under the 8,192 cap
(`4418 4947 5045 5498 5743 6292 7947 7963 8192 8192`, three at the cap). **Cap hits: 0 of 7
against 3 of 8** — E's raise was never touched; the distribution's upper half moved up by roughly
a thousand tokens, which is the content that was being truncated, now emitted. FastAPI+React:
`2804 3029 3722 4329 4628 4688 5009 5236 5394 6186 6254 7697` — lower and free-authored; no
hits.

**Wall clock.** Next.js 47–59 min (mean 53), FastAPI+React 54–73 (mean 59; the 73 is roll 1's
three rounds). The Next.js mean is under 1.6.4's 60 with zero corrections against two.

**Correction rounds.** Next.js 0/0/0/0/0/0 against 1.6.4's 0/0/0/0/0/1/0/1 and 1.6.3's
4/0/1/3/4/1/0/0. FastAPI+React 3/1/2/1/2/2 — the loop ran on every roll of the stack whose qa
suite is free-authored, and repaired two.

**Failed emissions banked (#971).** 0 on Next.js; 12/3/6/3/6/6 on FastAPI+React — every
attribution in §3 was read from them and from the per-round reports.

**`stores_beyond_roots`** (#1087's open half, #1112): rolls 3 and 4 of FastAPI+React stored
`participant` and a list projection beside `run`; fills never touched them.

---

## 6. What these sets do not claim

- **Not a general rate.** `full-38` (qwen3.8:27b) on `group_run`; `full` remains the canonical
  squad. The Next.js overrides are `build_profile=nextjs_ts` / `dev_capability=nextjs_ts`; the
  FastAPI+React set is `validated-fullstack`'s defaults.
- **Not evidence that C or D work live.** Q1/Q2/Q4 were never asked; the PRs' replay proofs are
  the only evidence. A green-with-zero-corrections set cannot exercise a repair path.
- **Not a significance claim** on 6/6 against 8/8 (Next.js) — N=6 cannot detect a change of the
  size in question, as pre-registered — nor on 2/6, which is a baseline with no bar.
- **Not a claim that FastAPI+React regressed.** #1125 dates from the stack's own spike
  (2026-07-14) and #1127 from its harness (#627); both were unexercised because authored mode
  had never run on this stack before 2026-08-26. #1126 is bleed, and #1131 names why.
- **Not a claim about response correctness beyond the contract's `json_has` floor** — the boot
  audit certifies installs, boots, status codes and the declared fields, as the 1.6.3 record §2
  established.

---

## 7. Rule for the next record

Carried from 1.6.3 §6 and applied here: name the failing assertion's origin — scaffold, contract,
app, or the qa author's own file — and the round it first appeared, from the stored reports. Added
by this set: **name whether each repair was applied or refused**, and count a green by re-dispatch
separately from a green by repair. Roll 5 and roll 6 read as "the loop failed to converge" from
the roll-up; from the executor log they are "the loop never applied a patch".
