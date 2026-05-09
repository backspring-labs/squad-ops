# Plan: SIP-0093 Multi-Role Plan Authoring

## Context

SIP-0093 implements SIP-0092 M2 via shared brief → parallel domain proposals → governed merge. The full design lives in `sips/accepted/SIP-0093-Multi-Role-Plan-Authoring.md` (Rev 2, accepted 2026-05-05, tightened in PR #136 on 2026-05-08). This plan doc pins per-PR file changes, schemas, runtime contracts, and tests.

**SIP:** `sips/accepted/SIP-0093-Multi-Role-Plan-Authoring.md`
**Parent SIP:** `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` (M2 implementation path)
**Branch model:** Each PR lands on a feature branch off main; M1 substrate behavior is preserved under `multi_role_plan_authoring: false` at every PR.

The five PRs (per SIP-0093 §8):

- **PR 93.0** — `plan_authoring_brief.yaml` schema and `governance.prepare_plan_authoring_brief` handler. Plus the `PlanAuthoringService` extraction from `_produce_plan` (called by both the M1-substrate path and the SIP-0093 fallback path).
- **PR 93.1** — Proposal and merge schemas (`ProposedPlanTasks` extension, `PlanGuidance`, `MergeDecisions`); brief-conflict model; per-canonical-task provenance.
- **PR 93.2** — Role proposer handlers (`development.propose_plan_tasks`, `qa.propose_plan_tasks`, `strategy.propose_plan_guidance`); fan-out wiring; proposal failure handling.
- **PR 93.3** — `governance.merge_plan` handler with deterministic merge policy (SIP-0093 §5.8) and `merge_decisions.yaml` output.
- **PR 93.4** — Single-author fallback path; proposal completeness classification; gate package; observability metrics.

**What already shipped** (do not re-create):

- `src/squadops/cycles/proposed_role_tasks.py` — `ProposedRoleTasks` + `ProposedTask` dataclasses plus a `from_yaml()` parser. Landed in PR #125. **PR 93.1 extends this** rather than rewriting it.
- `src/squadops/capabilities/handlers/_plan_authoring.py` — fenced YAML extraction and retry-with-corrective-feedback helpers. Used by all SIP-0093 handlers.
- `governance.correction_decision` `structural_plan_change_candidate` diagnostic field. Landed in commit `9657449`. SIP-0093 leaves this handler intact.

---

## Routing under `multi_role_plan_authoring`

The flag is the single switch between two unambiguous routes through framing. There is no hybrid mode.

**`multi_role_plan_authoring: false`** (M1 substrate path):

```
data.research → strategy.frame → development.design_plan → qa.define_test_strategy
  → governance.review_plan
      → calls PlanAuthoringService.produce_plan(...) inline
      → emits canonical implementation_plan.yaml
  → [GATE]
```

No `plan_authoring_brief.yaml`. No proposers. No `merge_decisions.yaml`. The route is byte-identical to today, with the only change being that `_produce_plan` now lives inside `PlanAuthoringService` (PR 93.0 extraction). Proven by the verbatim-equivalence test below.

**`multi_role_plan_authoring: true`** (SIP-0093 path):

```
data.research → strategy.frame → development.design_plan → qa.define_test_strategy
  → governance.prepare_plan_authoring_brief        (emits plan_authoring_brief.yaml)
  → development.propose_plan_tasks  ┐
  → qa.propose_plan_tasks           ├─ Rev 1: sequential; Rev 2: parallel fan-out
  → strategy.propose_plan_guidance  ┘
  → governance.merge_plan
      → if any proposal succeeded: deterministic merge per SIP-0093 §5.8
      → if all proposals failed: PlanAuthoringService.produce_plan(...) (RC-26 fallback)
      → emits canonical implementation_plan.yaml + merge_decisions.yaml
  → governance.review_plan          (sign-off only)
  → [GATE]
```

`governance.review_plan` does not call `PlanAuthoringService` on this route — its body conditions on the flag and either authors (flag off) or signs off (flag on).

This routing is the load-bearing simplification SIP-0093 makes possible: one flag, two complete routes, no hybrid behavior. Tests in PR 93.0 and PR 93.4 assert that the wrong route never fires for a given flag value.

---

## Runtime Contracts

These extend SIP-0092's RC-9..RC-21. New contracts are RC-22 through RC-26.

**RC-22 (Brief authority and immutability):** The `plan_authoring_brief.yaml` is authored once per cycle by `governance.prepare_plan_authoring_brief` and is immutable after emission. Proposers and the merger consume the brief as untrusted-input-shaped read-only context. The merger may *escalate* a `severity: blocking` brief conflict (per SIP-0093 §5.5) to operator at gate; the merger may *not* edit the brief. A revised brief, if needed, requires a re-run of the framing tail (out of scope for Rev 1).

**RC-23 (Proposal-merger artifact flow):** Every `proposed_plan_tasks.yaml` and `plan_guidance.yaml` artifact MUST reference the brief by `source_brief_id`. The merger rejects any proposal whose `source_brief_id` does not match the upstream brief — that proposal is treated as a missing proposal (`proposal_completeness: partial`, role recorded in `missing_proposals`). This prevents stale proposals from a prior framing attempt from contaminating a re-run.

**RC-24 (Merger-only task indices):** Proposers MUST NOT emit final numeric `task_index` values. Cross-proposal task references use `depends_on_focus` keys of the form `{role}:{focus}` per `proposed_role_tasks.focus_key()` (or symbolic dependency tags per SIP-0093 §5.4.3 — the existing implementation chose `{role}:{focus}` and Rev 1 adopts that). The proposal parser rejects integer values in `depends_on_focus`. The merger resolves these keys to numeric `depends_on` indices in the canonical `implementation_plan.yaml`.

**RC-25 (`merge_decisions.yaml` audit completeness):** Every canonical task in `implementation_plan.yaml` MUST appear in `merge_decisions.yaml` with `task_index`, `source_proposal_task_keys`, `proposed_by`, and `merge_action ∈ {accepted, merged, modified, gap_filled}`. Tasks created by the merger to fill gaps (no proposal source) are marked `merge_action: gap_filled`. Test: full canonical-plan / merge-decisions correspondence asserted in PR 93.3.

**RC-26 (Fallback marker authority):** When `multi_role_plan_authoring: true` and all role proposals fail, `merge_decisions.yaml` MUST set `authoring_mode: fallback_single_author` AND `proposal_completeness: fallback`. The canonical plan is produced by the shared `PlanAuthoringService.produce_plan(...)`. The system MUST NOT silently mark a fallback as `multi_role`; tests assert this property explicitly. Fallback frequency is a tracked gate metric (M2→M3 gate criterion C2).

**RC-27 (Canonical plan is the sole executor input):** The build executor consumes only the canonical `implementation_plan.yaml`. `plan_authoring_brief.yaml`, `proposed_plan_tasks.yaml`, `plan_guidance.yaml`, and `merge_decisions.yaml` are planning/gate evidence artifacts only — they MUST NOT be required by build execution after gate approval. This preserves the SIP-0086/SIP-0092 execution boundary: multi-role authoring changes plan *production*, not task *execution* semantics. The forwarding layer (`api/routes/cycles/runs.py`) only adds these new artifact types as gate evidence; existing `control_implementation_plan` forwarding to the build workload is unchanged.

**RC-28 (M3 independence from SIP-0093 internals):** When SIP-0092 Capability M3 (Plan Changes) ships, plan changes operate on the canonical `implementation_plan.yaml` regardless of whether that plan was produced by colocated authoring (M1 substrate), single-author fallback, or SIP-0093 multi-role merge. M3 MUST NOT couple to `merge_decisions.yaml`, per-role proposal artifacts, or proposal provenance. SIP-0093 changes the *origin* of the plan; M3 governs how it *evolves*. The two are orthogonal by construction.

---

## PR 93.0 — Brief schema, handler, and `PlanAuthoringService` extraction

**Why this PR exists first:** lets the brief flow be validated end-to-end before scaling proposer parallelism. Also extracts the M1-substrate's `_produce_plan` body into a shared service so the SIP-0093 fallback path (PR 93.4) and the existing M1 path use one implementation. No proposer code yet — this PR is foundational.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/cycles/plan_authoring_brief.py` (new) | `PlanAuthoringBrief` frozen dataclass + `from_yaml()` parser. Required Rev 1 fields: `version`, `brief_id`, `objective_summary`, `accepted_stack`, `must_cover_requirements`, `scope_cuts`, `risk_areas`. Optional fields preserved as-parsed but not validated beyond YAML well-formedness. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `GovernancePreparePlanAuthoringBriefHandler` (`governance.prepare_plan_authoring_brief`) — reads framing artifacts from `prior_outputs`, prompts the lead for a brief, parses with `PlanAuthoringBrief.from_yaml()`, returns the brief as primary output. Uses `_plan_authoring.retry_yaml_call` for the LLM loop. |
| `src/squadops/capabilities/handlers/_plan_authoring_service.py` (new) | **`PlanAuthoringService`**: extracts the body of `_produce_plan` from `planning_tasks.py:432–620` into a function-style service with one entry point — `produce_plan(prompt_inputs, llm_client, run_state) -> ImplementationPlan`. The retry loop, prompt construction, role/task_type constraint logic, and YAML validation move here intact. Both legacy (M1 substrate) and SIP-0093 fallback paths call this service. NO duplicated logic. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceReviewPlanHandler.handle()` calls `PlanAuthoringService.produce_plan(...)` when `multi_role_plan_authoring: false` (replacing the inline `_produce_plan` invocation). When `multi_role_plan_authoring: true`, this handler does NOT call the service — it consumes the canonical plan produced by upstream `governance.merge_plan` (wired in PR 93.3). |
| `src/squadops/cycles/task_plan.py` | Add `governance.prepare_plan_authoring_brief` to `PLANNING_TASK_STEPS` immediately after `qa.define_test_strategy`, gated on `multi_role_plan_authoring`. When the flag is false, the brief step is skipped. |
| Capability registry (where planning task types are registered) | Register `governance.prepare_plan_authoring_brief`. |
| `src/squadops/contracts/cycle_request_profiles/profiles/framing.yaml` | Conditional inclusion of the brief step when the resolved profile has `multi_role_plan_authoring: true`. |

**Why a service, not a verbatim move:** verbatim move would leave the M1 path with a near-duplicate of the new code, guaranteed to drift on the next prompt or retry-loop tweak. Extracting first means both paths share one implementation; the only difference is *which handler invokes it* and *whether the resulting plan is the `review_plan` primary output or the fallback path's*.

**Backward compatibility (RC-19):** when `multi_role_plan_authoring: false`, the M1 path calls `PlanAuthoringService.produce_plan(...)` with the same `prompt_inputs` as today's `_produce_plan` invocation, producing a byte-identical plan given identical seeded LLM responses. The verbatim-equivalence test below is the regression anchor.

### `PlanAuthoringBrief` schema (Rev 1)

```python
@dataclass(frozen=True)
class PlanAuthoringBrief:
    version: int
    brief_id: str
    objective_summary: str
    accepted_stack: dict[str, str]                     # e.g., {"language": "python", "framework": "fastapi"}
    must_cover_requirements: list[str]
    scope_cuts: list[str]
    risk_areas: list[str]
    # Optional Rev 1 fields (parsed if present, no validation beyond YAML shape):
    source_artifact_refs: list[str] = field(default_factory=list)
    major_components: list[str] = field(default_factory=list)
    dependency_assumptions: list[str] = field(default_factory=list)
    time_budget_guidance: dict[str, Any] = field(default_factory=dict)
    task_granularity_guidance: str = ""
    artifact_naming_conventions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
```

`brief_id` is a UUID generated at handler entry; the merger and proposers use it for `source_brief_id` matching (RC-23).

### Config keys

| Key | Default | Notes |
|---|---|---|
| `multi_role_plan_authoring` | `false` | Master switch. |
| `plan_authoring_contributors` | `["development", "qa", "strategy"]` | Parsed and validated in PR 93.0 even though no proposers consume it yet. |

### Tests

- Unit (`tests/unit/cycles/test_plan_authoring_brief.py`, new):
  - Required fields enforced; missing field raises `ValueError` with the field name in the message.
  - Optional fields default to empty when absent; populated fields parse round-trip.
  - Malformed YAML at top level raises `ValueError`.
  - Edge case: brief with `must_cover_requirements: []` parses but a downstream consumer-level test asserts the merger surfaces a warning operator-note.
- Unit (`tests/unit/capabilities/test_plan_authoring_service.py`, new):
  - `PlanAuthoringService.produce_plan(...)` produces the same `ImplementationPlan` as `_produce_plan` for an identical seeded LLM response (verbatim-equivalence regression anchor).
  - Service surfaces parse failures the same way `_produce_plan` did (no wording regression).
  - **M1-substrate side-effect-absence assertion** (added per Rev 2 review): when `multi_role_plan_authoring: false` and `GovernanceReviewPlanHandler.handle()` runs end-to-end through `PlanAuthoringService`, the run produces *no* `plan_authoring_brief.yaml`, *no* `proposed_plan_tasks.yaml`, *no* `plan_guidance.yaml`, and *no* `merge_decisions.yaml` artifacts. Hybrid behavior would silently leak SIP-0093 artifacts into the M1 path; this test pins the route boundary defined in §"Routing under `multi_role_plan_authoring`".
- Unit (`tests/unit/capabilities/test_prepare_plan_authoring_brief.py`, new):
  - Handler produces a `PlanAuthoringBrief` artifact for a seeded LLM response.
  - Handler emits a structured failure when the LLM response cannot be parsed after `retry_yaml_call` exhaustion.
- Integration (`tests/integration/cycles/test_brief_handler.py`, new):
  - Framing phase end-to-end with `multi_role_plan_authoring: true` produces a brief artifact AND an unchanged `governance.review_plan` plan output (since proposers don't exist yet, this PR keeps the legacy path active even with the flag on — the brief step is decorative until PR 93.2 wires proposers).
  - With `multi_role_plan_authoring: false`, the brief step is skipped and the cycle output is byte-identical to today's.

---

## PR 93.1 — Proposal and merge schemas

Pure schema work. No new handlers; no behavior change. Lets PR 93.2 and 93.3 layer on a stable schema surface.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/cycles/proposed_role_tasks.py` (extend) | Add required field `source_brief_id: str` to `ProposedRoleTasks`. Add `proposal_id: str`, `scope_statement: str`, `brief_conflicts: list[BriefConflict]` (default empty). Optional Rev 1 recommended fields: `source_artifact_refs`, `assumptions`, `risks`, `gaps_not_covered`, `confidence`. Update `from_yaml()` to enforce the new required fields and reject integer entries in `depends_on_focus` (RC-24). |
| `src/squadops/cycles/proposed_role_tasks.py` (extend) | New `BriefConflict` frozen dataclass with fields: `brief_field: str`, `proposed_change: str`, `reason: str`, `severity: Literal["warning", "blocking"]`, `affected_proposal_task_keys: list[str]`. Parse rejects unknown severity. |
| `src/squadops/cycles/plan_guidance.py` (new) | `PlanGuidance` frozen dataclass + `from_yaml()`. Fields: `version`, `guidance_id`, `source_brief_id`, `proposing_role: Literal["strategy"]`, `priority_guidance`, `ordering_guidance`, `risk_guidance`, `time_budget_guidance`, `scope_cut_guidance`, `must_not_skip`, `defer_if_time_constrained`, `confidence`. Required: `version`, `guidance_id`, `source_brief_id`, `proposing_role`. Rest optional. |
| `src/squadops/cycles/merge_decisions.py` (new) | `MergeDecisions` frozen dataclass + `from_yaml()`. Required Rev 1 fields: `version`, `target_plan_id`, `brief_id`, `proposal_ids`, `guidance_ids`, `authoring_mode: Literal["multi_role", "fallback_single_author"]`, `proposal_completeness: Literal["complete", "partial", "fallback"]`, `missing_proposals: list[str]`, `canonical_tasks: list[CanonicalTaskProvenance]`, `brief_conflicts_disposition: list[BriefConflictDisposition]`, `operator_notes: str`. |
| `src/squadops/cycles/merge_decisions.py` (new) | `CanonicalTaskProvenance` frozen dataclass: `task_index: int`, `source_proposal_task_keys: list[str]`, `proposed_by: list[str]`, `merge_action: Literal["accepted", "merged", "modified", "gap_filled"]`, `reason: str`. |
| `src/squadops/cycles/merge_decisions.py` (new) | `BriefConflictDisposition` frozen dataclass: `brief_field: str`, `severity: Literal["warning", "blocking"]`, `disposition: Literal["accepted", "rejected", "escalated_to_operator"]`, `reason: str`. |

### Schema invariants enforced by parsers

- `ProposedRoleTasks.from_yaml()` rejects integer `depends_on_focus` entries (RC-24). Existing `focus_key()` collision check is preserved.
- `PlanGuidance.from_yaml()` rejects `proposing_role != "strategy"` since strategy is the only Rev 1 contributor of guidance.
- `MergeDecisions.from_yaml()` enforces: every `canonical_tasks[i].task_index` is unique and contiguous starting at 0; `proposal_completeness == "fallback"` requires `authoring_mode == "fallback_single_author"` (RC-26 link).

### Config keys

No new keys in this PR.

### Tests

- Unit (`tests/unit/cycles/test_proposed_role_tasks_v2.py`, extends existing test file):
  - New required fields enforced with `ValueError` when missing.
  - `depends_on_focus` integer entry rejected; string entry parses; unknown collision rule enforced.
  - `BriefConflict` parses warning + blocking severities; unknown severity raises.
- Unit (`tests/unit/cycles/test_plan_guidance.py`, new):
  - Required fields enforced.
  - `proposing_role: development` rejected.
  - Optional fields default to empty when absent.
- Unit (`tests/unit/cycles/test_merge_decisions.py`, new):
  - Required fields enforced.
  - `proposal_completeness: fallback` with `authoring_mode: multi_role` rejected (the RC-26 invariant).
  - Non-contiguous `task_index` rejected.
  - Duplicate `task_index` rejected.
  - `BriefConflictDisposition` parses each disposition value; unknown rejected.

---

## PR 93.2 — Role proposer handlers and fan-out wiring

Adds the three role proposers and wires them into the framing sequence after the brief.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `DevelopmentProposePlanTasksHandler` (`development.propose_plan_tasks`). Reads brief + framing artifacts; prompts dev for domain-scoped task proposals; parses with `ProposedRoleTasks.from_yaml()`; returns proposal as primary output. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `QaProposePlanTasksHandler` (`qa.propose_plan_tasks`). Same shape, qa-scoped prompt. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `StrategyProposePlanGuidanceHandler` (`strategy.propose_plan_guidance`). Reads brief + framing artifacts; produces `plan_guidance.yaml`. |
| `src/squadops/cycles/task_plan.py` | Insert proposer steps into `PLANNING_TASK_STEPS` between `governance.prepare_plan_authoring_brief` and `governance.review_plan` when `multi_role_plan_authoring: true`. **Rev 1 ships sequential, not parallel** — see Risks section. |
| Capability registry | Register the three new task types. |

### Sequencing decision: Rev 1 ships sequential proposers

SIP-0093 §5.11 specifies parallel fan-out. The current executor (`task_plan.py`) walks `PLANNING_TASK_STEPS` sequentially with no parallel-group construct. Adding parallelism requires:

- Extending step-list shape to `list[tuple[str, str] | list[tuple[str, str]]]` and updating every consumer in `task_plan.py` and `planning_tasks.py`, OR
- A new "fan-out group" marker the dispatcher recognizes.

Both are non-trivial executor changes that broaden Rev 1's blast radius. **Rev 1 ships sequential.** Cost impact: framing tail extends from ~5–9 min (parallel target per SIP-0093 §6) to ~12–17 min (sequential). Still fits the validation profile's ≥2h cycle budget. Parallel fan-out becomes a Rev 2 follow-up after the propose-merge architecture has shown stability.

The plan doc surfaces this trade-off explicitly so future-us doesn't think parallelism was forgotten.

### Failure handling per RC-23

When a proposer fails (LLM error, timeout, malformed YAML after `retry_yaml_call` exhaustion, mismatched `source_brief_id`), the handler emits a structured failure record into the cycle artifact stream — not an exception that kills the cycle. The merger (PR 93.3) reads these failure records as "this role's proposal is missing" and proceeds.

### Config keys

`plan_authoring_contributors` (already validated in PR 93.0) is consumed here. Omitting `qa` from the contributors list skips the qa proposer step at sequence-build time. Adding `build` is a Rev 2 extension (SIP-0093 §5.12); Rev 1 raises a config validation error if `build` is in the contributors list.

### Tests

- Unit (`tests/unit/capabilities/test_propose_plan_tasks.py`, new):
  - Each of the three handlers produces its expected artifact for a seeded LLM response.
  - Each handler emits a structured failure (not an exception) when `retry_yaml_call` exhausts.
  - Each proposer's parsed output has `source_brief_id` matching the upstream brief; mismatch raises (failure record).
- Integration (`tests/integration/cycles/test_proposer_fanout.py`, new):
  - Framing phase end-to-end with `multi_role_plan_authoring: true` produces brief + 3 proposals + (still) the M1 substrate plan from `governance.review_plan` since the merger doesn't exist yet. This PR is foundational for PR 93.3.
  - With one proposer's LLM seeded to fail, the cycle continues; the failed proposer's artifact is absent; remaining proposals exist.
  - With `plan_authoring_contributors: ["development", "qa"]`, no strategy guidance is produced; cycle continues.

---

## PR 93.3 — `governance.merge_plan` handler with deterministic merge policy

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `GovernanceMergePlanHandler` (`governance.merge_plan`). Reads brief + all proposal artifacts + guidance artifact + proposer-failure records from `prior_outputs`. Prompts the lead for a merge decision following the deterministic policy below. Emits canonical `implementation_plan.yaml` AND `merge_decisions.yaml`. |
| `src/squadops/cycles/task_plan.py` | Insert `governance.merge_plan` after the proposer steps. `governance.review_plan` becomes sign-off only when the flag is on. |
| Capability registry | Register `governance.merge_plan`. |

### Deterministic merge policy (per SIP-0093 §5.8)

The merger applies these rules in order:

1. **Resolve brief conflicts.** Each `BriefConflict` from the proposers gets a `BriefConflictDisposition`. `severity: warning` → merger arbitrates (`accepted`/`rejected`). `severity: blocking` → `escalated_to_operator` automatic; canonical plan still emits.
2. **Domain-owner wins for task ownership.** Dev tasks: development. QA tasks: qa. Strategy never owns tasks.
3. **Deduplicate** — overlapping tasks across role proposals (Neo proposes "tests for endpoints"; Eve proposes the same → Eve wins because qa-domain).
4. **Merge compatible acceptance criteria** — dev and qa criteria can both survive on the same canonical task when they test different surfaces. Strictest-compatible-wins for criteria on a strictness ordering (e.g., `count_min` higher wins).
5. **Resolve dependency edges.** Convert `depends_on_focus` keys (`{role}:{focus}`) to numeric `depends_on` indices in the canonical plan. Unresolved keys (referencing a task no proposer produced) become `gap_fills` candidates per rule 7.
6. **Apply strategy guidance.** Ordering, priority, time-budget, risk callouts. Guidance affects ordering and priority hints, never task content or ownership.
7. **Fill gaps.** If qa references a dev component dev didn't propose, the merger may add the missing component (`merge_action: gap_filled`) or escalate via operator notes.
8. **Assign final task indices** producing the canonical 0..N sequence.
9. **Emit `merge_decisions.yaml`** with per-canonical-task provenance and brief-conflict dispositions.

### Worked-example test (the central regression anchor)

Per SIP-0093 §5.8 worked example: Neo proposes `dev.api.join` with `endpoint_defined`; Eve proposes `qa.backend.join_tests` with `regex_match` + `depends_on_focus: ["development:api join"]`. Merger emits two canonical tasks with the qa task's numeric `depends_on` resolved correctly. This test is mandatory; it's the deterministic-merge regression anchor.

### The single most important integration test

Per SIP-0093 §10: **"Eve proposes a QA task Neo omitted; merged plan includes it."** The seeded scenario: brief lists "duplicate-join 409 handling" in `must_cover_requirements`; Neo's proposal omits a corresponding qa task; Eve's proposal includes one. Assertion: the merged canonical plan contains the qa task. If this can't be reproduced, SIP-0093 isn't done. Lives in `tests/integration/cycles/test_merge_plan.py`.

### Config keys

No new keys.

### Tests

- Unit (`tests/unit/capabilities/test_merge_plan_handler.py`, new):
  - Worked-example test (above).
  - Brief conflict warning → merger records arbitration in `merge_decisions.yaml` `BriefConflictDisposition`.
  - Brief conflict blocking → merger records `escalated_to_operator`; canonical plan still emits.
  - Strict-compatible-wins acceptance criterion merging.
  - Dependency resolution: known `{role}:{focus}` keys resolve to indices; unknown keys flow into gap-fill candidates.
  - All-canonical-tasks-have-provenance invariant (RC-25).
- Integration (`tests/integration/cycles/test_merge_plan.py`, new):
  - **The Eve-proposes-omitted-qa-task test.** Required gate criterion.
  - Full framing-phase end-to-end with merger: brief → 3 proposals → merger → `governance.review_plan` sign-off. Canonical plan validates against `ImplementationPlan` schema.
  - Merger receives missing strategy proposal: cycle continues; `proposal_completeness: partial`; missing strategy guidance recorded as warning operator-note.

---

## PR 93.4 — Fallback, gate integration, observability

Closes the loop: all-proposals-failed fallback, completeness classification surfaced at gate, metrics for the M2→M3 gate criteria.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceMergePlanHandler.handle()` — when all proposals failed, call `PlanAuthoringService.produce_plan(...)` (extracted in PR 93.0). Set `authoring_mode: fallback_single_author` and `proposal_completeness: fallback` on the emitted `merge_decisions.yaml`. RC-26 invariant. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceReviewPlanHandler.handle()` (sign-off path under `multi_role_plan_authoring: true`) surfaces `merge_decisions.yaml` content into the planning artifact's evidence section so the operator sees brief, canonical plan, and merge decisions side-by-side at gate. |
| `src/squadops/api/routes/cycles/runs.py` | Gate-package extension — pass `plan_authoring_brief.yaml` and `merge_decisions.yaml` to the gate response alongside the canonical plan. |
| `src/squadops/telemetry/...` (new metric emissions) | Authoring duration (per role + total), proposal completeness counts (`complete`/`partial`/`fallback`), merge conflict counts (`brief_conflicts_disposition` rollup), fallback frequency. |

### Operator-visible artifacts at gate

Per SIP-0093 §4 (Non-Goals — operator visibility):

- **Primary** — `implementation_plan.yaml`, `plan_authoring_brief.yaml`, `merge_decisions.yaml`.
- **Intermediate evidence** — per-role `proposed_plan_tasks.yaml` and `plan_guidance.yaml` available for inspection but not surfaced as primary artifacts.
- **Fallback marker** — `authoring_mode: fallback_single_author` is visible at gate (operator must see when the cycle silently degraded to single-author).

### Metrics (M2→M3 gate criteria support)

The amended Gate M2→M3 criteria (per `docs/plans/SIP-0092-implementation-plan-improvement-plan.md`) need:

- **C1 — Multi-role contribution non-redundancy rate.** Computed from `merge_decisions.yaml` per-canonical-task `proposed_by`. A cycle counts toward the threshold when at least one canonical task has `proposed_by` containing a non-dev role and is not present in the dev proposal.
- **C2 — Sole-author fallback rate.** Computed from `authoring_mode: fallback_single_author` count over total cycles.
- **C3 — Structural-change candidate rate.** Already emitted by `governance.correction_decision` (commit `9657449`). No change here.
- **C4 — Plan-quality regression check.** Canonical-plan schema-validity rate; typed-acceptance evaluator-error rate. Existing M1 telemetry covers this.

### Config keys

No new keys.

### Tests

- Unit (`tests/unit/capabilities/test_merge_plan_fallback.py`, new):
  - All three proposers seeded to fail → merger calls `PlanAuthoringService.produce_plan(...)` → emits canonical plan AND `merge_decisions.yaml` with `authoring_mode: fallback_single_author` AND `proposal_completeness: fallback`.
  - RC-26 invariant: `authoring_mode: multi_role` with `proposal_completeness: fallback` is impossible (parser rejects; merger code asserts).
  - Two proposers fail, one succeeds → fallback NOT triggered; `proposal_completeness: partial`; surviving proposal is honored.
- Integration (`tests/integration/cycles/test_gate_package.py`, new):
  - Gate response includes brief + canonical plan + merge_decisions.
  - Cycle with full multi-role authoring → `authoring_mode: multi_role`, `proposal_completeness: complete`.
  - Cycle with one missing proposer → `proposal_completeness: partial`; missing role surfaced in `missing_proposals`.
  - Fallback cycle → operator sees `authoring_mode: fallback_single_author` in the gate package.
- Integration (`tests/integration/telemetry/test_plan_authoring_metrics.py`, new):
  - Authoring duration metrics emitted per role + total.
  - Proposal completeness counts emitted as separate counters.
  - Fallback frequency counter increments only on fallback cycles.

---

## Profile Config Examples

Mirrors SIP-0092 §6.4. Each PR's flag flips are deliberately small.

### After PR 93.0 lands (brief + service extraction; M1 path unchanged)

```yaml
# build profile — no behavior change
defaults:
  multi_role_plan_authoring: false          # M1 substrate behavior preserved
```

The brief handler exists and is wired but never runs at this stage. PR 93.0's gate is "M1 path is byte-identical to today" plus "brief handler works in isolation."

### After PR 93.4 lands (post-SIP-0093 ship; default-off)

```yaml
# build profile — short-cycle work, M1 substrate (cost analysis: SIP-0093 §6)
defaults:
  multi_role_plan_authoring: false

# validation profile — gate-cycle target with multi-role on
defaults:
  max_self_eval_passes: 2
  max_correction_attempts: 3
  multi_role_plan_authoring: true
  plan_authoring_contributors: ["development", "qa", "strategy"]

# selftest profile — smoke, M1 substrate (multi-role costs not justified for short cycles)
defaults:
  multi_role_plan_authoring: false
```

### Post-default-flip (separate small PR after stability criteria met)

```yaml
# build profile — multi-role on by default once stable
defaults:
  multi_role_plan_authoring: true
  plan_authoring_contributors: ["development", "qa", "strategy"]
```

The default flip is **out of scope for PR 93.4**. It is a separate small PR after the M2→M3 gate's stability criteria hold across a tracking window.

---

## Out of Scope (Plan-Level)

These are explicitly NOT in this plan. Each is named in SIP-0093 §12 (Future Work) or is a deliberate scope cut.

- **Parallel proposer fan-out.** Rev 1 ships sequential. Parallelism is a Rev 2 executor change.
- **Builder/Bob contributor (`build.propose_plan_tasks`).** SIP-0093 §5.12 explicit Rev 2 extension. Config validation rejects `build` in `plan_authoring_contributors` for Rev 1.
- **Per-role plan-change authoring at correction time.** SIP-0093 §12; depends on M3 shipping.
- **Proposer competition** (two proposers per role with different prompts).
- **Operator-visible per-role contribution surface in console UI.**
- **Adaptive proposer selection** based on telemetry.
- **Brief revision loop.** Rev 1 escalates blocking conflicts to operator; brief is immutable per RC-22.
- **Default flip of `multi_role_plan_authoring`.** Separate small PR after stability criteria met across a tracking window.

---

## Test Coverage Targets

Every test must catch a specific bug per `docs/TEST_QUALITY_STANDARD.md`. No tautological tests on dataclass fields.

| Layer | PR 93.0 | PR 93.1 | PR 93.2 | PR 93.3 | PR 93.4 |
|-------|---------|---------|---------|---------|---------|
| Unit (parser / dataclasses) | ✅ | ✅ | n/a | n/a | n/a |
| Unit (handler) | ✅ | n/a | ✅ | ✅ | ✅ |
| Integration (handler) | ✅ | n/a | ✅ | ✅ | ✅ |
| End-to-end cycle | n/a | n/a | ✅ | ✅ | ✅ |

**Self-check before committing tests:** re-read each test and delete any that only assert class attributes, only check `is not None`, or duplicate another test's coverage with different constants. Pair every mock-call-count assertion with an output/state assertion.

**Required gate criteria** (cannot ship SIP-0093 without these passing):

- Verbatim-equivalence test: M1 path through `PlanAuthoringService` produces byte-identical plans for identical seeded LLM responses (PR 93.0).
- Worked-example test: SIP-0093 §5.8 deterministic merge example (PR 93.3).
- "Eve proposes a QA task Neo omitted; merged plan includes it" (PR 93.3).
- Fallback path test: all-proposers-failed → `authoring_mode: fallback_single_author` (PR 93.4).
- RC-26 invariant test: `authoring_mode: multi_role` with `proposal_completeness: fallback` cannot occur (PR 93.4).

---

## Risks and Mitigations (Plan-Specific)

These are *plan-execution* risks — distinct from SIP-0093 §6 cost analysis and SIP-0092 §9 design risks.

| Risk | Mitigation |
|---|---|
| Parallel fan-out shipped accidentally before executor support exists | Rev 1 ships sequential. The plan doc explicitly notes this and SIP-0093 §6 cost analysis is recomputed in this plan doc with sequential numbers (~12–17 min framing tail). |
| `PlanAuthoringService` extraction in PR 93.0 introduces a regression in the M1 path | Verbatim-equivalence test on every PR (regression anchor). The service is a function-style module, not a class — minimizes refactoring surface. |
| Existing `proposed_role_tasks.py` shipped in PR #125 drifts from SIP-0093 Rev 2 vocabulary | PR 93.1 extends, doesn't rewrite. The `{role}:{focus}` dependency convention is grandfathered as the Rev 1 implementation form (RC-24); SIP-0093 §5.4.3's `dev.api.routes` shape was illustrative. |
| Merger LLM choreography drifts from the deterministic merge policy | Worked-example test from SIP-0093 §5.8 is a regression anchor. Merger prompt is structured around the policy steps explicitly. |
| Fallback path silently masquerades as multi-role authoring | RC-26 invariant + parser-level rejection of `multi_role` + `fallback` combination. Test asserts the impossibility. |
| Brief becomes "the plan" in practice (proposers rubber-stamp) | M2→M3 gate criterion C1 measures non-redundancy directly. If C1 fails after SIP-0093 ships, the brief prompt or proposer prompts are wrong, not the architecture. |
| `multi_role_plan_authoring` flag stays default-off forever | M2→M3 gate criteria measure SIP-0093 directly; default-flip is a follow-up PR after stability criteria hold across a tracking window. Call it out in retro after each long cycle so it doesn't drift. |
| Sequencing change to `PLANNING_TASK_STEPS` breaks downstream consumers | PR 93.0's `task_plan.py` change is gated by `multi_role_plan_authoring: false` default. Existing tests on the M1 path keep running unchanged. |

---

## Terminology Lock additions (PR Checklist)

Extends the SIP-0092 plan doc Terminology Lock. The SIP-0093 canonical terms (already added to SIP-0092 plan doc Terminology Lock in PR #136) are reproduced here for PR-time reference:

**Banned in new code** (allowed only in historical comments or migration tests):

- `split_implementation_planning`, `development.plan_implementation`, `development.plan_implementation_revise`, `plan_review.yaml`, `PlanReview`, `max_planning_revisions`, `review_status: revision_requested`, `revision_instructions`.

**Canonical terms:**

| Concept | Canonical term |
|---|---|
| Brief artifact | `plan_authoring_brief.yaml`, `PlanAuthoringBrief` |
| Brief handler | `GovernancePreparePlanAuthoringBriefHandler` (`governance.prepare_plan_authoring_brief`) |
| Role proposal artifact | `proposed_plan_tasks.yaml`, `ProposedRoleTasks`, `ProposedTask` |
| Strategy guidance artifact | `plan_guidance.yaml`, `PlanGuidance` |
| Per-role proposer task types | `development.propose_plan_tasks`, `qa.propose_plan_tasks`, `strategy.propose_plan_guidance` |
| Merger handler | `GovernanceMergePlanHandler` (`governance.merge_plan`) |
| Merge audit artifact | `merge_decisions.yaml`, `MergeDecisions` |
| Per-canonical-task provenance | `CanonicalTaskProvenance` |
| Brief-conflict disposition | `BriefConflictDisposition` |
| M2 master flag | `multi_role_plan_authoring` |
| M2 contributors flag | `plan_authoring_contributors` |

**Implementation:** the SIP-0092 plan doc's terminology-lock test (or PR-template checkbox) extends to cover SIP-0093 terms.

---

## References

- `sips/accepted/SIP-0093-Multi-Role-Plan-Authoring.md` — design (this plan implements §5 and §8)
- `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` — parent SIP; SIP-0093 implements its §6.2 (Capability M2)
- `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` — Stage M2 cross-references this plan; Gate M2→M3 criteria measure SIP-0093 behavior directly
- `docs/plans/SIP-0092-gate-M1-evaluation.md` — the M1→M2 gate evaluation that selected the multi-role authoring path
- `src/squadops/cycles/proposed_role_tasks.py` — schema foundation (extended by PR 93.1)
- `src/squadops/capabilities/handlers/_plan_authoring.py` — shared LLM-loop helpers (used by all SIP-0093 handlers)
- `src/squadops/capabilities/handlers/planning_tasks.py:432` — `_produce_plan`, source for the `PlanAuthoringService` extraction in PR 93.0
- `src/squadops/cycles/task_plan.py:59` — `PLANNING_TASK_STEPS`, extended by PR 93.0 / 93.2 / 93.3
- `examples/03_group_run/prd.md` — the canonical reference PRD this SIP would author plan tasks for
- `docs/TEST_QUALITY_STANDARD.md` — bar every test in this plan must clear

---

## Plan Revision History

- **Plan Rev 2 (2026-05-09):** Targeted tightening from review. Added explicit "Routing under `multi_role_plan_authoring`" section pinning flag-off vs flag-on routes (no hybrid mode). Added RC-27 (canonical plan is the sole executor input) and RC-28 (M3 independence from SIP-0093 internals). Extended PR 93.0's verbatim-equivalence test with an M1-substrate side-effect-absence assertion (no SIP-0093 artifacts produced when flag is off). No scope changes to the five-PR sequence.
- **Plan Rev 1 (2026-05-08):** Initial plan. Five PRs (93.0 through 93.4). RC-22..RC-26 runtime contracts. Sequential proposers in Rev 1 (parallel fan-out deferred to Rev 2). PR 93.0 extracts `PlanAuthoringService` for both M1-substrate and SIP-0093 fallback paths.
