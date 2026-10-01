# 1.9.0 — pre-registration (plan §4, §3.6)

**Rev 9 (2026-10-01): React rolls 1 and 2 read; the set paused on roll 2's rejection and resumed on the owner's ruling (§11d).**

**Rev 8 (2026-09-30): d8 read; the diagnostics close, §11b executed, the counted set opens (§10).**

**Rev 7 (2026-09-30): d7 read (§10); the set stopped on it and resumed on the owner's ruling (§11c).**

**Rev 6 (2026-09-30): d5 and d6 read (§10).**

**Rev 5 (2026-09-30): d4 read (§10).**

**Rev 4 (2026-09-30): d3 read (§10).**

**Rev 3 (2026-09-30): d2 read (§10). §11a's checkout move is re-timed to after the eighth diagnostic
(§11b).**

**Rev 2 (2026-09-30): d1 read (§10). The diagnostics' records directory is corrected (§11a).**

**Status: rev 1 (2026-09-29). Merged unreviewed: no crew review** (plan §7 decision 7). The owner
said "I don't have crew budget for the review — I think we need to fly solo". Decision 6's fallback
applies: the record says so here, at the revision. **Nothing in the set had launched at merge.** The rules, the
diagnostics, the predictions, the readouts and the pins are committed here on the 1.9 deploy before
any launch (plan §6 step 6: the owner reads this before the first diagnostic).
- **Pins.** Every pin in §1 was read from the deploy, or computed by the CLI's own code on its tree.
  None is carried from 1.8.2 without being re-read.
- **Once this merges, the cut criteria do not move.** Only readings are appended (§10). If the deploy
  moves, this registration is void and re-made, and nothing from the superseded deploy counts.
- **Crew review** (plan §7 decision 7): none, as stated above. No second reader has seen these
  rules or the configs. The PR ran `nostromo crew checks` as every PR does; that is a CI check, not a
  review.

**What this set measures.** These are the plan's experimental gate (§3.6), in its order:
1. **Behaviour held equal across the extraction** (#1507). The executor's completion boundary moved
   in three slices, with no behaviour change allowed to ride them. The set reads whether anything a
   cycle does changed anyway.
2. **The 1.8.2 claim still holds:** `unattended-chain` reads YES on every row.
3. **#1697's prediction reads on a counted set:** distinct correction ids, and every refund joined
   to its own dispatch.
4. **N as texture** (decision 5), at no extra rolls. It is the fourth count that 2.0's flip decision
   reads.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| Counted rolls | **4** on FastAPI+React (§4), **2** on Next.js+TS (§5), as 1.8.2 |
| Bar | **one: L1** (#1268): blocking on a counted roll whose contentless emission is not recovered |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack`, identical to 1.6.6 → 1.8.2 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React **`a79f58658cd8`**, Next.js+TS **`8e730c8ea169`**. Computed by the CLI's own `compute_config_hash(crp.defaults, overrides)` on the deploy's tree, and confirmed by each arm's first launch. **Unmoved from 1.8.2**: no 1.9 change touched `validated-fullstack` (each config's `pins_unmoved_because` says so) |
| `squad_profile_snapshot_ref` | **`2d8d4feb3519a7ec`**, read from the deploy by the driver's `live_squad_snapshot("full-38")`. **Unmoved**: no 1.9 change touched `full-38` |
| Deploy: commit | **`1abe3666`**, main after #1762, with main's full CI read green after every merge (§2). A label, not an assertion (#1296): the image IDs are the assertion |
| Deploy: image IDs | `runtime-api 1bfeb5513f55`, `max 3efa4b48b53c`, `neo 9f4f2ef24b06`, `nat 4d74fb20420a`, `bob b247f2ddd575`, `eve 20ead3ab5e8f`, `data e4f9220a2136`. **All seven changed** from A′ (§9). `joi c4a17c8d5558` and `han 18031b0f2d16` were rebuilt with them, han included for the first time since 1.8.1 (#1762); neither is in the identity assertion |
| Deploy: record | **`dep_d413c36959ab`** (#1720). 21 services, each with its image ID and revision label: every framework image reads `1abe3666`, and 9 infrastructure images carry no label. 5 models, each with its digest: `qwen3.8:27b` is `22130167c4c2`, and Atlas's `Qwen/Qwen3.8-27B-FP8` has none because Ollama does not serve it. **Every cycle of the set references it**, and every agent's heartbeat revision reads `revision_matches_deploy: True` against it |
| Loaded, not built | Each is a live call with its paired control (#522, #1425). 1.8.2's checks are carried unchanged. The 1.9 line's are appended to the counted configs' `runtime-api` and `neo` blocks. **Read from the deploy at registration:** `1697 repair-run_01234567-00-s00-qa.test_repair True`, `1754 run_paused False`, `1720 True False None`, `353 True 33`, `1753 1abe3666` |
| Per-task wait | `SQUADOPS__DISPATCH__TASK_TIMEOUT=1800`, required (1.8.2 item 15) |
| Gate policy | The 1.6.3 §6 constant, verbatim in each config's `gate_notes`; `--as-agent`; the decider recorded per roll |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-9-0-<arm>.yaml --roll N`; diagnostics via `shakeout --set …-diagnostic-*.yaml`; the chain via `chain --set …-diagnostic-unattended-chain.yaml`. The driver runs from its own checkout at this registration's merge commit (§8) |
| Preflight at registration | **All ten configs clean** on 2026-09-29, the two counted arms with `--counting` (the frozen images match, no framework drift). Nothing was launched to read a pin (#1648) |
| Order | **The eight diagnostics first**, which are the shakeout (§6), in 1.8.2's order: `compile-loop`, `false-criterion`, `redelivery`, `unattended-chain`, `own-frame-then-prose-repair-nextjs`, `own-frame-then-prose-repair`, `dev-lane-fastapi-react`, `dev-lane-nextjs`. Two runs each, the chain once, run by `var/1-9-0-logs/run_1_9_0_diagnostics.py` (1.8.2's sequencer, carried). Then FastAPI+React rolls 1–4, then Next.js+TS rolls 1–2 |

---

## 2. Preconditions: what the deploy carries

**Twenty-nine commits from v1.8.2 (`6daaad3b`) to `1abe3666`**, each merged with main's full CI read
green before the next. By kind:

| kind | merges |
|---|---|
| **#1697**: a round's task ids are unique within the run | `0739af1d` (#1733); the driver's two readers of the new ids, `0dba1336` (#1742) and `aa5ff6e1` (#1744) |
| **#1507**: the completion boundary, in three slices | `760386ef` (#1748), `c9b44204` (#1749), `f3b1e8c1` (#1750); the map `1910d6e9` (#1746) |
| **§3.3's instruments** (driver-side, except #1716) | #1714 `e50f0008`, #1718 `27f57002`, #1696 `6d175e9c`, #1724 `76746200`, #1716 `48042621`, the Prefect-log fallback `c7477a00` (#1745) |
| **The named debts that landed** | #1701 `d88f1fe6`, #1691 `edcd4bba`, #1722 `10126314`, #1448 `93ca3572`, #353 `aa7262c4`, #1732 `2addbee7` |
| **#1720, lineage** | `7acc2bc1` (#1753), `7e7ef1d6` (#1760), `ffb9f613` (#1761) |
| **#1754**: a paused run ends the sequence uncancelled | `41a60965` (#1759) |
| **The deploy's own two findings** | `1abe3666` (#1762): the recorder loads the deploy's secrets, and `all` rebuilds every agent service |
| Docs | the plan and its revisions (`343857f6`, `ca784a33`, `1d6a512c`); the 1.8.2 release package (`90efc467`, `bb8d0aa5`) |

**The deploy was made twice.**
- **The first attempt was from `ffb9f613`.** It exited 1: the deploy recorder failed, and han was not
  rebuilt. Both are fixed in #1762.
- **No cycle ran on the first attempt.** The set's deploy is the second, from `1abe3666`.
- **Its first cycle was #176's smoke** (`cyc_3d28edb8333e`: the `smoke` squad, `hello_squad`,
  `selftest`), which completed in 27 s (§7a item 3 of the plan). It is not a set cycle.
- The first attempt's container logs are kept at
  `~/squadops-deploy-logs/deploy-1-9-ffb9f613-before-redeploy-20260929T233810Z/`.

**What the deploy does not carry,** stated so that silence cannot read as shipped:
- **#1522 and #414** are correction-path behaviour changes. They land after this set reads, each with
  its own counted roll, or move to 2.0 (decision 3).
- **#567 moves to 2.0.** Its gate, a replay over every stored real emission, cannot run: no complete
  emission is stored anywhere (#567's comment of 2026-09-29; #1756).
- **#1031 moves to 2.0**, because it is not behaviour-neutral (§7a item 8). #1755 and #1757 are 2.0's.
- **Item 12, the convergence replay (§3.5), is not built.** It is driver-side and runs on the idle box
  with its predictions registered first; building it is the owner's call at this registration.

---

## 3. The exercise plan, stated before the first diagnostic

### 3a. The bar

| id | claim | blocking on | typed field |
|---|---|---|---|
| **L1** (#1268) | the loop remains able to produce a valid running result. A counted roll whose contentless emission is **not recovered** breaches it | every counted roll | `loop_texture.contentless_emissions`, the count beside the recovered flag |

### 3b. The live predictions

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **Behaviour held equal** (#1507, plan §3.6) | the six counted rolls and the diagnostics' own readouts, read against 1.8.2's | a counted roll rejected where 1.8.2's arm accepted (functional yield below **six of six**); L1 breached; or any diagnostic reading otherwise than on A′ where its fault is unchanged (compile-loop, false-criterion, redelivery, own-frame on both stacks) | that moving `execute_run`, `execute_cycle` and the framing gate out of the executor changed nothing a cycle does, on this deploy, on both stacks |
| **Campaign readiness, re-read** (1.8.2's claim) | `unattended-chain`: 1.8.2 §3b's row, verbatim | any ghost generation, any run left `running`, a hang past its bound, or a manual step | that the claim survives the extraction. The chain's end of each cycle now passes through `CycleCompletion` |
| **Round identity** (#1697) | every correction round's `corr-` and `repair-` ids across the set; `repeated_round_ids`; each refund's round in `refunded_rounds` | two dispatches in one run sharing an id; a non-empty `repeated_round_ids`; a refund not joined to its own round | that a refund's re-take and the refunded repair are two records, not one (the 1.8.2 finding §11d) |
| **The dev lane reaches its seam** (#1716) | `dev-lane-fastapi-react` and `dev-lane-nextjs`: the fault's `APPLIED` line after self-evaluation, then the dev repair's revision form and its retest | the fault's defect absent from what the task hands on (self-evaluation repaired it, as on A′, §11h); or the seam unreached after its two-run budget | that dev × React and dev × Next.js can be supplied at all. A′ could supply neither |
| **The contested result, the compile loop, redelivery** | `false-criterion`, `compile-loop`, `redelivery`, as 1.8.2 §3b and §3d registered them, including §11a's wording for compile-loop | as registered there | that the 1.8.2 readings hold on 1.9's code |

**A falsified prediction or an unreached seam stops the set, and the plan is revised in the open.**
A counted roll's rejection is read by its signature before anything else; a rejection that 1.8.2's arm
also produced on the same signature is texture, not a falsification. The judgment is made in §10, per
roll, from its record.

### 3c. N, read as texture (decision 5)

The definition, the cells and the three counting rules are **1.8.2 §3c's, verbatim**:
- a successful scoped revision transaction, verified and persisted under its verified identity;
- the cells are qa × React, qa × Next.js, dev × React and dev × Next.js;
- a scoped rewrite of more than half of a file does not count;
- a qa re-take counts under its `qa_retake_revision_form`.

**Differences from 1.8.2:**
- **N does not gate this set.** It is counted, reported per cell, and carried to 2.0's flip decision
  as the fourth count.
- **Two counting fixes are in** (decision 5):
  - #1697 ids keep two rounds that share an index apart;
  - #1724 records a re-take's verification, so a re-take whose checks all passed is countable.

**Supply.** Predicted from 1.8.2's, with dev × Next.js supplied for the first time by #1716's fault:

| cell | supplied by | expected |
|---|---|---|
| dev × React | `dev-lane-fastapi-react` | 1–2 |
| dev × Next.js | `dev-lane-nextjs` | 1–2 (A′: 0, unreachable) |
| qa × React | `own-frame-then-prose-repair` | 1–2 |
| qa × Next.js | `own-frame-then-prose-repair-nextjs` | 1–2 |

### 3d. The seam invariants: eight diagnostics

These are **1.8.2's diagnostics, unchanged in fault, invariant, readout and loaded checks**. Each
config's header says so, and the configs differ from 1.8.2's only in the name, the pre-registration
and the notes. Each has a **two-run budget**, and the chain runs once. **A seam not reached after its
budget stops the set.**

| diagnostic | fault(s) | invariant | N cell |
|---|---|---|---|
| `unattended-chain` | K = 4 React cycles: a cancel, a `neo` crash, `handler_hang` | 1.8.2's claim | none |
| `redelivery` | `qa_suite_own_frame_failure`, `qa_repair_process_killed` | #1627's rule and #1626's containment | none |
| `compile-loop` | `compile_loop_two_type_errors` (nextjs_ts) | SIP-0086 §12a | none |
| `false-criterion` | `false_criterion_alias_import` (nextjs_ts) | SIP-0096 §17a | none |
| `own-frame-then-prose-repair` | `qa_suite_own_frame_failure`, `repair_prose_only` | L7, L4, L5, and #1697's shape | qa × React |
| `own-frame-then-prose-repair-nextjs` | the same, fill mode | the same on the App Router stack | qa × Next.js |
| `dev-lane-fastapi-react` | `dev_join_response_omits_declared_fields`, **now held through self-evaluation (#1716)** | the dev lane | dev × React |
| `dev-lane-nextjs` | the same | the same on the App Router stack | dev × Next.js |

**Not in this set:** 1.8.2's `absent-suite`, `path-prefix`, `absent-suite-then-false-claim`,
`contentless-builder` and `contentless-builder-all-attempts`. Plan §4 names the eight above as the
diagnostics that exercise the run spine the extraction moved. The five exercise seams no 1.9 change
touched, and each read cleared on A′, except F1, which is ruled unreachable (§11i of 1.8.2).

### 3d′. One mechanism prediction per 1.9 change

Each is read where its mechanism shows, never as a rate. **Predicted-silent** ones say so before the
fact.

| change | mechanism predicted | read from |
|---|---|---|
| **#1507** (the three slices) | **predicted silent**: the same cycle, the same way. The one new fact is that every cycle's end names a `CycleStopReason` at `CycleCompletion`: `sequence_completed` on an accepted roll, and the gate's reasons where it stops | no log line is registered for `CycleEnd` in 1.9 (it is a view with no consumer); the readings are the rolls' own |
| **#1754** | **predicted silent**: no set cycle is deferred by a duty window or a focus-lease conflict | a run paused mid-set would read `run_paused`, uncancelled |
| **#1697** | every correction id carries `-s<NN>-`; a refunded round's re-take has its own id | §3b's round identity row |
| **#1716** | the dev fault's defect is present in what the develop task hands on, after its self-evaluation | the fault's `APPLIED` line; the first verification's failure on the join response |
| **#1745** | **predicted silent** while no rebuild happens: `log_sources` reads `docker` for every window | each record's `log_sources` |
| **#1714, #1718, #1696, #1724** | the driver's own: the #1699 guard, `did_not_bite`, the marker self-check, re-take verifications | the driver's refusals and the records' fields |
| **#1720, #1753** | every set cycle carries `deploy_id: dep_d413c36959ab`; every agent's heartbeat revision matches it for the whole set | the cycle detail; `/health/agents`, read by hand at each launch (the driver's identity asserts the images, and does not read the heartbeat) |
| **#353** | **predicted silent**: every agent's prompt pack verifies against its build stamp | the `353` loaded check; a `HashMismatchError` anywhere would falsify it |
| **#1448, #1701, #1691, #1722** | **predicted silent** on the cycle path. #1701 removes a duplicate warning on a cancel, and the chain's cancel shows one line | the chain's cycle 2 runtime log |

### 3e. Where each reading is read, and whether the source can hold it

This is 1.8.2 §3e, with one change and one addition:
- **Container logs are read first, and Prefect's stored log is the fallback** where a rebuild has
  replaced the container (#1745). Prefect cannot hold two kinds of line, and a record read from
  Prefect names both as **unaskable**:
  - the redelivery refusal;
  - a fault's `APPLIED` line written as its process dies.
- **The deploy record** (`deploy_records`) holds the images and the model digests the set ran on,
  and each cycle references it. The readings do not depend on it; it is lineage.
- **LangFuse still cuts every generation's stored text at 10,000 characters** (#1756, the framework's
  own cap), so no reading is registered on it.

### 3f. Texture

1.8.2 §3f is carried. **A field whose producer did not run reads UNASKABLE, never NO and never zero**
(#1593).

---

## 4. FastAPI+React (`fullstack_fastapi_react`): four counted rolls

Config `docs/plans/verification-sets/1-9-0-fastapi-react.yaml`, pinned to §1. Rolls 1–4, one roll per
driver invocation.

## 5. Next.js+TS (`nextjs_ts`): two counted rolls

Config `docs/plans/verification-sets/1-9-0-nextjs.yaml`, with overrides `build_profile=nextjs_ts` and
`development_profile=nextjs_ts`. Rolls 1–2.

## 6. The shakeout loop and its exit

**The eight diagnostics are the deploy's shakeout.** The exit rule, stated before the first launch,
is **a pass of the eight on one deploy with no new seam finding.**
- A finding becomes a fix, and the deploy moves.
- This registration is then void and re-made on the new deploy, and nothing from the superseded
  deploy counts.
- **Budget: three rounds.** The record reports how many it took.
- Every readout counts non-execution (skips, by reason) beside failure (#1261).

**Round 1:** the deploy at `1abe3666`.

## 7. Gate constant

The 1.6.3 §6 constant, verbatim in each set config's `gate_notes`, and `--as-agent`. Gates never
self-approve, and the decider is recorded per roll.

## 8. Prohibited while this set is open

- **No framework change under `src/` or `adapters/`, no config, profile or prompt-asset change, and
  no deploy move.** Each voids this registration.
- Docs changes, and driver changes that cannot alter a reading, are free.
- **No launch-and-cancel to read anything** (#1648).
- **No manual cancel within the chain's quiet timeout of a launch.**
- **No rebuild while the set is open.** A rebuild replaces the containers, and although #1745's
  fallback keeps the texture readable, the two kinds of line Prefect cannot hold would be lost.
- **The driver runs from its own checkout** (`squad-ops-driver`), detached at this registration's
  merge commit. The main checkout stays on `main` while any driver process runs.

## 9. Drift the record must declare

- **The image IDs** against A′'s: `runtime-api 793d9fd6dc1a`, `max 028cbd461ea1`, `neo
  2c97c2d6946e`, `nat 990a45dbae9b`, `bob d894a556280a`, `eve f3b72d5d754d` and `data b60aa428274d`,
  all rebuilt. A′'s container logs and image IDs are kept at
  `~/squadops-deploy-logs/deploy-1-9-before-20260929T230705Z/`.
- **The code between A′ and this deploy** is §2's twenty-nine commits. Every behaviour change in them
  is named in §3d′. Everything else is either the extraction (claimed behaviour-neutral, which is
  what §3b's first row reads) or driver and docs changes.
- **`resolved_config_hash` and `squad_profile_snapshot_ref`: unmoved**, each re-read on this deploy.
- **The configs** differ from 1.8.2's in their name, pre-registration, notes, the counted arms' pins,
  and the 1.9 checks appended to the counted arms' `runtime-api` and `neo` blocks. The diagnostics'
  faults, invariants and loaded checks are 1.8.2's.

---

## 10. Readings: appended as they land

### d1: `compile-loop`, run 1 of 2. `cyc_f4fca4758e83`, 2026-09-29 20:16–21:14 ET. **Cleared.**

- **Verdict:** `accepted`, with **zero correction rounds**.
- **Fault:** `compile_loop_two_type_errors` was applied to the develop tasks (for example, `m000`
  grew from 2,228 to 2,366 characters). The seam was reached: the task compiled clean through its
  self-evaluation passes (seven recorded under `development_develop_handler`), and no correction
  round ran.
- **Against the registration:** this reads as 1.8.2's A′ d1 read, so on this diagnostic the
  behaviour held equal across the extraction (§3b, first row).
- **Records location:** the record was written under `1-8-2-diagnostics/`, by §11a's defect, and
  is moved to `1-9-0-diagnostics/` after the eighth diagnostic (§11b).

### d2: `false-criterion`, run 1 of 2. `cyc_75be94aadbd3` / implementation `run_6feedfbf7eaf`, 21:19–22:03 ET. **Cleared.**

Record `false-criterion/shakeout-20260930T020336Z.json`.
- **Outcome:** `blocked_unverified`, 1 of 15. There was one correction round, and it ended at round
  0 as **`contested_check`**. The run's failure reason names the planted check:
  `acceptance:declared_imports on app/api/runs/route.ts (vc-declared-imports-lib-alias)`.
- **The fault:** planted its row (`rows 0 -> 1`) on every evaluation of the develop task's first
  attempt.
- **The dispute:** captured on the develop task (`by: dev`, round 0). The analyzer confirmed it: 1
  confirmed, 0 rejected, 0 unruled, 0 unmatched.
- **The import:** unchanged. The develop task's stored `app/api/runs/route.ts` (`art_df072eaa45a3`)
  imports through `@/lib/errors` and `@/lib/store`, with no relative import.
- **The passes:** three, each answering `form: none`.
- **Against A′ d2** (`cyc_959b9e726a4e`), the same in every clause of the invariant, with two
  differences, both the model's own choices:
  - **2 of 15 there, 1 here.** A′'s checks ran on two develop emissions; here they ran on one.
  - **The unresolved import:** A′'s named `@/lib/store`, and this one names `@/lib/errors`.
- **Reading: YES.** Every §3b falsifier is absent:
  - no refund without a dispute (`refunded_rounds` asked, none);
  - the dispute was read;
  - no rejection;
  - the import was not degraded.
- **The 1.9 mechanisms, where this cycle shows them:**
  - **#1697:** the round's ids are `corr-run_6feedfbf-00-s00-data.analyze_failure` and
    `…-00-s00-governance.correction_decision`. No repair was dispatched, and `repeated_round_ids`
    was asked and returned none.
  - **#1720:** the cycle carries `deploy_id: dep_d413c36959ab`.
  - **#1745:** `log_sources` is `docker` for both.
  - **#1753:** read by hand at 22:05 ET, in the gap before d3. All eight agents were `online` at
    `1abe3666`, `revision_matches_deploy: true`. **It was not read at d1's or d2's launch**, as
    §3d′ asks; those two rest on the deploy-time read (§2) and each cycle's `deploy_id`.
- **Texture:** one contentless emission, where A′ had none. It is a self-evaluation pass of 268
  characters with no fence (`development_develop_handler:self_eval`), one of the three `form: none`
  answers. A pass that finds nothing to change has no fence to carry. This is a diagnostic, not a
  counted roll, so L1 does not read it.

### d3: `redelivery`, run 1 of 2. `cyc_9ee4b3bb2d19` / implementation `run_b6a8121ca0b9`, 22:07–23:08 ET. **Cleared.**

Record `redelivery/shakeout-20260930T030822Z.json`.
- **Outcome:** `accepted`, 21 of 21, as on A′.
- **The kills:** both faults applied. The own-frame fault landed on the two suites (`m005`, `m006`)
  and was routed to the qa repair (L7). Both faulted repairs were killed, and each redelivery was
  refused as a typed `FAILED` for the repair's own id, not run again (#1627). Both runs completed,
  and none was left `running`.
- **Round identity (#1697), on the case that collided on A′.** A′'s two repairs shared one id,
  `repair-run_97f19dba-00-qa.test_repair` (1.8.2 §11d). Here every task of the two rounds has its
  own id:
  - `corr-run_b6a8121c-00-s00-data.analyze_failure`
  - `corr-run_b6a8121c-00-s00-governance.correction_decision`
  - `repair-run_b6a8121c-00-s00-qa.test_repair`
  - the same three at `-s01-`.

  Each refund names its own round ("refunded (round s00)", "(round s01)"), and
  `repeated_round_ids` was asked and returned none. **§3b's round-identity row holds here.**
- **The qa re-takes:** both are accepted edits.
  - `backend/tests/test_runs.py`: 1,277 of 8,430 characters (15%), `structural`.
  - `frontend/src/__tests__/runViews.test.jsx`: 189 of 6,867 (3%), `anchored`.

  **#1724 recorded each re-take's verification:** the suite executed with exit 0, 7 of 7 checks
  passed, and there were no failed checks. So both are countable qa × React candidates under §3c's
  rules, where A′'s were read by hand.
- **The child parse crash** (item 3): not forced, none occurred. **UNASKABLE.**
- **Reading: YES.**
- **1.9 mechanisms:**
  - `deploy_id: dep_d413c36959ab` (#1720);
  - `log_sources` is `docker` for both (#1745);
  - no contentless emission, and no task timeout;
  - heartbeats read at 23:09 ET, before d4: eight `online` at `1abe3666`, all matching (#1753).

### d4: `unattended-chain`, run once. 23:12–04:37 ET (5 h 25 m; A′ took 5 h 41 m). **YES on every row of the campaign-readiness claim.**

Record `unattended-chain/chain-20260930T083739Z.json`, with `cycle-0N-20260930T…` for each cycle.
`resumes 0`, `stopped` none. Every cycle was assessed, and there was no manual step. The box was
quiet before the first launch and after every cycle. The gate was approved by the driver under the
set's gate notes.

| cycle | fault | result |
|---|---|---|
| c1 `cyc_c6faa57c49d9` | none | accepted, 20 of 20, after two correction rounds. The rounds' ids are distinct at every stage: `corr-`, `repair-` and `retest-run_3581cad7-00-s00-…` and `…-01-s01-…` (#1697) |
| c2 `cyc_baa44d5f73d4` | cancel at develop, 00:50:47 ET | **the wait ended at 00:50:55** (`dispatch_wait_ended_by_cancel`, 8 s). The run is `cancelled`, with ghosts at **0 emissions and 0 late replies**, and the box was quiet 1 s after. Four stranded focus leases were released (#529) |
| c3 `cyc_48b45a9af31f` | `neo` killed while it ran the develop task, 01:28:22 ET | the redelivery was refused as typed (`task-run_3c0b2c31-m000-development.develop`); accepted, 21 of 21 |
| c4 `cyc_3ab2cf9c55ce` | `handler_hang` | seam **YES**: three develop tasks (`m000`–`m002`) each failed at 1,800.0 s as a typed `task_timeout`; accepted, 21 of 21 |

- **Against the claim** (§3b's second row, 1.8.2's verbatim): no ghost generation, no run left
  `running`, no hang past its bound, and no manual step. The claim survives the extraction. Each
  cycle's end now passes through `CycleCompletion`.
- **#1701:** no `Failed to transition run … to cancelled` line anywhere in the runtime-api's log
  since the set began. The cancel logs its own lines once.
- **#1754:** predicted silent, and silent: no run paused.
- **#1720:** all four chain cycles carry `deploy_id: dep_d413c36959ab` (`squadops cycles show`, each read).
- **Texture:** no task timeout in c1, where A′'s c1 hit the bound on a qa re-take. No contentless
  emission in any cycle.
- **Heartbeats** read at 04:38 ET, before d5: eight `online` at `1abe3666`, all matching. That
  includes `neo`, restarted by c3's fault.

### d5: `own-frame-then-prose-repair-nextjs`. **Cleared on run 2**, where A′ cleared on run 1.

**Run 1:** `cyc_1d359f7fa22c` / `run_8523f2ba1395`, 04:41–05:53 ET. **Seam not reached.**
- The own-frame fault applied to `m006`'s suite, on its first attempt.
- The round's analysis named `lib/store.ts`, a file the workspace does not have. It was refuted
  and told to the decision (#968).
- The decision routed the round to the **dev** repair, narrowed to `app/api/runs/[run_id]/route.ts`.
  The dev repair's retest failed. The cycle was accepted later, 16 of 16.
- L7 was unreached because of the analyzer's diagnosis, not the router. On this stack the own-frame
  route is taken on analyzer–decision unanimity (#1581). That is A′'s route too, and here the
  analyzer did not implicate the suite. The runner's own-frame stamp (`qa_owned_routed`) did not
  fire on this stack in either run, nor was it A′'s route.

**Run 2:** `cyc_359759afe0af` / `run_34c19ad936a9`, 05:57–07:08 ET. **Cleared.**
- **Outcome:** `accepted`, 19 of 19.
- **L7 YES:** the faults applied to both suites (`m006`, `m007`). Each round was routed `own_artifact`
  on analyzer–decision unanimity, to its own suite.
- **L4 YES:** both prose-only repairs (48 characters each) were refunded, "round s00" and "round
  s01", with distinct ids. `repeated_round_ids` was asked and returned none.
- **The qa re-takes:** both accepted edits (anchored, about 1% each):
  `__tests__/test_runs_happy.test.ts`, and `__tests__/test_runs_errors.test.ts`. **#1724 recorded
  each re-take's verification:** vitest executed, exit 0, and no failed checks. That makes **two
  qa × Next.js candidates**, where §3c expected 1–2.

**The judgment.** I read this as the same reading as A′'s, within the two-run budget the
registration gives every diagnostic. The mechanism both runs took is A′'s. Run 1's miss is the
analyzer's call on a round the fault had set up. The extraction did not move that seam.
- It stands as texture, not as a falsification of §3b's first row.
- A reviewer who reads "cleared on run 2" as "reading otherwise than on A′" has the record to say
  so.

**Texture:** the two contentless emissions are the planted prose-only repairs, both refunded. This
is a diagnostic, so L1 does not read it.

### d6: `own-frame-then-prose-repair`, run 1. `cyc_a045fa94c30f` / `run_8b0b06683639`, 07:12–08:08 ET. **Cleared, on its own terms.**

Record `own-frame-then-prose-repair/shakeout-20260930T120814Z.json`.
- **Outcome:** `accepted`, 21 of 21.
- **L7 YES:** each suite's own-frame failure was routed to its own suite by the runner's stamp
  (`qa_owned_routed`, #1130):
  - `backend/tests/test_runs.py` (a `TypeError` at `test_create_run_success:24`);
  - `frontend/src/__tests__/views.test.jsx`.
- **L4 YES, read directly.** On A′ this row read UNASKABLE: the two faulted repairs shared one id
  (`repair-run_99242d1e-00-qa.test_repair`), and it cleared only by the owner's ruling (1.8.2
  §11f). Here each repair has its own:
  - `repair-run_8b0b0668-00-s00-qa.test_repair`;
  - `…-00-s01-…`.

  The refunds name "round s00" and "round s01". **This is #1697's prediction on the diagnostic that
  was its shape** (plan §4). No ruling is needed.
- **The qa re-takes:** both accepted edits:
  - `backend/tests/test_runs.py`, 181 of 6,939 characters (3%);
  - `frontend/src/__tests__/views.test.jsx`, 138 of 4,181 (3%).

  Each has a recorded verification: the suite executed, exit 0, 6 and 7 passed, and no failed
  checks. That makes **two qa × React candidates.**
- **Heartbeats** read at 07:09 ET before d6, and at 08:08 ET before d7: all eight `online` and
  matching.

**N so far, as texture (§3c):**
- qa × React: 4 (d3's two and d6's two);
- qa × Next.js: 2 (d5);
- dev × React and dev × Next.js: their diagnostics are next.

### d7: `dev-lane-fastapi-react`. **Not reached after two runs: the fault never applied. Ruled UNASKABLE on this deploy (§11c).**

**Run 1:** `cyc_1e1c9364efe3` / `run_f59e47975fd7`, 08:12–09:15 ET. **Run 2:** `cyc_7a67a1c5b903` /
`run_a7a8b0253361`, 09:19–10:08 ET. Both were accepted, 20 of 20. Run 1 had one correction round,
on a qa suite; run 2 had none.

- **The fault did not bite in either run.** `dev_join_response_omits_declared_fields` logged
  `DID NOT BITE … emission_unchanged` on all four develop tasks of each run. #1718's instrument read
  it, and the seam is UNASKABLE, "neither YES nor NO" (#1588).
- **Why:** the fault finds the join handler by a literal path, a `/join` decorator in Python. Both
  runs' authored manifests named the join `POST /runs/{run_id}/participants` ("join a run with a
  participant name"), with leave as `DELETE /runs/{run_id}/participants/{participant_name}`. There
  was no `/join` route to rewrite.
- **How often:** 344 of the 395 manifests in the vault name a `/join` path, and 23 name the join as
  a `/participants` collection. Those 23 come from counted rolls and diagnostics alike, so this
  diagnostic does not push toward the naming. Two in a row was chance, on a defect: the fault should
  key on the join the manifest declares. That is **#1774**.
- **The set stopped** at 10:08 ET on §3d's rule. It was resumed on the owner's ruling (§11c).
- **#1716's prediction is not read on this deploy.** The fault's defect never entered a develop
  emission, so whether it survives self-evaluation was not asked. The dev × React cell stays empty
  here.

### d8: `dev-lane-nextjs`, run 1. `cyc_98a316402a1b` / `run_7b9430c961fb`, 21:06–22:05 ET. **Cleared: the dev lane reached its seam on the App Router stack.**

Record `dev-lane-nextjs/shakeout-20261001T020536Z.json`. The set resumed with this run on §11c's ruling.
- **#1716's prediction, read on Next.js: YES.**
  - The fault **applied** on `m000`'s first attempt (`app/api/runs/[run_id]/join/route.ts`, 5,114 →
    5,158 characters). The defect was in what the develop task handed on.
  - The qa task's join probe rejected the app (`vc-probe-api-runs-join`: "response missing key(s)").
  - The round was routed to the **dev** repair, narrowed to the probe-owned slot
    (`app/api/runs/[run_id]/join/route.ts`, #1015). Its revision form is an accepted anchored edit,
    179 of 1,366 characters (13%).
  - A′ could not reach this seam (1.8.2 §11h).
- **The repair did not converge.** Its patch verification passed (12 checks), and the qa suite's
  retest failed. The patch was discarded, which is today's path, and was never persisted (no
  `patch_candidate_identity` line).
  - Round 1 carried one failure, clearing 2 and adding 2. The run ended `plan_defect` at round 1:
    `rejected`, 16 of 18, with `vc-probe-api-runs-join` and `tests_pass` unmet.
  - This is a diagnostic, so the rejection is texture. Its signature is the join probe the fault
    planted, still failing after the discarded repair.
- **N (§3c):** not countable. A dev × Next.js transaction was produced and verified, but §3c counts
  only a transaction **persisted** under its verified identity, and this one's retest discarded it.
  The cell stays at 0 on this deploy. That is texture, since N does not gate (§3c).
- **#1522, read forward:** its completeness guard would also have discarded this repair. The round
  failed a probe row, and the retest, which runs only the suite and its authenticity rows, does not
  evaluate one.
- `repeated_round_ids` was asked and returned none; the rounds are `-s00-` and `-s01-`. There was no
  contentless emission and no task timeout.

### The diagnostics' close: `all_eight_ran`, 22:05 ET

- **Read:**
  - six cleared: d1, d2, d3, d5 (on run 2), d6 and d8;
  - the chain read YES on every row (d4);
  - d7 is UNASKABLE on this deploy (§11c).
- **No new seam finding.** d7's miss is the diagnostic's own fault (#1774), not a framework seam.
  By §6's exit rule this is the shakeout's pass, in one round on deploy `1abe3666`.
- **Heartbeats** read before every launch from d3 on: all eight `online` and matching each time.

**§11b executed at 22:06 ET:**
- **The 1.9 records moved.** All 36 files the set wrote under `1-8-2-diagnostics/` were copied to
  `1-9-0-diagnostics/<name>/`, each copy checked by sha256, and then the sources removed.
- **1.8.2's seven overwritten files were restored** from `squadops-1.8.2-records.tar.gz` (sha256
  `791ad261…`, as the package records): six `shakeout-deploy.json` and `unattended-chain/chain-state.json`.
  All 31 of 1.8.2's files in those directories now match the tarball byte for byte. The empty
  `dev-lane-nextjs` directory, which the 1.9 run had created, was removed.
- **The driver checkout moved** from `7fdda5b1` to `93253694`. The only difference between the two
  on `scripts/dev`, the counted configs, `src` and `adapters` is #1765's four
  `convergence_replay` files, which the driver does not import. `verification_set_driver.py` and
  both counted configs are identical.
- **The counted set launched at 22:07 ET.** Roll 1 is `cyc_20a01ea59964`, with HEAD pinned at
  `93253694` and config hash `a79f58658cd8`.

### React roll 1: `cyc_20a01ea59964`, 22:07–23:01 ET. **Accepted, 21 of 21.**

- **Outcome:** zero correction rounds, no contentless emission (L1 holds), no task timeout.
- **1.9's loaded checks are the deployed code.** The record's preflight compared each one with this
  registration's pin, and all matched:
  - `runtime-api`: `1697` (repair ids carry `-s00-`), `1754` (`run_paused`), `1720`;
  - `neo`: `353` (the prompt pack verifies, 33 entries) and `1753` (revision `1abe3666`).
- **Lineage:** `deploy_id: dep_d413c36959ab`; logs read from docker for both sources.

### React roll 2: `cyc_189cb78ce86b` / `run_2765fc519058`, 23:05 ET–00:13 ET. **Rejected, 20 of 21.**

- **The signature:**
  1. The frontend suite (`m006`'s `qa.test`, `src/__tests__/runs.test.jsx`) failed two RunDetail
     tests: "displays run details, allows a successful join, then shows duplicate error", and
     "displays a not-found message for an unknown run id".
  2. Round 0 routed it to the **dev** repair. Its revision is an accepted anchored edit of
     `frontend/src/views/RunDetail.jsx`, 132 of 4,311 characters (3%). Patch verification passed on
     10 checks.
  3. **The retest failed the same two tests**, so the repair was discarded, today's path.
  4. Round 1's re-dispatched suite failed four. They were the same two behaviours, once in
     `src/__tests__/runs.test.jsx` and again in a second copy of the suite the re-authoring wrote at
     `src/tests/runs.test.jsx`.
  5. The run ended `plan_defect` at round 1: "2 failure(s) carried from round 0 without progress (0
     cleared, 2 added)". `vc-suite-passes` is adverse.
- **Not the extraction's path.** Between v1.8.2 and `1abe3666`, the correction modules changed only
  by #1697's round-id threading (`0739af1d`). The executor's own changes on this path are the same
  threading. #1507's slices moved `execute_run`, `execute_cycle` and the framing gate, not the
  repair, the retest or the repeat rule.
- **A known signature.** The same `plan_defect` "carried without progress" rejection ended three
  earlier counted rolls: 1.8.0 React roll 6, 1.8.0 Next.js roll 1, and 1.8.1 React roll 1. Across
  the 97 counted rolls stored, 74 were accepted. 1.8.2's arm produced no rejection, so §3b's texture
  clause, which covers only signatures 1.8.2's arm produced, does not apply by its letter.
- **#1522 would not have changed it.** The retest cleared nothing.
- **L1 holds:** no contentless emission, and no task timeout. `repeated_round_ids` was asked and
  returned none.
- **§3b's first row, by its letter:** functional yield can now be at most five of six, against the
  registered six of six. The set was paused before roll 3 (00:14 ET) for the owner's ruling (§11d).

## 11. Amendments after the first launch

### 11a. The diagnostics' records go to the 1.9 line's own directory (2026-09-30)

**What changed.**
- The eight diagnostic configs carried 1.8.2's `records_dir`
  (`var/verification_sets/1-8-2-diagnostics/<name>`) from the configs they were generated from.
  Their records were landing beside 1.8.2's. They now point at
  `var/verification_sets/1-9-0-diagnostics/<name>`.
- The records written before the fix (d1 `compile-loop` and d2 `false-criterion`) are moved
  there unchanged.
- The two counted arms were unaffected: they use the default location
  (`var/verification_sets/1-9-0-<arm>`).

**The driver checkout moves.** *(Its timing is superseded by §11b: it does not move until the
eighth diagnostic ends.)* It moves from `7fdda5b1` to the commit carrying this fix, detached,
in the sequencer's gap between two diagnostics. Nothing else moves with it: the diff is the eight
`records_dir` lines and this document. No framework path changes, and no reading can.

**Evidence.** d1's record path, `var/verification_sets/1-8-2-diagnostics/compile-loop/shakeout-20260930T011458Z.json`.

**Who ruled.** This is a docs-only fix of the registration's own configs, made under §8's rule
that driver and docs changes which cannot alter a reading are free. It is recorded here so the
records' location, and the checkout's move, are part of the registration's history.

### 11b. The checkout moves after the eighth diagnostic, not between two (2026-09-30)

**What changed.**
- §11a moved the driver checkout in the sequencer's gap between two diagnostics. That timing was
  wrong. The sequencer loads a diagnostic's config *before* its gap
  (`var/1-9-0-logs/run_1_9_0_diagnostics.py`, the loop's first two lines). A move in the gap would
  split the two readers:
  - the driver would write the record under `1-9-0-diagnostics/`;
  - the sequencer would look for it under `1-8-2-diagnostics/`, find none, and read "seam not
    reached". That spends the second run and stops the set on a reading nobody made.
- So the checkout stays at `7fdda5b1` until the sequencer notes `all_eight_ran`, and all eight
  diagnostics write under `1-8-2-diagnostics/<name>/`. It moves to `93253694` (#1766) before the
  first counted roll launches; the counted arms' configs are the same at both commits.
- Once the eighth diagnostic ends, every 1.9 record moves to `1-9-0-diagnostics/<name>/` unchanged.

**Why no reading moves.** The shakeout and chain paths never read a directory's earlier records.
The driver's one directory read is the placement window's latest-record lookup, which no diagnostic
runs. The chain runs without `--resume`, so it starts from a fresh state and never from 1.8.2's.

**What it cost, and the restore.** The driver writes two files under fixed names in a records
directory. Each 1.9 run overwrote 1.8.2's copy of them in the diagnostic's own directory:
- `shakeout-deploy.json`, the shakeout's deploy identity, in each shakeout diagnostic's directory;
- `chain-state.json`, in `unattended-chain/`.

1.8.2's copies are restored from the line's records on the v1.8.2 Release. That is
`squadops-1.8.2-records.tar.gz`, whose sha256 `791ad261…` is the one the package records
(`site/content/releases/v1.8.2/package.yaml`) and was checked before use. The 1.9 copies move with
the 1.9 records.

**Evidence.** The sequencer's loop, above. Also the two overwritten identity files' timestamps: 20:16
and 21:18 ET, the launches of d1 and d2.

**Who ruled.** Mine, under §8, as in §11a: this corrects a docs amendment's timing, and no
framework path, config the driver reads during a run, or reading moves.

### 11c. The dev lane on FastAPI+React is read UNASKABLE on this deploy, and the set resumes (2026-09-30)

**What changed.** §3d's rule stopped the set when `dev-lane-fastapi-react` did not reach its seam
after two runs (§10, d7). The miss is a defect in the diagnostic's own fault, not a framework
finding. The fault keys on a literal `/join` path, and both runs' authored manifests named the join
otherwise (#1774). So:
- d7 is recorded **UNASKABLE on this deploy**. It is neither cleared nor a falsification of §3b. The
  extraction's claim is unaffected, since no seam the extraction moved was asked.
- **The set resumes as registered:** `dev-lane-nextjs` (d8, whose fault keys on a `join/route.ts`
  path, the naming most Next.js manifests use), then the six counted rolls.
- **#1774 is fixed in the rebuild that #1522 needs after the set**, and both dev-lane diagnostics are
  re-run on that deploy. #1716's prediction is read there, outside this registration, and stated as
  such.
- This is not the shakeout loop's "a finding becomes a fix, and the deploy moves" (§6). The finding
  is in the test harness, and moving the deploy for it would void eight diagnostic readings to
  re-ask none of the extraction's questions.

**Evidence.** §10's d7 reading, the two records `dev-lane-fastapi-react/shakeout-20260930T131528Z.json`
and `…140834Z.json`, and #1774.

**Who ruled.** The owner, 2026-09-30 at 21:06 ET, choosing "Ruled unaskable, resume" from the
options presented: this, a fix with a re-registration, or skipping d8 as well. Precedent: 1.8.2
§11h, where the dev lane on A′ was ruled unreachable by construction and the set continued. The set
resumed at 21:06 ET with d8.

### 11d. React roll 2's rejection: the counted set resumes, and the yield bar is ruled at the cut (2026-10-01)

**What changed.** §3b says a falsified prediction stops the set. Roll 2's rejection makes the
registered yield, six of six at 1.8.2's level, unreachable. The set was paused before roll 3 with
the STOP file at 00:14 ET, and the reading went to the owner.
- The rejection's path is unchanged in 1.9 except for round ids.
- Its signature is one 1.8.0 and 1.8.1 rolls produced.
- #1522 would not have changed it.

**The ruling.**
- Rolls 3–6 run as registered.
- Roll 2 is recorded as a rejection on a known signature, on a path the extraction did not move.
- **The yield bar is ruled at the cut**, on all six rolls, with this reading beside it. It is not
  read as met. The cut record states the yield as measured.
- The counted set resumed at 03:05 ET with roll 3 (`cyc_cf13ebda0daa`).

**Evidence.** §10's roll 2 reading: the record `1-9-0-fastapi-react/roll-02-20261001T041300Z.json`,
the vault's three test reports for `m006` and its retest, and `git log v1.8.2..1abe3666` on the
correction modules.

**Who ruled.** The owner, 2026-10-01 at 03:05 ET, choosing "Resume all four, rule at cut" over
"resume, stop on another rejection" and "stop the set now".
