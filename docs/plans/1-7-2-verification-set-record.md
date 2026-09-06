# 1.7.2 — Verification Sets: Record

**Closed 2026-09-06, 14:50Z.** Two counting sets, **nine counted rolls**: FastAPI+React six,
Next.js+TS three. **No voids and no resets inside the set**, and one void *before* it (§0).
Pre-registration: `docs/plans/1-7-2-verification-set-preregistration.md` (PR #1313), with the
pins added in PR #1322 — in force from roll 1 and unchanged throughout. Deploy frozen at
`d95af712`; the seven image ids are in each set config and were asserted by the driver at every
launch. HEAD pinned at **`b5e8fe12`** at roll 1 and held to the close.

**Zero code drift between the measured deploy and the tag.** `d95af712..b5e8fe12` is two YAML
files under `docs/`; the tag adds only this record and the release commit. The 1.6.2 lesson —
say what the cut evidence does not cover — has nothing to disclose here.

Sizing was the pre-registration's: six on FastAPI+React (the measurement) and three on
Next.js+TS (up from 1.7.1's two, because both 1.7.1 Next.js rolls went through the
contentless-emission path and this arm reads L1 directly).

---

## 0. The void roll, and the shakeout loop

**Counted roll 1 was launched, rejected, and voided.** `cyc_e33939eda950` (2026-09-05 16:24Z)
fell to **#1318**: an accepted patch never superseded the failed attempt's rows, so the run was
rejected on a defect the patch had already fixed. The set was stopped, the defect fixed
(PR #1319), and the set restarted from roll 1 on a rebuilt deploy. Its log is kept as
`roll-1.log.void-roll1-1318` and its HEAD pin as `head_pin.aborted-roll1-cb30c864`.

**The shakeout loop took five rounds against a budget of three.** The cut record owes two
numbers, not one:

| | |
|---|---|
| rounds taken | **5** |
| rounds attributable to the pack | **0** |

Every supersede came from the measuring apparatus. **Twelve instrument defects** across the
line — #1292, #1296, #1298, #1300, #1304, #1305, #1310, #1311, #1318, the P0 nullable false
positive, #1321, and the `refused_patches` truncation (§4.6) — and **none** from the eight items
being measured. Reported as one number this reads as an unstable pack; reported as two it says
three releases' worth of diagnostic machinery had never been run end to end and broke twelve
ways on first contact. The budget was set before anyone knew that.

---

## 1. Headline

### 1.1 FastAPI+React (`fullstack_fastapi_react`) — 5 of 6 functional

| # | cycle | verdict | boot audit | functional | criteria | corr | contentless | min |
|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_eafdc918e8b0` | rejected | FAIL | no | 17/19 | 1 | 0 of 18 | 44 |
| 2 | `cyc_b40ae312c8ac` | accepted | PASS | **yes** | 16/16 | 0 | 0 of 15 | 48 |
| 3 | `cyc_838e5997c81e` | accepted | PASS | **yes** | 16/16 | 0 | 0 of 17 | 53 |
| 4 | `cyc_05935ffcb572` | accepted | PASS | **yes** | 21/21 | 1 | 0 of 20 | 58 |
| 5 | `cyc_37f52053d14d` | accepted | PASS | **yes** | 21/21 | 1 | 0 of 20 | 56 |
| 6 | `cyc_1f292d1953c6` | accepted | PASS | **yes** | 18/18 | 0 | 0 of 16 | 48 |

The single rejection is an application defect: `vc-probe-runs-join` and `vc-probe-runs-leave`
returned a response missing `['id','title','datetime','meeting_location','created_at']` — the
join/leave endpoints did not return the Run body the manifest declares. The probe was winnable
(manifest `response: Run`, `success_status: 200`), so this is the cycle's work product, not a
seam.

### 1.2 Next.js+TS (`nextjs_ts`) — 3 of 3 functional

| # | cycle | verdict | boot audit | functional | criteria | corr | contentless | min |
|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_87ca1a908120` | accepted | PASS | **yes** | 17/17 | 0 | 0 of 15 | 55 |
| 2 | `cyc_c364a4af38a5` | accepted | PASS | **yes** | 17/17 | **3** | 0 of 35 | 109 |
| 3 | `cyc_58279e83c19b` | accepted | PASS | **yes** | 17/17 | 0 | 0 of 16 | 54 |

Texture, not a claim: N=6 and N=3 cannot detect a rate change, and §1 of the pre-registration
set no bar but L1. 1.7.1's comparison — React 3 of 5, Next.js 0 of 2 — is context, not a
measured improvement.

---

## 2. The predictions

**L1 was the set's one bar** (#1268): no qa first attempt is contentless. **Held — 0 contentless
emissions of 172 across nine rolls.** 1.7.1's React arm had three of five rolls carrying
contentless emissions and Next.js 0 of 2; that is what #1268 changed, and this is the evidence.
A falsified L1 would have blocked the cut, because it is the condition every other prediction is
measured *through*.

| prediction | reading | how |
|---|---|---|
| **L1** (#1268) | **HELD** | 0 of 172 emissions contentless |
| **L3** (#1271) | **HELD** | 0 stale evaluations — no run rejected on an earlier attempt's rows |
| **L4** (#1273) | **HELD** | two 0-case repair briefs, both with `tests_pass_rows: 0` — the rows carried no cases either |
| **L2** (#1269) | **UNEXERCISED** | no absent-suite repair arose |
| **L5** (#1260) | **UNEXERCISED** | no re-dispatched suite |
| **L6** (#788) | **UNEXERCISED** | no app runtime error |
| **L7** (#1270) | **UNEXERCISED** | `qa_owned_routed` empty on all nine |
| **L8** (#1272) | **UNEXERCISED** | no emission under a literal `path/` prefix |

**Five of eight predictions entered the set unexercised and left it unexercised.** They are held
only by the injected diagnostics of the shakeout loop (L7, L4 and L5 on `cyc_9e217c266f5f`), not
by any counted roll. Unexercised is not passed, and this record says so rather than letting nine
greens imply coverage.

**L3's reading is only possible because the readout was built after the defect was found.** The
`stale_evaluations` field — a later *store* carrying an earlier *evaluation* — did not exist when
#1318 was diagnosed; L3's declared read ("the last stored evaluation") reported HELD on the very
roll that falsified it. That readout is the fix, and it read clean on all nine.

**Carried readouts.** R1 fired twice, correctly: *"assertion contradicts a declared field kind:
participant_count asserted as string, the manifest declares number"*. R3, R5, R6 clean; R7
`decided_by_agent: 0`. Every "did it not happen, or did we not look" field is empty rather than
absent: `unverifiable_by_reason {}`, `no_execution_by_skip_reason {}`, zero skips on nine rolls.

**B-side:** P0 held on all nine after the round-4 record was re-rendered (§4.4).

---

## 3. What the loop did when it ran

**Six patches applied, two refused, across five correction rounds in nine rolls.**

Next.js roll 2 is the informative one. Three correction rounds; two `qa.test` repairs **refused**
on `assertion_kinds_match` (one also on `unterminated_source`), each judged against 38 agent rows
with 37–38 executed; 33 failed emissions banked; and the run still finished **accepted, 17/17,
zero failed checks**, in 109 minutes. The loop refused two bad repairs and converged anyway.
That is the correction machinery under more pressure than any other roll applied, and it is the
first time this line has evidence of a refusal path ending in an accept.

React rolls 4 and 5 each took a correction round and finished 21/21 — the repair-and-verify path
that #1318 broke, exercised on counted rolls and converging.

---

## 4. Findings

### 4.1 #1318 — an accepted patch never superseded the failed attempt's rows (void roll 1)

The ledger supersedes on `(check_id, subject, criterion_id)` since #1021, and
`PatchCheckRecord.to_check_row()` never carried `criterion_id`, so a patch-verified PASS landed
under `None` and matched nothing. Nothing re-emitted the `required_files` spine row at all. And
`supersede_evidence_artifacts` sat inside the behavioural-retest branch, so a task with no suite
re-stored the pre-patch evaluation eleven milliseconds before the patch's own file landed.
Fixed in PR #1319; the `stale_evaluations` readout is its instrument.

### 4.2 #1321 — the rejects-blank probe was unwinnable on stack 1

`blank_rejection_status` was hardcoded to 422 for `fullstack_fastapi_react` on the premise that
"pydantic 422s before any app code runs". The stack's own frozen `backend/errors.py` installs a
`RequestValidationError` handler returning the manifest's declared status, so a manifest
declaring 400 produced an app that correctly returned 400 and a probe that demanded 422. The
premise was already false when written — the handler landed 2026-07-14 (`fd222bf0`), #874 landed
2026-08-12 (`84dbd29d`). Two of 55 stored stack-1 manifests declare 400 and both were unwinnable;
two `nextjs_ts` manifests declaring the identical 400 passed, because that pack derives. Fixed in
PR #1321; rejected the round-4 React shakeout.

### 4.3 #1323 — a builder's unrequested file is admitted, and its repair is dropped

Found on counted roll 1. The builder authored `docker/serve.py` — neither a fill slot nor
scaffold-seeded, and the plan named only `Dockerfile` and `qa_handoff.md`. It was the **only**
failing check on that task (`undefined_names`, `os` used at line 23 and imported at line 37);
the two checks on what the builder was actually asked to produce passed. The repair fixed it and
was dropped as an `unauthorized_slot_emission` with `correction_requested: False`, and the patch
— verified 3 ms earlier against a tree that still contained the file — superseded the failing
row, so the defect vanished from the run report while remaining in the delivered file.

The rule already exists (`_BUILDER_FORBIDDEN_SOURCE_SUFFIXES`, the fay-7 `start.py` class). The
gap is that `_store_failed_emission` performs no authorization while
`_collect_artifacts_and_checkpoint` does, so a builder that fails *because of* a file it was not
allowed to author takes the unguarded route. **Open, and one wiring fix.**

### 4.4 The P0 nullable false positive — an instrument fix, the round kept

P0 demanded `T | None = None` for a field declared `required: false` **with a non-null default**,
so a manifest declaring `participant_count: {type: int, default: 0}` FALSIFIED P0 against a
scaffold that was right. P0 is a carried prediction and a falsification stops the set, so on a
counted roll this would have halted the run on a rule that is simply wrong. Driver-only, so per
pre-registration §2 the round was **kept** and its record re-rendered from the stored identity —
one line, `FALSIFIED` → `held`. The original is retained as
`shakeout-*.superseded-p0-false-positive.{json,md}`.

### 4.5 #1324 — the boot audit discards the response it judged

`evaluate_expectations` has the response in hand at the moment of failure and keeps only the
formatted message. Roll 1's rejection could not be root-caused from the record: the probe was
winnable, the delivered `Run` model carries all six asserted keys, and both handlers are
`response_model=Run` returning `run`. **Open.**

### 4.6 Instrument

Beyond the above: **#1310** (the absent-suite fault stops at the emission retry and never reaches
#1269's seam) and **#1311** (L8's readout reads post-repair names the extractor has already
stripped) are why L2 and L8 entered the set unexercisable as registered; both are 1.7.3
preconditions. **#1305** (the fullstack merge discarded every `suite_defect`, making #1130/#1270
inert on the React stack) is why 1.7.1's R2 looked unfixable. New here: the driver's
`refused_patches` field captures a fixed-width slice of the log line rather than the line, so the
two refusals in Next.js roll 2 are recorded mid-word (`'tion task=…'`, `'pe=qa.test …'`) — the
one texture field that says *why* a repair was rejected, degraded. To be filed.

And a declared texture field with no producer: pre-registration §4 lists **"qa primary tokens"**,
which no roll record carries (§8). Declared and unread — the shape #1312 records — found only
because the cut tried to use it.

---

## 5. Texture

- **Packaging (reporting-only, #598):** `npm_ci_without_lockfile` on **8 of 9 rolls**, twice on
  one. At that frequency it is a standing defect in what the squad builds, not noise.
- **Gate deciders**, recorded verbatim: mixed `system:no_open_questions` and
  `agent:005159fd-…`; the §6 constant text applied identically to all nine.
- **Wall clock:** React 44–58 min (median 53); Next.js 54–109 min. The 109 is roll 2's three
  correction rounds.
- **Criteria:** 16–21 verified per React roll, 17 per Next.js roll; **every criterion verified on
  all nine except roll 1's two probes**.
- **#1312's declared signature was never hit.** Expected on the order of one roll in nine; the
  builder emitted `qa_handoff.md` on every counted roll.

---

## 6. What these sets do not claim

- **Not a rate.** 5 of 6 and 3 of 3 against 1.7.1's 3 of 5 and 0 of 2 are not detectable changes.
  §1 set no bar but L1.
- **Not that the recovery path is sound.** Five of eight predictions are unexercised (§2); L2,
  L5, L6, L7 and L8 are held only by injected diagnostics.
- **Not that the correction loop converges in general** — it converged on five rounds in nine
  rolls, two of which refused a repair first.
- **Not a general rate**: `full-38` (qwen3.8:27b) on `group_run`.
- **Not a claim about response correctness beyond the contract's `json_has` floor** (1.6.3 §2).
- **Not that the builder's emission surface is sound** — §4.3 is open, and it was found by
  reading one roll rather than by any prediction.

---

## 7. Rule for the next record

Carried from 1.7.1 §7 (read the rounds before releasing the next roll; count contentless
emissions; read every readout by its reason). Added by this set:

- **Report the shakeout loop as two numbers** — rounds taken and rounds attributable to the pack.
  One number misreads twelve instrument defects as an unstable pack.
- **A readout that cannot see its own miss is a finding.** L3's declared read reported HELD on the
  roll that falsified it; the fix was a new field, not a new prediction. Before a set opens, ask
  of each prediction: what would this readout say if the prediction were false *for the reason we
  have not thought of*?
- **Name the unexercised predictions in the headline**, not only in a table. Nine greens next to
  "five of eight unexercised" is a different claim from nine greens.

---

## 8. Disposition of items the plan routed here

- **#1273** — L4 held in the counted set (§2) and L4/L5 held on the chained diagnostic
  (`cyc_9e217c266f5f`). PR #1288 landed two of its three parts and PR #1290 landed #1260. **The
  remainder is the retry-with-fact backstop (1.7.2 plan §8a), which has no issue; it is filed
  before 1.7.4's plan is written.** #1273 closes with this trail.
- **#1285** — the reading **cannot be made from this set**, and the reason is a finding of its
  own. The pre-registration §4 declares "qa primary tokens" as texture; the driver captures no
  token field on any roll (`fill_rejections`, `fill_targets` and `self_eval_fill_merges` are the
  fill-side texture it does carry). A declared texture field with no producer is the same shape
  as a required file with no consumer (#1312): it reads as measured and is not. #1285 stays open;
  the readout is added before the next set, or the field comes out of the texture list.
