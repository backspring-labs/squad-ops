# How it works

A **cycle** is one governed pass from requirement to application. It runs as a
sequence of workloads, each with its own agents, artifacts, and approval gates.

## 1. Framing — the squad authors the design

The squad reads the requirement and produces an **interface manifest**: the
entities, endpoints, error contracts, and screens the application will have.

This is the step that separates Squad Ops from a code generator. The design is
not supplied; it is written by the agents and then checked before anything is
built:

- **Schema gate** — does it parse, and is it structurally complete?
- **Winnability gate** — is the thing it describes actually *buildable and
  verifiable*? Does the skeleton expand, does the derived contract have a
  satisfiable set of checks, do the fill slots enumerate, do the test anchors
  cover the screens it promises?

A design that cannot be won is rejected before a single implementation task is
dispatched — which is the difference between failing in seconds and failing an
hour later.

## 2. Review — only when it is needed

The cycle stops for a human when the authored design records a genuinely
**unresolved question** — the squad saying the requirement does not determine
something, and declining to guess.

When there are no open questions, it proceeds without stopping. This is
deliberate. An earlier version reviewed every design, and the reviews became
rubber stamps that discussed facts the automated gates had already proven, while
a real unresolved question sat unsurfaced. A gate that is always approved
teaches nobody anything, and it makes a later reader unable to tell a considered
approval from a reflex.

## 3. Implementation — fill the slots

The accepted design expands into a **skeleton**: some files are frozen, others
are slots to be filled. Agents write into the slots. The frozen parts stay
frozen, and an attempt to write outside them is caught rather than merged.

## 4. Verification — execute, don't assume

Tests are **executed**, not merely authored. The application is installed,
built, booted, and probed over real HTTP against the contract derived from the
design.

!!! info "The rule that holds the rest up"

    Only checks that **executed and passed** count as verified. A check that did
    not run is recorded as `blocked_unverified` — never as a pass. Every cycle
    publishes an outcome disclosing what was verified, what was waived, what was
    never executed, and what has been chronically inert.

    This sounds obvious and is the single most load-bearing decision in the
    system. A framework that lets an unrun check read as green cannot tell you
    anything true about its own output — including whether it is improving.

## 5. Correction — bounded, and aimed

When something fails, the failure evidence is classified before anything is
repaired: is the defect in the application, in the test suite, or in the
machinery doing the measuring? Those route to different fixes, and confusing
them burns attempts.

Repairs run for a bounded number of rounds, carrying the failure evidence
forward so a later attempt knows what the earlier one was told.

---

## The squad

Six agents, each with a role, coordinated over a message queue.

| Agent | Role | Responsibility |
|---|---|---|
| Max | Lead | Orchestration, correction decisions, gate closeout |
| Nat | Strategy | Requirement framing, objective definition |
| Neo | Development | Interface design, implementation |
| Bob | Builder | Assembly of build artifacts into a runnable project |
| Eve | Quality | Test authoring, execution, verification |
| Data | Analytics | Failure analysis, evidence gathering, cycle assessment |

Squad composition is a **profile**, not a hardcoded roster:

| Profile | Model | Purpose |
|---|---|---|
| `smoke` | 3B | Liveness and plumbing only. Not a quality signal. |
| `lite` | 7B | The whole pipeline, cheaply. Framework validation. |
| `full` | 27B | The quality squad. What measurements are run on. |
