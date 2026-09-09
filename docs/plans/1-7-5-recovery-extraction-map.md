# 1.7.5 — the recovery extraction map (#1152 with #1443)

**Status:** the 1.7.5 plan §3.1's second design artifact (2026-09-09, rev 2 on the owner's
review the same day), reviewed by the owner before the first extraction PR (plan §7 step
3). It is one of two independent decisions reviewed together; the other is the
composition-roots standard (`docs/architecture/composition-roots.md`). **Nothing here is
derived from that standard.** The reason `correction_runner.py` has the shape this map gives
it must never require reading a composition-root policy: the two closures share a release
because both are structural debts blocking the next architecture, not because they are the
same architecture. **This map, not the plan, is the acceptance source for #1152 and #1443**:
the plan owns placement and sequencing; the map owns the scope, the steps, the core/tail
split and the proof.

**The one connection to the standard, stated so it is not mistaken for coupling:** any
collaborator this map introduces is constructed at the executor's existing composition seam
— its constructor, with an injectable override, the way `CorrectionRunner` is built at
`dispatched_flow_executor.py:365` — and handed the ports it needs from there. **This map
creates no second dependency-construction path**: no method constructs a collaborator or an
adapter inside itself to save lines. That applies the standard's rule for root-internal
composers; it does not derive this decision from it.

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
seams on the pinned deploy, with the readouts that can tell a regression there (§3.4).

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
| `src/squadops/cycles/patch_verification.py` (863 lines — **a growth watch item in the plan; this map adds nothing to it**) | `PatchCheckRecord`, `skip_reasons`, `PatchVerification`, `rebase_artifact_paths`, `overlay_artifacts`, `EvidenceSupersession` + `supersede_evidence_artifacts`, `materialize`, `verify_frozen_integrity`, `restore_frozen_files`, `_evaluate_file_owned_gate`, `verify_patched_artifacts` (207 lines) |
| `src/squadops/cycles/check_registry.py` (178 lines) | `framework_rows_owed()`, `framework_row_producer()`, `required_files_row()` (#1374) — **the home for framework-row composition** (§4 step 2) |
| `src/squadops/cycles/write_authorization.py` | **`WriteGrant`** (`:79`, transient, resolved per producer *before* generation) and `WriteAuthorization`; `scaffold_enforcement.py:133–144` resolves the grant for qa and builder producers |
| `src/squadops/cycles/correction_policy.py` | `CorrectionPathResolution`, `resolve_correction_path` — the rule that narrative rationale cannot outvote machine evidence |
| `src/squadops/cycles/correction_signature.py` | `failure_signature`, `classify_movement`, `should_terminate_plan_defect`, `repair_refused_in_round` — progress-aware termination (#687/#431/#435) |
| `src/squadops/cycles/task_outcome.py` | `TaskOutcome`, `FailureClassification`, `ContractComplianceViolation`, `CorrectionTermination` |
| `src/squadops/cycles/task_plan.py:299` | `repair_steps_for(failed_task_type, failure_locus)` — the table that picks the repairing role |
| `adapters/cycles/correction_runner.py:88–1009` | twelve module-level pure functions the protocol already calls: scoping, the frontend-build widening, probe-owned slots, `refuted_source_claims`, `_resolve_repair_target`, `_inject_deterministic_evidence`, `_locus_and_repair_target`, the two ownership vetoes |

### 3.2 The goldens — canonical-JSON-identical before and after every PR

| golden | captures | at |
|---|---|---|
| `tests/unit/cycles/test_context_assembly_golden.py` → `goldens/context_assembly.json` | the rendered context per task-type class | the context-assembly registry (#663) |
| `tests/unit/cycles/test_correction_context_golden.py` → `goldens/correction_context.json` | the repair-envelope and retest-envelope inputs, un-enriched | **`_dispatch_protocol_step`, mocked** — the seam every protocol step crosses |
| `tests/unit/cycles/test_plan_context_golden.py` → `goldens/plan_context.json` | the planning context | the plan-authoring seam |

**What "identical" means.** Both harnesses compare through `_canonical()` — `json.dumps(obj,
sort_keys=True, indent=1, default=str)` (`test_context_assembly_golden.py:4`,
`test_correction_context_golden.py:304`) — so the invariant is **the exact context presented
to the model is unchanged**, not the incidental byte order of a fixture. A deliberate context
change regenerates a golden in its own PR and reads as a behaviour change; an extraction PR
that needs to regenerate one has changed behaviour and is not an extraction PR (§5).

### 3.3 The unit suites that pin the moved code

`tests/unit/cycles/test_dispatched_flow_executor.py`, `test_dispatched_flow_executor_observability.py`,
`test_executor_checkpoint.py`, `test_executor_build_wiring.py`, `test_correction_runner.py`,
`test_correction_repair_prefect_propagation.py`, `test_correction_policy.py`,
`test_correction_signature.py`, `test_cycle_outcome.py`. Unchanged by every step; a test that
must change because a method moved is rewritten to enter at the new seam **in the same PR**,
never deleted (CLAUDE.md "Tests").

**A correction to the plan, made in the plan.** The 1.7.5 plan §3.5 listed "the
`tests/fixtures/roll_replays` corpus" among the extraction's proofs. That corpus is real
emissions replayed through *checks* (`test_acceptance_checks.py`, `test_additive_containment.py`,
`test_test_runner.py`, `test_dom_anchor_queries.py`, `test_scaffold.py`); nothing replays it
through the executor. It proves the checks the moved code calls, not the moved code. The
plan's row now points here for the proof (its rev 5), so no implementation PR cites a
harness that does not exist.

### 3.4 The five diagnostics — reachability and assertion coverage, block by block

Two levels, kept apart: **reached** means the diagnostic executes the block on the pinned
deploy; **asserted** means a registered readout would read differently if that block's
contract changed. A block that is reached but not asserted is proven by §3.2 and §3.3, and
the record says so rather than crediting the diagnostic.

| fault (`fault_injection.py:251`) | config | the seam it reaches | the moved block | the readout that asserts it |
|---|---|---|---|---|
| `qa_suite_absent` | absent-suite | the retest keyed on what the patch contains (L2, #1269) | accept-patch block 5 (§4 step 1); `reexecute_repaired_suite` | the record's "repair-retest seam reached" reading (1.7.3 pre-registration §3, L2) — **asserted** |
| `qa_suite_own_frame_failure` then `repair_prose_only` | own-frame-then-prose-repair | an own-frame failure routes to `qa.test_repair` (L7); a prose-only repair is refunded, not verified (L4); the re-take is briefed with its cases (L5) | protocol blocks 4–5 (§4 step 4); outcome block 4 (§4 step 3) | the locus pair `affected_task_types → correction_repair_locus` (L7), the refund count by reason (L4, #1276), the re-take's briefed cases (L5) — **asserted** |
| `qa_suite_at_path_prefix` | path-prefix | no emission lands under a literal `path/` prefix (L8b) | outcome block 1's hand-off to `_admit_failed_emission` | the extractor's strip count and the stored names (L8a/L8b, #1311) — **asserted** |
| `builder_emission_contentless` | contentless-builder | the builder's contentless attempt is retried with its fact (R1, #1372); no false corrected result is composed from it (F1, #1374) | outcome block 1 (§4 step 3); accept-patch block 6 (§4 step 1) | `retried_with_fact` / `retried_blind` (R1), `framework_rows_rederived` (F1) — **asserted** |
| `analyzer_false_source_claim` (chained behind `qa_suite_absent`) | absent-suite-then-false-claim | the decision does not inherit an analyzer claim the workspace refutes (A1, #968) | protocol blocks 1–2 (§4 step 4) | `decision_inherited_claims` beside `analyzer_claims_dropped` (A1, #1401) — **asserted** |

**Reached but not asserted by any diagnostic — proven by the goldens and suites:**
accept-patch blocks 1–4 (grants, overlay, verification reasons, the not-passed path) are
traversed by every diagnostic that reaches block 5 and by every live correction round, and
their readouts exist (#1323's dropped-with-evidence line, #1407's skips by reason) but are
not registered against these faults; outcome blocks 2–3 (classification, budget) likewise;
protocol block 3 (bank and terminate) is asserted only by `test_correction_signature.py`.
**Every block the map moves is reached by at least one diagnostic; the blocks whose contract
a diagnostic can distinguish are the ones the table marks asserted.** The pre-registration
registers the readouts in that column and no others as the extraction's live evidence.

Two-run budget each; a seam not reached is a closure finding that stops the line (plan §4).

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
calls in order.

**The extraction rule for this step, stated precisely.** *No behavioural dependency crosses a
block boundary differently: the extraction may normalise data passing into explicit
parameters and return values, but it may not reorder conditions or change which block owns
a decision.* A 511-line function carries cross-block temporaries exactly where its current
boundaries are imperfect; mechanically preserving those would produce seven methods with
awkward argument bundles only to move them in step 2. Making the data flow explicit is the
point of the step; moving a condition is not permitted.

*Proof:* §3.2 goldens unchanged; §3.3 executor suites unchanged; the absent-suite and
contentless-builder diagnostics reach blocks 5 and 6 on the line's deploy B and their
readouts (§3.4) read as before.

### Step 2 — the accepted-patch path leaves the executor

The seven methods move to a **`PatchAcceptance` collaborator in a new module beside
`correction_runner.py`** — the same shape `CorrectionRunner` already has: constructed in the
executor's constructor with an injectable override, handed the ports it needs (artifact
vault, the verifier, the dispatcher for the retest), handed the run-lived records at call
time (the bound record, the accepted-repair ids, the rejected-repair record).
`_try_accept_patch` becomes one delegation. Its responsibility, in one sentence: *turn a
proposed repair into an accepted or rejected candidate under grants, verification, retest and
evidence rules.*

**Where the pure halves go — not to `patch_verification.py`.** Block 5's pure half (*which*
retest a patch's contents key) and block 6's (the composition of the owed framework rows over
the patched set) leave the collaborator as functions, but `patch_verification.py` is 863
lines and on the plan's growth watch list; adding every pure piece of acceptance to it would
make it the next god module. The framework-row composition goes to
`src/squadops/cycles/check_registry.py` beside `framework_rows_owed()` and
`framework_row_producer()`, which already own the owed/producer half of the same concept
(178 lines). The retest keying stays a method on `PatchAcceptance` until a second consumer
appears — one caller is not a seam.

**The name.** `PatchAcceptance` is the current domain vocabulary — the thing accepted is a
patch everywhere the code and the records speak of it. When Scoped Code Revision lands in
1.8 the accepted thing will not always originate as a file patch, and `CandidateAcceptance`
will age better; the name is not changed speculatively here, and the pressure is recorded so
the 1.8 plan renames it deliberately or explains why not.

**Authority, and the constraint on it (a non-behavioural rule for this line).** Two
authorisation moments exist today and the map keeps them distinct: *repair authority* —
what the repairing producer is permitted to attempt — is a `WriteGrant`
(`write_authorization.py:79`) resolved before generation by `scaffold_enforcement.py:133–144`;
*candidate authorisation* — whether the emitted candidate lies inside that authority — is
what block 1 checks with the repairing step's grants (#1323, #1350). **The extraction must
not create a second derivation of the grant.** `PatchAcceptance` consumes the grant the
repair resolved; it does not re-derive one. The future direction, for the 1.8 plan and not
this line: one `WriteGrant` produced upstream, carried through repair dispatch, consumed by
candidate acceptance — defence in depth without two owners of the same rule, which is the
inconsistency Scoped Code Revision exists to remove.

*Proof:* as step 1, plus `test_executor_build_wiring.py` asserts the collaborator is built
once by the executor's constructor with its override (a wiring test entering at the caller
the live cycle uses, CLAUDE.md "A changed seam needs a wiring test").

### Step 3 — `_handle_task_outcome`: four named methods, in place

| block | offsets from `:2950` | what | rationale |
|---|---|---|---|
| 1 stamp and marker | +57…+103 | every handled outcome stamps an attempt; the emission-retry marker rides exactly one dispatch | #1260, #1304, #566 |
| 2 classify and retry | +104…+156 | the D5 fallback table; BLOCKED; RETRYABLE → `continue`; D9 fails without correction | D5, D9, `fails_without_correction` |
| 3 budget and protocol | +157…+218 | the run-level count bumped on *this* correction before dispatch; the dispatched envelope is what the retest hand-off gets | #374 |
| 4 refund and path | +219…+292 | an emission containing nothing is not an attempt, refunded and bounded separately; abort / rewind / patch / continue | #1053, #994 |

`_handle_task_outcome` becomes the four calls under step 1's extraction rule; the
correction-path dispatch in block 4 keeps its `if`/`elif` because it is a four-way action,
not a type chain. **Not a table** — the identifier convention's "tables over chains" is for
type-keyed dispatch, and this is keyed on the protocol's answer.

*Proof:* goldens; executor suites; the contentless-builder diagnostic asserts block 1
(`retried_with_fact`), the own-frame-then-prose diagnostic asserts block 4 (the refund by
reason), the path-prefix diagnostic asserts the admission block 1 hands off to.

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

**The protocol steps exchange explicit results.** *Each step consumes the previous step's
returned value and may not reach backward into an earlier step's local state or forward into
a shared mutable runner context.* After the step the orchestration reads as
`diagnose → resolve → bank-and-terminate → repair → judge`, with a typed value flowing across
each arrow; a helper that is shorter because it reads twenty attributes off `self` that the
old function used to hold in locals has not become structurally better, and the PR's
Evidence shows the five signatures to prove it did not.

*Proof:* the correction-context golden captures at `_dispatch_protocol_step` — every envelope
that crosses it is canonical-identical; `test_correction_runner.py` unchanged; the
absent-suite-then-false-claim diagnostic asserts blocks 1–2, the own-frame-then-prose
diagnostic asserts blocks 4–5.

### Step 5 — the repair half becomes a `CorrectionRepair` collaborator

Blocks 4 and 5 (+279…+529, the largest coherent half) are a concept, not a bag of functions:
*determine the repair steps, enforce ownership, dispatch the repair, judge whether a usable
repair emission exists.* They become a **`CorrectionRepair` collaborator**, constructed at the
executor's composition seam beside `CorrectionRunner` with an injectable override, handed to
the runner, and taking with it the module-level pure functions only the repair half calls
(`_resolve_repair_target`, `_locus_and_repair_target`, `_apply_ownership_veto`,
`_apply_emission_ownership_veto`, `_repair_step_rows`, the scoping helpers at `:88–160`),
flat in `adapters/cycles/` as the directory's other runners are. The split after the step:

| collaborator | owns |
|---|---|
| `CorrectionRunner` | diagnosis, policy resolution, banking and termination, the orchestration, and the facade `run_correction_protocol` |
| `CorrectionRepair` | repair-step selection, the ownership vetoes, repair dispatch, the emission judgment |

`refuted_source_claims` and `_attach_refuted_claims` stay with the runner: they are the
decision's, not the repair's. The goldens' import path
(`from adapters.cycles.correction_runner import CorrectionRunner`) is unchanged. A named
collaborator, not a module, because it is the seam Scoped Code Revision will evolve in 1.8:
a scoped revision is composed by the repair and materialised by the acceptance, and both
are now things with a constructor and a contract rather than a file of functions.

**The authority split, restated at this seam:** `CorrectionRepair` determines what the
repairing producer is allowed to attempt (it resolves and carries the `WriteGrant`);
`PatchAcceptance` proves the emitted candidate lies inside that authority before
materialisation and verification. Neither derives authority the other already resolved.

**The core ends here.** Steps 1–5 are the recovery path — what the five diagnostics assert
and what Scoped Code Revision lands through. They are the close criterion's core (plan §3.5):
a core left incomplete stops the line.

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

**`RunState` is constrained now so it does not become a bag of everything:** only run-lived
*mutable execution state* belongs in it — the holders named above; **ports and services do
not** (they are the executor's, bound at construction); **task-local values do not** (they
are `_execute_task`'s parameters and locals); every field carries its owner and the issue
that introduced it, and related fields are typed substructures (the correction counter and
signature state together, the ownership record and instruction carry together) rather than a
flat namespace; a method takes the substructure it reads, not the whole object, so no method
gains access to all run state merely because the object exists.

**The tail is re-placeable** by the stop rule (§6), and **it is not forced**: if the core
closes cleanly and the budget is short, the tail moves to the 1.8 rider without a line
spent on shrinking a method for its own sake.

### Named out of this map

`execute_cycle` (`:730`), `execute_run` (`:392`) and `_reject_invalid_plan_before_workload_gate`
(`:4247`): none of the five diagnostics reaches them, no 1.8 item lands through them, and
their proof would be a harness this line does not build. They are the next map's subject, and
#1152 stays open with the remainder named when this line's core lands. A successful core is
not a licence for "while we are here".

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

## 7. #1149's harvest — keyed to the decision, not to the move

Before a step's PR, the rationale its blocks carry in comments (the issue and SIP numbers in
§4's tables) is harvested into `docs/architecture/defended-bespoke-decisions.md` as numbered
entries in that file's existing shape — *what was decided, the failure that forced it, the
alternative rejected* — and the PR cites the entries it moved. **The harvest key is the
architectural decision, not the physical move:** #1323/#1350 justify both the grant
ownership in step 1 and the acceptance ordering in step 2 and get one entry that both PRs
cite; #1053 is one decision whether it is read in the outcome router or in the emission
judgment. A comment does not survive an extraction unless the refactorer reads it; the entry
does. The entries stay the register's lightweight shape — three lines each, never an ADR per
branch.

## 8. Naming — nothing new to learn

Flat files in `adapters/cycles/`, matching the directory; two collaborators named for what
they do (`PatchAcceptance`, `CorrectionRepair`), constructed where `CorrectionRunner` is
constructed today; pure logic moving toward the `src/squadops/cycles/` seam that already owns
its neighbours, and never toward the one the plan is watching for growth. No package is
introduced, no import path the goldens use changes, and no name in this map is a letter or a
number.
