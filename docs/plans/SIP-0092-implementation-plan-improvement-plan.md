# Plan: SIP-0092 Implementation Plan Improvement

## Context

SIP-0092 is a SIP-0086 follow-up that closes three deferred gaps in the implementation plan pipeline:

- **M1 — Typed Acceptance Criteria.** Today `acceptance_criteria` is `list[str]` informational input only; FC3 in `_validate_output_focused` is `included_in_evidence`. M1 introduces typed checks, severity, a `CheckOutcome` status enum, untrusted-input safety, and validator integration.
- **M2 — Separated Plan Authoring.** `_produce_plan` currently runs as a side-effect inside `GovernanceReviewPlanHandler.handle()` (`planning_tasks.py:424`). M2 splits authoring into a new `development.plan_implementation` task and turns `review_plan` into a structured reviewer that emits `plan_review.yaml`.
- **M3 — Plan Changes.** SIP-0086 §6.1.6 specified plan changes as the immutability-preserving evolution path; nothing was implemented. M3 introduces a plan-change schema, a pure structural applier, an execution-aware validator, conservative producer-side restrictions on autonomous correction (`add_task` + `tighten_acceptance` only), and provenance metadata on change-created tasks.

**SIP:** `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` (Rev 2)
**Parent SIP:** `sips/implemented/SIP-0086-Build-Convergence-Loop-Dynamic.md`
**Branch model:** This plan lands on `feature/sip-0092-implementation-plan-improvement` (off main, after SIP acceptance via PR #70). Implementation commits per phase build on this plan per the SIP workflow in `CLAUDE.md`.

The three stages (M1/M2/M3) are independently shippable and can land in separate feature branches if scheduling demands it. The default sequence below ships them in order because M1 produces the typed-check substrate that M3's `tighten_acceptance` operation extends, and M2's reviewer emits `plan_review.yaml` entries that reference M1's typed checks.

---

## Runtime Contracts

These invariants govern implementation across all phases. Numbered to extend SIP-0086's plan (RC-1..RC-8) without renumbering them.

**RC-9 (Severity and outcome status are independent dimensions):**

- *Severity* is authored on the criterion: `error | warning | info`.
- *Outcome status* is produced by the evaluator: `passed | failed | skipped | error`.
- The two are evaluated together. Only the combination `severity=error` AND `status ∈ {failed, error}` blocks validation (contributes to `missing_components` and triggers self-eval/correction).
- `status=skipped` never blocks, regardless of severity. `severity ∈ {warning, info}` never blocks, regardless of status. Both are surfaced in `ValidationResult.checks` evidence for triage.

**RC-9a (Evaluator error ≠ app incompleteness):** `status=error` means the evaluator could not safely or correctly evaluate the criterion (path-escape, regex timeout, command timeout, command-must-be-argv, parser exception). `status=failed` means the generated output did not meet the criterion. When `severity=error` + `status=error` blocks, the surfaced reason in `missing_components` and the self-eval prompt MUST identify the entry as an *evaluator/check failure*, not as missing app behavior — wording like `evaluator-error: <check>: <reason>` rather than `acceptance: <description>`. Repeated evaluator errors on the same criterion across self-eval passes escalate to correction (or operator) instead of looping; see RC-9b.

**RC-9b (Bounded evaluator-error retry, with explicit escalation contract):** A criterion that produces `status=error` on two consecutive evaluations within the same run hits the retry limit. Past the limit:

1. The criterion is **removed from the self-eval feedback list for that criterion** — the self-eval prompt for the same task no longer surfaces it as a gap to fix. (Other criteria continue to drive self-eval normally.) The criterion remains in `ValidationResult.checks` as evidence of permanent error.
2. A **structured validation-escalation event/artifact** is emitted (event type `evaluator_error_persisted`) carrying the criterion fingerprint, the last evaluator-error reason, the task ID, and the count of consecutive errors. This lands on the same escalation surface that handles `max_correction_attempts` exhaustion, so operators see persistent evaluator failures alongside correction exhaustion.
3. The **correction protocol may inspect the escalation event** as part of its decision-making, but **must not treat the evaluator error as missing application behavior**. Specifically: `evaluator-error:<check>` entries in the escalation context must not appear in correction prompts as `acceptance:<description>` strings. The wording boundary from RC-9a is load-bearing here — bad checks, unsafe paths, regex timeouts, or unsupported commands cannot drive `development.repair` loops.

This prevents pathological criteria from driving endless self-eval loops AND from hijacking correction into repair work it shouldn't be doing.

**RC-10 (Plan is untrusted input):** Every value in a typed check is treated as LLM-authored input. Paths are workspace-chrooted; commands are pattern-safelisted argv lists (RC-10a); regex and globs are bounded; symlinks pointing outside the workspace are rejected. Evaluator code never invokes a shell.

**RC-10a (Pattern-based command safelist):** The `command_check_safelist` is a list of *command patterns*, not bare argv[0] values. A pattern names argv[0] *and* the permitted argv[1..] shape. Examples: `python -m py_compile <file>`, `python -m mypy <args>`, `node --check <file>`, `ruff check <args?>`, `tsc --noEmit`, `eslint <args?>`, `pyflakes <file>`. Any of `python -c`, `python -m pip`, `python -m anything-not-listed`, `node -e`, shell strings, or argv that doesn't match a registered pattern produces `status=error` reason `command_not_in_safelist` (treating it as an evaluator error per RC-9a, not as a soft skip — the plan author asked for something we won't run). Pattern entries are operator-controlled config; plan authors cannot extend them.

**RC-11 (Authoring-time validation):** Unknown `check` names, malformed `params`, and unknown `severity` values are rejected by `ImplementationPlan.from_yaml()`. The existing `_produce_plan` retry loop (`planning_tasks.py:572`) treats these as parse failures and re-prompts. Stack-unsupported but well-formed checks are valid plans; they evaluate to `status: skipped`.

**RC-12 (Stack-aware bounded evaluators):** Each typed check declares the stacks it supports. Inputs outside that set produce `status: skipped` with reason `unsupported_stack_or_syntax`. New stacks are added in scoped follow-up PRs, never as heuristic expansion inside an existing check.

**RC-12a (Stack context is authoritative, not guessed):** Framework-level checks (e.g., `endpoint_defined`, `field_present` on Pydantic) require explicit stack context. The evaluator receives stack context from the resolved profile / plan metadata via `HandlerContext` — *not* by sniffing arbitrary file content. File extension (e.g., `.py`, `.ts`) is acceptable for language-level parsing decisions; framework-level decisions ("is this FastAPI?", "is this Pydantic v2?") consult declared stack context. When stack context is unset and a check requires it, the check returns `status: skipped` with reason `unsupported_stack_or_syntax` (NOT `error`), since the absence of context is an authoring/profile gap, not an evaluator failure.

**RC-13 (Original plan immutability):** The approved plan hash and the original plan YAML never change after gate approval. The "current working plan" is always derived as `apply_plan_changes(original, plan_changes)`. The original is the source of truth; plan changes are an append-only audit trail rooted in the original via `parent_plan_hash` over the canonical serialization.

**RC-14 (Pure structural applier; execution-aware validator):** `apply_plan_changes(original, plan_changes)` is a pure function — same inputs always produce the same `WorkingPlan`. Runtime constraints (plan change would invalidate started/completed work) are enforced separately by `validate_plan_change_for_run(plan_change, working_plan, run_state)`. Both must succeed before a plan change is forwarded to the executor.

**RC-15 (Completed-work immutability):** Plan changes affect only the remaining execution plan. They never replace, remove, reorder, or otherwise rewrite the semantic meaning of started or completed task checkpoints. Corrections to completed work are represented as new tasks (`add_task`) — never as mutations of prior ones. This is enforced by the execution-aware validator.

**RC-16 (Conservative autonomous producer):** The autonomous correction protocol may produce plan changes containing only `add_task` and `tighten_acceptance` operations. **In Rev 1 these are the only operations the schema and applier support at all** (per SIP §6.3.2 Rev 3 tightening) — the YAML parser rejects `remove_task`, `replace_task`, and `reorder` at parse time. Those operations remain in the SIP as the future-work design for operator-driven plan changes and `governance.replan`, but they are not present in Rev 1 code.

**RC-17 (Task index ≠ execution order after plan changes):** `task_index` is identity. Execution order is determined by `after_index` and `depends_on` in the working plan. Tooling and operator UI must not assume monotone-index ⇒ monotone-execution.

**RC-18 (Bounded plan change count):** Plan changes per run are bounded by `max_plan_changes` (default 5). After exhaustion, the correction protocol may not produce further plan changes — only patch or escalate. This is the runaway guardrail.

**RC-19 (Backward compatibility per stage):** Each stage preserves prior behavior under its disable flags. M1 off → criteria stay informational. M2 off (`split_implementation_planning: false`) → plan authoring stays inside `review_plan`. M3 loader off (`plan_changes_enabled: false`) → working plan equals original; correction stays in patch-only mode regardless of `correction_plan_changes_enabled`. M3 producer off (`correction_plan_changes_enabled: false`) → correction protocol restricted to `patch` and `escalate` even if loader is on. Misconfiguration (`correction_plan_changes_enabled: true` while `plan_changes_enabled: false`) is rejected at startup as inconsistent — the producer would emit changes the executor would never load.

**RC-20 (Plan change application timing + WorkingPlan as authoritative source at handler entry):** Plan changes land between executor build-plan expansion passes, not mid-task. The chosen mechanism: after a correction-protocol plan change is persisted *and* validated by both the structural applier and `validate_plan_change_for_run`, the executor performs a fresh build-plan expansion for the run — `working = apply_plan_changes(load_original_plan(run), load_plan_changes_for_run(run))` — and materializes envelopes for any newly active tasks (added by `add_task` or unmasked by tightened acceptance) at that boundary. In-flight task envelopes are not interrupted; already-completed checkpoints are not re-materialized.

**Envelope semantics when `plan_changes_enabled=true` (load-bearing rule):** Task envelopes are **identity carriers only**. They may carry `task_index`, `task_type`, role, focus, `expected_artifacts`, and metadata, but **acceptance criteria used for validation MUST be loaded from the current `WorkingPlan` by `task_index` at handler entry**, not from the envelope payload. If envelopes still contain acceptance criteria for legacy reasons, those criteria are non-authoritative once `plan_changes_enabled=true` and the handler must ignore them. This is what lets `tighten_acceptance` actually take effect on already-materialized but not-yet-started tasks: the envelope was materialized with the pre-tighten criteria, but the handler reads the post-tighten criteria from `WorkingPlan` when it runs.

A handler-side test verifies this: seed a task envelope with criteria set A, persist a `tighten_acceptance` plan change adding criterion B, then run the handler — it must validate against criteria A ∪ {B} sourced from `WorkingPlan`, not just criteria A from the envelope.

**RC-21 (Loader hard-fails on inconsistent plan-change state):** If plan changes exist for a run and any of `apply_plan_changes(original, plan_changes)` (hash mismatch, broken chain, structural invariant violation) or `validate_plan_change_for_run` (runtime invariant violation) rejects the chain, the loader does NOT silently fall back to the original plan. Instead it: (a) emits a structured control-plane error with the rejected plan change's `change_id` and reason; (b) marks the run state `plan_changes_inconsistent: true`; (c) prevents further plan-change production for the run; (d) escalates if the rejected plan change was needed for continued execution (e.g., the failed task's correction was contingent on the plan change) — pausing the run pending operator action. Silent fallback is explicitly disallowed because it makes the executor act on a plan the operator never approved as the working plan.

---

## Stage M1 — Typed Acceptance Criteria

Three PRs. Independently valuable: even without M2 or M3, M1 makes today's plans far more discriminating during validation.

### Phase M1.1 — Schema, Parser, Authoring-Time Validation

**Modified / new files:**

| File | Change |
|------|--------|
| `src/squadops/cycles/implementation_plan.py` | Add `TypedCheck` frozen dataclass. Extend `PlanTask.acceptance_criteria` to `list[str \| TypedCheck]`. Update `from_yaml()` to parse mixed lists with the flat-YAML normalization rule (SIP §6.1.1). |
| `src/squadops/cycles/acceptance_check_spec.py` (new) | **Single source of truth for check metadata.** Defines a `CheckSpec` dataclass (`name`, `required_params`, `optional_params`, `param_types`, `supported_stacks`, `requires_stack_context: bool`) and a registry `CHECK_SPECS: dict[str, CheckSpec]`. The parser in `implementation_plan.py` imports this registry to enforce RC-11; the evaluator framework in M1.2 imports the *same* registry to declare its capabilities. No separate `_KNOWN_CHECKS` table. This is the registry-of-record going forward; drift between parser and evaluator is structurally prevented. |

**`TypedCheck` dataclass (canonical internal form):**

```python
@dataclass(frozen=True)
class TypedCheck:
    check: str                  # vocabulary name
    params: dict                # all check-specific keys except check/severity/description
    severity: str = "error"     # error | warning | info
    description: str = ""
```

**Normalization rule:** flat YAML keys → `params` minus `{check, severity, description}`. Prose strings remain `str` and stay informational.

**Parse-time rejections (raise `ValueError`):**

- Unknown `check` name (not in `CHECK_SPECS`).
- Required field for the named check missing or wrong type (per `CHECK_SPECS[name].required_params` / `param_types`).
- `severity` not in `{error, warning, info}`.
- Path field with `..` traversal or absolute path (cheap pre-eval rejection at parse time; full chrooting still applies at evaluation).

**Tests:** `tests/unit/cycles/test_implementation_plan.py` (extend existing file)

- Mixed prose+typed list parses; both forms preserved with correct types.
- Typed-only list parses; each `TypedCheck.params` excludes `{check, severity, description}`.
- Default severity is `error` when omitted.
- Unknown `check` name raises `ValueError` with the offending name in the message.
- Each known check's required-field omission raises `ValueError` (parametrized over the check vocabulary).
- Wrong-type param (e.g., `methods_paths: "GET /runs"` as string) raises `ValueError`.
- Unknown `severity` value raises `ValueError`.
- Absolute path or `..` in path field raises `ValueError`.
- Round-trip: `from_yaml()` → re-serialize via canonical form → `from_yaml()` produces equal plan (load-bearing for M3 hashing in §6.3.6).

### Phase M1.2 — Check Evaluator Framework, Static Checks, Safety

**New files:**

| File | Purpose |
|------|---------|
| `src/squadops/cycles/acceptance_checks.py` | `CheckOutcome`, `BaseCheck`, registry, evaluator implementations. |
| `tests/unit/cycles/test_acceptance_checks.py` | Per-check unit tests including safety rejections. |

**`CheckOutcome` and base class:**

```python
@dataclass(frozen=True)
class CheckOutcome:
    status: str          # passed | failed | skipped | error
    actual: dict         # check-specific evidence
    reason: str          # human-readable summary

class BaseCheck:
    spec: CheckSpec      # references CHECK_SPECS[name] from acceptance_check_spec.py

    async def evaluate(
        self,
        params: dict,
        workspace_root: Path,
        artifacts: list[Artifact],
        context: HandlerContext,   # carries resolved stack context per RC-12a
    ) -> CheckOutcome: ...
```

**Registry:** evaluator implementations register against the canonical `CHECK_SPECS` registry from `acceptance_check_spec.py` (the same one the parser uses — item from RC-11 / single-source-of-truth rule). A `_CHECK_IMPLS: dict[str, type[BaseCheck]]` table maps each spec name to its evaluator class. Startup assertion verifies every entry in `CHECK_SPECS` has an implementation in `_CHECK_IMPLS`. Adding a new check is one entry in `CHECK_SPECS` plus one class registration — no dispatch edit, no parser edit.

**Revision 1 vocabulary:**

| Check | `requires_stack_context` | Stacks | Implementation notes |
|---|---|---|---|
| `endpoint_defined` | true | `fastapi` | AST walk for `@app.METHOD("/path")` and `@router.METHOD("/path")` decorators; path matching tolerant of trailing slash. Stack context comes from resolved profile/plan metadata (RC-12a) — never sniffed from file content. Flask deferred to a separate scoped PR. |
| `import_present` | false (language-only) | `python` (AST), JS/TS regex fallback gated behind `frontend_acceptance_checks` follow-up flag (out of scope here) | Walks `import` and `from ... import ...` nodes. Language detection from file extension (`.py`, `.ts`, `.js`) is sufficient — no framework context required. |
| `field_present` | true | `python` dataclasses, Pydantic v2 models | Walks class body assignments; matches `Annotated[...]` and `Field(...)` declarations. Pydantic-vs-dataclass distinction comes from declared stack context. |
| `regex_match` | false | stack-agnostic | Compiled regex with input-size bound. `count_min` defaults to 1. |
| `count_at_least` | false | stack-agnostic | Glob with workspace-chroot and 10,000-match cap. |
| `command_exit_zero` | false | stack-agnostic; gated by `command_acceptance_checks` flag | Runs in ACI executor; argv-only; pattern-safelisted (RC-10a). |

**Stack context wiring (RC-12a):** `HandlerContext` already carries the resolved profile. The check evaluator reads stack identity from `context.resolved_profile.stack` (or `context.plan.metadata.stack` if SIP-0072's stack registry concretization lands first). When `requires_stack_context=true` and stack is unset, the evaluator returns `status: skipped` reason `unsupported_stack_or_syntax` — not `error`, since this is an authoring/profile gap, not an evaluator failure.

**Safety implementation (RC-10 / RC-10a):**

- Path resolution helper `_safe_resolve(path: str, workspace_root: Path) -> Path` rejects absolute paths, `..` traversal, and symlinks pointing outside `workspace_root`. Returns `CheckOutcome(status="error", reason="path_escapes_workspace")` (RC-9a: evaluator error, not app incompleteness).
- Glob match cap (default 10_000). Exceeding produces `status: error` reason `glob_match_cap_exceeded`.
- Regex compilation guarded by input-size bound; pathological regex against long files produces `status: error` reason `regex_timeout`.
- **Pattern-based command safelist (RC-10a).** `command_check_safelist` is a list of patterns matched against the full argv, *not* just `argv[0]`. Patterns specify the permitted argv shape — examples in RC-10a above. Built-in default safelist:

  | Pattern | Allows |
  |---|---|
  | `python -m py_compile <file>` | exactly `argv = ["python", "-m", "py_compile", <single-file-path>]` |
  | `python -m mypy <args...>` | `argv[0:3] == ["python", "-m", "mypy"]`, remaining args are paths or known mypy flags |
  | `node --check <file>` | exactly `argv = ["node", "--check", <single-file-path>]` |
  | `ruff check <args...>` | `argv[0:2] == ["ruff", "check"]`, remaining args are paths/flags |
  | `tsc --noEmit` | exactly `argv = ["tsc", "--noEmit"]` (cwd = workspace) |
  | `eslint <args...>` | `argv[0] == "eslint"`, remaining args are paths/flags |
  | `pyflakes <file>` | exactly `argv = ["pyflakes", <single-file-path>]` |

  Any of `python -c <anything>`, `python -m pip <anything>`, `python -m <unlisted-module>`, `node -e <anything>`, shell strings, or argv that does not match a registered pattern → `status: error` reason `command_not_in_safelist` (RC-9a: evaluator-error, not skip — the plan asked for something we explicitly won't run, treat it as a check failure rather than silently passing). Shell-string command (single string instead of list) → `status: error` reason `command_must_be_argv`.
- Per-command timeout: default 10s, max 60s. Exceeding produces `status: error` reason `command_timeout` (RC-9a: an evaluator failure mode, not an app failure).
- Command env: clean restricted env (no `LD_PRELOAD`, no `PYTHONPATH` injection).

**Tests:** `tests/unit/cycles/test_acceptance_checks.py`

Per-check parametrized matrix covering `passed` / `failed` / `skipped` / `error`:

- `endpoint_defined`: all paths defined → passed; subset missing → failed with `actual.found` listing what was found and `actual.missing` listing what wasn't; stack context unset → skipped `unsupported_stack_or_syntax` (RC-12a); declared stack is FastAPI but file is not parseable Python AST → error.
- `import_present`: imports present → passed; module imported but symbol not imported → failed; file extension not in `{.py, .ts, .js}` → skipped.
- `field_present`: all fields declared on the named class → passed; partial → failed with `actual.missing`; class not found in file → failed `class_not_found`; stack context unset → skipped.
- `regex_match`: matches ≥ `count_min` → passed; matches < `count_min` → failed with `actual.match_count`; pathological regex on big input → error.
- `count_at_least`: glob meets minimum → passed; below minimum → failed; cap exceeded → error.
- `command_exit_zero`: argv matches a safelist pattern and exits 0 → passed; matches pattern but exits non-zero → failed with `actual.stdout_tail`/`stderr_tail`/`exit_code`; argv does not match any safelist pattern → **error reason `command_not_in_safelist`** (RC-10a — not skipped); shell string → error reason `command_must_be_argv`; over timeout → error reason `command_timeout`.

Pattern-matching tests (parametrized on `command_exit_zero`):

- `["python", "-m", "py_compile", "backend/main.py"]` → matches; runs.
- `["python", "-c", "print(1)"]` → no pattern match → error `command_not_in_safelist`.
- `["python", "-m", "pip", "install", "anything"]` → no pattern match → error.
- `["python", "-m", "unknown_module"]` → no pattern match → error (RC-10a explicitly: argv[0]=python alone is insufficient).
- `["ruff", "check", "src/"]` → matches.
- `"ruff check src/"` (string instead of list) → error `command_must_be_argv`.

Safety tests (parametrized across check types):

- Path with `..` → `status: error` reason `path_escapes_workspace`.
- Absolute path → `status: error` reason `path_escapes_workspace`.
- Symlink in workspace pointing to `/etc/passwd` → `status: error` reason `path_escapes_workspace`.
- Glob `**/*` against a workspace with > cap entries → `status: error` reason `glob_match_cap_exceeded`.

### Phase M1.3 — Validator Integration, Self-Eval Prompt, Authoring Prompt

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/cycle_tasks.py` | Replace today's informational FC3 (`cycle_tasks.py:965`) with typed-check evaluation. Severity-weighted contribution to `missing_components` per RC-9. Failed-check descriptions surfaced into the self-eval follow-up prompt. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | Extend the plan-authoring prompt (in `_produce_plan`, `planning_tasks.py:475–504`) to document the typed-check vocabulary, severity, flat-YAML shape, and safety rules. Examples-first (one concrete typed criterion per check type). |

**Validator integration (sketch, replaces `cycle_tasks.py:965` block):**

```python
typed = [c for c in inputs.get("acceptance_criteria", []) if isinstance(c, TypedCheck)]
prior_errors = self._load_prior_evaluator_errors(run_state, task_id)  # RC-9b: per-criterion error count

for criterion in typed:
    outcome = await self._evaluate_typed_check(criterion, artifacts, context)
    checks.append({
        "check": f"acceptance:{criterion.check}",
        "severity": criterion.severity,
        "params": criterion.params,
        "description": criterion.description,
        "status": outcome.status,
        "actual": outcome.actual,
        "reason": outcome.reason,
    })

    # RC-9: severity AND status are independent dimensions. Only error+{failed,error} blocks.
    if criterion.severity != "error":
        continue
    if outcome.status == "failed":
        # RC-9a: app-incompleteness wording.
        missing.append(f"acceptance:{criterion.description or criterion.check}")
    elif outcome.status == "error":
        criterion_key = criterion.fingerprint()  # stable id of criterion shape
        prior_count = prior_errors.get(criterion_key, 0)
        # RC-9b: drop from feedback after 2 consecutive errors; escalate via correction surface.
        if prior_count < 2:
            # RC-9a: evaluator-error wording, distinct from app-incompleteness.
            missing.append(f"evaluator-error:{criterion.check}: {outcome.reason}")
        else:
            self._escalate_persistent_evaluator_error(criterion, outcome)
        self._record_evaluator_error(run_state, task_id, criterion_key, prior_count + 1)
    # status in {passed, skipped} → never blocks
```

`fingerprint()` returns a stable key from `(check, params, severity)` so retries against the same criterion share an error counter, but a tightened-acceptance plan change producing a distinct shape resets it.

**Config keys (extend `_APPLIED_DEFAULTS_EXTRA_KEYS`):**

| Key | Default | Notes |
|---|---|---|
| `typed_acceptance` | `true` | Master flag. False → typed checks parse but evaluate to `skipped` reason `typed_acceptance_disabled`. |
| `command_acceptance_checks` | `true` (`false` in `selftest`) | Independent rollback for `command_exit_zero` only. |
| `command_check_safelist` | built-in safelist | Operator-controlled; plan authors cannot extend it. |

**Tests:**

Unit (`tests/unit/capabilities/test_cycle_tasks.py` extension):

RC-9 / RC-9a / RC-9b coverage matrix (parametrized over `(severity, status)`):

| severity | status | blocks? | `missing_components` entry |
|---|---|---|---|
| `error` | `passed` | no | — |
| `error` | `failed` | yes | `acceptance:<desc>` (app-incomplete) |
| `error` | `error` (1st) | yes | `evaluator-error:<check>: <reason>` |
| `error` | `error` (2nd) | yes | `evaluator-error:<check>: <reason>` |
| `error` | `error` (3rd+) | NO; escalated | dropped from prompt; surfaced via correction-escalation channel |
| `error` | `skipped` | no | — |
| `warning` | any | no | — (visible in evidence only) |
| `info` | any | no | — (visible in evidence only) |

Tests:

- Plan with typed `endpoint_defined` (severity `error`) and incomplete generated code → `missing_components` contains `acceptance:<desc>`; `ValidationResult.checks` includes the failed entry.
- Same plan, severity `warning` → `missing_components` empty; check appears in evidence.
- Plan with typed `endpoint_defined`, stack context unset → `status: skipped` reason `unsupported_stack_or_syntax`; not in `missing_components` regardless of severity.
- Plan with `command_exit_zero` argv `["python", "-c", "print(1)"]` and severity `error` → `status: error` reason `command_not_in_safelist`; `missing_components` entry is `evaluator-error:command_exit_zero: command_not_in_safelist` (not `acceptance:...`).
- Same `command_exit_zero` retried twice across self-eval passes → both errors surfaced; on the third evaluation the criterion is escalated and removed from the self-eval prompt feedback list (RC-9b).
- Plan with `typed_acceptance: false` in config → all typed checks evaluate to skipped with `typed_acceptance_disabled`.
- Plan with `command_acceptance_checks: false` → only `command_exit_zero` checks skip; static checks still evaluate.

Integration (`tests/integration/cycles/test_plan_acceptance.py`, new):

- Run a focused build subtask end-to-end with seeded LLM responses: complete code passes typed checks; partial code fails with specific `missing_components`; self-eval second pass receives the failed-check descriptions in its follow-up prompt and produces a corrected output that passes.

---

## Stage M2 — Separated Plan Authoring

**Conditional on the M1 → M2 gate.** Do not start this stage until the gate evaluation doc (`docs/plans/SIP-0092-gate-M1-evaluation.md`) is committed showing the criteria are met. See the Milestone Gates section below.

Two PRs. Default-off behind `split_implementation_planning: bool = false`. Default-flip is a small follow-up PR after metrics meet SIP §6.2.4 criteria — explicitly out of scope for this stage's first delivery.

### Phase M2.1 — `development.plan_implementation` Handler

**Modified / new files:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/_plan_authoring.py` (new) | **Shared `PlanAuthoringService`**: extracts the body of `_produce_plan` (`planning_tasks.py:432–620`) into a service with one entry point — `produce_plan(prompt_inputs, llm_client, run_state) -> ImplementationPlan`. The retry loop, prompt construction, role/task_type constraint logic, and YAML validation move here intact. Both legacy and split paths call this service. NO duplicated logic. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceReviewPlanHandler.handle()` calls `PlanAuthoringService.produce_plan(...)` when `split_implementation_planning: false` (replacing the inline call to `_produce_plan`). When `split_implementation_planning: true`, this handler does NOT call the service at all — it consumes the plan produced by the upstream `development.plan_implementation` step. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `DevelopmentPlanImplementationHandler.handle()` calls the same `PlanAuthoringService.produce_plan(...)` and returns the plan as its primary output artifact. |
| `src/squadops/cycles/task_plan.py` | Add `development.plan_implementation` to `PLANNING_TASK_STEPS` immediately before `governance.review_plan`, gated on `split_implementation_planning`. |
| Capability registry (where planning task types are registered) | Register `development.plan_implementation`. |

**Why a service, not a verbatim move:** verbatim move would leave the legacy path with a near-duplicate of the new code, guaranteed to drift on the next prompt or retry-loop tweak. Extracting first means both paths share one implementation; the only difference is *which handler invokes it* and *whether the resulting plan is the `review_plan` primary output or its review input*. This also makes M2.2's revision loop (`development.plan_implementation_revise`) trivial: it's a third caller of the same service with concerns appended to `prompt_inputs`.

**Backward compatibility (RC-19):** when `split_implementation_planning: false`, the legacy path calls `PlanAuthoringService.produce_plan(...)` with the same `prompt_inputs` as today's `_produce_plan` invocation, producing a byte-identical plan given identical seeded LLM responses. The verbatim-equivalence test below is the regression anchor.

**Config keys:**

| Key | Default |
|---|---|
| `split_implementation_planning` | `false` |

**Tests:**

- Unit: `DevelopmentPlanImplementationHandler` produces a `ImplementationPlan` artifact with the same content shape as today's `_produce_plan` for an identical seeded LLM response. (Baseline-equivalence test: same input, same output, different handler.)
- Unit: with `split_implementation_planning: true`, `review_plan` does not call `_produce_plan` (assert via spy/mock-call-count *paired* with output assertion that the plan artifact carried forward is the upstream one).
- Integration: planning phase end-to-end with the flag on produces the same final approved plan as the flag off, given identical seeded LLM responses for both plan authoring and review.

### Phase M2.2 — Reviewer Logic, `plan_review.yaml`, Revision Loop

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceReviewPlanHandler.handle()` (under `split_implementation_planning: true`) emits a `plan_review.yaml` artifact with the SIP §6.2.2 schema. Reviewer prompt is structured against the plan artifact. |
| `src/squadops/cycles/plan_review.py` (new) | `PlanReview` frozen dataclass + `from_yaml()` parser. Enforces the rule: `review_status: revision_requested` requires at least one structured concern with `target_task_index` or `prd_requirement` set. Pure prose revision requests are normalized to `approved_with_concerns` (the SIP §6.2.2 rule). |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `DevelopmentPlanImplementationReviseHandler`. Re-runs plan authoring with the structured concerns appended to the prompt. Triggered only when `review_status: revision_requested` and revision count < `max_planning_revisions`. |
| `src/squadops/cycles/task_plan.py` | Conditional `development.plan_implementation_revise` step inserted after `review_plan` when revision is requested and the revision budget remains. After exhaustion, planning proceeds with the latest plan; unresolved concerns are documented in `operator_notes`. |
| `governance.correction_decision` handler | Add the **non-operative `structural_plan_change_candidate` diagnostic field** to the correction-decision log artifact. Allowed values: `none | add_task | tighten_acceptance | other`. The correction LLM's prompt is extended to elicit this field even though M3.3's producer is not yet enabled. This is the diagnostic signal the M2 → M3 gate measures (see Milestone Gates section). The field is non-operative — it does not execute a plan change and does not affect the actual `decision`. |

**`PlanReview` schema (matches SIP §6.2.2):**

```python
@dataclass(frozen=True)
class PlanReview:
    version: int
    review_status: str       # approved | revision_requested | approved_with_concerns
    reviewer_confidence: str
    target_plan_id: str
    coverage_concerns: list[CoverageConcern]
    dependency_concerns: list[DependencyConcern]
    role_concerns: list[RoleConcern]
    acceptance_concerns: list[AcceptanceConcern]
    revision_instructions: str = ""
    operator_notes: str = ""
```

Each `*Concern` is a frozen dataclass with the fields listed in SIP §6.2.2.

**Acceptance concern → typed-check link:** `AcceptanceConcern.suggested_check` is parsed as a `TypedCheck` (M1's dataclass). This is the integration point that lets the reviewer suggest concrete machine-evaluable criteria, not just prose.

**Config keys:**

| Key | Default |
|---|---|
| `max_planning_revisions` | `1` |

**Tests:**

- Unit: `PlanReview.from_yaml()` parses a fully-populated review; revision_requested without any structured concern returns `approved_with_concerns` and surfaces a normalization warning in evidence.
- Unit: `revision_instructions` prose is preserved when concerns also exist.
- Unit: `AcceptanceConcern.suggested_check` round-trips through `TypedCheck` parsing.
- Integration: a planning run where the reviewer requests revision with one structured `acceptance_concern` produces a revised plan whose subtask matches `target_task_index` and now contains the suggested typed check.
- Integration: revision budget exhaustion proceeds to gate with the latest plan and `operator_notes` populated; no infinite loop.

**Default-flip work (out of scope for this stage):** the flip from `split_implementation_planning: false` to `true` is a separate small PR after the SIP §6.2.4 criteria are met across a tracking window. This plan does not commit to that PR's timing.

---

## Stage M3 — Plan Changes

**Conditional on the M2 → M3 gate.** Do not start this stage until the gate evaluation doc (`docs/plans/SIP-0092-gate-M2-evaluation.md`) is committed showing the criteria are met. See the Milestone Gates section below.

Three PRs. Default behavior split across two flags (per Rev 3 tightening):

- `plan_changes_enabled` (loader/applier) — when true, the executor loads any persisted plan-change artifacts and applies them at re-expansion boundaries. Zero plan changes produced ⇒ working plan equals original ⇒ no observable change vs today.
- `correction_plan_changes_enabled` (autonomous producer) — when true, the correction protocol may emit plan changes. When false, correction is restricted to `patch` and `escalate` regardless of loader state.

This split lets us ship and test loader behavior (M3.2) before authorizing the autonomous correction protocol to produce plan changes (M3.3). Default rollout has both off; each is enabled per-profile after its phase ships and the milestone gate confirms readiness.

**Rev 1 operation scope (per SIP §6.3.2 Rev 3 tightening):** Rev 1 implements **only `add_task` and `tighten_acceptance`** in the schema, applier, validator, and producer. The other three operations (`remove_task`, `replace_task`, `reorder`) are **deferred from code entirely** — they remain in the SIP as the future-work design for operator plan changes and `governance.replan`, but they have no dataclass, no applier branch, and no tests in this plan's PRs. A plan change YAML containing a deferred operation fails parsing. This narrowing is a deliberate scope cut, not a fallback.

### Phase M3.1 — Plan Change Schema and Pure Structural Applier

**New files:**

| File | Purpose |
|------|---------|
| `src/squadops/cycles/plan_change.py` | `PlanChange` dataclass + sub-types per operation; `apply_plan_changes()` pure function; canonical-serialization hashing helper. |
| `tests/unit/cycles/test_plan_change.py` | Per-operation applier tests, identity invariants, hash chain checks. |

**Operation types — Rev 1 scope (per SIP §6.3.2 Rev 3 tightening):**

| Op | Dataclass | Status |
|---|---|---|
| `add_task` | `AddTaskOp(after_index: int, task: PlanTask)` | **Rev 1** |
| `tighten_acceptance` | `TightenAcceptanceOp(task_index: int, add_criteria: list[str \| TypedCheck])` | **Rev 1** |

Deferred to future work (no dataclass, no applier branch, no tests in Rev 1):

- `remove_task` — operator/`governance.replan` only
- `replace_task` — operator/`governance.replan` only
- `reorder` — operator/`governance.replan` only

The YAML parser must reject plan-change documents that contain any deferred operation with a clear error message (`unsupported_operation_in_rev_1`).

**Canonical hashing (SIP §6.3.6):** dedicated helper `canonical_plan_hash(plan: ImplementationPlan) -> str`. Sorted keys, normalized whitespace, deterministic list ordering, SHA-256. Must round-trip stable across YAML re-saves; the round-trip test from M1.1 is the regression anchor.

**`apply_plan_changes(original, plan_changes) -> WorkingPlan`** (pure):

1. Verify `plan_changes[0].parent_plan_hash == canonical_plan_hash(original)`. Mismatch → `PlanChangeHashMismatch`.
2. Verify the chain: `plan_changes[i].parent_change_id == plan_changes[i-1].change_id` for `i ≥ 1`; first plan change has `parent_change_id = null`. Mismatch → `PlanChangeChainBroken`.
3. Verify `change_id` uniqueness across the chain. Collision → `PlanChangeIdCollision`.
4. Apply each plan change's operations in order. Per-op invariants for Rev 1:
   - `add_task`: new index strictly greater than current max across original + applied plan changes; non-empty contract (≥1 expected_artifact OR ≥1 error-severity typed criterion); dependencies must reference existing (active) tasks in the working plan.
   - `tighten_acceptance`: append-only; existing criteria preserved unchanged; severity may rise (`warning → error`) but not fall.
   - Any other operation type → reject at parse time (`unsupported_operation_in_rev_1`) before reaching the applier.
5. Returns a `WorkingPlan` with the original task list plus added tasks, and a derived execution order honoring `after_index` and `depends_on`.

(Rev 1 scope means the applier never sees `remove_task`, `replace_task`, or `reorder` — those are rejected during parsing. The `WorkingPlan` therefore has no tombstoning logic in Rev 1; tombstoning is part of the future-work `remove_task` / `replace_task` design but does not ship now.)

**`WorkingPlan`:** identical task identity (indices, deterministic IDs) for original tasks; added tasks carry their (change-assigned) indices.

**Loosening explicitly unsupported.** Severity downgrade in `tighten_acceptance` raises `PlanChangeLoosensAcceptance`. Loosening will not be supported in any future operation either.

**Tests:**

Per-operation (Rev 1 scope):

- `add_task`: index monotonicity enforced; empty-contract addition rejected; dependency on a non-existent index rejected.
- `tighten_acceptance`: append-only enforced; severity-raise allowed; severity-downgrade rejected.

Parse-time rejection of deferred ops:

- A plan-change YAML containing `op: remove_task`, `op: replace_task`, or `op: reorder` raises `UnsupportedOperationInRev1` at parse time, before the applier runs. Test parametrized over the three op names.

Chain and hash:

- Mismatched `parent_plan_hash` raises `PlanChangeHashMismatch`.
- Broken chain (gap in `parent_change_id`) raises `PlanChangeChainBroken`.
- Duplicate `change_id` in chain raises `PlanChangeIdCollision`.
- Canonical hash stable across YAML re-save (round-trip from M1.1 extended over the plan as a whole).

Identity:

- `task-{run}-m{idx}` IDs for original tasks unchanged after any number of plan changes.
- Added task IDs deterministic from `(run_id, new_index, task_type)` and unique.

Loosening:

- Any operation that would drop or weaken a criterion raises `PlanChangeLoosensAcceptance` regardless of who produced it.

### Phase M3.2 — Execution-Aware Validator, Loader Integration, Provenance

**Modified / new files:**

| File | Change |
|------|--------|
| `src/squadops/cycles/plan_change.py` | `validate_plan_change_for_run(plan_change, working_plan, run_state) -> list[ValidationError]` (SIP §6.3.4). |
| `src/squadops/cycles/task_plan.py` | Update `_replace_build_steps_with_plan` (`task_plan.py:341`) — and a renamed `_load_plan_for_run` helper if absent — to load original plan + plan changes and apply them: `working = apply_plan_changes(load_original_plan(run), load_plan_changes_for_run(run))`. Existing materialization runs against `working`. **Re-expansion timing per RC-20:** the loader is called at executor build-plan expansion boundaries (initial expansion at gate, and after each accepted plan change), never mid-task. Materialized envelopes for newly-active tasks are produced at that boundary. Already-materialized but not-yet-started tasks pick up `tighten_acceptance` updates via re-reading the working plan at handler entry — handlers MUST resolve criteria from the working plan at execution time (verified by handler-side test). |
| `src/squadops/api/routes/cycles/runs.py` | Extend forwarding path that today carries `control_implementation_plan` artifacts (`af306d3`, `075fd9e`) to also carry every `control_implementation_plan_change` for the run, ordered by `parent_change_id` chain. |
| `src/squadops/cycles/task_plan.py` | When materializing an envelope from an change-added task, populate metadata: `change_id`, `change_operation_index`, `change_reason`, `correction_decision_id` (when produced by correction protocol). |
| Persistence layer (cycle registry / artifact store) | Recognize `artifact_type: "control_implementation_plan_change"` (extend `ArtifactType` enum). |

**Execution-aware validator rejection rules (Rev 1 scope):**

- `tighten_acceptance` targeting a started/completed task → reject (`plan_change_tightens_started_task`). Even though the operation is append-only on criteria, mutating acceptance for in-flight or completed work would change what "passing" means for an artifact that already exists. Tightening is allowed only on not-yet-started tasks.
- `add_task` whose `depends_on` references a non-existent index → reject (`plan_change_depends_on_unknown`).

The validator does not need rules for `remove_task` / `replace_task` / `reorder` because those operations cannot reach this code path in Rev 1 — they're rejected at parse time (M3.1). Reservations for those rejection rules will land alongside the future operations in their own follow-up.

`apply_plan_changes(original, plan_changes)` must succeed *and* `validate_plan_change_for_run` must return empty before a plan change is forwarded to the executor.

**Loader hard-fail behavior (RC-21).** When `apply_plan_changes` or `validate_plan_change_for_run` rejects the plan-change chain, the loader does NOT silently fall back to the original plan. The loader:

1. Emits a structured control-plane error (event type `plan_change_chain_rejected`) with the rejected plan change's `change_id`, the rejection reason, and the run id.
2. Sets run state `plan_changes_inconsistent: true` (persisted on the cycle registry row).
3. Marks the run as ineligible for further plan-change production — the correction protocol consults this flag and falls back to `patch` or `escalate` for the remainder of the run.
4. If the rejected plan change's predecessor was successfully applied, execution continues against that earlier valid working plan (the rejected plan change is discarded; everything before it in the chain stands).
5. If no valid predecessor exists (rejection is on the very first plan change) AND the rejected plan change was needed for continued execution (a downstream task is blocked on it), the loader **pauses the run pending operator action** rather than continuing on a stale plan. The operator surface receives the structured error from step 1 with sufficient context to choose: roll forward via re-gate with corrected plan change, abort, or unblock manually.

Silent fallback to the original plan is explicitly disallowed because the executor would act on a plan the operator never approved as the working plan, which violates RC-13's "original is the source of truth, working is what the executor acts on, and the two are linked by an unbroken plan-change chain."

**Config keys:**

| Key | Default |
|---|---|
| `plan_changes_enabled` | `true` |
| `max_plan_changes` | `5` (selftest profile: `2`) |

**Tests:**

Unit (`validate_plan_change_for_run`):

- Each rejection rule fires for the matching `(operation, run_state)` pair (parametrized).
- Safe plan change (`add_task` only, dependencies satisfied) returns empty list.
- `tighten_acceptance` on a not-yet-started task → safe.
- `tighten_acceptance` on an in-flight task — explicit decision: rejected in Revision 1 to match completed-work immutability spirit even though it's append-only on criteria. (Encoded as a separate test with the chosen behavior; revisit only after operator feedback.)

Integration (`tests/integration/cycles/test_plan_change_loader.py`, new):

- 0 plan changes: working plan equals original (regression guard for default-on rollout).
- 1 plan change (`add_task`): loader produces working plan with the new task at re-expansion boundary; materialized envelope carries provenance metadata fields (assert exact field values, not just presence).
- N plan changes in chain: ordering is `parent_change_id`-chain regardless of `created_at` (RC-13 / SIP §6.3.6).
- **Hash mismatch on first plan change → loader emits `plan_change_chain_rejected` event, sets `plan_changes_inconsistent: true`, blocks further plan-change production, and (since no valid predecessor exists) pauses the run pending operator action.** Test asserts: structured event emitted with correct fields, run-state flag set, correction protocol reads the flag and falls back to patch/escalate, run marked paused (not silently continued on original plan).
- Hash mismatch on third plan change in a chain of three → loader keeps the first two applied, discards the third, marks `plan_changes_inconsistent: true`, blocks further plan-change production. Run continues against the working plan derived from the first two plan changes (no pause if no downstream task is blocked).
- `tighten_acceptance` plan change accepted between materialization and execution of a not-yet-started task → handler resolves the tightened criteria at execution time from the working plan (RC-20), not from the snapshot at materialization. Test seeds a tightened-acceptance plan change against task index 5 after task 5's envelope was materialized but before it ran; assert the validator sees the tightened criteria.

### Phase M3.3 — Correction-Protocol Integration (Restricted Producer)

**Modified files:**

| File | Change |
|------|--------|
| `governance.correction_decision` handler (location TBD per current handler layout) | Add `decision: plan_change` branch. Producer constructs `plan_change.yaml` containing only `add_task` and/or `tighten_acceptance` operations (RC-16). Any other operation produced here is a programming error and is rejected by `validate_plan_change_for_run` regardless. |
| Same handler | Bound by `max_plan_changes`; on exhaustion, falls back to `decision: patch` or `decision: escalate`. |
| Same handler | Populates `correction_decision_id` linking the plan change back to the correction event. |

**Producer construction rule:** the LLM is prompted to choose between `patch`, `plan_change (add_task)`, `plan_change (tighten_acceptance)`, and `escalate`. The handler enforces the operation restriction in code; even if the LLM emits a different op, it is dropped before the plan change is persisted, with a structured warning.

**Tests:**

Unit (correction handler):

- Seeded `SEMANTIC_FAILURE` warranting an additional task → handler emits `decision: plan_change` with one `add_task`; plan change parses; `correction_decision_id` populated.
- Seeded failure warranting tightened criteria → handler emits `decision: plan_change` with one `tighten_acceptance`.
- Seeded failure where LLM proposes `remove_task` → handler drops the op, emits structured warning, falls back to `decision: patch`. (Test asserts both the warning emission and the fallback decision.)
- `max_plan_changes` exhausted → handler does not emit plan change; falls back to patch or escalate.

End-to-end (`tests/integration/cycles/test_plan_change_correction_loop.py`, new):

- Long-cycle group_run with seeded responses reproducing SIP §7's example: subtask 6 fails `regex_match count_min: 5`; correction protocol fires; plan change produced (one `add_task` + one `tighten_acceptance`); execution-aware validator approves; `_load_plan_for_run` produces the expected working plan on next executor pass; subtask 9 runs with `change_id`/`correction_decision_id`/`change_reason` metadata; closeout artifact references original + plan change + working.
- Same scenario but the plan change would target subtask 1 (already completed) for `remove_task` — execution-aware validator rejects; correction falls back to patch.

---

## Milestone Gates

The three stages ship as one SIP, but **M2 and M3 are conditional**. Each is gated on evidence collected from regression cycles run after the prior stage lands. The default is **stop and re-evaluate** — proceeding to the next stage requires meeting the gate's criteria. This converts the stage sequence from a linear plan into an evidence-driven one, so we don't pay the cost of M2 and M3 on hypothetical failure modes.

### Why gates, not pre-commitment

M1 has concrete prod evidence forcing the issue (filename-only validation passing broken code). M2 and M3 are designing against acknowledged-tradeoff failure modes (M2: proposer-judge collapse per SIP-0086 §6.1.3; M3: plan immutability blocks long-cycle adaptability) — real concerns, but without sustained-load prod evidence on the post-SIP-0086 plan artifact. Gates make the next-stage decision a question evidence answers, not a decision the SIP locks in up-front.

### What counts as a "long-cycle group_run" for gate measurement

Gate samples are long-cycle group_run runs, defined as:

- **Profile:** the `validation` profile (defined in §6.4.1 / Profile Config Examples). It runs M1 at implementation-profile depth (`max_self_eval_passes: 2`, `max_correction_attempts: 3`) with M2 and M3 still off, so the typed-check signal and correction-decision diagnostics accumulate without M2/M3 confounding the measurement. Materially longer execution budget than the historical 1-hour smoke cycles — ≥2 hours wall-clock or until natural termination, whichever comes first. The same profile shape with M2/M3 flags flipped on becomes the M2 → M3 gate's measurement profile after those stages ship.
- **Reaches plan-relevant execution:** the run reaches at least the planning-phase gate, exposing plan-authoring, plan-validation, plan-review (when M2 is on), or correction behavior. Runs that fail before planning completes due to **infrastructure-only failures unrelated to the plan artifact** (RabbitMQ outage, Postgres connection refused, OOM kill, cosmic-ray restart) are **excluded** from the sample.
- **Inclusion when build-phase fails:** runs that reach planning or build and surface plan, validation, correction, or review behavior count toward the sample **even if they ultimately fail to produce a working app**. The gate is measuring whether SIP-0092's machinery is doing real work, not whether the squad is shipping perfect apps.

This makes the gate sample auditable. Each gate evaluation doc must list the cycle IDs in scope and which (if any) were excluded under the infrastructure-failure rule.

### Gate M1 → M2

Proceed to Stage M2 only when **all** of the following hold across a tracking window of ≥10 long-cycle group_run cycles run with M1 enabled:

| Criterion | Threshold | Why |
|---|---|---|
| Typed-acceptance evaluator-error rate (RC-9b) | <5% of typed checks per cycle | Pathological evaluator errors mean M1 itself is misbehaving; ship M2 on top of an unstable base and the signal is noise. |
| Cycles where typed acceptance changed an outcome | ≥5 of 10 cycles show at least one typed-check `failed` that triggered self-eval or correction (and would have passed under filename-only validation) | Confirms M1 is doing real work, not decorative. |
| Cycles with a planning defect detectable from plan + PRD before build | ≥3 of 10 cycles show a planning defect identified during post-run review where the defect is **visible from the plan artifact plus PRD/test strategy alone** (no need to inspect build outputs) **and** the defect maps to one of M2's `plan_review.yaml` concern categories: `coverage`, `dependency`, `role`, or `acceptance` | This is the M2-justification criterion. The criterion proves the defect lives in M2's detection surface (i.e., a structured reviewer with access to plan + PRD could have caught it) without claiming Max definitely would have. If plans are coming out clean under M1's discipline, the proposer-judge collapse isn't load-bearing and M2 should defer. |

If any criterion fails, **M2 is spun out as a separate proposed SIP** (`SIP-Implementation-Plan-Reviewer-Separation`) that re-litigates the design with the evidence-in-hand.

**Alternative authoring model on the table.** A sibling proposed SIP — [`SIP-Multi-Role-Plan-Authoring`](../../sips/proposed/SIP-Multi-Role-Plan-Authoring.md) — argues that both M1's combined-author/reviewer and M2's split (Neo authors, Max reviews) share a sole-broker structural property, and proposes a propose-merge model where each contributing role authors plan tasks for its domain and Max merges. The M1 → M2 gate evaluation should treat the gate's "is M2 needed?" question as "is *some* authoring change needed, and if so, which model?" — with three paths: ship M2 as written, ship the multi-role alternative, or ship neither and revisit. The evaluation doc must explicitly record which path was chosen and why; if a path other than M2-as-written wins, M2 is the spun-out SIP rather than the alternative.

### Gate M2 → M3

Proceed to Stage M3 only when **all** of the following hold across ≥10 long-cycle cycles with M2 enabled (`split_implementation_planning: true`):

| Criterion | Threshold | Why |
|---|---|---|
| Reviewer non-rubber-stamp rate | ≥3 of 10 cycles show the reviewer (Max) requesting at least one structured revision the proposer (Neo) would not have caught alone | Confirms M2 is solving the proposer-judge collapse, not just adding a second LLM call. If Max approves everything, M2 isn't earning its complexity. |
| Revision-loop activation rate | <50% of cycles enter the revision loop | If the reviewer is requesting revisions on most cycles, the prompt or rubric is wrong. Fix M2 before stacking M3 on top. |
| Cycles where autonomous correction identified a structural-change candidate | ≥3 of 10 cycles show correction-decision logs with `structural_plan_change_candidate ∈ {add_task, tighten_acceptance}` (see diagnostic field below) | This is the M3-justification criterion. Measured from a non-operative diagnostic field, not speculation. If correction is consistently choosing `patch`, plan-changes are solving a problem we don't have and M3 should defer. |
| Plan-quality regression check | Plan YAML validity rate ≥ baseline (per SIP §6.2.4) | Ensures M2 didn't regress the artifact M1 is built on. |

If any criterion fails, **M3 is spun out as a separate proposed SIP** (`SIP-Implementation-Plan-Changes`) with the gate evidence appended to its motivation section.

#### Diagnostic field for measuring M3 demand (added during M2 tracking, before M3 ships)

The M2 → M3 gate's "structural change candidate" criterion needs a measurable signal that doesn't require M3 to be implemented. The correction-decision handler (`governance.correction_decision`) records a non-operative diagnostic field in its decision log artifact during M2 tracking:

```yaml
# correction_decision.yaml (excerpt)
decision: patch                                 # the operative decision (what actually runs)
structural_plan_change_candidate: add_task      # diagnostic only — what the LLM would have chosen
                                                # if M3.3 were enabled
structural_plan_change_rationale: |
  Subtask 6 failed regex_match count_min=5; coverage gap requires a new subtask
  for join/leave endpoint tests, not a re-run of subtask 6.
```

Allowed values: `none | add_task | tighten_acceptance | other`.

- `none` — the correction LLM judged `patch` or `escalate` adequate; no structural change considered.
- `add_task` / `tighten_acceptance` — the LLM judged a structural plan change would be appropriate. These are the M3-relevant signal.
- `other` — the LLM proposed `remove_task` / `replace_task` / `reorder`; recorded for visibility but does not contribute to the M2 → M3 gate criterion (those operations are out of Rev 1 scope per §6.3.2).

The field is non-operative: it does not execute a plan change, does not gate the cycle, does not affect the actual `decision`. It exists only so the M2 → M3 gate can measure whether plan-change demand actually appears in production. The prompt that elicits it is added in M2.2 (so it's available throughout the M2 → M3 tracking window) and reused by M3.3's producer when that ships.

### Evaluation artifacts

Each gate evaluation produces a short doc **hand-authored by the human implementer** and committed to this repository at exactly:

- `docs/plans/SIP-0092-gate-M1-evaluation.md` (gates M1 → M2)
- `docs/plans/SIP-0092-gate-M2-evaluation.md` (gates M2 → M3)

These are not cycle outputs and are not auto-generated. They are release-style summary docs *about the SIP rollout*, in the same class as the plan doc itself. The metrics they cite are gathered from the cycle artifacts that already land at `data/artifacts/group_run/cyc_*/run_*/art_*/` plus LangFuse traces plus correction-decision logs — the implementer reads those and writes the summary. (Once hardening-plan item #3 — Cycle Evaluation Scorecard — ships, the metrics gathering can be automated, but the proceed/defer decision stays human.)

Each evaluation doc contains:

- **Tracking window** — the specific `cyc_*` IDs included in the evaluation, so the underlying evidence is auditable.
- **Per-criterion measured values** — one row per gate criterion with the threshold, the measured value, and pass/fail.
- **Proceed / defer decision** — explicit, with the signer (implementer name) and date.
- **If defer** — name and link the spun-out proposed SIP (`SIP-Implementation-Plan-Reviewer-Separation` or `SIP-Implementation-Plan-Changes` in `sips/proposed/`) and append the gate evidence to its motivation section.

**Commit gate (load-bearing):** the evaluation doc must exist on the SIP-0092 branch and link the cycle IDs **before the next stage's first PR opens**. The evaluation commit is the gate. This is what makes the pause real instead of pro forma — without a written, signed summary citing specific cycles, the next-stage PR cannot start.

### What gates do *not* govern

- **Bug fixes within an already-shipped stage.** If M1 ships and we discover a typed-check evaluator bug, fix it in place — that's not a new stage.
- **Stage-internal sequencing.** Each stage's PR sequence (M1.1/1.2/1.3, M2.1/2.2, M3.1/3.2/3.3) ships under one stage's gate, not three sub-gates.
- **Default-flip of `split_implementation_planning`.** That's M2's own internal gate per SIP §6.2.4 — separate from the M2 → M3 gate. Default-flip can happen any time after M2 ships, independent of whether M3 proceeds.

---

## Profile Config Examples

Mirrors SIP §6.4. The current rollout defaults keep M2 and M3 off (those stages are conditional on milestone gates). The post-gate target is shown separately so there's no contradiction between "M2/M3 are gated" and "profile examples enable them."

### Current rollout defaults (M1 on, M2 off, M3 off)

These ship with the M1 PRs. They activate typed acceptance and leave the M2/M3 surfaces dormant until their gates pass.

```yaml
# build profile — current rollout (M1 on, M2 off, M3 off)
defaults:
  build_plan: true
  output_validation: true
  max_self_eval_passes: 1
  typed_acceptance: true               # M1 default-on
  command_acceptance_checks: true
  split_implementation_planning: false      # M2 awaits gate
  plan_changes_enabled: false               # M3 loader awaits gate
  correction_plan_changes_enabled: false    # M3 producer awaits gate

# validation profile — gate-cycle target (long-cycle depth, M2/M3 still off)
# Used to gather evidence for the M1 → M2 milestone gate. Distinct from
# `build` (shallow self-eval) and `implementation` (post-gate target with
# M2/M3 on). Runs M1 at implementation-profile depth so typed-check
# signal and the structural_plan_change_candidate diagnostic field
# (added in M2.2) accumulate at the rate the gates require.
defaults:
  build_plan: true
  output_validation: true
  max_self_eval_passes: 2                   # implementation-profile depth
  max_correction_attempts: 3                # enough budget for correction to surface structural-change candidates (RC-9b / diagnostic field)
  typed_acceptance: true
  command_acceptance_checks: true
  split_implementation_planning: false      # M2 stays off until its gate
  plan_changes_enabled: false               # M3 loader stays off
  correction_plan_changes_enabled: false    # M3 producer stays off

# selftest profile — current rollout (smoke, minimal mechanical surface)
defaults:
  typed_acceptance: true
  command_acceptance_checks: false
  split_implementation_planning: false
  plan_changes_enabled: false
  correction_plan_changes_enabled: false
```

**Use the `validation` profile for cycles that feed the milestone gate evaluation docs.** The `build` profile is for default operator-driven cycles where `max_self_eval_passes: 1` is the right tradeoff for routine work; the `validation` profile is specifically tuned to give M1 enough depth that the gate criteria can be met or disconfirmed in a reasonable cycle-count window.

### Post-gate target profile (after M1 → M2 and M2 → M3 gates pass)

Do **not** enable these flags before the corresponding gate evaluation docs are committed. The implementation profile below is the long-cycle target once M2 and M3 ship.

```yaml
# implementation profile — post-gate target (long-cycle, all on, deeper)
defaults:
  build_plan: true
  output_validation: true
  max_self_eval_passes: 2
  typed_acceptance: true
  command_acceptance_checks: true
  split_implementation_planning: true       # post-M2 gate
  max_planning_revisions: 1
  plan_changes_enabled: true                # post-M3.2 ship
  correction_plan_changes_enabled: true     # post-M3.3 ship
  max_plan_changes: 8
  max_correction_attempts: 3
```

### Loader-only intermediate profile (between M3.2 and M3.3)

Useful for testing plan-change loading and applier behavior with synthesized changes (e.g., test fixtures) before authorizing the autonomous correction protocol to produce them.

```yaml
defaults:
  ...
  plan_changes_enabled: true                # loader on
  correction_plan_changes_enabled: false    # producer still off
  max_plan_changes: 5
```

---

## Out of Scope (Plan-Level)

These are explicitly NOT in this plan. Each is either named in SIP §5/§11 or a deliberate scope cut for review legibility.

- Sandbox app execution (smoke pack — separate SIP).
- UI/browser verification.
- Cross-handler "did the test exercise the code" checks (SIP-0086 §10 future work).
- Default flip of `split_implementation_planning` (separate small PR after SIP §6.2.4 criteria met).
- Operator-driven plan changes via API (SIP §11 future work).
- `governance.replan` task type (SIP §11 future work — would be the producer for `remove_task`/`replace_task`/`reorder`).
- Adaptive thresholds learned from prior cycles.
- Universal framework parsing in `endpoint_defined` etc. — Flask, JS/TS, etc. land in separate scoped PRs.
- Loosen-acceptance via gate (SIP §11 future work — distinct from in-cycle correction plan changes).

---

## Test Coverage Targets

Every test must catch a specific bug per `docs/TEST_QUALITY_STANDARD.md`. No tautological tests on dataclass fields.

| Layer | M1 | M2 | M3 |
|-------|----|----|----|
| Unit (parser / dataclasses) | ✅ | ✅ | ✅ |
| Unit (check eval / plan-change applier / plan-change validator) | ✅ | n/a | ✅ |
| Integration (handler) | ✅ | ✅ | ✅ |
| End-to-end cycle | ✅ | ✅ | ✅ |

**Self-check before committing tests:** re-read each test and delete any that only assert class attributes, only check `is not None`, or duplicate another test's coverage with different constants. Pair every mock-call-count assertion with an output/state assertion.

---

## Risks and Mitigations (Plan-Specific)

These are *plan-execution* risks — distinct from SIP §9 design risks.

| Risk | Mitigation |
|---|---|
| M1.2 evaluator framework grows to a universal AST library before any check ships | RC-12 stack-bounded `skipped` outcome ships in M1.2; new stacks land in scoped follow-up PRs only. |
| `command_exit_zero` slips its safelist by accepting "obvious" extensions in review | Safelist is operator-controlled config; extensions require an explicit PR touching `command_check_safelist` defaults, not a plan-author or handler-author edit. |
| M3.1 hashing over canonical form drifts from M1.1 round-trip helper | M1.1 round-trip test extended in M3.1 to cover full-plan hashing; same canonical helper used in both. |
| Producer emits unsupported op (M3.3) but execution-aware validator misses it | Defense in depth: producer-side restriction *and* validator rejection. M3.3 unit test seeds an unsupported-op LLM response and asserts both the producer-side drop and what would have been a validator reject. |
| Loader regression when `plan_changes_enabled: true` ships with zero plan changes in the wild | M3.2 integration test "0 plan changes → working == original" is a permanent regression guard. Run on every PR. |
| `split_implementation_planning` flag stays default-off forever | SIP §6.2.4 criteria + this plan's explicit "default-flip is a follow-up PR" — call it out in retro after each long cycle so it doesn't drift. |

---

## Terminology Lock (PR Checklist)

Per Rev 3 the artifact, dataclass, and module names were renamed. To prevent the rename from becoming half-applied during implementation, every PR landing under this plan must pass this checklist before merge:

**Banned terms in new code** (allowed only in historical comments, in references to SIP-0086 quotes, or when reading legacy on-disk artifacts during a migration):

- `BuildManifest`, `BuildTaskManifest`
- `ManifestTask`
- `ManifestDelta`, `manifest_delta`, `manifest_overlay`
- `ManifestReview`
- `WorkingManifest`
- `control_manifest`, `control_manifest_delta`
- `manifest_review.yaml`, `manifest_delta.yaml`
- `overlay` (as a noun for plan changes), `overlay_id`, `parent_overlay_id`, `apply_overlays`, `validate_overlay_for_run`
- `delta` (as a noun for plan changes)
- `decision: overlay`

**Canonical terms** that must be used instead:

| Concept | Canonical term |
|---|---|
| Plan dataclass | `ImplementationPlan` |
| Plan task element | `PlanTask` |
| Plan-change dataclass | `PlanChange` |
| Plan-change file | `plan_change.yaml`, `src/squadops/cycles/plan_change.py` |
| Plan review dataclass | `PlanReview` |
| Plan review file | `plan_review.yaml`, `src/squadops/cycles/plan_review.py` |
| Working plan dataclass | `WorkingPlan` |
| Plan artifact type | `control_implementation_plan` |
| Plan-change artifact type | `control_implementation_plan_change` |
| Correction decision value | `decision: plan_change` |
| Plan loader | `_load_plan_for_run`, `apply_plan_changes`, `validate_plan_change_for_run`, `load_plan_changes_for_run`, `load_original_plan` |
| Author handler | `DevelopmentPlanImplementationHandler` (`development.plan_implementation`) |
| Reviewer handler | `GovernanceReviewPlanHandler` (`governance.review_plan`) |

**Implementation:** the simplest landing is a tiny `tests/unit/cycles/test_terminology_lock.py` that greps the SIP-0092 source files for banned terms and asserts none appear (allowing exceptions in `tests/unit/cycles/legacy_*.py` for migration tests). Run as part of the regression test suite; failure indicates a half-applied rename. Lower-cost alternative: a PR-template checkbox referencing this section. Either is fine; the goal is to catch drift before it ships.

This check applies to **new code introduced under this plan's PRs**. The shipped SIP-0086 code on main still uses `control_manifest` / `BuildTaskManifest` until M1.1 (which migrates `cycles/build_manifest.py` → `cycles/implementation_plan.py`); the migration itself is allowed to read legacy names as it converts them.

---

## References

- `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` — design (this plan implements §6 and §8)
- `sips/implemented/SIP-0086-Build-Convergence-Loop-Dynamic.md` — parent SIP and its `RC-1..RC-8`
- `docs/plans/SIP-0086-build-convergence-loop-plan.md` — implementation plan style template
- `docs/plans/1-0-x-build-reliability-hardening-plan.md` — track-level plan that orders this SIP as #1
- `src/squadops/cycles/implementation_plan.py` — extended by M1.1
- `src/squadops/cycles/task_plan.py:341` — extended by M3.2
- `src/squadops/capabilities/handlers/cycle_tasks.py:965` — replaced by M1.3 (FC3 → typed-check evaluation)
- `src/squadops/capabilities/handlers/planning_tasks.py:432` — `_produce_plan`, source for the `PlanAuthoringService` extraction in M2.1
- `src/squadops/api/routes/cycles/runs.py` — plan-change forwarding extension in M3.2
- `adapters/capabilities/aci_executor.py` — sandbox executor used by `command_exit_zero`
- `docs/TEST_QUALITY_STANDARD.md` — bar every test in this plan must clear

---

## Plan Revision History

- **Plan Rev 5 (2026-04-30):** "Mechanical Acceptance" → "Typed Acceptance" rename throughout.
  - Config flag `mechanical_acceptance` → `typed_acceptance`; status reason `mechanical_acceptance_disabled` → `typed_acceptance_disabled`.
  - Stage M1 heading "Mechanical Acceptance Criteria" → "Typed Acceptance Criteria." Context-section bullet, validator integration text, and Profile Config Examples updated to match.
  - Pairs with SIP Rev 4 (same change in the SIP). Pre-implementation; zero blast radius. Rationale: "Typed" matches `TypedCheck` and the plan's "typed checks" usage; "Mechanical" reads opaque outside the SIP body's "informational vs mechanical" pairing.
- **Plan Rev 4 (2026-04-30):** Targeted tightening pre-implementation. Major changes:
  - **Resolved `decision: overlay` → `decision: plan_change`** everywhere (item 1). The previously-flagged open decision is closed; `overlay` is no longer a supported value anywhere in this plan, the SIP, prompts, handler branches, tests, logs, event names, artifacts, or examples. The SIP §6.1.6 quote was paraphrased to use post-rename terminology.
  - **Narrowed M3 Rev 1 operation set to `add_task` + `tighten_acceptance` only** (item 9). `remove_task`, `replace_task`, and `reorder` are deferred from code entirely (no dataclass, no applier branch, no validator branch, no tests). They remain in the SIP as future-work design for operator plan changes and `governance.replan`. The YAML parser rejects deferred operations at parse time with `unsupported_operation_in_rev_1`. This is a deliberate scope cut, not a fallback.
  - **Split plan-change loader from autonomous producer** via two flags (item 8): `plan_changes_enabled` (M3.2 — loader/applier) and `correction_plan_changes_enabled` (M3.3 — autonomous producer). Lets us test loader behavior with synthesized plan changes before authorizing the correction protocol to produce them. Misconfiguration (producer on, loader off) is rejected at startup.
  - **Profile examples separated** into current rollout defaults (M2/M3 off, gated) and post-gate target (item 2). Removes the contradiction between "M2/M3 are gated" and "profile examples enable them." Added a loader-only intermediate profile for M3.2 ↔ M3.3 testing.
  - **Added `validation` profile** to current rollout defaults (§6.4.1 / Profile Config Examples). Distinct from `build` (which has shallow self-eval) and `implementation` (the post-gate target with M2/M3 on). Runs M1 at implementation-profile depth with M2/M3 still off. This is the profile that feeds milestone gate evaluation cycles — the long-cycle group_run definition in the Milestone Gates section now points at it explicitly. Same profile shape with M2/M3 flags flipped on becomes the M2 → M3 gate's measurement profile after those stages ship.
  - **Defined "long-cycle group_run" for gate measurement** (item 3): profile, duration, what counts as reaching plan-relevant execution, and the infrastructure-failure exclusion rule. Each gate evaluation doc must cite cycle IDs and excluded runs.
  - **Tightened M1 → M2 gate criterion wording** (item 4): replaced "would plausibly have caught" with a concrete map-to-categories test — defects must be visible from plan + PRD + test strategy alone and map to one of M2's `plan_review.yaml` concern categories (coverage / dependency / role / acceptance). Proves the defect lives in M2's detection surface without speculating about reviewer behavior.
  - **Added `structural_plan_change_candidate` diagnostic field** (item 5) to the correction-decision log artifact. Non-operative; allowed values `none | add_task | tighten_acceptance | other`. Captured during M2 tracking so the M2 → M3 gate has a measurable signal without speculation. Added to M2.2 implementation scope so it's available throughout the M2 → M3 tracking window.
  - **Sharpened RC-9b** (item 6): persistent evaluator errors emit a structured `evaluator_error_persisted` escalation event, are removed from the self-eval feedback list for that criterion, and **the correction protocol must not treat the error as missing application behavior** (no `acceptance:<description>` wording in correction prompts for evaluator errors). Prevents bad checks / unsafe paths / regex timeouts from driving development repair loops.
  - **Tightened RC-20** (item 7): when `plan_changes_enabled=true`, task envelopes are identity carriers only. Acceptance criteria used for validation MUST be loaded from the current `WorkingPlan` by `task_index` at handler entry. Stale envelope criteria (if present) are non-authoritative. Handler-side test verifies `tighten_acceptance` actually takes effect on already-materialized but not-yet-started tasks.
  - **Added Terminology Lock (PR Checklist) section** (item 10) listing banned terms (`BuildManifest`, `manifest_delta`, `overlay`, `delta`, etc.) and canonical replacements. Implementation suggestion: a tiny terminology-lock test that greps SIP-0092 sources, or a PR-template checkbox. Catches half-applied renames before they ship.
- **Plan Rev 3 (2026-04-30):** Terminology rename pass + milestone gates. Major changes:
  - **Renamed throughout** to align with the SIP-0092 title rename (Maturation → Improvement, manifest → implementation plan, overlay/delta → plan change, control_manifest → control_implementation_plan, governance.assess_readiness → governance.review_plan, governance.plan_build → development.plan_implementation, etc.). No semantic changes; vocabulary now matches the accepted SIP and the post-rename module/class names. The `decision: plan_change` correction-protocol enum value was preserved as a flagged open decision pending broader naming alignment.
  - **Added Milestone Gates section** with concrete proceed-if criteria for M1 → M2 and M2 → M3, recorded in evaluation docs (`SIP-0092-gate-M1-evaluation.md`, `SIP-0092-gate-M2-evaluation.md`). M2 and M3 stage headings tagged as conditional on their respective gates. Default behavior is stop-and-re-evaluate; failed gate criteria spin the next stage out as a separate proposed SIP. Converts the linear plan into an evidence-driven one so we don't pay the cost of M2 and M3 on hypothetical failure modes.
- **Plan Rev 2 (2026-04-29):** Incorporated reviewer feedback. Major changes:
  - **RC-9 rewritten to separate severity from outcome status.** Only `severity=error` AND `status ∈ {failed, error}` blocks. Added `RC-9a` distinguishing evaluator error (`status=error`) from app incompleteness (`status=failed`) — evaluator errors surface with `evaluator-error:<check>` wording, not as missing app behavior. Added `RC-9b` bounding evaluator-error retry to two consecutive failures before escalating, preventing pathological criteria from driving endless self-eval loops.
  - **RC-10a added — pattern-based command safelist.** `command_check_safelist` now matches full argv shapes (e.g., `python -m py_compile <file>`), not just `argv[0]`. `python -c`, `python -m pip`, `python -m <unlisted>` are explicitly rejected. Out-of-pattern argv produces `status=error` reason `command_not_in_safelist` (treated as evaluator error per RC-9a, not silently skipped). Added `_CHECK_IMPLS` startup assertion.
  - **RC-12a added — stack context is authoritative, not guessed.** Framework-level checks read stack from resolved profile/plan metadata via `HandlerContext`, not by sniffing file content. File extension is fine for language-level decisions; framework decisions consult declared context. Stack-context-unset → `skipped` (authoring gap), not `error` (evaluator failure).
  - **RC-20 added — plan-change application timing.** Plan changes land at executor build-plan re-expansion boundaries, never mid-task. Already-materialized but not-yet-started tasks pick up `tighten_acceptance` updates by re-reading the working plan at handler entry.
  - **RC-21 added — loader hard-fails on inconsistent plan-change state.** Replaces silent fallback. Hash/chain/runtime rejection emits structured event, sets `plan_changes_inconsistent: true`, blocks further plan-change production, and (when no valid predecessor exists for a needed plan change) pauses the run pending operator action.
  - **Single source of truth for check metadata.** New `acceptance_check_spec.py` with `CheckSpec` registry consumed by *both* the parser (for `from_yaml()` validation) and the evaluator framework. No separate `_KNOWN_CHECKS` table that could drift.
  - **`_produce_plan` extracted into shared `PlanAuthoringService`** instead of moved verbatim. Both legacy `review_plan` and new `development.plan_implementation` paths call the service. M2.2's revision loop is a third caller. Eliminates the verbatim-duplicate drift risk.
  - **M3.1 Rev 1 disallows tombstoned-task dependencies.** Was: "dependency on tombstoned-but-artifacts-still-present allowed." Now: dependencies must reference active tasks. Avoids modeling runtime artifact persistence in the structural applier; future-work hook for an `artifact_dependency` concept if needed.
  - **M3 schedule-pressure fallback.** If implementation drags, ship `add_task` + `tighten_acceptance` end-to-end first; defer `remove_task` / `replace_task` / `reorder` from the schema and applier (they stay in the SIP for future operator plan changes / `governance.replan`).
- **Plan Rev 1 (2026-04-29):** Initial plan. Three stages M1/M2/M3 mapping to SIP §8. RC-9..RC-19 runtime contracts.
