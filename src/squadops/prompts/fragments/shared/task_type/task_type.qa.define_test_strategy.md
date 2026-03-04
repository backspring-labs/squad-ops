---
fragment_id: task_type.qa.define_test_strategy
layer: task_type
version: "0.9.16"
roles: ["qa"]
---
## QA Test Strategy (Planning Workload)

You are defining the test strategy for a planning workload. This is Stage A
maturity — no full test suite is expected. Your goal is to establish the
verification approach for implementation.

### Deliverables

1. **Acceptance checklist** — concrete pass/fail criteria derived from the
   objective frame's acceptance criteria
2. **Test strategy note** — how the implementation will be verified (unit,
   integration, contract, E2E scope decisions)
3. **Defect severity rubric** — classification scheme for issues found
   during implementation
4. **Risk-based test priorities** — which areas need the most coverage

### Stage A Maturity

At planning time, you define *what* to test and *how*, not the actual tests.
Test files are produced during the implementation workload, not here.

### Output Format

Produce a structured markdown document (`test_strategy.md`). The acceptance
checklist should be formatted as a markdown checklist that can be used
directly during implementation review.
