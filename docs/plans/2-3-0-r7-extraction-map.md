# 2.3 R7: the largest-units extraction map (#1994)

**Status:** reviewed. The owner approved unit 1's step table on 2026-10-15, and chose to review each
of units 2–5 at the step before its first extraction PR (#1994, comment 6188687592). It reviewed unit 2's
on the same day (§4b; #1994, comment 6191733584). The plan owns R7's
placement (phase 8, after R6). This map owns each unit's scope, its steps, the data that crosses each
step, and the proof each PR carries.

**Granularity:** units 1 and 2 are mapped to the step (§4, §4b). Units 3–5 are mapped to the block here. Each gets
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
| 4 | `test_correction_context_golden.py` (the repair and retest envelopes) and `test_correction_runner.py` | none |
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
