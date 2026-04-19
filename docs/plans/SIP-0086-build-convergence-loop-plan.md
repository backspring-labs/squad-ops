# Plan: SIP-0086 Build Convergence Loop

## Context

SIP-0086 addresses a group_run cycle that completed in 22 seconds, producing 15% of a full-stack FastAPI + React app and declaring success. The root cause is a four-link chain: static task plans (2 build tasks regardless of PRD complexity), single-pass LLM execution, mechanical success criteria, and an inert correction protocol. The SIP introduces two separable capabilities: (A) dynamic build task decomposition via a manifest, and (B) output validation with correction protocol activation.

**Branch:** `feature/sip-0086-build-convergence-loop` (off main)
**SIP:** `sips/accepted/SIP-0086-Build-Convergence-Loop-Dynamic.md` (Rev 4)

---

## Runtime Contracts

These invariants govern implementation across all phases.

**RC-1 (Manifest immutability):** The approved build task manifest becomes immutable after gate approval. Correction-driven additions or substitutions are represented as delta artifacts applied as overlays; they do not mutate the original manifest.

**RC-2 (Deterministic task IDs):** Manifest-derived task IDs follow `task-{run_id[:12]}-m{task_index:03d}-{task_type}`. IDs must be stable across checkpoint/resume and must not collide with planning-phase or correction-phase task ID namespaces.

**RC-3 (Sequential execution):** Revision 1 executes manifest tasks in listed order. `depends_on` is validated for correctness (no cycles, indices in range) but does not drive dynamic reordering or parallelization.

**RC-4 (Graceful fallback):** When no manifest is present or manifest extraction/validation fails, the executor falls back to static `BUILD_TASK_STEPS`. A warning is logged. No error is raised.

**RC-5 (Control-plane artifact type):** The manifest is stored with `artifact_type: "control_manifest"`, distinct from work-product types (`document`, `source`, `test`). This is a new artifact type.

**RC-6 (Focused prompt exclusivity):** When `subtask_focus` is present in inputs, the handler uses the focused prompt path. When absent, the legacy monolithic prompt path is used. There is no hybrid mode.

**RC-7 (Validation is cumulative):** Self-evaluation validates the merged artifact set (original + all self-eval additions), not only the latest response.

**RC-8 (Acceptance criteria are informational in Rev 1):** Acceptance criteria are included in prompts and evidence but are not mechanically enforced pass/fail gates. Focused-task validation gates on expected_artifacts presence and non-stub checks.

---

## Stage A — Build Decomposition (Phases 1–4)

Delivers manifest model, production, materialization, and focused prompts. Independently valuable: multi-task builds fill the timebox even without validation.

### Phase 1: Build Task Manifest Model & Schema

#### Commit 1a: ManifestTask, ManifestSummary, BuildTaskManifest dataclasses

**New file:**

| File | Contents |
|------|----------|
| `src/squadops/cycles/build_manifest.py` | `ManifestTask`, `ManifestSummary`, `BuildTaskManifest` frozen dataclasses |

**ManifestTask fields:**
- `task_index: int`
- `task_type: str`
- `role: str`
- `focus: str`
- `description: str`
- `expected_artifacts: list[str]`
- `acceptance_criteria: list[str]`
- `depends_on: list[int]`

**ManifestSummary fields:**
- `total_dev_tasks: int`
- `total_qa_tasks: int`
- `total_tasks: int`
- `estimated_layers: list[str]`

**BuildTaskManifest fields:**
- `version: int`
- `project_id: str`
- `cycle_id: str`
- `prd_hash: str`
- `tasks: list[ManifestTask]`
- `summary: ManifestSummary`

**Methods:**
- `from_yaml(cls, content: str) -> BuildTaskManifest` — parse YAML, validate schema
- `validate_against_profile(self, profile: SquadProfile) -> list[str]` — check roles exist in profile

**Tests:** `tests/unit/cycles/test_build_manifest.py` (~12)
- Valid manifest round-trips through `from_yaml()`
- Missing required fields raise `ValueError`
- `depends_on` with cycle (e.g., `[1, 0]` where 1 depends on 0 and 0 depends on 1) raises `ValueError`
- `depends_on` with out-of-range index raises `ValueError`
- `task_type` not in known set raises `ValueError`
- `validate_against_profile()` reports missing roles
- `validate_against_profile()` passes with valid profile
- Subtask count below `min_build_subtasks` raises `ValueError`
- Subtask count above `max_build_subtasks` raises `ValueError`
- Empty tasks list raises `ValueError`
- Malformed YAML raises `ValueError`
- Acceptance criteria field optional (empty list default)

#### Commit 1b: ArtifactType.CONTROL_MANIFEST + schema keys

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/cycles/models.py` | Add `CONTROL_MANIFEST = "control_manifest"` to `ArtifactType` class |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | Add `build_manifest`, `max_build_subtasks`, `min_build_subtasks` to `_APPLIED_DEFAULTS_EXTRA_KEYS` |

`CONTROL_MANIFEST` is introduced here (not deferred to Stage C) because RC-5 and Stage A manifest storage depend on it. The runtime contract must match the implementation order.

**Tests:** Existing schema tests should continue to pass. Add 1 test that the new keys are accepted in a profile defaults dict. Add 1 test that `ArtifactType.CONTROL_MANIFEST` exists.

---

### Phase 2: Manifest Production (governance.review)

#### Commit 2a: Extend GovernanceReviewHandler to produce manifest

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Override `handle()` in `GovernanceReviewHandler` (currently inherits from `_CycleTaskHandler` at lines 352–358) |

**Implementation:**

`GovernanceReviewHandler` currently has no `handle()` override — it inherits the base class `handle()` which produces a single `{_artifact_name}` document artifact.

**Design decision:** Override `GovernanceReviewHandler.handle()` as an intentional multi-artifact path that produces both the governance review and, when enabled, the manifest from a single LLM response. Do not call the base `handle()` and retrofit the manifest afterward — build one response path that explicitly owns both artifacts. This avoids shape drift from trying to layer manifest extraction on top of the generic inherited handler.

The override must:

1. Check `resolved_config.get("build_manifest", True)` — if disabled, delegate to base `handle()` (existing behavior)
2. When enabled, build a prompt that requests both the governance review AND the manifest as a fenced YAML block
3. Call LLM via `chat_stream_with_usage()` (same as base handler)
4. Extract governance review content (markdown prose) as the primary artifact
5. Extract `build_task_manifest.yaml` from fenced YAML blocks via `extract_fenced_files()`
6. Validate manifest structurally via `BuildTaskManifest.from_yaml()` — if validation fails, log warning, return governance review without manifest (RC-4 fallback)
7. Validate manifest against policy (subtask count vs `min_build_subtasks` / `max_build_subtasks` from resolved_config) — this is runtime policy, not schema validation (see note below)
8. Store manifest as additional artifact with `type: "control_manifest"` (RC-5)
9. Return `HandlerResult` with both governance review and manifest artifacts

**Validation separation:** Keep `BuildTaskManifest.from_yaml()` structural (schema, types, DAG correctness). Keep subtask min/max policy checks in the handler using resolved config. The dataclass parser should not be overloaded with cycle-specific runtime policy.

**Tests:** `tests/unit/capabilities/handlers/test_governance_review_manifest.py` (~8)
- Handler produces governance review + manifest when `build_manifest: true`
- Handler produces governance review only when `build_manifest: false`
- Malformed manifest YAML falls back gracefully (warning logged, no manifest artifact)
- Manifest below `min_build_subtasks` falls back gracefully
- Manifest above `max_build_subtasks` falls back gracefully
- Manifest artifact has `type: "control_manifest"`
- Manifest `prd_hash` matches SHA-256 of PRD content
- Handler works when LLM response contains no YAML block (graceful fallback)

---

### Phase 3: Manifest Consumption (task planner + executor)

#### Commit 3a: Extend generate_task_plan() with manifest parameter

**Modified file:**

| File | Change |
|------|--------|
| `src/squadops/cycles/task_plan.py` | Add `manifest: BuildTaskManifest | None = None` parameter to `generate_task_plan()` |

**Implementation:**

In `generate_task_plan()` (line 209), after step resolution:

1. If `manifest is not None` and build steps are included:
   - Replace static `BUILD_TASK_STEPS` (or `BUILDER_ASSEMBLY_TASK_STEPS`) with manifest-derived steps
   - For each `ManifestTask`, create `(task.task_type, task.role)` tuple
2. When creating envelopes for manifest-derived steps:
   - Use deterministic task IDs: `task-{run_id[:12]}-m{task_index:03d}-{task_type}` (RC-2)
   - The `-m{index}-` namespace must not collide with planning-phase IDs (UUID-based) or correction-phase IDs (`corr-{run_id}-{index}-{type}`)
   - Populate `inputs.subtask_focus`, `inputs.subtask_description`, `inputs.expected_artifacts`, `inputs.subtask_index`, `inputs.acceptance_criteria` from manifest task
3. Preserve existing lineage chaining (correlation_id, causation_id)

**Tests:** `tests/unit/cycles/test_task_plan_manifest.py` (~10)
- With manifest: produces N envelopes matching manifest task count (not 2)
- Without manifest: produces 2 envelopes (existing behavior unchanged)
- Manifest-derived envelopes have deterministic task IDs matching RC-2 pattern
- Manifest-derived envelopes have `subtask_focus` in inputs
- Manifest-derived envelopes have `acceptance_criteria` in inputs
- Causation chain links manifest tasks sequentially
- Planning steps preserved before manifest build steps
- Builder-aware routing still works when manifest includes builder role tasks
- Profile with missing role for manifest task raises CycleError
- Empty manifest (0 tasks) falls back to static steps
- Task ID namespaces do not collide: planning (UUID), manifest (`-m{idx}-`), correction (`corr-`) IDs are distinct

#### Commit 3b: Executor loads manifest after gate approval

**Modified file:**

| File | Change |
|------|--------|
| `adapters/cycles/distributed_flow_executor.py` | After gate approval in `_execute_sequential()`, load manifest from artifact vault and pass to `generate_task_plan()` |

**Implementation:**

In `_execute_sequential()`, after `_handle_gate()` returns (gate approved, run resumed):

1. Scan `stored_artifacts` for `art_ref.filename == "build_task_manifest.yaml"` (or `art_ref.artifact_type == "control_manifest"`)
2. If found: fetch content from vault, parse via `BuildTaskManifest.from_yaml()`
3. Call `generate_task_plan(cycle, run, profile, manifest=manifest)` to get materialized build envelopes
4. Merge with remaining plan: replace not-yet-executed build steps with manifest-derived envelopes
5. If not found or parse fails: log warning, continue with existing static plan (RC-4)

**Replacement semantics:** After gate approval, the executor rematerializes only the build-phase segment of the plan from the approved manifest and excludes already-completed planning envelopes by stable task ID. The already-approved planning-phase results remain untouched — the manifest does not alter completed planning task identity. Only the build-phase portion (previously static `BUILD_TASK_STEPS`) is replaced with manifest-derived envelopes.

**Tests:** `tests/unit/adapters/cycles/test_executor_manifest_loading.py` (~6)
- Executor loads manifest from artifact vault after gate approval
- Executor produces manifest-derived envelopes for build phase
- Executor falls back to static steps when no manifest in vault
- Executor falls back to static steps when manifest parse fails
- Completed planning tasks are skipped (not re-executed)
- Manifest-derived task IDs match checkpoint completed_task_ids on resume
- RC-1 immutability: after gate approval, correction/resume logic does not mutate the original manifest artifact; any repair data is stored as separate delta artifacts

#### Commit 3c: Update _enrich_envelope() artifact chaining for manifest-driven subtasks

**Modified file:**

| File | Change |
|------|--------|
| `adapters/cycles/distributed_flow_executor.py` | Update `_BUILD_ARTIFACT_FILTER` and/or `_enrich_envelope()` for dev→dev artifact chaining |

The existing `_enrich_envelope()` populates `artifact_contents` for build tasks by filtering prior artifacts via `_BUILD_ARTIFACT_FILTER`. Currently `development.develop` only consumes artifacts from `["strategy.analyze_prd", "development.design"]` — planning artifacts. It does not consume artifacts from prior `development.develop` tasks.

This must change for manifest-driven subtasks. Manifest-driven `development.develop` tasks must see prior source/config/document artifacts from earlier build subtasks, not only planning artifacts. Without this, Stage A may look successful while still starving later subtasks of accumulated build context.

**Implementation:** When manifest-driven subtasks are active (detectable via `subtask_focus` in envelope inputs), use a broader filter:
- `by_type: ["source", "config", "document"]` — include all prior build artifacts
- Or add `"development.develop"` to `by_producing_task` for `development.develop`

The broader `by_type` filter is preferred because it is manifest-agnostic and handles mixed dev/qa/builder task sequences.

**Tests:** `tests/unit/adapters/cycles/test_enrich_envelope_chaining.py` (~3)
- Subtask #4 receives source artifacts from subtasks #0–#3
- Subtask #4 receives planning artifacts (strategy, design) as well as prior build artifacts
- Legacy (non-manifest) enrichment unchanged

---

### Phase 4: Handler Prompt Adaptation

#### Commit 4a: DevelopmentDevelopHandler focused prompt

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | In `DevelopmentDevelopHandler`, detect `subtask_focus` in inputs and switch prompt construction |

**Implementation:**

Override or extend `_build_user_prompt()` (lines 490–517):

1. Check `inputs.get("subtask_focus")`
2. If present: build focused prompt per SIP §6.1.5 (focus, description, expected files, acceptance criteria, prior artifacts, "produce ONLY these files")
3. If absent: use existing monolithic prompt (RC-6)

The focused prompt includes:
- `## Build Task: {focus}`
- Description
- `### Expected Output Files` (bullet list)
- `### Acceptance Criteria` (bullet list)
- `### Context` (PRD)
- `### Prior Artifacts` (already built, do not reproduce)

**Tests:** `tests/unit/capabilities/handlers/test_dev_focused_prompt.py` (~5)
- Focused prompt includes subtask focus and description
- Focused prompt includes acceptance criteria section
- Focused prompt includes expected output files
- Focused prompt includes prior artifacts
- Legacy prompt used when no subtask_focus (unchanged behavior)
- RC-6 exclusivity: `subtask_focus` present → focused path only; absent → legacy path only; no hybrid

#### Commit 4b: QATestHandler focused prompt

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Same pattern for `QATestHandler` — detect `subtask_focus`, scope test generation to specific source artifacts |

**Tests:** `tests/unit/capabilities/handlers/test_qa_focused_prompt.py` (~3)
- Focused prompt scopes tests to subtask's expected artifacts
- Focused prompt includes acceptance criteria
- Legacy prompt used when no subtask_focus

---

## Stage A Checkpoint

At this point, a cycle with `build_manifest: true` will:
- Produce a manifest during governance.review
- Pause at gate for operator to review manifest
- After approval, materialize 8–15 focused build tasks
- Execute each with a focused prompt receiving prior artifacts
- Still use success-by-default (no validation yet)

**Validation cycle:** Run `group_run` cycle with `build` profile. Verify:
- Manifest is produced during governance.review
- Gate shows manifest alongside governance review
- Build phase has N tasks instead of 2
- Later subtasks actually receive prior build artifacts and reference them in output (artifact chain continuity)

The last point is critical — decomposition without artifact accumulation is just more tasks, not cumulative convergence.

---

## Stage B — Build Convergence & Correction Activation (Phases 5–7)

Delivers output validation, outcome classification, and self-evaluation. Works on both manifest-driven and legacy monolithic tasks.

### Phase 5: Output Validation Framework

#### Commit 5a: ValidationResult dataclass and base _validate_output()

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Add `ValidationResult` dataclass and `_validate_output()` to `_CycleTaskHandler` |

**ValidationResult fields:**
- `passed: bool`
- `checks: list[dict]`
- `missing_components: list[str]`
- `coverage_ratio: float`
- `summary: str`

**Base method:** Returns `ValidationResult(passed=True, ...)` by default (no validation). Build handlers override.

#### Commit 5b: DevelopmentDevelopHandler._validate_output() — focused mode

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Override `_validate_output()` in `DevelopmentDevelopHandler` with focused-task and legacy-monolithic modes per SIP §6.3.1/§6.3.2 |

**Focused-task checks (when `subtask_focus` present):**
- FC1: Expected artifacts present (from `inputs.expected_artifacts`) — **required gate**
- FC2: Non-stub files (shared `_detect_stubs()` helper) — **required gate**
- FC3: Acceptance criteria (informational, included in evidence — RC-8) — **not a gate in Rev 1**

**Focused-task pass/fail rule:** Focused-task validation passes only if all expected artifacts are present AND no required artifact is a stub. Acceptance criteria are recorded in evidence and included in self-eval prompts but do not fail the task in Revision 1.

**Legacy monolithic checks (when no `subtask_focus`):**

Legacy monolithic validation exists for backward compatibility and obvious incompleteness detection; manifest-driven focused validation is the intended operating mode for non-trivial builds. Heuristic monolithic validation is designed to catch obvious incompleteness, not to certify completeness.

- C1: Stack coverage heuristic (`_detect_expected_layers()` from PRD keywords)
- C2: Artifact count heuristic (`_estimate_min_artifacts()`)
- C3: Non-stub files

**Shared helpers:**
- `_detect_stubs(artifacts: list[dict]) -> list[str]` — returns list of stub filenames
- `_detect_expected_layers(prd: str, impl_plan: str | None) -> dict` — heuristic keyword matching
- `_estimate_min_artifacts(prd: str, impl_plan: str | None) -> int` — rough heuristic

**Tests:** `tests/unit/capabilities/handlers/test_dev_validation.py` (~12)
- Focused: all expected artifacts present → passes
- Focused: missing expected artifact → fails with specific missing list
- Focused: stub file detected → fails
- Focused: acceptance criteria included in evidence (informational)
- Legacy: backend + frontend layers detected from PRD with "FastAPI" + "React" → expects both
- Legacy: backend-only output for full-stack PRD → fails stack coverage
- Legacy: 3 artifacts for full-stack PRD → fails artifact count
- Legacy: stub file detected → fails
- Legacy: PRD with only backend keywords → expects backend only (no false frontend expectation)
- No subtask_focus and no PRD → passes (no validation possible)
- Validation result summary is human-readable
- Coverage ratio computed correctly

#### Commit 5c: QATestHandler._validate_output()

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Override `_validate_output()` in `QATestHandler` |

**Checks:**
- Test file presence (at least one file with test functions)
- Non-stub test files
- Test report presence (if expected)

**Tests:** `tests/unit/capabilities/handlers/test_qa_validation.py` (~5)

#### Commit 5d: Wire validation into handle()

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | In `DevelopmentDevelopHandler.handle()` and `QATestHandler.handle()`, call `_validate_output()` after `extract_fenced_files()` |

Check `resolved_config.get("output_validation", True)` — if disabled, skip validation (existing behavior).

**Tests:** Integration test verifying handler calls validation and returns failure when validation fails.

---

### Phase 6: Outcome Classification Wiring

#### Commit 6a: Wire outcome_class and failure_classification

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Import `TaskOutcome`, `FailureClassification`. Set `outputs["outcome_class"]` based on validation result. |

**Logic (per SIP §6.6):**
- Validation passed → `outputs["outcome_class"] = TaskOutcome.SUCCESS`
- Validation failed → `outputs["outcome_class"] = TaskOutcome.SEMANTIC_FAILURE`, `outputs["failure_classification"] = FailureClassification.WORK_PRODUCT`
- Include `validation_result` dict in both outputs and evidence

**Tests:** `tests/unit/capabilities/handlers/test_outcome_classification.py` (~4)
- Passed validation → `outcome_class == TaskOutcome.SUCCESS`
- Failed validation → `outcome_class == TaskOutcome.SEMANTIC_FAILURE`
- Failed validation → `failure_classification == FailureClassification.WORK_PRODUCT`
- Validation result included in outputs

---

### Phase 7: Self-Evaluation Pass

#### Commit 7a: _build_self_eval_prompt() and _merge_artifacts()

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | Add `_build_self_eval_prompt()` and `_merge_artifacts()` to `_CycleTaskHandler` |

**`_build_self_eval_prompt()`:** Constructs follow-up prompt with validation summary, missing components, and already-produced file list. Per SIP §6.5.

**`_merge_artifacts()`:** Merges new artifacts into existing by filename. Self-eval may add missing artifacts or replace same-name artifacts, but the merged set is always the authoritative candidate set for revalidation (RC-7). Records all additions and replacements in evidence with before/after sizes. Per SIP §6.7.

**Tests:** `tests/unit/capabilities/handlers/test_self_eval.py` (~6)
- Self-eval prompt includes validation summary
- Self-eval prompt includes missing components
- Self-eval prompt lists already-produced files
- Merge adds new files
- Merge replaces same-name files
- Merge records additions/replacements in evidence with sizes

#### Commit 7b: Wire self-evaluation loop in handle()

**Modified file:**

| File | Change |
|------|--------|
| `cycle_tasks.py` | In `DevelopmentDevelopHandler.handle()` and `QATestHandler.handle()`, add self-eval loop between validation failure and outcome classification |

**Logic (per SIP §6.5):**
1. After initial validation fails
2. Check `resolved_config.get("max_self_eval_passes", 1)` — if 0, skip to outcome classification
3. Loop up to `max_self_eval_passes` times:
   - Build self-eval prompt with validation failures
   - Second LLM call with conversation context (system, user, assistant, followup)
   - Extract fenced files from response
   - Merge into artifact set (RC-7: validate merged set)
   - Re-validate merged set
   - If validation passes, break
4. Record `self_eval_passes` count and `self_eval_final_validation` in evidence

**Tests:** `tests/unit/capabilities/handlers/test_self_eval_loop.py` (~5)
- Self-eval fires when validation fails and `max_self_eval_passes > 0`
- Self-eval skipped when `max_self_eval_passes == 0`
- Self-eval produces additional artifacts that are merged
- Validation runs against merged artifact set (RC-7)
- Self-eval bounded by `max_self_eval_passes`

---

## Stage B Checkpoint

At this point, build handlers:
- Validate output against subtask contract (focused) or PRD (legacy)
- Emit `outcome_class: SEMANTIC_FAILURE` when validation fails
- Attempt self-correction before escalating
- Trigger the SIP-0079 correction protocol for the first time

**Validation cycle:** Run `group_run` cycle. Deliberately use a model/prompt that produces incomplete output. Verify validation catches it, self-eval attempts correction, and if still incomplete, correction protocol fires.

---

## Stage C — Profile Tuning & Hardening (Phases 8–9)

### Phase 8: Profile Updates and Schema Keys

#### Commit 8a: Add all new keys to schema and profiles

**Modified files:**

| File | Change |
|------|--------|
| `schema.py` | Add `output_validation`, `max_self_eval_passes`, `min_artifact_count`, `stub_threshold_bytes` to `_APPLIED_DEFAULTS_EXTRA_KEYS` |
| `profiles/build.yaml` | Add `build_manifest: true`, `output_validation: true`, `max_self_eval_passes: 1`, `max_build_subtasks: 12` |
| `profiles/implementation.yaml` | Add `build_manifest: true`, `output_validation: true`, `max_self_eval_passes: 2`, `max_build_subtasks: 15` |
| `profiles/selftest.yaml` | Add `build_manifest: false`, `output_validation: false` |

---

### Phase 9: Full Test Suite

| Test | What |
|------|------|
| 9a | Integration: `governance.review` produces valid manifest from a realistic PRD |
| 9b | Integration: full cycle with manifest produces correct envelope count |
| 9c | Integration: handler returns SEMANTIC_FAILURE, correction protocol activates |
| 9d | Integration: self-eval resolves incomplete output without correction |
| 9e | End-to-end: group_run cycle with build profile produces ~8 build tasks |
| 9f | End-to-end: checkpoint/resume works with manifest-derived task IDs |

---

## File Change Summary

| File | Stage | Type |
|------|-------|------|
| `src/squadops/cycles/build_manifest.py` | A | New |
| `src/squadops/cycles/models.py` | A | Modified (ArtifactType.CONTROL_MANIFEST) |
| `src/squadops/cycles/task_plan.py` | A | Modified (manifest param) |
| `src/squadops/capabilities/handlers/cycle_tasks.py` | A+B | Modified (handlers, validation, self-eval) |
| `src/squadops/contracts/cycle_request_profiles/schema.py` | A+C | Modified (new keys) |
| `adapters/cycles/distributed_flow_executor.py` | A | Modified (manifest loading) |
| `src/squadops/contracts/cycle_request_profiles/profiles/build.yaml` | C | Modified |
| `src/squadops/contracts/cycle_request_profiles/profiles/implementation.yaml` | C | Modified |
| `src/squadops/contracts/cycle_request_profiles/profiles/selftest.yaml` | C | Modified |

---

## Risk Watch List

| Risk | Watch for | Mitigation |
|------|-----------|------------|
| `_enrich_envelope()` artifact filter doesn't chain dev→dev | Subtask #4 missing artifacts from #0–#3 | Phase 3c verification; update `_BUILD_ARTIFACT_FILTER` |
| Manifest YAML too large for LLM context window | Governance review truncates manifest | `_guard_prompt_size()` should protect; test with realistic PRD |
| Self-eval LLM call context too large | Second call with full conversation history exceeds context | Apply same `_guard_prompt_size()` to self-eval messages |
| Manifest task_type not matching handler registry | Executor dispatches task with no handler | Validate task_types in `BuildTaskManifest.from_yaml()` |
| Gate approval polling doesn't see manifest artifact | Manifest stored after gate check in wrong order | Manifest stored before gate pause, not after |
