# SIP-XXXX: Build Manifest Maturation — Mechanical Acceptance, Separated Authoring, and Delta Overlays

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-04-27
**Revision:** 1

---

## 1. Abstract

SIP-0086 introduced the build task manifest — a control-plane artifact produced during planning that decomposes a build into focused, role-typed subtasks. Capability A (manifest production, materialization, focused prompts, deterministic task IDs) shipped on main: `src/squadops/cycles/build_manifest.py`, `_produce_manifest` in `planning_tasks.py:432`, manifest expansion in `task_plan.py:341`. The first reliable group_run cycles to fill a build timebox came from this work.

Three follow-up gaps now bound how reliably a squad can build a non-trivial app over a long cycle. Each is named in SIP-0086 §10 (Future Work) but deferred at the time:

1. **Acceptance criteria are informational only** — they appear in the manifest, in the focused prompt, and in the self-evaluation prompt, but the validator does not evaluate them. Validation reduces to `expected_artifacts` filename matching plus stub detection (`cycle_tasks.py` FC1/FC2). A subtask whose generated code imports the wrong module, exposes the wrong endpoints, or omits required fields passes validation as long as the file names are right.
2. **Manifest authoring is colocated with planning approval** — `governance.assess_readiness` (Max) authors the manifest *and* signs off on planning readiness in the same handler call (`planning_tasks.py:420–428`). The proposer-judge collapse is acknowledged in SIP-0086 §6.1.3 as a known tradeoff; the operator gate is the only external check.
3. **The manifest is one-shot and immutable** — SIP-0086 §6.1.6 specifies that correction-driven changes are "represented as delta artifacts applied as overlays," but no overlay format, no overlay producer, and no overlay applier exist. In practice, a manifest that turns out wrong at hour 2 of a 6-hour cycle has no machine-readable revision path; the cycle either limps along with a bad plan or terminates at gate.

This SIP introduces three independently shippable capabilities that close those gaps:

- **Capability M1 — Mechanical Acceptance Criteria.** Add a typed acceptance check schema embedded in manifest tasks; evaluate them at handler validation time; surface results as first-class check entries in `ValidationResult.checks` alongside the existing FC1/FC2 checks.
- **Capability M2 — Separated Manifest Authoring.** Introduce a dedicated `governance.plan_build` planning task that authors the manifest. `governance.assess_readiness` reviews and signs off, restoring the proposer/reviewer separation.
- **Capability M3 — Manifest Delta Overlays.** Define a `manifest_delta.yaml` overlay schema and an applier that produces a derived working manifest from `(original_manifest, [overlay_1, ..., overlay_N])`. Wire the correction protocol and replan path to emit overlays instead of either mutating the original manifest or being unable to evolve it.

Each capability is independently valuable. M1 alone makes today's manifests far more discriminating. M2 alone improves planning-phase quality. M3 alone unlocks long-cycle adaptability. Together they turn the manifest from "produced once, consumed once" into a living plan the squad can iterate against.

---

## 2. Problem Statement

### 2.1 What SIP-0086 Shipped

Code grounded as of 2026-04-27 on main:

| Component | Location | Status |
|---|---|---|
| Manifest dataclasses + YAML parser + DAG validator | `src/squadops/cycles/build_manifest.py` | ✅ Shipped |
| Manifest production handler | `_produce_manifest` in `src/squadops/capabilities/handlers/planning_tasks.py:432` | ✅ Shipped (with retry loop and corrective feedback per `fbea2d7`) |
| Role + task_type constraints (squad-aware) | `planning_tasks.py:450–470` | ✅ Shipped (`c38a523`, `dc8e7c0`) |
| Builder routing in manifest prompt | `planning_tasks.py:475–504` | ✅ Shipped (`ec4db16`) |
| Manifest expansion to envelopes | `_replace_build_steps_with_manifest` in `task_plan.py:341` | ✅ Shipped |
| Deterministic task IDs (`task-{run}-m{idx}-{type}`) | `task_plan.py:281` | ✅ Shipped |
| Focused-task prompt adaptation | `cycle_tasks.py` (`subtask_focus` branch) | ✅ Shipped |
| Validation FC1 (expected_artifacts) + FC2 (non-stub) | `cycle_tasks.py` | ✅ Shipped |
| `outcome_class: SEMANTIC_FAILURE` emission | `cycle_tasks.py` | ✅ Shipped |
| Self-evaluation pass | `cycle_tasks.py` | ✅ Shipped |
| Gate promotion + control_manifest forwarding | `api/routes/cycles/runs.py` (`af306d3`, `075fd9e`) | ✅ Shipped |

The framework can decompose, materialize, prompt, validate, self-correct, and forward. What it cannot yet do is **judge whether the produced code does what the manifest said it should do**, and it cannot **revise the manifest mid-cycle**.

### 2.2 Gap M1: Acceptance Criteria Are Informational

`BuildTaskManifest` already carries `acceptance_criteria: list[str]` per task (`build_manifest.py:38`). The criteria are passed into the focused prompt (`cycle_tasks.py` `subtask_focus` branch) and the self-evaluation follow-up. They are *never* evaluated.

Consequence: a manifest entry like

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

### 2.3 Gap M2: Manifest Authoring Is Colocated With Planning Sign-Off

`governance.assess_readiness` (Max) currently:

1. Reads the planning artifact draft.
2. Validates frontmatter (`readiness`, `sufficiency_score`).
3. Decides whether planning is ready for the gate.
4. **Authors the build manifest in the same handler call** (`planning_tasks.py:420–428`).

The same agent invocation that judges planning sufficiency also produces the build decomposition that planning sufficiency is supposed to gate. SIP-0086 §6.1.3 explicitly named this:

> *"This introduces proposal-review colocation: the same component that proposes the build plan is judging its adequacy. The gate remains the human/operator checkpoint that mitigates this — the operator reviews the manifest before approving, providing an external check on decomposition quality. Long-term, a dedicated manifest producer (e.g., `governance.plan_build`) before `governance.review` may provide cleaner separation."*

Two operational consequences:

- **Single-call concentration.** A 32B model is asked to do governance review *and* manifest authoring in one call. Empirically (memory `project_spark_cycle_status.md`), Max occasionally emits invalid YAML in `build_task_manifest.yaml` even at 32B; concentration of both responsibilities is a contributing factor.
- **No reviewer for the proposer.** The operator gate is the only check; the squad itself never checks Max's decomposition before it reaches the gate. For a long cycle with a less-attentive operator, this is the weakest link in planning quality.

### 2.4 Gap M3: The Manifest Cannot Evolve

SIP-0086 §6.1.6 ("Plan identity"):

> *"The manifest becomes immutable after gate approval. The executor does not modify, reorder, or add to the manifest's task list. Correction-driven additions or substitutions are represented as delta artifacts applied as overlays; they do not mutate the original approved manifest."*

That's the design intent. The implementation has only the immutability half. There is no `manifest_delta.yaml` schema, no overlay producer, and no overlay applier. Today, when correction fires:

- The repair handler (`development.repair`) operates against the failed subtask with prior-artifact context.
- The original subtask checkpoint is preserved.
- No new subtasks can be added; no existing subtasks can be removed or reordered; no acceptance criteria can be tightened.

For a one-hour cycle this is acceptable — the repair handler converges or the cycle terminates. For a multi-hour cycle, the failure modes that warrant manifest evolution show up routinely:

- **Discovered missing layer** (e.g., manifest has no `auth` task because Max underweighted the PRD's auth requirement; correction needs to add a subtask, not just patch).
- **Re-order required** (e.g., frontend integration depends on a new backend endpoint that wasn't in the original manifest).
- **Stricter acceptance** (e.g., Eve discovers the original criteria were too loose; needs to ratchet them on a re-run).
- **Task split** (a subtask consistently fails because it bundled too much; needs to be split into two).

Without overlays, the cycle either limps along on a stale plan or terminates at the gate.

---

## 3. Design Principles

### 3.1 Acceptance criteria must be machine-readable to be enforceable

Free-text criteria are operator-readable, model-readable, and validator-illegible. The minimum useful unit is a typed check the validator can run. Criteria authoring should be guided into typed shapes rather than left as prose.

### 3.2 Separate the proposer from the reviewer

Authoring the build plan and signing off on planning readiness are different cognitive tasks. They should be different handler calls — even if the same agent role (Max) performs both — so the second call has a chance to catch the first call's mistakes.

### 3.3 Original manifest is the source of truth; overlays accumulate

The approved manifest stays immutable. Overlays are append-only audit trail. The "current working manifest" is always derived: `apply(original, overlays)`. This preserves the gate's contract (what the operator approved) while admitting evolution.

### 3.4 Overlays are governed, not free-form

A manifest overlay is a control-plane artifact like the manifest itself. It is produced by Max (or the repair chain on Max's behalf), validated against a schema, stored with `artifact_type: "control_manifest_delta"`, and observable. It is not a runtime mutation of in-memory state.

### 3.5 Backward-compatible at every layer

Manifests without typed acceptance still work (criteria continue to be informational for those tasks). Cycles without `governance.plan_build` still work (manifest production stays in `assess_readiness` as today). Cycles with no overlays produced still work (the working manifest equals the original).

### 3.6 Build on what shipped, don't re-spec it

This SIP does not redefine SIP-0086's manifest schema, executor materialization, deterministic task IDs, or correction routing. All of that is reused. Only acceptance evaluation, the authoring split, and the overlay format are new.

---

## 4. Goals

1. **Acceptance criteria with teeth.** A manifest task can carry typed acceptance checks (`endpoint_defined`, `import_present`, `field_present`, `command_exit_zero`, `regex_match`, `count_at_least`) that the build validator evaluates and reports as pass/fail, alongside existing FC1/FC2.
2. **Separated authoring.** A new `governance.plan_build` planning task authors the manifest. `governance.assess_readiness` becomes a true reviewer/sign-off step that may reject or request revisions to the manifest.
3. **Manifest delta overlays.** A typed overlay format supporting `add_task`, `remove_task`, `replace_task`, `tighten_acceptance`, and `reorder` operations, with an applier that produces the working manifest deterministically.
4. **Correction integration.** The correction protocol can produce overlays instead of (or in addition to) repair patches when a structural manifest change is the right response to a `SEMANTIC_FAILURE`.
5. **Observability.** Every overlay is stored as an artifact with `artifact_type: "control_manifest_delta"`. Every typed acceptance check result is in `ValidationResult.checks` and surfaced in evidence for the run.
6. **No regression.** Existing build profiles and existing manifests (with informational criteria, no overlays, monolithic authoring) continue to work without change.

---

## 5. Non-Goals

- Replacing the SIP-0086 manifest schema or task materialization mechanism.
- Defining a general-purpose constraint language. Typed acceptance checks are a small, fixed vocabulary chosen for build verification, not a Turing-complete DSL.
- Sandbox execution of generated code. Acceptance checks are static analysis (AST, regex, file content) plus targeted shell invocations (lint exit code, type-check exit code) — not running the app. Running the app is the smoke pack's job (separate SIP).
- Browser/UI verification. Same reason as above.
- Cross-handler "did the test exercise the code" checks. Listed in SIP-0086 §10 future work; remains out of scope here.
- Adaptive thresholds learned from prior cycles. Out of scope; criteria are author-specified per cycle.
- Replacing the operator gate. The gate still exists; M2 adds an *internal* reviewer step on top of it, not instead of it.

---

## 6. Design

### 6.1 Capability M1 — Mechanical Acceptance Criteria

#### 6.1.1 Schema extension

`ManifestTask.acceptance_criteria` today is `list[str]`. Extend it to accept either strings (informational, backward-compatible) or typed check dicts:

```yaml
acceptance_criteria:
  # Existing free-text form (informational, kept for back-compat)
  - "All 5 required endpoints are defined"

  # New typed forms (evaluated):
  - check: endpoint_defined
    file: backend/routes.py
    methods_paths:
      - [GET, /runs]
      - [POST, /runs]
      - [GET, /runs/{id}]
      - [POST, /runs/{id}/join]
      - [POST, /runs/{id}/leave]

  - check: import_present
    file: backend/routes.py
    module: backend.repository
    symbols: [Repository]

  - check: field_present
    file: backend/models.py
    target: class:RunEvent
    fields: [id, title, datetime, location, distance, pace_target, route_notes, participants]

  - check: regex_match
    file: backend/routes.py
    pattern: "status_code\\s*=\\s*409"
    description: "Duplicate join returns 409"

  - check: command_exit_zero
    command: ["python", "-m", "py_compile", "backend/routes.py"]
    cwd: "."
    timeout_seconds: 10
    description: "Backend compiles"
```

Parser changes localized to `build_manifest.py`. A `ManifestTask` becomes:

```python
@dataclass(frozen=True)
class TypedCheck:
    check: str
    params: dict          # check-specific payload (frozen)
    description: str = "" # human-readable summary

@dataclass(frozen=True)
class ManifestTask:
    task_index: int
    task_type: str
    role: str
    focus: str
    description: str
    expected_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: list[str | TypedCheck] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
```

Free-text strings remain accepted; mixed lists are valid.

#### 6.1.2 Check vocabulary (Revision 1)

A small, targeted set chosen because each one catches a real category of partial-build failures observed on group_run cycles:

| Check | Params | What it validates |
|---|---|---|
| `endpoint_defined` | `file`, `methods_paths` | FastAPI/Flask route decorator with method + path is present in the file. AST-based for FastAPI; regex fallback. Catches "wrote 2 of 5 endpoints" failures. |
| `import_present` | `file`, `module`, `symbols` | `from <module> import <symbols>` (or equivalent JS `import`) is present. Catches "wrote endpoints but never wired the repository." |
| `field_present` | `file`, `target` (class/dataclass/Pydantic model), `fields` | Named fields are declared on the named target. AST-based. Catches "model missing required attributes per PRD." |
| `regex_match` | `file`, `pattern`, optional `count_min` | Regex matches at least N times. Escape hatch for things AST checks don't cover (e.g., specific status codes, error messages). |
| `command_exit_zero` | `command`, `cwd`, `timeout_seconds` | Subprocess exits 0. Used for `py_compile`, `tsc --noEmit`, `eslint`, `ruff check`. Bounded by timeout; sandboxed via existing ACI executor. |
| `count_at_least` | `glob`, `min` | At least N files match the glob. Catches "wrote one component but PRD said three." |

Each check is implemented as a class with `evaluate(workspace_root, artifacts) -> CheckOutcome` returning `passed: bool`, `actual: dict`, `reason: str`. New checks are added by registering a class in a small registry — no dispatch logic in the validator.

The vocabulary is intentionally small. Future checks (e.g., `openapi_contract_match`, `pytest_collects`) can be added without touching the schema; the schema's open `params` dict accommodates them.

#### 6.1.3 Validator integration

`_validate_output_focused` in `cycle_tasks.py` already returns a `ValidationResult` with `checks: list[dict]`. Add a third check class alongside FC1 (expected_artifacts) and FC2 (non-stub):

```python
# FC3 (replaces today's "informational" stub)
typed_checks = [c for c in inputs.get("acceptance_criteria", []) if isinstance(c, dict)]
for criterion in typed_checks:
    outcome = await self._evaluate_typed_check(criterion, artifacts, context)
    checks.append({
        "check": f"acceptance:{criterion['check']}",
        "params": criterion.get("params", {}),
        "description": criterion.get("description", ""),
        "passed": outcome.passed,
        "actual": outcome.actual,
        "reason": outcome.reason,
    })
    if not outcome.passed:
        missing.append(f"acceptance:{criterion.get('description') or criterion['check']}")
```

Failed typed checks contribute to `missing_components`, which feeds the existing self-evaluation prompt unchanged. The self-eval LLM call now sees concrete failures ("acceptance: endpoint_defined POST /runs/{id}/join — actual: only GET /runs and POST /runs found") instead of generic "your output is incomplete."

Cumulative effect: today's self-eval pass produces additional files chasing keyword guesses; with typed checks it produces additional files chasing specific named gaps.

#### 6.1.4 Authoring guidance

The manifest authoring prompt (currently in `planning_tasks.py:508` and being moved by M2 to `governance.plan_build`) is extended to document the typed-check vocabulary and to encourage typed checks for any criterion that maps to one:

> *Where possible, express acceptance criteria as typed checks rather than prose. Available checks: `endpoint_defined`, `import_present`, `field_present`, `regex_match`, `command_exit_zero`, `count_at_least`. Mixed lists (some typed, some prose) are fine; prose criteria are surfaced to the implementer but not auto-evaluated.*

Free-text criteria remain valid. The authoring guidance is a quality nudge, not a constraint.

#### 6.1.5 Sandbox concerns for `command_exit_zero`

`command_exit_zero` runs subprocesses against generated code. This re-uses the existing ACI executor (`adapters/capabilities/aci_executor.py` — already used elsewhere) which provides a contained working directory and timeout. Allowed commands are restricted to a safelist (`python -m py_compile`, `python -m mypy`, `ruff check`, `tsc --noEmit`, `eslint`, `pyflakes`, `node --check`, `npm run lint`) — full sandbox isolation for arbitrary commands is left to the smoke-pack SIP, which needs proper container isolation anyway.

If a typed check requests a command outside the safelist, the validator records the check as `passed: false, reason: "command_not_in_safelist"`. The check authoring prompt references the safelist.

### 6.2 Capability M2 — Separated Manifest Authoring

#### 6.2.1 New planning task: `governance.plan_build`

Add a planning task that runs *before* `governance.assess_readiness`:

```
CURRENT (post-SIP-0086):
  Planning: data.research → strategy.frame → development.design_plan
            → qa.define_test_strategy → governance.assess_readiness (sign-off + manifest authoring)
            → [GATE]

PROPOSED:
  Planning: data.research → strategy.frame → development.design_plan
            → qa.define_test_strategy → governance.plan_build (manifest authoring)
            → governance.assess_readiness (sign-off, may reject/revise manifest)
            → [GATE]
```

Implementation: a new handler `GovernancePlanBuildHandler` in `planning_tasks.py` that takes the existing `_produce_manifest` logic (and its retry loop) verbatim, returns the manifest as its primary output rather than a side-effect on the planning artifact.

`governance.assess_readiness` loses its manifest-production responsibility and gains a manifest-review responsibility:

- Reads the manifest produced by `governance.plan_build` from prior outputs.
- Sanity-checks: subtask coverage vs. PRD, dependency sanity, role sanity.
- Either signs off (planning is ready, manifest is approved) or emits a revision request.

#### 6.2.2 Revision flow

If `assess_readiness` requests revision, options for handling:

- **Option A (Revision 1):** Surface the revision request as a `governance.plan_build_revise` task that re-runs manifest authoring with the reviewer feedback as input. Bounded by `max_planning_revisions: int = 1` in resolved config. After exhaustion, planning proceeds with the latest manifest and the reviewer concerns documented in the planning artifact for the operator gate.
- **Option B (deferred):** Full multi-round dialogue. Out of scope for Revision 1.

Option A is small, bounded, and reuses existing handler dispatch. The revision input is a structured `manifest_review.yaml` artifact produced by `assess_readiness` listing concrete concerns (e.g., "task 4 has no acceptance checks for the duplicate-join requirement").

#### 6.2.3 Backward compatibility

`governance.plan_build` is opt-in via `applied_defaults.split_manifest_authoring: bool = False` (default off in Revision 1, flipped to default on after stabilization). When false, the existing path stays — `assess_readiness` produces the manifest as today, and the new handler is skipped. When true, the planning step list inserts `governance.plan_build` and removes manifest production from `assess_readiness`.

Step-list resolution is in `task_plan.py`'s `_resolve_workload_steps`; the change is local.

### 6.3 Capability M3 — Manifest Delta Overlays

#### 6.3.1 Overlay schema

```yaml
# manifest_delta.yaml
version: 1
overlay_id: ovl_<uuid>
parent_manifest_hash: <sha256 of original manifest YAML>
parent_overlay_id: <prior overlay's overlay_id, or null if first>
created_at: 2026-04-27T18:00:00Z
created_by: governance.correction_decision
reason: "Subtask 4 failed acceptance after self-eval and one repair attempt; PRD requires duplicate-join 409 not present anywhere."
operations:
  - op: add_task
    after_index: 4
    task:
      task_index: 8        # Always > max existing index
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
      depends_on: [1]

  - op: tighten_acceptance
    task_index: 1
    add_criteria:
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths: [[POST, /runs/{id}/join]]
```

Operations supported in Revision 1:

| Op | Effect |
|---|---|
| `add_task` | Append a new task. New `task_index` must be greater than max existing index across original + prior overlays (preserves deterministic IDs). `after_index` controls execution order placement. |
| `remove_task` | Mark a task as removed. Dependencies on a removed task are an error if the depending task is not also removed. |
| `replace_task` | Replace a task's body wholesale (focus/description/expected_artifacts/acceptance). `task_index` and `task_type` are immutable. |
| `tighten_acceptance` | Append additional `acceptance_criteria` entries to an existing task. Cannot remove existing criteria — tightening only. |
| `reorder` | Change execution order without changing dependencies. |

`loosen_acceptance` (removing criteria) is intentionally not supported in Revision 1. Loosening is suspicious and should be a manual operator action via re-gate, not a correction-driven overlay.

#### 6.3.2 Applier semantics

```python
def apply_overlays(
    original: BuildTaskManifest,
    overlays: list[ManifestDelta],
) -> WorkingManifest:
    """Apply overlays in order to produce the working manifest.

    Each overlay's parent_overlay_id must equal the prior overlay's overlay_id
    (or null for the first), forming a linear chain. The original's hash must
    match every overlay's parent_manifest_hash.
    """
```

The applier is pure: same `(original, overlays)` always yields the same `WorkingManifest`. The working manifest is what `_replace_build_steps_with_manifest` consumes; today it consumes the `BuildTaskManifest` directly. The change at the consumer side is one line — load and apply overlays before passing to expansion.

**Identity invariants:**

- Original task indices never change.
- Original task IDs (`task-{run}-m{idx}-{type}`) never change. Already-completed checkpoints stay valid.
- New tasks added via overlays use indices strictly greater than any prior index, including across overlays. Deterministic IDs continue to be unique and stable.
- Removed tasks are tombstoned, not deleted — the working manifest preserves them as `status: removed_by_overlay` so audit trail and prior task IDs remain queryable.

#### 6.3.3 Storage and lookup

Overlays are stored in the artifact vault with `artifact_type: "control_manifest_delta"`. Forwarding to the implementation workload (the same path that today forwards `control_manifest`, fixed in `075fd9e`) is extended to forward all overlays for the run, ordered by `created_at`.

The executor's manifest-loading code (`_load_manifest_for_run`) becomes:

```python
manifest = load_original_manifest(run)
overlays = load_overlays_for_run(run)
working_manifest = apply_overlays(manifest, overlays)
```

#### 6.3.4 Overlay producers

Three sources can produce overlays:

1. **`governance.correction_decision` (M3 + correction).** When the correction protocol decides the right response to a `SEMANTIC_FAILURE` is structural rather than patch-only, it emits an overlay. The decision becomes typed: `decision: patch | overlay | escalate`. Today the decision is `patch | escalate` only.
2. **`governance.replan` (new, optional).** A standalone task that can be triggered (cadence-bound or on demand) to revise the manifest mid-run. Out of scope for M3 Revision 1; reserved as the integration point.
3. **Operator action via API** (future). Not in this SIP. Mentioned only to clarify the schema is operator-friendly.

Revision 1 wires only producer (1) — the correction-decision integration. Producer (2) is left as a future-work hook with the schema and applier in place to support it.

#### 6.3.5 Bounded overlay count

Unbounded overlays are a runaway risk. Add `max_manifest_overlays: int = 5` to resolved config. When exhausted, the correction protocol can no longer produce overlays — only patch or escalate. Operators see a clear signal that the manifest itself is the wrong shape and the cycle should re-gate.

### 6.4 Configuration Keys

Add to `_APPLIED_DEFAULTS_EXTRA_KEYS`:

| Key | Type | Default | Capability |
|-----|------|---------|------|
| `mechanical_acceptance` | `bool` | `true` | M1 — evaluate typed checks |
| `command_check_safelist` | `list[str]` | (built-in safelist) | M1 — `command_exit_zero` allowlist |
| `split_manifest_authoring` | `bool` | `false` | M2 — enable `governance.plan_build` |
| `max_planning_revisions` | `int` | `1` | M2 — bounded revision rounds |
| `manifest_overlays_enabled` | `bool` | `true` | M3 — apply overlays on load |
| `max_manifest_overlays` | `int` | `5` | M3 — overlay count ceiling |

Profile examples:

```yaml
# build profile (Revision 1 defaults — M1 on, M2 off, M3 on)
defaults:
  build_manifest: true
  output_validation: true
  max_self_eval_passes: 1
  mechanical_acceptance: true
  manifest_overlays_enabled: true
  max_manifest_overlays: 5
  split_manifest_authoring: false   # Flip true after M2 stabilizes

# implementation profile (long-cycle — all on)
defaults:
  build_manifest: true
  output_validation: true
  max_self_eval_passes: 2
  mechanical_acceptance: true
  manifest_overlays_enabled: true
  max_manifest_overlays: 8
  split_manifest_authoring: true
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
5. **`governance.plan_build`** (Max) → manifest with 9 subtasks, typed acceptance on 5 of them
6. **`governance.assess_readiness`** (Max) → reviews the manifest, requests one revision (subtask 6 has no acceptance for join/leave 409 handling)
7. `governance.plan_build_revise` (Max) → tightens subtask 6's criteria
8. **Gate** — operator sees the original manifest, the review concerns, and the revised manifest side-by-side; approves.

**Build phase (~2.5 hours):**
- Subtasks 0–4 run sequentially. Each validates against typed acceptance:
  - Subtask 1 (Backend API endpoints): `endpoint_defined` for all 5 endpoints + `import_present` for repository → passes.
  - Subtask 4 (Frontend detail view): `regex_match` for duplicate-name error display → fails. Self-eval fires; second LLM call sees the specific missing pattern and adds the handler. Re-validates → passes.
- Subtask 6 (qa.test backend) fails: tests run but only cover 3 of 5 endpoints (`count_at_least` glob `tests/test_*.py` failed at `actual=1, expected_min=1` — passed; but `endpoint_defined` cross-check on test file finds only 3 endpoint test functions). **Correction protocol fires.**
- Correction decision: `overlay` (not `patch`). Overlay adds a new subtask 9 ("Add tests for join/leave endpoints") and tightens subtask 6's criteria. Working manifest now has 10 active tasks. Original task IDs unchanged; new subtask gets `task-{run}-m009-qa.test`.
- Build resumes from subtask 9. Subtask 6's prior checkpoint stays.

**Wrap-up (~5 minutes):** Standard. Closeout artifact references the original manifest, the one overlay, and the working manifest.

**Net effect compared to today:** typed checks catch the partial test coverage that today's filename-only validation misses; the overlay lets the squad add a missing test subtask without re-gating; the separated authoring caught a planning gap before the gate.

---

## 8. Implementation Plan

Three independently shippable stages mapped to the three capabilities. Each stage delivers value alone.

### Stage M1 — Mechanical Acceptance (3 PRs)

**PR 1.1:** Schema + parser
- Extend `ManifestTask.acceptance_criteria` to accept typed dicts.
- Add `TypedCheck` dataclass.
- Update `BuildTaskManifest.from_yaml()` to parse mixed lists.
- Tests: typed-only, prose-only, mixed; malformed typed shapes; unknown check name.

**PR 1.2:** Check evaluator framework
- New module `src/squadops/cycles/acceptance_checks.py`.
- Base class + registry; implement `endpoint_defined`, `import_present`, `field_present`, `regex_match`, `count_at_least`, `command_exit_zero` (safelisted only).
- Tests per check: passing, failing, malformed params.

**PR 1.3:** Wire into `_validate_output_focused`
- Replace today's informational FC3 with typed-check evaluation.
- Update self-eval prompt to include specific failed check descriptions.
- Update authoring prompt to document the check vocabulary.
- Integration test: a manifest with typed checks fails when generated code is incomplete; passes when complete.

### Stage M2 — Separated Authoring (2 PRs)

**PR 2.1:** New `governance.plan_build` handler
- Move `_produce_manifest` body verbatim from `assess_readiness` to a new `GovernancePlanBuildHandler`.
- Register `governance.plan_build` task type.
- Add to planning step list when `split_manifest_authoring: true`.
- Backward-compat: keep `assess_readiness` manifest production behind the flag.

**PR 2.2:** Reviewer logic in `assess_readiness` + revision loop
- Add manifest-review prompt and `manifest_review.yaml` output schema.
- Add `governance.plan_build_revise` task triggered by review concerns.
- Bound revisions by `max_planning_revisions`.
- Integration test: revision request produces a revised manifest; bound exhaustion proceeds with annotations.

### Stage M3 — Delta Overlays (3 PRs)

**PR 3.1:** Overlay schema + applier
- New module `src/squadops/cycles/manifest_overlay.py`: `ManifestDelta`, `apply_overlays`, hash check, parent chain check, identity invariants.
- Tests for each operation type, parent-chain mismatches, removed-task dependency errors, index uniqueness.

**PR 3.2:** Loader integration
- Update `_load_manifest_for_run` to load and apply overlays.
- Update overlay forwarding (the path fixed in `075fd9e` for `control_manifest`) to also forward `control_manifest_delta` artifacts.
- Tests: working-manifest derivation across 0, 1, N overlays.

**PR 3.3:** Correction-protocol integration
- Extend `governance.correction_decision` to emit `decision: overlay` with a generated `manifest_delta.yaml`.
- Bound by `max_manifest_overlays`.
- Integration test: a `SEMANTIC_FAILURE` that warrants a structural change produces an overlay; overlay is applied; cycle continues with revised plan.

### Tests

Coverage targets per stage:

| Layer | M1 | M2 | M3 |
|-------|----|----|----|
| Unit (parser/dataclasses) | ✅ | ✅ | ✅ |
| Unit (check eval / overlay applier) | ✅ | n/a | ✅ |
| Integration (handler) | ✅ | ✅ | ✅ |
| End-to-end cycle | ✅ | ✅ | ✅ |

Every test must catch a specific bug per `docs/TEST_QUALITY_STANDARD.md`. No tautological tests on dataclass fields.

---

## 9. Risks and Mitigations

| Risk | Capability | Mitigation |
|---|---|---|
| Typed checks too strict; valid output flagged | M1 | Conservative initial vocabulary (no semantic `_intent_match`-style checks); `mechanical_acceptance: false` escape hatch; failed-check details in evidence support fast tuning. |
| Authoring prompt drowns in check syntax docs | M1 | Examples-first prompting (one concrete typed criterion per check type) plus a single-paragraph reference; mixed prose+typed lists explicitly allowed. |
| `command_exit_zero` runs untrusted code | M1 | Hard safelist; commands run in ACI-executor sandbox; per-check timeout; future smoke pack provides full container isolation. |
| Reviewer rubber-stamps the proposer (M2) | M2 | Reviewer prompt is structured against named gaps (PRD coverage, role coverage, acceptance coverage); operator gate remains as final external check. Reviewer cannot reduce criteria, only flag missing ones. |
| Revision loop oscillates | M2 | `max_planning_revisions: 1` bound (Revision 1); future expansion only after metrics support it. |
| Overlay storms (correction repeatedly emits overlays) | M3 | `max_manifest_overlays: 5` bound; after exhaustion, correction limited to patch or escalate. |
| Working-manifest divergence between runs | M3 | Pure deterministic applier; parent-hash and parent-overlay-id chain checks; replay tests on every PR. |
| Removed-task dependency errors (orphan dependencies) | M3 | Applier rejects overlays that orphan dependencies; correction-decision prompt requires the LLM to declare dependent removals together. |
| Existing manifests break | M1, M3 | Backward-compatible schema (prose criteria still valid; absent overlays = working manifest = original); feature flags default-on for new keys, default-off for M2. |
| Operator confusion: which manifest am I looking at? | M3 | Console must show original + overlay chain + working manifest distinctly. Console UI is downstream work but the artifact types make the distinction explicit. |

---

## 10. Alternatives Considered

### 10.1 Make all acceptance criteria typed; remove free-text

Cleaner, but loses operator-readable intent. Mixed lists let prose carry the "why" while typed checks carry the "what we'll measure."

### 10.2 Author manifest in `governance.review` instead of `governance.plan_build`

The original SIP-0086 spec called for `governance.review`; the implementation diverged to `governance.assess_readiness` because review was renamed. M2 lands the originally intended separation under the implemented naming, not a third name. `governance.plan_build` is more descriptive than reusing either existing name.

### 10.3 Treat overlays as in-place mutations of the manifest

Simpler API but loses the audit trail and the operator-readable "what changed since gate approval." The append-only chain is the same cost in implementation and a much stronger contract.

### 10.4 Skip M3; restrict long cycles to re-gate when the manifest is wrong

Re-gate is heavy: it implies operator attention every time the squad needs to add a subtask. For autonomous long cycles (the explicit motivation in the cycle-length thread), this defeats the purpose. M3's bounded overlays let the squad self-correct within governed limits.

### 10.5 Defer mechanical acceptance until full sandbox execution lands

Sandbox execution (run-the-app) is the smoke pack's job and is significant work (port allocation, container teardown, stack-aware startup). Mechanical acceptance via static analysis + safelisted commands is small, ships now, and complements the smoke pack rather than competing with it. Smoke pack later validates "the app runs"; M1 validates "the code says what the manifest said it should say." Both useful; not redundant.

---

## 11. Future Work

- **Stack-aware acceptance defaults.** When SIP-0072 (Stack Capability Registry) concretization lands, manifest authoring can pull stack-default check sets (e.g., FastAPI ⇒ `endpoint_defined` + `import_present` for the repo; React ⇒ `count_at_least` for components).
- **Operator-driven overlays via API.** An endpoint to submit an overlay manually for active runs, with the same applier and bounds.
- **Replan task.** A `governance.replan` cadence-bound task that produces overlays based on accumulated cycle state (time-budget pressure, defect density). Hooks reserved by M3.
- **Cross-handler validation.** A check that QA tests actually exercise the dev artifacts (named in SIP-0086 §10).
- **Adaptive safelist.** Per-stack expansions to `command_check_safelist` driven by the stack capability registry.
- **Loosen-acceptance via gate.** Operator-initiated acceptance loosening as a re-gated action, distinct from in-cycle correction overlays.

---

## 12. References

- **SIP-0086** — Build Convergence Loop (parent SIP; this SIP closes its §10 "Mechanical acceptance criteria evaluation" and "Separate manifest authoring from governance review" future-work items)
- **SIP-0079** — Implementation Run Contract (correction protocol the overlay producer integrates with)
- **SIP-0078** — Planning Workload Protocol (planning task step list extended by M2)
- **SIP-0072** — Stack-Aware Development Capabilities (future complement to typed-check authoring defaults)
- **SIP-0070** — Pulse Checks and Verification Framework (validator pattern reused)
- `src/squadops/cycles/build_manifest.py` — current manifest dataclasses and parser
- `src/squadops/capabilities/handlers/planning_tasks.py:432` — current `_produce_manifest` (moves under M2)
- `src/squadops/cycles/task_plan.py:341` — current `_replace_build_steps_with_manifest` (extended by M3 to apply overlays)
- `src/squadops/capabilities/handlers/cycle_tasks.py` — current `_validate_output_focused` (extended by M1)
- `src/squadops/api/routes/cycles/runs.py` — gate promotion + control_manifest forwarding (extended by M3 to forward `control_manifest_delta`)
- Memory: `project_sip0086_manifest_handoff_bug.md` — observed manifest forwarding bugs that motivate the artifact-type discipline overlays inherit
- Memory: `project_spark_cycle_status.md` — observed YAML emission failures motivating M2's authoring-vs-review split
