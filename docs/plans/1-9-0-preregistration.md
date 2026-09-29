# 1.9.0 — pre-registration (plan §4, §3.6)

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

*(none yet)*

## 11. Amendments after the first launch

*(none yet)*
