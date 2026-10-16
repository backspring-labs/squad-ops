# 2.3 R7: the largest-units extraction map (#1994)

**Status:** reviewed. The owner approved unit 1's step table on 2026-10-15, and chose to review each
of units 2–5 at the step before its first extraction PR (#1994, comment 6188687592). It reviewed unit 2's
on the same day (§4b; #1994, comment 6191733584), and unit 3's that evening (§4c; #1994, comment
6204066944). The plan owns R7's
placement (phase 8, after R6). This map owns each unit's scope, its steps, the data that crosses each
step, and the proof each PR carries.

**Granularity:** units 1, 2 and 3 are mapped to the step (§4, §4b, §4c), and unit 4's step table is
proposed (§4d) for the owner's review. Unit 5 is mapped to the block
here. Each gets
its step table in this file, re-measured on the tree it extracts from, and reviewed before its first
extraction PR. Measured on R6's tree (PR #2327), where units 3 and 4 live after the orchestration
move, to the top-level `squadops.execution` the owner ruled (#1992, comment 6188687208).

## 1. The invariant

> **An extraction moves code into named steps and changes no behaviour.**

That covers:
- no byte of what reaches a model, what a suite runs on, what a handler returns, what it banks
  as evidence or what it logs;
- no order among those;
- no fix: a defect found mid-extraction is filed, never fixed in the extraction PR. A fix inside
  a move reads as part of the move, and the line-diff proof can no longer tell them apart (1.7.5 §3).

## 2. The subject

| unit | now | at filing (2026-10-04) | where | what it owns |
|---|---:|---:|---|---|
| `QATestHandler.handle` | **481** | 443 | `capabilities/handlers/cycle/qa_test.py:1741` | the qa task's whole flow: prompt, generation, re-take, validation, suite, authenticity, evidence |
| `_CycleTaskHandler` | 1,665 (42 methods) | 1,558 (40) | `capabilities/handlers/cycle/base.py` | the template method every cycle handler inherits: `_llm_call` 177, `_evaluate_typed_acceptance` 158, `handle` 147, `_self_evaluate` 109 |
| `DispatchedFlowExecutor._execute_task` | 313 | 303 | `execution/dispatched_flow_executor.py:1731` | one task: preconditions, dispatch-with-retry and its routing closures, collection, pulse boundaries, the gate |
| `CorrectionRunner` | 1,305 (15 methods) | 1,254 | `execution/correction_runner.py` | the correction protocol: `run_correction_protocol` 195, `_diagnose` 180, `_check_progress_termination` 132, `_dispatch_protocol_step` 124 |
| `generate_task_plan` | 272 | 266 | `cycles/task_plan.py:1241` | the plan's one constructor: increment facts, steps, the per-step envelope loop |

Every unit grew between filing and now. Size alone isn't the criterion: `acceptance_checks.py` and
`scaffold.py` stay off the map, because each is a registry of small units with none over 100 lines.
The criterion is one unit owning several independent reasons to change.

## 3. The proof every extraction PR carries

1. **The sorted line diff** (#1152's technique). Every non-comment line the old body held appears in
   the new methods, re-indented. The only new lines are signatures, call lines, carrier fields and
   returns, and the PR lists them.
2. **Zero test edits.** The existing suites pass unchanged. If a test must change, the step changed
   behaviour or reached into a private name. The PR stops there, and the finding is recorded.
3. **The unit's golden, byte-identical.** Where no golden pins a unit, its step 0 captures one first,
   from the code before any extraction, in a PR of its own:

| unit | golden | step 0 |
|---|---|---|
| 1 | `test_qa_dev_handle_characterization.py` (every output shape, end to end) and `test_llm_call_characterization.py` | none |
| 2 | the same two for `handle` and `_llm_call` | **a characterization of `_evaluate_typed_acceptance`:** the rows, the missing list and the escalation counts for each status × severity × authored/injected case |
| 3 | none pins the per-task loop | **a characterization of `_execute_task`:** the events emitted, the evidence the ledger records, the collection calls and the patched-result swap, over a success, a corrected failure, a kept-progress round and an abort |
| 4 | `test_correction_context_golden.py` (the repair and retest envelopes) and `test_correction_runner.py` | none, measured to the block. **Measured to the step (§4d): a characterization of the diagnosis**, whose analysis and decision envelopes no golden records |
| 5 | `test_plan_context_golden.py` (`generate_task_plan`'s exact envelope inputs, framing and implementation) | none |

4. **Its own rebuild and regression pair.** Each unit is a structural batch, as the issue requires and
   phase 8 runs every rebuild.

## 4. Unit 1: `QATestHandler.handle`, step by step

`handle` already reads as named phases, and the comments name them. The extraction makes each phase a
method, with frozen carriers for what crosses between them. `validation` stays the mutable
`ValidationResult` it is today: the fold steps mutate it in place, and changing that is a redesign,
not an extraction.

| step | lines (now) | becomes | takes | returns |
|---|---|---|---|---|
| 1a | 1767–1835 | `_compose_user_prompt` | context, inputs, capability, its name, prd, prior outputs | a frozen `_QAPrompt` (user prompt, rendered template, sources, re-take offer), or the failure result when the plan artifacts are missing |
| 1b | 1837–1858 | `_shape_and_sections` | context, inputs, the prompt | the output shape, and the prompt with the increment scope, the outlet appendix and the fill section |
| 1c | 1860–1918 | `_generation_request` | context, inputs, capability, the prompt | a frozen `_QARequest` (assembled system prompt, messages, chat kwargs, model budget), or the guard's failure result |
| 1d | 1935–1984 | `_settle_emission` | context, inputs, content, response, kwargs, shape, re-take offer | a frozen `_QAEmission` (artifacts after the merge and authorization, the evidence extra, the re-take form), or the refusal or empty-emission result |
| 1e | 1986–2040 | `_validate_suite` | context, inputs, the emission, the request, the shape | validation and the artifacts after self-evaluation and the outlet |
| 1f | 2052–2079 | `_fold_suite_outcome` | validation, the test result, inputs | (mutates validation, as now) |
| 1g | 2081–2155 | `_authenticity_rows` | validation, artifacts, inputs, evidence extra | the typed-check evaluation artifact, if any (and mutates validation, as now) |
| 1h | 2157–2219 | `_suite_outputs` | everything the tail reads | the outputs dict, and validation after the probe fold |

After it, `handle` reads as: resolve the profile, the retest branch, 1a to 1h with the call and the
suite run between them, then `_finish`. That's about 70 lines.

**Two PRs:**
- 1a–1d (the generation half);
- 1e–1h (the verdict half).

Each carries the proof in §3.

**A seam to watch:** `retake_form` is mutated by 1e (`completed_by_self_eval`) and read by 1h. It stays
a dict on the `_QAEmission` carrier, which is frozen in its binding, not its contents, as `RunState`'s
lists are (1.7.5 §4 step 6). The PR names it.

## 4b. Unit 2: `_CycleTaskHandler`, step by step (reviewed by the owner, 2026-10-15)

**The owner's choices** (2026-10-15, #1994, comment 6191733584):
- **the acceptance-criteria check:** the smaller move, 2a below. Only its two decisions leave the class;
- **the model-call method:** only the authoring-envelope capture is pulled out, 2b below;
- **the two inline copies of existing helpers** (2c-1, 2c-2): replaced in a separate PR, #2335, after
  this unit's move, so the move's line diff stays a pure move.

Measured on main at `c255017a`. Unit 1 doesn't touch `base.py`, so these lines hold after it. The class
is 1,665 lines with 42 methods. Four of them are over 100 lines: `_llm_call` (177),
`_evaluate_typed_acceptance` (158), `handle` (147) and `_self_evaluate` (109).

**Step 0, its own PR: a characterization of `_evaluate_typed_acceptance`.**
- **What it captures:** a golden beside the existing two, recording what the method banks:
  - every field of each check row;
  - the `missing` list;
  - `typed_error_counts` afterwards.
- **The cases:**
  - severity (error, warning) against status (passed, failed, error, skipped);
  - a skip because config is off, and a skip for any other reason;
  - authored checks and framework-injected ones;
  - the prose and unparseable rows;
  - the empty-criteria return;
  - an evaluator error's third strike, which is escalated and appends nothing.
- **How it runs:** it enters at `QATestHandler()._evaluate_typed_acceptance`, as two existing tests do. It
  uses real criteria on a real workspace and never patches the evaluator, so 2a can move code without
  editing the test.

**2a: the typed-acceptance loop body becomes two functions beside the evaluator**
(`squadops.cycles.acceptance_evaluation`, which holds `evaluate_criterion`).

| step | lines (now) | becomes | takes | returns |
|---|---|---|---|---|
| 2a-1 | 717–749 | `acceptance_check_record` | the criterion, its outcome, the check index, whether it was authored, the subtask index | the check row, its evidence-gap flag included (#423) |
| 2a-2 | 766–781 | `apply_blocking_matrix` | the criterion, its outcome, `missing`, `typed_error_counts` | whether the error is past its second strike. It appends to `missing` and counts the strike as now (RC-9, RC-9a, RC-9b), and the handler logs the escalation as now |

- **Two lines change rather than move,** and the PR lists them. The loop's `continue` for a
  non-error severity becomes the function's `return False`. The escalation call stays in the
  handler, under `if apply_blocking_matrix(…)`, because it's the handler's log.
- **Where it departs from §5:** the method itself stays the handler's. That covers the split, the injected
  criteria, the workspace, the per-check log and the loop.
  - It needs `_framework_injected_criteria`, which lives in `base.py` and is imported from there by two
    test files.
  - Moving the method into `cycles` would make `cycles` import the handler module, or move that function
    and edit those tests.
  - The two pieces that are decisions move. The method drops to about 70 lines.

**2b: `_llm_call`.** One step: the authoring-envelope capture (1523–1539, SIP-0110 §0.11) becomes
`_capture_authoring_envelope`. It runs once before the call loop, and it changes for its own reason.
- **The call loop stays as it is.** It's the one post-call sequence #929 made on purpose. Of its 177
  lines, 37 are the docstring and about 45 are comments giving reasons.
- **Splitting it would separate the cap-exhausted retry from the accounting and the record,** which have
  to count the discarded call too (1.8.2 item 2). Size alone isn't the criterion (§2).

**2c: the generic `handle`.**

| step | lines (now) | becomes |
|---|---|---|
| 2c-1 | 1339–1357 | the model call's failure: `return self._fail_result(start_time, inputs, str(exc))` after the warning |
| 2c-2 | 1361–1369 | the provenance: `self._prompt_provenance(assembled, rendered)` |
| 2c-3 | 1383–1406 | `_mark_contentless`: the empty-or-contentless emission's marker (#998, #1372) |

- **2c-1 and 2c-2 are not new steps.** Each replaces an inline copy with an existing helper that builds
  the same thing.
  - `_fail_result` builds the same evidence, empty outputs and error.
  - `_prompt_provenance` builds the same dict. Its condition, `rendered is not None`, is the same as the
    copy's `renderer is not None and rendered is not None`, because `rendered` is set only when there is a
    renderer.
- **The line diff would show each copy's lines as gone,** so the PR that replaces them sets each one beside
  the helper's body, line for line. **The owner chose a separate PR** (#2335): this unit's move leaves
  both copies where they are, and 2c here is 2c-3 alone.

**Not on unit 2's table:**
- `_self_evaluate` (109): a loop of named calls already.
- `_record_generation` (92): one record built field by field.
- The other 37 methods: none over 60 lines.

**Order:** step 0, then 2a, then 2b with 2c-3, then unit 2's rebuild and regression pair; then #2335.

## 4c. Unit 3: `DispatchedFlowExecutor._execute_task`, step by step (reviewed by the owner, 2026-10-15)

**The owner's choices** (2026-10-15 19:00 ET, #1994, comment 6204066944):
- **the router** lives in `dispatched_flow_executor.py`, beside the executor (3a);
- **the success tail** is one method, `_after_task_success` (3c);
- **the dispatch announcement** becomes its own method, `_announce_dispatch` (3d).

Measured on main at `012208ee`: `src/squadops/execution/dispatched_flow_executor.py`, lines 1731–2043,
313 lines. The method runs one task of the plan. Its blocks:

| lines | block | lines in it |
|---|---|---:|
| 1731–1756 | signature and docstring | 26 |
| 1757–1768 | preconditions: skipped on resume, cancelled, past the time budget | 12 |
| 1770–1779 | enrich the envelope with the chain's context | 10 |
| 1781–1802 | announce the dispatch: create the Prefect task run (SIP-0087), emit `task.dispatched` (SIP-0077) | 22 |
| 1804–1927 | **the routing closures:** the held failed result, `_next_action`, `_route_outcome`, `_record_task_evidence` | 124 |
| 1929–1944 | dispatch with retry; on an abort, record the held result and re-raise | 16 |
| 1946–1969 | the patched-result swap (#389), the final evidence, the failure bookkeeping, the early return | 24 |
| 1971–1996 | on success: reset the failure count, collect and checkpoint, bind an authored manifest (#796) | 26 |
| 1998–2033 | pulse boundaries (SIP-0070) and the cadence bookkeeping | 36 |
| 2035–2043 | the gate | 9 |

**Why the closures are the long part.** `_next_action` passes 26 arguments to `_handle_task_outcome`.
Twelve values reach the three closures by capture: the executor, `state`, `envelope`, `enriched`, `cycle`,
`run_id`, `flow_run_id`, `profile`, `interface_manifest`, `budget_guard`, `ledger` and the held result.
Fifteen more are reached through `state`. Two capture rules are behaviour, and the move keeps both:
- **`consecutive_failures` is a snapshot.** `_route_outcome` binds `state.routing.consecutive_failures` as a
  default, so every routing decision in this task sees the count from before the first dispatch, not
  the live one. Found while writing step 0: nothing ever raises the count and nothing reads it, so
  SIP-0079's `max_consecutive_failures` is enforced by nothing (#2348, filed for the owner). The
  move keeps the snapshot as code, and step 0 pins the value handed over.
- **The held result is one dict, shared.** `_handle_task_outcome` writes the verified patch into it
  (`patched_result_holder`), and the swap after dispatch pops it from the same object.

**Step 0, its own PR: a characterization of `_execute_task`** (the §3 table pre-registered it).
- **What it records,** per case, in a golden beside the executor's tests:
  - the events emitted, with their context and payload;
  - the routing calls in order: `_admit_failed_emission`, `_handle_task_outcome` (the result it was given,
    the failure count it saw, whether it got the shared holder), `_store_kept_progress`, `supply_the_redispatch`;
  - the ledger's rows afterwards;
  - the collection call (which result, whether the checkpoint is retained), the manifest bind, the pulse
    calls and the gate;
  - `state` afterwards: the failure count, the accepted-repair ids, the cadence counters;
  - for the abort, the exception and the row recorded before it.
- **The cases:**
  - declined by a precondition (nothing dispatched);
  - a first-try success at a phase boundary, with pulse checks and a gate;
  - a failure re-dispatched once, then a success;
  - a failure whose repair is accepted (the patched result is swapped in before collection);
  - a kept-progress round (#1522), then an accepted repair;
  - a failure the correction lets through (`task_succeeded` false: no collection);
  - an abort raised from inside the dispatch.
- **How it runs:** it enters at `DispatchedFlowExecutor._execute_task` with a real `RunState` and `RunLedger`.
  Two collaborators are scripted:
  - the dispatcher's `dispatch_with_retry`, which calls the routing callback once per failed attempt,
    re-dispatches on `"continue"` and returns on `"accept_patch"` or `"break_correction"`, as the real one
    does (`task_dispatcher.py:653–663`);
  - `_handle_task_outcome` on the instance, which returns each case's actions.

  The steps below keep calling `_handle_task_outcome` through the executor and keep every module-level
  name in this module, so neither patch target moves and the test needs no edit.

**3a: the routing closures become a per-task router** (1804–1927, and the two uses at 1937 and 1943).

| step | lines (now) | becomes | holds | does |
|---|---|---|---|---|
| 3a | 1816–1927 | `_TaskOutcomeRouter`, a frozen dataclass in this module, built once per task where the closures are now | the twelve captured values; the failure count, read from `state` when it is built (the same moment the default was bound); the held-result dict | `next_action(result)` (was `_next_action`), `route(result)` (was `_route_outcome`; it's what `dispatch_with_retry` receives), `record_evidence(result)` (was `_record_task_evidence`) |

- **The bodies move as they are.** Each method's first lines unpack the attributes into the names the
  closure used (`cycle`, `run_id`, `state`, `ledger`, `_envelope`, `_enriched`, `_consecutive_failures`,
  `_holder`, and `_next_action` and `_record_task_evidence` bound to the router's own methods).
  `next_action` keeps `_next_action`'s parameters. So every line of each body appears in the line diff
  unchanged, re-indented. The unpack lines, the class and method signatures and the construction call
  are the new lines, and the PR lists them.
- **Outside the router, two call lines change:** `handle_task_outcome=_route_outcome` becomes
  `router.route`, and the abort path's `_record_task_evidence(_last_failed_result.get("result"))` becomes
  `router.record_evidence(router.held.get("result"))`.
- **Why the same module** (the owner's choice 1): the router calls four of the executor's private methods
  (`_handle_task_outcome`, `_admit_failed_emission`, `_store_kept_progress`, `_failure_recall`) and three
  of this module's names (`record_absent_emission`, `record_task_evidence`, `supply_the_redispatch`). In
  another module, those calls would cross a module boundary into private names, and a test that patches
  a name here would stop reaching the code (the hoist lesson, #2062).

**3b: the patched-result swap and the failure bookkeeping become one step** (1946–1964):
`router.settle(task_succeeded, result) -> TaskResult`. It pops the verified patch from the held dict, records
the final evidence and resets the failure count on a failed task. It returns the result. The early
`return` (1966–1969) stays in `_execute_task`.

**3c: the success tail becomes `_after_task_success`** (1971–2043, 73 lines). It takes `state`, the
envelope, the result and the run-invariant parameters it reads (`task_idx`, `plan`, `cycle`, `run_id`,
`flow_run_id`, `profile`, `run_root`, `obs_ctx`, `ledger`, `pulse`). Its four blocks are each one or two
calls already, so it stays one method (the owner's choice 2).

**3d: the dispatch announcement becomes `_announce_dispatch`** (1781–1802). It creates the Prefect task run,
emits `task.dispatched` and returns the task-run id. This one isn't in §5's block list. It's added because
it changes for its own reasons (SIP-0087, SIP-0077) and sits between the enrichment and the routing
(the owner's choice 3).

**After:** `_execute_task` reads as preconditions, enrich, announce, build the router, dispatch, settle,
and the success tail: about 100 lines, most of them the signature and the calls' keyword arguments.

**Not on unit 3's table:**
- **The two failure-count resets.** Lines 1964 and 1972 both set `state.routing.consecutive_failures = 0`:
  one on a failed task, one on a success. Merging them would change no behaviour, but it isn't a move,
  so 3b and 3c each keep their line.
- **`_handle_task_outcome` itself:** it's unit 4's neighbour, and the correction protocol's entry. It
  isn't touched here.

**The PRs:** step 0; then 3a with 3b (the router and what settles through it); then 3c with 3d; then
unit 3's rebuild and regression pair.

## 4d. Unit 4: `CorrectionRunner`, step by step (for the owner's review)

Measured on main at `f609f15a`: `src/squadops/execution/correction_runner.py`, the class at lines
392–1696, 1,305 lines in 15 methods. 1.7.5's recovery map already split the protocol into its five
steps, each a method that takes the previous step's value: diagnose, resolve the path, bank the delta and
check termination, repair, judge. So most of the long methods already have one job each. Where the length
is:

| method | lines | what it is | a step here? |
|---|---:|---|---|
| `run_correction_protocol` | 195 | 34 lines of signature and 31 of docstring. The body is the five steps as calls, with their keyword arguments | no: already a sequence of named calls, the reason §7 keeps `execute_cycle` off the map |
| `_diagnose` | 180 | the round's evidence (the event, the failure evidence and what is added to it, the round failure, the reserve), then a loop that builds and dispatches each declared step | **yes** |
| `_check_progress_termination` | 132 | one rule, #435's plan-defect terminal; a quarter of it is the docstring | no |
| `_dispatch_protocol_step` | 124 | the one per-step dispatch sequence: the budget, the Prefect task run, the events, emission enforcement, storage, the checkpoint. Four suites, the golden among them, patch or call it | no |
| `reexecute_repaired_suite` | 106 | the retest (#456): one job, and a public entry point | no |
| `_bank_delta_and_check_termination` | 102 | the plan delta and its storage, then the termination check, in the order that is the contract (#435) | no |

**`_diagnose`'s blocks** (1207–1386):

| lines | block | lines in it |
|---|---|---:|
| 1207–1238 | signature and docstring | 32 |
| 1239–1244 | the local `uuid4` import; the profile's declared steps (SIP-0108 §10i) | 6 |
| 1246–1257 | emit `CORRECTION_INITIATED` | 12 |
| 1259–1275 | the failure evidence: built, with the deterministic injections and the contested rows (SIP-0096 §17a) | 17 |
| 1276–1282 | the round failure, recorded on the ledger before any dispatch (SIP-0108 §4.2) | 7 |
| 1283–1292 | the priority reserve (#414): a round that only fails what the last attempt isn't held for ends here | 10 |
| 1294–1301 | the two output buckets (#95) and the correlation id | 8 |
| 1303–1368 | **the loop body:** one declared step's id, its role resolved against the profile, its inputs (with the analysis and the refuted claims after an analysis), its envelope, its dispatch | 66 |
| 1370–1380 | the step's outputs, into their bucket | 11 |
| 1381–1386 | the result | 6 |

**Step 0, its own PR: a characterization of the diagnosis.** §3's table said unit 4 needs no step 0. That
was measured to the block. The correction golden (`test_correction_context_golden.py`) records only the
repair and retest envelopes: it keeps step ids that start `repair-` (line 254). The analysis and decision
envelopes `_diagnose` builds are what 4b moves, and only single assertions in `test_correction_runner.py`
pin them (the resolved config on both, the analysis on the decision). Step 0 enters at
`run_correction_protocol` with the golden's harness shape (the dispatch seam captured, `uuid4` counted).
- **What it records,** per case:
  - the events emitted, in order, with their payloads;
  - every protocol step's envelope: its id, agent, type, correlation and causation ids, metadata and
    inputs;
  - the failure evidence the first step received;
  - the ledger's round-failure rows;
  - the exception, where the round ends.
- **The cases:**
  - the full declared shape: analyze, decide, repair;
  - the analyzer cites a source claim the tree refutes, so the decision's envelope carries the refuted
    claims;
  - repair alone declared: nothing is dispatched before the repair;
  - the previous round's repair disputed a check, so the evidence carries contested rows;
  - the last attempt is held for a required check this round didn't fail: the round ends before any
    dispatch, as `reserved_for_required`.

**4a: the round's evidence becomes `_round_evidence`** (1259–1292). It builds the failure evidence, adds the
deterministic injections and the contested rows, records the round failure and ends the chain at the
reserve, which raises. It returns the failure evidence.

**4b: one declared step becomes `_dispatch_declared_step`** (1304–1368). It builds the step's id, resolves
its role, assembles its inputs, builds the envelope and dispatches it through `_dispatch_protocol_step`. It
returns the step's result. The loop keeps the bucketing (#95). The method imports `uuid4` locally, as
`_diagnose` does now, and the correlation id is still drawn once before the loop. So the order of `uuid4`
calls doesn't change, and the golden's counter would catch it if it did.

**Where:** both on `CorrectionRunner`. 4b calls `_dispatch_protocol_step` through `self`, so the suites that
patch it on the instance keep reaching the code. The runner's own `__init__` hands the repair half a lambda
for the same reason (the hoist lesson, #2062).

**After:** `_diagnose` reads as the declared steps, `CORRECTION_INITIATED`, the round's evidence, the loop
(one call and the bucketing) and the result. That's about 110 lines, most of them signatures and the
calls' keyword arguments.

**The carrier §5 planned isn't built (the owner's choice).** §5 planned a frozen carrier holding the twenty
run-lived references once. Re-measured:
- `run_correction_protocol` and `reexecute_repaired_suite` are the runner's public entry points. Tests
  call or patch them in five and four suites, so their signatures stay (§3, zero test edits).
- `_dispatch_protocol_step` is the seam four suites patch or call, so its signature stays.
- `CorrectionRepair.dispatch` is another module's (1.7.5's repair half).

A carrier would be built in `run_correction_protocol` and unpacked again at three of its four uses. It
would shorten the signatures of 4a, 4b and `_diagnose` without separating any reason to change, and §2
makes that the criterion. So 4a and 4b take keyword-only parameters, as `_diagnose` does now. If the
owner wants the carrier anyway, it lands with 4a and 4b. It would hold what `_diagnose` and its two new
steps read, and `run_correction_protocol` would build it once.

**The PRs:** step 0; then 4a with 4b; then unit 4's rebuild and regression pair.

## 5. Units 2–5, to the block

**Unit 2: `_CycleTaskHandler`** (mapped to the step in §4b). The template method and its hooks in one class:
- **`_evaluate_typed_acceptance`** leaves the class for a collaborator beside the typed-check
  evaluator. Its loop body becomes one function that builds a check record and one that applies RC-9's
  blocking matrix. The handler keeps the call.
- **`_llm_call`:** its post-response sequence (dispute split, cap retries, fault, shape log, record) is
  already the single sequence #929 made, and most of its 177 lines are the reasons. Its step table
  decides whether the cap-retry pair (`_cap_exhausted_fact`, `_cap_truncated`) and the sequence become
  one `_settle_response` step, or whether the method stays as it is with the reasons, because size
  alone is not the criterion.
- **`handle`:** the generic path's provenance and empty-emission marking become two steps.

**Unit 3: `_execute_task`.**
- The three closures (`_next_action`, `_route_outcome`, `_record_task_evidence`, about 130 lines over 20
  captured references) become a small per-task router object, built with the run's state and the
  task's envelopes and holding the last failed result.
- The success tail (collection, the authored-manifest bind, pulse boundaries, the gate) becomes
  `_after_task_success`.
- The patched-result swap and the failure bookkeeping become one step.

**Unit 4: `CorrectionRunner`.**
- Its five steps already exist (1.7.5 §4 step 4). What makes them long now is the twenty run-lived
  references re-passed to each step. A frozen `_RoundRefs` carrier holds them once. They're frozen in
  binding, since the lists are the executor's and are mutated by design.
- `_diagnose` splits into the round's evidence (the failure evidence, the deterministic injections,
  contested rows, the round failure and the reserve) and one declared step's dispatch (the loop body).

**Unit 5: `generate_task_plan`.**
- A frozen `_PlanFacts` holds the increment and framing facts (footprint, criterion files, frozen files,
  test scope, evaluation, rejection context).
- The per-step loop's acceptance block (about 30 lines, seven criterion families) becomes
  `_plan_task_acceptance`.
- The envelope's inputs come from one builder.
- The loop drops to about 40 lines.

## 6. Order and box time

1 → 2 → 3 → 4 → 5, as the issue orders them:
- **1 first:** it's the largest.
- **2 after 1:** qa overrides the base's pieces, so 1's steps settle first.
- **3 and 4 after R6:** they change location first.
- **5 last:** it has the strongest golden and needs the least.

Each unit is one to three PRs, then a rebuild and its regression pair (about an hour of box time each,
on TensorFold). Units 2 and 3 each start with their step 0.

## 7. Not on the map

- Any behaviour change, or any defect fix. Each is filed.
- `acceptance_checks.py`, `scaffold.py` and the stack modules (§2).
- `execute_cycle` (221) and `execute_run` (187). They weren't in the issue, and the 1.7.5 map kept them
  out for the same reason: each is a sequence of named calls already.
