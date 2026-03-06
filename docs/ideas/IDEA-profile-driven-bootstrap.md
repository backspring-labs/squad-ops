# IDEA: Profile-Driven Bootstrap

## Status
Draft

## Intent
Explore a profile-driven approach to environment bootstrap and validation so SquadOps can support multiple development, local, and cloud targets with less setup friction and less hidden dependency risk.

This IDEA is intentionally focused on **intent, principles, and recommendations** rather than detailed implementation. The exact profile structures, existing scripts, and current runtime requirements should be treated as the real source of truth during SIP authoring.

---

## Why this matters
A repo clone plus `pip install` only addresses Python-level dependencies. It does not fully address the broader environment contract that a system like SquadOps may rely on, such as container tooling, local model runtimes, GPU-related support, platform-specific utilities, or cloud-facing tooling.

As SquadOps expands across different machine types and deployment paths, the setup experience can become harder to understand, harder to validate, and more prone to drift unless the expected environment is made more explicit.

This is not just a convenience problem. It directly affects reproducibility, onboarding quality, and confidence in longer-running execution paths.

---

## Core idea
Leverage the existing profile concept, where appropriate, as the anchor for environment expectations.

Rather than maintaining one set of assumptions for runtime behavior and another informal set of assumptions for machine setup, the platform should move toward a model where a selected profile helps answer three questions:

1. What kind of environment is this?
2. What capabilities does that environment need to provide?
3. How do we confirm that the environment is ready?

The aim is **alignment**, not over-design.

---

## Key principles

### 1. Treat Python and system dependencies as different concerns
Python package installation is only one layer of setup. Host-level and runtime-level requirements should be declared and validated through a different mechanism.

### 2. Keep profiles as the conceptual center of gravity
If profiles already represent meaningful environment choices, they are the natural place to connect environment expectations to setup and validation behavior.

### 3. Prefer capability-driven behavior over hard-coded environment branching
The system should ideally respond to what an environment needs, not only to the name of a profile. The exact shape of that model can be defined later based on what already exists.

### 4. Separate installation from validation
Provisioning and verification should be related, but not conflated. One concern prepares the machine. The other confirms that the machine satisfies the expected contract.

### 5. Avoid forcing uniformity where environments are genuinely different
Mac development, Windows development, Linux development, local hardware targets, and cloud targets may need different treatment. The design should unify the experience where helpful, without pretending every environment should behave identically.

### 6. Minimize hidden assumptions
A newcomer should not have to discover critical non-Python dependencies by trial and error.

### 7. Stay incremental
This should build on existing structures and conventions rather than introducing a parallel setup architecture unless the current codebase truly requires it.

---

## Recommended direction

### A. Make environment expectations more explicit
Wherever the profile model lives today, consider extending or associating it with enough information to describe the expected environment at a high level.

Not every detail needs to be captured immediately. The important shift is that environment setup stops being tribal knowledge and becomes part of the platform's declared operating assumptions.

### B. Introduce a bootstrap path
Create a clear bootstrap path for users that helps prepare a machine for the selected environment.

That bootstrap path does not need to solve every problem in its first version. Even a modest, well-scoped bootstrap capability would be a major improvement if it makes the required system dependencies and setup steps more consistent.

### C. Introduce a doctor or preflight path
Add a validation path that checks whether the selected environment is ready.

The value here is not only catching missing software. It is also catching mismatches between the chosen environment profile and the actual machine state before a run begins.

### D. Keep the user experience simple
Whatever the internal design becomes, the outer experience should feel straightforward:
- choose an environment
- bootstrap if needed
- validate readiness
- proceed

### E. Keep the design adaptable
The current set of supported environments may continue to evolve. The model should be flexible enough to support that evolution without requiring a major redesign each time a new target is added.

---

## What this should accomplish
A good outcome would look something like this:

- a new user can understand what kind of environment they are setting up
- required non-Python dependencies are surfaced earlier
- setup becomes more repeatable across supported targets
- validation becomes more precise and environment-aware
- operational confidence improves before longer runs are attempted
- the platform has a cleaner path for supporting multiple machine classes over time

---

## What this IDEA is **not** trying to lock down yet
This IDEA is not meant to prematurely fix:

- the exact schema of profiles
- the exact bootstrap script layout
- the exact set of supported package managers or installers
- the exact command surface
- the exact runtime dependency matrix for every target
- the exact division between required and optional tooling in each environment

Those specifics should come from a repo-aware SIP review that inspects the current implementation, conventions, and real profile/capability needs.

---

## Risks to avoid

### Over-specifying too early
It is easy to invent a clean model on paper that does not actually match the repo, the current profile system, or the real operational needs.

### Turning profiles into an unreadable rules engine
Profiles should help simplify intent, not become a dumping ground for uncontrolled complexity.

### Coupling too tightly to one current machine path
The immediate DGX Spark move is a strong motivator, but the design should remain useful across the broader environment set.

### Building a large installer before clarifying the contract
A bootstrap mechanism will be healthier if it is driven by a clear understanding of environment expectations rather than growing organically through one-off exceptions.

---

## Suggested framing for a later SIP
If this moves forward, the SIP should answer questions such as:

- What environment concepts already exist in SquadOps today?
- What setup responsibilities are currently implicit rather than declared?
- Which existing profile or deployment mechanisms can be reused?
- What is the minimum viable contract for bootstrap?
- What is the minimum viable contract for doctor/preflight?
- Which environments should be treated as first-class first?
- How should optional vs required dependencies be represented?
- How should the design support future expansion without excessive complexity?

---

## Recommendation
Proceed with this as a directional improvement area:

- make environment expectations more explicit
- align those expectations with the profile model where possible
- introduce a bootstrap concept
- introduce a doctor/preflight concept
- keep the first implementation narrow, practical, and grounded in the existing codebase

The strongest version of this idea is not a highly prescriptive install framework. It is a clearer platform contract for what each environment is expected to provide, plus a more reliable way to prepare and validate that environment.

---

## Notes
This IDEA assumes there is meaningful value in connecting bootstrap and validation behavior to the existing profile strategy, but it does **not** assume the final design details. Those should be informed by the current repo structure, current deployment profile implementation, and the actual dependency surface already present in SquadOps.
