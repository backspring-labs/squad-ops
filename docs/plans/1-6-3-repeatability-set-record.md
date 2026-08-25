# 1.6.3 — Repeatability Set: Record

**Closed 2026-08-24.** Eight counted rolls, no voids, no resets. Pre-registration:
`docs/plans/1-6-3-repeatability-set-preregistration.md`, in force from roll 1 and unchanged
throughout.

---

## 1. Headline

**5 of 8 functional — 62.5%, 95% CI [30.6%, 86.3%].**

Functional means what §5 pre-registered: verdict `accepted` **and** boot audit passes **and**
zero manual intervention. All three held for five rolls.

**8 of 8 boot audits passed**, and §2 below is careful about what that does and does not mean.

The interval is what §1.3 said it would be. This set cannot distinguish a 50% system from a
65% one and does not claim to. It establishes the baseline that 1.6.4's set compares against.

| roll | cycle | verdict | audit | corrections | wall | criteria |
|---|---|---|---|---|---|---|
| 1 | `cyc_a24e4619844e` | rejected | PASS | 4 | 96 min | 8/14 |
| 2 | `cyc_b04cfe4b6191` | accepted | PASS | 0 | 52 min | 12/14 |
| 3 | `cyc_1a3161035eb7` | accepted | PASS | 1 | 66 min | 12/14 |
| 4 | `cyc_a38814afc16d` | rejected | PASS | 3 | 97 min | 11/14 |
| 5 | `cyc_421d29473f86` | rejected | PASS | 4 | 110 min | 13/15 |
| 6 | `cyc_09936ee022b2` | accepted | PASS | 1 | 63 min | 13/14 |
| 7 | `cyc_c9fd8db53613` | accepted | PASS | 0 | 54 min | 12/14 |
| 8 | `cyc_9c43f56c5cd8` | accepted | PASS | 0 | 52 min | 11/14 |

Every gate was decided by `system:no_open_questions`. §6.1's operator path never fired, so
"zero manual intervention" is literally true for this set rather than true-by-ruling.

---

## 2. What the boot audit actually certifies — a correction made mid-set

**It does not verify response bodies.** Every contract probe in this set carries only
`status` and `error_code`; no `json_has` appears anywhere, because it has no producer
(#1079's deferred half). The audit certifies that the application **installs, builds, boots,
returns the declared status codes, and that the UI's requested paths resolve.** `id` is
checked only incidentally, via `capture: {run_id: id}`.

This correction was forced by roll 5 and is recorded because the set had been reporting the
stronger claim for four rolls. Field evidence is on #1079.

**The three rejections are therefore not interchangeable:**

| roll | cause | was the app actually correct? |
|---|---|---|
| 1 | #1087 — fill asserted `TABLES.Participant` | **yes** — false rejection |
| 4 | #1087 — fill asserted `TABLES.Participant` and `TABLES.RunSummary` | **yes** — false rejection |
| 5 | #1029's response floor caught a missing field the audit structurally cannot see | **no** — correct rejection |

So across eight rolls the framework **wrongly rejected two working applications and correctly
rejected one broken one**. That is a more actionable statement than the headline rate, and it
is the set's most useful output.

---

## 3. #1087 — the finding, and how it was held

Filed **#1087**. The frozen store exports `TABLES.X` for every declared entity, including
entities that exist only as embedded shapes (`Run.participants: list[Participant]`) or as
response projections (`GET /api/runs → list[RunSummary]`). Nothing tells the qa fill author
which tables a correct application root-persists. The dev stores embedded, matching the
declared shape; the fill asserts on the phantom table; a working app is rejected.

**Perfect separation on one frozen deploy:**

| tables the fills assert on | rolls | outcome |
|---|---|---|
| `Run` only | shakeout 2, 2, 3, 5, 6, 7, 8 | accepted (except roll 5, rejected for an unrelated real defect) |
| a non-`Run` table | 1, 4 | **both rejected** |

The dev side was verified correct in both failures: roll 4's three route handlers write to
`TABLES.Run` and nothing else.

**It was deliberately not filed on the first instance.** An early sweep suggested "7 of 8
cycles asserting `TABLES.Participant` were rejected"; that was an artifact of matching
`__tests__/harness.test.ts`, the *frozen* file that tests the store by inserting its own row.
Excluding it left two instances — a mechanism plus an anecdote. It was filed after roll 4
supplied the second frozen-deploy positive.

---

## 4. Texture

**The framing tax is gone.** Zero framing re-rolls across eight rolls, and one framing run
each across both shakeouts. The pre-1.6.2 green roll needed **three** framing runs, two of
them auto-rejected by `system:plan_validation` on the success-status restatement class. Ten
consecutive cycles have now framed on the first attempt. This is #1067 and #1070A, measured.

**Corrections split cleanly, with no overlap:**

| rounds | rolls | outcome |
|---|---|---|
| 0–1 | 2, 3, 6, 7, 8 | all accepted |
| 3–4 | 1, 4, 5 | all rejected |

Two of the five greens used the loop successfully (rolls 3 and 6 converged on round one), so
it is not dead weight. But **no roll in this set ever recovered past round one.** Greens
averaged 57 minutes, reds 101 — roughly two hours of the set's nine went to rounds that never
worked.

The honest reading is association, not cause: "corrections make it worse" and "hard rolls
need corrections and are also likelier to fail" are indistinguishable here. What the data does
support is that continuing past round one bought nothing in eight attempts.

**`criteria_unevidenced` never settled.** Every roll dropped between one and five
`vc-compiles-*` criteria, on one frozen deploy, ranging 8/14 to 13/15. §4 marked this
confounded before the set opened, and it stays confounded — the field measures #1021's
unexplained variability, not quality. Eight same-configuration samples is now the largest
body of evidence that question has, and it is banked for whoever takes #1021's mechanism.

**#971 earned its place in the stack.** 44, 48, 11, 48 and 11 failed emissions banked on the
rolls that needed them. Roll 1's root cause was traced by reading emissions that, before this
release, would not have existed.

---

## 5. What this set does not claim

- **Not a general rate.** `full-38` (qwen3.8:27b) with `build_profile=nextjs_ts` and
  `dev_capability=nextjs_ts`, on `group_run`. `full` (qwen3.6) remains the canonical squad and
  the meaning of every historical record; this set says nothing about it.
- **Not a claim about response correctness**, per §2.
- **Not evidence that #1082 catches truncations.** Nothing in eight rolls was truncated, so the
  guard was never asked. It demonstrated only that it does not reject healthy work — across
  eight rolls it produced zero false positives, which is the risk that mattered.
- **Not a significance claim.** 5/8 against the prior 1-of-3 is not a detectable improvement at
  this N, and §1.3 pre-registered that limit rather than discovering it afterwards.

---

## 6. Correction — 2026-08-25: rolls 1 and 4 were not false rejections

§2 and §3 above say the applications in rolls 1 and 4 were correct and were rejected only
by fills asserting on phantom tables. **That is wrong**, and the evidence that shows it
was banked at the time: the seven per-round `test_report.md` files each roll stored.

**What the reports say.** In both rolls, `vc-probe-api-runs-join.scaffold.test.ts` fails
with `expected undefined not to be undefined` at **every** round, including the last. That
message comes from the frozen response floor (`expectShape`, lines 35–36 of the shell,
#1029), which runs *before* the qa fill slot — the fill cannot cause it, and the final
fills in both rolls carry no `not.toBeUndefined()` of their own. Roll 4's final
`app/api/runs/[run_id]/join/route.ts` returns `participants` as bare strings where the
manifest declares `list[Participant]` with `name`. Both rolls' round-0 `failure_analysis.md`
name this correctly (`app_contract`, owner dev, line 36). The phantom-table assertion
(`join-duplicate`: `expected [] to have a length of 1 but got +0`) is a **second** failing
probe, never the only one.

**The corrected table:**

| roll | cause | was the app actually correct? |
|---|---|---|
| 1 | join response fails the frozen shape floor every round; #1087 phantom-table assertion is a second failure and misdirected the repair (`insert(TABLES.Participant, …)` at round 1) | **no** |
| 4 | join response fails the frozen shape floor every round (bare-string `participants`); #1087 is a second failure | **no** |
| 5 | join response fails the frozen shape floor (missing `normalized` on the participant element) | **no** |

So across eight rolls the framework rejected three applications, **all three correctly**,
and all three for the same defect class: the join endpoint's response shape versus the
declared element kind, diagnosed at round 0 and never landed by three or four repair rounds.

**How the error was made.** §2 records that the boot audit cannot see response bodies, and
§3 then infers "the app was fine" from the boot audit. The dev side was "verified correct"
by checking which table the routes wrote to — the storage target — not what the routes
returned. Audit PASS was read as application correctness one section after saying it
cannot mean that.

**What survives.** #1087 is real: the handle exists, the fills reached for it, and roll 1's
repair chased it. The "perfect separation" in §3 is also real as an *observation* — but it
separates rolls with a second failure from rolls without one, not working apps from
rejected ones. What does not survive is #1087 as the set's headline yield; fixed alone it
flips zero rolls. §4's correction-round association stands and is strengthened: every red
is a correctly-diagnosed one-field defect the loop failed to land.

**Rule for the next record:** for each rejection, name the failing assertion's origin —
spine or fill — and the round it first appeared, from the stored reports. Not from the
roll-up, not from the audit.
