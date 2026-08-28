# 1.6.6 — Verification Sets: Record

**Closed 2026-08-27, 23:02 ET.** Two counting sets, eight counted rolls, no voids, no resets.
Pre-registration: `docs/plans/1-6-6-verification-set-preregistration.md` (PR #1142, merged as
`873f4e50`; its §2 preconditions completed by PR #1143, merged as `2448f5d1` — the HEAD pin),
in force from roll 1 and unchanged throughout. Deploy frozen at `e14a6ad4` (main at the #1141
merge — the six fixes A–F; seven image ids in the pre-registration §1, asserted by the driver at
every launch). Every launch from a clean `main` (the owner's rule of 2026-08-27; two earlier
shakeouts launched from the pre-registration branch are recorded as diagnostics only). Executed
under the owner's delegation: the counted/void/reset reading and every prediction checked at
each boundary before the next launch.

Sizing was the owner's: **six rolls on FastAPI+React, where every fix came from; two on
Next.js+TS, where none was supposed to reach.**

---

## 1. Headline

**FastAPI+React (`fullstack_fastapi_react`): 4 of 6 functional — 67%, 95% CI [30%, 90%].** Against
the 1.6.5 baseline of 2 of 6 ([9.7%, 70.0%]) on the same protocol. Texture, not a claim: N=6 cannot
show a rate change and the pre-registration §1.3 said so. **Two greens clean, two by repair, none
by re-dispatch.**

**Next.js+TS (`nextjs_ts`): 2 of 2 — zero correction rounds.** The regression arm asked only whether
anything moved; nothing did.

**Every pre-registered prediction held wherever a roll exercised it, on both sets.** The early
stop never fired.

### 1.1 FastAPI+React

| roll | cycle | gate decider | verdict | audit | rounds | how it ended | criteria | qa primary tokens | wall (ET) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_cdf91361702b` | `system:no_open_questions` | accepted | PASS | 1 | green **by repair** | 15/15 | 3,785 | 15:16→16:14 (57m) |
| 2 | `cyc_4f6d873561a2` | `system:no_open_questions` | accepted | PASS | 0 | clean | 15/15 | 4,443 | 16:14→17:07 (52m) |
| 3 | `cyc_38d1e1689766` | `system:no_open_questions` | **rejected** | **FAIL** | 3 | attempts exhausted | 15/17 | 6,594 / 5,001 / 5,608 / 5,897 | 17:07→18:18 (70m) |
| 4 | `cyc_ac15b6c6209f` | agent, §6 constant | accepted | PASS | 1 | green **by repair** | 14/14 | 4,692 | 18:18→19:11 (51m) |
| 5 | `cyc_ae0631fddfc5` | `system:no_open_questions` | accepted | PASS | 0 | clean | 15/15 | 3,233 | 19:11→19:55 (43m) |
| 6 | `cyc_0c4664c2ae9a` | `system:no_open_questions` | **rejected** | PASS | 3 | attempts exhausted | 10/15 | 5,584 / 6,531 / 5,812 / 4,913 | 19:55→21:10 (74m) |

Config hash `c4d6a2165acf`, squad snapshot `575707c58536cf3b` on every roll. Zero framing
re-rolls; thirty-two consecutive cycles have now framed on the first attempt.

### 1.2 Next.js+TS

| roll | cycle | gate decider | verdict | audit | rounds | criteria | qa primary tokens | fills first | wall (ET) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_68b0e1769526` | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 5,060 | yes (fill @0, first path @1,762) | 21:11→22:04 (53m) |
| 2 | `cyc_06987a951236` | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 3,454 | yes (fill @0, first path @1,322) | 22:05→23:01 (54m) |

Config hash `d4d4f66217d8`, same snapshot.

---

## 2. The predictions — what the sets were built to answer

Read only from the evidence each names in the pre-registration; the driver's readouts added
for this set (`models_nullable_mismatches`, `multiple_elements_reports`,
`plan_defect_after_zero_applied`, `empty_body_probes`) are the record fields cited.

### 2.1 FastAPI+React — the measurement

| the fix | prediction id | result | evidence |
|---|---|---|---|
| **An optional field freezes nullable** (#1125, item A) | R1 | **held 3 of 3 exercised** — rolls 1, 2, 5 wrote `required: false, default: null` and the frozen `models.py` read `str \| None = None` for every optional field; rolls 3, 4, 6 omitted the key (not exercised). In 1.6.5 the same manifest shape opened five of six rolls with a 500. | `static_checks.p0.models_nullable_mismatches` = `[]` on all six; no `string_type … input_value=None` in any report |
| **The harness unmounts between tests** (#1127, B) | R2 | **held 6 of 6** — no stored report contains "Found multiple elements" | `static_checks.multiple_elements_reports` = `[]` |
| **The self-mocking check is the stack's definition** (#1126, C) | R3 | **held 6 of 6** — no suite that imports `App` or a view was failed by `no_self_mocking_tests` | eve log + stored suites (hand-read) |
| **A refused patch is not a round** (#1129, D) | R4 | **held 6 of 6, fired twice** — rolls 3 and 6 each had one refused patch (`endpoint_defined` / `file_owned_criteria`); the loop continued past it and neither run ended `plan_defect` after zero applied repairs (both ended by the attempt cap) | `loop_texture.plan_defect_after_zero_applied` = false on all six; `refused_rounds_not_counted` = 1 on roll 3 |
| **One request-body resolver** (#1128, E) | R5 | **held 6 of 6, not exercised** — every manifest declared request shapes, so no entity-typed request occurred; no POST probe carried `json: {}` | `static_checks.empty_body_probes` = `[]` |
| **The passing retest is what the task stores** (#1111, F) | R6 | **held, fired twice** — rolls 1 and 6: the qa task's stored `test_report.md` is the passing retest's report (in 1.6.5 roll 1 it was the failed one, and the next analysis read it) | `loop_texture.evidence_superseded` = 1 on rolls 1 and 6; vault timestamps |
| carried from 1.6.5: typed models (S0), coverage on accepted rolls (S1), never an empty dev target (S2), no cap hit (S3), suite runs on the stored set (Q3) | S0–S3, Q3 | **held** — S0 6/6, S1 4/4, S2 6/6 (every narrowing landed on `backend/routes.py`), S3 11/11 emissions (max 6,594 of 12,288), Q3 6/6 | driver record; eve `emission shape` |

**Unexercised is not passed.** R5's resolver and the synthesized body model never met an
entity-typed request; R1 met three manifests, not six. Each roll's record says which items it
exercised.

### 2.2 Next.js+TS — the regression arm

| prediction | result |
|---|---|
| fills first on every qa primary emission (Q0) | **held 2 of 2** (fill fence at index 0, first path fence at 1,762 / 1,322) |
| no qa primary reaches the 12,288 cap (Q5) | **held 2 of 2** (5,060; 3,454) |
| the seeded frozen tree agrees with the floor (P0) | **held 2 of 2** (`TABLES = ['Run']` = roots) |
| an accepted roll credits every criterion | **held 2 of 2** (14/14) |
| the self-mocking check still applies the Next.js definition | **not exercised** — neither roll emitted a suite the check had to judge either way |

---

## 3. What the loop did when it ran

It ran on four of the six FastAPI+React rolls and on neither Next.js roll. Per round, from the
stored per-round reports and the executor's own lines:

| roll | round 0 — what failed, and where the failing assertion came from | what the loop did | where it ended |
|---|---|---|---|
| 1 | the qa suite died at collection (conftest `ImportError`, exit 4) because the dev's `backend/routes.py` declared every route decorator on an empty path — **app defect** | one dev repair on `routes.py`; verification passed 6/6; retest passed | green **by repair**; F stored the passing report |
| 3 | `LeaveResult.removed` is declared `boolean` by the manifest and frozen model; the dev returned the participant's *name* (500, `vc-probe-runs-leave`) — **app defect, diagnosed correctly at round 0**; and the qa suite asserted `body["removed"] == "Carol"` in all four of its emissions — **qa-side assertion contradicting the declared kind** | round 0: dev repair set `removed=True` (correct per contract), verification 9/9, **retest failed on the qa assertion**; round 1: repair refused (`endpoint_defined` on a rewrite), **not counted as a repeat (D)**; round 2: repair regressed to the string; retest failed | attempts exhausted; **rejected**, audit FAIL |
| 4 | a builder (assemble) task failed typed checks — **build-side defect** | one `builder.assemble_repair`; verification 6/6 | green **by repair** |
| 6 | `uuid.uuid4().str` (`AttributeError` → 500 on POST /runs) — **app defect**; after its repair, the frontend suite failed on `expected "spy" to be called with ['/runs/run-1/join', …]` and then `expected undefined to be defined` — **qa-side expectations with no contract behind them** | round 0: repair, retest failed on a 409 assertion; round 1: repair, **retest passed** (F stored it); frontend `qa.test` then failed twice; round 2: dev repair refused (`file_owned_criteria`); shared attempt counter exhausted | **rejected — with the boot audit PASSING all five probes** |

**The two rejections are one class, and it is not a pack item.** A free-authored qa suite
asserted something the contract never said; a correct dev repair was rejected by that
assertion; nothing routed a defect to the qa-owned file. That class ended 1.6.5's roll 1 too.
It is what 1.7's Stack Seams pack addresses: the kind gate (#1153 — reject at emission an
assertion that contradicts a declared field kind, which on the evidence flips roll 3 outright),
the routing (#1130), and the scoping/signal for speculative frontend expectations (#1123).

**Greens by repair versus by re-dispatch, counted separately:** 2 by repair (rolls 1 and 4), 0 by
re-dispatch. In 1.6.5 this stack had 2 by repair, 0 by re-dispatch, out of two greens; the two
new greens are clean runs.

---

## 4. Findings

Filed 2026-08-27/28 on the owner's go, each cited to the stored artifacts:

- **#1153** — a free-authored qa suite can assert a declared boolean is a name and nothing checks
  it; the React counterpart of the Next.js fill kind gate (#1094). Roll 3.
- **#1130 (evidenced)** — the qa-owned file was named by every analysis and both decisions and
  never dispatched to. Roll 3.
- **#1123 (evidenced)** — a correct application exhausted by its own frontend suite's
  expectations; audit PASS. Roll 6.
- **Instrument correction, in the pre-registration §2:** the driver's refused-patch readout
  counted only `status=failed`; an `unverifiable` verification followed by a re-dispatch is also a
  patch never applied. Found by the Next.js shakeout, fixed before roll 1 (#1143).
- **Observation on the regression arm, not a prediction:** the Next.js *shakeout*
  (`cyc_38f95b29cf79`) entered the loop twice on a dev task (a TypeScript strict-null error in a
  page fill); both patches were `unverifiable` (no executable typed checks on `.tsx`), the task
  was re-dispatched twice, and the third emission compiled. D's branch executed there and was
  outcome-neutral (no structural candidate on either decision). Neither counted roll entered the
  loop.

The owner's architectural assessment of this tree, read the same night, produced #1147–#1152
and sharpened #154/#301; they are placed in the 1.7 plan, not here.

---

## 5. Texture

**qa primary completion tokens.** FastAPI+React `3233 3785 4443 4692 4913 5001 5584 5608 5812 5897
6531 6594` (max 6,594 of 12,288; 1.6.5's twelve ran 2,804–7,697). Next.js `3454 5060` (1.6.5's
seven: 3,263–9,148). No cap hit on either stack.

**Wall clock.** FastAPI+React 43–74 min (mean 58; the 70 and 74 are the two three-round reds);
Next.js 53–54.

**Correction rounds.** FastAPI+React 1/0/3/1/0/2 against 1.6.5's 3/1/2/1/2/2; Next.js 0/0.

**Refused versus applied patches (new readout).** Rolls 3 and 6: one refused each (both
whole-file rewrites of `routes.py`, both refused by a file-owned check); rolls 1, 3, 4, 6:
patches applied 3/4/1/5. The two refused patches were the only two rewrites; every accepted
repair kept the file's shape.

**Gates.** 7 by `system:no_open_questions`, 1 by the §6 constant (the gate text applied verbatim
to every roll).

**Store beyond roots** (#1087's stack-#1 half, #1112): rolls 1, 3, 4 stored `participant` and/or
`run_summary` beside `run`; harmless.

---

## 6. What these sets do not claim

- **Not a rate.** 4 of 6 against 2 of 6 is not a detectable change at N=6, and the pre-registration
  §1.3 said so before roll 1. 2 of 2 says "nothing moved", not a rate.
- **Not that the loop repairs the free-authored-assertion class.** It does not, and both rejections
  say so; that is 1.7's work, named.
- **Not that the request-body resolver works live** — no manifest gave it an entity-typed request.
- **Not a general rate**: `full-38` (qwen3.8:27b) on `group_run`; `full` remains the canonical squad.
- **Not a claim about response correctness beyond the contract's `json_has` floor** (1.6.3 §2).

---

## 7. Rule for the next record

Carried from 1.6.3 §6 and 1.6.5 §7: name each failing assertion's origin — scaffold, contract,
app, or the qa author's own file — and the round it first appeared, from the stored reports;
name whether each repair was applied or refused; count greens by re-dispatch separately from
greens by repair. Added by this set: **name which pack items each roll exercised**, so
"held 6 of 6" is never read where three rolls never asked the question.
