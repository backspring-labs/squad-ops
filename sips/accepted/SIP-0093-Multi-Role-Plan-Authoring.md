---
title: Multi-Role Plan Authoring
status: accepted
author: SquadOps Architecture
created_at: '2026-04-30T00:00:00Z'
sip_number: 93
updated_at: '2026-05-05T14:50:27.218672Z'
---
# SIP-0XXX: Multi-Role Plan Authoring

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-04-30
**Revision:** 1
**Relationship:** Replaces **SIP-0092 M2** (Separated Plan Authoring). Drafted while implementing SIP-0092 M1 on PR #72. Per the M1→M2 gate evaluation (`docs/plans/SIP-0092-gate-M1-evaluation.md`) and the maintainer's 2026-05-05 path-forward decision, this SIP supplants M2-as-written: M2's deliverables (proposer/judge decoupling, structured concerns, revision loop, `structural_plan_change_candidate` diagnostic) are absorbed across a sub-sequence of PRs on this SIP's multi-author backbone instead of M2's sole-broker design.

## 1. Abstract

The implementation plan (SIP-0092) decomposes a build into role-typed subtasks. Today (M1) one agent — Max, the lead — both produces and approves the plan. SIP-0092 M2 splits authoring out: Neo (dev) authors, Max reviews. This SIP proposes a different split: each role independently *contributes* plan tasks for their own domain, and Max *merges* the contributions into the canonical implementation plan. The framework already has multi-agent infrastructure; this SIP uses it for the artifact that most benefits from cross-role perspective.

## 2. Problem Statement

Both M1 (Max sole broker) and SIP-0092 M2 (Neo sole broker) have the same structural property: **one agent synthesizes the entire plan from the framing-phase outputs of all roles.** That single agent reads research, frame, design plan, and test strategy as `prior_outputs`, then writes the decomposition.

Three concerns with sole-broker authoring:

- **Single-perspective bias.** The sole author's role colors the decomposition. Max biases toward governance concerns; Neo biases toward implementation framing. QA's view of how the build should decompose to maximize testability never enters the plan directly — only via the prior `qa.define_test_strategy` output that the sole author chooses to interpret.
- **Cross-cutting coverage gaps.** A plan decomposition that doesn't aggregate role expertise can miss the integration points where roles collide: testability of dev components, security review of risky paths, performance benchmarks, infrastructure provisioning. Today these only enter the plan if the sole author thinks to include them.
- **Coupling to current task vocabulary.** The "Neo authors" choice in SIP-0092 M2 is plausible *because* the Rev 1 task vocabulary is mostly `development.develop` + `qa.test`. The moment we add task types — security review, performance benchmark, infra setup — the dev-only authoring model strains.

The 1.0.x hardening plan's broader theme is "the squad stays coherent over a long cycle." Sole-broker plan authoring is a coherence single-point-of-failure that compounds with cycle length: the longer the cycle, the more the sole author's bias has time to amplify into wrong-shape work.

## 3. Goals

1. **Distribute plan authorship across roles** so each role's expertise directly shapes the part of the plan it best understands.
2. **Preserve a single canonical implementation plan artifact** — operators and the executor still consume *one* plan, not N proposals.
3. **Keep the lead agent in the broker / merger position** so cross-role conflicts have an explicit resolver, matching real-world planning patterns (sprint planning with PM, design, engineering, QA participation).
4. **Bound coordination cost** — the propose-merge pattern must not balloon framing-phase LLM call counts beyond what long cycles can afford.
5. **Compose with SIP-0092 M1's typed acceptance** — each role's contribution carries its own typed acceptance criteria for the tasks it proposes.
6. **Compatible with SIP-0092 M3 plan changes** — multi-role authoring applies at framing time; in-cycle plan changes (M3) remain governed by the correction protocol.

## 4. Non-Goals

- Replacing the framing sequence (`data.research → strategy.frame → development.design_plan → qa.define_test_strategy → governance.<merge> → GATE`). Those steps are still the framing scaffolding; this SIP only changes who authors the plan within them.
- Distributing review or gate decisions. The merger/lead still owns the gate-readiness call.
- Implementing per-role plan-change authoring at correction time. SIP-0092 M3's correction-driven plan changes stay autonomous-correction-only.
- Producing N separate operator-visible artifacts. The squad shows the operator one plan; per-role proposals are intermediate artifacts.

## 5. Approach Sketch

### 5.1 New propose-task-type per contributing role

Each contributing role gets a `propose_plan_tasks` task type. Rev 1 contributors:

| Role | Task type | Contribution |
|---|---|---|
| Neo (dev) | `development.propose_plan_tasks` | Component decomposition, expected_artifacts, dependency edges, dev-side typed acceptance |
| Eve (qa) | `qa.propose_plan_tasks` | Test subtasks, qa-typed acceptance over dev artifacts (e.g., test-count `regex_match`), coverage strategy |
| Nat (strategy) | `strategy.propose_plan_tasks` | Ordering / priority hints, time-budget allocation per subtask |

`data.research` does not contribute plan tasks directly — its role is upstream context, and asking Data to propose subtasks risks scope creep.

Each propose-task receives the same `prior_outputs` upstream artifacts as today's sole-author task receives. Output is a `proposed_plan_tasks.yaml` artifact: a list of `PlanTask`-shaped entries scoped to that role's domain.

### 5.2 New merger task: `governance.merge_plan`

Max receives all `proposed_plan_tasks.yaml` artifacts as inputs and produces the canonical implementation plan by:

1. **Deduplicating** overlapping tasks across role proposals (e.g., Neo proposes "tests for endpoints"; Eve proposes the same — Eve's wins because it's qa-domain).
2. **Resolving conflicts** in dependency edges, role assignment, or acceptance criteria. Conflicts are recorded in a `merge_decisions.yaml` artifact for operator visibility at gate.
3. **Filling gaps** — e.g., if Eve's proposal references a dev component Neo didn't propose, the merger flags it and either adds the component or escalates.
4. **Renumbering** task indices to produce the canonical 0..N sequence.

The output is still a single `implementation_plan.yaml` with the SIP-0092 M1 schema. No format change.

### 5.3 Framing sequence under this SIP

```
data.research
  → strategy.frame
    → development.design_plan
      → qa.define_test_strategy
        → development.propose_plan_tasks      ┐
        → qa.propose_plan_tasks               ├─ in parallel
        → strategy.propose_plan_tasks         ┘
          → governance.merge_plan             ← canonical plan + merge_decisions.yaml
            → [GATE]
```

The propose-tasks fan out in parallel (no inter-dependencies) so wall-clock cost grows additively with the slowest proposer, not the sum of all proposers.

### 5.4 Fall-back behavior

A role that fails to produce a proposal (LLM error, timeout, malformed YAML) does not block the merger. The merger receives whatever proposals succeeded and notes the missing role in `merge_decisions.yaml`. This preserves single-point-of-failure protection — one bad LLM call doesn't kill the cycle.

If *all* proposals fail, the merger falls back to sole authorship using the same prompt as SIP-0092 M2's `development.plan_implementation`. This is the SIP-0092-M2-equivalent fallback, ensuring this SIP is never strictly worse than M2.

## 6. Comparison to SIP-0092 M2

| Dimension | M1 (today) | SIP-0092 M2 | This SIP |
|---|---|---|---|
| Author count | 1 (Max) | 1 (Neo) | N (one per contributing role) |
| Reviewer / merger | Implicit (Max self-reviews) | Max (separate task) | Max (merges, plus reviews via SIP-0092 M2's review step if both ship) |
| LLM calls in framing tail | 1 | 2 (author + review) | N+1 (parallel propose + merge) |
| Per-role direct expertise in plan | Indirect | Indirect | **Direct** |
| Resilience to single-LLM failure | None | Reviewer catches some | Failed proposals don't block; merger absorbs survivors |
| Design assumption | Single broker is sufficient | Authoring and reviewing are different cognitive tasks | Multi-perspective decomposition is better than single-perspective |

This SIP is *compatible* with SIP-0092 M2: the merger step can run M2's review-and-revise loop after producing the canonical plan, giving both multi-role authorship *and* a structured reviewer pass. Or it can replace M2 entirely by treating the merger as both author-broker and reviewer.

## 7. Open Questions

- **Conflict resolution policy.** When Neo and Eve propose the same task with different acceptance criteria, what's the merger's rule? Strictest-wins? Domain-owner-wins (Eve for qa, Neo for dev)? Operator pre-declared? Needs design.
- **Strategy's contribution shape.** Nat proposing ordering/priorities is shaped differently from Neo and Eve proposing tasks. Is `strategy.propose_plan_tasks` actually `strategy.propose_priorities` (with no full task list)? Probably yes; the merger then applies the priorities to dev/qa tasks.
- **Builder role in non-trivial squads.** SIP-0071's Bob (builder) handles assembly/packaging. Does Bob also propose plan tasks for assembly subtasks, or does Neo cover that today? Probably Bob in the 6-agent squad, Neo in the 5-agent squad.
- **Cost vs. value at low cycle counts.** N+1 LLM calls is a real cost; for short cycles, M2's 2 calls may be sufficient. Should the propose-merge protocol be config-gated? Probably yes (`multi_role_plan_authoring: true|false`), default off until evidence supports it.
- **Interaction with SIP-0092's M1 → M2 gate criterion 3** ("plan defects detectable from plan + PRD before build execution"). If this SIP ships *instead of* M2, the M1 → M2 gate's reviewer-related criteria need re-framing — there's no separate reviewer to evaluate.

## 8. Relationship to SIP-0092

This SIP is drafted as an **alternative** to SIP-0092 M2's authoring split, not a replacement for SIP-0092 as a whole. SIP-0092 M1 (typed acceptance) and M3 (plan changes) are orthogonal to who authors the plan and remain valid regardless of which authoring model lands.

Three paths the M1 → M2 gate evaluation can take after SIP-0092 M1 ships:

1. **Ship SIP-0092 M2 as written** — Neo authors, Max reviews. Sole-broker model preserved.
2. **Ship this SIP instead of SIP-0092 M2** — multi-role propose, Max merges. Sole-broker model replaced.
3. **Ship neither yet** — keep M1's combined-author/reviewer for now; revisit when long-cycle evidence supports a split.

The SIP-0092 M1 → M2 gate evaluation doc (`docs/plans/SIP-0092-gate-M1-evaluation.md`) is the natural decision point: with this SIP on the table, the gate's "is M2 needed?" question becomes "is *some* authoring change needed, and if so, which model?"

## 9. Future Work

- **Per-role plan-change authoring at correction time.** Once SIP-0092 M3 ships, an aggregate equivalent for plan changes (each role can propose a `tighten_acceptance` or `add_task` plan change in their domain; merger integrates).
- **Proposer competition.** Run two proposers per role with different prompts; merger picks the better proposal per task. Hedge against single-LLM bad-day failures.
- **Operator-visible per-role contribution surface.** Console UI shows which role proposed each plan task; operator can override or revert per-role contributions at gate.
- **Adaptive proposer selection.** Once telemetry exists (cycle scorecard), enable/disable proposers per cycle based on proposal acceptance rate.

## 10. References

- `sips/accepted/SIP-0092-Implementation-Plan-Improvement.md` — parent design; this SIP is an alternative to M2.
- `sips/implemented/SIP-0086-Build-Convergence-Loop-Dynamic.md` — original implementation plan introduction (the artifact this SIP modifies authorship of).
- `docs/plans/1-0-x-build-reliability-hardening-plan.md` — broader context: long-cycle coherence is the hardening axis.
- `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` — Milestone Gates section names this SIP as a candidate alternative for the M1 → M2 gate evaluation.
- `examples/03_group_run/prd.md` — the canonical reference PRD this SIP would author plan tasks for.
