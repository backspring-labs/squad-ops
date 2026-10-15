# 2.3 R7: the largest-units extraction map (#1994)

**Status:** a draft for the owner's review, as 1.7.5's extraction map was reviewed before its first
extraction PR. The plan owns R7's placement (phase 8, after R6). This map owns each unit's scope, its
steps, the data that crosses each step, and the proof each PR carries.

**Granularity:** unit 1 is mapped to the step. Units 2–5 are mapped to the block here. Each gets
its step table in this file, re-measured on the tree it extracts from, and reviewed before its first
extraction PR. Measured on R6's tree (PR #2327), where units 3 and 4 live after the orchestration
move. If R6 lands under `squadops.cycles.execution` instead, only their package changes.

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

## 5. Units 2–5, to the block

**Unit 2: `_CycleTaskHandler`.** The template method and its hooks in one class:
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
