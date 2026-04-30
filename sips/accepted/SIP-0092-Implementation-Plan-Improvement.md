---
title: Implementation Plan Improvement — Mechanical Acceptance, Separated Authoring, and
  Plan Changes
status: accepted
author: SquadOps Architecture
created_at: '2026-04-27T00:00:00Z'
sip_number: 92
updated_at: '2026-04-29T23:39:19.875323Z'
---
# SIP-0092: Implementation Plan Improvement — Mechanical Acceptance, Separated Authoring, and Plan Changes

**Status:** Accepted
**Authors:** SquadOps Architecture
**Created:** 2026-04-27
**Revision:** 2
**Updated:** 2026-04-27 (rev 2 — incorporated external review)

---

## 1. Abstract

SIP-0086 introduced the implementation plan — a control-plane artifact produced during planning that decomposes a build into focused, role-typed subtasks. Capability A (plan production, materialization, focused prompts, deterministic task IDs) shipped on main: `src/squadops/cycles/implementation_plan.py`, `_produce_plan` in `planning_tasks.py:432`, plan expansion in `task_plan.py:341`. The first reliable group_run cycles to fill a build timebox came from this work.

Three follow-up gaps now bound how reliably a squad can build a non-trivial app over a long cycle. Each is named in SIP-0086 §10 (Future Work) but deferred at the time:

1. **Acceptance criteria are informational only** — they appear in the plan, in the focused prompt, and in the self-evaluation prompt, but the validator does not evaluate them. Validation reduces to `expected_artifacts` filename matching plus stub detection (`cycle_tasks.py` FC1/FC2). A subtask whose generated code imports the wrong module, exposes the wrong endpoints, or omits required fields passes validation as long as the file names are right.
2. **Plan authoring is colocated with planning approval** — `governance.review_plan` (Max) authors the plan *and* signs off on planning readiness in the same handler call (`planning_tasks.py:420–428`). The proposer-judge collapse is acknowledged in SIP-0086 §6.1.3 as a known tradeoff; the operator gate is the only external check.
3. **The plan is one-shot and immutable** — SIP-0086 §6.1.6 specifies that correction-driven changes are "represented as plan-change artifacts applied as changes," but no change format, no change producer, and no change applier exist. In practice, a plan that turns out wrong at hour 2 of a 6-hour cycle has no machine-readable revision path; the cycle either limps along with a bad plan or terminates at gate.

This SIP introduces three independently shippable capabilities that close those gaps:

- **Capability M1 — Mechanical Acceptance Criteria.** Add a typed acceptance check schema embedded in plan tasks; evaluate them at handler validation time; surface results as first-class check entries in `ValidationResult.checks` alongside the existing FC1/FC2 checks. Checks carry severity (`error` / `warning` / `info`) and produce a typed `CheckOutcome` (`passed` / `failed` / `skipped` / `error`).
- **Capability M2 — Separated Plan Authoring.** Introduce a dedicated `development.plan_implementation` planning task that authors the plan. `governance.review_plan` reviews and signs off, restoring the proposer/reviewer separation. Reviewer concerns are produced as a typed `plan_review.yaml` artifact that can be fed mechanically into a bounded revision loop.
- **Capability M3 — Plan Changes.** Define a `plan_change.yaml` change schema and a *pure structural applier* paired with an *execution-aware validator*. Wire the correction protocol to emit plan changes restricted to `add_task` and `tighten_acceptance` operations only — the broader operation set (`remove_task` / `replace_task` / `reorder`) is supported in the schema and applier but reserved for operator action or a future `governance.replan` task, not autonomous correction.

Each capability is independently valuable. M1 alone makes today's plans far more discriminating. M2 alone improves planning-phase quality. M3 alone unlocks long-cycle adaptability. Together they turn the plan from "produced once, consumed once" into a living plan the squad can iterate against — without giving autonomous correction the keys to rewrite history.

---

## 2. Problem Statement

### 2.1 What SIP-0086 Shipped

Code grounded as of 2026-04-27 on main:

| Component | Location | Status |
|---|---|---|
| Plan dataclasses + YAML parser + DAG validator | `src/squadops/cycles/implementation_plan.py` | ✅ Shipped |
| Plan production handler | `_produce_plan` in `src/squadops/capabilities/handlers/planning_tasks.py:432` | ✅ Shipped (with retry loop and corrective feedback per `fbea2d7`) |
| Role + task_type constraints (squad-aware) | `planning_tasks.py:450–470` | ✅ Shipped (`c38a523`, `dc8e7c0`) |
| Builder routing in plan prompt | `planning_tasks.py:475–504` | ✅ Shipped (`ec4db16`) |
| Plan expansion to envelopes | `_replace_build_steps_with_plan` in `task_plan.py:341` | ✅ Shipped |
| Deterministic task IDs (`task-{run}-m{idx}-{type}`) | `task_plan.py:281` | ✅ Shipped |
| Focused-task prompt adaptation | `cycle_tasks.py` (`subtask_focus` branch) | ✅ Shipped |
| Validation FC1 (expected_artifacts) + FC2 (non-stub) | `cycle_tasks.py` | ✅ Shipped |
| `outcome_class: SEMANTIC_FAILURE` emission | `cycle_tasks.py` | ✅ Shipped |
| Self-evaluation pass | `cycle_tasks.py` | ✅ Shipped |
| Gate promotion + control_implementation_plan forwarding | `api/routes/cycles/runs.py` (`af306d3`, `075fd9e`) | ✅ Shipped |

The framework can decompose, materialize, prompt, validate, self-correct, and forward. What it cannot yet do is **judge whether the produced code does what the plan said it should do**, and it cannot **revise the plan mid-cycle**.

### 2.2 Gap M1: Acceptance Criteria Are Informational

`ImplementationPlan` already carries `acceptance_criteria: list[str]` per task (`implementation_plan.py:38`). The criteria are passed into the focused prompt (`cycle_tasks.py` `subtask_focus` branch) and the self-evaluation follow-up. They are *never* evaluated.

Consequence: a plan entry like

```yaml
- task_index: 1
  task_type: development.develop
  focus: "Backend API endpoints"
  expected_artifacts:
    - "backend/main.py"
    - "backend/routes.py"
  acceptance_criteria:
    - "All 5 required endpoints (GET /runs, POST /runs, GET /runs/{id}, POST /runs/{id}/join, POST /runs/{id}/leave) are defined"
    - "Endpoints import and use the repository from task 0"
    - "Duplicate participant join returns 409"
```

passes validation if the LLM produces files at `backend/main.py` and `backend/routes.py` containing more than 100 bytes and no obvious stub patterns — even if the actual content defines two endpoints and never imports the repository. The downstream `qa.test` task and any pulse check then operate against incomplete code.

This is not a hypothetical. SIP-0086 §6.3.1 marks FC3 as `"evaluation": "included_in_evidence"` and `"passed": True` (informational). On 2026-04-18 group_run cycles (memory `project_sip0086_manifest_handoff_bug.md`), correction never fired even on visibly partial implementations because the validators couldn't see the gap.

### 2.3 Gap M2: Plan Authoring Is Colocated With Planning Sign-Off

`governance.review_plan` (Max) currently:

1. Reads the planning artifact draft.
2. Validates frontmatter (`readiness`, `sufficiency_score`).
3. Decides whether planning is ready for the gate.
4. **Authors the implementation plan in the same handler call** (`planning_tasks.py:420–428`).

The same agent invocation that judges planning sufficiency also produces the build decomposition that planning sufficiency is supposed to gate. SIP-0086 §6.1.3 explicitly named this:

> *"This introduces proposal-review colocation: the same component that proposes the build plan is judging its adequacy. The gate remains the human/operator checkpoint that mitigates this — the operator reviews the plan before approving, providing an external check on decomposition quality. Long-term, a dedicated plan producer (e.g., `development.plan_implementation`) before `governance.review` may provide cleaner separation."*

Two operational consequences:

- **Single-call concentration.** A 32B model is asked to do governance review *and* plan authoring in one call. Empirically (memory `project_spark_cycle_status.md`), Max occasionally emits invalid YAML in `implementation_plan.yaml` even at 32B; concentration of both responsibilities is a contributing factor.
- **No reviewer for the proposer.** The operator gate is the only check; the squad itself never checks Max's decomposition before it reaches the gate. For a long cycle with a less-attentive operator, this is the weakest link in planning quality.

### 2.4 Gap M3: The Plan Cannot Evolve

SIP-0086 §6.1.6 ("Plan identity"):

> *"The plan becomes immutable after gate approval. The executor does not modify, reorder, or add to the plan's task list. Correction-driven additions or substitutions are represented as plan-change artifacts applied as changes; they do not mutate the original approved plan."* (Quoted from SIP-0086 §6.1.6, paraphrased to use SIP-0092's renamed terminology.)

That's the design intent. The implementation has only the immutability half. There is no `plan_change.yaml` schema, no change producer, and no change applier. Today, when correction fires:

- The repair handler (`development.repair`) operates against the failed subtask with prior-artifact context.
- The original subtask checkpoint is preserved.
- No new subtasks can be added; no existing subtasks can be removed or reordered; no acceptance criteria can be tightened.

For a one-hour cycle this is acceptable — the repair handler converges or the cycle terminates. For a multi-hour cycle, the failure modes that warrant plan evolution show up routinely:

- **Discovered missing layer** (e.g., plan has no `auth` task because Max underweighted the PRD's auth requirement; correction needs to add a subtask, not just patch).
- **Stricter acceptance** (e.g., Eve discovers the original criteria were too loose; needs to ratchet them on a re-run).

Without changes, the cycle either limps along on a stale plan or terminates at the gate.

---

## 3. Design Principles

### 3.1 Acceptance criteria must be machine-readable to be enforceable

Free-text criteria are operator-readable, model-readable, and validator-illegible. The minimum useful unit is a typed check the validator can run. Criteria authoring should be guided into typed shapes rather than left as prose.

### 3.2 Treat the plan as untrusted input

The plan is LLM-authored. Typed checks reference file paths, glob patterns, regexes, and command specs. Every one of those is a foot-gun if treated as trusted. The evaluator chroots paths to the workspace root, rejects shell strings, runs commands as argv arrays, and enforces a safelist.

### 3.3 Separate the proposer from the reviewer

Authoring the build plan and signing off on planning readiness are different cognitive tasks. They should be different handler calls — even if the same agent role (Max) performs both — so the second call has a chance to catch the first call's mistakes.

### 3.4 Original plan is the source of truth; plan changes accumulate

The approved plan stays immutable. Plan changes are append-only audit trail. The "current working plan" is always derived: `apply(original, changes)`. This preserves the gate's contract (what the operator approved) while admitting evolution.

### 3.5 Pure structural applier; execution-aware validator

The applier is pure: same `(original, changes)` always yields the same working plan. Runtime constraints — "this plan change would invalidate already-completed work" — live in a separate execution-aware validator that consults run state. Keeping these layers apart preserves test tractability without weakening runtime safety.

### 3.6 Autonomous correction is conservative

The schema supports five operations (`add_task`, `remove_task`, `replace_task`, `tighten_acceptance`, `reorder`). The autonomous correction producer in Revision 1 emits only the two safe ones (`add_task`, `tighten_acceptance`). Everything else requires operator action or a future `governance.replan` task. Correction can grow the plan and tighten the contract; it cannot rewrite history.

### 3.7 Plan changes affect only the remaining execution plan

Plan changes do not replace, remove, reorder, or otherwise rewrite the semantic meaning of already-completed task checkpoints. Corrections to completed work are represented as new tasks, not mutations of prior ones. This protects artifact lineage so the working plan never makes history look different from what actually happened.

### 3.8 Backward-compatible at every layer

Plans without typed acceptance still work (criteria continue to be informational for those tasks). Cycles without `development.plan_implementation` still work (plan production stays in `review_plan` as today). Cycles with no plan changes produced still work (the working plan equals the original).

### 3.9 Build on what shipped, don't re-spec it

This SIP does not redefine SIP-0086's plan schema, executor materialization, deterministic task IDs, or correction routing. All of that is reused. Only acceptance evaluation, the authoring split, and the change format are new.

---

## 4. Goals

1. **Acceptance criteria with teeth.** A plan task can carry typed acceptance checks with explicit severity that the build validator evaluates and reports as pass/fail/skipped/error in `ValidationResult.checks`.
2. **Untrusted-input safety.** All paths chrooted to workspace root, no shell execution, command invocations are argv-only and safelisted.
3. **Authoring-time validation.** Unknown check names or malformed params fail plan validation (at planning/gate), not at hour 2 of build.
4. **Bounded stack support.** Stack-specific check evaluators target the actual reference-app stacks (FastAPI, React+Vite); other stacks produce `skipped` outcomes rather than guessing.
5. **Separated authoring.** A new `development.plan_implementation` planning task authors the plan. `governance.review_plan` becomes a true reviewer/sign-off step that may reject or request structured revisions to the plan.
6. **Plan changes — schema and pure applier.** Five operation types in the schema; pure structural applier producing a deterministic working plan from `(original, [change_1, ..., change_N])`.
7. **Execution-aware change validation.** Before any plan change is accepted for an active run, an execution-aware validator rejects plan changes that would invalidate already-started or completed work.
8. **Conservative autonomous correction.** The correction protocol can produce plan changes — but only `add_task` and `tighten_acceptance` operations. Removal/replacement/reordering require operator action or future `governance.replan`.
9. **Observability.** Every plan change is stored as `artifact_type: "control_implementation_plan_change"`. Every change-created task carries provenance metadata (`change_id`, `operation_index`, `reason`, `correction_decision_id`). Every typed acceptance check result is in `ValidationResult.checks`.
10. **No regression.** Existing build profiles and existing plans (with informational criteria, no changes, monolithic authoring) continue to work without change.

---

## 5. Non-Goals

- Replacing the SIP-0086 plan schema or task materialization mechanism.
- Defining a general-purpose constraint language. Typed acceptance checks are a small, fixed vocabulary chosen for build verification, not a Turing-complete DSL.
- Sandbox execution of generated code. Acceptance checks are static analysis (AST, regex, file content) plus targeted shell invocations against a safelist (lint exit code, type-check exit code) — not running the app. Running the app is the smoke pack's job (separate SIP).
- Browser/UI verification.
- Cross-handler "did the test exercise the code" checks. Listed in SIP-0086 §10 future work; remains out of scope here.
- Autonomous plan change operations beyond `add_task` and `tighten_acceptance` in Revision 1. The applier supports more; the autonomous producer does not.
- Adaptive thresholds learned from prior cycles. Out of scope; criteria are author-specified per cycle.
- Replacing the operator gate. The gate still exists; M2 adds an *internal* reviewer step on top of it, not instead of it.
- Universal framework parsing. `endpoint_defined` and similar checks target the reference-app stacks only; other stacks return `skipped` rather than risk false negatives.

---

## 6. Design

### 6.1 Capability M1 — Mechanical Acceptance Criteria

#### 6.1.1 Schema: flat YAML, normalized internal form

`PlanTask.acceptance_criteria` today is `list[str]`. Extend it to accept either strings (informational, backward-compatible) or **flat-YAML typed entries**. The parser normalizes every typed entry into a `TypedCheck` object before evaluators see it.

**Authoring-friendly YAML (flat keys):**

```yaml
acceptance_criteria:
  # Existing free-text form (informational, kept for back-compat)
  - "All 5 required endpoints are defined"

  # Typed forms — flat keys at top level, plus optional severity/description:
  - check: endpoint_defined
    file: backend/routes.py
    methods_paths:
      - [GET, /runs]
      - [POST, /runs]
      - [GET, /runs/{id}]
      - [POST, /runs/{id}/join]
      - [POST, /runs/{id}/leave]
    severity: error
    description: "Backend exposes the 5 PRD endpoints"

  - check: import_present
    file: backend/routes.py
    module: backend.repository
    symbols: [Repository]
    severity: error

  - check: regex_match
    file: backend/routes.py
    pattern: "status_code\\s*=\\s*409"
    count_min: 1
    severity: warning              # rolling out; not yet a hard fail
    description: "Duplicate join returns 409"

  - check: command_exit_zero
    command: ["python", "-m", "py_compile", "backend/routes.py"]
    cwd: "."
    timeout_seconds: 10
    severity: error
```

**Normalized internal form** (what evaluators see):

```python
@dataclass(frozen=True)
class TypedCheck:
    check: str                 # vocabulary name, e.g., "endpoint_defined"
    params: dict               # all check-specific fields except check/severity/description
    severity: str = "error"    # error | warning | info
    description: str = ""

@dataclass(frozen=True)
class PlanTask:
    task_index: int
    task_type: str
    role: str
    focus: str
    description: str
    expected_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: list[str | TypedCheck] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
```

**Normalization rule (canonical):**

> Typed-check YAML uses flat keys for authoring convenience. The parser normalizes every typed criterion into a `TypedCheck` where `params` contains all fields *except* `check`, `severity`, and `description`. Only the normalized form is passed to evaluators or surfaced in `ValidationResult`. Mixed lists (some typed, some prose) are valid; prose strings remain informational.

This eliminates the implementation hazard where authors and evaluators see different shapes.

#### 6.1.2 Severity

Each typed check carries a `severity` field with values `error` (default), `warning`, or `info`.

| Severity | Behavior |
|---|---|
| `error` | Failed check contributes to `missing_components` and triggers self-eval/correction. |
| `warning` | Failed check is reported in evidence but does not fail the task or block progress. |
| `info` | Informational; result captured in evidence for tuning, never fails or warns. |

This gives a safe rollout path for new checks without globally disabling `mechanical_acceptance`.

#### 6.1.3 Check vocabulary (Revision 1)

| Check | Params | What it validates |
|---|---|---|
| `endpoint_defined` | `file`, `methods_paths` | Route decorator with method + path is present. AST-based for FastAPI; regex fallback. Targets observed "wrote 2 of 5 endpoints" failures. |
| `import_present` | `file`, `module`, `symbols` | `from <module> import <symbols>` (or equivalent JS `import`) is present. Targets "wrote endpoints but never wired the repository." |
| `field_present` | `file`, `target` (class/dataclass/Pydantic model), `fields` | Named fields are declared on the named target. AST-based. Targets "model missing required attributes per PRD." |
| `regex_match` | `file`, `pattern`, optional `count_min` (default 1) | Regex matches at least N times. Escape hatch for things AST checks don't cover (specific status codes, error messages, mention counts). |
| `command_exit_zero` | `command` (argv list), `cwd`, `timeout_seconds` | Subprocess from safelist exits 0. Used for `py_compile`, `tsc --noEmit`, `eslint`, `ruff check`. Bounded by timeout; sandboxed via existing ACI executor. |
| `count_at_least` | `glob`, `min` | At least N files match the glob. Targets "wrote one component but PRD said three." |

Each check is implemented as a class with `evaluate(workspace_root, artifacts) -> CheckOutcome`. New checks are added by registering a class in a small registry — no dispatch logic in the validator.

#### 6.1.4 CheckOutcome status enum

```python
@dataclass(frozen=True)
class CheckOutcome:
    status: str          # "passed" | "failed" | "skipped" | "error"
    actual: dict         # check-specific evidence (e.g., found endpoints, file size)
    reason: str          # human-readable summary
```

Status values:

| Status | When |
|---|---|
| `passed` | Check evaluated and the assertion held. |
| `failed` | Check evaluated and the assertion did not hold. |
| `skipped` | Check is well-formed but not evaluable in this context — e.g., target file missing, unsupported stack/syntax (`unsupported_stack_or_syntax` reason), command type disabled by config (`command_acceptance_checks: false`), or `mechanical_acceptance: false`. Reported as evidence; not a failure. |
| `error` | Evaluator itself raised an unexpected exception. Treated as a failure for `error`-severity checks; logged with stack trace. |

`ValidationResult` consumers that expect a legacy `passed: bool` derive it from `status == "passed"` (with severity weighting — `warning`/`info` failures are not `passed=False`).

This separation is what lets a "no FastAPI in this stack" outcome (skipped) be distinguished from "the endpoints aren't there" (failed) — the same evidence shape that makes triage tractable.

#### 6.1.5 Path and command safety

All typed checks are evaluated against LLM-authored input. The evaluator treats every value as untrusted:

- **Paths** (`file`, `cwd`, `glob`): resolved relative to the workspace root; absolute paths rejected; `..` traversal rejected; symlinks pointing outside the workspace rejected when feasible. A path that resolves outside the workspace produces `status: error` with reason `path_escapes_workspace`.
- **Globs**: bounded by max-match count (default 10,000) to prevent denial of service via pathological globs.
- **Regex patterns**: compiled with a timeout (where the regex engine supports it) or with input-size bound; pathological regexes produce `status: error` with reason `regex_timeout`.
- **Commands**: only argv lists accepted; shell strings rejected outright. Argv[0] must be in the safelist (`python -m py_compile`, `python -m mypy`, `ruff check`, `tsc --noEmit`, `eslint`, `pyflakes`, `node --check`, `npm run lint`). Out-of-safelist commands produce `status: skipped` with reason `command_not_in_safelist`. Execution runs in the existing ACI executor (`adapters/capabilities/aci_executor.py`) with the workspace as cwd and a clean restricted environment (no `LD_PRELOAD`, no `PYTHONPATH` injection, etc.).
- **Timeouts**: every command-bearing check has a hard timeout (default 10s, max 60s).

The safelist is configurable via `command_check_safelist`; entries can only be added by operator-controlled config, not by plan authors.

#### 6.1.6 Stack-aware bounded evaluators

Several checks are stack-specific (`endpoint_defined` understands FastAPI/Flask decorators; `import_present` understands Python `from X import Y` and ES module imports). Rather than letting any one check become a universal framework parser, each evaluator declares its supported stacks and returns `status: skipped` with reason `unsupported_stack_or_syntax` for anything outside that set.

Revision 1 stack support:

| Check | Supports |
|---|---|
| `endpoint_defined` | FastAPI (AST). Flask added on demand. |
| `import_present` | Python (AST). JS/TS (regex fallback) added when reference-app frontend stack lands. |
| `field_present` | Python dataclasses, Pydantic v2 models (AST). |
| `regex_match`, `count_at_least`, `command_exit_zero` | Stack-agnostic. |

Adding a new stack is a separate, scoped PR — not a heuristic expansion inside an existing check.

#### 6.1.7 Authoring-time validation

Bad typed checks should be caught at planning/gate time, not at hour 2 of build:

| Condition | Outcome |
|---|---|
| Unknown `check` name | Plan invalid; `ImplementationPlan.from_yaml()` raises `ValueError`. Plan production retry loop sees the error and re-prompts. |
| Malformed `params` for a known check (missing required field, wrong type) | Plan invalid; same handling. |
| Well-formed check for unsupported stack | Plan valid; check evaluates with `status: skipped`, reason `unsupported_stack_or_syntax`. |
| Free-text string criterion | Valid; informational. |
| Unknown `severity` value | Plan invalid. |

The retry loop in `_produce_plan` (`planning_tasks.py:572`) already re-prompts on `ValueError`; this rule extends what counts as invalid.

#### 6.1.8 Validator integration

`_validate_output_focused` in `cycle_tasks.py` already returns a `ValidationResult` with `checks: list[dict]`. Add a third check class alongside FC1 (expected_artifacts) and FC2 (non-stub):

```python
typed_checks = [c for c in inputs.get("acceptance_criteria", []) if isinstance(c, TypedCheck)]
for criterion in typed_checks:
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
    if outcome.status == "failed" and criterion.severity == "error":
        missing.append(f"acceptance:{criterion.description or criterion.check}")
```

Only `error`-severity failed checks contribute to `missing_components`. The self-eval LLM call sees these specific named gaps in its follow-up prompt instead of generic "your output is incomplete." `warning`/`info` failures and `skipped` outcomes appear in evidence for operator triage.

#### 6.1.9 Authoring guidance

The plan authoring prompt is extended to document the typed-check vocabulary, severity defaults, the stack-bounded check semantics, and the path/command safety rules:

> *Where possible, express acceptance criteria as typed checks rather than prose. Available checks: `endpoint_defined`, `import_present`, `field_present`, `regex_match`, `count_at_least`, `command_exit_zero`. Use flat YAML keys for the check-specific fields. Severity defaults to `error`; use `warning` for new or experimental checks. All paths must be inside the workspace root. Commands must be argv lists drawn from the safelist. Mixed prose+typed lists are fine; prose criteria are surfaced to the implementer but not auto-evaluated.*

### 6.2 Capability M2 — Separated Plan Authoring

#### 6.2.1 New planning task: `development.plan_implementation`

Add a planning task that runs *before* `governance.review_plan`:

```
CURRENT (post-SIP-0086):
  Planning: data.research → strategy.frame → development.design_plan
            → qa.define_test_strategy → governance.review_plan (sign-off + plan authoring)
            → [GATE]

PROPOSED:
  Planning: data.research → strategy.frame → development.design_plan
            → qa.define_test_strategy → development.plan_implementation (plan authoring)
            → governance.review_plan (sign-off + plan review)
            → [optional development.plan_implementation_revise loop, bounded by max_planning_revisions]
            → [GATE]
```

Implementation: a new handler `DevelopmentPlanImplementationHandler` in `planning_tasks.py` that takes the existing `_produce_plan` logic (and its retry loop) verbatim, returns the plan as its primary output rather than a side-effect on the planning artifact.

`governance.review_plan` loses its plan-production responsibility and gains a plan-review responsibility.

#### 6.2.2 `plan_review.yaml` schema

The reviewer step produces a structured artifact. Prose-only review concerns are explicitly disallowed.

```yaml
# plan_review.yaml
version: 1
review_status: approved | revision_requested | approved_with_concerns
reviewer_confidence: low | medium | high
target_plan_id: <plan artifact id>

coverage_concerns:
  - prd_requirement: "duplicate-join 409 handling"
    target_task_index: null            # null = missing entirely from plan
    note: "PRD requires 409 on duplicate join; no plan task references it."

dependency_concerns:
  - target_task_index: 4
    note: "Frontend detail view depends on task 1 (API) but does not list it in depends_on."

role_concerns:
  - target_task_index: 6
    note: "Test task assigned to dev role; should be qa."

acceptance_concerns:
  - target_task_index: 1
    missing_check: "endpoint_defined for POST /runs/{id}/join"
    suggested_check:
      check: endpoint_defined
      file: backend/routes.py
      methods_paths: [[POST, /runs/{id}/join]]

revision_instructions: |
  Free-text guidance for the next plan authoring attempt.

operator_notes: |
  Anything the operator should see at gate, even on approval.
```

**Rule:** `governance.review_plan` may not return `review_status: revision_requested` unless it emits at least one structured concern with a `target_task_index` or `prd_requirement` reference where applicable. Pure prose revision requests are rejected and treated as `approved_with_concerns`.

#### 6.2.3 Revision loop

If `review_status: revision_requested`, dispatch `development.plan_implementation_revise` — a lightweight task that re-runs plan authoring with the structured concerns appended to the prompt. Bounded by `max_planning_revisions: int = 1` in resolved config. After exhaustion, planning proceeds with the latest plan and the unresolved concerns documented in `operator_notes` for the gate.

#### 6.2.4 Default-flip criteria

`split_implementation_planning: bool = false` in Revision 1. Flip to `true` once these conditions hold across a tracking window:

- At least 5 successful long-cycle planning runs with the split enabled (no gate failures attributable to the new flow).
- Plan YAML validity rate (parses on first attempt) is equal to or better than the colocated baseline.
- Planning workload duration regression ≤ 20% relative to the colocated baseline.
- Revision-loop activation rate is below 50% (otherwise the reviewer is requesting too many revisions, which usually means the prompt or rubric is wrong).

These thresholds are intentionally low-bar; the goal is to prevent indefinite "after stabilization" drift, not to set perfectionist gates. Flipping the default is a small follow-up PR, not part of this SIP's first delivery.

### 6.3 Capability M3 — Plan Changes

#### 6.3.1 Plan change schema

```yaml
# plan_change.yaml
version: 1
change_id: ovl_<uuid>
parent_plan_hash: <sha256 of CANONICAL serialized plan, see 6.3.6>
parent_change_id: <prior plan change's change_id, or null if first>
created_at: 2026-04-27T18:00:00Z
created_by: governance.correction_decision
reason: "Subtask 4 failed acceptance after self-eval and one repair attempt; PRD requires duplicate-join 409 not present anywhere."
operations:
  - op: add_task
    after_index: 4
    task:
      task_index: 8        # Always > max existing index across original + prior plan changes
      task_type: development.develop
      role: dev
      focus: "Add 409 duplicate-join handling"
      description: |
        ...
      expected_artifacts: [backend/routes.py]
      acceptance_criteria:
        - check: regex_match
          file: backend/routes.py
          pattern: "status_code\\s*=\\s*409"
          severity: error
      depends_on: [1]

  - op: tighten_acceptance
    task_index: 1
    add_criteria:
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths: [[POST, /runs/{id}/join]]
        severity: error
```

#### 6.3.2 Operations and invariants

**Revision 1 implements only `add_task` and `tighten_acceptance` in the schema, applier, and validator.** The other three operations (`remove_task`, `replace_task`, `reorder`) are **not present in code in Rev 1** — they remain in this section as the future-work design for operator-driven plan changes and a future `governance.replan` task. This narrows the implementation surface to the only operations the autonomous correction protocol justifies (per §6.3.10), reducing risk and aligning code with current use cases.

Rev 1 operations and invariants enforced at apply time:

| Op | Invariants | Status |
|---|---|---|
| `add_task` | New `task_index` strictly greater than max existing index across original + prior plan changes. Dependencies must reference existing (active or tombstoned) task indices. Added task must include at least one `expected_artifact` or one `error`-severity typed acceptance criterion (no empty-contract additions). | **Rev 1** |
| `tighten_acceptance` | Append-only. New criteria added; existing criteria neither removed nor weakened. Severity may be raised (`warning` → `error`) but not lowered. | **Rev 1** |

Future-work operations (designed here, not implemented in Rev 1):

| Op | Invariants | Status |
|---|---|---|
| `remove_task` | Cannot remove a task that has already started or completed in the current run. Tombstones the task in the working plan; does not delete from history. Any active task that depends on the removed task is an error unless the dependent is also tombstoned in the same plan change. | Future (operator / `governance.replan`) |
| `replace_task` | `task_index` and `task_type` immutable. Cannot replace a task that has already started or completed (use `add_task` for a follow-up instead). May not loosen acceptance — replacement criteria must be at least as strict as the original. | Future (operator / `governance.replan`) |
| `reorder` | Must not violate `depends_on`. Limited to not-yet-started tasks. | Future (operator / `governance.replan`) |

`loosen_acceptance` (removing or weakening criteria) is intentionally not supported in any form, ever. Loosening is suspicious and should be a manual operator action via re-gate, not a correction-driven plan change.

#### 6.3.3 Pure structural applier

```python
def apply_plan_changes(
    original: ImplementationPlan,
    changes: list[PlanChange],
) -> WorkingPlan:
    """Apply plan changes in order to produce the working plan.

    Pure function: same (original, changes) always yields same WorkingPlan.
    Validates structural invariants ONLY:
      - parent_change_id chain is linear and well-formed
      - parent_plan_hash matches canonical hash of original
      - operations satisfy structural invariants (§6.3.2)
      - new task indices are monotonic and unique

    Does NOT validate runtime constraints (that's validate_plan_change_for_run).
    """
```

Identity invariants the applier guarantees:

- Original task indices never change.
- Original task IDs (`task-{run}-m{idx}-{type}`) never change. Already-completed checkpoints stay valid.
- New tasks added via plan changes use indices strictly greater than any prior index, including across plan changes. Deterministic IDs continue to be unique and stable.
- Removed tasks are tombstoned, not deleted — the working plan preserves them as `status: removed_by_change` so audit trail and prior task IDs remain queryable.

#### 6.3.4 Execution-aware validator

Before a plan change is accepted for an active run, an execution-aware validator consults run state and rejects plan changes that would invalidate already-started or completed work:

```python
def validate_plan_change_for_run(
    plan_change: PlanChange,
    working_plan: WorkingPlan,
    run_state: RunState,        # which task IDs have started/completed/checkpointed
) -> list[ValidationError]:
    """Reject plan changes that mutate completed or in-flight work.

    Returns empty list if plan change is safe to accept.
    """
```

Rejection rules:

- `remove_task` targeting a task that has started or completed → reject.
- `replace_task` targeting a task that has started or completed → reject.
- `reorder` involving any started task → reject in Revision 1.
- `add_task` whose dependencies include a tombstoned task that has not produced the artifacts the new task expects → reject.

The applier produces the plan derivation; the validator approves the plan change for runtime use. Both must succeed before a plan change is forwarded to the executor.

#### 6.3.5 Completed-work immutability (explicit)

> Plan changes affect the remaining execution plan. They do not rewrite the semantic meaning of already-completed task checkpoints. Corrections to completed work are represented as new tasks (`add_task`) or repair tasks, not mutations of prior ones.

This is what the execution-aware validator enforces; called out separately because it's the load-bearing safety property.

#### 6.3.6 Canonical hashing and chain order

- **Plan hash** is computed over a canonical serialization of the parsed `ImplementationPlan` (sorted keys, normalized whitespace, deterministic list ordering), not over raw YAML text. Raw YAML hashing is a footgun because re-saved plans can produce different bytes despite identical content.
- **Plan change chain order** is determined by `parent_change_id` linkage, forming a strict linear chain rooted at the original plan. `created_at` is metadata for display only; it does not affect chain order or hash inputs.
- `change_id` uniqueness is enforced; collisions are rejected at apply time.

#### 6.3.7 Task identity vs. execution order

The applier preserves task indices as identity; execution order can diverge when plan changes add tasks. For example, a plan change adding `task_index: 9` `after_index: 4` produces a working plan where `m009` executes between `m004` and `m005` despite its higher index.

> **Task index is identity, not execution order.** `task-{run}-m009-development.develop` is a stable, unique reference for that task across checkpoints, logs, and artifacts. Its position in the working plan's execution order is determined by `after_index` and `depends_on`, not by index sort order.

Tooling and operator UI must not assume monotone-index ⇒ monotone-execution.

#### 6.3.8 Change-created task provenance

Every task materialized from a plan change carries metadata identifying the plan change that produced it:

```python
metadata = {
    "step_index": ...,
    "role": ...,
    "routing_reason": ...,
    # SIP-0092: plan change provenance
    "change_id": "ovl_abc123",
    "change_operation_index": 0,         # which op in the plan change produced this task
    "change_reason": "Subtask 4 failed acceptance...",
    "correction_decision_id": "corr_def456",  # if produced by correction protocol
}
```

This is what lets an operator answer "why does task `m009` exist" without grepping logs.

#### 6.3.9 Storage and forwarding

Plan changes are stored in the artifact vault with `artifact_type: "control_implementation_plan_change"`. The forwarding path that today carries `control_implementation_plan` artifacts to the implementation workload (fixed in `075fd9e`) is extended to carry all `control_implementation_plan_change` artifacts for the run, ordered by `parent_change_id` chain.

The executor's plan-loading code (`_load_plan_for_run`) becomes:

```python
plan = load_original_plan(run)
plan_changes = load_plan_changes_for_run(run)            # ordered by parent_change_id chain
working_plan = apply_plan_changes(plan, plan_changes)
```

#### 6.3.10 Re-gate matrix

| Operation | Rev 1 implementation | Autonomous correction producer | Operator action (future) | Future `governance.replan` |
|---|---|---|---|---|
| `add_task` | ✅ shipped | ✅ allowed | ✅ allowed | ✅ allowed |
| `tighten_acceptance` | ✅ shipped | ✅ allowed | ✅ allowed | ✅ allowed |
| `remove_task` | ❌ not in code | n/a (deferred) | requires schema + applier extension | reserved |
| `replace_task` | ❌ not in code | n/a (deferred) | requires schema + applier extension | reserved |
| `reorder` | ❌ not in code | n/a (deferred) | requires schema + applier extension | reserved |

Rev 1 narrowing rationale (§6.3.2): the autonomous correction protocol only justifies `add_task` and `tighten_acceptance`; the other three operations are designed here for future operator-driven plan changes and a future `governance.replan` task, but their schema, applier, and validator implementations are deferred. A plan change containing a deferred operation fails parsing in Rev 1.

#### 6.3.11 Bounded plan change count

Unbounded plan changes are a runaway risk. `max_plan_changes: int = 5` in resolved config. When exhausted, the correction protocol can no longer produce plan changes — only patch or escalate. Operators see a clear signal that the plan itself is the wrong shape and the cycle should re-gate.

### 6.4 Configuration Keys

Add to `_APPLIED_DEFAULTS_EXTRA_KEYS`:

| Key | Type | Default | Capability |
|-----|------|---------|------|
| `mechanical_acceptance` | `bool` | `true` | M1 — evaluate typed checks |
| `command_acceptance_checks` | `bool` | `true` (false in `selftest`) | M1 — enable `command_exit_zero` |
| `command_check_safelist` | `list[str]` | (built-in safelist, see §6.1.5) | M1 |
| `split_implementation_planning` | `bool` | `false` | M2 — enable `development.plan_implementation` |
| `max_planning_revisions` | `int` | `1` | M2 — bounded revision rounds |
| `plan_changes_enabled` | `bool` | `false` | M3.2 — loader/applier reads and applies persisted plan-change artifacts |
| `correction_plan_changes_enabled` | `bool` | `false` | M3.3 — autonomous correction protocol may emit plan changes |
| `max_plan_changes` | `int` | `5` | M3 — plan change count ceiling per run |

The split between `plan_changes_enabled` (loader/applier) and `correction_plan_changes_enabled` (autonomous producer) lets us ship and observe loader behavior with synthesized plan changes before authorizing the correction protocol to produce them. When `correction_plan_changes_enabled=true` but `plan_changes_enabled=false`, the producer is configured to emit changes but the executor never loads them — the producer is rejected at startup as a misconfiguration.

#### 6.4.1 Profile examples — current rollout defaults

The default profiles for the SIP-0092 rollout keep M2 and M3 off because their stages are conditional on milestone gates (see plan doc Milestone Gates section). M1 is enabled by default once shipped because it has prod evidence forcing the issue and is not gate-conditional.

```yaml
# build profile (current rollout — M1 on, M2 off, M3 off)
defaults:
  build_plan: true
  output_validation: true
  max_self_eval_passes: 1
  mechanical_acceptance: true               # M1 default-on
  command_acceptance_checks: true
  split_implementation_planning: false      # M2 awaits gate
  plan_changes_enabled: false               # M3 loader awaits gate
  correction_plan_changes_enabled: false    # M3 producer awaits gate

# selftest profile (smoke — minimal mechanical surface, M2/M3 off)
defaults:
  mechanical_acceptance: true
  command_acceptance_checks: false          # static checks only
  split_implementation_planning: false
  plan_changes_enabled: false
  correction_plan_changes_enabled: false
```

#### 6.4.2 Profile examples — post-gate target

These profiles show the **target state after the M1 → M2 and M2 → M3 milestone gates pass** and the corresponding stages ship. Do not enable these flags until the gate evaluation docs (`docs/plans/SIP-0092-gate-M{N}-evaluation.md`) are committed.

```yaml
# implementation profile (long-cycle — post-gate target, all on, deeper)
defaults:
  build_plan: true
  output_validation: true
  max_self_eval_passes: 2
  mechanical_acceptance: true
  command_acceptance_checks: true
  split_implementation_planning: true       # post-M2 gate
  max_planning_revisions: 1
  plan_changes_enabled: true                # post-M3.2 ship
  correction_plan_changes_enabled: true     # post-M3.3 ship
  max_plan_changes: 8
  max_correction_attempts: 3
```

---

## 7. Expected Behavior: group_run Cycle With This SIP

Long-cycle group_run (4-hour budget) running `implementation` profile:

**Planning phase (~12 minutes):**
1. `data.research` → context summary
2. `strategy.frame` → objective frame
3. `development.design_plan` → design plan
4. `qa.define_test_strategy` → test strategy with concrete typed criteria suggestions
5. **`development.plan_implementation`** (Max) → plan with 9 subtasks; typed acceptance with mixed `error` and `warning` severity on 5 of them
6. **`governance.review_plan`** (Max) → reviews plan, emits `plan_review.yaml` with `review_status: revision_requested` and one structured `acceptance_concern` (subtask 6 has no acceptance check for join/leave 409 handling)
7. `development.plan_implementation_revise` (Max) → tightens subtask 6 acceptance with a `regex_match` for the 409 status code
8. **Gate** — operator sees the original plan, the structured review concerns, and the revised plan side-by-side; approves.

**Build phase (~2.5 hours):**
- Subtasks 0–4 run sequentially. Each validates against typed acceptance:
  - Subtask 1 (Backend API endpoints): `endpoint_defined` for all 5 endpoints (severity `error`) + `import_present` for repository → all `passed`.
  - Subtask 4 (Frontend detail view): `regex_match` for duplicate-name error display (severity `error`) → `failed`. Self-eval fires; second LLM call sees the specific missing pattern in the failure description and adds the handler. Re-validates → `passed`.
- Subtask 6 (qa.test backend): tests run but only cover 3 of 5 endpoints. `regex_match` over `tests/test_backend.py` with `pattern: "client\\.(get|post)\\(['\"]/runs"`, `count_min: 5`, severity `error` → `failed` (only 3 matches). **Correction protocol fires.**
- Correction decision: `plan_change` (not `patch`). The autonomous producer is restricted to `add_task` and `tighten_acceptance`. It emits a plan change with one `add_task` operation (new subtask 9 "Add tests for join/leave endpoints") plus a `tighten_acceptance` on subtask 6 (raise `count_min` to enforce future runs see all 5). The execution-aware validator confirms neither operation touches completed work — subtask 6's existing checkpoint is preserved as `status: original_failed`; subtask 9 is appended. Working plan now has 10 active tasks.
- Build resumes from subtask 9. The new task carries provenance metadata (`change_id: ovl_xyz`, `correction_decision_id: corr_abc`, `change_reason: "qa.test backend coverage failed regex_match count_min=5"`), so any operator looking at task `m009` can trace exactly why it exists.

**Wrap-up (~5 minutes):** Standard. Closeout artifact references the original plan, the one plan change, the working plan, and the `plan_review.yaml`.

**Net effect compared to today:** typed `regex_match` with explicit `count_min` catches the partial test coverage that today's filename-only validation misses; the autonomous correction plan change (limited to `add_task` + `tighten_acceptance`) lets the squad add a missing test subtask without re-gating; the separated authoring caught a planning gap before the gate; the structured `plan_review.yaml` made the revision loop mechanical rather than prose-driven.

---

## 8. Implementation Plan

Three independently shippable stages mapped to the three capabilities. Each stage delivers value alone.

### Stage M1 — Mechanical Acceptance (3 PRs)

**PR 1.1:** Schema + parser + authoring-time validation
- Extend `PlanTask.acceptance_criteria` to accept typed dicts via flat YAML.
- Add `TypedCheck` dataclass and the normalization rule (§6.1.1).
- Update `ImplementationPlan.from_yaml()` to parse mixed lists and reject unknown check names / malformed params (§6.1.7).
- Tests: typed-only, prose-only, mixed; malformed typed shapes; unknown check name; unknown severity; flat-vs-nested parsing.

**PR 1.2:** Check evaluator framework + static checks + safety
- New module `src/squadops/cycles/acceptance_checks.py`.
- `CheckOutcome` with status enum (§6.1.4).
- Base class + registry; implement `endpoint_defined` (FastAPI), `import_present` (Python), `field_present`, `regex_match`, `count_at_least`. Plus `command_exit_zero` behind `command_acceptance_checks` flag (§6.1.5).
- Path/command safety enforcement (workspace chroot, argv-only, safelist, timeouts).
- Stack-aware bounded evaluation with `unsupported_stack_or_syntax` skip outcome (§6.1.6).
- Tests per check: passing, failing, skipped, error; severity behavior; safety rejections (path traversal, shell strings, oversize globs, command-not-in-safelist).

**PR 1.3:** Wire into `_validate_output_focused`
- Replace today's informational FC3 with typed-check evaluation.
- `error`-severity failures contribute to `missing_components`; `warning`/`info` and `skipped` reported in evidence only.
- Update self-eval prompt to include specific failed check descriptions.
- Update authoring prompt to document the check vocabulary, severity, and safety rules.
- Integration test: a plan with typed checks fails when generated code is incomplete; passes when complete; warning-severity check failure does not fail the task.

### Stage M2 — Separated Authoring (2 PRs)

**PR 2.1:** New `development.plan_implementation` handler
- Move `_produce_plan` body verbatim from `review_plan` to a new `DevelopmentPlanImplementationHandler`.
- Register `development.plan_implementation` task type.
- Add to planning step list when `split_implementation_planning: true`.
- Backward-compat: keep `review_plan` plan production behind the flag.

**PR 2.2:** Reviewer logic + structured review schema + revision loop
- Add `plan_review.yaml` schema (§6.2.2) and reviewer prompt.
- Reject prose-only revision requests (§6.2.2 rule).
- Add `development.plan_implementation_revise` task triggered on `review_status: revision_requested`.
- Bound revisions by `max_planning_revisions`.
- Document default-flip criteria (§6.2.4) in the SIP and surface a metric the operator can check.
- Integration test: structured concern produces a revised plan that addresses the concern; bound exhaustion proceeds with annotations in `operator_notes`.

### Stage M3 — Plan Changes (3 PRs)

**PR 3.1:** Plan change schema + pure structural applier
- New module `src/squadops/cycles/plan_change.py`: `PlanChange`, `apply_plan_changes`, canonical hashing (§6.3.6), parent chain check, identity invariants, structural operation invariants (§6.3.2).
- Schema supports all 5 operations.
- Tests for each operation type, parent-chain mismatches, hash mismatches, removed-task dependency errors, index uniqueness, severity-tightening rules.

**PR 3.2:** Execution-aware validator + loader integration + provenance
- `validate_plan_change_for_run()` (§6.3.4) consulting run state.
- Update `_load_plan_for_run` to load and apply plan changes via the chain order.
- Update plan change forwarding to carry `control_implementation_plan_change` artifacts.
- Add plan change provenance metadata to materialized envelopes (§6.3.8).
- Tests: working-plan derivation across 0/1/N plan changes; rejection of plan changes mutating started/completed tasks; provenance fields populated on materialized envelopes.

**PR 3.3:** Correction-protocol integration (restricted operations only)
- Extend `governance.correction_decision` to emit `decision: plan_change` with a generated `plan_change.yaml`.
- **Producer-side restriction:** correction protocol may only emit `add_task` and `tighten_acceptance` operations. Any other operation in a correction-produced plan change is rejected by the execution-aware validator.
- Bound by `max_plan_changes`.
- Integration test: a `SEMANTIC_FAILURE` that warrants a structural change produces a plan change with a single `add_task` (or `tighten_acceptance`); plan change is applied; cycle continues with revised plan; provenance metadata flows through.

### Tests

Coverage targets per stage:

| Layer | M1 | M2 | M3 |
|-------|----|----|----|
| Unit (parser/dataclasses) | ✅ | ✅ | ✅ |
| Unit (check eval / change applier / plan change validator) | ✅ | n/a | ✅ |
| Integration (handler) | ✅ | ✅ | ✅ |
| End-to-end cycle | ✅ | ✅ | ✅ |

Every test must catch a specific bug per `docs/TEST_QUALITY_STANDARD.md`. No tautological tests on dataclass fields.

---

## 9. Risks and Mitigations

| Risk | Capability | Mitigation |
|---|---|---|
| Typed checks too strict; valid output flagged | M1 | Severity field lets new checks ship at `warning`. `mechanical_acceptance: false` global escape hatch. Failed-check details in evidence support fast tuning. |
| Authoring prompt drowns in check syntax docs | M1 | Examples-first prompting (one concrete typed criterion per check type) plus a single-paragraph reference; mixed prose+typed lists explicitly allowed. |
| `command_exit_zero` runs untrusted code | M1 | Hard safelist; commands run in ACI-executor sandbox; per-check timeout; `command_acceptance_checks: false` disable flag; future smoke pack provides full container isolation. |
| Path/glob/regex injection from LLM-authored plans | M1 | Workspace chroot, argv-only, glob match cap, regex timeout, symlink rejection (§6.1.5). Plan is treated as untrusted input by design. |
| Stack expansion creep in `endpoint_defined` etc. | M1 | Explicit `unsupported_stack_or_syntax` skip outcome; new stacks added only via separate scoped PR (§6.1.6). |
| Reviewer rubber-stamps the proposer (M2) | M2 | Reviewer prompt is structured against named gaps; structured `plan_review.yaml` cannot be prose-only. Operator gate remains as final external check. |
| Revision loop oscillates | M2 | `max_planning_revisions: 1` bound (Revision 1); future expansion only after metrics support it. |
| `split_implementation_planning` flag stays default-off forever | M2 | Concrete flip criteria (§6.2.4) instead of "after stabilization." |
| Plan change storms (correction repeatedly emits changes) | M3 | `max_plan_changes: 5` bound; after exhaustion, correction limited to patch or escalate. |
| Autonomous correction makes plan incoherent via removal/replacement | M3 | Producer-side restriction: correction protocol may only emit `add_task` and `tighten_acceptance` (§6.3.10). Schema and applier support more operations, but only operator or future `governance.replan` may produce them. |
| Working-plan divergence between runs | M3 | Pure deterministic applier; canonical-form hashing (not raw YAML); parent-change-id chain ordering; replay tests on every PR. |
| Plan change mutates completed work, invalidating checkpoints | M3 | Execution-aware validator (§6.3.4) rejects any plan change touching started/completed task IDs. Completed-work immutability is an explicit principle (§3.7) and an enforced rule. |
| Operator confusion: which plan am I looking at? | M3 | Console must show original + change chain + working plan distinctly. Change-created tasks carry `change_id` / `change_reason` / `correction_decision_id` provenance metadata (§6.3.8). |

---

## 10. Alternatives Considered

### 10.1 Make all acceptance criteria typed; remove free-text

Cleaner, but loses operator-readable intent. Mixed lists let prose carry the "why" while typed checks carry the "what we'll measure."

### 10.2 Allow autonomous correction to emit any operation

Initial draft of M3 allowed the correction producer to emit all five operation types. Rev 2 restricted to `add_task` + `tighten_acceptance` because removal/replacement/reordering can easily make a long-cycle plan incoherent — the very situation correction is supposed to fix. Conservative producer plus full schema support gives us the full operation set when an operator (or future `governance.replan`) needs it, without giving autonomous correction the keys to rewrite history.

### 10.3 Treat plan changes as in-place mutations of the plan

Simpler API but loses the audit trail and the operator-readable "what changed since gate approval." The append-only chain is the same cost in implementation and a much stronger contract.

### 10.4 Skip M3; restrict long cycles to re-gate when the plan is wrong

Re-gate is heavy: it implies operator attention every time the squad needs to add a subtask. For autonomous long cycles (the explicit motivation in the cycle-length thread), this defeats the purpose. M3's bounded plan changes let the squad self-correct within governed limits.

### 10.5 Defer mechanical acceptance until full sandbox execution lands

Sandbox execution (run-the-app) is the smoke pack's job and is significant work. Mechanical acceptance via static analysis + safelisted commands is small, ships now, and complements the smoke pack rather than competing with it. Smoke pack later validates "the app runs"; M1 validates "the code says what the plan said it should say." Both useful; not redundant.

### 10.6 Hash raw YAML rather than canonical serialization

Raw-YAML hashing is the obvious approach but unstable across whitespace/key-order changes. Canonical serialization adds a small amount of complexity for parent-hash stability across re-saves. Worth it.

---

## 11. Future Work

- **Expand autonomous correction operation set.** Once long-cycle telemetry supports it, `governance.replan` can be the producer for `remove_task` / `replace_task` / `reorder`. Correction protocol stays conservative.
- **Stack-aware acceptance defaults.** When SIP-0072 (Stack Capability Registry) concretization lands, plan authoring can pull stack-default check sets (e.g., FastAPI ⇒ `endpoint_defined` + `import_present` for the repo; React ⇒ `count_at_least` for components).
- **Cross-handler validation.** A check that QA tests actually exercise the dev artifacts (named in SIP-0086 §10).
- **Operator-driven plan changes via API.** An endpoint to submit a plan change manually for active runs, with the same applier and bounds. Operator plan changes may use any of the five operations.
- **Replan task.** A `governance.replan` cadence-bound task that produces plan changes based on accumulated cycle state (time-budget pressure, defect density). Hooks reserved by M3.
- **Adaptive safelist.** Per-stack expansions to `command_check_safelist` driven by the stack capability registry.
- **Loosen-acceptance via gate.** Operator-initiated acceptance loosening as a re-gated action, distinct from in-cycle correction plan changes.

---

## 12. Revision History

- **Rev 3 (2026-04-30):** Terminology + scope tightening pre-implementation. Major changes:
  - **Title:** "Build Manifest Maturation — Mechanical Acceptance, Separated Authoring, and Delta Overlays" → "Implementation Plan Improvement — Mechanical Acceptance, Separated Authoring, and Plan Changes." Build manifest → implementation plan, delta overlay → plan change throughout. Three-layer alignment: module `cycles/implementation_plan.py`, class `ImplementationPlan`, artifact_type `control_implementation_plan`.
  - **Resolved correction-protocol decision name:** `decision: overlay` → `decision: plan_change` everywhere. The deprecated value is not supported.
  - **Narrowed M3 Rev 1 schema/applier scope to `add_task` + `tighten_acceptance`** (§6.3.2). The other three operations (`remove_task`, `replace_task`, `reorder`) are deferred from code entirely; they remain in this SIP as future-work design for operator-driven plan changes and `governance.replan`. The YAML parser rejects deferred operations at parse time.
  - **Split plan-change config** (§6.4): `plan_changes_enabled` (loader/applier) is now distinct from `correction_plan_changes_enabled` (autonomous producer). Default rollout has both off; misconfiguration (producer on, loader off) is rejected at startup.
  - **Profile examples reorganized** (§6.4.1, §6.4.2): current rollout defaults (M2/M3 off, gated) separated from post-gate target. Removes the contradiction between "M2/M3 are gated" and "examples enable them."
  - **Re-gate matrix updated** (§6.3.10) to show Rev 1 implementation status alongside autonomous/operator/replan eligibility.
  - **Implementation plan doc** introduces concrete milestone gates (M1 → M2, M2 → M3) and a structural-plan-change diagnostic field captured during M2 tracking. See `docs/plans/SIP-0092-implementation-plan-improvement-plan.md`.
- **Rev 2 (2026-04-27):** Incorporated external review. Major changes:
  - Typed-check schema normalized: flat YAML for authoring, internal `TypedCheck(check, params, severity, description)` for evaluators (§6.1.1).
  - Added severity field (§6.1.2) — `error` (default), `warning`, `info`. Only `error` failures contribute to `missing_components`.
  - Added `CheckOutcome` status enum (§6.1.4) — `passed` / `failed` / `skipped` / `error`.
  - Added explicit path/command safety subsection (§6.1.5).
  - Added stack-aware bounded evaluation rule with `unsupported_stack_or_syntax` skip outcome (§6.1.6).
  - Added authoring-time validation rules (§6.1.7) — unknown check names / malformed params fail plan validation at parse time.
  - Added `command_acceptance_checks` config flag for independent rollback of `command_exit_zero`.
  - Added `plan_review.yaml` schema (§6.2.2) with rule that revision requests cannot be prose-only.
  - Added M2 default-flip criteria (§6.2.4) replacing "after stabilization."
  - Split plan change handling into pure structural applier (§6.3.3) and execution-aware validator (§6.3.4).
  - Added explicit completed-work immutability principle (§3.7) and rule (§6.3.5).
  - **Restricted autonomous correction producer to `add_task` + `tighten_acceptance` only** (§6.3.10). Schema and applier still support all 5 ops; producer does not.
  - Tightened operation-level invariants per op (§6.3.2).
  - Specified canonical hashing and parent-change-id chain order (§6.3.6).
  - Clarified task index ≠ execution order after plan changes (§6.3.7).
  - Added change-created task provenance metadata (§6.3.8).
  - Fixed group_run example: replaced `endpoint_defined` cross-applied to test files with `regex_match` `count_min: 5` over the test file (§7).
  - Added Alternatives 10.2 and 10.6.
- **Rev 1 (2026-04-27):** Initial proposal.

---

## 13. References

- **SIP-0086** — Build Convergence Loop (parent SIP; this SIP closes its §10 "Mechanical acceptance criteria evaluation" and "Separate plan authoring from governance review" future-work items)
- **SIP-0079** — Implementation Run Contract (correction protocol the change producer integrates with)
- **SIP-0078** — Planning Workload Protocol (planning task step list extended by M2)
- **SIP-0072** — Stack-Aware Development Capabilities (future complement to typed-check authoring defaults)
- **SIP-0070** — Pulse Checks and Verification Framework (validator pattern reused)
- `src/squadops/cycles/implementation_plan.py` — current plan dataclasses and parser
- `src/squadops/capabilities/handlers/planning_tasks.py:432` — current `_produce_plan` (moves under M2)
- `src/squadops/cycles/task_plan.py:341` — current `_replace_build_steps_with_plan` (extended by M3 to apply changes)
- `src/squadops/capabilities/handlers/cycle_tasks.py` — current `_validate_output_focused` (extended by M1)
- `src/squadops/api/routes/cycles/runs.py` — gate promotion + control_implementation_plan forwarding (extended by M3 to forward `control_implementation_plan_change`)
- `adapters/capabilities/aci_executor.py` — sandbox executor for `command_exit_zero`
- Memory: `project_sip0086_manifest_handoff_bug.md` — observed plan forwarding bugs that motivate the artifact-type discipline plan changes inherit
- Memory: `project_spark_cycle_status.md` — observed YAML emission failures motivating M2's authoring-vs-review split
