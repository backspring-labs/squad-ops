# 1.8.1 verification set — pre-registration (plan §7 step 5)

**Status:** rev 3 (2026-09-20) — **re-made after the shakeout's second finding** (#1626). Rev 2 is
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
| `resolved_config_hash` | FastAPI+React observed on roll 1 and recorded in §10, Next.js+TS likewise — 1.8.0 read `3921c5a62106` and `33cadf53688e`; a change is drift the record declares (§9) |
| `squad_profile_snapshot_ref` | **`2d8d4feb3519a7ec`** — **not precomputable.** `serves_roles` entered the snapshot payload (#1611) and the flat completion cap moved a value (#1620/#1619), and the PUT that lands the cap bumps `version`, which is itself inside `compute_profile_snapshot_hash`'s payload. The pre-1.8.1 pin was `575707c58536cf3b`; the file at version 1 computes `cbf3a18d…`; **the deploy stamps neither.** The driver refuses a counting roll on any other (#1571) |
| Deploy — commit | **`70f578fe`** — rev 2's `f6994271` plus #1628 (the parse guard) and #1627 (the redelivery bound), both under `src/`. **A label, not an assertion** (#1296): the image ids are the assertion, and they are unchanged. `git diff 18798083..f6994271 -- src/ adapters/` is empty, which is why no rebuild followed the fix |
| Deploy — image ids | `runtime-api 0d33b2820245`, `max 4fbb4efad454`, `neo c379594cb4fd`, `nat d7c038b44c32`, `runtime-api 3ccd7f7b931e`, `max 84708fd3ceb6`, `neo 1e74a0b5334d`, `nat bd81e2c6fb2c`, `bob 4abda1d62302`, `eve 55a19a45982b`, `data 1af2fef0345a` — **all seven changed** at the rev 3 rebuild (rev 1/2's were `0d33b2820245`, `4fbb4efad454`, `c379594cb4fd`, `d7c038b44c32`, `c2c1a64c7063`, `4dfeb0dcdb62`, `9e1c65ee4d06`). **The pin is unchanged at `2d8d4feb3519a7ec`** — re-read from the deploy, not assumed: the squad profile was not touched (deploy F's, superseded, were `runtime-api b3278c26dd25`, `max 36cc6eb9a923`, `neo 07498c2a4a94`, `nat 1ddf151647c0`, `bob b59711b8f653`, `eve 14d15dc8e3f7`, `data 9a41965b25ad`) |
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

**Rounds so far: two, and neither reached a second diagnostic.** Round 1 (rev 1) found #1623 —
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
