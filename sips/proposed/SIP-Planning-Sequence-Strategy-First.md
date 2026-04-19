# SIP-0XXX: Planning Sequence — Strategy Before Research

**Status:** Proposed (stub)
**Authors:** SquadOps Architecture
**Created:** 2026-04-19
**Revision:** 1

## 1. Abstract

`PLANNING_TASK_STEPS` in `src/squadops/cycles/task_plan.py` currently runs `data.research_context` before `strategy.frame_objective`. This inverts the natural dependency: data should research *against a framed question*, not produce generic context that strategy then ingests. The proposal: swap the first two steps so strategy frames the objective first, then data researches in service of that frame.

## 2. Problem Statement

Current order (SIP-0078):

```python
PLANNING_TASK_STEPS = [
    ("data.research_context", "data"),       # ← first
    ("strategy.frame_objective", "strat"),
    ("development.design_plan", "dev"),
    ("qa.define_test_strategy", "qa"),
    ("governance.assess_readiness", "lead"),
]
```

Issues observed during SIP-0086 validation cycles:

- **Research without a framing question is fishing.** Data produces broad domain context before anyone has articulated what the project is trying to achieve. For well-defined PRDs (e.g., `play_game`), this adds little — the PRD already contains the relevant context.
- **Inverted leverage.** On `spark-squad-with-builder`, Data runs qwen2.5:7b (weakest model) first. Nat (32b) then ingests that weakest-first-pass research as context for objective framing. The higher-leverage step should come first.
- **Template coupling.** Nat's `frame_objective` prompt reads `prior_outputs` from data by convention. Any reorder must swap the direction of this dependency (data reads from strat).

## 3. Proposed Order

```python
PLANNING_TASK_STEPS = [
    ("strategy.frame_objective", "strat"),   # Nat: what/why/who, from the PRD
    ("data.research_context", "data"),       # Data: answers to Nat's raised questions
    ("development.design_plan", "dev"),      # Neo: how to build it
    ("qa.define_test_strategy", "qa"),       # Eve: how to verify
    ("governance.assess_readiness", "lead"), # Max: consolidate + manifest
]
```

## 4. Open Questions

- **Research-heavy domains.** For projects where broad domain scan genuinely precedes framing (e.g., novel science, medical, legal), data-first may be warranted. Should the sequence be configurable via an `applied_defaults` key (e.g., `planning_sequence: strategy_first | data_first`)?
- **Template rewiring.** `strategy.frame_objective`'s prompt assumes data has run and currently pulls from `prior_outputs["data"]`. Swap requires updating both prompts (Nat reads from PRD only; Data reads from `prior_outputs["strat"]`).
- **Backward compat.** Existing `planning` workload runs reference task_ids derived from step index. Reordering changes stable IDs — resume/checkpoint compatibility with in-flight runs needs a plan.

## 5. Non-Goals

- Not changing which planning tasks exist, only their order.
- Not changing the implementation/build/correction/wrapup sequences (different SIPs).

## 6. References

- `src/squadops/cycles/task_plan.py` — `PLANNING_TASK_STEPS` definition
- `src/squadops/capabilities/handlers/planning_tasks.py` — prompt templates with cross-role `prior_outputs` reads
- SIP-0078 — original planning workload protocol that defined the current order
- SIP-0086 validation cycle `cyc_ecc88f0bdcd5` — empirical observation motivating this change
