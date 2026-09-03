# 1.7.1 — Verification Sets: Record

**Closed 2026-09-03, 04:25 ET.** Two counting sets, seven counted rolls: **FastAPI+React stopped at
five by the early-stop rule** (R2 falsified on roll 4; the sixth withheld) and **Next.js+TS two**.
No voids, no resets. Pre-registration: `docs/plans/1-7-1-verification-set-preregistration.md`
(PR #1266, merged as `8b58061c` — the HEAD pin, asserted by the driver at every launch), in force
from roll 1 and unchanged throughout. Deploy frozen at `f85de47a` (main at the #1265 merge; seven
image ids in the pre-registration §1, asserted at every launch). Six shakeout deploys preceded it
(pre-registration §2); the exit rule — a pair on one deploy with no new seam finding — was met on
the sixth. Every launch from a clean `main`, chained overnight on the owner's instruction of
2026-09-02 ("roll all 8"); the counted/void/reset reading and the prediction check made at each
boundary, with one recorded deviation (§3.3). The owner ruled at 03:00 ET, with the React arm
read: finish the Next.js arm and cut 1.7.1 as is.

Sizing was the owner's: six rolls on FastAPI+React (the measurement — every item of the pack's
§2.3 came from this stack) and two on Next.js+TS (#939 and #1229 change what a Next.js roll does).

---

## 1. Headline

**FastAPI+React (`fullstack_fastapi_react`): 3 of 5 functional.** Texture, not a claim: N=5 cannot
show a rate change against 1.6.6's 4 of 6, and the pre-registration §1 set no bar. **Two greens
clean, one by re-dispatch after two applied repairs whose retests both failed, none by repair.**
The delivered app passed the boot audit on **all five** rolls, including both failures.

**Next.js+TS (`nextjs_ts`): 0 of 2.** Both delivered apps passed the boot audit. The qa role's
primary emission was contentless on nine of its eleven attempts across the two rolls (§5); every
green fill came from a repair, and on roll 2 the kind gate refused all three.

**One pre-registered prediction falsified — R2, on React roll 4** (§2). The early stop fired; roll
6 was not launched. R1, R5 and R7 held with a positive trace on the rolls that exercised them; R6
held; R3 read zero; R4 was exercised only degenerately and once ambiguously (§2).

**Every non-green but one is a harness evidence-plumbing failure on the recovery path after a
contentless qa emission** (§4.1, §4.2, §4.5), none of it pack code. The one squad-side failure is
Next.js roll 2, where three repairs asserted a declared `number` as a string and the #1153 gate
refused each — the pack doing what it was built to do, on a suite that never got written.

### 1.1 FastAPI+React

| roll | cycle | gate decider | verdict | audit | rounds | how it ended | criteria | qa emission tokens (attempts) | wall (UTC) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_4d52bbd34a32` | `system:no_open_questions` | accepted | PASS | 0 | clean (first attempt contentless, 67; transport retry) | 15/15 | 67 → 2,489 / 2,947 | 01:50→02:40 (49m) |
| 2 | `cyc_9c085ec2e9e5` | agent, §6 constant | **blocked_unverified** | PASS | 2 | builder patch applied; qa patch applied, **no retest** (§4.1) | 9/15 | 122, 165 (contentless) → repair 1,365 | 02:40→03:31 (50m) |
| 3 | `cyc_f05692bb3ceb` | `system:no_open_questions` | accepted | PASS | 0 | clean | 16/16 | 2,073 | 03:34→04:20 (45m) |
| 4 | `cyc_de4b2dea73a0` | agent, §6 constant | accepted | PASS | 2 | two dev repairs applied, both retests red; green **by re-dispatch** (third suite) | 16/16 | 2,248 / 150 / 2,049 / 1,653 / 2,427 | 04:20→05:25 (63m) |
| 5 | `cyc_ca02bed7fbb4` | `system:no_open_questions` | **rejected** | PASS | 1 | qa repair refused (contentless); re-dispatch passed 8/8, **rows not recorded** (§4.2) | 16/19 | 3,059 → repair 154 → 2,139 / 998 | 05:25→06:13 (47m) |
| 6 | — | — | withheld | — | — | early stop after roll 4 (R2) | — | — | — |

Config hash `c4d6a2165acf`, squad snapshot `575707c58536cf3b` on every roll. Zero framing re-rolls.

### 1.2 Next.js+TS

| roll | cycle | gate decider | verdict | audit | rounds | how it ended | criteria | qa emission tokens (attempts) | wall (UTC) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_9be98128f0e9` | `system:no_open_questions` | **rejected** | PASS | 3 | API suite green **by repair** (8 fills); UI suite failed containment + one anchor case; its repair refunded (empty), the re-take briefed without the case, its repair prose-only → loop terminated unverifiable (§4.5) | 17/18 | 122 → repair 3,278; UI: contentless → repair 106 (refunded) → repair 149 (prose) | 06:13→07:16 (62m) |
| 2 | `cyc_5b027f3e74fc` | agent, §6 constant | **blocked_unverified** | PASS | 3 | primary contentless ×5; three repairs (7 fills each) refused by the kind gate; attempts exhausted | 8/14 | 114, 208, 214, 239, 121 → repairs 3,890 / 4,920 / 2,068 | 07:19→08:25 (65m) |

Config hash `d4d4f66217d8`, same snapshot.

---

## 2. The predictions — what the sets were built to answer

Read only from the evidence each names in the pre-registration §3/§4; the driver's 1.7.1
readouts (`typed_checks.*`, `loop_texture.qa_owned_routed`, `absent_anchor_routed`,
`repair_brief_case_counts`, `decided_by_agent`, `unverifiable_toolchain_absent`) are the record
fields cited, with the instrument corrections of §4.6 applied. Which rolls exercised each
prediction is stated, per the 1.6.6 rule (§7 there).

| # | prediction | exercised by | outcome |
|---|---|---|---|
| **R1** (#1153) | no qa assertion contradicting a declared kind reaches execution | every roll; positively on Next.js roll 2 | **held** — Next.js roll 2's three repairs asserted `participants` (declared `list`) and `participantCount` (declared `number`) as strings and the gate refused each at the verifier, on rule-B agent rows (`agent_executed=7` ×3); nothing contradicting a kind reached execution on any roll. React roll 5's readout of "1" is a `file_not_found` row (§4.6) |
| **R2** (#1130) | an own-frame failure in a qa-owned file is routed to `qa.test_repair` with that file as target | React roll 4, round 1 | **FALSIFIED.** `TypeError: default.click is not a function` raised at `runs.test.jsx:108` (qa-owned; the suite imported `userEvent` from the wrong package); the analyzer implicated only that file; the runner vetoed it from the dev target (#884) and dispatched `development.correction_repair` against app files. `qa_owned_routed = 0`. Mechanism, read from the code: `test_runner.suite_defects()` stamps own-frame defects only for `NameError` or a Python argument-binding `TypeError` (`test_runner.py:927-931`); the JavaScript shape matches neither. The fix works for the pytest shape it was built from (1.6.5 roll 3) and not for this one. The plan's narrower wording ("a collection-time error") would read this as unexercised; the pre-registration governs. Owner's ruling: cut as is; the detector gap goes to 1.7.2 (§4.3) |
| **R3** (#668) | every rendering RTL suite queries a declared anchor | React rolls 4–5, Next.js roll 1 (`dom_anchor_queries` bound) | **held** — 0 anchor findings |
| **R4** (#1123) | every `qa.test_repair` brief names the failing cases | five qa repairs on React 2/5 and Next.js 1/2; one brief with a non-empty failed row (Next.js roll 1, round 1) | **held where a failed row carried cases; ambiguous on the refund re-take.** Every brief with 0 cases was built from a failed row that carried none (contentless emissions; a suite at the wrong path). Next.js roll 1 round 1 carried its 1 case correctly; after that repair was refunded, the re-taken round was briefed from the *refunded emission* and carried 0 while the original row still carried the case (§4.5). By the letter the brief matched the row the runner read; by intent the case was lost. Not read as established falsification; the owner rules |
| **R5** (#1022) | no additive suite fetching a live server or invoking nothing reaches execution | React rolls 1, 4, 5; Next.js roll 1 (positive) | **held** — Next.js roll 1's UI suite (`react-dom/server` render, no route) was rejected at emission (`no_application_invocation`) and routed to the qa re-author, as designed. "Reaches execution" is read as #1022 built it: the handler runs every emitted suite before the typed evaluation, and the gate's effect is that the rejected suite's verdict is the suite's own defect. Note that the run was nonetheless rejected on that suite's `tests_pass` row after the re-author failed twice (§4.5) |
| **R6** (#939) | no `.ts`/`.tsx` emission with an unresolved name reaches execution | both Next.js rolls | **held** — 0 rejections, 0 `ReferenceError` in any stored report |
| **R7** (#1229) | no repair returns `unverifiable / no_executed_blocking_checks` for an absent toolchain | eleven repairs across both sets | **held** — every verdict but one was decided on executed agent rows (`agent_executed` 2, 5, 3, 9, 1, 6, 7, 7, 7); the one `unverifiable` (Next.js roll 1, re-take) came from an **absent file**, not an absent toolchain — the repair emitted prose only (§4.5). The readout cannot tell the two apart (§4.6). React roll 5's refusal shows #1262 discounting five `file_not_found` agent rows (`agent_rows=6 agent_executed=1`) |
| S0–S3, Q0, Q3, Q5, P0, Coverage | carried from 1.6.6 | every roll | **held** (P0 asserted on each; `stores_beyond_roots`: `participant` on React 1–2, `participant, run_summary` on 3 — the #1087 shape, carried) |

---

## 3. What the loop did when it ran

### 3.1 Rounds
React: rolls 2, 4 and 5 entered the loop (five repairs: builder 1, qa 2, dev 2). Applied 4, refused
1 (roll 5, correctly — the repair emitted nothing). Retests dispatched 2 (roll 4, both red); none
after the roll-2 qa repair (§4.1). Re-dispatches 4. Greens: 2 clean, 1 by re-dispatch, 0 by repair.
Next.js: both rolls entered the loop (six repairs, all qa). Applied 1, refunded 1, refused 3,
terminated 1. Greens: 0. One suite green by repair (roll 1's API suite) inside a rejected run.

### 3.2 Rule B live
Every repair evaluated its typed criteria in the producing role's container and the verifier read
the rows (`patch_verification … agent_rows=N agent_executed=M` on all eleven). `decided_by_agent`
was 0 on every roll: the verifier's own rows reached the same verdict each time, so no verdict
rested on the agent rows alone. The positive evidence is that the rows existed, were executed, and
were discounted correctly where the file was absent (#1262).

### 3.3 Deviation
React roll 5 was launched before roll 4's rounds had been read: the assistant released the chain
on roll 4's headline (accepted) at 05:25Z and read the rounds afterwards, finding R2 falsified at
05:28Z and arming the stop. Roll 5 therefore ran after the early stop should have fired. It is
recorded as a counted roll on the same pin and deploy; its evidence (§4.2) is reported. Next.js
roll 2 was launched by hand after roll 1's full reading (07:19Z). The chain's boundary release is
now a two-step: read, then release (§7).

---

## 4. Findings

Drafted 2026-09-03 for the owner's go (six drafts in the session scratchpad), each cited to the
stored artifacts; placed 1.7.2 by the owner's ruling to cut as is.

### 4.1 A qa.test repair of an ABSENT suite is accepted without the #456 retest — React roll 2, Next.js roll 1
`qa.test` emitted a preamble (React roll 2 twice: 122 / 165 tokens; Next.js roll 1's API suite
once); `qa.test_repair` produced the suite and ran it green in the qa container
(`agent_executed=5` and `=6`, incl. the executing check); no retest was dispatched —
`dispatched_flow_executor.py:3215` gates the retest on the failed result already carrying a
`test_result`, which an emission failure never has; on React roll 2 `tests_pass` and
`frontend_build` stayed `subject_missing` → `blocked_unverified`. Pre-existing (#456-era), exposed
by the contentless emission. Audit PASS.

### 4.2 A re-dispatched qa.test's passing rows never reach the ledger — React roll 5
Attempt 1 at `path/backend/tests/test_runs.py` (§4.4) → 7 failed rows; repair refused; attempt 2
at the right path → `art_792d67a6dd27`, 8/8 passed, identities identical. Summary: rejected on
attempt 1's rows; none of attempt 2's typed rows in `verified`. Replay through
`normalize_task_checks` + `aggregate_verification`: both attempts → accepted; attempt 1 only →
rejected. The §6.5 resolver works; the rows were never recorded. Drop site not established
(candidates named in the draft). Pre-existing (#379-era recording path). Audit PASS.

### 4.3 #1130's own-frame detector is pytest-shaped — React roll 4 (R2)
§2. Fix shape: per-runner own-frame declaration (stack-aware, per the owner's 08-27 ruling),
validated against `art_b119474ce8fa`.

### 4.4 The fence template `language:path/to/file` copied literally — React roll 5
`fences={'path': 1} head='```python:path/backend/tests/test_runs.py'`. Correct content at the wrong
path; a whole round spent. Prompt-asset fix (concrete example on the task's own expected file) plus
a parser backstop.

### 4.5 The refund path re-briefs from the refunded emission, and prose-only output counts as content — Next.js roll 1
Round 1's brief carried the failing case; the repair emitted nothing and was refunded (#1053, "1 of
3"); the re-take's `analyze_failure` ran on the refunded emission and its brief carried 0 cases;
the re-taken repair emitted 149 chars of prose, banked as `repair_output.md`, which the refund
rule (`correction_runner.py:1795-1808`, "all artifacts empty") counts as content — so it was
verified instead of refunded, produced two `file_not_found` rows (discounted), and
`correction_terminated_unverifiable` (#1221) ended the loop with a message about an absent
toolchain. The run was rejected on the `tests_pass` row of the suite the gate had already rejected.

### 4.6 Instrument
- `typed_checks.kind_gate_rejections` / `additive_rejections` count failed rows regardless of
  reason: React roll 5's "1" is a `file_not_found` row. Count by reason.
- `loop_texture.unverifiable_toolchain_absent` counts every `no_executed_blocking_checks` verdict;
  Next.js roll 1's came from an absent file. Read the agent rows' reasons.
- `loop_texture.empty_repair_emissions` keys on one log token and missed the prose-only repairs;
  read the emission-shape log (`chars=` / `fences=`).
- The chain's boundary release must follow the reading (§3.3).

---

## 5. Texture

- **Contentless qa emissions** (a preamble or nothing, 67–263 completion tokens): React 5 across 5
  rolls (first attempt on rolls 1, 2 ×2, 4; the repair on roll 5); Next.js 9 of 11 primary
  attempts across 2 rolls. 1.6.6 recorded none. The qa role writes intent ("I'll verify the
  workspace state…") and stops. Reported as measured for the Reasoning line (1.7.0); no prediction
  attached, and it shaped five of seven rolls.
- qa primary completion tokens on emissions that produced a suite: React 2,073–3,059 (1.6.6:
  3,233–6,594); Next.js repairs 2,068–4,920.
- Wall clock 45–65 min per roll (1.6.6: 43–74). Zero framing re-rolls on either set; the gate was
  system-decided on four rolls and agent-decided under the §6 constant on three.
- `checks_by_environment`: development 15–32, qa 5–38, builder 1–2 per roll.
- `container_packaging` (#598, reporting-only): `npm_ci_without_lockfile` on React rolls 3 and 5
  and both Next.js rolls — the finding every Next.js shakeout produced, now on both builders.
- Next.js roll 2: the kind-gate refusal reason was carried into the next brief (#870) and the
  third repair still asserted `participantCount` as a string.

---

## 6. What these sets do not claim

- **Not a rate.** 3 of 5 against 4 of 6, and 0 of 2 against 2 of 2, are not detectable changes; §1
  set no bar.
- **Not that the recovery path is sound after a contentless qa emission** — it is not, in four
  distinct seams (§4.1, §4.2, §4.5), all pre-existing and reached for the first time because the
  emissions were contentless.
- **Not that #1130 covers the frontend** — it covers the pytest shape it was built from (§2, R2).
- **Not that the Next.js arm regressed on the pack** — its two failures are a qa role that did not
  write a suite and a kind gate that refused what the repairs wrote; the pack's gates held.
- **Not a general rate**: `full-38` (qwen3.8:27b) on `group_run`.
- **Not a claim about response correctness beyond the contract's `json_has` floor** (1.6.3 §2).

---

## 7. Rule for the next record

Carried from 1.6.6 §7 (origin of each failing assertion; applied vs refused; greens by re-dispatch
separately; which pack items each roll exercised). Added by this set: **read the rounds before
releasing the next roll** — a headline verdict is not the boundary reading; **count contentless
emissions** (chars/fences from the emission-shape log) as a texture field; and **read every
readout by its reason**, not its count — three of the driver's prediction readouts counted rows
whose reason was not the one the prediction names (§4.6).
