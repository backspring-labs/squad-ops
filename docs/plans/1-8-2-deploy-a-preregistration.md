# 1.8.2 deploy A — pre-registration (plan §4.1, §4.4)

**Rev 4 (2026-09-25, after the third diagnostic): a seam finding, #1697, and the owner's ruling on
it — §11d.**
**Rev 3 (2026-09-25, after the second diagnostic): a second instrument fix — §11c.**
**Rev 2 (2026-09-25, after the first diagnostic): one owner ruling on a falsifier's wording
and one instrument fix — §11. No pin, arm, fault or budget moved.**

**Status: rev 1 (2026-09-25) — the rules, the arms, the diagnostics, the readouts and the pins,
committed on deploy A before any launch. Nothing has launched.** Deploy A was built from `ccc9475d`
at 00:36 ET (one rebuild: `runtime-api` and the nine agents). Every pin in §1 was read from the
deploy or computed by the CLI's own code on its tree (plan §4.4 rule 4); none is carried from 1.8.1.
Once this commit merges, the cut criteria do not move; only readings are appended (§10). If the
deploy moves after it, it is void and re-made, and nothing from the superseded deploy counts.

**What this set measures, in the order the plan ruled (decision 1 = BOTH).**
1. **Campaign readiness — the line's claim**: a cycle is safe to leave running unattended. Read by
   the `unattended-chain` diagnostic and the three unattended seams it depends on (items 3, 10, 15,
   11). If any of these cannot be read, the line does not claim campaign readiness (plan §3.9).
2. **The model-capability tranche**: SIP-0086 §12a (the compile loop) through `compile-loop`, and
   SIP-0096 §17a (the contested result, #1581) through `false-criterion`.
3. **N on A's supply** (SIP-0107 §39.8, re-fixed at 6, §3c): the flip lands on deploy B **only if N
   is met here**; if it is not, the flip moves to 1.9 as a 2.0 decision with the count stated.
4. **The regression bar**: L1 on every counted roll, functional yield reported.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| Counted rolls | **4** on FastAPI+React (§4) and **2** on Next.js+TS (§5), as in 1.8.1 — the regression bar and N's margin (plan §4.1) |
| Bar | **one: L1** (#1268) — blocking on a counted roll whose contentless emission is not recovered |
| **N** (SIP-0107 §39.8) | **6 successful scoped revision transactions across the counted rolls and the diagnostics together, at least one in each required cell** — qa × React, qa × Next.js, dev × React, dev × Next.js (§3c). **Re-fixed here, before any transaction that could count is observed.** 1.8.1's 4 of 6 do not carry |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 → 1.8.1 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React **`a79f58658cd8`**, Next.js+TS **`8e730c8ea169`** — computed by the CLI's own `compute_config_hash(crp.defaults, overrides)` on the deploy's tree and **confirmed by each arm's first launch**, never by a launch-and-cancel (plan §4.4 rule 4, #1648). **Moved** from 1.8.1's `58eed2c52e1f` / `fff4a6435c97` because SIP-0086 §12a change 1 (#1682) added `max_self_eval_passes: 3` to `validated-fullstack` — drift the record declares (§9) |
| `squad_profile_snapshot_ref` | **`2d8d4feb3519a7ec`** — read from deploy A by the driver's own `live_squad_snapshot("full-38")`, not assumed. **Unchanged from 1.8.1**: no 1.8.2 change touched `full-38` |
| Deploy — commit | **`ccc9475d`** — main after #1689, every prelude merge of §2 with main's full CI read green before the next. **A label, not an assertion** (#1296): the image ids are the assertion |
| Deploy — image ids | `runtime-api f22b70abcd73`, `max 028cbd461ea1`, `neo 2c97c2d6946e`, `nat 990a45dbae9b`, `bob d894a556280a`, `eve f3b72d5d754d`, `data b60aa428274d` — **all seven changed** from deploy B″ (§9), each read by `docker inspect` after the rebuild. `joi 89ec34c9f0b0` and `han 1c891e9cd081` were rebuilt with them so no container serves older code; neither is in the set's identity assertion |
| Loaded, not built | Verified per container as a live call with its paired control, never a symbol import (#522, #1425): the 1.8.2 prelude surfaces appended to the counted configs' `runtime-api`, `neo` and `eve` blocks (§3d′), and each diagnostic's own rows |
| Per-task wait | `SQUADOPS__DISPATCH__TASK_TIMEOUT=1800` in `.env`, **required** (item 15, #1675): the compose line refuses to start without it, and both sides of the hang bound read it (#1678) |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider recorded per roll |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-8-2-<arm>.yaml --roll N`; diagnostics via `shakeout --set …-diagnostic-*.yaml`; the chain via `chain --set …-diagnostic-unattended-chain.yaml` |
| Order | **The thirteen diagnostics first** (two-run budget each; the chain once) — they are deploy A's shakeout (§6) — then FastAPI+React rolls 1–4, then Next.js+TS rolls 1–2 |

---

## 2. Preconditions — what deploy A carries

Deploy A carries the 1.8.2 prelude, SIP-0086 §12a changes 1–3 and SIP-0096 §17a: **twenty-four
merges on top of the plan** (`939b6115`), each with main's full CI read green before the next.

| # | merge | what it changed |
|---|---|---|
| 1 | `336b6f63` (#1666) | item 8 — the driver's records have one home, the main checkout's `var/` |
| 2 | `b6c12c9a` (#1667) | item 9 — `worktree_hygiene.py`, and cut step 8 to run it |
| 3 | `7ad175ed` (#1668) | item 14 — the `chain` command: K cycles back to back, faults as registered data, a quiet box asserted between launches |
| 4 | `0d6bfa38` (#1669) | item 7 — the closure guard reads the title and commits (#1621); the manifest rewrite anchored to its entry (#1639) |
| 5 | `bead44a8` (#1670) | item 16 — `attach_release_records.py` (the upload itself waits for the owner) |
| 6 | `235c13b5` (#1671) | item 13 — the capture reads the run's own interface (#1665) |
| 7 | `23d73885` (#1672) | item 4 — the marker self-check at preflight (#1632) |
| 8 | `24f2d7d6` (#1674) | item 11 — the repair records which Correction Decision section its brief carried (#1661) |
| 9 | `a40682dd` (#1675) | item 15, part 1 — the per-task wait is declared and required |
| 10 | `b23a7bb0` (#1673) | item 5 — a pin carried from an earlier line says why |
| 11 | `2dbfb5c7` (#1677) | the chain reads a cancelled run's late replies where they land (a defect in #1668) |
| 12 | `7c6d3863` (#1676) | item 1 — the retest readout: where a retested patch still fails, by locus, with regressions |
| 13 | `7f98fb98` (#1679) | item 3 — the JSX parse runs in a worker process, so a native fault kills it, not the agent (Refs #1626) |
| 14 | `5648cde8` (#1682) | §12a change 1 — the loop's depth is the request profile's, required |
| 15 | `ac903757` (#1680) | item 6 — the qa repair brief shows the line each failing case failed on |
| 16 | `c6de8e00` (#1678) | item 15, part 2 — the hang bound is the declared wait on both sides; `handler_hang` |
| 17 | `01e33a71` (#1681) | item 2 — a call that spent its whole budget and wrote nothing is asked again once, with the fact |
| 18 | `33b69664` (#1683) | item 10 — a run's cancel reaches the agent already holding its task (#1648) |
| 19 | `0c2f097e` (#1684) | §17a change 1 — a producer's dispute is captured as a typed output |
| 20 | `e78672ee` (#1685) | §17a changes 2–5 — contested rows, the analyzer's rulings, a confirmed dispute ends the chain, the readout (#1581) |
| 21 | `28bbc29c` (#1686) | §12a change 1 — a self-evaluation pass booked under its own key |
| 22 | `339b3530` (#1687) | §12a change 2 — a failed TypeScript build carries every type error |
| 23 | `00a939e4` (#1688) | §12a change 3 — the pass, and a qa re-take after a refunded repair, see what they edit |
| 24 | `ccc9475d` (#1689) | the faults the three new diagnostics run on |

**Two things the plan named that deploy A does not carry, stated so silence cannot read as
shipped.**
- **SIP-0086 §12a change 4 is held for the owner.** Its premise — that the repairs evaluate a second
  time after a loop — does not hold: the repairs have no loop, and evaluate once after they emit
  (#1229). Building it means giving the repairs a self-evaluation loop, which the plan does not
  settle. SIP-0086 §12a's last paragraph records this.
- **Item 12, the convergence replay, is not built.** It is driver-side (no deploy change) and fifth
  in §3.9's drop order; whether it is built during this window and run overnight on the idle box,
  or dropped to 1.9, is the owner's call at this registration. Its predictions would be registered
  here before it ran.

**The pins, and how they were read.** The image ids and the squad snapshot were read from the
deploy by the driver's own functions; the config hashes were computed by the CLI's code on the
deploy's tree (§1). **No cycle was launched to read a pin** (plan §4.4 rule 4, #1648). The first
launch of each arm confirms its hash against the server, and a mismatch refuses that roll.

---

## 3. The exercise plan — stated before the first diagnostic

### 3a. The bar

| id | claim | blocking on | typed field |
|---|---|---|---|
| **L1** (#1268) | the loop remains able to produce a valid running result — a counted roll whose contentless emission is **not recovered** breaches it | every counted roll | `loop_texture.contentless_emissions`, the count beside the recovered flag |

### 3b. The live predictions

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **Campaign readiness** (plan §4.1 `unattended-chain`) — per cycle a terminal state within its bound; zero ghost generations after the cancel; the crash a typed fact and the run leaving `running`; the hang ended at the declared wait as a typed `task_timeout` fact; a quiet box before every launch; an assessment on every cycle; zero manual actions besides the registered gate policy | the chain record (§3e) | any ghost generation, any run left `running`, a hang past its bound, or a manual step | that four cycles, three of them faulted, run back to back with no human action and leave nothing behind — on this deploy, this stack |
| **The compile loop** (§12a) | `compile-loop` | a correction round, no pass, or a final compile failing — *rev 2: a correction round **caused by the compile failure** (§11a)* | that a pass shown every type error and the file it edits compiles clean inside the task |
| **The contested result** (§17a) | `false-criterion` | a refund with no dispute, a dispute never read, a rejection, or the import degraded | that a false check is disputed, read and ruled on, and ends at the operator rather than as a lost round |
| **All-attempt integrity** (§39.8, first reading) — carried verbatim from 1.8.1 §3b | the per-repair `repair_revision_form` and `anchored_edit_transaction` lines; `patch_candidate_identity`; the driver's `loop_texture.repair_revision_forms` and `candidate_identities` | one defect class on any transaction | that the contract holds where it was exercised |
| **Success-path readiness** (§39.8, second reading) — at least **N = 6**, one per required cell (§3c) | the sum of §3c's counting rules over counted rolls and diagnostics | fewer than 6, **or any required cell at zero** | that a scoped repair can be produced on demand in every lane the flip will govern |
| **A wrong-locus round is a dispute, not a patch** (plan §3.4's second prediction from 1.8.1 deploy A) — where a qa-suite failure is routed to a dev repair, the dev disputes the suite's check (a contested row by `dev`) rather than emitting a patch that breaks the build | `loop_texture.contested_rows` beside the round's locus line | a wrong-locus dev repair that patches the suite's subject instead of disputing — **reporting-only**: no diagnostic forces a wrong-locus round, so its absence reads UNASKABLE, never YES | that a producer aimed at the wrong artifact says so in a typed voice |

**An unmet N blocks the flip and is recorded as a shortfall, not retried into existence.** A
falsified prediction or an unreached seam stops the set and the plan is revised in the open.

### 3c. N — the definition, the cells, the supply, and the counting rules

**A successful transaction** (§39.8): resolved inside its grant, composed, passed its preservation
proof (§17), **verified, and persisted under the identity it was verified with** (§20). A
transaction refused, failed closed, or whose repair failed patch verification or the retest adds
nothing.

**Rule 4.4 #1 — a seam reached is not a cell supplied.** The supply column below is a prediction
with a falsification condition, and the per-cell tally is printed at every diagnostic's clearance.
**Rule 4.4 #2 — the counting definition governs, the supply column forecasts** (carried from the
owner's 1.8.1 ruling of 2026-09-22): a transaction produced by a diagnostic whose column says
"none" counts in the cell its repairing role and stack place it in.

| cell | forcing fault (diagnostic) | what the repair revises | expected successful transactions | counted-roll expectation |
|---|---|---|---|---|
| **dev × React** | `dev_join_response_omits_declared_fields` (`dev-lane-fastapi-react`) | the join handler in `backend/routes.py` | 1–2 | ~1 across four rolls |
| **dev × Next.js** | the same (`dev-lane-nextjs`) | `app/api/runs/[run_id]/join/route.ts` — `function:POST#try` or an anchored edit | 1–2 | ~0 across two rolls |
| **qa × React** | `qa_suite_own_frame_failure` + `repair_prose_only` (`own-frame-then-prose-repair`) | the qa suite the fault broke — **and, new on this deploy, the re-take after the refunded prose repair is an edit request on the shown suite** (§12a change 3) | 1–2 | ~1 across four rolls |
| **qa × Next.js** | the same in fill mode (`own-frame-then-prose-repair-nextjs`) | the shells by fill (§9.3) and the free suite by anchored edit; **the re-take is an edit request on the free suite** | 1–2 | ~1 across two rolls |
| builder × React | `builder_emission_contentless_all_attempts` | `assembly_notes.md` — anchored edits only | 0–1, declared not required | none |

**What is new against 1.8.1's supply, and why it is predicted to matter.** 1.8.1 read 4 of 6: on
both stacks every qa re-take after a refunded repair **re-emitted** the suite (1.8.1 record §10b;
zero scoped qa transactions in five Next.js runs). Deploy A makes that re-take an edit request
(§12a change 3's plan §3.3 addition). **Predicted:** the qa cells' re-takes read `form=edits` on their
`qa_retake_revision_form` line. **Falsified by** a re-take that re-emits the suite whole with the
form offered.

Expected total **5–10 against N = 6**. A required cell at zero fails the reading regardless of the
total.

**The three counting rules**, carried verbatim from the 1.8.1 pre-registration §3c: (1) a qa fill
repair counts as a §9.3 region transaction when its merged shells are accepted and persisted under
their verified identity, reported in its own column; (2) a transaction that replaced more than half
of its file's characters is a scoped rewrite and does not count toward N; (3) every transaction is
read against the round that produced it, from its revision form. **A qa re-take counts under the
same definition**: its `qa_retake_revision_form` line is its revision form, and its retest is the
verification.

### 3d. The seam invariants — thirteen diagnostics

The 1.8.1 nine, unchanged in fault, invariant and readout (their configs carried with one
construction fix, §9), plus four. **Two-run budget each; the chain runs once. A seam not reached
after its budget stops the set.**

| diagnostic | fault(s) | invariant | readout | N cell |
|---|---|---|---|---|
| `absent-suite` | `qa_suite_absent` | **L2** (#1269) | "repair-retest seam reached" | none |
| `own-frame-then-prose-repair` | `qa_suite_own_frame_failure`, `repair_prose_only` | **L7**, **L4**, **L5** — and the re-take's revision form (§3c) | the locus line, the refund line, the re-take's `qa_retake_revision_form` | **qa × React** |
| `own-frame-then-prose-repair-nextjs` | the same, fill mode | the same three on the App Router stack | as above, plus `fill_merge_evidence` | **qa × Next.js** |
| `path-prefix` | `qa_suite_at_path_prefix` | **L8b** (#1311) | the extractor's strip count | none |
| `absent-suite-then-false-claim` | `qa_suite_absent`, `analyzer_false_source_claim` | **A1** (#968) | `analyzer_claims_refuted`, `decision_inherited_claims` | none |
| `contentless-builder` | `builder_emission_contentless` | **R1** (#1372) | `retried_with_fact` | none |
| `contentless-builder-all-attempts` | `builder_emission_contentless_all_attempts` | **F1** (#1374) | the re-derived required_files line | builder × React (declared) |
| `dev-lane-fastapi-react` | `dev_join_response_omits_declared_fields` | **the dev lane** (SIP-0107 step 3) | the dev repair's revision form; the retest | **dev × React** |
| `dev-lane-nextjs` | the same | the same on the App Router stack | as above | **dev × Next.js** |
| **`compile-loop`** | `compile_loop_two_type_errors` (nextjs_ts) | **§12a** — the task compiles until clean | both errors repaired by the develop task's passes; the final compile clean; **zero correction rounds** (*for the compile failure — rev 2, §11a*); every pass in the usage ledger (`development.develop:self_eval`) | none |
| **`false-criterion`** | `false_criterion_alias_import` (nextjs_ts) | **§17a** — the producer disputes, the framework reads it | the import unchanged; a typed dispute; the row `contested`; the analyzer **confirms**; the chain ends `contested_check`, the check named on the terminal decision | none |
| **`redelivery`** | `qa_suite_own_frame_failure`, `qa_repair_process_killed` | **#1627's rule and #1626's containment** | a typed `FAILED` for the original task id; the queue drains; the handler not re-run; **the run leaves `running`**; with item 3 built, a child parse crash returns `None` and the parent survives — **not forced by this fault**, read only if one occurs, and UNASKABLE otherwise | none |
| **`unattended-chain`** | K = 4 React cycles: a cancel (cycle 2, at `development.develop`), a `neo` crash (cycle 3), `handler_hang` (cycle 4) | **the line's claim** | §3b's campaign-readiness row, per cycle | none |

### 3d′. Deploy A — one mechanism prediction per prelude change

Each is read where its mechanism shows, never as a rate. **Predicted-silent** ones say so before the
fact.

| change | mechanism predicted | read from |
|---|---|---|
| **item 1** (#1676) | every patch retest that still fails names its failures' locus — in the edited region, in an edited file, outside the edited files, or with no repo frame — and the regressions | `loop_texture.retest_*` on every correction round |
| **item 2** (#1681) | **predicted rare.** A call that spends its whole budget and writes nothing is asked again once with the fact, and logged `cap_exhausted_retry` beside a `:cap_exhausted` emission shape | the agents' emission-shape lines; silence where no call exhausts its cap |
| **item 3** (#1679) | **predicted silent.** A native fault in the JSX parse kills the worker, not the agent; the parent reads `None` and continues | no agent restart during a parse; `redelivery` exercises the neighbouring bound |
| **item 4** (#1672) | every set's preflight passes the marker self-check, one real line per collector | the driver's preflight output |
| **item 6** (#1680) | a qa repair brief names the line each failing case failed on | the repair brief's `case_frames` in the qa repairs' stored prompts |
| **item 10** (#1683) | a cancel tells the agents holding the run's work on their control queue **before** teardown; the agent drops a queued task and cancels a running one; nothing replies | `unattended-chain` cycle 2's `ghost_readings`: **`emissions_after_cancel` 0 and `late_replies` 0**. The cancel response's `agents_notified` and the agents' `task_skipped: run cancelled` lines are corroboration read by hand, not the registered reading — the chain record does not hold them |
| **item 11** (#1674) | every repair records which Correction Decision section its brief carried | `repair_revision_form.decision_section` |
| **item 15** (#1675, #1678) | a hung task fails at the declared 1,800 s wait on both sides as a typed `task_timeout` fact | `unattended-chain` cycle 4: `loop_texture.task_timeouts` |
| **§12a change 1** (#1682, #1686) | every build task's loop runs to the profile's depth of 3, and each pass is booked under `<task_type>:self_eval` | the run summaries' usage; `compile-loop` |
| **§12a change 2** (#1687) | a failed Next.js build's row carries every type error from `tsc`, or says why it cannot | `frontend_compiles` rows' `diagnostics` / `diagnostics_unavailable` |
| **§12a change 3** (#1688) | a pass shown files answers with edits or records a whole-file response; a qa re-take after a refund is an edit request | `self_eval_revision_form` and `qa_retake_revision_form` lines |
| **§17a** (#1684, #1685) | a dispute is captured, marked, ruled on and read; a confirmation ends the chain as `contested_check`; a rejection proceeds as the failure | `false-criterion`; `loop_texture.contested_rows` everywhere else as texture |
| **items 5, 7, 8, 9, 13, 14, 16** | tooling — **predicted silent on the cycle path**; their readings are the driver's and the cut's own | the driver's refusals, the records' home, the capture at the cut |

### 3e. Where each reading is read, and that the source can hold it (plan §4.4 rule 3)

| reading | source | can it hold the fact? |
|---|---|---|
| seam readouts, loop texture, revision forms, contested rows, task timeouts, passes, refusals | the driver's per-cycle record, built from the runtime-api and agent container logs over the cycle's window | yes — logs are read uncapped per window and written to the record; **a rebuild wipes container logs**, so no rebuild while a set is open (§8) |
| ghost generations after the cancel | the chain record's `ghost_readings` (late replies read where they land, #1677) and the agents' emission-shape lines by time window | yes — emission-shape lines carry no cycle id, so the window is the join, as registered in item 14's design |
| terminal state and kind | `cycle_runs` and the run's `RunTerminalDecision` in `run_loop_summaries` | yes — typed rows |
| usage per pass | `run_loop_summaries.usage.by_task_type` | yes — typed row, no cap |
| the stored prompt of a repair or pass | LangFuse | **no — capped at 10,000 characters of input**; no reading is registered on it. The decision section is read from `repair_revision_form` (#1661) instead |

### 3f. Texture — observed, never blocking, every field with its unaskable state declared

1.8.1 §3f carried, plus: per pass, `self_eval_revision_forms`; per re-take, `qa_retake_revision_form`;
per round, `contested_rows` (confirmed / rejected / unruled / unmatched, by role); per build failure,
`diagnostic_count`. **A field whose producer did not run reads UNASKABLE, never NO and never zero**
(#1593).

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — four counted rolls

Config `docs/plans/verification-sets/1-8-2-fastapi-react.yaml`, pinned to §1. Rolls 1–4, one roll
per driver invocation.

## 5. Next.js+TS (`nextjs_ts`) — two counted rolls

Config `docs/plans/verification-sets/1-8-2-nextjs.yaml`, overrides `build_profile=nextjs_ts` and
`development_profile=nextjs_ts`. Rolls 1–2.

## 6. The shakeout loop and its exit

**The thirteen diagnostics are deploy A's shakeout.** The exit rule, stated before the first
launch: **a pass of the thirteen on one deploy with no new seam finding.** A finding becomes a fix,
the deploy moves, this registration is void and re-made on the new deploy, and no transaction from
the superseded deploy counts toward N. **Budget: three rounds**; the record reports how many it
took. Every readout counts non-execution (skips, by reason) beside failure (#1261).

## 7. Gate constant

The 1.6.3 §6 constant, verbatim in each set config's `gate_notes`. `--as-agent`. Gates never
self-approve; the decider is recorded per roll.

## 8. Prohibited while this set is open

**No framework change under `src/` or `adapters/`, no config, profile or prompt-asset change, and no
deploy move** — each voids this commit. Docs and driver-only changes are free **only** where they
cannot alter a reading. **No launch-and-cancel** to read anything (#1648). **No manual cancel within
the chain's quiet timeout of a launch.** No rebuild while a set is open (it wipes the logs §3e reads).

## 9. Drift the record must declare

- `resolved_config_hash` per arm against 1.8.1's `58eed2c52e1f` / `fff4a6435c97` — the cause is
  §12a change 1's `max_self_eval_passes` (#1682).
- the `squad_profile_snapshot_ref`: **unchanged** at 1.8.1's `2d8d4feb3519a7ec` (read from deploy A); a roll that stamps anything else is drift and refuses.
- the image ids against deploy B″'s (`runtime-api 6e79feea4be6`, `max a2024380e17a`, `nat ebab70571b37`,
  `neo 05ed019afaad`, `eve 26c0677205ed`, `bob e05878f59014`, `data b81c1a8895d1`, `joi 8447fd3a7fd5`,
  `han 9d07cc875bdf`); B″'s container logs are kept at `~/squadops-deploy-logs/`.
- **one construction fix in the carried configs**: the runtime-api check that built
  `DispatchedFlowExecutor()` bare now passes `task_timeout=1800`, because item 15 made the wait
  required. What the check asserts is unchanged.

---

## 10. Readings — appended as they land

*(Appended after each diagnostic, the chain and each counted roll. Nothing else in this document
moves.)*

Records: `var/verification_sets/1-8-2-diagnostics/<diagnostic>/…`, `1-8-2-fastapi-react/roll-0N-…`,
`1-8-2-nextjs/roll-0N-…` — on the Spark, in the main checkout's `var/` (item 8), attached to the
Release at the cut after a credential scan (item 16). Every reading here is taken from the stored
record, never from memory of the run. Times ET.

### d1 — `compile-loop`, run 1 of 2: `cyc_eb4ed3bde52d` / implementation `run_c4d376ad26f2`, 08:13–09:12 ET

Record `compile-loop/shakeout-20260925T131200Z.json`. Driver at `cc71ec54`.

- **Outcome:** `accepted`; 17 of 17 criteria verified; boot audit PASS; no agent restarts; config
  hash `91080ef9ce39` (the diagnostic's overrides, non-counting).
- **The fault** applied to both develop tasks on their first attempts (`m000` 6,631 → 6,769 chars,
  `m001` 10,313 → 10,451).
- **The passes** — read from the develop agent's `self_eval_revision_form` lines (§11b):
  - `m000`, pass 1: offered the edit form on four files; three edits refused, **nothing applied**
    (one transaction, all or none — SIP-0107 §14).
  - `m000`, pass 2: edits accepted on three files.
  - `m001`, pass 1: an edit accepted on `app/page.tsx`.

  Three passes in all, each booked under `development.develop:self_eval` (`calls: 3`,
  `run_loop_summaries`).
- **The final compile:** `frontend_compiles` 7 passed, 0 failed across the stored typed-check
  evaluations.
- **Correction rounds: 1**, and not the compile's. `builder.assemble`'s `assembly_notes.md` lacked
  a `## How to Test` section (`regex_match`, `match_count_below_minimum`; correction decision
  `art_4d21df2074a4`: `patch`).
  - The builder repair answered with an anchored edit (22 of 67 characters, 33%).
  - Patch verification passed, and its verified and persisted identities agree.
- **The driver's seam readout: `reached: false`** — it counts every correction round. **Reading:
  HELD, by the owner's ruling (§11a)**: no type error left its develop task.
  - The literal NO stands in the record beside this reading.
  - The second budgeted run was not spent.
- **L1:** no contentless emission.
- **N:** the builder's accepted edit falls in builder × Next.js — not a required cell (rule 4.4 #2);
  nothing toward N's six.
- **Harness note:** the sequencer launching the diagnostics misread the deploy-identity file as
  this cycle's record, and was stopped before it relaunched `compile-loop`; no extra cycle ran.

### d2 — `false-criterion`, run 1 of 2: `cyc_1727c96394da` / implementation `run_27462d5a739b`, 09:31–10:22 ET

Record `false-criterion/shakeout-20260925T142214Z.json`. Driver at `a284f17c`.

- **Outcome:** `blocked_unverified`; one correction round, which terminated
  `correction_terminated` / **`contested_check`**. The run's `RunTerminalDecision` names the
  check: `acceptance:declared_imports on app/api/runs/route.ts (vc-declared-imports-lib-alias)`.
- **The fault** planted its row on every evaluation of the develop task's first attempt: four
  `APPLIED … rows 0 -> 1` lines in the develop agent's log, 10:14–10:19 ET.
- **The dispute:**
  - Captured on the develop task (`by: dev`, round 0) and matched to the planted row.
  - Ruled **confirmed** by the analyzer: 1 confirmed, 0 rejected, 0 unruled.
- **The import:** unchanged. The develop task's stored `app/api/runs/route.ts` still imports
  through `@/lib/store`, `@/lib/errors` and `@/lib/models`.
- **The passes:** all three answered `form: none`, changing nothing — the right answer to a
  check the producer holds is false.
  - Pass 2's `disputed_checks` block did not parse, and was logged as such.
  - The dispute counted came from one of the task's other emissions; the record does not say
    which.
- **The driver's seam readout: `reached: null` (UNASKABLE)**, "the fault never applied". It could
  not parse the plant's `rows 0 -> 1` form (§11c). **Every observable the prediction names held**
  (§3b: no refund without a dispute, the dispute read, no rejection, the import not degraded).
  The reading on the record's own terms waits for run 2, on the fixed driver.
- **L1:** no contentless emission.
- **Evidence kept:** the fault and form lines, verbatim, at
  `var/1-8-2-logs/false-criterion-1-fault-and-forms.log`.

### d2 — `false-criterion`, run 2 of 2: `cyc_db35b68f0a20` / implementation `run_af375b6b838c`, 10:35–11:54 ET

Record `false-criterion/shakeout-20260925T155437Z.json`. Driver at `81847d25` (§11c's fix).

- **Seam readout: `reached: true`.** The plant applied on all four evaluations of the develop
  task's first attempt (`0→1 rows`).
- **The dispute:** made by `dev` and **confirmed**.
- **The run's end:** `RunTerminalDecision` is `correction_terminated` / **`contested_check`**,
  naming `acceptance:declared_imports on app/api/runs/route.ts (vc-declared-imports-lib-alias)`.
- **The import:** unchanged. The develop task's stored route file carries two `@/lib` imports and
  no relative one.
- **Reading: YES** — every falsifier in §3b absent. **`false-criterion` cleared.**
- **Texture:**
  - `self_eval_revision_forms` is in the record, from §11b's fix: three passes, `form: none`.
  - One develop `:self_eval` pass is counted in `contentless_emissions` (273 characters, no
    files): the dispute-only answer. L1 binds counted rolls only.

### d3 — `redelivery`, run 1 of 2: `cyc_8176207ea2f3` / implementation `run_f10f98e6ef82`, 11:58–12:56 ET

Record `redelivery/shakeout-20260925T165620Z.json`. Driver at `81847d25`.

- **Outcome:** `accepted`; 21 of 21 criteria verified; boot audit PASS.
- **The run had two qa suites** (`m005`, `m006`). The own-frame fault broke each on its first
  attempt; each was routed to a qa repair; the process fault killed each repair's agent after its
  model returned (exit 137; the qa agent restarted twice, by the fault).
- **Each redelivery was refused** as a typed `FAILED` for the repair's id, not run again (#1627),
  and the queue drained. The run completed — none was left `running`.
- **Seam readouts:** `qa_suite_own_frame_failure` **YES**, `qa_repair_process_killed` **YES**.
  **`redelivery` cleared.**
- **Item 3's child-parse bound:** not forced by this fault, and no parse crash occurred —
  UNASKABLE, as registered.
- **The qa re-takes after the refused repairs were both edit requests, both accepted** — §3c's
  prediction for the qa cells (`form=edits`) observed on both re-takes:
  - `backend/tests/test_runs.py`: 122 of 6,416 characters (2%);
  - `frontend/src/__tests__/run-detail.test.jsx`: 107 of 2,982 characters (4%).

  Two qa × React candidates. Rule 4.4 #2 places a diagnostic's transaction in its cell; they are
  tallied at the set's close against §3c's definition.
- **Finding: #1697** — both repairs carried the id `repair-run_f10f98e6-00-qa.test_repair` (§11d).

---

## 11. Amendments after the first launch

### 11a. `compile-loop`'s falsifier counts only a correction round caused by the compile failure — owner's ruling, 2026-09-25

**What changed.** §3b's "falsified by a correction round" and §3d's "**zero correction rounds**"
now read *a correction round caused by the compile failure*.

**The evidence.** d1 (§10):
- Both injected type-error pairs were repaired inside their develop tasks.
- Every final compile was clean.
- The run's one correction round came from `builder.assemble`'s documentation check on
  `assembly_notes.md`, a task the fault never touched.

The clause was written as a proxy for "the compile failure escaped the task". The proxy fired on a
round that has nothing to do with it.

**Who ruled.** The owner, on the evidence above. The alternatives offered were spending the
second budgeted run, or reading the prediction as falsified and stopping the set.

**What did not change.** The driver's `compile_loop_two_type_errors` readout still counts every
round. Changing it would alter a reading mid-set (§8). The record keeps the literal NO, and §10
states the reading beside it.

### 11b. The driver collects the pass and re-take revision forms — an instrument gap, fixed before d2

**The gap.** Several parts of this document read two lines no record held:
- §3c counts a qa re-take by its `qa_retake_revision_form` line.
- §3f registers `self_eval_revision_forms` as texture.
- §3d′ reads §12a change 3 from both lines.
- §3e says the record can hold them.

The driver collected only `repair_revision_form`. Both lines were dropped at its agent-window
filter, so N's qa cells, whose new supply on this deploy is the re-take (§3c), could not have been
counted from any record.

**The fix** (driver-only; it adds a registered reading and alters none):
- Both lines are kept, and read into `loop_texture.self_eval_revision_forms` and
  `loop_texture.qa_retake_revision_forms`.
- Each is registered with the condition under which it is unaskable.
- Each is rendered in the record.
- Each is sampled for the #1632 marker self-check.

From d2 on, the driver runs from the fix's merge commit. It changes `scripts/dev/`, `docs/` and
`tests/` only, with zero drift under `src/` or `adapters/`. The counted rolls pin that commit at
roll 1.

**d1's forms** are not in its record. They were read from the containers before any rebuild and
kept verbatim at `var/1-8-2-logs/compile-loop-1-revision-forms.log`. §10's d1 reading cites them.

### 11c. The driver reads a planted row's `APPLIED` line — an instrument gap, fixed before d2's second run

**The gap.** `faults_applied` parsed only a transform's `chars N -> M` form. `false-criterion`'s
fault is a planted row, which logs `rows 0 -> 1` (1.8.2 plan §4.1, #1689). Its four `APPLIED`
lines were never read, so `seam_readouts` found the fault "never applied" and read the seam
UNASKABLE (#1588's rule), although the dispute it exists to produce was captured and confirmed.

**Why the guards missed it:**
- The #1689 test read the seam through `SEAM_READOUTS` directly, never through `seam_readouts`,
  the wrapper that asks whether the fault applied.
- The #1632 marker self-check had only a `chars`-form sample for `faults_applied`.

**The fix** (driver-only; it lets the reading be asked and alters no other reading):
- The parse takes both forms, keeping each attempt's unit (`rows_before`/`rows_after` for a plant).
- The render names the unit.
- A real `rows`-form line is added to the marker samples.
- A test enters at `planted_rows` and reads through `seam_readouts`.

**d2's budget.** Run 1 read UNASKABLE, so run 2 of 2 runs on the fixed driver. That is the
budget's own rule for a seam the record could not ask, and needs no ruling.

### 11d. #1697 is a seam finding; the readouts refuse a repeated round index — owner's ruling, 2026-09-25

**The finding.** A repair's id is `repair-{run}-{correction_attempts:02d}-{task_type}`
(`adapters/cycles/correction_repair.py:1000`), and a retest's is the same with `retest-`
(`correction_runner.py:1574`). A refunded round does not advance the counter, so two dispatches
can share an id: d3's two qa repairs were both `repair-run_f10f98e6-00-qa.test_repair`.

**Why it is a seam finding.** The id scheme predates this line (2026-09-10; #1627 is v1.8.1's), so
it is not "a seam the pack touched". It is the other half of the definition
(`verification-sets/README.md`): "**a prediction's readout that cannot see its own miss**".
- Item 1's retest readout (§3d′, #1676 — this line's own) joins a retest to its repair **by the
  round index in their ids**. Two repairs at one index would merge their edits and keep one
  retest, and the locus it reports would be of neither.
- L4's refund join (the own-frame diagnostics) keys on the same index.
- Neither could tell.
- No reading in this set was affected: no record so far holds a retest round, and d3's two
  repairs were killed before they patched.

**The ruling.** The owner, offered (a) a driver fix with the set continuing, or (b) §6 read
literally — fix the ids under `adapters/`, rebuild, void this registration and rerun the
thirteen — ruled **(a)**. The ground is that a readout's own blindness, fixed in the driver, does
not move the deploy, as with §11b.

**The fix** (driver-only). The dispatcher's `repair-` and `retest-` lines are kept, and
`loop_texture.repeated_round_ids` names any id dispatched more than once.
- Item 1's readout sets a round with a repeated index aside
  (`loop_texture.unjoinable_retest_rounds`) rather than joining it.
- The run's retest totals then read UNASKABLE, naming #1697, rather than partial.
- L4 reads UNASKABLE on a refund whose round it cannot name.
- The framework fix — a run-unique repair and retest id — is #1697's, and lands where the deploy
  moves anyway (deploy B or 1.9).
