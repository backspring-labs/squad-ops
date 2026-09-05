# 1.7.2 — plan

**Revision 1, 2026-09-03.** Written the day v1.7.1 was tagged, from the 1.7.1 verification-set
record (`docs/plans/1-7-1-verification-set-record.md`), the 1.7.0 plan's Loop Honesty pack and
line breakdown (`docs/plans/1-7-0-plan.md` §2.3, §3.1), the six issues that record filed
(#1268–#1273) and the stored per-round artifacts of the seven counted rolls. **This plan is
about one thing: the correction loop tells the truth about what happened after a failed
attempt** — what it saw, what it re-ran, what it recorded — because the 1.7.1 rolls showed
that every non-green but one was the loop losing evidence on the path *after* a failure rather
than the squad failing to fix anything.

**The rulings that shape it** (owner, 2026-09-03): 1.7.1 is cut as is with R2 falsified, and
#1270 is fixed here rather than in a 1.7.1.1 (§5 records the amendment to the 1.7.0 plan's
§3.1 rule); **#1268 is the top of the line** — the qa role's contentless first attempt is the
origin every other 1.7.1 finding was reached through, it is new on the 1.7.0 tree, and its
mechanism is unread, so it is *instrumented before it is fixed*; the line's hardening intent
is served by evidence integrity first and infrastructure second (§6).

---

## 1. What the 1.7.1 record says the pack has to answer

| what the rolls showed | rolls | issue | what it says about the loop |
|---|---|---|---|
| the qa role wrote a sentence of intent and stopped — 14 attempts in 7 rolls, zero in 1.6.6, first seen 2026-08-31 | R1, R2, R4, R5; N1, N2 | **#1268** | the loop's single most common entry condition in this line is one it had never met before |
| a repair of an *absent* suite is accepted without the #456 retest, because the retest is keyed on a stale `test_result` the failed attempt never had | R2, N1 | **#1269** | the loop re-tests only failures that already had behavioural evidence |
| a re-dispatched task's passing rows never reach the ledger; the run is rejected on the first attempt's rows — replay: both attempts recorded → accepted | R5 | **#1271** | the loop records the failure and forgets the recovery |
| after a refunded repair the re-take is briefed from the *empty emission*, not the original failure, and a prose-only repair counts as content, so the second one is verified instead of refunded and the loop ends "unverifiable" for a file that does not exist | N1 | **#1273** | the loop analyses its own last output instead of the failure it is repairing |
| a re-dispatched qa.test re-authors without the case that found the defect | 1.7.1 shakeout | **#1260** | the re-dispatch has no memory of what failed |
| an own-frame JavaScript TypeError in the qa-owned suite goes to the dev chain — the #1130 detector is pytest-shaped; **R2 falsified** | R4 | **#1270** | the one prediction the pack lost, on a shape the fix never saw |
| the fence template's placeholder `path/to/file` copied literally; a correct suite at the wrong path, a whole round spent | R5 | **#1272** | one prompt token, one round |
| three prediction readouts counted rows whose reason was not the one the prediction names | R5, N1 | **#1276** | the instrument the next set is read from |
| R2, R4 and R7 were unexercised on three of five React rolls; a diagnostic that hands the seam its input is a replay, not an exercise | all | **#1251** | predictions that no roll is likely to reach need a fault the roll's own path takes |

Two things the table says that the 1.7.0 plan's Loop Honesty list did not know. First, the
loop's failures cluster on *one seam* — the evidence after a failed attempt — and #1269, #1271,
#1273 and #1260 are four faces of it; fixing them as four unrelated bugs is how #1259 and #1264
happened. Second, the pack's original items (#788, #994, #995, #999, #1110, #968) were chosen
from 1.6.x rolls; three of them are the same seam (#994, #995 discard state; #999 never
persists it) and belong with the four above, while #968 and #1054 (the analysis trusted
unchecked) are a different mechanism and keep their own half.

---

## 2. The pack — roll-verified, eight items

Capacity per the 1.7.0 plan §3.1: six to eight roll-verified items, each with a prediction
readable from the record and a roll where it can fire.

### 2.1 #1268 — the contentless first attempt: read it, then fix it

**Instrument first.** Before any change: read three of the contentless generations from
LangFuse (Next.js roll 2 `cyc_5b027f3e74fc` m006 attempts 1–5 are the densest sample) with
prompt, response, usage, finish reason and the reasoning split, and one 1.6.6 qa.test
generation for contrast. The emission-shape log gains the finish reason and the reasoning
token count beside `chars`/`fences` if it does not carry them, so the next roll's record
reads the shape without a LangFuse visit. **The reading is recorded as an amendment to this
plan (§8) before the fix is chosen**; the candidates, in the order the evidence suggests, are
the Reasoning line's stop/budget handling (1.7.0 §2.1), the streaming-path reasoning-text
handling (#1194, landed the day the shape first appears), and prompt growth from the 1.7.1 qa
additions. Whichever it is, the fix is a *single* change with the prediction below; a
contentless emission that still occurs after it is retried with the emission-shape fact in the
retry feedback, not silently.

**Prediction L1:** no qa task's first attempt on either stack is contentless (chars < 400 and
zero fences); falsified by one such emission in a counted roll; read from the emission-shape
readout (#1276), not the banked artifact count.

### 2.2 The evidence after a failed attempt — one seam, four faces (#1269, #1271, #1273, #1260)

Built as one mechanism with one table (CLAUDE.md "Typed checks": every seam that evaluates
the task's criteria and the tree each sees, plus what each records), landed as four PRs in
this order, each with its replay from the stored roll and a wiring test that enters at the
executor's task loop:

- **#1271 first** — the recording. A re-dispatched attempt's rows reach the ledger under the
  same identity as the failed attempt's, so §6.5 supersedes them (the replay in the record §4.2
  is the test's oracle). Establish the drop site before the fix; the record names two
  candidates and the one that is right is the one the wiring test enters through.
- **#1269** — the retest is keyed on the task's *evidence contract* (a `qa.test` whose
  contract requires `tests_pass`), not on the failed result already carrying a
  `test_result`. A repair that supplies the suite an emission failure lacked is retested.
- **#1273** — a refunded round is re-briefed from the original failed result (its
  `failing_cases`), and the refund rule counts only workspace-typed artifacts, so a prose-only
  repair is refunded rather than verified. The #1221 termination message names the absent
  file when that is what happened.
- **#1260** — the re-dispatch carries the failing cases the previous attempt exposed, as the
  repair brief already does (#1123's mechanism, applied to the re-dispatch envelope). This is
  the "design, not a patch" the issue asked for; the design is that one sentence, and the
  brief's case list is the seam that already exists.

**Predictions L2–L5** (§4): after a repair of an absent suite the run carries executed
`tests_pass` evidence (L2); a run whose last attempt passed is never rejected on an earlier
attempt's rows (L3); every re-taken brief carries the original failed row's cases and no
prose-only repair is verified (L4); a re-dispatched qa.test's suite carries every case the
failed attempt's report named (L5).

### 2.3 #788 — the repairer reads the traceback

From the original list, kept: `app_tracebacks` is captured (#687) and reaches the analyzer,
and the repair prompt renders five evidence blocks without it. One entry in the fragment, one
prediction. **L6:** a repair of a runtime-error failure is briefed with the traceback; read
from the stored repair brief.

### 2.4 #1270 — the own-frame detector is a per-runner declaration

The 1.7.1 R2 item, first in sequence after the instrument (§5). Stack-aware per the owner's
2026-08-27 ruling: the runner declares which own-frame shapes it recognises — pytest keeps
`NameError` and the argument-binding `TypeError`; vitest adds `… is not a function`,
`… is not defined`, `Cannot read properties of undefined` raised at an own frame with no
application frame beneath — and the routing seam stays runner-neutral. Validated against the
real emission (`art_b119474ce8fa`), not a fixture. **L7 is 1.7.1's R2 re-registered verbatim,
with the JavaScript shape named** and a fault-injected diagnostic that produces it (§4).

### 2.5 #1272 — the fence template's placeholder

Prompt asset, not Python: the convention is stated on the task's own expected file
(``` ```python:backend/tests/test_runs.py``` `) rather than `path/to/file`, in every
template that states it (`request.cycle_repair_task.md`,
`request.cycle_emission_retry_feedback.md`, `request.development_develop.focused_build_task.md`,
and qa.test's), plus a parser backstop that strips a leading `path/` segment the expected
list does not contain and reports the strip. **L8:** no emission lands at a path with the
literal `path/` prefix; read from the stored artifact names.

### 2.6 What is deliberately not built

- **#994, #995, #968, #1054, #1070, #936/#933** — Loop Honesty's second half, 1.7.3 as the
  1.7.0 plan placed it; #994/#995 are this pack's seam but its capacity is eight, and #968/#1054
  (the analysis checked against the source) are a different mechanism.
  *Rev 4: re-placed to 1.7.4 by `docs/plans/1-7-3-plan.md` §6 — §3's ruling makes the
  Boundaries list 1.7.3's whole content, and #1312/#1254 lead the 1.7.4 pack.*
- **#414** — stays a design item at review; the refund mechanics #1273 touches are not a
  budget redesign.
- **#1122** — an `enhancement`, the 1.8 lane, unchanged.
- **A second fix for #1268 before the first is measured.** One change, one prediction.

---

## 3. The CI-verified list — frozen at three (owner's ruling, 2026-09-04)

**Preconditions, before the pack's first roll-verified PR:**

- **#1276** — the driver's readouts by reason; the set is read from them.
- **#1251** — the fault-injection hook: a cycle-create override that makes a named task's
  emission take a named fault (an own-frame `is not a function` in the qa suite; an absent
  suite; a suite at `path/…`; a refunded repair) *on the roll's own path*. The 1.7.1 record
  §3 and `docs/plans/verification-sets/README.md` already require it; three of eight
  predictions here cannot be exercised without it.

### What shipped

| item | what | PR |
|---|---|---|
| **#1150** | one home for the gate rule — `GATE_REJECTED_STATES` derived from `TERMINAL_STATES` | #1302 |
| **#1110** | the retry path says whether the #998 remedy reached the prompt | #1303 |
| **#1148** | the fan-out path records verification evidence | #1307 |

### What moved to 1.7.3, and the count that decided it

Eleven move: **#154, #377, #381, #305, #559, #922, #218, #1254, #999, #1087, #1112.**
(#225 and #219 had already been moved to 1.7.3 at rev 1, making the original list fourteen.)

**Why now.** The list was allocated to "the other lane, in parallel" and was never staffed:
on 2026-09-04, thirteen of the fourteen had no branch at all, and the fourteenth (#1087) had
one commit, 98 behind main, whose own message reads *"fork's work, 10 regression failures,
NOT opened as a PR"*. Six of the eleven are shared-vocabulary refactors — import rewiring,
status vocabularies, a three-way capability rename — which are multi-day each and, landing
beside a pack whose reds must be attributable, would make a regression unattributable
between the pack and the refactor. That is the reason CLAUDE.md quarantines structural
refactors into their own release in the first place.

**The count this line owes the record.** Several of these have been scheduled before and
not shipped, and a plan that schedules them a fifth time without saying so is the "spec that
no longer describes reality" failure in plan form:

| item | release plans that scheduled it | times |
|---|---|---|
| #559 | 1.4.3, 1.4.4, 1.5.0, 1.7.0, 1.7.2 | **5** |
| #154 | 1.4-evidence-arc, 1.5.0, 1.7.0, 1.7.2 | **4** |
| #999 | 1.6.4, 1.7.0, 1.7.1, 1.7.2 | **4** |
| #1110 | 1.6.5, 1.7.0, 1.7.1, 1.7.2 | 4 — **shipped here** |
| #377, #381, #305 | 1.5.0, 1.7.0, 1.7.2 | 3 each |

**So 1.7.3 must carry this list as its content, not beside a headline.** The structural
reason these slip is that they are always secondary to something that gates a cut, and
CI-verified work gates nothing. Attaching them to a 1.7.3 that already has "Loop Honesty,
second half" as its headline reproduces the condition exactly. A release whose subject *is*
this list is the only version of "deferred" that has ever been distinguishable from "never".

### Drift the cut record must declare

Three items of the intended 1.7.2 tree shipped and eleven did not. The cut record names the
eleven and says they are additive-by-omission — nothing in the pack depends on them, and
**#1254 is the one to call out by name**: it doubles `harness_boundary` on every bound qa
suite, so the counted set measures a checks ledger with a known duplication in it. That is
stated here, before roll 1, rather than discovered in the record.

---

## 4. The verification set — exercise, by injection where a roll will not reach it

Two counting sets on one frozen deploy — **FastAPI+React N = 6, Next.js+TS N = 3** (up from
2: both 1.7.1 Next.js rolls went through the contentless-emission path, so that arm reads L1
directly and L2/L4 fire there first; a third roll is one more chance to reach delivery at the
cost of an hour) — with two changes from 1.7.1, both from its record §7:

- **Every prediction has an exercise plan stated before roll 1.** Where the last three sets
  show a roll is unlikely to reach it (L2, L4, L5, L7 need a specific failure shape), a
  fault-injected diagnostic on the deploy before roll 1 runs the roll's own path with the
  fault (#1251); it is reported as a diagnostic, never as a roll, and "unexercised" on a
  counted roll then reads as "exercised by injection, held/falsified", not as silence.
- **Every readout is read by its reason** (#1276), and the record counts contentless
  emissions and non-execution beside failure.

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
| **R1, R3, R5, R6, R7; S0–S3, Q0, Q3, Q5, P0** | carried from 1.7.1 unchanged — unexercised is not passed | as there | as there |

**Texture:** verdict rate against 1.7.1's 3 of 5 and 0 of 2 (no bar); rounds; greens by
repair vs re-dispatch; refused vs applied vs refunded; contentless emissions per roll; qa
primary tokens; `checks_by_environment`.

**Shakeout loop with the exit rule** (`docs/plans/verification-sets/README.md`): a pair on one
deploy with no new seam finding, budgeted at three rounds, the count reported in the record.

**Early stop, one direction.** A falsified L1–L8 stops the set. The set's record and the cut
say what the rolls did not exercise.

**One bar, and only one: L1.** The line's other predictions keep 1.7.1's convention — no
rate bar, a falsification stops the set and the cut says so. L1 is different because #1268 is
the condition every other item is measured *through*: a set in which a first attempt is still
contentless has not measured the pack, it has measured the loop's recovery from the same
fault again. So **a falsified L1 blocks the cut** — the fix is revised from the new evidence
and the set re-rolled — where 1.7.1's R2 did not.

---

## 5. The 1.7.1.1 that was not cut — an amendment to the 1.7.0 plan §3.1

The 1.7.0 plan §3.1 says a falsified prediction "costs a 1.7.x.1 before the next pack opens".
1.7.1's R2 was falsified and the owner cut 1.7.1 as is (2026-09-03), with the item placed here.
The rule's purpose — the falsified item is fixed and *re-tested before the pack moves on* — is
kept: #1270 is first in this pack's sequence after the instrument, L7 is R2 re-registered
verbatim with the shape that falsified it, and the fault-injected diagnostic makes it
exercisable on the first shakeout rather than left to chance. The separate patch release is
not kept, because a one-item release whose prediction no roll is likely to reach would ship a
fix without the evidence the rule exists to collect. The 1.7.0 plan's revision history records
this in the same PR.

---

## 6. Hardening — what this line does and does not pull forward

The odd minor is stabilization; its hardening is defined in the 1.7.0 plan §2.6 as "what 1.8
needs underneath it". The 1.7.1 rolls say the thing most in the way of an unattended campaign
is not the ops floor but the loop's evidence: five of seven rolls were decided by what the
loop lost after a failure. So this line's hardening is §2.2 — evidence integrity on the
recovery path — and the instrument (#1276, #1251) that makes the next set's claims readable.
The infrastructure rider (#1147, #575, #577, #576, #578, #330, #300, #581, #560, #372, #352,
#353, #574, plus #1204/#1205 from the 1.7.1 plan §2.4) stays in 1.7.3 as placed: **no 1.7.1
roll reached any of it**, and pulling it forward would put CI-verified churn beside a pack
whose reds must be attributable. The one exception considered and not taken: #1147 (one
timeout for two things) — no roll in this line or the last has hit either bound.
*Rev 4: the rider is re-placed to 1.7.4 by the 1.7.3 plan §6, for the reason §3 states —
1.7.3 carries the Boundaries list and nothing beside it.*

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.7.0 plan's §7 amendment (§5).
2. **#1268's reading** — the LangFuse read and the emission-shape fields; recorded as an
   amendment here (§8) with the fix decision. Nothing else about #1268 lands before it.
3. **Preconditions** — #1276 (readouts by reason), #1251 (fault injection), each CI-verified.
4. **#1270**, then **#2.2 in order** (#1271, #1269, #1273, #1260), each on its own branch with
   its replay from the stored roll as the test and a wiring test entering at the executor.
5. **#788, #1272, the #1268 fix.**
6. **The rider** in parallel on the other lane.
7. Rebuild, verify the loaded modules in-container, shakeouts with the fault-injected
   diagnostics to the exit rule, pre-register, roll — **no merges to main while the set is
   open**.
8. Record from the per-round evidence; cut 1.7.2 by the seven steps in `CLAUDE.md`. Then 1.7.3
   (Loop Honesty, second half; the infrastructure rider — *rev 4: both re-placed to 1.7.4;
   1.7.3 is the Boundaries list per §3, planned in `docs/plans/1-7-3-plan.md`*).

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

- **#1268's fix** is decided from the reading in step 2 and recorded as an amendment here.
  What is decided now: it is **one** change, and if the reading is inconclusive the fix is the
  retry-with-fact (a contentless emission re-prompted with the emission-shape fact in the
  retry feedback), because that holds L1 regardless of cause and leaves the cause readable in
  the next record.
- **L1 is the line's one bar** (§4) — a falsified L1 blocks the cut.
- **Next.js+TS N = 3** (§4).
- **#1260 reuses the repair brief's case list** — the same presence-keyed `failing_cases` the
  #1123 brief carries, threaded onto the re-dispatch envelope; no new key, one home for one
  fact (`feedback: gate on prose means missing derivation` — the fact is derived, not
  restated).
- **#225 and #219 go to 1.7.3 now** (§3).
- **#414 stays at design review** — the refund mechanics #1273 touches are not a budget
  redesign, and no 1.7.1 roll exhausted a budget for a severity-blind reason.

---

## 8a. The #1268 reading — 2026-09-03

§2.1 gates the fix on reading the contentless generations *before* any change is chosen
(`feedback: instrument before fixing`). This section is that reading, and the fix it selects.

### What was read

- **All 31 `qa.test` / `qa.test_repair` generations of the seven counted rolls**, from
  LangFuse: prompt (capped at 10,000 chars, `telemetry/models.py:134`), usage, latency and
  the per-generation metadata, which carries the reasoning level actually sent.
- **The five banked contentless emissions of Next.js roll 2 in full** —
  `art_fc4fdc92cd4d`, `art_6e15a5b5a05f`, `art_1d7f616690b5`, `art_4225f34d48c8`,
  `art_065386df941c` (`cyc_5b027f3e74fc` / `run_d515e656db78`), 109–265 bytes each.
- **Thirteen 1.6.6-era `qa.test` generations** (2026-08-27/28) as the contrast §2.1 asks for.
- **The agent emission-shape window for the whole counted set**: 162 emissions logged, 16
  contentless (13 `qa_test_handler`, 2 `qa_test_repair_handler`, 1 `qa_test_handler:self_eval`).

### What the emissions are

A single sentence of intent and nothing else — "I'll examine the workspace to confirm the
store API, the route handler export signatures, and the DELETE participants endpoint before
writing tests." One of the sixteen goes further and shows what the model was about to do:
`chars=467 … head='Let me first examine the current state of the workspace … <function_calls>
<invoke name="fs.read_file"><parameter name="path">backen'`. **The model is announcing a tool
call and stopping.** There is no tool loop at this seam and no tools are offered.

### The three candidates §2.1 names, and what the reading does to each

| candidate | verdict | on what evidence |
|---|---|---|
| the Reasoning line's stop/budget handling (1.7.0 §2.1) | **this is it** — but not as a *budget* | see below |
| the streaming path's `reasoning_text` handling (#1194) | **falsified** | `metadata.reasoning = "none"` on every one, so `think: false` was sent and there was no thinking channel to drop. `reasoning_text` is null because none was produced, not because it was lost. |
| prompt growth from the 1.7.1 qa additions | **falsified as a cause** | 1.6.6 ran 8,568–21,875-token prompts and returned 3,233–6,594 completion tokens. On the 1.7.x tree an 8,853-token prompt goes contentless (`cyc_ca02bed7fbb4` repair) and a 21,758-token one succeeds (`cyc_f05692bb3ceb`). There is no size threshold; the failure is stochastic at every size. |

Also falsified, and worth stating because #1268's own text hedges on it: **it is not a
truncation.** Outputs are 67–303 completion tokens against a `num_predict` of 12,288, every
one with `done_reason: stop`, and the model's context length is 262,144 — the prompt is
nowhere near a bound.

### The one systematic difference between the two trees

`metadata.reasoning` is `None` on every 1.6.6 generation and `"none"` on every 1.7.x one.
Those are different wires, not different spellings: `None` means the handler passed no level
and the payload carried **no `think` key at all**, so the model's own default applied;
`"none"` means `ReasoningLevel.NONE`, which the Ollama adapter sends as **`think: false`**
(`adapters/llm/ollama.py`, `_build_chat_payload`).

The change is `918b4f87`, 2026-08-28, "#927 phase 2 — every capability declares how much
reasoning its output wants", which declared `qa.test` and `qa.test_repair` as
`ReasoningLevel.NONE` and, in the same commit, began recording the level in the generation
metadata. #1268's own dating matches it with nothing to spare: zero contentless emissions in
the 1.6.6 counted rolls (a deploy that predates the commit), the first one 2026-08-31 02:31Z
on the first deploy that carried it.

### The paired live A/B — the mechanism, measured rather than inferred

A correlation across two deploys is not a mechanism, so it was put to the model directly.
Same system prompt (the real assembled `qa`/`agent_start`/`qa.test` prompt), same user
prompt, same `num_predict`, no temperature (production sends none, so the model's own
default applies), 17,049 prompt tokens against the roll's 15,854–16,040 — arms interleaved:

| arm | wire | usable emissions (≥1 addressed fence) |
|---|---|---|
| **A** | `think: false` — production today | **1 of 6** (18,425 chars once; then 96, 1,034, 106, 115, 143 chars, no fence) |
| **B** | no `think` key — the pre-#927 wire | **6 of 6** (9,582–17,906 chars, 2 fences each, 4,226–8,554 thinking chars) |
| **C** | `think: true` — the wire the policy can actually send | **6 of 6** (11,798–13,248 chars, 2 fences each, 7,932–24,330 thinking chars) |

Arms B and C are indistinguishable in outcome and both differ from A; the wire the fix can
actually send is therefore the wire that was measured. Arm C exists because **the reasoning
policy cannot express arm B.** `resolve_reasoning_level`
returns a level or `None`, and `None` only for a model with no reasoning channel at all; for
qwen3.8:27b any non-NONE level becomes `think: true`. Landing the fix on arm B alone would
replace a measured inference with an unmeasured one.

**What the A/B does not establish.** The prompt is a faithful *reconstruction*, not the
roll's bytes: LangFuse stores the first 10,000 chars, and the remainder was rebuilt from the
roll's own vault sources and the repo's own qa appendices. It reproduces the shape and the
size, and it reproduces the failure; it is not the same string. N = 6 per arm, one model, one
task type. The claim it supports is the one it was run for: on this seam the `think` flag
moves the contentless rate, and no other candidate does.

### What the fix costs, stated

#927's declaration was not arbitrary. #924 measured the deployed qa **fill brief** at 5,727
completion tokens with the channel on and 413 with it off, for the same eight fill fences —
"reason where the output is an argument, don't where the output is a transcription", and
filling declared slots is transcription. That measurement stands. What it did not measure is
the **primary authoring** task on this prompt, which is not transcription: arm B spends
4,226–8,554 characters of thinking and returns a whole suite, and arm A returns a sentence
five times in six. A round saved on tokens costs a correction round, and #1268 counts what
that came to — fourteen attempts across seven rolls, five of seven rolls shaped by it.

### The fix

**One change, per §8: the declaration, for the two authoring capabilities only.** Arm C is
the fix's own wire and it held 6 of 6.
`qa.test` and `qa.test_repair` move off `ReasoningLevel.NONE`. Every other `NONE` entry
stays — including the fill-mode paths #924 actually measured, which are transcription and
keep the channel off. Prediction **L1** reads it, and L1 is the line's one bar: a contentless
first attempt on a counted roll blocks the cut.

§8's stated fallback — retry-with-fact — is **not** taken as the primary fix, because the
reading is not inconclusive. It remains the right backstop and is worth having on its own
merits: a contentless emission should be re-prompted with its own emission-shape fact rather
than silently re-rolled. That is a separate item, not this one.

### One consequence for §4

#1276 renamed the prediction readouts the carried rows R1/R3/R5/R6/R7 are "read from … as
there": `kind_gate_rejections` → `assertion_kinds_match_rows`, and so on, each now a
`{reason: count}` map with non-execution beside failure, and `unverifiable_toolchain_absent`
→ `unverifiable_by_reason`. The predictions are unchanged; the names and shapes they are read
from are not. The 1.7.1 plan and pre-registration keep the old names, being the record of
what the instrument was called when those sets ran.

## 9. Revision history

- **Rev 4 (2026-09-05)** — §2.6, §6 and §7 step 8 still placed Loop Honesty's second half and
  the infrastructure rider in 1.7.3, written at rev 1 before rev 3's §3 ruling made the
  Boundaries list 1.7.3's subject. Each now carries a pointer to `docs/plans/1-7-3-plan.md`,
  which re-places them to 1.7.4 by name. Nothing about the 1.7.2 pack or its set changes; the
  pre-registration is untouched.

- **Rev 3 (2026-09-04)** — §3 frozen at three shipped items (#1150, #1110, #1148) with
  eleven moved to 1.7.3, on the owner's ruling. The list had never been staffed — thirteen
  of fourteen with no branch, the fourteenth 98 commits behind and self-declared broken —
  and §3 now carries the count of how many release plans have scheduled each item before,
  because deferring #559 for the fifth time without recording it is how a plan stops
  describing reality. Adds the drift the cut record must declare, naming #1254 as the one
  omission the counted set can feel.

- **Rev 2 (2026-09-03)** — §8a records the #1268 reading and the fix it selects (the
  `think: false` the #927 declaration sends, measured against its own control), and notes
  #1276's rename of the readouts §4 carries. Nothing else in the plan changes.
- **Rev 1 (2026-09-03)** — written the day v1.7.1 was tagged; §8 turned from open items into
  recommendations the same day at the owner's request. Written from the 1.7.1 record, the 1.7.0
  plan §2.3/§3.1, issues #1268–#1273 and #1276, and the stored artifacts of the seven counted
  rolls. Re-cuts Loop Honesty's first half around the 1.7.1 evidence: the four recovery-path
  seams and #1260 replace #994/#995/#968 (to 1.7.3), #999/#1110 move to the CI rider, #1270 and
  #1272 join, #1268 leads with an instrument-first rule; #1251 and #1276 become preconditions.
