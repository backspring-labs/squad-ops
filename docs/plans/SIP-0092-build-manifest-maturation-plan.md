# Plan: SIP-0092 Build Manifest Maturation

## Context

SIP-0092 is a SIP-0086 follow-up that closes three deferred gaps in the build manifest pipeline:

- **M1 — Mechanical Acceptance Criteria.** Today `acceptance_criteria` is `list[str]` informational input only; FC3 in `_validate_output_focused` is `included_in_evidence`. M1 introduces typed checks, severity, a `CheckOutcome` status enum, untrusted-input safety, and validator integration.
- **M2 — Separated Manifest Authoring.** `_produce_manifest` currently runs as a side-effect inside `GovernanceAssessReadinessHandler.handle()` (`planning_tasks.py:424`). M2 splits authoring into a new `governance.plan_build` task and turns `assess_readiness` into a structured reviewer that emits `manifest_review.yaml`.
- **M3 — Manifest Delta Overlays.** SIP-0086 §6.1.6 specified overlays as the immutability-preserving evolution path; nothing was implemented. M3 introduces an overlay schema, a pure structural applier, an execution-aware validator, conservative producer-side restrictions on autonomous correction (`add_task` + `tighten_acceptance` only), and provenance metadata on overlay-created tasks.

**SIP:** `sips/accepted/SIP-0092-Build-Manifest-Maturation-Mechanical.md` (Rev 2)
**Parent SIP:** `sips/implemented/SIP-0086-Build-Convergence-Loop-Dynamic.md`
**Branch model:** This plan lands on `feature/sip-0092-build-manifest-maturation` (off main, after SIP acceptance via PR #70). Implementation commits per phase build on this plan per the SIP workflow in `CLAUDE.md`.

The three stages (M1/M2/M3) are independently shippable and can land in separate feature branches if scheduling demands it. The default sequence below ships them in order because M1 produces the typed-check substrate that M3's `tighten_acceptance` operation extends, and M2's reviewer emits `manifest_review.yaml` entries that reference M1's typed checks.

---

## Runtime Contracts

These invariants govern implementation across all phases. Numbered to extend SIP-0086's plan (RC-1..RC-8) without renumbering them.

**RC-9 (Acceptance is severity-weighted):** A typed acceptance check failure contributes to `missing_components` only when its severity is `error`. `warning`, `info`, and `skipped` outcomes are reported in `ValidationResult.checks` evidence but do not fail the task and do not trigger correction.

**RC-10 (Manifest is untrusted input):** Every value in a typed check is treated as LLM-authored input. Paths are workspace-chrooted; commands are argv-only and safelisted; regex and globs are bounded; symlinks pointing outside the workspace are rejected. Evaluator code never invokes a shell.

**RC-11 (Authoring-time validation):** Unknown `check` names, malformed `params`, and unknown `severity` values are rejected by `BuildTaskManifest.from_yaml()`. The existing `_produce_manifest` retry loop (`planning_tasks.py:572`) treats these as parse failures and re-prompts. Stack-unsupported but well-formed checks are valid manifests; they evaluate to `status: skipped`.

**RC-12 (Stack-aware bounded evaluators):** Each typed check declares the stacks it supports. Inputs outside that set produce `status: skipped` with reason `unsupported_stack_or_syntax`. New stacks are added in scoped follow-up PRs, never as heuristic expansion inside an existing check.

**RC-13 (Original manifest immutability):** The approved manifest hash and the original manifest YAML never change after gate approval. The "current working manifest" is always derived as `apply_overlays(original, overlays)`. The original is the source of truth; overlays are an append-only audit trail rooted in the original via `parent_manifest_hash` over the canonical serialization.

**RC-14 (Pure structural applier; execution-aware validator):** `apply_overlays(original, overlays)` is a pure function — same inputs always produce the same `WorkingManifest`. Runtime constraints (overlay would invalidate started/completed work) are enforced separately by `validate_overlay_for_run(overlay, working_manifest, run_state)`. Both must succeed before an overlay is forwarded to the executor.

**RC-15 (Completed-work immutability):** Overlays affect only the remaining execution plan. They never replace, remove, reorder, or otherwise rewrite the semantic meaning of started or completed task checkpoints. Corrections to completed work are represented as new tasks (`add_task`) — never as mutations of prior ones. This is enforced by the execution-aware validator.

**RC-16 (Conservative autonomous producer):** The autonomous correction protocol may produce overlays containing only `add_task` and `tighten_acceptance` operations. The schema and the structural applier support all five operation types; producer-side restriction is enforced in the execution-aware validator. Other operations require operator action or a future `governance.replan`.

**RC-17 (Task index ≠ execution order after overlays):** `task_index` is identity. Execution order is determined by `after_index` and `depends_on` in the working manifest. Tooling and operator UI must not assume monotone-index ⇒ monotone-execution.

**RC-18 (Bounded overlay count):** Overlays per run are bounded by `max_manifest_overlays` (default 5). After exhaustion, the correction protocol may not produce further overlays — only patch or escalate. This is the runaway guardrail.

**RC-19 (Backward compatibility per stage):** Each stage preserves prior behavior under its disable flag. M1 off → criteria stay informational. M2 off (`split_manifest_authoring: false`) → manifest authoring stays inside `assess_readiness`. M3 off (`manifest_overlays_enabled: false`) → working manifest equals original; correction stays in patch-only mode.

---

## Stage M1 — Mechanical Acceptance Criteria

Three PRs. Independently valuable: even without M2 or M3, M1 makes today's manifests far more discriminating during validation.

### Phase M1.1 — Schema, Parser, Authoring-Time Validation

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/cycles/build_manifest.py` | Add `TypedCheck` frozen dataclass. Extend `ManifestTask.acceptance_criteria` to `list[str \| TypedCheck]`. Update `from_yaml()` to parse mixed lists with the flat-YAML normalization rule (SIP §6.1.1). |
| `src/squadops/cycles/build_manifest.py` | New `_KNOWN_CHECKS` registry (name → required-params spec) used by the parser to enforce RC-11. |

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

- Unknown `check` name.
- Required field for the named check missing or wrong type (per `_KNOWN_CHECKS` spec).
- `severity` not in `{error, warning, info}`.
- Path field with `..` traversal or absolute path (cheap pre-eval rejection at parse time; full chrooting still applies at evaluation).

**Tests:** `tests/unit/cycles/test_build_manifest.py` (extend existing file)

- Mixed prose+typed list parses; both forms preserved with correct types.
- Typed-only list parses; each `TypedCheck.params` excludes `{check, severity, description}`.
- Default severity is `error` when omitted.
- Unknown `check` name raises `ValueError` with the offending name in the message.
- Each known check's required-field omission raises `ValueError` (parametrized over the check vocabulary).
- Wrong-type param (e.g., `methods_paths: "GET /runs"` as string) raises `ValueError`.
- Unknown `severity` value raises `ValueError`.
- Absolute path or `..` in path field raises `ValueError`.
- Round-trip: `from_yaml()` → re-serialize via canonical form → `from_yaml()` produces equal manifest (load-bearing for M3 hashing in §6.3.6).

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
    name: str
    supported_stacks: frozenset[str]   # e.g., {"fastapi"}; empty = stack-agnostic

    async def evaluate(
        self,
        params: dict,
        workspace_root: Path,
        artifacts: list[Artifact],
        context: HandlerContext,
    ) -> CheckOutcome: ...
```

**Registry:** `_CHECK_REGISTRY: dict[str, type[BaseCheck]]`. Adding a new check is a class registration, not a dispatch edit.

**Revision 1 vocabulary:**

| Check | Stacks | Implementation notes |
|---|---|---|
| `endpoint_defined` | `fastapi` | AST walk for `@app.METHOD("/path")` and `@router.METHOD("/path")` decorators; path matching tolerant of trailing slash. Flask deferred to a separate scoped PR. |
| `import_present` | `python` (AST). JS/TS regex fallback gated behind `frontend_acceptance_checks` follow-up flag (out of scope here). | Walks `import` and `from ... import ...` nodes. |
| `field_present` | `python` (AST: dataclasses, Pydantic v2 models) | Walks class body assignments; matches `Annotated[...]` and `Field(...)` declarations. |
| `regex_match` | stack-agnostic | Compiled regex with input-size bound. `count_min` defaults to 1. |
| `count_at_least` | stack-agnostic | Glob with workspace-chroot and 10,000-match cap. |
| `command_exit_zero` | stack-agnostic; gated by `command_acceptance_checks` flag | Runs in ACI executor; argv-only; safelist enforced. |

**Safety implementation (RC-10):**

- Path resolution helper `_safe_resolve(path: str, workspace_root: Path) -> Path` rejects absolute paths, `..` traversal, and symlinks pointing outside `workspace_root`. Returns `CheckOutcome(status="error", reason="path_escapes_workspace")` to caller via raised `PathSafetyError`.
- Glob match cap (default 10_000). Exceeding produces `status: error` with reason `glob_match_cap_exceeded`.
- Regex compilation guarded by input-size bound; pathological regex against long files produces `status: error` with reason `regex_timeout`.
- Command safelist `command_check_safelist` (config-loaded; built-in default in SIP §6.1.5). Argv[0] not in safelist → `status: skipped` reason `command_not_in_safelist`. Shell-string command (single string instead of list) → `status: error` reason `command_must_be_argv`.
- Per-command timeout: default 10s, max 60s. Exceeding produces `status: failed` reason `command_timeout`.
- Command env: clean restricted env (no `LD_PRELOAD`, no `PYTHONPATH` injection).

**Tests:** `tests/unit/cycles/test_acceptance_checks.py`

Per-check parametrized matrix covering `passed` / `failed` / `skipped` / `error`:

- `endpoint_defined`: all paths defined → passed; subset missing → failed with `actual.found` listing what was found and `actual.missing` listing what wasn't; non-FastAPI file → skipped `unsupported_stack_or_syntax`.
- `import_present`: imports present → passed; module imported but symbol not imported → failed; non-Python target → skipped.
- `field_present`: all fields declared on the named class → passed; partial → failed with `actual.missing`; class not found in file → failed `class_not_found`.
- `regex_match`: matches ≥ `count_min` → passed; matches < `count_min` → failed with `actual.match_count`; pathological regex on big input → error.
- `count_at_least`: glob meets minimum → passed; below minimum → failed; cap exceeded → error.
- `command_exit_zero`: argv exits 0 → passed; non-zero → failed with `actual.stdout_tail`/`stderr_tail`/`exit_code`; argv[0] not safelisted → skipped; shell string → error; over timeout → failed `command_timeout`.

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
| `src/squadops/capabilities/handlers/planning_tasks.py` | Extend the manifest-authoring prompt (in `_produce_manifest`, `planning_tasks.py:475–504`) to document the typed-check vocabulary, severity, flat-YAML shape, and safety rules. Examples-first (one concrete typed criterion per check type). |

**Validator integration (sketch, replaces `cycle_tasks.py:965` block):**

```python
typed = [c for c in inputs.get("acceptance_criteria", []) if isinstance(c, TypedCheck)]
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
    if outcome.status == "failed" and criterion.severity == "error":
        missing.append(f"acceptance:{criterion.description or criterion.check}")
```

**Config keys (extend `_APPLIED_DEFAULTS_EXTRA_KEYS`):**

| Key | Default | Notes |
|---|---|---|
| `mechanical_acceptance` | `true` | Master flag. False → typed checks parse but evaluate to `skipped` reason `mechanical_acceptance_disabled`. |
| `command_acceptance_checks` | `true` (`false` in `selftest`) | Independent rollback for `command_exit_zero` only. |
| `command_check_safelist` | built-in safelist | Operator-controlled; manifest authors cannot extend it. |

**Tests:**

Unit (`tests/unit/capabilities/test_cycle_tasks.py` extension):

- Manifest with typed `endpoint_defined` (severity `error`) and incomplete generated code → `missing_components` contains the criterion description; `ValidationResult.checks` includes the failed entry.
- Same manifest, severity `warning` → `missing_components` empty; check appears in evidence.
- Manifest with typed `endpoint_defined` for non-FastAPI artifact → `status: skipped`; not in `missing_components` regardless of severity.
- Manifest with `mechanical_acceptance: false` in config → all typed checks evaluate to skipped with `mechanical_acceptance_disabled`.
- Manifest with `command_acceptance_checks: false` → only `command_exit_zero` checks skip; static checks still evaluate.

Integration (`tests/integration/cycles/test_manifest_acceptance.py`, new):

- Run a focused build subtask end-to-end with seeded LLM responses: complete code passes typed checks; partial code fails with specific `missing_components`; self-eval second pass receives the failed-check descriptions in its follow-up prompt and produces a corrected output that passes.

---

## Stage M2 — Separated Manifest Authoring

Two PRs. Default-off behind `split_manifest_authoring: bool = false`. Default-flip is a small follow-up PR after metrics meet SIP §6.2.4 criteria — explicitly out of scope for this stage's first delivery.

### Phase M2.1 — `governance.plan_build` Handler

**Modified / new files:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `GovernancePlanBuildHandler` class. Body of `_produce_manifest` (`planning_tasks.py:432–620`) moves verbatim into `GovernancePlanBuildHandler.handle()`. The retry loop, prompt construction, role/task_type constraint logic, and YAML validation all transfer. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceAssessReadinessHandler.handle()` keeps its current path *only* when `split_manifest_authoring: false`. When the flag is true, it skips the inline `_produce_manifest` call and instead consumes the manifest produced by the upstream `governance.plan_build` step. |
| `src/squadops/cycles/task_plan.py` | Add `governance.plan_build` to `PLANNING_TASK_STEPS` immediately before `governance.assess_readiness`, gated on `split_manifest_authoring`. |
| Capability registry (where planning task types are registered) | Register `governance.plan_build`. |

**Backward compatibility (RC-19):** when `split_manifest_authoring: false`, `PLANNING_TASK_STEPS` and `assess_readiness` behavior are byte-identical to today. No new task is dispatched. This is the safe default for Revision 1 of this SIP.

**Config keys:**

| Key | Default |
|---|---|
| `split_manifest_authoring` | `false` |

**Tests:**

- Unit: `GovernancePlanBuildHandler` produces a `BuildTaskManifest` artifact with the same content shape as today's `_produce_manifest` for an identical seeded LLM response. (Baseline-equivalence test: same input, same output, different handler.)
- Unit: with `split_manifest_authoring: true`, `assess_readiness` does not call `_produce_manifest` (assert via spy/mock-call-count *paired* with output assertion that the manifest artifact carried forward is the upstream one).
- Integration: planning phase end-to-end with the flag on produces the same final approved manifest as the flag off, given identical seeded LLM responses for both manifest authoring and review.

### Phase M2.2 — Reviewer Logic, `manifest_review.yaml`, Revision Loop

**Modified files:**

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceAssessReadinessHandler.handle()` (under `split_manifest_authoring: true`) emits a `manifest_review.yaml` artifact with the SIP §6.2.2 schema. Reviewer prompt is structured against the manifest artifact. |
| `src/squadops/cycles/manifest_review.py` (new) | `ManifestReview` frozen dataclass + `from_yaml()` parser. Enforces the rule: `review_status: revision_requested` requires at least one structured concern with `target_task_index` or `prd_requirement` set. Pure prose revision requests are normalized to `approved_with_concerns` (the SIP §6.2.2 rule). |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `GovernancePlanBuildReviseHandler`. Re-runs manifest authoring with the structured concerns appended to the prompt. Triggered only when `review_status: revision_requested` and revision count < `max_planning_revisions`. |
| `src/squadops/cycles/task_plan.py` | Conditional `governance.plan_build_revise` step inserted after `assess_readiness` when revision is requested and the revision budget remains. After exhaustion, planning proceeds with the latest manifest; unresolved concerns are documented in `operator_notes`. |

**`ManifestReview` schema (matches SIP §6.2.2):**

```python
@dataclass(frozen=True)
class ManifestReview:
    version: int
    review_status: str       # approved | revision_requested | approved_with_concerns
    reviewer_confidence: str
    target_manifest_id: str
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

- Unit: `ManifestReview.from_yaml()` parses a fully-populated review; revision_requested without any structured concern returns `approved_with_concerns` and surfaces a normalization warning in evidence.
- Unit: `revision_instructions` prose is preserved when concerns also exist.
- Unit: `AcceptanceConcern.suggested_check` round-trips through `TypedCheck` parsing.
- Integration: a planning run where the reviewer requests revision with one structured `acceptance_concern` produces a revised manifest whose subtask matches `target_task_index` and now contains the suggested typed check.
- Integration: revision budget exhaustion proceeds to gate with the latest manifest and `operator_notes` populated; no infinite loop.

**Default-flip work (out of scope for this stage):** the flip from `split_manifest_authoring: false` to `true` is a separate small PR after the SIP §6.2.4 criteria are met across a tracking window. This plan does not commit to that PR's timing.

---

## Stage M3 — Manifest Delta Overlays

Three PRs. Default-on behind `manifest_overlays_enabled: bool = true` once shipped (zero overlays produced ⇒ working manifest equals original ⇒ no observable change vs today).

### Phase M3.1 — Overlay Schema and Pure Structural Applier

**New files:**

| File | Purpose |
|------|---------|
| `src/squadops/cycles/manifest_overlay.py` | `ManifestDelta` dataclass + sub-types per operation; `apply_overlays()` pure function; canonical-serialization hashing helper. |
| `tests/unit/cycles/test_manifest_overlay.py` | Per-operation applier tests, identity invariants, hash chain checks. |

**Operation types (SIP §6.3.2):**

| Op | Dataclass |
|---|---|
| `add_task` | `AddTaskOp(after_index: int, task: ManifestTask)` |
| `remove_task` | `RemoveTaskOp(task_index: int)` |
| `replace_task` | `ReplaceTaskOp(task_index: int, replacement: ManifestTask)` |
| `tighten_acceptance` | `TightenAcceptanceOp(task_index: int, add_criteria: list[str \| TypedCheck])` |
| `reorder` | `ReorderOp(new_order: list[int])` |

**Canonical hashing (SIP §6.3.6):** dedicated helper `canonical_manifest_hash(manifest: BuildTaskManifest) -> str`. Sorted keys, normalized whitespace, deterministic list ordering, SHA-256. Must round-trip stable across YAML re-saves; the round-trip test from M1.1 is the regression anchor.

**`apply_overlays(original, overlays) -> WorkingManifest`** (pure):

1. Verify `overlays[0].parent_manifest_hash == canonical_manifest_hash(original)`. Mismatch → `OverlayHashMismatch`.
2. Verify the chain: `overlays[i].parent_overlay_id == overlays[i-1].overlay_id` for `i ≥ 1`; first overlay has `parent_overlay_id = null`. Mismatch → `OverlayChainBroken`.
3. Verify `overlay_id` uniqueness across the chain. Collision → `OverlayIdCollision`.
4. Apply each overlay's operations in order. Per-op invariants (SIP §6.3.2):
   - `add_task`: new index strictly greater than current max across original + applied overlays; non-empty contract (≥1 expected_artifact OR ≥1 error-severity typed criterion); dependencies reference live or tombstoned existing indices.
   - `remove_task`: target exists and is not already tombstoned; tombstones it (`status: removed_by_overlay`); any dependent that is not also tombstoned in the same overlay is an error.
   - `replace_task`: target exists, has not been tombstoned; replacement preserves `task_index` and `task_type`; replacement criteria are at least as strict (no removed criteria, no severity downgrades).
   - `tighten_acceptance`: append-only; existing criteria preserved unchanged; severity may rise (`warning → error`) but not fall.
   - `reorder`: target indices form a permutation of not-yet-tombstoned tasks; `depends_on` constraints satisfied by the new order.
5. Returns a `WorkingManifest` with the original task list plus tombstones plus added tasks, and a derived execution order honoring `after_index` and `depends_on`.

**`WorkingManifest`:** identical task identity (indices, deterministic IDs) for original and pass-through tasks; tombstoned tasks remain queryable by index/ID; added tasks carry their (overlay-assigned) indices.

**Loosening explicitly unsupported.** No operation type permits removing or weakening criteria. Severity downgrade in `replace_task` or `tighten_acceptance` raises `OverlayLoosensAcceptance`.

**Tests:**

Per-operation:

- `add_task`: index monotonicity enforced; empty-contract addition rejected; dependency on a tombstoned-but-artifacts-still-present task allowed; dependency on a non-existent index rejected.
- `remove_task`: tombstones target; live dependent without same-overlay tombstoning rejected.
- `replace_task`: index/task_type immutability enforced; criteria-loosening rejected; severity-downgrade rejected.
- `tighten_acceptance`: append-only enforced; severity-raise allowed; severity-downgrade rejected.
- `reorder`: dependency-violating order rejected.

Chain and hash:

- Mismatched `parent_manifest_hash` raises `OverlayHashMismatch`.
- Broken chain (gap in `parent_overlay_id`) raises `OverlayChainBroken`.
- Duplicate `overlay_id` in chain raises `OverlayIdCollision`.
- Canonical hash stable across YAML re-save (round-trip from M1.1 extended over the manifest as a whole).

Identity:

- `task-{run}-m{idx}` IDs for original tasks unchanged after any number of overlays.
- Added task IDs deterministic from `(run_id, new_index, task_type)` and unique.

Loosening:

- Any operation that would drop or weaken a criterion raises `OverlayLoosensAcceptance` regardless of who produced it.

### Phase M3.2 — Execution-Aware Validator, Loader Integration, Provenance

**Modified / new files:**

| File | Change |
|------|--------|
| `src/squadops/cycles/manifest_overlay.py` | `validate_overlay_for_run(overlay, working_manifest, run_state) -> list[ValidationError]` (SIP §6.3.4). |
| `src/squadops/cycles/task_plan.py` | Update `_replace_build_steps_with_manifest` (`task_plan.py:341`) — and a renamed `_load_manifest_for_run` helper if absent — to load original manifest + overlays and apply them: `working = apply_overlays(load_original(run), load_overlays_for_run(run))`. Existing materialization runs against `working`. |
| `src/squadops/api/routes/cycles/runs.py` | Extend forwarding path that today carries `control_manifest` artifacts (`af306d3`, `075fd9e`) to also carry every `control_manifest_delta` for the run, ordered by `parent_overlay_id` chain. |
| `src/squadops/cycles/task_plan.py` | When materializing an envelope from an overlay-added task, populate metadata: `overlay_id`, `overlay_operation_index`, `overlay_reason`, `correction_decision_id` (when produced by correction protocol). |
| Persistence layer (cycle registry / artifact store) | Recognize `artifact_type: "control_manifest_delta"` (extend `ArtifactType` enum). |

**Execution-aware validator rejection rules (SIP §6.3.4):**

- `remove_task` targeting a started/completed task → reject (`overlay_removes_started_task`).
- `replace_task` targeting a started/completed task → reject (`overlay_replaces_started_task`).
- `reorder` involving any started task → reject in Revision 1 (`overlay_reorders_started_task`).
- `add_task` whose dependencies include a tombstoned task whose required artifacts are not produced → reject (`overlay_depends_on_tombstoned_without_artifacts`).

`apply_overlays(original, overlays)` must succeed *and* `validate_overlay_for_run` must return empty before an overlay is forwarded to the executor. Either failure → reject, log structured error, surface to operator (no overlay applied to the run state).

**Config keys:**

| Key | Default |
|---|---|
| `manifest_overlays_enabled` | `true` |
| `max_manifest_overlays` | `5` (selftest profile: `2`) |

**Tests:**

Unit (`validate_overlay_for_run`):

- Each rejection rule fires for the matching `(operation, run_state)` pair (parametrized).
- Safe overlay (`add_task` only, dependencies satisfied) returns empty list.
- `tighten_acceptance` on a not-yet-started task → safe.
- `tighten_acceptance` on an in-flight task — explicit decision: rejected in Revision 1 to match completed-work immutability spirit even though it's append-only on criteria. (Encoded as a separate test with the chosen behavior; revisit only after operator feedback.)

Integration (`tests/integration/cycles/test_manifest_overlay_loader.py`, new):

- 0 overlays: working manifest equals original (regression guard for default-on rollout).
- 1 overlay (`add_task`): loader produces working manifest with the new task; materialized envelope carries provenance metadata fields (assert exact field values, not just presence).
- N overlays in chain: ordering is `parent_overlay_id`-chain regardless of `created_at` (RC-13 / SIP §6.3.6).
- Hash mismatch on first overlay → loader logs and falls back to original manifest; correction may not produce further overlays this run.

### Phase M3.3 — Correction-Protocol Integration (Restricted Producer)

**Modified files:**

| File | Change |
|------|--------|
| `governance.correction_decision` handler (location TBD per current handler layout) | Add `decision: overlay` branch. Producer constructs `manifest_delta.yaml` containing only `add_task` and/or `tighten_acceptance` operations (RC-16). Any other operation produced here is a programming error and is rejected by `validate_overlay_for_run` regardless. |
| Same handler | Bound by `max_manifest_overlays`; on exhaustion, falls back to `decision: patch` or `decision: escalate`. |
| Same handler | Populates `correction_decision_id` linking the overlay back to the correction event. |

**Producer construction rule:** the LLM is prompted to choose between `patch`, `overlay (add_task)`, `overlay (tighten_acceptance)`, and `escalate`. The handler enforces the operation restriction in code; even if the LLM emits a different op, it is dropped before the overlay is persisted, with a structured warning.

**Tests:**

Unit (correction handler):

- Seeded `SEMANTIC_FAILURE` warranting an additional task → handler emits `decision: overlay` with one `add_task`; overlay parses; `correction_decision_id` populated.
- Seeded failure warranting tightened criteria → handler emits `decision: overlay` with one `tighten_acceptance`.
- Seeded failure where LLM proposes `remove_task` → handler drops the op, emits structured warning, falls back to `decision: patch`. (Test asserts both the warning emission and the fallback decision.)
- `max_manifest_overlays` exhausted → handler does not emit overlay; falls back to patch or escalate.

End-to-end (`tests/integration/cycles/test_overlay_correction_loop.py`, new):

- Long-cycle group_run with seeded responses reproducing SIP §7's example: subtask 6 fails `regex_match count_min: 5`; correction protocol fires; overlay produced (one `add_task` + one `tighten_acceptance`); execution-aware validator approves; `_load_manifest_for_run` produces the expected working manifest on next executor pass; subtask 9 runs with `overlay_id`/`correction_decision_id`/`overlay_reason` metadata; closeout artifact references original + overlay + working.
- Same scenario but the overlay would target subtask 1 (already completed) for `remove_task` — execution-aware validator rejects; correction falls back to patch.

---

## Profile Config Examples

Verbatim from SIP §6.4 (build / implementation / selftest). Land alongside Stage M3 PR 3.2 since it activates `manifest_overlays_enabled` and `max_manifest_overlays`.

```yaml
# build profile (Rev 1 defaults — M1 on, M2 off, M3 on)
defaults:
  build_manifest: true
  output_validation: true
  max_self_eval_passes: 1
  mechanical_acceptance: true
  command_acceptance_checks: true
  manifest_overlays_enabled: true
  max_manifest_overlays: 5
  split_manifest_authoring: false

# implementation profile (long-cycle — all on, deeper)
defaults:
  build_manifest: true
  output_validation: true
  max_self_eval_passes: 2
  mechanical_acceptance: true
  command_acceptance_checks: true
  manifest_overlays_enabled: true
  max_manifest_overlays: 8
  split_manifest_authoring: true
  max_correction_attempts: 3

# selftest profile (smoke — minimal mechanical surface)
defaults:
  mechanical_acceptance: true
  command_acceptance_checks: false
  manifest_overlays_enabled: true
  max_manifest_overlays: 2
```

---

## Out of Scope (Plan-Level)

These are explicitly NOT in this plan. Each is either named in SIP §5/§11 or a deliberate scope cut for review legibility.

- Sandbox app execution (smoke pack — separate SIP).
- UI/browser verification.
- Cross-handler "did the test exercise the code" checks (SIP-0086 §10 future work).
- Default flip of `split_manifest_authoring` (separate small PR after SIP §6.2.4 criteria met).
- Operator-driven overlays via API (SIP §11 future work).
- `governance.replan` task type (SIP §11 future work — would be the producer for `remove_task`/`replace_task`/`reorder`).
- Adaptive thresholds learned from prior cycles.
- Universal framework parsing in `endpoint_defined` etc. — Flask, JS/TS, etc. land in separate scoped PRs.
- Loosen-acceptance via gate (SIP §11 future work — distinct from in-cycle correction overlays).

---

## Test Coverage Targets

Every test must catch a specific bug per `docs/TEST_QUALITY_STANDARD.md`. No tautological tests on dataclass fields.

| Layer | M1 | M2 | M3 |
|-------|----|----|----|
| Unit (parser / dataclasses) | ✅ | ✅ | ✅ |
| Unit (check eval / overlay applier / overlay validator) | ✅ | n/a | ✅ |
| Integration (handler) | ✅ | ✅ | ✅ |
| End-to-end cycle | ✅ | ✅ | ✅ |

**Self-check before committing tests:** re-read each test and delete any that only assert class attributes, only check `is not None`, or duplicate another test's coverage with different constants. Pair every mock-call-count assertion with an output/state assertion.

---

## Risks and Mitigations (Plan-Specific)

These are *plan-execution* risks — distinct from SIP §9 design risks.

| Risk | Mitigation |
|---|---|
| M1.2 evaluator framework grows to a universal AST library before any check ships | RC-12 stack-bounded `skipped` outcome ships in M1.2; new stacks land in scoped follow-up PRs only. |
| `command_exit_zero` slips its safelist by accepting "obvious" extensions in review | Safelist is operator-controlled config; extensions require an explicit PR touching `command_check_safelist` defaults, not a manifest-author or handler-author edit. |
| M3.1 hashing over canonical form drifts from M1.1 round-trip helper | M1.1 round-trip test extended in M3.1 to cover full-manifest hashing; same canonical helper used in both. |
| Producer emits unsupported op (M3.3) but execution-aware validator misses it | Defense in depth: producer-side restriction *and* validator rejection. M3.3 unit test seeds an unsupported-op LLM response and asserts both the producer-side drop and what would have been a validator reject. |
| Loader regression when `manifest_overlays_enabled: true` ships with zero overlays in the wild | M3.2 integration test "0 overlays → working == original" is a permanent regression guard. Run on every PR. |
| `split_manifest_authoring` flag stays default-off forever | SIP §6.2.4 criteria + this plan's explicit "default-flip is a follow-up PR" — call it out in retro after each long cycle so it doesn't drift. |

---

## References

- `sips/accepted/SIP-0092-Build-Manifest-Maturation-Mechanical.md` — design (this plan implements §6 and §8)
- `sips/implemented/SIP-0086-Build-Convergence-Loop-Dynamic.md` — parent SIP and its `RC-1..RC-8`
- `docs/plans/SIP-0086-build-convergence-loop-plan.md` — implementation plan style template
- `docs/plans/1-0-x-build-reliability-hardening-plan.md` — track-level plan that orders this SIP as #1
- `src/squadops/cycles/build_manifest.py` — extended by M1.1
- `src/squadops/cycles/task_plan.py:341` — extended by M3.2
- `src/squadops/capabilities/handlers/cycle_tasks.py:965` — replaced by M1.3 (FC3 → typed-check evaluation)
- `src/squadops/capabilities/handlers/planning_tasks.py:432` — `_produce_manifest`, source for the verbatim move in M2.1
- `src/squadops/api/routes/cycles/runs.py` — overlay forwarding extension in M3.2
- `adapters/capabilities/aci_executor.py` — sandbox executor used by `command_exit_zero`
- `docs/TEST_QUALITY_STANDARD.md` — bar every test in this plan must clear
