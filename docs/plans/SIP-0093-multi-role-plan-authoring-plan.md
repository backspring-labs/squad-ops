# Plan: SIP-0093 Multi-Role Plan Authoring

## Context

SIP-0093 implements SIP-0092 M2 via shared brief → parallel domain proposals → governed merge. The full design lives in `sips/accepted/SIP-0093-Multi-Role-Plan-Authoring.md` (Rev 2, accepted 2026-05-05, tightened in PR #136 on 2026-05-08). This plan doc pins per-PR file changes, schemas, runtime contracts, and tests.

**SIP:** `sips/accepted/SIP-0093-Multi-Role-Plan-Authoring.md`
**Parent SIP:** `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` (M2 implementation path)
**Branch model:** Each PR lands on a feature branch off main. **PRs 93.0–93.2 are inert additions** — they add new modules and register new handlers, but do not modify `PLANNING_TASK_STEPS` or `governance.review_plan`'s body. The pre-SIP-0093 inline-authoring path keeps running unchanged through 93.2. **PR 93.3 is the cutover**: it adds the merger, rewires `PLANNING_TASK_STEPS`, and removes inline authoring from `governance.review_plan` atomically. After 93.3 there is exactly one runtime route for plan production. PR 93.4 wires the gate package and observability around the post-cutover route.

The five PRs (per SIP-0093 §8 Rev 3):

- **PR 93.0** — `PlanAuthoringService` extraction from `_produce_plan` (pure refactor; current handler calls the service inline, byte-identical output) plus `plan_authoring_brief.yaml` schema and `governance.prepare_plan_authoring_brief` handler (registered, not wired). Inert.
- **PR 93.1** — Proposal and merge schemas (`ProposedPlanTasks` extension, `PlanGuidance`, `MergeDecisions`); brief-conflict model; per-canonical-task provenance. Pure schema. Inert.
- **PR 93.2** — Role proposer handlers (`development.propose_plan_tasks`, `qa.propose_plan_tasks`, `strategy.propose_plan_guidance`); proposal failure shape. Registered, not wired. Inert.
- **PR 93.3 (cutover)** — `governance.merge_plan` handler with deterministic merge policy (SIP-0093 §5.8) and `merge_decisions.yaml` output. **Rewires `PLANNING_TASK_STEPS`: brief → proposers (per `plan_authoring_contributors`) → merger → review_plan(sign-off). Removes inline `_produce_plan` invocation from `GovernanceReviewPlanHandler`.** Sole-author handling for empty contributors and all-proposals-failed. The runtime route changes here.
- **PR 93.4** — Gate package surfacing, observability metrics, degraded-sole-author operator warning, console hooks for the new gate artifacts.

**What already shipped** (do not re-create):

- `src/squadops/cycles/proposed_role_tasks.py` — `ProposedRoleTasks` + `ProposedTask` dataclasses plus a `from_yaml()` parser. Landed in PR #125. **PR 93.1 extends this** rather than rewriting it.
- `src/squadops/capabilities/handlers/_plan_authoring.py` — fenced YAML extraction and retry-with-corrective-feedback helpers. Used by all SIP-0093 handlers.
- `governance.correction_decision` `structural_plan_change_candidate` diagnostic field. Landed in commit `9657449`. SIP-0093 leaves this handler intact.

---

## Routing: one runtime route, contributor-driven width

After PR 93.3 (cutover), the framing pipeline is unconditional. There is no `multi_role_plan_authoring` flag. `plan_authoring_contributors` controls *who participates*, not *which path runs*. An empty list yields sole-author mode through the same handler chain.

```
data.research → strategy.frame → development.design_plan → qa.define_test_strategy
  → governance.prepare_plan_authoring_brief                    (emits plan_authoring_brief.yaml)
  → development.propose_plan_tasks   ┐                          (only if "development" ∈ contributors)
  → qa.propose_plan_tasks            ├─ steps included per     (only if "qa"          ∈ contributors)
  → strategy.propose_plan_guidance   ┘  plan_authoring_contributors  (only if "strategy"    ∈ contributors)
  → governance.merge_plan
      → if ≥1 proposal succeeded:    deterministic merge per SIP-0093 §5.8       → authoring_mode: multi_role
      → if 0 proposals available:    PlanAuthoringService.produce_plan(...)      → authoring_mode: sole_author
                                                                                   sole_author_reason:
                                                                                     - no_contributors_configured  (contributors == [])
                                                                                     - all_proposals_failed         (contributors != [], but all failed)
      → emits canonical implementation_plan.yaml + merge_decisions.yaml
  → governance.review_plan          (sign-off only)
  → [GATE]
```

**No flag. No hybrid mode.** The *handler chain* is the same regardless of contributors config — only the *content* of `PLANNING_TASK_STEPS` shifts (proposer steps included or omitted based on the contributors list). `governance.review_plan`'s body never authors a plan; after 93.3 cutover it always signs off on a canonical plan produced upstream by the merger.

**Brief is unconditional.** The brief is always produced, even when the contributors list is empty. This keeps the gate package shape constant across all cycles and gives sole-author mode an operator-readable scope summary at gate. Cost is one extra LLM call (~30–60s) for sole-author cycles; accepted as the price of one path.

**M1 substrate disappears as a runtime route.** `_produce_plan`'s body lives only as the `PlanAuthoringService` function the merger calls when there are no proposals to merge. There is no separate "M1 path" after 93.3.

---

## Runtime Contracts

These extend SIP-0092's RC-9..RC-21. New contracts are RC-22 through RC-26.

**RC-22 (Brief authority and immutability):** The `plan_authoring_brief.yaml` is authored once per cycle by `governance.prepare_plan_authoring_brief` and is immutable after emission. Proposers and the merger consume the brief as untrusted-input-shaped read-only context. The merger may *escalate* a `severity: blocking` brief conflict (per SIP-0093 §5.5) to operator at gate; the merger may *not* edit the brief. A revised brief, if needed, requires a re-run of the framing tail (out of scope for Rev 1).

**RC-23 (Proposal-merger artifact flow):** Every `proposed_plan_tasks.yaml` and `plan_guidance.yaml` artifact MUST reference the brief by `source_brief_id`. The merger rejects any proposal whose `source_brief_id` does not match the upstream brief — that proposal is treated as a missing proposal (`proposal_completeness: partial`, role recorded in `missing_proposals`). This prevents stale proposals from a prior framing attempt from contaminating a re-run.

**RC-24 (Merger-only task indices):** Proposers MUST NOT emit final numeric `task_index` values. Cross-proposal task references use `depends_on_focus` keys of the form `{role}:{focus}` per `proposed_role_tasks.focus_key()` (or symbolic dependency tags per SIP-0093 §5.4.3 — the existing implementation chose `{role}:{focus}` and Rev 1 adopts that). The proposal parser rejects integer values in `depends_on_focus`. The merger resolves these keys to numeric `depends_on` indices in the canonical `implementation_plan.yaml`.

**RC-25 (`merge_decisions.yaml` audit completeness):** Every canonical task in `implementation_plan.yaml` MUST appear in `merge_decisions.yaml` with `task_index`, `source_proposal_task_keys`, `proposed_by`, and `merge_action ∈ {accepted, merged, modified, gap_filled}`. Tasks created by the merger to fill gaps (no proposal source) are marked `merge_action: gap_filled`. Test: full canonical-plan / merge-decisions correspondence asserted in PR 93.3.

**RC-26 (Authoring-mode authority):** `merge_decisions.yaml` MUST record `authoring_mode ∈ {multi_role, sole_author}` and, when `authoring_mode == sole_author`, `sole_author_reason ∈ {no_contributors_configured, all_proposals_failed}`. `multi_role` requires that at least one role proposal arrived and parsed and contributed at least one canonical task. `sole_author` requires that the canonical plan was produced by `PlanAuthoringService.produce_plan(...)`. The two values cannot coexist; tests assert this property explicitly at parser level and in the merger. Degraded-sole-author frequency (`sole_author_reason: all_proposals_failed`) is a tracked gate metric (M2→M3 gate criterion C2); cycles configured as sole-author (`no_contributors_configured`) are excluded from C2.

**RC-27 (Canonical plan is the sole executor input):** The build executor consumes only the canonical `implementation_plan.yaml`. `plan_authoring_brief.yaml`, `proposed_plan_tasks.yaml`, `plan_guidance.yaml`, and `merge_decisions.yaml` are planning/gate evidence artifacts only — they MUST NOT be required by build execution after gate approval. This preserves the SIP-0086/SIP-0092 execution boundary: multi-role authoring changes plan *production*, not task *execution* semantics. The forwarding layer (`api/routes/cycles/runs.py`) only adds these new artifact types as gate evidence; existing `control_implementation_plan` forwarding to the build workload is unchanged.

**RC-28 (M3 independence from SIP-0093 internals):** When SIP-0092 Capability M3 (Plan Changes) ships, plan changes operate on the canonical `implementation_plan.yaml` regardless of whether that plan was produced by colocated authoring (M1 substrate), single-author fallback, or SIP-0093 multi-role merge. M3 MUST NOT couple to `merge_decisions.yaml`, per-role proposal artifacts, or proposal provenance. SIP-0093 changes the *origin* of the plan; M3 governs how it *evolves*. The two are orthogonal by construction.

---

## PR 93.0 — `PlanAuthoringService` extraction + brief schema and handler

**Why this PR exists first:** pure refactor + dormant additions. Extracts `_produce_plan` into a service so the cutover PR (93.3) doesn't have to land both an extraction *and* a route change. Adds the brief schema and handler so the merger PR (93.3) can wire them in without simultaneously inventing them. No behavior change in this PR — `governance.review_plan` continues to produce the canonical plan inline (now via the service); the brief handler is registered but not yet in `PLANNING_TASK_STEPS`.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/cycles/plan_authoring_brief.py` (new) | `PlanAuthoringBrief` frozen dataclass + `from_yaml()` parser. Required Rev 1 fields: `version`, `brief_id`, `objective_summary`, `accepted_stack`, `must_cover_requirements`, `scope_cuts`, `risk_areas`. Optional fields preserved as-parsed but not validated beyond YAML well-formedness. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `GovernancePreparePlanAuthoringBriefHandler` (`governance.prepare_plan_authoring_brief`) — reads framing artifacts from `prior_outputs`, prompts the lead for a brief, parses with `PlanAuthoringBrief.from_yaml()`, returns the brief as primary output. Uses `_plan_authoring.retry_yaml_call` for the LLM loop. |
| `src/squadops/capabilities/handlers/_plan_authoring_service.py` (new) | **`PlanAuthoringService`**: extracts the body of `_produce_plan` from `planning_tasks.py:432–620` into a function-style service with one entry point — `produce_plan(prompt_inputs, llm_client, run_state) -> ImplementationPlan`. The retry loop, prompt construction, role/task_type constraint logic, and YAML validation move here intact. After 93.3 cutover, only the merger calls this service (for sole-author mode). |
| `src/squadops/capabilities/handlers/planning_tasks.py` | `GovernanceReviewPlanHandler.handle()` calls `PlanAuthoringService.produce_plan(...)` inline (replacing the inline `_produce_plan` invocation). Behavior is byte-identical to today; this is a pure refactor. The handler still authors and signs off — the cutover PR (93.3) will remove the authoring side, leaving sign-off only. |
| Capability registry (where planning task types are registered) | Register `governance.prepare_plan_authoring_brief`. Handler exists; not yet in `PLANNING_TASK_STEPS`. |

**Why a service first:** the merger needs `PlanAuthoringService` for sole-author mode (both `no_contributors_configured` and `all_proposals_failed` cases call it). Landing the service in 93.0 means 93.3 can rewire `PLANNING_TASK_STEPS` without simultaneously moving 200 lines of LLM-loop / prompt construction code. Pure refactor first, route change later.

**Verbatim equivalence (regression anchor):** `PlanAuthoringService.produce_plan(...)` must produce a byte-identical `ImplementationPlan` to today's `_produce_plan` for identical seeded LLM responses. This is the safety bar PR 93.0 must clear before the rest of the sequence can layer on top.

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
| `plan_authoring_contributors` | `["development", "qa", "strategy"]` | Validated by config loader (Rev 1 contributors must be a subset of `{development, qa, strategy}`; `build` is a Rev 2 extension and rejected here). PR 93.0 only validates the value; no consumer reads it yet. |

**Removed flag:** the original Rev 1 design called for a `multi_role_plan_authoring` master flag. Removed before any code shipped — the propose/merge pipeline is unconditional after 93.3 cutover, and `plan_authoring_contributors: []` is the documented way to opt a profile into sole-author mode.

### Tests

- Unit (`tests/unit/cycles/test_plan_authoring_brief.py`, new):
  - Required fields enforced; missing field raises `ValueError` with the field name in the message.
  - Optional fields default to empty when absent; populated fields parse round-trip.
  - Malformed YAML at top level raises `ValueError`.
  - Edge case: brief with `must_cover_requirements: []` parses but a downstream consumer-level test asserts the merger surfaces a warning operator-note.
- Unit (`tests/unit/capabilities/test_plan_authoring_service.py`, new):
  - `PlanAuthoringService.produce_plan(...)` produces the same `ImplementationPlan` as `_produce_plan` for an identical seeded LLM response (verbatim-equivalence regression anchor — the safety bar 93.0 must clear).
  - Service surfaces parse failures the same way `_produce_plan` did (no wording regression).
- Unit (`tests/unit/capabilities/test_prepare_plan_authoring_brief.py`, new):
  - Handler produces a `PlanAuthoringBrief` artifact for a seeded LLM response.
  - Handler emits a structured failure when the LLM response cannot be parsed after `retry_yaml_call` exhaustion.
- Integration (`tests/integration/cycles/test_brief_handler.py`, new):
  - Brief handler invoked in isolation produces a parseable brief; handler is **not** in `PLANNING_TASK_STEPS` yet so framing-phase cycles remain byte-identical to today.
  - End-to-end framing cycle: `governance.review_plan` calls `PlanAuthoringService.produce_plan(...)` and produces the canonical plan; output equals pre-93.0 cycle output for the same seeded inputs.

---

## PR 93.1 — Proposal and merge schemas

Pure schema work. No new handlers; no behavior change. Lets PR 93.2 and 93.3 layer on a stable schema surface.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/cycles/proposed_role_tasks.py` (extend) | Add required field `source_brief_id: str` to `ProposedRoleTasks`. Add `proposal_id: str`, `scope_statement: str`, `brief_conflicts: list[BriefConflict]` (default empty). Optional Rev 1 recommended fields: `source_artifact_refs`, `assumptions`, `risks`, `gaps_not_covered`, `confidence`. Update `from_yaml()` to enforce the new required fields and reject integer entries in `depends_on_focus` (RC-24). |
| `src/squadops/cycles/proposed_role_tasks.py` (extend) | New `BriefConflict` frozen dataclass with fields: `brief_field: str`, `proposed_change: str`, `reason: str`, `severity: Literal["warning", "blocking"]`, `affected_proposal_task_keys: list[str]`. Parse rejects unknown severity. |
| `src/squadops/cycles/plan_guidance.py` (new) | `PlanGuidance` frozen dataclass + `from_yaml()`. Fields: `version`, `guidance_id`, `source_brief_id`, `proposing_role: Literal["strategy"]`, `priority_guidance`, `ordering_guidance`, `risk_guidance`, `time_budget_guidance`, `scope_cut_guidance`, `must_not_skip`, `defer_if_time_constrained`, `confidence`. Required: `version`, `guidance_id`, `source_brief_id`, `proposing_role`. Rest optional. |
| `src/squadops/cycles/merge_decisions.py` (new) | `MergeDecisions` frozen dataclass + `from_yaml()`. Required Rev 1 fields: `version`, `target_plan_id`, `brief_id`, `proposal_ids`, `guidance_ids`, `authoring_mode: Literal["multi_role", "sole_author"]`, `sole_author_reason: Literal["no_contributors_configured", "all_proposals_failed"] \| None` (required when `authoring_mode == "sole_author"`, must be `None` otherwise), `proposal_completeness: Literal["complete", "partial", "sole_author"]`, `missing_proposals: list[MissingProposal]` (with per-role failure_reason), `canonical_tasks: list[CanonicalTaskProvenance]`, `brief_conflicts_disposition: list[BriefConflictDisposition]`, `operator_notes: str`. |
| `src/squadops/cycles/merge_decisions.py` (new) | `CanonicalTaskProvenance` frozen dataclass: `task_index: int`, `source_proposal_task_keys: list[str]`, `proposed_by: list[str]`, `merge_action: Literal["accepted", "merged", "modified", "gap_filled"]`, `reason: str`. |
| `src/squadops/cycles/merge_decisions.py` (new) | `BriefConflictDisposition` frozen dataclass: `brief_field: str`, `severity: Literal["warning", "blocking"]`, `disposition: Literal["accepted", "rejected", "escalated_to_operator"]`, `reason: str`. |

### Schema invariants enforced by parsers

- `ProposedRoleTasks.from_yaml()` rejects integer `depends_on_focus` entries (RC-24). Existing `focus_key()` collision check is preserved.
- `PlanGuidance.from_yaml()` rejects `proposing_role != "strategy"` since strategy is the only Rev 1 contributor of guidance.
- `MergeDecisions.from_yaml()` enforces: every `canonical_tasks[i].task_index` is unique and contiguous starting at 0; `authoring_mode == "sole_author"` requires `sole_author_reason ∈ {"no_contributors_configured", "all_proposals_failed"}` AND `proposal_completeness == "sole_author"`; `authoring_mode == "multi_role"` requires `sole_author_reason is None` AND `proposal_completeness ∈ {"complete", "partial"}`. Mismatches raise `ValueError` (RC-26 enforcement at parser level).

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
| `src/squadops/cycles/task_plan.py` | (No `PLANNING_TASK_STEPS` modification in this PR — registered handlers stay dormant. The cutover PR (93.3) wires the brief, proposers, and merger together atomically.) |
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
- Integration (proposer handlers in isolation — no `PLANNING_TASK_STEPS` change in this PR):
  - Each proposer handler invoked directly produces a parseable proposal/guidance artifact for a seeded brief + framing prior_outputs.
  - Failure-injection per handler: `retry_yaml_call` exhaustion produces a structured failure record, not an exception.
  - Brief-id mismatch: handler called with a brief whose `brief_id` doesn't match the proposal's `source_brief_id` produces a structured failure record (RC-23 enforcement at handler level).
  - End-to-end framing cycle remains byte-identical to today (handlers registered, not wired into `PLANNING_TASK_STEPS` until 93.3).

---

## PR 93.3 — `governance.merge_plan` + cutover (the runtime route changes here)

This is the only PR in the sequence that changes the runtime route. It lands the merger and rewires `PLANNING_TASK_STEPS` atomically. After 93.3, the pre-SIP-0093 inline-authoring path inside `governance.review_plan` is gone; there is exactly one runtime route for plan production. Sole-author mode (configured empty contributors, or all-proposals-failed) flows through the same handler chain via `PlanAuthoringService`.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/capabilities/handlers/planning_tasks.py` | New `GovernanceMergePlanHandler` (`governance.merge_plan`). Reads brief + all proposal artifacts + guidance artifact + proposer-failure records from `prior_outputs`. If ≥1 proposal succeeded, applies the deterministic policy below; if 0 proposals available (configured empty contributors, or all proposals failed), calls `PlanAuthoringService.produce_plan(...)` directly. Always emits canonical `implementation_plan.yaml` + `merge_decisions.yaml` with `authoring_mode` / `sole_author_reason` / `proposal_completeness` per RC-26. |
| `src/squadops/capabilities/handlers/planning_tasks.py` | **`GovernanceReviewPlanHandler.handle()` cutover**: remove inline `PlanAuthoringService.produce_plan(...)` invocation introduced in PR 93.0. Handler is now sign-off only — it consumes the canonical plan from upstream merger and validates planning readiness. Surfaces `merge_decisions.yaml` content into the planning artifact's evidence section so the operator sees brief, canonical plan, and merge decisions side-by-side at gate. |
| `src/squadops/cycles/task_plan.py` | **Rewire `PLANNING_TASK_STEPS`**: after `qa.define_test_strategy`, append `governance.prepare_plan_authoring_brief`, then proposer steps for each role in `plan_authoring_contributors` (sequential in Rev 1), then `governance.merge_plan`, then `governance.review_plan` (sign-off). Empty contributors list → no proposer steps in the sequence; merger receives no proposals and runs sole-author mode. |
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
  - Merger receives missing strategy proposal: cycle continues; `authoring_mode: multi_role`; `proposal_completeness: partial`; missing strategy guidance recorded as warning operator-note.
  - **Sole-author cycle (configured)** — `plan_authoring_contributors: []`. Cycle runs brief → merger (no proposers in `PLANNING_TASK_STEPS`) → review_plan sign-off. Merger calls `PlanAuthoringService` directly. `merge_decisions.yaml` records `authoring_mode: sole_author`, `sole_author_reason: no_contributors_configured`, `proposal_completeness: sole_author`, `missing_proposals: []`. No operator warning rendered (configured mode).
  - **Sole-author cycle (degraded)** — contributors configured but all proposals seeded to fail. Merger emits `authoring_mode: sole_author`, `sole_author_reason: all_proposals_failed`, populated `missing_proposals` with per-role failure reasons. Operator warning rendered.
  - **Cutover regression** — verify the inline `_produce_plan` invocation in `GovernanceReviewPlanHandler` is gone (handler does not call `PlanAuthoringService` anywhere in its body after this PR; assertion via inspecting handler module imports/calls or via a test that exercises sign-off without the merger and confirms it raises rather than silently authoring).

---

## PR 93.4 — Gate package, observability, degraded-sole-author surfacing

Closes the loop on the route 93.3 cut over to: gate-package wiring for the new artifacts, telemetry for the M2→M3 gate criteria, and operator-warning surfacing for degraded-sole-author cycles.

### Modified / new files

| File | Change |
|------|--------|
| `src/squadops/api/routes/cycles/runs.py` | Gate-package extension — surface `plan_authoring_brief.yaml` and `merge_decisions.yaml` as primary artifacts alongside `implementation_plan.yaml`. Per-role `proposed_plan_tasks.yaml` and `plan_guidance.yaml` remain queryable as intermediate evidence but not in the primary view. |
| `src/squadops/api/routes/cycles/runs.py` | Operator warning rendered when `merge_decisions.yaml.authoring_mode == "sole_author"` AND `sole_author_reason == "all_proposals_failed"`. No warning for `no_contributors_configured` (configured cycle mode). |
| `src/squadops/telemetry/...` (new metric emissions) | Authoring duration (per role + total), proposal completeness counts (`complete`/`partial`/`sole_author`), merge conflict counts (`brief_conflicts_disposition` rollup), degraded-sole-author frequency (`sole_author_reason: all_proposals_failed` only). |
| Console UI hooks | Brief, canonical plan, merge_decisions surfaced as primary at gate; degraded-sole-author warning rendered prominently. |

### Operator-visible artifacts at gate

Per SIP-0093 §4 (Non-Goals — operator visibility) and SIP-0092 §6.2.2 primary-vs-intermediate split:

- **Primary** — `implementation_plan.yaml`, `plan_authoring_brief.yaml`, `merge_decisions.yaml`.
- **Intermediate evidence** — per-role `proposed_plan_tasks.yaml` and `plan_guidance.yaml` available for inspection but not surfaced as primary artifacts.
- **Authoring-mode marker** — `authoring_mode` and (when sole-author) `sole_author_reason` are visible in the primary surface. A degraded-sole-author cycle (`all_proposals_failed`) renders an explicit operator warning; a configured sole-author cycle (`no_contributors_configured`) does not.

### Metrics (M2→M3 gate criteria support)

The amended Gate M2→M3 criteria (per `docs/plans/SIP-0092-implementation-plan-improvement-plan.md`) need:

- **C1 — Multi-role contribution non-redundancy rate.** Computed from `merge_decisions.yaml` per-canonical-task `proposed_by`, sample limited to cycles with `authoring_mode: multi_role`. A cycle counts toward the threshold when at least one canonical task has `proposed_by` containing a non-dev role and is not present in the dev proposal.
- **C2 — Degraded-sole-author rate.** Computed from `authoring_mode: sole_author AND sole_author_reason: all_proposals_failed` count over (total cycles − configured-sole-author cycles). Cycles with `sole_author_reason: no_contributors_configured` are excluded — they're an intentional configuration, not a failure mode.
- **C3 — Structural-change candidate rate.** Already emitted by `governance.correction_decision` (commit `9657449`). No change here.
- **C4 — Plan-quality regression check.** Canonical-plan schema-validity rate; typed-acceptance evaluator-error rate. Existing M1 telemetry covers this.

### Config keys

No new keys.

### Tests

- Unit (`tests/unit/capabilities/test_merge_plan_sole_author.py`, new):
  - **Configured sole-author** — `plan_authoring_contributors: []` cycle. Merger calls `PlanAuthoringService` directly. Emits `merge_decisions.yaml` with `authoring_mode: sole_author`, `sole_author_reason: no_contributors_configured`, empty `missing_proposals`. No operator warning.
  - **Degraded sole-author** — contributors configured, all proposals fail. Emits `authoring_mode: sole_author`, `sole_author_reason: all_proposals_failed`, `missing_proposals` populated with failure reasons. Operator warning rendered.
  - **RC-26 invariant** — `authoring_mode: multi_role` cannot coexist with `sole_author_reason != None`; `authoring_mode: sole_author` requires a `sole_author_reason`. Parser-level rejection.
  - Two proposers fail, one succeeds → `authoring_mode: multi_role`; `proposal_completeness: partial`; surviving proposal is honored.
- Integration (`tests/integration/cycles/test_gate_package.py`, new):
  - Gate response includes brief + canonical plan + merge_decisions as primary; per-role artifacts queryable but not in primary view.
  - Cycle with full multi-role authoring → primary view shows `authoring_mode: multi_role`, `proposal_completeness: complete`. No warning.
  - Cycle with one missing proposer → `authoring_mode: multi_role`, `proposal_completeness: partial`; missing role surfaced in `missing_proposals`. No warning.
  - Configured-sole-author cycle → `authoring_mode: sole_author`, `sole_author_reason: no_contributors_configured` in primary view. No operator warning.
  - Degraded-sole-author cycle → operator warning rendered prominently.
- Integration (`tests/integration/telemetry/test_plan_authoring_metrics.py`, new):
  - Authoring duration metrics emitted per role + total.
  - Proposal completeness counts emitted as separate counters (`complete`/`partial`/`sole_author`).
  - Degraded-sole-author frequency counter increments only on `sole_author_reason: all_proposals_failed`; configured-sole-author cycles do NOT increment this counter.

---

## Profile Config Examples

Mirrors SIP-0092 §6.4. The single config knob is `plan_authoring_contributors`; profiles tune participation, not path.

### After PR 93.0–93.2 land (inert additions; current path unchanged)

```yaml
# build profile — no behavior change; new modules dormant
defaults:
  plan_authoring_contributors: ["development", "qa", "strategy"]   # validated, not consumed yet
```

PRs 93.0–93.2 register handlers and validate config but do not modify `PLANNING_TASK_STEPS` or `governance.review_plan` body. Cycles run today's framing pipeline unchanged. Each PR's gate is "current cycle output is byte-identical to today."

### After PR 93.3 lands (cutover; one runtime route)

```yaml
# build profile — multi-role authoring active
defaults:
  plan_authoring_contributors: ["development", "qa", "strategy"]

# validation profile — gate-cycle target with full multi-role
defaults:
  max_self_eval_passes: 2
  max_correction_attempts: 3
  plan_authoring_contributors: ["development", "qa", "strategy"]

# selftest profile — short cycle, sole-author mode (skips proposer fan-out)
defaults:
  plan_authoring_contributors: []
```

`plan_authoring_contributors: []` makes the merger run sole-author mode through the same handler chain — no separate runtime route, no flag. `selftest` cycles avoid the framing-tail cost of multi-role authoring this way.

### After PR 93.4 lands (gate-package and observability)

Same profile shapes as above — no new config keys. PR 93.4 only changes what's surfaced at gate and what telemetry is emitted; profile-level behavior is set in 93.3.

### Post-M3 (after M2→M3 gate passes)

```yaml
# implementation profile — long-cycle target, all on
defaults:
  plan_authoring_contributors: ["development", "qa", "strategy"]
  plan_changes_enabled: true
  correction_plan_changes_enabled: true
  max_plan_changes: 8
  max_correction_attempts: 3
```

M3 flags are out of scope for SIP-0093; shown here only as the post-M3 target shape.

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
- **`multi_role_plan_authoring` master flag.** Removed before any code shipped (Plan Rev 3); the propose/merge pipeline is unconditional after 93.3 cutover. Short cycles use `plan_authoring_contributors: []` for sole-author mode through the same handler chain.

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

- Verbatim-equivalence test: `PlanAuthoringService.produce_plan(...)` produces byte-identical plans to today's `_produce_plan` for identical seeded LLM responses (PR 93.0).
- Worked-example test: SIP-0093 §5.8 deterministic merge example (PR 93.3).
- "Eve proposes a QA task Neo omitted; merged plan includes it" (PR 93.3).
- Configured-sole-author cycle test: `plan_authoring_contributors: []` produces canonical plan via merger calling `PlanAuthoringService` directly; `merge_decisions.yaml` records `sole_author_reason: no_contributors_configured` (PR 93.3).
- Degraded-sole-author cycle test: contributors configured but all proposals fail → `authoring_mode: sole_author`, `sole_author_reason: all_proposals_failed`, operator warning rendered (PR 93.4).
- RC-26 invariant test: `authoring_mode: multi_role` cannot coexist with `sole_author_reason != None`; `authoring_mode: sole_author` requires a `sole_author_reason` (PR 93.1 parser, asserted again in PR 93.3 merger code).
- Cutover regression test: after PR 93.3, `GovernanceReviewPlanHandler` does not author a plan — it only signs off on the canonical plan from upstream merger (PR 93.3).

---

## Risks and Mitigations (Plan-Specific)

These are *plan-execution* risks — distinct from SIP-0093 §6 cost analysis and SIP-0092 §9 design risks.

| Risk | Mitigation |
|---|---|
| Parallel fan-out shipped accidentally before executor support exists | Rev 1 ships sequential. The plan doc explicitly notes this and SIP-0093 §6 cost analysis uses sequential numbers (~12–17 min framing tail). |
| `PlanAuthoringService` extraction in PR 93.0 introduces a regression in the current path | Verbatim-equivalence test is the gate for 93.0. The service is a function-style module, not a class — minimizes refactoring surface. PR 93.0 is a pure refactor (no route change). |
| PR 93.3 cutover ships partially — handlers exist but `PLANNING_TASK_STEPS` rewiring is half-done | The cutover is one atomic PR (rewire + remove inline authoring) with the cutover-regression test. No half-state is mergeable: tests fail if the inline path is still callable, and tests fail if the merger path is incomplete. |
| Existing `proposed_role_tasks.py` shipped in PR #125 drifts from SIP-0093 Rev 2 vocabulary | PR 93.1 extends, doesn't rewrite. The `{role}:{focus}` dependency convention is grandfathered as the Rev 1 implementation form (RC-24); SIP-0093 §5.4.3's `dev.api.routes` shape was illustrative. |
| Merger LLM choreography drifts from the deterministic merge policy | Worked-example test from SIP-0093 §5.8 is a regression anchor. Merger prompt is structured around the policy steps explicitly. |
| Degraded-sole-author silently masquerades as multi-role authoring | RC-26 invariant + parser-level rejection of inconsistent `authoring_mode`/`sole_author_reason` combinations. Test asserts the impossibility. Operator warning rendered only on `all_proposals_failed`, never on `multi_role`. |
| Brief becomes "the plan" in practice (proposers rubber-stamp) | M2→M3 gate criterion C1 measures non-redundancy directly. If C1 fails after SIP-0093 ships, the brief prompt or proposer prompts are wrong, not the architecture. |
| Sole-author mode used silently in profiles that should be multi-role | `plan_authoring_contributors: []` is an explicit, reviewable config choice in profile YAML. CRP defaults make it visible. PR-template checklist asks reviewers to confirm contributors values are intentional. |
| Cutover PR (93.3) blast radius too large to review | 93.0–93.2 land first as inert additions, so 93.3's diff is bounded to: merger handler, `PLANNING_TASK_STEPS` rewiring, `governance.review_plan` body trim, and the integration tests. Schema and proposer code are already in main. |

---

## Terminology Lock additions (PR Checklist)

Extends the SIP-0092 plan doc Terminology Lock. The SIP-0093 canonical terms (already added to SIP-0092 plan doc Terminology Lock in PR #136) are reproduced here for PR-time reference:

**Banned in new code** (allowed only in historical comments or migration tests):

- `split_implementation_planning`, `development.plan_implementation`, `development.plan_implementation_revise`, `plan_review.yaml`, `PlanReview`, `max_planning_revisions`, `review_status: revision_requested`, `revision_instructions`.
- `multi_role_plan_authoring` — removed before any code shipped (Plan Rev 3); see Rev 3 history below.
- `fallback_single_author`, `proposal_completeness: fallback` — replaced by `authoring_mode: sole_author` + `sole_author_reason` taxonomy.
- "M1 substrate path" / "M1 substrate route" — after 93.3 there is one runtime route. The `PlanAuthoringService` function exists but is not a route.

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
| M2 contributors config | `plan_authoring_contributors` (single config knob; no master flag) |
| Authoring mode marker | `authoring_mode: multi_role \| sole_author` |
| Sole-author reason | `sole_author_reason: no_contributors_configured \| all_proposals_failed` |

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
- `src/squadops/cycles/task_plan.py:59` — `PLANNING_TASK_STEPS`, rewired in PR 93.3 cutover
- `examples/03_group_run/prd.md` — the canonical reference PRD this SIP would author plan tasks for
- `docs/TEST_QUALITY_STANDARD.md` — bar every test in this plan must clear

---

## Plan Revision History

- **Plan Rev 3 (2026-05-09):** Removed `multi_role_plan_authoring` feature flag before any code shipped, in line with SIP-0093 Rev 3.
  - Routing section rewritten: one runtime route after 93.3 cutover; `plan_authoring_contributors` controls participation, not path. Empty list yields sole-author mode through the same handler chain.
  - PR sequence restructured: 93.0–93.2 are inert additions; **93.3 is the cutover** that rewires `PLANNING_TASK_STEPS` and removes inline authoring from `GovernanceReviewPlanHandler`; 93.4 is gate-package + observability. The five-PR boundary stays the same; what each PR delivers shifts.
  - RC-26 reframed as authoring-mode authority (`authoring_mode: multi_role | sole_author` + `sole_author_reason`). The "fallback" name is gone; sole-author is now a configured mode for short cycles, not just failure recovery.
  - PR 93.0 reframed as a pure refactor (`PlanAuthoringService` extraction) plus dormant brief schema/handler. No `task_plan.py` modification in 93.0.
  - PR 93.1 schema updated for new `authoring_mode` / `sole_author_reason` / `proposal_completeness` taxonomy.
  - PR 93.2 reframed as inert additions of proposer handlers; no `PLANNING_TASK_STEPS` change.
  - PR 93.3 absorbs the cutover: merger + rewire + `governance.review_plan` body trim, atomic.
  - PR 93.4 reframed as gate-package surfacing + observability around the post-cutover route. Adds the degraded-sole-author operator warning (only on `all_proposals_failed`, not on `no_contributors_configured`).
  - Profile examples rewritten without the flag. `selftest` uses `plan_authoring_contributors: []`; `build` / `validation` use the full contributor list.
  - Required gate criteria updated: dropped "M1 path verbatim under flag off" framing (no flag); added configured-sole-author and degraded-sole-author cycle tests; added cutover-regression test.
  - Risks recast: cutover-half-state risk (mitigation: 93.3 is atomic), silent sole-author misuse risk (mitigation: profile YAML review).
  - Terminology lock: bans `multi_role_plan_authoring`, `fallback_single_author`, "M1 substrate path/route" in new code.
- **Plan Rev 2 (2026-05-09):** Targeted tightening from review. Added explicit "Routing under `multi_role_plan_authoring`" section pinning flag-off vs flag-on routes (no hybrid mode). Added RC-27 (canonical plan is the sole executor input) and RC-28 (M3 independence from SIP-0093 internals). Extended PR 93.0's verbatim-equivalence test with an M1-substrate side-effect-absence assertion (no SIP-0093 artifacts produced when flag is off). No scope changes to the five-PR sequence. *(Note: the routing-section content from Rev 2 was rewritten in Rev 3 to reflect the no-flag design; the side-effect-absence assertion is no longer relevant since there's no separate M1 path.)*
- **Plan Rev 1 (2026-05-08):** Initial plan. Five PRs (93.0 through 93.4). RC-22..RC-26 runtime contracts. Sequential proposers in Rev 1 (parallel fan-out deferred to Rev 2). PR 93.0 extracts `PlanAuthoringService` for both M1-substrate and SIP-0093 fallback paths.
