# 1.8.1 verification set — pre-registration (plan §7 step 5)

**Record corrections, 2026-09-22 (not a revision — no fixed parameter, prediction or rule moves):**
§1's image-id row had listed eleven ids (rev 1/2's four beside rev 3's seven) and the deploy-commit
row still said the ids were "unchanged", a sentence left from rev 2 — both corrected to what rev 3
recorded one row down. §10 is appended, which the section header always required and no earlier
revision did. **One ruling recorded (owner, 2026-09-22):** §3c's *definition* of a successful
transaction governs the count, and §3d's "N cell" column is the supply forecast, not a restriction
— a transaction produced by a diagnostic whose column says "none" counts in the cell its repairing
role and stack place it in. Ruled before the Next.js counted rolls were observed; it changes the
qa × React reading (§10e) and nothing about qa × Next.js.

**Status:** rev 5 (2026-09-22) — **the counted arms' config-hash pins corrected.** The nine
diagnostics all cleared under rev 4; counted roll 1 then **refused**, correctly: the set pinned
`3921c5a62106`, carried verbatim from the 1.8.0 config, and the deploy resolves `58eed2c52e1f`.

**Cause, and it is a registration defect not a deploy one.** The 1.8.1 counted configs were built
from 1.8.0's. The deploy commit, the seven image ids and the squad snapshot were updated;
`expected_config_hash_prefix` was not. The hash legitimately moved because **#1614 — a 1.8.1
prelude change — added `correction_steps` to every request profile**, which is part of the
resolved config. Both arms carried a stale value: React `3921c5a62106`, Next.js `33cadf53688e`.

**Corrected to what this deploy resolves:** React **`58eed2c52e1f`**, Next.js **`fff4a6435c97`**,
each observed by attempting a roll and reading the refusal, each verified stable.

**No roll was counted.** The guard fires after the cycle resolves its config — preflight cannot
know the hash — so each attempt launched a cycle that was then refused and cancelled through the
CLI; `cycle_runs` shows zero `running`. Nothing entered N.

**The diagnostics stand, by the owner's ruling of 2026-09-22 ("correct the pin and go").** They
assert no pins — every diagnostic config carries `expected_squad_snapshot_prefix: ""` — and no
seam reading depends on the resolved config hash. This is narrower than rev 4's withdrawn
narrowing and differs in kind: a deploy-IDENTITY assertion corrected to match the deploy, not an
outcome threshold revisited after seeing outcomes. It is recorded here so the distinction is
arguable rather than assumed.

*Rev 4's status block, kept for the record:* re-made after the shakeout's third finding (#1631), whose
fix changes a registered reading. **§8 voids rev 3 on that alone**: a driver-only change is free
only where it *cannot* alter a reading, and this one exists to make A1 readable at all. **The
deploy does NOT move** — instrument only, `scripts/dev/` — and the images and pin were re-read
unchanged, exactly the rev 2 precedent (void without rebuild). Voiding and rebuilding are separate
questions and §8 asks only the first.

**The strict rule applies: rev 4 re-runs all nine.** An earlier draft of this block narrowed the
void — six rev-3 clearances carried, only diagnostics 7–9 re-run — on the ground that adding a
marker to the runtime filter cannot alter L7, L4, the dev-lane seam, L2 or L8b. **That narrowing
is withdrawn.** Two reasons, the second decisive:

1. **It was proposed after seeing six favourable results.** Scoped invalidation may be a defensible
   policy, but inventing it once the results are known is the bias the registration exists to
   prevent. §6 requires "a diagnostic pass on one deploy with no new seam finding"; §8 makes a
   reading-changing driver edit the move that voids the registration. Neither admits a carry.
2. **It was incoherent.** The four required N cells are supplied by those same six diagnostics'
   transactions, and the superseded-registration rule says those do not carry. The draft therefore
   either smuggled rev-3 transactions into N or left rev 4 without the supply its own §3c says the
   cells depend on. It cannot be both.

**So: all nine diagnostics re-run under rev 4, and no rev-3 transaction counts toward N.** If
scoped invalidation is wanted as a rule, it is written *before* the next set and applies to
whatever that set finds — not decided here with six clears already in hand.

**The budget clock (Dallas U1), fixed here because the text did not address it.** Diagnostic 7
exhausted its two runs under rev 3. **A void registration voids its budget accounting with it**:
diagnostic 7 begins rev 4 with a fresh two-run budget. The alternative — carrying an exhausted
budget across a registration that has been re-made precisely because the reading was broken —
would make the set unstartable for a defect the framework has already fixed.

*Rev 3's status block, kept for the record:* re-made after the second finding (#1626). Rev 2 is
void by §8, and this time **the deploy genuinely moves**: #1627 and #1628 change `src/`
(`agents/entrypoint.py`, `cycles/structural_jsx.py`), so all seven images were rebuilt and every id
changed. Contrast rev 2, which moved the instrument only and correctly did NOT rebuild.

*Rev 2's note, kept for the record:* re-made after the first finding (#1623, fixed by #1624); the
deploy did not move. #1624 touched only the driver, the tests and
this document — **zero drift under `src/` and `adapters/`** between rev 1's `18798083` and rev 2's
`f6994271` — so the seven images that serve the framework are byte-identical and are NOT rebuilt.
Rebuilding would mint new ids for identical source and make the record less comparable, not more.
The instrument moved; the deploy did not. Committed on the frozen deploy before any diagnostic
launches. Once merged, the cut criteria do not move; only diagnostic
readings are appended (§10). If the deploy moves after this commit, the commit is void and re-made,
and no transaction from the superseded deploy counts toward N.

**What this set measures.** One thing: **whether SIP-0107's flip precondition is met on a fresh
count.** 1.8.0 read **N = 5 of 6 with qa × Next.js empty** (1.8.0 pre-registration §10c.4) — the
cell's diagnostic supply was named in its §3c and never registered. §39.8 is explicit that fewer
than N means step 7 does not happen, and that N is fixed before any transaction that could count
toward it is observed. **F's five transactions therefore do not carry.** 1.8.1 re-supplies N under
this pre-registration, on this deploy, with the ninth diagnostic registered first. The bar is L1.

If N is met, the flip lands on deploy B as its own PR. **If N is unmet, 1.8.1 ships without the
flip and says so** — SIP-0107 stays `accepted` with step 7 named open, the shortfall recorded as
§39.8's own words describe it, and no owner discretion after the measurement (plan §8 decision 2).

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| Counted rolls | **4** on FastAPI+React (§4) and **2** on Next.js+TS (§5) — reduced from 1.8.0's 6+3 because the diagnostics carry the supply this line needs and the counted rolls are margin (plan §4.1) |
| Bar | **one: L1** (#1268) — blocking on a counted roll whose contentless emission is *not recovered*; the count tracked and never quoted as zero |
| **N** (SIP-0107 §39.8) | **6 successful scoped revision transactions across the counted rolls and the diagnostics together, with at least one in each required cell** — qa × React, qa × Next.js, dev × React, dev × Next.js (§3c). **Re-fixed here**, before any transaction that could count is observed. 1.8.0's five do not carry |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 → 1.8.0 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React **`58eed2c52e1f`**, Next.js+TS **`fff4a6435c97`** — read from this deploy at rev 5, NOT carried from 1.8.0 (`3921c5a62106` / `33cadf53688e`), which #1614's `correction_steps` addition invalidated — 1.8.0 read `3921c5a62106` and `33cadf53688e`; a change is drift the record declares (§9) |
| `squad_profile_snapshot_ref` | **`2d8d4feb3519a7ec`** — **not precomputable.** `serves_roles` entered the snapshot payload (#1611) and the flat completion cap moved a value (#1620/#1619), and the PUT that lands the cap bumps `version`, which is itself inside `compute_profile_snapshot_hash`'s payload. The pre-1.8.1 pin was `575707c58536cf3b`; the file at version 1 computes `cbf3a18d…`; **the deploy stamps neither.** The driver refuses a counting roll on any other (#1571) |
| Deploy — commit | **`70f578fe`** — rev 2's `f6994271` plus #1628 (the parse guard) and #1627 (the redelivery bound), both under `src/`. **A label, not an assertion** (#1296): the image ids are the assertion, and **all seven changed** at the rev 3 rebuild because those two fixes are under `src/`. (Rev 2's `f6994271` had NOT rebuilt: `git diff 18798083..f6994271 -- src/ adapters/` was empty.) |
| Deploy — image ids | `runtime-api 3ccd7f7b931e`, `max 84708fd3ceb6`, `neo 1e74a0b5334d`, `nat bd81e2c6fb2c`, `bob 4abda1d62302`, `eve 55a19a45982b`, `data 1af2fef0345a` — **all seven changed** at the rev 3 rebuild (rev 1/2's were `0d33b2820245`, `4fbb4efad454`, `c379594cb4fd`, `d7c038b44c32`, `c2c1a64c7063`, `4dfeb0dcdb62`, `9e1c65ee4d06`). **The pin is unchanged at `2d8d4feb3519a7ec`** — re-read from the deploy, not assumed: the squad profile was not touched (deploy F's, superseded, were `runtime-api b3278c26dd25`, `max 36cc6eb9a923`, `neo 07498c2a4a94`, `nat 1ddf151647c0`, `bob b59711b8f653`, `eve 14d15dc8e3f7`, `data 9a41965b25ad`) |
| Loaded, not built | Verified per container as a live call with its paired control (`verify_A_loaded`): the twelve prelude surfaces of §3d′, read from the loaded modules of `runtime-api`, `eve`, `neo` and `bob` — never by grepping a file (#522) |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-8-1-<arm>.yaml --roll N`; diagnostics via `shakeout --set …-diagnostic-*.yaml` |
| Order | **The nine diagnostics first** (two-run budget each) — they ARE deploy A's shakeout, no separate pair precedes them — then FastAPI+React rolls 1–4, then Next.js+TS rolls 1–2 |

---

## 2. Preconditions — the prelude, and why there is no separate shakeout pair

Deploy A carries the whole 1.8.1 prelude: **twelve merges on top of the plan** (`f011bd73`), every
one with main's full CI read green before the next.

| # | merge | what it changed |
|---|---|---|
| 1 | `17225055` (#1603) | a qa task's free-authored suite failing beside its fill slots is a repair target **with** the shells (#1602) |
| 2 | `d542519e` (#1608) | a root-level `__tests__/` is excluded from the qa source set (#1539) |
| 3 | `93ed2602` (#1612) | the inert series history is read as of the perspective cycle, not as of now (#1526) |
| 4 | `82861663` (#1613) | `GET /api/v1/projects/{id}/cycles/{id}/assessment` + `squadops cycles assess` |
| 5 | `bbd70b3c` (#1609) | the seeded conftest owns store isolation via an autouse `reset()` (#1598) |
| 6 | `90a23765` (#1611) | the role → agent map is **declared** and the silent `resolve_agent_config` fallback **deleted**; migration 1510 backfills persisted JSONB; `serves_roles` enters the snapshot payload (#1610 closed here) |
| 7 | `8256365a` (#1614) | the correction protocol's steps are declared by the request profile; `CORRECTION_TASK_STEPS` removed; no decide ⇒ deterministic `patch` |
| 8 | `fe48d5ee` (#1615) | a process serves the roles its roster entry declares |
| 9 | `331a95da` (#1617) | the 1.8.1 diagnostics registered — **including the ninth, the supply 1.8.0 never had** |
| 10 | `5494ea29` (#1618) | the per-roll record renders the cycle assessment |
| 11 | `a57a83d2` (#1616) | A1 reads the refutation **mechanism**, not a literal token; a refutation joins only the decision it was told (#1600) |
| 12 | `18798083` (#1620) | the arm axis — substrate held equal, solo absences proved; #1619 resolution 1 applied in-tree |

**The nine diagnostics ARE deploy A's shakeout.** No checkpoint pair precedes them (plan §7 step 5).
Each runs the roll's own path with the fault injected in the producing role's container (#1251) —
never a call into the seam with its input in hand, which is a replay of the function and is named
as one. **A seam not reached after two runs stops the set**; the plan is then revised in the open.

**A known gap this deploy closes, recorded because it was nearly missed.** `full-38` is served from
Postgres and was seeded 2026-09-15; the seeder skips an already-seeded profile forever, so #1620's
flat completion cap in `config/squad-profiles.yaml` reaches nothing on its own. Deploy A therefore
applies it through `PUT /api/v1/squad-profiles/full-38` and **reads the resulting pin back from the
deploy** (§1). Skipped, the arm preflight would refuse and the counted set's pin would not match
what the deploy serves — loud, but at launch rather than before it. **#1619 closes at that PUT**,
not at #1620's merge.

---

## 3. The exercise plan — stated before the first diagnostic

### 3a. The bar

| id | claim | blocking on | typed field |
|---|---|---|---|
| **L1** (#1268) | the loop remains able to produce a valid running result — a counted roll whose contentless emission is **not recovered** breaches it | every counted roll | `loop_texture.contentless_emissions`, the count beside the recovered flag |

### 3b. The live predictions

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **All-attempt integrity** (§39.8, first reading) — across every attempted transaction, counted rolls and diagnostics together, successful or refused: zero outside-grant changes, post-verification drops, verified/persisted identity mismatches, preservation violations (by reconstruction), partial acceptances, over-ceiling regrants, and zero restorations on a successful scoped transaction; **unauthorized whole-file responses a reported count per cell, not a violation** (§46a), offered and unoffered alike (§46p) | the per-repair `repair_revision_form` and `anchored_edit_transaction` lines in the repairing role's container; `patch_candidate_identity` at acceptance; the driver's `loop_texture.repair_revision_forms` and `candidate_identities` | one of the defect classes on any transaction | that the contract holds where it was exercised — this deploy, these stacks, these lanes — and nothing about repairs no roll or diagnostic produced |
| **Success-path readiness** (§39.8, second reading) — at least **N = 6** successful scoped transactions, at least one per required cell (§3c) | the sum of §3c's counting rules over counted rolls and diagnostics | fewer than 6, **or any required cell at zero** | that a scoped repair can be produced on demand in every lane the flip will govern |
| **The rendered packaging** (#598) | the check's rows per roll; the builder's emission log | one finding on an accepted emission, or a builder-authored Dockerfile | that the rendering is what the boot audit builds |

**An unmet N blocks the flip and is recorded as a shortfall, not retried into existence.** A
falsified prediction or an unreached seam stops the set and the plan is revised in the open, never
amended after.

### 3c. N — the definition, the cells, the supply, and three counting rules

**A successful transaction** (§39.8): resolved inside its grant, composed, passed its preservation
proof (§17), **verified, and persisted under the identity it was verified with** (§20). A
transaction refused, failed closed, or whose repair failed patch verification or the retest adds
nothing.

**Why N is re-fixed rather than continued.** 1.8.0 read 5 of 6 with **qa × Next.js empty**, and
§39.8 fixes N before any transaction that could count toward it is observed. Continuing a count
across a superseded deploy would let the shortfall be retried into existence. F's five do not
carry; a rerun on **this** deploy counts, a superseded deploy's never does.

**Required cells and their supply.** The counted rolls supply little by design — seven of nine
1.7.5 counted rolls took zero correction rounds — so the diagnostics carry the requirement and the
four counted React rolls plus two Next.js rolls are margin.

| cell | forcing fault (diagnostic) | what the repair revises | expected successful transactions | counted-roll expectation |
|---|---|---|---|---|
| **dev × React** | `dev_join_response_omits_declared_fields` (`dev-lane-fastapi-react`) | the join handler in `backend/routes.py` — a structural `function:` entity or an anchored edit | 1–2 (two-run budget) | ~1 across four rolls |
| **dev × Next.js** | `dev_join_response_omits_declared_fields` (`dev-lane-nextjs`) | the join handler in `app/api/runs/[run_id]/join/route.ts` — `function:POST#try` or an anchored edit | 1–2 | ~0 across two rolls (no dev round in six Next.js shakeouts across the line) |
| **qa × React** | `qa_suite_own_frame_failure` + `repair_prose_only` (`own-frame-then-prose-repair`) | the qa suite the fault broke — an anchored edit on the existing file | 1–2 (the second repair, after the prose one is refunded) | ~1 across four rolls |
| **qa × Next.js** | **`own-frame-then-prose-repair-nextjs` — the ninth diagnostic, in fill mode (#1617)** | the scaffold shells by **fill** (§9.3 region) and, since #1584, the free-authored suite by anchored edit — #1603 makes both targets together | 1–2 | ~1 across two rolls |
| builder × React | `builder_emission_contentless_all_attempts` (F1) | `assembly_notes.md` by `builder.assemble_repair` — Markdown, anchored edits only | 0–1 — **declared, not required** | none (the builder emits only notes, #598) |
| builder × Next.js | — | — | **unaskable**: no forcing fault is registered on this stack's builder, and #598 leaves it nothing to revise but `assembly_notes.md` | none |

**This is the cell 1.8.0 could not fill.** Its §3c named "the same diagnostic in fill mode" as
qa × Next.js's supply and never registered it; the one Next.js roll with a qa fill repair lost its
retest to #1602. Both halves are closed on this deploy — the diagnostic exists (#1617) and the
retest reaches it (#1603).

Expected total **5–10 against N = 6**. A required cell at zero fails the reading regardless of the
total, which is the coverage §39.8 demands.

**Three counting rules, fixed here** (carried verbatim from the 1.8.0 pre-registration §3c, because
changing a counting rule between sets is how a shortfall becomes a rounding decision).

1. **A qa repair in fill mode counts as a §9.3 region transaction** when the merged shells are
   accepted and persisted under the identity they were verified with. It does not run through
   `RevisionTransaction`, so its integrity evidence is the fill-merge record (`fill_merge_evidence`:
   `dropped_shell_rewrites` zero, `misaddressed` zero, `additive_containment` held) in place of the
   transaction record. **Without this rule the qa × Next.js cell cannot be met by construction**:
   every scaffold-bound qa repair fills. Fill transactions are reported in their own column.
2. **A successful transaction that replaced more than half of its file's characters is a scoped
   rewrite and does not count toward N.** Reported per cell in its own column. The threshold is the
   `replaced.pct` the revision form carries (§46o); a whole-file response is 100 by definition.
3. **Every transaction is read against the round that produced it**, not in isolation: the
   `repair_revision_form` line names the form offered, the form taken, the modes, the replaced span
   per file and the fragment-anchor count; the per-cell table carries every one of those columns, so
   the sum against N and the texture behind it come from the same rows.

### 3d. The seam invariants — nine diagnostics, two-run budget each

| diagnostic | fault(s) | invariant | readout | N cell |
|---|---|---|---|---|
| `absent-suite` | `qa_suite_absent` | **L2** (#1269) — a repair supplying the suite an emission failure lacked is retested; #1406's untouched-file rule rides it | "repair-retest seam reached" | none — the suite is new, not revised |
| `own-frame-then-prose-repair` | `qa_suite_own_frame_failure`, `repair_prose_only` | **L7** (#1270) routes to `qa.test_repair`; **L4** (#1273) a prose-only repair is refunded, not verified; **L5** the re-take is briefed | the locus line, the refund line, the second repair's revision form | **qa × React** |
| **`own-frame-then-prose-repair-nextjs`** | the same, **fill mode** | the same three, on the App Router stack where the qa repair fills scaffold shells; **#1603's target set** — the free suite and the shells together | as above, plus `fill_merge_evidence` | **qa × Next.js** |
| `path-prefix` | `qa_suite_at_path_prefix` | **L8b** (#1311) — no emission lands under a literal `path/` prefix | the extractor's strip count and the stored names | none |
| `absent-suite-then-false-claim` | `qa_suite_absent`, `analyzer_false_source_claim` | **A1** (#968) — the decision does not inherit an analyzer claim the workspace refutes | `analyzer_claims_refuted` and `decision_inherited_claims`, joined per decision step (#1616); `refuted_verbatim` reported beside `inherited` and never counted as it | none |
| `contentless-builder` | `builder_emission_contentless` | **R1** (#1372) — retried with its fact, not blind | `retried_with_fact` | none |
| `contentless-builder-all-attempts` | `builder_emission_contentless_all_attempts` | **F1** (#1374) — no false corrected result composed; `builder.assemble_repair` reached | the re-derived required_files line; the repair's revision form | builder × React (declared) |
| `dev-lane-fastapi-react` | `dev_join_response_omits_declared_fields` | **the dev lane** (SIP-0107 step 3) — a probe failure on a developer-owned route is repaired by a development repair aimed at the probe-owned slot, inside its grant | the locus and target lines; the dev repair's revision form; the retest | **dev × React** |
| `dev-lane-nextjs` | the same | the same, on the App Router stack — `function:POST#try` keeps the signature and the catch envelope by construction (§46j) | as above | **dev × Next.js** |

Each config's `loaded_checks` asserts the seam's presence on the deployed image before the run,
with a control. **A seam not reached after two runs stops the set.**

**Round 1 (rev 1) found one, and it was the instrument.** `own-frame-then-prose-repair-nextjs`
(`cyc_464625db7c2b`, 65 min) read **L4 YES, L7 NO** — on an invariant that HELD. The own-frame
failure did route to the qa repair, through #1581's unanimity branch; L7's predicate was the
literal string `qa_owned_routed`, one of five branches that route a failure to its own artifact.
**The budget was not spent on run 2**, because `qa_owned_routed: []` is also the exact signature of
the real #1130/#1270 defect — the two readings were indistinguishable, so a second run would have
read NO again and proved nothing. Fixed by **#1624**: L7 reads the affirmative own-artifact locus
whichever branch logged it, joined on the faulted task's type. Review of that fix caught a false
green of its own — #1054's `own_artifact DISPUTED` falls through to the **dev chain** and a prefix
match swallowed it — so only `own_artifact — ` counts, filtered in the reading as well as the
collector. The deploy-A reading stands in §10 as evidence and **counts toward nothing**.

**Round 3 (rev 3) found the third, and it was an instrument again.** Six of nine cleared and all
four required cells exercised **under rev 3, which is now void — none of those transactions counts
toward rev 4's N, and all nine re-run** — then diagnostic 7 (`absent-suite-then-false-claim`) read **A1 NO on
both budget runs**. #968's prose refutation fired correctly, with the `decision_task=` field #1616
added; `_runtime_lines_of_interest`'s allow-list dropped the line before any collector saw it, so
`analyzer_claims_refuted` read empty and `_a1_reading`, which requires at least one refutation,
could not return YES. **Two runs spent on a reading that was structurally incapable of passing.**

Fixed by **#1633** (#1631): the marker is allow-listed and the test enters **at the filter**, not
at the reader. The cause of the miss is worth the record — **#1616 verified that reader by feeding
`docker logs` straight into it, bypassing the filter**, proving the function and saying nothing
about the wiring. That is the #1250/#1256/#1261 shape for the third time on this line. A
class-closing test was attempted, failed its own mutation check twice, and was dropped to **#1632**
rather than shipped as a guard that guards nothing.

**Round 2 (rev 2) found the second, and it was not an instrument.** The same diagnostic
(`cyc_5613d2fb55e4`) reached the qa repair, and the qa agent took a **SIGSEGV** inside
`qa_test_repair_handler` — a corrupt `tree_sitter` node, #1626. Docker restarted it, the broker
redelivered the unacked message, and it died again: **37 restarts in ~90 minutes, no record
written, and `cycle_runs.status` left `running` with nothing running**, which by the driver's own
contract makes every later preflight refuse. One message bricked the deploy.

Two fixes followed, and **only these move the deploy**:

- **#1627** — the bound. A redelivered `comms.task` is converted to a typed `FAILED` for the
  original task id and acked; only recorded cycle governance may retry it. SIP §5.3a carries the
  rule, why it follows from *completion being unknown* rather than from a cause, the ack-gap case,
  and the single-active-consumer condition it rests on.
- **#1628** — the parse guard. A node row outside the content is a corrupt parse, refused rather
  than indexed on. **It does not stop the SIGSEGV** — verified: the crash moves rather than
  stopping, because the binding dies while producing the value. #1626 stays open; subprocess
  isolation is validated (child `-11`, parent survives) and not built.

**Deployment acceptance ran before this registration**, as the review required: 3 of 4 assertions
pass on the rebuilt deploy — `FAILED` for the original task id, the queue drains, the handler is
not broker-run again — plus `x-death` measured absent on an automatic requeue. **The fourth, that
a run leaves `running` through correction or termination, is NOT covered**: the probe used a
synthetic task with no `cycle_runs` row. **It is asserted explicitly on the first counted-or-
diagnostic run of round 3**, not assumed from the other three.

### 3d′. Deploy A — one mechanism prediction per prelude fix

Each fix is read where its mechanism shows, never as a rate. **Four are predicted silent on this
set**, and saying so before the fact is the point: a guard that lands after the loop already
complies is honest only if the prediction said it would be quiet.

| fix | mechanism predicted | read from |
|---|---|---|
| **#1603** (#1602) | a qa round whose free-authored suite fails beside its fill slots names **both** the free suite and the shells in its repair target set, and the retest runs | `own-frame-then-prose-repair-nextjs`: the target line and `patch_retest`. **This is the fix that makes qa × Next.js reachable at all** |
| **#1608** (#1539) | **predicted silent.** A root-level `__tests__/` is excluded from the qa source set; the 37 such filenames in the vault were already matched by the stack patterns, so no stored run changes | the qa source-set listing on every Next.js roll; any change is drift (§9) |
| **#1612** (#1526) | the inert window on a record is anchored at **its own** perspective cycle, so a later cycle cannot retroactively move an earlier record's inert reading | the inert section of every record; reporting-only |
| **#1613** | `squadops cycles assess` returns an assessment for every completed roll, from the same stores the record reads | one invocation per arm, recorded in §10 |
| **#1609** (#1598) | **predicted silent.** A scaffolded suite's stores reset between tests through the seeded conftest's autouse `reset()`, with no plan hint claiming it; two of 2,755 stored suites use a non-function-scoped fixture and neither is at risk | any scaffolded qa suite run; a cross-test bleed falsifies it |
| **#1611** (#1610) | every task dispatches to the agent its profile **declares**; no queue named after a role is ever created, and `UndeclaredRolesError` never fires on `full-38`. Migration 1510 backfilled `serves_roles` on the persisted row | `generate_task_plan`'s dispatch; the agents' consumed queues; **the deploy's stored profile, read in §1** |
| **#1614** | every correction round runs exactly the steps `validated-fullstack` declares — analyze, decide, repair — read from the profile, with no second table in code | the correction rounds of any diagnostic that corrects |
| **#1615** | **predicted silent on a squad arm**, where each process's declared roles are its own single role; its exercise is the Solo arm on B′. A miss would name both declarations in `HandlerNotFoundError` | any dispatched task; silence is the prediction |
| **#1617** | all nine configs load and derive their stack, and the ninth's fault lands where the record can count it | the driver's config test, and the ninth diagnostic's first run |
| **#1618** | every record carries its `CycleAssessment` with the attribution id (SIP-0108 §4.1–4.2) | every record; reporting-only |
| **#1616** (#1600) | when #968's refutation fires and the lead **quotes** the refuted path in order to reject it, **A1 reads YES** with `refuted_verbatim` naming the path and `inherited: False`. Where the refutation did not fire, **A1 reads UNASKABLE, never YES** — a clean decision without a refutation proves only that the fault never reached the lead | `absent-suite-then-false-claim`'s record: `analyzer_claims_refuted`, `decision_inherited_claims`, `refuted_verbatim`, `unjoinable_refutations` |
| **#1620** (#1619) | **predicted silent on this set** — no comparison runs on deploy A, and `arm` is empty on all nine diagnostic configs, which declares "not part of a comparison" rather than asserting one. Its live effect here is the flat completion cap reaching the deploy through the PUT | the arm preflight is not invoked; the cap is read in §1 |

**The fix this round produced — one mechanism prediction, same rule as the table above.**

| fix | mechanism predicted | read from |
|---|---|---|
| **#1624** (#1623) | on the re-run, the own-frame failure routes to the qa repair and **L7 reads YES with the branch named** — `analyzer_and_decision_unanimous` if the round is unanimous, `qa_owned_routed` if the suite is stamped qa-owned. A run whose routing is DISPUTED (#1054), which falls through to the dev chain, still reads **NO** | `own-frame-then-prose-repair-nextjs` and `own-frame-then-prose-repair`: `loop_texture.own_artifact_locus` and the seam's evidence list |

**Round 2's fixes — one mechanism prediction each.**

| fix | mechanism predicted | read from |
|---|---|---|
| **#1627** (#1626) | **predicted silent on a clean round.** A redelivery only occurs when a delivery went unacked, which a healthy round never produces. If one *does* occur, the record must show a typed `FAILED` for the original task id, the queue draining, and **no second handler invocation** — never a silent broker replay | the agent's `redelivered_task_refused` line; the run's task results; `eve_comms` depth |
| **#1628** (#1626) | **predicted silent**, and explicitly NOT a fix for the crash. If a corrupt node recurs, `jsx_entities` returns `None` — a structural-parse miss the repair path already handles — rather than indexing on the row. The SIGSEGV itself is unbounded by this and #1626 stays open | `jsx_entities: corrupt parse tree` warnings, expected absent; a repeat SIGSEGV would be a new finding, not a regression of this fix |

### 3e. CI invariants, read live as texture

The rewind invariant (W1), the locus invariant (D1, with #1581's unanimity rule beside #1054's
dispute rule), the derived-rows invariant (F1), the untouched-file rule (#1406), the #1501 carried
signature rule.

### 3f. Texture — observed, never blocking, every field with its unaskable state declared

Per repair, from the revision form (§46k–§46p): files offered with their entity counts; the form
taken; the modes; the replaced span per file; fragment anchors; whole-file responses offered and
unoffered; refusals and retries. Per round: the locus line and which rule chose it; the termination
reason; carried, cleared and added signature counts. Per roll: emitted bytes and tokens per repair;
correction rounds; framing-run verdicts; fill-mode completion tokens; `container_packaging` rows;
the three #80 lineage fields; a `run_loop_summaries` row per run; the `CycleAssessment` with its
attribution id. **Unauthorized whole-file responses per cell** are the count the flip replays from —
reported, not blocking, until the flip lands.

**Every field declares its unaskable state.** A field whose producer did not run reads UNASKABLE,
never NO and never zero (#1593). A1's unjoinable case (#1616) is the worked example: a record from a
deploy predating `decision_task=` cannot join a refutation to a decision, so it reads UNASKABLE
rather than claiming a mechanism it cannot see.

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — four counted rolls

Config `docs/plans/verification-sets/1-8-1-fastapi-react.yaml`, pinned to §1's snapshot. Rolls 1–4,
one roll per driver invocation, gate policy the 1.6.3 §6 constant, decider recorded per roll.

## 5. Next.js+TS (`nextjs_ts`) — two counted rolls

Config `docs/plans/verification-sets/1-8-1-nextjs.yaml`, overrides `build_profile=nextjs_ts` and
`development_profile=nextjs_ts`. Rolls 1–2.

## 6. The shakeout loop and its exit

**The nine diagnostics are the shakeout** (§2). The exit rule, stated before the first launch: a
diagnostic pass on one deploy with **no new seam finding**. A finding becomes a fix, the deploy
moves, this pre-registration is void and re-made on the new deploy, and no transaction from the
superseded deploy counts. **Budget: two runs per diagnostic**; a seam unreached after two stops the
set. The record reports how many rounds it took, which is evidence about the pack.

**Rounds so far: three.** Round 3 is the first to get past its first diagnostic: it cleared six
of nine and all four required cells before halting on diagnostic 7, where A1 could not read a
refutation that fired (#1631) — an instrument defect, like round 1's. **Round 4 begins at rev 4
and re-runs all nine**; rev 3's clearances are evidence in §10 and count toward nothing.

*Rounds 1 and 2, as recorded then:* **two, and neither reached a second diagnostic.** Round 1 (rev 1) found #1623 —
an instrument defect — on its first diagnostic. Round 2 (rev 2) found **#1626** on the same
diagnostic: the qa agent took a SIGSEGV inside a repair handler and the framework answered with an
unbounded crash-restart loop, 37 restarts in ~90 minutes, no record, and a `running` row that would
have made every later preflight refuse. Round 3 begins at rev 3 on rebuilt images.

**That is evidence about the pack and is recorded as such.** Two rounds, two findings, both on the
FIRST diagnostic of the nine, and neither was a squad failure: one was a seam reader that could not
tell a working routing from the defect it exists to catch, the other a native crash with no bound
around it. A pack that surfaces two framework defects before reaching its second diagnostic is
doing its job; a cut record that smoothed that into "the shakeout took three rounds" would lose the
only interesting fact about it. A pack that yields a finding on its first
diagnostic is evidence about the pack, and it is recorded as such rather than smoothed away.

## 7. Gate constant

The 1.6.3 §6 constant, verbatim in each set config's `gate_notes`. `--as-agent`. Gates never
self-approve; the decider is recorded per roll.

## 8. Prohibited while this set is open

**Nothing merges to main** (plan §7). No framework change under `src/` or `adapters/`; no config,
profile or prompt-asset change; no deploy move. Docs and driver-only changes are free **only** where
they cannot alter a reading — and a change that could is a deploy move, which voids this commit.

## 9. Drift the record must declare

The `resolved_config_hash` per arm against 1.8.0's `3921c5a62106` / `33cadf53688e`; the
`squad_profile_snapshot_ref` against the pre-1.8.1 `575707c58536cf3b`, with **both 1.8.1 causes
named** — `serves_roles` entering the payload (#1611) and the flat cap plus the PUT's `version` bump
(#1620/#1619); the image ids against deploy F's; any qa source-set change (#1608, predicted silent).

---

## 10. Diagnostic readings — appended as they land

*(Appended after each diagnostic and each counted roll. Nothing else in this document moves.)*

Records: `var/verification_sets/1-8-1-diagnostics/<diagnostic>/shakeout-<UTC>.{md,json}`,
`1-8-1-fastapi-react/roll-0N-<UTC>.*`, `1-8-1-nextjs/roll-0N-<UTC>.*` — on the Spark, gitignored;
the readings below are the committed evidence. Every reading here is taken from the stored record
(`seam_reached`, `loop_texture.repair_revision_forms`, `.retests`, `.candidate_identities`), never
from memory of the run. Times ET.

### 10a. Rounds 1–3 — superseded registrations; evidence, counting toward nothing

| round (rev) | diagnostic | run | cycle | verdict | rounds | seam |
|---|---|---|---|---|---|---|
| 1 (rev 1, `87c3311a`) | `own-frame-then-prose-repair-nextjs` | 1 | `cyc_464625db7c2b` | accepted | 1 | L7 **NO** on an invariant that held — the literal-token reader, **#1623**; L4 YES. Run 2 not spent (§3d) |
| 2 (rev 2, `61057f73`) | `own-frame-then-prose-repair-nextjs` | 1 | `cyc_5613d2fb55e4` | **no record** | — | the qa agent took a SIGSEGV in `qa_test_repair_handler`, 37 restarts in ~90 min — **#1626**; run cancelled through the CLI 18:26 |
| 3 (rev 3, `9b9d1de7`) | `own-frame-then-prose-repair-nextjs` | 1 | `cyc_162510005044` | accepted | 1 | L7 **NO** — routed to the dev chain (`development_correction_repair_handler none`), L4 **UNASKABLE** (the prose fault's target never ran) |
| 3 | `own-frame-then-prose-repair-nextjs` | 2 | `cyc_de7f3c333ee5` | accepted | 2 | L7 **YES**, L4 **YES** — both qa repairs prose, both refunded; no qa patch |
| 3 | `own-frame-then-prose-repair` | 1 | `cyc_0396488b4d39` | accepted | 2 | L7 **YES**, L4 **YES** |
| 3 | `dev-lane-fastapi-react` | 1 | `cyc_d5b371320f0c` | accepted | 2 | **YES** |
| 3 | `dev-lane-nextjs` | 1 | `cyc_12d5d6ff7a2c` | accepted | 1 | **YES** |
| 3 | `absent-suite` | 1 | `cyc_36646382b789` | accepted | 3 | L2 **YES** |
| 3 | `path-prefix` | 1 | `cyc_4cc271160ce1` | accepted | 0 | L8b **YES** |
| 3 | `absent-suite-then-false-claim` | 1 | `cyc_fecad3e1f03b` | blocked_unverified | 1 | L2 **NO**, A1 **NO** |
| 3 | `absent-suite-then-false-claim` | 2 | `cyc_e6eecfd14869` | accepted | 2 | L2 **YES**, A1 **NO** — the refutation fired and the allow-list dropped it, **#1631**; both budget runs structurally unable to read YES |

Round 3 ran 2026-09-20 21:39 → 2026-09-21 07:07 ET and halted at diagnostic 7; diagnostics 8 and 9
never ran under rev 3.

### 10b. Round 4 (rev 4, driver HEAD `449a162b`, deploy `70f578fe` images) — the nine, in 12 runs

2026-09-21 10:55 → 2026-09-22 01:08 ET. Nine of nine seams reached inside the two-run budget;
three needed their second run. **No new seam finding — the §6 exit rule is met on this round.**

| diagnostic | run | cycle | verdict | rounds | min | seam |
|---|---|---|---|---|---|---|
| `own-frame-then-prose-repair-nextjs` | 1 | `cyc_53dd83ddda50` | accepted | 1 | 59 | L7 **NO** — the own-frame failure routed to the **dev chain** (`development_correction_repair_handler none`, 7 files offered, refunded); L4 **UNASKABLE**. A genuine routing NO, as #1624 predicted for the DISPUTED/dev-chain case |
| `own-frame-then-prose-repair-nextjs` | 2 | `cyc_bce374af7e89` | accepted | 1 | 60 | L7 **YES** — `own_artifact — analyzer_and_decision_unanimous` (#1581); L4 **YES** — the prose repair refunded (`refund 1 of 3`). **No qa patch followed**: after the refund the qa task **re-emitted** the suite (`task-run_0647ee1b-m004-qa.test` artifacts at 14:00 and again at 14:09 ET), `candidate_identities` asked_none, retests 0 |
| `own-frame-then-prose-repair` | 1 | `cyc_3ba9057e5cdf` | accepted | 4 | 78 | L7 **YES** — `own_artifact — qa_owned_routed` (#1130) on both suites; L4 **YES**. Three accepted anchored qa edits (5% and 3% of `run_views.test.jsx`) and a 1% dev edit on `routes.py` — **every retest FAILED** (`Repaired suite still fails`), no §20 identity line; the cycle reached `accepted` by the qa task re-emitting each suite after its failed retest (15:07, 15:21, 15:29 ET) |
| `dev-lane-fastapi-react` | 1 | `cyc_4535eb6c687c` | accepted | 1 | 53 | **YES** — dev anchored edit on `backend/routes.py`, 119 of 3,398 chars (**4%**), verified, retest `SUCCEEDED`, `patch_candidate_identity` verified = persisted |
| `dev-lane-nextjs` | 1 | `cyc_4162e71ebc57` | accepted | 1 | 52 | **YES** — dev anchored edit on `app/api/runs/[run_id]/join/route.ts`, 200 of 1,631 chars (**12%**), verified, retest passed, identity verified = persisted |
| `absent-suite` | 1 | `cyc_6070e7a96402` | rejected | 2 | 65 | L2 **NO** — the repair's patch verification failed `contract_assertions_match`, so no retest ran; probes and `tests_pass` failed. A squad miss, not an instrument one |
| `absent-suite` | 2 | `cyc_38cbb5b54693` | rejected | 3 | 81 | L2 **YES** — three retests ran; one anchored 3% edit accepted by the verifier, **retest FAILED**; two `new_files_only` responses |
| `path-prefix` | 1 | `cyc_d797d515c06b` | accepted | 0 | 45 | L8b **YES** — zero strips, zero stored under `path/` |
| `absent-suite-then-false-claim` | 1 | `cyc_df65ea551311` | accepted | 2 | 73 | L2 **YES**; A1 **NO** — the refutation fired (`backend/__squadops_injected_fault__.py`) and the decision did not inherit the path, but **echoed** the claim's phrase (`router registration`); the reader refuses an echo by design (#1600) |
| `absent-suite-then-false-claim` | 2 | `cyc_dd2822190433` | accepted | 3 | 73 | L2 **YES**; A1 **YES** — refuted verbatim, `inherited: False`, no echo — **the first A1 YES on any 1.8.x deploy**. One anchored 3% qa edit on `backend/tests/test_runs.py` (219 of 7,370), retest `SUCCEEDED`, identity verified = persisted |
| `contentless-builder` | 1 | `cyc_9e47702af705` | accepted | 1 | 62 | R1 **YES** — the retry carried its emission-shape fact and was accepted. One anchored 2% qa edit accepted by the verifier, **retest FAILED** |
| `contentless-builder-all-attempts` | 1 | `cyc_b7058e601977` | rejected | 3 | 57 | F1 **YES** — `builder.assemble_repair` reached, framework rows re-derived from the patched set; two anchored edits on `assembly_notes.md` (2% of 1,801; then **62%** of 206), identity verified = persisted. **Read over the unaskable `required_files_rows`** (filtered at the typed-check seam, #114) |

**The three second runs.** Two are the squad, one is the routing: absent-suite's first repair failed
verification (no retest is the correct NO); the false-claim lead echoed a refuted claim on its first
run (the correct NO); the Next.js own-frame failure routed to the dev chain on its first run, as it
had on one of two rev-3 runs — **the route an own-frame failure takes on the App Router stack is not
deterministic**, two of five runs across the line went to the dev chain.

**L1 on the diagnostics:** the contentless counts in these records are the injected faults
themselves (`qa_test_handler` ×4 on the absent-suite family, `builder_assemble_handler` on the
contentless-builder pair, the prose-only `qa_test_repair_handler`); none is a bar reading.

### 10c. The §3d′ fix predictions — read

| fix | reading |
|---|---|
| #1603 (#1602) | **half held**: on `cyc_bce374af7e89` the target line named the free-authored suite (`__tests__/runs.test.ts`, 14 entities offered to the qa repair); the retest half is **not exercised** — no qa patch followed the refunded prose repair, so nothing was retested |
| #1608 (#1539) | predicted silent — **not read on this pass**; the §9 qa source-set comparison is outstanding for the cut record |
| #1612 (#1526) | reporting-only; `inert` reads `asked_none` on every record and assessment read |
| #1613 | **held** — `squadops cycles assess` invoked on `cyc_a7354627cf1c` (React) and `cyc_bce374af7e89` (Next.js): verdict, criteria coverage, `required_unverified`, `inert`, each with its evidence column |
| #1609 (#1598) | predicted silent — **not falsified**: no retest or suite failure in any record is attributed to a store bleed; not separately instrumented |
| #1611 (#1610) | **held** — 0 `UndeclaredRolesError`, 0 `HandlerNotFoundError` in runtime-api, eve, neo and bob logs since the rev 3 deploy; the served snapshot `2d8d4feb3519a7ec` carries `serves_roles` (§1) |
| #1614 | **held** — every correcting round in every record runs `data.analyze_failure` → `governance.correction_decision` → repair, read from the artifact lineage (`corr-…-NN-…`, `repair-…-NN-…`) |
| #1615 | predicted silent — **silent**: 0 `HandlerNotFoundError` |
| #1617 | **held** — nine configs loaded; the ninth's fault applied (`task-run_0647ee1b-m004-qa.test`, 9,642 → 9,709 chars) and its record read the cell |
| #1618 | **held** — 22 of 22 records carry `cycle_assessment` |
| #1616 (#1600) | **held** — A1 YES on `cyc_dd2822190433` with `refuted_verbatim` naming the path and `inherited: False`; the NO on `cyc_df65ea551311` is the echo case, refused as designed; UNASKABLE never read where the refutation fired |
| #1620 (#1619) | predicted silent — **silent**: the arm preflight was not invoked; the flat cap reached the deploy through the PUT and the pin was read from it (§1) |
| #1624 (#1623) | **held, with the branch named** — `analyzer_and_decision_unanimous` on Next.js (`cyc_bce374af7e89`), `qa_owned_routed` on React (`cyc_3ba9057e5cdf`); the two dev-chain runs (`cyc_162510005044`, `cyc_53dd83ddda50`) read **NO**, as predicted for that case |
| #1627 (#1626) | predicted silent — **silent**: `squadops-eve` RestartCount 0 since the rebuild; exactly one `redelivered_task_refused` line in its log, the deployment-acceptance probe. **The fourth acceptance assertion (a run leaves `running` after a refusal) remains unexercised** — no redelivery occurred on any run |
| #1628 (#1626) | predicted silent — **silent**: 0 `corrupt parse` warnings in runtime-api since the rebuild; no SIGSEGV recurred |

### 10d. The counted arm — FastAPI+React rolls 1–4 (2026-09-22 05:40 → 10:10 ET)

Launched from HEAD `ffd826b2` (rev 5) on the same seven images; config hash `58eed2c52e1f`, snapshot
`2d8d4feb3519a7ec` — both read from the deploy at launch.

| roll | cycle | verdict | audit | rounds | min | reading |
|---|---|---|---|---|---|---|
| 1 | `cyc_b98c45fcd5c8` | **rejected** | FAIL — `vc-probe-dev-seed` 500 | 3 | 114 | one accepted qa edit on `backend/tests/test_runs.py` — 85 of 85 chars (**100%**), one fragment anchor — **retest FAILED**; a second qa repair prose, refunded. **L1: 1 contentless emission, `qa_test_handler:self_eval`** — 0 chars out at the 12,288-token cap, 44,894 reasoning chars. **L1 HELD by construction**: a contentless self-eval pass yields no fenced files, so `_self_evaluate` re-validates the first-pass artifacts and the task proceeds; the loop then ran three correction rounds. The rejection is the probe 500, unrelated |
| 2 | `cyc_d50ab727db40` | accepted, functional | PASS | 0 | 49 | clean — 18/18 |
| 3 | `cyc_6bcef7f3f8e4` | accepted, functional | PASS | 0 | 51 | clean — 21/21 |
| 4 | `cyc_a7354627cf1c` | accepted, functional | PASS | 1 | 50 | **dev × React**: `development_correction_repair_handler` anchored edit on `frontend/src/views/CreateRunView.jsx`, 395 of 3,123 chars (**13%**), verified, retest `SUCCEEDED`, identity verified = persisted |

React 3 of 4 functional. L1 held on all four.

### 10d′. The counted arm — Next.js+TS rolls 1–2 (2026-09-22 10:11 → 12:56 ET)

Roll 1 launched from HEAD `ffd826b2`; roll 2 from `e2f06d8a` after #1635 (docs only — the diff from
`ffd826b2` under `src/`, `adapters/`, `scripts/` and `config/` is empty; the roll-1 pin is archived beside
the records as `.head_pin.rev5-ffd826b2`). Config hash `fff4a6435c97`, snapshot `2d8d4feb3519a7ec`, the
same seven images.

| roll | cycle | verdict | audit | rounds | min | reading |
|---|---|---|---|---|---|---|
| 1 | `cyc_4d9602ce0a66` | accepted, functional | PASS | 1 | 93 | the qa repair (`__tests__/ui.test.ts`, 9 entities offered) emitted **nothing** — `cap_exhausted`: 12,288 completion tokens, the cap, 49,254 reasoning chars, 0 out; refunded; the qa task re-emitted the suite and it passed. **No transaction.** L1: one contentless emission, recovered by the refund and the re-emission — held |
| 2 | `cyc_5bbf85db4622` | accepted, functional | PASS | 1 | 68 | the decision routed a qa-suite failure to a **dev** repair: `development_correction_repair_handler` anchored edit on `app/api/runs/route.ts`, 677 of 1,919 chars (**35%**), verified 8 checks, **retest FAILED** (`tests_pass` and `frontend_build`), no identity line — the patch was not accepted; the qa task re-emitted the suite at 12:47 ET and it passed on the unpatched tree. **No transaction.** L1: none |

Next.js 2 of 2 functional. L1 held on both. **Zero scoped transactions on the App Router stack across the
whole line**: nine Next.js cycles (five ninth-diagnostic runs, two dev-lane runs, two counted rolls)
produced one that counts — the dev-lane diagnostic's — and no qa transaction at all.

### 10e. N — the reading (the set is complete; every registered source observed)

**The counting evidence.** §3c counts a transaction that is verified **and passed its retest** and
was persisted under the identity it was verified with. That identity is written once, at
acceptance (`patch_acceptance.py` `_accept_patch`, SIP-0107 §20, the `patch_candidate_identity`
line), and only after the retest passed — so it is the arbiter. Runtime-api has logged exactly six
such lines since rev 4 took effect, and they are the six rows below. A verifier-accepted edit whose
retest failed is, in §3c's words, a transaction "whose repair failed … the retest" and adds nothing.

| cell | count | transaction | replaced | retest | identity |
|---|---|---|---|---|---|
| dev × React | **2** | `dev-lane-fastapi-react` — `backend/routes.py` | 4% | SUCCEEDED | held |
| | | counted React 4 — `frontend/src/views/CreateRunView.jsx` | 13% | SUCCEEDED | held |
| dev × Next.js | **1** | `dev-lane-nextjs` — `app/api/runs/[run_id]/join/route.ts` | 12% | passed | held |
| qa × React | **1** | `absent-suite-then-false-claim` run 2 — `backend/tests/test_runs.py` | 3% | SUCCEEDED | held — counts by the owner's ruling above (§3c governs; the §3d column is a forecast) |
| qa × Next.js | **0** | — | | | |
| builder × React (declared, not required) | 0 | `contentless-builder-all-attempts` — `assembly_notes.md` | **62%** | (no suite) | held — **excluded by counting rule 2** |

**N = 4 against 6, with qa × Next.js at zero. The success-path readiness prediction (§3b) is
falsified on both of its conditions, and SIP-0107 §39.8's precondition for step 7 is not met on
this deploy.** By plan §3.3 and §8 decision 2: the flip PR is not merged, 1.8.1 ships without it and
says so, SIP-0107 stays `accepted` with step 7 named open, and deploy B is the prelude's deploy
re-pinned; the line continues to B′. No discretion enters after this reading, and nothing is
re-run — an unmet N "is recorded as a shortfall, not retried into existence" (§3b).

**The shortfall in §39.8's own terms.** Two successful transactions short of six, and one required
cell empty. The empty cell is the one 1.8.0 could not fill either; this line registered its supply
(the ninth diagnostic, #1617) and the retest that 1.8.0 lost (#1603), ran it five times across four
registrations, and it produced no scoped qa transaction. The all-attempt integrity prediction
(§3b, first reading) **held** on every attempted transaction: zero outside-grant changes, zero
identity mismatches, zero partial acceptances; every verifier-accepted edit that did not count
failed its retest, which is the contract working, not failing. The rendered-packaging prediction
(#598) held: no builder-authored Dockerfile, no finding on an accepted emission.

**Counted-roll supply, as forecast and as read.** §3c forecast ~1 dev × React and ~1 qa × React
across four React rolls (read: 1 and 0), ~0 dev × Next.js and ~1 qa × Next.js across two Next.js
rolls (read: 0 and 0). Six counted rolls, five functional, one transaction. The diagnostics were
the supply by design and they supplied three of the four.

**What was accepted by the verifier and did not count, and why** — every one is a retest failure:

| where | edit | why it does not count |
|---|---|---|
| `own-frame-then-prose-repair` (the registered qa × React supplier) | qa anchored 5% and 3% on `run_views.test.jsx`; dev anchored 1% on `routes.py` | all three retests FAILED |
| `absent-suite` run 2 | qa anchored 3% on `test_runs.py` | retest FAILED |
| `contentless-builder` | qa anchored 2% on `run_views.test.jsx` | retest FAILED |
| counted React 1 | qa anchored, 100% of `test_runs.py` | retest FAILED — and rule 2 |
| `contentless-builder-all-attempts` | builder anchored 62% | rule 2 |

**Added by the Next.js rolls.** Roll 1's empty qa repair was not prose: it spent the whole flat
completion cap (#1619/#1620, 12,288) on reasoning and emitted nothing — the same shape as React
roll 1's self-eval pass (12,288 tokens, 44,894 reasoning chars, 0 out). Two of two cap-exhausted
emissions on this deploy are reasoning that never reached a fence: one per stack, a count and not a
rate, and a second 1.8.2 input distinct from the qa repair prompt. Roll 2 adds a wrong-locus round:
the lead routed a qa-suite failure to a dev repair whose patch broke the frontend build and was
discarded; the re-authored suite passed on the unpatched tree.

**The finding this working surfaces, stated as a mechanism.** On this deploy the loop's response to
a qa own-frame failure is **re-authoring, not scoped repair**: on React every scoped qa repair of
the faulted suite failed its retest and the qa task then re-emitted the suite; on Next.js the qa
repair answered in prose (faulted once, and once unfaulted under rev 3) and the qa task re-emitted.
Five runs of the ninth diagnostic across the line produced **zero** scoped qa transactions on the
App Router stack. The §3c supply forecast for both qa cells — "1–2, the second repair after the
prose one is refunded" — assumed the re-take would be a repair; it is a re-emission. This is the
substantive input to the 1.8.2 plan and to SIP-0107 step 7, whatever the Next.js rolls read.
