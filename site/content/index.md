# Squad Ops

**A multi-agent framework that turns a written requirement into a verified
application** — running on local open-weight models, against a design the squad
authored rather than one it was handed.

## What separates it

Assuming you already know what agent orchestration is, four things are unusual
here.

### The design is authored, then gated

Most frameworks orchestrate *implementation* against a design a human supplied.
Here the squad produces the interface design itself — entities, endpoints, error
contracts, screens — and that design passes two automated gates before any code
is written: is it structurally complete, and is it **winnable**, meaning the
thing it describes can actually be built and verified.

A design that cannot be won is rejected in seconds, rather than an hour into a
build that was never going to converge.

### Only executed checks count

A check that did not run is recorded as `blocked_unverified` — never as a pass,
never silently as a failure. Every cycle publishes what was verified, what
failed, what never executed, and what has been chronically inert across runs.

This is the load-bearing decision in the system. A framework that lets an unrun
check read as green cannot tell you anything true about its own output —
including whether it is getting better.

### The claims are measured, not demonstrated

Results come from windows whose size, inputs, deployment hash and scoring rule
are frozen **before the first run**, so a number cannot be improved by re-rolling
until it looks good. The most recent: a squad-authored design produced a working
application with no human intervention in **4 of 6** registered runs, with the
scoring instrument's own error disclosed on the record.

[The full evidence, and what it does not show](evidence.md){ .md-button }

### Work is addressed to roles, not personalities

A capability declares which roles may fulfil it; a squad profile decides which
agent instance and model fills each role. Agent ids are queue addresses, not
behaviour — swap one and the cycle is unchanged, provided the role is still
filled. There is no character to prompt-engineer.

---

## The thesis

Give a small model more structure instead of giving it more parameters.

Everything runs on locally hosted open-weight models — no hosted API, no
per-token cost, nothing leaving the machine. The reference deployment is a Qwen
27B model on an NVIDIA DGX Spark. That constraint is the point: effort goes into
scaffolding, verification and correction rather than into a larger model.

Whether structure can substitute for scale is the open question the project
exists to answer, and the measurement programme is how it gets answered.

---

## Where to go

<div class="grid cards" markdown>

-   **[Evidence](evidence.md)**

    Method, results, and the boundary of what they support.

-   **[Key concepts](key-concepts.md)**

    Cycles, runs, tasks, gates; capabilities, roles, squad profiles.

-   **[Getting started](getting-started.md)**

    Install, bootstrap, run your first cycle.

-   **[Architecture](architecture.md)**

    Ports and adapters, distributed execution, dependency choices.

-   **[Roadmap](roadmap.md)**

    What ships next, and what each release has to earn first.

-   **[Improvement proposals](design/sips/index.md)**

    Every architectural decision, recorded and searchable.

</div>

---

Squad Ops is a research project under active development, not a product. It is
built in the open at
[backspring-labs/squad-ops](https://github.com/backspring-labs/squad-ops), where
every architectural decision is filed as a proposal and every release carries
the evidence it was cut on.
