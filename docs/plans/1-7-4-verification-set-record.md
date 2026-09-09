# 1.7.4 — Verification Sets: Record

**Frozen deploy `dfe9a6f2`** (images: runtime-api `afa3d44bf0d7` · max `79f4cd50888e` · neo
`f0a8763936ab` · nat `1463d82507ca` · bob `3538b8cd506a` · eve `b366dfdc9a22` · data
`612264db115f`). Instrument at `be2e9dea`. Nine counted rolls, six FastAPI+React and three
Next.js+TS, launched 2026-09-08 21:52Z and closed 2026-09-09 06:35Z.

Pre-registration: `docs/plans/1-7-4-verification-set-preregistration.md`. Plan:
`docs/plans/1-7-4-plan.md` rev 3.

---

## 1. Headline

**Functional App Yield 7 of 9, zero human interventions.**

| arm | roll | cycle | verdict | boot | functional | corr | criteria | L1 | skips |
|---|---|---|---|---|---|---|---|---|---|
| React | 1 | `cyc_a17ee1347743` | accepted | PASS | **yes** | 0 | 18/18 | 0 of 15 | 0 |
| React | 2 | `cyc_e4e818ee8196` | rejected | FAIL | no | 0 | 15/16 | 0 of 15 | 0 |
| React | 3 | `cyc_ece3e9d2f3c8` | accepted | PASS | **yes** | 1 | 18/18 | 0 of 18 | 0 |
| React | 4 | `cyc_cdf3c674a49a` | accepted | PASS | **yes** | 0 | 20/20 | 0 of 16 | 0 |
| React | 5 | `cyc_e60b855d0e7a` | rejected | PASS | no | 3 | 16/17 | 0 of 29 | **5** |
| React | 6 | `cyc_08117e841446` | accepted | PASS | **yes** | 0 | 21/21 | 0 of 16 | 0 |
| Next.js | 1 | `cyc_a142ccb92b6a` | accepted | PASS | **yes** | 0 | 17/17 | 0 of 16 | 0 |
| Next.js | 2 | `cyc_153ef2eaace5` | accepted | PASS | **yes** | **5** | 16/16 | **7 of 35** | 0 |
| Next.js | 3 | `cyc_4f2693c9f281` | accepted | PASS | **yes** | 0 | 16/16 | 0 of 15 | 0 |

**Validity.** All nine rolls ran on the pinned deploy: zero image drift on all seven services,
config hash `3921c5a62106…` / `33cadf53688e…` per arm, squad snapshot `575707c58536…`, HEAD pinned
at `be2e9dea` throughout, and the #1438 framework-drift guard clean at every launch. No roll was
voided or reset. No merge to main occurred while the set was open.

**Every accepted roll credited all of its criteria.** No roll anywhere in the set carried an
unevidenced criterion. Both rejections named the criterion they lost.

---

## 2. The bars

### L1 (#1268) — held, as amended before the set opened

**7 contentless emissions of 160 logged**, all seven on Next.js roll 2, which **recovered fully**:
accepted, boot PASS, 16/16, functional, zero intervention, after 5 correction rounds. Eight of
nine rolls read zero.

L1 was **split before the set opened**, on the owner's ruling recorded as the pre-registration's
sixth §3a entry, after the round-2 shakeout breached it:

- **blocking** — a counted roll whose contentless emission is *not recovered*;
- **tracked, never blocking** — the occurrence count.

No counted roll was lost to a contentless emission, so the blocking half never fired. The
occurrence half is reported here and nowhere quoted as zero.

The amendment was made **before** the counted set opened, which is when semantics are settled;
making it after the readings would have been the goalpost-moving this line has refused elsewhere.

### H1 (#1312) — holds by construction

No counted roll was rejected or blocked on `qa_handoff.md`. It cannot be: #1430 removed the
document from the request, and the framework stopped requiring it in the pack. Reported as
structural rather than as a bar that survived a test it cannot fail.

**H1's live readout is empty on every roll, and that is not evidence either way.** Both driver
sources are structurally empty on a roll with no correction round: the framework's
`required_files` row is filtered out of the typed-check artifact by design (#114 keeps only
`acceptance:`-prefixed rows), and `required_files_declared` reads runtime-api lines emitted only on
the accepted-patch path. The run reports carry what the fields cannot.

**The bar was measured once, in the shakeouts, as a counterfactual.** Round 3's Next.js builder
emitted `QA_HANDOFF.md`; replaying that roll's own emission through both contracts gives
`missing=['qa_handoff.md']` under the retired contract and `passed` under the current one. That
roll would have been rejected on filename casing alone.

---

## 3. Live hypotheses

| claim | method | reading |
|---|---|---|
| **F1** (#1374) | deterministic exercise | **exercised on deploy A** (contentless-builder diagnostic, seam reached). **No live occurrence in the counted set** — `framework_rows_rederived` is empty on all nine rolls, because no accepted patch supplied a framework row's subject. Stated, not credited. |
| **B1** (#1087/#1112) | every roll | **read on all nine**: 1–11 suites read per roll, **zero** non-root fixture-table mentions anywhere. |
| **Q1** (#1285) | every Next.js roll | **answered as a trade** — see below. |

### Q1 — the fill-mode reasoning declaration, measured

The owner ruled before the set to **leave the declaration in place** so the set could read it,
rather than revert and make Q1 null by construction.

| Next.js roll | qa emissions | reading |
|---|---|---|
| 1 | 1 | `qa_test_handler 3943 / 0` — clean suite, first attempt |
| 2 | many | **7 contentless**, 5 correction rounds, 61 min — recovered |
| 3 | 1 | clean |

Against the React arm, where the same handler runs at `medium`: 5,499–15,896 completion tokens.

**The saving is real and so is the failure rate.** Fill-mode `think:false` produced a working
suite in a single emission on two of three rolls at roughly a quarter of the React arm's tokens,
and on the third it produced seven sentences of intent and cost five correction rounds. The
recovery loop absorbed it. This is the mechanism #1434 names: #1268 measured `think:false` at 1
usable emission in 6, and #924's fill measurement — which justified the declaration — measured
**token cost**, not **usability at rate**.

Q1 is read, never a gate (owner's fifth §3a ruling). The disposition of the declaration is
1.7.5's to make, on this evidence.

---

## 4. Seam invariants, and the experimental gate's amendment

**The plan's step 10 required the diagnostics to be re-run on the pinned deploy. They were not.**
The set moved from the pins straight to the counted rolls. The experimental gate of §3.5 reads
"every seam invariant's diagnostic reached its seam on the pinned deploy", and as written it is
**not met**. Recorded here as an amendment on the owner's ruling, with what is and is not covered
named rather than blurred:

| invariant | evidence | on the pinned deploy? |
|---|---|---|
| **R1** (#1372) | **live**: `2 aimed / 2 with fact / 0 blind`, Next.js roll 2 | **yes** |
| **D1** (#1054) | **live**: locus routed to dev — `development.correction_repair → frontend/src/views/RunDetailView.jsx` (roll 5) and `→ backend/routes.py` (round-3 shakeout) | **yes** |
| **A1** (#968) | the lead caught the analyzer's false `backend/models.py` claim and proceeded on the true cause | shakeout deploy `2822f06b`, **not D** |
| **W1** (#994) | CI-only by declaration (no honest fault exists) | n/a |
| **H2** (#1312) | CI invariant | n/a |
| **L2 / L4 / L7 / L8** (1.7.3) | reached on **deploy A** only | **no** |

**Why the amendment was accepted.** The two invariants the pack could plausibly have regressed —
R1, whose retry path the pack built, and D1, whose classifier it touched — both have *live*
readings on the pinned deploy. The four carried 1.7.3 invariants and A1 prove seam
*reachability*, which was demonstrated on deploy A and re-demonstrated across three shakeout pairs
on deploys C and D. Re-running five diagnostics with a two-run budget would have consumed most of
a day to re-prove reachability that was not in doubt.

**What this costs, stated plainly:** this record cannot claim L2, L4, L7, L8 or A1 were proven on
the deploy the numbers come from. A regression in those seams introduced by the pack would not
have been caught by this set.

---

## 5. Findings

Nine findings were filed across the line; six were fixed and merged before the set opened.

| # | what | disposition |
|---|---|---|
| **#1425** | three of seven loaded-check probes had **never run** — they named containers that do not exist, and the identity recorded `No such container` beside the four that answered, through a checkpoint pair read as clean | fixed (#1426): probes declare their service, unknown services refused at load, **preflight refuses to launch on a probe that could not run** |
| **#1427** | the retired `qa_handoff.md` was still demanded by the group_run PRD in seven places, so the framing role wrote it into the definition of done and the builder spent its emission on it | fixed (#1430): nine references removed across both PRDs, finishing SIP-0098 §6.7; a derived guard now fails any request fixture that names a framework-owned document |
| **#1431** | the record's "failed emissions banked" counted **artifacts**, not emissions | fixed as a label defect (#1437) after the first fix (#1432) was falsified within the hour |
| **#1436** | banked artifacts carry no attempt marker, so an emission count is **not derivable** | filed; runtime code, queued behind the set |
| **#1434** | #1268's failure mode returned on fill-mode `qa.test` — the shape #1285 declared `think:false` | filed; declaration left in place by ruling so the set could read it (see Q1) |
| **#1428** | **every** framing run reports `blocked_unverified` for three checks its tasks can never subject | filed; pre-existing, verdicts unaffected |
| **#1406** | a qa repair's patch verification passes while carrying `missing_tooling` skips, which can demote already-passed criteria | **recurred once in the set** — roll 5, 5 skips, all on passing verifications. Demoted nothing there: `vc-suite-passes` failed legitimately. Per the registered condition, **roll 5's coverage figure is never quoted as whole.** Framework half remains in 1.7.5 |
| — | the driver **imports `squadops` modules** to judge P0 and B1, so a framework change landing after the deploy would judge a roll against code the system never ran | fixed (#1438): a counting roll refuses to launch on `src/`/`adapters/` drift from the frozen commit; `frozen_deploy_commit` was typed and read by nothing before this |
| — | re-rendering a record with `collect()` alone produces a **hollow** record: `loop_texture` is assembled separately and is derived from container logs, so **a rebuild destroys it permanently** | eight hollow re-renders produced and deleted; records are write-once evidence |

---

## 6. What the loop did when it ran

**The qa repair path: three recoveries and one honest refusal**, plus the counted set's own.

| cycle | rounds | verification | outcome |
|---|---|---|---|
| `cyc_69d34bc41c20` | 1 | 12 checks, 0 skips | retest SUCCEEDED |
| `cyc_c45d60c9eb16` | 1 | 8 checks, 0 skips | SUCCEEDED *after two contentless emissions* |
| `cyc_ece3e9d2f3c8` (roll 3) | 1 | 14 checks, 0 skips | SUCCEEDED |
| `cyc_153ef2eaace5` (Next.js roll 2) | 5 | — | **recovered from 7 contentless emissions** |
| `cyc_057c598c10de` | 2 | 16 checks, 0 skips | **FAILED → `plan_defect`**, refused `tighten_acceptance` |
| `cyc_e60b855d0e7a` (roll 5) | 3 | 8 checks | **FAILED → "Max correction attempts (3) exhausted"** |

`agent_executed == agent_rows` on every verification: nothing was credited unexecuted.

**The two rejections failed differently, which is worth more than if they had matched.** Roll 2
was caught only by the **post-hoc** boot audit — `by_check` carries no `vc-probe-*` entries on any
roll, so probe criteria are executed by the probe runner at the audit and there is no correction
opportunity by construction. Roll 5 exhausted three repairs on a suite it could not fix **while
its app worked** (boot PASS, all probes answered) and terminated honestly rather than crediting
itself.

**Roll 5 is the set's one divergence between boot-PASS and verdict-rejected.** Functional App
Yield requires verdict *and* audit, so a demonstrably working application scored non-functional
because its tests never passed. The definition is not being questioned here; the divergence is
recorded because this is the first line to produce one.

---

## 7. Step 13 — the live readings, read live and not by a roll

| item | reading |
|---|---|
| **#330** | Prefect loop overruns **0 in every counted roll's window**, all nine |
| **#372** | deploy D: `realm 'squadops-dev' synced — added 0, skipped 11, overwritten 0` (and the same for `squadops-local`). Deploy B added 2 and skipped 9. **The sync converged and is idempotent** — the two additions were a one-time reconciliation |
| **#300** | `MIGRATIONS_ADVISORY_LOCK_KEY = 8318552514319182183 > 0`, loaded in-container. **Zero** migration lines in 18,847 runtime-api log lines and zero in the deploy log: the constant is live and **the acquisition path is unexercised on this deploy**. Not claimed as verified |

---

## 8. What this set does not claim

- It does not claim the seams L2, L4, L7, L8 or A1 were proven on the deploy the numbers come
  from — see §4.
- It does not claim F1 occurred live; it was exercised deterministically on a pre-pack deploy.
- It does not claim roll 5's coverage figure is whole: #1406's skips were present on that roll.
- It does not claim #300's lock acquisition works, only that the key is loaded.
- It does not claim the fill-mode reasoning declaration is right or wrong. It measures its cost
  and its saving and hands both to 1.7.5.
- Nine rolls on one PRD and two stacks is not a statement about arbitrary products.

---

## 9. Rule for the next record

**A readout that cannot distinguish "did not happen" from "could not be asked" is not evidence.**
Three of this line's findings are the same defect wearing different clothes: a probe that could
not run recorded like one that answered (#1425); a field labelled in units it did not count
(#1431); an empty H1 readout that meant "structurally unpopulated", not "nothing found". Before a
field is registered in a pre-registration, state what it reads when the thing it measures is
**unaskable**, not merely absent.
