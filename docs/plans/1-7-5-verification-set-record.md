# 1.7.5 — Verification Sets: Record

Read against `docs/plans/1-7-5-verification-set-preregistration.md`, in force from roll 1 by
its commit on `docs/1-7-5-preregistration` and merged as `38ebe30b` before the first counted
launch. Every number here comes from a roll's own record in
`var/verification_sets/1-7-5-<arm>/roll-NN-*.json`, written at completion; `loop_texture` is
derived from container logs over each cycle's window and cannot be regenerated.

---

## 1. Headline

**Nine counted rolls on one frozen deploy. Seven accepted, two rejected, functional 7/9.
159/161 criteria. Boot audit PASS 9/9, P0 held 9/9, zero framing re-rolls. The bar held.**

| arm / roll | cycle | verdict | criteria | failed | rounds | contentless / emissions | min |
|---|---|---|---|---|---|---|---|
| React 01 | `cyc_f1f25d100436` | **accepted** | 18/18 | — | 0 | 0/16 | 46 |
| React 02 | `cyc_5a6e5ed0caeb` | **accepted** | 21/21 | — | 0 | 0/17 | 52 |
| React 03 | `cyc_89153929749f` | **rejected** | 20/21 | `tests_pass` | 3 | 0/31 | 103 |
| React 04 | `cyc_25b77dad0ef1` | **accepted** | 18/18 | — | 0 | 0/17 | 56 |
| React 05 | `cyc_0eab68279d8e` | **accepted** | 22/22 | — | 0 | 0/16 | 48 |
| React 06 | `cyc_18aa25b4a57e` | **rejected** | 13/14 | `tests_pass` | 2 | 0/22 | 59 |
| Next.js 01 | `cyc_8d383802f3a1` | **accepted** | 16/16 | — | 0 | 0/14 | 44 |
| Next.js 02 | `cyc_551eaf49884a` | **accepted** | 16/16 | — | 0 | 0/15 | 56 |
| Next.js 03 | `cyc_6156e09ad6da` | **accepted** | 15/15 | — | 0 | 0/19 | 52 |

8h41m of counted wall clock. Both rejections are the same failure, described in §5.

**The pins held identically on all nine rolls** — one squad snapshot (`575707c58536cf3b`), one
HEAD (`1e6ac721`), **one image set**, and each arm's own `resolved_config_hash` asserted at
every launch (`3921c5a62106` React, `33cadf53688e` Next.js). Nothing merged to main between
roll 1 and the last counted roll.

---

## 2. The bar

### L1 (#1268) — held

*A counted roll whose contentless emission is not recovered breaches it.*

**Zero contentless emissions of 167 logged, across all nine rolls** — including both
rejections, which logged 31 and 22 emissions respectively. The occurrence count is reported
here rather than quoted as a zero, per the bar's own wording: the field was asked on every
roll and answered `asked_none` on every roll.

**In context across the 1.7 line**, so the zero is read against its own history rather than
as a novelty: 1.7.2 zero, 1.7.3 zero of 163, **1.7.4 seven of 160** — all seven on one Next.js
roll, which recovered fully — and 1.7.5 zero of 167. The bar has held on every set that
declared it; 1.7.4 is the only one where it was tested by an actual occurrence.

---

## 3. The live hypothesis

### The fill declaration (#1434) — not falsified, with its ceiling named

*Zero contentless fill-mode first attempts across the counted set; read on every Next.js roll;
falsified by one.*

**Zero on all three rolls.** Every fill did real work rather than passing through:

| roll | contentless | `qa_test` completion | reasoning chars | slots filled | not-applicable | store touched |
|---|---|---|---|---|---|---|
| 1 | 0 of 14 | 8,525 | 16,141 | 7 | 0 | yes |
| 2 | 0 of 15 | **12,288 — at the completion cap** | 29,233 | 8 | 0 | yes |
| 3 | 0 of 19 | 5,512 | 7,634 | 7 | 0 | yes |

No fill-layer rejections in any stored suite.

**The caveat is load-bearing and is not a hedge.** Roll 2's qa author spent its *entire* output
budget — 12,288 is exactly the `completion_cap` that appears in the emission-retry lines — on
top of 29,233 characters of reasoning, and still produced a working suite. The claim is
therefore: **zero contentless in three rolls, one of which sat on the ceiling.** What holds is
that `LOW` was sufficient on this workload, this provider, this model and this deploy. It is
**not** evidence that there is headroom, and a provider or model change re-opens the reading.

---

## 4. The seam invariants — four of five reached, and the gate amended

Five diagnostics ran on the pinned deploy before roll 1. **Six of seven fault-seams reached;
four of five diagnostics.**

| diagnostic | seam(s) | reached | the evidence |
|---|---|---|---|
| `absent-suite` | L2 | **YES** | `patch_retest … reason=Repaired suite still fails`, after `correction_repair_locus: own_artifact` and `patch_verification … status=passed checks=12` |
| `own-frame-then-prose-repair` | L7 | **YES** | `qa_owned_routed: …runViews.test.jsx raised TypeError in its own frame (renders run rows …:44); qa.test re-authors …` |
| | L4 | **YES** | `correction attempt 1 refunded: the repair emitted no content (cap_exhausted) … (refund 1 of 3)`; the emission behind it is 0 chars on 12,288 completion tokens and 46,137 reasoning chars |
| `path-prefix` | L8b | **YES** | `placeholder_strips: [{emitted: "path/backend/tests/test_runs.py", stripped_to: "backend/tests/test_runs.py"}]` with `stored_under_placeholder` empty |
| `contentless-builder` | F1/R1 | **NO** | R1 reached, F1 not — see below |
| `absent-suite-then-false-claim` | A1 | **YES** | the fault APPLIED (`chars 1475 → 1828`) and visible in the analyzer's emission head; both decisions carry neither its marker nor its substance, and one names the refutation outright |
| | L2 | **YES** | two retests, both `status=SUCCEEDED passed=True reason=Repaired suite passed` |

Each of the four that reached also *recovered*: accepted, boot audit PASS, 18/18, 17/17, 18/18
and 21/21 with zero failed checks — on runs whose red was manufactured.

**`contentless-builder` did not reach its seam, the gate was therefore not met as written, and
the owner ruled the line closes anyway.** The mechanism, the timeline that explains it, what
the line consequently does not cover, and the remedy owed are in **plan §3.9a** — recorded
there and not only here, because this record is superseded at the next cut and that gate's own
text says "no amendment."

Two things this record states plainly rather than leaving to that section:

1. **F1 (#1374) is unexercised on any deploy carrying #1372**, including by the nine counted
   rolls. The same retry stands between a contentless builder attempt and correction there too.
2. **The budget stands at one run, not two.** The second was started (`cyc_af33eeb931a0`,
   10:00:37Z) and cancelled through the CLI about nine minutes in so the counted set could
   start. No record exists for it. A budget reported as spent when it was not is the same class
   of error as a stop rule quietly dropped.

**The instruments were proven before the set.** All five diagnostics' `loaded_checks` ran
against the deploy-B containers before roll 1 — 0 of 12 blocks raised, every control pair
answering both ways rather than one. All six declared faults have a `SEAM_READOUTS` entry, so
none was unreadable by construction (#1300).

---

## 5. Findings

### F-1 — a repair loop burns its budget when the failing set churns around a stable core (#1501)

**Both rejections are this, and they behave oppositely, which is what localises it.**

**React roll 6** — backend pytest suite. Same two tests failed both rounds, exact signature
match, `plan_defect` termination at round 1 with a named reason after one wasted round:

```
correction_terminated_plan_defect task=task-run_943d57cc-m005-qa.test rounds=0..1
  candidate=tighten_acceptance
  signature=tests_pass|tests/test_runs.py|failed;…;test=test_leave_run_removes_participant;
            tests_pass|tests/test_runs.py|failed;…;test=test_leave_run_unknown_name_rejected
```

**React roll 3** — frontend vitest suite. Three rounds, six patches, 103 minutes, ending
`Max correction attempts (3) exhausted` with **no** named reason.

`failure_signature()` emits one element per failing test and
`CorrectionRunner._check_progress_termination` terminates only on an **exact adjacent repeat**.
Roll 3's failing set was 6, 4, 5, 6 across four qa attempts — never an exact repeat — while
**three titles failed in every single attempt**: `displays a server error when the API rejects
the create request`, `displays the duplicate-name error when join is rejected`, `navigates to
the runs list after a successful create`. A stable three-element core, invisible to an equality
test because two or three elements oscillated around it.

The oscillation is the dev repair's blast radius, not qa churn: the repair re-emitted the same
three view files every round (`CreateRunView.jsx`, `RunDetailView.jsx`, `RunsListView.jsx`), and
a wide edit fixes some assertions while breaking others.

Filed with both rolls and the contrast. Proposed fix: compare the intersection beside the exact
match. Roll 3 would have ended at round 1 naming three specific assertions.

**Not the extraction.** The signature rule predates #1152, and `correction_runner`,
`correction_repair` and `patch_acceptance` each behaved as written.

### F-2 — the baseline stylesheet has no rules for `dl`/`dt`/`dd` (#1499)

Found by building and photographing a delivered app. Measured across every stored view emission
in the vault (3,022 `.jsx`/`.tsx` files): **92 files across 81 distinct cycles use `<dl>`, against
13 using `<table>` — which is styled.** The squad reaches for a definition list seven times more
often than a table. Framework source, so it needs a rebuild and moves a committed golden.

### F-3 — the deploy-B refusal, and the guard that should have caught it

Recorded in the pre-registration §2. Both arms died in two seconds on their first `cycles
create` with HTTP 500, `RuntimeError: ProjectRegistryPort not configured`: #301's comms factory
imported `A2AServerAdapter` at module scope and only `agent.lock` ships the `a2a` SDK.
`_init_cycle_subsystem`'s `except Exception` turned it into one log line and the container
passed its health check. Three things landed — #1494 (local import), #1495 (the swallowing
`except` gone; a runtime-api that cannot bind its cycle ports refuses to start), and #637's
guard extended to import what each root *composes at startup*, verified red pre-fix and green
post-fix against a venv built from `api.lock`.

**It spent no shakeout round** — a round is spent when a pair completes and is read.

### F-4 — two defects in this line's own instruments

1. **The pin-freezing scripts agreed with themselves.** Both refuse unless the two arms' records
   agree on one deploy. Dry-run before the closing pair landed, they **passed** — because
   neither arm had a deploy-B record yet, so both were reading deploy A's and agreed perfectly.
   They would have pinned the set to images that no longer existed. Both now read `docker
   inspect` for all seven containers and refuse on any difference. Agreement between two arms is
   not agreement with the running deploy.
2. **The generations reading needed a control, not a ratio.** §3e registered the caution
   itself — `gens_per_task` read exactly 1.00 on every cycle before #929 and was wrong every
   time. See §6.

---

## 6. Readings taken live, not by a roll

### The #1206 generations reading — EQUAL

**React 20 generation records against 20 LLM calls; Next.js 18 against 18**, on the shakeout
pair that closed the loop, where the 2026-08-31 pair read 26 against 35.

The ratio alone would not have settled it. The reading joins on a value the two sides produce
independently — the completion-token count, which LangFuse receives over HTTP from the adapter's
usage block while `log_emission_shape` writes it into the agent container's own log from a
different module. **Every count matched on both sides in both arms; none was named by only
one.** The LangFuse side is scoped by `metadata.cycle_id` rather than by a clock window.

### The shakeout loop — exited at round 1

Deploy A took four rounds; **deploy B took one**. Both arms of the closing pair accepted,
functional, P0 held, zero failed/adverse/unverified/unevidenced — React 18/18 in 51 min,
Next.js 16/16 in 56 min. **Rounds attributable to the closures: zero** (F-3 spent none).

The React arm of that pair is what carries evidence about the extraction: it took a correction
round deploy A's last React shakeout never did, so 22 `loop_texture` fields that read UNASKABLE
there were asked, and the arm's unaskable count fell 31 → 6. `PatchAcceptance._retest_patched_suite`
reached with `passed=True reason=Repaired suite passed`; `evidence_superseded` emitted by
`adapters.cycles.patch_acceptance` itself — the moved block naming itself in the deployed logs,
which no unit suite can demonstrate.

---

## 7. What this set does not claim

* **F1 (#1374) is unexercised** — see §4 and plan §3.9a. The remedy is a re-registration.
* **`contentless-builder`'s budget was one run, not two.**
* **`LOW` has no demonstrated headroom** — one of three Next.js rolls sat on the completion cap.
* **Nothing about other providers or models.** One provider, one model, one workload, one deploy.
* **The two rejections are not evidence that the squad cannot deliver these stacks** — both
  delivered apps installed, built, booted and answered their contract probes (boot audit PASS
  9/9). What failed was each roll's own test suite, and in one case the loop's ability to say so
  in fewer than three rounds.
* **The 7/9 verdict rate is not a measure of the closures.** 1.7.4 also read 7 of 9 accepted,
  on the same PRD, squad and request profile — so the rate moved not at all, which is what a
  release of three structural closures should do to it. The one comparison that did move is the
  boot audit: **1.7.4 read 8/9 PASS, 1.7.5 reads 9/9.** One roll's delivered app is a small
  sample and this record does not claim the closures caused it.

---

## 8. Drift between the measured deploy and the tag

**Framework drift: zero.** `git diff 8fd30eb8..<tag> -- src/ adapters/` is **empty** — the
tagged framework is byte-identical to the images the set ran on.

Fifteen files differ, every one additive and outside the framework:

| area | files | what |
|---|---|---|
| `docs/plans/` | 8 | this record, the pre-registration, the seven set/diagnostic configs |
| `scripts/` | 4 | the two capture commands, the release-package guard's rule 3, `--showcase` |
| `tests/` | 1 | rule 3's tests |
| `examples/` | 1 | the screenshot seed |
| `CLAUDE.md` | 1 | cut step 7 rewritten |

None is reachable from a cycle. The driver's own framework-drift check enforced the `src/` and
`adapters/` clause on every one of the nine counting launches.

---

## 9. Rule for the next record

**Check a diagnostic's "not reached" against its own previous line before calling it a
regression** — and check whether the deploy those earlier diagnostics ran on carried the fixes
of its own tag. `contentless-builder` read YES on 1.7.4 only because that deploy predated
#1372 by eight hours and was never re-run on the pinned one. A readout written against a
framework can outlive it, and a fix that makes the loop recover *earlier* can make a seam
registered downstream of the old recovery point unreachable — reporting NO for a system that
got better.
