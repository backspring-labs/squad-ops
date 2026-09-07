# 1.7.3 — Verification Sets: Record

**Closed 2026-09-07, 21:39Z.** Two counting sets, **nine counted rolls**: FastAPI+React six, Next.js+TS
three. **No voids and no resets inside the set**, and one void *before* it restarted (§0).
Pre-registration: `docs/plans/1-7-3-verification-set-preregistration.md` (merged in PR #1353,
pinned in #1361, re-pinned to deploy D in #1366, the diagnostics' results in #1363). Deploy frozen
at **`933aed95`** (deploy D); the seven image ids are in each set config and were asserted by the
driver at every launch. HEAD pinned at **`dcf69d3e`** at roll 1 and held to the close.

**Zero code drift between the measured deploy and the tag.** `933aed95..dcf69d3e` is the pinned
pre-registration and two set configs under `docs/`; the tag adds only this record and the release
commit. The 1.6.2 lesson — say what the cut evidence does not cover — has one thing to disclose:
**the three diagnostics ran on deploy C, which is D minus #1364** (§2). #1364 changes the
accepted-patch path's spine row for a contentless builder attempt; none of the diagnostics'
seams is on that path, and no counted roll produced a contentless builder attempt, so #1364's
live evidence is its wiring test, not a roll.

Sizing was the pre-registration's: six on FastAPI+React (the measurement) and three on
Next.js+TS, the 1.7.2 sizes held because this plan expected list-attributable regressions for the
first time. It found none.

---

## 0. The void roll, and the shakeout loop

**Counted roll 1 was launched, rejected, and voided.** `cyc_af7dd4ad95b0` (2026-09-07 09:50Z, on
deploy C) fell to **#1364**: the builder's first emission was contentless, the correction protocol
repaired it, the patch verified and was accepted, the app booted with 18/18 criteria — and the
verdict was `blocked_unverified`, because #1318's spine-row re-derivation ran only when the failed
attempt had *carried* a `required_files` row, and an attempt that wrote nothing carried nothing.
The 1.7.2 precedent (its record §0) was applied without discount: the set stopped, the defect
was fixed (PR #1365), the deploy rebuilt (D), one shakeout pair run to the exit rule, the pins
moved (#1366), and the set restarted from roll 1 on `dcf69d3e`. Its log is kept as
`roll-01.log.void-roll1-1364`, its record as `roll-01-20260907T104434Z.void-1364.json`, and its
HEAD pin as `.head_pin.aborted-roll1-f51805b0`.

**The shakeout loop took three pairs against a budget of three, and none of them was the list's.**

| | |
|---|---|
| rounds taken (pairs on this line's deploys) | **3** — B, C, D |
| rounds attributable to the list | **0** |
| instrument rounds, counted apart | 2 on deploy A/A″ (found #1347, #1350, #1352) |

| deploy | built from | what the pair found |
|---|---|---|
| B | `4a2cf724` (the structural block) + #1347 #1350 #1352 | React clean. Next.js rejected with the app booting: `assertion_kinds_match` read `typeof … toBe('number')` as a string assertion — **#1359**, pre-existing (1.7.2 Next.js roll 2 took the same refusal twice and its record called it correct). The structural block was clean on both halves. |
| C | `23c6a0ae` (main: the behavioural block + #1351 #1359 + the instrument and migration fixes) | Both halves clean; `assertion_kinds_match` passed on the first Next.js emission and `fill_merge_evidence` populated (#999). Exit rule met. The three diagnostics ran here (§2). Counted roll 1 then found #1364. |
| D | `933aed95` (C + #1364) | React rejected on the #1312 shape — the builder omitted `qa_handoff.md` twice, the loop terminated honestly: the cycle's, not a seam. Next.js clean. Exit rule met; **the frozen deploy**. |

Every supersede came from the measuring apparatus or the loop's own accounting. **Seven harness
and instrument defects** across the line — #1347, #1350, #1352, #1351, #1359, #1364 and the
driver's L4 readout (#1362) — and **none** from the sixteen items being measured. Two of the seven
had been misread by the previous line: the kind gate had refused correct assertions in 1.7.2 and
the record called it correct; the Python own-frame fault had never reached execution, so L7 on
pytest was "held" on a diagnostic that exercised nothing.

---

## 1. Headline

### 1.1 FastAPI+React (`fullstack_fastapi_react`) — 5 of 6 functional

| # | cycle | verdict | boot audit | functional | criteria | corr | contentless qa first | strips | min |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_597f5cb76fb2` | rejected | PASS | no | 20/21 | 2 | 0 | 0 | 52 |
| 2 | `cyc_4acd6ce64ca1` | accepted | PASS | yes | 21/21 | 0 | 0 | 0 | 50 |
| 3 | `cyc_ce33e6a1da5f` | accepted | PASS | yes | 21/21 | 0 | 0 | 0 | 53 |
| 4 | `cyc_b9961579f33b` | accepted | PASS | yes | 21/21 | 1 | 0 | 0 | 52 |
| 5 | `cyc_52a2c7438d12` | accepted | PASS | yes | 18/18 | 2 | 0 | 0 | 51 |
| 6 | `cyc_3270c790620e` | accepted | PASS | yes | 19/19 | 1 | 0 | 0 | 52 |

**Roll 1 is the declared non-pack rejection cause** (pre-registration §4, #1312): the builder's
first emission was a Dockerfile and nothing else (373 completion tokens against a normal
1,900–4,300), its repair emitted ten fences with no path address, `qa_handoff.md` was never
written, and the loop terminated `unverifiable` because every deciding check named a file the
repair did not write. The delivered app booted and answered all five probes; the verdict —
"Build deliverable incomplete" — is true of the tree. Counted, non-functional, the cycle's.

**Roll 4 is the same first emission recovered**: 642 tokens, the handoff missing, one builder
repair that addressed its files, patch accepted, 21/21.

### 1.2 Next.js+TS (`nextjs_ts`) — 3 of 3 functional

| # | cycle | verdict | boot audit | functional | criteria | corr | contentless qa first | strips | min |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_2dfbb0f1af81` | accepted | PASS | yes | 17/17 | 0 | 0 | 0 | 60 |
| 2 | `cyc_5cb087956ba9` | accepted | PASS | yes | 17/17 | 0 | 0 | 0 | 65 |
| 3 | `cyc_57cdbad02f67` | accepted | PASS | yes | 17/17 | 0 | 0 | 0 | 60 |

Three rolls, zero correction rounds, 17/17 on each; `assertion_kinds_match` passed on the first
emission of every roll — the check that had refused a correct suite thirteen times on deploy B
(#1359) — and `fill_merge_evidence` carried eight fills per roll, every fill touching the store.

---

## 2. The predictions

**L1 was the set's one bar** (#1268): no qa first attempt is contentless. **Held — 0 contentless
emissions of 163 across nine rolls**, any handler. The one contentless emission this line
saw in a counted launch was the void roll's *builder* (§0), which is not L1's subject and which
#1364 now reports correctly.

| prediction | reading | how |
|---|---|---|
| **L1** (#1268) | **HELD** | 0 of 163 emissions contentless |
| **L3** (#1271) | **HELD** | no run rejected on an earlier attempt's rows; `evidence_superseded` on every accepted patch |
| **L8a** (#1272, the model) | **HELD** | `placeholder_strips` empty on all nine — the model never emitted under the placeholder |
| **B1** (#1087/#1112) | **HELD** | no stored qa suite names a fixture table for a non-root entity (root entity `Run`; 43 suites read) |
| **L2** (#1269) | **HELD on the diagnostic** (deploy C, `cyc_508def6d810f`) | two rounds, the first repair retested and failed, the second passed; unexercised by any counted roll |
| **L7** (#1270) | **HELD on the diagnostic** (`cyc_6258b632e198`) — **on a pytest suite for the first time** | the #1352 fault reached execution and routed to `qa.test_repair`; unexercised by any counted roll |
| **L4** (#1273) | **HELD on the diagnostic** (same cycle) | the prose-only repair refunded; read on the re-rendered record after #1362 — the first render's readout was wired to the wrong field |
| **L5** (#1260) | **HELD on the diagnostic** (same cycle) | the re-taken round briefed with the failing case |
| **L8b** (#1272, the extractor) | **HELD on the diagnostic** (`cyc_82e1bd587051`) | two strips, `stored_under_placeholder` empty |
| **L6** (#788) | **UNEXERCISED** | no app runtime error on any roll |

**Five of ten predictions are held only by injected diagnostics**, as in 1.7.2 — but this time
each diagnostic's seam was reached, and the record can say so because the readout is the seam
(`seam_reached`, #1310), not the fault. The diagnostics ran on deploy C; D differs by #1364, which
is off every one of their paths.

**Carried readouts.** R1 did not fire (the kind gate passed on every Next.js emission after
#1359). R3, R5, R6 clean. R7 `decided_by_agent: 0` on all nine. Every "did it not happen, or did
we not look" field is empty rather than absent: `unverifiable_by_reason` empty on eight rolls
and `{no_executed_blocking_checks: 1}` on roll 1, where it names the builder's repair;
`no_execution_by_skip_reason` empty on eight and `{file_not_in_patch: 2}` on roll 1, the same
fact from the other side.

**B-side:** P0 held on all nine.

---

## 3. What the loop did when it ran

**Eight patches applied and one refused, all on the React arm, across six correction rounds in nine rolls; the Next.js arm ran three rolls with zero rounds.** The refusal is roll 1's (§1.1). No round was refunded; no repair was re-routed to the qa role by the own-frame detector; no re-take was briefed.

**Roll 1 is the informative one on the loop's honesty.** The builder's repair wrote ten fences
without a path; the verifier found no executed blocking check it could decide (two skips,
`file_not_in_patch`), refused to call the patch verified on nothing, and the loop stopped rather
than spend rounds it could not win. That is #1129 and #1259 doing their job. The delivered app was
fine; the deliverable was not; the record agrees with the tree.

---

## 4. Findings

### 4.1 #1364 — the accepted patch of a contentless builder attempt never got its spine row (void roll 1)

The #1318 family's second instance in two lines. #1318 re-derived `required_files` on the patched
set only when the failed attempt had carried the row; a contentless attempt carries nothing. The
row is now the builder's by contract (`TaskType.emits_required_files`). Two false rejections on
one mechanism in two lines says the accepted-patch path should derive every framework row from
the patched set by contract; that is 1.7.4's, not a third gate.

### 4.2 #1350 — a repair's grants were the failed task's, not the repairing step's

Found by the chain diagnostic on A″: a dev repair of a qa failure was judged as a QA write to a
dev slot and refused. Every repair artifact now names the step that emitted it, enforcement
judges by that producer, and an unnamed repair artifact fails the run loudly. My own #1323
change; the diagnostic caught it before the set.

### 4.3 #1352 — the Python own-frame fault never reached execution

A `NameError` is what the emission seam's `undefined_names` check exists to refuse; the handler's
self-eval removed the fault before the suite ran. 1.7.2's chain held L7 on its vitest task while
its pytest task exercised nothing, invisibly. The fault is now an argument-binding `TypeError`;
L7 held on a pytest suite for the first time on this line.

### 4.4 #1359 — the kind gate read `typeof` assertions as strings

Deploy B's Next.js half refused a correct suite thirteen times. Pre-existing (#1153); 1.7.2's
record called the same refusal correct. The refused suite is pinned as a replay fixture and
passes under its own manifest.

### 4.5 #1351 — the router restore put back half a statement

A prefixed router with empty route paths, restored to a bare router with empty paths, is a file
FastAPI refuses to load. The restore now re-homes the paths it strips a prefix from, and abandons
rather than emit an empty path. Found by the chain diagnostic's own app.

### 4.6 Instrument

#1347 (the emission-retry marker rode every later dispatch — the absent-suite fault re-applied
to every correction re-take). The driver's L4 readout was wired to `refused_rounds_not_counted`,
the #1129 exclusion, and read the chain diagnostic's refund as "not reached"; #1362 added
`refunded_rounds` and the record was re-rendered from its stored identity (§2's driver-only-fix
rule). Migration 1150 altered `agent_status`, a table only `init.sql` creates, and main's
integration job — not a required check — was red for six merges before it was read (#1357). PR
#1353 merged the pre-registration draft under the #1352 fix's title, opened from the wrong working
directory; retitled, the issue reopened and closed by its real PR.

---

## 5. Texture

- **The builder's short first emission.** Two of six counted React rolls (1 and 4) began with a builder first emission of 373 and 642 completion tokens against 1,391–2,382 on the other four; one recovered by repair, one did not. Counting the two shakeouts on C/D and the void roll (160 tokens), four of the last nine React builder first emissions on this line were short, at the same prompt size (16.5–23.8k tokens) as the normal ones; 1.7.2's set saw one in seven. Texture, not a finding: the prompt did not change, the model's output length did — and it is 1.7.4's evidence for #1312.
- **Packaging (reporting-only, #598):** `npm_ci_without_lockfile` on 4 of 9 (one React roll, all three Next.js rolls) rolls.
- **Gate deciders**, recorded verbatim; the §7 constant applied identically to all nine.
- **Wall clock:** React 50–53 min; Next.js 60–65 min.
- **Criteria:** 18–21 verified per React roll; 17 per Next.js roll.
- **#1285's producer exists now** (#1334): across the six React rolls the qa handler's ten
  emissions carried 58,058 completion tokens and 135,775 reasoning characters, with
  `reasoning_tokens` unreported on every one — the reading must be made from characters. The
  fill-mode cost question the plan routed to this record: the Next.js qa emissions (fill mode) carried 30,470 completion tokens and 69,186 reasoning characters over three rolls, about 10.2k tokens per emission, against React's 5.8k per emission over ten. The cost is visible now; whether it is material is 1.7.4's reading, and it has a producer.

---

## 6. What these sets do not claim

- **Not a rate.** 5 of 6 and 3 of 3 against 1.7.2's 5 of 6 and 3 of 3 are not detectable
  changes. §1 set no bar but L1.
- **Not that the list is regression-free.** The attribution claim holds in one direction: a red
  would have been the refactor's; a green is not evidence about the list beyond the guards that
  verify it in CI.
- **Not that the recovery path is sound in general.** Five predictions are held only by injected
  diagnostics (§2), on deploy C.
- **Not a general rate**: `full-38` (qwen3.8:27b) on `group_run`.
- **Not that the builder's emission surface is sound** — roll 1 and the D shakeout are the #1312
  shape, 1.7.4's lead item.

---

## 7. Rule for the next record

Carried from 1.7.2 §7 (two numbers for the shakeout loop; a readout that cannot see its own
miss is a finding; name the unexercised predictions in the headline). Added by this set:

- **A void roll is scored by the tree, not the verdict.** Roll 1's void and roll 1's restart both
  had booting apps; one was a false verdict and one was a true one. The record must say which
  the harness got right.
- **Read every job of main's CI run after every merge**, not the required checks alone.
- **A pinned deploy that differs from the diagnostics' deploy names the difference** and says
  whether any diagnostic's path crosses it.

---

## 8. Disposition of items the plan routed here

- **#1285** — the producer exists (#1334) and the reading is in §5: reasoning tokens are
  unreported on every qa emission; reasoning characters are present. Whether the fill-mode cost
  is material is not decided here — the producer landed mid-line (#1334); the per-emission cost is ~10.2k completion tokens on Next.js (fill mode) against ~5.8k on React, with reasoning characters in the same ratio. Stays open for 1.7.4's plan to place.
- **#1312 / #1254** — 1.7.4's lead item, with this set's evidence: the builder's short first
  emission on two of six of the counted React rolls, one unrecovered.
- **#1351, #1359, #1364** — fixed on this line as the fourteenth to sixteenth items (plan rev 4
  §9), each the owner's to veto.
- **The retry-with-fact backstop** (1.7.2 §8a) still has no issue; filed before 1.7.4's plan.
