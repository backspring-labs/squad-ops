# 1.7.5 — the recovery extraction map (#1152 with #1443)

**Status:** the 1.7.5 plan §3.1's second design artifact (2026-09-09), reviewed by the owner
before the first extraction PR (plan §7 step 3). It is one of two independent decisions
reviewed together; the other is the composition-roots standard
(`docs/architecture/composition-roots.md`). **Nothing here is derived from that standard.**
The reason `correction_runner.py` has the shape this map gives it must never require reading
a composition-root policy: the two closures share a release because both are structural
debts blocking the next architecture, not because they are the same architecture.

## 1. The invariant

> **Moving the recovery implementation does not change the recovery contract proven across
> 1.7.2–1.7.4.**

The contract is the three-part sentence the 1.7.4 plan tested every pack row against —
*truthful failure → truthful correction → durable repaired state* — and the seams that
enforce it are the ones the last two lines instrumented: the retry-with-fact backstop
(#1372), the accepted-patch derivation by contract (#1374), the rewind that never discards an
accepted repair (#994), the analyzer claim the decision refuses to inherit (#968), the locus
classifier (#1054), the retest keyed on what the patch contains (#1269, the owner's ruling of
2026-09-03), the refund of an empty repair (#1053, #1273). Every one of those lives in the
three methods this map moves. The proof that they still hold after the move is therefore
not a unit test of the moved code alone; it is the five fault diagnostics reaching their
seams on the pinned deploy (§3.4).

## 2. The subject, measured on main `5c686cbd` (2026-09-09)

| unit | lines | where | what it owns |
|---|---|---|---|
| `DispatchedFlowExecutor` | 4,668 of the file's 4,933 (4,349 when #1152 was filed) | `adapters/cycles/dispatched_flow_executor.py` | the run |
| `_try_accept_patch` | **511** | `:3245` | the accepted-patch path: grants, overlay, verification, retest, supersession, framework rows |
| `_execute_sequential` | 412 | `:1565` | the per-task loop: run-lived state, checkpoint restore, dispatch and retry, collection, gates |
| `execute_cycle` | 396 | `:730` | **out of this map** |
| `execute_run` | 325 | `:392` | **out of this map** |
| `_reject_invalid_plan_before_workload_gate` | 301 | `:4247` | **out of this map** |
| `_handle_task_outcome` | 294 | `:2950` | the outcome router: stamp, classify, retry, budget, protocol, path |
| `CorrectionRunner` | 1,090 of the file's 2,145 (1,461 at v1.6.0) | `adapters/cycles/correction_runner.py` | the correction protocol |
| `run_correction_protocol` | **536** | `:1505` | analyze → decide → bank → terminate? → repair → judge the emission |

The call chain the diagnostics run down: `_execute_sequential` (`:1797`) →
`_handle_task_outcome` (`:3126`) → `run_correction_protocol` → back in the executor
(`:3215`) → `_try_accept_patch`.

**The criterion that puts these three on the map and not `acceptance_checks.py`** (2,245
lines, 64 units, largest 75): one growing unit that owns multiple independent reasons to
change. `run_correction_protocol` is edited for the analyzer, the decision, the rewind, the
repair and the retest, and it grew by every Loop Honesty row.

## 3. The seams, and the proof each step carries

### 3.1 The domain seams that already exist — the map moves logic *toward* them, never invents a parallel one

| seam | what it already owns |
|---|---|
| `src/squadops/cycles/patch_verification.py` | `PatchCheckRecord`, `skip_reasons`, `PatchVerification`, `rebase_artifact_paths`, `overlay_artifacts`, `EvidenceSupersession` + `supersede_evidence_artifacts`, `materialize`, `verify_frozen_integrity`, `restore_frozen_files`, `_evaluate_file_owned_gate`, `verify_patched_artifacts` (207 lines) |
| `src/squadops/cycles/correction_policy.py` | `CorrectionPathResolution`, `resolve_correction_path` — the rule that narrative rationale cannot outvote machine evidence |
| `src/squadops/cycles/correction_signature.py` | `failure_signature`, `classify_movement`, `should_terminate_plan_defect`, `repair_refused_in_round` — progress-aware termination (#687/#431/#435) |
| `src/squadops/cycles/task_outcome.py` | `TaskOutcome`, `FailureClassification`, `ContractComplianceViolation`, `CorrectionTermination` |
| `src/squadops/cycles/task_plan.py:299` | `repair_steps_for(failed_task_type, failure_locus)` — the table that picks the repairing role |
| `src/squadops/cycles/check_registry.py` | `framework_rows_owed()`, `framework_row_producer()` (#1374) |
| `adapters/cycles/correction_runner.py:88–1009` | twelve module-level pure functions the protocol already calls: scoping, the frontend-build widening, probe-owned slots, `refuted_source_claims`, `_resolve_repair_target`, `_inject_deterministic_evidence`, `_locus_and_repair_target`, the two ownership vetoes |

### 3.2 The goldens — byte-identical before and after every PR

| golden | captures | at |
|---|---|---|
| `tests/unit/cycles/test_context_assembly_golden.py` → `goldens/context_assembly.json` | the rendered context per task-type class | the context-assembly registry (#663) |
| `tests/unit/cycles/test_correction_context_golden.py` → `goldens/correction_context.json` | the repair-envelope and retest-envelope inputs, un-enriched | **`_dispatch_protocol_step`, mocked** — the seam every protocol step crosses |
| `tests/unit/cycles/test_plan_context_golden.py` → `goldens/plan_context.json` | the planning context | the plan-authoring seam |

A deliberate context change regenerates a golden in its own PR and reads as a behaviour
change; an extraction PR that needs to regenerate one has changed behaviour and is not an
extraction PR (§5).

### 3.3 The unit suites that pin the moved code

`tests/unit/cycles/test_dispatched_flow_executor.py`, `test_dispatched_flow_executor_observability.py`,
`test_executor_checkpoint.py`, `test_executor_build_wiring.py`, `test_correction_runner.py`,
`test_correction_repair_prefect_propagation.py`, `test_correction_policy.py`,
`test_correction_signature.py`, `test_cycle_outcome.py`. Unchanged by every step; a test that
must change because a method moved is rewritten to enter at the new seam **in the same PR**,
never deleted (CLAUDE.md "Tests").

**A correction to the plan's wording.** The 1.7.5 plan §3.5 lists "the `tests/fixtures/roll_replays`
corpus" among the extraction's proofs. That corpus is real emissions replayed through
*checks* (`test_acceptance_checks.py`, `test_additive_containment.py`, `test_test_runner.py`,
`test_dom_anchor_queries.py`, `test_scaffold.py`); nothing replays it through the executor.
It proves the checks the moved code calls, not the moved code. The map's proof is §3.2, §3.3
and §3.4; the plan's row is corrected at its next revision rather than left to imply a
harness that does not exist.

### 3.4 The five diagnostics — the seams the moved code owns, reached on the pinned deploy

| fault (`fault_injection.py:251`) | config | the seam it reaches | the moved block that owns it |
|---|---|---|---|
| `qa_suite_absent` | absent-suite | the retest keyed on what the patch contains (L2, #1269) | `_try_accept_patch` retest block (§4 step 1, block 5); `reexecute_repaired_suite` |
| `qa_suite_own_frame_failure` then `repair_prose_only` | own-frame-then-prose-repair | the locus routes an own-frame failure to `qa.test_repair` (L7); a prose-only repair is refunded, not verified (L4); the re-take is briefed with its cases (L5) | `run_correction_protocol` repair selection and emission judgment (§4 step 4, blocks 4–5); `_handle_task_outcome` refund (§4 step 3, block 4) |
| `qa_suite_at_path_prefix` | path-prefix | no emission lands under a literal `path/` prefix (L8b) | `_handle_task_outcome` admission of the failed emission; `_admit_failed_emission` |
| `builder_emission_contentless` | contentless-builder | the builder's contentless attempt is retried with its fact (R1, #1372); no false corrected result is composed from it (F1, #1374) | `_handle_task_outcome` marker block (§4 step 3, block 1); `_try_accept_patch` framework-rows block (§4 step 1, block 6) |
| `analyzer_false_source_claim` (chained behind `qa_suite_absent`) | absent-suite-then-false-claim | the decision does not inherit an analyzer claim the workspace refutes (A1, #968) | `run_correction_protocol` diagnosis loop and resolution (§4 step 4, blocks 1–2) |

**Every block the map moves is reached by at least one diagnostic.** That is the proof the
unit suites cannot give: a seam reached on the pinned deploy after the move, by a fault
injected at the producing role's own emission seam, with the whole downstream path running
as it would on a real defect. Two-run budget each; a seam not reached is a closure finding
that stops the line (plan §4).

## 4. The map — one PR per step, in this order

### Step 1 — `_try_accept_patch`: seven named methods, in place

The block map of the 511 lines, by the comment headers the code already carries (offsets
from `:3245`):

| block | offsets | what | rationale it carries (#1149 harvest) |
|---|---|---|---|
| 1 grants | +44…+102 | the verified set is the set that will be stored; the grants are the *repairing* step's | #1323, #1350 |
| 2 overlay and owned criteria | +103…+172 | verify against the accepted workspace tree; the criteria owned by the files the repair rewrote, presence-keyed on the manifest | #643, #870 |
| 3 verification and its reasons | +173…+228 | why nothing executed, not just that nothing did; structurally unevaluable with no behavioural evidence is not a fix | #1276, #1221 |
| 4 the not-passed path | +229…+275 | a rejected patch is recorded with its reason, never discarded | #1221 (rule B) |
| 5 the retest | +276…+379 | keyed on what the patch contains, not on the failed result; `None` means no retest ran | #456, #1269, the owner's ruling 2026-09-03 |
| 6 supersession and framework rows | +380…+510 | the failed attempt's evidence never survives beside the accepted patch's; every framework row the task type owes by contract is re-derived from the patched set | #1111, #1318, #1374 |
| 7 accept | +511 | `return "accept_patch"` | — |

Each block becomes a named private method on the executor with the block's inputs as
parameters and its outputs as a small return value; `_try_accept_patch` becomes the seven
calls in order. **No line of logic moves between blocks; no condition changes.** The seven
names are chosen at the PR from the block titles above.

*Proof:* §3.2 goldens unchanged; §3.3 executor suites unchanged; the absent-suite and
contentless-builder diagnostics reach blocks 5 and 6 on the line's deploy B.

### Step 2 — the accepted-patch path leaves the executor

The seven methods move to a **`PatchAcceptance` collaborator in a new module beside
`correction_runner.py`** — the same shape `CorrectionRunner` already has: constructed by the
executor's factory with the ports it needs (artifact vault, the verifier, the dispatcher for
the retest), handed the run-lived records at call time (the bound record, the accepted-repair
ids, the rejected-repair record). `_try_accept_patch` becomes one delegation. The pure halves
of blocks 5 and 6 — *which* retest a patch's contents key, and the composition of the owed
framework rows over the patched set — move to `src/squadops/cycles/patch_verification.py`
beside `verify_patched_artifacts`, which already owns the rest of that logic; the collaborator
keeps the I/O (store, checkpoint, dispatch).

*Proof:* as step 1, plus the executor's construction tests (`test_executor_build_wiring.py`)
assert the collaborator is built once by the factory (a wiring test entering at the caller
the live cycle uses, CLAUDE.md "A changed seam needs a wiring test").

### Step 3 — `_handle_task_outcome`: four named methods, in place

| block | offsets from `:2950` | what | rationale |
|---|---|---|---|
| 1 stamp and marker | +57…+103 | every handled outcome stamps an attempt; the emission-retry marker rides exactly one dispatch | #1260, #1304, #566 |
| 2 classify and retry | +104…+156 | the D5 fallback table; BLOCKED; RETRYABLE → `continue`; D9 fails without correction | D5, D9, `fails_without_correction` |
| 3 budget and protocol | +157…+218 | the run-level count bumped on *this* correction before dispatch; the dispatched envelope is what the retest hand-off gets | #374 |
| 4 refund and path | +219…+292 | an emission containing nothing is not an attempt, refunded and bounded separately; abort / rewind / patch / continue | #1053, #994 |

`_handle_task_outcome` becomes the four calls; the correction-path dispatch in block 4 keeps
its `if`/`elif` because it is a four-way action, not a type chain. **Not a table** — the
identifier convention's "tables over chains" is for type-keyed dispatch, and this is keyed on
the protocol's answer.

*Proof:* goldens; executor suites; the contentless-builder diagnostic reaches block 1 (the
marker and the retry with its fact), the own-frame-then-prose diagnostic reaches block 4 (the
refund), the path-prefix diagnostic reaches the admission that block 1 hands off to.

### Step 4 — `run_correction_protocol`: five named methods on `CorrectionRunner`, by protocol step

| block | offsets from `:1505` | protocol step | rationale |
|---|---|---|---|
| 1 diagnosis | +59…+172 | the frozen-ownership record for repair emissions; the loop over `CORRECTION_TASK_STEPS` through `_dispatch_protocol_step`, each step's outputs captured in its own variable | SIP-0100 3.4b, #95 |
| 2 resolution | +173…+256 | `resolve_correction_path`; an override is disclosed in the event payload, the model's rationale left intact | `correction_policy` |
| 3 bank and terminate | +257…+278 | the plan delta stored before any repair; the signature-state termination check after it | #687, #431, #435 |
| 4 repair | +279…+487 | `repair_steps_for(task_type, locus)`; the dispatch of each repair step; the ownership vetoes | #568, #1054 |
| 5 the emission judged | +488…+529 | did the repair emit a *file*: the extractor's marker is the answer, prose is not content, a rewind or continue is never refunded | #1053, #1273 |

`run_correction_protocol` becomes the five calls, returning the same `CorrectionProtocolResult`.
`_dispatch_protocol_step` (`:1268`), `_check_progress_termination` (`:1393`) and
`reexecute_repaired_suite` (`:2047`) are untouched.

*Proof:* the correction-context golden captures at `_dispatch_protocol_step` — every envelope
that crosses it is byte-identical; `test_correction_runner.py` unchanged; the
absent-suite-then-false-claim diagnostic reaches blocks 1–2, the own-frame-then-prose
diagnostic reaches blocks 4–5.

### Step 5 — the repair half leaves the runner

Blocks 4 and 5 (+279…+529, the largest coherent half) move to a **`correction_repair` module
beside `correction_runner.py`**, flat in `adapters/cycles/` as the directory's other runners
are (`pulse_boundary_runner.py`, `task_dispatcher.py`, `run_completion.py`), taking with them
the module-level pure functions only they call (`_resolve_repair_target`,
`_locus_and_repair_target`, `_apply_ownership_veto`, `_apply_emission_ownership_veto`,
`_repair_step_rows`, the scoping helpers at `:88–160`). `CorrectionRunner` keeps the
diagnosis loop, the resolution, the banking and the facade, and imports the repair module.
`refuted_source_claims` and `_attach_refuted_claims` stay with the runner: they are the
decision's, not the repair's. The goldens' import path
(`from adapters.cycles.correction_runner import CorrectionRunner`) is unchanged.

**The core ends here.** Steps 1–5 are the recovery path — what the five diagnostics prove
and what Scoped Code Revision lands through. They are the close criterion's core (plan
§3.5): a core left incomplete stops the line.

### Step 6 — the tail: `_execute_sequential`

The 412 lines open with ten run-lived state holders (offsets +22…+73 from `:1565`: the
stored-artifact refs, the bound scaffold record, the authored-manifest binding, the
checkpoint state, the outcome-routing state, the correction counter #374, the signature
state #435, the instruction carry SIP-0100 3.4b, the rejected-repair record #870, the
accepted-repair ids #994, the compliance counter 3.4a, the time budget RC-8/#511), then the
checkpoint restore (+94…+120), the seeding and the plan loop (+155…+345) whose body is
dispatch, the retry loop around `_handle_task_outcome`, the patched-result swap (#389),
collection and checkpoint, and the manifest binding (#796). The extraction: the holders into
a `RunState` dataclass constructed once at the top and passed down; the loop body into
`_execute_task(state, envelope)`. Two PRs, in that order.

**The tail is re-placeable** by the stop rule (§6). It is on the map so its shape is decided
now and not at the PR.

### Named out of this map

`execute_cycle` (`:730`), `execute_run` (`:392`) and `_reject_invalid_plan_before_workload_gate`
(`:4247`): none of the five diagnostics reaches them, no 1.8 item lands through them, and
their proof would be a harness this line does not build. They are the next map's subject, and
#1152 stays open with the remainder named when this line's core lands.

## 5. The forbidden change

**No behavioural change rides an extraction PR.** A defect found while extracting — a
condition that reads wrong, a branch that cannot be reached, a comment that contradicts the
code — is **filed and fixed in its own PR**, before or after the extraction, never inside it;
the extraction PR carries the issue number in its Evidence and moves the code as found. A PR
that regenerates a golden has changed behaviour and is renamed for what it is. This is the
rule #663 ran under across three slices, and it is what makes "a red on deploy B belongs to
the closures" a statement about three named PR series rather than about a blur.

## 6. The stop rule, and what "landed" means

The map is the scope. The shakeout budget (plan §4: three pairs on deploy B) is the clock.

- **Core** = steps 1–5. If the budget is spent before the core is complete, the line does not
  close 1.7; the plan says so in the open (plan §5) rather than re-placing a closure.
- **Tail** = step 6. If the budget is spent after the core and before the tail, the tail is
  re-placed by name into the 1.8 plan's rider with this map attached and the plan's §3.8
  count incremented — a plan-management disposition that satisfies the close criterion for
  the tail only.
- **Out of map** = the three methods §4 names, re-placed with #1152 kept open and its
  remainder stated.

## 7. #1149's harvest — the precondition of each step

Before each step's PR, the rationale the block carries in comments (the issue and SIP
numbers in §4's tables) is harvested into `docs/architecture/defended-bespoke-decisions.md`
as numbered entries in that file's existing shape — *what was decided, the failure that
forced it, the alternative rejected* — and the PR cites the entries it moved. Step 1's
harvest is the largest (eleven issues across seven blocks) and is the first PR of the
closure. A comment does not survive an extraction unless the refactorer reads it; the entry
does.

## 8. Naming — nothing new to learn

Flat files in `adapters/cycles/`, matching the directory; a collaborator named for what it
does (`PatchAcceptance`, `correction_repair`), constructed where `CorrectionRunner` is
constructed today; pure logic moving toward the `src/squadops/cycles/` seam that already owns
its neighbours. No package is introduced, no import path the goldens use changes, and no
name in this map is a letter or a number.
