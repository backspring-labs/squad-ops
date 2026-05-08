---
title: Multi-Role Plan Authoring
status: accepted
author: SquadOps Architecture
created_at: '2026-04-30T00:00:00Z'
sip_number: 93
updated_at: '2026-05-07T00:00:00Z'
---
# SIP-0093: Multi-Role Plan Authoring

**Status:** Accepted
**Authors:** SquadOps Architecture
**Created:** 2026-04-30
**Revision:** 2

**Relationship:** This SIP **is** the implementation path for SIP-0092 M2. The M1→M2 gate evaluation (`docs/plans/SIP-0092-gate-M1-evaluation.md`, merged in PR #117 on 2026-05-05) selected the multi-role authoring path; SIP-0093 supplants M2-as-originally-written. The original single-author `development.plan_implementation → governance.review_plan` flow is retained only as the all-proposals-failed fallback (§5.10), not as the target architecture. SIP-0092 M1 (typed acceptance) and M3 (plan changes) are orthogonal to plan authorship and stand unchanged.

## 1. Abstract

The implementation plan (SIP-0092) decomposes a build into role-typed subtasks. Today (M1 substrate) one agent — Max, the lead — both produces and approves the plan. SIP-0092 M2 calls for separating the proposer from the reviewer. SIP-0093 implements that separation as **shared brief → parallel domain proposals → governed merge**: a lead-authored brief frames the problem, each contributing role independently proposes plan content for its own domain against the brief, and the lead merges those contributions into the canonical implementation plan.

This is not parallel independent planning. The shared brief pins stack, scope, and constraints before fan-out so proposers operate from the same worldview. Each proposer is domain-scoped (no proposer authors a complete plan). The merger is auditable through a structured `merge_decisions.yaml`. Final task indices are assigned only by the merger.

## 2. Problem Statement

Both M1 (Max sole broker) and M2-as-originally-written (Neo sole broker) have the same structural property: **one agent synthesizes the entire plan from the framing-phase outputs of all roles.** That single agent reads research, frame, design plan, and test strategy as `prior_outputs`, then writes the decomposition.

Three concerns with sole-broker authoring:

- **Single-perspective bias.** The sole author's role colors the decomposition. Max biases toward governance concerns; Neo biases toward implementation framing. QA's view of how the build should decompose to maximize testability never enters the plan directly — only via the prior `qa.define_test_strategy` output that the sole author chooses to interpret.
- **Cross-cutting coverage gaps.** A plan decomposition that doesn't aggregate role expertise can miss the integration points where roles collide: testability of dev components, security review of risky paths, performance benchmarks, infrastructure provisioning. Today these only enter the plan if the sole author thinks to include them.
- **Coupling to current task vocabulary.** The "Neo authors" choice in M2-as-originally-written is plausible *because* the Rev 1 task vocabulary is mostly `development.develop` + `qa.test`. The moment we add task types — security review, performance benchmark, infra setup — the dev-only authoring model strains.

The 1.0.x hardening plan's broader theme is "the squad stays coherent over a long cycle." Sole-broker plan authoring is a coherence single-point-of-failure that compounds with cycle length: the longer the cycle, the more the sole author's bias has time to amplify into wrong-shape work.

## 3. Goals

1. **Distribute plan authorship across roles** so each role's expertise directly shapes the part of the plan it best understands.
2. **Preserve a single canonical implementation plan artifact** — operators and the executor still consume *one* plan, not N proposals.
3. **Establish a shared worldview before fan-out** via a lead-authored `plan_authoring_brief.yaml` so role proposers don't each invent a different interpretation of the framing outputs.
4. **Keep the lead agent in the broker / merger position** so cross-role conflicts have an explicit resolver, matching real-world planning patterns (sprint planning with PM, design, engineering, QA participation).
5. **Bound coordination cost** — the propose-merge pattern must not balloon framing-phase LLM call counts beyond what long cycles can afford. See §6.
6. **Compose with SIP-0092 M1's typed acceptance** — each role's contribution carries its own typed acceptance criteria for the tasks it proposes.
7. **Compose with SIP-0092 M3 plan changes** — multi-role authoring applies at framing time; in-cycle plan changes (M3) remain governed by the correction protocol and are unaffected by who originally authored each task.
8. **Preserve the M2→M3 diagnostic signal** — the non-operative `structural_plan_change_candidate` field on `governance.correction_decision` continues to be elicited so the M2→M3 gate has the evidence it needs.

## 4. Non-Goals

- Replacing the framing sequence (`data.research → strategy.frame → development.design_plan → qa.define_test_strategy → ...`). Those steps are still the framing scaffolding; this SIP only changes who authors the plan within them.
- Distributing review or gate decisions. The merger / lead still owns the gate-readiness call.
- Implementing per-role plan-change authoring at correction time. SIP-0092 M3's correction-driven plan changes stay autonomous-correction-only.
- **Per-role proposals as primary operator artifacts.** Per-role `proposed_plan_tasks.yaml` files are intermediate evidence, not gate artifacts. The operator receives one canonical `implementation_plan.yaml`, plus `plan_authoring_brief.yaml` and `merge_decisions.yaml` summarizing accepted, rejected, merged, missing, and gap-filled role contributions.
- Independent plan generation. Each proposer operates from the same `plan_authoring_brief.yaml` and proposes only domain-scoped contributions. The canonical plan exists only after `governance.merge_plan`.

## 5. Approach

### 5.1 Shared plan-authoring brief

A new lead task, `governance.prepare_plan_authoring_brief`, runs after the framing artifacts (`data.research`, `strategy.frame`, `development.design_plan`, `qa.define_test_strategy`) and before any role proposer. Its output, `plan_authoring_brief.yaml`, is the single shared frame all proposers read.

The brief is intentionally tight: scope-framing only, not plan content. It does not assign task indices. It does not list subtasks. It does not replace role proposals.

**Required fields (Rev 1):**

```yaml
# plan_authoring_brief.yaml (Rev 1 required set)
version: 1
brief_id: <uuid>
source_artifact_refs: [...]              # framing artifacts the brief was derived from
objective_summary: |                     # one-paragraph statement of what the cycle must produce
  ...
accepted_stack:                          # frozen stack/runtime decisions for this cycle
  language: python
  framework: fastapi
  persistence: in_memory_repository
must_cover_requirements:                 # bullet list of PRD must-haves the plan must address
  - ...
scope_cuts:                              # what is explicitly out of scope for this cycle
  - ...
risk_areas:                              # cross-role concerns flagged for proposer attention
  - ...
```

**Recommended optional fields** (may be populated when the lead has signal for them; not required for Rev 1):
`major_components`, `dependency_assumptions`, `time_budget_guidance`, `task_granularity_guidance`, `artifact_naming_conventions`, `open_questions`.

**Why limit Rev 1 to six required fields:** the longer the brief, the closer it slides to "the brief *is* the plan and proposers are typing exercises." The six required fields cover the dimensions proposers must agree on (objective, stack, requirements, scope, risk) without pre-deciding decomposition. Optional fields earn promotion to required only after real cycles show they are load-bearing.

**The brief author is still Max.** This trades "Max sole plan broker" for "Max sole brief broker." That is a meaningful softening — briefs are smaller-surface than plans, so a brief-authoring bias affects fewer downstream decisions — but it does not eliminate sole-broker concern. It is acceptable because the brief contains decisions (stack, scope) that genuinely should be lead-owned and because the brief is auditable (proposers can disagree via §5.5 conflict reports).

### 5.2 Domain-scoped role proposals

**Invariant:** multi-role plan authoring is not independent plan generation. Each proposer operates from the same `plan_authoring_brief.yaml` and proposes only domain-scoped contributions. The canonical implementation plan exists only after `governance.merge_plan`.

**Domain ownership (Rev 1):**

| Role | Owns proposals for |
|------|--------------------|
| Development (Neo) | Implementation/component tasks, dev-side typed acceptance, dependency edges among dev tasks |
| QA (Eve) | Test, acceptance, validation, evidence tasks; qa-side typed acceptance over dev artifacts |
| Strategy (Nat) | Cross-cutting *guidance*: ordering, priority, risk, scope, time-budget — **not** task content (see §5.3) |
| Build (Bob, optional) | Packaging, app startup, integration wiring, build-system glue, runnable commands, deployment scripts (only when builder role is enabled — see §5.12) |

**Rule:** no proposer assigns final `task_index` values. Final indices are produced only by the merger (§5.6).

### 5.3 Per-role propose tasks

Each contributing role gets a propose task type:

| Role | Task type | Output artifact |
|------|-----------|-----------------|
| Development | `development.propose_plan_tasks` | `proposed_plan_tasks.yaml` |
| QA | `qa.propose_plan_tasks` | `proposed_plan_tasks.yaml` |
| Strategy | `strategy.propose_plan_guidance` | `plan_guidance.yaml` |
| Build (optional) | `build.propose_plan_tasks` | `proposed_plan_tasks.yaml` |

**Why strategy is `propose_plan_guidance`, not `propose_plan_tasks`:** strategy's value is priority, ordering, and tradeoff framing, not task decomposition. Forcing strategy into `PlanTask` shape would produce fake implementation tasks and merge noise. The merger applies guidance to dev/qa/build tasks during merge.

`data.research` does not contribute plan tasks directly — its role is upstream context for the brief, and asking Data to propose subtasks risks scope creep.

### 5.4 Proposal artifact schemas

#### 5.4.1 `proposed_plan_tasks.yaml` (dev / qa / build)

**Required fields (Rev 1):**

```yaml
version: 1
proposal_id: <uuid>
source_brief_id: <brief_id>              # MUST match the upstream brief
proposing_role: development | qa | build
scope_statement: |                        # one-paragraph self-assessment of what this proposal covers
  ...
tasks:                                   # list of proposed plan tasks (see below)
  - ...
brief_conflicts: []                       # see §5.5 — empty list if no conflicts
```

**Recommended optional fields** (Rev 1 best-effort, not required to parse):
`source_artifact_refs`, `assumptions`, `risks`, `gaps_not_covered`, `confidence`.

**Per-proposed-task fields:**

```yaml
- proposal_task_id: dev.api.routes        # symbolic ID, role-namespaced (see §5.4.3)
  proposed_task_type: development.develop
  proposed_role: development
  focus: |
    Implement POST /runs/{id}/join with 409 on duplicate-join.
  description: |
    ...
  expected_artifacts: [backend/routes.py]
  acceptance_criteria:                    # M1 typed checks (RC-9..RC-12)
    - check: endpoint_defined
      file: backend/routes.py
      methods_paths: [[POST, /runs/{id}/join]]
      severity: error
  symbolic_depends_on: []                 # see §5.4.3
  rationale: |
    ...
  priority_hint: high | medium | low      # optional
```

**Why a tight required set:** `assumptions`, `risks`, `gaps_not_covered`, and `confidence` are LLM-output fields that populate inconsistently even when required. Mark them recommended; let the merger record actual gaps in `merge_decisions.yaml` rather than relying on proposers to self-report them reliably.

#### 5.4.2 `plan_guidance.yaml` (strategy)

```yaml
version: 1
guidance_id: <uuid>
source_brief_id: <brief_id>
proposing_role: strategy
priority_guidance:                        # which areas should run first / deepest
  - area: backend_api
    priority: high
    rationale: |
      ...
ordering_guidance:                        # ordering hints across symbolic IDs
  - before: dev.repository
    after: dev.api.routes
    rationale: |
      ...
risk_guidance:                            # risk callouts per symbolic ID or area
  - target: dev.api.routes
    risk: |
      ...
time_budget_guidance:                     # rough percentage allocations
  - area: backend_api
    budget_pct: 30
scope_cut_guidance: []                    # additional cuts beyond brief scope_cuts
must_not_skip: []                         # essential items that must survive merge
defer_if_time_constrained: []             # items the merger may drop under budget pressure
confidence: low | medium | high           # optional
```

Strategy's artifact is not a `PlanTask` list. The merger reads it as overlay guidance and applies it during merge.

#### 5.4.3 Symbolic dependencies

Final numeric task indices are merger-only. Cross-proposal dependencies (e.g., qa-proposed test depending on a dev-proposed component) use **loose symbolic tags** the merger resolves at integration time.

**Convention:** `<role>.<area>[.<subarea>]` — examples: `dev.api.routes`, `dev.repository`, `qa.backend.endpoint_tests`, `qa.frontend.smoke_tests`, `build.startup`.

**Rule:** the proposal parser rejects final numeric task indices in `symbolic_depends_on`. This forces proposers to use symbolic tags and lets the merger handle integration without proposers needing visibility into each other's numbering.

**Why loose symbolic, not pre-declared namespace:** pre-declaring the symbolic namespace in the brief makes the brief heavier and pre-decides decomposition. Loose tags ("Eve says her tests need dev's API implementation") let the merger match against whatever `dev.api.*` tasks actually appeared in Neo's proposal.

### 5.5 Brief conflict handling

If a proposer disagrees with the shared brief, it must not silently diverge. Each `proposed_plan_tasks.yaml` may include a `brief_conflicts` list:

```yaml
brief_conflicts:
  - brief_field: accepted_stack
    proposed_change: Use SQLite instead of in-memory repository
    reason: PRD requires persistence across app restart
    severity: warning | blocking
    affected_proposal_task_ids: [dev.repository, qa.persistence_tests]
```

`governance.merge_plan` must accept, reject, or escalate each conflict and record the disposition in `merge_decisions.yaml`.

**Severity rule:**

- **`warning`** — merger may resolve unilaterally and record the decision. Example: one proposer suggests a slightly stricter naming convention.
- **`blocking`** — merger **escalates to operator** at gate. The merger does not have standing to override a blocking conflict because blocking conflicts are typically *correctness* claims about the spec the brief author missed (the SQLite example above is one — Eve is asserting the brief contradicts the PRD). The canonical plan still emits, with the blocking conflict surfaced as an `operator_notes` entry the operator must address before approving.

This keeps the shared brief authoritative without making it authoritarian.

### 5.6 Merger task: `governance.merge_plan`

Max receives `plan_authoring_brief.yaml`, all `proposed_plan_tasks.yaml` artifacts, and `plan_guidance.yaml` as inputs. The merger produces:

1. **`implementation_plan.yaml`** — the canonical SIP-0092 M1 plan (no schema change). Tasks in 0..N order with merger-assigned indices.
2. **`merge_decisions.yaml`** — structured audit of how the canonical plan was assembled (§5.7).

The merger:

1. **Resolves brief conflicts** — accept/reject/escalate per §5.5.
2. **Deduplicates** overlapping tasks across role proposals (e.g., Neo proposes "tests for endpoints"; Eve proposes the same — Eve wins because it's qa-domain).
3. **Merges acceptance criteria** — combine compatible criteria from different roles on the same canonical task (§5.8 rule 2).
4. **Resolves dependency edges** — convert symbolic dependencies to final numeric `depends_on` indices.
5. **Applies strategy guidance** — ordering, priority, time-budget, risk callouts.
6. **Fills gaps** — if Eve's proposal references a dev component Neo didn't propose, the merger flags it and either adds the component or escalates.
7. **Assigns final task indices** producing the canonical 0..N sequence.

The output `implementation_plan.yaml` validates against the SIP-0092 M1 schema with no format change.

### 5.7 `merge_decisions.yaml`

The merger must be auditable. Otherwise Max becomes the new opaque sole broker.

**Required fields (Rev 1):**

```yaml
version: 1
target_plan_id: <plan_id>
brief_id: <brief_id>
proposal_ids: [<dev_proposal_id>, <qa_proposal_id>, <build_proposal_id?>]
guidance_ids: [<strategy_guidance_id>]
authoring_mode: multi_role | fallback_single_author
proposal_completeness: complete | partial | fallback     # see §5.9
missing_proposals: []                     # role IDs whose proposal was missing or failed
canonical_tasks:
  - task_index: 0
    source_proposal_task_ids: [dev.api.routes]
    proposed_by: [development]
    merge_action: accepted | merged | modified | gap_filled
    reason: |
      ...
brief_conflicts_disposition:              # one entry per conflict raised in §5.5
  - brief_field: accepted_stack
    severity: blocking
    disposition: escalated_to_operator | accepted | rejected
    reason: |
      ...
operator_notes: |                         # free-text surfaced at gate
  ...
```

**Recommended optional fields** (Rev 2): `merge_quality_check`, `final_ordering_rationale`, `merge_confidence`, separate accepted/merged/deduplicated/rejected breakdown lists. Rev 1 collapses these into the per-task `merge_action` enum (`accepted | merged | modified | gap_filled`) plus the `rejected_tasks` flat list.

**Why this is tight:** every additional required field is another thing the LLM can mess up and another schema surface tests must exercise. The Rev 1 required set is exactly what the M2→M3 gate's "multi-role contribution non-redundancy rate" criterion needs to evaluate; further detail can land in Rev 2 after real cycles show what's load-bearing.

### 5.8 Deterministic merge policy

Conflict resolution is not an open question. Rev 1 policy:

1. **Domain-owner wins for task ownership.**
   - Development tasks: Neo (or Bob, when builder is enabled, for build/assembly tasks).
   - QA tasks: Eve.
   - Strategy never owns tasks; it influences priority, ordering, and scope.

2. **Compatible acceptance criteria are merged.** Dev criteria and QA criteria can both survive on the canonical task when they test different surfaces. Two criteria are *compatible* when they target the same surface in non-contradictory ways.

3. **Strictest compatible criterion wins** when criteria are on a strictness ordering (e.g., `count_min: 5` vs `count_min: 3` — `count_min: 5` is strictly stronger). Most typed checks are not on a strictness ordering — they test different things — and in that case both criteria are preserved on the same canonical task.

4. **Incompatible task proposals** are resolved by one of:
   - **Split into separate tasks** when the proposals address distinguishable surfaces (e.g., Neo proposes a single `dev.api.routes` covering 5 endpoints; Eve proposes test tasks split per endpoint — the merger may split Neo's into 5 dev tasks).
   - **Domain-owner version wins** with the rejected alternative recorded in `merge_decisions.yaml` `rejected_tasks`.
   - **Structured merge conflict** surfaced in `merge_decisions.yaml` and escalated to operator if the conflict affects required scope, dependency validity, or acceptance coverage.

5. **Merge conflicts block gate** only when they affect required scope, dependency validity, or acceptance coverage. Style-level conflicts (naming, ordering nuances) record but do not block.

**Worked example.**

> Neo proposes:
> ```yaml
> - proposal_task_id: dev.api.join
>   proposed_task_type: development.develop
>   acceptance_criteria:
>     - {check: endpoint_defined, file: backend/routes.py, methods_paths: [[POST, /runs/{id}/join]], severity: error}
> ```
>
> Eve proposes:
> ```yaml
> - proposal_task_id: qa.backend.join_tests
>   proposed_task_type: qa.test
>   acceptance_criteria:
>     - {check: regex_match, file: tests/test_backend.py, pattern: "status_code\\s*=\\s*409", count_min: 1, severity: error}
>   symbolic_depends_on: [dev.api.join]
> ```
>
> **Merger result:**
> - Two canonical tasks emitted (different domain owners, different surfaces — non-overlapping).
> - `dev.api.join` becomes `task_index: 1` owned by `development`. Acceptance carries Neo's `endpoint_defined`.
> - `qa.backend.join_tests` becomes `task_index: 2` owned by `qa`. Acceptance carries Eve's `regex_match`. `depends_on: [1]` (resolved from `symbolic_depends_on: [dev.api.join]`).
> - `merge_decisions.yaml` records both as `merge_action: accepted` with `proposed_by` set correctly.

### 5.9 Proposal completeness classification

The merger emits a required field on `merge_decisions.yaml`:

`proposal_completeness: complete | partial | fallback`

- **`complete`** — every expected role's proposal/guidance artifact arrived and parsed.
- **`partial`** — at least one expected proposal/guidance artifact was missing or failed to parse. The merger continues with surviving proposals.
- **`fallback`** — all proposals failed; merger fell back to single-author plan production (§5.10).

**Required warnings recorded in `merge_decisions.yaml` operator_notes:**
- Missing QA proposal → "QA coverage warning: plan was authored without qa-domain input."
- Missing dev proposal → "Implementation decomposition warning: plan was authored without dev-domain input."
- Missing strategy guidance → "Ordering/priority warning: plan ordering was assigned without strategy guidance."
- Missing build proposal (when builder enabled) → "Build/assembly warning: plan was authored without build-domain input."

The gate evaluation slices on which roles were missing — those signals matter differently. The classification enum is intentionally three-state; richer breakdown lives in `missing_proposals` and operator notes.

### 5.10 Fallback behavior (narrowed)

A role that fails to produce a proposal (LLM error, timeout, malformed YAML) does not block the merger. The merger proceeds with whatever proposals succeeded and records the missing role(s) in `merge_decisions.yaml`. This is `proposal_completeness: partial`.

**Fallback to single-author plan production is invoked only when *all* role proposals fail.** When fallback fires:

- `authoring_mode: fallback_single_author`
- `proposal_completeness: fallback`
- `missing_proposals: [development, qa, strategy, ...]` listing every failed proposal with its failure reason.
- The canonical plan is produced by Max running today's `_produce_plan` logic (the M1 substrate's plan-authoring path inside `governance.review_plan`, extracted into a shared `PlanAuthoringService` per the SIP-0092 plan doc M2.1).
- `merge_decisions.yaml` is still emitted, recording the fallback explicitly.
- Fallback status is surfaced at gate (operator must see when the cycle silently degraded to single-author).
- Fallback frequency is a tracked gate metric (M2→M3 gate criterion C2: sole-author fallback rate must stay <20% per `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` Gate M2→M3).

The system must not silently appear to use multi-role authoring when it actually fell back to one author.

### 5.11 Framing sequence under this SIP

```
data.research
  → strategy.frame
    → development.design_plan
      → qa.define_test_strategy
        → governance.prepare_plan_authoring_brief        (NEW — produces plan_authoring_brief.yaml)
          → development.propose_plan_tasks    ┐
          → qa.propose_plan_tasks             ├─ in parallel
          → strategy.propose_plan_guidance    │
          → build.propose_plan_tasks          ┘  (only when builder role enabled)
            → governance.merge_plan                       (NEW — produces implementation_plan.yaml + merge_decisions.yaml)
              → governance.review_plan                    (sign-off only — see §5.6 ownership of gate-readiness)
                → [GATE]
```

The propose-tasks fan out in parallel (no inter-dependencies) so wall-clock cost grows additively with the slowest proposer, not the sum of all proposers.

### 5.12 Builder / Bob behavior

Bob (builder role, SIP-0071) is profile-gated:

- **5-agent squad (no builder):** Neo owns build/assembly proposals via `development.propose_plan_tasks`. No `build.propose_plan_tasks` runs.
- **6-agent squad (builder enabled):** Bob contributes `build.propose_plan_tasks` covering packaging, app startup, integration wiring, build-system glue, runnable commands, and deployment/start scripts. Neo's scope shrinks correspondingly to component implementation.

Bob is **optional and not required for Rev 1.** Rev 1 ships with the three-role contributor set (development, qa, strategy). The builder hook is a Rev 2 extension once the multi-role backbone has shown stability. This avoids overfitting the base SIP to the 6-agent squad while preserving the extension point.

Implementation note: agent proper names ("Neo", "Eve", "Bob") appear in this SIP body for design-doc readability. Handler/task IDs use role identifiers (`development`, `qa`, `build`); per repo convention, source code does not embed proper names.

### 5.13 M3 diagnostic preservation

Replacing M2-as-originally-written must not drop the evidence the M2→M3 gate needs.

The non-operative `structural_plan_change_candidate` field on `governance.correction_decision` (allowed values `none | add_task | tighten_acceptance | other`) continues to be elicited by the correction LLM. It is not affected by SIP-0093 — `governance.correction_decision` is a build-phase handler, orthogonal to plan authorship. The diagnostic was added in the SIP-0093-prep cluster (commit `9657449`) and remains in place.

The M2→M3 gate criteria amended in PR #135 explicitly note this criterion as "unchanged from the original gate." See `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` §"Gate M2 → M3."

## 6. Cost analysis

Multi-role authoring adds LLM calls to the framing tail.

| Authoring model | Framing-tail LLM calls | Critical-path calls |
|----|----|----|
| M1 substrate (today) | 1 (sole authoring inside `review_plan`) | 1 |
| SIP-0093 (this SIP) | N+2 (brief + N parallel proposers + merger) | 3 (brief, then slowest proposer, then merger) |

Where N is the number of contributing role proposers (3 in Rev 1: dev, qa, strategy; 4 if builder is enabled).

**Wall-clock cost depends on hardware throughput.** For Spark-class hardware (per `reference_spark_gpu.md`: ~16 tps at 27B, ~68 tps at 7B):

- Brief at 32B: ~30–60s for a 600–1200 token output.
- Each proposer at 32B: ~2–4 min for typical proposal sizes.
- Merger at 32B: ~2–4 min.
- **Critical-path estimate:** ~5–9 minutes vs ~2–4 minutes for the M1 substrate's single call. Roughly 2–3× framing-tail cost.

**Why this is acceptable:**
- Long cycles (≥2h budgets per the validation profile) absorb a ~5-minute increase in framing tail without meaningfully shifting the build budget.
- The cost is paid once per cycle, not per task.
- The fallback (§5.10) reverts to M1-substrate cost when all proposals fail, so the worst case is "same as today."

**Why not free:**
- Short cycles (selftest, smoke) gain little from multi-role authoring and pay full overhead. Default `multi_role_plan_authoring: false` keeps these on the M1 substrate.
- The brief author (Max at 32B) is a serial dependency before the parallel fan-out; if the brief takes longer than expected, the whole framing tail slows.

**Telemetry:** PR 93.5 ships authoring duration metrics so the cost model is observable, not hypothesized.

## 7. Configuration

**Two flags. No three-by-two routing matrix.** Per the no-dual-path-flags principle, `split_implementation_planning` (the original M2 flag) is removed; SIP-0093 is the single forward path with a master-switch flag.

| Key | Type | Default | Purpose |
|----|----|----|----|
| `multi_role_plan_authoring` | `bool` | `false` | Master switch. False → M1 substrate (today's colocated authoring inside `governance.review_plan`). True → SIP-0093 flow. |
| `plan_authoring_contributors` | `list[str]` | `["development", "qa", "strategy"]` | Which role proposers fan out. Omitting `qa` runs without QA proposals (`proposal_completeness: partial`). Adding `build` enables the builder hook (§5.12) when the squad has it. |

**Removed flags** (no longer relevant once SIP-0093 lands as M2 path):
- `split_implementation_planning` — superseded by `multi_role_plan_authoring`.
- `max_planning_revisions` — there is no revision loop in SIP-0093.

**Always-true behavior** (not configurable, to prevent broken configurations):
- Fallback-to-single-author when all proposals fail (§5.10) — must always be true; making it optional invites silent cycle-kill.
- Merger emits `merge_decisions.yaml` — auditability is not optional.

## 8. Implementation PR sequence

Five PRs. Independently reviewable. Each preserves prior behavior under `multi_role_plan_authoring: false`.

### PR 93.0 — Brief schema and `governance.prepare_plan_authoring_brief` handler

Land the brief schema and brief-producing handler before any proposer work. Lets the brief flow be validated end-to-end before scaling proposer parallelism.

**Deliver:**
- `plan_authoring_brief.yaml` schema with the six required Rev 1 fields.
- `PlanAuthoringBrief` frozen dataclass + `from_yaml()` parser.
- `GovernancePreparePlanAuthoringBriefHandler` task type.
- Integration test: handler produces a parseable brief from seeded framing inputs.

### PR 93.1 — Proposal and merge schemas

**Deliver:**
- `ProposedPlanTasks` (already partially landed in `src/squadops/cycles/proposed_role_tasks.py` — extend to schema described in §5.4.1).
- `PlanGuidance` for strategy artifacts (§5.4.2).
- `MergeDecisions` for §5.7.
- Symbolic-dependency convention enforced by parser (rejects final numeric indices in `symbolic_depends_on`).
- `brief_conflicts` model (§5.5).
- Per-canonical-task provenance model.

### PR 93.2 — Role proposer handlers

**Deliver:**
- `development.propose_plan_tasks` handler.
- `qa.propose_plan_tasks` handler.
- `strategy.propose_plan_guidance` handler.
- Config-gated parallel fan-out from `task_plan.py`.
- Proposal failure handling (§5.10 partial-completeness path).
- Reuses `PlanAuthoringService` infrastructure from the SIP-0092 plan doc M2.1 extraction.

### PR 93.3 — Governance merge handler

**Deliver:**
- `governance.merge_plan` handler.
- Deterministic merge policy (§5.8) including the worked-example test case.
- Canonical `implementation_plan.yaml` output with merger-assigned indices.
- `merge_decisions.yaml` output with per-canonical-task provenance.
- Symbolic-to-numeric dependency resolution.

### PR 93.4 — Fallback, gate integration, observability

**Deliver:**
- Single-author fallback path (§5.10) reusing the extracted `PlanAuthoringService`.
- Proposal completeness classification (§5.9).
- Merge quality warnings populated from `merge_decisions.yaml`.
- Gate package: canonical plan + `merge_decisions.yaml` + `plan_authoring_brief.yaml`.
- Authoring duration, proposal completeness, merge conflict, and fallback frequency metrics.

## 9. Acceptance criteria (structural)

These are the structural criteria for the SIP itself. Per-PR acceptance criteria and gate-evaluation criteria live in the implementation plan doc (`docs/plans/SIP-0093-multi-role-plan-authoring-plan.md`, to be drafted).

1. Multi-role authoring is config-gated by a single master flag (`multi_role_plan_authoring`), default-off.
2. A shared `plan_authoring_brief.yaml` is produced before proposal fan-out and consumed by every proposer.
3. Proposals are domain-scoped; no proposer authors a complete plan; no proposer assigns final task indices.
4. Strategy contributes guidance, not fake tasks (`plan_guidance.yaml`, not `proposed_plan_tasks.yaml`).
5. Cross-proposal dependencies use symbolic IDs, not final numeric indices.
6. The merger produces one canonical `implementation_plan.yaml` validating against the SIP-0092 M1 schema.
7. The merger emits `merge_decisions.yaml` recording per-canonical-task provenance and brief-conflict dispositions.
8. Proposal failures degrade gracefully and are recorded; partial completeness is visible at gate.
9. All-proposal failure falls back to single-author production and is explicitly marked (`authoring_mode: fallback_single_author`).
10. The `structural_plan_change_candidate` diagnostic on `governance.correction_decision` remains emitted.
11. Final task indices are assigned only by the merger.
12. Typed acceptance criteria from proposals survive merge.

## 10. Tests

The full test inventory lives in the implementation plan doc. Critical tests called out here:

**The single most important test in the suite:** "Eve proposes a QA task Neo omitted; merged plan includes it." This is the test that proves the multi-role architecture is doing real work, not just adding LLM calls. **Required gate criterion** — if this scenario can't be reproduced in regression, SIP-0093 isn't done.

**Other essential tests:**

- Brief parser rejects malformed brief; proposers reject proposals with mismatched `source_brief_id`.
- Proposal parser rejects final numeric task indices in `symbolic_depends_on`.
- Strategy guidance parser does not require `PlanTask` shape.
- Domain-owner conflict policy (§5.8 rule 1) behaves deterministically — same inputs produce same canonical plan.
- Compatible acceptance criteria from dev and qa survive merge on the same canonical task.
- Missing proposal is recorded in `merge_decisions.yaml` with `proposal_completeness: partial` and the specific role flagged.
- All-proposals-failed triggers `authoring_mode: fallback_single_author` and emits a `merge_decisions.yaml` recording every failure reason.
- Final canonical plan has valid contiguous task indices.
- Brief conflicts (warning vs blocking) are accepted/rejected/escalated and recorded.
- Gate package includes `implementation_plan.yaml`, `merge_decisions.yaml`, and `plan_authoring_brief.yaml` (operator-visible artifacts).
- Worked-example merge from §5.8 passes deterministically.

Per `docs/TEST_QUALITY_STANDARD.md`: every assertion on absence/presence is paired with a content assertion (e.g., "missing proposal is recorded" must assert *what* is recorded, not just that something is).

## 11. Relationship to SIP-0092

SIP-0093 is the M2 implementation path for SIP-0092. SIP-0092 §6.2 describes Capability M2 — Separated Plan Authoring; SIP-0093 implements that capability via shared brief → parallel domain proposals → governed merge.

SIP-0092 M1 (typed acceptance) is the substrate SIP-0093 builds on: every proposed task carries M1 typed acceptance criteria, merged criteria validate against M1's schema, and the merger's canonical plan validates against the M1 `ImplementationPlan` schema unchanged.

SIP-0092 M3 (plan changes) is orthogonal to plan authorship. SIP-0093 changes who authors the original plan; M3 governs how that plan can evolve in-cycle. The `structural_plan_change_candidate` diagnostic that bridges M2 to M3 is preserved (§5.13).

The SIP-0092 §6.2 spec was rewritten to describe the SIP-0093 design as the M2 implementation, replacing the original Neo-authors / Max-reviews design. The original M2 design lives in git history.

## 12. Future Work

- **Per-role plan-change authoring at correction time.** Once SIP-0092 M3 ships, an aggregate equivalent for plan changes (each role can propose a `tighten_acceptance` or `add_task` plan change in their domain; merger integrates).
- **Proposer competition.** Run two proposers per role with different prompts; merger picks the better proposal per task. Hedge against single-LLM bad-day failures.
- **Operator-visible per-role contribution surface.** Console UI shows which role proposed each plan task; operator can override or revert per-role contributions at gate.
- **Adaptive proposer selection.** Once telemetry exists (cycle scorecard), enable/disable proposers per cycle based on proposal acceptance rate.
- **Builder role contributor (`build.propose_plan_tasks`)** — Rev 2 extension once multi-role backbone is stable.
- **Brief revision loop.** A single-pass brief-conflict-resolution loop where blocking conflicts trigger a brief revision before merge. Rev 1 escalates to operator instead.

## 13. References

- `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` — parent design; SIP-0093 is the M2 implementation path per §6.2.
- `sips/implemented/SIP-0086-Build-Convergence-Loop-Dynamic.md` — original implementation plan introduction (the artifact this SIP modifies authorship of).
- `docs/plans/1-0-x-build-reliability-hardening-plan.md` — broader context: long-cycle coherence is the hardening axis.
- `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` — Gate M2→M3 criteria (PR #135 amendment) measure SIP-0093's behavior directly.
- `docs/plans/SIP-0092-gate-M1-evaluation.md` — the M1→M2 gate evaluation that selected the multi-role authoring path.
- `examples/03_group_run/prd.md` — the canonical reference PRD this SIP would author plan tasks for.
