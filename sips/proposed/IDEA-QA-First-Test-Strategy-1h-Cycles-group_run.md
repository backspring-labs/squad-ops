# IDEA — QA-First Test Strategy for 1-Hour SquadOps Cycles (group_run Focus)

## Status
Draft

## Summary
Define a practical QA-first strategy for early **1-hour SquadOps execution cycles** (especially for `group_run`) that avoids rigid “write all tests first” behavior and instead prioritizes **acceptance alignment, fast validation, and low-thrash feedback loops**.

This IDEA proposes a **hybrid QA-first model**:

- QA prepares **acceptance checks first** (lightweight and PRD-aligned)
- Bob/Dev implement a bounded vertical slice
- QA validates and reports defects
- Automated tests expand **after behavior stabilizes**

This approach is designed to improve first-run success rates while still preserving a path toward stronger test discipline over time.

---

## Why This IDEA Exists
A common instinct is to ask whether QA should “write tests first” before implementation begins.

That instinct is useful (it pushes toward rigor), but for **early autonomous runs with short time budgets (e.g., 1 hour)**, requiring QA to write a full test suite first can create:

- brittle tests against changing implementation details
- rework when routes/labels/data shapes change mid-run
- false failures that consume cycle time
- delayed feedback on actual runability and user flows

For early SquadOps maturity, the better question is:

> What should QA produce first to maximize alignment and useful signal inside a short cycle?

---

## Core Recommendation
For early 1-hour runs, QA should **not** be required to write a complete automated test suite first.

### Instead, QA should produce first:
1. **Acceptance Checklist (required)**
2. **Test Strategy Note (short)**
3. **Optional Smoke Test Skeleton** (only if implementation surface is stable enough)

This preserves QA-first alignment without forcing brittle automation too early.

---

## Design Goal
Optimize short-run success for:

- **runability**
- **one working happy path**
- **fast defect detection**
- **clean defect/fix loop**
- **clear evidence for Pulse Checks**

Not completeness of test automation.

---

## Assumptions
This IDEA assumes:

- A **Micro-PRD / execution brief** exists for the cycle and defines a bounded MVP slice
- The squad is operating with a core role set (Lead, Strategy, Dev, QA, Data) plus Bob as dedicated builder
- The goal is a **solid attempt** in a short autonomous run (1+ hour), not final production hardening

If a Micro-PRD is not present, QA acceptance checks will be weaker and more subjective.

---

## What QA Should Do First (v1 Guidance)

### 1) Acceptance Checklist (Required)
QA derives a short, concrete checklist from the Micro-PRD acceptance criteria.

This is the most important “tests first” artifact in early runs.

#### Characteristics
- PRD-aligned
- QA-verifiable
- concise
- focused on the happy path
- stable even if implementation details shift

#### Example (group_run 1-hour cycle)
- App starts with documented command
- Main route loads without error
- User can create a group (mock/local persistence acceptable)
- User can view at least one run item
- App does not crash during happy-path flow
- QA can record evidence of the result

This gives Bob/Dev a target and gives Lead a gateable validation baseline.

---

### 2) Test Strategy Note (Short)
QA should create a brief note describing how validation will be performed in this cycle.

#### Recommended contents
- What will be **manual** this cycle
- What could be **automated** later
- What evidence QA will capture
- What constitutes a blocker vs non-blocker
- Any assumptions (stack, routes, startup command, mock data allowed)

This helps prevent surprises and avoids overcommitting to automation before the app stabilizes.

---

### 3) Optional Smoke Test Skeleton (Conditional)
If stack, route names, and startup flow are stable enough, QA may prepare a basic smoke test scaffold early.

Examples:
- test file skeleton
- placeholder smoke flow
- command structure for future execution

#### Important constraint
Do **not** spend large amounts of early cycle time building brittle tests against uncertain implementation details.

This is optional for early runs and should be time-boxed.

---

## Why “Write All Tests First” Is Too Rigid for Early 1-Hour Runs
In short autonomous runs, these details often move during implementation:

- routes
- labels
- UI structure
- data shape
- startup/config wiring

If QA fully automates too early, likely outcomes include:

- tests failing due to harmless implementation shifts
- wasted QA effort rewriting tests
- Bob/Dev thrash reacting to unstable assertions
- less time spent proving the app actually works

This is not an argument against test-first discipline.
It is an argument for **staged test-first discipline** matched to SquadOps maturity and cycle duration.

---

## Recommended QA-First Strategy by SquadOps Maturity Stage

### Stage A — Early Long-Run Maturity (Current Recommendation)
**Goal:** Get a successful autonomous build/validate loop working.

#### Flow
- QA prepares acceptance checklist + short strategy note
- Bob/Dev implement a bounded vertical slice
- QA validates manually / with lightweight checks
- QA reports defects with evidence
- QA (and/or Bob/Dev) add tests once behavior stabilizes

#### Why this works
- maximizes usable feedback
- minimizes brittle test thrash
- improves odds of completing one happy path in a short cycle

---

### Stage B — Intermediate Maturity
**Goal:** Increase repeatability and faster regression detection.

#### Flow
- QA writes smoke tests first (targeted and stable)
- Bob implements to pass smoke expectations
- Dev supports integration/tooling
- QA expands regression checks for implemented flows

#### Characteristics
- stronger automation
- less manual-only validation
- still scoped to stable surfaces

---

### Stage C — Higher Maturity
**Goal:** Tighten reliability, contracts, and automated gating.

#### Flow
- contract/smoke checks first
- feature test automation in parallel with implementation
- regression suite enforced at Pulse Checks
- stronger gate decisions driven by evidence

#### Characteristics
- more deterministic cycle outcomes
- greater upfront testing investment
- better suited to longer and more complex runs

---

## Test Ownership Split (Recommended)
Rather than “QA writes every test first,” split test ownership by test type.

### QA owns
- Acceptance tests/checklists
- Smoke/e2e validation (manual and automated as maturity increases)
- Defect reproduction steps
- Regression verification
- Severity and gate recommendations

### Bob/Dev own
- Unit tests
- Component tests
- Implementation-level checks
- Build/lint/self-check execution
- Fix verification at code level before handoff

This division supports specialization and reduces role confusion.

---

## Practical `group_run` 1-Hour Run Pattern (QA-Focused View)

### Before implementation starts
QA creates:
- acceptance checklist (required)
- short validation strategy note
- defect severity rubric (recommended)
- optional smoke skeleton (if stable enough)

### During implementation
- Bob builds feature slice
- Dev handles integration/tooling/stabilization
- QA monitors for readiness and clarifies acceptance expectations if needed

### Validation phase
QA executes:
- happy-path checks
- startup/runability checks
- evidence capture (logs/screenshots/command outputs)
- defect reports (severity + repro)

### If time remains
- add/expand smoke automation around stabilized behaviors
- document regression checks for next cycle

---

## Suggested Defect Severity Rubric (Simple v1)
QA should classify defects to speed Lead decisions at Pulse Check.

### Sev 1 — Blocker
- app does not start
- main route/crucial flow unavailable
- crash on primary happy path

### Sev 2 — Major
- key feature partially broken
- incorrect behavior in main flow
- workaround exists but acceptance criteria at risk

### Sev 3 — Minor
- UI/copy issue
- non-critical edge case
- polish defect not affecting happy path completion

This helps Lead decide continue / rework / defer.

---

## Capability Implications for Agents (What to Develop)

### QA Agent capabilities needed (priority)
- derive acceptance checklist from Micro-PRD
- write concise validation strategy notes
- execute smoke/manual checks quickly
- produce structured defect reports (severity + repro + evidence)
- recommend gate outcomes
- optionally scaffold smoke automation when stable

### Bob Agent capabilities needed
- consume acceptance checklist
- produce run instructions and known limitations
- self-check build/test/lint before handoff
- stay within scoped feature slice

### Dev Agent capabilities needed
- stabilize startup/integration issues quickly
- repair config/tooling blockers
- support testability and reproducibility

### Lead Agent capabilities needed
- protect scope
- time-box validation/fix loops
- prioritize blockers over polish
- use QA evidence to make pulse decisions

### Strategy Agent capabilities needed
- write acceptance criteria QA can verify
- define out-of-scope explicitly
- avoid ambiguous “nice-to-have” requirements in 1-hour cycles

### Data Agent capabilities needed
- aggregate test/build outcomes and defects
- summarize progress vs acceptance checklist
- surface recurring blockers/drift

---

## Decision Rule for Early 1-Hour Cycles
Use this rule unless the cycle explicitly targets test automation:

> QA should write **acceptance checks first**, not necessarily a full automated test suite first.

This is the default behavior for early `group_run` cycles.

---

## Risks and Tradeoffs

### Risk: too little automation
If QA remains manual-only for too long, regressions will grow as scope expands.

**Mitigation**
- promote repeatable checks into smoke automation in subsequent cycles
- define a maturity plan (Stage A → B → C)

### Risk: acceptance checklist too vague
If QA checks are vague, Bob/Dev may still drift.

**Mitigation**
- tie checklist directly to Micro-PRD acceptance criteria
- require observable pass/fail wording

### Risk: over-automation too early
QA may still invest too much time in brittle tests before implementation stabilizes.

**Mitigation**
- make smoke skeleton optional and time-boxed
- prioritize runability and one happy path

---

## Suggested Next Step
Create a companion artifact:
- **`group_run` 1-Hour Micro-PRD / Execution Brief**
- plus a **QA Acceptance Checklist template**

These two artifacts together will give the squad a much better chance at a successful first long-run attempt.

---

## Candidate Follow-on SIP Topics
- QA acceptance checklist schema for SquadOps cycles
- Pulse Check gate decisions based on QA/Data evidence
- Test ownership policy (QA vs Bob/Dev)
- Maturity-based testing progression (Stage A/B/C)
